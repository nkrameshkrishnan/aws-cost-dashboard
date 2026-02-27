import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '@/api/analytics'

/**
 * Hook to fetch AWS Cost Forecast with fallback to statistical forecast.
 *
 * Uses AWS Cost Explorer Forecast API when available,
 * falls back to linear regression when AWS forecast is unavailable.
 */
export function useAWSForecast(
  accountName: string,
  days: number = 30,
  useFallback: boolean = false,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['awsForecast', accountName, days, useFallback],
    queryFn: () => analyticsApi.getAWSForecast(accountName, days, useFallback),
    enabled: enabled && !!accountName,
    staleTime: 60 * 60 * 1000, // 1 hour - forecasts are relatively stable
    retry: 2, // Retry twice on failure
  })
}

/**
 * Hook to fetch Month-over-Month cost comparison.
 *
 * Compares current month costs to previous month with percentage change.
 */
export function useAWSMoMComparison(
  accountName: string,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['awsMoMComparison', accountName],
    queryFn: () => analyticsApi.getMoMComparison(accountName),
    enabled: enabled && !!accountName,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}

/**
 * Hook to fetch Year-over-Year cost comparison.
 *
 * Compares current month costs to same month last year with percentage change.
 */
export function useAWSYoYComparison(
  accountName: string,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['awsYoYComparison', accountName],
    queryFn: () => analyticsApi.getYoYComparison(accountName),
    enabled: enabled && !!accountName,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}

/**
 * Combined hook to fetch all forecast analytics data.
 * Useful for analytics dashboard pages.
 */
export function useForecastAnalytics(
  accountName: string,
  forecastDays: number = 30,
  enabled: boolean = true
) {
  const forecast = useAWSForecast(accountName, forecastDays, false, enabled)
  const momComparison = useAWSMoMComparison(accountName, enabled)
  const yoyComparison = useAWSYoYComparison(accountName, enabled)

  return {
    forecast,
    momComparison,
    yoyComparison,
    isLoading: forecast.isLoading || momComparison.isLoading || yoyComparison.isLoading,
    isError: forecast.isError || momComparison.isError || yoyComparison.isError,
    error: forecast.error || momComparison.error || yoyComparison.error,
  }
}
