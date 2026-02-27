"""
Pydantic schemas for AWS Account API.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AWSAccountCreate(BaseModel):
    """Schema for creating a new AWS account."""

    name: str = Field(..., min_length=1, max_length=100, description="Account name")
    description: Optional[str] = Field(None, max_length=500, description="Account description")
    access_key_id: str = Field(..., min_length=16, max_length=128, description="AWS Access Key ID")
    secret_access_key: str = Field(..., min_length=16, max_length=128, description="AWS Secret Access Key")
    region: str = Field(default="us-east-1", description="Default AWS region")


class AWSAccountUpdate(BaseModel):
    """Schema for updating an AWS account."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    access_key_id: Optional[str] = Field(None, min_length=16, max_length=128)
    secret_access_key: Optional[str] = Field(None, min_length=16, max_length=128)
    region: Optional[str] = None
    is_active: Optional[bool] = None


class AWSAccountResponse(BaseModel):
    """Schema for AWS account response (without credentials)."""

    id: int
    name: str
    description: Optional[str] = None
    account_id: Optional[str] = None
    region: str
    is_active: bool
    last_validated: Optional[datetime] = None
    validation_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AWSAccountValidation(BaseModel):
    """Schema for AWS account validation response."""

    valid: bool
    account_id: Optional[str] = None
    user_id: Optional[str] = None
    arn: Optional[str] = None
    error: Optional[str] = None
