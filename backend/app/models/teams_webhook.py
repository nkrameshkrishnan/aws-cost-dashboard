"""
Database model for Microsoft Teams webhooks.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database.base import Base


class TeamsWebhook(Base):
    """Microsoft Teams webhook configuration."""

    __tablename__ = "teams_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    webhook_url = Column(Text, nullable=False)  # Encrypted in production
    webhook_type = Column(String(50), default='teams', nullable=False)  # 'teams' or 'power_automate'
    is_active = Column(Boolean, default=True, nullable=False)

    # Notification preferences
    send_budget_alerts = Column(Boolean, default=True, nullable=False)
    send_cost_summaries = Column(Boolean, default=False, nullable=False)
    send_audit_reports = Column(Boolean, default=False, nullable=False)

    # Thresholds for budget alerts
    budget_threshold_percentage = Column(Integer, default=80, nullable=False)  # Trigger at 80%

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_sent_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<TeamsWebhook(id={self.id}, name='{self.name}', active={self.is_active})>"
