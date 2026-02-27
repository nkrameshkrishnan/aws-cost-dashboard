# AWS Cost Dashboard - Staging Deployment Guide

**Environment**: Staging
**Target Cost**: ~$200/month (smaller instances than production)
**Deployment Time**: 1-2 hours
**Prerequisites**: AWS Account, AWS CLI, Docker, Terraform

---

## Overview

This guide walks you through deploying the AWS Cost Dashboard to a staging environment on AWS to validate the infrastructure before production deployment.

### Staging vs Production Differences

| Component | Staging | Production |
|-----------|---------|------------|
| **Database** | db.t3.small | db.t3.medium |
| **Redis** | cache.t3.micro (single node) | cache.t3.medium (Multi-AZ) |
| **ECS Tasks** | 1 task | 2 tasks |
| **Auto-scaling** | 1-3 tasks | 2-10 tasks |
| **Backups** | 1 day retention | 7 day retention |
| **Multi-AZ** | Disabled | Enabled |
| **Cost** | ~$200/month | ~$415/month |

---

## Pre-Deployment Checklist

### 1. AWS Account Setup

- [ ] AWS account with appropriate permissions
- [ ] AWS CLI installed and configured
- [ ] Billing alerts enabled
- [ ] Cost Explorer enabled (takes 24 hours to activate)

### 2. Local Requirements

- [ ] Terraform >= 1.0 installed
- [ ] Docker >= 20.10 installed
- [ ] Git configured
- [ ] Text editor (vim, nano, VS Code)

### 3. Generate Application Secrets

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY (Fernet key)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate strong database password
openssl rand -base64 32
```

Save these values securely - you'll need them in the next step.

---

## Step 1: Configure Terraform Variables

### 1.1. Navigate to Terraform Directory

```bash
cd infrastructure/terraform
```

### 1.2. Create terraform.tfvars

```bash
cp terraform.tfvars.example terraform.tfvars
```

### 1.3. Edit Configuration

```bash
vim terraform.tfvars
```

**Staging Configuration**:

```hcl
# ============================================================================
# AWS Cost Dashboard - Staging Environment
# ============================================================================

# General Configuration
aws_region   = "us-east-1"  # Change to your preferred region
environment  = "staging"
project_name = "awscost"

# Database Configuration
db_name                  = "aws_cost_dashboard"
db_username              = "dbadmin"
db_password              = "YOUR_STRONG_PASSWORD_HERE"  # From pre-deployment step
db_instance_class        = "db.t3.small"                # Smaller for staging
db_allocated_storage     = 20                           # 20 GB for staging
db_engine_version        = "15.4"

# Redis Configuration
redis_node_type          = "cache.t3.micro"   # Smallest for staging
redis_num_cache_nodes    = 1                  # Single node
redis_engine_version     = "7.0"

# Application Secrets (from pre-deployment step)
secret_key     = "YOUR_SECRET_KEY_HERE"
jwt_secret_key = "YOUR_JWT_SECRET_KEY_HERE"
encryption_key = "YOUR_ENCRYPTION_KEY_HERE"  # 44 characters

# Docker Images
# Option 1: Build and push to ECR first (recommended)
backend_image  = "123456789012.dkr.ecr.us-east-1.amazonaws.com/awscost-backend:staging"
frontend_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/awscost-frontend:staging"

# Option 2: Use Docker Hub
# backend_image  = "your-dockerhub-username/awscost-backend:staging"
# frontend_image = "your-dockerhub-username/awscost-frontend:staging"

# Option 3: Use GitHub Container Registry
# backend_image  = "ghcr.io/your-username/awscost-backend:staging"
# frontend_image = "ghcr.io/your-username/awscost-frontend:staging"

# ECS Configuration (scaled down for staging)
backend_task_cpu    = 512      # 0.5 vCPU
backend_task_memory = 1024     # 1 GB
frontend_task_cpu   = 256      # 0.25 vCPU
frontend_task_memory = 512     # 512 MB
ecs_desired_count   = 1        # 1 task for staging
ecs_min_capacity    = 1
ecs_max_capacity    = 3

# Load Balancer (Optional: HTTPS)
# certificate_arn = ""  # Leave empty for HTTP only
# certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/abc-123"  # For HTTPS

# Optional: S3 Bucket for Reports
# s3_bucket_arn = "arn:aws:s3:::your-reports-bucket"
```

---

## Step 2: Build and Push Docker Images

### Option A: AWS ECR (Recommended)

#### 2.1. Create ECR Repositories

```bash
# Set your AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="us-east-1"

# Create repositories
aws ecr create-repository \
  --repository-name awscost-backend \
  --region $AWS_REGION

aws ecr create-repository \
  --repository-name awscost-frontend \
  --region $AWS_REGION
```

#### 2.2. Login to ECR

```bash
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

#### 2.3. Build and Push Images

```bash
# Navigate to project root
cd /path/to/aws-cost-dashboard

# Build backend image
docker build -f backend/Dockerfile.prod -t awscost-backend:staging backend/
docker tag awscost-backend:staging \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/awscost-backend:staging
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/awscost-backend:staging

# Build frontend image
docker build -f frontend/Dockerfile.prod -t awscost-frontend:staging frontend/
docker tag awscost-frontend:staging \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/awscost-frontend:staging
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/awscost-frontend:staging
```

### Option B: Docker Hub

```bash
# Login to Docker Hub
docker login

# Build and push
docker build -f backend/Dockerfile.prod -t your-username/awscost-backend:staging backend/
docker push your-username/awscost-backend:staging

docker build -f frontend/Dockerfile.prod -t your-username/awscost-frontend:staging frontend/
docker push your-username/awscost-frontend:staging
```

---

## Step 3: Deploy Infrastructure with Terraform

### 3.1. Initialize Terraform

```bash
cd infrastructure/terraform
terraform init
```

Expected output:
```
Initializing modules...
Initializing the backend...
Initializing provider plugins...
Terraform has been successfully initialized!
```

### 3.2. Validate Configuration

```bash
terraform validate
```

Expected output:
```
Success! The configuration is valid.
```

### 3.3. Plan Deployment

```bash
terraform plan -out=staging.tfplan
```

Review the plan carefully. You should see:
- ~60-70 resources to be created
- VPC with subnets, NAT gateways
- RDS database (db.t3.small)
- ElastiCache Redis (cache.t3.micro)
- ECS cluster, task definitions, services
- Application Load Balancer
- Security groups
- IAM roles
- CloudWatch log groups
- Secrets Manager secrets

### 3.4. Apply Configuration

```bash
terraform apply staging.tfplan
```

**⏱️ Deployment Duration**: 15-20 minutes

Progress indicators:
- VPC and networking: 2-3 minutes
- RDS database: 5-8 minutes
- ElastiCache Redis: 3-5 minutes
- ECS cluster and services: 3-5 minutes
- Load balancer: 2-3 minutes

### 3.5. Save Outputs

```bash
terraform output > deployment-outputs.txt
```

**Important outputs**:
- `alb_dns_name` - URL to access your application
- `alb_url` - Full URL (http:// or https://)
- `ecs_cluster_name` - ECS cluster name
- `backend_service_name` - Backend service name
- `frontend_service_name` - Frontend service name

---

## Step 4: Verify Deployment

### 4.1. Check Infrastructure Status

```bash
# Check ECS services
aws ecs describe-services \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --services \
    $(terraform output -raw backend_service_name) \
    $(terraform output -raw frontend_service_name) \
  --query 'services[*].[serviceName,status,runningCount,desiredCount]' \
  --output table

# Check ALB target health
ALB_ARN=$(terraform output -raw alb_arn)
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --load-balancer-arn $ALB_ARN \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)
```

### 4.2. Access Application

```bash
# Get application URL
ALB_URL=$(terraform output -raw alb_url)
echo "Application URL: $ALB_URL"

# Open in browser
open $ALB_URL  # macOS
# OR
xdg-open $ALB_URL  # Linux
# OR manually navigate to the URL in your browser
```

### 4.3. Run Health Checks

```bash
# From project root
./scripts/health-check.sh staging $ALB_URL
```

Expected output:
```
==========================================
AWS Cost Dashboard - Health Check
==========================================
Environment: staging
Base URL: http://awscost-staging-alb-123456789.us-east-1.elb.amazonaws.com

✓ Backend API is healthy (HTTP 200)
✓ Database connection is healthy
✓ Redis connection is healthy
✓ AWS connectivity is healthy

==========================================
System Metrics
==========================================
{
  "cache": {
    "hit_rate": 0,
    "total_hits": 0
  }
}
==========================================
Health Check Summary
==========================================
Total checks: 4
Failed checks: 0
Success rate: 100%

✓ All health checks passed!
```

---

## Step 5: Post-Deployment Configuration

### 5.1. Run Database Migrations

```bash
# Get database endpoint
DB_ENDPOINT=$(terraform output -raw rds_endpoint)

# Option 1: Run migrations from ECS task
aws ecs execute-command \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --task $(aws ecs list-tasks \
    --cluster $(terraform output -raw ecs_cluster_name) \
    --service $(terraform output -raw backend_service_name) \
    --query 'taskArns[0]' --output text) \
  --container backend \
  --interactive \
  --command "/bin/bash"

# Then inside the container:
alembic upgrade head

# Option 2: Run migrations locally (requires VPN/bastion)
# Update DATABASE_URL in backend/.env with RDS endpoint
# cd backend && alembic upgrade head
```

### 5.2. Create Initial AWS Account Configuration

Navigate to the application and:
1. Go to Settings → AWS Accounts
2. Add your AWS account credentials
3. Test connection
4. Save

### 5.3. Configure Budget Alerts (Optional)

1. Navigate to Budgets page
2. Create your first budget
3. Set alert thresholds
4. Configure Teams webhook (if using Teams integration)

---

## Step 6: Monitoring & Logging

### 6.1. View CloudWatch Logs

```bash
# Backend logs
aws logs tail /ecs/awscost-staging-backend --follow

# Frontend logs
aws logs tail /ecs/awscost-staging-frontend --follow
```

### 6.2. Monitor ECS Service

```bash
# Watch service events
watch -n 5 'aws ecs describe-services \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --services $(terraform output -raw backend_service_name) \
  --query "services[0].events[0:3]"'
```

### 6.3. Set Up CloudWatch Alarms (Recommended)

```bash
# Create alarm for ECS CPU utilization
aws cloudwatch put-metric-alarm \
  --alarm-name awscost-staging-high-cpu \
  --alarm-description "Alert when ECS CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=ServiceName,Value=$(terraform output -raw backend_service_name) \
              Name=ClusterName,Value=$(terraform output -raw ecs_cluster_name)
```

---

## Troubleshooting

### Issue 1: ECS Tasks Not Starting

**Symptoms**: Tasks are stuck in PENDING or keep restarting

**Check**:
```bash
# Get task failures
aws ecs describe-tasks \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --tasks $(aws ecs list-tasks \
    --cluster $(terraform output -raw ecs_cluster_name) \
    --service $(terraform output -raw backend_service_name) \
    --query 'taskArns[0]' --output text) \
  --query 'tasks[0].stoppedReason'
```

**Common causes**:
- Image pull errors (check ECR permissions)
- Insufficient memory/CPU
- Environment variable issues
- Database connection failures

**Solutions**:
1. Check CloudWatch logs for errors
2. Verify docker images exist in registry
3. Check security group rules
4. Verify secrets in Secrets Manager

### Issue 2: Application Not Accessible via ALB

**Symptoms**: 502/503 errors from load balancer

**Check**:
```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $(terraform output -raw backend_target_group_arn)
```

**Common causes**:
- Health check failing
- Security groups blocking traffic
- Tasks not running

**Solutions**:
1. Check health check endpoint: `curl $ALB_URL/health`
2. Verify security groups allow ALB → ECS traffic
3. Check if ECS tasks are running

### Issue 3: Database Connection Errors

**Symptoms**: Backend logs show connection errors

**Check**:
```bash
# Test database connectivity from ECS task
aws ecs execute-command \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --task <task-id> \
  --container backend \
  --interactive \
  --command "/bin/bash"

# Inside container:
pg_isready -h $DATABASE_HOST -p 5432
```

**Solutions**:
1. Verify RDS security group allows traffic from ECS security group
2. Check database credentials in Secrets Manager
3. Verify database is in "available" state

### Issue 4: High Costs

**Check current spend**:
```bash
# Get current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --filter file://<(echo '{"Tags":{"Key":"Environment","Values":["staging"]}}')
```

**Cost optimization**:
1. Stop environment when not in use:
   ```bash
   # Stop ECS services
   aws ecs update-service \
     --cluster $(terraform output -raw ecs_cluster_name) \
     --service $(terraform output -raw backend_service_name) \
     --desired-count 0
   ```
2. Use smaller instance types
3. Disable Multi-AZ for staging
4. Reduce backup retention

---

## Updating the Deployment

### Code Changes

```bash
# Rebuild and push images
docker build -f backend/Dockerfile.prod -t awscost-backend:staging backend/
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/awscost-backend:staging

# Force new deployment
aws ecs update-service \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service $(terraform output -raw backend_service_name) \
  --force-new-deployment
```

### Infrastructure Changes

```bash
# Make changes to terraform.tfvars or Terraform files

# Plan changes
terraform plan

# Apply changes
terraform apply
```

---

## Destroying the Staging Environment

**⚠️ WARNING**: This will delete all resources and data!

```bash
# Disable deletion protection on RDS (if enabled)
aws rds modify-db-instance \
  --db-instance-identifier awscost-db-staging \
  --no-deletion-protection

# Destroy all resources
terraform destroy

# Confirm by typing: yes
```

**Cleanup ECR** (optional):
```bash
aws ecr delete-repository \
  --repository-name awscost-backend \
  --force

aws ecr delete-repository \
  --repository-name awscost-frontend \
  --force
```

---

## Cost Monitoring

### Expected Monthly Costs (Staging)

| Service | Specification | Monthly Cost |
|---------|--------------|--------------|
| VPC | 1 VPC, 4 subnets | Free |
| NAT Gateway | 2 NAT GWs | ~$65 |
| ECS Fargate | 1 task, 0.75 vCPU, 1.5GB | ~$35 |
| RDS PostgreSQL | db.t3.small, Single-AZ | ~$40 |
| ElastiCache Redis | cache.t3.micro, Single node | ~$15 |
| ALB | Application Load Balancer | ~$25 |
| CloudWatch Logs | 30-day retention | ~$10 |
| Data Transfer | Minimal | ~$10 |
| **Total** | | **~$200/month** |

### Cost Alerts

Set up billing alerts:
```bash
# Create SNS topic for billing alerts
aws sns create-topic --name awscost-billing-alerts

# Subscribe to topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:awscost-billing-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# Create billing alarm
aws cloudwatch put-metric-alarm \
  --alarm-name staging-monthly-cost-alert \
  --alarm-description "Alert when staging costs exceed $250" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 21600 \
  --threshold 250 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=Currency,Value=USD
```

---

## Next Steps

After successful staging deployment:

1. ✅ **Run functional tests** - Test all features manually
2. ✅ **Run load tests** - Use k6 or Locust
3. ✅ **Security audit** - Run security scans
4. ✅ **Performance optimization** - Tune cache TTL, database queries
5. ✅ **Documentation** - Document any issues found
6. ✅ **Production planning** - Prepare for production deployment

---

## Support & Resources

- [Infrastructure README](infrastructure/README.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Terraform Modules Documentation](infrastructure/terraform/modules/README.md)
- [Health Check Script](scripts/health-check.sh)
- [AWS ECS Troubleshooting](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/troubleshooting.html)

---

**Deployment Status**: Ready
**Estimated Deployment Time**: 1-2 hours
**Estimated Monthly Cost**: ~$200
