# Terraform Modules

| Module | Purpose |
|--------|---------|
| `networking` | VPC, subnets (public + private), IGW, NAT Gateways, route tables |
| `security` | Security groups for RDS, Redis, and EKS node communication |
| `ecr` | ECR repository for backend Docker images (with lifecycle policy) |
| `database` | RDS PostgreSQL — Multi-AZ in production, single-AZ in dev |
| `cache` | ElastiCache Redis cluster |
| `secrets` | AWS Secrets Manager secrets for DB credentials and app keys |
| `monitoring` | CloudWatch log group for the backend (`/eks/<prefix>-backend`) |

The EKS cluster itself is created by **eksctl** (`scripts/eks-cluster.yaml`), not Terraform.
The frontend is served from **GitHub Pages** and is not part of this infrastructure.
