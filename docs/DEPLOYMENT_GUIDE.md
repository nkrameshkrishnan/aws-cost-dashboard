# AWS Cost Dashboard - Deployment Guide

Complete guide for deploying the AWS Cost Dashboard to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Production Deployment Options](#production-deployment-options)
4. [AWS ECS/Fargate Deployment](#aws-ecsfargate-deployment)
5. [Docker Compose Deployment](#docker-compose-deployment)
6. [Environment Configuration](#environment-configuration)
7. [SSL/TLS Configuration](#ssltls-configuration)
8. [Monitoring and Logging](#monitoring-and-logging)
9. [Backup and Recovery](#backup-and-recovery)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

- **Docker** (20.10+) and Docker Compose (2.0+)
- **AWS CLI** (2.0+) configured with appropriate credentials
- **Node.js** (20.x) and npm (for local frontend development)
- **Python** (3.11+) and pip (for local backend development)
- **Git** for version control

### AWS Account Requirements

- AWS account with appropriate IAM permissions
- Access to the following AWS services:
  - **ECS/Fargate** - Container orchestration
  - **RDS PostgreSQL** - Database
  - **ElastiCache Redis** - Caching
  - **ALB** (Application Load Balancer) - Load balancing
  - **Route 53** - DNS (optional)
  - **CloudFront** - CDN (optional)
  - **Secrets Manager** - Secure credential storage
  - **CloudWatch** - Logging and monitoring

### Required IAM Permissions

The application needs IAM permissions to access:
- **AWS Cost Explorer API** - Cost data retrieval
- **AWS Budgets API** - Budget information
- **EC2, RDS, Lambda, ELB** - FinOps audit resource scanning

See [IAM_PERMISSIONS.md](./IAM_PERMISSIONS.md) for the complete IAM policy.

---

## Local Development Setup

### Quick Start with Docker Compose

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/aws-cost-dashboard.git
   cd aws-cost-dashboard
   ```

2. **Configure environment variables:**
   ```bash
   # Backend
   cp backend/.env.example backend/.env
   # Edit backend/.env with your settings

   # Frontend
   cp frontend/.env.example frontend/.env
   # Edit frontend/.env if needed
   ```

3. **Configure AWS credentials:**
   Ensure `~/.aws/credentials` contains your AWS profiles:
   ```ini
   [default]
   aws_access_key_id = YOUR_ACCESS_KEY
   aws_secret_access_key = YOUR_SECRET_KEY
   region = us-east-1
   ```

4. **Start the application:**
   ```bash
   docker-compose up -d
   ```

5. **Access the application:**
   - **Frontend**: http://localhost:5173
   - **Backend API**: http://localhost:8000
   - **API Docs**: http://localhost:8000/docs

6. **View logs:**
   ```bash
   docker-compose logs -f backend
   docker-compose logs -f frontend
   ```

7. **Stop the application:**
   ```bash
   docker-compose down
   ```

### Local Development (Without Docker)

#### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Start PostgreSQL and Redis (via Docker or local installation)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15-alpine
docker run -d -p 6379:6379 redis:7-alpine

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment
cp .env.example .env
# Edit .env if needed

# Start development server
npm run dev
```

---

## Production Deployment Options

### Option 1: AWS ECS/Fargate (Recommended)

**Pros:**
- Fully managed container orchestration
- Auto-scaling capabilities
- High availability across multiple AZs
- Integrated with AWS services (ALB, CloudWatch, Secrets Manager)
- No EC2 instance management

**Cons:**
- Higher cost than EC2-based deployments
- AWS-specific (not portable)

**Best for:** Production environments requiring high availability and scalability

### Option 2: Docker Compose on EC2

**Pros:**
- Simple deployment
- Full control over infrastructure
- Lower cost for small deployments
- Easy to understand and debug

**Cons:**
- Manual scaling
- Requires EC2 instance management
- Single point of failure (without additional setup)

**Best for:** Development, staging, or small production environments

### Option 3: Kubernetes (EKS)

**Pros:**
- Highly scalable
- Multi-cloud portability
- Advanced orchestration features

**Cons:**
- Complex setup and management
- Higher operational overhead
- More expensive

**Best for:** Large-scale deployments or organizations already using Kubernetes

---

## AWS ECS/Fargate Deployment

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                          Internet                            │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                    Route 53 (DNS)                            │
│                  your-domain.com                             │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│         CloudFront (CDN) - Optional                          │
│              Static asset caching                            │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│      Application Load Balancer (ALB)                         │
│         SSL/TLS Termination                                  │
│      Port 443 (HTTPS) → Target Groups                        │
└─────────────┬────────────────────────┬────────────────────────┘
              │                        │
┌─────────────▼──────────┐  ┌─────────▼─────────────────────┐
│   Frontend Container   │  │   Backend Container           │
│    (Nginx + React)     │  │   (FastAPI + Gunicorn)        │
│    Port 80 → 3000      │  │   Port 8000                   │
│    ECS Fargate Task    │  │   ECS Fargate Task            │
│    Auto-scaling        │  │   Auto-scaling                │
└─────────────┬──────────┘  └─────────┬─────────────────────┘
              │                        │
              └────────────┬───────────┘
                           │
          ┌────────────────┼────────────────────┐
          │                │                    │
┌─────────▼─────┐  ┌───────▼───────┐  ┌────────▼────────┐
│  RDS          │  │ ElastiCache   │  │  AWS Services   │
│  PostgreSQL   │  │  Redis        │  │  Cost Explorer  │
│  Multi-AZ     │  │  Cluster      │  │  Budgets, EC2   │
└───────────────┘  └───────────────┘  └─────────────────┘
```

### Step 1: Provision AWS Infrastructure

#### 1.1 Create VPC and Networking

```bash
# Create VPC
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=awscost-vpc}]'

# Create subnets (public and private in 2 AZs)
# Public subnet AZ1
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=awscost-public-1a}]'

# Public subnet AZ2
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=awscost-public-1b}]'

# Private subnet AZ1
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.11.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=awscost-private-1a}]'

# Private subnet AZ2
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.12.0/24 \
  --availability-zone us-east-1b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=awscost-private-1b}]'

# Create and attach Internet Gateway
aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=awscost-igw}]'

aws ec2 attach-internet-gateway \
  --internet-gateway-id igw-xxxxx \
  --vpc-id vpc-xxxxx
```

#### 1.2 Create RDS PostgreSQL Database

```bash
# Create DB subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name awscost-db-subnet-group \
  --db-subnet-group-description "Subnet group for AWS Cost Dashboard" \
  --subnet-ids subnet-private-1a subnet-private-1b

# Create RDS PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier awscost-db-prod \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.4 \
  --master-username dbadmin \
  --master-user-password 'YOUR_STRONG_PASSWORD' \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --db-subnet-group-name awscost-db-subnet-group \
  --vpc-security-group-ids sg-xxxxx \
  --backup-retention-period 7 \
  --multi-az \
  --auto-minor-version-upgrade \
  --publicly-accessible false \
  --tags Key=Name,Value=awscost-db-prod
```

#### 1.3 Create ElastiCache Redis Cluster

```bash
# Create cache subnet group
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name awscost-redis-subnet-group \
  --cache-subnet-group-description "Subnet group for Redis" \
  --subnet-ids subnet-private-1a subnet-private-1b

# Create Redis cluster
aws elasticache create-replication-group \
  --replication-group-id awscost-redis-prod \
  --replication-group-description "Redis for AWS Cost Dashboard" \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.t3.medium \
  --num-cache-clusters 2 \
  --cache-subnet-group-name awscost-redis-subnet-group \
  --security-group-ids sg-xxxxx \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --automatic-failover-enabled \
  --multi-az-enabled
```

### Step 2: Build and Push Docker Images

#### 2.1 Build production images

```bash
# Build backend image
docker build -f backend/Dockerfile.prod -t awscost-backend:latest backend/

# Build frontend image
docker build -f frontend/Dockerfile.prod -t awscost-frontend:latest frontend/
```

#### 2.2 Push to Container Registry

**Option A: Amazon ECR**

```bash
# Create ECR repositories
aws ecr create-repository --repository-name awscost-backend
aws ecr create-repository --repository-name awscost-frontend

# Get login credentials
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push backend
docker tag awscost-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/awscost-backend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/awscost-backend:latest

# Tag and push frontend
docker tag awscost-frontend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/awscost-frontend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/awscost-frontend:latest
```

**Option B: GitHub Container Registry** (configured in CI/CD)

### Step 3: Create ECS Cluster and Task Definitions

#### 3.1 Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name awscost-production-cluster \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy \
    capacityProvider=FARGATE,weight=1 \
    capacityProvider=FARGATE_SPOT,weight=4 \
  --tags key=Environment,value=production
```

#### 3.2 Store secrets in AWS Secrets Manager

```bash
# Create secret for database credentials
aws secretsmanager create-secret \
  --name awscost/prod/database \
  --secret-string '{
    "username":"dbadmin",
    "password":"YOUR_DB_PASSWORD",
    "host":"awscost-db-prod.xxxxx.us-east-1.rds.amazonaws.com",
    "port":"5432",
    "dbname":"aws_cost_dashboard"
  }'

# Create secret for application keys
aws secretsmanager create-secret \
  --name awscost/prod/app-keys \
  --secret-string '{
    "SECRET_KEY":"GENERATE_RANDOM_64_CHAR_STRING",
    "JWT_SECRET_KEY":"GENERATE_RANDOM_64_CHAR_STRING",
    "ENCRYPTION_KEY":"GENERATE_FERNET_KEY"
  }'
```

#### 3.3 Create Task Definition

Create `task-definition-production.json`:

```json
{
  "family": "awscost-production",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/awscostAppRole",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/awscost-backend:latest",
      "cpu": 512,
      "memory": 1024,
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "DEBUG", "value": "false"},
        {"name": "LOG_LEVEL", "value": "WARNING"},
        {"name": "REDIS_HOST", "value": "awscost-redis-prod.xxxxx.cache.amazonaws.com"},
        {"name": "REDIS_PORT", "value": "6379"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:awscost/prod/database:DATABASE_URL::"},
        {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:awscost/prod/app-keys:SECRET_KEY::"},
        {"name": "JWT_SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:awscost/prod/app-keys:JWT_SECRET_KEY::"},
        {"name": "ENCRYPTION_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:awscost/prod/app-keys:ENCRYPTION_KEY::"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/awscost-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    },
    {
      "name": "frontend",
      "image": "ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/awscost-frontend:latest",
      "cpu": 512,
      "memory": 1024,
      "essential": true,
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/awscost-frontend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:80/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 10
      }
    }
  ]
}
```

Register the task definition:

```bash
aws ecs register-task-definition --cli-input-json file://task-definition-production.json
```

### Step 4: Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name awscost-prod-alb \
  --subnets subnet-public-1a subnet-public-1b \
  --security-groups sg-xxxxx \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4

# Create target groups
aws elbv2 create-target-group \
  --name awscost-backend-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxxxx \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30

aws elbv2 create-target-group \
  --name awscost-frontend-tg \
  --protocol HTTP \
  --port 80 \
  --vpc-id vpc-xxxxx \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30

# Create HTTPS listener (requires ACM certificate)
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:... \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:.../awscost-frontend-tg

# Create listener rule for API path
aws elbv2 create-rule \
  --listener-arn arn:aws:elasticloadbalancing:... \
  --priority 10 \
  --conditions Field=path-pattern,Values='/api/*' \
  --actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:.../awscost-backend-tg
```

### Step 5: Create ECS Service

```bash
aws ecs create-service \
  --cluster awscost-production-cluster \
  --service-name awscost-production-service \
  --task-definition awscost-production \
  --desired-count 2 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={
      subnets=[subnet-private-1a,subnet-private-1b],
      securityGroups=[sg-xxxxx],
      assignPublicIp=DISABLED
    }" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:.../awscost-backend-tg,containerName=backend,containerPort=8000" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:.../awscost-frontend-tg,containerName=frontend,containerPort=80" \
  --health-check-grace-period-seconds 60 \
  --deployment-configuration "maximumPercent=200,minimumHealthyPercent=100,deploymentCircuitBreaker={enable=true,rollback=true}" \
  --enable-execute-command
```

### Step 6: Configure Auto-Scaling

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/awscost-production-cluster/awscost-production-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# Create scaling policy based on CPU utilization
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/awscost-production-cluster/awscost-production-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-target-tracking \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
      "TargetValue": 70.0,
      "PredefinedMetricSpecification": {
        "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
      },
      "ScaleInCooldown": 300,
      "ScaleOutCooldown": 60
    }'
```

### Step 7: Configure DNS (Route 53)

```bash
# Create A record pointing to ALB
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "cost-dashboard.your-domain.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "awscost-prod-alb-123456789.us-east-1.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

---

## Docker Compose Deployment

For simpler deployments on a single EC2 instance:

### Step 1: Launch EC2 Instance

```bash
# Launch Ubuntu 22.04 instance
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.large \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxx \
  --subnet-id subnet-xxxxx \
  --user-data file://user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=awscost-prod}]'
```

### Step 2: Install Docker and Docker Compose

SSH into the instance and run:

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add current user to docker group
sudo usermod -aG docker $USER
```

### Step 3: Deploy Application

```bash
# Clone repository
git clone https://github.com/your-org/aws-cost-dashboard.git
cd aws-cost-dashboard

# Create production environment file
cp backend/.env.example backend/.env
# Edit backend/.env with production values

# Start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Step 4: Configure Nginx as Reverse Proxy

Install Nginx on the host for SSL termination:

```bash
sudo apt-get install nginx certbot python3-certbot-nginx

# Generate SSL certificate
sudo certbot --nginx -d your-domain.com
```

Nginx configuration (`/etc/nginx/sites-available/awscost`):

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Environment Configuration

### Backend Environment Variables

Key configuration variables for production:

```bash
# Application
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=WARNING

# Security (CRITICAL: Use strong random keys)
SECRET_KEY=<64-character-random-string>
JWT_SECRET_KEY=<64-character-random-string>
ENCRYPTION_KEY=<fernet-key>

# Database
DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/dbname

# Redis
REDIS_HOST=elasticache-endpoint
REDIS_PORT=6379
REDIS_PASSWORD=<redis-password>
REDIS_SSL=True

# CORS
CORS_ORIGINS=https://your-domain.com

# AWS
AWS_REGION=us-east-1
# Use IAM roles in production (no credentials in env vars)
```

### Generating Secure Keys

```bash
# Generate SECRET_KEY and JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## SSL/TLS Configuration

### Option 1: AWS Certificate Manager (ACM)

1. Request certificate in ACM
2. Validate domain ownership
3. Attach certificate to ALB listener

```bash
aws acm request-certificate \
  --domain-name your-domain.com \
  --validation-method DNS \
  --subject-alternative-names *.your-domain.com
```

### Option 2: Let's Encrypt (for EC2 deployments)

```bash
sudo certbot --nginx -d your-domain.com
```

---

## Monitoring and Logging

### CloudWatch Logs

Configure log retention:

```bash
aws logs create-log-group --log-group-name /ecs/awscost-backend
aws logs put-retention-policy --log-group-name /ecs/awscost-backend --retention-in-days 30
```

### CloudWatch Alarms

```bash
# High CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name awscost-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:alerts
```

### Application Performance Monitoring

Consider integrating:
- **Datadog** - Comprehensive monitoring
- **New Relic** - APM and infrastructure monitoring
- **Sentry** - Error tracking
- **CloudWatch Insights** - Log analysis

---

## Backup and Recovery

### Database Backups

RDS automated backups are enabled by default. Configure:

```bash
aws rds modify-db-instance \
  --db-instance-identifier awscost-db-prod \
  --backup-retention-period 30 \
  --preferred-backup-window "03:00-04:00"
```

### Manual Snapshots

```bash
aws rds create-db-snapshot \
  --db-instance-identifier awscost-db-prod \
  --db-snapshot-identifier awscost-db-manual-$(date +%Y%m%d)
```

### Disaster Recovery

1. **Regular backups**: Automated daily snapshots
2. **Multi-AZ deployment**: Automatic failover
3. **Cross-region replication**: For critical deployments
4. **Recovery Time Objective (RTO)**: < 1 hour
5. **Recovery Point Objective (RPO)**: < 5 minutes

---

## Troubleshooting

### Common Issues

#### 1. Application not starting

**Symptoms:** ECS tasks fail to start or continuously restart

**Solutions:**
- Check CloudWatch logs for errors
- Verify environment variables and secrets
- Check security group rules (allow traffic from ALB)
- Validate IAM task role permissions

```bash
# View task logs
aws ecs describe-tasks \
  --cluster awscost-production-cluster \
  --tasks <task-id>

# Check CloudWatch logs
aws logs tail /ecs/awscost-backend --follow
```

#### 2. Database connection errors

**Symptoms:** "Unable to connect to database" errors

**Solutions:**
- Verify RDS security group allows traffic from ECS tasks
- Check DATABASE_URL is correct
- Verify RDS instance is available
- Test connection from ECS task:

```bash
# Execute command in running task
aws ecs execute-command \
  --cluster awscost-production-cluster \
  --task <task-id> \
  --container backend \
  --interactive \
  --command "/bin/bash"

# Inside container
psql $DATABASE_URL
```

#### 3. High latency / slow responses

**Solutions:**
- Check Redis cache hit rate
- Review CloudWatch metrics for CPU/memory
- Enable connection pooling
- Optimize database queries
- Scale up ECS tasks

#### 4. CORS errors

**Symptoms:** Frontend cannot access API

**Solutions:**
- Verify CORS_ORIGINS environment variable
- Check ALB security group
- Verify frontend is using correct API URL

#### 5. SSL certificate errors

**Solutions:**
- Verify ACM certificate is validated
- Check ALB listener is using correct certificate
- Ensure Route 53 points to ALB

### Health Check Commands

```bash
# Backend health check
curl https://your-domain.com/api/v1/health

# Check task status
aws ecs describe-services \
  --cluster awscost-production-cluster \
  --services awscost-production-service

# View recent deployments
aws ecs list-task-definitions --family-prefix awscost-production
```

### Rollback Deployment

```bash
# Revert to previous task definition
aws ecs update-service \
  --cluster awscost-production-cluster \
  --service awscost-production-service \
  --task-definition awscost-production:PREVIOUS_VERSION
```

---

## Next Steps

After successful deployment:

1. **Configure monitoring and alerting**
2. **Set up automated backups**
3. **Configure log aggregation**
4. **Implement CI/CD pipeline** (see [CI/CD documentation](.github/workflows/README.md))
5. **Configure AWS accounts and budgets**
6. **Set up Microsoft Teams webhooks for alerts**
7. **Review security best practices**

---

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/your-org/aws-cost-dashboard/issues
- **Documentation**: https://github.com/your-org/aws-cost-dashboard/wiki

---

## License

[Your License Here]
