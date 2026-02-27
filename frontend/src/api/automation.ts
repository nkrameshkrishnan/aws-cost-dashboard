/**
 * Automation API client for managing scheduled jobs.
 */
import axios from './axios'

export interface Job {
  job_id: string
  name: string
  next_run_time: string | null
  trigger?: string
  enabled: boolean
}

export interface JobListResponse {
  jobs: Job[]
  total: number
}

export interface ScheduleBudgetAlertsRequest {
  job_id?: string
  cron_expression?: string
  enabled?: boolean
}

export interface ScheduleAuditRequest {
  job_id: string
  account_name: string
  cron_expression?: string
  audit_types?: string[]
  send_teams_notification?: boolean
  webhook_id?: number | null
  enabled?: boolean
}

export interface SchedulerStatus {
  running: boolean
  total_jobs: number
  active_jobs: number
}

export const automationApi = {
  /**
   * List all scheduled jobs.
   */
  async listJobs(): Promise<JobListResponse> {
    const response = await axios.get('/automation/jobs')
    return response.data
  },

  /**
   * Get details of a specific job.
   */
  async getJob(jobId: string): Promise<Job> {
    const response = await axios.get(`/automation/jobs/${jobId}`)
    return response.data
  },

  /**
   * Schedule automated budget alerts.
   */
  async scheduleBudgetAlerts(request: ScheduleBudgetAlertsRequest = {}): Promise<Job> {
    const response = await axios.post('/automation/budget-alerts/schedule', request)
    return response.data
  },

  /**
   * Schedule automated audit job.
   */
  async scheduleAudit(request: ScheduleAuditRequest): Promise<Job> {
    const response = await axios.post('/automation/audits/schedule', request)
    return response.data
  },

  /**
   * Pause a scheduled job.
   */
  async pauseJob(jobId: string): Promise<{ success: boolean; message: string }> {
    const response = await axios.post(`/automation/jobs/${jobId}/pause`)
    return response.data
  },

  /**
   * Resume a paused job.
   */
  async resumeJob(jobId: string): Promise<{ success: boolean; message: string }> {
    const response = await axios.post(`/automation/jobs/${jobId}/resume`)
    return response.data
  },

  /**
   * Delete a scheduled job.
   */
  async deleteJob(jobId: string): Promise<{ success: boolean; message: string }> {
    const response = await axios.delete(`/automation/jobs/${jobId}`)
    return response.data
  },

  /**
   * Run a job immediately (doesn't affect schedule).
   */
  async runJobNow(jobId: string): Promise<{ success: boolean; message: string }> {
    const response = await axios.post(`/automation/jobs/${jobId}/run-now`)
    return response.data
  },

  /**
   * Get scheduler status.
   */
  async getSchedulerStatus(): Promise<SchedulerStatus> {
    const response = await axios.get('/automation/status')
    return response.data
  },
}
