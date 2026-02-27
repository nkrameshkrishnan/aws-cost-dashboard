# Terraform Modular Architecture

## Overview

The AWS Cost Dashboard infrastructure has been refactored from a monolithic Terraform configuration into a modular architecture for better maintainability, reusability, and scalability.

## What Changed

### Before (Monolithic)
- Single `main.tf` file with 1000+ lines
- All resources defined in one file
- Difficult to maintain and test
- Hard to reuse components

### After (Modular)
- 8 specialized modules in `modules/` directory
- Each module focuses on a specific infrastructure component
- Clear separation of concerns
- Reusable and testable components

## Module Structure

```
infrastructure/terraform/
├── main-modular.tf              # Root configuration (orchestrates modules)
├── variables-modular.tf         # Root variables
├── terraform.tfvars.example     # Example configuration
└── modules/
    ├── networking/              # VPC, subnets, NAT gateways
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── security/                # Security groups
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── database/                # RDS PostgreSQL
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── cache/                   # ElastiCache Redis
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── secrets/                 # AWS Secrets Manager
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── monitoring/              # CloudWatch + IAM roles
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── alb/                     # Application Load Balancer
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── ecs/                     # ECS cluster + services
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── README.md                # Module documentation
```

## Module Dependencies

The modules are orchestrated with the following dependency chain:

```
┌──────────────┐
│  networking  │
└──────┬───────┘
       │
       ├──────> ┌──────────┐
       │        │ security │
       │        └────┬─────┘
       │             │
       │             ├──────> ┌──────────┐
       │             │        │ database │
       │             │        └────┬─────┘
       │             │             │
       │             ├──────> ┌────┴────┐
       │             │        │  cache  │
       │             │        └────┬────┘
       │             │             │
       │             │        ┌────▼─────┐
       │             │        │ secrets  │
       │             │        └────┬─────┘
       │             │             │
       │             │        ┌────▼──────┐
       │             │        │monitoring │
       │             │        └────┬──────┘
       │             │             │
       └──────> ┌────▼─────┐       │
                │   alb    │       │
                └────┬─────┘       │
                     │             │
                     └──────┬──────┘
                            │
                       ┌────▼────┐
                       │   ecs   │
                       └─────────┘
```

## How to Use

### 1. Fresh Deployment (Recommended)

For new deployments or new environments:

```bash
# Navigate to terraform directory
cd infrastructure/terraform

# Configure your variables
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars  # Edit with your values

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply the configuration
terraform apply
```

### 2. Migration from Existing Monolithic Deployment

If you have an existing deployment using the old monolithic configuration:

**Option A: Destroy and Redeploy** (Only if you can afford downtime)
```bash
# Backup state
cp terraform.tfstate terraform.tfstate.backup

# Destroy old infrastructure
terraform destroy

# Deploy with new modular structure
terraform init
terraform plan
terraform apply
```

**Option B: State Migration** (Zero downtime, more complex)

This requires moving resources in Terraform state to new module paths. This is an advanced operation that requires careful mapping of old resource paths to new module paths. Please consult the Terraform state migration documentation or contact your DevOps team.

### 3. Using Individual Modules

You can also use individual modules in other projects:

```hcl
# Example: Use only the networking module
module "my_network" {
  source = "./modules/networking"

  name_prefix = "myapp-prod"
  vpc_cidr    = "10.0.0.0/16"

  tags = {
    Project     = "MyApp"
    Environment = "production"
  }
}
```

## Module Overview

### 1. Networking Module
- **Purpose**: Creates VPC with public/private subnets across 2 AZs
- **Resources**: VPC, subnets, NAT gateways, route tables, Internet Gateway
- **Cost**: ~$65/month (NAT Gateways)

### 2. Security Module
- **Purpose**: Creates security groups with least-privilege rules
- **Resources**: ALB, ECS, RDS, ElastiCache security groups
- **Cost**: Free

### 3. Database Module
- **Purpose**: Creates RDS PostgreSQL database
- **Resources**: RDS instance, subnet group, automated backups
- **Cost**: ~$130/month (db.t3.medium Multi-AZ)

### 4. Cache Module
- **Purpose**: Creates ElastiCache Redis cluster
- **Resources**: Redis replication group, subnet group
- **Cost**: ~$100/month (cache.t3.medium Multi-AZ)

### 5. Secrets Module
- **Purpose**: Stores sensitive data in AWS Secrets Manager
- **Resources**: Secrets for database, Redis, application keys
- **Cost**: ~$2/month (3 secrets × $0.40/month + API calls)

### 6. Monitoring Module
- **Purpose**: Creates CloudWatch logs and IAM roles
- **Resources**: Log groups, ECS task execution role, ECS task role
- **Cost**: ~$10/month (CloudWatch logs)

### 7. ALB Module
- **Purpose**: Creates Application Load Balancer
- **Resources**: ALB, target groups, listeners, listener rules
- **Cost**: ~$25/month

### 8. ECS Module
- **Purpose**: Creates ECS cluster with Fargate services
- **Resources**: ECS cluster, task definitions, services, auto-scaling
- **Cost**: ~$75/month (2 tasks, 1.5 vCPU total, 3GB RAM total)

**Total Monthly Cost**: ~$415/month (production configuration)

## Benefits of Modular Architecture

### 1. **Maintainability**
- Each module has a single responsibility
- Changes to one module don't affect others
- Easier to understand and debug

### 2. **Reusability**
- Use modules across multiple projects
- Share modules with team members
- Build a library of infrastructure components

### 3. **Testability**
- Test each module independently
- Validate module inputs/outputs
- Use different configurations for testing

### 4. **Collaboration**
- Team members can work on different modules simultaneously
- Clear ownership boundaries
- Easier code reviews

### 5. **Scalability**
- Add new modules without modifying existing ones
- Remove unused modules easily
- Version modules independently

### 6. **DRY Principle**
- Don't Repeat Yourself
- Define infrastructure patterns once
- Reuse across environments (dev, staging, production)

## Configuration Examples

### Development Environment

```hcl
# terraform.tfvars
environment          = "dev"
db_instance_class    = "db.t3.small"
db_allocated_storage = 20
redis_node_type      = "cache.t3.micro"
redis_num_cache_nodes = 1
ecs_desired_count    = 1
ecs_min_capacity     = 1
ecs_max_capacity     = 2
```

**Cost**: ~$120/month

### Staging Environment

```hcl
# terraform.tfvars
environment          = "staging"
db_instance_class    = "db.t3.medium"
db_allocated_storage = 50
redis_node_type      = "cache.t3.small"
redis_num_cache_nodes = 2
ecs_desired_count    = 2
ecs_min_capacity     = 1
ecs_max_capacity     = 5
```

**Cost**: ~$300/month

### Production Environment

```hcl
# terraform.tfvars
environment          = "production"
db_instance_class    = "db.t3.medium"
db_allocated_storage = 100
redis_node_type      = "cache.t3.medium"
redis_num_cache_nodes = 2
ecs_desired_count    = 2
ecs_min_capacity     = 2
ecs_max_capacity     = 10
certificate_arn      = "arn:aws:acm:us-east-1:123456789012:certificate/abc..."
```

**Cost**: ~$415/month

### High-Performance Production

```hcl
# terraform.tfvars
environment          = "production"
db_instance_class    = "db.r5.large"
db_allocated_storage = 500
redis_node_type      = "cache.r5.large"
redis_num_cache_nodes = 3
backend_task_cpu     = 2048
backend_task_memory  = 4096
ecs_desired_count    = 4
ecs_min_capacity     = 2
ecs_max_capacity     = 20
```

**Cost**: ~$800/month

## Outputs

The modular configuration provides the same outputs as the monolithic version:

```bash
terraform output

# Key outputs:
# - alb_dns_name: DNS name of the load balancer
# - alb_url: Full URL to access the application
# - ecs_cluster_name: Name of the ECS cluster
# - backend_service_name: Name of the backend service
# - frontend_service_name: Name of the frontend service
# - rds_endpoint: Database endpoint (sensitive)
# - redis_endpoint: Redis endpoint (sensitive)
# - vpc_id: VPC ID
# - private_subnet_ids: Private subnet IDs
# - public_subnet_ids: Public subnet IDs
```

## Troubleshooting

### Module Not Found

**Error**: `Module not found: networking`

**Solution**: Ensure you're running Terraform from the correct directory:
```bash
cd infrastructure/terraform
terraform init
```

### Variable Not Declared

**Error**: `Variable "xyz" is not declared in the root module`

**Solution**: Ensure you're using `variables-modular.tf` or have renamed it to `variables.tf`

### Dependency Issues

**Error**: Resources fail to create due to missing dependencies

**Solution**: The root `main.tf` includes `depends_on` clauses. Don't remove them.

### State Migration Issues

**Error**: Resources already exist when applying modular configuration

**Solution**: Either:
1. Destroy old infrastructure first (with downtime)
2. Use `terraform state mv` to migrate resources (advanced, zero downtime)

## Best Practices

1. **Always use variables**: Don't hardcode values in modules
2. **Tag everything**: Use consistent tagging across all resources
3. **Document modules**: Keep module READMEs up to date
4. **Version modules**: Use Git tags for module versions
5. **Test modules**: Test each module with different inputs
6. **Use remote state**: Store state in S3 for team collaboration
7. **Enable state locking**: Use DynamoDB for state locking
8. **Review plans**: Always review `terraform plan` before applying

## Next Steps

1. ✅ Modular architecture implemented
2. ✅ Module documentation created
3. ✅ Migration guide provided
4. ⏳ Test modules in development environment
5. ⏳ Set up remote state backend (S3 + DynamoDB)
6. ⏳ Implement CI/CD for Terraform (already have GitHub Actions)
7. ⏳ Create Terraform workspaces for multiple environments
8. ⏳ Add module versioning

## Support

For questions or issues:
1. Check [modules/README.md](modules/README.md) for module documentation
2. Review [infrastructure/README.md](../README.md) for deployment guide
3. Check Terraform plan output for errors
4. Open an issue on GitHub

---

**Last Updated**: Phase 9 - Deployment & Documentation
**Status**: ✅ Complete
