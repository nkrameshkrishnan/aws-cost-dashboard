# AWS Cost Dashboard — Infrastructure

Terraform configuration for deploying the AWS Cost Dashboard backend to AWS.

## Architecture

The frontend is a static React app hosted on **GitHub Pages** (free). Only the backend (FastAPI) runs on AWS infrastructure.

```
┌──────────────────────────────────────────────────────────────────┐
│  GitHub Pages  (React SPA — static, free)                        │
│  https://your-username.github.io/aws-cost-dashboard              │
└────────────────────────┬─────────────────────────────────────────┘
                         │  HTTPS API calls
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  API Gateway HTTP API  (public HTTPS endpoint)                   │
│  CORS allows GitHub Pages + localhost                            │
└────────────────────────┬─────────────────────────────────────────┘
                         │  VPC Link (private)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  Internal ALB  (private subnets only)                            │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  ECS Fargate — Backend  (FastAPI, port 8000)                     │
│  Auto-scaling 2-10 tasks · Fargate + Fargate Spot                │
│  Private subnets, no public IP                                   │
└───────┬────────────────┬───────────────────────────┬─────────────┘
        │                │                           │
        ▼                ▼                           ▼
  RDS PostgreSQL   ElastiCache Redis         AWS APIs
  (Multi-AZ)       (Multi-AZ)           Cost Explorer, Budgets,
                                         EC2, RDS, Lambda, S3
```

Network layout:

```
VPC (10.0.0.0/16)
├── Public subnets  (10.0.0.0/24, 10.0.1.0/24) — NAT Gateways
└── Private subnets (10.0.10.0/24, 10.0.11.0/24) — ECS, RDS, Redis, ALB
```

---

## Modules

| Module | Resources |
|--------|-----------|
| `networking` | VPC, public/private subnets, IGW, NAT Gateways, route tables |
| `security` | Security groups for ALB, ECS tasks, RDS, Redis, VPC Link |
| `database` | RDS PostgreSQL (Multi-AZ in production) |
| `cache` | ElastiCache Redis cluster |
| `secrets` | AWS Secrets Manager — DB credentials + app secrets |
| `monitoring` | CloudWatch log group, ECS task execution + task IAM roles |
| `alb` | Internal ALB + backend target group + listeners |
| `ecs` | ECS cluster, backend task definition + service, auto-scaling |
| `vpc-link` | VPC Link connecting API Gateway to the private ALB |
| `api-gateway` | API Gateway HTTP API — public entry point, CORS, CloudWatch logs |

---

## Quick Start

### 1. Configure variables

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars
```

Key values to fill in:

```hcl
backend_image = "ghcr.io/your-org/aws-cost-dashboard-backend:1.0.0"

db_username = "dbadmin"
db_password = "..."        # openssl rand -base64 24

secret_key     = "..."     # openssl rand -hex 32
jwt_secret_key = "..."     # openssl rand -hex 32
encryption_key = "..."     # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

cors_allowed_origins = [
  "https://YOUR-GITHUB-USERNAME.github.io",
  "http://localhost:5173",
]
```

### 2. Deploy

```bash
terraform init
terraform plan
terraform apply
```

Deployment takes approximately 15-20 minutes.

### 3. Wire up the frontend

After apply, retrieve the API URL:

```bash
terraform output api_gateway_url
```

Set this value as `VITE_API_BASE_URL` in root `.env.production`, then rebuild the frontend and push to GitHub Pages.

---

## Estimated Monthly Cost

| Resource | Spec | Est. cost |
|----------|------|-----------|
| API Gateway | HTTP API | ~$1 |
| ECS Fargate | 2 tasks, 1 vCPU / 2 GB (Spot mix) | ~$40-60 |
| RDS PostgreSQL | db.t3.medium, Multi-AZ, 100 GB | ~$130 |
| ElastiCache Redis | cache.t3.medium, 2 nodes | ~$100 |
| Internal ALB | | ~$20 |
| NAT Gateway | 2 (Multi-AZ) | ~$65 |
| CloudWatch Logs | | ~$5 |
| **Total** | | **~$360-380/month** |

Development environment (smaller instances, single-AZ, 1 task): ~$100/month

```hcl
environment           = "dev"
db_instance_class     = "db.t3.small"
db_allocated_storage  = 20
redis_node_type       = "cache.t3.micro"
redis_num_cache_nodes = 1
ecs_desired_count     = 1
ecs_min_capacity      = 1
```

---

## CORS Configuration

`cors_allowed_origins` must include your GitHub Pages URL before deploying. Both the API Gateway and the backend read this list.

```hcl
cors_allowed_origins = [
  "https://your-username.github.io",       # GitHub Pages (primary)
  "https://dashboard.your-domain.com",     # custom domain (if any)
  "http://localhost:5173",                 # local dev
]
```

After changing origins, run `terraform apply` then rebuild/redeploy the frontend.

---

## Remote State (recommended for production)

Uncomment the `backend "s3"` block in `main.tf` and create the prerequisites:

```bash
aws s3 mb s3://your-terraform-state-bucket --region us-east-1
aws s3api put-bucket-versioning \
  --bucket your-terraform-state-bucket \
  --versioning-configuration Status=Enabled

aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

---

## Useful Commands

```bash
# Get all outputs (includes api_gateway_url)
terraform output

# Tail backend logs
aws logs tail /ecs/awscost-production-backend --follow

# Force a new ECS deployment (picks up a new image tag)
aws ecs update-service \
  --cluster $(terraform output -raw ecs_cluster_name) \
  --service $(terraform output -raw backend_service_name) \
  --force-new-deployment

# Destroy (irreversible — requires manual RDS deletion protection removal first)
terraform destroy
```

---

## Troubleshooting

**ECS tasks not starting** — Check CloudWatch Logs (`/ecs/awscost-production-backend`). Verify Secrets Manager has the correct keys and the ECS task execution role has `secretsmanager:GetSecretValue` permission.

**CORS errors in browser** — Confirm the exact GitHub Pages origin (no trailing slash) is in `cors_allowed_origins`. Run `terraform apply` to push the change.

**`terraform apply` fails on RDS** — `db_password` must be at least 8 characters and avoid special characters (`@`, `/`, `"`).

**Frontend gets 502** — The `/health` endpoint on the backend is failing. Check ECS task logs and confirm `DATABASE_URL` and `REDIS_HOST` resolve correctly inside the VPC.
