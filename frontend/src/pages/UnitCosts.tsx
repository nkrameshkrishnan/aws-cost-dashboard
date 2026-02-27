import { useState } from 'react'
import { useUnitCosts, useUnitCostTrend } from '@/hooks/useUnitCosts'
import { useMultiRegionUnitCosts } from '@/hooks/useMultiRegionUnitCosts'
import { useDateRanges } from '@/hooks/useCostData'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { TrendingUp, TrendingDown, Users, CreditCard, Activity, Database, DollarSign, Minus, Info, AlertTriangle, ArrowUpRight, ArrowDownRight, CheckCircle } from 'lucide-react'
import { parseISO, format } from 'date-fns'
import { InfoModal } from '@/components/common/InfoModal'
import { ProfileSelector } from '@/components/common/ProfileSelector'
import { useProfileStore } from '@/store/profileStore'
import { LoadingPage } from '@/components/common/LoadingPage'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

const AWS_REGIONS = [
  { code: 'us-east-1', name: 'US East (N. Virginia)' },
  { code: 'us-east-2', name: 'US East (Ohio)' },
  { code: 'us-west-1', name: 'US West (N. California)' },
  { code: 'us-west-2', name: 'US West (Oregon)' },
  { code: 'ap-south-1', name: 'Asia Pacific (Mumbai)' },
  { code: 'ap-northeast-1', name: 'Asia Pacific (Tokyo)' },
  { code: 'ap-northeast-2', name: 'Asia Pacific (Seoul)' },
  { code: 'ap-southeast-1', name: 'Asia Pacific (Singapore)' },
  { code: 'ap-southeast-2', name: 'Asia Pacific (Sydney)' },
  { code: 'eu-central-1', name: 'Europe (Frankfurt)' },
  { code: 'eu-west-1', name: 'Europe (Ireland)' },
  { code: 'eu-west-2', name: 'Europe (London)' },
  { code: 'sa-east-1', name: 'South America (São Paulo)' },
]

export function UnitCosts() {
  const { selectedProfile } = useProfileStore()
  const [metricType, setMetricType] = useState<'cost_per_user' | 'cost_per_transaction' | 'cost_per_api_call' | 'cost_per_gb'>('cost_per_user')
  const [selectedRegion, setSelectedRegion] = useState('us-east-2')
  const { currentMonth } = useDateRanges()

  // Hooks
  const { data: unitCosts, isLoading, error } = useUnitCosts(
    selectedProfile,
    currentMonth.start,
    currentMonth.end,
    selectedRegion
  )

  const { data: trendData, isLoading: trendLoading } = useUnitCostTrend(
    selectedProfile,
    metricType,
    6,
    selectedRegion
  )

  // Prefetch data for all other regions in the background
  useMultiRegionUnitCosts(
    selectedProfile,
    currentMonth.start,
    currentMonth.end,
    selectedRegion,
    metricType
  )

  const getTrendIcon = (trend?: string) => {
    if (trend === 'improving') return <TrendingDown className="w-5 h-5 text-modernGreen-700" />
    if (trend === 'degrading') return <TrendingUp className="w-5 h-5 text-modernRed-700" />
    return <Minus className="w-5 h-5 text-gray-600" />
  }

  const getTrendColor = (trend?: string) => {
    if (trend === 'improving') return 'text-modernGreen-700 bg-modernGreen-50'
    if (trend === 'degrading') return 'text-modernRed-700 bg-modernRed-50'
    return 'text-gray-600 bg-gray-50'
  }

  const getTrendLabel = (trend?: string) => {
    if (trend === 'improving') return 'Improving'
    if (trend === 'degrading') return 'Degrading'
    return 'Stable'
  }

  // Custom tooltip for trend chart
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-white p-4 border border-trendRed-200 rounded-lg shadow-xl">
          <p className="text-sm font-semibold text-gray-900 mb-2">{data.date}</p>
          <p className="text-lg text-trendRed-700 font-bold mb-1">
            ${data.unit_cost?.toFixed(4)}
          </p>
          <p className="text-xs text-gray-500">Total Cost: ${data.total_cost?.toLocaleString()}</p>
          <p className="text-xs text-gray-500">Metric Value: {data.metric_value?.toLocaleString()}</p>
        </div>
      )
    }
    return null
  }

  if (isLoading) {
    return <LoadingPage message="Loading unit cost metrics..." />
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-modernRed-700">Error loading unit costs: {String(error)}</div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <DollarSign className="w-8 h-8 text-trendRed-700" />
              Unit Cost Metrics
            </h1>
            <p className="text-gray-600 mt-2">Track cost efficiency as your business scales</p>
          </div>
          <div className="flex items-center gap-3">
            <ProfileSelector />
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium focus:ring-2 focus:ring-trendRed-500 focus:border-trendRed-500 bg-white hover:bg-gray-50 transition-colors"
              aria-label="Select AWS Region"
            >
              {AWS_REGIONS.map((region) => (
                <option key={region.code} value={region.code}>
                  {region.name}
                </option>
              ))}
            </select>
            <InfoModal
              content={`What are Unit Cost Metrics?

Unit cost metrics help you understand cost efficiency by dividing your total AWS costs by business metrics like active users, transactions, or API calls. This reveals whether your cloud spending is growing faster or slower than your business.

Key Metrics:
• Cost per User: Total AWS cost divided by active users (from Cognito)
• Cost per Transaction: Cost per business transaction processed (EC2 hours, API Gateway, Lambda, ALB, DynamoDB)
• Cost per API Call: Cost per API request handled (API Gateway)
• Cost per GB: Cost per gigabyte of data processed (S3 + CloudFront)

Automatic Metric Collection:
Metrics are automatically collected from AWS:
- EC2: Instance running hours (for infrastructure-focused accounts)
- API Gateway: Request counts
- Lambda: Invocation counts
- ALB: Request counts
- DynamoDB: Read/Write capacity units
- S3: Bytes downloaded
- CloudFront: Bytes served
- Cognito: Active users (if configured)

Trend Analysis:
• Improving: Unit costs decreasing (more efficient)
• Degrading: Unit costs increasing (less efficient)
• Stable: Unit costs relatively constant

Best Practice: Your unit costs should grow slower than your business metrics (revenue, users, transactions). If cost per transaction is decreasing while transaction count increases, you're achieving economies of scale.`}
              variant="teal"
            />
          </div>
        </div>

        {/* Automatic Collection Info Banner */}
        {unitCosts &&
         unitCosts.cost_per_user == null &&
         unitCosts.cost_per_transaction == null &&
         unitCosts.cost_per_api_call == null &&
         unitCosts.cost_per_gb == null ? (
          <div className="bg-amber-50 border-l-4 border-amber-600 p-4 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-700 mt-0.5 flex-shrink-0" />
              <div>
                <h3 className="text-sm font-semibold text-amber-900 mb-1">
                  No CloudWatch Metrics Found
                </h3>
                <p className="text-sm text-amber-800 mb-2">
                  No business metrics were automatically collected. This could be because:
                </p>
                <ul className="text-sm text-amber-800 space-y-1 list-disc list-inside ml-2">
                  <li>No EC2 instances running in the configured region</li>
                  <li>No API Gateway, Lambda, ALB, or DynamoDB activity in the selected period</li>
                  <li>No S3 or CloudFront data transfer activity</li>
                  <li>Resources exist in a different AWS region than configured</li>
                  <li>Missing IAM permissions for CloudWatch:GetMetricStatistics or EC2:DescribeInstances</li>
                </ul>
                <p className="text-sm text-amber-800 mt-2">
                  <strong>Tip:</strong> Check that your AWS account region is correctly configured in AWS Accounts settings.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-modernTeal-50 border-l-4 border-modernTeal-600 p-4 rounded-lg">
            <div className="flex items-start gap-3">
              <Info className="w-5 h-5 text-modernTeal-700 mt-0.5 flex-shrink-0" />
              <div>
                <h3 className="text-sm font-semibold text-modernTeal-900 mb-1">
                  Automatic Metric Collection Enabled
                </h3>
                <p className="text-sm text-modernTeal-800">
                  Business metrics are automatically collected from AWS based on your actual resource usage.
                  Metrics include EC2 instance hours, API Gateway requests, Lambda invocations, ALB requests, DynamoDB operations, and S3/CloudFront data transfer.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {/* Cost per User */}
        <div className="card hover:shadow-card-hover transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600 text-sm font-medium">Cost per User</span>
            <Users className="w-5 h-5 text-trendRed-700" />
          </div>
          {isLoading ? (
            <div className="py-4">
              <LoadingSpinner size="sm" />
            </div>
          ) : unitCosts?.cost_per_user != null ? (
            <>
              <div className="text-2xl font-bold text-gray-900">
                ${unitCosts.cost_per_user.toFixed(4)}
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getTrendColor(unitCosts.trend)}`}>
                  {getTrendIcon(unitCosts.trend)}
                  {getTrendLabel(unitCosts.trend)}
                </div>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {unitCosts.total_users?.toLocaleString()} total users
              </div>
            </>
          ) : (
            <div className="text-sm text-gray-500">No data available</div>
          )}
        </div>

        {/* Cost per Transaction */}
        <div className="card hover:shadow-card-hover transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600 text-sm font-medium">Cost per Transaction</span>
            <CreditCard className="w-5 h-5 text-modernTeal-700" />
          </div>
          {isLoading ? (
            <div className="py-4">
              <LoadingSpinner size="sm" />
            </div>
          ) : unitCosts?.cost_per_transaction != null ? (
            <>
              <div className="text-2xl font-bold text-gray-900">
                ${unitCosts.cost_per_transaction.toFixed(4)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {unitCosts.total_transactions?.toLocaleString()} transactions
              </div>
            </>
          ) : (
            <div className="text-sm text-gray-500">No data available</div>
          )}
        </div>

        {/* Cost per API Call */}
        <div className="card hover:shadow-card-hover transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600 text-sm font-medium">Cost per API Call</span>
            <Activity className="w-5 h-5 text-modernGreen-700" />
          </div>
          {isLoading ? (
            <div className="py-4">
              <LoadingSpinner size="sm" />
            </div>
          ) : unitCosts?.cost_per_api_call != null ? (
            <>
              <div className="text-2xl font-bold text-gray-900">
                ${unitCosts.cost_per_api_call.toFixed(6)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {unitCosts.total_api_calls?.toLocaleString()} API calls
              </div>
            </>
          ) : (
            <div className="text-sm text-gray-500">No data available</div>
          )}
        </div>

        {/* Cost per GB */}
        <div className="card hover:shadow-card-hover transition-all">
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-600 text-sm font-medium">Cost per GB</span>
            <Database className="w-5 h-5 text-modernYellow-700" />
          </div>
          {isLoading ? (
            <div className="py-4">
              <LoadingSpinner size="sm" />
            </div>
          ) : unitCosts?.cost_per_gb != null ? (
            <>
              <div className="text-2xl font-bold text-gray-900">
                ${unitCosts.cost_per_gb.toFixed(2)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {unitCosts.total_gb_processed?.toLocaleString()} GB processed
              </div>
            </>
          ) : (
            <div className="text-sm text-gray-500">No data available</div>
          )}
        </div>
      </div>

      {/* Trend Chart */}
      <div className="card">
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-trendRed-700" />
              6-Month Unit Cost Trend
            </h3>
            <div className="flex items-center gap-3">
              <select
                value={metricType}
                onChange={(e) => setMetricType(e.target.value as any)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-trendRed-500 focus:border-trendRed-500"
                aria-label="Select unit cost metric type"
              >
                <option value="cost_per_user">Cost per User</option>
                <option value="cost_per_transaction">Cost per Transaction</option>
                <option value="cost_per_api_call">Cost per API Call</option>
                <option value="cost_per_gb">Cost per GB</option>
              </select>
            </div>
          </div>
        </div>

        {trendLoading ? (
          <div className="h-96 flex items-center justify-center">
            <LoadingSpinner size="lg" text="Loading trend data..." />
          </div>
        ) : trendData && trendData.trend_data.length > 0 ? (
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData.trend_data} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                <defs>
                  <linearGradient id="unitCostGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#D71920" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#00CDB9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  dataKey="date"
                  stroke="#6B7280"
                  tick={{ fill: '#6B7280', fontSize: 11 }}
                  tickFormatter={(value) => format(parseISO(value), 'MMM yyyy')}
                />
                <YAxis
                  stroke="#6B7280"
                  tick={{ fill: '#6B7280', fontSize: 12 }}
                  tickFormatter={(value) => `$${value.toFixed(4)}`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="unit_cost"
                  stroke="#D71920"
                  strokeWidth={3}
                  dot={{ fill: '#D71920', r: 5 }}
                  activeDot={{ r: 7 }}
                  name="Unit Cost"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-96 flex flex-col items-center justify-center">
            <Activity className="w-12 h-12 mb-3 text-gray-400" />
            <p className="text-gray-700 font-medium mb-2">No CloudWatch Metrics Available</p>
            <p className="text-sm text-gray-600 text-center max-w-md">
              No metrics were found in CloudWatch for the selected time period.
              This account may not have active API Gateway, Lambda, ALB, DynamoDB, S3, or CloudFront resources.
            </p>
          </div>
        )}
      </div>

      {/* Total Cost Summary */}
      {unitCosts && (
        <div className="card mt-8 bg-gradient-to-br from-trendRed-50 to-modernTeal-50 border border-trendRed-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Total AWS Cost</p>
              <p className="text-3xl font-bold text-trendRed-700">
                ${unitCosts.total_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {currentMonth.start} to {currentMonth.end}
              </p>
            </div>
            {unitCosts.mom_change_percent != null && (
              <div className="text-right">
                <p className="text-sm text-gray-600 mb-1">MoM Change</p>
                <div className={`flex items-center gap-2 ${unitCosts.mom_change_percent > 0 ? 'text-modernRed-700' : 'text-modernGreen-700'}`}>
                  {unitCosts.mom_change_percent > 0 ? <ArrowUpRight className="w-5 h-5" /> : <ArrowDownRight className="w-5 h-5" />}
                  <span className="text-2xl font-bold">
                    {Math.abs(unitCosts.mom_change_percent).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Getting Started & Best Practices Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        {/* Getting Started */}
        <div className="card border-l-4 border-modernTeal-600">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-modernTeal-100 rounded-lg">
              <Info className="w-5 h-5 text-modernTeal-700" />
            </div>
            <h3 className="text-lg font-bold text-modernGray-900">Getting Started</h3>
          </div>
          <div className="space-y-3 text-sm text-modernGray-700">
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-modernTeal-100 text-modernTeal-700 rounded-full flex items-center justify-center text-xs font-bold">1</span>
              <div>
                <p className="font-semibold">Ensure AWS Resources are Running</p>
                <p className="text-xs text-modernGray-600">Unit costs require active resources (EC2, Lambda, API Gateway, etc.) in your selected region</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-modernTeal-100 text-modernTeal-700 rounded-full flex items-center justify-center text-xs font-bold">2</span>
              <div>
                <p className="font-semibold">Wait for Metrics Collection</p>
                <p className="text-xs text-modernGray-600">CloudWatch metrics are collected automatically. Initial data may take 5-15 minutes to appear</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-modernTeal-100 text-modernTeal-700 rounded-full flex items-center justify-center text-xs font-bold">3</span>
              <div>
                <p className="font-semibold">Select Correct Region</p>
                <p className="text-xs text-modernGray-600">Use the region selector to match where your resources are deployed</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-modernTeal-100 text-modernTeal-700 rounded-full flex items-center justify-center text-xs font-bold">4</span>
              <div>
                <p className="font-semibold">Monitor Trends Over Time</p>
                <p className="text-xs text-modernGray-600">Check back weekly to track if unit costs improve as your application scales</p>
              </div>
            </div>
          </div>
        </div>

        {/* Best Practices */}
        <div className="card border-l-4 border-modernGreen-600">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-modernGreen-100 rounded-lg">
              <CheckCircle className="w-5 h-5 text-modernGreen-700" />
            </div>
            <h3 className="text-lg font-bold text-modernGray-900">Best Practices</h3>
          </div>
          <div className="space-y-3">
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Track Against Business Goals</p>
                <p className="text-xs text-modernGray-600">Unit costs should decrease or stay flat as you scale to achieve economies of scale</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Set Alerts for Increases</p>
                <p className="text-xs text-modernGray-600">If cost per transaction rises, investigate inefficiencies or resource misconfigurations</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Optimize High-Cost Services</p>
                <p className="text-xs text-modernGray-600">Focus on services with the highest contribution to cost per transaction (EC2, RDS, Lambda)</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Compare Across Regions</p>
                <p className="text-xs text-modernGray-600">Use the region selector to compare unit costs and identify expensive regions</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Review Monthly Trends</p>
                <p className="text-xs text-modernGray-600">Consistent improvement means better infrastructure efficiency</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
