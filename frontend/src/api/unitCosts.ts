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

export const createBusinessMetric = async (data: {
  profile_name: string
  metric_date: string
  active_users?: number
  total_transactions?: number
  api_calls?: number
  data_processed_gb?: number
  custom_metric_1?: number
  custom_metric_1_name?: string
}): Promise<BusinessMetric> => {
  const response = await axios.post('/unit-costs/business-metrics', data)
  return response.data
}

export const getBusinessMetrics = async (
  profileName: string,
  startDate: string,
  endDate: string
): Promise<BusinessMetric[]> => {
  const response = await axios.get('/unit-costs/business-metrics', {
    params: { profile_name: profileName, start_date: startDate, end_date: endDate }
  })
  return response.data
}

export const calculateUnitCosts = async (
  profileName: string,
  startDate: string,
  endDate: string,
  region: string = 'us-east-2'
): Promise<UnitCost> => {
  const response = await axios.get('/unit-costs/calculate', {
    params: { profile_name: profileName, start_date: startDate, end_date: endDate, region }
  })
  return response.data
}

export const getUnitCostTrend = async (
  profileName: string,
  metricType: string,
  months: number = 6,
  region: string = 'us-east-2'
): Promise<UnitCostTrend> => {
  const response = await axios.get('/unit-costs/trend', {
    params: { profile_name: profileName, metric_type: metricType, months, region }
  })
  return response.data
}
