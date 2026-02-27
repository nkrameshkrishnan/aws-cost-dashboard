"""
S3 resource auditing service.
"""
import boto3
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from app.schemas.audit import (
    S3BucketWithoutLifecycle,
    S3IncompleteMultipartUpload,
    S3AuditResults
)

logger = logging.getLogger(__name__)


# S3 storage pricing per GB per month (USD) for us-east-1
S3_STORAGE_PRICING = {
    'STANDARD': 0.023,
    'INTELLIGENT_TIERING': 0.023,  # + monitoring fee
    'STANDARD_IA': 0.0125,
    'ONEZONE_IA': 0.01,
    'GLACIER': 0.004,
    'GLACIER_IR': 0.004,
    'DEEP_ARCHIVE': 0.00099,
}


class S3Auditor:
    """Service for auditing S3 buckets."""

    @staticmethod
    def audit_s3_buckets(
        session: boto3.Session,
        multipart_age_threshold: int = 7
    ) -> S3AuditResults:
        """
        Audit S3 buckets for optimization opportunities.

        Args:
            session: Boto3 session
            multipart_age_threshold: Days threshold for incomplete multipart uploads

        Returns:
            S3AuditResults with findings
        """
        try:
            s3_client = session.client('s3')
            cloudwatch_client = session.client('cloudwatch')
            region = session.region_name or 'us-east-1'

            # Get all buckets
            response = s3_client.list_buckets()
            buckets = response.get('Buckets', [])

            buckets_without_lifecycle = []
            incomplete_multipart_uploads = []

            for bucket in buckets:
                bucket_name = bucket['Name']

                # Check bucket location
                try:
                    location_response = s3_client.get_bucket_location(Bucket=bucket_name)
                    bucket_region = location_response.get('LocationConstraint') or 'us-east-1'
                except s3_client.exceptions.ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', '')
                    if error_code in ['InvalidRequest', 'IllegalLocationConstraintException']:
                        # Bucket might have Transfer Acceleration enabled or other special config
                        logger.debug(f"Skipping location check for bucket {bucket_name}: {error_code}")
                        bucket_region = region  # Use session region as fallback
                    else:
                        logger.warning(f"Could not get location for bucket {bucket_name}: {e}")
                        bucket_region = 'unknown'
                except Exception as e:
                    # Check if it's a Transfer Acceleration or path-style addressing error
                    error_message = str(e)
                    if 'Path-style addressing' in error_message or 'S3 Accelerate' in error_message:
                        logger.debug(f"Skipping location check for bucket {bucket_name}: Transfer Acceleration config")
                        bucket_region = region  # Use session region as fallback
                    else:
                        logger.warning(f"Could not get location for bucket {bucket_name}: {e}")
                        bucket_region = 'unknown'

                # Audit lifecycle policies
                lifecycle_finding = S3Auditor._audit_lifecycle_policy(
                    s3_client,
                    cloudwatch_client,
                    bucket_name,
                    bucket['CreationDate'],
                    bucket_region
                )
                if lifecycle_finding:
                    buckets_without_lifecycle.append(lifecycle_finding)

                # Audit incomplete multipart uploads
                multipart_findings = S3Auditor._audit_multipart_uploads(
                    s3_client,
                    bucket_name,
                    multipart_age_threshold,
                    bucket_region
                )
                incomplete_multipart_uploads.extend(multipart_findings)

            # Calculate totals
            total_lifecycle_savings = sum(b.potential_monthly_savings for b in buckets_without_lifecycle)
            total_multipart_waste = sum(u.estimated_monthly_cost for u in incomplete_multipart_uploads)
            total_savings = total_lifecycle_savings + total_multipart_waste

            return S3AuditResults(
                buckets_without_lifecycle=buckets_without_lifecycle,
                incomplete_multipart_uploads=incomplete_multipart_uploads,
                total_lifecycle_savings=round(total_lifecycle_savings, 2),
                total_multipart_waste=round(total_multipart_waste, 2),
                total_potential_savings=round(total_savings, 2)
            )

        except Exception as e:
            logger.error(f"Error auditing S3 buckets: {e}")
            return S3AuditResults()

    @staticmethod
    def _audit_lifecycle_policy(
        s3_client,
        cloudwatch_client,
        bucket_name: str,
        creation_date: datetime,
        region: str
    ) -> S3BucketWithoutLifecycle:
        """Check if bucket has lifecycle policy configured."""
        try:
            # Check if lifecycle policy exists
            has_lifecycle = False
            try:
                s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
                has_lifecycle = True
            except Exception as e:
                # Check if it's a "no lifecycle configuration" error or Transfer Acceleration issue
                error_message = str(e)
                if ('NoSuchLifecycleConfiguration' in error_message or
                    'does not exist' in error_message.lower() or
                    'InvalidRequest' in error_message or
                    'Transfer Acceleration' in error_message):
                    # Bucket either has no lifecycle or has Transfer Acceleration issues
                    # In either case, skip lifecycle audit for this bucket
                    logger.debug(f"Skipping lifecycle check for {bucket_name}: {error_message[:100]}")
                    return None
                else:
                    logger.warning(f"Could not check lifecycle for {bucket_name}: {e}")
                    return None

            if has_lifecycle:
                return None  # Bucket has lifecycle policy, no finding

            # Get bucket size and object count from CloudWatch
            bucket_size_gb, object_count = S3Auditor._get_bucket_metrics(
                cloudwatch_client,
                bucket_name
            )

            # Only flag buckets with significant size (>1GB)
            if bucket_size_gb < 1.0:
                return None

            # Estimate storage class breakdown (assume all STANDARD if no lifecycle)
            storage_class_breakdown = {
                'STANDARD': bucket_size_gb
            }

            # Calculate current cost (all in STANDARD)
            current_monthly_cost = bucket_size_gb * S3_STORAGE_PRICING['STANDARD']

            # Estimate potential savings with lifecycle policy
            # Assume 40% can move to IA, 20% to Glacier
            potential_savings = (
                bucket_size_gb * 0.4 * (S3_STORAGE_PRICING['STANDARD'] - S3_STORAGE_PRICING['STANDARD_IA']) +
                bucket_size_gb * 0.2 * (S3_STORAGE_PRICING['STANDARD'] - S3_STORAGE_PRICING['GLACIER'])
            )

            # Get tags
            tags = {}
            try:
                tags_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
                for tag in tags_response.get('TagSet', []):
                    tags[tag['Key']] = tag['Value']
            except Exception:
                pass  # No tags

            if potential_savings > 1.0:  # Only flag if savings > $1/month
                return S3BucketWithoutLifecycle(
                    bucket_name=bucket_name,
                    creation_date=creation_date,
                    total_size_gb=round(bucket_size_gb, 2),
                    object_count=object_count,
                    storage_class_breakdown=storage_class_breakdown,
                    estimated_monthly_cost=round(current_monthly_cost, 2),
                    potential_monthly_savings=round(potential_savings, 2),
                    region=region,
                    tags=tags,
                    recommendation=f"Bucket has {bucket_size_gb:.1f}GB without lifecycle policy. Implement lifecycle rules to transition to IA/Glacier and save ~${potential_savings:.2f}/month."
                )

        except Exception as e:
            logger.error(f"Error auditing lifecycle for {bucket_name}: {e}")

        return None

    @staticmethod
    def _audit_multipart_uploads(
        s3_client,
        bucket_name: str,
        age_threshold: int,
        region: str
    ) -> List[S3IncompleteMultipartUpload]:
        """Find incomplete multipart uploads."""
        incomplete_uploads = []

        try:
            response = s3_client.list_multipart_uploads(Bucket=bucket_name)
            uploads = response.get('Uploads', [])
        except s3_client.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'InvalidRequest':
                # S3 Transfer Acceleration not configured - this is normal, skip this bucket
                logger.debug(f"Skipping multipart upload check for bucket {bucket_name}: Transfer Acceleration not configured")
                return incomplete_uploads
            else:
                logger.error(f"Error listing multipart uploads for {bucket_name}: {e}")
                return incomplete_uploads
        except Exception as e:
            logger.error(f"Error finding incomplete uploads for {bucket_name}: {e}")
            return incomplete_uploads

        try:
            for upload in uploads:
                upload_id = upload['UploadId']
                key = upload['Key']
                initiated_date = upload['Initiated']

                # Calculate age
                days_old = (datetime.now(initiated_date.tzinfo) - initiated_date).days

                if days_old >= age_threshold:
                    # Get parts to estimate size
                    try:
                        parts_response = s3_client.list_parts(
                            Bucket=bucket_name,
                            Key=key,
                            UploadId=upload_id
                        )
                        parts = parts_response.get('Parts', [])
                        parts_count = len(parts)

                        # Estimate size (sum of part sizes)
                        total_size_bytes = sum(part.get('Size', 0) for part in parts)
                        size_gb = total_size_bytes / (1024 ** 3)

                        # Calculate monthly cost
                        monthly_cost = size_gb * S3_STORAGE_PRICING['STANDARD']

                        if monthly_cost > 0.01:  # Only flag if cost > $0.01/month
                            incomplete_upload = S3IncompleteMultipartUpload(
                                bucket_name=bucket_name,
                                upload_id=upload_id,
                                key=key,
                                initiated_date=initiated_date,
                                days_old=days_old,
                                parts_count=parts_count,
                                estimated_size_gb=round(size_gb, 3),
                                estimated_monthly_cost=round(monthly_cost, 2),
                                region=region,
                                recommendation=f"Incomplete multipart upload is {days_old} days old. Abort upload to free {size_gb:.2f}GB and save ${monthly_cost:.2f}/month."
                            )
                            incomplete_uploads.append(incomplete_upload)

                    except Exception as e:
                        # Check if it's an AccessDenied error (expected if IAM policy lacks s3:ListMultipartUploadParts)
                        error_message = str(e)
                        if 'AccessDenied' in error_message or 'ListMultipartUploadParts' in error_message:
                            logger.debug(f"Skipping multipart upload {upload_id[:20]}... for {bucket_name}: Missing s3:ListMultipartUploadParts permission")
                        else:
                            logger.warning(f"Could not get parts for upload {upload_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing uploads for {bucket_name}: {e}")

        return incomplete_uploads

    @staticmethod
    def _get_bucket_metrics(
        cloudwatch_client,
        bucket_name: str
    ) -> tuple:
        """Get bucket size and object count from CloudWatch."""
        try:
            # Get BucketSizeBytes metric
            end_time = datetime.now()
            start_time = end_time - timedelta(days=2)

            size_response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BucketSizeBytes',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'StandardStorage'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )

            bucket_size_bytes = 0
            datapoints = size_response.get('Datapoints', [])
            if datapoints:
                # Get most recent datapoint
                latest = max(datapoints, key=lambda x: x['Timestamp'])
                bucket_size_bytes = latest['Average']

            bucket_size_gb = bucket_size_bytes / (1024 ** 3)

            # Get NumberOfObjects metric
            object_response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='NumberOfObjects',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )

            object_count = 0
            obj_datapoints = object_response.get('Datapoints', [])
            if obj_datapoints:
                latest = max(obj_datapoints, key=lambda x: x['Timestamp'])
                object_count = int(latest['Average'])

            return bucket_size_gb, object_count

        except Exception as e:
            logger.warning(f"Could not get metrics for {bucket_name}: {e}")
            return 0.0, 0
