# ==============================================================================
# AWS Cost Dashboard — Terraform Root Configuration
# ==============================================================================
#
# Architecture
# ───────────────────────────────────────────────────────────────────────────
#  GitHub Pages (frontend)
#       │  HTTPS API calls
#       ▼
#  nginx Ingress (NLB + sslip.io TLS)   ← CORS allows GitHub Pages origin
#       │
#       ▼
#  EKS — Backend Deployment (FastAPI, HPA 2-10 pods)
#       │
#       ├── RDS PostgreSQL  (this module — private subnet)
#       ├── ElastiCache Redis  (this module — private subnet)
#       └── AWS APIs via IRSA  (Cost Explorer, Budgets, EC2, RDS …)
#
# Division of responsibility
# ───────────────────────────────────────────────────────────────────────────
#  Terraform  → VPC · RDS · ElastiCache · Secrets Manager · ECR · CloudWatch
#  eksctl     → EKS cluster · node groups · OIDC / IRSA service account
#  kubectl    → Application manifests (kubernetes/ directory)
#
# Usage:
#   1. Copy terraform.tfvars.example → terraform.tfvars and fill in values
#   2. terraform init
#   3. terraform plan -out=tfplan
#   4. terraform apply tfplan
#   5. After apply, note the outputs and update kubernetes/base/configmap.yaml
#      with the RDS endpoint and Redis endpoint, then run:
#      ./scripts/eks-deploy.sh
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
  vpc_cidr    = var.vpc_cidr
  tags        = local.common_tags
}

# ==============================================================================
# ECR — Container Registry for backend images
# ==============================================================================

module "ecr" {
  source = "./modules/ecr"

  name_prefix     = local.name_prefix
  repository_name = var.ecr_repository_name
  tags            = local.common_tags
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
# CloudWatch Logs
# ==============================================================================

module "monitoring" {
  source = "./modules/monitoring"

  name_prefix        = local.name_prefix
  log_retention_days = 30
  tags               = local.common_tags

  depends_on = [module.secrets]
}

# ==============================================================================
# Outputs
# ==============================================================================

output "ecr_repository_url" {
  description = "ECR repository URL — set as ECR_REPOSITORY in GitHub Actions secrets"
  value       = module.ecr.repository_url
}

output "rds_endpoint" {
  description = "RDS database endpoint — update kubernetes/base/configmap.yaml with this value"
  value       = module.database.endpoint
  sensitive   = true
}

output "rds_address" {
  description = "RDS database hostname (without port)"
  value       = module.database.address
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis cache endpoint — update kubernetes/base/configmap.yaml with this value"
  value       = module.cache.primary_endpoint_address
  sensitive   = true
}

output "vpc_id" {
  description = "VPC ID — pass to eksctl if creating the EKS cluster in the same VPC"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs — used for EKS node groups and RDS subnet group"
  value       = module.networking.private_subnet_ids
}

output "backend_log_group_name" {
  description = "CloudWatch log group name for backend pods"
  value       = module.monitoring.backend_log_group_name
}

output "db_credentials_secret_arn" {
  description = "ARN of the Secrets Manager secret holding DB credentials"
  value       = module.secrets.db_credentials_secret_arn
  sensitive   = true
}
