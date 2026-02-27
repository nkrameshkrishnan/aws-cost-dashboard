# AWS API Gateway + ECS Deployment Guide

This guide walks you through deploying the AWS Cost Dashboard backend infrastructure using AWS API Gateway and ECS Fargate.

## Architecture Overview

```
GitHub Pages → API Gateway → VPC Link → Internal ALB → ECS Fargate
                                                        ↓
                                                    RDS + Redis
```

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI v2 installed (`aws --version`)
- Terraform installed (`terraform --version`)
- Docker installed (`docker --version`)
- Git installed

## Step 1: Configure AWS Credentials

### Option A: AWS SSO Login (Recommended for Enterprise)

If you're using AWS SSO (Single Sign-On):

```bash
# Configure SSO profile
aws configure sso

# Follow the prompts:
# - SSO start URL: Your organization's SSO portal URL
# - SSO region: us-east-1 (or your region)
# - CLI default client Region: us-east-1
# - CLI default output format: json
# - CLI profile name: ramesh (or any name)

# Login to AWS
aws sso login --profile ramesh

# Set environment variable to use this profile
export AWS_PROFILE=ramesh

# Verify credentials
aws sts get-caller-identity
```

### Option B: Standard AWS Credentials

```bash
# Configure AWS credentials
aws configure

# Enter when prompted:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: us-east-1
# - Default output format: json

# Verify credentials
aws sts get-caller-identity
```

**Expected Output:**
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "302645411908",
    "Arn": "arn:aws:iam::302645411908:user/your-username"
}
```

## Step 2: Review Terraform Configuration

The `terraform.tfvars` file has been pre-configured with:

✅ **AWS Account ID:** 302645411908
✅ **Region:** us-east-1
✅ **Environment:** dev (cost-optimized for development)
✅ **Database Password:** Auto-generated secure password
✅ **Secret Keys:** Auto-generated encryption keys
✅ **CORS Origins:** GitHub Pages URL configured

**Cost-Optimized Settings for Development:**
- RDS: `db.t3.micro` (instead of db.t3.medium)
- ElastiCache: `cache.t3.micro` (instead of cache.t3.medium)
- ECS Tasks: 1 task (instead of 2)
- CPU/Memory: 512 CPU / 1024 MB (instead of 1024/2048)

**Estimated Monthly Cost:** ~$45-55/month for development

Review the file:
```bash
cat infrastructure/terraform/terraform.tfvars
```

## Step 3: Create ECR Repositories

Create ECR repositories to store Docker images:

```bash
# Create backend repository
aws ecr create-repository \
  --repository-name awscost-backend \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true

# Create frontend repository (for future use)
aws ecr create-repository \
  --repository-name awscost-frontend \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true
```

**Expected Output:**
```json
{
    "repository": {
        "repositoryArn": "arn:aws:ecr:us-east-1:302645411908:repository/awscost-backend",
        "repositoryName": "awscost-backend",
        "repositoryUri": "302645411908.dkr.ecr.us-east-1.amazonaws.com/awscost-backend"
    }
}
```

## Step 4: Build and Push Backend Docker Image

```bash
# Navigate to project root
cd /Users/rameshkrishnannarashimankrishnamurthy/aws-cost-dashboard

# Build backend Docker image
docker build -f backend/Dockerfile.prod -t awscost-backend:latest ./backend

# Verify image was built
docker images | grep awscost-backend

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  302645411908.dkr.ecr.us-east-1.amazonaws.com

# Tag the image
docker tag awscost-backend:latest \
  302645411908.dkr.ecr.us-east-1.amazonaws.com/awscost-backend:latest

# Push to ECR
docker push 302645411908.dkr.ecr.us-east-1.amazonaws.com/awscost-backend:latest
```

**Note:** Frontend is hosted on GitHub Pages, so we don't need to push the frontend image for now.

## Step 5: Deploy Infrastructure with Terraform

```bash
# Navigate to Terraform directory
cd infrastructure/terraform

# Initialize Terraform (download providers and modules)
terraform init

# Validate configuration
terraform validate

# Plan the deployment (see what will be created)
terraform plan -out=tfplan

# Review the plan output carefully
# Expected resources: ~60-70 resources to be created
# - VPC with public/private subnets
# - Internal ALB
# - VPC Link
# - API Gateway HTTP API
# - ECS Cluster and Service
# - RDS PostgreSQL database
# - ElastiCache Redis
# - Security groups, IAM roles, CloudWatch logs, etc.

# Apply the plan (deploy infrastructure)
terraform apply tfplan
```

**Deployment Time:** Approximately 15-20 minutes

**What gets created:**
1. ✅ VPC with public and private subnets across 2 AZs
2. ✅ NAT Gateway for outbound internet access
3. ✅ Internal Application Load Balancer (not publicly accessible)
4. ✅ VPC Link to connect API Gateway to ALB
5. ✅ API Gateway HTTP API with CORS configured
6. ✅ ECS Fargate cluster and service
7. ✅ RDS PostgreSQL database (db.t3.micro)
8. ✅ ElastiCache Redis (cache.t3.micro)
9. ✅ Security groups and IAM roles
10. ✅ CloudWatch log groups
11. ✅ Secrets Manager for sensitive data

## Step 6: Get API Gateway URL

After successful deployment, get the API Gateway URL:

```bash
# Get API Gateway URL
terraform output api_gateway_url

# Example output:
# https://abc123xyz.execute-api.us-east-1.amazonaws.com
```

**Save this URL!** You'll need it for the frontend configuration.

## Step 7: Verify Backend Health

Test the backend health endpoint:

```bash
# Store API URL in variable
API_URL=$(terraform output -raw api_gateway_url)

# Test health endpoint
curl $API_URL/api/v1/health

# Expected response:
# {"status":"healthy","timestamp":"2026-02-27T...","database":"connected","cache":"connected"}
```

If you see `{"status":"healthy"}`, the backend is running successfully! 🎉

## Step 8: Test CORS Configuration

Verify CORS is configured correctly for GitHub Pages:

```bash
# Test CORS preflight
curl -X OPTIONS \
  -H "Origin: https://dsgithub.trendmicro.com/pages/rameshkrishnan-narashimankrishnamurthy/aws-cost-dashboard" \
  -H "Access-Control-Request-Method: GET" \
  -v \
  $API_URL/api/v1/health 2>&1 | grep -i "access-control"

# Expected headers:
# access-control-allow-origin: https://dsgithub.trendmicro.com/pages/rameshkrishnan-narashimankrishnamurthy/aws-cost-dashboard
# access-control-allow-credentials: true
```

## Step 9: Update Frontend Configuration

Update the frontend to use the deployed API Gateway URL:

```bash
# Navigate to frontend directory
cd ../../frontend

# Create/update .env.production
cat > .env.production << EOF
VITE_API_BASE_URL=$API_URL
VITE_API_VERSION=v1
EOF

# Build frontend with new API URL
npm run build

# Deploy to GitHub Pages
npm run deploy
```

## Step 10: Access Your Application

Your application should now be fully deployed:

**Frontend:** https://dsgithub.trendmicro.com/pages/rameshkrishnan-narashimankrishnamurthy/aws-cost-dashboard
**Backend API:** `https://[your-api-id].execute-api.us-east-1.amazonaws.com`

## Troubleshooting

### Issue: "Unable to locate credentials"

**Solution:**
```bash
# For SSO:
aws sso login --profile ramesh
export AWS_PROFILE=ramesh

# For standard credentials:
aws configure
```

### Issue: Terraform plan fails with "Error: No valid credential sources found"

**Solution:**
```bash
# Verify AWS credentials are working
aws sts get-caller-identity

# If not working, reconfigure:
aws configure
```

### Issue: Docker push fails with "no basic auth credentials"

**Solution:**
```bash
# Re-authenticate with ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  302645411908.dkr.ecr.us-east-1.amazonaws.com
```

### Issue: Backend health check fails

**Solution:**
```bash
# Check ECS task status
aws ecs list-tasks --cluster awscost-dev-cluster --region us-east-1

# Get task details
aws ecs describe-tasks \
  --cluster awscost-dev-cluster \
  --tasks [task-arn-from-above] \
  --region us-east-1

# Check CloudWatch logs
aws logs tail /ecs/awscost-dev-backend --follow --region us-east-1
```

### Issue: CORS errors in browser

**Solution:**
1. Verify CORS origins in terraform.tfvars match your GitHub Pages URL exactly
2. Redeploy infrastructure: `terraform apply`
3. Clear browser cache and reload

### Issue: RDS connection timeout

**Possible causes:**
- Security group not allowing ECS task traffic
- RDS not in correct subnet
- Database still initializing (wait 5-10 minutes)

**Check:**
```bash
# View RDS instance status
aws rds describe-db-instances \
  --db-instance-identifier awscost-dev-database \
  --query 'DBInstances[0].DBInstanceStatus' \
  --region us-east-1
```

## Viewing Logs

### ECS Task Logs (Application Logs)
```bash
# View backend logs in real-time
aws logs tail /ecs/awscost-dev-backend --follow --region us-east-1

# View last 1 hour of logs
aws logs tail /ecs/awscost-dev-backend --since 1h --region us-east-1
```

### API Gateway Logs
```bash
# View API Gateway access logs
aws logs tail /aws/apigateway/awscost-dev-http-api --follow --region us-east-1
```

### ALB Logs
Access logs are stored in CloudWatch Logs group: `/aws/alb/awscost-dev-alb`

## Monitoring

### CloudWatch Dashboard

You can create a CloudWatch dashboard to monitor your application:

```bash
# View ECS service metrics in AWS Console
# https://console.aws.amazon.com/ecs/

# View API Gateway metrics
# https://console.aws.amazon.com/apigateway/

# View RDS metrics
# https://console.aws.amazon.com/rds/
```

### Key Metrics to Monitor

1. **ECS Service:**
   - CPU Utilization (should be < 70%)
   - Memory Utilization (should be < 80%)
   - Running task count (should match desired count)

2. **API Gateway:**
   - Request count
   - 4xx/5xx error rates
   - Latency (P50, P90, P99)

3. **RDS:**
   - CPU Utilization
   - Database Connections
   - Freeable Memory
   - Read/Write IOPS

4. **ElastiCache:**
   - CPU Utilization
   - Cache Hit Rate (should be > 80%)
   - Network Bytes In/Out

## Cost Optimization

### Development Environment (~$45-55/month)

Current configuration:
- RDS: db.t3.micro ($15/month)
- ElastiCache: cache.t3.micro ($12/month)
- ECS Fargate: 1 task 512 CPU / 1024 MB ($10/month)
- API Gateway: HTTP API with 1M requests ($1/month)
- VPC Link ($10/month)
- NAT Gateway ($32/month)
- Data Transfer (~$5/month)

### Further Cost Reduction

1. **Stop non-production resources overnight:**
```bash
# Stop ECS service
aws ecs update-service \
  --cluster awscost-dev-cluster \
  --service awscost-dev-backend-service \
  --desired-count 0 \
  --region us-east-1

# Start in the morning
aws ecs update-service \
  --cluster awscost-dev-cluster \
  --service awscost-dev-backend-service \
  --desired-count 1 \
  --region us-east-1
```

2. **Use RDS Aurora Serverless v2** for auto-pause (future optimization)

3. **Use AWS VPN instead of NAT Gateway** ($5/month vs $32/month)

## Cleanup (Destroying Infrastructure)

**⚠️ WARNING:** This will delete all resources and data!

```bash
# Navigate to Terraform directory
cd infrastructure/terraform

# Destroy all resources
terraform destroy

# Confirm by typing 'yes' when prompted

# Delete ECR repositories
aws ecr delete-repository \
  --repository-name awscost-backend \
  --force \
  --region us-east-1

aws ecr delete-repository \
  --repository-name awscost-frontend \
  --force \
  --region us-east-1
```

## Next Steps

After successful deployment:

1. ✅ **Add AWS Account Credentials**
   - Navigate to: https://[your-github-pages-url]/aws-accounts
   - Click "Add AWS Account"
   - Enter AWS account details and credentials
   - Test connection

2. ✅ **Set Up Budgets**
   - Navigate to: https://[your-github-pages-url]/budgets
   - Create monthly budget alerts
   - Configure notification emails

3. ✅ **Run FinOps Audit**
   - Navigate to: https://[your-github-pages-url]/finops-audit
   - Run comprehensive cost audit
   - Review recommendations

4. ✅ **Configure Automation**
   - Set up scheduled cost snapshots
   - Enable auto-tagging
   - Configure RI/SP recommendations

## Support

For issues and questions:
- GitHub Issues: https://dsgithub.trendmicro.com/rameshkrishnan-narashimankrishnamurthy/aws-cost-dashboard/issues
- Documentation: See `IMPLEMENTATION_SUMMARY.md` and `GITHUB_PAGES_DEPLOYMENT.md`

## Security Best Practices

1. ✅ **Secrets Management**
   - All secrets stored in AWS Secrets Manager
   - Database credentials rotated regularly
   - Encryption keys never committed to Git

2. ✅ **Network Security**
   - ALB in private subnets (not internet-facing)
   - VPC Link for API Gateway → ALB communication
   - Security groups with least-privilege access
   - Database only accessible from ECS tasks

3. ✅ **Data Encryption**
   - RDS encryption at rest enabled
   - ElastiCache encryption in transit enabled
   - AWS credentials encrypted with Fernet key
   - HTTPS for all API communication

4. ✅ **IAM Security**
   - Task execution role with minimal permissions
   - No long-term AWS credentials in code
   - OIDC for GitHub Actions (when enabled)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│ GitHub Pages (Frontend)                                 │
│ https://dsgithub.trendmicro.com/pages/.../              │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────────────────┐
│ API Gateway HTTP API                                    │
│ https://[api-id].execute-api.us-east-1.amazonaws.com   │
│ - CORS: GitHub Pages URL                               │
│ - Rate Limiting: 10,000 req/sec                        │
│ - CloudWatch Logging                                    │
└────────────────────┬────────────────────────────────────┘
                     │ VPC Link
                     ▼
┌─────────────────────────────────────────────────────────┐
│ Internal ALB (Private Subnets)                          │
│ - Health checks: /api/v1/health                        │
│ - Target: ECS tasks                                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ ECS Fargate Cluster                                     │
│ ┌──────────────────────────────────────────┐           │
│ │ Backend Service (1 task - dev)           │           │
│ │ - FastAPI application                     │           │
│ │ - Gunicorn + Uvicorn workers             │           │
│ │ - Auto-scaling: 1-4 tasks                │           │
│ └──────────────────────────────────────────┘           │
└───────────────┬─────────────────┬──────────────────────┘
                │                 │
                ▼                 ▼
┌────────────────────────┐  ┌──────────────────────┐
│ RDS PostgreSQL         │  │ ElastiCache Redis    │
│ - db.t3.micro          │  │ - cache.t3.micro     │
│ - 20 GB storage        │  │ - 1 node (dev)       │
│ - Private subnet       │  │ - Private subnet     │
│ - Encrypted at rest    │  │ - Encrypted transit  │
└────────────────────────┘  └──────────────────────┘
```

---

**Deployment Complete!** 🎉

You now have a production-ready AWS Cost Dashboard with:
- ✅ Serverless frontend on GitHub Pages
- ✅ API Gateway for API management
- ✅ ECS Fargate for container orchestration
- ✅ RDS PostgreSQL for data persistence
- ✅ ElastiCache Redis for caching
- ✅ Full Infrastructure as Code with Terraform
- ✅ Comprehensive monitoring and logging
- ✅ Security best practices implemented
