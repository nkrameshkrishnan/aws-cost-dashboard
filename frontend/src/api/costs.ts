import api from './axios'
import {
  CostSummary,
  DailyCostsResponse,
  ServiceBreakdownResponse,
  CostTrendResponse,
  MoMComparison,
  YoYComparison,
  ForecastResponse,
  DashboardData,
  DrillDownResponse,
  DrillDownFilters,
} from '@/types'

export const costsApi = {
  /**
   * Get cost summary for a profile and date range
   */
  getSummary: async (
    profileName: string,
    startDate: string,
    endDate: string
  ): Promise<CostSummary> => {
    const response = await api.get('/costs/summary', {
      params: { profile_name: profileName, start_date: startDate, end_date: endDate },
    })
    return response.data
  },

  /**
   * Get daily cost breakdown
   */
  getDailyCosts: async (
    profileName: string,
    startDate: string,
    endDate: string
  ): Promise<DailyCostsResponse> => {
    const response = await api.get('/costs/daily', {
      params: { profile_name: profileName, start_date: startDate, end_date: endDate },
    })
    return response.data
  },

  /**
   * Get cost breakdown by AWS service
   */
  getServiceBreakdown: async (
    profileName: string,
    startDate: string,
    endDate: string,
    topN: number = 10
  ): Promise<ServiceBreakdownResponse> => {
    const response = await api.get('/costs/by-service', {
      params: {
        profile_name: profileName,
        start_date: startDate,
        end_date: endDate,
        top_n: topN,
      },
    })
    return response.data
  },

  /**
   * Get monthly cost trend
   */
  getCostTrend: async (
    profileName: string,
    months: number = 6
  ): Promise<CostTrendResponse> => {
    const response = await api.get('/costs/trend', {
      params: { profile_name: profileName, months },
    })
    return response.data
  },

  /**
   * Get month-over-month comparison
   */
  getMoMComparison: async (
    profileName: string,
    currentMonthStart: string,
    currentMonthEnd: string
  ): Promise<MoMComparison> => {
    const response = await api.get('/costs/mom-comparison', {
      params: {
        profile_name: profileName,
        current_month_start: currentMonthStart,
        current_month_end: currentMonthEnd,
      },
    })
    return response.data
  },

  /**
   * Get year-over-year comparison
   */
  getYoYComparison: async (
    profileName: string,
    currentPeriodStart: string,
    currentPeriodEnd: string
  ): Promise<YoYComparison> => {
    const response = await api.get('/costs/yoy-comparison', {
      params: {
        profile_name: profileName,
        current_period_start: currentPeriodStart,
        current_period_end: currentPeriodEnd,
      },
    })
    return response.data
  },

  /**
   * Get cost forecast
   */
  getForecast: async (
    profileName: string,
    days: number = 30,
    granularity: string = 'MONTHLY'
  ): Promise<ForecastResponse> => {
    const response = await api.get('/costs/forecast', {
      params: { profile_name: profileName, days, granularity },
    })
    return response.data
  },

  /**
   * Get all dashboard data in a single API call (optimized)
   * Returns: last 30 days cost, current month cost, MoM comparison, and forecast
   */
  getDashboardData: async (profileName: string): Promise<DashboardData> => {
    const response = await api.get('/costs/dashboard', {
      params: { profile_name: profileName },
    })
    return response.data
  },

  /**
   * Get cost drill-down by dimension with optional filters
   * Supports multi-level drill-down (e.g., SERVICE -> REGION -> LINKED_ACCOUNT)
   */
  getDrillDown: async (
    profileName: string,
    startDate: string,
    endDate: string,
    dimension: string,
    filters?: DrillDownFilters
  ): Promise<DrillDownResponse> => {
    const response = await api.get('/costs/drill-down', {
      params: {
        profile_name: profileName,
        start_date: startDate,
        end_date: endDate,
        dimension,
        service: filters?.service,
        region: filters?.region,
        account_id: filters?.account_id,
      },
    })
    return response.data
  },
}
