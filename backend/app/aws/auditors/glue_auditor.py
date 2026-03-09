"""
AWS Glue cost optimization auditor.
Identifies unused Glue crawlers and jobs.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from app.auditors.base import AuditorBase

logger = logging.getLogger(__name__)


class GlueAuditor(AuditorBase):
    """Auditor for AWS Glue crawlers and jobs."""

    def __init__(self, session: boto3.Session, region: str):
        super().__init__(session, region)
        self.glue = session.client('glue', region_name=region)

    def run(self, days: int = 30, **kwargs) -> dict:
        """Run all Glue audit checks."""
        return {
            'unused_crawlers': self.audit_unused_crawlers(days=days),
            'unused_jobs': self.audit_unused_jobs(days=days),
        }

    def audit_unused_crawlers(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Find Glue crawlers with no recent runs.

        Args:
            days: Number of days to check for crawler runs (default: 30)

        Returns:
            List of unused Glue crawlers
        """
        unused = []

        try:
            paginator = self.glue.get_paginator('get_crawlers')

            for page in paginator.paginate():
                for crawler in page.get('Crawlers', []):
                    crawler_name = crawler['Name']
                    crawler_state = crawler['State']
                    last_crawl = crawler.get('LastCrawl')

                    # Check if crawler has ever run
                    if last_crawl is None:
                        unused.append({
                            'crawler_name': crawler_name,
                            'region': self.region,
                            'crawler_state': crawler_state,
                            'last_crawl_status': 'NEVER_RUN',
                            'days_since_last_crawl': None,
                            'recommendation': 'Delete crawler that has never been run'
                        })
                    else:
                        completed_on = last_crawl.get('CompletedOn')
                        if completed_on:
                            days_since = (datetime.now(completed_on.tzinfo) - completed_on).days

                            if days_since > days:
                                unused.append({
                                    'crawler_name': crawler_name,
                                    'region': self.region,
                                    'crawler_state': crawler_state,
                                    'last_crawl_status': last_crawl.get('Status'),
                                    'days_since_last_crawl': days_since,
                                    'last_crawl_date': completed_on.isoformat(),
                                    'recommendation': f'No crawls in {days} days - consider deleting'
                                })

        except ClientError as e:
            logger.error(f"Error listing Glue crawlers: {e}")

        return unused

    def audit_unused_jobs(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Find Glue ETL jobs with no recent runs.

        Args:
            days: Number of days to check for job runs (default: 30)

        Returns:
            List of unused Glue jobs
        """
        unused = []

        try:
            paginator = self.glue.get_paginator('get_jobs')

            for page in paginator.paginate():
                for job in page.get('Jobs', []):
                    job_name = job['Name']
                    max_capacity = job.get('MaxCapacity')
                    worker_type = job.get('WorkerType')
                    number_of_workers = job.get('NumberOfWorkers')

                    # Get job runs to check for recent activity
                    try:
                        runs_response = self.glue.get_job_runs(
                            JobName=job_name,
                            MaxResults=1
                        )

                        job_runs = runs_response.get('JobRuns', [])

                        if len(job_runs) == 0:
                            # Job has never been run
                            unused.append({
                                'job_name': job_name,
                                'region': self.region,
                                'worker_type': worker_type,
                                'number_of_workers': number_of_workers,
                                'max_capacity': max_capacity,
                                'last_run_status': 'NEVER_RUN',
                                'days_since_last_run': None,
                                'recommendation': 'Delete job that has never been run'
                            })
                        else:
                            latest_run = job_runs[0]
                            started_on = latest_run.get('StartedOn')

                            if started_on:
                                days_since = (datetime.now(started_on.tzinfo) - started_on).days

                                if days_since > days:
                                    unused.append({
                                        'job_name': job_name,
                                        'region': self.region,
                                        'worker_type': worker_type,
                                        'number_of_workers': number_of_workers,
                                        'max_capacity': max_capacity,
                                        'last_run_status': latest_run.get('JobRunState'),
                                        'days_since_last_run': days_since,
                                        'last_run_date': started_on.isoformat(),
                                        'recommendation': f'No runs in {days} days - consider deleting'
                                    })

                    except ClientError as e:
                        logger.warning(f"Could not get job runs for {job_name}: {e}")

        except ClientError as e:
            logger.error(f"Error listing Glue jobs: {e}")

        return unused
