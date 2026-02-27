import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Activity,
  BarChart3,
  Calendar,
  Settings,
  Play,
  RefreshCw,
  ArrowLeft,
  Home,
  DollarSign,
  Search,
  Cloud,
  Cog,
  Zap,
  Download,
  FileSpreadsheet,
} from 'lucide-react'
import { analyticsApi, type AnomalyDetectionRequest } from '@/api/analytics'
import { costsApi } from '@/api/costs'
import { awsAccountsApi } from '@/api/awsAccounts'
import { exportApi } from '@/api/export'
import { useProfileStore } from '@/store/profileStore'
import { ProfileSelector } from '@/components/common/ProfileSelector'
import { InfoModal } from '@/components/common/InfoModal'
import { LoadingPage } from '@/components/common/LoadingPage'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { useForecastAnalytics } from '@/hooks/useForecastAnalytics'
import { format, subDays, parseISO } from 'date-fns'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts'

export function Analytics() {
  const navigate = useNavigate()
  const { selectedProfile } = useProfileStore()
  const [anomalyMethod, setAnomalyMethod] = useState<'z_score' | 'iqr' | 'spike' | 'drift' | 'all'>('all')
  const [anomalyThreshold, setAnomalyThreshold] = useState(2.5)
  const [awsForecastDays, setAwsForecastDays] = useState(30)

  // S3 export states

  // Check for AWS accounts
  const { data: awsAccounts, isLoading: loadingAccounts } = useQuery({
    queryKey: ['awsAccounts'],
    queryFn: () => awsAccountsApi.list(),
    retry: 1,
  })
  const hasAccounts = awsAccounts && awsAccounts.length > 0

  // AWS-integrated forecast analytics
  const { forecast: awsForecast, isLoading: loadingAwsAnalytics } = useForecastAnalytics(
    selectedProfile,
    awsForecastDays,
    hasAccounts && !!selectedProfile
  )

  // Fetch historical cost data (last 90 days)
  const startDate = format(subDays(new Date(), 90), 'yyyy-MM-dd')
  const endDate = format(new Date(), 'yyyy-MM-dd')

  const { data: dailyCosts, isLoading: loadingCosts } = useQuery({
    queryKey: ['dailyCosts', selectedProfile, startDate, endDate],
    queryFn: () => costsApi.getDailyCosts(selectedProfile, startDate, endDate),
    enabled: hasAccounts && !!selectedProfile,
  })

  // Prepare historical data for analytics
  const historicalData = dailyCosts?.daily_costs?.map((item: any) => ({
    date: item.date,
    cost: item.cost,
  })) || []

  // Anomaly detection mutation
  const anomalyMutation = useMutation({
    mutationFn: (request: AnomalyDetectionRequest) => analyticsApi.detectAnomalies(request),
  })

  // PDF Export mutation
  const exportPDFMutation = useMutation({
    mutationFn: async () => {
      // Read S3 configuration from Settings
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      const s3Bucket = localStorage.getItem('s3ExportBucket') || ''

      const endDate = format(new Date(), 'yyyy-MM-dd')
      const startDate = format(subDays(new Date(), 30), 'yyyy-MM-dd')
      return exportApi.exportForecastPDF(
        selectedProfile,
        startDate,
        endDate,
        awsForecastDays,
        uploadToS3,
        uploadToS3 ? s3Bucket : undefined
      )
    },
    onSuccess: (data: any) => {
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      if (uploadToS3) {
        const response = data as { success: boolean; message: string; s3_url?: string; file_name?: string }
        if (response.s3_url) {
          alert(`✅ ${response.message}\n\nS3 URL: ${response.s3_url}\nFile: ${response.file_name}`)
        } else {
          alert(`✅ ${response.message}`)
        }
      } else {
        const blob = data as Blob
        const fileName = exportApi.generateExportFileName('forecast_report', selectedProfile, 'pdf')
        exportApi.downloadBlob(blob, fileName)
        alert(`✅ PDF forecast report downloaded: ${fileName}`)
      }
    },
    onError: (error: any) => {
      alert(`❌ Failed to export PDF: ${error.response?.data?.detail || error.message || 'Unknown error'}`)
    }
  })

  // Excel Export mutation
  const exportExcelMutation = useMutation({
    mutationFn: async () => {
      // Read S3 configuration from Settings
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      const s3Bucket = localStorage.getItem('s3ExportBucket') || ''

      const endDate = format(new Date(), 'yyyy-MM-dd')
      const startDate = format(subDays(new Date(), 30), 'yyyy-MM-dd')
      return exportApi.exportForecastExcel(
        selectedProfile,
        startDate,
        endDate,
        awsForecastDays,
        uploadToS3,
        uploadToS3 ? s3Bucket : undefined
      )
    },
    onSuccess: (data: any) => {
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      if (uploadToS3) {
        const response = data as { success: boolean; message: string; s3_url?: string; file_name?: string }
        if (response.s3_url) {
          alert(`✅ ${response.message}\n\nS3 URL: ${response.s3_url}\nFile: ${response.file_name}`)
        } else {
          alert(`✅ ${response.message}`)
        }
      } else {
        const blob = data as Blob
        const fileName = exportApi.generateExportFileName('forecast_report', selectedProfile, 'xlsx')
        exportApi.downloadBlob(blob, fileName)
        alert(`✅ Excel forecast report downloaded: ${fileName}`)
      }
    },
    onError: (error: any) => {
      alert(`❌ Failed to export Excel: ${error.response?.data?.detail || error.message || 'Unknown error'}`)
    }
  })

  // Run anomaly detection
  const runAnomalyDetection = () => {
    if (historicalData.length > 0) {
      anomalyMutation.mutate({
        historical_data: historicalData,
        method: anomalyMethod,
        threshold: anomalyThreshold,
      })
    }
  }

  // Get anomalies
  const anomalies = anomalyMutation.data?.anomalies || []
  const criticalAnomalies = anomalies.filter((a) => a.severity === 'critical' || a.severity === 'high')

  if (!loadingAccounts && !hasAccounts) {
    return (
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8 flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Advanced Analytics</h1>
            <p className="text-gray-600 mt-2">AWS Cost Explorer forecasting and anomaly detection</p>
          </div>
          <div className="flex items-center gap-3">
            <ProfileSelector />
          </div>
        </div>

        <div className="card mb-8 bg-gradient-to-r from-yellow-50 to-amber-50 border-l-4 border-yellow-500">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-yellow-500 rounded-lg">
              <AlertTriangle className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No AWS Accounts Configured</h3>
              <p className="text-gray-700 mb-4">
                To use analytics features like AWS Cost Explorer forecasting and anomaly detection, you need to add at least one
                AWS account first.
              </p>
              <button
                onClick={() => navigate('/aws-accounts')}
                className="btn-primary flex items-center gap-2"
              >
                <Cloud className="w-4 h-4" />
                Add AWS Account
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-gray-900">Advanced Analytics</h1>
            <InfoModal
              content="Advanced analytics provides AWS Cost Explorer's ML-powered forecasting and statistical anomaly detection to predict future costs and identify unusual spending patterns."
              variant="blue"
            />
          </div>
          <p className="text-gray-600 mt-2">Cost forecasting, anomaly detection, and trend analysis</p>
        </div>
        <div className="flex items-center gap-3">
          <ProfileSelector />
        </div>
      </div>

      {/* Export Section */}
      {hasAccounts && selectedProfile && (
        <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border-2 border-blue-200 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-1">Export Forecast Reports</h3>
              <p className="text-sm text-gray-600">
                Download or upload to S3 (configure in Settings)
              </p>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => exportPDFMutation.mutate()}
                className="btn-secondary flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download PDF
              </button>
              <button
                type="button"
                onClick={() => exportExcelMutation.mutate()}
                className="btn-secondary flex items-center gap-2"
              >
                <FileSpreadsheet className="w-4 h-4" />
                Download Excel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600 text-sm">Historical Data Points</span>
            <Activity className="w-5 h-5 text-trendRed-700" />
          </div>
          <div className="text-2xl font-bold text-gray-900">{historicalData.length}</div>
          <div className="text-sm text-gray-500 mt-1">Last 90 days</div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600 text-sm">Anomalies Detected</span>
            <AlertTriangle className="w-5 h-5 text-orange-500" />
          </div>
          <div className="text-2xl font-bold text-gray-900">{anomalies.length}</div>
          <div className="text-sm text-gray-500 mt-1">{criticalAnomalies.length} critical</div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600 text-sm">AWS Forecast</span>
            <TrendingUp className="w-5 h-5 text-modernTeal-700" />
          </div>
          <div className="text-2xl font-bold text-gray-900">
            {awsForecast.data?.total_forecasted_cost
              ? `$${awsForecast.data.total_forecasted_cost.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
              : '-'}
          </div>
          <div className="text-sm text-gray-500 mt-1">Next {awsForecastDays} days</div>
        </div>
      </div>

      {/* AWS-Integrated Forecast Section */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-xl font-bold text-gray-900">AWS Cost Explorer Forecast</h2>
              <InfoModal
                content={`What is AWS Cost Explorer Forecast?

This section uses Amazon's native Cost Explorer Forecast API for the most accurate cost predictions available. AWS uses sophisticated machine learning models trained on your actual usage patterns and AWS service pricing data.

How It Works:
• Primary: AWS Cost Explorer Forecast API provides ML-powered predictions
• Fallback: If AWS forecast is unavailable, uses statistical linear regression
• Confidence Intervals: Shows 95% prediction range for forecasted costs
• Trend Analysis: Identifies if costs are increasing, decreasing, or stable

Key Benefits vs Statistical Methods:
• More Accurate: Trained on your actual AWS account patterns
• Service-Aware: Understands AWS service pricing and billing cycles
• Real-Time: Reflects current usage trends and seasonality
• Official: Uses Amazon's own forecasting engine

Comparison Features:
• Month-over-Month (MoM): Compare current month to previous month
• Year-over-Year (YoY): Compare to same period last year
• Trend Indicators: Visual representation of cost direction`}
                variant="teal"
              />
            </div>
            <p className="text-gray-600 text-sm">ML-powered predictions from AWS Cost Explorer API</p>
          </div>
        </div>

        {/* Forecast Configuration */}
        <div className="mb-6 p-4 bg-modernTeal-50 rounded-lg border border-modernTeal-200">
          <label htmlFor="aws-forecast-days" className="block text-sm font-medium text-gray-700 mb-2">
            <Calendar className="w-4 h-4 inline mr-2" />
            AWS Forecast Horizon
          </label>
          <select
            id="aws-forecast-days"
            value={awsForecastDays}
            onChange={(e) => setAwsForecastDays(parseInt(e.target.value))}
            className="input max-w-xs"
          >
            <option value="7">7 days</option>
            <option value="14">14 days</option>
            <option value="30">30 days</option>
            <option value="60">60 days</option>
            <option value="90">90 days</option>
          </select>
        </div>

        {/* AWS Forecast Results */}
        {loadingAwsAnalytics ? (
          <div className="h-64 flex items-center justify-center">
            <div className="animate-pulse text-gray-500">Loading AWS forecast data...</div>
          </div>
        ) : awsForecast.data ? (
          <div>
            {/* Forecast Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="p-4 bg-gradient-to-br from-trendRed-50 to-modernTeal-50 rounded-lg border border-trendRed-200">
                <div className="text-sm text-gray-600 mb-1">Forecast Method</div>
                <div className="text-lg font-bold text-trendRed-700">
                  {awsForecast.data.forecast_method === 'aws_api' ? '🤖 AWS ML Model' : '📊 Statistical Fallback'}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {awsForecast.data.forecast_method === 'aws_api'
                    ? 'Using Cost Explorer Forecast API'
                    : 'Linear regression fallback'}
                </div>
              </div>

              <div className="p-4 bg-gradient-to-br from-modernTeal-50 to-modernGreen-50 rounded-lg border border-modernTeal-200">
                <div className="text-sm text-gray-600 mb-1">Total Forecasted Cost</div>
                <div className="text-2xl font-bold text-modernTeal-700">
                  ${(awsForecast.data.total_forecasted_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <div className="text-xs text-gray-500 mt-1">Next {awsForecast.data.forecast_period_days || 30} days</div>
              </div>

              <div className="p-4 bg-gradient-to-br from-modernGreen-50 to-modernTeal-50 rounded-lg border border-modernGreen-200">
                <div className="text-sm text-gray-600 mb-1">Confidence Level</div>
                <div className="text-lg font-bold text-modernGreen-700">{awsForecast.data.confidence_level || '95%'}</div>
                <div className="text-xs text-gray-500 mt-1">Prediction reliability</div>
              </div>
            </div>

            {/* Forecast Chart */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Daily Cost Predictions</h3>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={(awsForecast.data.predictions || []).map(p => ({
                  date: format(parseISO(p.date), 'MMM dd'),
                  predicted: p.predicted_cost || 0,
                  lower: p.lower_bound || 0,
                  upper: p.upper_bound || 0,
                }))}>
                  <defs>
                    <linearGradient id="predictedGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00CDB9" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#00CDB9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#6b7280" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#6b7280" tickFormatter={(value) => `$${value.toFixed(0)}`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                    formatter={(value: any) => [`$${value.toFixed(2)}`, '']}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="upper"
                    stroke="#FFCD00"
                    fill="none"
                    strokeDasharray="3 3"
                    strokeWidth={1.5}
                    name="Upper Bound (95%)"
                  />
                  <Area
                    type="monotone"
                    dataKey="predicted"
                    stroke="#00CDB9"
                    fill="url(#predictedGradient)"
                    strokeWidth={3}
                    name="Predicted Cost"
                  />
                  <Area
                    type="monotone"
                    dataKey="lower"
                    stroke="#FFCD00"
                    fill="none"
                    strokeDasharray="3 3"
                    strokeWidth={1.5}
                    name="Lower Bound (95%)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : awsForecast.error ? (
          <div className="p-6 bg-red-50 border border-red-200 rounded-lg text-center">
            <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-2" />
            <p className="text-red-900 font-semibold mb-1">Failed to load AWS forecast</p>
            <p className="text-sm text-red-700">{String(awsForecast.error)}</p>
          </div>
        ) : (
          <div className="p-6 bg-gray-50 rounded-lg text-center text-gray-600">
            Select an AWS account to view forecast
          </div>
        )}
      </div>

      {/* Anomaly Detection Section */}
      <div className="card mt-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-xl font-bold text-gray-900">Anomaly Detection</h2>
              <InfoModal
                content={`What is Anomaly Detection?

Anomaly detection uses statistical methods to identify unusual spending patterns that deviate significantly from your normal cost behavior. This helps you catch unexpected charges, misconfigurations, or security issues early.

Detection Methods:
• Z-Score: Identifies outliers based on standard deviation from the mean
• IQR (Interquartile Range): Detects outliers using statistical quartiles
• Spike Detection: Finds sudden increases in spending
• Drift Detection: Identifies gradual trend changes over time
• All Methods (Recommended): Runs all detection algorithms for comprehensive analysis

Severity Levels:
• Critical: Extremely unusual spending, requires immediate attention
• High: Significant deviation from normal, investigate soon
• Medium: Noticeable anomaly, monitor closely
• Low: Minor deviation, may be expected variance

How to Use:
1. Select an anomaly detection method or use All
2. Adjust the threshold (higher = fewer false positives, lower = more sensitive)
3. Click "Detect Anomalies" to scan your cost history
4. Review flagged anomalies with dates, amounts, and severity ratings

Default threshold of 2.5 standard deviations catches significant anomalies while minimizing false alarms.`}
                variant="blue"
              />
            </div>
            <p className="text-gray-600 text-sm">Identify unusual cost patterns and spikes</p>
          </div>
          <button
            type="button"
            onClick={runAnomalyDetection}
            disabled={loadingCosts || !hasAccounts}
            className="btn-secondary flex items-center gap-2"
          >
            {anomalyMutation.isPending ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Scanning...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Detect Anomalies
              </>
            )}
          </button>
        </div>

        {/* Anomaly Configuration */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <BarChart3 className="w-4 h-4 inline mr-2" />
              Detection Algorithm
            </label>
            <select
              value={anomalyMethod}
              onChange={(e) => setAnomalyMethod(e.target.value as any)}
              className="input"
              aria-label="Detection Algorithm"
            >
              <option value="all">All Methods (Recommended)</option>
              <option value="z_score">Z-Score Analysis</option>
              <option value="iqr">IQR Method</option>
              <option value="spike">Sudden Spike Detection</option>
              <option value="drift">Cost Drift Detection</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Settings className="w-4 h-4 inline mr-2" />
              Sensitivity Threshold
            </label>
            <select
              value={anomalyThreshold}
              onChange={(e) => setAnomalyThreshold(parseFloat(e.target.value))}
              className="input"
              aria-label="Sensitivity Threshold"
            >
              <option value="2.0">High (2.0σ) - More alerts</option>
              <option value="2.5">Medium (2.5σ) - Balanced</option>
              <option value="3.0">Low (3.0σ) - Fewer alerts</option>
            </select>
          </div>
        </div>

        {/* Anomalies Table */}
        {anomalyMutation.data && (
          <div>
            {anomalies.length === 0 ? (
              <div className="text-center py-12 bg-green-50 rounded-lg">
                <div className="text-green-600 mb-2">
                  <Activity className="w-12 h-12 mx-auto" />
                </div>
                <p className="text-gray-900 font-semibold mb-1">No anomalies detected</p>
                <p className="text-gray-600 text-sm">Your costs are following normal patterns</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cost</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Severity</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Change</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {[...anomalies].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()).map((anomaly, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {format(parseISO(anomaly.date), 'MMM dd, yyyy')}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          ${anomaly.cost.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span
                            className={`px-2 py-1 text-xs font-semibold rounded-full ${
                              anomaly.severity === 'critical'
                                ? 'bg-modernRed-100 text-modernRed-800'
                                : anomaly.severity === 'high'
                                ? 'bg-modernYellow-100 text-modernYellow-800'
                                : anomaly.severity === 'medium'
                                ? 'bg-modernYellow-100 text-modernYellow-800'
                                : 'bg-modernTeal-100 text-modernTeal-800'
                            }`}
                          >
                            {anomaly.severity.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 capitalize">
                          {anomaly.type}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {anomaly.percentage_change && (
                            <span
                              className={`font-medium ${
                                anomaly.percentage_change > 0 ? 'text-modernRed-700' : 'text-modernGreen-700'
                              }`}
                            >
                              {anomaly.percentage_change > 0 ? '+' : ''}
                              {anomaly.percentage_change.toFixed(1)}%
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-600">{anomaly.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  )
}
