# AWS Cost Dashboard — Infrastructure

Terraform configuration for the AWS infrastructure layer of the AWS Cost Dashboard.

## Architecture

The frontend is a static React app hosted on **GitHub Pages** (free, no infrastructure needed).
The backend (FastAPI) runs on **EKS** (Kubernetes), with Terraform managing the persistent data layer.

```
┌──────────────────────────────────────────────────────────────────┐
│  GitHub Pages  (React SPA — static, free)                        │
│  https://nkrameshkrishnan.github.io/aws-cost-dashboard/          │
└────────────────────────┬─────────────────────────────────────────┘
                         │  HTTPS API calls
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  nginx Ingress  (NLB + sslip.io TLS)                             │
│  CORS allows GitHub Pages + localhost                            │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  EKS — Backend Deployment  (FastAPI, HPA 2-10 pods)              │
│  Private subnets, IRSA for AWS API access                        │
└───────┬────────────────┬───────────────────────────┬─────────────┘
        │                │                           │
        ▼                ▼                           ▼
  RDS PostgreSQL   ElastiCache Redis         AWS APIs (IRSA)
  (Multi-AZ)       (Multi-AZ)           Cost Explorer, Budgets,
                                         EC2, RDS, Lambda, S3
```

**Division of responsibility:**

| Layer | Tool | What it manages |
|-------|------|----------------|
| Persistent infrastructure | **Terraform** | VPC · RDS · ElastiCache · ECR · Secrets Manager · CloudWatch |
| Kubernetes cluster | **eksctl** (`scripts/eks-cluster.yaml`) | EKS cluster · node groups · OIDC / IRSA |
| Application | **kubectl** (`kubernetes/` manifests) | Pods · Services · Ingress · HPA |

---

## Modules

| Module | Resources |
|--------|-----------|
| `networking` | VPC, public/private subnets, IGW, NAT Gateways, route tables |
| `security` | Security groups for RDS and Redis (allow from VPC CIDR) |
| `ecr` | ECR repository with scan-on-push and lifecycle policy |
| `database` | RDS PostgreSQL (Multi-AZ in production) |
| `cache` | ElastiCache Redis cluster |
| `secrets` | AWS Secrets Manager — DB credentials + app secrets |
| `monitoring` | CloudWatch log group `/eks/awscost-production-backend` |

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
aws_region = "us-east-1"

db_username = "dbadmin"
db_password = "..."        # openssl rand -base64 24

secret_key     = "..."     # openssl rand -hex 32
jwt_secret_key = "..."     # openssl rand -hex 32
encryption_key = "..."     # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Apply

```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Deployment takes approximately 10-15 minutes (RDS + ElastiCache spin-up dominates).

### 3. Note the outputs

```bash
terraform output ecr_repository_url   # → set as ECR_REPOSITORY in GitHub Actions
terraform output rds_address           # → update kubernetes/base/configmap.yaml
terraform output redis_endpoint        # → update kubernetes/base/configmap.yaml
```

### 4. Deploy the application

After Terraform, create the EKS cluster and deploy the backend:

```bash
./scripts/eks-deploy.sh
```

That script reads the ECR URL from the environment and handles cluster creation,
image build/push, TLS ingress setup, and rollout.

---

## Estimated Monthly Cost

### Production (Multi-AZ, 2 nodes)

| Resource | Spec | Est. cost |
|----------|------|-----------|
| EKS cluster control plane | | ~$73 |
| EC2 nodes (t3.medium × 2) | on-demand | ~$60 |
| RDS PostgreSQL | db.t3.medium, Multi-AZ, 100 GB | ~$130 |
| ElastiCache Redis | cache.t3.medium, 2 nodes | ~$100 |
| NAT Gateway | 2 (Multi-AZ HA) | ~$65 |
| ECR | storage + transfer | ~$2 |
| CloudWatch Logs | | ~$5 |
| **Total** | | **~$435/month** |

### Development (single-AZ, 1 small node)

```hcl
environment           = "dev"
db_instance_class     = "db.t3.small"
db_allocated_storage  = 20
redis_node_type       = "cache.t3.micro"
redis_num_cache_nodes = 1
```

Estimated dev cost: ~$140/month.

> **Tip:** Stop the EKS node group overnight to cut EC2 costs:
> `aws eks update-nodegroup-config --cluster-name aws-cost-dashboard --nodegroup-name backend-ng --scaling-config desiredSize=0`

---

## CORS

CORS is configured in two places:

1. **Backend application** — `CORS_ORIGINS` in `.env.production`:
   ```
   CORS_ORIGINS=https://nkrameshkrishnan.github.io,http://localhost:5173,http://localhost:3000
   ```

2. **nginx Ingress** — `nginx.ingress.kubernetes.io/cors-allow-origin` in `kubernetes/ingress/ingress.yaml`:
   ```yaml
   nginx.ingress.kubernetes.io/cors-allow-origin: "https://nkrameshkrishnan.github.io"
   ```

Both are already set for the production GitHub Pages URL.
The CORS origin is the scheme + host only — **no trailing slash, no path**.

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
# Get all outputs
terraform output

# Tail backend logs
aws logs tail /eks/awscost-production-backend --follow

# Check running pods
kubectl get pods -n aws-cost-dashboard

# Force a new rollout (picks up a new image)
kubectl rollout restart deployment/backend -n aws-cost-dashboard

# Scale nodes to zero (save cost overnight)
aws eks update-nodegroup-config \
  --cluster-name aws-cost-dashboard \
  --nodegroup-name backend-ng \
  --scaling-config desiredSize=0,minSize=0,maxSize=4

# Scale nodes back up
aws eks update-nodegroup-config \
  --cluster-name aws-cost-dashboard \
  --nodegroup-name backend-ng \
  --scaling-config desiredSize=2,minSize=1,maxSize=4

# Destroy all Terraform resources (irreversible)
terraform destroy
```

---

## Troubleshooting

**Pods not starting** — Check logs: `kubectl logs -n aws-cost-dashboard deploy/backend`
Verify the `backend-secret` exists and has correct `DATABASE_URL` and `ENCRYPTION_KEY`.

**CORS errors in browser** — The origin `https://nkrameshkrishnan.github.io` is already
configured. If you see CORS errors, confirm the ingress annotation and `CORS_ORIGINS` env
var match — no trailing slash, no path suffix.

**`terraform apply` fails on RDS** — `db_password` must be ≥ 8 chars and must not contain
`@`, `/`, or `"`.

**Frontend gets 502** — Run `kubectl describe pod -n aws-cost-dashboard -l app.kubernetes.io/component=backend`
to check startup failures. Usually a bad `DATABASE_URL` or unreachable Redis.

**ECR push denied** — IAM user needs `ecr:GetAuthorizationToken`,
`ecr:BatchCheckLayerAvailability`, `ecr:PutImage`, `ecr:InitiateLayerUpload`,
`ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`.
