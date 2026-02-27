"""
DynamoDB auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from app.schemas.audit import (
    DynamoDBUnusedTable,
    DynamoDBBillingModeOptimization,
    DynamoDBAuditResults
)

logger = logging.getLogger(__name__)


# DynamoDB pricing (USD for us-east-1)
# On-Demand: $1.25 per million write RCUs, $0.25 per million read RCUs
# Provisioned: $0.00065/hour per WCU ($0.47/month), $0.00013/hour per RCU ($0.09/month)
DYNAMODB_PROVISIONED_WCU_COST = 0.00065 * 730  # ~$0.47/month per WCU
DYNAMODB_PROVISIONED_RCU_COST = 0.00013 * 730  # ~$0.09/month per RCU
DYNAMODB_STORAGE_COST_PER_GB = 0.25  # $0.25/GB/month

# Thresholds
UNUSED_THRESHOLD_DAYS = 30
BILLING_MODE_SWITCH_THRESHOLD_READS = 1000000  # 1M consistent reads/month


class DynamoDBAuditor:
    """Service for auditing DynamoDB tables."""

    @staticmethod
    def audit_dynamodb(
        session: boto3.Session,
        unused_threshold_days: int = UNUSED_THRESHOLD_DAYS,
        lookback_days: int = 30
    ) -> DynamoDBAuditResults:
        """
        Audit DynamoDB tables for unused tables and billing mode optimization.

        Args:
            session: Boto3 session
            unused_threshold_days: Days without activity to consider unused
            lookback_days: Days to look back for metrics

        Returns:
            DynamoDBAuditResults with findings
        """
        try:
            dynamodb_client = session.client('dynamodb')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            unused_tables = []
            billing_mode_opportunities = []

            # Get all tables
            paginator = dynamodb_client.get_paginator('list_tables')
            table_names = []

            for page in paginator.paginate():
                table_names.extend(page.get('TableNames', []))

            for table_name in table_names:
                # Get table details
                table_desc = dynamodb_client.describe_table(TableName=table_name)
                table = table_desc['Table']

                table_size_bytes = table.get('TableSizeBytes', 0)
                table_size_gb = table_size_bytes / (1024 ** 3)
                item_count = table.get('ItemCount', 0)
                billing_mode = table.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED')
                table_status = table.get('TableStatus', 'UNKNOWN')
                table_arn = table['TableArn']
                creation_time = table.get('CreationDateTime')

                # Get tags
                tags = {}
                try:
                    tags_response = dynamodb_client.list_tags_of_resource(ResourceArn=table_arn)
                    for tag in tags_response.get('Tags', []):
                        tags[tag['Key']] = tag['Value']
                except Exception:
                    pass

                # Get provisioned capacity if applicable
                provisioned_read_capacity = 0
                provisioned_write_capacity = 0

                if billing_mode == 'PROVISIONED':
                    provisioned_throughput = table.get('ProvisionedThroughput', {})
                    provisioned_read_capacity = provisioned_throughput.get('ReadCapacityUnits', 0)
                    provisioned_write_capacity = provisioned_throughput.get('WriteCapacityUnits', 0)

                # Get CloudWatch metrics
                consumed_reads, consumed_writes = DynamoDBAuditor._get_consumed_capacity(
                    cloudwatch_client, table_name, lookback_days
                )

                # Check if unused (no reads or writes)
                if consumed_reads == 0 and consumed_writes == 0:
                    storage_cost = table_size_gb * DYNAMODB_STORAGE_COST_PER_GB

                    if billing_mode == 'PROVISIONED':
                        provisioned_cost = (
                            provisioned_read_capacity * DYNAMODB_PROVISIONED_RCU_COST +
                            provisioned_write_capacity * DYNAMODB_PROVISIONED_WCU_COST
                        )
                        total_cost = storage_cost + provisioned_cost
                    else:
                        total_cost = storage_cost

                    unused_table = DynamoDBUnusedTable(
                        table_name=table_name,
                        table_size_gb=round(table_size_gb, 3),
                        item_count=item_count,
                        billing_mode=billing_mode,
                        days_without_activity=lookback_days,
                        estimated_monthly_cost=round(total_cost, 2),
                        region=region,
                        tags=tags,
                        recommendation=f"Table has no read/write activity in {lookback_days} days. Consider backing up and deleting to save ${total_cost:.2f}/month."
                    )
                    unused_tables.append(unused_table)
                    continue  # Don't check billing mode if already flagged as unused

                # Check billing mode optimization
                # On-Demand → Provisioned: if traffic is consistent
                # Provisioned → On-Demand: if traffic is sporadic
                if billing_mode == 'PROVISIONED' and consumed_reads > 0:
                    # Check if under-utilized (provisioned capacity > actual usage)
                    avg_read_capacity_used = consumed_reads / (lookback_days * 86400)  # Per second
                    avg_write_capacity_used = consumed_writes / (lookback_days * 86400)

                    read_utilization = avg_read_capacity_used / provisioned_read_capacity if provisioned_read_capacity > 0 else 0
                    write_utilization = avg_write_capacity_used / provisioned_write_capacity if provisioned_write_capacity > 0 else 0

                    # If utilization is very low (<10%), switching to on-demand might save money
                    if read_utilization < 0.10 or write_utilization < 0.10:
                        current_cost = (
                            provisioned_read_capacity * DYNAMODB_PROVISIONED_RCU_COST +
                            provisioned_write_capacity * DYNAMODB_PROVISIONED_WCU_COST +
                            table_size_gb * DYNAMODB_STORAGE_COST_PER_GB
                        )

                        # Rough estimate of on-demand cost
                        monthly_read_units = consumed_reads
                        monthly_write_units = consumed_writes
                        on_demand_cost = (
                            (monthly_read_units / 1000000) * 0.25 +  # $0.25 per million RRUs
                            (monthly_write_units / 1000000) * 1.25 +  # $1.25 per million WRUs
                            table_size_gb * DYNAMODB_STORAGE_COST_PER_GB
                        )

                        potential_savings = current_cost - on_demand_cost

                        if potential_savings > 0:
                            billing_opt = DynamoDBBillingModeOptimization(
                                table_name=table_name,
                                current_billing_mode='PROVISIONED',
                                recommended_billing_mode='ON_DEMAND',
                                current_read_capacity=provisioned_read_capacity,
                                current_write_capacity=provisioned_write_capacity,
                                avg_read_utilization=round(read_utilization * 100, 2),
                                avg_write_utilization=round(write_utilization * 100, 2),
                                estimated_monthly_cost=round(current_cost, 2),
                                potential_monthly_savings=round(potential_savings, 2),
                                region=region,
                                tags=tags,
                                recommendation=f"Table has low capacity utilization (Read: {read_utilization*100:.1f}%, Write: {write_utilization*100:.1f}%). Switch to On-Demand billing to save ~${potential_savings:.2f}/month."
                            )
                            billing_mode_opportunities.append(billing_opt)

                elif billing_mode == 'PAY_PER_REQUEST' and consumed_reads > BILLING_MODE_SWITCH_THRESHOLD_READS:
                    # High consistent traffic on On-Demand → might benefit from Provisioned
                    avg_read_capacity_needed = consumed_reads / (lookback_days * 86400)
                    avg_write_capacity_needed = consumed_writes / (lookback_days * 86400)

                    # Add 20% buffer
                    recommended_rcu = int(avg_read_capacity_needed * 1.2)
                    recommended_wcu = int(avg_write_capacity_needed * 1.2)

                    # Calculate costs
                    monthly_read_units = consumed_reads
                    monthly_write_units = consumed_writes
                    current_cost = (
                        (monthly_read_units / 1000000) * 0.25 +
                        (monthly_write_units / 1000000) * 1.25 +
                        table_size_gb * DYNAMODB_STORAGE_COST_PER_GB
                    )

                    provisioned_cost = (
                        recommended_rcu * DYNAMODB_PROVISIONED_RCU_COST +
                        recommended_wcu * DYNAMODB_PROVISIONED_WCU_COST +
                        table_size_gb * DYNAMODB_STORAGE_COST_PER_GB
                    )

                    potential_savings = current_cost - provisioned_cost

                    if potential_savings > 0:
                        billing_opt = DynamoDBBillingModeOptimization(
                            table_name=table_name,
                            current_billing_mode='ON_DEMAND',
                            recommended_billing_mode='PROVISIONED',
                            current_read_capacity=0,
                            current_write_capacity=0,
                            avg_read_utilization=0.0,
                            avg_write_utilization=0.0,
                            estimated_monthly_cost=round(current_cost, 2),
                            potential_monthly_savings=round(potential_savings, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"Table has consistent high traffic. Switch to Provisioned billing (RCU: {recommended_rcu}, WCU: {recommended_wcu}) to save ~${potential_savings:.2f}/month."
                        )
                        billing_mode_opportunities.append(billing_opt)

            # Calculate totals
            total_unused_cost = sum(t.estimated_monthly_cost for t in unused_tables)
            total_billing_mode_savings = sum(t.potential_monthly_savings for t in billing_mode_opportunities)
            total_savings = total_unused_cost + total_billing_mode_savings

            return DynamoDBAuditResults(
                unused_tables=unused_tables,
                billing_mode_opportunities=billing_mode_opportunities,
                total_unused_cost=round(total_unused_cost, 2),
                total_billing_mode_savings=round(total_billing_mode_savings, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing DynamoDB: {e}")
            return DynamoDBAuditResults()

    @staticmethod
    def _get_consumed_capacity(
        cloudwatch_client,
        table_name: str,
        lookback_days: int
    ) -> tuple:
        """Get consumed read and write capacity units."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Get ConsumedReadCapacityUnits
            read_response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ConsumedReadCapacityUnits',
                Dimensions=[
                    {'Name': 'TableName', 'Value': table_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            # Get ConsumedWriteCapacityUnits
            write_response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ConsumedWriteCapacityUnits',
                Dimensions=[
                    {'Name': 'TableName', 'Value': table_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            read_datapoints = read_response.get('Datapoints', [])
            write_datapoints = write_response.get('Datapoints', [])

            total_reads = sum(dp['Sum'] for dp in read_datapoints)
            total_writes = sum(dp['Sum'] for dp in write_datapoints)

            return total_reads, total_writes

        except Exception as e:
            logger.warning(f"Could not get consumed capacity for table {table_name}: {e}")
            return 0, 0
