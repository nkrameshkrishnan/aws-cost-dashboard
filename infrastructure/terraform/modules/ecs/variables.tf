# ==============================================================================
# ECS Module Variables
# ==============================================================================

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  type        = string
}

variable "task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  type        = string
}

variable "task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

variable "backend_target_group_arn" {
  description = "ARN of the backend ALB target group"
  type        = string
}

variable "backend_image" {
  description = "Docker image for the backend (FastAPI)"
  type        = string
}

variable "backend_task_cpu" {
  description = "CPU units for backend task (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "backend_task_memory" {
  description = "Memory (MB) for backend task"
  type        = number
  default     = 2048
}

variable "desired_count" {
  description = "Desired number of backend tasks"
  type        = number
  default     = 2
}

variable "min_capacity" {
  description = "Minimum number of tasks for auto-scaling"
  type        = number
  default     = 2
}

variable "max_capacity" {
  description = "Maximum number of tasks for auto-scaling"
  type        = number
  default     = 10
}

variable "db_username" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "db_endpoint" {
  description = "Database endpoint"
  type        = string
}

variable "db_port" {
  description = "Database port"
  type        = number
  default     = 5432
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "redis_endpoint" {
  description = "Redis endpoint"
  type        = string
}

variable "redis_port" {
  description = "Redis port"
  type        = number
  default     = 6379
}

variable "app_secrets_arn" {
  description = "ARN of the application secrets in Secrets Manager"
  type        = string
  sensitive   = true
}

variable "backend_log_group_name" {
  description = "Name of the backend CloudWatch log group"
  type        = string
}

variable "cors_allowed_origins" {
  description = "Allowed CORS origins for the backend API (must include GitHub Pages URL)"
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
