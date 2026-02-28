import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  calculateUnitCostsAsync,
  getUnitCostTrendAsync,
  pollJobUntilComplete,
  getBusinessMetrics,
  createBusinessMetric,
  type UnitCost,
  type UnitCostTrend,
  type BusinessMetric
} from '@/api/unitCosts'

const CACHE_TIME = 5 * 60 * 1000 // 5 minutes

export function useUnitCosts(
  profileName: string,
  startDate: string,
  endDate: string,
  region: string = 'us-east-2'
) {
  return useQuery<UnitCost>({
    queryKey: ['unitCosts', profileName, startDate, endDate, region],
    queryFn: async () => {
      const { job_id } = await calculateUnitCostsAsync(profileName, startDate, endDate, region)
      return pollJobUntilComplete<UnitCost>(job_id)
    },
    enabled: !!profileName && !!startDate && !!endDate && !!region,
    retry: 1,
    staleTime: CACHE_TIME,
  })
}

export function useUnitCostTrend(
  profileName: string,
  metricType: string,
  months: number = 6,
  region: string = 'us-east-2'
) {
  return useQuery<UnitCostTrend>({
    queryKey: ['unitCostTrend', profileName, metricType, months, region],
    queryFn: async () => {
      const { job_id } = await getUnitCostTrendAsync(profileName, metricType, months, region)
      return pollJobUntilComplete<UnitCostTrend>(job_id)
    },
    enabled: !!profileName && !!metricType && !!region,
    retry: 1,
    staleTime: CACHE_TIME,
  })
}

export function useBusinessMetrics(
  profileName: string,
  startDate: string,
  endDate: string
) {
  return useQuery<BusinessMetric[]>({
    queryKey: ['businessMetrics', profileName, startDate, endDate],
    queryFn: () => getBusinessMetrics(profileName, startDate, endDate),
    enabled: !!profileName && !!startDate && !!endDate,
  })
}

export function useCreateBusinessMetric() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createBusinessMetric,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['businessMetrics'] })
      queryClient.invalidateQueries({ queryKey: ['unitCosts'] })
      queryClient.invalidateQueries({ queryKey: ['unitCostTrend'] })
    },
  })
}
