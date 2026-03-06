import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { ArrowUpIcon, ArrowDownIcon, TrendingUp } from 'lucide-react'
import { useYoYComparison, useDateRanges } from '@/hooks/useCostData'
import { InfoModal } from '@/components/common/InfoModal'

interface YoYComparisonChartProps {
  profileName: string
}

export function YoYComparisonChart({ profileName }: YoYComparisonChartProps) {
  const { currentMonth } = useDateRanges()
  const { data: yoyData, isLoading, error } = useYoYComparison(
    profileName,
    currentMonth.start,
    currentMonth.end
  )

  if (isLoading) {
    return (
      <div className="h-80 flex items-center justify-center">
        <div className="animate-pulse text-gray-500">Loading YoY comparison...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-80 flex flex-col items-center justify-center text-red-500">
        <TrendingUp className="w-12 h-12 mb-2 opacity-50" />
        <p>Error loading YoY comparison</p>
        <p className="text-sm mt-1">{String(error)}</p>
      </div>
    )
  }

  if (!yoyData) {
    return (
      <div className="h-80 flex flex-col items-center justify-center text-gray-500">
        <TrendingUp className="w-12 h-12 mb-2 opacity-50" />
        <p>No YoY comparison data available</p>
      </div>
    )
  }

  // Prepare chart data
  const chartData = [
    {
      name: 'Same Period Last Year',
      cost: yoyData.previous_year_period.cost,
      label: 'Last Year',
    },
    {
      name: 'Current Period',
      cost: yoyData.current_period.cost,
      label: 'This Year',
    },
  ]

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-4 border border-brandRed-200 rounded-lg shadow-xl">
          <p className="text-sm font-semibold text-gray-900 mb-1">{payload[0].payload.name}</p>
          <p className="text-lg text-brandRed-700 font-bold">
            ${payload[0].value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
        </div>
      )
    }
    return null
  }

  const isIncrease = yoyData.change_percent > 0
  const changeColor = isIncrease ? 'text-modernRed-700' : 'text-modernGreen-700'
  const changeBgColor = isIncrease ? 'bg-modernRed-50' : 'bg-modernGreen-50'

  return (
    <div className="h-full">
      <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-brandRed-700" />
          Year-over-Year Comparison
        </h3>
        <div className="flex items-center gap-2">
        <div className={`flex items-center px-3 py-2 ${changeBgColor} rounded-full`}>
          {isIncrease ? (
            <ArrowUpIcon className={`w-4 h-4 ${changeColor}`} />
          ) : (
            <ArrowDownIcon className={`w-4 h-4 ${changeColor}`} />
          )}
          <span className={`text-sm ml-1 ${changeColor} font-bold`}>
            {Math.abs(yoyData.change_percent).toFixed(1)}%
          </span>
        </div>
          <InfoModal
            content={`What does this chart show?

This chart compares your AWS costs for the current period with the same period from last year, helping you identify long-term cost trends and annual growth patterns. The comparison uses the exact same date range from one year ago to ensure an apples-to-apples comparison.

Chart Components:
• Same Period Last Year (Gray Bar): Total AWS costs for the equivalent period from exactly one year ago (e.g., if current period is Jan 1-15, 2025, this shows Jan 1-15, 2024)
• Current Period (Red Bar): Total AWS costs for the current time period being analyzed
• Percentage Badge: Shows the year-over-year change percentage with color coding (Red with ↑ arrow for increase, Green with ↓ arrow for decrease)
• Change Amount: Absolute dollar amount difference between the two periods

How to Calculate YoY Change:

Year-over-Year (YoY) change is calculated using the following formula:
YoY % = ((Current Period - Same Period Last Year) / Same Period Last Year) × 100

For example, if the same period last year was $10,000 and current period is $12,000:
YoY % = (($12,000 - $10,000) / $10,000) × 100 = 20% increase

Why YoY Comparison Matters:
• Seasonal Patterns: Accounts for seasonal variations in business activity (e.g., retail peaks during holidays, quarterly processing cycles)
• Long-term Trends: Reveals whether your cloud spending is growing faster or slower than your business growth
• Budget Planning: Provides insights for annual budget forecasting and strategic planning
• ROI Analysis: Helps evaluate if cost optimization efforts are effective over the long term

When to Use This Chart:
• Annual budget reviews and planning cycles
• Evaluating infrastructure scaling and growth patterns
• Comparing year-over-year efficiency improvements
• Identifying recurring seasonal cost patterns
• Assessing the long-term impact of migration or modernization initiatives

Important Considerations:
• Business Growth: A YoY increase isn't necessarily bad if it aligns with business growth (e.g., more users, increased revenue)
• Service Changes: New services or infrastructure adopted in the current year will naturally show an increase
• AWS Pricing: AWS occasionally adjusts pricing, which can affect YoY comparisons

Best Practice: Compare your YoY cost growth rate against your YoY revenue or user growth rate. Ideally, your cloud costs should grow at a slower rate than your business metrics, indicating improving efficiency and economies of scale.`}
            variant="teal"
          />
        </div>
      </div>

      <div className="mb-3 text-sm text-gray-600">
        <p>Change: <span className={`font-semibold ${changeColor}`}>
          ${Math.abs(yoyData.change_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span></p>
      </div>

      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis
              dataKey="label"
              stroke="#6B7280"
              tick={{ fill: '#6B7280', fontSize: 12 }}
            />
            <YAxis
              stroke="#6B7280"
              tick={{ fill: '#6B7280', fontSize: 12 }}
              tickFormatter={(value) => `$${value.toLocaleString()}`}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(215, 25, 32, 0.1)' }} />
            <Bar dataKey="cost" radius={[8, 8, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={index === 0 ? '#9CA3AF' : '#D71920'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
