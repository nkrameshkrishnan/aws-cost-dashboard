"""
Automation API endpoints for managing scheduled jobs.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.scheduler_service import SchedulerService

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== Request/Response Schemas ==========

class ScheduleBudgetAlertsRequest(BaseModel):
    """Request to schedule budget alerts."""
    job_id: str = Field(default="budget-alerts-default", description="Unique job identifier")
    cron_expression: str = Field(default="0 */6 * * *", description="Cron expression (every 6 hours)")
    enabled: bool = Field(default=True, description="Enable job immediately")


class ScheduleAuditRequest(BaseModel):
    """Request to schedule audit job."""
    job_id: str = Field(..., description="Unique job identifier")
    account_name: str = Field(..., description="AWS account to audit")
    cron_expression: str = Field(default="0 2 * * *", description="Cron expression (daily at 2 AM)")
    audit_types: Optional[List[str]] = Field(
        default=None,
        description="Audit types to run (null = all)"
    )
    send_teams_notification: bool = Field(default=True, description="Send Teams notification when complete")
    webhook_id: Optional[int] = Field(default=None, description="Specific webhook ID (null = all)")
    enabled: bool = Field(default=True, description="Enable job immediately")


class JobResponse(BaseModel):
    """Job details response."""
    job_id: str
    name: str
    next_run_time: Optional[str]
    trigger: Optional[str] = None
    enabled: bool


class JobListResponse(BaseModel):
    """List of jobs response."""
    jobs: List[JobResponse]
    total: int


# ========== Endpoints ==========

@router.get("/jobs", response_model=JobListResponse)
def list_scheduled_jobs():
    """
    List all scheduled automation jobs.

    Returns:
        List of all scheduled jobs with their details
    """
    try:
        jobs = SchedulerService.list_jobs()
        return {
            "jobs": jobs,
            "total": len(jobs)
        }
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing jobs: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_details(job_id: str):
    """
    Get details of a specific scheduled job.

    Args:
        job_id: Job identifier

    Returns:
        Job details
    """
    try:
        job = SchedulerService.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}"
            )
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting job: {str(e)}"
        )


@router.post("/budget-alerts/schedule", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def schedule_budget_alerts(request: ScheduleBudgetAlertsRequest):
    """
    Schedule automated budget alert checks.

    This creates a recurring job that checks all budgets and sends Teams notifications
    when thresholds are exceeded.

    Args:
        request: Schedule configuration

    Returns:
        Created job details

    Example:
        ```
        POST /api/v1/automation/budget-alerts/schedule
        {
            "job_id": "budget-alerts-hourly",
            "cron_expression": "0 * * * *",  // Every hour
            "enabled": true
        }
        ```
    """
    try:
        result = SchedulerService.schedule_budget_alerts(
            job_id=request.job_id,
            cron_expression=request.cron_expression,
            enabled=request.enabled
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error scheduling budget alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scheduling budget alerts: {str(e)}"
        )


@router.post("/audits/schedule", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def schedule_audit(request: ScheduleAuditRequest):
    """
    Schedule automated FinOps audit jobs.

    This creates a recurring job that runs audits on the specified account
    and optionally sends results to Teams.

    Args:
        request: Schedule configuration

    Returns:
        Created job details

    Example:
        ```
        POST /api/v1/automation/audits/schedule
        {
            "job_id": "audit-prod-daily",
            "account_name": "production",
            "cron_expression": "0 2 * * *",  // Daily at 2 AM
            "audit_types": ["ec2", "ebs", "rds"],
            "send_teams_notification": true,
            "enabled": true
        }
        ```
    """
    try:
        result = SchedulerService.schedule_audit(
            job_id=request.job_id,
            account_name=request.account_name,
            cron_expression=request.cron_expression,
            audit_types=request.audit_types,
            send_teams_notification=request.send_teams_notification,
            webhook_id=request.webhook_id,
            enabled=request.enabled
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error scheduling audit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scheduling audit: {str(e)}"
        )


@router.post("/jobs/{job_id}/pause")
def pause_job(job_id: str):
    """
    Pause a scheduled job.

    Args:
        job_id: Job identifier

    Returns:
        Success message
    """
    try:
        success = SchedulerService.pause_job(job_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}"
            )
        return {"success": True, "message": f"Job paused: {job_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausing job: {str(e)}"
        )


@router.post("/jobs/{job_id}/resume")
def resume_job(job_id: str):
    """
    Resume a paused job.

    Args:
        job_id: Job identifier

    Returns:
        Success message
    """
    try:
        success = SchedulerService.resume_job(job_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}"
            )
        return {"success": True, "message": f"Job resumed: {job_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resuming job: {str(e)}"
        )


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    """
    Delete a scheduled job.

    Args:
        job_id: Job identifier

    Returns:
        Success message
    """
    try:
        success = SchedulerService.remove_job(job_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}"
            )
        return {"success": True, "message": f"Job deleted: {job_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting job: {str(e)}"
        )


@router.post("/jobs/{job_id}/run-now")
def run_job_now(job_id: str):
    """
    Trigger immediate execution of a scheduled job (doesn't affect schedule).

    Args:
        job_id: Job identifier

    Returns:
        Success message
    """
    try:
        success = SchedulerService.run_job_now(job_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found or failed to execute: {job_id}"
            )
        return {"success": True, "message": f"Job executed: {job_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running job: {str(e)}"
        )


@router.get("/status")
def get_scheduler_status():
    """
    Get scheduler status.

    Returns:
        Scheduler running status and job count
    """
    try:
        is_running = SchedulerService.is_running()
        jobs = SchedulerService.list_jobs() if is_running else []

        return {
            "running": is_running,
            "total_jobs": len(jobs),
            "active_jobs": len([j for j in jobs if j.get("enabled", False)])
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting status: {str(e)}"
        )
