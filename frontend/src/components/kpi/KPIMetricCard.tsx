/**
 * KPI Metric Card Component
 * Displays an individual KPI metric with status, trend, and value
 */
import { KPIValue, KPIDefinition, getKPIStatusColor, formatKPIValue, getTrendIcon } from '@/types/kpi'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface KPIMetricCardProps {
  kpi: KPIDefinition
  value: KPIValue
  isLoading?: boolean
}

export function KPIMetricCard({ kpi, value, isLoading }: KPIMetricCardProps) {
  if (isLoading) {
    return (
      <div className="card bg-modernGray-50">
        <div className="animate-pulse">
          <div className="h-4 bg-modernGray-200 rounded w-2/3 mb-4"></div>
          <div className="h-10 bg-modernGray-200 rounded w-1/2 mb-3"></div>
          <div className="h-3 bg-modernGray-200 rounded w-full"></div>
        </div>
      </div>
    )
  }

  const statusColor = getKPIStatusColor(value.status)
  const formattedValue = formatKPIValue(value.value, kpi.format)

  // Get status badge color
  const getBadgeClass = () => {
    switch (value.status) {
      case 'excellent':
        return 'bg-modernGreen-100 text-modernGreen-800 border-modernGreen-300'
      case 'good':
        return 'bg-modernTeal-100 text-modernTeal-800 border-modernTeal-300'
      case 'warning':
        return 'bg-modernYellow-100 text-modernYellow-800 border-modernYellow-300'
      case 'poor':
        return 'bg-modernRed-100 text-modernRed-800 border-modernRed-300'
      default:
        return 'bg-modernGray-100 text-modernGray-800 border-modernGray-300'
    }
  }

  // Get trend icon and color
  const getTrendDisplay = () => {
    switch (value.trend) {
      case 'up':
        return {
          icon: <TrendingUp className="w-4 h-4" />,
          color: kpi.higher_is_better ? 'text-modernGreen-700' : 'text-modernRed-700',
          bg: kpi.higher_is_better ? 'bg-modernGreen-100' : 'bg-modernRed-100'
        }
      case 'down':
        return {
          icon: <TrendingDown className="w-4 h-4" />,
          color: kpi.higher_is_better ? 'text-modernRed-700' : 'text-modernGreen-700',
          bg: kpi.higher_is_better ? 'bg-modernRed-100' : 'bg-modernGreen-100'
        }
      default:
        return {
          icon: <Minus className="w-4 h-4" />,
          color: 'text-modernGray-600',
          bg: 'bg-modernGray-100'
        }
    }
  }

  const trendDisplay = getTrendDisplay()

  // Get border color for card accent
  const getBorderColor = () => {
    switch (value.status) {
      case 'excellent':
        return 'border-l-modernGreen-600'
      case 'good':
        return 'border-l-modernTeal-600'
      case 'warning':
        return 'border-l-modernYellow-600'
      case 'poor':
        return 'border-l-modernRed-600'
      default:
        return 'border-l-modernGray-400'
    }
  }

  return (
    <div className={`card border-l-4 ${getBorderColor()} animate-fade-in`}>
      {/* Header with status badge */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-modernGray-600 uppercase tracking-wide mb-1">
            {kpi.name}
          </h3>
          <p className="text-xs text-modernGray-500">{kpi.description}</p>
        </div>
        <span
          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getBadgeClass()}`}
        >
          {value.status}
        </span>
      </div>

      {/* Value display */}
      <div className="mb-4">
        <div className="flex items-baseline gap-2">
          <p className="text-4xl font-bold text-modernGray-900">{formattedValue}</p>
          {value.target_value && (
            <p className="text-sm text-modernGray-500">
              / {formatKPIValue(value.target_value, kpi.format)} target
            </p>
          )}
        </div>
      </div>

      {/* Trend indicator */}
      <div className="flex items-center gap-2 pt-3 border-t border-modernGray-200">
        <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${trendDisplay.bg}`}>
          <span className={trendDisplay.color}>{trendDisplay.icon}</span>
          <span className={`text-xs font-semibold ${trendDisplay.color}`}>
            {value.trend === 'stable' ? 'Stable' : `Trending ${value.trend}`}
          </span>
        </div>
        {value.previous_value !== undefined && value.previous_value !== null && (
          <span className="text-xs text-modernGray-500">
            from {formatKPIValue(value.previous_value, kpi.format)}
          </span>
        )}
      </div>
    </div>
  )
}
