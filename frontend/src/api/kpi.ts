/**
 * KPI API client for AWS Cost Management
 */
import api from './axios'
import { KPIDefinition, KPIValue, KPIMetrics } from '@/types/kpi'

export const kpiApi = {
  /**
   * Get all KPI definitions
   */
  async getDefinitions(): Promise<Record<string, KPIDefinition>> {
    const response = await api.get('/kpi/definitions')
    return response.data
  },

  /**
   * Get a specific KPI definition
   */
  async getDefinition(kpiId: string): Promise<KPIDefinition> {
    const response = await api.get(`/kpi/definitions/${kpiId}`)
    return response.data
  },

  /**
   * Calculate all KPIs for a given profile
   */
  async calculateAllKPIs(profileName: string): Promise<Record<string, KPIValue>> {
    const response = await api.get(`/kpi/calculate/${encodeURIComponent(profileName)}`)
    return response.data
  },

  /**
   * Calculate a specific KPI for a given profile
   */
  async calculateKPI(profileName: string, kpiId: string): Promise<KPIValue> {
    const response = await api.get(
      `/kpi/calculate/${encodeURIComponent(profileName)}/${kpiId}`
    )
    return response.data
  },

  /**
   * Get complete KPI metrics including history
   */
  async getMetrics(
    profileName: string,
    kpiId: string,
    daysHistory: number = 30
  ): Promise<KPIMetrics> {
    const response = await api.get(
      `/kpi/metrics/${encodeURIComponent(profileName)}/${kpiId}`,
      { params: { days_history: daysHistory } }
    )
    return response.data
  },
}
