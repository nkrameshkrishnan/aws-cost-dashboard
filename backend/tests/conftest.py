"""
Global test configuration and fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import fakeredis

from app.main import app
from app.database.base import Base


@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine.

    check_same_thread=False is required so that the in-memory SQLite database
    can be shared between the main test thread and the FastAPI background
    thread used by TestClient.

    All model modules must be imported *before* create_all so that their
    Table objects are registered on Base.metadata.
    """
    # Ensure every ORM model is registered with Base.metadata before we call
    # create_all().  Without these imports the tables won't exist in the
    # in-memory SQLite DB and endpoints will fail with "no such table".
    from app.models.aws_account import AWSAccount          # noqa: F401
    from app.models.budget import Budget                   # noqa: F401
    from app.models.teams_webhook import TeamsWebhook      # noqa: F401
    from app.models.business_metric import BusinessMetric  # noqa: F401
    from app.models.async_job import AsyncJob              # noqa: F401
    from app.models.kpi import KPIThreshold                # noqa: F401

    # StaticPool is critical: sqlite:///:memory: normally creates a fresh
    # empty database for every new connection.  StaticPool forces all
    # connections to reuse the same underlying connection, so the tables
    # created by create_all() are visible to every subsequent session.
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    """Create database session for each test."""
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def redis_client():
    """Create fake Redis client."""
    return fakeredis.FakeRedis()


@pytest.fixture(scope="function")
def client(db_session, redis_client):
    """Create FastAPI test client with auth bypassed.

    The production app is wrapped in PrivateNetworkMiddleware so the FastAPI
    instance is at app.app.  We override get_current_active_user for the
    duration of each test so that auth-protected endpoints are reachable
    without a real JWT token.
    """
    from app.core.security import get_current_active_user
    from app.database.base import get_db

    # Resolve the inner FastAPI instance (app is wrapped in PrivateNetworkMiddleware)
    fastapi_app = app.app if hasattr(app, "app") else app

    # Stub out auth — always return a synthetic test user
    def override_auth():
        return {"id": 1, "username": "testuser", "email": "test@example.com",
                "is_active": True, "is_superuser": False}

    # Stub out the DB dependency — use the in-memory test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_current_active_user] = override_auth
    fastapi_app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def aws_credentials(monkeypatch):
    """Mock AWS credentials."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
