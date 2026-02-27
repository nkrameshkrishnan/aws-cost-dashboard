import { useMemo } from 'react'
import { AlertCircle, AlertTriangle, CheckCircle, TrendingUp, Bell } from 'lucide-react'
import type { BudgetStatus } from '@/api/budgets'

interface BudgetCardProps {
  status: BudgetStatus
  onClick?: () => void
  onSendAlert?: (budgetId: number) => void
}

export function BudgetCard({ status, onClick, onSendAlert }: BudgetCardProps) {
  const alertConfig = useMemo(() => {
    switch (status.alert_level) {
      case 'exceeded':
        return {
          color: 'red',
          icon: AlertCircle,
          bgColor: 'bg-red-50',
          borderColor: 'border-red-200',
          textColor: 'text-red-700',
          progressColor: 'bg-red-500',
          label: 'Budget Exceeded'
        }
      case 'critical':
        return {
          color: 'orange',
          icon: AlertTriangle,
          bgColor: 'bg-orange-50',
          borderColor: 'border-orange-200',
          textColor: 'text-orange-700',
          progressColor: 'bg-orange-500',
          label: 'Critical'
        }
      case 'warning':
        return {
          color: 'yellow',
          icon: AlertTriangle,
          bgColor: 'bg-yellow-50',
          borderColor: 'border-yellow-200',
          textColor: 'text-yellow-700',
          progressColor: 'bg-yellow-500',
          label: 'Warning'
        }
      default:
        return {
          color: 'green',
          icon: CheckCircle,
          bgColor: 'bg-green-50',
          borderColor: 'border-green-200',
          textColor: 'text-green-700',
          progressColor: 'bg-green-500',
          label: 'On Track'
        }
    }
  }, [status.alert_level])

  const Icon = alertConfig.icon

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(amount)
  }

  const formatPeriod = (period: string) => {
    return period.charAt(0).toUpperCase() + period.slice(1)
  }

  return (
    <div
      className={`card border-l-4 ${alertConfig.borderColor} ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-4 gap-3 pr-8">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-gray-900 truncate">{status.budget_name}</h3>
          <p className="text-sm text-gray-500">{formatPeriod(status.period)} Budget</p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1 ${alertConfig.bgColor} rounded-full flex-shrink-0`}>
          <Icon className={`w-4 h-4 ${alertConfig.textColor}`} />
          <span className={`text-xs font-medium ${alertConfig.textColor} whitespace-nowrap`}>
            {alertConfig.label}
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="font-medium text-gray-700">
            {formatCurrency(status.current_spend)} of {formatCurrency(status.budget_amount)}
          </span>
          <span className={`font-semibold ${alertConfig.textColor}`}>
            {status.percentage_used.toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className={`h-full ${alertConfig.progressColor} transition-all duration-500`}
            style={{ width: `${Math.min(status.percentage_used, 100)}%` }}
          />
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-gray-500">Remaining</p>
          <p className="font-semibold text-gray-900">
            {formatCurrency(status.remaining)}
          </p>
        </div>
        {status.days_remaining !== null && status.days_remaining !== undefined && (
          <div>
            <p className="text-gray-500">Days Left</p>
            <p className="font-semibold text-gray-900">{status.days_remaining}</p>
          </div>
        )}
      </div>

      {/* Projection Warning */}
      {status.is_projected_to_exceed && status.projected_spend && (
        <div className={`mt-4 flex items-start gap-2 p-3 ${alertConfig.bgColor} rounded`}>
          <TrendingUp className={`w-4 h-4 ${alertConfig.textColor} mt-0.5 flex-shrink-0`} />
          <div className="text-sm">
            <p className={`font-medium ${alertConfig.textColor}`}>
              Projected to exceed budget
            </p>
            <p className="text-gray-600 mt-0.5">
              Estimated spend: {formatCurrency(status.projected_spend)} ({status.projected_percentage?.toFixed(1)}%)
            </p>
          </div>
        </div>
      )}

      {/* Send Alert Button */}
      {onSendAlert && status.percentage_used >= 50 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onSendAlert(status.budget_id)
            }}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded transition-colors"
            title="Send alert to configured Teams webhooks"
          >
            <Bell className="w-4 h-4" />
            <span>Send Teams Alert</span>
          </button>
        </div>
      )}
    </div>
  )
}
