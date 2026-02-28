import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

/**
 * Multi-region unit costs prefetching hook.
 *
 * Currently disabled to avoid overwhelming the backend with concurrent async jobs.
 * With async jobs taking 2+ minutes each, prefetching 12 regions would create
 * 24 concurrent jobs (unit costs + trend), which is inefficient.
 *
 * Users can manually switch regions and data loads on-demand.
 * Future improvement: Implement background job queue with rate limiting.
 */
export function useMultiRegionUnitCosts(
  profileName: string,
  startDate: string,
  endDate: string,
  currentRegion: string,
  metricType: string = 'cost_per_user'
) {
  const queryClient = useQueryClient()

  useEffect(() => {
    // Intentionally empty - prefetching disabled (see function docstring)
  }, [profileName, startDate, endDate, currentRegion, metricType, queryClient])
}
