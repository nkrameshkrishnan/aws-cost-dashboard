"""
KPI calculation service for AWS Cost Management.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.kpi import (
    KPICategory,
    KPIStatus,
    KPIValue,
    KPIMetrics,
    KPITrend,
    AWS_COST_KPI_DEFINITIONS,
    KPIDefinition,
    KPIThreshold
)
from app.models.budget import Budget
from app.services.cost_processor_db import DatabaseCostProcessor
from app.core.job_storage import job_storage
from app.services.aws_budgets_service import AWSBudgetsService


class KPIService:
    """Service for calculating AWS cost KPIs."""

    def __init__(self, db: Session):
        self.db = db

    def calculate_kpi_status(
        self,
        value: float,
        thresholds: KPIThreshold,
        higher_is_better: bool
    ) -> KPIStatus:
        """Determine KPI status based on value and thresholds."""
        if higher_is_better:
            if value >= thresholds.excellent:
                return KPIStatus.EXCELLENT
            elif value >= thresholds.good:
                return KPIStatus.GOOD
            elif value >= thresholds.warning:
                return KPIStatus.WARNING
            else:
                return KPIStatus.POOR
        else:
            if value <= thresholds.excellent:
                return KPIStatus.EXCELLENT
            elif value <= thresholds.good:
                return KPIStatus.GOOD
            elif value <= thresholds.warning:
                return KPIStatus.WARNING
            else:
                return KPIStatus.POOR

    def calculate_trend(self, current: float, previous: Optional[float]) -> str:
        """Calculate trend direction."""
        if previous is None or previous == 0:
            return "stable"

        change_percent = ((current - previous) / previous) * 100

        if abs(change_percent) < 2:  # Less than 2% change
            return "stable"
        elif change_percent > 0:
            return "up"
        else:
            return "down"

    async def calculate_cost_efficiency(self, profile_name: str) -> KPIValue:
        """
        Calculate cost efficiency based on budget utilization and cost trends.
        Efficiency score combines budget performance and cost management.
        """
        definition = AWS_COST_KPI_DEFINITIONS["cost_efficiency"]

        try:
            # Get budget utilization
            budget_kpi = await self.calculate_budget_utilization(profile_name)
            budget_util = budget_kpi.value

            # Get cost growth rate
            growth_kpi = await self.calculate_cost_growth_rate(profile_name)
            cost_growth = growth_kpi.value

            # Calculate efficiency score (0-100%)
            # Start with base 100%
            efficiency = 100.0

            # Penalize for over-budget (reduce by % over budget)
            if budget_util > 100:
                over_budget_penalty = min((budget_util - 100) / 2, 30)  # Max 30% penalty
                efficiency -= over_budget_penalty

            # Penalize for cost growth (reduce by growth rate)
            if cost_growth > 0:
                growth_penalty = min(cost_growth / 2, 20)  # Max 20% penalty
                efficiency -= growth_penalty

            # Bonus for cost reduction
            if cost_growth < 0:
                reduction_bonus = min(abs(cost_growth) / 2, 10)  # Max 10% bonus
                efficiency = min(efficiency + reduction_bonus, 100)

            # Ensure efficiency is between 0 and 100
            efficiency = max(0, min(100, efficiency))

            status = self.calculate_kpi_status(
                efficiency,
                definition.thresholds,
                definition.higher_is_better
            )

            return KPIValue(
                category=definition.category,
                value=round(efficiency, 2),
                status=status,
                trend="stable" if abs(cost_growth) < 5 else ("up" if cost_growth < 0 else "down"),
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )
        except Exception:
            # Fallback to neutral score
            return KPIValue(
                category=definition.category,
                value=70.0,
                status=KPIStatus.GOOD,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )

    async def calculate_budget_utilization(self, profile_name: str) -> KPIValue:
        """
        Calculate budget utilization using projected end-of-period spending.
        Uses the same calculation as Budget Status page for consistency.
        """
        definition = AWS_COST_KPI_DEFINITIONS["budget_utilization"]

        try:
            # Get active budgets
            budgets = self.db.query(Budget).filter(Budget.is_active == True).all()

            if not budgets:
                return KPIValue(
                    category=definition.category,
                    value=0.0,
                    status=KPIStatus.UNKNOWN,
                    trend="stable",
                    profile_name=profile_name,
                    calculated_at=datetime.utcnow()
                )

            # Calculate date range for current budget period
            now = datetime.now()
            today = now.date()

            # Current month: first day to today
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # End of current month
            if now.month == 12:
                period_end = now.replace(year=now.year + 1, month=1, day=1)
            else:
                period_end = now.replace(month=now.month + 1, day=1)

            # Get current spending for this period
            cost_summary = DatabaseCostProcessor.get_cost_summary(
                db=self.db,
                account_name=profile_name,
                start_date=period_start.strftime('%Y-%m-%d'),
                end_date=today.strftime('%Y-%m-%d')
            )

            current_spend = cost_summary.get('total_cost', 0.0)
            total_budget = sum(b.amount for b in budgets)

            # Calculate projection using AWS Budgets API (matches AWS Console)
            days_remaining = (period_end - now).days
            projected_spend = None

            if days_remaining > 0:
                try:
                    # Use AWS Budgets API forecast - matches what AWS Console shows
                    # Get the first active budget for this account
                    if budgets:
                        budget_name = budgets[0].name
                        budget_forecast = AWSBudgetsService.get_budget_forecast(
                            self.db,
                            profile_name,
                            budget_name=budget_name
                        )

                        # AWS Budgets returns the total forecasted spend
                        projected_spend = budget_forecast.get('forecasted_spend', 0.0)
                    else:
                        raise ValueError("No budgets found")

                except Exception as e:
                    # Fallback to linear projection
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"KPI Budget Calc - AWS Budgets forecast failed, using linear projection. Error: {e}")

                    days_elapsed = (now - period_start).days
                    if days_elapsed > 0:
                        daily_avg = current_spend / days_elapsed
                        total_days = (period_end - period_start).days
                        projected_spend = daily_avg * total_days
                    else:
                        projected_spend = current_spend
            else:
                projected_spend = current_spend

            # Calculate utilization as projected percentage
            if total_budget > 0:
                utilization = (projected_spend / total_budget) * 100
            else:
                utilization = 0.0

            status = self.calculate_kpi_status(
                utilization,
                definition.thresholds,
                definition.higher_is_better
            )

            return KPIValue(
                category=definition.category,
                value=round(utilization, 2),
                status=status,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow(),
                target_value=100.0
            )
        except Exception:
            # Return unknown status if calculation fails
            return KPIValue(
                category=definition.category,
                value=0.0,
                status=KPIStatus.UNKNOWN,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )

    async def calculate_cost_growth_rate(self, profile_name: str) -> KPIValue:
        """Calculate month-over-month cost growth rate using actual data."""
        definition = AWS_COST_KPI_DEFINITIONS["cost_growth_rate"]

        try:
            today = datetime.now().date()

            # Current month
            current_month_start = today.replace(day=1)
            current_summary = DatabaseCostProcessor.get_cost_summary(
                db=self.db,
                account_name=profile_name,
                start_date=current_month_start.strftime('%Y-%m-%d'),
                end_date=today.strftime('%Y-%m-%d')
            )
            current_cost = current_summary.get('total_cost', 0.0)

            # Previous month
            prev_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
            prev_month_end = current_month_start - timedelta(days=1)
            prev_summary = DatabaseCostProcessor.get_cost_summary(
                db=self.db,
                account_name=profile_name,
                start_date=prev_month_start.strftime('%Y-%m-%d'),
                end_date=prev_month_end.strftime('%Y-%m-%d')
            )
            prev_cost = prev_summary.get('total_cost', 0.0)

            if prev_cost > 0:
                growth_rate = ((current_cost - prev_cost) / prev_cost) * 100
            else:
                growth_rate = 0.0

            status = self.calculate_kpi_status(
                growth_rate,
                definition.thresholds,
                definition.higher_is_better
            )

            trend = self.calculate_trend(current_cost, prev_cost)

            return KPIValue(
                category=definition.category,
                value=round(growth_rate, 2),
                status=status,
                trend=trend,
                previous_value=prev_cost,
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )
        except Exception:
            return KPIValue(
                category=definition.category,
                value=0.0,
                status=KPIStatus.UNKNOWN,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )

    async def calculate_daily_spend_rate(self, profile_name: str) -> KPIValue:
        """Calculate average daily spend for current month using actual data."""
        definition = AWS_COST_KPI_DEFINITIONS["daily_spend_rate"]

        try:
            today = datetime.now().date()
            start_of_month = today.replace(day=1)

            cost_summary = DatabaseCostProcessor.get_cost_summary(
                db=self.db,
                account_name=profile_name,
                start_date=start_of_month.strftime('%Y-%m-%d'),
                end_date=today.strftime('%Y-%m-%d')
            )

            total_cost = cost_summary.get('total_cost', 0.0)
            days_elapsed = today.day
            daily_avg = total_cost / days_elapsed if days_elapsed > 0 else 0.0

            status = self.calculate_kpi_status(
                daily_avg,
                definition.thresholds,
                definition.higher_is_better
            )

            return KPIValue(
                category=definition.category,
                value=round(daily_avg, 2),
                status=status,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )
        except Exception:
            return KPIValue(
                category=definition.category,
                value=0.0,
                status=KPIStatus.UNKNOWN,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )

    async def calculate_savings_potential(self, profile_name: str) -> KPIValue:
        """
        Calculate monthly savings potential from FinOps audit recommendations.
        Uses the latest audit results if available, otherwise estimates from budget overage.
        """
        definition = AWS_COST_KPI_DEFINITIONS["savings_potential"]

        try:
            # Try to get latest audit results from job storage
            # Get recent jobs and find the most recent one with non-zero savings
            recent_jobs = job_storage.list_jobs(account_name=profile_name, limit=20)

            savings = 0.0

            # Find the most recent completed job with non-zero savings
            for job in recent_jobs:
                if job['status'] == 'completed' and job['results']:
                    audit_results = job['results']
                    potential_savings = 0.0

                    if isinstance(audit_results, dict) and 'summary' in audit_results:
                        potential_savings = audit_results['summary'].get('total_potential_savings', 0.0)
                    elif hasattr(audit_results, 'summary'):
                        potential_savings = getattr(audit_results.summary, 'total_potential_savings', 0.0)

                    # Use the first job with non-zero savings
                    if potential_savings > 0:
                        savings = potential_savings
                        break

            # Fallback to estimation if no audit results found
            if savings == 0.0:
                # Get budget utilization
                budget_kpi = await self.calculate_budget_utilization(profile_name)
                budget_util = budget_kpi.value

                # Get current month spending
                today = datetime.now().date()
                start_of_month = today.replace(day=1)
                cost_summary = DatabaseCostProcessor.get_cost_summary(
                    db=self.db,
                    account_name=profile_name,
                    start_date=start_of_month.strftime('%Y-%m-%d'),
                    end_date=today.strftime('%Y-%m-%d')
                )
                current_spend = cost_summary.get('total_cost', 0.0)

                # Estimate savings potential from over-budget spending
                if budget_util > 100 and current_spend > 0:
                    # Get budget amount
                    budgets = self.db.query(Budget).filter(Budget.is_active == True).all()
                    if budgets:
                        total_budget = sum(b.amount for b in budgets)
                        days_in_month = (datetime(today.year, today.month % 12 + 1, 1).date() - timedelta(days=1)).day
                        period_progress = today.day / days_in_month
                        expected_spend = total_budget * period_progress

                        if current_spend > expected_spend:
                            # Estimate 15% of overage as savings potential
                            overage = current_spend - expected_spend
                            savings = overage * 0.15

            status = self.calculate_kpi_status(
                savings,
                definition.thresholds,
                definition.higher_is_better
            )

            return KPIValue(
                category=definition.category,
                value=round(savings, 2),
                status=status,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )
        except Exception:
            return KPIValue(
                category=definition.category,
                value=0.0,
                status=KPIStatus.EXCELLENT,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )

    async def calculate_resource_waste_ratio(self, profile_name: str) -> KPIValue:
        """
        Calculate resource waste ratio based on budget performance and cost efficiency.
        Estimates percentage of spending that could be optimized.
        """
        definition = AWS_COST_KPI_DEFINITIONS["resource_waste_ratio"]

        try:
            # Get budget utilization and cost efficiency
            budget_kpi = await self.calculate_budget_utilization(profile_name)
            budget_util = budget_kpi.value

            cost_growth_kpi = await self.calculate_cost_growth_rate(profile_name)
            cost_growth = cost_growth_kpi.value

            # Calculate waste ratio (0-100%)
            # Base waste on over-budget spending and cost growth
            waste_ratio = 0.0

            # If significantly over budget, estimate waste ratio
            if budget_util > 120:
                # Estimate 10-25% waste for significantly over-budget accounts
                waste_ratio += min((budget_util - 100) * 0.15, 25)

            # If costs are growing rapidly, add to waste estimate
            if cost_growth > 10:
                waste_ratio += min(cost_growth * 0.5, 15)

            # Ensure waste ratio is between 0 and 100
            waste_ratio = max(0, min(100, waste_ratio))

            status = self.calculate_kpi_status(
                waste_ratio,
                definition.thresholds,
                definition.higher_is_better
            )

            return KPIValue(
                category=definition.category,
                value=round(waste_ratio, 2),
                status=status,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )
        except Exception:
            return KPIValue(
                category=definition.category,
                value=0.0,
                status=KPIStatus.EXCELLENT,
                trend="stable",
                profile_name=profile_name,
                calculated_at=datetime.utcnow()
            )

    async def calculate_all_kpis(self, profile_name: str) -> Dict[str, KPIValue]:
        """Calculate all KPIs for a given profile."""
        return {
            "cost_efficiency": await self.calculate_cost_efficiency(profile_name),
            "budget_utilization": await self.calculate_budget_utilization(profile_name),
            "cost_growth_rate": await self.calculate_cost_growth_rate(profile_name),
            "daily_spend_rate": await self.calculate_daily_spend_rate(profile_name),
            "savings_potential": await self.calculate_savings_potential(profile_name),
            "resource_waste_ratio": await self.calculate_resource_waste_ratio(profile_name),
        }

    async def get_kpi_metrics(
        self,
        kpi_id: str,
        profile_name: str,
        days_history: int = 30
    ) -> KPIMetrics:
        """Get complete KPI metrics with history."""
        definition = AWS_COST_KPI_DEFINITIONS.get(kpi_id)
        if not definition:
            raise ValueError(f"Unknown KPI: {kpi_id}")

        calculator_map = {
            "cost_efficiency": self.calculate_cost_efficiency,
            "budget_utilization": self.calculate_budget_utilization,
            "cost_growth_rate": self.calculate_cost_growth_rate,
            "daily_spend_rate": self.calculate_daily_spend_rate,
            "savings_potential": self.calculate_savings_potential,
            "resource_waste_ratio": self.calculate_resource_waste_ratio,
        }

        calculator = calculator_map.get(kpi_id)
        if not calculator:
            raise ValueError(f"No calculator for KPI: {kpi_id}")

        current_value = await calculator(profile_name)
        history: List[KPITrend] = []

        return KPIMetrics(
            kpi=definition,
            current=current_value,
            history=history,
            target_value=current_value.target_value
        )
