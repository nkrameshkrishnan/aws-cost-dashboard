"""
Database base model and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Database dependency for FastAPI.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    # Import models to ensure they are registered with SQLAlchemy
    from app.models.aws_account import AWSAccount  # noqa: F401
    from app.models.budget import Budget  # noqa: F401
    from app.models.teams_webhook import TeamsWebhook  # noqa: F401
    from app.models.business_metric import BusinessMetric  # noqa: F401
    from app.models.async_job import AsyncJob  # noqa: F401

    Base.metadata.create_all(bind=engine)
