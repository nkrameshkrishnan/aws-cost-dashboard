"""
Database utilities and query optimization helpers.
"""
import time
import logging
from typing import Optional
from contextlib import contextmanager
from sqlalchemy import event, create_engine, pool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from app.config import settings
from app.core.performance import performance_metrics

logger = logging.getLogger(__name__)

# SQLAlchemy base
Base = declarative_base()

# Database engine with optimized connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=pool.QueuePool,
    pool_size=10,  # Number of connections to maintain
    max_overflow=20,  # Additional connections when pool is exhausted
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False,  # Set to True for SQL query logging
    connect_args={
        "options": "-c timezone=utc"
    }
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Query performance tracking
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query start time."""
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query execution time and log slow queries."""
    total_time = time.time() - conn.info["query_start_time"].pop()
    duration_ms = total_time * 1000

    # Log slow queries (>1 second)
    if duration_ms > 1000:
        # Truncate long queries for logging
        query_preview = statement[:200] + "..." if len(statement) > 200 else statement
        logger.warning(
            f"Slow query detected ({duration_ms:.2f}ms): {query_preview}"
        )

        # Record in performance metrics
        performance_metrics.record_slow_query(
            query=query_preview,
            duration_ms=duration_ms,
            params={"executemany": executemany}
        )


def get_db() -> Session:
    """
    Database session dependency for FastAPI endpoints.

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Database session context manager.

    Usage:
        with get_db_context() as db:
            items = db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def drop_tables():
    """Drop all database tables (use with caution!)."""
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")


def get_connection_pool_stats() -> dict:
    """
    Get database connection pool statistics.

    Returns:
        Dictionary with pool stats
    """
    pool_stats = engine.pool.status()

    return {
        "pool_size": engine.pool.size(),
        "checked_in_connections": engine.pool.checkedin(),
        "checked_out_connections": engine.pool.checkedout(),
        "overflow_connections": engine.pool.overflow(),
        "total_connections": engine.pool.size() + engine.pool.overflow(),
        "status": pool_stats
    }


class QueryOptimizer:
    """
    Helper class for database query optimization.
    Provides utilities for efficient querying and batch operations.
    """

    @staticmethod
    def batch_query(db: Session, query, batch_size: int = 1000):
        """
        Execute query in batches to avoid memory issues with large result sets.

        Args:
            db: Database session
            query: SQLAlchemy query object
            batch_size: Number of records per batch

        Yields:
            Batches of query results
        """
        offset = 0
        while True:
            batch = query.limit(batch_size).offset(offset).all()
            if not batch:
                break

            yield batch
            offset += batch_size

    @staticmethod
    def bulk_insert(db: Session, model_class, records: list, batch_size: int = 500):
        """
        Efficiently insert multiple records in batches.

        Args:
            db: Database session
            model_class: SQLAlchemy model class
            records: List of dictionaries with record data
            batch_size: Number of records to insert per batch

        Returns:
            Number of records inserted
        """
        if not records:
            return 0

        total_inserted = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            db.bulk_insert_mappings(model_class, batch)
            db.commit()
            total_inserted += len(batch)

        logger.info(f"Bulk inserted {total_inserted} {model_class.__name__} records")
        return total_inserted

    @staticmethod
    def bulk_update(db: Session, model_class, records: list, batch_size: int = 500):
        """
        Efficiently update multiple records in batches.

        Args:
            db: Database session
            model_class: SQLAlchemy model class
            records: List of dictionaries with record data (must include id)
            batch_size: Number of records to update per batch

        Returns:
            Number of records updated
        """
        if not records:
            return 0

        total_updated = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            db.bulk_update_mappings(model_class, batch)
            db.commit()
            total_updated += len(batch)

        logger.info(f"Bulk updated {total_updated} {model_class.__name__} records")
        return total_updated

    @staticmethod
    def optimize_query_with_indexes(db: Session, table_name: str, columns: list):
        """
        Create indexes on specified columns for query optimization.

        Args:
            db: Database session
            table_name: Name of the table
            columns: List of column names to index

        Note:
            This is a utility function. In production, indexes should be
            defined in SQLAlchemy models or Alembic migrations.
        """
        for column in columns:
            index_name = f"idx_{table_name}_{column}"
            try:
                db.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON {table_name}({column})"
                )
                db.commit()
                logger.info(f"Created index: {index_name}")
            except Exception as e:
                logger.error(f"Failed to create index {index_name}: {e}")
                db.rollback()


# Global query optimizer instance
query_optimizer = QueryOptimizer()


def init_database():
    """
    Initialize database with optimizations.
    Call this on application startup.
    """
    # Create tables
    create_tables()

    # Log connection pool configuration
    logger.info(
        f"Database connection pool initialized: "
        f"size={engine.pool.size()}, "
        f"max_overflow={engine.pool._max_overflow}"
    )

    # Enable query performance tracking
    logger.info("Database query performance tracking enabled")
