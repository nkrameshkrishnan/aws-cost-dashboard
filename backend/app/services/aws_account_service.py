"""
AWS Account service for managing stored accounts and credentials.
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from app.models.aws_account import AWSAccount
from app.schemas.aws_account import (
    AWSAccountCreate,
    AWSAccountUpdate,
    AWSAccountValidation
)
from app.core.encryption import credential_encryption
from app.core.cache import cache_manager
from app.core.cache_config import AWS_ACCOUNTS

logger = logging.getLogger(__name__)


class AWSAccountService:
    """Service for managing AWS accounts in the database."""

    @staticmethod
    def create_account(db: Session, account_data: AWSAccountCreate) -> AWSAccount:
        """
        Create a new AWS account with encrypted credentials.

        Args:
            db: Database session
            account_data: Account creation data

        Returns:
            Created AWS account
        """
        # Encrypt credentials
        encrypted_access_key = credential_encryption.encrypt(account_data.access_key_id)
        encrypted_secret_key = credential_encryption.encrypt(account_data.secret_access_key)

        # Create account model
        db_account = AWSAccount(
            name=account_data.name,
            description=account_data.description,
            encrypted_access_key_id=encrypted_access_key,
            encrypted_secret_access_key=encrypted_secret_key,
            region=account_data.region,
            is_active=True
        )

        # Validate credentials and get account ID
        validation = AWSAccountService.validate_credentials(
            account_data.access_key_id,
            account_data.secret_access_key
        )

        if validation.valid:
            db_account.account_id = validation.account_id
            db_account.last_validated = datetime.utcnow()
            db_account.validation_error = None
        else:
            db_account.validation_error = validation.error

        db.add(db_account)
        db.commit()
        db.refresh(db_account)

        # Invalidate accounts list cache
        AWSAccountService._invalidate_accounts_cache()

        logger.info(f"Created AWS account: {db_account.name} (ID: {db_account.id})")
        return db_account

    @staticmethod
    def get_account(db: Session, account_id: int) -> Optional[AWSAccount]:
        """Get an AWS account by ID."""
        return db.query(AWSAccount).filter(AWSAccount.id == account_id).first()

    @staticmethod
    def get_account_by_name(db: Session, name: str) -> Optional[AWSAccount]:
        """Get an AWS account by name."""
        return db.query(AWSAccount).filter(AWSAccount.name == name).first()

    @staticmethod
    def list_accounts(db: Session, active_only: bool = True) -> List[AWSAccount]:
        """
        List all AWS accounts with caching.

        Args:
            db: Database session
            active_only: If True, only return active accounts

        Returns:
            List of AWS accounts
        """
        # Generate cache key
        cache_key = cache_manager._generate_key(
            'aws_accounts:list',
            'active' if active_only else 'all'
        )

        # Try to get from cache
        cached_data = cache_manager.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for AWS accounts list (active_only={active_only})")
            # Return cached account IDs and refresh from DB to get full objects
            # This ensures we have the latest data while still benefiting from cache
            account_ids = cached_data
            if account_ids:
                query = db.query(AWSAccount).filter(AWSAccount.id.in_(account_ids))
                return query.order_by(AWSAccount.name).all()
            return []

        logger.info(f"Cache miss for AWS accounts list (active_only={active_only}), fetching from DB...")

        # Query database
        query = db.query(AWSAccount)
        if active_only:
            query = query.filter(AWSAccount.is_active == True)

        accounts = query.order_by(AWSAccount.name).all()

        # Cache account IDs (not full objects to avoid serialization issues)
        account_ids = [account.id for account in accounts]
        cache_manager.set(cache_key, account_ids, ttl=AWS_ACCOUNTS)
        logger.info(f"Cached AWS accounts list (TTL: {AWS_ACCOUNTS}s)")

        return accounts

    @staticmethod
    def update_account(
        db: Session,
        account_id: int,
        account_data: AWSAccountUpdate
    ) -> Optional[AWSAccount]:
        """
        Update an AWS account.

        Args:
            db: Database session
            account_id: Account ID to update
            account_data: Update data

        Returns:
            Updated account or None if not found
        """
        db_account = AWSAccountService.get_account(db, account_id)
        if not db_account:
            return None

        # Update fields
        update_data = account_data.dict(exclude_unset=True)

        # Handle credential updates
        if "access_key_id" in update_data:
            db_account.encrypted_access_key_id = credential_encryption.encrypt(
                update_data.pop("access_key_id")
            )

        if "secret_access_key" in update_data:
            db_account.encrypted_secret_access_key = credential_encryption.encrypt(
                update_data.pop("secret_access_key")
            )

        # Update other fields
        for field, value in update_data.items():
            setattr(db_account, field, value)

        # Revalidate if credentials were updated
        if "access_key_id" in account_data.dict(exclude_unset=True) or \
           "secret_access_key" in account_data.dict(exclude_unset=True):
            access_key = credential_encryption.decrypt(db_account.encrypted_access_key_id)
            secret_key = credential_encryption.decrypt(db_account.encrypted_secret_access_key)

            validation = AWSAccountService.validate_credentials(access_key, secret_key)
            if validation.valid:
                db_account.account_id = validation.account_id
                db_account.last_validated = datetime.utcnow()
                db_account.validation_error = None
            else:
                db_account.validation_error = validation.error

        db.commit()
        db.refresh(db_account)

        # Invalidate accounts list cache
        AWSAccountService._invalidate_accounts_cache()

        logger.info(f"Updated AWS account: {db_account.name} (ID: {account_id})")
        return db_account

    @staticmethod
    def delete_account(db: Session, account_id: int) -> bool:
        """
        Delete an AWS account and all related data.

        Args:
            db: Database session
            account_id: Account ID to delete

        Returns:
            True if deleted, False if not found
        """
        from app.models.budget import Budget

        db_account = AWSAccountService.get_account(db, account_id)
        if not db_account:
            return False

        # Delete related budgets first (cascade will handle this, but explicit is better)
        db.query(Budget).filter(Budget.aws_account_id == account_id).delete()

        # Delete the account
        db.delete(db_account)
        db.commit()

        # Invalidate accounts list cache
        AWSAccountService._invalidate_accounts_cache()

        logger.info(f"Deleted AWS account and related data: {db_account.name} (ID: {account_id})")
        return True

    @staticmethod
    def get_decrypted_credentials(db: Session, account_id: int) -> Optional[tuple]:
        """
        Get decrypted credentials for an AWS account.

        Args:
            db: Database session
            account_id: Account ID

        Returns:
            Tuple of (access_key_id, secret_access_key) or None
        """
        db_account = AWSAccountService.get_account(db, account_id)
        if not db_account:
            return None

        access_key = credential_encryption.decrypt(db_account.encrypted_access_key_id)
        secret_key = credential_encryption.decrypt(db_account.encrypted_secret_access_key)

        return (access_key, secret_key)

    @staticmethod
    def validate_credentials(
        access_key_id: str,
        secret_access_key: str
    ) -> AWSAccountValidation:
        """
        Validate AWS credentials by calling STS GetCallerIdentity.

        Args:
            access_key_id: AWS Access Key ID
            secret_access_key: AWS Secret Access Key

        Returns:
            Validation result
        """
        try:
            # Create a temporary session
            session = boto3.Session(
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key
            )

            # Call STS to validate credentials
            sts = session.client('sts')
            identity = sts.get_caller_identity()

            return AWSAccountValidation(
                valid=True,
                account_id=identity['Account'],
                user_id=identity['UserId'],
                arn=identity['Arn']
            )

        except NoCredentialsError as e:
            logger.error(f"No credentials provided: {e}")
            return AWSAccountValidation(
                valid=False,
                error="No credentials provided"
            )

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))

            logger.error(f"AWS credential validation failed: {error_code} - {error_msg}")

            return AWSAccountValidation(
                valid=False,
                error=f"{error_code}: {error_msg}"
            )

        except Exception as e:
            logger.error(f"Unexpected error validating credentials: {e}")
            return AWSAccountValidation(
                valid=False,
                error=str(e)
            )

    @staticmethod
    def _invalidate_accounts_cache():
        """Invalidate AWS accounts list cache."""
        cache_manager.delete(cache_manager._generate_key('aws_accounts:list', 'active'))
        cache_manager.delete(cache_manager._generate_key('aws_accounts:list', 'all'))
        logger.info("Invalidated AWS accounts list cache")
