"""
API endpoints for Microsoft Teams webhook integration.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database.base import get_db
from app.models.teams_webhook import TeamsWebhook
from app.schemas.teams import (
    TeamsWebhookCreate,
    TeamsWebhookUpdate,
    TeamsWebhookResponse,
    TeamsWebhookTestRequest,
    TeamsWebhookTestResponse,
    TeamsSendNotificationRequest,
    TeamsSendNotificationResponse
)
from app.integrations.teams import TeamsNotificationService
from app.services.budget_notification_service import BudgetNotificationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhooks", response_model=TeamsWebhookResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    webhook: TeamsWebhookCreate,
    db: Session = Depends(get_db)
):
    """Create a new Teams webhook configuration."""
    # Check if webhook with same name already exists
    existing = db.query(TeamsWebhook).filter(TeamsWebhook.name == webhook.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook with name '{webhook.name}' already exists"
        )

    # Create new webhook
    db_webhook = TeamsWebhook(**webhook.model_dump())
    db.add(db_webhook)
    db.commit()
    db.refresh(db_webhook)

    logger.info(f"Created Teams webhook: {db_webhook.name} (ID: {db_webhook.id})")
    return db_webhook


@router.get("/webhooks", response_model=List[TeamsWebhookResponse])
def list_webhooks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all Teams webhooks."""
    webhooks = db.query(TeamsWebhook).offset(skip).limit(limit).all()
    return webhooks


@router.get("/webhooks/{webhook_id}", response_model=TeamsWebhookResponse)
def get_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific Teams webhook by ID."""
    webhook = db.query(TeamsWebhook).filter(TeamsWebhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found"
        )
    return webhook


@router.put("/webhooks/{webhook_id}", response_model=TeamsWebhookResponse)
def update_webhook(
    webhook_id: int,
    webhook_update: TeamsWebhookUpdate,
    db: Session = Depends(get_db)
):
    """Update a Teams webhook configuration."""
    db_webhook = db.query(TeamsWebhook).filter(TeamsWebhook.id == webhook_id).first()
    if not db_webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found"
        )

    # Update fields
    update_data = webhook_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_webhook, field, value)

    db.commit()
    db.refresh(db_webhook)

    logger.info(f"Updated Teams webhook: {db_webhook.name} (ID: {db_webhook.id})")
    return db_webhook


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    """Delete a Teams webhook."""
    db_webhook = db.query(TeamsWebhook).filter(TeamsWebhook.id == webhook_id).first()
    if not db_webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found"
        )

    db.delete(db_webhook)
    db.commit()

    logger.info(f"Deleted Teams webhook: {db_webhook.name} (ID: {webhook_id})")
    return None


@router.post("/test", response_model=TeamsWebhookTestResponse)
def test_webhook(
    test_request: TeamsWebhookTestRequest
):
    """Test a webhook by sending a test message."""
    try:
        success = TeamsNotificationService.test_webhook(
            test_request.webhook_url,
            test_request.webhook_type
        )

        if success:
            webhook_type_name = "Teams channel" if test_request.webhook_type == 'teams' else "Power Automate workflow"
            return TeamsWebhookTestResponse(
                success=True,
                message=f"Test notification sent successfully! Check your {webhook_type_name}."
            )
        else:
            return TeamsWebhookTestResponse(
                success=False,
                message="Failed to send test notification. Please check your webhook URL."
            )

    except Exception as e:
        logger.error(f"Error testing webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing webhook: {str(e)}"
        )


@router.post("/send", response_model=TeamsSendNotificationResponse)
def send_notification(
    notification: TeamsSendNotificationRequest,
    db: Session = Depends(get_db)
):
    """Send a notification to a Teams webhook."""
    # Get webhook from database
    webhook = db.query(TeamsWebhook).filter(TeamsWebhook.id == notification.webhook_id).first()
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {notification.webhook_id} not found"
        )

    if not webhook.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook '{webhook.name}' is not active"
        )

    # Send notification based on webhook type
    try:
        if webhook.webhook_type == 'power_automate':
            # Convert to simple format for Power Automate
            payload = TeamsNotificationService.convert_to_power_automate_format(
                notification.notification_type,
                notification.data
            )
            success = TeamsNotificationService.send_to_power_automate(webhook.webhook_url, payload)
        else:
            # Create adaptive card for Teams
            if notification.notification_type == "budget_alert":
                card = TeamsNotificationService.create_budget_alert_card(
                    budget_name=notification.data.get('budget_name', 'Unknown'),
                    current_spend=notification.data.get('current_spend', 0),
                    budget_amount=notification.data.get('budget_amount', 0),
                    percentage=notification.data.get('percentage', 0),
                    forecast_spend=notification.data.get('forecast_spend', 0),
                    account_name=notification.data.get('account_name', 'Unknown')
                )
            elif notification.notification_type == "cost_summary":
                card = TeamsNotificationService.create_cost_summary_card(
                    period=notification.data.get('period', 'Daily'),
                    total_cost=notification.data.get('total_cost', 0),
                    previous_cost=notification.data.get('previous_cost', 0),
                    change_percentage=notification.data.get('change_percentage', 0),
                    top_services=notification.data.get('top_services', []),
                    account_name=notification.data.get('account_name', 'Unknown')
                )
            elif notification.notification_type == "audit_report":
                card = TeamsNotificationService.create_audit_findings_card(
                    total_findings=notification.data.get('total_findings', 0),
                    potential_savings=notification.data.get('potential_savings', 0),
                    top_findings=notification.data.get('top_findings', []),
                    account_name=notification.data.get('account_name', 'Unknown')
                )
            elif notification.notification_type == "custom":
                card = TeamsNotificationService.create_simple_message_card(
                    title=notification.data.get('title', 'Notification'),
                    message=notification.data.get('message', ''),
                    color=notification.data.get('color', 'accent')
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown notification type: {notification.notification_type}"
                )

            # Send notification
            success = TeamsNotificationService.send_adaptive_card(webhook.webhook_url, card)

        if success:
            # Update last_sent_at
            from datetime import datetime
            webhook.last_sent_at = datetime.utcnow()
            db.commit()

            return TeamsSendNotificationResponse(
                success=True,
                message="Notification sent successfully",
                webhook_name=webhook.name
            )
        else:
            return TeamsSendNotificationResponse(
                success=False,
                message="Failed to send notification",
                webhook_name=webhook.name
            )

    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending notification: {str(e)}"
        )


@router.post("/budget-alerts/check")
def check_budget_alerts(db: Session = Depends(get_db)):
    """
    Check all active budgets and send Teams notifications for those exceeding thresholds.
    This endpoint can be called manually or scheduled via cron job.
    """
    try:
        result = BudgetNotificationService.check_and_send_budget_alerts(db)
        return {
            "success": True,
            "message": f"Budget alert check completed. Sent {result['notifications_sent']} notifications.",
            **result
        }
    except Exception as e:
        logger.error(f"Error checking budget alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking budget alerts: {str(e)}"
        )


@router.post("/budget-alerts/{budget_id}")
def send_budget_alert(
    budget_id: int,
    db: Session = Depends(get_db)
):
    """
    Send immediate budget alert for a specific budget to all configured webhooks.
    Useful for testing or manual triggering of budget alerts.
    """
    try:
        result = BudgetNotificationService.send_immediate_budget_alert(db, budget_id)

        if not result.get('success'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('error', 'Failed to send budget alert')
            )

        return {
            "success": True,
            "message": f"Budget alert sent to {result['notifications_sent']} webhook(s)",
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending budget alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending budget alert: {str(e)}"
        )
