/**
 * KPI (Key Performance Indicators) Type Definitions for AWS Cost Management
 */

export type KPICategory =
  | 'cost_efficiency'
  | 'budget_performance'
  | 'savings_rate'
  | 'cost_trend'
  | 'resource_optimization'
  | 'spend_velocity'

export type KPIStatus = 'excellent' | 'good' | 'warning' | 'poor' | 'unknown'

export interface KPIThreshold {
  excellent: number
  good: number
  warning: number
  poor: number
}

export interface KPIDefinition {
  id: string
  category: KPICategory
  name: string
  description: string
  unit: string
  thresholds: KPIThreshold
  format: 'number' | 'percentage' | 'currency' | 'duration'
  higher_is_better: boolean
}

export interface KPIValue {
  category: KPICategory
  value: number
  status: KPIStatus
  trend: 'up' | 'down' | 'stable'
  previous_value?: number
  profile_name?: string
  calculated_at: string
  target_value?: number
}

export interface KPITrend {
  date: string
  value: number
  status: KPIStatus
}

export interface KPIMetrics {
  kpi: KPIDefinition
  current: KPIValue
  history: KPITrend[]
  target_value?: number
}

// Helper function to get status color
export function getKPIStatusColor(status: KPIStatus): string {
  switch (status) {
    case 'excellent':
      return 'modernGreen'
    case 'good':
      return 'modernTeal'
    case 'warning':
      return 'modernYellow'
    case 'poor':
      return 'modernRed'
    default:
      return 'modernGray'
  }
}

// Helper function to format KPI value
export function formatKPIValue(value: number, format: string): string {
  switch (format) {
    case 'currency':
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(value)
    case 'percentage':
      return `${value.toFixed(1)}%`
    case 'duration':
      if (value < 60) {
        return `${value.toFixed(0)} min`
      } else if (value < 1440) {
        return `${(value / 60).toFixed(1)} hours`
      } else {
        return `${(value / 1440).toFixed(1)} days`
      }
    case 'number':
    default:
      return value.toFixed(2)
  }
}

// Helper function to get trend icon
export function getTrendIcon(trend: string): '↑' | '↓' | '→' {
  switch (trend) {
    case 'up':
      return '↑'
    case 'down':
      return '↓'
    default:
      return '→'
  }
}
