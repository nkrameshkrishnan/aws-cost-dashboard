# ==============================================================================
# Root Module Variables
# ==============================================================================

# ==============================================================================
# General
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
# Networking
# ==============================================================================

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# ==============================================================================
# ECR — Container Registry
# ==============================================================================

variable "ecr_repository_name" {
  description = "Name for the ECR repository that stores backend images"
  type        = string
  default     = "aws-cost-dashboard-backend"
}

# ==============================================================================
# Database (RDS PostgreSQL)
# ==============================================================================

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "aws_cost_dashboard"
}

variable "db_username" {
  description = "Master username for RDS"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Master password for RDS"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8
    error_message = "Database password must be at least 8 characters."
  }
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB for RDS"
  type        = number
  default     = 100
}

variable "db_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "15.16"
}

# ==============================================================================
# Cache (ElastiCache Redis)
# ==============================================================================

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_cache_nodes" {
  description = "Number of Redis cache nodes (1 for dev, 2+ for production)"
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
  description = "Application secret key (min 32 chars) — generate with: openssl rand -hex 32"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.secret_key) >= 32
    error_message = "Secret key must be at least 32 characters."
  }
}

variable "jwt_secret_key" {
  description = "JWT signing key (min 32 chars) — generate with: openssl rand -hex 32"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.jwt_secret_key) >= 32
    error_message = "JWT secret key must be at least 32 characters."
  }
}

variable "encryption_key" {
  description = "Fernet key for credential encryption (44 chars) — generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.encryption_key) == 44
    error_message = "Encryption key must be a valid Fernet key (44 characters)."
  }
}

# ==============================================================================
# Optional: S3 bucket for report uploads
# ==============================================================================

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket used for report uploads (optional)."
  type        = string
  default     = ""
}
