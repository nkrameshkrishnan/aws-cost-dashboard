import api from './axios'

export interface HistoricalDataPoint {
  date: string
  cost: number
}

export interface ServiceCostDataPoint {
  date: string
  cost: number
  service: string
}

export interface ForecastPrediction {
  date: string
  predicted_cost: number
  lower_bound: number
  upper_bound: number
  confidence: string
}

export interface AccuracyMetrics {
  r_squared: number
  p_value?: number
  std_error?: number
  mae?: number
  mape?: number
  rmse?: number
}

export interface ForecastResponse {
  method: string
  r_squared?: number
  trend?: string
  daily_change?: number
  predictions: ForecastPrediction[]
  accuracy_metrics: AccuracyMetrics
}

export interface ForecastRequest {
  historical_data: HistoricalDataPoint[]
  days_ahead?: number
  method?: 'linear' | 'moving_average' | 'exponential_smoothing' | 'ensemble'
}

export interface Anomaly {
  date: string
  cost: number
  baseline_cost?: number
  z_score?: number
  iqr_value?: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  type: string
  delta?: number
  percentage_change?: number
  description: string
  service?: string
}

export interface AnomalyDetectionResponse {
  anomalies: Anomaly[]
  method: string
  total_anomalies?: number
}

export interface AnomalyDetectionRequest {
  historical_data: HistoricalDataPoint[]
  method?: 'z_score' | 'iqr' | 'spike' | 'drift' | 'all'
  threshold?: number
  spike_threshold?: number
  drift_window?: number
}

export interface ServiceAnomalyDetectionRequest {
  service_data: ServiceCostDataPoint[]
  threshold?: number
}

export interface SeasonalityResponse {
  has_seasonality: boolean
  seasonal_period?: number
  seasonal_strength?: number
  trend_strength?: number
  description: string
}

export interface SeasonalityRequest {
  historical_data: HistoricalDataPoint[]
}

export interface AWSForecastResponse {
  account_name: string
  forecast_method: 'aws_api' | 'statistical'
  forecast_period_days: number
  predictions: ForecastPrediction[]
  total_forecasted_cost: number
  confidence_level: string
  generated_at: string
}

export interface ComparisonData {
  current_period: {
    start_date: string
    end_date: string
    total_cost: number
  }
  previous_period: {
    start_date: string
    end_date: string
    total_cost: number
  }
  change: {
    absolute: number
    percentage: number
  }
  trend: 'increasing' | 'decreasing' | 'stable'
}

export interface MoMComparisonResponse {
  account_name: string
  comparison: ComparisonData
  generated_at: string
}

export interface YoYComparisonResponse {
  account_name: string
  comparison: ComparisonData
  generated_at: string
}

export const analyticsApi = {
  /**
   * Generate cost forecast
   */
  async forecast(request: ForecastRequest): Promise<ForecastResponse> {
    const response = await api.post('/analytics/forecast', request)
    return response.data
  },

  /**
   * Detect cost anomalies
   */
  async detectAnomalies(request: AnomalyDetectionRequest): Promise<AnomalyDetectionResponse> {
    const response = await api.post('/analytics/anomalies', request)
    return response.data
  },

  /**
   * Detect service-specific anomalies
   */
  async detectServiceAnomalies(
    request: ServiceAnomalyDetectionRequest
  ): Promise<AnomalyDetectionResponse> {
    const response = await api.post('/analytics/service-anomalies', request)
    return response.data
  },

  /**
   * Detect seasonality patterns
   */
  async detectSeasonality(request: SeasonalityRequest): Promise<SeasonalityResponse> {
    const response = await api.post('/analytics/seasonality', request)
    return response.data
  },

  /**
   * Get AWS Cost Forecast (with fallback to statistical forecast)
   */
  async getAWSForecast(
    accountName: string,
    days: number = 30,
    useFallback: boolean = false
  ): Promise<AWSForecastResponse> {
    const response = await api.get('/analytics/aws/forecast', {
      params: {
        account_name: accountName,
        days,
        use_fallback: useFallback,
      },
    })
    return response.data
  },

  /**
   * Get Month-over-Month cost comparison
   */
  async getMoMComparison(accountName: string): Promise<MoMComparisonResponse> {
    const response = await api.get('/analytics/aws/comparison/mom', {
      params: {
        account_name: accountName,
      },
    })
    return response.data
  },

  /**
   * Get Year-over-Year cost comparison
   */
  async getYoYComparison(accountName: string): Promise<YoYComparisonResponse> {
    const response = await api.get('/analytics/aws/comparison/yoy', {
      params: {
        account_name: accountName,
      },
    })
    return response.data
  },
}
