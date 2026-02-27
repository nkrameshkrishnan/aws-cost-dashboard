"""
Unit Cost Service for calculating cost efficiency metrics.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import logging

from app.models.business_metric import BusinessMetric
from app.models.aws_account import AWSAccount
from app.schemas.unit_cost import (
    BusinessMetricCreate,
    BusinessMetricResponse,
    UnitCostResponse,
    UnitCostTrendResponse
)
from app.services.cost_processor_db import DatabaseCostProcessor
from app.aws.session_manager import AWSSessionManager
from app.aws.cloudwatch_metrics import CloudWatchMetricsCollector

logger = logging.getLogger(__name__)


class UnitCostService:
    """Service for managing business metrics and calculating unit costs."""

    def __init__(self, db: Session):
        self.db = db

    def create_business_metric(
        self,
        metric_data: BusinessMetricCreate
    ) -> BusinessMetricResponse:
        """
        Create or update a business metric entry.

        Args:
            metric_data: Business metric data

        Returns:
            Created/updated business metric
        """
        # Parse date
        metric_date = datetime.strptime(metric_data.metric_date, "%Y-%m-%d").date()

        # Check if exists
        existing = self.db.query(BusinessMetric).filter(
            and_(
                BusinessMetric.profile_name == metric_data.profile_name,
                BusinessMetric.metric_date == metric_date
            )
        ).first()

        if existing:
            # Update existing
            existing.active_users = metric_data.active_users
            existing.total_transactions = metric_data.total_transactions
            existing.api_calls = metric_data.api_calls
            existing.data_processed_gb = metric_data.data_processed_gb
            existing.custom_metric_1 = metric_data.custom_metric_1
            existing.custom_metric_1_name = metric_data.custom_metric_1_name
            self.db.commit()
            self.db.refresh(existing)
            metric = existing
        else:
            # Create new
            metric = BusinessMetric(
                profile_name=metric_data.profile_name,
                metric_date=metric_date,
                active_users=metric_data.active_users,
                total_transactions=metric_data.total_transactions,
                api_calls=metric_data.api_calls,
                data_processed_gb=metric_data.data_processed_gb,
                custom_metric_1=metric_data.custom_metric_1,
                custom_metric_1_name=metric_data.custom_metric_1_name
            )
            self.db.add(metric)
            self.db.commit()
            self.db.refresh(metric)

        return BusinessMetricResponse(
            id=metric.id,
            profile_name=metric.profile_name,
            metric_date=str(metric.metric_date),
            active_users=metric.active_users,
            total_transactions=metric.total_transactions,
            api_calls=metric.api_calls,
            data_processed_gb=metric.data_processed_gb,
            custom_metric_1=metric.custom_metric_1,
            custom_metric_1_name=metric.custom_metric_1_name,
            created_at=metric.created_at,
            updated_at=metric.updated_at
        )

    def get_business_metrics(
        self,
        profile_name: str,
        start_date: str,
        end_date: str
    ) -> List[BusinessMetricResponse]:
        """
        Get business metrics for a date range.

        Args:
            profile_name: AWS profile name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of business metrics
        """
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        metrics = self.db.query(BusinessMetric).filter(
            and_(
                BusinessMetric.profile_name == profile_name,
                BusinessMetric.metric_date >= start,
                BusinessMetric.metric_date <= end
            )
        ).order_by(BusinessMetric.metric_date).all()

        return [
            BusinessMetricResponse(
                id=m.id,
                profile_name=m.profile_name,
                metric_date=str(m.metric_date),
                active_users=m.active_users,
                total_transactions=m.total_transactions,
                api_calls=m.api_calls,
                data_processed_gb=m.data_processed_gb,
                custom_metric_1=m.custom_metric_1,
                custom_metric_1_name=m.custom_metric_1_name,
                created_at=m.created_at,
                updated_at=m.updated_at
            )
            for m in metrics
        ]

    def calculate_unit_costs(
        self,
        profile_name: str,
        start_date: str,
        end_date: str,
        region: str = 'us-east-2'
    ) -> UnitCostResponse:
        """
        Calculate unit costs for a period using automatic CloudWatch metrics.

        Args:
            profile_name: AWS profile name (account name in database)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            region: AWS region to collect metrics from (default: us-east-2)

        Returns:
            Unit cost calculations
        """
        # Get total cost for period using DatabaseCostProcessor
        cost_summary = DatabaseCostProcessor.get_cost_summary(
            self.db,
            profile_name,  # account_name in database
            start_date,
            end_date
        )
        total_cost = cost_summary.get('total_cost', 0.0)

        # Use provided region parameter
        logger.info(f"Collecting CloudWatch metrics from region: {region}")

        # Get business metrics from CloudWatch (automatic collection)
        try:
            session_manager = AWSSessionManager(db=self.db)
            session = session_manager.get_session(profile_name)

            cloudwatch_collector = CloudWatchMetricsCollector(session, region=region)
            metrics = cloudwatch_collector.get_business_metrics(start_date, end_date)

            total_users = metrics.get('active_users')
            total_transactions = metrics.get('total_transactions')
            total_api_calls = metrics.get('api_calls')
            total_gb = metrics.get('data_processed_gb')
            ec2_hours = metrics.get('ec2_instance_hours')

            logger.info(f"CloudWatch metrics collected for {profile_name} in {region}: {metrics}")
        except Exception as e:
            logger.error(f"Error collecting CloudWatch metrics: {str(e)}", exc_info=True)
            # Return empty metrics on error
            total_users = None
            total_transactions = None
            total_api_calls = None
            total_gb = None
            ec2_hours = None

        # If no transactions but have EC2 hours, use EC2 hours as transactions
        # This allows infrastructure-focused accounts to still see unit costs
        if not total_transactions and ec2_hours:
            logger.info(f"Using EC2 instance hours ({ec2_hours}) as transaction metric")
            total_transactions = ec2_hours

        # Calculate unit costs
        cost_per_user = (total_cost / total_users) if total_users else None
        cost_per_transaction = (total_cost / total_transactions) if total_transactions else None
        cost_per_api_call = (total_cost / total_api_calls) if total_api_calls else None
        cost_per_gb = (total_cost / total_gb) if total_gb else None

        # Calculate trend (compare to previous period)
        period_days = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        prev_end = start_dt - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days)

        try:
            prev_cost_summary = DatabaseCostProcessor.get_cost_summary(
                self.db,
                profile_name,
                str(prev_start),
                str(prev_end)
            )
            prev_total_cost = prev_cost_summary.get('total_cost', 0.0)

            # Get previous period CloudWatch metrics
            session = session_manager.get_session(profile_name)
            cloudwatch_collector = CloudWatchMetricsCollector(session, region=region)
            prev_metrics = cloudwatch_collector.get_business_metrics(str(prev_start), str(prev_end))

            prev_total_transactions = prev_metrics.get('total_transactions')
            prev_cost_per_transaction = (prev_total_cost / prev_total_transactions) if prev_total_transactions else None

            # Determine trend based on cost per transaction
            trend = None
            mom_change = None
            if cost_per_transaction and prev_cost_per_transaction:
                change = ((cost_per_transaction - prev_cost_per_transaction) / prev_cost_per_transaction) * 100
                mom_change = change
                if change < -5:
                    trend = "improving"  # Cost per transaction decreasing significantly
                elif change > 5:
                    trend = "degrading"  # Cost per transaction increasing significantly
                else:
                    trend = "stable"
        except Exception as e:
            logger.warning(f"Error calculating trend: {str(e)}")
            trend = None
            mom_change = None

        return UnitCostResponse(
            profile_name=profile_name,
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            cost_per_user=cost_per_user,
            cost_per_transaction=cost_per_transaction,
            cost_per_api_call=cost_per_api_call,
            cost_per_gb=cost_per_gb,
            cost_per_custom_metric=None,  # Not using custom metrics with CloudWatch
            total_users=total_users,
            total_transactions=total_transactions,
            total_api_calls=total_api_calls,
            total_gb_processed=total_gb,
            total_custom_metric=None,  # Not using custom metrics with CloudWatch
            custom_metric_name=None,  # Not using custom metrics with CloudWatch
            trend=trend,
            mom_change_percent=mom_change
        )

    def get_unit_cost_trend(
        self,
        profile_name: str,
        metric_type: str,
        months: int = 6,
        region: str = 'us-east-2'
    ) -> UnitCostTrendResponse:
        """
        Get unit cost trend over time using automatic CloudWatch metrics.

        Args:
            profile_name: AWS profile name (account name in database)
            metric_type: Type of unit cost (cost_per_user, cost_per_transaction, etc.)
            months: Number of months to analyze
            region: AWS region to collect metrics from (default: us-east-2)

        Returns:
            Unit cost trend data
        """
        trend_data = []
        end_date = datetime.now().date()

        for i in range(months):
            # Calculate month range
            month_end = end_date - timedelta(days=i * 30)
            month_start = month_end - timedelta(days=29)

            try:
                unit_costs = self.calculate_unit_costs(
                    profile_name=profile_name,
                    start_date=str(month_start),
                    end_date=str(month_end),
                    region=region
                )

                # Extract the requested metric
                metric_value = None
                metric_total = None

                if metric_type == "cost_per_user":
                    metric_value = unit_costs.cost_per_user
                    metric_total = unit_costs.total_users
                elif metric_type == "cost_per_transaction":
                    metric_value = unit_costs.cost_per_transaction
                    metric_total = unit_costs.total_transactions
                elif metric_type == "cost_per_api_call":
                    metric_value = unit_costs.cost_per_api_call
                    metric_total = unit_costs.total_api_calls
                elif metric_type == "cost_per_gb":
                    metric_value = unit_costs.cost_per_gb
                    metric_total = unit_costs.total_gb_processed

                if metric_value is not None:
                    trend_data.append({
                        "date": str(month_start),
                        "unit_cost": round(metric_value, 4),
                        "total_cost": round(unit_costs.total_cost, 2),
                        "metric_value": metric_total
                    })
            except Exception as e:
                logger.warning(f"Error calculating trend for {month_start}: {str(e)}")
                continue

        # Reverse to chronological order
        trend_data.reverse()

        return UnitCostTrendResponse(
            profile_name=profile_name,
            metric_type=metric_type,
            trend_data=trend_data
        )
