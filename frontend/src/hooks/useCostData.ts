import { useQuery } from '@tanstack/react-query'
import { costsApi } from '@/api/costs'
import { format, subDays, startOfMonth, endOfMonth } from 'date-fns'

/**
 * Hook to fetch cost summary for a profile
 */
export function useCostSummary(
  profileName: string,
  startDate: string,
  endDate: string,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['costSummary', profileName, startDate, endDate],
    queryFn: () => costsApi.getSummary(profileName, startDate, endDate),
    enabled: enabled && !!profileName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to fetch daily costs for a profile
 */
export function useDailyCosts(
  profileName: string,
  startDate: string,
  endDate: string,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['dailyCosts', profileName, startDate, endDate],
    queryFn: () => costsApi.getDailyCosts(profileName, startDate, endDate),
    enabled: enabled && !!profileName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to fetch service breakdown
 */
export function useServiceBreakdown(
  profileName: string,
  startDate: string,
  endDate: string,
  topN: number = 10,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['serviceBreakdown', profileName, startDate, endDate, topN],
    queryFn: () => costsApi.getServiceBreakdown(profileName, startDate, endDate, topN),
    enabled: enabled && !!profileName,
    staleTime: 15 * 60 * 1000, // 15 minutes
  })
}

/**
 * Hook to fetch cost trend
 */
export function useCostTrend(
  profileName: string,
  months: number = 6,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['costTrend', profileName, months],
    queryFn: () => costsApi.getCostTrend(profileName, months),
    enabled: enabled && !!profileName,
    staleTime: 60 * 60 * 1000, // 1 hour
  })
}

/**
 * Hook to fetch month-over-month comparison
 */
export function useMoMComparison(
  profileName: string,
  currentMonthStart: string,
  currentMonthEnd: string,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['momComparison', profileName, currentMonthStart, currentMonthEnd],
    queryFn: () => costsApi.getMoMComparison(profileName, currentMonthStart, currentMonthEnd),
    enabled: enabled && !!profileName,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}

/**
 * Hook to fetch year-over-year comparison
 */
export function useYoYComparison(
  profileName: string,
  currentPeriodStart: string,
  currentPeriodEnd: string,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['yoyComparison', profileName, currentPeriodStart, currentPeriodEnd],
    queryFn: () => costsApi.getYoYComparison(profileName, currentPeriodStart, currentPeriodEnd),
    enabled: enabled && !!profileName && !!currentPeriodStart && !!currentPeriodEnd,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}

/**
 * Hook to fetch cost forecast
 */
export function useCostForecast(
  profileName: string,
  days: number = 30,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['costForecast', profileName, days],
    queryFn: () => costsApi.getForecast(profileName, days),
    enabled: enabled && !!profileName,
    staleTime: 60 * 60 * 1000, // 1 hour
  })
}

/**
 * Hook to fetch daily cost forecast with granular data
 */
export function useDailyForecast(
  profileName: string,
  days: number = 30,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['dailyForecast', profileName, days],
    queryFn: () => costsApi.getForecast(profileName, days, 'DAILY'),
    enabled: enabled && !!profileName,
    staleTime: 60 * 60 * 1000, // 1 hour
  })
}

/**
 * Optimized hook to fetch all dashboard data in a single API call.
 * Reduces the number of API requests from 4+ to just 1.
 * Returns: last 30 days cost, current month cost, MoM comparison, and forecast.
 */
export function useDashboardData(
  profileName: string,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: ['dashboardData', profileName],
    queryFn: () => costsApi.getDashboardData(profileName),
    enabled: enabled && !!profileName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Helper hook to get date ranges for common periods
 */
export function useDateRanges() {
  const today = new Date()

  return {
    last30Days: {
      start: format(subDays(today, 30), 'yyyy-MM-dd'),
      end: format(today, 'yyyy-MM-dd'),
    },
    currentMonth: {
      start: format(startOfMonth(today), 'yyyy-MM-dd'),
      end: format(endOfMonth(today), 'yyyy-MM-dd'),
    },
    last7Days: {
      start: format(subDays(today, 7), 'yyyy-MM-dd'),
      end: format(today, 'yyyy-MM-dd'),
    },
  }
}
