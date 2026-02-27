# ==============================================================================
# VPC Link Module - Variables
# ==============================================================================

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the VPC Link (should be private subnets)"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs for the VPC Link"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
