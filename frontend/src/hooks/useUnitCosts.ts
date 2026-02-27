import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  calculateUnitCosts,
  getUnitCostTrend,
  getBusinessMetrics,
  createBusinessMetric,
  UnitCost,
  UnitCostTrend,
  BusinessMetric
} from '@/api/unitCosts'

export const useUnitCosts = (profileName: string, startDate: string, endDate: string, region: string = 'us-east-2') => {
  return useQuery<UnitCost>({
    queryKey: ['unitCosts', profileName, startDate, endDate, region],
    queryFn: () => calculateUnitCosts(profileName, startDate, endDate, region),
    enabled: !!profileName && !!startDate && !!endDate && !!region,
  })
}

export const useUnitCostTrend = (profileName: string, metricType: string, months: number = 6, region: string = 'us-east-2') => {
  return useQuery<UnitCostTrend>({
    queryKey: ['unitCostTrend', profileName, metricType, months, region],
    queryFn: () => getUnitCostTrend(profileName, metricType, months, region),
    enabled: !!profileName && !!metricType && !!region,
  })
}

export const useBusinessMetrics = (profileName: string, startDate: string, endDate: string) => {
  return useQuery<BusinessMetric[]>({
    queryKey: ['businessMetrics', profileName, startDate, endDate],
    queryFn: () => getBusinessMetrics(profileName, startDate, endDate),
    enabled: !!profileName && !!startDate && !!endDate,
  })
}

export const useCreateBusinessMetric = () => {
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
