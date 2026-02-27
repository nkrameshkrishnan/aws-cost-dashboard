import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { calculateUnitCosts, getUnitCostTrend } from '@/api/unitCosts'

const AWS_REGIONS = [
  'us-east-1',
  'us-east-2',
  'us-west-1',
  'us-west-2',
  'ap-south-1',
  'ap-northeast-1',
  'ap-northeast-2',
  'ap-southeast-1',
  'ap-southeast-2',
  'eu-central-1',
  'eu-west-1',
  'eu-west-2',
  'sa-east-1',
]

export const useMultiRegionUnitCosts = (
  profileName: string,
  startDate: string,
  endDate: string,
  currentRegion: string,
  metricType: string = 'cost_per_user'
) => {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!profileName || !startDate || !endDate) return

    // Prefetch data for all regions except the currently selected one
    // This runs in the background and caches the results
    AWS_REGIONS.forEach((region) => {
      if (region !== currentRegion) {
        // Prefetch unit costs for this region
        queryClient.prefetchQuery({
          queryKey: ['unitCosts', profileName, startDate, endDate, region],
          queryFn: () => calculateUnitCosts(profileName, startDate, endDate, region),
          staleTime: 5 * 60 * 1000, // Cache for 5 minutes
        })

        // Prefetch trend data for this region
        queryClient.prefetchQuery({
          queryKey: ['unitCostTrend', profileName, metricType, 6, region],
          queryFn: () => getUnitCostTrend(profileName, metricType, 6, region),
          staleTime: 5 * 60 * 1000, // Cache for 5 minutes
        })
      }
    })
  }, [profileName, startDate, endDate, currentRegion, metricType, queryClient])
}
