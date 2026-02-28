import axios from './axios'

export interface BusinessMetric {
  id: number
  profile_name: string
  metric_date: string
  active_users?: number
  total_transactions?: number
  api_calls?: number
  data_processed_gb?: number
  custom_metric_1?: number
  custom_metric_1_name?: string
  created_at: string
  updated_at: string
}

export interface UnitCost {
  profile_name: string
  start_date: string
  end_date: string
  total_cost: number
  cost_per_user?: number
  cost_per_transaction?: number
  cost_per_api_call?: number
  cost_per_gb?: number
  cost_per_custom_metric?: number
  total_users?: number
  total_transactions?: number
  total_api_calls?: number
  total_gb_processed?: number
  total_custom_metric?: number
  custom_metric_name?: string
  trend?: string
  mom_change_percent?: number
}

export interface UnitCostTrend {
  profile_name: string
  metric_type: string
  trend_data: Array<{
    date: string
    unit_cost: number
    total_cost: number
    metric_value: number
  }>
}

export interface AsyncJobResponse {
  job_id: string
  status: string
  message?: string
}

export interface AsyncJobStatus {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  job_type: string
  created_at: string
  started_at?: string
  completed_at?: string
  result?: any
  error?: string
}

export async function createBusinessMetric(data: {
  profile_name: string
  metric_date: string
  active_users?: number
  total_transactions?: number
  api_calls?: number
  data_processed_gb?: number
  custom_metric_1?: number
  custom_metric_1_name?: string
}): Promise<BusinessMetric> {
  const response = await axios.post('/unit-costs/business-metrics', data)
  return response.data
}

export async function getBusinessMetrics(
  profileName: string,
  startDate: string,
  endDate: string
): Promise<BusinessMetric[]> {
  const response = await axios.get('/unit-costs/business-metrics', {
    params: { profile_name: profileName, start_date: startDate, end_date: endDate }
  })
  return response.data
}

export async function calculateUnitCosts(
  profileName: string,
  startDate: string,
  endDate: string,
  region: string = 'us-east-2'
): Promise<UnitCost> {
  const response = await axios.get('/unit-costs/calculate', {
    params: { profile_name: profileName, start_date: startDate, end_date: endDate, region },
    timeout: 150000, // 150 seconds for AWS Cost Explorer API calls
  })
  return response.data
}

export async function getUnitCostTrend(
  profileName: string,
  metricType: string,
  months: number = 6,
  region: string = 'us-east-2'
): Promise<UnitCostTrend> {
  const response = await axios.get('/unit-costs/trend', {
    params: { profile_name: profileName, metric_type: metricType, months, region },
    timeout: 150000, // 150 seconds for AWS Cost Explorer API calls
  })
  return response.data
}

// ==============================================================================
// Async Job Functions (for long-running operations)
// ==============================================================================

export async function calculateUnitCostsAsync(
  profileName: string,
  startDate: string,
  endDate: string,
  region: string = 'us-east-2'
): Promise<AsyncJobResponse> {
  const response = await axios.post('/unit-costs/calculate/async', null, {
    params: { profile_name: profileName, start_date: startDate, end_date: endDate, region }
  })
  return response.data
}

export async function getUnitCostTrendAsync(
  profileName: string,
  metricType: string,
  months: number = 6,
  region: string = 'us-east-2'
): Promise<AsyncJobResponse> {
  const response = await axios.post('/unit-costs/trend/async', null, {
    params: { profile_name: profileName, metric_type: metricType, months, region }
  })
  return response.data
}

export async function getJobStatus(jobId: string): Promise<AsyncJobStatus> {
  const response = await axios.get(`/unit-costs/jobs/${jobId}`)
  return response.data
}

/**
 * Poll for job completion with exponential backoff.
 * Returns the job result when completed.
 */
export async function pollJobUntilComplete<T = unknown>(
  jobId: string,
  onProgress?: (status: AsyncJobStatus) => void,
  maxAttempts: number = 120,
  initialDelayMs: number = 1000
): Promise<T> {
  let attempts = 0
  let delay = initialDelayMs
  const maxDelay = 10000

  while (attempts < maxAttempts) {
    const status = await getJobStatus(jobId)

    if (onProgress) {
      onProgress(status)
    }

    if (status.status === 'completed') {
      return status.result as T
    }

    if (status.status === 'failed') {
      throw new Error(status.error || 'Job failed')
    }

    await new Promise(resolve => setTimeout(resolve, delay))
    delay = Math.min(delay * 1.2, maxDelay)
    attempts++
  }

  throw new Error('Job polling timeout - job did not complete in time')
}
