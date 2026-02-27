# Terraform Modules

This directory contains reusable Terraform modules for deploying the AWS Cost Dashboard infrastructure.

## Module Structure

The infrastructure is organized into 8 modular components:

```
modules/
├── networking/     # VPC, subnets, NAT gateways, route tables
├── security/       # Security groups for ALB, ECS, RDS, ElastiCache
├── database/       # RDS PostgreSQL database
├── cache/          # ElastiCache Redis cluster
├── secrets/        # AWS Secrets Manager secrets
├── monitoring/     # CloudWatch logs and IAM roles
├── alb/            # Application Load Balancer and target groups
└── ecs/            # ECS cluster, task definitions, services, auto-scaling
```

## Module Dependencies

The modules have the following dependency chain:

```
networking ──┬──> security ──┬──> database ───┬──> secrets ──> monitoring ──┬──> ecs
             │               │                 │                             │
             │               └──> cache ───────┘                             │
             │                                                                │
             └──> alb ─────────────────────────────────────────────────────>─┘
```

## Usage

### Using the Modular Configuration

The root `main-modular.tf` file orchestrates all modules:

```bash
# Initialize Terraform
terraform init

# Plan with modular configuration
terraform plan -var-file=terraform.tfvars

# Apply with modular configuration
terraform apply -var-file=terraform.tfvars
```

### Using Individual Modules

Each module can also be used independently:

```hcl
module "networking" {
  source = "./modules/networking"

  name_prefix = "myapp-prod"
  vpc_cidr    = "10.0.0.0/16"

  tags = {
    Environment = "production"
  }
}
```

## Module Documentation

### 1. Networking Module

**Purpose**: Creates VPC, subnets, NAT gateways, and routing tables.

**Resources**:
- 1 VPC
- 2 public subnets (across 2 AZs)
- 2 private subnets (across 2 AZs)
- 1 Internet Gateway
- 2 NAT Gateways (one per AZ)
- Route tables and associations

**Inputs**:
- `name_prefix` - Prefix for resource names
- `vpc_cidr` - CIDR block for VPC (default: 10.0.0.0/16)
- `tags` - Common tags

**Outputs**:
- `vpc_id` - VPC ID
- `public_subnet_ids` - List of public subnet IDs
- `private_subnet_ids` - List of private subnet IDs
- `nat_gateway_ids` - List of NAT Gateway IDs

---

### 2. Security Module

**Purpose**: Creates security groups with least-privilege rules.

**Resources**:
- ALB security group (HTTP/HTTPS from internet)
- ECS security group (traffic from ALB)
- RDS security group (PostgreSQL from ECS)
- ElastiCache security group (Redis from ECS)

**Inputs**:
- `name_prefix` - Prefix for resource names
- `vpc_id` - VPC ID
- `tags` - Common tags

**Outputs**:
- `alb_security_group_id`
- `ecs_security_group_id`
- `rds_security_group_id`
- `redis_security_group_id`

---

### 3. Database Module

**Purpose**: Creates RDS PostgreSQL database with Multi-AZ support.

**Resources**:
- RDS DB subnet group
- RDS DB instance (PostgreSQL)
- Automated backups

**Inputs**:
- `name_prefix` - Prefix for resource names
- `db_name` - Database name
- `db_username` - Master username (sensitive)
- `db_password` - Master password (sensitive)
- `instance_class` - Instance type (default: db.t3.medium)
- `allocated_storage` - Storage in GB (default: 100)
- `engine_version` - PostgreSQL version (default: 15.4)
- `multi_az` - Enable Multi-AZ (default: true for production)
- `subnet_ids` - Private subnet IDs
- `vpc_security_group_ids` - Security group IDs
- `backup_retention_period` - Backup retention days (default: 7)
- `skip_final_snapshot` - Skip final snapshot on deletion
- `tags` - Common tags

**Outputs**:
- `endpoint` - Database endpoint
- `port` - Database port (5432)
- `db_instance_id` - DB instance identifier

---

### 4. Cache Module

**Purpose**: Creates ElastiCache Redis cluster with Multi-AZ replication.

**Resources**:
- ElastiCache subnet group
- ElastiCache replication group (Redis)

**Inputs**:
- `name_prefix` - Prefix for resource names
- `node_type` - Node type (default: cache.t3.medium)
- `num_cache_nodes` - Number of nodes (default: 2)
- `engine_version` - Redis version (default: 7.0)
- `subnet_ids` - Private subnet IDs
- `vpc_security_group_ids` - Security group IDs
- `snapshot_retention_limit` - Snapshot retention days (default: 5)
- `tags` - Common tags

**Outputs**:
- `primary_endpoint_address` - Primary endpoint (sensitive)
- `reader_endpoint_address` - Reader endpoint (sensitive)
- `port` - Redis port (6379)

---

### 5. Secrets Module

**Purpose**: Stores sensitive data in AWS Secrets Manager.

**Resources**:
- Database credentials secret
- Redis credentials secret (optional)
- Application secrets (SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY)

**Inputs**:
- `name_prefix` - Prefix for resource names
- `db_username` - Database username (sensitive)
- `db_password` - Database password (sensitive)
- `db_endpoint` - Database endpoint
- `db_port` - Database port
- `db_name` - Database name
- `redis_endpoint` - Redis endpoint
- `redis_port` - Redis port
- `redis_auth_token` - Redis auth token (optional, sensitive)
- `secret_key` - Application secret key (sensitive)
- `jwt_secret_key` - JWT secret key (sensitive)
- `encryption_key` - Encryption key (sensitive)
- `recovery_window_in_days` - Recovery window (default: 30)
- `tags` - Common tags

**Outputs**:
- `db_credentials_secret_arn` - DB credentials ARN (sensitive)
- `redis_credentials_secret_arn` - Redis credentials ARN (sensitive)
- `app_secrets_arn` - Application secrets ARN (sensitive)

---

### 6. Monitoring Module

**Purpose**: Creates CloudWatch log groups and IAM roles for ECS.

**Resources**:
- CloudWatch log groups (backend, frontend)
- ECS task execution role (for pulling images and accessing secrets)
- ECS task role (for application AWS API access)
- IAM policies for Cost Explorer, Budgets, EC2, RDS, Lambda, ELB

**Inputs**:
- `name_prefix` - Prefix for resource names
- `log_retention_days` - Log retention period (default: 30)
- `secret_arns` - List of Secrets Manager ARNs to grant access
- `s3_bucket_arn` - S3 bucket ARN for report uploads (optional)
- `tags` - Common tags

**Outputs**:
- `backend_log_group_name` - Backend log group name
- `frontend_log_group_name` - Frontend log group name
- `ecs_task_execution_role_arn` - Task execution role ARN
- `ecs_task_role_arn` - Task role ARN

---

### 7. ALB Module

**Purpose**: Creates Application Load Balancer with target groups.

**Resources**:
- Application Load Balancer
- Target groups (backend, frontend)
- HTTP listener (redirect to HTTPS if cert provided)
- HTTPS listener (if certificate ARN provided)
- Listener rules for routing

**Inputs**:
- `name_prefix` - Prefix for resource names
- `vpc_id` - VPC ID
- `public_subnet_ids` - Public subnet IDs
- `alb_security_group_id` - ALB security group ID
- `certificate_arn` - ACM certificate ARN (optional)
- `enable_deletion_protection` - Enable deletion protection (default: true for production)
- `tags` - Common tags

**Outputs**:
- `alb_arn` - ALB ARN
- `alb_dns_name` - ALB DNS name
- `alb_zone_id` - ALB zone ID
- `backend_target_group_arn` - Backend target group ARN
- `frontend_target_group_arn` - Frontend target group ARN
- `http_listener_arn` - HTTP listener ARN
- `https_listener_arn` - HTTPS listener ARN (if certificate provided)

---

### 8. ECS Module

**Purpose**: Creates ECS cluster, task definitions, services, and auto-scaling.

**Resources**:
- ECS cluster with Container Insights
- Capacity providers (FARGATE, FARGATE_SPOT)
- Task definitions (backend, frontend)
- ECS services (backend, frontend)
- Auto-scaling targets and policies (CPU, memory)

**Inputs**:
- `name_prefix` - Prefix for resource names
- `environment` - Environment name
- `aws_region` - AWS region
- `private_subnet_ids` - Private subnet IDs for tasks
- `ecs_security_group_id` - ECS security group ID
- `task_execution_role_arn` - Task execution role ARN
- `task_role_arn` - Task role ARN
- `backend_target_group_arn` - Backend target group ARN
- `frontend_target_group_arn` - Frontend target group ARN
- `backend_image` - Backend Docker image
- `frontend_image` - Frontend Docker image
- `backend_task_cpu` - Backend CPU units (default: 1024)
- `backend_task_memory` - Backend memory MB (default: 2048)
- `frontend_task_cpu` - Frontend CPU units (default: 512)
- `frontend_task_memory` - Frontend memory MB (default: 1024)
- `desired_count` - Desired task count (default: 2)
- `min_capacity` - Min tasks for auto-scaling (default: 2)
- `max_capacity` - Max tasks for auto-scaling (default: 10)
- `db_username` - Database username (sensitive)
- `db_password` - Database password (sensitive)
- `db_endpoint` - Database endpoint
- `db_port` - Database port
- `db_name` - Database name
- `redis_endpoint` - Redis endpoint
- `redis_port` - Redis port
- `app_secrets_arn` - Application secrets ARN (sensitive)
- `backend_log_group_name` - Backend log group name
- `frontend_log_group_name` - Frontend log group name
- `tags` - Common tags

**Outputs**:
- `cluster_id` - ECS cluster ID
- `cluster_name` - ECS cluster name
- `cluster_arn` - ECS cluster ARN
- `backend_service_name` - Backend service name
- `frontend_service_name` - Frontend service name
- `backend_task_definition_arn` - Backend task definition ARN
- `frontend_task_definition_arn` - Frontend task definition ARN

---

## Migration from Monolithic Configuration

If you're migrating from the monolithic `main.tf`:

1. **Backup your state**:
   ```bash
   cp terraform.tfstate terraform.tfstate.backup
   ```

2. **Review the new modular structure**:
   - Check `main-modular.tf` to understand module orchestration
   - Review `variables-modular.tf` for variable definitions

3. **Option 1: Fresh Deployment** (Recommended for new environments):
   ```bash
   # Use the modular configuration
   mv main.tf main.tf.old
   mv main-modular.tf main.tf
   mv variables-modular.tf variables.tf

   terraform init
   terraform plan
   terraform apply
   ```

4. **Option 2: State Migration** (For existing infrastructure):
   ```bash
   # Import existing resources into modules
   # This requires careful mapping - contact support for assistance
   ```

## Benefits of Modular Architecture

1. **Reusability**: Use individual modules in different projects
2. **Maintainability**: Changes to one module don't affect others
3. **Testing**: Test modules independently
4. **Collaboration**: Team members can work on different modules
5. **Versioning**: Version modules separately
6. **Clarity**: Easier to understand infrastructure structure

## Best Practices

1. **Version Control**: Keep modules in version control
2. **Module Versions**: Pin module versions in production
3. **Documentation**: Document module inputs/outputs
4. **Testing**: Test modules with different input combinations
5. **DRY Principle**: Don't repeat yourself - reuse modules
6. **Naming**: Use consistent naming conventions
7. **Tagging**: Apply consistent tags across all resources

## Support

For issues with modules:
1. Check module README files
2. Review Terraform plan output
3. Check AWS console for resource status
4. Open an issue on GitHub

---

## License

[Your License Here]
