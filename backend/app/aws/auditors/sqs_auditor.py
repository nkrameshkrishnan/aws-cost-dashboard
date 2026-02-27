"""
SQS cost optimization auditor.
Identifies unused queues and queues with unnecessarily high retention.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from app.schemas.audit import SQSUnusedQueue, SQSHighRetentionQueue

logger = logging.getLogger(__name__)


class SQSAuditor:
    """Auditor for SQS queues."""

    def __init__(self, session: boto3.Session, region: str):
        self.session = session
        self.region = region
        self.sqs = session.client('sqs', region_name=region)
        self.cloudwatch = session.client('cloudwatch', region_name=region)

    def audit_unused_queues(self, days: int = 30) -> List[SQSUnusedQueue]:
        """
        Find SQS queues with no message activity.

        Args:
            days: Number of days to check for activity (default: 30)

        Returns:
            List of unused queues
        """
        unused = []

        try:
            response = self.sqs.list_queues()
            queue_urls = response.get('QueueUrls', [])

            for queue_url in queue_urls:
                queue_name = queue_url.split('/')[-1]

                # Get queue attributes
                try:
                    attrs = self.sqs.get_queue_attributes(
                        QueueUrl=queue_url,
                        AttributeNames=['All']
                    )['Attributes']

                    messages_sent = int(attrs.get('ApproximateNumberOfMessages', 0))
                    messages_not_visible = int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
                    messages_delayed = int(attrs.get('ApproximateNumberOfMessagesDelayed', 0))

                    # Check CloudWatch metrics for message activity
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=days)

                    try:
                        metrics = self.cloudwatch.get_metric_statistics(
                            Namespace='AWS/SQS',
                            MetricName='NumberOfMessagesSent',
                            Dimensions=[{'Name': 'QueueName', 'Value': queue_name}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,
                            Statistics=['Sum']
                        )

                        total_sent = sum(point['Sum'] for point in metrics['Datapoints'])

                        # If no messages and no activity, mark as unused
                        if total_sent == 0 and messages_sent == 0:
                            is_fifo = queue_name.endswith('.fifo')
                            unused.append(SQSUnusedQueue(
                                queue_name=queue_name,
                                queue_url=queue_url,
                                region=self.region,
                                is_fifo=is_fifo,
                                messages_available=messages_sent,
                                total_sent_period=0,
                                days_checked=days,
                                retention_period_seconds=int(attrs.get('MessageRetentionPeriod', 0)),
                                recommendation='Delete unused queue'
                            ))
                    except ClientError as e:
                        logger.warning(f"Could not get metrics for queue {queue_name}: {e}")

                except ClientError as e:
                    logger.warning(f"Could not get attributes for queue {queue_url}: {e}")

        except ClientError as e:
            logger.error(f"Error listing SQS queues: {e}")

        return unused

    def audit_high_retention_queues(self) -> List[SQSHighRetentionQueue]:
        """
        Find SQS queues with unnecessarily high message retention (>7 days).

        Returns:
            List of queues with high retention
        """
        high_retention = []

        try:
            response = self.sqs.list_queues()
            queue_urls = response.get('QueueUrls', [])

            for queue_url in queue_urls:
                queue_name = queue_url.split('/')[-1]

                try:
                    attrs = self.sqs.get_queue_attributes(
                        QueueUrl=queue_url,
                        AttributeNames=['MessageRetentionPeriod']
                    )['Attributes']

                    retention_seconds = int(attrs.get('MessageRetentionPeriod', 0))
                    retention_days = retention_seconds / 86400

                    # Flag queues with retention > 7 days
                    if retention_days > 7:
                        high_retention.append(SQSHighRetentionQueue(
                            queue_name=queue_name,
                            queue_url=queue_url,
                            region=self.region,
                            retention_period_days=round(retention_days, 1),
                            retention_period_seconds=retention_seconds,
                            max_retention_days=14,  # AWS maximum
                            recommendation=f'Consider reducing retention from {round(retention_days, 1)} days to 3-4 days'
                        ))
                except ClientError as e:
                    logger.warning(f"Could not get attributes for queue {queue_url}: {e}")

        except ClientError as e:
            logger.error(f"Error listing SQS queues: {e}")

        return high_retention
