import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useRightSizingRecommendations, useRightSizingSummary, useTopSavingsOpportunities } from '@/hooks/useRightSizing'
import { Server, HardDrive, Zap, Gauge, DollarSign, TrendingUp, AlertTriangle, CheckCircle, Filter, ArrowUpDown, AlertCircle, Download, FileSpreadsheet } from 'lucide-react'
import { InfoModal } from '@/components/common/InfoModal'
import { ProfileSelector } from '@/components/common/ProfileSelector'
import { LoadingPage } from '@/components/common/LoadingPage'
import { exportApi } from '@/api/export'
import { useProfileStore } from '@/store/profileStore'

type SortField = 'savings' | 'finding' | 'resource_type' | 'resource_name'
type SortDirection = 'asc' | 'desc'

export function RightSizing() {
  const { selectedProfile } = useProfileStore()
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>('')
  const [findingFilter, setFindingFilter] = useState<string>('')
  const [sortField, setSortField] = useState<SortField>('savings')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')


  // Hooks
  const { data: summary, isLoading: summaryLoading } = useRightSizingSummary(selectedProfile)
  const { data: recommendations, isLoading: recsLoading } = useRightSizingRecommendations(
    selectedProfile,
    '' // Always fetch all recommendations, filter client-side
  )
  const { data: topOpportunities, isLoading: topLoading } = useTopSavingsOpportunities(selectedProfile, 5)

  // PDF Export mutation
  const exportPDFMutation = useMutation({
    mutationFn: async () => {
      // Read S3 configuration from Settings
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      const s3Bucket = localStorage.getItem('s3ExportBucket') || ''

      return exportApi.exportRightSizingPDF(
        selectedProfile,
        resourceTypeFilter || undefined,
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
        const fileName = exportApi.generateExportFileName('rightsizing_report', selectedProfile, 'pdf')
        exportApi.downloadBlob(blob, fileName)
        alert(`✅ PDF right-sizing report downloaded: ${fileName}`)
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

      return exportApi.exportRightSizingExcel(
        selectedProfile,
        resourceTypeFilter || undefined,
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
        const fileName = exportApi.generateExportFileName('rightsizing_report', selectedProfile, 'xlsx')
        exportApi.downloadBlob(blob, fileName)
        alert(`✅ Excel right-sizing report downloaded: ${fileName}`)
      }
    },
    onError: (error: any) => {
      alert(`❌ Failed to export Excel: ${error.response?.data?.detail || error.message || 'Unknown error'}`)
    }
  })

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const getFilteredAndSortedRecommendations = () => {
    if (!recommendations) return []

    let filtered = Array.isArray(recommendations.recommendations) ? recommendations.recommendations : []

    // Apply resource type filter
    if (resourceTypeFilter) {
      filtered = filtered.filter(r => r.resource_type === resourceTypeFilter)
    }

    // Apply finding filter
    if (findingFilter) {
      filtered = filtered.filter(r => r.finding.toLowerCase().includes(findingFilter.toLowerCase()))
    }

    // Sort
    const sorted = [...filtered].sort((a, b) => {
      let compareValue = 0

      switch (sortField) {
        case 'savings':
          compareValue = a.estimated_monthly_savings - b.estimated_monthly_savings
          break
        case 'finding':
          compareValue = a.finding.localeCompare(b.finding)
          break
        case 'resource_type':
          compareValue = a.resource_type.localeCompare(b.resource_type)
          break
        case 'resource_name':
          compareValue = a.resource_name.localeCompare(b.resource_name)
          break
      }

      return sortDirection === 'asc' ? compareValue : -compareValue
    })

    return sorted
  }

  const getResourceTypeIcon = (type: string) => {
    switch (type) {
      case 'ec2_instance':
        return <Server className="w-5 h-5 text-brandRed-700" />
      case 'ebs_volume':
        return <HardDrive className="w-5 h-5 text-modernTeal-700" />
      case 'lambda_function':
        return <Zap className="w-5 h-5 text-modernYellow-700" />
      case 'auto_scaling_group':
        return <Gauge className="w-5 h-5 text-modernGreen-700" />
      default:
        return <Server className="w-5 h-5 text-gray-500" />
    }
  }

  const getResourceTypeLabel = (type: string) => {
    switch (type) {
      case 'ec2_instance':
        return 'EC2 Instance'
      case 'ebs_volume':
        return 'EBS Volume'
      case 'lambda_function':
        return 'Lambda Function'
      case 'auto_scaling_group':
        return 'Auto Scaling Group'
      default:
        return type
    }
  }

  const getFindingBadge = (finding: string) => {
    const lower = finding.toLowerCase()
    if (lower.includes('overprovisioned')) {
      return <span className="px-2 py-1 text-xs font-semibold rounded-full bg-modernYellow-100 text-modernYellow-800">Overprovisioned</span>
    }
    if (lower.includes('underprovisioned')) {
      return <span className="px-2 py-1 text-xs font-semibold rounded-full bg-modernRed-100 text-modernRed-800">Underprovisioned</span>
    }
    if (lower.includes('optimized')) {
      return <span className="px-2 py-1 text-xs font-semibold rounded-full bg-modernGreen-100 text-modernGreen-800">Optimized</span>
    }
    return <span className="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">{finding}</span>
  }

  const getPerformanceRiskBadge = (risk?: number) => {
    if (risk === undefined) return null
    if (risk === 0) return <span className="text-xs text-modernGreen-700 font-medium">Very Low</span>
    if (risk <= 1) return <span className="text-xs text-modernGreen-600 font-medium">Low</span>
    if (risk <= 2) return <span className="text-xs text-modernYellow-600 font-medium">Medium</span>
    if (risk <= 3) return <span className="text-xs text-modernYellow-700 font-medium">High</span>
    return <span className="text-xs text-modernRed-700 font-medium">Very High</span>
  }

  if (summaryLoading || recsLoading || topLoading) {
    return <LoadingPage message="Loading right-sizing recommendations..." />
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-brandRed-700" />
            Right-Sizing Recommendations
          </h1>
          <p className="text-gray-600 mt-2">AWS Compute Optimizer insights for cost savings</p>
        </div>
        <div className="flex items-center gap-3">
          <ProfileSelector />
          <InfoModal
            content={`What are Right-Sizing Recommendations?

Right-sizing recommendations from AWS Compute Optimizer help you optimize your cloud resources based on actual usage data. The service uses machine learning to analyze historical utilization metrics and suggest optimal configurations.

Supported Resources:
• EC2 Instances: Detect over/under-provisioned instances
• EBS Volumes: Identify over-provisioned storage
• Lambda Functions: Optimize memory allocation
• Auto Scaling Groups: Improve instance type selection

How It Works:
1. AWS collects minimum 30 hours of utilization data
2. Machine learning analyzes CPU, memory, network, and I/O patterns
3. Recommendations generated with performance risk scores
4. Estimated monthly savings calculated for each recommendation

Finding Types:
• Overprovisioned: Resource has more capacity than needed (savings opportunity)
• Underprovisioned: Resource may not have enough capacity (performance risk)
• Optimized: Resource is appropriately sized

Performance Risk Score (0-5):
• 0-1: Very Low/Low - Safe to implement
• 2-3: Medium/High - Review before implementing
• 4-5: Very High - Requires careful evaluation

Requirements:
• AWS Compute Optimizer must be enabled
• IAM permissions for compute-optimizer API calls
• Minimum 30 hours of resource utilization data

Best Practice: Start with recommendations that have low performance risk and high savings potential. Implement changes in non-production environments first.`}
            variant="teal"
          />
        </div>
      </div>

      {/* Export Section */}
      {selectedProfile && (
        <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border-2 border-blue-200 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-1">Export Right-Sizing Reports</h3>
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

      {/* AWS Compute Optimizer Info - Show when no recommendations */}
      {summary &&
       summary.total_ec2_recommendations === 0 &&
       summary.total_ebs_recommendations === 0 &&
       summary.total_lambda_recommendations === 0 &&
       summary.total_asg_recommendations === 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-blue-900 mb-2">AWS Compute Optimizer Not Available</h3>
              <p className="text-sm text-blue-800 mb-3">
                No right-sizing recommendations are available. This could be because:
              </p>
              <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
                <li>AWS Compute Optimizer is not enabled for this account</li>
                <li>Insufficient resource utilization data (requires 30+ hours)</li>
                <li>No resources currently running that can be optimized</li>
                <li>Missing IAM permissions for Compute Optimizer APIs</li>
              </ul>
              <p className="text-sm text-blue-800 mt-3">
                <strong>To enable:</strong> Visit AWS Console → Compute Optimizer → Opt in
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* Total Savings */}
          <div className="card bg-gradient-to-br from-brandRed-50 to-modernTeal-50 border border-brandRed-100">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-700 text-sm font-medium">Potential Monthly Savings</span>
              <DollarSign className="w-6 h-6 text-brandRed-700" />
            </div>
            <div className="text-3xl font-bold text-brandRed-700">
              ${summary.total_potential_savings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-gray-600 mt-1">
              {summary.total_ec2_recommendations + summary.total_ebs_recommendations + summary.total_lambda_recommendations + summary.total_asg_recommendations} recommendations
            </div>
          </div>

          {/* EC2 Recommendations */}
          <div className="card hover:shadow-card-hover transition-all">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-600 text-sm font-medium">EC2 Instances</span>
              <Server className="w-5 h-5 text-brandRed-700" />
            </div>
            <div className="text-2xl font-bold text-gray-900">{summary.total_ec2_recommendations}</div>
            <div className="text-xs text-gray-500 mt-1">Instance recommendations</div>
          </div>

          {/* EBS Recommendations */}
          <div className="card hover:shadow-card-hover transition-all">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-600 text-sm font-medium">EBS Volumes</span>
              <HardDrive className="w-5 h-5 text-modernTeal-700" />
            </div>
            <div className="text-2xl font-bold text-gray-900">{summary.total_ebs_recommendations}</div>
            <div className="text-xs text-gray-500 mt-1">Volume recommendations</div>
          </div>

          {/* Lambda Recommendations */}
          <div className="card hover:shadow-card-hover transition-all">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-600 text-sm font-medium">Lambda Functions</span>
              <Zap className="w-5 h-5 text-modernYellow-700" />
            </div>
            <div className="text-2xl font-bold text-gray-900">{summary.total_lambda_recommendations}</div>
            <div className="text-xs text-gray-500 mt-1">Function recommendations</div>
          </div>
        </div>
      )}

      {/* Findings Summary */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="card bg-modernYellow-50 border border-modernYellow-200">
            <div className="flex items-center gap-3 mb-2">
              <AlertTriangle className="w-5 h-5 text-modernYellow-700" />
              <span className="text-sm font-medium text-modernYellow-900">Overprovisioned</span>
            </div>
            <div className="text-2xl font-bold text-modernYellow-900">{summary.overprovisioned_resources}</div>
            <div className="text-xs text-modernYellow-700 mt-1">Resources with excess capacity</div>
          </div>

          <div className="card bg-modernRed-50 border border-modernRed-200">
            <div className="flex items-center gap-3 mb-2">
              <AlertTriangle className="w-5 h-5 text-modernRed-700" />
              <span className="text-sm font-medium text-modernRed-900">Underprovisioned</span>
            </div>
            <div className="text-2xl font-bold text-modernRed-900">{summary.underprovisioned_resources}</div>
            <div className="text-xs text-modernRed-700 mt-1">Resources needing more capacity</div>
          </div>

          <div className="card bg-modernGreen-50 border border-modernGreen-200">
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle className="w-5 h-5 text-modernGreen-700" />
              <span className="text-sm font-medium text-modernGreen-900">Optimized</span>
            </div>
            <div className="text-2xl font-bold text-modernGreen-900">{summary.optimized_resources}</div>
            <div className="text-xs text-modernGreen-700 mt-1">Resources properly sized</div>
          </div>
        </div>
      )}

      {/* Top Savings Opportunities */}
      {topOpportunities && topOpportunities.length > 0 && (
        <div className="card mb-8 bg-gradient-to-br from-modernGreen-50 to-modernTeal-50 border border-modernGreen-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-modernGreen-700" />
            Top 5 Savings Opportunities
          </h3>
          <div className="space-y-3">
            {topOpportunities.map((opp, index) => (
              <div key={index} className="bg-white rounded-lg p-4 border border-modernGreen-200 hover:shadow-md transition-all">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {getResourceTypeIcon(opp.resource_type)}
                      <span className="font-medium text-gray-900">{opp.resource_name}</span>
                      {getFindingBadge(opp.finding)}
                    </div>
                    <div className="text-sm text-gray-600">
                      {opp.current_config} → {opp.recommended_config}
                    </div>
                    {opp.performance_risk !== undefined && (
                      <div className="text-xs text-gray-500 mt-1">
                        Performance Risk: {getPerformanceRiskBadge(opp.performance_risk)}
                      </div>
                    )}
                  </div>
                  <div className="text-right ml-4">
                    <div className="text-2xl font-bold text-modernGreen-700">
                      ${opp.estimated_monthly_savings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    <div className="text-xs text-gray-500">per month</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters and Table */}
      <div className="card">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">All Recommendations</h3>
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-500" />
              <select
                aria-label="Filter by resource type"
                value={resourceTypeFilter}
                onChange={(e) => setResourceTypeFilter(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brandRed-500 focus:border-brandRed-500"
              >
                <option value="">All Resource Types</option>
                <option value="ec2_instance">EC2 Instances</option>
                <option value="ebs_volume">EBS Volumes</option>
                <option value="lambda_function">Lambda Functions</option>
                <option value="auto_scaling_group">Auto Scaling Groups</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <select
                aria-label="Filter by finding type"
                value={findingFilter}
                onChange={(e) => setFindingFilter(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brandRed-500 focus:border-brandRed-500"
              >
                <option value="">All Findings</option>
                <option value="overprovisioned">Overprovisioned</option>
                <option value="underprovisioned">Underprovisioned</option>
                <option value="optimized">Optimized</option>
              </select>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('resource_type')}
                >
                  <div className="flex items-center gap-1">
                    Resource Type
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('resource_name')}
                >
                  <div className="flex items-center gap-1">
                    Resource Name
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Region
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Current Config
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Recommended Config
                </th>
                <th
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('finding')}
                >
                  <div className="flex items-center gap-1">
                    Finding
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Utilization
                </th>
                <th
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('savings')}
                >
                  <div className="flex items-center gap-1">
                    Monthly Savings
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {getFilteredAndSortedRecommendations().map((rec, index) => (
                <tr key={index} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      {getResourceTypeIcon(rec.resource_type)}
                      <span className="text-sm text-gray-900">{getResourceTypeLabel(rec.resource_type)}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900 max-w-xs truncate" title={rec.resource_name}>
                      {rec.resource_name}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded text-gray-700">
                      {rec.region || 'N/A'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    {rec.current_config}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-modernTeal-700">
                    {rec.recommended_config}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getFindingBadge(rec.finding)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    {rec.cpu_utilization != null && (
                      <div>CPU: {rec.cpu_utilization.toFixed(1)}%</div>
                    )}
                    {rec.memory_utilization != null && (
                      <div>Mem: {rec.memory_utilization.toFixed(1)}%</div>
                    )}
                    {rec.performance_risk != null && (
                      <div className="text-xs mt-1">Risk: {getPerformanceRiskBadge(rec.performance_risk)}</div>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-bold text-modernGreen-700">
                      ${rec.estimated_monthly_savings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    {rec.savings_percentage != null && (
                      <div className="text-xs text-gray-500">
                        {rec.savings_percentage.toFixed(1)}% savings
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {getFilteredAndSortedRecommendations().length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <CheckCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No recommendations found</p>
              <p className="text-sm mt-1">Try adjusting your filters or check AWS Compute Optimizer status</p>
            </div>
          )}
        </div>
      </div>

      {/* Quick Start & Implementation Guide Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        {/* Quick Start Guide */}
        <div className="card border-l-4 border-blue-600">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Zap className="w-5 h-5 text-blue-700" />
            </div>
            <h3 className="text-lg font-bold text-modernGray-900">Quick Start Guide</h3>
          </div>
          <div className="space-y-3 text-sm text-modernGray-700">
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-bold">1</span>
              <div>
                <p className="font-semibold">Enable AWS Compute Optimizer</p>
                <p className="text-xs text-modernGray-600">Go to AWS Console → Compute Optimizer → Enable. Free for all AWS accounts.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-bold">2</span>
              <div>
                <p className="font-semibold">Wait for Data Collection</p>
                <p className="text-xs text-modernGray-600">Compute Optimizer requires minimum 30 hours of utilization metrics. Check back after 48 hours.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-bold">3</span>
              <div>
                <p className="font-semibold">Review Recommendations</p>
                <p className="text-xs text-modernGray-600">Start with "Overprovisioned" findings with Low performance risk for easy wins.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-bold">4</span>
              <div>
                <p className="font-semibold">Test Before Production</p>
                <p className="text-xs text-modernGray-600">Apply changes to dev/staging first. Monitor performance for 24-48 hours before production.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-bold">5</span>
              <div>
                <p className="font-semibold">Export & Share Reports</p>
                <p className="text-xs text-modernGray-600">Use PDF/Excel export to share findings with your team and track implementation progress.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Implementation Checklist */}
        <div className="card border-l-4 border-modernGreen-600">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-modernGreen-100 rounded-lg">
              <CheckCircle className="w-5 h-5 text-modernGreen-700" />
            </div>
            <h3 className="text-lg font-bold text-modernGray-900">Implementation Checklist</h3>
          </div>
          <div className="space-y-3">
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Prioritize by Savings & Risk</p>
                <p className="text-xs text-modernGray-600">Sort by "Monthly Savings" and filter for Low/Very Low performance risk first</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Document Current Configuration</p>
                <p className="text-xs text-modernGray-600">Before making changes, note instance types, volumes, and Lambda memory settings</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Create Snapshots/Backups</p>
                <p className="text-xs text-modernGray-600">Take EBS snapshots and Lambda version backups before resizing</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Schedule During Low Traffic</p>
                <p className="text-xs text-modernGray-600">Implement instance type changes during maintenance windows or off-peak hours</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Monitor Post-Implementation</p>
                <p className="text-xs text-modernGray-600">Watch CloudWatch metrics (CPU, memory, latency) for 48 hours after changes</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-modernGreen-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-modernGray-900">Have Rollback Plan Ready</p>
                <p className="text-xs text-modernGray-600">Keep original configuration handy to quickly revert if issues arise</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics & Tips */}
      <div className="card mt-6 bg-gradient-to-r from-purple-50 to-pink-50 border-2 border-purple-200">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-purple-600 rounded-lg shadow-md flex-shrink-0">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-purple-900 mb-2">Understanding Performance Risk Scores</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="font-semibold text-modernGreen-700 mb-1">✓ Risk 0-1 (Very Low/Low)</p>
                <p className="text-xs text-modernGray-700">Safe to implement immediately. Minimal chance of performance degradation.</p>
              </div>
              <div>
                <p className="font-semibold text-modernYellow-700 mb-1">⚠ Risk 2-3 (Medium/High)</p>
                <p className="text-xs text-modernGray-700">Test thoroughly first. May impact performance under peak load conditions.</p>
              </div>
              <div>
                <p className="font-semibold text-modernRed-700 mb-1">⛔ Risk 4-5 (Very High)</p>
                <p className="text-xs text-modernGray-700">High risk of performance issues. Only implement with extensive testing.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
