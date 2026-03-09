import { AlertTriangle, TrendingUp, ExternalLink } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { Anomaly } from '@/api/analytics'

interface AnomalyAlertWidgetProps {
  anomalies: Anomaly[]
  isLoading?: boolean
}

export function AnomalyAlertWidget({ anomalies, isLoading }: AnomalyAlertWidgetProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="card border-l-4 border-orange-500 animate-pulse">
        <div className="h-20 bg-gray-100 rounded"></div>
      </div>
    )
  }

  const criticalAnomalies = anomalies.filter(a => a.severity === 'critical' || a.severity === 'high')

  if (anomalies.length === 0) {
    return (
      <div className="card border-l-4 border-green-500 bg-gradient-to-r from-green-50 to-emerald-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-green-500 rounded-lg">
              <TrendingUp className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">No Cost Anomalies Detected</h3>
              <p className="text-sm text-gray-600">Your costs are following normal patterns</p>
            </div>
          </div>
          <button
            onClick={() => navigate('/analytics')}
            className="text-sm text-green-700 hover:text-green-800 font-medium flex items-center gap-1"
          >
            View Analytics
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="card border-l-4 border-orange-500 bg-gradient-to-r from-orange-50 to-red-50">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-orange-500 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Cost Anomalies Detected</h3>
            <p className="text-sm text-gray-600">
              {anomalies.length} unusual cost pattern{anomalies.length !== 1 ? 's' : ''} found
              {criticalAnomalies.length > 0 && (
                <span className="ml-2 text-red-600 font-semibold">
                  ({criticalAnomalies.length} critical)
                </span>
              )}
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/analytics')}
          className="text-sm text-orange-700 hover:text-orange-800 font-medium flex items-center gap-1"
        >
          Investigate
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>

      {/* Show top 3 critical anomalies */}
      <div className="space-y-2">
        {criticalAnomalies.slice(0, 3).map((anomaly, index) => (
          <div
            key={index}
            className="flex items-center justify-between p-3 bg-white rounded-lg border border-orange-200"
          >
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
                    anomaly.severity === 'critical'
                      ? 'bg-red-100 text-red-800'
                      : 'bg-orange-100 text-orange-800'
                  }`}
                >
                  {anomaly.severity.toUpperCase()}
                </span>
                <span className="text-sm font-medium text-gray-900">{anomaly.date}</span>
              </div>
              <p className="text-sm text-gray-600">{anomaly.description}</p>
            </div>
            <div className="text-right ml-4">
              <div className="text-lg font-bold text-gray-900">${(anomaly.cost ?? 0).toFixed(2)}</div>
              {anomaly.percentage_change && (
                <div className="text-sm text-red-600 font-semibold">
                  +{anomaly.percentage_change.toFixed(1)}%
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {anomalies.length > 3 && (
        <div className="mt-3 text-center">
          <button
            onClick={() => navigate('/analytics')}
            className="text-sm text-orange-700 hover:text-orange-800 font-semibold"
          >
            View all {anomalies.length} anomalies →
          </button>
        </div>
      )}
    </div>
  )
}
