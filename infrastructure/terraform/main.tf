# ==============================================================================
# AWS Cost Dashboard — Terraform Root Configuration
# ==============================================================================
#
# Architecture
# ───────────────────────────────────────────────────────────────────────────
#  GitHub Pages (frontend)
#       │  HTTPS API calls
#       ▼
#  API Gateway HTTP API  ←  CORS allows GitHub Pages origin
#       │  VPC Link
#       ▼
#  Internal ALB  (private subnets)
#       │
#       ▼
#  ECS Fargate — Backend (FastAPI, port 8000)
#       │
#       ├── RDS PostgreSQL
#       ├── ElastiCache Redis
#       └── AWS APIs (Cost Explorer, Budgets, EC2, RDS, Lambda …)
# ───────────────────────────────────────────────────────────────────────────
#
# Usage:
#   1. Copy terraform.tfvars.example → terraform.tfvars and fill in values
#   2. terraform init
#   3. terraform plan
#   4. terraform apply
# ==============================================================================

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment for remote state (recommended for production)
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "aws-cost-dashboard/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ==============================================================================
# Local Variables
# ==============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ==============================================================================
# Networking
# ==============================================================================

module "networking" {
  source = "./modules/networking"

  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  tags        = local.common_tags
}

# ==============================================================================
# Security Groups
# ==============================================================================

module "security" {
  source = "./modules/security"

  name_prefix = local.name_prefix
  vpc_id      = module.networking.vpc_id
  tags        = local.common_tags
}

# ==============================================================================
# RDS PostgreSQL
# ==============================================================================

module "database" {
  source = "./modules/database"

  name_prefix             = local.name_prefix
  database_name           = var.db_name
  master_username         = var.db_username
  master_password         = var.db_password
  instance_class          = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  engine_version          = var.db_engine_version
  multi_az                = var.environment == "production"
  private_subnet_ids      = module.networking.private_subnet_ids
  security_group_id       = module.security.rds_security_group_id
  backup_retention_period = var.environment == "production" ? 7 : 1
  skip_final_snapshot     = var.environment != "production"
  tags                    = local.common_tags

  depends_on = [module.networking, module.security]
}

# ==============================================================================
# ElastiCache Redis
# ==============================================================================

module "cache" {
  source = "./modules/cache"

  name_prefix              = local.name_prefix
  node_type                = var.redis_node_type
  num_cache_nodes          = var.redis_num_cache_nodes
  engine_version           = var.redis_engine_version
  private_subnet_ids       = module.networking.private_subnet_ids
  security_group_id        = module.security.elasticache_security_group_id
  snapshot_retention_limit = var.environment == "production" ? 5 : 0
  tags                     = local.common_tags

  depends_on = [module.networking, module.security]
}

# ==============================================================================
# Secrets Manager
# ==============================================================================

module "secrets" {
  source = "./modules/secrets"

  name_prefix    = local.name_prefix
  db_username    = var.db_username
  db_password    = var.db_password
  db_endpoint    = module.database.address
  db_port        = module.database.port
  db_name        = var.db_name
  redis_endpoint = module.cache.primary_endpoint_address
  redis_port     = module.cache.port
  secret_key     = var.secret_key
  jwt_secret_key = var.jwt_secret_key
  encryption_key = var.encryption_key
  tags           = local.common_tags

  depends_on = [module.database, module.cache]
}

# ==============================================================================
# CloudWatch Logs + IAM Roles
# ==============================================================================

module "monitoring" {
  source = "./modules/monitoring"

  name_prefix        = local.name_prefix
  log_retention_days = 30
  secret_arns = [
    module.secrets.db_credentials_secret_arn,
    module.secrets.app_secrets_arn
  ]
  s3_bucket_arn = var.s3_bucket_arn
  tags          = local.common_tags

  depends_on = [module.secrets]
}

# ==============================================================================
# Internal Application Load Balancer (backend only)
# ==============================================================================

module "alb" {
  source = "./modules/alb"

  name_prefix                = local.name_prefix
  vpc_id                     = module.networking.vpc_id
  internal                   = true  # Private ALB — accessed only via API Gateway VPC Link
  private_subnet_ids         = module.networking.private_subnet_ids
  public_subnet_ids          = module.networking.public_subnet_ids
  alb_security_group_id      = module.security.alb_security_group_id
  certificate_arn            = var.certificate_arn
  enable_deletion_protection = var.environment == "production"
  tags                       = local.common_tags

  depends_on = [module.networking, module.security]
}

# ==============================================================================
# ECS Fargate — Backend only
# (Frontend is served from GitHub Pages)
# ==============================================================================

module "ecs" {
  source = "./modules/ecs"

  name_prefix              = local.name_prefix
  environment              = var.environment
  aws_region               = var.aws_region
  private_subnet_ids       = module.networking.private_subnet_ids
  ecs_security_group_id    = module.security.ecs_tasks_security_group_id
  task_execution_role_arn  = module.monitoring.ecs_task_execution_role_arn
  task_role_arn            = module.monitoring.ecs_task_role_arn
  backend_target_group_arn = module.alb.backend_target_group_arn
  backend_image            = var.backend_image
  backend_task_cpu         = var.backend_task_cpu
  backend_task_memory      = var.backend_task_memory
  desired_count            = var.ecs_desired_count
  min_capacity             = var.ecs_min_capacity
  max_capacity             = var.ecs_max_capacity
  db_username              = var.db_username
  db_password              = var.db_password
  db_endpoint              = module.database.address
  db_port                  = module.database.port
  db_name                  = var.db_name
  redis_endpoint           = module.cache.primary_endpoint_address
  redis_port               = module.cache.port
  app_secrets_arn          = module.secrets.app_secrets_arn
  backend_log_group_name   = module.monitoring.backend_log_group_name
  cors_allowed_origins     = var.cors_allowed_origins
  tags                     = local.common_tags

  depends_on = [
    module.networking,
    module.security,
    module.database,
    module.cache,
    module.secrets,
    module.monitoring,
    module.alb
  ]
}

# ==============================================================================
# VPC Link (connects API Gateway to the private ALB)
# ==============================================================================

module "vpc_link" {
  source = "./modules/vpc-link"

  name_prefix        = local.name_prefix
  subnet_ids         = module.networking.private_subnet_ids
  security_group_ids = [module.security.vpc_link_security_group_id]
  tags               = local.common_tags

  depends_on = [module.networking, module.security, module.alb]
}

# ==============================================================================
# API Gateway HTTP API (public entry point for the GitHub Pages frontend)
# ==============================================================================

module "api_gateway" {
  source = "./modules/api-gateway"

  name_prefix          = local.name_prefix
  vpc_link_id          = module.vpc_link.vpc_link_id
  alb_listener_arn     = module.alb.http_listener_arn
  cors_allowed_origins = var.cors_allowed_origins
  custom_domain_name   = var.custom_domain_name
  certificate_arn      = var.certificate_arn
  tags                 = local.common_tags

  depends_on = [module.vpc_link, module.alb]
}

# ==============================================================================
# Outputs
# ==============================================================================

output "api_gateway_url" {
  description = "API Gateway invoke URL — set this as VITE_API_BASE_URL in .env.production before building"
  value       = module.api_gateway.api_invoke_url
}

output "api_gateway_id" {
  description = "ID of the API Gateway HTTP API"
  value       = module.api_gateway.api_id
}

output "custom_domain_url" {
  description = "Custom domain URL for the API (if configured)"
  value       = var.custom_domain_name != "" ? "https://${var.custom_domain_name}" : ""
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "backend_service_name" {
  description = "ECS backend service name"
  value       = module.ecs.backend_service_name
}

output "rds_endpoint" {
  description = "RDS database endpoint"
  value       = module.database.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis cache endpoint"
  value       = module.cache.primary_endpoint_address
  sensitive   = true
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}
