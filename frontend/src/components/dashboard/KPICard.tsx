import { ArrowUpIcon, ArrowDownIcon, DollarSign, TrendingUp, Calendar } from 'lucide-react'

interface KPICardProps {
  title: string
  value: string | number
  subtitle?: string
  trend?: {
    value: number
    isPositive: boolean
  }
  isLoading?: boolean
  icon?: 'dollar' | 'trending' | 'calendar'
  gradient?: string
}

export function KPICard({ title, value, subtitle, trend, isLoading, icon, gradient }: KPICardProps) {
  const getIcon = () => {
    switch (icon) {
      case 'dollar':
        return <DollarSign className="w-6 h-6" />
      case 'trending':
        return <TrendingUp className="w-6 h-6" />
      case 'calendar':
        return <Calendar className="w-6 h-6" />
      default:
        return <DollarSign className="w-6 h-6" />
    }
  }

  const gradientClass = gradient || 'from-blue-500 to-blue-600'

  if (isLoading) {
    return (
      <div className="card bg-modernGray-50">
        <div className="animate-pulse">
          <div className="h-4 bg-modernGray-200 rounded w-1/2 mb-4"></div>
          <div className="h-8 bg-modernGray-200 rounded w-3/4 mb-2"></div>
          <div className="h-3 bg-modernGray-200 rounded w-1/3"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="card border-l-4 border-trendRed-700 animate-fade-in">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-sm font-semibold text-modernGray-600 uppercase tracking-wide">{title}</h3>
        <div className={`p-2.5 rounded-card bg-gradient-to-br ${gradientClass} text-white shadow-md`}>
          {getIcon()}
        </div>
      </div>
      <p className="text-4xl font-bold text-modernGray-900 mb-1">{value}</p>
      {subtitle && <p className="text-sm text-modernGray-500 font-medium">{subtitle}</p>}
      {trend && (
        <div className="flex items-center mt-4 pt-4 border-t border-modernGray-200">
          {trend.isPositive ? (
            <div className="flex items-center px-2.5 py-1 bg-modernGreen-100 rounded-full">
              <ArrowDownIcon className="w-3 h-3 text-modernGreen-700" />
              <span className="text-xs ml-1 text-modernGreen-700 font-semibold">
                {Math.abs(trend.value).toFixed(1)}%
              </span>
            </div>
          ) : (
            <div className="flex items-center px-2.5 py-1 bg-modernRed-100 rounded-full">
              <ArrowUpIcon className="w-3 h-3 text-modernRed-700" />
              <span className="text-xs ml-1 text-modernRed-700 font-semibold">
                {Math.abs(trend.value).toFixed(1)}%
              </span>
            </div>
          )}
          <span className="text-xs text-modernGray-500 ml-2 font-medium">from last month</span>
        </div>
      )}
    </div>
  )
}
