"""
Async Job model for long-running operations.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.sql import func
import enum

from app.database.base import Base


class JobStatus(str, enum.Enum):
    """Job status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, enum.Enum):
    """Job type enum."""
    UNIT_COST_CALCULATE = "unit_cost_calculate"
    UNIT_COST_TREND = "unit_cost_trend"


class AsyncJob(Base):
    """Async job for long-running operations."""

    __tablename__ = "async_jobs"

    id = Column(String, primary_key=True, index=True)
    job_type = Column(Enum(JobType), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)

    # Input parameters (JSON string)
    parameters = Column(Text, nullable=False)

    # Result (JSON string)
    result = Column(Text, nullable=True)

    # Error message if failed
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<AsyncJob(id={self.id}, type={self.job_type}, status={self.status})>"
