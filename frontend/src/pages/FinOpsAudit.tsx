import { useState, useMemo, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProfileStore } from '@/store/profileStore'
import { useMutation, useQuery } from '@tanstack/react-query'
import { finopsApi } from '@/api/finops'
import { teamsApi } from '@/api/teams'
import { awsAccountsApi } from '@/api/awsAccounts'
import { exportApi } from '@/api/export'
import { usePagination } from '@/hooks/usePagination'
import { useAuditPolling } from '@/hooks/useAuditPolling'
import { Pagination } from '@/components/common/Pagination'
import { AuditProgressBar } from '@/components/audit/AuditProgressBar'
import {
  Search,
  AlertCircle,
  TrendingDown,
  DollarSign,
  Cloud,
  Server,
  HardDrive,
  Network,
  Tag,
  Play,
  Loader2,
  Filter,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  X,
  Database,
  Zap,
  FolderOpen,
  Activity,
  Globe,
  MemoryStick,
  FileText,
  Table,
  TrendingUp,
  Layers,
  Camera,
  Send,
  Download,
  FileSpreadsheet,
  Upload,
  Info,
} from 'lucide-react'
import type {
  FullAuditResults,
  EC2IdleInstance,
  EBSUnattachedVolume,
  ElasticIPUnattached,
  UntaggedResource,
  RDSIdleInstance,
  LambdaUnusedFunction,
  LambdaOverProvisionedFunction,
  S3BucketWithoutLifecycle,
  LoadBalancerNoTargets,
  NATGatewayIdle,
  NATGatewayUnused,
  ElastiCacheIdleCluster,
  CloudWatchLogGroupLongRetention,
  CloudWatchLogGroupUnused,
  DynamoDBUnusedTable,
  DynamoDBBillingModeOptimization,
  UncoveredEC2Instance,
  // Phase 6 types
  VPCEndpointUnused,
  VPCEndpointDuplicate,
  EFSUnusedFileSystem,
  EFSWithoutLifecycle,
  EBSOrphanedSnapshot,
  EBSDuplicateSnapshot,
  DataTransferHighCost,
  ElasticBeanstalkUnusedEnvironment,
  ElasticBeanstalkNonProdRunning,
  // Phase 7 types
  CloudFrontUnusedDistribution,
  CloudFrontNoLogging,
  Route53UnusedHostedZone,
  SQSUnusedQueue,
  SQSHighRetentionQueue,
  SNSUnusedTopic,
  APIGatewayUnusedAPI,
  APIGatewayNoCaching,
  StepFunctionsUnusedStateMachine,
  ECSOversizedTask,
  RedshiftIdleCluster,
  KinesisUnusedStream,
  GlueUnusedCrawler,
  GlueUnusedJob,
} from '@/types/audit'

type SortField = 'cpu' | 'cost' | 'days' | 'size' | 'connections' | 'memory'
type SortDirection = 'asc' | 'desc' | null

export function FinOpsAudit() {
  const navigate = useNavigate()
  const { selectedProfile } = useProfileStore()
  const [auditResults, setAuditResults] = useState<FullAuditResults | null>(null)

  // Initialize currentJobId from localStorage to persist across navigation
  const [currentJobId, setCurrentJobId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(`audit_job_id_${selectedProfile}`)
    } catch (e) {
      return null
    }
  })

  const [isLoadingCache, setIsLoadingCache] = useState(true)

  // Check if AWS accounts are configured
  const { data: awsAccounts, isLoading: loadingAccounts } = useQuery({
    queryKey: ['awsAccounts'],
    queryFn: () => awsAccountsApi.list(),
    retry: 1
  })

  const hasAccounts = awsAccounts && awsAccounts.length > 0

  // Filter states
  const [selectedResourceTypes, setSelectedResourceTypes] = useState<string[]>([])
  const [selectedRegions, setSelectedRegions] = useState<string[]>([])

  // Sort states
  const [ec2SortField, setEc2SortField] = useState<SortField | null>(null)
  const [ec2SortDirection, setEc2SortDirection] = useState<SortDirection>(null)
  const [ebsSortField, setEbsSortField] = useState<SortField | null>(null)
  const [ebsSortDirection, setEbsSortDirection] = useState<SortDirection>(null)
  const [rdsSortField, setRdsSortField] = useState<SortField | null>(null)
  const [rdsSortDirection, setRdsSortDirection] = useState<SortDirection>(null)

  // Teams integration states
  const [showTeamsModal, setShowTeamsModal] = useState(false)
  const [selectedWebhookId, setSelectedWebhookId] = useState<number | null>(null)


  // Async audit polling
  const handleAuditComplete = useCallback((results: FullAuditResults) => {
    setAuditResults(results)
    // Reset filters when new audit completes
    setSelectedResourceTypes([])
    setSelectedRegions([])
    // Cache results
    try {
      localStorage.setItem(`audit_results_${selectedProfile}`, JSON.stringify(results))
      localStorage.setItem(`audit_timestamp_${selectedProfile}`, new Date().toISOString())
      // Keep job ID so user can send results to Teams after audit completes
      // Job ID will be cleared when new audit starts or user clears results
    } catch (e) {
      console.error('Failed to cache results:', e)
    }
  }, [selectedProfile])

  // Handle audit errors
  const handleAuditError = useCallback((error: string) => {
    console.error('Audit error:', error)
    // Clear job ID on error
    try {
      localStorage.removeItem(`audit_job_id_${selectedProfile}`)
      setCurrentJobId(null)
    } catch (e) {
      console.error('Failed to clear job ID:', e)
    }
  }, [selectedProfile])

  // Handle progress updates with partial results
  const handleAuditProgress = useCallback((status: any) => {
    console.log('Progress update:', status.progress, '%', status.current_step)
    // If we have partial results or final results in the status, show them
    if (status.results) {
      setAuditResults(status.results)
    } else if (status.partial_results) {
      // Convert partial results to FullAuditResults format
      setAuditResults(status.partial_results as FullAuditResults)
    }
  }, [])

  const { status: jobStatus, isPolling, error: pollingError } = useAuditPolling({
    jobId: currentJobId,
    onComplete: handleAuditComplete,
    onError: handleAuditError,
    onProgress: handleAuditProgress,
  })

  // Start async audit mutation
  const { mutate: startAsyncAudit, isPending: isStarting } = useMutation({
    mutationFn: () =>
      finopsApi.startAsyncAudit({
        account_name: selectedProfile,
        audit_types: [
          'ec2', 'ebs', 'eip', 'tagging',
          'rds', 'lambda', 's3', 'lb',
          'nat_gateway', 'elasticache', 'cloudwatch_logs', 'dynamodb', 'savings_plans',
          // Phase 6 audit types
          'vpc_endpoint', 'efs', 'ebs_snapshot', 'data_transfer', 'beanstalk',
          // Phase 7 audit types
          'cloudfront', 'route53', 'sqs', 'sns', 'apigateway', 'stepfunctions', 'ecs', 'redshift', 'kinesis', 'glue'
        ],
      }),
    onSuccess: (response) => {
      setCurrentJobId(response.job_id)
      // Save job ID to localStorage so audit continues across page navigations
      try {
        localStorage.setItem(`audit_job_id_${selectedProfile}`, response.job_id)
      } catch (e) {
        console.error('Failed to save job ID:', e)
      }
      // Clear previous results
      setAuditResults(null)
      setSelectedResourceTypes([])
      setSelectedRegions([])
    },
  })

  // Fetch Teams webhooks
  const { data: webhooks } = useQuery({
    queryKey: ['teams-webhooks'],
    queryFn: () => teamsApi.listWebhooks()
  })

  // Send to Teams mutation
  const sendToTeamsMutation = useMutation({
    mutationFn: (webhookId?: number) => {
      // Prefer sending cached audit results directly to avoid job ID lookup issues
      if (auditResults) {
        return finopsApi.sendAuditToTeams({
          auditResults,
          webhookId,
        })
      }
      // Fall back to job ID if audit results not available
      if (currentJobId) {
        return finopsApi.sendAuditToTeams({
          jobId: currentJobId,
          webhookId,
        })
      }
      throw new Error('No audit results or job ID available')
    },
    onSuccess: (result) => {
      const message = result.errors.length > 0
        ? `✅ Sent to ${result.notifications_sent} webhook(s). ${result.errors.length} error(s) occurred.`
        : `✅ Audit report sent to ${result.notifications_sent} webhook(s)! Total findings: ${result.total_findings}, Potential savings: $${result.total_savings.toFixed(2)}/month`
      alert(message)
      setShowTeamsModal(false)
      setSelectedWebhookId(null)
    },
    onError: (error: any) => {
      alert(`❌ Failed to send to Teams: ${error.response?.data?.detail || error.message || 'Unknown error'}`)
    }
  })

  // PDF Export mutation
  const exportPDFMutation = useMutation({
    mutationFn: async () => {
      // Read S3 configuration from Settings
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      const s3Bucket = localStorage.getItem('s3ExportBucket') || ''

      const options = {
        auditResults: auditResults || undefined,
        jobId: !auditResults ? currentJobId || undefined : undefined,
        uploadToS3: uploadToS3,
        s3Bucket: uploadToS3 ? s3Bucket : undefined
      }

      if (!auditResults && !currentJobId) {
        throw new Error('No audit results available for export')
      }

      return exportApi.exportAuditPDF(options)
    },
    onSuccess: (data: any) => {
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      if (uploadToS3) {
        // S3 upload returns JSON response with S3 details
        const response = data as { success: boolean; message: string; s3_url?: string; file_name?: string }
        if (response.s3_url) {
          alert(`✅ ${response.message}\n\nS3 URL: ${response.s3_url}\nFile: ${response.file_name}`)
        } else {
          alert(`✅ ${response.message}`)
        }
      } else {
        // Download returns blob
        const blob = data as Blob
        const fileName = exportApi.generateFileName(selectedProfile, 'pdf')
        exportApi.downloadBlob(blob, fileName)
        alert(`✅ PDF report downloaded: ${fileName}`)
      }
    },
    onError: (error: any) => {
      alert(`❌ Failed to export PDF: ${error.response?.data?.detail || error.message || 'Unknown error'}`)
    }
  })

  // Excel Export mutation
  const exportExcelMutation = useMutation({
    mutationFn: async () => {
      // Read S3 configuration from Settings
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      const s3Bucket = localStorage.getItem('s3ExportBucket') || ''

      const options = {
        auditResults: auditResults || undefined,
        jobId: !auditResults ? currentJobId || undefined : undefined,
        uploadToS3: uploadToS3,
        s3Bucket: uploadToS3 ? s3Bucket : undefined
      }

      if (!auditResults && !currentJobId) {
        throw new Error('No audit results available for export')
      }

      return exportApi.exportAuditExcel(options)
    },
    onSuccess: (data: any) => {
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      if (uploadToS3) {
        // S3 upload returns JSON response with S3 details
        const response = data as { success: boolean; message: string; s3_url?: string; file_name?: string }
        if (response.s3_url) {
          alert(`✅ ${response.message}\n\nS3 URL: ${response.s3_url}\nFile: ${response.file_name}`)
        } else {
          alert(`✅ ${response.message}`)
        }
      } else {
        // Download returns blob
        const blob = data as Blob
        const fileName = exportApi.generateFileName(selectedProfile, 'xlsx')
        exportApi.downloadBlob(blob, fileName)
        alert(`✅ Excel report downloaded: ${fileName}`)
      }
    },
    onError: (error: any) => {
      alert(`❌ Failed to export Excel: ${error.response?.data?.detail || error.message || 'Unknown error'}`)
    }
  })

  // Check for cached results on mount
  const loadCachedResults = useCallback(() => {
    setIsLoadingCache(true)
    try {
      const cached = localStorage.getItem(`audit_results_${selectedProfile}`)
      const timestamp = localStorage.getItem(`audit_timestamp_${selectedProfile}`)
      if (cached && timestamp) {
        const results = JSON.parse(cached)
        const age = Date.now() - new Date(timestamp).getTime()
        // Use cached if less than 30 minutes old
        if (age < 30 * 60 * 1000) {
          setAuditResults(results)
        }
      }
    } catch (e) {
      console.error('Failed to load cached results:', e)
    } finally {
      setIsLoadingCache(false)
    }
  }, [selectedProfile])

  // Load cached results and resume job when profile changes
  useEffect(() => {
    loadCachedResults()
    // Load job ID from localStorage for current profile
    try {
      const storedJobId = localStorage.getItem(`audit_job_id_${selectedProfile}`)
      if (storedJobId && storedJobId !== currentJobId) {
        setCurrentJobId(storedJobId)
        console.log('Resuming audit job:', storedJobId)
      }
    } catch (e) {
      console.error('Failed to load job ID:', e)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile])

  // Auto-trigger audit on page load if no recent cached results
  useEffect(() => {
    if (!hasAccounts || loadingAccounts) return
    if (isPolling || isStarting || currentJobId) return // Don't start if already running

    // Check if we need to run a fresh audit
    const shouldRunAudit = () => {
      try {
        const cached = localStorage.getItem(`audit_results_${selectedProfile}`)
        const timestamp = localStorage.getItem(`audit_timestamp_${selectedProfile}`)

        if (!cached || !timestamp) return true // No cache, run audit

        const age = Date.now() - new Date(timestamp).getTime()
        return age >= 30 * 60 * 1000 // Cache older than 30 min, run audit
      } catch (e) {
        return true // Error reading cache, run audit
      }
    }

    if (shouldRunAudit()) {
      console.log('Auto-starting FinOps audit on page load...')
      startAsyncAudit()
    }
  }, [hasAccounts, loadingAccounts, selectedProfile, isPolling, isStarting, currentJobId, startAsyncAudit])

  // Get all resource types - 28 audit types matching backend
  const resourceTypes = useMemo(() => {
    return [
      'EC2',
      'EBS',
      'Elastic IP',
      'Tagging',
      'RDS',
      'Lambda',
      'S3',
      'Load Balancer',
      'NAT Gateway',
      'ElastiCache',
      'CloudWatch Logs',
      'DynamoDB',
      'Savings Plans',
      'VPC Endpoint',
      'EFS',
      'EBS Snapshot',
      'Data Transfer',
      'Elastic Beanstalk',
      // Phase 7 types
      'CloudFront',
      'Route53',
      'SQS',
      'SNS',
      'API Gateway',
      'Step Functions',
      'ECS',
      'Redshift',
      'Kinesis',
      'Glue',
    ]
  }, [])

  const regions = useMemo(() => {
    if (!auditResults) return []
    const regionSet = new Set<string>()
    auditResults.ec2_audit?.idle_instances?.forEach((i) => regionSet.add(i.region))
    auditResults.ec2_audit?.stopped_instances?.forEach((i) => regionSet.add(i.region))
    auditResults.ebs_audit?.unattached_volumes?.forEach((v) => regionSet.add(v.region))
    auditResults.eip_audit?.unattached_ips?.forEach((e) => regionSet.add(e.region))
    auditResults.tagging_audit?.untagged_resources?.forEach((r) => regionSet.add(r.region))
    auditResults.rds_audit?.idle_instances.forEach((i) => regionSet.add(i.region))
    auditResults.rds_audit?.stopped_instances.forEach((i) => regionSet.add(i.region))
    auditResults.lambda_audit?.unused_functions.forEach((f) => regionSet.add(f.region))
    auditResults.lambda_audit?.over_provisioned_functions.forEach((f) => regionSet.add(f.region))
    auditResults.s3_audit?.buckets_without_lifecycle.forEach((b) => regionSet.add(b.region))
    auditResults.lb_audit?.lbs_no_targets.forEach((lb) => regionSet.add(lb.region))
    auditResults.lb_audit?.lbs_low_traffic.forEach((lb) => regionSet.add(lb.region))
    auditResults.nat_gateway_audit?.idle_gateways.forEach((ng: NATGatewayIdle) => regionSet.add(ng.region))
    auditResults.nat_gateway_audit?.unused_gateways.forEach((ng: NATGatewayUnused) => regionSet.add(ng.region))
    auditResults.elasticache_audit?.idle_clusters.forEach((ec: ElastiCacheIdleCluster) => regionSet.add(ec.region))
    auditResults.cloudwatch_logs_audit?.long_retention_groups.forEach((lg: CloudWatchLogGroupLongRetention) => regionSet.add(lg.region))
    auditResults.cloudwatch_logs_audit?.unused_groups.forEach((lg: CloudWatchLogGroupUnused) => regionSet.add(lg.region))
    auditResults.dynamodb_audit?.unused_tables.forEach((dt: DynamoDBUnusedTable) => regionSet.add(dt.region))
    auditResults.dynamodb_audit?.billing_mode_opportunities.forEach((dt: DynamoDBBillingModeOptimization) => regionSet.add(dt.region))
    auditResults.savings_plans_audit?.uncovered_ec2_instances.forEach((sp: UncoveredEC2Instance) => regionSet.add(sp.region))
    // Phase 6 regions
    auditResults.vpc_endpoint_audit?.unused_endpoints.forEach((vp: VPCEndpointUnused) => regionSet.add(vp.region))
    auditResults.vpc_endpoint_audit?.duplicate_endpoints.forEach((vp: VPCEndpointDuplicate) => regionSet.add(vp.region))
    auditResults.efs_audit?.unused_file_systems.forEach((efs: EFSUnusedFileSystem) => regionSet.add(efs.region))
    auditResults.efs_audit?.file_systems_without_lifecycle.forEach((efs: EFSWithoutLifecycle) => regionSet.add(efs.region))
    auditResults.ebs_snapshot_audit?.orphaned_snapshots.forEach((snap: EBSOrphanedSnapshot) => regionSet.add(snap.region))
    auditResults.ebs_snapshot_audit?.duplicate_snapshots.forEach((snap: EBSDuplicateSnapshot) => regionSet.add(snap.region))
    auditResults.data_transfer_audit?.high_cost_transfers.forEach((dt: DataTransferHighCost) => regionSet.add(dt.source_region))
    auditResults.beanstalk_audit?.unused_environments.forEach((eb: ElasticBeanstalkUnusedEnvironment) => regionSet.add(eb.region))
    auditResults.beanstalk_audit?.nonprod_running_24_7.forEach((eb: ElasticBeanstalkNonProdRunning) => regionSet.add(eb.region))
    // Phase 7 regions
    auditResults.sqs_audit?.unused_queues.forEach((q: SQSUnusedQueue) => regionSet.add(q.region))
    auditResults.sqs_audit?.high_retention_queues.forEach((q: SQSHighRetentionQueue) => regionSet.add(q.region))
    auditResults.sns_audit?.unused_topics.forEach((t: SNSUnusedTopic) => regionSet.add(t.region))
    auditResults.apigateway_audit?.unused_apis.forEach((api: APIGatewayUnusedAPI) => regionSet.add(api.region))
    auditResults.apigateway_audit?.apis_without_caching.forEach((api: APIGatewayNoCaching) => regionSet.add(api.region))
    auditResults.stepfunctions_audit?.unused_state_machines.forEach((sm: StepFunctionsUnusedStateMachine) => regionSet.add(sm.region))
    auditResults.ecs_audit?.oversized_tasks.forEach((task: ECSOversizedTask) => regionSet.add(task.region))
    auditResults.redshift_audit?.idle_clusters.forEach((cluster: RedshiftIdleCluster) => regionSet.add(cluster.region))
    auditResults.kinesis_audit?.unused_streams.forEach((stream: KinesisUnusedStream) => regionSet.add(stream.region))
    auditResults.glue_audit?.unused_crawlers.forEach((crawler: GlueUnusedCrawler) => regionSet.add(crawler.region))
    auditResults.glue_audit?.unused_jobs.forEach((job: GlueUnusedJob) => regionSet.add(job.region))
    return Array.from(regionSet).sort()
  }, [auditResults])

  // Filter and sort EC2 idle instances
  const filteredSortedEC2Instances = useMemo(() => {
    if (!auditResults?.ec2_audit?.idle_instances) return []
    let filtered = auditResults.ec2_audit.idle_instances

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('EC2')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((i) => selectedRegions.includes(i.region))
    }

    if (ec2SortField && ec2SortDirection) {
      filtered = [...filtered].sort((a, b) => {
        let comparison = 0
        if (ec2SortField === 'cpu') {
          comparison = a.avg_cpu_utilization - b.avg_cpu_utilization
        } else if (ec2SortField === 'cost') {
          comparison = a.estimated_monthly_cost - b.estimated_monthly_cost
        }
        return ec2SortDirection === 'asc' ? comparison : -comparison
      })
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions, ec2SortField, ec2SortDirection])

  // Filter and sort EBS volumes
  const filteredSortedEBSVolumes = useMemo(() => {
    if (!auditResults?.ebs_audit?.unattached_volumes) return []
    let filtered = auditResults.ebs_audit.unattached_volumes

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('EBS')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((v) => selectedRegions.includes(v.region))
    }

    if (ebsSortField && ebsSortDirection) {
      filtered = [...filtered].sort((a, b) => {
        let comparison = 0
        if (ebsSortField === 'size') {
          comparison = a.size_gb - b.size_gb
        } else if (ebsSortField === 'days') {
          comparison = a.days_unattached - b.days_unattached
        } else if (ebsSortField === 'cost') {
          comparison = a.estimated_monthly_cost - b.estimated_monthly_cost
        }
        return ebsSortDirection === 'asc' ? comparison : -comparison
      })
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions, ebsSortField, ebsSortDirection])

  // Filter EIPs
  const filteredEIPs = useMemo(() => {
    if (!auditResults?.eip_audit?.unattached_ips) return []
    let filtered = auditResults.eip_audit.unattached_ips

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Elastic IP')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((e) => selectedRegions.includes(e.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter untagged resources
  const filteredUntagged = useMemo(() => {
    if (!auditResults?.tagging_audit?.untagged_resources) return []
    let filtered = auditResults.tagging_audit.untagged_resources

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Tagging')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((r) => selectedRegions.includes(r.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter and sort RDS idle instances
  const filteredSortedRDSInstances = useMemo(() => {
    if (!auditResults?.rds_audit?.idle_instances) return []
    let filtered = auditResults.rds_audit.idle_instances

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('RDS')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((i) => selectedRegions.includes(i.region))
    }

    if (rdsSortField && rdsSortDirection) {
      filtered = [...filtered].sort((a, b) => {
        let comparison = 0
        if (rdsSortField === 'cpu') {
          comparison = a.avg_cpu_utilization - b.avg_cpu_utilization
        } else if (rdsSortField === 'connections') {
          comparison = a.avg_connections - b.avg_connections
        } else if (rdsSortField === 'cost') {
          comparison = a.estimated_monthly_cost - b.estimated_monthly_cost
        }
        return rdsSortDirection === 'asc' ? comparison : -comparison
      })
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions, rdsSortField, rdsSortDirection])

  // Filter Lambda unused functions
  const filteredLambdaUnused = useMemo(() => {
    if (!auditResults?.lambda_audit?.unused_functions) return []
    let filtered = auditResults.lambda_audit.unused_functions

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Lambda')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((f) => selectedRegions.includes(f.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter Lambda over-provisioned functions
  const filteredLambdaOverProvisioned = useMemo(() => {
    if (!auditResults?.lambda_audit?.over_provisioned_functions) return []
    let filtered = auditResults.lambda_audit.over_provisioned_functions

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Lambda')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((f) => selectedRegions.includes(f.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter S3 buckets without lifecycle
  const filteredS3NoLifecycle = useMemo(() => {
    if (!auditResults?.s3_audit?.buckets_without_lifecycle) return []
    let filtered = auditResults.s3_audit.buckets_without_lifecycle

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('S3')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((b) => selectedRegions.includes(b.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter LBs with no targets
  const filteredLBNoTargets = useMemo(() => {
    if (!auditResults?.lb_audit?.lbs_no_targets) return []
    let filtered = auditResults.lb_audit.lbs_no_targets

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Load Balancer')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((lb) => selectedRegions.includes(lb.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter NAT Gateway idle
  const filteredNATGatewayIdle = useMemo(() => {
    if (!auditResults?.nat_gateway_audit?.idle_gateways) return []
    let filtered = auditResults.nat_gateway_audit.idle_gateways

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('NAT Gateway')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((ng: NATGatewayIdle) => selectedRegions.includes(ng.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter NAT Gateway unused
  const filteredNATGatewayUnused = useMemo(() => {
    if (!auditResults?.nat_gateway_audit?.idle_gateways) return []
    let filtered = auditResults.nat_gateway_audit.unused_gateways

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('NAT Gateway')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((ng: NATGatewayUnused) => selectedRegions.includes(ng.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter ElastiCache idle
  const filteredElastiCacheIdle = useMemo(() => {
    if (!auditResults?.elasticache_audit?.idle_clusters) return []
    let filtered = auditResults.elasticache_audit.idle_clusters

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('ElastiCache')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((ec: ElastiCacheIdleCluster) => selectedRegions.includes(ec.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter CloudWatch Logs long retention
  const filteredCWLogsLongRetention = useMemo(() => {
    if (!auditResults?.cloudwatch_logs_audit?.long_retention_groups) return []
    let filtered = auditResults.cloudwatch_logs_audit.long_retention_groups

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('CloudWatch Logs')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((lg: CloudWatchLogGroupLongRetention) => selectedRegions.includes(lg.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter CloudWatch Logs unused
  const filteredCWLogsUnused = useMemo(() => {
    if (!auditResults?.cloudwatch_logs_audit?.long_retention_groups) return []
    let filtered = auditResults.cloudwatch_logs_audit.unused_groups

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('CloudWatch Logs')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((lg: CloudWatchLogGroupUnused) => selectedRegions.includes(lg.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter DynamoDB unused
  const filteredDynamoDBUnused = useMemo(() => {
    if (!auditResults?.dynamodb_audit?.unused_tables) return []
    let filtered = auditResults.dynamodb_audit.unused_tables

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('DynamoDB')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((dt: DynamoDBUnusedTable) => selectedRegions.includes(dt.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter DynamoDB billing mode
  const filteredDynamoDBBilling = useMemo(() => {
    if (!auditResults?.dynamodb_audit?.unused_tables) return []
    let filtered = auditResults.dynamodb_audit.billing_mode_opportunities

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('DynamoDB')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((dt: DynamoDBBillingModeOptimization) => selectedRegions.includes(dt.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Filter Uncovered EC2
  const filteredUncoveredEC2 = useMemo(() => {
    if (!auditResults?.savings_plans_audit?.uncovered_ec2_instances) return []
    let filtered = auditResults.savings_plans_audit.uncovered_ec2_instances

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Savings Plans')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((sp: UncoveredEC2Instance) => selectedRegions.includes(sp.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 6: VPC Endpoint filtering
  const filteredVPCEndpointUnused = useMemo(() => {
    if (!auditResults?.vpc_endpoint_audit?.unused_endpoints) return []
    let filtered = auditResults.vpc_endpoint_audit.unused_endpoints

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('VPC Endpoint')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((vp: VPCEndpointUnused) => selectedRegions.includes(vp.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  const filteredVPCEndpointDuplicate = useMemo(() => {
    if (!auditResults?.vpc_endpoint_audit?.unused_endpoints) return []
    let filtered = auditResults.vpc_endpoint_audit.duplicate_endpoints

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('VPC Endpoint')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((vp: VPCEndpointDuplicate) => selectedRegions.includes(vp.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 6: EFS filtering
  const filteredEFSUnused = useMemo(() => {
    if (!auditResults?.efs_audit?.unused_file_systems) return []
    let filtered = auditResults.efs_audit.unused_file_systems

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('EFS')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((efs: EFSUnusedFileSystem) => selectedRegions.includes(efs.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  const filteredEFSNoLifecycle = useMemo(() => {
    if (!auditResults?.efs_audit?.unused_file_systems) return []
    let filtered = auditResults.efs_audit.file_systems_without_lifecycle

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('EFS')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((efs: EFSWithoutLifecycle) => selectedRegions.includes(efs.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 6: EBS Snapshot filtering
  const filteredEBSOrphanedSnapshots = useMemo(() => {
    if (!auditResults?.ebs_snapshot_audit?.orphaned_snapshots) return []
    let filtered = auditResults.ebs_snapshot_audit.orphaned_snapshots

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('EBS Snapshot')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((snap: EBSOrphanedSnapshot) => selectedRegions.includes(snap.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  const filteredEBSDuplicateSnapshots = useMemo(() => {
    if (!auditResults?.ebs_snapshot_audit?.orphaned_snapshots) return []
    let filtered = auditResults.ebs_snapshot_audit.duplicate_snapshots

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('EBS Snapshot')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((snap: EBSDuplicateSnapshot) => selectedRegions.includes(snap.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 6: Data Transfer filtering
  const filteredDataTransfer = useMemo(() => {
    if (!auditResults?.data_transfer_audit?.high_cost_transfers) return []
    let filtered = auditResults.data_transfer_audit.high_cost_transfers

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Data Transfer')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((dt: DataTransferHighCost) => selectedRegions.includes(dt.source_region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 6: Elastic Beanstalk filtering
  const filteredBeanstalkUnused = useMemo(() => {
    if (!auditResults?.beanstalk_audit?.unused_environments) return []
    let filtered = auditResults.beanstalk_audit.unused_environments

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Elastic Beanstalk')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((bs: ElasticBeanstalkUnusedEnvironment) => selectedRegions.includes(bs.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  const filteredBeanstalkNonProd = useMemo(() => {
    if (!auditResults?.beanstalk_audit?.unused_environments) return []
    let filtered = auditResults.beanstalk_audit.nonprod_running_24_7

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Elastic Beanstalk')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((bs: ElasticBeanstalkNonProdRunning) => selectedRegions.includes(bs.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: CloudFront filtering
  const filteredCloudFrontUnused = useMemo(() => {
    if (!auditResults?.cloudfront_audit?.unused_distributions) return []
    let filtered = auditResults.cloudfront_audit.unused_distributions

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('CloudFront')) {
      return []
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  const filteredCloudFrontNoLogging = useMemo(() => {
    if (!auditResults?.cloudfront_audit?.distributions_without_logging) return []
    let filtered = auditResults.cloudfront_audit.distributions_without_logging

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('CloudFront')) {
      return []
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: Route53 filtering
  const filteredRoute53Unused = useMemo(() => {
    if (!auditResults?.route53_audit?.unused_hosted_zones) return []
    let filtered = auditResults.route53_audit.unused_hosted_zones

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Route53')) {
      return []
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: SQS filtering
  const filteredSQSUnused = useMemo(() => {
    if (!auditResults?.sqs_audit?.unused_queues) return []
    let filtered = auditResults.sqs_audit.unused_queues

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('SQS')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((q) => selectedRegions.includes(q.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  const filteredSQSHighRetention = useMemo(() => {
    if (!auditResults?.sqs_audit?.high_retention_queues) return []
    let filtered = auditResults.sqs_audit.high_retention_queues

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('SQS')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((q) => selectedRegions.includes(q.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: SNS filtering
  const filteredSNSUnused = useMemo(() => {
    if (!auditResults?.sns_audit?.unused_topics) return []
    let filtered = auditResults.sns_audit.unused_topics

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('SNS')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((t) => selectedRegions.includes(t.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: API Gateway filtering
  const filteredAPIGatewayUnused = useMemo(() => {
    if (!auditResults?.apigateway_audit?.unused_apis) return []
    let filtered = auditResults.apigateway_audit.unused_apis

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('API Gateway')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((api) => selectedRegions.includes(api.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  const filteredAPIGatewayNoCaching = useMemo(() => {
    if (!auditResults?.apigateway_audit?.apis_without_caching) return []
    let filtered = auditResults.apigateway_audit.apis_without_caching

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('API Gateway')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((api) => selectedRegions.includes(api.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: Step Functions filtering
  const filteredStepFunctionsUnused = useMemo(() => {
    if (!auditResults?.stepfunctions_audit?.unused_state_machines) return []
    let filtered = auditResults.stepfunctions_audit.unused_state_machines

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Step Functions')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((sm) => selectedRegions.includes(sm.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: ECS filtering
  const filteredECSOversized = useMemo(() => {
    if (!auditResults?.ecs_audit?.oversized_tasks) return []
    let filtered = auditResults.ecs_audit.oversized_tasks

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('ECS')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((task) => selectedRegions.includes(task.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: Redshift filtering
  const filteredRedshiftIdle = useMemo(() => {
    if (!auditResults?.redshift_audit?.idle_clusters) return []
    let filtered = auditResults.redshift_audit.idle_clusters

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Redshift')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((cluster) => selectedRegions.includes(cluster.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: Kinesis filtering
  const filteredKinesisUnused = useMemo(() => {
    if (!auditResults?.kinesis_audit?.unused_streams) return []
    let filtered = auditResults.kinesis_audit.unused_streams

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Kinesis')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((stream) => selectedRegions.includes(stream.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Phase 7: Glue filtering
  const filteredGlueUnusedCrawlers = useMemo(() => {
    if (!auditResults?.glue_audit?.unused_crawlers) return []
    let filtered = auditResults.glue_audit.unused_crawlers

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Glue')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((crawler) => selectedRegions.includes(crawler.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  const filteredGlueUnusedJobs = useMemo(() => {
    if (!auditResults?.glue_audit?.unused_jobs) return []
    let filtered = auditResults.glue_audit.unused_jobs

    if (selectedResourceTypes.length > 0 && !selectedResourceTypes.includes('Glue')) {
      return []
    }

    if (selectedRegions.length > 0) {
      filtered = filtered.filter((job) => selectedRegions.includes(job.region))
    }

    return filtered
  }, [auditResults, selectedResourceTypes, selectedRegions])

  // Pagination hooks
  const ec2Pagination = usePagination<EC2IdleInstance>({ data: filteredSortedEC2Instances, initialItemsPerPage: 10 })
  const ebsPagination = usePagination<EBSUnattachedVolume>({ data: filteredSortedEBSVolumes, initialItemsPerPage: 10 })
  const eipPagination = usePagination<ElasticIPUnattached>({ data: filteredEIPs, initialItemsPerPage: 10 })
  const untaggedPagination = usePagination<UntaggedResource>({ data: filteredUntagged, initialItemsPerPage: 10 })
  const rdsPagination = usePagination<RDSIdleInstance>({ data: filteredSortedRDSInstances, initialItemsPerPage: 10 })
  const lambdaUnusedPagination = usePagination<LambdaUnusedFunction>({ data: filteredLambdaUnused, initialItemsPerPage: 10 })
  const lambdaOverProvisionedPagination = usePagination<LambdaOverProvisionedFunction>({ data: filteredLambdaOverProvisioned, initialItemsPerPage: 10 })
  const s3Pagination = usePagination<S3BucketWithoutLifecycle>({ data: filteredS3NoLifecycle, initialItemsPerPage: 10 })
  const lbPagination = usePagination<LoadBalancerNoTargets>({ data: filteredLBNoTargets, initialItemsPerPage: 10 })
  const natGatewayIdlePagination = usePagination<NATGatewayIdle>({ data: filteredNATGatewayIdle, initialItemsPerPage: 10 })
  const natGatewayUnusedPagination = usePagination<NATGatewayUnused>({ data: filteredNATGatewayUnused, initialItemsPerPage: 10 })
  const elasticacheIdlePagination = usePagination<ElastiCacheIdleCluster>({ data: filteredElastiCacheIdle, initialItemsPerPage: 10 })
  const cwLogsLongRetentionPagination = usePagination<CloudWatchLogGroupLongRetention>({ data: filteredCWLogsLongRetention, initialItemsPerPage: 10 })
  const cwLogsUnusedPagination = usePagination<CloudWatchLogGroupUnused>({ data: filteredCWLogsUnused, initialItemsPerPage: 10 })
  const dynamodbUnusedPagination = usePagination<DynamoDBUnusedTable>({ data: filteredDynamoDBUnused, initialItemsPerPage: 10 })
  const dynamodbBillingPagination = usePagination<DynamoDBBillingModeOptimization>({ data: filteredDynamoDBBilling, initialItemsPerPage: 10 })
  const savingsPlansEC2Pagination = usePagination<UncoveredEC2Instance>({ data: filteredUncoveredEC2, initialItemsPerPage: 10 })

  // Phase 6 pagination hooks
  const vpcEndpointUnusedPagination = usePagination<VPCEndpointUnused>({ data: filteredVPCEndpointUnused, initialItemsPerPage: 10 })
  const vpcEndpointDuplicatePagination = usePagination<VPCEndpointDuplicate>({ data: filteredVPCEndpointDuplicate, initialItemsPerPage: 10 })
  const efsUnusedPagination = usePagination<EFSUnusedFileSystem>({ data: filteredEFSUnused, initialItemsPerPage: 10 })
  const efsNoLifecyclePagination = usePagination<EFSWithoutLifecycle>({ data: filteredEFSNoLifecycle, initialItemsPerPage: 10 })
  const ebsOrphanedSnapshotPagination = usePagination<EBSOrphanedSnapshot>({ data: filteredEBSOrphanedSnapshots, initialItemsPerPage: 10 })
  const ebsDuplicateSnapshotPagination = usePagination<EBSDuplicateSnapshot>({ data: filteredEBSDuplicateSnapshots, initialItemsPerPage: 10 })
  const dataTransferPagination = usePagination<DataTransferHighCost>({ data: filteredDataTransfer, initialItemsPerPage: 10 })
  const beanstalkUnusedPagination = usePagination<ElasticBeanstalkUnusedEnvironment>({ data: filteredBeanstalkUnused, initialItemsPerPage: 10 })
  const beanstalkNonProdPagination = usePagination<ElasticBeanstalkNonProdRunning>({ data: filteredBeanstalkNonProd, initialItemsPerPage: 10 })

  // Phase 7 pagination hooks
  const cloudfrontUnusedPagination = usePagination<CloudFrontUnusedDistribution>({ data: filteredCloudFrontUnused, initialItemsPerPage: 10 })
  const cloudfrontNoLoggingPagination = usePagination<CloudFrontNoLogging>({ data: filteredCloudFrontNoLogging, initialItemsPerPage: 10 })
  const route53UnusedPagination = usePagination<Route53UnusedHostedZone>({ data: filteredRoute53Unused, initialItemsPerPage: 10 })
  const sqsUnusedPagination = usePagination<SQSUnusedQueue>({ data: filteredSQSUnused, initialItemsPerPage: 10 })
  const sqsHighRetentionPagination = usePagination<SQSHighRetentionQueue>({ data: filteredSQSHighRetention, initialItemsPerPage: 10 })
  const snsUnusedPagination = usePagination<SNSUnusedTopic>({ data: filteredSNSUnused, initialItemsPerPage: 10 })
  const apigatewayUnusedPagination = usePagination<APIGatewayUnusedAPI>({ data: filteredAPIGatewayUnused, initialItemsPerPage: 10 })
  const apigatewayNoCachingPagination = usePagination<APIGatewayNoCaching>({ data: filteredAPIGatewayNoCaching, initialItemsPerPage: 10 })
  const stepfunctionsUnusedPagination = usePagination<StepFunctionsUnusedStateMachine>({ data: filteredStepFunctionsUnused, initialItemsPerPage: 10 })
  const ecsOversizedPagination = usePagination<ECSOversizedTask>({ data: filteredECSOversized, initialItemsPerPage: 10 })
  const redshiftIdlePagination = usePagination<RedshiftIdleCluster>({ data: filteredRedshiftIdle, initialItemsPerPage: 10 })
  const kinesisUnusedPagination = usePagination<KinesisUnusedStream>({ data: filteredKinesisUnused, initialItemsPerPage: 10 })
  const glueUnusedCrawlersPagination = usePagination<GlueUnusedCrawler>({ data: filteredGlueUnusedCrawlers, initialItemsPerPage: 10 })
  const glueUnusedJobsPagination = usePagination<GlueUnusedJob>({ data: filteredGlueUnusedJobs, initialItemsPerPage: 10 })

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
    }).format(amount)
  }

  const toggleSort = (
    currentField: SortField | null,
    currentDirection: SortDirection,
    newField: SortField,
    setField: (field: SortField | null) => void,
    setDirection: (direction: SortDirection) => void
  ) => {
    if (currentField === newField) {
      if (currentDirection === 'asc') {
        setDirection('desc')
      } else if (currentDirection === 'desc') {
        setField(null)
        setDirection(null)
      }
    } else {
      setField(newField)
      setDirection('asc')
    }
  }

  const SortIcon = ({
    field,
    currentField,
    currentDirection,
  }: {
    field: SortField
    currentField: SortField | null
    currentDirection: SortDirection
  }) => {
    if (currentField !== field) return <ArrowUpDown className="w-3 h-3 text-gray-400" />
    if (currentDirection === 'asc') return <ArrowUp className="w-3 h-3 text-blue-600" />
    if (currentDirection === 'desc') return <ArrowDown className="w-3 h-3 text-blue-600" />
    return <ArrowUpDown className="w-3 h-3 text-gray-400" />
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <div className="p-2.5 bg-gradient-to-br from-orange-500 to-red-600 rounded-lg shadow-md">
                <Search className="w-7 h-7 text-white" />
              </div>
              FinOps Audit
            </h1>
            <p className="text-gray-600 mt-2">
              Identify cost optimization opportunities and waste across all AWS regions
            </p>
          </div>
          <button
            type="button"
            onClick={() => startAsyncAudit()}
            disabled={isStarting || isPolling}
            className="btn-primary flex items-center gap-2 shadow-lg hover:shadow-xl transition-all"
          >
            {isStarting || isPolling ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {isStarting ? 'Starting Audit...' : 'Running Audit...'}
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Run Audit
              </>
            )}
          </button>
        </div>
      </div>

      {/* No AWS Accounts Warning */}
      {!loadingAccounts && !hasAccounts && (
        <div className="card mb-8 bg-gradient-to-r from-yellow-50 to-amber-50 border-l-4 border-yellow-500">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-yellow-500 rounded-lg">
              <AlertCircle className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No AWS Accounts Configured</h3>
              <p className="text-gray-700 mb-4">
                To run FinOps audits and identify cost optimization opportunities, you need to add at least one AWS account first. Audits scan 28 different resource types across all regions to find waste and savings.
              </p>
              <button
                onClick={() => navigate('/aws-accounts')}
                className="btn-primary flex items-center gap-2"
              >
                <Cloud className="w-4 h-4" />
                Add AWS Account
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      {hasAccounts && (jobStatus || isPolling) && (
        <div className="mb-8">
          {jobStatus ? (
            <AuditProgressBar
              progress={jobStatus.progress}
              status={jobStatus.status}
              currentStep={jobStatus.current_step}
              error={pollingError || jobStatus.error}
            />
          ) : (
            <AuditProgressBar
              progress={0}
              status="pending"
              currentStep="Initializing audit job..."
              error={pollingError || undefined}
            />
          )}
        </div>
      )}

      {/* Audit Summary */}
      {hasAccounts && auditResults && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="card bg-gradient-to-br from-red-50 to-orange-50 border-l-4 border-red-500 hover:shadow-lg transition-shadow">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-red-500 to-red-600 rounded-lg shadow-md">
                  <AlertCircle className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-600 uppercase">Total Findings</h3>
              </div>
              <p className="text-4xl font-bold text-gray-900">
                {auditResults?.summary?.total_findings ?? 0}
              </p>
            </div>

            <div className="card bg-gradient-to-br from-green-50 to-emerald-50 border-l-4 border-green-500 hover:shadow-lg transition-shadow">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg shadow-md">
                  <TrendingDown className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-600 uppercase">
                  Potential Savings
                </h3>
              </div>
              <p className="text-4xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
                {formatCurrency(auditResults?.summary?.total_potential_savings ?? 0)}/mo
              </p>
            </div>

            <div className="card bg-gradient-to-br from-blue-50 to-indigo-50 border-l-4 border-blue-500 hover:shadow-lg transition-shadow">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg shadow-md">
                  <Server className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-600 uppercase">Compute Waste</h3>
              </div>
              <p className="text-4xl font-bold text-gray-900">
                {(auditResults?.ec2_audit?.idle_instances?.length ?? 0) + (auditResults?.rds_audit?.idle_instances?.length ?? 0)}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                EC2 + RDS Idle
              </p>
            </div>

            <div className="card bg-gradient-to-br from-purple-50 to-pink-50 border-l-4 border-purple-500 hover:shadow-lg transition-shadow">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg shadow-md">
                  <HardDrive className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-600 uppercase">Storage Waste</h3>
              </div>
              <p className="text-4xl font-bold text-gray-900">
                {(auditResults?.ebs_audit?.unattached_volumes?.length ?? 0) + (auditResults?.s3_audit?.buckets_without_lifecycle?.length ?? 0)}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                EBS + S3
              </p>
            </div>
          </div>

          {/* Export Options */}
          <div className="mb-6 card bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-600" />
                <div>
                  <h3 className="text-base font-bold text-gray-800">Export Options</h3>
                  <p className="text-sm text-gray-600">Download or upload to S3 (configure in Settings)</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => exportPDFMutation.mutate()}
                  className="btn-secondary flex items-center gap-2"
                  disabled={!auditResults && !currentJobId}
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </button>
                <button
                  type="button"
                  onClick={() => exportExcelMutation.mutate()}
                  className="btn-secondary flex items-center gap-2"
                  disabled={!auditResults && !currentJobId}
                >
                  <FileSpreadsheet className="w-4 h-4" />
                  Download Excel
                </button>
                <button
                  type="button"
                  onClick={() => setShowTeamsModal(true)}
                  className="btn-primary flex items-center gap-2"
                  disabled={!webhooks || webhooks.length === 0}
                >
                  <Send className="w-4 h-4" />
                  Send to Teams
                </button>
                {webhooks && webhooks.length === 0 && (
                  <p className="ml-3 text-sm text-gray-500 self-center">
                    No Teams webhooks configured. Add one in Settings.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Top Opportunities */}
          {(auditResults?.summary?.top_opportunities?.length ?? 0) > 0 && (
            <div className="card mb-8 bg-gradient-to-r from-orange-50 via-red-50 to-pink-50 border-l-4 border-orange-500">
              <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <TrendingDown className="w-6 h-6 text-orange-600" />
                Top Savings Opportunities
              </h2>
              <ul className="space-y-2">
                {auditResults?.summary?.top_opportunities?.map((opportunity, index) => (
                  <li
                    key={index}
                    className="flex items-center gap-3 p-3 bg-white rounded-lg shadow-sm border border-orange-200"
                  >
                    <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-orange-500 to-red-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                      {index + 1}
                    </div>
                    <span className="text-gray-700 font-medium">{opportunity}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Filters */}
          <div className="card mb-6 bg-gradient-to-r from-gray-50 to-blue-50">
            <div className="flex items-center gap-2 mb-4">
              <Filter className="w-5 h-5 text-blue-600" />
              <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Resource Type Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Resource Types
                </label>
                <div className="flex flex-wrap gap-2">
                  {resourceTypes.map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => {
                        setSelectedResourceTypes((prev) =>
                          prev.includes(type)
                            ? prev.filter((t) => t !== type)
                            : [...prev, type]
                        )
                      }}
                      className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                        selectedResourceTypes.includes(type)
                          ? 'bg-blue-600 text-white shadow-md'
                          : 'bg-white text-gray-700 border border-gray-300 hover:border-blue-600'
                      }`}
                    >
                      {type}
                    </button>
                  ))}
                  {selectedResourceTypes.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSelectedResourceTypes([])}
                      className="px-3 py-1.5 rounded-full text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-all"
                    >
                      <X className="w-3 h-3 inline mr-1" />
                      Clear
                    </button>
                  )}
                </div>
              </div>

              {/* Region Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Regions</label>
                <div className="flex flex-wrap gap-2">
                  {regions.map((region) => (
                    <button
                      key={region}
                      type="button"
                      onClick={() => {
                        setSelectedRegions((prev) =>
                          prev.includes(region)
                            ? prev.filter((r) => r !== region)
                            : [...prev, region]
                        )
                      }}
                      className={`px-3 py-1.5 rounded-full text-sm font-medium font-mono transition-all ${
                        selectedRegions.includes(region)
                          ? 'bg-purple-600 text-white shadow-md'
                          : 'bg-white text-gray-700 border border-gray-300 hover:border-purple-600'
                      }`}
                    >
                      {region}
                    </button>
                  ))}
                  {selectedRegions.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSelectedRegions([])}
                      className="px-3 py-1.5 rounded-full text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-all"
                    >
                      <X className="w-3 h-3 inline mr-1" />
                      Clear
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Detailed Findings */}
          <div className="card">
            <div className="border-b border-gray-200 mb-6">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">Detailed Findings</h2>
            </div>

            {/* EC2 Idle Instances */}
            {filteredSortedEC2Instances.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Server className="w-5 h-5 text-blue-600" />
                  Idle EC2 Instances ({filteredSortedEC2Instances.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Instance ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th
                          className="px-4 py-3 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                          onClick={() =>
                            toggleSort(ec2SortField, ec2SortDirection, 'cpu', setEc2SortField, setEc2SortDirection)
                          }
                        >
                          <div className="flex items-center gap-1">
                            Avg CPU %
                            <SortIcon field="cpu" currentField={ec2SortField} currentDirection={ec2SortDirection} />
                          </div>
                        </th>
                        <th
                          className="px-4 py-3 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                          onClick={() =>
                            toggleSort(ec2SortField, ec2SortDirection, 'cost', setEc2SortField, setEc2SortDirection)
                          }
                        >
                          <div className="flex items-center gap-1">
                            Monthly Cost
                            <SortIcon field="cost" currentField={ec2SortField} currentDirection={ec2SortDirection} />
                          </div>
                        </th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {ec2Pagination.paginatedData.map((instance) => (
                        <tr key={instance.instance_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{instance.instance_id}</td>
                          <td className="px-4 py-3">{instance.instance_type}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {instance.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {instance.avg_cpu_utilization.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(instance.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{instance.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={ec2Pagination.currentPage}
                  totalPages={ec2Pagination.totalPages}
                  totalItems={filteredSortedEC2Instances.length}
                  itemsPerPage={ec2Pagination.itemsPerPage}
                  onPageChange={ec2Pagination.setCurrentPage}
                  onItemsPerPageChange={ec2Pagination.setItemsPerPage}
                />
              </div>
            )}

            {/* RDS Idle Instances */}
            {filteredSortedRDSInstances.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Database className="w-5 h-5 text-indigo-600" />
                  Idle RDS Instances ({filteredSortedRDSInstances.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">DB Instance ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Class</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Engine</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th
                          className="px-4 py-3 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                          onClick={() =>
                            toggleSort(rdsSortField, rdsSortDirection, 'cpu', setRdsSortField, setRdsSortDirection)
                          }
                        >
                          <div className="flex items-center gap-1">
                            Avg CPU %
                            <SortIcon field="cpu" currentField={rdsSortField} currentDirection={rdsSortDirection} />
                          </div>
                        </th>
                        <th
                          className="px-4 py-3 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                          onClick={() =>
                            toggleSort(rdsSortField, rdsSortDirection, 'connections', setRdsSortField, setRdsSortDirection)
                          }
                        >
                          <div className="flex items-center gap-1">
                            Avg Connections
                            <SortIcon field="connections" currentField={rdsSortField} currentDirection={rdsSortDirection} />
                          </div>
                        </th>
                        <th
                          className="px-4 py-3 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                          onClick={() =>
                            toggleSort(rdsSortField, rdsSortDirection, 'cost', setRdsSortField, setRdsSortDirection)
                          }
                        >
                          <div className="flex items-center gap-1">
                            Monthly Cost
                            <SortIcon field="cost" currentField={rdsSortField} currentDirection={rdsSortDirection} />
                          </div>
                        </th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {rdsPagination.paginatedData.map((instance) => (
                        <tr key={instance.db_instance_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{instance.db_instance_id}</td>
                          <td className="px-4 py-3 text-xs">{instance.db_instance_class}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold">
                              {instance.engine}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {instance.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {instance.avg_cpu_utilization.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-semibold">
                              {instance.avg_connections.toFixed(0)}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(instance.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{instance.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={rdsPagination.currentPage}
                  totalPages={rdsPagination.totalPages}
                  totalItems={filteredSortedRDSInstances.length}
                  itemsPerPage={rdsPagination.itemsPerPage}
                  onPageChange={rdsPagination.setCurrentPage}
                  onItemsPerPageChange={rdsPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Lambda Unused Functions */}
            {filteredLambdaUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-yellow-600" />
                  Unused Lambda Functions ({filteredLambdaUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Function Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Runtime</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Since Invocation</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {lambdaUnusedPagination.paginatedData.map((func) => (
                        <tr key={func.function_arn} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{func.function_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-semibold">
                              {func.runtime}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {func.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {func.days_since_invocation} days
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{func.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={lambdaUnusedPagination.currentPage}
                  totalPages={lambdaUnusedPagination.totalPages}
                  totalItems={filteredLambdaUnused.length}
                  itemsPerPage={lambdaUnusedPagination.itemsPerPage}
                  onPageChange={lambdaUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={lambdaUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* S3 Buckets Without Lifecycle */}
            {filteredS3NoLifecycle.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <FolderOpen className="w-5 h-5 text-teal-600" />
                  S3 Buckets Without Lifecycle Policy ({filteredS3NoLifecycle.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Bucket Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Size (GB)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Object Count</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Current Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {s3Pagination.paginatedData.map((bucket) => (
                        <tr key={bucket.bucket_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{bucket.bucket_name}</td>
                          <td className="px-4 py-3">{bucket.total_size_gb.toFixed(2)} GB</td>
                          <td className="px-4 py-3">{bucket.object_count.toLocaleString()}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {bucket.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(bucket.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(bucket.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{bucket.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={s3Pagination.currentPage}
                  totalPages={s3Pagination.totalPages}
                  totalItems={filteredS3NoLifecycle.length}
                  itemsPerPage={s3Pagination.itemsPerPage}
                  onPageChange={s3Pagination.setCurrentPage}
                  onItemsPerPageChange={s3Pagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Load Balancers with No Targets */}
            {filteredLBNoTargets.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-pink-600" />
                  Load Balancers with No Targets ({filteredLBNoTargets.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">LB Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Active</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {lbPagination.paginatedData.map((lb) => (
                        <tr key={lb.lb_arn} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{lb.lb_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-semibold uppercase">
                              {lb.lb_type}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {lb.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded-full text-xs font-semibold">
                              {lb.days_active} days
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(lb.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{lb.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={lbPagination.currentPage}
                  totalPages={lbPagination.totalPages}
                  totalItems={filteredLBNoTargets.length}
                  itemsPerPage={lbPagination.itemsPerPage}
                  onPageChange={lbPagination.setCurrentPage}
                  onItemsPerPageChange={lbPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Unattached EBS Volumes */}
            {filteredSortedEBSVolumes.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <HardDrive className="w-5 h-5 text-purple-600" />
                  Unattached EBS Volumes ({filteredSortedEBSVolumes.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Volume ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th
                          className="px-4 py-3 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                          onClick={() =>
                            toggleSort(ebsSortField, ebsSortDirection, 'size', setEbsSortField, setEbsSortDirection)
                          }
                        >
                          <div className="flex items-center gap-1">
                            Size (GB)
                            <SortIcon field="size" currentField={ebsSortField} currentDirection={ebsSortDirection} />
                          </div>
                        </th>
                        <th
                          className="px-4 py-3 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                          onClick={() =>
                            toggleSort(ebsSortField, ebsSortDirection, 'days', setEbsSortField, setEbsSortDirection)
                          }
                        >
                          <div className="flex items-center gap-1">
                            Days Unattached
                            <SortIcon field="days" currentField={ebsSortField} currentDirection={ebsSortDirection} />
                          </div>
                        </th>
                        <th
                          className="px-4 py-3 text-left font-semibold text-gray-700 cursor-pointer hover:bg-gray-100"
                          onClick={() =>
                            toggleSort(ebsSortField, ebsSortDirection, 'cost', setEbsSortField, setEbsSortDirection)
                          }
                        >
                          <div className="flex items-center gap-1">
                            Monthly Cost
                            <SortIcon field="cost" currentField={ebsSortField} currentDirection={ebsSortDirection} />
                          </div>
                        </th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {ebsPagination.paginatedData.map((volume) => (
                        <tr key={volume.volume_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{volume.volume_id}</td>
                          <td className="px-4 py-3">{volume.volume_type}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {volume.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{volume.size_gb} GB</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded-full text-xs font-semibold">
                              {volume.days_unattached} days
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(volume.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{volume.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={ebsPagination.currentPage}
                  totalPages={ebsPagination.totalPages}
                  totalItems={filteredSortedEBSVolumes.length}
                  itemsPerPage={ebsPagination.itemsPerPage}
                  onPageChange={ebsPagination.setCurrentPage}
                  onItemsPerPageChange={ebsPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Unattached Elastic IPs */}
            {filteredEIPs.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Network className="w-5 h-5 text-cyan-600" />
                  Unattached Elastic IPs ({filteredEIPs.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Public IP</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Allocation ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {eipPagination.paginatedData.map((eip) => (
                        <tr key={eip.allocation_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{eip.public_ip}</td>
                          <td className="px-4 py-3 font-mono text-xs">{eip.allocation_id}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {eip.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(eip.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{eip.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={eipPagination.currentPage}
                  totalPages={eipPagination.totalPages}
                  totalItems={filteredEIPs.length}
                  itemsPerPage={eipPagination.itemsPerPage}
                  onPageChange={eipPagination.setCurrentPage}
                  onItemsPerPageChange={eipPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Untagged Resources */}
            {filteredUntagged.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Tag className="w-5 h-5 text-yellow-600" />
                  Untagged Resources ({filteredUntagged.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Resource ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Missing Tags</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {untaggedPagination.paginatedData.map((resource, index) => (
                        <tr key={index} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold uppercase">
                              {resource.resource_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">{resource.resource_id}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {resource.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-1">
                              {resource.missing_tags.map((tag) => (
                                <span
                                  key={tag}
                                  className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{resource.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={untaggedPagination.currentPage}
                  totalPages={untaggedPagination.totalPages}
                  totalItems={filteredUntagged.length}
                  itemsPerPage={untaggedPagination.itemsPerPage}
                  onPageChange={untaggedPagination.setCurrentPage}
                  onItemsPerPageChange={untaggedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 5: NAT Gateway Idle */}
            {filteredNATGatewayIdle.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Globe className="w-5 h-5 text-emerald-600" />
                  Idle NAT Gateways ({filteredNATGatewayIdle.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">NAT Gateway ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">VPC ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">GB Out/Day</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Active</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {natGatewayIdlePagination.paginatedData.map((ng) => (
                        <tr key={ng.nat_gateway_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{ng.nat_gateway_id}</td>
                          <td className="px-4 py-3 font-mono text-xs">{ng.vpc_id}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {ng.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {ng.avg_gb_out_per_day.toFixed(2)} GB
                            </span>
                          </td>
                          <td className="px-4 py-3">{ng.days_active} days</td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(ng.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(ng.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{ng.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={natGatewayIdlePagination.currentPage}
                  totalPages={natGatewayIdlePagination.totalPages}
                  totalItems={filteredNATGatewayIdle.length}
                  itemsPerPage={natGatewayIdlePagination.itemsPerPage}
                  onPageChange={natGatewayIdlePagination.setCurrentPage}
                  onItemsPerPageChange={natGatewayIdlePagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 5: NAT Gateway Unused */}
            {filteredNATGatewayUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Globe className="w-5 h-5 text-red-600" />
                  Unused NAT Gateways ({filteredNATGatewayUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">NAT Gateway ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">VPC ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Active</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {natGatewayUnusedPagination.paginatedData.map((ng) => (
                        <tr key={ng.nat_gateway_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{ng.nat_gateway_id}</td>
                          <td className="px-4 py-3 font-mono text-xs">{ng.vpc_id}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {ng.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{ng.days_active} days</td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(ng.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{ng.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={natGatewayUnusedPagination.currentPage}
                  totalPages={natGatewayUnusedPagination.totalPages}
                  totalItems={filteredNATGatewayUnused.length}
                  itemsPerPage={natGatewayUnusedPagination.itemsPerPage}
                  onPageChange={natGatewayUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={natGatewayUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 5: ElastiCache Idle Clusters */}
            {filteredElastiCacheIdle.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <MemoryStick className="w-5 h-5 text-orange-600" />
                  Idle ElastiCache Clusters ({filteredElastiCacheIdle.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Cluster ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Node Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Nodes</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">CPU %</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Cache Hit Rate</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {elasticacheIdlePagination.paginatedData.map((ec) => (
                        <tr key={ec.cluster_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{ec.cluster_id}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-semibold uppercase">
                              {ec.cluster_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs">{ec.node_type}</td>
                          <td className="px-4 py-3">{ec.num_nodes}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {ec.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {ec.avg_cpu_utilization.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-semibold">
                              {ec.cache_hit_rate.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(ec.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{ec.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={elasticacheIdlePagination.currentPage}
                  totalPages={elasticacheIdlePagination.totalPages}
                  totalItems={filteredElastiCacheIdle.length}
                  itemsPerPage={elasticacheIdlePagination.itemsPerPage}
                  onPageChange={elasticacheIdlePagination.setCurrentPage}
                  onItemsPerPageChange={elasticacheIdlePagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 5: CloudWatch Logs Long Retention */}
            {filteredCWLogsLongRetention.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-indigo-600" />
                  CloudWatch Log Groups with Long Retention ({filteredCWLogsLongRetention.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Log Group Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Size (GB)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Current Retention</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommended Retention</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {cwLogsLongRetentionPagination.paginatedData.map((lg) => (
                        <tr key={lg.log_group_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{lg.log_group_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {lg.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{lg.stored_gb.toFixed(2)} GB</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {lg.current_retention_days} days
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs font-semibold">
                              {lg.recommended_retention_days} days
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(lg.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(lg.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{lg.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={cwLogsLongRetentionPagination.currentPage}
                  totalPages={cwLogsLongRetentionPagination.totalPages}
                  totalItems={filteredCWLogsLongRetention.length}
                  itemsPerPage={cwLogsLongRetentionPagination.itemsPerPage}
                  onPageChange={cwLogsLongRetentionPagination.setCurrentPage}
                  onItemsPerPageChange={cwLogsLongRetentionPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 5: CloudWatch Logs Unused */}
            {filteredCWLogsUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-gray-600" />
                  Unused CloudWatch Log Groups ({filteredCWLogsUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Log Group Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Size (GB)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Since Last Event</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {cwLogsUnusedPagination.paginatedData.map((lg) => (
                        <tr key={lg.log_group_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{lg.log_group_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {lg.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{lg.stored_gb.toFixed(2)} GB</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {lg.days_since_last_event} days
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(lg.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{lg.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={cwLogsUnusedPagination.currentPage}
                  totalPages={cwLogsUnusedPagination.totalPages}
                  totalItems={filteredCWLogsUnused.length}
                  itemsPerPage={cwLogsUnusedPagination.itemsPerPage}
                  onPageChange={cwLogsUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={cwLogsUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 5: DynamoDB Unused Tables */}
            {filteredDynamoDBUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Table className="w-5 h-5 text-blue-600" />
                  Unused DynamoDB Tables ({filteredDynamoDBUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Table Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Size (GB)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Item Count</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Billing Mode</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Inactive</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {dynamodbUnusedPagination.paginatedData.map((dt) => (
                        <tr key={dt.table_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{dt.table_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {dt.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{dt.table_size_gb.toFixed(2)} GB</td>
                          <td className="px-4 py-3">{dt.item_count.toLocaleString()}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold uppercase">
                              {dt.billing_mode}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {dt.days_without_activity} days
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(dt.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{dt.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={dynamodbUnusedPagination.currentPage}
                  totalPages={dynamodbUnusedPagination.totalPages}
                  totalItems={filteredDynamoDBUnused.length}
                  itemsPerPage={dynamodbUnusedPagination.itemsPerPage}
                  onPageChange={dynamodbUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={dynamodbUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 5: DynamoDB Billing Mode Optimization */}
            {filteredDynamoDBBilling.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Table className="w-5 h-5 text-green-600" />
                  DynamoDB Billing Mode Optimization Opportunities ({filteredDynamoDBBilling.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Table Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Current Mode</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommended Mode</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Read Utilization</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Write Utilization</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Current Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {dynamodbBillingPagination.paginatedData.map((dt) => (
                        <tr key={dt.table_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{dt.table_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {dt.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-semibold uppercase">
                              {dt.current_billing_mode}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-semibold uppercase">
                              {dt.recommended_billing_mode}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-semibold">
                              {dt.avg_read_utilization.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-semibold">
                              {dt.avg_write_utilization.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(dt.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(dt.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{dt.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={dynamodbBillingPagination.currentPage}
                  totalPages={dynamodbBillingPagination.totalPages}
                  totalItems={filteredDynamoDBBilling.length}
                  itemsPerPage={dynamodbBillingPagination.itemsPerPage}
                  onPageChange={dynamodbBillingPagination.setCurrentPage}
                  onItemsPerPageChange={dynamodbBillingPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 5: Savings Plans - Uncovered EC2 */}
            {filteredUncoveredEC2.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-violet-600" />
                  EC2 Instances Without Savings Plans Coverage ({filteredUncoveredEC2.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Instance ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Instance Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Running</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings (20-70%)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommended Commitment</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {savingsPlansEC2Pagination.paginatedData.map((sp) => (
                        <tr key={sp.instance_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{sp.instance_id}</td>
                          <td className="px-4 py-3 text-xs">{sp.instance_type}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {sp.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-semibold">
                              {sp.days_running} days
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(sp.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(sp.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-violet-100 text-violet-700 rounded text-xs font-semibold uppercase">
                              {sp.recommended_commitment}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{sp.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={savingsPlansEC2Pagination.currentPage}
                  totalPages={savingsPlansEC2Pagination.totalPages}
                  totalItems={filteredUncoveredEC2.length}
                  itemsPerPage={savingsPlansEC2Pagination.itemsPerPage}
                  onPageChange={savingsPlansEC2Pagination.setCurrentPage}
                  onItemsPerPageChange={savingsPlansEC2Pagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: Unused VPC Endpoints */}
            {filteredVPCEndpointUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Network className="w-5 h-5 text-blue-600" />
                  Unused VPC Endpoints ({filteredVPCEndpointUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Endpoint ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Service</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">VPC ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">AZs</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">GB/Day</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {vpcEndpointUnusedPagination.paginatedData.map((vp) => (
                        <tr key={vp.endpoint_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{vp.endpoint_id}</td>
                          <td className="px-4 py-3 text-xs">{vp.service_name.split('.').pop()}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold">
                              {vp.endpoint_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">{vp.vpc_id}</td>
                          <td className="px-4 py-3">{vp.num_azs}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {vp.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{vp.avg_gb_per_day.toFixed(3)} GB</td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(vp.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{vp.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={vpcEndpointUnusedPagination.currentPage}
                  totalPages={vpcEndpointUnusedPagination.totalPages}
                  totalItems={filteredVPCEndpointUnused.length}
                  itemsPerPage={vpcEndpointUnusedPagination.itemsPerPage}
                  onPageChange={vpcEndpointUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={vpcEndpointUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: Duplicate VPC Endpoints */}
            {filteredVPCEndpointDuplicate.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Network className="w-5 h-5 text-orange-600" />
                  Duplicate VPC Endpoints ({filteredVPCEndpointDuplicate.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Service</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">VPC ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Duplicate Count</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {vpcEndpointDuplicatePagination.paginatedData.map((vp, idx) => (
                        <tr key={`${vp.vpc_id}-${vp.service_name}-${idx}`} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{vp.service_name.split('.').pop()}</td>
                          <td className="px-4 py-3 font-mono text-xs">{vp.vpc_id}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded-full text-xs font-semibold">
                              {vp.duplicate_count}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {vp.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(vp.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(vp.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{vp.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={vpcEndpointDuplicatePagination.currentPage}
                  totalPages={vpcEndpointDuplicatePagination.totalPages}
                  totalItems={filteredVPCEndpointDuplicate.length}
                  itemsPerPage={vpcEndpointDuplicatePagination.itemsPerPage}
                  onPageChange={vpcEndpointDuplicatePagination.setCurrentPage}
                  onItemsPerPageChange={vpcEndpointDuplicatePagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: Unused EFS File Systems */}
            {filteredEFSUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <FolderOpen className="w-5 h-5 text-red-600" />
                  Unused EFS File Systems ({filteredEFSUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">File System ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Size (GB)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Performance Mode</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Without Connections</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {efsUnusedPagination.paginatedData.map((efs) => (
                        <tr key={efs.file_system_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{efs.file_system_id}</td>
                          <td className="px-4 py-3 text-xs">{efs.file_system_name || '-'}</td>
                          <td className="px-4 py-3">{efs.size_gb.toFixed(2)} GB</td>
                          <td className="px-4 py-3 text-xs">{efs.performance_mode}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {efs.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {efs.days_without_connections} days
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(efs.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{efs.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={efsUnusedPagination.currentPage}
                  totalPages={efsUnusedPagination.totalPages}
                  totalItems={filteredEFSUnused.length}
                  itemsPerPage={efsUnusedPagination.itemsPerPage}
                  onPageChange={efsUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={efsUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: EFS Without Lifecycle */}
            {filteredEFSNoLifecycle.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <FolderOpen className="w-5 h-5 text-yellow-600" />
                  EFS Without Lifecycle Policy ({filteredEFSNoLifecycle.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">File System ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Size (GB)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Performance Mode</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Current Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {efsNoLifecyclePagination.paginatedData.map((efs) => (
                        <tr key={efs.file_system_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{efs.file_system_id}</td>
                          <td className="px-4 py-3 text-xs">{efs.file_system_name || '-'}</td>
                          <td className="px-4 py-3">{efs.size_gb.toFixed(2)} GB</td>
                          <td className="px-4 py-3 text-xs">{efs.performance_mode}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {efs.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(efs.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(efs.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{efs.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={efsNoLifecyclePagination.currentPage}
                  totalPages={efsNoLifecyclePagination.totalPages}
                  totalItems={filteredEFSNoLifecycle.length}
                  itemsPerPage={efsNoLifecyclePagination.itemsPerPage}
                  onPageChange={efsNoLifecyclePagination.setCurrentPage}
                  onItemsPerPageChange={efsNoLifecyclePagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: Orphaned EBS Snapshots */}
            {filteredEBSOrphanedSnapshots.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Camera className="w-5 h-5 text-red-600" />
                  Orphaned EBS Snapshots ({filteredEBSOrphanedSnapshots.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Snapshot ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Volume ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Size (GB)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">AMI Deleted?</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Age (days)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {ebsOrphanedSnapshotPagination.paginatedData.map((snap) => (
                        <tr key={snap.snapshot_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{snap.snapshot_id}</td>
                          <td className="px-4 py-3 font-mono text-xs">{snap.volume_id || '-'}</td>
                          <td className="px-4 py-3">{snap.size_gb} GB</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${snap.ami_deleted ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'}`}>
                              {snap.ami_deleted ? 'Yes' : 'No'}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {snap.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{snap.days_old} days</td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(snap.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{snap.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={ebsOrphanedSnapshotPagination.currentPage}
                  totalPages={ebsOrphanedSnapshotPagination.totalPages}
                  totalItems={filteredEBSOrphanedSnapshots.length}
                  itemsPerPage={ebsOrphanedSnapshotPagination.itemsPerPage}
                  onPageChange={ebsOrphanedSnapshotPagination.setCurrentPage}
                  onItemsPerPageChange={ebsOrphanedSnapshotPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: Duplicate EBS Snapshots */}
            {filteredEBSDuplicateSnapshots.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Camera className="w-5 h-5 text-orange-600" />
                  Duplicate EBS Snapshots ({filteredEBSDuplicateSnapshots.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Volume ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Total Snapshots</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Duplicate Count</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Total Size (GB)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {ebsDuplicateSnapshotPagination.paginatedData.map((snap) => (
                        <tr key={snap.volume_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{snap.volume_id}</td>
                          <td className="px-4 py-3">{snap.snapshot_ids.length}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded-full text-xs font-semibold">
                              {snap.duplicate_count}
                            </span>
                          </td>
                          <td className="px-4 py-3">{snap.size_gb} GB</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {snap.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(snap.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(snap.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{snap.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={ebsDuplicateSnapshotPagination.currentPage}
                  totalPages={ebsDuplicateSnapshotPagination.totalPages}
                  totalItems={filteredEBSDuplicateSnapshots.length}
                  itemsPerPage={ebsDuplicateSnapshotPagination.itemsPerPage}
                  onPageChange={ebsDuplicateSnapshotPagination.setCurrentPage}
                  onItemsPerPageChange={ebsDuplicateSnapshotPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: High Cost Data Transfer */}
            {filteredDataTransfer.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Send className="w-5 h-5 text-purple-600" />
                  High Cost Data Transfer ({filteredDataTransfer.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Service</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Transfer Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Source Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Dest Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly GB</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {dataTransferPagination.paginatedData.map((dt, idx) => (
                        <tr key={`${dt.service}-${dt.transfer_type}-${idx}`} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{dt.service}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold">
                              {dt.transfer_type}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {dt.source_region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {dt.dest_region ? (
                              <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                                {dt.dest_region}
                              </span>
                            ) : '-'}
                          </td>
                          <td className="px-4 py-3">{dt.monthly_gb.toFixed(1)} GB</td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(dt.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(dt.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{dt.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={dataTransferPagination.currentPage}
                  totalPages={dataTransferPagination.totalPages}
                  totalItems={filteredDataTransfer.length}
                  itemsPerPage={dataTransferPagination.itemsPerPage}
                  onPageChange={dataTransferPagination.setCurrentPage}
                  onItemsPerPageChange={dataTransferPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: Unused Elastic Beanstalk Environments */}
            {filteredBeanstalkUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-red-600" />
                  Unused Elastic Beanstalk Environments ({filteredBeanstalkUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Environment Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Application</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Status</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Health</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Requests/Day</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {beanstalkUnusedPagination.paginatedData.map((bs) => (
                        <tr key={bs.environment_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{bs.environment_name}</td>
                          <td className="px-4 py-3 text-xs">{bs.application_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-semibold">
                              {bs.status}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs font-semibold">
                              {bs.health}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {bs.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                              {bs.request_count_per_day.toFixed(1)}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(bs.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{bs.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={beanstalkUnusedPagination.currentPage}
                  totalPages={beanstalkUnusedPagination.totalPages}
                  totalItems={filteredBeanstalkUnused.length}
                  itemsPerPage={beanstalkUnusedPagination.itemsPerPage}
                  onPageChange={beanstalkUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={beanstalkUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 6: Non-Prod Beanstalk Running 24/7 */}
            {filteredBeanstalkNonProd.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-yellow-600" />
                  Non-Production Beanstalk Running 24/7 ({filteredBeanstalkNonProd.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Environment Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Application</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Environment Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Instances</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {beanstalkNonProdPagination.paginatedData.map((bs) => (
                        <tr key={bs.environment_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{bs.environment_name}</td>
                          <td className="px-4 py-3 text-xs">{bs.application_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs font-semibold uppercase">
                              {bs.environment_type}
                            </span>
                          </td>
                          <td className="px-4 py-3">{bs.instance_count}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {bs.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(bs.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(bs.potential_monthly_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{bs.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={beanstalkNonProdPagination.currentPage}
                  totalPages={beanstalkNonProdPagination.totalPages}
                  totalItems={filteredBeanstalkNonProd.length}
                  itemsPerPage={beanstalkNonProdPagination.itemsPerPage}
                  onPageChange={beanstalkNonProdPagination.setCurrentPage}
                  onItemsPerPageChange={beanstalkNonProdPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: CloudFront Unused Distributions */}
            {filteredCloudFrontUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Globe className="w-5 h-5 text-orange-600" />
                  Unused CloudFront Distributions ({filteredCloudFrontUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Distribution ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Domain Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Enabled</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Total Requests</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {cloudfrontUnusedPagination.paginatedData.map((cf) => (
                        <tr key={cf.distribution_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{cf.distribution_id}</td>
                          <td className="px-4 py-3 text-xs">{cf.domain_name}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${cf.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                              {cf.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                          </td>
                          <td className="px-4 py-3">{cf.total_requests.toLocaleString()}</td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(cf.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{cf.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={cloudfrontUnusedPagination.currentPage}
                  totalPages={cloudfrontUnusedPagination.totalPages}
                  totalItems={filteredCloudFrontUnused.length}
                  itemsPerPage={cloudfrontUnusedPagination.itemsPerPage}
                  onPageChange={cloudfrontUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={cloudfrontUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: CloudFront No Logging */}
            {filteredCloudFrontNoLogging.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Globe className="w-5 h-5 text-orange-600" />
                  CloudFront Without Logging ({filteredCloudFrontNoLogging.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Distribution ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Domain Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Enabled</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {cloudfrontNoLoggingPagination.paginatedData.map((cf) => (
                        <tr key={cf.distribution_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{cf.distribution_id}</td>
                          <td className="px-4 py-3 text-xs">{cf.domain_name}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${cf.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                              {cf.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{cf.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={cloudfrontNoLoggingPagination.currentPage}
                  totalPages={cloudfrontNoLoggingPagination.totalPages}
                  totalItems={filteredCloudFrontNoLogging.length}
                  itemsPerPage={cloudfrontNoLoggingPagination.itemsPerPage}
                  onPageChange={cloudfrontNoLoggingPagination.setCurrentPage}
                  onItemsPerPageChange={cloudfrontNoLoggingPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: Route53 Unused Hosted Zones */}
            {filteredRoute53Unused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Globe className="w-5 h-5 text-blue-600" />
                  Unused Route53 Hosted Zones ({filteredRoute53Unused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Hosted Zone ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Total Records</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">User Records</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {route53UnusedPagination.paginatedData.map((hz) => (
                        <tr key={hz.hosted_zone_id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{hz.hosted_zone_id}</td>
                          <td className="px-4 py-3 text-xs">{hz.hosted_zone_name}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${hz.is_private ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}>
                              {hz.is_private ? 'Private' : 'Public'}
                            </span>
                          </td>
                          <td className="px-4 py-3">{hz.total_records}</td>
                          <td className="px-4 py-3">{hz.user_records}</td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(hz.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{hz.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={route53UnusedPagination.currentPage}
                  totalPages={route53UnusedPagination.totalPages}
                  totalItems={filteredRoute53Unused.length}
                  itemsPerPage={route53UnusedPagination.itemsPerPage}
                  onPageChange={route53UnusedPagination.setCurrentPage}
                  onItemsPerPageChange={route53UnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: SQS Unused Queues */}
            {filteredSQSUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-purple-600" />
                  Unused SQS Queues ({filteredSQSUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Queue Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Messages Available</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Messages Sent (period)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {sqsUnusedPagination.paginatedData.map((q) => (
                        <tr key={q.queue_url} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{q.queue_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {q.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${q.is_fifo ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}>
                              {q.is_fifo ? 'FIFO' : 'Standard'}
                            </span>
                          </td>
                          <td className="px-4 py-3">{q.messages_available.toLocaleString()}</td>
                          <td className="px-4 py-3">{q.total_sent_period.toLocaleString()}</td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{q.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={sqsUnusedPagination.currentPage}
                  totalPages={sqsUnusedPagination.totalPages}
                  totalItems={filteredSQSUnused.length}
                  itemsPerPage={sqsUnusedPagination.itemsPerPage}
                  onPageChange={sqsUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={sqsUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: SQS High Retention Queues */}
            {filteredSQSHighRetention.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-purple-600" />
                  SQS Queues with High Retention ({filteredSQSHighRetention.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Queue Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Retention Period (days)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Max Retention (days)</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {sqsHighRetentionPagination.paginatedData.map((q) => (
                        <tr key={q.queue_url} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{q.queue_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {q.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-semibold">
                              {q.retention_period_days.toFixed(1)} days
                            </span>
                          </td>
                          <td className="px-4 py-3">{q.max_retention_days} days</td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{q.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={sqsHighRetentionPagination.currentPage}
                  totalPages={sqsHighRetentionPagination.totalPages}
                  totalItems={filteredSQSHighRetention.length}
                  itemsPerPage={sqsHighRetentionPagination.itemsPerPage}
                  onPageChange={sqsHighRetentionPagination.setCurrentPage}
                  onItemsPerPageChange={sqsHighRetentionPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: SNS Unused Topics */}
            {filteredSNSUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Send className="w-5 h-5 text-pink-600" />
                  Unused SNS Topics ({filteredSNSUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Topic Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Confirmed Subs</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Pending Subs</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Messages Published</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {snsUnusedPagination.paginatedData.map((t) => (
                        <tr key={t.topic_arn} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{t.topic_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {t.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{t.subscriptions_confirmed}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${t.subscriptions_pending > 0 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-700'}`}>
                              {t.subscriptions_pending}
                            </span>
                          </td>
                          <td className="px-4 py-3">{t.messages_published.toLocaleString()}</td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{t.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={snsUnusedPagination.currentPage}
                  totalPages={snsUnusedPagination.totalPages}
                  totalItems={filteredSNSUnused.length}
                  itemsPerPage={snsUnusedPagination.itemsPerPage}
                  onPageChange={snsUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={snsUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: API Gateway Unused APIs */}
            {filteredAPIGatewayUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Network className="w-5 h-5 text-teal-600" />
                  Unused API Gateway APIs ({filteredAPIGatewayUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">API Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Stage</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Total Requests</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Checked</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {apigatewayUnusedPagination.paginatedData.map((api) => (
                        <tr key={api.api_id + api.stage} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{api.api_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-mono">
                              {api.stage}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {api.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{api.total_requests.toLocaleString()}</td>
                          <td className="px-4 py-3">{api.days_checked}</td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{api.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={apigatewayUnusedPagination.currentPage}
                  totalPages={apigatewayUnusedPagination.totalPages}
                  totalItems={filteredAPIGatewayUnused.length}
                  itemsPerPage={apigatewayUnusedPagination.itemsPerPage}
                  onPageChange={apigatewayUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={apigatewayUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: API Gateway Without Caching */}
            {filteredAPIGatewayNoCaching.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Network className="w-5 h-5 text-teal-600" />
                  API Gateway Without Caching ({filteredAPIGatewayNoCaching.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">API Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Stage</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Avg Daily Requests</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Potential Savings</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {apigatewayNoCachingPagination.paginatedData.map((api) => (
                        <tr key={api.api_id + api.stage} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{api.api_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-mono">
                              {api.stage}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {api.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{api.avg_daily_requests.toLocaleString()}</td>
                          <td className="px-4 py-3 font-semibold text-green-600">
                            {formatCurrency(api.potential_cost_savings)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{api.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={apigatewayNoCachingPagination.currentPage}
                  totalPages={apigatewayNoCachingPagination.totalPages}
                  totalItems={filteredAPIGatewayNoCaching.length}
                  itemsPerPage={apigatewayNoCachingPagination.itemsPerPage}
                  onPageChange={apigatewayNoCachingPagination.setCurrentPage}
                  onItemsPerPageChange={apigatewayNoCachingPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: Step Functions Unused State Machines */}
            {filteredStepFunctionsUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-indigo-600" />
                  Unused Step Functions State Machines ({filteredStepFunctionsUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">State Machine Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Total Executions</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Since Last</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {stepfunctionsUnusedPagination.paginatedData.map((sm) => (
                        <tr key={sm.state_machine_arn} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{sm.state_machine_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-semibold uppercase">
                              {sm.type}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {sm.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">{sm.total_executions ?? 0}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-semibold">
                              {sm.days_since_last_execution ?? '-'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{sm.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={stepfunctionsUnusedPagination.currentPage}
                  totalPages={stepfunctionsUnusedPagination.totalPages}
                  totalItems={filteredStepFunctionsUnused.length}
                  itemsPerPage={stepfunctionsUnusedPagination.itemsPerPage}
                  onPageChange={stepfunctionsUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={stepfunctionsUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: ECS Oversized Tasks */}
            {filteredECSOversized.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Server className="w-5 h-5 text-cyan-600" />
                  ECS Oversized Tasks ({filteredECSOversized.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Service Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Cluster</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Task CPU</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Task Memory</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Avg CPU %</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Avg Memory %</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {ecsOversizedPagination.paginatedData.map((task, idx) => (
                        <tr key={`${task.cluster_name}-${task.service_name}-${idx}`} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{task.service_name}</td>
                          <td className="px-4 py-3 text-xs">{task.cluster_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {task.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs">{task.task_cpu}</td>
                          <td className="px-4 py-3 text-xs">{task.task_memory}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold">
                              {task.avg_cpu_utilization.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-semibold">
                              {task.avg_memory_utilization.toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{task.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={ecsOversizedPagination.currentPage}
                  totalPages={ecsOversizedPagination.totalPages}
                  totalItems={filteredECSOversized.length}
                  itemsPerPage={ecsOversizedPagination.itemsPerPage}
                  onPageChange={ecsOversizedPagination.setCurrentPage}
                  onItemsPerPageChange={ecsOversizedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: Redshift Idle Clusters */}
            {filteredRedshiftIdle.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Database className="w-5 h-5 text-red-600" />
                  Idle Redshift Clusters ({filteredRedshiftIdle.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Cluster ID</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Node Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Nodes</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Avg Connections</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {redshiftIdlePagination.paginatedData.map((cluster) => (
                        <tr key={cluster.cluster_identifier} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-mono text-xs">{cluster.cluster_identifier}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {cluster.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs">{cluster.node_type}</td>
                          <td className="px-4 py-3">{cluster.number_of_nodes}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-semibold">
                              {cluster.avg_database_connections.toFixed(1)}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(cluster.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{cluster.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={redshiftIdlePagination.currentPage}
                  totalPages={redshiftIdlePagination.totalPages}
                  totalItems={filteredRedshiftIdle.length}
                  itemsPerPage={redshiftIdlePagination.itemsPerPage}
                  onPageChange={redshiftIdlePagination.setCurrentPage}
                  onItemsPerPageChange={redshiftIdlePagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: Kinesis Unused Streams */}
            {filteredKinesisUnused.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-orange-600" />
                  Unused Kinesis Streams ({filteredKinesisUnused.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Stream Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Status</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Shards</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Incoming Records</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Monthly Cost</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {kinesisUnusedPagination.paginatedData.map((stream) => (
                        <tr key={stream.stream_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{stream.stream_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {stream.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-semibold uppercase">
                              {stream.stream_status}
                            </span>
                          </td>
                          <td className="px-4 py-3">{stream.shard_count}</td>
                          <td className="px-4 py-3">{stream.incoming_records.toLocaleString()}</td>
                          <td className="px-4 py-3 font-semibold text-gray-600">
                            {formatCurrency(stream.estimated_monthly_cost)}
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{stream.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={kinesisUnusedPagination.currentPage}
                  totalPages={kinesisUnusedPagination.totalPages}
                  totalItems={filteredKinesisUnused.length}
                  itemsPerPage={kinesisUnusedPagination.itemsPerPage}
                  onPageChange={kinesisUnusedPagination.setCurrentPage}
                  onItemsPerPageChange={kinesisUnusedPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: Glue Unused Crawlers */}
            {filteredGlueUnusedCrawlers.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Table className="w-5 h-5 text-yellow-600" />
                  Unused Glue Crawlers ({filteredGlueUnusedCrawlers.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Crawler Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">State</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Last Status</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Since Last Crawl</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {glueUnusedCrawlersPagination.paginatedData.map((crawler) => (
                        <tr key={crawler.crawler_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{crawler.crawler_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {crawler.region}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-semibold uppercase">
                              {crawler.crawler_state}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${crawler.last_crawl_status === 'SUCCEEDED' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                              {crawler.last_crawl_status}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-semibold">
                              {crawler.days_since_last_crawl ?? '-'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{crawler.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={glueUnusedCrawlersPagination.currentPage}
                  totalPages={glueUnusedCrawlersPagination.totalPages}
                  totalItems={filteredGlueUnusedCrawlers.length}
                  itemsPerPage={glueUnusedCrawlersPagination.itemsPerPage}
                  onPageChange={glueUnusedCrawlersPagination.setCurrentPage}
                  onItemsPerPageChange={glueUnusedCrawlersPagination.setItemsPerPage}
                />
              </div>
            )}

            {/* Phase 7: Glue Unused Jobs */}
            {filteredGlueUnusedJobs.length > 0 && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <Table className="w-5 h-5 text-yellow-600" />
                  Unused Glue Jobs ({filteredGlueUnusedJobs.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Job Name</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Region</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Worker Type</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Workers</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Last Status</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Days Since Last Run</th>
                        <th className="px-4 py-3 text-left font-semibold text-gray-700">Recommendation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {glueUnusedJobsPagination.paginatedData.map((job) => (
                        <tr key={job.job_name} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs">{job.job_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-mono">
                              {job.region}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs">{job.worker_type ?? '-'}</td>
                          <td className="px-4 py-3">{job.number_of_workers ?? '-'}</td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${job.last_run_status === 'SUCCEEDED' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                              {job.last_run_status}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-semibold">
                              {job.days_since_last_run ?? '-'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-600 text-xs">{job.recommendation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  currentPage={glueUnusedJobsPagination.currentPage}
                  totalPages={glueUnusedJobsPagination.totalPages}
                  totalItems={filteredGlueUnusedJobs.length}
                  itemsPerPage={glueUnusedJobsPagination.itemsPerPage}
                  onPageChange={glueUnusedJobsPagination.setCurrentPage}
                  onItemsPerPageChange={glueUnusedJobsPagination.setItemsPerPage}
                />
              </div>
            )}
          </div>
        </>
      )}

      {/* Loading State - Skeleton Cards (only for cache loading) */}
      {isLoadingCache && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="card animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
                <div className="h-10 bg-gray-200 rounded w-1/2"></div>
              </div>
            ))}
          </div>
          <div className="card text-center py-12">
            <Loader2 className="w-10 h-10 text-blue-500 mx-auto mb-3 animate-spin" />
            <p className="text-gray-600 font-medium">Loading cached results...</p>
          </div>
        </>
      )}

      {/* Empty State - Preview Structure */}
      {!auditResults && !isLoadingCache && !isStarting && !isPolling && !jobStatus && (
        <>
          {/* Preview Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="card bg-gradient-to-br from-red-50 to-orange-50 border-l-4 border-red-300 opacity-60">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-red-400 to-red-500 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase">Total Findings</h3>
              </div>
              <p className="text-4xl font-bold text-gray-400">-</p>
            </div>
            <div className="card bg-gradient-to-br from-green-50 to-emerald-50 border-l-4 border-green-300 opacity-60">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-green-400 to-emerald-500 rounded-lg">
                  <TrendingDown className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase">Potential Savings</h3>
              </div>
              <p className="text-4xl font-bold text-gray-400">-</p>
            </div>
            <div className="card bg-gradient-to-br from-blue-50 to-cyan-50 border-l-4 border-blue-300 opacity-60">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-blue-400 to-cyan-500 rounded-lg">
                  <Server className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase">Regions Scanned</h3>
              </div>
              <p className="text-4xl font-bold text-gray-400">-</p>
            </div>
            <div className="card bg-gradient-to-br from-purple-50 to-pink-50 border-l-4 border-purple-300 opacity-60">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-gradient-to-br from-purple-400 to-pink-500 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-white" />
                </div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase">Audit Types</h3>
              </div>
              <p className="text-4xl font-bold text-gray-400">-</p>
            </div>
          </div>

          {/* Empty State Message */}
          <div className="card text-center py-16 bg-gradient-to-br from-gray-50 to-gray-100">
            <Search className="w-20 h-20 text-gray-300 mx-auto mb-6" />
            <h3 className="text-xl font-semibold text-gray-700 mb-2">No Audit Results Yet</h3>
            <p className="text-gray-500 mb-6">
              Click "Run Audit" above to identify cost optimization opportunities across 18 audit types
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-2xl mx-auto">
              <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">EC2 Idle Instances</span>
              <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium">Unattached EBS</span>
              <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-xs font-medium">Unused Lambda</span>
              <span className="px-3 py-1 bg-orange-100 text-orange-700 rounded-full text-xs font-medium">Idle RDS</span>
              <span className="px-3 py-1 bg-pink-100 text-pink-700 rounded-full text-xs font-medium">S3 Lifecycle</span>
              <span className="px-3 py-1 bg-cyan-100 text-cyan-700 rounded-full text-xs font-medium">NAT Gateways</span>
              <span className="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">And 12 more...</span>
            </div>
          </div>
        </>
      )}

      {/* Teams Modal */}
      {showTeamsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Send Audit Report to Teams</h2>

            {webhooks && Array.isArray(webhooks) && webhooks.length > 0 ? (
              <>
                <p className="text-sm text-gray-600 mb-4">
                  Select a Teams webhook to send the audit findings, or send to all active webhooks configured for audit reports:
                </p>

                <div className="space-y-2 mb-6 max-h-64 overflow-y-auto">
                  {/* Option to send to all webhooks */}
                  <button
                    type="button"
                    onClick={() => setSelectedWebhookId(null)}
                    className={`w-full text-left p-3 rounded-lg border-2 transition-all ${
                      selectedWebhookId === null
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-gray-900">All Active Webhooks</p>
                        <p className="text-xs text-gray-500 mt-1">
                          Send to all webhooks configured for audit reports
                        </p>
                      </div>
                      <span className="px-2 py-1 text-xs font-medium rounded bg-purple-100 text-purple-800">
                        Multiple
                      </span>
                    </div>
                  </button>

                  {webhooks.map((webhook) => (
                    <button
                      key={webhook.id}
                      type="button"
                      onClick={() => setSelectedWebhookId(webhook.id)}
                      className={`w-full text-left p-3 rounded-lg border-2 transition-all ${
                        selectedWebhookId === webhook.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      } ${!webhook.is_active ? 'opacity-50' : ''}`}
                      disabled={!webhook.is_active}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-semibold text-gray-900">{webhook.name}</p>
                          {webhook.description && (
                            <p className="text-xs text-gray-500 mt-1">{webhook.description}</p>
                          )}
                        </div>
                        {webhook.is_active ? (
                          <span className="px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-800">
                            Active
                          </span>
                        ) : (
                          <span className="px-2 py-1 text-xs font-medium rounded bg-gray-100 text-gray-600">
                            Inactive
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      // If null is selected, send to all webhooks; otherwise send to specific webhook
                      sendToTeamsMutation.mutate(selectedWebhookId === null ? undefined : selectedWebhookId!)
                    }}
                    disabled={sendToTeamsMutation.isPending}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {sendToTeamsMutation.isPending ? 'Sending...' : 'Send Report'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowTeamsModal(false)
                      setSelectedWebhookId(null)
                    }}
                    disabled={sendToTeamsMutation.isPending}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="text-sm text-gray-600 mb-4">
                  No Teams webhooks configured. Please add a webhook in Settings first.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setShowTeamsModal(false)
                    navigate('/settings')
                  }}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Go to Settings
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
