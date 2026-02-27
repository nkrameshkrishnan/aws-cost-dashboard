"""
Kinesis cost optimization auditor.
Identifies unused Kinesis streams with no data ingestion.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class KinesisAuditor:
    """Auditor for Kinesis Data Streams."""

    def __init__(self, session: boto3.Session, region: str):
        self.session = session
        self.region = region
        self.kinesis = session.client('kinesis', region_name=region)
        self.cloudwatch = session.client('cloudwatch', region_name=region)

    def audit_unused_streams(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Find Kinesis streams with no incoming data.

        Args:
            days: Number of days to check for activity (default: 7)

        Returns:
            List of unused Kinesis streams
        """
        unused = []

        try:
            paginator = self.kinesis.get_paginator('list_streams')

            for page in paginator.paginate():
                for stream_name in page.get('StreamNames', []):
                    # Get stream details
                    try:
                        stream_desc = self.kinesis.describe_stream(StreamName=stream_name)['StreamDescription']
                        stream_status = stream_desc['StreamStatus']
                        shard_count = len(stream_desc['Shards'])

                        # Calculate estimated monthly cost
                        # Standard: $0.015 per shard-hour = ~$11/month per shard
                        # Enhanced fan-out: Additional $0.015 per consumer shard-hour
                        estimated_monthly_cost = shard_count * 11

                        # Check CloudWatch metrics for incoming records
                        end_time = datetime.utcnow()
                        start_time = end_time - timedelta(days=days)

                        try:
                            metrics = self.cloudwatch.get_metric_statistics(
                                Namespace='AWS/Kinesis',
                                MetricName='IncomingRecords',
                                Dimensions=[{'Name': 'StreamName', 'Value': stream_name}],
                                StartTime=start_time,
                                EndTime=end_time,
                                Period=3600,
                                Statistics=['Sum']
                            )

                            total_records = sum(p['Sum'] for p in metrics['Datapoints'])

                            # If no incoming records, mark as unused
                            if total_records == 0:
                                unused.append({
                                    'stream_name': stream_name,
                                    'region': self.region,
                                    'stream_status': stream_status,
                                    'shard_count': shard_count,
                                    'incoming_records': 0,
                                    'days_checked': days,
                                    'estimated_monthly_cost': estimated_monthly_cost,
                                    'recommendation': 'Delete unused Kinesis stream'
                                })

                        except ClientError as e:
                            logger.warning(f"Could not get metrics for stream {stream_name}: {e}")

                    except ClientError as e:
                        logger.warning(f"Could not describe stream {stream_name}: {e}")

        except ClientError as e:
            logger.error(f"Error listing Kinesis streams: {e}")

        return unused
