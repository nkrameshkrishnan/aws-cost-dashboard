"""
Pydantic schemas for Microsoft Teams webhook integration.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal
from datetime import datetime


class TeamsWebhookBase(BaseModel):
    """Base schema for Teams webhook."""
    name: str = Field(..., min_length=1, max_length=255, description="Webhook name")
    description: Optional[str] = Field(None, description="Webhook description")
    webhook_url: str = Field(..., description="Webhook URL (Teams or Power Automate)")
    webhook_type: Literal['teams', 'power_automate'] = Field('teams', description="Webhook type: teams or power_automate")
    is_active: bool = Field(True, description="Whether webhook is active")
    send_budget_alerts: bool = Field(True, description="Send budget threshold alerts")
    send_cost_summaries: bool = Field(False, description="Send daily/weekly cost summaries")
    send_audit_reports: bool = Field(False, description="Send FinOps audit reports")
    budget_threshold_percentage: int = Field(80, ge=0, le=100, description="Budget alert threshold percentage")


class TeamsWebhookCreate(TeamsWebhookBase):
    """Schema for creating a Teams webhook."""
    pass


class TeamsWebhookUpdate(BaseModel):
    """Schema for updating a Teams webhook."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_type: Optional[Literal['teams', 'power_automate']] = None
    is_active: Optional[bool] = None
    send_budget_alerts: Optional[bool] = None
    send_cost_summaries: Optional[bool] = None
    send_audit_reports: Optional[bool] = None
    budget_threshold_percentage: Optional[int] = Field(None, ge=0, le=100)


class TeamsWebhookResponse(TeamsWebhookBase):
    """Schema for Teams webhook response."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TeamsWebhookTestRequest(BaseModel):
    """Schema for testing a Teams webhook."""
    webhook_url: str = Field(..., description="Webhook URL to test")
    webhook_type: Literal['teams', 'power_automate'] = Field('teams', description="Webhook type")


class TeamsWebhookTestResponse(BaseModel):
    """Schema for webhook test response."""
    success: bool
    message: str


class TeamsSendNotificationRequest(BaseModel):
    """Schema for sending a notification to Teams."""
    webhook_id: int = Field(..., description="Webhook ID to use")
    notification_type: str = Field(..., description="Type of notification (budget_alert, cost_summary, audit_report, custom)")
    data: dict = Field(..., description="Notification data")


class TeamsSendNotificationResponse(BaseModel):
    """Schema for send notification response."""
    success: bool
    message: str
    webhook_name: str
