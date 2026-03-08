"""
Pydantic schemas for Automation API endpoints.

These models define the request/response structure for:
- Scheduled job management
- Budget alert scheduling
- Audit scheduling
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ScheduleBudgetAlertsRequest(BaseModel):
    """Request to schedule budget alerts."""
    job_id: str = Field(
        default="budget-alerts-default",
        description="Unique job identifier"
    )
    cron_expression: str = Field(
        default="0 */6 * * *",
        description="Cron expression (default: every 6 hours)"
    )
    enabled: bool = Field(
        default=True,
        description="Enable job immediately after creation"
    )


class ScheduleAuditRequest(BaseModel):
    """Request to schedule audit job."""
    job_id: str = Field(
        ...,
        description="Unique job identifier"
    )
    account_name: str = Field(
        ...,
        description="AWS account to audit"
    )
    cron_expression: str = Field(
        default="0 2 * * *",
        description="Cron expression (default: daily at 2 AM)"
    )
    audit_types: Optional[List[str]] = Field(
        default=None,
        description="Audit types to run (null = all types)"
    )
    send_teams_notification: bool = Field(
        default=True,
        description="Send Teams notification when complete"
    )
    webhook_id: Optional[int] = Field(
        default=None,
        description="Specific webhook ID (null = all active webhooks)"
    )
    enabled: bool = Field(
        default=True,
        description="Enable job immediately after creation"
    )


class JobResponse(BaseModel):
    """Job details response."""
    job_id: str
    name: str
    next_run_time: Optional[str] = None
    trigger: Optional[str] = None
    enabled: bool


class JobListResponse(BaseModel):
    """List of jobs response."""
    jobs: List[JobResponse]
    total: int


class JobStatusResponse(BaseModel):
    """Job status response with progress details."""
    job_id: str
    status: str
    progress: int
    current_step: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict] = None