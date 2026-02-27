"""
Business Metrics database model.
Stores business metrics for unit cost calculations.
"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from app.database.base import Base


class BusinessMetric(Base):
    """
    Business Metrics model for storing operational metrics.

    Used to calculate unit costs like cost/user, cost/transaction, etc.
    """

    __tablename__ = "business_metrics"

    id = Column(Integer, primary_key=True, index=True)
    profile_name = Column(String(100), nullable=False, index=True)
    metric_date = Column(Date, nullable=False, index=True)

    # Core business metrics
    active_users = Column(Integer, nullable=True)
    total_transactions = Column(Integer, nullable=True)
    api_calls = Column(Integer, nullable=True)
    data_processed_gb = Column(Float, nullable=True)

    # Custom metrics (extensible)
    custom_metric_1 = Column(Float, nullable=True)
    custom_metric_1_name = Column(String(100), nullable=True)

    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Ensure one record per profile per date
    __table_args__ = (
        UniqueConstraint('profile_name', 'metric_date', name='_profile_date_uc'),
    )

    def __repr__(self):
        return f"<BusinessMetric(profile='{self.profile_name}', date='{self.metric_date}')>"
