# AWS Cost Dashboard - Infrastructure as Code

This directory contains Infrastructure as Code (IaC) templates for deploying the AWS Cost Dashboard to AWS.

## Directory Structure

```
infrastructure/
├── terraform/              # Terraform configuration (recommended)
│   ├── main.tf            # Main Terraform configuration
│   └── terraform.tfvars.example
└── cloudformation/        # CloudFormation templates (alternative)
    └── (coming soon)
```

---

## Terraform Deployment (Recommended)

### Overview

The Terraform configuration in `terraform/` creates a complete, production-ready infrastructure on AWS including:

**Networking:**
- VPC with public and private subnets across 2 Availability Zones
- Internet Gateway for public internet access
- NAT Gateways for private subnet internet access
- Route tables and associations

**Compute:**
- ECS Fargate cluster for container orchestration
- Auto-scaling configuration (2-10 tasks)
- Application Load Balancer with health checks
- SSL/TLS support (optional)

**Data Layer:**
- RDS PostgreSQL database (Multi-AZ for production)
- ElastiCache Redis cluster (Multi-AZ)
- Automated backups and snapshots

**Security:**
- Security groups with least-privilege access
- IAM roles for ECS tasks
- AWS Secrets Manager for sensitive data
- Encryption at rest and in transit

**Monitoring:**
- CloudWatch Log Groups with 30-day retention
- Container Insights enabled
- CloudWatch Alarms (optional)

### Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** >= 1.0 installed
3. **AWS CLI** >= 2.0 configured
4. **Docker** for building images
5. **jq** for JSON processing

### Quick Start

#### 1. Configure Variables

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set your values:

```hcl
aws_region = "us-east-1"
environment = "production"
project_name = "awscost"

# Database
db_username = "dbadmin"
db_password = "YOUR_STRONG_PASSWORD"  # Use openssl rand -base64 32

# Docker images (replace with your registry)
backend_image = "ghcr.io/your-org/awscost-backend:latest"
frontend_image = "ghcr.io/your-org/awscost-frontend:latest"

# Optional: Custom domain
domain_name = "cost-dashboard.your-domain.com"
certificate_arn = "arn:aws:acm:us-east-1:123...:certificate/abc..."
```

#### 2. Initialize Terraform

```bash
terraform init
```

This downloads required providers and initializes the backend.

#### 3. Plan Deployment

```bash
terraform plan
```

Review the planned changes. Terraform will show you what resources will be created.

#### 4. Apply Configuration

```bash
terraform apply
```

Type `yes` to confirm. Deployment takes approximately 15-20 minutes.

#### 5. Get Outputs

```bash
terraform output
```

**Important outputs:**
- `alb_dns_name`: URL to access your application
- `rds_endpoint`: Database endpoint
- `redis_endpoint`: Redis endpoint
- `ecs_cluster_name`: ECS cluster name

### Using the Deployment Script

For automated deployment, use the provided script:

```bash
# Plan deployment
../scripts/deploy.sh production plan

# Deploy infrastructure
../scripts/deploy.sh production apply

# Destroy infrastructure (CAUTION!)
../scripts/deploy.sh production destroy
```

The script handles:
- Prerequisites checking
- Docker image building and pushing
- Terraform initialization and execution
- Output display

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          Internet                            │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│         Application Load Balancer (ALB)                      │
│              SSL/TLS Termination                             │
│         Health Checks: /health (backend, frontend)           │
└─────────────┬────────────────────────┬────────────────────────┘
              │                        │
    ┌─────────▼──────────┐  ┌─────────▼─────────────────────┐
    │  Frontend          │  │  Backend                      │
    │  Container         │  │  Container                    │
    │  (Nginx)           │  │  (FastAPI)                    │
    │  Port 80           │  │  Port 8000                    │
    └─────────┬──────────┘  └─────────┬─────────────────────┘
              │                        │
              └────────────┬───────────┘
                           │
          ┌────────────────┼────────────────────┐
          │                │                    │
┌─────────▼─────┐  ┌───────▼───────┐  ┌────────▼────────┐
│  RDS          │  │ ElastiCache   │  │  AWS Services   │
│  PostgreSQL   │  │  Redis        │  │  Cost Explorer  │
│  Multi-AZ     │  │  Cluster      │  │  Budgets        │
└───────────────┘  └───────────────┘  └─────────────────┘
```

### Network Architecture

```
VPC (10.0.0.0/16)
├── Public Subnets (Internet-facing)
│   ├── Subnet 1 (10.0.1.0/24) - AZ 1
│   │   └── NAT Gateway 1
│   └── Subnet 2 (10.0.2.0/24) - AZ 2
│       └── NAT Gateway 2
│
└── Private Subnets (Internal only)
    ├── Subnet 1 (10.0.11.0/24) - AZ 1
    │   ├── ECS Tasks
    │   ├── RDS Primary
    │   └── Redis Node 1
    └── Subnet 2 (10.0.12.0/24) - AZ 2
        ├── ECS Tasks
        ├── RDS Standby
        └── Redis Node 2
```

---

## Resource Specifications

### Default Configuration

| Resource | Specification | Monthly Cost (Est.) |
|----------|--------------|---------------------|
| **VPC** | 1 VPC, 4 subnets | Free |
| **NAT Gateway** | 2 NAT GWs (Multi-AZ) | ~$65 |
| **ECS Fargate** | 2 tasks, 1 vCPU, 2GB RAM | ~$75 |
| **RDS PostgreSQL** | db.t3.medium, Multi-AZ | ~$130 |
| **ElastiCache Redis** | cache.t3.medium, Multi-AZ | ~$100 |
| **ALB** | Application Load Balancer | ~$25 |
| **Data Transfer** | Varies by usage | ~$20 |
| **Total** | | **~$415/month** |

### Production Configuration

For larger production deployments:

```hcl
# High-performance configuration
db_instance_class = "db.r5.large"      # $200/month
redis_node_type = "cache.r5.large"     # $175/month
ecs_task_cpu = "2048"                  # 2 vCPU
ecs_task_memory = "4096"               # 4 GB
ecs_desired_count = 4                  # 4 tasks
```

Estimated cost: ~$800/month

---

## Customization

### Scaling Configuration

Modify auto-scaling parameters in `main.tf`:

```hcl
# Auto-scaling target
resource "aws_appautoscaling_target" "ecs" {
  max_capacity = 10  # Maximum tasks
  min_capacity = 2   # Minimum tasks
}

# CPU-based scaling
target_value = 70.0  # Scale at 70% CPU
scale_in_cooldown  = 300   # Wait 5 min before scaling in
scale_out_cooldown = 60    # Wait 1 min before scaling out
```

### Database Configuration

Adjust database specs in `terraform.tfvars`:

```hcl
db_instance_class = "db.t3.large"     # Larger instance
db_allocated_storage = 500            # 500 GB storage
multi_az = true                       # Enable Multi-AZ
```

### Redis Configuration

Modify Redis cluster:

```hcl
redis_node_type = "cache.r5.large"    # Larger nodes
redis_num_cache_nodes = 3             # 3-node cluster
```

### Environment-Specific Deployments

Use workspaces for multiple environments:

```bash
# Create workspace
terraform workspace new staging

# Switch workspace
terraform workspace select production

# Deploy
terraform apply -var="environment=$(terraform workspace show)"
```

---

## Security Best Practices

### 1. Secrets Management

**Never commit secrets to version control!**

- Use AWS Secrets Manager for sensitive data
- Store database passwords securely
- Rotate secrets regularly
- Use IAM roles instead of access keys

### 2. Network Security

- Private subnets for all data resources
- Security groups with least-privilege access
- Enable VPC Flow Logs (optional)
- Use AWS WAF for ALB (optional)

### 3. Encryption

- Enable encryption at rest (RDS, ElastiCache)
- Enable encryption in transit (TLS)
- Use AWS KMS for key management (optional)

### 4. IAM Permissions

The ECS task role has read-only access to AWS services:
- Cost Explorer
- Budgets
- EC2, RDS, Lambda (for auditing)

**No write permissions** - the application cannot modify resources.

---

## State Management

### Local State (Default)

Terraform state is stored locally in `terraform.tfstate`.

**⚠️ Important:** This file contains sensitive data. Do NOT commit to version control!

### Remote State (Recommended for Teams)

For production and team environments, use remote state:

```hcl
# Uncomment in main.tf
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "aws-cost-dashboard/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
```

Create S3 bucket and DynamoDB table:

```bash
# S3 bucket for state
aws s3 mb s3://your-terraform-state-bucket
aws s3api put-bucket-versioning \
  --bucket your-terraform-state-bucket \
  --versioning-configuration Status=Enabled

# DynamoDB table for locking
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
```

---

## Troubleshooting

### Common Issues

#### 1. "Error creating VPC"

**Cause:** VPC quota reached or CIDR conflict

**Solution:**
- Check VPC quota: `aws ec2 describe-account-attributes`
- Choose different CIDR block in `terraform.tfvars`

#### 2. "Error creating RDS instance"

**Cause:** DB subnet group or parameter issue

**Solution:**
- Ensure subnets are in different AZs
- Check RDS service quotas
- Verify db_password meets requirements (min 8 chars)

#### 3. "Error registering task definition"

**Cause:** Docker images not accessible

**Solution:**
- Verify images exist in registry
- Check ECR permissions
- Ensure execution role can pull images

#### 4. "ECS tasks failing to start"

**Cause:** Resource constraints or secrets access

**Solution:**
- Check CloudWatch logs
- Verify secrets exist in Secrets Manager
- Check IAM role permissions
- Ensure security groups allow outbound traffic

### Viewing Logs

```bash
# Terraform output
terraform output

# ECS task logs
aws logs tail /ecs/awscost-backend-production --follow

# ECS service events
aws ecs describe-services \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --services $(terraform output -raw ecs_service_name) \
  --query 'services[0].events[0:5]'
```

---

## Maintenance

### Updating Infrastructure

```bash
# Plan changes
terraform plan

# Apply updates
terraform apply

# ECS will perform rolling update automatically
```

### Destroying Infrastructure

**⚠️ CAUTION:** This permanently deletes all resources!

```bash
# Review what will be destroyed
terraform plan -destroy

# Destroy (requires confirmation)
terraform destroy
```

**Note:** RDS has deletion protection enabled in production. You must manually disable it before destroying:

```bash
aws rds modify-db-instance \
  --db-instance-identifier awscost-db-production \
  --no-deletion-protection
```

---

## Cost Optimization

### Development Environment

For non-production:

```hcl
environment = "development"
db_instance_class = "db.t3.small"
db_allocated_storage = 20
redis_node_type = "cache.t3.micro"
redis_num_cache_nodes = 1  # Single node (no Multi-AZ)
ecs_desired_count = 1
```

Estimated cost: ~$120/month

### Spot Instances

ECS uses Fargate Spot by default (80% weight) for cost savings:

```hcl
default_capacity_provider_strategy {
  capacity_provider = "FARGATE"
  weight            = 1
  base              = 1  # Always run 1 task on regular Fargate
}

default_capacity_provider_strategy {
  capacity_provider = "FARGATE_SPOT"
  weight            = 4  # 80% on Spot
}
```

Potential savings: ~30% on compute costs

---

## Support

For infrastructure issues:

1. Check [DEPLOYMENT_GUIDE.md](../docs/DEPLOYMENT_GUIDE.md)
2. Review Terraform output and logs
3. Check AWS console for service health
4. Open an issue on GitHub

---

## License

[Your License Here]
