import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  ComposedChart,
  ReferenceLine,
  Legend,
} from 'recharts'
import { useDailyCosts, useDailyForecast, useDateRanges } from '@/hooks/useCostData'
import { TrendingUp, Calendar } from 'lucide-react'
import { format, parseISO, subDays, addDays } from 'date-fns'
import { InfoModal } from '@/components/common/InfoModal'

interface ForecastChartProps {
  profileName: string
}

export function ForecastChart({ profileName }: ForecastChartProps) {
  const today = new Date()
  const historicalStart = format(subDays(today, 30), 'yyyy-MM-dd')
  const historicalEnd = format(today, 'yyyy-MM-dd')

  const { data: historicalData, isLoading: isLoadingHistorical, error: historicalError } = useDailyCosts(
    profileName,
    historicalStart,
    historicalEnd
  )

  const { data: forecastData, isLoading: isLoadingForecast, error: forecastError } = useDailyForecast(
    profileName,
    30
  )

  if (isLoadingHistorical || isLoadingForecast) {
    return (
      <div className="h-96 flex items-center justify-center">
        <div className="animate-pulse text-gray-500">Loading forecast data...</div>
      </div>
    )
  }

  if (historicalError || forecastError) {
    return (
      <div className="h-96 flex flex-col items-center justify-center text-red-500">
        <TrendingUp className="w-12 h-12 mb-2 opacity-50" />
        <p>Error loading forecast data</p>
        <p className="text-sm mt-1">{String(historicalError || forecastError)}</p>
      </div>
    )
  }

  if (!historicalData || !Array.isArray(historicalData.daily_costs) || historicalData.daily_costs.length === 0) {
    return (
      <div className="h-96 flex flex-col items-center justify-center text-gray-500">
        <Calendar className="w-12 h-12 mb-2 opacity-50" />
        <p>No historical cost data available</p>
      </div>
    )
  }

  // Combine historical and forecast data
  const combinedData: any[] = []

  // Add historical data
  historicalData.daily_costs.forEach((record, index) => {
    const isLastHistorical = index === historicalData.daily_costs.length - 1
    combinedData.push({
      date: format(parseISO(record.date), 'MMM dd'),
      fullDate: record.date,
      actualCost: record.cost,
      forecastedCost: isLastHistorical ? record.cost : undefined, // Bridge point
      type: 'historical',
    })
  })

  // Add forecast data if available
  if (forecastData && Array.isArray(forecastData.daily_forecast) && forecastData.daily_forecast.length > 0) {
    // Get the last historical cost for the bridge
    const lastHistoricalCost = historicalData.daily_costs[historicalData.daily_costs.length - 1]?.cost || 0

    forecastData.daily_forecast.forEach((record, index) => {
      const isFirstForecast = index === 0
      combinedData.push({
        date: format(parseISO(record.date), 'MMM dd'),
        fullDate: record.date,
        actualCost: isFirstForecast ? lastHistoricalCost : undefined, // Bridge point
        forecastedCost: record.forecasted_cost,
        type: 'forecast',
      })
    })
  }

  // Calculate totals
  const historicalTotal = historicalData.total_cost || 0
  const forecastTotal = forecastData?.forecasted_cost || 0

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      const isHistorical = data.type === 'historical'
      return (
        <div className="bg-white p-4 border border-brandRed-200 rounded-lg shadow-xl">
          <p className="text-sm font-semibold text-gray-900 mb-1">
            {format(parseISO(data.fullDate), 'EEEE, MMM dd, yyyy')}
          </p>
          <p className={`text-lg font-bold ${isHistorical ? 'text-brandRed-700' : 'text-modernTeal-700'}`}>
            ${(data.actualCost || data.forecastedCost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {isHistorical ? 'Actual Cost' : 'Forecasted Cost'}
          </p>
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
            Cost Forecast: Historical vs Predicted
          </h3>
          <InfoModal
            content={`What does this chart show?

This chart displays your actual AWS costs for the past 30 days (red line) alongside predicted costs for the next 30 days (teal dashed line). The vertical "Today" line separates historical data from forecasted data.

How are forecasted costs predicted?

The cost predictions are generated using AWS Cost Explorer's Forecast API, which employs sophisticated machine learning algorithms to analyze your spending patterns:

• Historical Analysis: The algorithm examines your past AWS spending to identify trends, patterns, and usage behaviors
• Seasonality Detection: It accounts for recurring patterns such as weekly cycles, monthly variations, or seasonal changes in usage
• Trend Identification: The model detects whether your costs are increasing, decreasing, or remaining stable over time
• Probabilistic Prediction: AWS generates a probability-based forecast, showing the most likely cost scenario (mean value) for each future day

Key Metrics:
• Last 30 Days Total: Sum of actual costs for the previous 30 days
• Next 30 Days Forecast: Predicted total cost for the upcoming 30 days
• Expected Change: Percentage difference between historical and forecasted totals

Important Notes:
• Forecasts are predictions, not guarantees - actual costs may vary
• Accuracy improves with more historical data and stable usage patterns
• Sudden changes in usage (e.g., new services, infrastructure changes) may not be reflected
• Use this forecast for budgeting and capacity planning`}
            variant="teal"
          />
        </div>
        <div className="flex gap-6 text-sm text-gray-600">
          <div>
            <span className="font-medium">Last 30 Days Total:</span>{' '}
            <span className="text-brandRed-700 font-bold">
              ${historicalTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          <div>
            <span className="font-medium">Next 30 Days Forecast:</span>{' '}
            <span className="text-modernTeal-700 font-bold">
              ${forecastTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
          {forecastTotal > 0 && historicalTotal > 0 && (
            <div>
              <span className="font-medium">Expected Change:</span>{' '}
              <span className={`font-bold ${forecastTotal > historicalTotal ? 'text-modernRed-700' : 'text-modernGreen-700'}`}>
                {forecastTotal > historicalTotal ? '+' : ''}
                {(((forecastTotal - historicalTotal) / historicalTotal) * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="h-96">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={combinedData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
            <defs>
              <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#D71920" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#D71920" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00CDB9" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#00CDB9" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis
              dataKey="date"
              stroke="#6B7280"
              tick={{ fill: '#6B7280', fontSize: 10 }}
              angle={-45}
              textAnchor="end"
              height={80}
              interval="preserveStartEnd"
            />
            <YAxis
              stroke="#6B7280"
              tick={{ fill: '#6B7280', fontSize: 12 }}
              tickFormatter={(value) => `$${value.toLocaleString()}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="line"
              formatter={(value) => {
                if (value === 'actualCost') return 'Actual Costs'
                if (value === 'forecastedCost') return 'Forecasted Costs'
                return value
              }}
            />
            <ReferenceLine
              x={format(today, 'MMM dd')}
              stroke="#1F2937"
              strokeWidth={2}
              strokeDasharray="5 5"
              label={{
                value: 'Today',
                position: 'top',
                fill: '#1F2937',
                fontSize: 12,
              }}
            />
            <Area
              type="monotone"
              dataKey="actualCost"
              fill="url(#actualGradient)"
              stroke="none"
              connectNulls={false}
            />
            <Area
              type="monotone"
              dataKey="forecastedCost"
              fill="url(#forecastGradient)"
              stroke="none"
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="actualCost"
              stroke="#D71920"
              strokeWidth={3}
              dot={false}
              connectNulls={false}
              name="Actual Costs"
            />
            <Line
              type="monotone"
              dataKey="forecastedCost"
              stroke="#00CDB9"
              strokeWidth={3}
              strokeDasharray="5 5"
              dot={false}
              connectNulls={false}
              name="Forecasted Costs"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
