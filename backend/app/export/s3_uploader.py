"""
S3 uploader service for uploading generated reports to S3.
"""
import boto3
import logging
from datetime import datetime
from typing import Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3UploaderService:
    """Service for uploading reports to AWS S3."""

    @staticmethod
    def upload_report(
        file_content: bytes,
        bucket_name: str,
        file_name: str,
        aws_session: Optional[boto3.Session] = None,
        content_type: str = 'application/pdf',
        folder_prefix: str = 'reports'
    ) -> dict:
        """
        Upload a report file to S3.

        Args:
            file_content: File content as bytes
            bucket_name: S3 bucket name
            file_name: Name of the file to save
            aws_session: Optional boto3 session (uses default if not provided)
            content_type: MIME type of the file
            folder_prefix: S3 folder prefix (default: 'reports')

        Returns:
            Dictionary with upload status and S3 URL
        """
        try:
            # Use provided session or create default one
            s3_client = aws_session.client('s3') if aws_session else boto3.client('s3')

            # Generate S3 key with timestamp
            timestamp = datetime.now().strftime('%Y/%m/%d')
            s3_key = f"{folder_prefix}/{timestamp}/{file_name}"

            # Upload file
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                ServerSideEncryption='AES256'  # Enable encryption at rest
            )

            # Generate S3 URL
            s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"

            logger.info(f"Successfully uploaded report to S3: {s3_url}")

            return {
                'success': True,
                's3_url': s3_url,
                's3_bucket': bucket_name,
                's3_key': s3_key,
                'message': 'Report uploaded successfully'
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"S3 upload failed: {error_code} - {error_message}")

            return {
                'success': False,
                'error': f"S3 upload failed: {error_code} - {error_message}"
            }

        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }

    @staticmethod
    def upload_audit_report(
        file_content: bytes,
        account_name: str,
        report_format: str,
        bucket_name: str,
        aws_session: Optional[boto3.Session] = None
    ) -> dict:
        """
        Upload an audit report to S3 with standardized naming.

        Args:
            file_content: Report content as bytes
            account_name: AWS account name
            report_format: Report format (pdf, xlsx, csv)
            bucket_name: S3 bucket name
            aws_session: Optional boto3 session

        Returns:
            Upload status dictionary
        """
        # Generate standardized file name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_account_name = account_name.replace(' ', '_').replace('/', '_')
        file_name = f"finops_audit_{safe_account_name}_{timestamp}.{report_format}"

        # Determine content type
        content_types = {
            'pdf': 'application/pdf',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'csv': 'text/csv',
            'json': 'application/json'
        }
        content_type = content_types.get(report_format, 'application/octet-stream')

        return S3UploaderService.upload_report(
            file_content=file_content,
            bucket_name=bucket_name,
            file_name=file_name,
            aws_session=aws_session,
            content_type=content_type,
            folder_prefix='finops-reports'
        )

    @staticmethod
    def generate_presigned_url(
        bucket_name: str,
        s3_key: str,
        aws_session: Optional[boto3.Session] = None,
        expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for temporary access to a report.

        Args:
            bucket_name: S3 bucket name
            s3_key: S3 object key
            aws_session: Optional boto3 session
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL or None if generation fails
        """
        try:
            s3_client = aws_session.client('s3') if aws_session else boto3.client('s3')

            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )

            return presigned_url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
