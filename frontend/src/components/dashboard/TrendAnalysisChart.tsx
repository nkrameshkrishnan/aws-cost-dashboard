import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  ComposedChart,
  Area,
} from 'recharts'
import { useCostTrend } from '@/hooks/useCostData'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { InfoModal } from '@/components/common/InfoModal'

interface TrendAnalysisChartProps {
  profileName: string
}

export function TrendAnalysisChart({ profileName }: TrendAnalysisChartProps) {
  const { data: trendData, isLoading, error } = useCostTrend(profileName, 12)

  if (isLoading) {
    return (
      <div className="h-96 flex items-center justify-center">
        <div className="animate-pulse text-gray-500">Loading trend analysis...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-96 flex flex-col items-center justify-center text-red-500">
        <TrendingUp className="w-12 h-12 mb-2 opacity-50" />
        <p>Error loading trend data</p>
        <p className="text-sm mt-1">{String(error)}</p>
      </div>
    )
  }

  if (!trendData || !trendData.trend_data || trendData.trend_data.length === 0) {
    return (
      <div className="h-96 flex flex-col items-center justify-center text-gray-500">
        <TrendingUp className="w-12 h-12 mb-2 opacity-50" />
        <p>No trend data available</p>
      </div>
    )
  }

  // Format data for chart
  const chartData = trendData.trend_data.map((record) => ({
    month: format(parseISO(record.month), 'MMM yyyy'),
    cost: record.cost,
    momChange: record.mom_change_percent,
    fullMonth: record.month,
  }))

  // Calculate simple linear regression for trend line
  const n = chartData.length
  const sumX = chartData.reduce((sum, _, i) => sum + i, 0)
  const sumY = chartData.reduce((sum, item) => sum + item.cost, 0)
  const sumXY = chartData.reduce((sum, item, i) => sum + i * item.cost, 0)
  const sumX2 = chartData.reduce((sum, _, i) => sum + i * i, 0)

  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX)
  const intercept = (sumY - slope * sumX) / n

  const chartDataWithTrend = chartData.map((item, i) => ({
    ...item,
    trend: slope * i + intercept,
  }))

  // Overall trend direction
  const overallTrend = slope > 0 ? 'increasing' : slope < 0 ? 'decreasing' : 'stable'
  const avgCost = chartData.reduce((sum, item) => sum + item.cost, 0) / chartData.length
  const latestCost = chartData[chartData.length - 1].cost
  const latestMoMChange = chartData[chartData.length - 1].momChange

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-white p-4 border border-brandRed-200 rounded-lg shadow-xl">
          <p className="text-sm font-semibold text-gray-900 mb-2">{data.month}</p>
          <p className="text-lg text-brandRed-700 font-bold mb-1">
            ${data.cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          {data.momChange !== null && data.momChange !== undefined && (
            <div className="flex items-center gap-1 mt-2">
              {data.momChange > 0 ? (
                <TrendingUp className="w-4 h-4 text-modernRed-700" />
              ) : data.momChange < 0 ? (
                <TrendingDown className="w-4 h-4 text-modernGreen-700" />
              ) : (
                <Minus className="w-4 h-4 text-gray-600" />
              )}
              <span className={`text-sm font-semibold ${
                data.momChange > 0 ? 'text-modernRed-700' : data.momChange < 0 ? 'text-modernGreen-700' : 'text-gray-600'
              }`}>
                {Math.abs(data.momChange).toFixed(1)}% MoM
              </span>
            </div>
          )}
        </div>
      )
    }
    return null
  }

  return (
    <div className="h-full">
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-brandRed-700" />
            12-Month Cost Trend Analysis
          </h3>
          <InfoModal
            content={`What does this chart show?

This chart displays your monthly AWS costs over the past 12 months, helping you identify long-term spending trends and patterns. The red line shows actual monthly costs, while the teal dashed line represents a linear trend line calculated using regression analysis.

Chart Components:
• Red Line & Area: Your actual monthly AWS costs with a gradient fill showing the spending pattern over time
• Dashed Teal Line: Linear regression trend line calculated using statistical analysis to show the overall direction of your spending
• Data Points: Each point represents the total cost for a specific month. Hover over points to see detailed information including month-over-month (MoM) change

Understanding the Metrics:
• Latest: Your most recent month's total cost
• Average: Mean monthly cost across the 12-month period
• Trend: Overall direction indicated by the slope of the trend line (Increasing ↑, Decreasing ↓, or Stable −)
• MoM Change: Month-over-month percentage change shown in tooltips, indicating how much costs increased or decreased compared to the previous month

How to Use This Chart:
• Identify seasonal patterns or recurring spikes in spending
• Detect unusual cost anomalies that require investigation
• Track the effectiveness of cost optimization initiatives over time
• Plan future budgets based on historical trends
• Compare current spending against historical averages

Pro Tip: If you notice an increasing trend, review your service breakdown to identify which AWS services are driving the growth. Use this information to implement targeted cost optimization strategies.`}
            variant="teal"
          />
        </div>
        <div className="flex gap-6 text-sm text-gray-600">
          <div>
            <span className="font-medium">Latest:</span>{' '}
            <span className="text-gray-900 font-semibold">
              ${latestCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <div>
            <span className="font-medium">Average:</span>{' '}
            <span className="text-gray-900 font-semibold">
              ${avgCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="font-medium">Trend:</span>{' '}
            {overallTrend === 'increasing' ? (
              <span className="flex items-center text-modernRed-700 font-semibold">
                <TrendingUp className="w-4 h-4 mr-1" />
                Increasing
              </span>
            ) : overallTrend === 'decreasing' ? (
              <span className="flex items-center text-modernGreen-700 font-semibold">
                <TrendingDown className="w-4 h-4 mr-1" />
                Decreasing
              </span>
            ) : (
              <span className="flex items-center text-gray-600 font-semibold">
                <Minus className="w-4 h-4 mr-1" />
                Stable
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="h-96">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartDataWithTrend} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
            <defs>
              <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#D71920" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#00CDB9" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis
              dataKey="month"
              stroke="#6B7280"
              tick={{ fill: '#6B7280', fontSize: 11 }}
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis
              stroke="#6B7280"
              tick={{ fill: '#6B7280', fontSize: 12 }}
              tickFormatter={(value) => `$${value.toLocaleString()}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="cost"
              fill="url(#costGradient)"
              stroke="none"
            />
            <Line
              type="monotone"
              dataKey="cost"
              stroke="#D71920"
              strokeWidth={3}
              dot={{ fill: '#D71920', r: 4 }}
              activeDot={{ r: 6 }}
            />
            <Line
              type="monotone"
              dataKey="trend"
              stroke="#00CDB9"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
              name="Trend Line"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
