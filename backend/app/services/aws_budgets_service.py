"""
AWS Budgets service for importing budgets from AWS Budgets API.
"""
from sqlalchemy.orm import Session
from typing import List, Dict
import logging
from datetime import datetime

from app.aws.session_manager_db import db_session_manager
from app.models.aws_account import AWSAccount
from app.models.budget import Budget, BudgetPeriod
from app.schemas.budget import BudgetCreate

logger = logging.getLogger(__name__)


class AWSBudgetsService:
    """Service for importing budgets from AWS Budgets API."""

    @staticmethod
    def get_budgets_client(db: Session, account_name: str):
        """
        Get AWS Budgets client for a database account.

        Args:
            db: Database session
            account_name: AWS account name from database

        Returns:
            Boto3 Budgets client
        """
        # Budgets API is only available in us-east-1
        return db_session_manager.get_client(
            db,
            account_name,
            'budgets',
            region_name='us-east-1'
        )

    @staticmethod
    def fetch_aws_budgets(db: Session, account_name: str) -> List[Dict]:
        """
        Fetch budgets from AWS Budgets API.

        Args:
            db: Database session
            account_name: AWS account name from database

        Returns:
            List of budget data from AWS
        """
        try:
            # Get AWS account
            account = db.query(AWSAccount).filter(
                AWSAccount.name == account_name,
                AWSAccount.is_active == True
            ).first()

            if not account or not account.account_id:
                raise ValueError(f"AWS account {account_name} not found or missing account ID")

            client = AWSBudgetsService.get_budgets_client(db, account_name)

            # Describe budgets
            response = client.describe_budgets(
                AccountId=account.account_id
            )

            budgets_data = response.get('Budgets', [])
            logger.info(f"Found {len(budgets_data)} budgets in AWS for account {account_name}")

            return budgets_data

        except Exception as e:
            logger.error(f"Error fetching AWS budgets for {account_name}: {e}")
            raise

    @staticmethod
    def import_aws_budgets(
        db: Session,
        account_name: str,
        overwrite: bool = False
    ) -> Dict:
        """
        Import budgets from AWS Budgets API into database.

        Args:
            db: Database session
            account_name: AWS account name from database
            overwrite: Whether to update existing budgets with same name

        Returns:
            Import summary with counts
        """
        try:
            # Get AWS account
            account = db.query(AWSAccount).filter(
                AWSAccount.name == account_name,
                AWSAccount.is_active == True
            ).first()

            if not account:
                raise ValueError(f"AWS account {account_name} not found")

            # Fetch budgets from AWS
            aws_budgets = AWSBudgetsService.fetch_aws_budgets(db, account_name)

            imported_count = 0
            updated_count = 0
            skipped_count = 0
            errors = []

            for aws_budget in aws_budgets:
                try:
                    budget_name = aws_budget.get('BudgetName', 'Unnamed Budget')

                    # Check if budget already exists
                    existing = db.query(Budget).filter(
                        Budget.aws_account_id == account.id,
                        Budget.name == budget_name
                    ).first()

                    if existing and not overwrite:
                        skipped_count += 1
                        logger.info(f"Skipping existing budget: {budget_name}")
                        continue

                    # Parse AWS budget data
                    budget_data = AWSBudgetsService._parse_aws_budget(
                        aws_budget,
                        account.id
                    )

                    if existing and overwrite:
                        # Update existing budget
                        for key, value in budget_data.items():
                            if key != 'aws_account_id':  # Don't change account
                                setattr(existing, key, value)
                        db.commit()
                        updated_count += 1
                        logger.info(f"Updated budget: {budget_name}")
                    else:
                        # Create new budget
                        logger.debug(f"Creating budget with data: {budget_data}")
                        try:
                            db_budget = Budget(**budget_data)
                            db.add(db_budget)
                            db.commit()
                            imported_count += 1
                            logger.info(f"Imported budget: {budget_name}")
                        except Exception as create_error:
                            logger.error(f"Failed to create Budget object: {create_error}")
                            logger.error(f"Budget data types: {[(k, type(v).__name__) for k, v in budget_data.items()]}")
                            raise

                except Exception as e:
                    error_msg = f"Error importing budget {aws_budget.get('BudgetName', 'Unknown')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    db.rollback()  # Roll back failed transaction
                    continue

            return {
                'total_found': len(aws_budgets),
                'imported': imported_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"Error importing AWS budgets: {e}")
            raise

    @staticmethod
    def get_budget_forecast(db: Session, account_name: str, budget_name: str = None) -> Dict:
        """
        Get budget forecast from AWS Budgets API.

        This returns the forecasted spend that AWS Budgets calculates,
        which matches what you see in the AWS Console.

        Args:
            db: Database session
            account_name: AWS account name from database
            budget_name: Specific budget name (optional, uses first budget if not provided)

        Returns:
            Dictionary with actual_spend, forecasted_spend, budget_amount
        """
        try:
            # Get AWS account
            account = db.query(AWSAccount).filter(
                AWSAccount.name == account_name,
                AWSAccount.is_active == True
            ).first()

            if not account or not account.account_id:
                raise ValueError(f"AWS account {account_name} not found or missing account ID")

            client = AWSBudgetsService.get_budgets_client(db, account_name)

            if budget_name:
                # Get specific budget
                response = client.describe_budget(
                    AccountId=account.account_id,
                    BudgetName=budget_name
                )
                budget_data = response.get('Budget', {})
            else:
                # Get all budgets and use the first one
                response = client.describe_budgets(
                    AccountId=account.account_id
                )
                budgets = response.get('Budgets', [])
                if not budgets:
                    raise ValueError(f"No budgets found for account {account_name}")
                budget_data = budgets[0]

            # Extract calculated spend
            calculated_spend = budget_data.get('CalculatedSpend', {})
            actual_spend_obj = calculated_spend.get('ActualSpend', {})
            forecasted_spend_obj = calculated_spend.get('ForecastedSpend', {})
            budget_limit = budget_data.get('BudgetLimit', {})

            actual_spend = float(actual_spend_obj.get('Amount', 0))
            forecasted_spend = float(forecasted_spend_obj.get('Amount', 0))
            budget_amount = float(budget_limit.get('Amount', 0))

            logger.info(f"AWS Budgets forecast for {account_name}: actual=${actual_spend:.2f}, forecast=${forecasted_spend:.2f}, budget=${budget_amount:.2f}")

            return {
                'actual_spend': actual_spend,
                'forecasted_spend': forecasted_spend,
                'budget_amount': budget_amount,
                'budget_name': budget_data.get('BudgetName', ''),
                'currency': actual_spend_obj.get('Unit', 'USD')
            }

        except Exception as e:
            logger.error(f"Error getting AWS Budgets forecast for {account_name}: {e}")
            raise

    @staticmethod
    def _parse_aws_budget(aws_budget: Dict, aws_account_id: int) -> Dict:
        """
        Parse AWS budget data into database format.

        Args:
            aws_budget: AWS budget data from API
            aws_account_id: Database AWS account ID

        Returns:
            Dictionary with budget data for database
        """
        # Extract budget amount
        budget_limit = aws_budget.get('BudgetLimit', {})
        amount = float(budget_limit.get('Amount', 0))

        # Determine period from time unit
        time_unit = aws_budget.get('TimeUnit', 'MONTHLY')
        period_map = {
            'MONTHLY': BudgetPeriod.MONTHLY,
            'QUARTERLY': BudgetPeriod.QUARTERLY,
            'ANNUALLY': BudgetPeriod.YEARLY,
            'DAILY': BudgetPeriod.MONTHLY  # Map daily to monthly
        }
        period = period_map.get(time_unit, BudgetPeriod.MONTHLY)

        # Extract time period
        time_period = aws_budget.get('TimePeriod', {})
        start_date_str = time_period.get('Start')
        end_date_str = time_period.get('End')

        # Parse dates - handle different formats and convert to timezone-naive
        try:
            if start_date_str:
                if isinstance(start_date_str, str):
                    # Handle ISO format with or without timezone
                    start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                    # Convert to timezone-naive by removing tzinfo
                    start_date = start_date.replace(tzinfo=None)
                elif isinstance(start_date_str, datetime):
                    # Ensure timezone-naive
                    start_date = start_date_str.replace(tzinfo=None) if start_date_str.tzinfo else start_date_str
                else:
                    start_date = datetime.now()
            else:
                start_date = datetime.now()
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse start date: {start_date_str}, using current date")
            start_date = datetime.now()

        try:
            if end_date_str:
                if isinstance(end_date_str, str):
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    # Convert to timezone-naive by removing tzinfo
                    end_date = end_date.replace(tzinfo=None)
                elif isinstance(end_date_str, datetime):
                    # Ensure timezone-naive
                    end_date = end_date_str.replace(tzinfo=None) if end_date_str.tzinfo else end_date_str
                else:
                    end_date = None
            else:
                end_date = None
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse end date: {end_date_str}, setting to None")
            end_date = None

        # Get notification thresholds (use first threshold if available)
        notifications = aws_budget.get('NotificationsWithSubscribers', [])
        threshold_warning = 80.0
        threshold_critical = 100.0

        if notifications:
            # Get first notification threshold
            first_notification = notifications[0].get('Notification', {})
            threshold = first_notification.get('Threshold')
            comparison = first_notification.get('ComparisonOperator', 'GREATER_THAN')
            notification_type = first_notification.get('ThresholdType', 'PERCENTAGE')

            if notification_type == 'PERCENTAGE' and threshold:
                if comparison == 'GREATER_THAN':
                    threshold_warning = float(threshold)
                    threshold_critical = 100.0
                elif len(notifications) > 1:
                    second_notification = notifications[1].get('Notification', {})
                    second_threshold = second_notification.get('Threshold')
                    if second_threshold:
                        threshold_critical = float(second_threshold)

        # Ensure all types are correct
        return {
            'name': str(aws_budget.get('BudgetName', 'Unnamed Budget')),
            'description': f"Imported from AWS Budgets - {aws_budget.get('BudgetType', 'COST')}",
            'aws_account_id': int(aws_account_id),  # Ensure integer
            'amount': float(amount),  # Ensure float
            'period': period,  # Already enum
            'start_date': start_date,  # Already datetime
            'end_date': end_date,  # Already datetime or None
            'threshold_warning': float(threshold_warning),  # Ensure float
            'threshold_critical': float(threshold_critical),  # Ensure float
            'is_active': True
        }
