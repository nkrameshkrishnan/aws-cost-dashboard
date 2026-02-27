"""
AWS Account management API endpoints.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import logging

from app.database.base import get_db
from app.schemas.aws_account import (
    AWSAccountCreate,
    AWSAccountUpdate,
    AWSAccountResponse,
    AWSAccountValidation
)
from app.services.aws_account_service import AWSAccountService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=AWSAccountResponse, status_code=201)
async def create_aws_account(
    account_data: AWSAccountCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new AWS account with credentials.

    Credentials are encrypted before storage.
    """
    try:
        # Check if account name already exists
        existing = AWSAccountService.get_account_by_name(db, account_data.name)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Account with name '{account_data.name}' already exists"
            )

        account = AWSAccountService.create_account(db, account_data)
        return account

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating AWS account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[AWSAccountResponse])
async def list_aws_accounts(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    List all AWS accounts.

    Args:
        active_only: If True, only return active accounts
    """
    try:
        accounts = AWSAccountService.list_accounts(db, active_only=active_only)
        return accounts

    except Exception as e:
        logger.error(f"Error listing AWS accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}", response_model=AWSAccountResponse)
async def get_aws_account(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Get an AWS account by ID.
    """
    try:
        account = AWSAccountService.get_account(db, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="AWS account not found")

        return account

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AWS account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{account_id}", response_model=AWSAccountResponse)
async def update_aws_account(
    account_id: int,
    account_data: AWSAccountUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an AWS account.

    If credentials are updated, they will be re-validated.
    """
    try:
        account = AWSAccountService.update_account(db, account_id, account_data)
        if not account:
            raise HTTPException(status_code=404, detail="AWS account not found")

        return account

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating AWS account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{account_id}", status_code=204)
async def delete_aws_account(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete an AWS account.

    This will permanently delete the account and its credentials.
    """
    try:
        deleted = AWSAccountService.delete_account(db, account_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="AWS account not found")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting AWS account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/validate", response_model=AWSAccountValidation)
async def validate_aws_account(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Validate AWS account credentials.

    Tests the stored credentials by calling AWS STS GetCallerIdentity.
    """
    try:
        credentials = AWSAccountService.get_decrypted_credentials(db, account_id)
        if not credentials:
            raise HTTPException(status_code=404, detail="AWS account not found")

        access_key, secret_key = credentials
        validation = AWSAccountService.validate_credentials(access_key, secret_key)

        return validation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating AWS account: {e}")
        raise HTTPException(status_code=500, detail=str(e))
