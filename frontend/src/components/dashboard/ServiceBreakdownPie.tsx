import { useState } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'
import { useServiceBreakdown } from '@/hooks/useCostData'
import { DrillDownModal } from '@/components/common/DrillDownModal'

interface ServiceBreakdownPieProps {
  profileName: string
  startDate: string
  endDate: string
  topN?: number
}

// Abbreviate AWS service names for better readability
const abbreviateServiceName = (serviceName: string): string => {
  const abbreviations: Record<string, string> = {
    'Amazon Elastic Compute Cloud': 'EC2',
    'Amazon Simple Storage Service': 'S3',
    'Amazon Relational Database Service': 'RDS',
    'Amazon Virtual Private Cloud': 'VPC',
    'Amazon Elastic Container Service': 'ECS',
    'Amazon Elastic Kubernetes Service': 'EKS',
    'AWS Lambda': 'Lambda',
    'Amazon CloudFront': 'CloudFront',
    'Amazon DynamoDB': 'DynamoDB',
    'Amazon ElastiCache': 'ElastiCache',
    'Amazon CloudWatch': 'CloudWatch',
    'Amazon Route 53': 'Route 53',
    'AWS Key Management Service': 'KMS',
    'Amazon API Gateway': 'API Gateway',
    'AWS Secrets Manager': 'Secrets Manager',
    'Amazon Simple Notification Service': 'SNS',
    'Amazon Simple Queue Service': 'SQS',
    'Amazon Elastic Load Balancing': 'ELB',
    'AWS Certificate Manager': 'ACM',
    'Amazon Elastic Container Registry': 'ECR',
    'AWS CloudTrail': 'CloudTrail',
    'AWS Config': 'Config',
    'Amazon Kinesis': 'Kinesis',
    'AWS Glue': 'Glue',
    'Amazon Athena': 'Athena',
    'AWS Step Functions': 'Step Functions',
    'Amazon EventBridge': 'EventBridge',
    'AWS Systems Manager': 'Systems Manager',
  }

  return abbreviations[serviceName] || serviceName
}

// Color palette for the pie chart - Trend Micro theme colors
const COLORS = [
  '#D71920', // Trend Micro Red (brand color)
  '#00CDB9', // Modern Teal
  '#00CD87', // Modern Green
  '#FFCD00', // Modern Yellow
  '#FF1919', // Modern Red
  '#E53935', // Trend Red 600
  '#1F9B8E', // Modern Teal 700
  '#178F56', // Modern Green 700
  '#D1AA00', // Modern Yellow 700
  '#28AC9D', // Modern Teal 600
  '#6B7280', // Modern Gray 500
]

export function ServiceBreakdownPie({
  profileName,
  startDate,
  endDate,
  topN = 10,
}: ServiceBreakdownPieProps) {
  const [drillDownOpen, setDrillDownOpen] = useState(false)
  const [selectedService, setSelectedService] = useState<string | null>(null)

  const { data, isLoading, error } = useServiceBreakdown(
    profileName,
    startDate,
    endDate,
    topN
  )

  const handlePieClick = (data: any) => {
    const fullName = data.fullName
    setSelectedService(fullName)
    setDrillDownOpen(true)
  }

  if (isLoading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="animate-pulse text-gray-500">Loading service data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="text-red-500">Error loading service data: {String(error)}</div>
      </div>
    )
  }

  if (!data || data.services.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="text-gray-500">No service cost data available</div>
      </div>
    )
  }

  // Format data for pie chart with abbreviated names
  const chartData = data.services.map((service) => ({
    name: abbreviateServiceName(service.service),
    fullName: service.service,
    value: service.cost,
  }))

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const percentage = ((payload[0].value / data.total_cost) * 100).toFixed(1)
      const fullName = payload[0].payload.fullName
      return (
        <div className="bg-white p-3 border border-trendRed-200 rounded-lg shadow-xl">
          <p className="text-sm font-semibold text-gray-900">{payload[0].name}</p>
          {fullName !== payload[0].name && (
            <p className="text-xs text-gray-500 mb-1">{fullName}</p>
          )}
          <p className="text-base text-trendRed-700 font-bold">
            ${payload[0].value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-modernTeal-700 font-medium">{percentage}% of total</p>
        </div>
      )
    }
    return null
  }

  // Custom label for pie slices - show percentage only for slices >5%
  const renderLabel = (entry: any) => {
    const percentage = ((entry.value / data.total_cost) * 100)
    if (percentage < 5) return '' // Hide labels for small slices
    return `${percentage.toFixed(0)}%`
  }

  return (
    <>
      <div className="h-[440px]">
        <div className="text-xs text-modernTeal-700 bg-modernTeal-50 border border-modernTeal-200 rounded-lg px-3 py-1.5 text-center mb-1 font-medium">
          💡 Click on any service to drill down by region
        </div>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart margin={{ top: 0, right: 10, bottom: -5, left: 10 }}>
            <Pie
              data={chartData}
              cx="50%"
              cy="43%"
              labelLine={false}
              label={renderLabel}
              outerRadius={88}
              innerRadius={44}
              fill="#8884d8"
              dataKey="value"
              paddingAngle={2}
              onClick={handlePieClick}
              style={{ cursor: 'pointer' }}
            >
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                  stroke="#fff"
                  strokeWidth={2}
                  style={{ cursor: 'pointer' }}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              verticalAlign="bottom"
              height={105}
              iconType="circle"
              wrapperStyle={{
                fontSize: '11px',
                paddingTop: '0px',
                paddingBottom: '3px',
                maxHeight: '105px',
                overflowY: 'auto',
                lineHeight: '1.25',
                marginTop: '-5px'
              }}
              formatter={(value) => {
                // Truncate very long service names for legend
                if (value.length > 35) {
                  return value.substring(0, 32) + '...'
                }
                return value
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {selectedService && (
        <DrillDownModal
          isOpen={drillDownOpen}
          onClose={() => setDrillDownOpen(false)}
          profileName={profileName}
          startDate={startDate}
          endDate={endDate}
          initialDimension="REGION"
          initialFilters={{ service: selectedService }}
        />
      )}
    </>
  )
}
