# ==============================================================================
# API Gateway Module - Variables
# ==============================================================================

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_link_id" {
  description = "ID of the VPC Link to connect API Gateway to the private ALB"
  type        = string
}

variable "alb_listener_arn" {
  description = "ARN of the ALB listener to integrate with"
  type        = string
}

variable "cors_allowed_origins" {
  description = "List of allowed CORS origins (e.g., GitHub Pages, custom domains)"
  type        = list(string)
  default = [
    "http://localhost:5173",
    "http://localhost:3000",
  ]
}

variable "custom_domain_name" {
  description = "Optional custom domain name for the API Gateway (e.g., api.example.com)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ARN of the ACM certificate for custom domain (required if custom_domain_name is set)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
