"""
Budget service for managing budgets and calculating status.
"""
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from app.models.budget import Budget
from app.models.aws_account import AWSAccount
from app.schemas.budget import (
    BudgetCreate,
    BudgetUpdate,
    BudgetStatus,
    BudgetAlertLevel,
    BudgetSummary
)
from app.services.cost_processor_db import DatabaseCostProcessor
from app.services.aws_budgets_service import AWSBudgetsService

logger = logging.getLogger(__name__)


class BudgetService:
    """Service for managing budgets and calculating budget status."""

    @staticmethod
    def create_budget(db: Session, budget_data: BudgetCreate) -> Budget:
        """
        Create a new budget.

        Args:
            db: Database session
            budget_data: Budget creation data

        Returns:
            Created budget
        """
        # Verify AWS account exists
        account = db.query(AWSAccount).filter(
            AWSAccount.id == budget_data.aws_account_id
        ).first()

        if not account:
            raise ValueError(f"AWS account with ID {budget_data.aws_account_id} not found")

        db_budget = Budget(
            name=budget_data.name,
            description=budget_data.description,
            aws_account_id=budget_data.aws_account_id,
            amount=budget_data.amount,
            period=budget_data.period,
            start_date=budget_data.start_date,
            end_date=budget_data.end_date,
            threshold_warning=budget_data.threshold_warning,
            threshold_critical=budget_data.threshold_critical,
            is_active=budget_data.is_active
        )

        db.add(db_budget)
        db.commit()
        db.refresh(db_budget)

        logger.info(f"Created budget: {db_budget.name} (ID: {db_budget.id})")
        return db_budget

    @staticmethod
    def get_budget(db: Session, budget_id: int) -> Optional[Budget]:
        """Get a budget by ID."""
        return db.query(Budget).filter(Budget.id == budget_id).first()

    @staticmethod
    def list_budgets(
        db: Session,
        aws_account_id: Optional[int] = None,
        active_only: bool = True
    ) -> List[Budget]:
        """
        List budgets with optional filtering.

        Args:
            db: Database session
            aws_account_id: Filter by AWS account ID
            active_only: Only return active budgets

        Returns:
            List of budgets
        """
        # Use joinedload to prevent N+1 queries when accessing aws_account relationship
        query = db.query(Budget).options(joinedload(Budget.aws_account))

        if aws_account_id:
            query = query.filter(Budget.aws_account_id == aws_account_id)

        if active_only:
            query = query.filter(Budget.is_active == True)

        return query.order_by(Budget.created_at.desc()).all()

    @staticmethod
    def update_budget(
        db: Session,
        budget_id: int,
        budget_data: BudgetUpdate
    ) -> Optional[Budget]:
        """
        Update a budget.

        Args:
            db: Database session
            budget_id: Budget ID
            budget_data: Budget update data

        Returns:
            Updated budget or None if not found
        """
        db_budget = BudgetService.get_budget(db, budget_id)

        if not db_budget:
            return None

        # Update fields if provided
        update_data = budget_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_budget, field, value)

        db.commit()
        db.refresh(db_budget)

        logger.info(f"Updated budget: {db_budget.name} (ID: {db_budget.id})")
        return db_budget

    @staticmethod
    def delete_budget(db: Session, budget_id: int) -> bool:
        """
        Delete a budget.

        Args:
            db: Database session
            budget_id: Budget ID

        Returns:
            True if deleted, False if not found
        """
        db_budget = BudgetService.get_budget(db, budget_id)

        if not db_budget:
            return False

        db.delete(db_budget)
        db.commit()

        logger.info(f"Deleted budget: {db_budget.name} (ID: {budget_id})")
        return True

    @staticmethod
    def get_budget_status(db: Session, budget_id: int) -> Optional[BudgetStatus]:
        """
        Get budget status with current spending and alerts.

        Args:
            db: Database session
            budget_id: Budget ID

        Returns:
            Budget status or None if budget not found
        """
        # Use joinedload to prevent N+1 query when accessing aws_account
        budget = db.query(Budget).options(
            joinedload(Budget.aws_account)
        ).filter(Budget.id == budget_id).first()

        if not budget:
            return None

        # Use the relationship instead of a separate query
        account = budget.aws_account

        if not account:
            raise ValueError(f"AWS account not found for budget {budget_id}")

        # Calculate date range for CURRENT budget period based on budget type
        now = datetime.now()

        # Calculate current period based on budget period type
        if budget.period == 'monthly':
            # Current month: first day to today (or end of month if budget ends sooner)
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # End of current month
            if now.month == 12:
                period_end = now.replace(year=now.year + 1, month=1, day=1)
            else:
                period_end = now.replace(month=now.month + 1, day=1)
        elif budget.period == 'quarterly':
            # Current quarter
            quarter_month = ((now.month - 1) // 3) * 3 + 1
            period_start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            # End of current quarter (3 months later)
            end_month = quarter_month + 3
            if end_month > 12:
                period_end = now.replace(year=now.year + 1, month=end_month - 12, day=1)
            else:
                period_end = now.replace(month=end_month, day=1)
        elif budget.period == 'yearly':
            # Current year
            period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = now.replace(year=now.year + 1, month=1, day=1)
        else:
            # Fallback to monthly
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                period_end = now.replace(year=now.year + 1, month=1, day=1)
            else:
                period_end = now.replace(month=now.month + 1, day=1)

        # Don't query beyond today
        if period_end > now:
            query_end = now
        else:
            query_end = period_end

        # Get current spending for this period
        try:
            cost_summary = DatabaseCostProcessor.get_cost_summary(
                db,
                account.name,
                period_start.strftime("%Y-%m-%d"),
                query_end.strftime("%Y-%m-%d")
            )
            current_spend = cost_summary['total_cost']
        except Exception as e:
            logger.error(f"Error fetching costs for budget {budget_id}: {e}")
            current_spend = 0.0

        # Calculate percentage used
        percentage_used = (current_spend / budget.amount * 100) if budget.amount > 0 else 0
        remaining = max(0, budget.amount - current_spend)

        # Calculate days remaining in current period
        days_remaining = (period_end - now).days
        days_remaining = max(0, days_remaining)

        # Determine alert level
        alert_level = BudgetService._calculate_alert_level(
            percentage_used,
            budget.threshold_warning,
            budget.threshold_critical
        )

        # Calculate projection using AWS Budgets API forecast (matches AWS Console)
        projected_spend = None
        projected_percentage = None
        is_projected_to_exceed = False

        if days_remaining > 0:
            try:
                # Use AWS Budgets API forecast - this matches what AWS Console shows
                budget_forecast = AWSBudgetsService.get_budget_forecast(
                    db,
                    account.name,
                    budget_name=budget.name
                )

                # AWS Budgets returns the total forecasted spend for the period
                projected_spend = budget_forecast.get('forecasted_spend', 0.0)
                projected_percentage = (projected_spend / budget.amount * 100) if budget.amount > 0 else 0
                is_projected_to_exceed = projected_spend > budget.amount

            except Exception as e:
                logger.warning(f"Failed to get AWS Budgets forecast, falling back to linear projection: {e}")
                # Fallback to simple linear projection if AWS Budgets API fails
                days_elapsed = (now - period_start).days
                if days_elapsed > 0:
                    daily_avg = current_spend / days_elapsed
                    total_days = (period_end - period_start).days
                    projected_spend = daily_avg * total_days
                    projected_percentage = (projected_spend / budget.amount * 100) if budget.amount > 0 else 0
                    is_projected_to_exceed = projected_spend > budget.amount

        return BudgetStatus(
            budget_id=budget.id,
            budget_name=budget.name,
            budget_amount=budget.amount,
            period=budget.period,
            start_date=period_start,  # Current period start
            end_date=period_end,  # Current period end
            current_spend=round(current_spend, 2),
            percentage_used=round(percentage_used, 2),
            remaining=round(remaining, 2),
            days_remaining=days_remaining,
            alert_level=alert_level,
            threshold_warning=budget.threshold_warning,
            threshold_critical=budget.threshold_critical,
            projected_spend=round(projected_spend, 2) if projected_spend else None,
            projected_percentage=round(projected_percentage, 2) if projected_percentage else None,
            is_projected_to_exceed=is_projected_to_exceed
        )

    @staticmethod
    def get_budgets_summary(db: Session, aws_account_id: Optional[int] = None) -> BudgetSummary:
        """
        Get summary of all budgets.

        Args:
            db: Database session
            aws_account_id: Optional filter by AWS account

        Returns:
            Budget summary statistics
        """
        budgets = BudgetService.list_budgets(db, aws_account_id, active_only=False)
        active_budgets = [b for b in budgets if b.is_active]

        total_budget_amount = sum(b.amount for b in active_budgets)
        total_current_spend = 0.0
        budgets_at_warning = 0
        budgets_at_critical = 0
        budgets_exceeded = 0

        for budget in active_budgets:
            status = BudgetService.get_budget_status(db, budget.id)
            if status:
                total_current_spend += status.current_spend

                if status.alert_level == BudgetAlertLevel.WARNING:
                    budgets_at_warning += 1
                elif status.alert_level == BudgetAlertLevel.CRITICAL:
                    budgets_at_critical += 1
                elif status.alert_level == BudgetAlertLevel.EXCEEDED:
                    budgets_exceeded += 1

        return BudgetSummary(
            total_budgets=len(budgets),
            active_budgets=len(active_budgets),
            total_budget_amount=round(total_budget_amount, 2),
            total_current_spend=round(total_current_spend, 2),
            budgets_at_warning=budgets_at_warning,
            budgets_at_critical=budgets_at_critical,
            budgets_exceeded=budgets_exceeded
        )

    @staticmethod
    def _calculate_alert_level(
        percentage_used: float,
        threshold_warning: float,
        threshold_critical: float
    ) -> BudgetAlertLevel:
        """
        Calculate alert level based on percentage used and thresholds.

        Args:
            percentage_used: Current percentage of budget used
            threshold_warning: Warning threshold percentage
            threshold_critical: Critical threshold percentage

        Returns:
            Alert level
        """
        if percentage_used >= 100:
            return BudgetAlertLevel.EXCEEDED
        elif percentage_used >= threshold_critical:
            return BudgetAlertLevel.CRITICAL
        elif percentage_used >= threshold_warning:
            return BudgetAlertLevel.WARNING
        else:
            return BudgetAlertLevel.NORMAL
