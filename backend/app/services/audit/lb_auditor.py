"""
Load Balancer auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from app.schemas.audit import (
    LoadBalancerNoTargets,
    LoadBalancerLowTraffic,
    LoadBalancerAuditResults
)

logger = logging.getLogger(__name__)


# Load Balancer pricing (approximate monthly costs in USD for us-east-1)
LB_PRICING = {
    'application': 22.0,  # ALB: $0.0225/hour ~= $16.43/month + LCU costs
    'network': 22.0,      # NLB: $0.0225/hour ~= $16.43/month + LCU costs
    'classic': 20.0,      # CLB: $0.025/hour ~= $18.25/month
}

# Low traffic threshold (requests per day)
LOW_TRAFFIC_THRESHOLD = 100


class LoadBalancerAuditor:
    """Service for auditing Elastic Load Balancers."""

    @staticmethod
    def audit_load_balancers(
        session: boto3.Session,
        low_traffic_threshold: int = LOW_TRAFFIC_THRESHOLD,
        lookback_days: int = 7
    ) -> LoadBalancerAuditResults:
        """
        Audit Elastic Load Balancers for unused and low-traffic LBs.

        Args:
            session: Boto3 session
            low_traffic_threshold: Request count threshold for low traffic (per day)
            lookback_days: Days to look back for metrics

        Returns:
            LoadBalancerAuditResults with findings
        """
        try:
            elbv2_client = session.client('elbv2')
            elb_client = session.client('elb')  # For Classic LBs
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            lbs_no_targets = []
            lbs_low_traffic = []

            # Audit Application and Network Load Balancers
            alb_nlb_findings = LoadBalancerAuditor._audit_alb_nlb(
                elbv2_client,
                cloudwatch_client,
                region,
                low_traffic_threshold,
                lookback_days
            )
            lbs_no_targets.extend(alb_nlb_findings['no_targets'])
            lbs_low_traffic.extend(alb_nlb_findings['low_traffic'])

            # Audit Classic Load Balancers
            clb_findings = LoadBalancerAuditor._audit_classic_lb(
                elb_client,
                cloudwatch_client,
                region,
                low_traffic_threshold,
                lookback_days
            )
            lbs_no_targets.extend(clb_findings['no_targets'])
            lbs_low_traffic.extend(clb_findings['low_traffic'])

            # Calculate totals
            total_no_target_cost = sum(lb.estimated_monthly_cost for lb in lbs_no_targets)
            total_low_traffic_waste = sum(lb.potential_monthly_savings for lb in lbs_low_traffic)
            total_savings = total_no_target_cost + total_low_traffic_waste

            return LoadBalancerAuditResults(
                lbs_no_targets=lbs_no_targets,
                lbs_low_traffic=lbs_low_traffic,
                total_no_target_cost=round(total_no_target_cost, 2),
                total_low_traffic_waste=round(total_low_traffic_waste, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing load balancers: {e}")
            return LoadBalancerAuditResults()

    @staticmethod
    def _audit_alb_nlb(
        elbv2_client,
        cloudwatch_client,
        region: str,
        low_traffic_threshold: int,
        lookback_days: int
    ) -> dict:
        """Audit Application and Network Load Balancers."""
        no_targets = []
        low_traffic = []

        try:
            # Get all ALBs and NLBs
            response = elbv2_client.describe_load_balancers()
            load_balancers = response.get('LoadBalancers', [])

            for lb in load_balancers:
                lb_name = lb['LoadBalancerName']
                lb_arn = lb['LoadBalancerArn']
                lb_type = lb['Type']  # application or network
                created_time = lb['CreatedTime']
                days_active = (datetime.now(created_time.tzinfo) - created_time).days

                # Get tags
                tags = {}
                try:
                    tags_response = elbv2_client.describe_tags(ResourceArns=[lb_arn])
                    for tag_desc in tags_response.get('TagDescriptions', []):
                        for tag in tag_desc.get('Tags', []):
                            tags[tag['Key']] = tag['Value']
                except Exception as e:
                    logger.warning(f"Could not get tags for {lb_name}: {e}")

                # Check for target groups
                target_groups_response = elbv2_client.describe_target_groups(
                    LoadBalancerArn=lb_arn
                )
                target_groups = target_groups_response.get('TargetGroups', [])

                has_healthy_targets = False
                for tg in target_groups:
                    tg_arn = tg['TargetGroupArn']
                    health_response = elbv2_client.describe_target_health(
                        TargetGroupArn=tg_arn
                    )
                    targets = health_response.get('TargetHealthDescriptions', [])
                    healthy_targets = [t for t in targets if t['TargetHealth']['State'] == 'healthy']
                    if healthy_targets:
                        has_healthy_targets = True
                        break

                # Flag LBs with no healthy targets
                if not has_healthy_targets:
                    monthly_cost = LB_PRICING.get(lb_type, 22.0)

                    no_target_lb = LoadBalancerNoTargets(
                        lb_name=lb_name,
                        lb_arn=lb_arn,
                        lb_type=lb_type,
                        created_time=created_time,
                        days_active=days_active,
                        estimated_monthly_cost=monthly_cost,
                        region=region,
                        tags=tags,
                        recommendation=f"{lb_type.upper()} has no healthy targets for {days_active} days. Consider deleting to save ${monthly_cost:.2f}/month."
                    )
                    no_targets.append(no_target_lb)
                else:
                    # Check for low traffic
                    avg_request_count = LoadBalancerAuditor._get_avg_request_count(
                        cloudwatch_client,
                        lb_arn,
                        lb_type,
                        lookback_days
                    )

                    if avg_request_count is not None and avg_request_count < low_traffic_threshold:
                        monthly_cost = LB_PRICING.get(lb_type, 22.0)
                        # Potential savings: full cost if very low traffic
                        potential_savings = monthly_cost if avg_request_count < 10 else monthly_cost * 0.5

                        low_traffic_lb = LoadBalancerLowTraffic(
                            lb_name=lb_name,
                            lb_arn=lb_arn,
                            lb_type=lb_type,
                            created_time=created_time,
                            avg_request_count=round(avg_request_count, 0),
                            avg_processed_bytes=0.0,  # Would need additional metric
                            estimated_monthly_cost=monthly_cost,
                            potential_monthly_savings=potential_savings,
                            region=region,
                            tags=tags,
                            recommendation=f"{lb_type.upper()} has only {avg_request_count:.0f} requests/day (very low traffic). Consider consolidating or deleting to save ~${potential_savings:.2f}/month."
                        )
                        low_traffic.append(low_traffic_lb)

        except Exception as e:
            logger.error(f"Error auditing ALB/NLB: {e}")

        return {'no_targets': no_targets, 'low_traffic': low_traffic}

    @staticmethod
    def _audit_classic_lb(
        elb_client,
        cloudwatch_client,
        region: str,
        low_traffic_threshold: int,
        lookback_days: int
    ) -> dict:
        """Audit Classic Load Balancers."""
        no_targets = []
        low_traffic = []

        try:
            response = elb_client.describe_load_balancers()
            load_balancers = response.get('LoadBalancerDescriptions', [])

            for lb in load_balancers:
                lb_name = lb['LoadBalancerName']
                created_time = lb['CreatedTime']
                days_active = (datetime.now(created_time.tzinfo) - created_time).days

                # Get tags
                tags = {}
                try:
                    tags_response = elb_client.describe_tags(LoadBalancerNames=[lb_name])
                    for tag_desc in tags_response.get('TagDescriptions', []):
                        for tag in tag_desc.get('Tags', []):
                            tags[tag['Key']] = tag['Value']
                except Exception as e:
                    logger.warning(f"Could not get tags for CLB {lb_name}: {e}")

                # Check for instances
                instances = lb.get('Instances', [])
                has_healthy_instances = False

                if instances:
                    health_response = elb_client.describe_instance_health(
                        LoadBalancerName=lb_name
                    )
                    healthy_instances = [
                        i for i in health_response.get('InstanceStates', [])
                        if i['State'] == 'InService'
                    ]
                    has_healthy_instances = bool(healthy_instances)

                # Flag CLBs with no healthy instances
                if not has_healthy_instances:
                    monthly_cost = LB_PRICING['classic']

                    no_target_lb = LoadBalancerNoTargets(
                        lb_name=lb_name,
                        lb_arn=f"classic:{lb_name}",  # CLBs don't have ARNs
                        lb_type='classic',
                        created_time=created_time,
                        days_active=days_active,
                        estimated_monthly_cost=monthly_cost,
                        region=region,
                        tags=tags,
                        recommendation=f"Classic LB has no healthy instances. Consider migrating to ALB/NLB or deleting to save ${monthly_cost:.2f}/month."
                    )
                    no_targets.append(no_target_lb)
                else:
                    # Check for low traffic
                    avg_request_count = LoadBalancerAuditor._get_avg_request_count_classic(
                        cloudwatch_client,
                        lb_name,
                        lookback_days
                    )

                    if avg_request_count is not None and avg_request_count < low_traffic_threshold:
                        monthly_cost = LB_PRICING['classic']
                        potential_savings = monthly_cost if avg_request_count < 10 else monthly_cost * 0.5

                        low_traffic_lb = LoadBalancerLowTraffic(
                            lb_name=lb_name,
                            lb_arn=f"classic:{lb_name}",
                            lb_type='classic',
                            created_time=created_time,
                            avg_request_count=round(avg_request_count, 0),
                            avg_processed_bytes=0.0,
                            estimated_monthly_cost=monthly_cost,
                            potential_monthly_savings=potential_savings,
                            region=region,
                            tags=tags,
                            recommendation=f"Classic LB with very low traffic ({avg_request_count:.0f} requests/day). Consider migrating to ALB or deleting to save ~${potential_savings:.2f}/month."
                        )
                        low_traffic.append(low_traffic_lb)

        except Exception as e:
            logger.error(f"Error auditing Classic LBs: {e}")

        return {'no_targets': no_targets, 'low_traffic': low_traffic}

    @staticmethod
    def _get_avg_request_count(
        cloudwatch_client,
        lb_arn: str,
        lb_type: str,
        lookback_days: int
    ) -> Optional[float]:
        """Get average request count per day for ALB/NLB."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            # Extract LB name from ARN
            lb_full_name = lb_arn.split(':loadbalancer/')[1]

            metric_name = 'RequestCount' if lb_type == 'application' else 'ActiveFlowCount'

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ApplicationELB' if lb_type == 'application' else 'AWS/NetworkELB',
                MetricName=metric_name,
                Dimensions=[
                    {'Name': 'LoadBalancer', 'Value': lb_full_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                avg_per_day = sum(dp['Sum'] for dp in datapoints) / len(datapoints)
                return avg_per_day
            return None

        except Exception as e:
            logger.warning(f"Could not get request count for LB: {e}")
            return None

    @staticmethod
    def _get_avg_request_count_classic(
        cloudwatch_client,
        lb_name: str,
        lookback_days: int
    ) -> Optional[float]:
        """Get average request count per day for Classic LB."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=lookback_days)

            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/ELB',
                MetricName='RequestCount',
                Dimensions=[
                    {'Name': 'LoadBalancerName', 'Value': lb_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                avg_per_day = sum(dp['Sum'] for dp in datapoints) / len(datapoints)
                return avg_per_day
            return None

        except Exception as e:
            logger.warning(f"Could not get request count for Classic LB {lb_name}: {e}")
            return None
