"""
AWS Session Manager for multi-account support.
Manages boto3 sessions for multiple AWS profiles and provides client factories.
"""
import boto3
from botocore.exceptions import ProfileNotFound, NoCredentialsError, ClientError
from typing import Dict, List, Optional
import configparser
import logging
import os

from app.config import settings
from app.core.encryption import credential_encryption

logger = logging.getLogger(__name__)


class AWSSessionManager:
    """
    Manages AWS sessions for multiple profiles.
    Provides session pooling and client factory methods.
    """

    def __init__(self, db=None):
        """Initialize the session manager."""
        self._sessions: Dict[str, boto3.Session] = {}
        self._credentials_path = settings.aws_credentials_path
        self.db = db

    def get_session(self, profile_name: str = "default") -> boto3.Session:
        """
        Get or create a boto3 session for the specified profile.

        First tries to get credentials from the database (encrypted).
        Falls back to AWS CLI profiles from ~/.aws/credentials.

        Args:
            profile_name: AWS account name from database or profile name from ~/.aws/credentials

        Returns:
            boto3.Session instance

        Raises:
            ProfileNotFound: If the profile doesn't exist
            NoCredentialsError: If credentials are invalid
        """
        # Return cached session if available
        if profile_name in self._sessions:
            logger.debug(f"Returning cached session for profile: {profile_name}")
            return self._sessions[profile_name]

        # Try to get credentials from database first
        if self.db:
            logger.info(f"Database session provided, attempting to get credentials for: {profile_name}")
            try:
                from app.models.aws_account import AWSAccount

                account = self.db.query(AWSAccount).filter(AWSAccount.name == profile_name).first()

                if not account:
                    logger.warning(f"No account found in database with name: {profile_name}")
                elif not account.is_active:
                    logger.warning(f"Account '{profile_name}' found in database but is not active")
                else:
                    logger.info(f"Found active account in database: {profile_name}")
                    logger.info(f"Creating session from database credentials for: {profile_name}")

                    # Decrypt credentials using the same encryption service that encrypted them
                    logger.debug(f"Decrypting access key for: {profile_name}")
                    access_key_id = credential_encryption.decrypt(account.encrypted_access_key_id)
                    logger.debug(f"Decrypting secret key for: {profile_name}")
                    secret_access_key = credential_encryption.decrypt(account.encrypted_secret_access_key)
                    logger.info(f"Successfully decrypted credentials for: {profile_name}")

                    # Create session with decrypted credentials
                    session = boto3.Session(
                        aws_access_key_id=access_key_id,
                        aws_secret_access_key=secret_access_key
                    )
                    logger.info(f"Created boto3 session for: {profile_name}")

                    # Validate session
                    sts = session.client('sts')
                    identity = sts.get_caller_identity()
                    logger.info(f"Database session validated for account: {identity['Account']}")

                    # Cache the session
                    self._sessions[profile_name] = session
                    return session

            except Exception as e:
                logger.error(f"Error creating session from database for {profile_name}: {e}", exc_info=True)
                # Fall through to try AWS CLI profiles
        else:
            logger.info(f"No database session provided, skipping database credential lookup")

        # Fall back to AWS CLI profiles
        try:
            # Create new session from AWS CLI profile
            logger.info(f"Creating new AWS session from CLI profile: {profile_name}")
            session = boto3.Session(profile_name=profile_name)

            # Validate session by making a test call
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            logger.info(f"CLI session validated for account: {identity['Account']}")

            # Cache the session
            self._sessions[profile_name] = session
            return session

        except ProfileNotFound:
            logger.error(f"AWS profile not found in database or CLI: {profile_name}")
            raise
        except NoCredentialsError:
            logger.error(f"No credentials found for profile: {profile_name}")
            raise
        except ClientError as e:
            logger.error(f"Error validating AWS session: {e}")
            raise

    def list_profiles(self) -> List[str]:
        """
        List all available AWS profiles from credentials file.

        Returns:
            List of profile names
        """
        try:
            if not os.path.exists(self._credentials_path):
                logger.warning(f"AWS credentials file not found: {self._credentials_path}")
                return []

            config = configparser.ConfigParser()
            config.read(self._credentials_path)

            # Filter out default section and return profile names
            profiles = [
                section for section in config.sections()
                if section != 'default'
            ]

            # Add 'default' if it has credentials
            if config.has_section('default') or os.path.exists(
                os.path.expanduser('~/.aws/config')
            ):
                profiles.insert(0, 'default')

            logger.info(f"Found {len(profiles)} AWS profiles")
            return profiles

        except Exception as e:
            logger.error(f"Error reading AWS credentials file: {e}")
            return []

    def validate_profile(self, profile_name: str) -> Dict[str, any]:
        """
        Validate an AWS profile by attempting to get caller identity.

        Args:
            profile_name: AWS profile name to validate

        Returns:
            Dictionary with validation result and account info
        """
        try:
            session = self.get_session(profile_name)
            sts = session.client('sts')
            identity = sts.get_caller_identity()

            return {
                "valid": True,
                "profile_name": profile_name,
                "account_id": identity['Account'],
                "user_id": identity['UserId'],
                "arn": identity['Arn']
            }

        except Exception as e:
            logger.error(f"Profile validation failed for {profile_name}: {e}")
            return {
                "valid": False,
                "profile_name": profile_name,
                "error": str(e)
            }

    def get_client(
        self,
        service_name: str,
        profile_name: str = "default",
        region_name: Optional[str] = None
    ):
        """
        Get an AWS service client for a specific profile.

        Args:
            service_name: AWS service name (e.g., 'ce', 'ec2', 'budgets')
            profile_name: AWS profile name
            region_name: AWS region (defaults to config setting)

        Returns:
            Boto3 service client
        """
        session = self.get_session(profile_name)
        region = region_name or settings.AWS_DEFAULT_REGION

        logger.debug(f"Creating {service_name} client for profile {profile_name} in {region}")
        return session.client(service_name, region_name=region)

    def get_resource(
        self,
        service_name: str,
        profile_name: str = "default",
        region_name: Optional[str] = None
    ):
        """
        Get an AWS service resource for a specific profile.

        Args:
            service_name: AWS service name (e.g., 's3', 'dynamodb')
            profile_name: AWS profile name
            region_name: AWS region (defaults to config setting)

        Returns:
            Boto3 service resource
        """
        session = self.get_session(profile_name)
        region = region_name or settings.AWS_DEFAULT_REGION

        logger.debug(f"Creating {service_name} resource for profile {profile_name} in {region}")
        return session.resource(service_name, region_name=region)

    def assume_role(
        self,
        role_arn: str,
        session_name: str = "aws-cost-dashboard",
        profile_name: str = "default"
    ) -> boto3.Session:
        """
        Assume an IAM role and return a session with temporary credentials.

        Args:
            role_arn: ARN of the role to assume
            session_name: Name for the assumed role session
            profile_name: Profile to use for assuming the role

        Returns:
            boto3.Session with assumed role credentials
        """
        try:
            session = self.get_session(profile_name)
            sts = session.client('sts')

            logger.info(f"Assuming role: {role_arn}")
            response = sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name
            )

            credentials = response['Credentials']

            # Create new session with temporary credentials
            assumed_session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )

            return assumed_session

        except ClientError as e:
            logger.error(f"Error assuming role {role_arn}: {e}")
            raise

    def clear_cache(self, profile_name: Optional[str] = None):
        """
        Clear cached sessions.

        Args:
            profile_name: Specific profile to clear, or None to clear all
        """
        if profile_name:
            if profile_name in self._sessions:
                del self._sessions[profile_name]
                logger.info(f"Cleared cached session for profile: {profile_name}")
        else:
            self._sessions.clear()
            logger.info("Cleared all cached sessions")


# Global session manager instance
session_manager = AWSSessionManager()
