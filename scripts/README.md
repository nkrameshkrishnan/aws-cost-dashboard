# AWS Cost Dashboard — Scripts

Utility scripts for building, deploying, and operating the AWS Cost Dashboard.

## Architecture context

```
Frontend  →  GitHub Pages   (static React bundle — deploy with deploy-pages.sh)
Backend   →  ECS Fargate    (FastAPI — deploy with deploy.sh via Terraform)
Entry     →  API Gateway    (public HTTPS endpoint, set as VITE_API_BASE_URL)
```

---

## Scripts overview

| Script | Purpose |
|--------|---------|
| `build-prod.sh` | Build backend + frontend Docker images |
| `deploy.sh` | Deploy backend infrastructure (Terraform + ECS) |
| `deploy-pages.sh` | Build frontend and push to GitHub Pages |
| `db-migrate.sh` | Run Alembic database migrations |
| `backup-db.sh` | Backup / restore RDS PostgreSQL |
| `manage-secrets.sh` | Generate and manage AWS Secrets Manager keys |
| `health-check.sh` | Check health of all components |
| `setup-testing.sh` | Set up the local test environment |

---

## build-prod.sh — Build Docker images

Reads all config from `.env.production`.

```bash
# Build only (backend + frontend images)
./scripts/build-prod.sh

# Build and push to registry
./scripts/build-prod.sh --push
```

After `--push`, update `terraform.tfvars`:
```hcl
backend_image = "your-registry/aws-cost-dashboard-backend:VERSION"
```

> The frontend Docker image is built for reference. The primary production
> deployment of the frontend is via GitHub Pages (`deploy-pages.sh`).

---

## deploy.sh — Backend infrastructure deployment

Deploys Terraform infrastructure (VPC, RDS, Redis, ECS, API Gateway).
Optionally builds and pushes the backend Docker image first.

```bash
# Usage
./scripts/deploy.sh [environment] [action]

# Plan changes
./scripts/deploy.sh production plan

# Apply (builds + pushes backend image, then runs Terraform)
./scripts/deploy.sh production apply

# Destroy (with confirmation)
./scripts/deploy.sh staging destroy
```

Valid environments: `dev`, `staging`, `production`

**Requirements:** `terraform`, `aws`, `docker`, `jq`, `.env.production`

After `apply`, the script prints the `api_gateway_url`. Set that as
`VITE_API_BASE_URL` in `.env.production`, then deploy the frontend:

```bash
./scripts/deploy-pages.sh
```

---

## deploy-pages.sh — GitHub Pages deployment

Builds the React app (baking `VITE_*` vars from `.env.production` into the
bundle) and pushes `dist/` to the `gh-pages` branch.

```bash
# Build and deploy
./scripts/deploy-pages.sh

# Dry run (build only, no git push)
./scripts/deploy-pages.sh --dry-run
```

**First-time setup:**
1. Run `./scripts/deploy-pages.sh` — this creates the `gh-pages` branch.
2. In GitHub: **Settings → Pages → Branch: `gh-pages` / `(root)`**.
3. Note your Pages URL (e.g. `https://your-username.github.io/aws-cost-dashboard`).
4. Add it to `cors_allowed_origins` in `terraform.tfvars`, then re-run `deploy.sh`.

**Requirements:** `node`, `npm`, `git`, `VITE_API_BASE_URL` in `.env.production`

---

## db-migrate.sh — Database migrations

Runs Alembic migrations against the configured database.

```bash
./scripts/db-migrate.sh upgrade          # Apply all pending migrations
./scripts/db-migrate.sh downgrade        # Roll back one migration
./scripts/db-migrate.sh history          # Show migration history
./scripts/db-migrate.sh current          # Show current revision
./scripts/db-migrate.sh create "msg"     # Generate a new migration
```

Set `DATABASE_URL` before running locally:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/aws_cost_dashboard \
  ./scripts/db-migrate.sh upgrade
```

In production, ECS tasks run migrations on startup via the entrypoint.

---

## backup-db.sh — Database backup and restore

```bash
./scripts/backup-db.sh production create    # Create compressed backup
./scripts/backup-db.sh production list      # List available backups
./scripts/backup-db.sh staging    restore   # Interactive restore
./scripts/backup-db.sh production cleanup   # Delete backups older than 30 days
```

Backups are written to `backups/` at the project root and optionally uploaded
to S3 if `BACKUP_S3_BUCKET` is set.

**Requirements:** `pg_dump`, `psql`, `gzip`, `aws` (for S3 uploads)

---

## manage-secrets.sh — Secrets management

```bash
# Generate keys locally (paste into .env.production / terraform.tfvars)
./scripts/manage-secrets.sh generate

# Create secrets in AWS Secrets Manager for production
./scripts/manage-secrets.sh create production

# View current secrets
./scripts/manage-secrets.sh get production

# Rotate keys (invalidates all user sessions)
./scripts/manage-secrets.sh rotate production
```

Secrets stored: `SECRET_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`.

**Requirements:** `aws`, `jq`, `python3`, `cryptography` package

---

## health-check.sh — Component health check

```bash
# Local dev stack
./scripts/health-check.sh local http://localhost:8000

# Production (use the API Gateway URL from `terraform output api_gateway_url`)
./scripts/health-check.sh production https://abc123.execute-api.us-east-1.amazonaws.com/prod
```

Checks: backend `/health`, database, Redis, AWS connectivity, ECS service status.

---

## setup-testing.sh — Test environment setup

```bash
./scripts/setup-testing.sh all       # Backend + frontend test deps
./scripts/setup-testing.sh backend   # Python venv + pytest deps only
./scripts/setup-testing.sh frontend  # npm test deps only
```

Creates `tests/.venv` for the backend test suite.

---

## Common workflows

### First deploy

```bash
# 1. Fill in all config
cp .env.example .env.production
# Edit .env.production — set DOCKER_REGISTRY, VERSION, db passwords, secrets, etc.
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set cors_allowed_origins, backend_image, secrets, etc.

# 2. Generate application secrets (paste values into .env.production + terraform.tfvars)
./scripts/manage-secrets.sh generate

# 3. Build and push backend image
./scripts/build-prod.sh --push

# 4. Deploy backend infrastructure (~15-20 min)
./scripts/deploy.sh production apply
# Note the api_gateway_url printed at the end

# 5. Set the API Gateway URL in .env.production
# VITE_API_BASE_URL=https://abc123.execute-api.us-east-1.amazonaws.com/prod

# 6. Run database migrations
./scripts/db-migrate.sh upgrade

# 7. Deploy frontend to GitHub Pages
./scripts/deploy-pages.sh
```

### Deploying a new backend version

```bash
# 1. Bump VERSION in .env.production
# 2. Build and push the new image
./scripts/build-prod.sh --push
# 3. Update backend_image in terraform.tfvars to the new tag
# 4. Deploy
./scripts/deploy.sh production apply
# Or force ECS to pick up the new image without Terraform:
# aws ecs update-service --cluster CLUSTER --service BACKEND_SVC --force-new-deployment
```

### Deploying a frontend change

```bash
# Ensure VITE_API_BASE_URL is set in .env.production
./scripts/deploy-pages.sh
```

### Daily operations

```bash
# Health check
./scripts/health-check.sh production https://YOUR-API-GATEWAY-URL

# Create database backup
./scripts/backup-db.sh production create

# Tail backend logs
aws logs tail /ecs/awscost-production-backend --follow
```

---

## Prerequisites

| Tool | Required by | Install |
|------|------------|---------|
| `bash` 4+ | All | — |
| `aws` CLI v2 | deploy, backup, manage-secrets, health-check | `brew install awscli` |
| `terraform` ≥ 1.0 | deploy | `brew install terraform` |
| `docker` | build-prod, deploy | docker.com |
| `node` / `npm` | deploy-pages, setup-testing | nodejs.org |
| `git` | deploy-pages | — |
| `jq` | several | `brew install jq` |
| `pg_dump` / `psql` | backup-db, db-migrate | `brew install postgresql-client` |
| `python3` | db-migrate, manage-secrets | python.org |

AWS credentials must be configured (`aws configure` or environment variables).

---

## Making scripts executable

```bash
chmod +x scripts/*.sh
```
