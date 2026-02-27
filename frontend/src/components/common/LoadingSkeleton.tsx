interface LoadingSkeletonProps {
  variant?: 'text' | 'card' | 'chart' | 'table' | 'kpi' | 'list'
  count?: number
  className?: string
}

export function LoadingSkeleton({ variant = 'text', count = 1, className = '' }: LoadingSkeletonProps) {
  const baseClass = 'animate-pulse bg-gradient-to-r from-modernGray-200 via-modernGray-100 to-modernGray-200 bg-[length:200%_100%] rounded'

  const renderSkeleton = () => {
    switch (variant) {
      case 'kpi':
        return (
          <div className={`card p-6 ${className}`}>
            <div className="flex items-center justify-between mb-4">
              <div className={`h-4 w-24 ${baseClass}`} />
              <div className={`h-10 w-10 rounded-lg ${baseClass}`} />
            </div>
            <div className={`h-8 w-32 mb-2 ${baseClass}`} />
            <div className={`h-3 w-20 ${baseClass}`} />
          </div>
        )

      case 'card':
        return (
          <div className={`card p-6 ${className}`}>
            <div className={`h-6 w-48 mb-4 ${baseClass}`} />
            <div className="space-y-3">
              <div className={`h-4 w-full ${baseClass}`} />
              <div className={`h-4 w-3/4 ${baseClass}`} />
              <div className={`h-4 w-5/6 ${baseClass}`} />
            </div>
          </div>
        )

      case 'chart':
        return (
          <div className={`card p-6 ${className}`}>
            <div className={`h-6 w-40 mb-6 ${baseClass}`} />
            <div className={`h-64 w-full ${baseClass}`} />
          </div>
        )

      case 'table':
        return (
          <div className={`card p-6 ${className}`}>
            {/* Table Header */}
            <div className="grid grid-cols-4 gap-4 mb-4 pb-4 border-b border-modernGray-200">
              {[...Array(4)].map((_, i) => (
                <div key={`header-${i}`} className={`h-4 ${baseClass}`} />
              ))}
            </div>
            {/* Table Rows */}
            {[...Array(5)].map((_, rowIndex) => (
              <div key={`row-${rowIndex}`} className="grid grid-cols-4 gap-4 mb-3">
                {[...Array(4)].map((_, colIndex) => (
                  <div key={`cell-${rowIndex}-${colIndex}`} className={`h-4 ${baseClass}`} />
                ))}
              </div>
            ))}
          </div>
        )

      case 'list':
        return (
          <div className={`space-y-3 ${className}`}>
            {[...Array(count)].map((_, i) => (
              <div key={i} className="card p-4">
                <div className="flex items-center gap-4">
                  <div className={`h-12 w-12 rounded-full ${baseClass}`} />
                  <div className="flex-1 space-y-2">
                    <div className={`h-4 w-3/4 ${baseClass}`} />
                    <div className={`h-3 w-1/2 ${baseClass}`} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )

      case 'text':
      default:
        return (
          <div className={`space-y-2 ${className}`}>
            {[...Array(count)].map((_, i) => (
              <div key={i} className={`h-4 w-full ${baseClass}`} />
            ))}
          </div>
        )
    }
  }

  return <>{renderSkeleton()}</>
}

// Individual skeleton components for specific use cases
export function SkeletonKPICard({ className = '' }: { className?: string }) {
  return <LoadingSkeleton variant="kpi" className={className} />
}

export function SkeletonCard({ className = '' }: { className?: string }) {
  return <LoadingSkeleton variant="card" className={className} />
}

export function SkeletonChart({ className = '' }: { className?: string }) {
  return <LoadingSkeleton variant="chart" className={className} />
}

export function SkeletonTable({ className = '' }: { className?: string }) {
  return <LoadingSkeleton variant="table" className={className} />
}

export function SkeletonList({ count = 3, className = '' }: { count?: number; className?: string }) {
  return <LoadingSkeleton variant="list" count={count} className={className} />
}
