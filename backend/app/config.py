"""
Application configuration management using Pydantic settings.
Loads configuration from environment variables and .env file.
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application Settings
    APP_NAME: str = "AWS Cost Dashboard"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production-min32chars", min_length=32)

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    # Add production GitHub Pages and common localhost dev origins
    CORS_ORIGINS_STR: str = "http://localhost:5173,http://localhost:3000,https://nkrameshkrishnan.github.io/aws-cost-dashboard"

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/aws_cost_dashboard",
        description="PostgreSQL database URL"
    )

    # Redis Cache Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # AWS Configuration
    AWS_DEFAULT_REGION: str = "us-east-1"
    AWS_PROFILE_CONFIG_PATH: str = Field(
        default="~/.aws/credentials",
        description="Path to AWS credentials file"
    )
    # LocalStack (local AWS mocking)
    USE_LOCALSTACK: bool = True
    LOCALSTACK_ENDPOINT_URL: str = "http://localstack:4566"
    AWS_ACCESS_KEY_ID: str = Field(default="test")
    AWS_SECRET_ACCESS_KEY: str = Field(default="test")

    # Export Settings
    EXPORT_S3_BUCKET: str = ""
    EXPORT_LOCAL_PATH: str = "/tmp/exports"

    # Microsoft Teams Integration
    TEAMS_WEBHOOK_URL: str = ""

    # JWT Authentication
    JWT_SECRET_KEY: str = Field(default="dev-jwt-secret-key-change-in-production-min32chars", min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption for AWS Credentials in Database
    ENCRYPTION_KEY: str = Field(
        default="2nF7qR9xK3mP8vL5tJ4wH6eC1bN0aY3sD7fG2hK9mQ8=",  # Default key for development
        description="Fernet encryption key for AWS credentials (must be 32 url-safe base64-encoded bytes)"
    )

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/var/log/cost-dashboard/app.log"

    # Cache TTL Settings (in seconds)
    CACHE_TTL_CURRENT_MONTH: int = 300  # 5 minutes
    CACHE_TTL_HISTORICAL: int = 86400  # 24 hours
    CACHE_TTL_FORECAST: int = 3600  # 1 hour
    CACHE_TTL_SERVICE_BREAKDOWN: int = 900  # 15 minutes
    CACHE_TTL_BUDGET_STATUS: int = 600  # 10 minutes
    CACHE_TTL_AUDIT_RESULTS: int = 1800  # 30 minutes

    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(',') if origin.strip()]

    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def aws_credentials_path(self) -> str:
        """Expand AWS credentials path."""
        return os.path.expanduser(self.AWS_PROFILE_CONFIG_PATH)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()
