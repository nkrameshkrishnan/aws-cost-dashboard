"""
Database base model and session management.
"""
import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

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


def upgrade_db() -> None:
    """
    Apply all pending Alembic migrations to bring the schema to 'head'.

    This is the production-safe way to manage schema changes.  Call this
    from the application startup event instead of init_db().

    For existing databases that were bootstrapped with create_all() before
    Alembic was introduced, stamp them at the baseline revision once, then
    upgrade:

        alembic stamp 0001
        alembic upgrade head
    """
    from alembic.config import Config
    from alembic import command

    # Locate alembic.ini relative to this file:
    # backend/app/database/base.py -> backend/alembic.ini (two dirs up)
    ini_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
    )

    alembic_cfg = Config(ini_path)
    # Ensure the URL always comes from app settings, not the ini placeholder.
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    logger.info("Running Alembic migrations …")
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations complete.")


def init_db() -> None:
    """
    Create all tables via SQLAlchemy metadata (test / development only).

    WARNING: Do NOT call this in production.  It has no awareness of schema
    history and will silently skip columns that exist on a model but are
    missing from the live table.  Use upgrade_db() for production deployments.

    This function is retained for use in unit tests where an in-memory
    SQLite database is created fresh for each test run.
    """
    # Import models to ensure they are registered with SQLAlchemy
    from app.models.aws_account import AWSAccount  # noqa: F401
    from app.models.budget import Budget  # noqa: F401
    from app.models.teams_webhook import TeamsWebhook  # noqa: F401
    from app.models.business_metric import BusinessMetric  # noqa: F401
    from app.models.async_job import AsyncJob  # noqa: F401

    Base.metadata.create_all(bind=engine)
