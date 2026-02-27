"""
Scheduler service for automated jobs (budget alerts, audits, remediations).
Uses APScheduler for cron-based job scheduling.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from sqlalchemy.orm import Session

from app.database.base import SessionLocal, engine
from app.services.budget_notification_service import BudgetNotificationService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing scheduled automation jobs."""

    _scheduler: Optional[BackgroundScheduler] = None
    _is_running = False

    @classmethod
    def initialize(cls, database_url: str):
        """
        Initialize the scheduler with job store and executors.

        Args:
            database_url: SQLAlchemy database URL for job persistence
        """
        if cls._scheduler is not None:
            logger.warning("Scheduler already initialized")
            return

        # Configure job stores and executors
        jobstores = {
            'default': SQLAlchemyJobStore(url=database_url)
        }

        executors = {
            'default': ThreadPoolExecutor(10)
        }

        job_defaults = {
            'coalesce': True,  # Combine missed runs
            'max_instances': 1,  # Prevent concurrent runs
            'misfire_grace_time': 300  # 5 minutes grace period
        }

        cls._scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        logger.info("Scheduler initialized successfully")

    @classmethod
    def start(cls):
        """Start the scheduler."""
        if cls._scheduler is None:
            raise RuntimeError("Scheduler not initialized. Call initialize() first.")

        if not cls._is_running:
            cls._scheduler.start()
            cls._is_running = True
            logger.info("Scheduler started")

            # Log all scheduled jobs
            jobs = cls._scheduler.get_jobs()
            logger.info(f"Loaded {len(jobs)} scheduled jobs")
            for job in jobs:
                logger.info(f"  - {job.id}: {job.name} (next run: {job.next_run_time})")

    @classmethod
    def shutdown(cls, wait: bool = True):
        """Shutdown the scheduler."""
        if cls._scheduler and cls._is_running:
            cls._scheduler.shutdown(wait=wait)
            cls._is_running = False
            logger.info("Scheduler shutdown")

    @classmethod
    def is_running(cls) -> bool:
        """Check if scheduler is running."""
        return cls._is_running

    # ========== Budget Alert Jobs ==========

    @staticmethod
    def _run_budget_alerts():
        """Execute budget alert check (called by scheduler)."""
        db = SessionLocal()
        try:
            logger.info("Running scheduled budget alert check...")
            result = BudgetNotificationService.check_and_send_budget_alerts(db)
            logger.info(
                f"Budget alert check complete: "
                f"{result['notifications_sent']} notifications sent, "
                f"{result['budgets_checked']} budgets checked, "
                f"{len(result.get('errors', []))} errors"
            )
        except Exception as e:
            logger.error(f"Error running budget alert check: {e}", exc_info=True)
        finally:
            db.close()

    @classmethod
    def schedule_budget_alerts(
        cls,
        job_id: str = "budget-alerts-default",
        cron_expression: str = "0 */6 * * *",  # Every 6 hours
        enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Schedule automated budget alert checks.

        Args:
            job_id: Unique identifier for this job
            cron_expression: Cron expression (default: every 6 hours)
            enabled: Whether to enable the job immediately

        Returns:
            Job info dictionary
        """
        if cls._scheduler is None:
            raise RuntimeError("Scheduler not initialized")

        # Parse cron expression
        # Format: "minute hour day month day_of_week"
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron expression. Expected: 'minute hour day month day_of_week'")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone='UTC'
        )

        # Remove existing job if it exists
        if cls._scheduler.get_job(job_id):
            cls._scheduler.remove_job(job_id)

        # Add new job
        job = cls._scheduler.add_job(
            func=cls._run_budget_alerts,
            trigger=trigger,
            id=job_id,
            name=f"Budget Alerts Check ({cron_expression})",
            replace_existing=True
        )

        if not enabled:
            job.pause()

        logger.info(f"Scheduled budget alert job: {job_id} ({cron_expression})")

        return {
            "job_id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "enabled": enabled
        }

    # ========== Audit Jobs ==========

    @staticmethod
    def _run_audit(
        account_name: str,
        audit_types: List[str],
        send_teams_notification: bool = True,
        webhook_id: Optional[int] = None
    ):
        """Execute scheduled audit (called by scheduler)."""
        db = SessionLocal()
        try:
            logger.info(f"Running scheduled audit for account: {account_name}")

            # Start async audit
            from app.schemas.audit import AuditRequest
            request = AuditRequest(
                account_name=account_name,
                audit_types=audit_types
            )

            # This would need to be implemented in audit_service to support sync execution
            # For now, log that we would trigger it
            logger.info(f"Would trigger audit with types: {audit_types}")

            # TODO: Implement sync audit execution or queue async audit
            # result = AuditService.run_sync_audit(db, request)

            # if send_teams_notification:
            #     # Send Teams notification with results
            #     pass

        except Exception as e:
            logger.error(f"Error running scheduled audit: {e}", exc_info=True)
        finally:
            db.close()

    @classmethod
    def schedule_audit(
        cls,
        job_id: str,
        account_name: str,
        cron_expression: str = "0 2 * * *",  # Daily at 2 AM
        audit_types: Optional[List[str]] = None,
        send_teams_notification: bool = True,
        webhook_id: Optional[int] = None,
        enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Schedule automated audit jobs.

        Args:
            job_id: Unique identifier for this job
            account_name: AWS account to audit
            cron_expression: Cron expression (default: daily at 2 AM)
            audit_types: List of audit types to run (None = all)
            send_teams_notification: Send notification when complete
            webhook_id: Specific webhook ID (None = all webhooks)
            enabled: Whether to enable the job immediately

        Returns:
            Job info dictionary
        """
        if cls._scheduler is None:
            raise RuntimeError("Scheduler not initialized")

        if audit_types is None:
            audit_types = ["ec2", "ebs", "eip", "tagging", "rds", "lambda", "s3", "lb"]

        # Parse cron expression
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron expression")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone='UTC'
        )

        # Remove existing job if it exists
        if cls._scheduler.get_job(job_id):
            cls._scheduler.remove_job(job_id)

        # Add new job
        job = cls._scheduler.add_job(
            func=cls._run_audit,
            trigger=trigger,
            args=[account_name, audit_types, send_teams_notification, webhook_id],
            id=job_id,
            name=f"Audit: {account_name} ({cron_expression})",
            replace_existing=True
        )

        if not enabled:
            job.pause()

        logger.info(f"Scheduled audit job: {job_id} for {account_name}")

        return {
            "job_id": job.id,
            "name": job.name,
            "account_name": account_name,
            "audit_types": audit_types,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "enabled": enabled
        }

    # ========== Job Management ==========

    @classmethod
    def list_jobs(cls) -> List[Dict[str, Any]]:
        """List all scheduled jobs."""
        if cls._scheduler is None:
            return []

        jobs = cls._scheduler.get_jobs()
        return [
            {
                "job_id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "enabled": not job.next_run_time is None
            }
            for job in jobs
        ]

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """Get specific job details."""
        if cls._scheduler is None:
            return None

        job = cls._scheduler.get_job(job_id)
        if not job:
            return None

        return {
            "job_id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
            "enabled": job.next_run_time is not None,
            "func": job.func.__name__,
            "args": job.args,
            "kwargs": job.kwargs
        }

    @classmethod
    def pause_job(cls, job_id: str) -> bool:
        """Pause a scheduled job."""
        if cls._scheduler is None:
            return False

        try:
            cls._scheduler.pause_job(job_id)
            logger.info(f"Paused job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error pausing job {job_id}: {e}")
            return False

    @classmethod
    def resume_job(cls, job_id: str) -> bool:
        """Resume a paused job."""
        if cls._scheduler is None:
            return False

        try:
            cls._scheduler.resume_job(job_id)
            logger.info(f"Resumed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error resuming job {job_id}: {e}")
            return False

    @classmethod
    def remove_job(cls, job_id: str) -> bool:
        """Remove a scheduled job."""
        if cls._scheduler is None:
            return False

        try:
            cls._scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {e}")
            return False

    @classmethod
    def run_job_now(cls, job_id: str) -> bool:
        """Trigger immediate execution of a scheduled job."""
        if cls._scheduler is None:
            return False

        try:
            job = cls._scheduler.get_job(job_id)
            if not job:
                logger.error(f"Job not found: {job_id}")
                return False

            # Execute job immediately
            job.func(*job.args, **job.kwargs)
            logger.info(f"Manually triggered job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error running job {job_id}: {e}", exc_info=True)
            return False
