"""
Debug endpoints for troubleshooting CloudWatch metrics collection.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import logging

from app.database.base import get_db
from app.models.aws_account import AWSAccount
from app.aws.session_manager import AWSSessionManager
from app.aws.cloudwatch_metrics import CloudWatchMetricsCollector

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/cloudwatch-metrics-debug")
def debug_cloudwatch_metrics(
    profile_name: str = Query(..., description="AWS profile name"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to show CloudWatch metrics collection details.
    Shows region, EC2 instances found, and all metric values.
    """
    # Get AWS account info
    aws_account = db.query(AWSAccount).filter(AWSAccount.name == profile_name).first()
    if not aws_account:
        return {"error": f"AWS account '{profile_name}' not found"}

    region = aws_account.region if aws_account else 'us-east-1'

    try:
        session_manager = AWSSessionManager(db=db)
        session = session_manager.get_session(profile_name)

        # Get EC2 instances in the region
        ec2 = session.client('ec2', region_name=region)
        ec2_response = ec2.describe_instances()

        instances = []
        instance_count = 0
        for reservation in ec2_response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                instance_count += 1
                instances.append({
                    'instance_id': instance['InstanceId'],
                    'instance_type': instance['InstanceType'],
                    'state': instance['State']['Name'],
                    'launch_time': str(instance.get('LaunchTime', '')),
                    'availability_zone': instance['Placement']['AvailabilityZone']
                })

        # Collect CloudWatch metrics
        cloudwatch_collector = CloudWatchMetricsCollector(session, region=region)
        metrics = cloudwatch_collector.get_business_metrics(start_date, end_date)

        return {
            "account_name": profile_name,
            "account_id": aws_account.account_id,
            "region": region,
            "date_range": f"{start_date} to {end_date}",
            "ec2_instances_found": instance_count,
            "ec2_instances": instances,
            "cloudwatch_metrics": metrics,
            "debug_info": {
                "api_gateway_requests": metrics['breakdown']['api_gateway_requests'],
                "lambda_invocations": metrics['breakdown']['lambda_invocations'],
                "alb_requests": metrics['breakdown']['alb_requests'],
                "dynamodb_requests": metrics['breakdown']['dynamodb_requests'],
                "s3_gb": metrics['breakdown']['s3_gb'],
                "cloudfront_gb": metrics['breakdown']['cloudfront_gb'],
                "ec2_instance_hours": metrics['breakdown']['ec2_instance_hours']
            }
        }

    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "account_name": profile_name,
            "region": region
        }
