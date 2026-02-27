import { useQuery } from '@tanstack/react-query'
import {
  getRightSizingRecommendations,
  getRightSizingSummary,
  getTopSavingsOpportunities,
  RightSizingRecommendationsResponse,
  RightSizingSummary,
  RightSizingRecommendation
} from '@/api/rightsizing'

export const useRightSizingRecommendations = (profileName: string, resourceTypes?: string) => {
  return useQuery<RightSizingRecommendationsResponse>({
    queryKey: ['rightSizingRecommendations', profileName, resourceTypes],
    queryFn: () => getRightSizingRecommendations(profileName, resourceTypes),
    enabled: !!profileName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export const useRightSizingSummary = (profileName: string) => {
  return useQuery<RightSizingSummary>({
    queryKey: ['rightSizingSummary', profileName],
    queryFn: () => getRightSizingSummary(profileName),
    enabled: !!profileName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export const useTopSavingsOpportunities = (profileName: string, limit: number = 10) => {
  return useQuery<RightSizingRecommendation[]>({
    queryKey: ['topSavingsOpportunities', profileName, limit],
    queryFn: () => getTopSavingsOpportunities(profileName, limit),
    enabled: !!profileName,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
