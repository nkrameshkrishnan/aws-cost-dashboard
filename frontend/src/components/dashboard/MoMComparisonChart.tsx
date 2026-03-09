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
import { MoMComparison } from '@/types'
import { InfoModal } from '@/components/common/InfoModal'

interface MoMComparisonChartProps {
  profileName: string
  momData?: MoMComparison
}

export function MoMComparisonChart({ profileName, momData }: MoMComparisonChartProps) {

  if (!momData || !momData.current_month || !momData.previous_month) {
    return (
      <div className="h-80 flex flex-col items-center justify-center text-gray-500">
        <TrendingUp className="w-12 h-12 mb-2 opacity-50" />
        <p>No comparison data available</p>
      </div>
    )
  }

  // Prepare chart data
  const chartData = [
    {
      name: 'Previous Month',
      cost: momData.previous_month.cost,
      label: 'Prev',
    },
    {
      name: 'Current Month',
      cost: momData.current_month.cost,
      label: 'Current',
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

  const isIncrease = momData.change_percent > 0
  const changeColor = isIncrease ? 'text-modernRed-700' : 'text-modernGreen-700'
  const changeBgColor = isIncrease ? 'bg-modernRed-50' : 'bg-modernGreen-50'

  return (
    <div className="h-full">
      <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-brandRed-700" />
          Month-over-Month Comparison
        </h3>
        <div className="flex items-center gap-2">
          <div className={`flex items-center px-3 py-2 ${changeBgColor} rounded-full`}>
          {isIncrease ? (
            <ArrowUpIcon className={`w-4 h-4 ${changeColor}`} />
          ) : (
            <ArrowDownIcon className={`w-4 h-4 ${changeColor}`} />
          )}
          <span className={`text-sm ml-1 ${changeColor} font-bold`}>
            {Math.abs(momData.change_percent).toFixed(1)}%
          </span>
        </div>
          <InfoModal
            content={`What does this chart show?

This chart compares your AWS costs between the current month and the previous month, helping you quickly identify short-term cost changes and trends. The bar chart displays both months side-by-side for easy visual comparison.

Chart Components:
• Previous Month (Gray Bar): Total AWS costs for the completed previous month
• Current Month (Red Bar): Total AWS costs accumulated in the current month so far (month-to-date)
• Percentage Badge: Shows the month-over-month change percentage with color coding (Red with ↑ arrow for increase, Green with ↓ arrow for decrease)
• Change Amount: Dollar amount difference between the two months

How to Calculate MoM Change:

Month-over-Month (MoM) change is calculated using the following formula:
MoM % = ((Current Month - Previous Month) / Previous Month) × 100

For example, if previous month was $1,000 and current month is $1,200:
MoM % = (($1,200 - $1,000) / $1,000) × 100 = 20% increase

Important Considerations:
• Partial Month Data: If the current month is not complete, the comparison shows costs accumulated so far, which may not be fully representative
• Billing Lag: AWS costs may have a 1-2 day delay before appearing in Cost Explorer
• Different Month Lengths: Months with different numbers of days (28-31) may naturally show variation

When to Use This Chart:
• Monitor immediate cost impacts of recent infrastructure changes
• Track progress toward monthly cost reduction goals
• Quickly identify unexpected cost spikes that need investigation
• Compare spending patterns at the same point in different months

Pro Tip: For a fair comparison during the first half of the month, multiply the current month's cost by the appropriate factor (e.g., ×2 if halfway through) to estimate the full month's projected cost.`}
            variant="teal"
          />
        </div>
      </div>

      <div className="mb-3 text-sm text-gray-600">
        <p>Change: <span className={`font-semibold ${changeColor}`}>
          ${Math.abs(momData.change_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
