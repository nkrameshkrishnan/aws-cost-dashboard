// Type definitions for the AWS Cost Dashboard

export interface CostSummary {
  profile_name: string
  start_date: string
  end_date: string
  total_cost: number
  currency: string
  period_count: number
}

export interface DailyCostRecord {
  date: string
  cost: number
}

export interface DailyCostsResponse {
  profile_name: string
  start_date: string
  end_date: string
  daily_costs: DailyCostRecord[]
  total_cost: number
}

export interface ServiceCostRecord {
  service: string
  cost: number
}

export interface ServiceBreakdownResponse {
  profile_name: string
  start_date: string
  end_date: string
  services: ServiceCostRecord[]
  total_cost: number
}

export interface MonthlyTrendRecord {
  month: string
  cost: number
  mom_change_percent: number | null
}

export interface CostTrendResponse {
  profile_name: string
  months: number
  trend_data: MonthlyTrendRecord[]
}

export interface MoMComparison {
  current_month: {
    start: string
    end: string
    cost: number
  }
  previous_month: {
    start: string
    end: string
    cost: number
  }
  change_amount: number
  change_percent: number
}

export interface YoYComparison {
  current_period: {
    start: string
    end: string
    cost: number
  }
  previous_year_period: {
    start: string
    end: string
    cost: number
  }
  change_amount: number
  change_percent: number
}

export interface DailyForecastRecord {
  date: string
  forecasted_cost: number
}

export interface ForecastResponse {
  profile_name: string
  forecast_period_start: string
  forecast_period_end: string
  forecasted_cost: number
  currency: string
  error?: string
  daily_forecast?: DailyForecastRecord[]
}

export interface DashboardData {
  last_30_days: CostSummary
  current_month: CostSummary
  mom_comparison: MoMComparison
  forecast: ForecastResponse
}

export interface ProfileValidation {
  valid: boolean
  profile_name: string
  account_id?: string
  user_id?: string
  arn?: string
  error?: string
}

export interface DateRange {
  start: Date
  end: Date
}

export interface ChartDataPoint {
  name: string
  value: number
  date?: string
}

export interface DrillDownRecord {
  dimension_value: string
  cost: number
  percentage: number
}

export interface DrillDownResponse {
  profile_name: string
  start_date: string
  end_date: string
  dimension: string
  filters: Record<string, string>
  total_cost: number
  breakdown: DrillDownRecord[]
  currency: string
}

export interface DrillDownFilters {
  service?: string
  region?: string
  account_id?: string
}
