import axios from './axios'

export interface RightSizingRecommendation {
  resource_arn: string
  resource_name: string
  resource_type: string
  current_config: string
  recommended_config: string
  finding: string
  region?: string
  cpu_utilization?: number
  memory_utilization?: number
  performance_risk?: number
  estimated_monthly_savings: number
  savings_percentage?: number
  recommendation_source: string
}

export interface RightSizingRecommendationsResponse {
  profile_name: string
  total_recommendations: number
  total_monthly_savings: number
  recommendations_by_type: Record<string, number>
  recommendations: RightSizingRecommendation[]
}

export interface RightSizingSummary {
  profile_name: string
  total_ec2_recommendations: number
  total_ebs_recommendations: number
  total_lambda_recommendations: number
  total_asg_recommendations: number
  total_potential_savings: number
  overprovisioned_resources: number
  underprovisioned_resources: number
  optimized_resources: number
}

export const getRightSizingRecommendations = async (
  profileName: string,
  resourceTypes?: string
): Promise<RightSizingRecommendationsResponse> => {
  const response = await axios.get('/rightsizing/recommendations', {
    params: { profile_name: profileName, resource_types: resourceTypes }
  })
  return response.data
}

export const getRightSizingSummary = async (
  profileName: string
): Promise<RightSizingSummary> => {
  const response = await axios.get('/rightsizing/summary', {
    params: { profile_name: profileName }
  })
  return response.data
}

export const getTopSavingsOpportunities = async (
  profileName: string,
  limit: number = 10
): Promise<RightSizingRecommendation[]> => {
  const response = await axios.get('/rightsizing/top-opportunities', {
    params: { profile_name: profileName, limit }
  })
  return response.data
}
