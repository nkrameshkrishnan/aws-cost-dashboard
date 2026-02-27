/**
 * FinOps audit API client.
 */
import axios from './axios'
import type {
  AuditRequest,
  FullAuditResults,
  EC2IdleInstance,
  EBSUnattachedVolume,
  ElasticIPUnattached,
  UntaggedResource,
} from '@/types/audit'

export interface AsyncAuditResponse {
  job_id: string
  status: string
  message: string
  status_url: string
  results_url: string
}

export interface AuditJobStatus {
  job_id: string
  account_name: string
  audit_types: string[]
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number  // 0-100
  current_step: string
  created_at: string
  started_at?: string
  completed_at?: string
  error?: string
  partial_results?: Record<string, any>
  results?: FullAuditResults
}

export const finopsApi = {
  /**
   * Run a full audit on an AWS account (synchronous - may timeout).
   */
  async runAudit(request: AuditRequest): Promise<FullAuditResults> {
    const response = await axios.post('/finops/audit', request)
    return response.data
  },

  /**
   * Start an async audit job and get job ID immediately.
   */
  async startAsyncAudit(request: AuditRequest): Promise<AsyncAuditResponse> {
    const response = await axios.post('/finops/audit/async', request)
    return response.data
  },

  /**
   * Poll for audit job status and progress.
   */
  async getAuditStatus(jobId: string): Promise<AuditJobStatus> {
    const response = await axios.get(`/finops/audit/status/${jobId}`)
    return response.data
  },

  /**
   * Get complete audit results (throws if not ready).
   * Can optionally return partial results for in-progress audits.
   */
  async getAuditResults(jobId: string, includePartial: boolean = true): Promise<FullAuditResults> {
    const response = await axios.get(`/finops/audit/results/${jobId}`, {
      params: { include_partial: includePartial }
    })
    return response.data
  },

  /**
   * Get list of available AWS regions for an account.
   */
  async getAvailableRegions(accountName: string): Promise<{
    account_name: string
    total_regions: number
    active_regions: number
    regions: string[]
  }> {
    const response = await axios.get(`/finops/regions/${accountName}`)
    return response.data
  },

  /**
   * List recent audit jobs.
   */
  async listAuditJobs(accountName?: string, limit = 20): Promise<{ jobs: AuditJobStatus[], count: number }> {
    const response = await axios.get('/finops/audit/jobs', {
      params: { account_name: accountName, limit }
    })
    return response.data
  },

  /**
   * Get idle EC2 instances for an account.
   */
  async getIdleInstances(
    accountName: string,
    cpuThreshold: number = 5.0
  ): Promise<{ idle_instances: EC2IdleInstance[]; total_cost: number }> {
    const response = await axios.get(`/finops/audit/idle-instances/${accountName}`, {
      params: { cpu_threshold: cpuThreshold },
    })
    return response.data
  },

  /**
   * Get unattached EBS volumes for an account.
   */
  async getUnattachedVolumes(
    accountName: string,
    daysThreshold: number = 7
  ): Promise<{ unattached_volumes: EBSUnattachedVolume[]; total_cost: number }> {
    const response = await axios.get(`/finops/audit/unattached-volumes/${accountName}`, {
      params: { days_threshold: daysThreshold },
    })
    return response.data
  },

  /**
   * Get unattached Elastic IPs for an account.
   */
  async getUnattachedIPs(
    accountName: string
  ): Promise<{ unattached_ips: ElasticIPUnattached[]; total_cost: number }> {
    const response = await axios.get(`/finops/audit/unattached-ips/${accountName}`)
    return response.data
  },

  /**
   * Get untagged resources for an account.
   */
  async getUntaggedResources(
    accountName: string,
    requiredTags: string = 'Environment,Owner,Project'
  ): Promise<{
    untagged_resources: UntaggedResource[]
    total_untagged: number
    compliance_percentage: number
  }> {
    const response = await axios.get(`/finops/audit/untagged-resources/${accountName}`, {
      params: { required_tags: requiredTags },
    })
    return response.data
  },

  /**
   * Send audit report to Teams webhooks.
   * Either jobId or auditResults must be provided.
   */
  async sendAuditToTeams(
    options: {
      jobId?: string
      auditResults?: FullAuditResults
      webhookId?: number
    }
  ): Promise<{
    success: boolean
    message: string
    notifications_sent: number
    webhooks_checked: number
    total_findings: number
    total_savings: number
    top_opportunities: number
    errors: string[]
  }> {
    const { jobId, auditResults, webhookId } = options

    // Build request body
    const requestBody = {
      audit_results: auditResults,
      webhook_id: webhookId,
    }

    // Build query params
    const params = jobId ? { job_id: jobId } : {}

    const response = await axios.post(
      '/finops/audit/send-to-teams',
      requestBody,
      { params }
    )
    return response.data
  },
}
