# ==============================================================================
# Root Module Variables
# ==============================================================================
# These variables are used across multiple modules

# ==============================================================================
# General Configuration
# ==============================================================================

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "awscost"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

# ==============================================================================
# Networking Configuration
# ==============================================================================

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# ==============================================================================
# Database Configuration
# ==============================================================================

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "aws_cost_dashboard"
}

variable "db_username" {
  description = "Master username for the database"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Master password for the database"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8
    error_message = "Database password must be at least 8 characters long."
  }
}

variable "db_instance_class" {
  description = "Instance class for RDS database"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB for RDS database"
  type        = number
  default     = 100
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.16"
}

# ==============================================================================
# Redis Configuration
# ==============================================================================

variable "redis_node_type" {
  description = "Node type for ElastiCache Redis"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes (1 for dev, 2+ for production)"
  type        = number
  default     = 2
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

# ==============================================================================
# Application Secrets
# ==============================================================================

variable "secret_key" {
  description = "Application secret key for session encryption"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.secret_key) >= 32
    error_message = "Secret key must be at least 32 characters long."
  }
}

variable "jwt_secret_key" {
  description = "JWT secret key for token signing"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.jwt_secret_key) >= 32
    error_message = "JWT secret key must be at least 32 characters long."
  }
}

variable "encryption_key" {
  description = "Fernet encryption key for AWS credential encryption"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.encryption_key) == 44
    error_message = "Encryption key must be a valid Fernet key (44 characters)."
  }
}

# ==============================================================================
# ECS Configuration
# ==============================================================================

variable "backend_image" {
  description = "Docker image for backend application"
  type        = string
}

variable "frontend_image" {
  description = "Docker image for frontend application"
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

variable "frontend_task_cpu" {
  description = "CPU units for frontend task (512 = 0.5 vCPU)"
  type        = number
  default     = 512
}

variable "frontend_task_memory" {
  description = "Memory (MB) for frontend task"
  type        = number
  default     = 1024
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_min_capacity" {
  description = "Minimum number of ECS tasks for auto-scaling"
  type        = number
  default     = 2
}

variable "ecs_max_capacity" {
  description = "Maximum number of ECS tasks for auto-scaling"
  type        = number
  default     = 10
}

# ==============================================================================
# Load Balancer Configuration
# ==============================================================================

variable "certificate_arn" {
  description = "ARN of ACM certificate for HTTPS (optional)"
  type        = string
  default     = ""
}

# ==============================================================================
# API Gateway Configuration
# ==============================================================================

variable "cors_allowed_origins" {
  description = "List of allowed CORS origins for API Gateway (e.g., GitHub Pages URL, custom domains)"
  type        = list(string)
  default     = [
    "http://localhost:5173",
    "http://localhost:3000",
  ]

  validation {
    condition     = length(var.cors_allowed_origins) > 0
    error_message = "At least one CORS origin must be specified."
  }
}

variable "custom_domain_name" {
  description = "Custom domain name for API Gateway (e.g., api.example.com). Leave empty to use default API Gateway domain"
  type        = string
  default     = ""
}

# ==============================================================================
# Optional: S3 Bucket for Reports
# ==============================================================================

variable "s3_bucket_arn" {
  description = "ARN of S3 bucket for report uploads (optional)"
  type        = string
  default     = ""
}
