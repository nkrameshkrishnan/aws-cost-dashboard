"""
Tests for AWS Session Manager.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import boto3
from botocore.exceptions import ProfileNotFound, NoCredentialsError

from app.aws.session_manager import AWSSessionManager


def _patched_manager(mock_session_class, mock_settings_obj=None):
    """Helper: create a fresh AWSSessionManager with boto3.Session patched."""
    manager = AWSSessionManager()
    return manager


class TestAWSSessionManager:
    """Test AWS Session Manager."""

    def _mock_session(self, account_id="123456789012"):
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": account_id,
            "UserId": "AIDAI123456789EXAMPLE",
            "Arn": f"arn:aws:iam::{account_id}:user/testuser",
        }
        mock_session.client.return_value = mock_sts
        return mock_session, mock_sts

    def test_get_session_default_profile(self, aws_credentials):
        """Test getting session with default profile."""
        with patch("boto3.Session") as mock_session_class:
            mock_session, _ = self._mock_session()
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            session = manager.get_session()

            assert session is not None
            assert session == mock_session

    def test_get_session_caching(self, aws_credentials):
        """Test that sessions are cached."""
        with patch("boto3.Session") as mock_session_class:
            mock_session, _ = self._mock_session()
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()

            session1 = manager.get_session("default")
            session2 = manager.get_session("default")

            assert session1 is session2
            assert mock_session_class.call_count == 1

    def test_get_client_s3(self, aws_credentials):
        """Test getting boto3 S3 client."""
        with patch("boto3.Session") as mock_session_class, \
             patch("app.aws.session_manager.settings") as mock_settings:
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            mock_session = MagicMock()
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_client = MagicMock()

            def client_factory(service, **kwargs):
                return mock_sts if service == "sts" else mock_client

            mock_session.client.side_effect = client_factory
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            client = manager.get_client("s3")

            assert client is not None

    def test_get_client_with_profile(self, aws_credentials):
        """Test getting boto3 client with specific profile."""
        with patch("boto3.Session") as mock_session_class, \
             patch("app.aws.session_manager.settings") as mock_settings:
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            mock_session = MagicMock()
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_client = MagicMock()

            def client_factory(service, **kwargs):
                return mock_sts if service == "sts" else mock_client

            mock_session.client.side_effect = client_factory
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            client = manager.get_client("s3", profile_name="default")

            assert client is not None

    def test_get_client_with_region(self, aws_credentials):
        """Test getting boto3 client with custom region."""
        with patch("boto3.Session") as mock_session_class, \
             patch("app.aws.session_manager.settings") as mock_settings:
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            mock_session = MagicMock()
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_client = MagicMock()
            mock_client.meta.region_name = "ap-southeast-1"

            def client_factory(service, **kwargs):
                if service == "sts":
                    return mock_sts
                mock_client.meta.region_name = kwargs.get("region_name", "us-east-1")
                return mock_client

            mock_session.client.side_effect = client_factory
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            client = manager.get_client("s3", region_name="ap-southeast-1")

            assert client is not None
            assert client.meta.region_name == "ap-southeast-1"

    def test_get_resource_s3(self, aws_credentials):
        """Test getting boto3 S3 resource."""
        with patch("boto3.Session") as mock_session_class, \
             patch("app.aws.session_manager.settings") as mock_settings:
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            mock_session = MagicMock()
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_resource = MagicMock()
            mock_resource.meta = {}

            mock_session.client.return_value = mock_sts
            mock_session.resource.return_value = mock_resource
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            resource = manager.get_resource("s3")

            assert resource is not None
            assert hasattr(resource, "meta")

    def test_get_resource_with_region(self, aws_credentials):
        """Test getting boto3 resource with custom region."""
        with patch("boto3.Session") as mock_session_class, \
             patch("app.aws.session_manager.settings") as mock_settings:
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            mock_session = MagicMock()
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_resource = MagicMock()

            mock_session.client.return_value = mock_sts
            mock_session.resource.return_value = mock_resource
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            resource = manager.get_resource("s3", region_name="eu-west-1")

            assert resource is not None

    def test_validate_profile_success(self, aws_credentials):
        """Test profile validation with valid credentials."""
        with patch("boto3.Session") as mock_session_class:
            mock_session, _ = self._mock_session()
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            result = manager.validate_profile("default")

            assert result["valid"] is True
            assert result["profile_name"] == "default"
            assert "account_id" in result
            assert "arn" in result

    def test_validate_profile_invalid(self):
        """Test profile validation with invalid profile."""
        manager = AWSSessionManager()
        result = manager.validate_profile("non-existent-profile")

        assert result["valid"] is False
        assert result["profile_name"] == "non-existent-profile"
        assert "error" in result

    def test_list_profiles_empty(self):
        """Test listing profiles when credentials file doesn't exist."""
        manager = AWSSessionManager()

        with patch("os.path.exists", return_value=False):
            profiles = manager.list_profiles()
            assert profiles == []

    def test_list_profiles_with_credentials(self):
        """Test listing profiles from credentials file."""
        manager = AWSSessionManager()

        with patch("configparser.ConfigParser") as mock_config:
            mock_parser = MagicMock()
            mock_parser.sections.return_value = ["profile1", "profile2"]
            mock_parser.has_section.return_value = True
            mock_config.return_value = mock_parser

            with patch("os.path.exists", return_value=True):
                profiles = manager.list_profiles()

                assert isinstance(profiles, list)
                assert "default" in profiles

    def test_assume_role(self, aws_credentials):
        """Test assuming IAM role."""
        manager = AWSSessionManager()

        role_arn = "arn:aws:iam::123456789012:role/TestRole"

        with patch.object(manager, "get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_sts = MagicMock()
            mock_sts.assume_role.return_value = {
                "Credentials": {
                    "AccessKeyId": "ASIAIOSFODNN7EXAMPLE",
                    "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY",
                    "SessionToken": "token123",
                    "Expiration": "2024-12-31T23:59:59Z",
                }
            }
            mock_session.client.return_value = mock_sts
            mock_get_session.return_value = mock_session

            assumed_session = manager.assume_role(
                role_arn=role_arn,
                session_name="test-session",
            )

            assert assumed_session is not None
            assert isinstance(assumed_session, boto3.Session)
            mock_sts.assume_role.assert_called_once()

    def test_clear_cache_specific_profile(self, aws_credentials):
        """Test clearing cache for specific profile."""
        with patch("boto3.Session") as mock_session_class:
            mock_session, _ = self._mock_session()
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            manager.get_session("default")
            assert "default" in manager._sessions

            manager.clear_cache("default")
            assert "default" not in manager._sessions

    def test_clear_cache_all(self, aws_credentials):
        """Test clearing all cached sessions."""
        with patch("boto3.Session") as mock_session_class:
            mock_session, _ = self._mock_session()
            mock_session_class.return_value = mock_session

            manager = AWSSessionManager()
            manager.get_session("default")
            assert len(manager._sessions) > 0

            manager.clear_cache()
            assert len(manager._sessions) == 0

    def test_invalid_profile_raises_error(self):
        """Test that invalid profile raises appropriate error."""
        manager = AWSSessionManager()

        with pytest.raises((ProfileNotFound, NoCredentialsError)):
            manager.get_session(profile_name="definitely-non-existent-profile-12345")
