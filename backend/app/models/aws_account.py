"""
AWS Account database model.
Stores AWS credentials securely with encryption.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from datetime import datetime

from app.database.base import Base


class AWSAccount(Base):
    """
    AWS Account model for storing credentials.

    Credentials are encrypted at rest using Fernet symmetric encryption.
    """

    __tablename__ = "aws_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500))

    # Encrypted AWS credentials
    encrypted_access_key_id = Column(String(500), nullable=False)
    encrypted_secret_access_key = Column(String(500), nullable=False)

    # AWS account metadata
    account_id = Column(String(12))  # Will be populated after validation
    region = Column(String(50), default="us-east-1")

    # Status
    is_active = Column(Boolean, default=True)
    last_validated = Column(DateTime(timezone=True), nullable=True)
    validation_error = Column(String(500), nullable=True)

    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<AWSAccount(id={self.id}, name='{self.name}', account_id='{self.account_id}')>"
