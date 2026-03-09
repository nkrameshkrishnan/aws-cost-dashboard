import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X, ChevronRight, TrendingUp, Loader2 } from 'lucide-react'
import { costsApi } from '@/api/costs'
import type { DrillDownResponse, DrillDownFilters } from '@/types'

interface DrillDownLevel {
  dimension: string
  dimensionLabel: string
  value?: string
  filters: DrillDownFilters
}

interface DrillDownModalProps {
  isOpen: boolean
  onClose: () => void
  profileName: string
  startDate: string
  endDate: string
  initialDimension?: string
  initialValue?: string
  initialFilters?: DrillDownFilters
}

const DIMENSION_LABELS: Record<string, string> = {
  SERVICE: 'Services',
  REGION: 'Regions',
  LINKED_ACCOUNT: 'Linked Accounts',
  USAGE_TYPE: 'Usage Types',
  INSTANCE_TYPE: 'Instance Types',
}

const DRILL_DOWN_SEQUENCE = ['SERVICE', 'REGION', 'LINKED_ACCOUNT']

export function DrillDownModal({
  isOpen,
  onClose,
  profileName,
  startDate,
  endDate,
  initialDimension = 'SERVICE',
  initialValue,
  initialFilters = {},
}: DrillDownModalProps) {
  const [currentLevel, setCurrentLevel] = useState(0)
  const [drillPath, setDrillPath] = useState<DrillDownLevel[]>([
    {
      dimension: initialDimension,
      dimensionLabel: DIMENSION_LABELS[initialDimension] || initialDimension,
      value: initialValue,
      filters: initialFilters,
    },
  ])
  const [data, setData] = useState<DrillDownResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch drill-down data
  useEffect(() => {
    if (!isOpen) return

    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const currentPath = drillPath[currentLevel]
        const response = await costsApi.getDrillDown(
          profileName,
          startDate,
          endDate,
          currentPath.dimension,
          currentPath.filters
        )
        setData(response)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch drill-down data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [isOpen, profileName, startDate, endDate, currentLevel, drillPath])

  // Close on escape key
  useEffect(() => {
    if (isOpen) {
      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          onClose()
        }
      }
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, onClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  const handleDrillDown = (value: string) => {
    const currentPath = drillPath[currentLevel]
    const currentDimensionIndex = DRILL_DOWN_SEQUENCE.indexOf(currentPath.dimension)

    // Check if we can drill down further
    if (currentDimensionIndex < DRILL_DOWN_SEQUENCE.length - 1) {
      const nextDimension = DRILL_DOWN_SEQUENCE[currentDimensionIndex + 1]

      // Build new filters
      const newFilters: DrillDownFilters = { ...currentPath.filters }
      if (currentPath.dimension === 'SERVICE') {
        newFilters.service = value
      } else if (currentPath.dimension === 'REGION') {
        newFilters.region = value
      } else if (currentPath.dimension === 'LINKED_ACCOUNT') {
        newFilters.account_id = value
      }

      // Add new level to drill path
      const newPath = [
        ...drillPath.slice(0, currentLevel + 1),
        {
          dimension: nextDimension,
          dimensionLabel: DIMENSION_LABELS[nextDimension] || nextDimension,
          value,
          filters: newFilters,
        },
      ]

      setDrillPath(newPath)
      setCurrentLevel(currentLevel + 1)
    }
  }

  const handleBreadcrumbClick = (index: number) => {
    setCurrentLevel(index)
    setDrillPath(drillPath.slice(0, index + 1))
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(amount)
  }

  if (!isOpen) return null

  const modalRoot = document.getElementById('modal-root')
  if (!modalRoot) return null

  const currentPath = drillPath[currentLevel]
  const canDrillDown = DRILL_DOWN_SEQUENCE.indexOf(currentPath.dimension) < DRILL_DOWN_SEQUENCE.length - 1

  const modal = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-brandRed-50 to-modernTeal-50">
          <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-brandRed-700" />
              Cost Drill-Down Analysis
            </h3>

            {/* Breadcrumbs */}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {drillPath.map((path, index) => (
                <div key={index} className="flex items-center gap-2">
                  {index > 0 && <ChevronRight className="w-4 h-4 text-gray-400" />}
                  <button
                    type="button"
                    onClick={() => handleBreadcrumbClick(index)}
                    className={`text-sm px-2 py-1 rounded transition-colors ${
                      index === currentLevel
                        ? 'bg-brandRed-700 text-white font-medium shadow-button'
                        : 'bg-white text-gray-600 hover:bg-brandRed-50 hover:text-brandRed-700'
                    }`}
                  >
                    {path.value || path.dimensionLabel}
                  </button>
                </div>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 hover:bg-white/50 rounded-lg transition-colors ml-4"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-6 overflow-y-auto max-h-[calc(85vh-200px)]">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-brandRed-700 animate-spin" />
              <p className="text-gray-600 mt-4">Loading {currentPath.dimensionLabel.toLowerCase()}...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="bg-modernRed-50 border border-modernRed-200 rounded-lg p-4 max-w-md">
                <p className="text-modernRed-700 text-sm">{error}</p>
              </div>
            </div>
          ) : data && Array.isArray(data.breakdown) && data.breakdown.length > 0 ? (
            <>
              {/* Summary */}
              <div className="bg-gradient-to-br from-brandRed-50 to-modernTeal-50 rounded-lg p-4 mb-6 border border-brandRed-100">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Cost</p>
                    <p className="text-2xl font-bold text-brandRed-700">{formatCurrency(data.total_cost)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-600">Showing</p>
                    <p className="text-lg font-semibold text-gray-900">
                      {data.breakdown.length} {currentPath.dimensionLabel.toLowerCase()}
                    </p>
                  </div>
                </div>
              </div>

              {/* Breakdown Table */}
              <div className="space-y-2">
                {data.breakdown.map((record, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => canDrillDown && handleDrillDown(record.dimension_value)}
                    className={`w-full text-left p-4 rounded-lg border border-gray-200 transition-all ${
                      canDrillDown
                        ? 'hover:border-brandRed-300 hover:shadow-card-hover hover:bg-brandRed-50/30 cursor-pointer'
                        : 'cursor-default'
                    }`}
                    disabled={!canDrillDown}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-gray-900 truncate">
                            {record.dimension_value}
                          </p>
                          {canDrillDown && (
                            <ChevronRight className="w-4 h-4 text-brandRed-600 flex-shrink-0" />
                          )}
                        </div>
                        <div className="flex items-center gap-4 mt-1">
                          <span className="text-sm text-gray-500">
                            {record.percentage.toFixed(1)}% of total
                          </span>
                        </div>
                      </div>
                      <div className="text-right ml-4">
                        <p className="text-lg font-semibold text-brandRed-700">
                          {formatCurrency(record.cost)}
                        </p>
                      </div>
                    </div>

                    {/* Progress bar */}
                    <div className="mt-3">
                      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-brandRed-600 to-modernTeal-500 transition-all duration-500"
                          style={{ width: `${Math.min(record.percentage, 100)}%` }}
                        />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-12">
              <p className="text-gray-500">No data available for this breakdown</p>
            </div>
          )}
        </div>

        {/* Footer */}
              <div className="px-6 py-4 border-t border-gray-100 bg-gray-50">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {canDrillDown
                ? '💡 Click on an item to drill down further'
                : 'Maximum drill-down level reached'}
            </p>
            <button
              type="button"
              onClick={onClose}
              className="py-2.5 px-6 rounded-button font-medium text-white bg-brandRed-700 hover:bg-brandRed-800 shadow-button hover:shadow-button-hover transition-all"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(modal, modalRoot)
}
