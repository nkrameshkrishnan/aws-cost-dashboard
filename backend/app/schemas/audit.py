"""
Schemas for FinOps audit findings and results.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class AuditSeverity(str, Enum):
    """Severity levels for audit findings."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditCategory(str, Enum):
    """Categories of audit findings."""
    IDLE_RESOURCES = "idle_resources"
    UNATTACHED_RESOURCES = "unattached_resources"
    UNTAGGED_RESOURCES = "untagged_resources"
    OVERSIZED_RESOURCES = "oversized_resources"
    OLD_SNAPSHOTS = "old_snapshots"


# EC2 Audit Schemas
class EC2IdleInstance(BaseModel):
    """Idle EC2 instance finding."""
    instance_id: str
    instance_type: str
    instance_name: Optional[str] = None
    state: str
    launch_time: datetime
    avg_cpu_utilization: float
    days_running: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class EC2StoppedInstance(BaseModel):
    """Stopped EC2 instance finding."""
    instance_id: str
    instance_type: str
    instance_name: Optional[str] = None
    stopped_time: Optional[datetime] = None
    days_stopped: int
    estimated_ebs_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


# EBS Audit Schemas
class EBSUnattachedVolume(BaseModel):
    """Unattached EBS volume finding."""
    volume_id: str
    volume_type: str
    size_gb: int
    created_time: datetime
    days_unattached: int
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class EBSOldSnapshot(BaseModel):
    """Old EBS snapshot finding."""
    snapshot_id: str
    volume_id: Optional[str] = None
    size_gb: int
    created_time: datetime
    days_old: int
    estimated_monthly_cost: float
    region: str
    description: Optional[str] = None
    tags: Dict[str, str] = {}
    recommendation: str


# Elastic IP Audit Schemas
class ElasticIPUnattached(BaseModel):
    """Unattached Elastic IP finding."""
    allocation_id: str
    public_ip: str
    days_unattached: int
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


# Tagging Compliance Schemas
class UntaggedResource(BaseModel):
    """Untagged resource finding."""
    resource_type: str  # ec2, rds, lambda, elb, etc.
    resource_id: str
    resource_name: Optional[str] = None
    resource_arn: Optional[str] = None
    region: str
    missing_tags: List[str]
    current_tags: Dict[str, str] = {}
    recommendation: str


# RDS Audit Schemas
class RDSIdleInstance(BaseModel):
    """Idle RDS instance finding."""
    db_instance_id: str
    db_instance_class: str
    engine: str
    engine_version: str
    allocated_storage_gb: int
    status: str
    created_time: datetime
    avg_cpu_utilization: float
    avg_connections: float
    days_running: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class RDSStoppedInstance(BaseModel):
    """Stopped RDS instance finding."""
    db_instance_id: str
    db_instance_class: str
    engine: str
    allocated_storage_gb: int
    stopped_time: Optional[datetime] = None
    days_stopped: int
    estimated_storage_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class RDSOldSnapshot(BaseModel):
    """Old RDS snapshot finding."""
    snapshot_id: str
    db_instance_id: Optional[str] = None
    engine: str
    allocated_storage_gb: int
    snapshot_type: str  # manual, automated
    created_time: datetime
    days_old: int
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


# Lambda Audit Schemas
class LambdaUnusedFunction(BaseModel):
    """Unused Lambda function finding."""
    function_name: str
    function_arn: str
    runtime: str
    memory_mb: int
    last_modified: datetime
    days_since_invocation: int
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class LambdaOverProvisionedFunction(BaseModel):
    """Over-provisioned Lambda function finding."""
    function_name: str
    function_arn: str
    runtime: str
    configured_memory_mb: int
    avg_memory_used_mb: float
    memory_utilization_percent: float
    monthly_invocations: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


# S3 Audit Schemas
class S3BucketWithoutLifecycle(BaseModel):
    """S3 bucket without lifecycle policy finding."""
    bucket_name: str
    creation_date: datetime
    total_size_gb: float
    object_count: int
    storage_class_breakdown: Dict[str, float]  # storage class -> size in GB
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class S3IncompleteMultipartUpload(BaseModel):
    """S3 incomplete multipart upload finding."""
    bucket_name: str
    upload_id: str
    key: str
    initiated_date: datetime
    days_old: int
    parts_count: int
    estimated_size_gb: float
    estimated_monthly_cost: float
    region: str
    recommendation: str


# Load Balancer Audit Schemas
class LoadBalancerNoTargets(BaseModel):
    """Load balancer with no targets finding."""
    lb_name: str
    lb_arn: str
    lb_type: str  # application, network, classic
    created_time: datetime
    days_active: int
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class LoadBalancerLowTraffic(BaseModel):
    """Load balancer with low traffic finding."""
    lb_name: str
    lb_arn: str
    lb_type: str  # application, network, classic
    created_time: datetime
    avg_request_count: float
    avg_processed_bytes: float
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


# Aggregate Audit Results
class AuditSummary(BaseModel):
    """Summary of audit findings."""
    total_findings: int
    total_potential_savings: float
    findings_by_category: Dict[str, int]
    findings_by_severity: Dict[str, int]
    top_opportunities: List[str]


class EC2AuditResults(BaseModel):
    """EC2 audit results."""
    idle_instances: List[EC2IdleInstance] = []
    stopped_instances: List[EC2StoppedInstance] = []
    total_idle_cost: float = 0.0
    total_stopped_ebs_cost: float = 0.0
    total_potential_savings: float = 0.0


class EBSAuditResults(BaseModel):
    """EBS audit results."""
    unattached_volumes: List[EBSUnattachedVolume] = []
    old_snapshots: List[EBSOldSnapshot] = []
    total_unattached_cost: float = 0.0
    total_snapshot_cost: float = 0.0
    total_potential_savings: float = 0.0


class ElasticIPAuditResults(BaseModel):
    """Elastic IP audit results."""
    unattached_ips: List[ElasticIPUnattached] = []
    total_cost: float = 0.0


class TaggingAuditResults(BaseModel):
    """Tagging compliance audit results."""
    untagged_resources: List[UntaggedResource] = []
    total_untagged: int = 0
    compliance_percentage: float = 0.0


class RDSAuditResults(BaseModel):
    """RDS audit results."""
    idle_instances: List[RDSIdleInstance] = []
    stopped_instances: List[RDSStoppedInstance] = []
    old_snapshots: List[RDSOldSnapshot] = []
    total_idle_cost: float = 0.0
    total_stopped_storage_cost: float = 0.0
    total_snapshot_cost: float = 0.0
    total_potential_savings: float = 0.0


class LambdaAuditResults(BaseModel):
    """Lambda audit results."""
    unused_functions: List[LambdaUnusedFunction] = []
    over_provisioned_functions: List[LambdaOverProvisionedFunction] = []
    total_unused_cost: float = 0.0
    total_over_provisioned_waste: float = 0.0
    total_potential_savings: float = 0.0


class S3AuditResults(BaseModel):
    """S3 audit results."""
    buckets_without_lifecycle: List[S3BucketWithoutLifecycle] = []
    incomplete_multipart_uploads: List[S3IncompleteMultipartUpload] = []
    total_lifecycle_savings: float = 0.0
    total_multipart_waste: float = 0.0
    total_potential_savings: float = 0.0


class LoadBalancerAuditResults(BaseModel):
    """Load Balancer audit results."""
    lbs_no_targets: List[LoadBalancerNoTargets] = []
    lbs_low_traffic: List[LoadBalancerLowTraffic] = []
    total_no_target_cost: float = 0.0
    total_low_traffic_waste: float = 0.0
    total_potential_savings: float = 0.0


# NAT Gateway Audit Schemas (Phase 5)
class NATGatewayIdle(BaseModel):
    """Idle NAT Gateway finding."""
    nat_gateway_id: str
    subnet_id: str
    vpc_id: str
    created_time: datetime
    days_active: int
    avg_gb_out_per_day: float
    avg_gb_in_per_day: float
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class NATGatewayUnused(BaseModel):
    """Unused NAT Gateway finding."""
    nat_gateway_id: str
    subnet_id: str
    vpc_id: str
    created_time: datetime
    days_active: int
    avg_gb_out_per_day: float
    avg_gb_in_per_day: float
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class NATGatewayAuditResults(BaseModel):
    """NAT Gateway audit results."""
    idle_gateways: List[NATGatewayIdle] = []
    unused_gateways: List[NATGatewayUnused] = []
    total_idle_waste: float = 0.0
    total_unused_cost: float = 0.0
    total_potential_savings: float = 0.0


# ElastiCache Audit Schemas (Phase 5)
class ElastiCacheIdleCluster(BaseModel):
    """Idle ElastiCache cluster finding."""
    cluster_id: str
    cluster_type: str  # redis or memcached
    node_type: str
    num_nodes: int
    status: str
    avg_cpu_utilization: float
    cache_hit_rate: float
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class ElastiCacheOverProvisionedCluster(BaseModel):
    """Over-provisioned ElastiCache cluster finding."""
    cluster_id: str
    cluster_type: str
    current_node_type: str
    num_nodes: int
    avg_cpu_utilization: float
    avg_memory_utilization: float
    evictions_per_day: float
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class ElastiCacheAuditResults(BaseModel):
    """ElastiCache audit results."""
    idle_clusters: List[ElastiCacheIdleCluster] = []
    over_provisioned_clusters: List[ElastiCacheOverProvisionedCluster] = []
    total_idle_cost: float = 0.0
    total_over_provisioned_waste: float = 0.0
    total_potential_savings: float = 0.0


# CloudWatch Logs Audit Schemas (Phase 5)
class CloudWatchLogGroupLongRetention(BaseModel):
    """Log group with long retention finding."""
    log_group_name: str
    stored_gb: float
    current_retention_days: int
    recommended_retention_days: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class CloudWatchLogGroupUnused(BaseModel):
    """Unused log group finding."""
    log_group_name: str
    stored_gb: float
    retention_days: int
    last_event_time: datetime
    days_since_last_event: int
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class CloudWatchLogsAuditResults(BaseModel):
    """CloudWatch Logs audit results."""
    long_retention_groups: List[CloudWatchLogGroupLongRetention] = []
    unused_groups: List[CloudWatchLogGroupUnused] = []
    total_retention_waste: float = 0.0
    total_unused_cost: float = 0.0
    total_potential_savings: float = 0.0


# DynamoDB Audit Schemas (Phase 5)
class DynamoDBUnusedTable(BaseModel):
    """Unused DynamoDB table finding."""
    table_name: str
    table_size_gb: float
    item_count: int
    billing_mode: str
    days_without_activity: int
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class DynamoDBBillingModeOptimization(BaseModel):
    """DynamoDB billing mode optimization finding."""
    table_name: str
    current_billing_mode: str
    recommended_billing_mode: str
    current_read_capacity: int
    current_write_capacity: int
    avg_read_utilization: float
    avg_write_utilization: float
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class DynamoDBAuditResults(BaseModel):
    """DynamoDB audit results."""
    unused_tables: List[DynamoDBUnusedTable] = []
    billing_mode_opportunities: List[DynamoDBBillingModeOptimization] = []
    total_unused_cost: float = 0.0
    total_billing_mode_savings: float = 0.0
    total_potential_savings: float = 0.0


# Savings Plans/RI Coverage Audit Schemas (Phase 5)
class UncoveredEC2Instance(BaseModel):
    """EC2 instance not covered by Savings Plan finding."""
    instance_id: str
    instance_type: str
    instance_name: Optional[str] = None
    days_running: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    recommended_commitment: str
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class UncoveredRDSInstance(BaseModel):
    """RDS instance not covered by Reserved Instance finding."""
    db_instance_id: str
    db_instance_class: str
    engine: str
    days_running: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    recommended_commitment: str
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class UnderutilizedReservedInstance(BaseModel):
    """Underutilized Reserved Instance finding."""
    reservation_id: str
    instance_type: str
    instance_count: int
    utilization_percentage: float
    wasted_monthly_cost: float
    expiration_date: datetime
    region: str
    recommendation: str


class SavingsPlansCoverageResults(BaseModel):
    """Savings Plans and RI coverage audit results."""
    uncovered_ec2_instances: List[UncoveredEC2Instance] = []
    uncovered_rds_instances: List[UncoveredRDSInstance] = []
    underutilized_ris: List[UnderutilizedReservedInstance] = []
    total_ec2_savings_opportunity: float = 0.0
    total_rds_savings_opportunity: float = 0.0
    total_ri_waste: float = 0.0
    total_potential_savings: float = 0.0
    ec2_coverage_percentage: float = 0.0
    rds_coverage_percentage: float = 0.0


# VPC Endpoints Audit Schemas (Phase 6)
class VPCEndpointUnused(BaseModel):
    """Unused VPC Endpoint finding."""
    endpoint_id: str
    service_name: str
    endpoint_type: str  # Interface or Gateway
    vpc_id: str
    num_azs: int
    days_active: int
    avg_gb_per_day: float
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class VPCEndpointDuplicate(BaseModel):
    """Duplicate VPC Endpoint finding."""
    service_name: str
    vpc_id: str
    endpoint_ids: List[str]
    duplicate_count: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    recommendation: str


class VPCEndpointAuditResults(BaseModel):
    """VPC Endpoints audit results."""
    unused_endpoints: List[VPCEndpointUnused] = []
    duplicate_endpoints: List[VPCEndpointDuplicate] = []
    total_unused_cost: float = 0.0
    total_duplicate_waste: float = 0.0
    total_potential_savings: float = 0.0


# EFS Audit Schemas (Phase 6)
class EFSUnusedFileSystem(BaseModel):
    """Unused EFS file system finding."""
    file_system_id: str
    file_system_name: Optional[str] = None
    size_gb: float
    creation_time: datetime
    days_without_connections: int
    performance_mode: str
    throughput_mode: str
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class EFSWithoutLifecycle(BaseModel):
    """EFS without lifecycle policy finding."""
    file_system_id: str
    file_system_name: Optional[str] = None
    size_gb: float
    standard_storage_gb: float
    performance_mode: str
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class EFSAuditResults(BaseModel):
    """EFS audit results."""
    unused_file_systems: List[EFSUnusedFileSystem] = []
    file_systems_without_lifecycle: List[EFSWithoutLifecycle] = []
    total_unused_cost: float = 0.0
    total_lifecycle_savings: float = 0.0
    total_potential_savings: float = 0.0


# EBS Snapshot Optimization Schemas (Phase 6)
class EBSOrphanedSnapshot(BaseModel):
    """Orphaned EBS snapshot finding (AMI deleted)."""
    snapshot_id: str
    volume_id: Optional[str] = None
    size_gb: int
    created_time: datetime
    days_old: int
    ami_id: Optional[str] = None
    ami_deleted: bool
    estimated_monthly_cost: float
    region: str
    description: Optional[str] = None
    tags: Dict[str, str] = {}
    recommendation: str


class EBSDuplicateSnapshot(BaseModel):
    """Duplicate EBS snapshot finding."""
    volume_id: str
    snapshot_ids: List[str]
    duplicate_count: int
    size_gb: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    recommendation: str


class EBSSnapshotAuditResults(BaseModel):
    """EBS Snapshot optimization audit results."""
    orphaned_snapshots: List[EBSOrphanedSnapshot] = []
    duplicate_snapshots: List[EBSDuplicateSnapshot] = []
    total_orphaned_cost: float = 0.0
    total_duplicate_waste: float = 0.0
    total_potential_savings: float = 0.0


# Data Transfer Analysis Schemas (Phase 6)
class DataTransferHighCost(BaseModel):
    """High data transfer cost finding."""
    service: str  # NAT Gateway, EC2, etc.
    transfer_type: str  # cross-az, cross-region, internet
    source_region: str
    dest_region: Optional[str] = None
    monthly_gb: float
    estimated_monthly_cost: float
    potential_monthly_savings: float
    recommendation: str


class DataTransferAuditResults(BaseModel):
    """Data Transfer analysis audit results."""
    high_cost_transfers: List[DataTransferHighCost] = []
    total_transfer_cost: float = 0.0
    total_potential_savings: float = 0.0


# Elastic Beanstalk Audit Schemas (Phase 6)
class ElasticBeanstalkUnusedEnvironment(BaseModel):
    """Unused Elastic Beanstalk environment finding."""
    environment_name: str
    environment_id: str
    application_name: str
    status: str
    health: str
    days_since_deployment: int
    request_count_per_day: float
    estimated_monthly_cost: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class ElasticBeanstalkNonProdRunning(BaseModel):
    """Non-production Beanstalk environment running 24/7 finding."""
    environment_name: str
    environment_id: str
    application_name: str
    tier: str
    environment_type: str  # dev, test, staging (from tags)
    instance_count: int
    estimated_monthly_cost: float
    potential_monthly_savings: float
    region: str
    tags: Dict[str, str] = {}
    recommendation: str


class ElasticBeanstalkAuditResults(BaseModel):
    """Elastic Beanstalk audit results."""
    unused_environments: List[ElasticBeanstalkUnusedEnvironment] = []
    nonprod_running_24_7: List[ElasticBeanstalkNonProdRunning] = []
    total_unused_cost: float = 0.0
    total_nonprod_waste: float = 0.0
    total_potential_savings: float = 0.0


# Phase 7 Audit Schemas - CloudFront
class CloudFrontUnusedDistribution(BaseModel):
    """Unused CloudFront distribution finding."""
    distribution_id: str
    domain_name: str
    enabled: bool
    total_requests: int
    days_checked: int
    estimated_monthly_cost: float
    recommendation: str


class CloudFrontNoLogging(BaseModel):
    """CloudFront distribution without logging finding."""
    distribution_id: str
    domain_name: str
    enabled: bool
    logging_enabled: bool
    recommendation: str


class CloudFrontAuditResults(BaseModel):
    """CloudFront audit results."""
    unused_distributions: List[CloudFrontUnusedDistribution] = []
    distributions_without_logging: List[CloudFrontNoLogging] = []
    total_unused_cost: float = 0.0


# Phase 7 Audit Schemas - Route53
class Route53UnusedHostedZone(BaseModel):
    """Unused Route53 hosted zone finding."""
    hosted_zone_id: str
    hosted_zone_name: str
    is_private: bool
    total_records: int
    user_records: int
    estimated_monthly_cost: float
    recommendation: str


class Route53AuditResults(BaseModel):
    """Route53 audit results."""
    unused_hosted_zones: List[Route53UnusedHostedZone] = []
    total_potential_savings: float = 0.0


# Phase 7 Audit Schemas - SQS
class SQSUnusedQueue(BaseModel):
    """Unused SQS queue finding."""
    queue_name: str
    queue_url: str
    region: str
    is_fifo: bool
    messages_available: int
    total_sent_period: int
    days_checked: int
    retention_period_seconds: int
    recommendation: str


class SQSHighRetentionQueue(BaseModel):
    """SQS queue with high retention finding."""
    queue_name: str
    queue_url: str
    region: str
    retention_period_days: float
    retention_period_seconds: int
    max_retention_days: int
    recommendation: str


class SQSAuditResults(BaseModel):
    """SQS audit results."""
    unused_queues: List[SQSUnusedQueue] = []
    high_retention_queues: List[SQSHighRetentionQueue] = []


# Phase 7 Audit Schemas - SNS
class SNSUnusedTopic(BaseModel):
    """Unused SNS topic finding."""
    topic_name: str
    topic_arn: str
    region: str
    subscriptions_confirmed: int
    subscriptions_pending: int
    messages_published: int
    days_checked: int
    recommendation: str


class SNSAuditResults(BaseModel):
    """SNS audit results."""
    unused_topics: List[SNSUnusedTopic] = []


# Phase 7 Audit Schemas - API Gateway
class APIGatewayUnusedAPI(BaseModel):
    """Unused API Gateway API finding."""
    api_id: str
    api_name: str
    stage: str
    region: str
    total_requests: int
    days_checked: int
    created_date: Optional[str] = None
    recommendation: str


class APIGatewayNoCaching(BaseModel):
    """API Gateway without caching finding."""
    api_id: str
    api_name: str
    stage: str
    region: str
    cache_enabled: bool
    avg_daily_requests: int
    potential_cost_savings: float
    recommendation: str


class APIGatewayAuditResults(BaseModel):
    """API Gateway audit results."""
    unused_apis: List[APIGatewayUnusedAPI] = []
    apis_without_caching: List[APIGatewayNoCaching] = []
    total_potential_savings: float = 0.0


# Phase 7 Audit Schemas - Step Functions
class StepFunctionsUnusedStateMachine(BaseModel):
    """Unused Step Functions state machine finding."""
    state_machine_name: str
    state_machine_arn: str
    type: str
    region: str
    total_executions: Optional[int] = None
    days_since_last_execution: Optional[int] = None
    last_execution_date: Optional[str] = None
    created_date: Optional[str] = None
    recommendation: str


class StepFunctionsAuditResults(BaseModel):
    """Step Functions audit results."""
    unused_state_machines: List[StepFunctionsUnusedStateMachine] = []


# Phase 7 Audit Schemas - ECS
class ECSOversizedTask(BaseModel):
    """ECS oversized task finding."""
    cluster_name: str
    service_name: str
    region: str
    launch_type: str
    task_cpu: str
    task_memory: str
    avg_cpu_utilization: float
    avg_memory_utilization: float
    desired_count: int
    recommendation: str


class ECSAuditResults(BaseModel):
    """ECS audit results."""
    oversized_tasks: List[ECSOversizedTask] = []


# Phase 7 Audit Schemas - Redshift
class RedshiftIdleCluster(BaseModel):
    """Idle Redshift cluster finding."""
    cluster_identifier: str
    region: str
    cluster_status: str
    node_type: str
    number_of_nodes: int
    avg_database_connections: float
    days_checked: int
    estimated_monthly_cost: float
    recommendation: str


class RedshiftAuditResults(BaseModel):
    """Redshift audit results."""
    idle_clusters: List[RedshiftIdleCluster] = []
    total_potential_savings: float = 0.0


# Phase 7 Audit Schemas - Kinesis
class KinesisUnusedStream(BaseModel):
    """Unused Kinesis stream finding."""
    stream_name: str
    region: str
    stream_status: str
    shard_count: int
    incoming_records: int
    days_checked: int
    estimated_monthly_cost: float
    recommendation: str


class KinesisAuditResults(BaseModel):
    """Kinesis audit results."""
    unused_streams: List[KinesisUnusedStream] = []
    total_potential_savings: float = 0.0


# Phase 7 Audit Schemas - Glue
class GlueUnusedCrawler(BaseModel):
    """Unused Glue crawler finding."""
    crawler_name: str
    region: str
    crawler_state: str
    last_crawl_status: str
    days_since_last_crawl: Optional[int] = None
    last_crawl_date: Optional[str] = None
    recommendation: str


class GlueUnusedJob(BaseModel):
    """Unused Glue job finding."""
    job_name: str
    region: str
    worker_type: Optional[str] = None
    number_of_workers: Optional[int] = None
    max_capacity: Optional[float] = None
    last_run_status: str
    days_since_last_run: Optional[int] = None
    last_run_date: Optional[str] = None
    recommendation: str


class GlueAuditResults(BaseModel):
    """Glue audit results."""
    unused_crawlers: List[GlueUnusedCrawler] = []
    unused_jobs: List[GlueUnusedJob] = []


class FullAuditResults(BaseModel):
    """Complete audit results for an AWS account."""
    account_name: str
    audit_timestamp: datetime
    ec2_audit: EC2AuditResults
    ebs_audit: EBSAuditResults
    eip_audit: ElasticIPAuditResults
    tagging_audit: TaggingAuditResults
    rds_audit: Optional[RDSAuditResults] = None
    lambda_audit: Optional[LambdaAuditResults] = None
    s3_audit: Optional[S3AuditResults] = None
    lb_audit: Optional[LoadBalancerAuditResults] = None
    nat_gateway_audit: Optional[NATGatewayAuditResults] = None
    elasticache_audit: Optional[ElastiCacheAuditResults] = None
    cloudwatch_logs_audit: Optional[CloudWatchLogsAuditResults] = None
    dynamodb_audit: Optional[DynamoDBAuditResults] = None
    savings_plans_audit: Optional[SavingsPlansCoverageResults] = None
    # Phase 6 audits
    vpc_endpoint_audit: Optional[VPCEndpointAuditResults] = None
    efs_audit: Optional[EFSAuditResults] = None
    ebs_snapshot_audit: Optional[EBSSnapshotAuditResults] = None
    data_transfer_audit: Optional[DataTransferAuditResults] = None
    beanstalk_audit: Optional[ElasticBeanstalkAuditResults] = None
    # Phase 7 audits
    cloudfront_audit: Optional[CloudFrontAuditResults] = None
    route53_audit: Optional[Route53AuditResults] = None
    sqs_audit: Optional[SQSAuditResults] = None
    sns_audit: Optional[SNSAuditResults] = None
    apigateway_audit: Optional[APIGatewayAuditResults] = None
    stepfunctions_audit: Optional[StepFunctionsAuditResults] = None
    ecs_audit: Optional[ECSAuditResults] = None
    redshift_audit: Optional[RedshiftAuditResults] = None
    kinesis_audit: Optional[KinesisAuditResults] = None
    glue_audit: Optional[GlueAuditResults] = None
    summary: AuditSummary


# API Request/Response Schemas
class AuditRequest(BaseModel):
    """Request to run an audit."""
    account_name: str
    audit_types: List[str] = Field(
        default=["ec2", "ebs", "eip", "tagging", "rds", "lambda", "s3", "lb", "nat_gateway", "elasticache", "cloudwatch_logs", "dynamodb", "savings_plans", "vpc_endpoint", "efs", "ebs_snapshot", "data_transfer", "beanstalk", "cloudfront", "route53", "sqs", "sns", "apigateway", "stepfunctions", "ecs", "redshift", "kinesis", "glue"],
        description="Types of audits to run (ec2, ebs, eip, tagging, rds, lambda, s3, lb, nat_gateway, elasticache, cloudwatch_logs, dynamodb, savings_plans, vpc_endpoint, efs, ebs_snapshot, data_transfer, beanstalk, cloudfront, route53, sqs, sns, apigateway, stepfunctions, ecs, redshift, kinesis, glue)"
    )
    regions: List[str] = Field(
        default=[],
        description="AWS regions to scan (empty list scans all enabled regions)"
    )
    cpu_threshold: float = Field(
        default=5.0,
        description="CPU threshold for idle EC2 instances (%)"
    )
    days_stopped_threshold: int = Field(
        default=7,
        description="Days threshold for stopped instances"
    )
    days_unattached_threshold: int = Field(
        default=7,
        description="Days threshold for unattached volumes"
    )
    snapshot_age_threshold: int = Field(
        default=90,
        description="Age threshold for old snapshots (days)"
    )
    required_tags: List[str] = Field(
        default=["Environment", "Owner", "Project"],
        description="Required tags for compliance"
    )
    skip_empty_regions: bool = Field(
        default=True,
        description="Skip regions with minimal activity (speeds up audit significantly)"
    )
    min_region_cost: float = Field(
        default=1.0,
        description="Minimum monthly cost to scan a region ($ - used when skip_empty_regions=True)"
    )
    quick_audit_top_regions: Optional[int] = Field(
        default=None,
        description="Quick audit mode: scan only top N regions by cost (None = scan all)"
    )


class AuditJobStatus(BaseModel):
    """Status of an audit job."""
    job_id: str
    account_name: str
    audit_types: List[str]
    status: str  # pending, running, completed, failed
    progress: int = 0  # 0-100
    current_step: str = "Initializing..."
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    partial_results: Optional[Dict[str, Any]] = None
    results: Optional[FullAuditResults] = None
