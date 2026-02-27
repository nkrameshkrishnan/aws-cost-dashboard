"""
Budget notification service for sending alerts via Microsoft Teams webhooks.
Monitors budget thresholds and sends notifications when limits are breached.
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.budget import Budget
from app.models.teams_webhook import TeamsWebhook
from app.models.aws_account import AWSAccount
from app.services.budget_service import BudgetService
from app.integrations.teams import TeamsNotificationService
from app.schemas.budget import BudgetAlertLevel

logger = logging.getLogger(__name__)


class BudgetNotificationService:
    """Service for sending budget threshold alerts."""

    @staticmethod
    def check_and_send_budget_alerts(db: Session) -> dict:
        """
        Check all active budgets and send Teams notifications for those exceeding thresholds.

        Args:
            db: Database session

        Returns:
            Dictionary with notification results
        """
        # Fetch active webhooks with budget alerts enabled
        webhooks = db.query(TeamsWebhook).filter(
            TeamsWebhook.is_active == True,
            TeamsWebhook.send_budget_alerts == True
        ).all()

        if not webhooks:
            logger.info("No active webhooks configured for budget alerts")
            return {
                "webhooks_checked": 0,
                "budgets_checked": 0,
                "notifications_sent": 0,
                "errors": []
            }

        # Fetch all active budgets
        budgets = BudgetService.list_budgets(db, active_only=True)

        notifications_sent = 0
        errors = []

        for budget in budgets:
            try:
                # Get budget status
                status = BudgetService.get_budget_status(db, budget.id)

                if not status:
                    continue

                # Get AWS account for account name
                account = db.query(AWSAccount).filter(
                    AWSAccount.id == budget.aws_account_id
                ).first()
                account_name = account.name if account else "Unknown"

                # Check each webhook's threshold
                for webhook in webhooks:
                    # Only send if budget usage exceeds webhook's threshold
                    if status.percentage_used >= webhook.budget_threshold_percentage:
                        success = BudgetNotificationService._send_budget_alert(
                            webhook=webhook,
                            budget_name=status.budget_name,
                            current_spend=status.current_spend,
                            budget_amount=status.budget_amount,
                            percentage=status.percentage_used,
                            forecast_spend=status.projected_spend or status.current_spend,
                            account_name=account_name,
                            alert_level=status.alert_level
                        )

                        if success:
                            # Update last_sent_at timestamp
                            webhook.last_sent_at = datetime.now()
                            db.commit()
                            notifications_sent += 1
                            logger.info(
                                f"Sent budget alert for '{status.budget_name}' "
                                f"({status.percentage_used:.1f}%) to webhook '{webhook.name}'"
                            )
                        else:
                            error_msg = f"Failed to send alert for budget '{status.budget_name}' to webhook '{webhook.name}'"
                            errors.append(error_msg)
                            logger.error(error_msg)

            except Exception as e:
                error_msg = f"Error processing budget {budget.id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        return {
            "webhooks_checked": len(webhooks),
            "budgets_checked": len(budgets),
            "notifications_sent": notifications_sent,
            "errors": errors
        }

    @staticmethod
    def _send_budget_alert(
        webhook: TeamsWebhook,
        budget_name: str,
        current_spend: float,
        budget_amount: float,
        percentage: float,
        forecast_spend: float,
        account_name: str,
        alert_level: BudgetAlertLevel
    ) -> bool:
        """
        Send a budget alert to a specific webhook.

        Args:
            webhook: TeamsWebhook instance
            budget_name: Name of the budget
            current_spend: Current spending
            budget_amount: Total budget amount
            percentage: Percentage used
            forecast_spend: Forecasted spend
            account_name: AWS account name
            alert_level: Alert level (normal, warning, critical, exceeded)

        Returns:
            True if successful, False otherwise
        """
        try:
            if webhook.webhook_type == 'power_automate':
                # Send to Power Automate
                data = {
                    'budget_name': budget_name,
                    'current_spend': current_spend,
                    'budget_amount': budget_amount,
                    'percentage': percentage,
                    'forecast_spend': forecast_spend,
                    'account_name': account_name,
                    'alert_level': alert_level
                }
                pa_data = TeamsNotificationService.convert_to_power_automate_format(
                    'budget_alert',
                    data
                )
                return TeamsNotificationService.send_to_power_automate(
                    webhook.webhook_url,
                    pa_data
                )
            else:
                # Send adaptive card to Teams
                card = TeamsNotificationService.create_budget_alert_card(
                    budget_name=budget_name,
                    current_spend=current_spend,
                    budget_amount=budget_amount,
                    percentage=percentage,
                    forecast_spend=forecast_spend,
                    account_name=account_name
                )
                return TeamsNotificationService.send_adaptive_card(
                    webhook.webhook_url,
                    card
                )

        except Exception as e:
            logger.error(f"Error sending budget alert: {e}")
            return False

    @staticmethod
    def send_immediate_budget_alert(
        db: Session,
        budget_id: int
    ) -> dict:
        """
        Send immediate budget alert for a specific budget to all configured webhooks.

        Args:
            db: Database session
            budget_id: Budget ID to send alert for

        Returns:
            Dictionary with notification results
        """
        # Fetch budget status
        status = BudgetService.get_budget_status(db, budget_id)

        if not status:
            return {
                "success": False,
                "error": f"Budget {budget_id} not found"
            }

        # Get budget and account
        budget = BudgetService.get_budget(db, budget_id)
        if not budget:
            return {
                "success": False,
                "error": f"Budget {budget_id} not found"
            }

        account = db.query(AWSAccount).filter(
            AWSAccount.id == budget.aws_account_id
        ).first()
        account_name = account.name if account else "Unknown"

        # Fetch active webhooks with budget alerts enabled
        webhooks = db.query(TeamsWebhook).filter(
            TeamsWebhook.is_active == True,
            TeamsWebhook.send_budget_alerts == True
        ).all()

        if not webhooks:
            return {
                "success": False,
                "error": "No active webhooks configured for budget alerts"
            }

        notifications_sent = 0
        errors = []

        for webhook in webhooks:
            success = BudgetNotificationService._send_budget_alert(
                webhook=webhook,
                budget_name=status.budget_name,
                current_spend=status.current_spend,
                budget_amount=status.budget_amount,
                percentage=status.percentage_used,
                forecast_spend=status.projected_spend or status.current_spend,
                account_name=account_name,
                alert_level=status.alert_level
            )

            if success:
                webhook.last_sent_at = datetime.now()
                db.commit()
                notifications_sent += 1
            else:
                errors.append(f"Failed to send to webhook '{webhook.name}'")

        return {
            "success": notifications_sent > 0,
            "notifications_sent": notifications_sent,
            "webhooks_checked": len(webhooks),
            "errors": errors
        }
