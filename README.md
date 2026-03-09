# AWS Cost Dashboard

A production-ready web application for monitoring, analyzing, and optimizing AWS spending across multiple accounts. Features cost visualization, budget tracking, FinOps audits, right-sizing recommendations, forecasting, and automated reporting.

## Features

- **Multi-Account Monitoring** — Track costs across multiple AWS accounts using named profiles
- **Cost Visualization** — Interactive charts for daily/monthly trends, service breakdowns, and MoM comparisons
- **Budget Tracking** — Compare actual vs budget with forecast projections and threshold alerts
- **FinOps Audits** — Detect idle instances, untagged resources, unused volumes, and unattached EIPs
- **Right-Sizing Recommendations** — Instance optimization suggestions based on CloudWatch utilization
- **Cost Forecasting** — Predictions via AWS Cost Explorer with anomaly detection
- **Export & Reporting** — PDF, CSV, JSON, and Excel reports with optional S3 upload
- **Microsoft Teams Integration** — Send cost alerts and report summaries to Teams channels
- **Redis Caching** — Minimizes AWS API calls and associated costs

## Tech Stack

**Backend** — FastAPI · PostgreSQL · Redis · SQLAlchemy · APScheduler · ReportLab · boto3

**Frontend** — React 18 + TypeScript · Vite · TanStack Query · Recharts · Tailwind CSS · Zustand

**Infrastructure** — Docker · Terraform (AWS ECS/Fargate)

---

## Prerequisites

- Docker & Docker Compose
- AWS CLI configured with profiles in `~/.aws/credentials`
- IAM permissions for Cost Explorer, Budgets, EC2, RDS, Lambda, S3 (see [IAM Permissions](#iam-permissions))

For local development without Docker: Python 3.11+, Node.js 20+, PostgreSQL 15+, Redis 7+

---

## Quick Start (Development)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/aws-cost-dashboard.git
cd aws-cost-dashboard

# 2. Create your local environment file
cp .env.example .env
# Edit .env — the defaults work for local dev, just add your AWS profile names

# 3. Start the full stack
docker-compose up --build
```

This starts PostgreSQL (5432), Redis (6379), the backend API (8000), and the frontend dev server (5173).

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API docs (Swagger)**: http://localhost:8000/docs

---

## Configuration

All configuration is driven by environment variables. There are two primary env files at the project root:

| File | Purpose |
|------|---------|
| `.env.example` | Template with every variable and safe dev defaults — copy to `.env` for local dev |
| `.env.production` | **Single source of truth for production** — edit this before deploying |

Nothing else needs to be modified before deploying to production. Both Docker Compose files and the build script read directly from these files.

### Setting up production config

```bash
cp .env.example .env.production
# Then edit .env.production — fill in all CHANGE_ME_... placeholders
```

Key values to set before a production deploy:

```env
DOCKER_REGISTRY=your-registry.example.com
VERSION=1.0.0
VITE_API_BASE_URL=https://api.your-domain.com

SECRET_KEY=<openssl rand -hex 32>
JWT_SECRET_KEY=<openssl rand -hex 32>
ENCRYPTION_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

DATABASE_URL=postgresql://user:password@your-db-host:5432/aws_cost_dashboard
REDIS_HOST=your-redis-host

CORS_ORIGINS=https://your-domain.com
EXPORT_S3_BUCKET=your-reports-bucket
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
```

### Adding a new config variable

1. Add it to `.env.example` with a comment.
2. Add it to `.env.production` with the production value.
3. Add the field to `backend/app/config.py` (`Settings` class) with a safe default.
4. If it's a frontend Vite variable (`VITE_` prefix), also add `ARG`/`ENV` to `frontend/Dockerfile.prod`.

---

## Running Tests

Tests live in a standalone project at `tests/` — completely separate from application code.

```bash
# Install test dependencies (one-time)
cd tests
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt

# Run all tests
python -m pytest

# Run by category
python -m pytest -m unit          # fast unit tests only
python -m pytest -m integration   # requires Postgres + Redis
python -m pytest -m "not slow and not aws"  # skip slow and AWS-live tests

# Run a single file
python -m pytest test_api/test_health.py
```

Or run the full isolated test stack via Docker (no local deps needed):

```bash
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

---

## Production Deployment

### Build Docker images

```bash
# Builds backend + frontend images from .env.production
./scripts/build-prod.sh

# Build and push to registry
./scripts/build-prod.sh --push
```

### Deploy with Docker Compose

```bash
docker-compose -f docker-compose.prod.yml --env-file .env.production up -d
```

### Run database migrations

```bash
cd backend
DATABASE_URL=<your-production-url> alembic upgrade head
```

### Deploy to AWS ECS/Fargate

Terraform configuration is in `infrastructure/terraform/`. It provisions ECS clusters, RDS, ElastiCache, ALB, and supporting IAM roles.

```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file="production.tfvars"
terraform apply
```

---

## Project Structure

```
aws-cost-dashboard/
├── .env.example             ← Template for all environment variables
├── .env.production          ← Production config (single source of truth)
├── docker-compose.yml       ← Dev stack (hot-reload)
├── docker-compose.prod.yml  ← Production stack
├── docker-compose.test.yml  ← Ephemeral CI test stack
│
├── backend/                 ← FastAPI application
│   └── app/
│       ├── api/v1/          ← Route handlers (costs, budgets, finops, export, …)
│       ├── services/        ← Business logic and AWS SDK calls
│       ├── models/          ← SQLAlchemy ORM models
│       ├── schemas/         ← Pydantic request/response schemas
│       └── config.py        ← Settings (all values from env vars)
│
├── frontend/                ← React + Vite application
│   └── src/
│       ├── components/      ← Reusable UI components
│       ├── pages/           ← Page-level views
│       ├── api/             ← Axios client and endpoint functions
│       └── hooks/           ← Custom React hooks
│
├── tests/                   ← Standalone test project
│   ├── pytest.ini           ← Config (pythonpath → ../backend)
│   ├── conftest.py          ← Shared fixtures
│   ├── requirements-test.txt
│   ├── test_api/
│   ├── test_aws/
│   ├── test_core/
│   ├── test_schemas/
│   └── test_services/
│
├── infrastructure/
│   └── terraform/           ← AWS ECS/Fargate infrastructure as code
│
└── scripts/
    ├── build-prod.sh        ← Builds both Docker images from .env.production
    └── setup-testing.sh     ← One-time test environment setup
```

---

## IAM Permissions

The IAM policy in `iam-policy.json` grants read-only access for cost analysis and auditing. No resources can be modified.

```bash
# Create the policy via AWS CLI
aws iam create-policy \
  --policy-name AWSCostDashboardPolicy \
  --policy-document file://iam-policy.json
```

Or manually via the console: **IAM → Policies → Create Policy → JSON** — paste the contents of `iam-policy.json`, replace `your-reports-bucket` with your S3 bucket name (or remove the S3 write statement if not using report uploads), then attach to your IAM user or role.

| Feature | Key Permissions Required |
|---------|--------------------------|
| Cost Dashboard | `ce:GetCostAndUsage`, `ce:GetCostForecast`, `ce:GetDimensionValues` |
| Budget Tracking | `budgets:ViewBudget`, `budgets:DescribeBudgets` |
| EC2 Audit | `ec2:Describe*`, `cloudwatch:GetMetricStatistics` |
| RDS Audit | `rds:DescribeDBInstances`, `rds:DescribeDBSnapshots` |
| Lambda Audit | `lambda:ListFunctions`, `lambda:ListTags` |
| S3 Audit | `s3:ListAllMyBuckets`, `s3:GetBucketLifecycleConfiguration` |
| Load Balancer Audit | `elasticloadbalancing:Describe*` |
| ElastiCache Audit | `elasticache:DescribeReplicationGroups` |
| Savings Plans | `ce:GetSavingsPlansCoverage`, `ce:GetReservationCoverage` |
| Report Upload (optional) | `s3:PutObject` on your reports bucket |

---

## Caching Strategy

Redis caches AWS Cost Explorer responses to reduce API costs and latency.

| Data Type | Default TTL | Notes |
|-----------|-------------|-------|
| Current month costs | 5 min | Updates throughout the day |
| Historical costs | 24 hr | Immutable once finalized |
| Cost forecasts | 1 hr | Relatively stable |
| Service breakdowns | 15 min | Balance of freshness vs cost |
| Budget status | 10 min | Needs to be reasonably current |
| Audit results | 30 min | Resources change slowly |

TTLs are configurable via env vars (`CACHE_TTL_CURRENT_MONTH`, `CACHE_TTL_HISTORICAL`, etc.).

---

## Troubleshooting

**Backend won't start**
- Check Postgres and Redis are up: `docker-compose ps`
- Verify env file is present: `ls .env` (for dev) or `ls .env.production` (for prod)
- Check logs: `docker-compose logs backend`

**AWS API errors**
- Verify IAM permissions: `aws iam simulate-principal-policy ...`
- Confirm Cost Explorer is enabled in your account (it must be activated once)
- Check credentials: `aws sts get-caller-identity --profile your-profile`

**Frontend shows wrong API URL**
- For Docker dev: the frontend proxies to `http://localhost:8000` by default
- For production builds: `VITE_API_BASE_URL` must be set in `.env.production` before running `build-prod.sh` — it is baked into the JS bundle at build time

**Tests failing to import `app.*`**
- Ensure you're running `python -m pytest` from the `tests/` directory, not from the repo root
- The `pythonpath = ../backend` in `tests/pytest.ini` resolves imports correctly

---

## License

MIT
