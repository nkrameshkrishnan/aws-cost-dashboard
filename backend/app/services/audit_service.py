"""
Main FinOps audit orchestration service.
"""
import boto3
import logging
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.aws_account import AWSAccount
from app.aws.session_manager_db import db_session_manager
from app.core.cache import cache_manager
from app.core.job_storage import job_storage
from app.config import settings
from typing import Optional
from app.schemas.audit import (
    AuditRequest,
    FullAuditResults,
    AuditSummary,
    EC2AuditResults,
    EBSAuditResults,
    ElasticIPAuditResults,
    TaggingAuditResults,
    RDSAuditResults,
    LambdaAuditResults,
    S3AuditResults,
    LoadBalancerAuditResults,
    NATGatewayAuditResults,
    ElastiCacheAuditResults,
    CloudWatchLogsAuditResults,
    DynamoDBAuditResults,
    SavingsPlansCoverageResults,
    # Phase 6 audit results
    VPCEndpointAuditResults,
    EFSAuditResults,
    EBSSnapshotAuditResults,
    DataTransferAuditResults,
    ElasticBeanstalkAuditResults,
    # Phase 7 audit results
    CloudFrontAuditResults,
    Route53AuditResults,
    SQSAuditResults,
    SNSAuditResults,
    APIGatewayAuditResults,
    StepFunctionsAuditResults,
    ECSAuditResults,
    RedshiftAuditResults,
    KinesisAuditResults,
    GlueAuditResults
)
from app.services.audit.ec2_auditor import EC2Auditor
from app.services.audit.ebs_auditor import EBSAuditor
from app.services.audit.eip_auditor import ElasticIPAuditor
from app.services.audit.tagging_auditor import TaggingAuditor
from app.services.audit.rds_auditor import RDSAuditor
from app.services.audit.lambda_auditor import LambdaAuditor
from app.services.audit.s3_auditor import S3Auditor
from app.services.audit.lb_auditor import LoadBalancerAuditor
from app.services.audit.nat_gateway_auditor import NATGatewayAuditor
from app.services.audit.elasticache_auditor import ElastiCacheAuditor
from app.services.audit.cloudwatch_logs_auditor import CloudWatchLogsAuditor
from app.services.audit.dynamodb_auditor import DynamoDBAuditor
from app.services.audit.savings_plans_auditor import SavingsPlansAuditor
# Phase 6 auditors
from app.services.audit.vpc_endpoint_auditor import VPCEndpointAuditor
from app.services.audit.efs_auditor import EFSAuditor
from app.services.audit.ebs_snapshot_auditor import EBSSnapshotAuditor
from app.services.audit.data_transfer_auditor import DataTransferAuditor
from app.services.audit.beanstalk_auditor import ElasticBeanstalkAuditor
# Phase 7 auditors
from app.aws.auditors.cloudfront_auditor import CloudFrontAuditor
from app.aws.auditors.route53_auditor import Route53Auditor
from app.aws.auditors.sqs_auditor import SQSAuditor
from app.aws.auditors.sns_auditor import SNSAuditor
from app.aws.auditors.apigateway_auditor import APIGatewayAuditor
from app.aws.auditors.stepfunctions_auditor import StepFunctionsAuditor
from app.aws.auditors.ecs_auditor import ECSAuditor
from app.aws.auditors.redshift_auditor import RedshiftAuditor
from app.aws.auditors.kinesis_auditor import KinesisAuditor
from app.aws.auditors.glue_auditor import GlueAuditor

logger = logging.getLogger(__name__)


class AuditService:
    """Main service for orchestrating FinOps audits."""

    @staticmethod
    def _filter_active_regions(
        base_session,
        all_regions: List[str],
        min_monthly_cost: float = 1.0
    ) -> List[str]:
        """
        Filter regions to only include those with recent activity/costs.
        Significantly speeds up audits by skipping empty regions.

        Args:
            base_session: Boto3 session
            all_regions: List of all regions to check
            min_monthly_cost: Minimum monthly cost to consider region active (default $1)

        Returns:
            List of active region names
        """
        try:
            from datetime import datetime, timedelta

            ce_client = base_session.client('ce', region_name='us-east-1')

            # Check last 7 days of costs
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)

            # Get costs by region
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'REGION'}
                ]
            )

            # Calculate weekly costs by region
            region_costs = {}
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    region = group['Keys'][0]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    region_costs[region] = region_costs.get(region, 0) + cost

            # Estimate monthly cost (weekly * 4.33) and collect with costs for sorting
            region_monthly_costs = []
            for region in all_regions:
                # Cost Explorer returns region names slightly differently
                # Try exact match first, then fuzzy match
                monthly_est = 0.0
                for ce_region, weekly_cost in region_costs.items():
                    if region in ce_region or ce_region in region:
                        monthly_est = weekly_cost * 4.33
                        break

                region_monthly_costs.append((region, monthly_est))

                if monthly_est >= min_monthly_cost:
                    logger.debug(f"Region {region} is active (est. ${monthly_est:.2f}/month)")
                else:
                    logger.info(f"Skipping region {region} (est. ${monthly_est:.2f}/month - below ${min_monthly_cost} threshold)")

            # Sort regions by cost (descending) and filter
            region_monthly_costs.sort(key=lambda x: x[1], reverse=True)
            active_regions = [region for region, cost in region_monthly_costs if cost >= min_monthly_cost]

            if not active_regions:
                # Fallback: if no regions detected, scan all (better safe than sorry)
                logger.warning("No active regions detected, falling back to scanning all regions")
                return all_regions

            logger.info(f"Filtered {len(all_regions)} regions down to {len(active_regions)} active regions (sorted by cost)")
            return active_regions

        except Exception as e:
            logger.warning(f"Failed to filter active regions, scanning all: {e}")
            return all_regions

    @staticmethod
    def _scan_cloudfront(base_session, audit_request: AuditRequest) -> Dict:
        """Scan CloudFront distributions (global service)."""
        try:
            logger.info("Scanning CloudFront (global service)")
            cloudfront_auditor = CloudFrontAuditor(base_session)
            unused_distros = cloudfront_auditor.audit_unused_distributions(days=30)
            no_logging = cloudfront_auditor.audit_distributions_without_logging()
            return {
                'service': 'cloudfront',
                'unused_distributions': unused_distros,
                'distributions_without_logging': no_logging,
                'total_unused_cost': sum(d.get('estimated_monthly_cost', 0) for d in unused_distros)
            }
        except Exception as e:
            logger.error(f"Error scanning CloudFront: {e}")
            return {'service': 'cloudfront', 'error': str(e)}

    @staticmethod
    def _scan_route53(base_session, audit_request: AuditRequest) -> Dict:
        """Scan Route53 hosted zones (global service)."""
        try:
            logger.info("Scanning Route53 (global service)")
            route53_auditor = Route53Auditor(base_session)
            unused_zones = route53_auditor.audit_unused_hosted_zones()
            return {
                'service': 'route53',
                'unused_hosted_zones': unused_zones,
                'total_potential_savings': sum(z.get('estimated_monthly_cost', 0) for z in unused_zones)
            }
        except Exception as e:
            logger.error(f"Error scanning Route53: {e}")
            return {'service': 'route53', 'error': str(e)}

    @staticmethod
    def _scan_single_region(
        region: str,
        access_key: str,
        secret_key: str,
        audit_request: AuditRequest
    ) -> Dict:
        """
        Scan a single region for audit findings.
        This method is designed to be run in parallel.

        Returns:
            Dictionary with audit results for this region
        """
        try:
            logger.info(f"Scanning region: {region}")

            # Create session for this specific region
            region_session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )

            region_results = {
                'region': region,
                'ec2_audit': None,
                'ebs_audit': None,
                'eip_audit': None,
                'tagging_audit': None,
                'rds_audit': None,
                'lambda_audit': None,
                's3_audit': None,
                'lb_audit': None,
                'nat_gateway_audit': None,
                'elasticache_audit': None,
                'cloudwatch_logs_audit': None,
                'dynamodb_audit': None,
                'savings_plans_audit': None,
                # Phase 6 audits
                'vpc_endpoint_audit': None,
                'efs_audit': None,
                'ebs_snapshot_audit': None,
                'data_transfer_audit': None,
                'beanstalk_audit': None
            }

            # Run selected audits for this region
            if 'ec2' in audit_request.audit_types:
                region_results['ec2_audit'] = EC2Auditor.audit_ec2_instances(
                    region_session,
                    cpu_threshold=audit_request.cpu_threshold,
                    days_stopped_threshold=audit_request.days_stopped_threshold
                )

            if 'ebs' in audit_request.audit_types:
                region_results['ebs_audit'] = EBSAuditor.audit_ebs_resources(
                    region_session,
                    days_unattached_threshold=audit_request.days_unattached_threshold,
                    snapshot_age_threshold=audit_request.snapshot_age_threshold
                )

            if 'eip' in audit_request.audit_types:
                region_results['eip_audit'] = ElasticIPAuditor.audit_elastic_ips(region_session)

            if 'tagging' in audit_request.audit_types:
                region_results['tagging_audit'] = TaggingAuditor.audit_tagging_compliance(
                    region_session,
                    required_tags=audit_request.required_tags
                )

            if 'rds' in audit_request.audit_types:
                region_results['rds_audit'] = RDSAuditor.audit_rds_resources(
                    region_session,
                    cpu_threshold=audit_request.cpu_threshold,
                    days_stopped_threshold=audit_request.days_stopped_threshold,
                    snapshot_age_threshold=audit_request.snapshot_age_threshold
                )

            if 'lambda' in audit_request.audit_types:
                region_results['lambda_audit'] = LambdaAuditor.audit_lambda_functions(
                    region_session,
                    days_unused_threshold=30  # Could add to AuditRequest parameters
                )

            if 's3' in audit_request.audit_types:
                region_results['s3_audit'] = S3Auditor.audit_s3_buckets(
                    region_session,
                    multipart_age_threshold=7  # Could add to AuditRequest parameters
                )

            if 'lb' in audit_request.audit_types:
                region_results['lb_audit'] = LoadBalancerAuditor.audit_load_balancers(
                    region_session,
                    low_traffic_threshold=100  # Could add to AuditRequest parameters
                )

            if 'nat_gateway' in audit_request.audit_types:
                region_results['nat_gateway_audit'] = NATGatewayAuditor.audit_nat_gateways(
                    region_session,
                    idle_threshold_gb=1.0  # Could add to AuditRequest parameters
                )

            if 'elasticache' in audit_request.audit_types:
                region_results['elasticache_audit'] = ElastiCacheAuditor.audit_elasticache(
                    region_session,
                    cpu_threshold=5.0  # Could add to AuditRequest parameters
                )

            if 'cloudwatch_logs' in audit_request.audit_types:
                region_results['cloudwatch_logs_audit'] = CloudWatchLogsAuditor.audit_cloudwatch_logs(
                    region_session,
                    long_retention_threshold=30  # Could add to AuditRequest parameters
                )

            if 'dynamodb' in audit_request.audit_types:
                region_results['dynamodb_audit'] = DynamoDBAuditor.audit_dynamodb(
                    region_session,
                    unused_threshold_days=30  # Could add to AuditRequest parameters
                )

            if 'savings_plans' in audit_request.audit_types:
                region_results['savings_plans_audit'] = SavingsPlansAuditor.audit_savings_plans_coverage(
                    region_session,
                    lookback_days=30  # Could add to AuditRequest parameters
                )

            # Phase 6 audits
            if 'vpc_endpoint' in audit_request.audit_types:
                region_results['vpc_endpoint_audit'] = VPCEndpointAuditor.audit_vpc_endpoints(
                    region_session,
                    lookback_days=7  # Could add to AuditRequest parameters
                )

            if 'efs' in audit_request.audit_types:
                region_results['efs_audit'] = EFSAuditor.audit_efs_file_systems(
                    region_session,
                    lookback_days=30  # Could add to AuditRequest parameters
                )

            if 'ebs_snapshot' in audit_request.audit_types:
                region_results['ebs_snapshot_audit'] = EBSSnapshotAuditor.audit_ebs_snapshots(
                    region_session,
                    min_age_days=30  # Could add to AuditRequest parameters
                )

            if 'data_transfer' in audit_request.audit_types:
                region_results['data_transfer_audit'] = DataTransferAuditor.audit_data_transfer(
                    region_session,
                    lookback_days=30  # Could add to AuditRequest parameters
                )

            if 'beanstalk' in audit_request.audit_types:
                region_results['beanstalk_audit'] = ElasticBeanstalkAuditor.audit_beanstalk_environments(
                    region_session,
                    lookback_days=14  # Could add to AuditRequest parameters
                )

            # Phase 7 audits
            if 'sqs' in audit_request.audit_types:
                sqs_auditor = SQSAuditor(region_session, region)
                unused_queues = sqs_auditor.audit_unused_queues(days=30)
                high_retention = sqs_auditor.audit_high_retention_queues()
                region_results['sqs_audit'] = {
                    'unused_queues': unused_queues,
                    'high_retention_queues': high_retention
                }

            if 'sns' in audit_request.audit_types:
                sns_auditor = SNSAuditor(region_session, region)
                region_results['sns_audit'] = {
                    'unused_topics': sns_auditor.audit_unused_topics(days=30)
                }

            if 'apigateway' in audit_request.audit_types:
                apigw_auditor = APIGatewayAuditor(region_session, region)
                unused_apis = apigw_auditor.audit_unused_apis(days=30)
                no_caching = apigw_auditor.audit_apis_without_caching()
                region_results['apigateway_audit'] = {
                    'unused_apis': unused_apis,
                    'apis_without_caching': no_caching
                }

            if 'stepfunctions' in audit_request.audit_types:
                sfn_auditor = StepFunctionsAuditor(region_session, region)
                region_results['stepfunctions_audit'] = {
                    'unused_state_machines': sfn_auditor.audit_unused_state_machines(days=30)
                }

            if 'ecs' in audit_request.audit_types:
                ecs_auditor = ECSAuditor(region_session, region)
                region_results['ecs_audit'] = {
                    'oversized_tasks': ecs_auditor.audit_oversized_tasks()
                }

            if 'redshift' in audit_request.audit_types:
                redshift_auditor = RedshiftAuditor(region_session, region)
                region_results['redshift_audit'] = {
                    'idle_clusters': redshift_auditor.audit_idle_clusters()
                }

            if 'kinesis' in audit_request.audit_types:
                kinesis_auditor = KinesisAuditor(region_session, region)
                region_results['kinesis_audit'] = {
                    'unused_streams': kinesis_auditor.audit_unused_streams(days=7)
                }

            if 'glue' in audit_request.audit_types:
                glue_auditor = GlueAuditor(region_session, region)
                unused_crawlers = glue_auditor.audit_unused_crawlers(days=30)
                unused_jobs = glue_auditor.audit_unused_jobs(days=30)
                region_results['glue_audit'] = {
                    'unused_crawlers': unused_crawlers,
                    'unused_jobs': unused_jobs
                }

            logger.info(f"Completed scanning region: {region}")
            return region_results

        except Exception as e:
            logger.warning(f"Error scanning region {region}: {e}")
            return {
                'region': region,
                'error': str(e),
                'ec2_audit': None,
                'ebs_audit': None,
                'eip_audit': None,
                'tagging_audit': None,
                'rds_audit': None,
                'lambda_audit': None,
                's3_audit': None,
                'lb_audit': None,
                'nat_gateway_audit': None,
                'elasticache_audit': None,
                'cloudwatch_logs_audit': None,
                'dynamodb_audit': None,
                'savings_plans_audit': None,
                # Phase 6 audits
                'vpc_endpoint_audit': None,
                'efs_audit': None,
                'ebs_snapshot_audit': None,
                'data_transfer_audit': None,
                'beanstalk_audit': None
            }

    @staticmethod
    def run_full_audit(
        db: Session,
        audit_request: AuditRequest,
        job_id: Optional[str] = None
    ) -> FullAuditResults:
        """
        Run a full audit on an AWS account across multiple regions.
        Uses Redis caching to speed up repeated audits (30-minute TTL).

        Args:
            db: Database session
            audit_request: Audit request with parameters
            job_id: Optional job ID for progress tracking

        Returns:
            FullAuditResults with all audit findings
        """
        # Generate cache key based on audit parameters
        cache_key = cache_manager._generate_key(
            "audit:full",
            audit_request.account_name,
            tuple(sorted(audit_request.audit_types)) if audit_request.audit_types else (),
            tuple(sorted(audit_request.regions)) if audit_request.regions else (),
            audit_request.cpu_threshold,
            audit_request.days_stopped_threshold,
            audit_request.days_unattached_threshold,
            audit_request.snapshot_age_threshold,
            tuple(sorted(audit_request.required_tags)) if audit_request.required_tags else ()
        )

        # Try to get from cache
        cached_result = cache_manager.get(cache_key)
        if cached_result is not None:
            logger.info(f"Cache hit for audit: {audit_request.account_name}")
            # Convert dict back to FullAuditResults using model_validate for proper deserialization
            return FullAuditResults.model_validate(cached_result)

        # Cache miss - run the audit
        logger.info(f"Cache miss - running audit for: {audit_request.account_name}")

        try:
            # Create base session using database credentials
            base_session = db_session_manager.get_session(db, audit_request.account_name)

            # Determine regions to scan
            regions_to_scan = audit_request.regions
            if not regions_to_scan:
                # Get all enabled regions
                ec2_client = base_session.client('ec2')
                regions_response = ec2_client.describe_regions(
                    Filters=[{'Name': 'opt-in-status', 'Values': ['opt-in-not-required', 'opted-in']}]
                )
                regions_to_scan = [region['RegionName'] for region in regions_response['Regions']]
                logger.info(f"Found {len(regions_to_scan)} enabled regions")

                # Smart filtering: Skip empty regions for faster audits
                if audit_request.skip_empty_regions:
                    logger.info(f"Smart filtering enabled - checking region activity...")
                    regions_to_scan = AuditService._filter_active_regions(
                        base_session,
                        regions_to_scan,
                        min_monthly_cost=audit_request.min_region_cost
                    )

                # Quick audit mode: Scan only top N regions
                if audit_request.quick_audit_top_regions and audit_request.quick_audit_top_regions < len(regions_to_scan):
                    logger.info(f"Quick audit mode: limiting to top {audit_request.quick_audit_top_regions} regions")
                    # Regions already sorted by cost from _filter_active_regions
                    regions_to_scan = regions_to_scan[:audit_request.quick_audit_top_regions]

                logger.info(f"Will scan {len(regions_to_scan)} regions: {', '.join(regions_to_scan)}")
            else:
                logger.info(f"Scanning specified regions: {', '.join(regions_to_scan)}")

            logger.info(f"Starting audit for account: {audit_request.account_name} across {len(regions_to_scan)} region(s)")

            # Get account and decrypt credentials once
            account = db.query(AWSAccount).filter(
                AWSAccount.name == audit_request.account_name
            ).first()

            if not account:
                raise ValueError(f"AWS account '{audit_request.account_name}' not found")

            from app.core.encryption import credential_encryption
            access_key = credential_encryption.decrypt(account.encrypted_access_key_id)
            secret_key = credential_encryption.decrypt(account.encrypted_secret_access_key)

            # Initialize aggregated results
            ec2_audit = EC2AuditResults()
            ebs_audit = EBSAuditResults()
            eip_audit = ElasticIPAuditResults()
            tagging_audit = TaggingAuditResults()
            rds_audit = RDSAuditResults()
            lambda_audit = LambdaAuditResults()
            s3_audit = S3AuditResults()
            lb_audit = LoadBalancerAuditResults()
            nat_gateway_audit = NATGatewayAuditResults()
            elasticache_audit = ElastiCacheAuditResults()
            cloudwatch_logs_audit = CloudWatchLogsAuditResults()
            dynamodb_audit = DynamoDBAuditResults()
            savings_plans_audit = SavingsPlansCoverageResults()
            # Phase 6 audit results
            vpc_endpoint_audit = VPCEndpointAuditResults()
            efs_audit = EFSAuditResults()
            ebs_snapshot_audit = EBSSnapshotAuditResults()
            data_transfer_audit = DataTransferAuditResults()
            beanstalk_audit = ElasticBeanstalkAuditResults()
            # Phase 7 audit results
            cloudfront_audit = CloudFrontAuditResults()
            route53_audit = Route53AuditResults()
            sqs_audit = SQSAuditResults()
            sns_audit = SNSAuditResults()
            apigateway_audit = APIGatewayAuditResults()
            stepfunctions_audit = StepFunctionsAuditResults()
            ecs_audit = ECSAuditResults()
            redshift_audit = RedshiftAuditResults()
            kinesis_audit = KinesisAuditResults()
            glue_audit = GlueAuditResults()

            # Scan regions in parallel using ThreadPoolExecutor
            # Use max 15 workers for faster scanning (increased from 10)
            # AWS rate limits are per-region, so more workers is safe
            max_workers = min(15, len(regions_to_scan))
            logger.info(f"Scanning {len(regions_to_scan)} regions in parallel with {max_workers} workers")

            # Track progress
            total_regions = len(regions_to_scan)
            completed_regions = 0

            # Update initial progress and set status to running
            if job_id:
                job_storage.update_job_status(
                    job_id,
                    status='running',
                    progress=5,
                    current_step=f"Starting scan across {total_regions} region(s)..."
                )

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all region scans
                future_to_region = {
                    executor.submit(
                        AuditService._scan_single_region,
                        region,
                        access_key,
                        secret_key,
                        audit_request
                    ): ('region', region)
                    for region in regions_to_scan
                }

                # Submit global service scans in parallel (CloudFront & Route53)
                # These run concurrently with regional scans for faster execution
                if 'cloudfront' in audit_request.audit_types:
                    cloudfront_future = executor.submit(
                        AuditService._scan_cloudfront,
                        base_session,
                        audit_request
                    )
                    future_to_region[cloudfront_future] = ('global', 'cloudfront')

                if 'route53' in audit_request.audit_types:
                    route53_future = executor.submit(
                        AuditService._scan_route53,
                        base_session,
                        audit_request
                    )
                    future_to_region[route53_future] = ('global', 'route53')

                # Collect results as they complete
                for future in as_completed(future_to_region):
                    scan_type, scan_target = future_to_region[future]
                    try:
                        scan_results = future.result()

                        # Handle global service results
                        if scan_type == 'global':
                            if scan_target == 'cloudfront' and 'unused_distributions' in scan_results:
                                cloudfront_audit.unused_distributions.extend(scan_results['unused_distributions'])
                                cloudfront_audit.distributions_without_logging.extend(scan_results.get('distributions_without_logging', []))
                                cloudfront_audit.total_unused_cost = scan_results.get('total_unused_cost', 0)
                                logger.info(f"Global service CloudFront scan complete")
                            elif scan_target == 'route53' and 'unused_hosted_zones' in scan_results:
                                route53_audit.unused_hosted_zones.extend(scan_results['unused_hosted_zones'])
                                route53_audit.total_potential_savings = scan_results.get('total_potential_savings', 0)
                                logger.info(f"Global service Route53 scan complete")
                            continue  # Skip regional result processing

                        # Handle regional results
                        region = scan_target
                        region_results = scan_results

                        # Merge EC2 results
                        if region_results.get('ec2_audit'):
                            region_ec2_audit = region_results['ec2_audit']
                            ec2_audit.idle_instances.extend(region_ec2_audit.idle_instances)
                            ec2_audit.stopped_instances.extend(region_ec2_audit.stopped_instances)
                            ec2_audit.total_idle_cost += region_ec2_audit.total_idle_cost
                            ec2_audit.total_stopped_ebs_cost += region_ec2_audit.total_stopped_ebs_cost
                            ec2_audit.total_potential_savings += region_ec2_audit.total_potential_savings

                        # Merge EBS results
                        if region_results.get('ebs_audit'):
                            region_ebs_audit = region_results['ebs_audit']
                            ebs_audit.unattached_volumes.extend(region_ebs_audit.unattached_volumes)
                            ebs_audit.old_snapshots.extend(region_ebs_audit.old_snapshots)
                            ebs_audit.total_unattached_cost += region_ebs_audit.total_unattached_cost
                            ebs_audit.total_snapshot_cost += region_ebs_audit.total_snapshot_cost
                            ebs_audit.total_potential_savings += region_ebs_audit.total_potential_savings

                        # Merge EIP results
                        if region_results.get('eip_audit'):
                            region_eip_audit = region_results['eip_audit']
                            eip_audit.unattached_ips.extend(region_eip_audit.unattached_ips)
                            eip_audit.total_cost += region_eip_audit.total_cost

                        # Merge tagging results
                        if region_results.get('tagging_audit'):
                            region_tagging_audit = region_results['tagging_audit']
                            tagging_audit.untagged_resources.extend(region_tagging_audit.untagged_resources)
                            tagging_audit.total_untagged += region_tagging_audit.total_untagged

                        # Merge RDS results
                        if region_results.get('rds_audit'):
                            region_rds_audit = region_results['rds_audit']
                            rds_audit.idle_instances.extend(region_rds_audit.idle_instances)
                            rds_audit.stopped_instances.extend(region_rds_audit.stopped_instances)
                            rds_audit.old_snapshots.extend(region_rds_audit.old_snapshots)
                            rds_audit.total_idle_cost += region_rds_audit.total_idle_cost
                            rds_audit.total_stopped_storage_cost += region_rds_audit.total_stopped_storage_cost
                            rds_audit.total_snapshot_cost += region_rds_audit.total_snapshot_cost
                            rds_audit.total_potential_savings += region_rds_audit.total_potential_savings

                        # Merge Lambda results
                        if region_results.get('lambda_audit'):
                            region_lambda_audit = region_results['lambda_audit']
                            lambda_audit.unused_functions.extend(region_lambda_audit.unused_functions)
                            lambda_audit.over_provisioned_functions.extend(region_lambda_audit.over_provisioned_functions)
                            lambda_audit.total_unused_cost += region_lambda_audit.total_unused_cost
                            lambda_audit.total_over_provisioned_waste += region_lambda_audit.total_over_provisioned_waste
                            lambda_audit.total_potential_savings += region_lambda_audit.total_potential_savings

                        # Merge S3 results
                        if region_results.get('s3_audit'):
                            region_s3_audit = region_results['s3_audit']
                            s3_audit.buckets_without_lifecycle.extend(region_s3_audit.buckets_without_lifecycle)
                            s3_audit.incomplete_multipart_uploads.extend(region_s3_audit.incomplete_multipart_uploads)
                            s3_audit.total_lifecycle_savings += region_s3_audit.total_lifecycle_savings
                            s3_audit.total_multipart_waste += region_s3_audit.total_multipart_waste
                            s3_audit.total_potential_savings += region_s3_audit.total_potential_savings

                        # Merge Load Balancer results
                        if region_results.get('lb_audit'):
                            region_lb_audit = region_results['lb_audit']
                            lb_audit.lbs_no_targets.extend(region_lb_audit.lbs_no_targets)
                            lb_audit.lbs_low_traffic.extend(region_lb_audit.lbs_low_traffic)
                            lb_audit.total_no_target_cost += region_lb_audit.total_no_target_cost
                            lb_audit.total_low_traffic_waste += region_lb_audit.total_low_traffic_waste
                            lb_audit.total_potential_savings += region_lb_audit.total_potential_savings

                        # Merge NAT Gateway results
                        if region_results.get('nat_gateway_audit'):
                            region_nat_audit = region_results['nat_gateway_audit']
                            nat_gateway_audit.idle_gateways.extend(region_nat_audit.idle_gateways)
                            nat_gateway_audit.unused_gateways.extend(region_nat_audit.unused_gateways)
                            nat_gateway_audit.total_idle_waste += region_nat_audit.total_idle_waste
                            nat_gateway_audit.total_unused_cost += region_nat_audit.total_unused_cost
                            nat_gateway_audit.total_potential_savings += region_nat_audit.total_potential_savings

                        # Merge ElastiCache results
                        if region_results.get('elasticache_audit'):
                            region_ec_audit = region_results['elasticache_audit']
                            elasticache_audit.idle_clusters.extend(region_ec_audit.idle_clusters)
                            elasticache_audit.over_provisioned_clusters.extend(region_ec_audit.over_provisioned_clusters)
                            elasticache_audit.total_idle_cost += region_ec_audit.total_idle_cost
                            elasticache_audit.total_over_provisioned_waste += region_ec_audit.total_over_provisioned_waste
                            elasticache_audit.total_potential_savings += region_ec_audit.total_potential_savings

                        # Merge CloudWatch Logs results
                        if region_results.get('cloudwatch_logs_audit'):
                            region_cw_audit = region_results['cloudwatch_logs_audit']
                            cloudwatch_logs_audit.long_retention_groups.extend(region_cw_audit.long_retention_groups)
                            cloudwatch_logs_audit.unused_groups.extend(region_cw_audit.unused_groups)
                            cloudwatch_logs_audit.total_retention_waste += region_cw_audit.total_retention_waste
                            cloudwatch_logs_audit.total_unused_cost += region_cw_audit.total_unused_cost
                            cloudwatch_logs_audit.total_potential_savings += region_cw_audit.total_potential_savings

                        # Merge DynamoDB results
                        if region_results.get('dynamodb_audit'):
                            region_ddb_audit = region_results['dynamodb_audit']
                            dynamodb_audit.unused_tables.extend(region_ddb_audit.unused_tables)
                            dynamodb_audit.billing_mode_opportunities.extend(region_ddb_audit.billing_mode_opportunities)
                            dynamodb_audit.total_unused_cost += region_ddb_audit.total_unused_cost
                            dynamodb_audit.total_billing_mode_savings += region_ddb_audit.total_billing_mode_savings
                            dynamodb_audit.total_potential_savings += region_ddb_audit.total_potential_savings

                        # Merge Savings Plans results
                        if region_results.get('savings_plans_audit'):
                            region_sp_audit = region_results['savings_plans_audit']
                            savings_plans_audit.uncovered_ec2_instances.extend(region_sp_audit.uncovered_ec2_instances)
                            savings_plans_audit.uncovered_rds_instances.extend(region_sp_audit.uncovered_rds_instances)
                            savings_plans_audit.underutilized_ris.extend(region_sp_audit.underutilized_ris)
                            savings_plans_audit.total_ec2_savings_opportunity += region_sp_audit.total_ec2_savings_opportunity
                            savings_plans_audit.total_rds_savings_opportunity += region_sp_audit.total_rds_savings_opportunity
                            savings_plans_audit.total_ri_waste += region_sp_audit.total_ri_waste
                            savings_plans_audit.total_potential_savings += region_sp_audit.total_potential_savings

                        # Phase 6: Merge VPC Endpoint results
                        if region_results.get('vpc_endpoint_audit'):
                            region_vpc_audit = region_results['vpc_endpoint_audit']
                            vpc_endpoint_audit.unused_endpoints.extend(region_vpc_audit.unused_endpoints)
                            vpc_endpoint_audit.duplicate_endpoints.extend(region_vpc_audit.duplicate_endpoints)
                            vpc_endpoint_audit.total_unused_cost += region_vpc_audit.total_unused_cost
                            vpc_endpoint_audit.total_duplicate_waste += region_vpc_audit.total_duplicate_waste
                            vpc_endpoint_audit.total_potential_savings += region_vpc_audit.total_potential_savings

                        # Phase 6: Merge EFS results
                        if region_results.get('efs_audit'):
                            region_efs_audit = region_results['efs_audit']
                            efs_audit.unused_file_systems.extend(region_efs_audit.unused_file_systems)
                            efs_audit.file_systems_without_lifecycle.extend(region_efs_audit.file_systems_without_lifecycle)
                            efs_audit.total_unused_cost += region_efs_audit.total_unused_cost
                            efs_audit.total_lifecycle_savings += region_efs_audit.total_lifecycle_savings
                            efs_audit.total_potential_savings += region_efs_audit.total_potential_savings

                        # Phase 6: Merge EBS Snapshot results
                        if region_results.get('ebs_snapshot_audit'):
                            region_snap_audit = region_results['ebs_snapshot_audit']
                            ebs_snapshot_audit.orphaned_snapshots.extend(region_snap_audit.orphaned_snapshots)
                            ebs_snapshot_audit.duplicate_snapshots.extend(region_snap_audit.duplicate_snapshots)
                            ebs_snapshot_audit.total_orphaned_cost += region_snap_audit.total_orphaned_cost
                            ebs_snapshot_audit.total_duplicate_waste += region_snap_audit.total_duplicate_waste
                            ebs_snapshot_audit.total_potential_savings += region_snap_audit.total_potential_savings

                        # Phase 6: Merge Data Transfer results
                        if region_results.get('data_transfer_audit'):
                            region_dt_audit = region_results['data_transfer_audit']
                            data_transfer_audit.high_cost_transfers.extend(region_dt_audit.high_cost_transfers)
                            data_transfer_audit.total_transfer_cost += region_dt_audit.total_transfer_cost
                            data_transfer_audit.total_potential_savings += region_dt_audit.total_potential_savings

                        # Phase 6: Merge Elastic Beanstalk results
                        if region_results.get('beanstalk_audit'):
                            region_bs_audit = region_results['beanstalk_audit']
                            beanstalk_audit.unused_environments.extend(region_bs_audit.unused_environments)
                            beanstalk_audit.nonprod_running_24_7.extend(region_bs_audit.nonprod_running_24_7)
                            beanstalk_audit.total_unused_cost += region_bs_audit.total_unused_cost
                            beanstalk_audit.total_nonprod_waste += region_bs_audit.total_nonprod_waste
                            beanstalk_audit.total_potential_savings += region_bs_audit.total_potential_savings

                        # Phase 7: Merge SQS results
                        if region_results.get('sqs_audit'):
                            region_sqs = region_results['sqs_audit']
                            sqs_audit.unused_queues.extend(region_sqs['unused_queues'])
                            sqs_audit.high_retention_queues.extend(region_sqs['high_retention_queues'])

                        # Phase 7: Merge SNS results
                        if region_results.get('sns_audit'):
                            region_sns = region_results['sns_audit']
                            sns_audit.unused_topics.extend(region_sns['unused_topics'])

                        # Phase 7: Merge API Gateway results
                        if region_results.get('apigateway_audit'):
                            region_apigw = region_results['apigateway_audit']
                            apigateway_audit.unused_apis.extend(region_apigw['unused_apis'])
                            apigateway_audit.apis_without_caching.extend(region_apigw['apis_without_caching'])
                            apigateway_audit.total_potential_savings += sum(
                                api.get('potential_cost_savings', 0) for api in region_apigw['apis_without_caching']
                            )

                        # Phase 7: Merge Step Functions results
                        if region_results.get('stepfunctions_audit'):
                            region_sfn = region_results['stepfunctions_audit']
                            stepfunctions_audit.unused_state_machines.extend(region_sfn['unused_state_machines'])

                        # Phase 7: Merge ECS results
                        if region_results.get('ecs_audit'):
                            region_ecs = region_results['ecs_audit']
                            ecs_audit.oversized_tasks.extend(region_ecs['oversized_tasks'])

                        # Phase 7: Merge Redshift results
                        if region_results.get('redshift_audit'):
                            region_redshift = region_results['redshift_audit']
                            redshift_audit.idle_clusters.extend(region_redshift['idle_clusters'])
                            redshift_audit.total_potential_savings += sum(
                                cluster.get('estimated_monthly_cost', 0) for cluster in region_redshift['idle_clusters']
                            )

                        # Phase 7: Merge Kinesis results
                        if region_results.get('kinesis_audit'):
                            region_kinesis = region_results['kinesis_audit']
                            kinesis_audit.unused_streams.extend(region_kinesis['unused_streams'])
                            kinesis_audit.total_potential_savings += sum(
                                stream.get('estimated_monthly_cost', 0) for stream in region_kinesis['unused_streams']
                            )

                        # Phase 7: Merge Glue results
                        if region_results.get('glue_audit'):
                            region_glue = region_results['glue_audit']
                            glue_audit.unused_crawlers.extend(region_glue['unused_crawlers'])
                            glue_audit.unused_jobs.extend(region_glue['unused_jobs'])

                    except Exception as e:
                        logger.error(f"Failed to process results for region {region}: {e}")
                        continue
                    finally:
                        # Update progress after each region completes
                        completed_regions += 1
                        if job_id:
                            # Calculate progress: 5% initial + 85% for regions + 10% final
                            region_progress = int(5 + (completed_regions / total_regions) * 85)
                            current_step = f"Scanned {region} ({completed_regions}/{total_regions} regions)"

                            # Create partial results with current aggregated data
                            # This allows frontend to display incremental results
                            partial_summary = AuditService._generate_summary(
                                ec2_audit, ebs_audit, eip_audit, tagging_audit,
                                rds_audit, lambda_audit, s3_audit, lb_audit,
                                nat_gateway_audit, elasticache_audit,
                                cloudwatch_logs_audit, dynamodb_audit, savings_plans_audit,
                                vpc_endpoint_audit, efs_audit, ebs_snapshot_audit,
                                data_transfer_audit, beanstalk_audit
                            )

                            partial_results = FullAuditResults(
                                account_name=audit_request.account_name,
                                audit_timestamp=datetime.now(),
                                ec2_audit=ec2_audit,
                                ebs_audit=ebs_audit,
                                eip_audit=eip_audit,
                                tagging_audit=tagging_audit,
                                rds_audit=rds_audit if 'rds' in audit_request.audit_types else None,
                                lambda_audit=lambda_audit if 'lambda' in audit_request.audit_types else None,
                                s3_audit=s3_audit if 's3' in audit_request.audit_types else None,
                                lb_audit=lb_audit if 'lb' in audit_request.audit_types else None,
                                nat_gateway_audit=nat_gateway_audit if 'nat_gateway' in audit_request.audit_types else None,
                                elasticache_audit=elasticache_audit if 'elasticache' in audit_request.audit_types else None,
                                cloudwatch_logs_audit=cloudwatch_logs_audit if 'cloudwatch_logs' in audit_request.audit_types else None,
                                dynamodb_audit=dynamodb_audit if 'dynamodb' in audit_request.audit_types else None,
                                savings_plans_audit=savings_plans_audit if 'savings_plans' in audit_request.audit_types else None,
                                vpc_endpoint_audit=vpc_endpoint_audit if 'vpc_endpoint' in audit_request.audit_types else None,
                                efs_audit=efs_audit if 'efs' in audit_request.audit_types else None,
                                ebs_snapshot_audit=ebs_snapshot_audit if 'ebs_snapshot' in audit_request.audit_types else None,
                                data_transfer_audit=data_transfer_audit if 'data_transfer' in audit_request.audit_types else None,
                                beanstalk_audit=beanstalk_audit if 'beanstalk' in audit_request.audit_types else None,
                                cloudfront_audit=cloudfront_audit if 'cloudfront' in audit_request.audit_types else None,
                                route53_audit=route53_audit if 'route53' in audit_request.audit_types else None,
                                sqs_audit=sqs_audit if 'sqs' in audit_request.audit_types else None,
                                sns_audit=sns_audit if 'sns' in audit_request.audit_types else None,
                                apigateway_audit=apigateway_audit if 'apigateway' in audit_request.audit_types else None,
                                stepfunctions_audit=stepfunctions_audit if 'stepfunctions' in audit_request.audit_types else None,
                                ecs_audit=ecs_audit if 'ecs' in audit_request.audit_types else None,
                                redshift_audit=redshift_audit if 'redshift' in audit_request.audit_types else None,
                                kinesis_audit=kinesis_audit if 'kinesis' in audit_request.audit_types else None,
                                glue_audit=glue_audit if 'glue' in audit_request.audit_types else None,
                                summary=partial_summary
                            )

                            # Update progress with partial results for real-time display
                            job_storage.update_job_status(
                                job_id,
                                progress=region_progress,
                                current_step=current_step,
                                partial_results=partial_results.model_dump(mode='json')
                            )
                            logger.info(f"Progress: {region_progress}% - {current_step}")

            # Note: Global services (CloudFront, Route53) are now scanned in parallel
            # with regional scans above for better performance

            # Recalculate tagging compliance percentage
            if tagging_audit.total_untagged > 0:
                # This is simplified - in production, track total resources too
                tagging_audit.compliance_percentage = 0.0

            # Generate summary
            summary = AuditService._generate_summary(
                ec2_audit,
                ebs_audit,
                eip_audit,
                tagging_audit,
                rds_audit,
                lambda_audit,
                s3_audit,
                lb_audit,
                nat_gateway_audit,
                elasticache_audit,
                cloudwatch_logs_audit,
                dynamodb_audit,
                savings_plans_audit,
                vpc_endpoint_audit,
                efs_audit,
                ebs_snapshot_audit,
                data_transfer_audit,
                beanstalk_audit
            )

            # Update progress for final aggregation
            if job_id:
                job_storage.update_job_status(
                    job_id,
                    progress=95,
                    current_step="Aggregating final results..."
                )

            logger.info(f"Audit complete across {len(regions_to_scan)} region(s). "
                       f"Total findings: {summary.total_findings}, "
                       f"Potential savings: ${summary.total_potential_savings:.2f}/month")

            # Create results
            results = FullAuditResults(
                account_name=audit_request.account_name,
                audit_timestamp=datetime.now(),
                ec2_audit=ec2_audit,
                ebs_audit=ebs_audit,
                eip_audit=eip_audit,
                tagging_audit=tagging_audit,
                rds_audit=rds_audit if 'rds' in audit_request.audit_types else None,
                lambda_audit=lambda_audit if 'lambda' in audit_request.audit_types else None,
                s3_audit=s3_audit if 's3' in audit_request.audit_types else None,
                lb_audit=lb_audit if 'lb' in audit_request.audit_types else None,
                nat_gateway_audit=nat_gateway_audit if 'nat_gateway' in audit_request.audit_types else None,
                elasticache_audit=elasticache_audit if 'elasticache' in audit_request.audit_types else None,
                cloudwatch_logs_audit=cloudwatch_logs_audit if 'cloudwatch_logs' in audit_request.audit_types else None,
                dynamodb_audit=dynamodb_audit if 'dynamodb' in audit_request.audit_types else None,
                savings_plans_audit=savings_plans_audit if 'savings_plans' in audit_request.audit_types else None,
                # Phase 6 audits
                vpc_endpoint_audit=vpc_endpoint_audit if 'vpc_endpoint' in audit_request.audit_types else None,
                efs_audit=efs_audit if 'efs' in audit_request.audit_types else None,
                ebs_snapshot_audit=ebs_snapshot_audit if 'ebs_snapshot' in audit_request.audit_types else None,
                data_transfer_audit=data_transfer_audit if 'data_transfer' in audit_request.audit_types else None,
                beanstalk_audit=beanstalk_audit if 'beanstalk' in audit_request.audit_types else None,
                # Phase 7 audits
                cloudfront_audit=cloudfront_audit if 'cloudfront' in audit_request.audit_types else None,
                route53_audit=route53_audit if 'route53' in audit_request.audit_types else None,
                sqs_audit=sqs_audit if 'sqs' in audit_request.audit_types else None,
                sns_audit=sns_audit if 'sns' in audit_request.audit_types else None,
                apigateway_audit=apigateway_audit if 'apigateway' in audit_request.audit_types else None,
                stepfunctions_audit=stepfunctions_audit if 'stepfunctions' in audit_request.audit_types else None,
                ecs_audit=ecs_audit if 'ecs' in audit_request.audit_types else None,
                redshift_audit=redshift_audit if 'redshift' in audit_request.audit_types else None,
                kinesis_audit=kinesis_audit if 'kinesis' in audit_request.audit_types else None,
                glue_audit=glue_audit if 'glue' in audit_request.audit_types else None,
                summary=summary
            )

            # Cache the results (30 minute TTL for audit results)
            # Use model_dump with mode='json' to ensure datetime is serialized properly
            try:
                cache_data = results.model_dump(mode='json')
                cache_manager.set(cache_key, cache_data, settings.CACHE_TTL_AUDIT_RESULTS)
                logger.debug(f"Cached audit results: {cache_key}")
            except Exception as cache_error:
                logger.warning(f"Failed to cache audit results: {cache_error}")

            # Mark job as complete (if tracking progress)
            if job_id:
                # Note: The job_storage.set_final_results() is called from the endpoint
                # but we'll update progress to 100% here
                job_storage.update_job_status(
                    job_id,
                    status='completed',
                    progress=100,
                    current_step=f"Audit complete! Found {summary.total_findings} findings."
                )

            return results

        except Exception as e:
            # Mark job as failed if tracking progress
            if job_id:
                job_storage.update_job_status(
                    job_id,
                    status='failed',
                    error=str(e)
                )
            logger.error(f"Error running audit: {e}")
            raise

    @staticmethod
    def _generate_summary(
        ec2_audit: EC2AuditResults,
        ebs_audit: EBSAuditResults,
        eip_audit: ElasticIPAuditResults,
        tagging_audit: TaggingAuditResults,
        rds_audit: RDSAuditResults,
        lambda_audit: LambdaAuditResults,
        s3_audit: S3AuditResults,
        lb_audit: LoadBalancerAuditResults,
        nat_gateway_audit: NATGatewayAuditResults,
        elasticache_audit: ElastiCacheAuditResults,
        cloudwatch_logs_audit: CloudWatchLogsAuditResults,
        dynamodb_audit: DynamoDBAuditResults,
        savings_plans_audit: SavingsPlansCoverageResults,
        vpc_endpoint_audit: VPCEndpointAuditResults,
        efs_audit: EFSAuditResults,
        ebs_snapshot_audit: EBSSnapshotAuditResults,
        data_transfer_audit: DataTransferAuditResults,
        beanstalk_audit: ElasticBeanstalkAuditResults
    ) -> AuditSummary:
        """Generate audit summary from individual audit results."""

        # Count findings by category
        findings_by_category = {
            'idle_ec2_instances': len(ec2_audit.idle_instances),
            'stopped_ec2_instances': len(ec2_audit.stopped_instances),
            'unattached_ebs_volumes': len(ebs_audit.unattached_volumes),
            'old_ebs_snapshots': len(ebs_audit.old_snapshots),
            'unattached_elastic_ips': len(eip_audit.unattached_ips),
            'untagged_resources': len(tagging_audit.untagged_resources),
            'idle_rds_instances': len(rds_audit.idle_instances),
            'stopped_rds_instances': len(rds_audit.stopped_instances),
            'old_rds_snapshots': len(rds_audit.old_snapshots),
            'unused_lambda_functions': len(lambda_audit.unused_functions),
            'over_provisioned_lambda': len(lambda_audit.over_provisioned_functions),
            's3_no_lifecycle': len(s3_audit.buckets_without_lifecycle),
            's3_incomplete_uploads': len(s3_audit.incomplete_multipart_uploads),
            'lb_no_targets': len(lb_audit.lbs_no_targets),
            'lb_low_traffic': len(lb_audit.lbs_low_traffic),
            'idle_nat_gateways': len(nat_gateway_audit.idle_gateways),
            'unused_nat_gateways': len(nat_gateway_audit.unused_gateways),
            'idle_elasticache': len(elasticache_audit.idle_clusters),
            'over_provisioned_elasticache': len(elasticache_audit.over_provisioned_clusters),
            'long_retention_logs': len(cloudwatch_logs_audit.long_retention_groups),
            'unused_log_groups': len(cloudwatch_logs_audit.unused_groups),
            'unused_dynamodb_tables': len(dynamodb_audit.unused_tables),
            'dynamodb_billing_opportunities': len(dynamodb_audit.billing_mode_opportunities),
            'uncovered_ec2_sp': len(savings_plans_audit.uncovered_ec2_instances),
            'uncovered_rds_ri': len(savings_plans_audit.uncovered_rds_instances),
            'underutilized_ri': len(savings_plans_audit.underutilized_ris),
            # Phase 6 findings
            'unused_vpc_endpoints': len(vpc_endpoint_audit.unused_endpoints),
            'duplicate_vpc_endpoints': len(vpc_endpoint_audit.duplicate_endpoints),
            'unused_efs_file_systems': len(efs_audit.unused_file_systems),
            'efs_no_lifecycle': len(efs_audit.file_systems_without_lifecycle),
            'orphaned_ebs_snapshots': len(ebs_snapshot_audit.orphaned_snapshots),
            'duplicate_ebs_snapshots': len(ebs_snapshot_audit.duplicate_snapshots),
            'high_cost_data_transfer': len(data_transfer_audit.high_cost_transfers),
            'unused_beanstalk_envs': len(beanstalk_audit.unused_environments),
            'nonprod_beanstalk_247': len(beanstalk_audit.nonprod_running_24_7),
        }

        total_findings = sum(findings_by_category.values())

        # Calculate total potential savings
        total_savings = (
            ec2_audit.total_potential_savings +
            ebs_audit.total_potential_savings +
            eip_audit.total_cost +
            rds_audit.total_potential_savings +
            lambda_audit.total_potential_savings +
            s3_audit.total_potential_savings +
            lb_audit.total_potential_savings +
            nat_gateway_audit.total_potential_savings +
            elasticache_audit.total_potential_savings +
            cloudwatch_logs_audit.total_potential_savings +
            dynamodb_audit.total_potential_savings +
            savings_plans_audit.total_potential_savings +
            # Phase 6 savings
            vpc_endpoint_audit.total_potential_savings +
            efs_audit.total_potential_savings +
            ebs_snapshot_audit.total_potential_savings +
            data_transfer_audit.total_potential_savings +
            beanstalk_audit.total_potential_savings
        )

        # Categorize findings by severity
        findings_by_severity = {
            'critical': (
                len(ec2_audit.idle_instances) + len(rds_audit.idle_instances) +
                len(nat_gateway_audit.unused_gateways) + len(elasticache_audit.idle_clusters) +
                len(savings_plans_audit.uncovered_ec2_instances)
            ),  # High cost items
            'high': (
                len(ebs_audit.unattached_volumes) + len(eip_audit.unattached_ips) +
                len(lb_audit.lbs_no_targets) + len(nat_gateway_audit.idle_gateways) +
                len(dynamodb_audit.unused_tables)
            ),
            'medium': (
                len(ec2_audit.stopped_instances) + len(ebs_audit.old_snapshots) +
                len(rds_audit.stopped_instances) + len(s3_audit.buckets_without_lifecycle) +
                len(elasticache_audit.over_provisioned_clusters) + len(cloudwatch_logs_audit.long_retention_groups) +
                len(dynamodb_audit.billing_mode_opportunities)
            ),
            'low': (
                len(tagging_audit.untagged_resources) + len(lambda_audit.unused_functions) +
                len(s3_audit.incomplete_multipart_uploads) + len(cloudwatch_logs_audit.unused_groups)
            ),
        }

        # Generate top opportunities (sorted by savings)
        opportunities = []

        if len(ec2_audit.idle_instances) > 0:
            opportunities.append((ec2_audit.total_idle_cost, f"{len(ec2_audit.idle_instances)} idle EC2 instances (${ec2_audit.total_idle_cost:.2f}/month)"))

        if len(rds_audit.idle_instances) > 0:
            opportunities.append((rds_audit.total_idle_cost, f"{len(rds_audit.idle_instances)} idle RDS instances (${rds_audit.total_idle_cost:.2f}/month)"))

        if len(ebs_audit.unattached_volumes) > 0:
            opportunities.append((ebs_audit.total_unattached_cost, f"{len(ebs_audit.unattached_volumes)} unattached EBS volumes (${ebs_audit.total_unattached_cost:.2f}/month)"))

        if len(s3_audit.buckets_without_lifecycle) > 0:
            opportunities.append((s3_audit.total_lifecycle_savings, f"{len(s3_audit.buckets_without_lifecycle)} S3 buckets without lifecycle (${s3_audit.total_lifecycle_savings:.2f}/month)"))

        if len(lb_audit.lbs_no_targets) > 0:
            opportunities.append((lb_audit.total_no_target_cost, f"{len(lb_audit.lbs_no_targets)} load balancers with no targets (${lb_audit.total_no_target_cost:.2f}/month)"))

        if len(lambda_audit.over_provisioned_functions) > 0:
            opportunities.append((lambda_audit.total_over_provisioned_waste, f"{len(lambda_audit.over_provisioned_functions)} over-provisioned Lambda (${lambda_audit.total_over_provisioned_waste:.2f}/month)"))

        if len(eip_audit.unattached_ips) > 0:
            opportunities.append((eip_audit.total_cost, f"{len(eip_audit.unattached_ips)} unattached Elastic IPs (${eip_audit.total_cost:.2f}/month)"))

        if len(ebs_audit.old_snapshots) > 0:
            opportunities.append((ebs_audit.total_snapshot_cost, f"{len(ebs_audit.old_snapshots)} old EBS snapshots (${ebs_audit.total_snapshot_cost:.2f}/month)"))

        if len(rds_audit.old_snapshots) > 0:
            opportunities.append((rds_audit.total_snapshot_cost, f"{len(rds_audit.old_snapshots)} old RDS snapshots (${rds_audit.total_snapshot_cost:.2f}/month)"))

        # Phase 5 opportunities
        if len(nat_gateway_audit.unused_gateways) > 0:
            opportunities.append((nat_gateway_audit.total_unused_cost, f"{len(nat_gateway_audit.unused_gateways)} unused NAT Gateways (${nat_gateway_audit.total_unused_cost:.2f}/month)"))

        if len(nat_gateway_audit.idle_gateways) > 0:
            opportunities.append((nat_gateway_audit.total_idle_waste, f"{len(nat_gateway_audit.idle_gateways)} idle NAT Gateways (${nat_gateway_audit.total_idle_waste:.2f}/month)"))

        if len(elasticache_audit.idle_clusters) > 0:
            opportunities.append((elasticache_audit.total_idle_cost, f"{len(elasticache_audit.idle_clusters)} idle ElastiCache clusters (${elasticache_audit.total_idle_cost:.2f}/month)"))

        if len(elasticache_audit.over_provisioned_clusters) > 0:
            opportunities.append((elasticache_audit.total_over_provisioned_waste, f"{len(elasticache_audit.over_provisioned_clusters)} over-provisioned ElastiCache (${elasticache_audit.total_over_provisioned_waste:.2f}/month)"))

        if len(cloudwatch_logs_audit.long_retention_groups) > 0:
            opportunities.append((cloudwatch_logs_audit.total_retention_waste, f"{len(cloudwatch_logs_audit.long_retention_groups)} log groups with long retention (${cloudwatch_logs_audit.total_retention_waste:.2f}/month)"))

        if len(cloudwatch_logs_audit.unused_groups) > 0:
            opportunities.append((cloudwatch_logs_audit.total_unused_cost, f"{len(cloudwatch_logs_audit.unused_groups)} unused log groups (${cloudwatch_logs_audit.total_unused_cost:.2f}/month)"))

        if len(dynamodb_audit.unused_tables) > 0:
            opportunities.append((dynamodb_audit.total_unused_cost, f"{len(dynamodb_audit.unused_tables)} unused DynamoDB tables (${dynamodb_audit.total_unused_cost:.2f}/month)"))

        if len(dynamodb_audit.billing_mode_opportunities) > 0:
            opportunities.append((dynamodb_audit.total_billing_mode_savings, f"{len(dynamodb_audit.billing_mode_opportunities)} DynamoDB billing optimizations (${dynamodb_audit.total_billing_mode_savings:.2f}/month)"))

        if len(savings_plans_audit.uncovered_ec2_instances) > 0:
            opportunities.append((savings_plans_audit.total_ec2_savings_opportunity, f"{len(savings_plans_audit.uncovered_ec2_instances)} EC2 instances without Savings Plans (${savings_plans_audit.total_ec2_savings_opportunity:.2f}/month)"))

        if len(savings_plans_audit.uncovered_rds_instances) > 0:
            opportunities.append((savings_plans_audit.total_rds_savings_opportunity, f"{len(savings_plans_audit.uncovered_rds_instances)} RDS instances without RIs (${savings_plans_audit.total_rds_savings_opportunity:.2f}/month)"))

        if len(savings_plans_audit.underutilized_ris) > 0:
            opportunities.append((savings_plans_audit.total_ri_waste, f"{len(savings_plans_audit.underutilized_ris)} underutilized Reserved Instances (${savings_plans_audit.total_ri_waste:.2f}/month)"))

        # Sort by savings (descending) and take top 5
        opportunities.sort(key=lambda x: x[0], reverse=True)
        top_opportunities = [opp[1] for opp in opportunities[:5]]

        return AuditSummary(
            total_findings=total_findings,
            total_potential_savings=round(total_savings, 2),
            findings_by_category=findings_by_category,
            findings_by_severity=findings_by_severity,
            top_opportunities=top_opportunities
        )
