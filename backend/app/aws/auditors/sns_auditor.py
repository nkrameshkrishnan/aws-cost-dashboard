"""
SNS cost optimization auditor.
Identifies unused SNS topics.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from app.schemas.audit import SNSUnusedTopic

logger = logging.getLogger(__name__)


class SNSAuditor:
    """Auditor for SNS topics."""

    def __init__(self, session: boto3.Session, region: str):
        self.session = session
        self.region = region
        self.sns = session.client('sns', region_name=region)
        self.cloudwatch = session.client('cloudwatch', region_name=region)

    def audit_unused_topics(self, days: int = 30) -> List[SNSUnusedTopic]:
        """
        Find SNS topics with no publish activity.

        Args:
            days: Number of days to check for activity (default: 30)

        Returns:
            List of unused SNS topics
        """
        unused = []

        try:
            paginator = self.sns.get_paginator('list_topics')

            for page in paginator.paginate():
                for topic in page.get('Topics', []):
                    topic_arn = topic['TopicArn']
                    topic_name = topic_arn.split(':')[-1]

                    # Get topic attributes
                    try:
                        attrs = self.sns.get_topic_attributes(TopicArn=topic_arn)['Attributes']
                        subscriptions_confirmed = int(attrs.get('SubscriptionsConfirmed', 0))
                        subscriptions_pending = int(attrs.get('SubscriptionsPending', 0))

                        # Check CloudWatch metrics for publish activity
                        end_time = datetime.utcnow()
                        start_time = end_time - timedelta(days=days)

                        try:
                            metrics = self.cloudwatch.get_metric_statistics(
                                Namespace='AWS/SNS',
                                MetricName='NumberOfMessagesPublished',
                                Dimensions=[{'Name': 'TopicName', 'Value': topic_name}],
                                StartTime=start_time,
                                EndTime=end_time,
                                Period=86400,
                                Statistics=['Sum']
                            )

                            total_published = sum(point['Sum'] for point in metrics['Datapoints'])

                            # If no messages published in period, mark as unused
                            if total_published == 0:
                                unused.append(SNSUnusedTopic(
                                    topic_name=topic_name,
                                    topic_arn=topic_arn,
                                    region=self.region,
                                    subscriptions_confirmed=subscriptions_confirmed,
                                    subscriptions_pending=subscriptions_pending,
                                    messages_published=0,
                                    days_checked=days,
                                    recommendation='Delete unused topic' if subscriptions_confirmed == 0 else 'Review topic usage'
                                ))
                        except ClientError as e:
                            logger.warning(f"Could not get metrics for topic {topic_name}: {e}")

                    except ClientError as e:
                        logger.warning(f"Could not get attributes for topic {topic_arn}: {e}")

        except ClientError as e:
            logger.error(f"Error listing SNS topics: {e}")

        return unused
