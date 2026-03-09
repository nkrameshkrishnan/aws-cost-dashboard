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
  ComposedChart,
} from 'recharts'
import { useDailyCosts } from '@/hooks/useCostData'
import { format, parseISO } from 'date-fns'

interface CostTrendChartProps {
  profileName: string
  startDate: string
  endDate: string
}

export function CostTrendChart({ profileName, startDate, endDate }: CostTrendChartProps) {
  const { data, isLoading, error } = useDailyCosts(profileName, startDate, endDate)

  if (isLoading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="animate-pulse text-gray-500">Loading cost data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="text-red-500">Error loading cost data: {String(error)}</div>
      </div>
    )
  }

  if (!data || !Array.isArray(data.daily_costs) || data.daily_costs.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="text-gray-500">No cost data available for this period</div>
      </div>
    )
  }

  // Format data for chart (filter out any null/undefined records)
  const chartData = data.daily_costs
    .filter((record) => record != null && record.cost != null)
    .map((record) => ({
      date: format(parseISO(record.date), 'MMM dd'),
      cost: record.cost,
      fullDate: record.date,
    }))

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-4 border border-brandRed-200 rounded-lg shadow-xl">
          <p className="text-sm font-semibold text-gray-900 mb-1">
            {format(parseISO(payload[0].payload.fullDate), 'EEEE, MMM dd, yyyy')}
          </p>
          <p className="text-lg text-brandRed-700 font-bold">
            ${payload[0].value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
        </div>
      )
    }
    return null
  }

  // Calculate average for reference line
  const avgCost = chartData.reduce((sum, item) => sum + item.cost, 0) / chartData.length

  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#D71920" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="#00CDB9" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            stroke="#d1d5db"
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#6b7280' }}
            stroke="#d1d5db"
            tickLine={false}
            tickFormatter={(value) => `$${value.toFixed(0)}`}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#D71920', strokeWidth: 1, strokeDasharray: '5 5' }} />
          <Legend
            wrapperStyle={{ paddingTop: '10px' }}
            iconType="circle"
          />
          <Area
            type="monotone"
            dataKey="cost"
            fill="url(#colorCost)"
            stroke="none"
          />
          <Line
            type="monotone"
            dataKey="cost"
            name="Daily Cost"
            stroke="#D71920"
            strokeWidth={3}
            dot={{ r: 4, fill: '#D71920', strokeWidth: 2, stroke: '#fff' }}
            activeDot={{ r: 6, fill: '#C62828', strokeWidth: 2, stroke: '#fff' }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
