import { TrendingUp, TrendingDown, ExternalLink, Activity } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { ForecastResponse } from '@/api/analytics'
import { format, parseISO } from 'date-fns'

interface QuickForecastWidgetProps {
  forecast: ForecastResponse | null
  isLoading?: boolean
}

export function QuickForecastWidget({ forecast, isLoading }: QuickForecastWidgetProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="card border-l-4 border-blue-500 animate-pulse">
        <div className="h-32 bg-gray-100 rounded"></div>
      </div>
    )
  }

  if (!forecast || !Array.isArray(forecast.predictions) || forecast.predictions.length === 0) {
    return null
  }

  const next7Days = forecast.predictions.slice(0, 7)
  const avgDailyCost = next7Days.reduce((sum, p) => sum + p.predicted_cost, 0) / next7Days.length
  const totalForecast = next7Days.reduce((sum, p) => sum + p.predicted_cost, 0)

  return (
    <div className="card border-l-4 border-blue-500 bg-gradient-to-r from-blue-50 to-indigo-50">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-blue-500 rounded-lg">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">7-Day Cost Forecast</h3>
            <p className="text-sm text-gray-600">
              AI-powered prediction · {(forecast.r_squared! * 100).toFixed(0)}% accuracy
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/analytics')}
          className="text-sm text-blue-700 hover:text-blue-800 font-medium flex items-center gap-1"
        >
          Full Analytics
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>

      {/* Forecast Summary */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-white p-4 rounded-lg border border-blue-200">
          <div className="text-sm text-gray-600 mb-1">Next 7 Days</div>
          <div className="text-2xl font-bold text-gray-900">${totalForecast.toFixed(0)}</div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-blue-200">
          <div className="text-sm text-gray-600 mb-1">Avg Daily</div>
          <div className="text-2xl font-bold text-gray-900">${avgDailyCost.toFixed(2)}</div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-blue-200">
          <div className="text-sm text-gray-600 mb-1">Trend</div>
          <div className="flex items-center gap-2">
            {forecast.trend === 'increasing' ? (
              <>
                <TrendingUp className="w-5 h-5 text-red-500" />
                <span className="text-xl font-bold text-red-600">
                  +${Math.abs(forecast.daily_change || 0).toFixed(2)}
                </span>
              </>
            ) : (
              <>
                <TrendingDown className="w-5 h-5 text-green-500" />
                <span className="text-xl font-bold text-green-600">
                  -${Math.abs(forecast.daily_change || 0).toFixed(2)}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Mini Chart - Daily Predictions */}
      <div className="bg-white p-3 rounded-lg border border-blue-200">
        <div className="text-xs text-gray-500 font-semibold mb-2">Daily Predictions</div>
        <div className="flex items-end justify-between gap-1 h-16">
          {next7Days.map((pred, index) => {
            const maxCost = Math.max(...next7Days.map(p => p.predicted_cost))
            const height = (pred.predicted_cost / maxCost) * 100

            return (
              <div key={index} className="flex-1 flex flex-col items-center">
                <div
                  className="w-full bg-gradient-to-t from-blue-500 to-blue-400 rounded-t transition-all hover:from-blue-600 hover:to-blue-500"
                  style={{ height: `${height}%` }}
                  title={`${format(parseISO(pred.date), 'MMM dd')}: $${pred.predicted_cost.toFixed(2)}`}
                />
                <div className="text-xs text-gray-500 mt-1">
                  {format(parseISO(pred.date), 'dd')}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Method Info */}
      <div className="mt-3 text-center">
        <span className="text-xs text-gray-500">
          Method: <span className="font-semibold">{forecast.method.replace(/_/g, ' ').toUpperCase()}</span>
        </span>
      </div>
    </div>
  )
}
