import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Settings, DollarSign, AlertCircle, TrendingUp, BarChart3, PieChart, Search, Cloud, Cog, Download, FileSpreadsheet } from 'lucide-react'
import { format, subDays } from 'date-fns'

import { KPICard } from '@/components/dashboard/KPICard'
import { CostTrendChart } from '@/components/dashboard/CostTrendChart'
import { ServiceBreakdownPie } from '@/components/dashboard/ServiceBreakdownPie'
import { ForecastChart } from '@/components/dashboard/ForecastChart'
import { MoMComparisonChart } from '@/components/dashboard/MoMComparisonChart'
import { YoYComparisonChart } from '@/components/dashboard/YoYComparisonChart'
import { TrendAnalysisChart } from '@/components/dashboard/TrendAnalysisChart'
import { AnomalyAlertWidget } from '@/components/dashboard/AnomalyAlertWidget'
import { QuickForecastWidget } from '@/components/dashboard/QuickForecastWidget'
import { ProfileSelector } from '@/components/common/ProfileSelector'
import { InfoModal } from '@/components/common/InfoModal'
import { LoadingPage } from '@/components/common/LoadingPage'
import { SetupRequired } from '@/components/common/SetupRequired'
import { useProfileStore } from '@/store/profileStore'
import { budgetsApi } from '@/api/budgets'
import { awsAccountsApi } from '@/api/awsAccounts'
import { costsApi } from '@/api/costs'
import { analyticsApi } from '@/api/analytics'
import { exportApi } from '@/api/export'
import {
  useDashboardData,
  useDateRanges,
} from '@/hooks/useCostData'

export function Dashboard() {
  const { selectedProfile } = useProfileStore()
  const dateRanges = useDateRanges()
  const navigate = useNavigate()


  // Check if AWS accounts are configured
  const { data: awsAccounts, isLoading: loadingAccounts, error: accountsError } = useQuery({
    queryKey: ['awsAccounts'],
    queryFn: () => awsAccountsApi.list(),
    retry: 1,
    retryDelay: 1000,
  })

  const hasAccounts = awsAccounts && awsAccounts.length > 0

  // Optimized: Fetch all dashboard data in ONE API call (only if accounts exist)
  const { data: dashboardData, isLoading: loadingDashboard, error: dashboardError } = useDashboardData(selectedProfile, hasAccounts)

  // Extract data from optimized response
  const last30DaysData = dashboardData?.last_30_days
  const currentMonthData = dashboardData?.current_month
  const momData = dashboardData?.mom_comparison
  const forecastData = dashboardData?.forecast

  // Fetch budget summary
  const { data: budgetSummary } = useQuery({
    queryKey: ['budgetSummary'],
    queryFn: () => budgetsApi.summary()
  })

  // Fetch budgets for projection info
  const { data: budgets } = useQuery({
    queryKey: ['budgets'],
    queryFn: () => budgetsApi.list()
  })

  // Fetch budget statuses for projection data
  const { data: budgetStatuses } = useQuery({
    queryKey: ['budgetStatuses', budgets],
    queryFn: async () => {
      if (!budgets || budgets.length === 0) return []
      const statuses = await Promise.all(
        budgets.map(b => budgetsApi.status(b.id))
      )
      return statuses
    },
    enabled: !!budgets && budgets.length > 0
  })

  // Find budgets projected to exceed
  const projectedToExceed = budgetStatuses?.filter(status => status.is_projected_to_exceed) || []

  // Analytics: Fetch historical data for last 90 days
  const analyticsStartDate = format(subDays(new Date(), 90), 'yyyy-MM-dd')
  const analyticsEndDate = format(new Date(), 'yyyy-MM-dd')

  const { data: dailyCostsForAnalytics } = useQuery({
    queryKey: ['dailyCostsAnalytics', selectedProfile, analyticsStartDate, analyticsEndDate],
    queryFn: () => costsApi.getDailyCosts(selectedProfile, analyticsStartDate, analyticsEndDate),
    enabled: hasAccounts && !!selectedProfile,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })

  const historicalData = dailyCostsForAnalytics?.daily_costs?.map((item: any) => ({
    date: item.date,
    cost: item.cost,
  })) || []

  // Analytics: Run forecast (7 days, ensemble method)
  const forecastMutation = useMutation({
    mutationFn: () => analyticsApi.forecast({
      historical_data: historicalData,
      days_ahead: 7,
      method: 'ensemble',
    }),
  })

  // Analytics: Run anomaly detection (all methods)
  const anomalyMutation = useMutation({
    mutationFn: () => analyticsApi.detectAnomalies({
      historical_data: historicalData,
      method: 'all',
      threshold: 2.5,
    }),
  })

  // PDF Export mutation
  const exportPDFMutation = useMutation({
    mutationFn: async () => {
      // Read S3 configuration from Settings
      const uploadToS3 = localStorage.getItem('s3ExportEnabled') === 'true'
      const s3Bucket = localStorage.getItem('s3ExportBucket') || ''

      return exportApi.exportCostPDF(
        selectedProfile,
        dateRanges.last30Days.start,
        dateRanges.last30Days.end,
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
        const fileName = exportApi.generateExportFileName('cost_report', selectedProfile, 'pdf')
        exportApi.downloadBlob(blob, fileName)
        alert(`✅ PDF report downloaded: ${fileName}`)
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

      return exportApi.exportCostExcel(
        selectedProfile,
        dateRanges.last30Days.start,
        dateRanges.last30Days.end,
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
        const fileName = exportApi.generateExportFileName('cost_report', selectedProfile, 'xlsx')
        exportApi.downloadBlob(blob, fileName)
        alert(`✅ Excel report downloaded: ${fileName}`)
      }
    },
    onError: (error: any) => {
      alert(`❌ Failed to export Excel: ${error.response?.data?.detail || error.message || 'Unknown error'}`)
    }
  })

  // Auto-run analytics when historical data is loaded
  const analyticsLoaded = historicalData.length > 0
  if (analyticsLoaded && !forecastMutation.data && !forecastMutation.isPending) {
    forecastMutation.mutate()
  }
  if (analyticsLoaded && !anomalyMutation.data && !anomalyMutation.isPending) {
    anomalyMutation.mutate()
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0
    }).format(amount)
  }

  // Show loading page while checking for accounts
  if (loadingAccounts) {
    return <LoadingPage message="Loading AWS accounts..." />
  }

  // Show setup page if there's an error fetching accounts or no accounts exist
  if (accountsError || !hasAccounts) {
    return <SetupRequired error={accountsError as Error | undefined} type="aws-accounts" />
  }

  return (
    <div className="container mx-auto px-4 py-8 animate-fade-in">
      {/* Header with Profile Selector */}
      <div className="mb-8 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-modernGray-900 tracking-tight">AWS Cost Dashboard</h1>
            <InfoModal
              content="This dashboard provides a comprehensive overview of your AWS costs including trends, forecasts, and budget tracking across all configured AWS accounts."
              variant="teal"
            />
          </div>
          <p className="text-modernGray-600 mt-2">Monitor your AWS costs across multiple accounts</p>
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
              <h3 className="text-lg font-semibold text-gray-800 mb-1">Export Cost Reports</h3>
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

      {/* No AWS Accounts Warning */}
      {!loadingAccounts && !hasAccounts && (
        <div className="card-accent-warning mb-8">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-modernYellow-600 rounded-card shadow-sm">
              <AlertCircle className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-modernGray-900 mb-2">No AWS Accounts Configured</h3>
              <p className="text-modernGray-700 mb-4">
                To view cost data and analytics, you need to add at least one AWS account first.
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
      )}

      {/* KPI Cards */}
      {hasAccounts && (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <KPICard
          title="Last 30 Days"
          value={last30DaysData ? `$${last30DaysData.total_cost.toLocaleString()}` : '$0.00'}
          subtitle="Total cost"
          icon="calendar"
          gradient="from-modernTeal-500 to-modernTeal-700"
          isLoading={loadingDashboard}
        />

        <KPICard
          title="Current Month"
          value={
            currentMonthData ? `$${currentMonthData.total_cost.toLocaleString()}` : '$0.00'
          }
          subtitle="as of today"
          icon="dollar"
          gradient="from-modernGreen-500 to-modernGreen-700"
          trend={
            momData
              ? {
                  value: momData.change_percent,
                  isPositive: momData.change_percent < 0,
                }
              : undefined
          }
          isLoading={loadingDashboard}
        />

        <KPICard
          title="Forecasted"
          value={
            forecastData ? `$${forecastData.forecasted_cost.toLocaleString()}` : '$0.00'
          }
          subtitle="for this month"
          icon="trending"
          gradient="from-brandRed-600 to-brandRed-800"
          isLoading={loadingDashboard}
        />
      </div>
      )}

      {/* Budget Summary */}
      {hasAccounts && budgetSummary && (
        <div className="card mb-8 border-l-4 border-modernYellow-600 animate-fade-in">
          <div className="flex justify-between items-start mb-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-gradient-to-br from-modernYellow-600 to-modernYellow-700 rounded-card shadow-md">
                <DollarSign className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-modernGray-900">Budget Overview</h2>
                <p className="text-sm text-modernGray-600 font-medium">
                  {budgetSummary.active_budgets > 0
                    ? `${budgetSummary.active_budgets} active budget${budgetSummary.active_budgets !== 1 ? 's' : ''}`
                    : 'No budgets configured'}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => navigate('/budgets')}
              className="btn-primary text-sm"
            >
              {budgetSummary.active_budgets > 0 ? 'Manage Budgets' : 'Create Budget'}
            </button>
          </div>

          {budgetSummary.active_budgets > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-5 bg-modernGray-50 rounded-card shadow-sm border border-modernGray-200 hover:shadow-md transition-all duration-200">
              <p className="text-xs text-modernGray-600 uppercase tracking-wide font-semibold mb-2">Total Budget</p>
              <p className="text-3xl font-bold bg-gradient-to-r from-modernTeal-600 to-modernTeal-700 bg-clip-text text-transparent">
                {formatCurrency(budgetSummary.total_budget_amount)}
              </p>
            </div>

            <div className="p-5 bg-modernGray-50 rounded-card shadow-sm border border-modernGray-200 hover:shadow-md transition-all duration-200">
              <p className="text-xs text-modernGray-600 uppercase tracking-wide font-semibold mb-2">Current Spend</p>
              <p className="text-3xl font-bold bg-gradient-to-r from-modernGreen-600 to-modernGreen-700 bg-clip-text text-transparent">
                {formatCurrency(budgetSummary.total_current_spend)}
              </p>
              <div className="mt-3 w-full bg-modernGray-200 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    budgetSummary.total_current_spend / budgetSummary.total_budget_amount >= 1
                      ? 'bg-gradient-to-r from-modernRed-500 to-modernRed-600'
                      : budgetSummary.total_current_spend / budgetSummary.total_budget_amount >= 0.8
                      ? 'bg-gradient-to-r from-modernYellow-500 to-modernYellow-600'
                      : 'bg-gradient-to-r from-modernGreen-500 to-modernGreen-600'
                  }`}
                  style={{
                    width: `${Math.min(
                      (budgetSummary.total_current_spend / budgetSummary.total_budget_amount) * 100,
                      100
                    )}%`
                  }}
                />
              </div>
              <p className="text-xs text-modernGray-600 mt-2 font-medium">
                {((budgetSummary.total_current_spend / budgetSummary.total_budget_amount) * 100).toFixed(1)}% used
              </p>
            </div>

            <div className="p-5 bg-modernGray-50 rounded-card shadow-sm border border-modernGray-200 hover:shadow-md transition-all duration-200">
              <p className="text-xs text-modernGray-600 uppercase tracking-wide font-semibold mb-2">Budget Alerts</p>
              <div className="flex flex-col gap-2 mt-2">
                <div className="flex flex-wrap gap-2">
                  {budgetSummary.budgets_exceeded > 0 && (
                    <div className="flex items-center gap-1 px-3 py-1.5 bg-modernRed-100 text-modernRed-700 rounded-full shadow-sm">
                      <AlertCircle className="w-4 h-4" />
                      <span className="text-xs font-semibold">{budgetSummary.budgets_exceeded} Exceeded</span>
                    </div>
                  )}
                  {budgetSummary.budgets_at_critical > 0 && (
                    <div className="flex items-center gap-1 px-3 py-1.5 bg-brandRed-100 text-brandRed-700 rounded-full shadow-sm">
                      <TrendingUp className="w-4 h-4" />
                      <span className="text-xs font-semibold">{budgetSummary.budgets_at_critical} Critical</span>
                    </div>
                  )}
                  {budgetSummary.budgets_at_warning > 0 && (
                    <div className="flex items-center gap-1 px-3 py-1.5 bg-modernYellow-100 text-modernYellow-700 rounded-full shadow-sm">
                      <AlertCircle className="w-4 h-4" />
                      <span className="text-xs font-semibold">{budgetSummary.budgets_at_warning} Warning</span>
                    </div>
                  )}
                  {budgetSummary.budgets_exceeded === 0 &&
                   budgetSummary.budgets_at_critical === 0 &&
                   budgetSummary.budgets_at_warning === 0 &&
                   projectedToExceed.length === 0 && (
                    <span className="text-sm text-modernGreen-700 font-semibold bg-modernGreen-100 px-3 py-1.5 rounded-full">✓ All budgets on track</span>
                  )}
                </div>

                {/* Projection warnings */}
                {projectedToExceed.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-modernGray-200">
                    <p className="text-xs text-modernGray-600 font-semibold mb-2">⚠️ Projected to Exceed:</p>
                    {projectedToExceed.map((status) => (
                      <div key={status.budget_id} className="text-xs text-modernTeal-800 bg-modernTeal-50 px-3 py-2 rounded-card mb-1.5 border border-modernTeal-200">
                        <span className="font-bold">{status.budget_name}</span>
                        {' · '}
                        Est: {formatCurrency(status.projected_spend || 0)}
                        {' '}({status.projected_percentage?.toFixed(1)}%)
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
          ) : (
            <div className="text-center py-12 bg-white rounded-xl">
              <DollarSign className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-600 mb-4 font-medium">No budgets configured yet</p>
              <p className="text-gray-500 text-sm mb-6">Create your first budget to start tracking spending</p>
              <button
                type="button"
                onClick={() => navigate('/budgets')}
                className="btn-primary shadow-lg hover:shadow-xl transition-shadow"
              >
                Create Your First Budget
              </button>
            </div>
          )}
        </div>
      )}

      {/* Charts */}
      {hasAccounts && (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost Trend Chart */}
        <div className="card hover:shadow-xl transition-all duration-300 border-l-4 border-blue-500">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2.5 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shadow-md">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Cost Trend</h2>
              <p className="text-sm text-gray-500 font-medium">Last 30 Days</p>
            </div>
          </div>
          <CostTrendChart
            profileName={selectedProfile}
            startDate={dateRanges.last30Days.start}
            endDate={dateRanges.last30Days.end}
          />
        </div>

        {/* Service Breakdown */}
        <div className="card hover:shadow-xl transition-all duration-300 border-l-4 border-purple-500">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2.5 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg shadow-md">
              <PieChart className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Top Services</h2>
              <p className="text-sm text-gray-500 font-medium">Current Month</p>
            </div>
          </div>
          <ServiceBreakdownPie
            profileName={selectedProfile}
            startDate={dateRanges.currentMonth.start}
            endDate={dateRanges.currentMonth.end}
          />
        </div>
      </div>
      )}

      {/* Advanced Cost Analytics Section */}
      {hasAccounts && (
      <div className="mt-8">
        <div className="flex items-center gap-3 mb-6">
          <TrendingUp className="w-7 h-7 text-blue-600" />
          <h2 className="text-2xl font-bold text-gray-900">Advanced Cost Analytics</h2>
        </div>

        {/* Analytics Widgets - AI-Powered Insights */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <QuickForecastWidget
            forecast={forecastMutation.data || null}
            isLoading={forecastMutation.isPending}
          />
          <AnomalyAlertWidget
            anomalies={anomalyMutation.data?.anomalies || []}
            isLoading={anomalyMutation.isPending}
          />
        </div>

        {/* Cost Forecast - Full Width */}
        <div className="card mb-6">
          <ForecastChart profileName={selectedProfile} />
        </div>

        {/* Trend Analysis - Full Width */}
        <div className="card mb-6">
          <TrendAnalysisChart profileName={selectedProfile} />
        </div>

        {/* MoM and YoY Comparison - Side by Side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <MoMComparisonChart
              profileName={selectedProfile}
              momData={dashboardData?.mom_comparison}
            />
          </div>
          <div className="card">
            <YoYComparisonChart profileName={selectedProfile} />
          </div>
        </div>
      </div>
      )}
    </div>
  )
}
