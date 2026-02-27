/**
 * TypeScript types for FinOps audit features.
 */

export interface EC2IdleInstance {
  instance_id: string
  instance_type: string
  instance_name: string | null
  state: string
  launch_time: string
  avg_cpu_utilization: number
  days_running: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface EC2StoppedInstance {
  instance_id: string
  instance_type: string
  instance_name: string | null
  stopped_time: string | null
  days_stopped: number
  estimated_ebs_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface EBSUnattachedVolume {
  volume_id: string
  volume_type: string
  size_gb: number
  created_time: string
  days_unattached: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface EBSOldSnapshot {
  snapshot_id: string
  volume_id: string | null
  size_gb: number
  created_time: string
  days_old: number
  estimated_monthly_cost: number
  region: string
  description: string | null
  tags: Record<string, string>
  recommendation: string
}

export interface ElasticIPUnattached {
  allocation_id: string
  public_ip: string
  days_unattached: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface UntaggedResource {
  resource_type: string
  resource_id: string
  resource_name: string | null
  resource_arn: string | null
  region: string
  missing_tags: string[]
  current_tags: Record<string, string>
  recommendation: string
}

export interface EC2AuditResults {
  idle_instances: EC2IdleInstance[]
  stopped_instances: EC2StoppedInstance[]
  total_idle_cost: number
  total_stopped_ebs_cost: number
  total_potential_savings: number
}

export interface EBSAuditResults {
  unattached_volumes: EBSUnattachedVolume[]
  old_snapshots: EBSOldSnapshot[]
  total_unattached_cost: number
  total_snapshot_cost: number
  total_potential_savings: number
}

export interface ElasticIPAuditResults {
  unattached_ips: ElasticIPUnattached[]
  total_cost: number
}

export interface TaggingAuditResults {
  untagged_resources: UntaggedResource[]
  total_untagged: number
  compliance_percentage: number
}

// RDS Audit Types
export interface RDSIdleInstance {
  db_instance_id: string
  db_instance_class: string
  engine: string
  engine_version: string
  allocated_storage_gb: number
  status: string
  created_time: string
  avg_cpu_utilization: number
  avg_connections: number
  days_running: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface RDSStoppedInstance {
  db_instance_id: string
  db_instance_class: string
  engine: string
  allocated_storage_gb: number
  stopped_time: string | null
  days_stopped: number
  estimated_storage_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface RDSOldSnapshot {
  snapshot_id: string
  db_instance_id: string | null
  engine: string
  allocated_storage_gb: number
  snapshot_type: string
  created_time: string
  days_old: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface RDSAuditResults {
  idle_instances: RDSIdleInstance[]
  stopped_instances: RDSStoppedInstance[]
  old_snapshots: RDSOldSnapshot[]
  total_idle_cost: number
  total_stopped_storage_cost: number
  total_snapshot_cost: number
  total_potential_savings: number
}

// Lambda Audit Types
export interface LambdaUnusedFunction {
  function_name: string
  function_arn: string
  runtime: string
  memory_mb: number
  last_modified: string
  days_since_invocation: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface LambdaOverProvisionedFunction {
  function_name: string
  function_arn: string
  runtime: string
  configured_memory_mb: number
  avg_memory_used_mb: number
  memory_utilization_percent: number
  monthly_invocations: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface LambdaAuditResults {
  unused_functions: LambdaUnusedFunction[]
  over_provisioned_functions: LambdaOverProvisionedFunction[]
  total_unused_cost: number
  total_over_provisioned_waste: number
  total_potential_savings: number
}

// S3 Audit Types
export interface S3BucketWithoutLifecycle {
  bucket_name: string
  creation_date: string
  total_size_gb: number
  object_count: number
  storage_class_breakdown: Record<string, number>
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface S3IncompleteMultipartUpload {
  bucket_name: string
  upload_id: string
  key: string
  initiated_date: string
  days_old: number
  parts_count: number
  estimated_size_gb: number
  estimated_monthly_cost: number
  region: string
  recommendation: string
}

export interface S3AuditResults {
  buckets_without_lifecycle: S3BucketWithoutLifecycle[]
  incomplete_multipart_uploads: S3IncompleteMultipartUpload[]
  total_lifecycle_savings: number
  total_multipart_waste: number
  total_potential_savings: number
}

// Load Balancer Audit Types
export interface LoadBalancerNoTargets {
  lb_name: string
  lb_arn: string
  lb_type: string
  created_time: string
  days_active: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface LoadBalancerLowTraffic {
  lb_name: string
  lb_arn: string
  lb_type: string
  created_time: string
  avg_request_count: number
  avg_processed_bytes: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface LoadBalancerAuditResults {
  lbs_no_targets: LoadBalancerNoTargets[]
  lbs_low_traffic: LoadBalancerLowTraffic[]
  total_no_target_cost: number
  total_low_traffic_waste: number
  total_potential_savings: number
}

// NAT Gateway Audit Types (Phase 5)
export interface NATGatewayIdle {
  nat_gateway_id: string
  subnet_id: string
  vpc_id: string
  created_time: string
  days_active: number
  avg_gb_out_per_day: number
  avg_gb_in_per_day: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface NATGatewayUnused {
  nat_gateway_id: string
  subnet_id: string
  vpc_id: string
  created_time: string
  days_active: number
  avg_gb_out_per_day: number
  avg_gb_in_per_day: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface NATGatewayAuditResults {
  idle_gateways: NATGatewayIdle[]
  unused_gateways: NATGatewayUnused[]
  total_idle_waste: number
  total_unused_cost: number
  total_potential_savings: number
}

// ElastiCache Audit Types (Phase 5)
export interface ElastiCacheIdleCluster {
  cluster_id: string
  cluster_type: string
  node_type: string
  num_nodes: number
  status: string
  avg_cpu_utilization: number
  cache_hit_rate: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface ElastiCacheOverProvisionedCluster {
  cluster_id: string
  cluster_type: string
  current_node_type: string
  num_nodes: number
  avg_cpu_utilization: number
  avg_memory_utilization: number
  evictions_per_day: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface ElastiCacheAuditResults {
  idle_clusters: ElastiCacheIdleCluster[]
  over_provisioned_clusters: ElastiCacheOverProvisionedCluster[]
  total_idle_cost: number
  total_over_provisioned_waste: number
  total_potential_savings: number
}

// CloudWatch Logs Audit Types (Phase 5)
export interface CloudWatchLogGroupLongRetention {
  log_group_name: string
  stored_gb: number
  current_retention_days: number
  recommended_retention_days: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface CloudWatchLogGroupUnused {
  log_group_name: string
  stored_gb: number
  retention_days: number
  last_event_time: string
  days_since_last_event: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface CloudWatchLogsAuditResults {
  long_retention_groups: CloudWatchLogGroupLongRetention[]
  unused_groups: CloudWatchLogGroupUnused[]
  total_retention_waste: number
  total_unused_cost: number
  total_potential_savings: number
}

// DynamoDB Audit Types (Phase 5)
export interface DynamoDBUnusedTable {
  table_name: string
  table_size_gb: number
  item_count: number
  billing_mode: string
  days_without_activity: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface DynamoDBBillingModeOptimization {
  table_name: string
  current_billing_mode: string
  recommended_billing_mode: string
  current_read_capacity: number
  current_write_capacity: number
  avg_read_utilization: number
  avg_write_utilization: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface DynamoDBAuditResults {
  unused_tables: DynamoDBUnusedTable[]
  billing_mode_opportunities: DynamoDBBillingModeOptimization[]
  total_unused_cost: number
  total_billing_mode_savings: number
  total_potential_savings: number
}

// Savings Plans/RI Coverage Audit Types (Phase 5)
export interface UncoveredEC2Instance {
  instance_id: string
  instance_type: string
  instance_name: string | null
  days_running: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  recommended_commitment: string
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface UncoveredRDSInstance {
  db_instance_id: string
  db_instance_class: string
  engine: string
  days_running: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  recommended_commitment: string
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface UnderutilizedReservedInstance {
  reservation_id: string
  instance_type: string
  instance_count: number
  utilization_percentage: number
  wasted_monthly_cost: number
  expiration_date: string
  region: string
  recommendation: string
}

export interface SavingsPlansCoverageResults {
  uncovered_ec2_instances: UncoveredEC2Instance[]
  uncovered_rds_instances: UncoveredRDSInstance[]
  underutilized_ris: UnderutilizedReservedInstance[]
  total_ec2_savings_opportunity: number
  total_rds_savings_opportunity: number
  total_ri_waste: number
  total_potential_savings: number
  ec2_coverage_percentage: number
  rds_coverage_percentage: number
}

// VPC Endpoints Audit Types (Phase 6)
export interface VPCEndpointUnused {
  endpoint_id: string
  service_name: string
  endpoint_type: string
  vpc_id: string
  num_azs: number
  days_active: number
  avg_gb_per_day: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface VPCEndpointDuplicate {
  service_name: string
  vpc_id: string
  endpoint_ids: string[]
  duplicate_count: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  recommendation: string
}

export interface VPCEndpointAuditResults {
  unused_endpoints: VPCEndpointUnused[]
  duplicate_endpoints: VPCEndpointDuplicate[]
  total_unused_cost: number
  total_duplicate_waste: number
  total_potential_savings: number
}

// EFS Audit Types (Phase 6)
export interface EFSUnusedFileSystem {
  file_system_id: string
  file_system_name: string | null
  size_gb: number
  creation_time: string
  days_without_connections: number
  performance_mode: string
  throughput_mode: string
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface EFSWithoutLifecycle {
  file_system_id: string
  file_system_name: string | null
  size_gb: number
  standard_storage_gb: number
  performance_mode: string
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface EFSAuditResults {
  unused_file_systems: EFSUnusedFileSystem[]
  file_systems_without_lifecycle: EFSWithoutLifecycle[]
  total_unused_cost: number
  total_lifecycle_savings: number
  total_potential_savings: number
}

// EBS Snapshot Optimization Types (Phase 6)
export interface EBSOrphanedSnapshot {
  snapshot_id: string
  volume_id: string | null
  size_gb: number
  created_time: string
  days_old: number
  ami_id: string | null
  ami_deleted: boolean
  estimated_monthly_cost: number
  region: string
  description: string | null
  tags: Record<string, string>
  recommendation: string
}

export interface EBSDuplicateSnapshot {
  volume_id: string
  snapshot_ids: string[]
  duplicate_count: number
  size_gb: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  recommendation: string
}

export interface EBSSnapshotAuditResults {
  orphaned_snapshots: EBSOrphanedSnapshot[]
  duplicate_snapshots: EBSDuplicateSnapshot[]
  total_orphaned_cost: number
  total_duplicate_waste: number
  total_potential_savings: number
}

// Data Transfer Analysis Types (Phase 6)
export interface DataTransferHighCost {
  service: string
  transfer_type: string
  source_region: string
  dest_region: string | null
  monthly_gb: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  recommendation: string
}

export interface DataTransferAuditResults {
  high_cost_transfers: DataTransferHighCost[]
  total_transfer_cost: number
  total_potential_savings: number
}

// Elastic Beanstalk Audit Types (Phase 6)
export interface ElasticBeanstalkUnusedEnvironment {
  environment_name: string
  environment_id: string
  application_name: string
  status: string
  health: string
  days_since_deployment: number
  request_count_per_day: number
  estimated_monthly_cost: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface ElasticBeanstalkNonProdRunning {
  environment_name: string
  environment_id: string
  application_name: string
  tier: string
  environment_type: string
  instance_count: number
  estimated_monthly_cost: number
  potential_monthly_savings: number
  region: string
  tags: Record<string, string>
  recommendation: string
}

export interface ElasticBeanstalkAuditResults {
  unused_environments: ElasticBeanstalkUnusedEnvironment[]
  nonprod_running_24_7: ElasticBeanstalkNonProdRunning[]
  total_unused_cost: number
  total_nonprod_waste: number
  total_potential_savings: number
}

// Phase 7 Audit Types - CloudFront
export interface CloudFrontUnusedDistribution {
  distribution_id: string
  domain_name: string
  enabled: boolean
  total_requests: number
  days_checked: number
  estimated_monthly_cost: number
  recommendation: string
}

export interface CloudFrontNoLogging {
  distribution_id: string
  domain_name: string
  enabled: boolean
  logging_enabled: boolean
  recommendation: string
}

export interface CloudFrontAuditResults {
  unused_distributions: CloudFrontUnusedDistribution[]
  distributions_without_logging: CloudFrontNoLogging[]
  total_unused_cost: number
}

// Phase 7 Audit Types - Route53
export interface Route53UnusedHostedZone {
  hosted_zone_id: string
  hosted_zone_name: string
  is_private: boolean
  total_records: number
  user_records: number
  estimated_monthly_cost: number
  recommendation: string
}

export interface Route53AuditResults {
  unused_hosted_zones: Route53UnusedHostedZone[]
  total_potential_savings: number
}

// Phase 7 Audit Types - SQS
export interface SQSUnusedQueue {
  queue_name: string
  queue_url: string
  region: string
  is_fifo: boolean
  messages_available: number
  total_sent_period: number
  days_checked: number
  retention_period_seconds: number
  recommendation: string
}

export interface SQSHighRetentionQueue {
  queue_name: string
  queue_url: string
  region: string
  retention_period_days: number
  retention_period_seconds: number
  max_retention_days: number
  recommendation: string
}

export interface SQSAuditResults {
  unused_queues: SQSUnusedQueue[]
  high_retention_queues: SQSHighRetentionQueue[]
}

// Phase 7 Audit Types - SNS
export interface SNSUnusedTopic {
  topic_name: string
  topic_arn: string
  region: string
  subscriptions_confirmed: number
  subscriptions_pending: number
  messages_published: number
  days_checked: number
  recommendation: string
}

export interface SNSAuditResults {
  unused_topics: SNSUnusedTopic[]
}

// Phase 7 Audit Types - API Gateway
export interface APIGatewayUnusedAPI {
  api_id: string
  api_name: string
  stage: string
  region: string
  total_requests: number
  days_checked: number
  created_date?: string
  recommendation: string
}

export interface APIGatewayNoCaching {
  api_id: string
  api_name: string
  stage: string
  region: string
  cache_enabled: boolean
  avg_daily_requests: number
  potential_cost_savings: number
  recommendation: string
}

export interface APIGatewayAuditResults {
  unused_apis: APIGatewayUnusedAPI[]
  apis_without_caching: APIGatewayNoCaching[]
  total_potential_savings: number
}

// Phase 7 Audit Types - Step Functions
export interface StepFunctionsUnusedStateMachine {
  state_machine_name: string
  state_machine_arn: string
  type: string
  region: string
  total_executions?: number
  days_since_last_execution?: number
  last_execution_date?: string
  created_date?: string
  recommendation: string
}

export interface StepFunctionsAuditResults {
  unused_state_machines: StepFunctionsUnusedStateMachine[]
}

// Phase 7 Audit Types - ECS
export interface ECSOversizedTask {
  cluster_name: string
  service_name: string
  region: string
  launch_type: string
  task_cpu: string
  task_memory: string
  avg_cpu_utilization: number
  avg_memory_utilization: number
  desired_count: number
  recommendation: string
}

export interface ECSAuditResults {
  oversized_tasks: ECSOversizedTask[]
}

// Phase 7 Audit Types - Redshift
export interface RedshiftIdleCluster {
  cluster_identifier: string
  region: string
  cluster_status: string
  node_type: string
  number_of_nodes: number
  avg_database_connections: number
  days_checked: number
  estimated_monthly_cost: number
  recommendation: string
}

export interface RedshiftAuditResults {
  idle_clusters: RedshiftIdleCluster[]
  total_potential_savings: number
}

// Phase 7 Audit Types - Kinesis
export interface KinesisUnusedStream {
  stream_name: string
  region: string
  stream_status: string
  shard_count: number
  incoming_records: number
  days_checked: number
  estimated_monthly_cost: number
  recommendation: string
}

export interface KinesisAuditResults {
  unused_streams: KinesisUnusedStream[]
  total_potential_savings: number
}

// Phase 7 Audit Types - Glue
export interface GlueUnusedCrawler {
  crawler_name: string
  region: string
  crawler_state: string
  last_crawl_status: string
  days_since_last_crawl?: number
  last_crawl_date?: string
  recommendation: string
}

export interface GlueUnusedJob {
  job_name: string
  region: string
  worker_type?: string
  number_of_workers?: number
  max_capacity?: number
  last_run_status: string
  days_since_last_run?: number
  last_run_date?: string
  recommendation: string
}

export interface GlueAuditResults {
  unused_crawlers: GlueUnusedCrawler[]
  unused_jobs: GlueUnusedJob[]
}

export interface AuditSummary {
  total_findings: number
  total_potential_savings: number
  findings_by_category: Record<string, number>
  findings_by_severity: Record<string, number>
  top_opportunities: string[]
}

export interface FullAuditResults {
  account_name: string
  audit_timestamp: string
  ec2_audit: EC2AuditResults
  ebs_audit: EBSAuditResults
  eip_audit: ElasticIPAuditResults
  tagging_audit: TaggingAuditResults
  rds_audit?: RDSAuditResults
  lambda_audit?: LambdaAuditResults
  s3_audit?: S3AuditResults
  lb_audit?: LoadBalancerAuditResults
  nat_gateway_audit?: NATGatewayAuditResults
  elasticache_audit?: ElastiCacheAuditResults
  cloudwatch_logs_audit?: CloudWatchLogsAuditResults
  dynamodb_audit?: DynamoDBAuditResults
  savings_plans_audit?: SavingsPlansCoverageResults
  // Phase 6 audits
  vpc_endpoint_audit?: VPCEndpointAuditResults
  efs_audit?: EFSAuditResults
  ebs_snapshot_audit?: EBSSnapshotAuditResults
  data_transfer_audit?: DataTransferAuditResults
  beanstalk_audit?: ElasticBeanstalkAuditResults
  // Phase 7 audits
  cloudfront_audit?: CloudFrontAuditResults
  route53_audit?: Route53AuditResults
  sqs_audit?: SQSAuditResults
  sns_audit?: SNSAuditResults
  apigateway_audit?: APIGatewayAuditResults
  stepfunctions_audit?: StepFunctionsAuditResults
  ecs_audit?: ECSAuditResults
  redshift_audit?: RedshiftAuditResults
  kinesis_audit?: KinesisAuditResults
  glue_audit?: GlueAuditResults
  summary: AuditSummary
}

export interface AuditRequest {
  account_name: string
  audit_types?: string[]
  regions?: string[]
  cpu_threshold?: number
  days_stopped_threshold?: number
  days_unattached_threshold?: number
  snapshot_age_threshold?: number
  required_tags?: string[]
}
