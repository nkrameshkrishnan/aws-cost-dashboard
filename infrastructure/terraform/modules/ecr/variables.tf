# ==============================================================================
# ECR Module Variables
# ==============================================================================

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "repository_name" {
  description = "Name for the ECR repository"
  type        = string
  default     = "aws-cost-dashboard-backend"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
