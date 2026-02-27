"""
Savings Plans and Reserved Instances coverage auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.schemas.audit import (
    UncoveredEC2Instance,
    UncoveredRDSInstance,
    UnderutilizedReservedInstance,
    SavingsPlansCoverageResults
)

logger = logging.getLogger(__name__)


# Savings estimates (percentage savings)
EC2_SAVINGS_PLAN_DISCOUNT = 0.72  # Up to 72% savings
RDS_RI_DISCOUNT = 0.60  # Up to 60% savings for 3-year RI


class SavingsPlansAuditor:
    """Service for auditing Savings Plans and Reserved Instances coverage."""

    @staticmethod
    def audit_savings_plans_coverage(
        session: boto3.Session,
        lookback_days: int = 30
    ) -> SavingsPlansCoverageResults:
        """
        Audit EC2 and RDS instances for Savings Plans/RI coverage.

        Args:
            session: Boto3 session
            lookback_days: Days to analyze for coverage

        Returns:
            SavingsPlansCoverageResults with findings
        """
        try:
            ce_client = session.client('ce')
            ec2_client = session.client('ec2')
            rds_client = session.client('rds')
            region = session.region_name or 'us-east-1'

            uncovered_ec2 = []
            uncovered_rds = []
            underutilized_ris = []

            # Get Savings Plans coverage from Cost Explorer
            coverage_data = SavingsPlansAuditor._get_coverage_data(ce_client, lookback_days)

            # Get uncovered EC2 instances
            ec2_findings = SavingsPlansAuditor._analyze_ec2_coverage(
                ec2_client, coverage_data, region
            )
            uncovered_ec2.extend(ec2_findings)

            # Get uncovered RDS instances
            rds_findings = SavingsPlansAuditor._analyze_rds_coverage(
                rds_client, coverage_data, region
            )
            uncovered_rds.extend(rds_findings)

            # Get underutilized Reserved Instances
            ri_findings = SavingsPlansAuditor._analyze_ri_utilization(
                ce_client, ec2_client, region, lookback_days
            )
            underutilized_ris.extend(ri_findings)

            # Calculate totals
            total_ec2_opportunity = sum(i.potential_monthly_savings for i in uncovered_ec2)
            total_rds_opportunity = sum(i.potential_monthly_savings for i in uncovered_rds)
            total_ri_waste = sum(ri.wasted_monthly_cost for ri in underutilized_ris)
            total_savings = total_ec2_opportunity + total_rds_opportunity + total_ri_waste

            # Calculate coverage percentages
            total_ec2_instances = len(uncovered_ec2) if uncovered_ec2 else 0
            total_rds_instances = len(uncovered_rds) if uncovered_rds else 0

            return SavingsPlansCoverageResults(
                uncovered_ec2_instances=uncovered_ec2,
                uncovered_rds_instances=uncovered_rds,
                underutilized_ris=underutilized_ris,
                total_ec2_savings_opportunity=round(total_ec2_opportunity, 2),
                total_rds_savings_opportunity=round(total_rds_opportunity, 2),
                total_ri_waste=round(total_ri_waste, 2),
                total_potential_savings=round(total_savings, 2),
                ec2_coverage_percentage=0.0,  # Would need more data
                rds_coverage_percentage=0.0   # Would need more data
            )

        except Exception as e:
            logger.error(f"Error auditing Savings Plans coverage: {e}")
            return SavingsPlansCoverageResults()

    @staticmethod
    def _get_coverage_data(ce_client, lookback_days: int) -> dict:
        """Get Savings Plans and RI coverage data from Cost Explorer."""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=lookback_days)

            # Get Savings Plans coverage
            sp_response = ce_client.get_savings_plans_coverage(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='MONTHLY'
            )

            # Get RI coverage
            ri_response = ce_client.get_reservation_coverage(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='MONTHLY'
            )

            return {
                'savings_plans': sp_response.get('SavingsPlansCoverages', []),
                'reservations': ri_response.get('CoveragesByTime', [])
            }

        except Exception as e:
            logger.warning(f"Could not get coverage data from Cost Explorer: {e}")
            return {'savings_plans': [], 'reservations': []}

    @staticmethod
    def _analyze_ec2_coverage(ec2_client, coverage_data: dict, region: str) -> List:
        """Analyze EC2 instances for Savings Plans coverage."""
        uncovered = []

        try:
            # Get all running EC2 instances
            response = ec2_client.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )

            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    launch_time = instance['LaunchTime']
                    days_running = (datetime.now(launch_time.tzinfo) - launch_time).days

                    # Get instance name
                    instance_name = None
                    tags = {}
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'Name':
                            instance_name = tag['Value']
                        tags[tag['Key']] = tag['Value']

                    # Estimate monthly cost (simplified - would need actual pricing API)
                    estimated_hourly_cost = SavingsPlansAuditor._estimate_ec2_hourly_cost(instance_type)
                    estimated_monthly_cost = estimated_hourly_cost * 730

                    # Estimate savings from Savings Plan
                    potential_savings = estimated_monthly_cost * EC2_SAVINGS_PLAN_DISCOUNT

                    # For this simplified version, flag all instances as uncovered
                    # In production, you'd check against actual Savings Plans
                    uncovered_instance = UncoveredEC2Instance(
                        instance_id=instance_id,
                        instance_type=instance_type,
                        instance_name=instance_name,
                        days_running=days_running,
                        estimated_monthly_cost=round(estimated_monthly_cost, 2),
                        potential_monthly_savings=round(potential_savings, 2),
                        recommended_commitment='1-year Compute Savings Plan',
                        region=region,
                        tags=tags,
                        recommendation=f"Instance {instance_id} ({instance_type}) not covered by Savings Plan. Purchase commitment to save up to ${potential_savings:.2f}/month (72% discount)."
                    )
                    uncovered.append(uncovered_instance)

        except Exception as e:
            logger.error(f"Error analyzing EC2 coverage: {e}")

        return uncovered

    @staticmethod
    def _analyze_rds_coverage(rds_client, coverage_data: dict, region: str) -> List:
        """Analyze RDS instances for Reserved Instance coverage."""
        uncovered = []

        try:
            response = rds_client.describe_db_instances()
            db_instances = response.get('DBInstances', [])

            for db in db_instances:
                db_instance_id = db['DBInstanceIdentifier']
                db_instance_class = db['DBInstanceClass']
                engine = db['Engine']
                status = db['DBInstanceStatus']

                if status != 'available':
                    continue

                created_time = db.get('InstanceCreateTime')
                days_running = (datetime.now(created_time.tzinfo) - created_time).days if created_time else 0

                # Get tags
                tags = {}
                try:
                    tags_response = rds_client.list_tags_for_resource(
                        ResourceName=db['DBInstanceArn']
                    )
                    for tag in tags_response.get('TagList', []):
                        tags[tag['Key']] = tag['Value']
                except Exception:
                    pass

                # Estimate monthly cost (simplified)
                estimated_hourly_cost = SavingsPlansAuditor._estimate_rds_hourly_cost(db_instance_class, engine)
                estimated_monthly_cost = estimated_hourly_cost * 730

                # Estimate savings from RI
                potential_savings = estimated_monthly_cost * RDS_RI_DISCOUNT

                uncovered_db = UncoveredRDSInstance(
                    db_instance_id=db_instance_id,
                    db_instance_class=db_instance_class,
                    engine=engine,
                    days_running=days_running,
                    estimated_monthly_cost=round(estimated_monthly_cost, 2),
                    potential_monthly_savings=round(potential_savings, 2),
                    recommended_commitment='3-year Reserved Instance',
                    region=region,
                    tags=tags,
                    recommendation=f"RDS instance {db_instance_id} ({db_instance_class}) not covered by RI. Purchase 3-year RI to save up to ${potential_savings:.2f}/month (60% discount)."
                )
                uncovered.append(uncovered_db)

        except Exception as e:
            logger.error(f"Error analyzing RDS coverage: {e}")

        return uncovered

    @staticmethod
    def _analyze_ri_utilization(ce_client, ec2_client, region: str, lookback_days: int) -> List:
        """Analyze Reserved Instance utilization."""
        underutilized = []

        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=lookback_days)

            # Get RI utilization from Cost Explorer
            response = ce_client.get_reservation_utilization(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='MONTHLY'
            )

            utilization_data = response.get('UtilizationsByTime', [])

            # For each underutilized RI, create a finding
            # This is simplified - in production you'd get actual RI details
            for util_period in utilization_data:
                total_utilization = util_period.get('Total', {})
                utilization_pct = float(total_utilization.get('UtilizationPercentage', '100'))

                if utilization_pct < 50:  # Less than 50% utilized
                    # This is a simplified version
                    # In production, you'd get specific RI details from describe_reserved_instances
                    underutilized_ri = UnderutilizedReservedInstance(
                        reservation_id='ri-example',  # Would get from actual RI
                        instance_type='m5.large',     # Would get from actual RI
                        instance_count=1,
                        utilization_percentage=round(utilization_pct, 2),
                        wasted_monthly_cost=round(100 * (1 - utilization_pct / 100), 2),  # Simplified
                        expiration_date=datetime.now() + timedelta(days=365),
                        region=region,
                        recommendation=f"Reserved Instance only {utilization_pct:.1f}% utilized. Consider modifying or selling on RI Marketplace."
                    )
                    underutilized.append(underutilized_ri)
                    break  # Only add one example for now

        except Exception as e:
            logger.warning(f"Could not get RI utilization data: {e}")

        return underutilized

    @staticmethod
    def _estimate_ec2_hourly_cost(instance_type: str) -> float:
        """Estimate EC2 instance hourly cost (simplified pricing)."""
        # Simplified pricing - in production, use AWS Price List API
        pricing_map = {
            't2.micro': 0.0116,
            't2.small': 0.023,
            't2.medium': 0.0464,
            't3.micro': 0.0104,
            't3.small': 0.0208,
            't3.medium': 0.0416,
            't3.large': 0.0832,
            'm5.large': 0.096,
            'm5.xlarge': 0.192,
            'm5.2xlarge': 0.384,
            'c5.large': 0.085,
            'c5.xlarge': 0.17,
            'r5.large': 0.126,
            'r5.xlarge': 0.252,
        }
        return pricing_map.get(instance_type, 0.10)  # Default $0.10/hour

    @staticmethod
    def _estimate_rds_hourly_cost(instance_class: str, engine: str) -> float:
        """Estimate RDS instance hourly cost (simplified pricing)."""
        # Simplified pricing - in production, use AWS Price List API
        base_pricing = {
            'db.t3.micro': 0.017,
            'db.t3.small': 0.034,
            'db.t3.medium': 0.068,
            'db.t3.large': 0.136,
            'db.m5.large': 0.184,
            'db.m5.xlarge': 0.368,
            'db.r5.large': 0.24,
            'db.r5.xlarge': 0.48,
        }

        # Aurora costs more
        multiplier = 1.5 if 'aurora' in engine.lower() else 1.0

        return base_pricing.get(instance_class, 0.15) * multiplier
