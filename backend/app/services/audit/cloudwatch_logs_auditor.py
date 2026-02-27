"""
CloudWatch Logs auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from app.schemas.audit import (
    CloudWatchLogGroupLongRetention,
    CloudWatchLogGroupUnused,
    CloudWatchLogsAuditResults
)

logger = logging.getLogger(__name__)


# CloudWatch Logs pricing (USD)
CW_LOGS_INGESTION_COST_PER_GB = 0.50  # $0.50/GB ingested
CW_LOGS_STORAGE_COST_PER_GB = 0.03    # $0.03/GB/month stored
CW_LOGS_ARCHIVE_STORAGE_COST_PER_GB = 0.03  # $0.03/GB/month

# Thresholds
LONG_RETENTION_DAYS = 30  # More than 30 days is considered long
RECOMMENDED_RETENTION_DAYS = 7  # Recommend 7 days for most logs
UNUSED_THRESHOLD_DAYS = 30  # No log events in 30 days


class CloudWatchLogsAuditor:
    """Service for auditing CloudWatch Log Groups."""

    @staticmethod
    def audit_cloudwatch_logs(
        session: boto3.Session,
        long_retention_threshold: int = LONG_RETENTION_DAYS,
        unused_threshold_days: int = UNUSED_THRESHOLD_DAYS
    ) -> CloudWatchLogsAuditResults:
        """
        Audit CloudWatch Log Groups for cost optimization opportunities.

        Args:
            session: Boto3 session
            long_retention_threshold: Days threshold for long retention
            unused_threshold_days: Days without events to consider unused

        Returns:
            CloudWatchLogsAuditResults with findings
        """
        try:
            logs_client = session.client('logs')
            region = session.region_name or 'us-east-1'

            long_retention_groups = []
            unused_groups = []

            # Get all log groups
            paginator = logs_client.get_paginator('describe_log_groups')

            for page in paginator.paginate():
                log_groups = page.get('logGroups', [])

                for lg in log_groups:
                    log_group_name = lg['logGroupName']
                    retention_days = lg.get('retentionInDays', 0)  # 0 = never expire
                    stored_bytes = lg.get('storedBytes', 0)
                    stored_gb = stored_bytes / (1024 ** 3)
                    creation_time = datetime.fromtimestamp(lg.get('creationTime', 0) / 1000)

                    # Get tags
                    tags = {}
                    try:
                        tags_response = logs_client.list_tags_for_resource(
                            resourceArn=lg['arn']
                        )
                        tags = tags_response.get('tags', {})
                    except Exception:
                        pass

                    # Get last event time
                    last_event_time = CloudWatchLogsAuditor._get_last_event_time(
                        logs_client, log_group_name
                    )

                    # Check if unused (no recent events)
                    if last_event_time:
                        days_since_last_event = (datetime.now() - last_event_time).days

                        if days_since_last_event > unused_threshold_days:
                            # Calculate cost (storage only, no new ingestion)
                            monthly_storage_cost = stored_gb * CW_LOGS_STORAGE_COST_PER_GB

                            unused_lg = CloudWatchLogGroupUnused(
                                log_group_name=log_group_name,
                                stored_gb=round(stored_gb, 3),
                                retention_days=retention_days if retention_days > 0 else 9999,
                                last_event_time=last_event_time,
                                days_since_last_event=days_since_last_event,
                                estimated_monthly_cost=round(monthly_storage_cost, 2),
                                region=region,
                                tags=tags,
                                recommendation=f"Log group has no events for {days_since_last_event} days. Consider deleting to save ${monthly_storage_cost:.2f}/month."
                            )
                            unused_groups.append(unused_lg)
                            continue  # Don't check retention if already flagged as unused

                    # Check if retention is too long
                    if retention_days == 0 or retention_days > long_retention_threshold:
                        # Calculate current vs recommended storage cost
                        current_monthly_cost = stored_gb * CW_LOGS_STORAGE_COST_PER_GB

                        # Estimate savings from reducing retention to recommended days
                        if retention_days == 0:
                            # Assume data is accumulated over months
                            reduction_factor = RECOMMENDED_RETENTION_DAYS / 90  # Assume 90 days worth
                        else:
                            reduction_factor = RECOMMENDED_RETENTION_DAYS / retention_days

                        potential_savings = current_monthly_cost * (1 - reduction_factor)

                        display_retention = retention_days if retention_days > 0 else "Never Expire"

                        long_ret_lg = CloudWatchLogGroupLongRetention(
                            log_group_name=log_group_name,
                            stored_gb=round(stored_gb, 3),
                            current_retention_days=retention_days if retention_days > 0 else 9999,
                            recommended_retention_days=RECOMMENDED_RETENTION_DAYS,
                            estimated_monthly_cost=round(current_monthly_cost, 2),
                            potential_monthly_savings=round(potential_savings, 2),
                            region=region,
                            tags=tags,
                            recommendation=f"Log group has {display_retention} day retention with {stored_gb:.2f} GB stored. Reduce to {RECOMMENDED_RETENTION_DAYS} days to save ~${potential_savings:.2f}/month."
                        )
                        long_retention_groups.append(long_ret_lg)

            # Calculate totals
            total_unused_cost = sum(lg.estimated_monthly_cost for lg in unused_groups)
            total_retention_waste = sum(lg.potential_monthly_savings for lg in long_retention_groups)
            total_savings = total_unused_cost + total_retention_waste

            return CloudWatchLogsAuditResults(
                long_retention_groups=long_retention_groups,
                unused_groups=unused_groups,
                total_retention_waste=round(total_retention_waste, 2),
                total_unused_cost=round(total_unused_cost, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing CloudWatch Logs: {e}")
            return CloudWatchLogsAuditResults()

    @staticmethod
    def _get_last_event_time(logs_client, log_group_name: str) -> Optional[datetime]:
        """Get the timestamp of the last log event in a log group."""
        try:
            # Get log streams sorted by last event time
            response = logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=1
            )

            streams = response.get('logStreams', [])
            if streams and 'lastEventTime' in streams[0]:
                # Convert milliseconds to datetime
                return datetime.fromtimestamp(streams[0]['lastEventTime'] / 1000)

            return None

        except Exception as e:
            logger.warning(f"Could not get last event time for {log_group_name}: {e}")
            return None
