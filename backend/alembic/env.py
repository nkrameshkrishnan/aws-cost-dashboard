"""
Alembic environment configuration.

Reads DATABASE_URL from the application settings so migrations always target
the same database as the running application.  Supports both offline (SQL
script generation) and online (direct connection) modes.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Make the 'app' package importable from the alembic/ subdirectory.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the shared SQLAlchemy Base so autogenerate can see all mapped tables.
from app.database.base import Base  # noqa: E402

# Import every model module so their Table objects are registered on Base.metadata
# before autogenerate compares against the live database.
from app.models.aws_account import AWSAccount        # noqa: F401, E402
from app.models.budget import Budget                 # noqa: F401, E402
from app.models.teams_webhook import TeamsWebhook    # noqa: F401, E402
from app.models.business_metric import BusinessMetric  # noqa: F401, E402
from app.models.async_job import AsyncJob            # noqa: F401, E402

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url with the value from the environment / app settings.
# This means the ini file's placeholder is never actually used at runtime.
try:
    from app.config import settings
    db_url = settings.DATABASE_URL
except Exception:
    # Fallback: read directly from the environment variable so the CLI works
    # even outside the full application context (e.g. in CI).
    db_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))

config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata target for 'autogenerate' support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL to stdout without a live DB connection — useful for
    reviewing migration SQL before applying it.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode against a live database connection.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
