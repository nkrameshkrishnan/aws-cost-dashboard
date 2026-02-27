"""
Budget database model.
Stores budget information for AWS accounts with alert thresholds.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database.base import Base


class BudgetPeriod(str, enum.Enum):
    """Budget period types."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class Budget(Base):
    """
    Budget model for tracking cost budgets per AWS account.
    """
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)

    # AWS Account relationship
    # Index on foreign key for efficient lookups
    aws_account_id = Column(Integer, ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    aws_account = relationship("AWSAccount", backref="budgets")

    # Budget details
    amount = Column(Float, nullable=False)  # Budget amount in USD
    period = Column(Enum(BudgetPeriod), default=BudgetPeriod.MONTHLY, nullable=False)

    # Date range
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)  # Null means ongoing

    # Alert thresholds (percentages)
    threshold_warning = Column(Float, default=80.0)  # Warning at 80%
    threshold_critical = Column(Float, default=100.0)  # Critical at 100%

    # Status
    # Index on is_active since we filter by it frequently
    is_active = Column(Boolean, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Budget(id={self.id}, name='{self.name}', amount={self.amount}, period={self.period})>"
