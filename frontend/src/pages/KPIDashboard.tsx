/**
 * KPI Dashboard Page
 * Displays AWS Cost Management KPIs with organization and per-account views
 */
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useProfileStore } from '@/store/profileStore'
import { ProfileSelector } from '@/components/common/ProfileSelector'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { KPIMetricCard } from '@/components/kpi/KPIMetricCard'
import { kpiApi } from '@/api/kpi'
import { finopsApi } from '@/api/finops'
import { KPIDefinition, KPIValue } from '@/types/kpi'
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  AlertCircle,
  Loader2,
  Building,
  Cloud
} from 'lucide-react'

type ViewMode = 'organization' | 'account'

export function KPIDashboard() {
  const { selectedProfile } = useProfileStore()
  const [viewMode, setViewMode] = useState<ViewMode>('account')
  const [auditRunning, setAuditRunning] = useState(false)

  // Fetch KPI definitions
  const { data: definitions, isLoading: loadingDefinitions } = useQuery({
    queryKey: ['kpi-definitions'],
    queryFn: () => kpiApi.getDefinitions(),
    staleTime: 1000 * 60 * 60, // 1 hour
  })

  // Fetch KPI values
  const { data: kpiValues, isLoading: loadingKPIs, error: kpiError } = useQuery({
    queryKey: ['kpi-values', selectedProfile],
    queryFn: () => kpiApi.calculateAllKPIs(selectedProfile),
    enabled: !!selectedProfile,
    refetchInterval: 1000 * 60 * 5, // Refresh every 5 minutes
  })

  // Trigger background audit when profile is selected
  useEffect(() => {
    const triggerBackgroundAudit = async () => {
      if (!selectedProfile || auditRunning) return

      try {
        setAuditRunning(true)
        await finopsApi.startAsyncAudit({
          account_name: selectedProfile,
          audit_types: ['idle_instances', 'unattached_volumes', 'unattached_ips', 'untagged_resources']
        })
        console.log(`Background audit started for ${selectedProfile}`)
      } catch (error) {
        console.error('Failed to start background audit:', error)
      } finally {
        setAuditRunning(false)
      }
    }

    triggerBackgroundAudit()
  }, [selectedProfile])

  const isLoading = loadingDefinitions || loadingKPIs

  // Get summary stats
  const getSummaryStats = () => {
    if (!kpiValues) return null

    const values = Object.values(kpiValues)
    const excellentCount = values.filter(v => v.status === 'excellent').length
    const poorCount = values.filter(v => v.status === 'poor').length
    const warningCount = values.filter(v => v.status === 'warning').length

    return { excellentCount, poorCount, warningCount, totalCount: values.length }
  }

  const summary = getSummaryStats()

  return (
    <div className="container mx-auto px-4 py-8 animate-fade-in">
      {/* Header */}
      <div className="mb-8 flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-modernGray-900 tracking-tight">KPI Dashboard</h1>
          <p className="text-modernGray-600 mt-2">
            Key performance indicators for AWS cost management and FinOps
          </p>
          {auditRunning && (
            <div className="mt-3 flex items-center gap-2 text-sm text-modernTeal-700">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Running background audit...</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <ProfileSelector />
        </div>
      </div>

      {/* View Mode Selector and Summary */}
      <div className="card mb-8 border-l-4 border-brandRed-700">
        <div className="flex flex-col gap-4">
          {/* View Mode Toggle */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex bg-modernGray-100 rounded-button p-1">
                <button
                  onClick={() => setViewMode('account')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200 ${
                    viewMode === 'account'
                      ? 'bg-white shadow-md text-brandRed-700 font-semibold'
                      : 'text-modernGray-600 hover:text-modernGray-900'
                  }`}
                >
                  <Cloud className="w-4 h-4" />
                  <span className="text-sm">Account View</span>
                </button>
                <button
                  onClick={() => setViewMode('organization')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200 ${
                    viewMode === 'organization'
                      ? 'bg-white shadow-md text-brandRed-700 font-semibold'
                      : 'text-modernGray-600 hover:text-modernGray-900'
                  }`}
                  disabled
                  title="Organization view coming soon"
                >
                  <Building className="w-4 h-4" />
                  <span className="text-sm">Organization</span>
                  <span className="text-xs bg-modernYellow-100 text-modernYellow-800 px-2 py-0.5 rounded-full">
                    Soon
                  </span>
                </button>
              </div>
            </div>

            {/* Summary Badges */}
            {summary && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="badge-success">
                  {summary.excellentCount} Excellent
                </span>
                {summary.warningCount > 0 && (
                  <span className="badge-warning">
                    {summary.warningCount} Warning
                  </span>
                )}
                {summary.poorCount > 0 && (
                  <span className="badge-error">
                    {summary.poorCount} Needs Attention
                  </span>
                )}
                <span className="badge-neutral">
                  {summary.totalCount} Total Metrics
                </span>
              </div>
            )}
          </div>

          {/* Account info */}
          {viewMode === 'account' && selectedProfile && (
            <div className="flex items-center gap-2 text-sm text-modernGray-600 pt-3 border-t border-modernGray-200">
              <Cloud className="w-4 h-4" />
              <span>Viewing KPIs for: <span className="font-semibold text-modernGray-900">{selectedProfile}</span></span>
            </div>
          )}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="card">
          <div className="py-12">
            <LoadingSpinner size="lg" text="Loading KPI metrics..." />
          </div>
        </div>
      )}

      {/* Error State */}
      {kpiError && (
        <div className="card-accent-error">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-modernRed-600 rounded-card">
              <AlertCircle className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-modernGray-900 mb-2">
                Failed to Load KPIs
              </h3>
              <p className="text-modernGray-700">
                {kpiError instanceof Error ? kpiError.message : 'An unknown error occurred'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* KPI Metrics Grid */}
      {!isLoading && !kpiError && kpiValues && definitions && (
        <>
          <div className="mb-6">
            <h2 className="text-xl font-bold text-modernGray-900 mb-2">Performance Metrics</h2>
            <p className="text-sm text-modernGray-600">
              AWS cost management KPIs calculated for the current period
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            {Object.entries(kpiValues).map(([kpiId, value]) => {
              const definition = definitions[kpiId]
              if (!definition) return null

              return (
                <KPIMetricCard
                  key={kpiId}
                  kpi={definition}
                  value={value}
                />
              )
            })}
          </div>

          {/* About Section */}
          <div className="card border-l-4 border-modernTeal-600">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-modernTeal-100 rounded-card">
                <BarChart3 className="w-6 h-6 text-modernTeal-700" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-modernGray-900 mb-2">
                  About AWS Cost KPIs
                </h3>
                <p className="text-sm text-modernGray-700 mb-3">
                  These Key Performance Indicators help you understand your AWS cost performance,
                  identify optimization opportunities, and track progress toward your FinOps goals.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-modernGray-600">
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-modernGreen-600 rounded-full mt-1"></div>
                    <div>
                      <strong>Excellent:</strong> Performance exceeds targets, well optimized
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-modernTeal-600 rounded-full mt-1"></div>
                    <div>
                      <strong>Good:</strong> Performance meets expectations, on track
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-modernYellow-600 rounded-full mt-1"></div>
                    <div>
                      <strong>Warning:</strong> Performance needs attention, review recommended
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-modernRed-600 rounded-full mt-1"></div>
                    <div>
                      <strong>Poor:</strong> Critical attention needed, immediate action required
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
