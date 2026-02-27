# AWS Cost Dashboard - Utility Scripts

This directory contains utility scripts for deploying, managing, and maintaining the AWS Cost Dashboard application.

## Available Scripts

### 1. deploy.sh - Deployment Automation

Automates the complete deployment process including building Docker images and applying Terraform infrastructure.

**Usage:**
```bash
./scripts/deploy.sh [environment] [action]
```

**Arguments:**
- `environment`: dev, staging, or production (default: dev)
- `action`: plan, apply, or destroy (default: plan)

**Examples:**
```bash
# Plan deployment to development
./scripts/deploy.sh dev plan

# Deploy to production
./scripts/deploy.sh production apply

# Destroy staging infrastructure
./scripts/deploy.sh staging destroy
```

**What it does:**
1. Checks prerequisites (Terraform, AWS CLI, Docker, jq)
2. Validates AWS credentials
3. Builds production Docker images
4. Pushes images to configured registry
5. Runs Terraform to provision infrastructure
6. Displays deployment information

---

### 2. db-migrate.sh - Database Migrations

Manages database schema migrations using Alembic.

**Usage:**
```bash
./scripts/db-migrate.sh [command] [options]
```

**Commands:**
- `upgrade`: Upgrade to latest migration (default)
- `downgrade`: Downgrade one migration
- `history`: Show migration history
- `current`: Show current migration version
- `create "message"`: Create a new migration
- `init`: Initialize Alembic (first time only)

**Examples:**
```bash
# Upgrade database to latest version
./scripts/db-migrate.sh upgrade

# Create new migration
./scripts/db-migrate.sh create "add user preferences table"

# Show migration history
./scripts/db-migrate.sh history

# Downgrade one version
./scripts/db-migrate.sh downgrade
```

---

### 3. manage-secrets.sh - Secrets Management

Helps generate and manage application secrets in AWS Secrets Manager.

**Usage:**
```bash
./scripts/manage-secrets.sh [command] [environment]
```

**Commands:**
- `generate`: Generate new application keys locally
- `create`: Create secrets in AWS Secrets Manager
- `update`: Update secrets in AWS Secrets Manager
- `get`: Retrieve secrets from AWS Secrets Manager
- `rotate`: Rotate application keys (invalidates user sessions)

**Examples:**
```bash
# Generate keys locally (for .env file)
./scripts/manage-secrets.sh generate

# Create secrets in AWS for production
./scripts/manage-secrets.sh create production

# View current secrets
./scripts/manage-secrets.sh get staging

# Rotate production keys
./scripts/manage-secrets.sh rotate production
```

**Generated Keys:**
- `SECRET_KEY`: Session encryption key
- `JWT_SECRET_KEY`: JWT token signing key
- `ENCRYPTION_KEY`: Fernet key for AWS credential encryption

---

### 4. health-check.sh - System Health Monitoring

Performs comprehensive health checks on all application components.

**Usage:**
```bash
./scripts/health-check.sh [environment] [url]
```

**Examples:**
```bash
# Check local development environment
./scripts/health-check.sh local http://localhost:8000

# Check production
./scripts/health-check.sh production https://cost-dashboard.example.com
```

**What it checks:**
- Backend API availability
- Database connectivity
- Redis cache connectivity
- AWS API connectivity
- ECS service status (for AWS deployments)
- System performance metrics

**Output:**
```
✓ Backend API is healthy (HTTP 200)
✓ Database connection is healthy
✓ Redis connection is healthy
✓ AWS connectivity is healthy
========================================
System Metrics
========================================
{
  "cache": {
    "hit_rate": 78.5,
    "total_hits": 1247
  },
  "api": {
    "avg_response_time_ms": 145.6
  }
}
```

---

### 5. backup-db.sh - Database Backup & Restore

Creates and manages PostgreSQL database backups.

**Usage:**
```bash
./scripts/backup-db.sh [environment] [action]
```

**Actions:**
- `create`: Create a new backup (default)
- `restore`: Restore from a backup
- `list`: List available backups
- `cleanup`: Remove old backups

**Examples:**
```bash
# Create production backup
./scripts/backup-db.sh production create

# List all backups
./scripts/backup-db.sh production list

# Restore from backup
./scripts/backup-db.sh staging restore

# Remove backups older than 30 days
./scripts/backup-db.sh production cleanup
```

**Features:**
- Compressed backups (gzip)
- S3 upload support (if configured)
- Automatic retention management
- Safe restore with confirmation

**Environment Variables:**
- `BACKUP_S3_BUCKET`: S3 bucket for backup uploads (optional)

---

## Prerequisites

### Required Tools

All scripts require:
- **bash** (4.0+)
- **jq** - JSON processor
- **curl** - HTTP client

### Script-Specific Requirements

**deploy.sh:**
- Terraform (>= 1.0)
- AWS CLI (>= 2.0)
- Docker (>= 20.10)

**db-migrate.sh:**
- Python 3.11+
- Alembic (`pip install alembic`)
- PostgreSQL client tools

**manage-secrets.sh:**
- Python 3.11+
- AWS CLI
- cryptography package (`pip install cryptography`)

**backup-db.sh:**
- PostgreSQL client tools (`pg_dump`, `psql`)
- gzip

### AWS Credentials

Most scripts require AWS credentials configured:

```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1
```

---

## Making Scripts Executable

Before first use, make scripts executable:

```bash
chmod +x scripts/*.sh
```

---

## Common Workflows

### Initial Setup

```bash
# 1. Generate application keys
./scripts/manage-secrets.sh generate
# Save output to backend/.env

# 2. Configure Terraform
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# 3. Deploy infrastructure
./scripts/deploy.sh production apply

# 4. Run database migrations
./scripts/db-migrate.sh upgrade
```

### Daily Operations

```bash
# Health check
./scripts/health-check.sh production https://your-domain.com

# Create database backup
./scripts/backup-db.sh production create

# View application metrics
curl https://your-domain.com/api/v1/performance/stats | jq .
```

### Deployment Updates

```bash
# Build and deploy new version
./scripts/deploy.sh production plan
./scripts/deploy.sh production apply

# Check health after deployment
./scripts/health-check.sh production https://your-domain.com
```

### Disaster Recovery

```bash
# List available backups
./scripts/backup-db.sh production list

# Restore from backup
./scripts/backup-db.sh production restore

# Run migrations if needed
./scripts/db-migrate.sh upgrade
```

---

## Environment Variables

Scripts support these environment variables:

| Variable | Description | Used By |
|----------|-------------|---------|
| `BACKUP_S3_BUCKET` | S3 bucket for database backups | backup-db.sh |
| `TERRAFORM_DIR` | Custom Terraform directory | deploy.sh |
| `AWS_REGION` | AWS region | All AWS scripts |
| `AWS_PROFILE` | AWS CLI profile | All AWS scripts |

---

## Troubleshooting

### "Permission denied" error

Make scripts executable:
```bash
chmod +x scripts/*.sh
```

### "AWS credentials not configured"

Configure AWS CLI:
```bash
aws configure
```

### "Terraform not found"

Install Terraform:
```bash
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

### "pg_dump not found"

Install PostgreSQL client:
```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql-client

# RHEL/CentOS
sudo yum install postgresql
```

---

## Script Development

### Adding New Scripts

1. Create script in `scripts/` directory
2. Add shebang: `#!/bin/bash`
3. Set error handling: `set -e`
4. Add usage documentation in comments
5. Include color output functions
6. Make executable: `chmod +x scripts/your-script.sh`
7. Update this README

### Best Practices

- Use `set -e` for error handling
- Provide help/usage information
- Use colored output for better UX
- Validate inputs and prerequisites
- Add confirmation for destructive operations
- Log important actions
- Return meaningful exit codes

---

## Support

For issues with scripts:
1. Check prerequisites are installed
2. Verify AWS credentials
3. Review script output for errors
4. Check [DEPLOYMENT_GUIDE.md](../docs/DEPLOYMENT_GUIDE.md)
5. Open an issue on GitHub

---

## License

[Your License Here]
