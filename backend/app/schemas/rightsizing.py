from pydantic import BaseModel, Field
from typing import Optional, List


class RightSizingRecommendation(BaseModel):
    """Schema for a right-sizing recommendation"""
    resource_arn: str = Field(..., description="AWS resource ARN")
    resource_name: str = Field(..., description="Resource name/ID")
    resource_type: str = Field(..., description="Type: ec2_instance, ebs_volume, lambda_function, auto_scaling_group")
    current_config: str = Field(..., description="Current configuration (e.g., 't3.large', 'gp3 100GB')")
    recommended_config: str = Field(..., description="Recommended configuration")
    finding: str = Field(..., description="Finding: Underprovisioned, Overprovisioned, Optimized, etc.")
    region: Optional[str] = Field(None, description="AWS region where the resource is located")
    cpu_utilization: Optional[float] = Field(None, description="CPU utilization percentage")
    memory_utilization: Optional[float] = Field(None, description="Memory utilization percentage")
    performance_risk: Optional[float] = Field(None, description="Performance risk score (0-5)")
    estimated_monthly_savings: float = Field(..., description="Estimated monthly savings in USD")
    savings_percentage: Optional[float] = Field(None, description="Savings percentage")
    recommendation_source: str = Field(default="aws_compute_optimizer", description="Source of recommendation")


class RightSizingRecommendationsResponse(BaseModel):
    """Schema for right-sizing recommendations response"""
    profile_name: str
    total_recommendations: int
    total_monthly_savings: float
    recommendations_by_type: dict  # {resource_type: count}
    recommendations: List[RightSizingRecommendation]


class RightSizingSummary(BaseModel):
    """Schema for right-sizing summary"""
    profile_name: str
    total_ec2_recommendations: int
    total_ebs_recommendations: int
    total_lambda_recommendations: int
    total_asg_recommendations: int
    total_potential_savings: float
    overprovisioned_resources: int
    underprovisioned_resources: int
    optimized_resources: int
