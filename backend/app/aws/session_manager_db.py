"""
AWS Session Manager for database-stored credentials.
Creates boto3 sessions using credentials from the database.
"""
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.models.aws_account import AWSAccount
from app.core.encryption import credential_encryption

logger = logging.getLogger(__name__)


class DatabaseSessionManager:
    """
    Manages AWS sessions using credentials stored in the database.
    """

    @staticmethod
    def get_session(db: Session, account_name: str) -> boto3.Session:
        """
        Get or create a boto3 session for a database-stored account.

        Args:
            db: Database session
            account_name: AWS account name from database

        Returns:
            boto3.Session instance

        Raises:
            ValueError: If account not found or inactive
            NoCredentialsError: If credentials are invalid
        """
        # Get account from database
        account = db.query(AWSAccount).filter(
            AWSAccount.name == account_name,
            AWSAccount.is_active == True
        ).first()

        if not account:
            raise ValueError(f"AWS account '{account_name}' not found or inactive")

        # Decrypt credentials
        access_key = credential_encryption.decrypt(account.encrypted_access_key_id)
        secret_key = credential_encryption.decrypt(account.encrypted_secret_access_key)

        try:
            # Create session with decrypted credentials
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=account.region
            )

            # Validate session
            sts = session.client('sts')
            identity = sts.get_caller_identity()

            logger.info(f"Created session for account: {account_name} ({identity['Account']})")
            return session

        except NoCredentialsError:
            logger.error(f"Invalid credentials for account: {account_name}")
            raise
        except ClientError as e:
            logger.error(f"Error creating session for {account_name}: {e}")
            raise

    @staticmethod
    def get_client(
        db: Session,
        account_name: str,
        service_name: str,
        region_name: Optional[str] = None
    ):
        """
        Get an AWS service client for a database-stored account.

        Args:
            db: Database session
            account_name: AWS account name from database
            service_name: AWS service name (e.g., 'ce', 'ec2')
            region_name: AWS region (uses account default if not specified)

        Returns:
            Boto3 service client
        """
        session = DatabaseSessionManager.get_session(db, account_name)

        if region_name:
            return session.client(service_name, region_name=region_name)
        else:
            return session.client(service_name)

    @staticmethod
    def list_account_names(db: Session, active_only: bool = True) -> list[str]:
        """
        List all account names from the database.

        Args:
            db: Database session
            active_only: If True, only return active accounts

        Returns:
            List of account names
        """
        query = db.query(AWSAccount.name)

        if active_only:
            query = query.filter(AWSAccount.is_active == True)

        accounts = query.order_by(AWSAccount.name).all()
        return [account[0] for account in accounts]


# Global instance for convenience
db_session_manager = DatabaseSessionManager()
