"""
Application configuration management using Pydantic settings.

All values are loaded from environment variables (or a .env file).
The canonical list of every supported variable lives in /.env.example
at the project root.  For production, set variables via .env.production
or your secrets manager — never hardcode values here.
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings — every field maps 1-to-1 to an env var."""

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    APP_NAME: str = "AWS Cost Dashboard"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # -------------------------------------------------------------------------
    # Security  (no defaults in production — values MUST come from env)
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production-min32chars",
        min_length=32,
        description="App secret key — generate with: secrets.token_urlsafe(48)",
    )
    JWT_SECRET_KEY: str = Field(
        default="dev-jwt-secret-key-change-in-production-min32chars",
        min_length=32,
        description="JWT signing key — generate with: secrets.token_urlsafe(48)",
    )
    ENCRYPTION_KEY: str = Field(
        default="",
        description=(
            "Fernet key for AWS credential encryption. "
            "Generate with: from cryptography.fernet import Fernet; Fernet.generate_key()"
        ),
    )

    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------
    API_V1_PREFIX: str = "/api/v1"

    # CORS origins — comma-separated string; all allowed origins go in .env.production
    CORS_ORIGINS_STR: str = "http://localhost:5173,http://localhost:3000"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/aws_cost_dashboard",
        description="PostgreSQL connection URL",
    )

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # -------------------------------------------------------------------------
    # AWS
    # -------------------------------------------------------------------------
    AWS_PROFILE_CONFIG_PATH: str = "/root/.aws/credentials"
    AWS_REGION: str = "us-east-1"

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------
    EXPORT_S3_BUCKET: str = ""
    EXPORT_LOCAL_PATH: str = "/tmp/exports"

    # -------------------------------------------------------------------------
    # Microsoft Teams
    # -------------------------------------------------------------------------
    TEAMS_WEBHOOK_URL: str = ""

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/var/log/cost-dashboard/app.log"

    # -------------------------------------------------------------------------
    # Cache TTL (seconds)
    # -------------------------------------------------------------------------
    CACHE_TTL_CURRENT_MONTH: int = 300      # 5 min
    CACHE_TTL_HISTORICAL: int = 86400       # 24 h
    CACHE_TTL_FORECAST: int = 3600          # 1 h
    CACHE_TTL_SERVICE_BREAKDOWN: int = 900  # 15 min
    CACHE_TTL_BUDGET_STATUS: int = 600      # 10 min
    CACHE_TTL_AUDIT_RESULTS: int = 1800     # 30 min

    # -------------------------------------------------------------------------
    # Feature flags
    # -------------------------------------------------------------------------
    FEATURE_RIGHTSIZING: bool = True
    FEATURE_BUDGETS: bool = True
    FEATURE_FINOPS_AUDIT: bool = True
    FEATURE_ANALYTICS: bool = True
    FEATURE_AUTOMATION: bool = True
    FEATURE_UNIT_COSTS: bool = True

    # -------------------------------------------------------------------------
    # Docs / dev
    # -------------------------------------------------------------------------
    ENABLE_DOCS: bool = True
    ENABLE_TEST_ENDPOINTS: bool = False

    # -------------------------------------------------------------------------
    # Computed properties
    # -------------------------------------------------------------------------
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS_STR into a list."""
        return [o.strip() for o in self.CORS_ORIGINS_STR.split(",") if o.strip()]

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def aws_credentials_path(self) -> str:
        return os.path.expanduser(self.AWS_PROFILE_CONFIG_PATH)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton — imported everywhere as `from app.config import settings`
settings = Settings()
