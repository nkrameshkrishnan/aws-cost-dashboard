# Terraform Modules

| Module | Purpose |
|--------|---------|
| `networking` | VPC, subnets (public + private), IGW, NAT Gateways, route tables |
| `security` | Security groups for ALB, ECS tasks, RDS, Redis, and VPC Link |
| `database` | RDS PostgreSQL — Multi-AZ in production, single-AZ in dev |
| `cache` | ElastiCache Redis cluster |
| `secrets` | AWS Secrets Manager secrets for DB credentials and app keys |
| `monitoring` | CloudWatch log group for the backend, ECS task execution role, ECS task role |
| `alb` | Internal Application Load Balancer — backend target group and listeners |
| `ecs` | ECS Fargate cluster + backend service + auto-scaling (backend only) |
| `vpc-link` | API Gateway VPC Link to the private ALB |
| `api-gateway` | API Gateway HTTP API — public HTTPS endpoint with CORS for GitHub Pages |

The frontend is served from **GitHub Pages** and is not part of this infrastructure.
