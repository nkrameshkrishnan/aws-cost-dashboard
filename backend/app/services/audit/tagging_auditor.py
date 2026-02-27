"""
Resource tagging compliance auditing service.
"""
import boto3
import logging
from typing import List, Dict, Set
from app.schemas.audit import (
    UntaggedResource,
    TaggingAuditResults
)

logger = logging.getLogger(__name__)


class TaggingAuditor:
    """Service for auditing resource tagging compliance."""

    @staticmethod
    def audit_tagging_compliance(
        session: boto3.Session,
        required_tags: List[str]
    ) -> TaggingAuditResults:
        """
        Audit resources for tagging compliance.

        Args:
            session: Boto3 session
            required_tags: List of required tag keys

        Returns:
            TaggingAuditResults with findings
        """
        try:
            region = session.region_name or 'us-east-1'
            untagged_resources = []

            # Audit EC2 instances
            untagged_resources.extend(
                TaggingAuditor._audit_ec2_tags(session, region, required_tags)
            )

            # Audit RDS instances
            untagged_resources.extend(
                TaggingAuditor._audit_rds_tags(session, region, required_tags)
            )

            # Audit Lambda functions
            untagged_resources.extend(
                TaggingAuditor._audit_lambda_tags(session, region, required_tags)
            )

            # Audit ELBs
            untagged_resources.extend(
                TaggingAuditor._audit_elb_tags(session, region, required_tags)
            )

            # Calculate compliance
            total_resources = len(untagged_resources)
            # In production, also count compliant resources to calculate percentage
            compliance_percentage = 0.0 if total_resources > 0 else 100.0

            return TaggingAuditResults(
                untagged_resources=untagged_resources,
                total_untagged=total_resources,
                compliance_percentage=round(compliance_percentage, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing tagging compliance: {e}")
            return TaggingAuditResults()

    @staticmethod
    def _audit_ec2_tags(
        session: boto3.Session,
        region: str,
        required_tags: List[str]
    ) -> List[UntaggedResource]:
        """Audit EC2 instance tags."""
        untagged = []

        try:
            ec2_client = session.client('ec2')
            response = ec2_client.describe_instances()

            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_id = instance['InstanceId']

                    # Get current tags
                    current_tags = {}
                    instance_name = None
                    for tag in instance.get('Tags', []):
                        current_tags[tag['Key']] = tag['Value']
                        if tag['Key'] == 'Name':
                            instance_name = tag['Value']

                    # Check for missing required tags
                    missing_tags = [tag for tag in required_tags if tag not in current_tags]

                    if missing_tags:
                        untagged.append(UntaggedResource(
                            resource_type='ec2',
                            resource_id=instance_id,
                            resource_name=instance_name,
                            resource_arn=f"arn:aws:ec2:{region}::instance/{instance_id}",
                            region=region,
                            missing_tags=missing_tags,
                            current_tags=current_tags,
                            recommendation=f"Add missing tags: {', '.join(missing_tags)}"
                        ))

        except Exception as e:
            logger.warning(f"Error auditing EC2 tags: {e}")

        return untagged

    @staticmethod
    def _audit_rds_tags(
        session: boto3.Session,
        region: str,
        required_tags: List[str]
    ) -> List[UntaggedResource]:
        """Audit RDS instance tags."""
        untagged = []

        try:
            rds_client = session.client('rds')
            response = rds_client.describe_db_instances()

            for db_instance in response.get('DBInstances', []):
                db_id = db_instance['DBInstanceIdentifier']
                db_arn = db_instance['DBInstanceArn']

                # Get tags
                tags_response = rds_client.list_tags_for_resource(ResourceName=db_arn)
                current_tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagList', [])}

                # Check for missing required tags
                missing_tags = [tag for tag in required_tags if tag not in current_tags]

                if missing_tags:
                    untagged.append(UntaggedResource(
                        resource_type='rds',
                        resource_id=db_id,
                        resource_name=db_id,
                        resource_arn=db_arn,
                        region=region,
                        missing_tags=missing_tags,
                        current_tags=current_tags,
                        recommendation=f"Add missing tags: {', '.join(missing_tags)}"
                    ))

        except Exception as e:
            logger.warning(f"Error auditing RDS tags: {e}")

        return untagged

    @staticmethod
    def _audit_lambda_tags(
        session: boto3.Session,
        region: str,
        required_tags: List[str]
    ) -> List[UntaggedResource]:
        """Audit Lambda function tags."""
        untagged = []

        try:
            lambda_client = session.client('lambda')
            response = lambda_client.list_functions()

            for function in response.get('Functions', []):
                function_name = function['FunctionName']
                function_arn = function['FunctionArn']

                # Get tags
                current_tags = function.get('Tags', {})

                # Check for missing required tags
                missing_tags = [tag for tag in required_tags if tag not in current_tags]

                if missing_tags:
                    untagged.append(UntaggedResource(
                        resource_type='lambda',
                        resource_id=function_name,
                        resource_name=function_name,
                        resource_arn=function_arn,
                        region=region,
                        missing_tags=missing_tags,
                        current_tags=current_tags,
                        recommendation=f"Add missing tags: {', '.join(missing_tags)}"
                    ))

        except Exception as e:
            logger.warning(f"Error auditing Lambda tags: {e}")

        return untagged

    @staticmethod
    def _audit_elb_tags(
        session: boto3.Session,
        region: str,
        required_tags: List[str]
    ) -> List[UntaggedResource]:
        """Audit ELB tags."""
        untagged = []

        try:
            elb_client = session.client('elbv2')
            response = elb_client.describe_load_balancers()

            for lb in response.get('LoadBalancers', []):
                lb_arn = lb['LoadBalancerArn']
                lb_name = lb['LoadBalancerName']

                # Get tags
                tags_response = elb_client.describe_tags(ResourceArns=[lb_arn])
                current_tags = {}
                for tag_desc in tags_response.get('TagDescriptions', []):
                    for tag in tag_desc.get('Tags', []):
                        current_tags[tag['Key']] = tag['Value']

                # Check for missing required tags
                missing_tags = [tag for tag in required_tags if tag not in current_tags]

                if missing_tags:
                    untagged.append(UntaggedResource(
                        resource_type='elb',
                        resource_id=lb_name,
                        resource_name=lb_name,
                        resource_arn=lb_arn,
                        region=region,
                        missing_tags=missing_tags,
                        current_tags=current_tags,
                        recommendation=f"Add missing tags: {', '.join(missing_tags)}"
                    ))

        except Exception as e:
            logger.warning(f"Error auditing ELB tags: {e}")

        return untagged
