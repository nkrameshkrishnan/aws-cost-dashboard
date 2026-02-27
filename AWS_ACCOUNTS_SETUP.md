# AWS Account Management via UI - Setup Guide

## Overview

The AWS Cost Dashboard now supports **adding AWS accounts through the web interface**!

No more configuring `~/.aws/credentials` files - you can now:
- ✅ Add AWS credentials directly in the UI
- ✅ Manage multiple AWS accounts from one place
- ✅ Switch between accounts with a dropdown
- ✅ Credentials are encrypted at rest in PostgreSQL

## What Changed

### Backend

1. **Database Models**: AWS accounts stored in PostgreSQL
2. **Credential Encryption**: Fernet symmetric encryption for Access Keys
3. **New API Endpoints**: `/api/v1/aws-accounts/*`
4. **Database Session Manager**: Creates boto3 sessions from stored credentials

### Frontend

1. **AWS Accounts Page**: New UI to add/manage/delete accounts
2. **Updated Profile Selector**: Loads accounts from database instead of hardcoded list
3. **Real-time Validation**: Credentials validated on creation

## Quick Start

### 1. Restart the Backend

The backend needs to restart to create database tables:

```bash
cd aws-cost-dashboard
docker-compose restart backend
```

Wait 10 seconds, then check it started successfully:

```bash
docker-compose logs backend | tail -20
```

Look for:
```
INFO:     Application startup complete.
Database tables initialized
```

### 2. Access the AWS Accounts Page

Open your browser and navigate to:

**http://localhost:5173/aws-accounts**

### 3. Add Your First AWS Account

Click "Add AWS Account" and fill in the form:

**Required Fields:**
- **Account Name**: A friendly name (e.g., "Production", "Dev-Account")
- **AWS Access Key ID**: Your AWS access key (starts with `AKIA...`)
- **AWS Secret Access Key**: Your AWS secret key

**Optional Fields:**
- **Description**: Notes about this account
- **Default Region**: AWS region (defaults to `us-east-1`)

**Example:**
```
Account Name: Production
Description: Main production AWS account
Access Key ID: AKIAIOSFODNN7EXAMPLE
Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
Default Region: us-east-1
```

### 4. Click "Create Account"

The system will:
1. Encrypt your credentials using Fernet encryption
2. Store them in PostgreSQL
3. Validate them by calling AWS STS `GetCallerIdentity`
4. Display the AWS Account ID if validation succeeds

### 5. View Cost Data

Go back to the Dashboard: **http://localhost:5173/dashboard**

The profile selector now shows your database accounts:
- Select your account from the dropdown
- Cost data will load automatically
- All charts update with real data

## API Endpoints

### List AWS Accounts
```bash
curl http://localhost:8000/api/v1/aws-accounts/
```

### Create AWS Account
```bash
curl -X POST http://localhost:8000/api/v1/aws-accounts/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production",
    "description": "Main production account",
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "region": "us-east-1"
  }'
```

### Validate Account
```bash
curl -X POST http://localhost:8000/api/v1/aws-accounts/1/validate
```

### Delete Account
```bash
curl -X DELETE http://localhost:8000/api/v1/aws-accounts/1
```

## Security Features

### Encryption

Credentials are encrypted using **Fernet symmetric encryption**:
- Encryption key derived from `SECRET_KEY` in config
- AES-128 encryption with HMAC authentication
- Credentials never stored in plaintext

### Database Schema

```sql
CREATE TABLE aws_accounts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(500),
    encrypted_access_key_id VARCHAR(500) NOT NULL,  -- Encrypted
    encrypted_secret_access_key VARCHAR(500) NOT NULL,  -- Encrypted
    account_id VARCHAR(12),  -- AWS Account ID (from validation)
    region VARCHAR(50) DEFAULT 'us-east-1',
    is_active BOOLEAN DEFAULT TRUE,
    last_validated TIMESTAMP,
    validation_error VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### IAM Permissions Required

Your AWS IAM user needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:GetCallerIdentity",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast"
      ],
      "Resource": "*"
    }
  ]
}
```

## Troubleshooting

### Backend Won't Start

**Error**: `pydantic_core._pydantic_core.ValidationError`

**Fix**: Make sure you're using the updated config with default values. Restart:
```bash
docker-compose down
docker-compose up --build
```

### "Table does not exist" Error

**Fix**: Database tables weren't created. Check logs:
```bash
docker-compose logs backend | grep "Database tables"
```

Should see: `Database tables initialized`

If not, manually initialize:
```bash
docker-compose exec backend python -c "from app.database.base import init_db; init_db()"
```

### Credentials Validation Fails

**Symptoms**: Account created but shows validation error

**Causes**:
1. **Invalid credentials** - Check Access Key and Secret Key
2. **IAM permissions** - User needs `sts:GetCallerIdentity` permission
3. **Expired credentials** - Generate new access keys in AWS Console

**Debug**:
```bash
# Test credentials with AWS CLI
aws sts get-caller-identity \
  --aws-access-key-id YOUR_KEY \
  --aws-secret-access-key YOUR_SECRET
```

### No Accounts Appear in Profile Selector

**Fix 1**: Clear browser cache and reload

**Fix 2**: Check if accounts exist:
```bash
curl http://localhost:8000/api/v1/aws-accounts/
```

**Fix 3**: Check browser console (F12) for errors

### Cost Data Shows $0.00

**Causes**:
1. **Cost Explorer not enabled** - Enable in AWS Console
2. **No cost data for date range** - Try a different date
3. **Wrong account selected** - Check profile selector

## Migration Guide

### From File-Based Credentials

If you have existing `~/.aws/credentials`:

1. Open your credentials file:
```bash
cat ~/.aws/credentials
```

2. For each profile, add it via the UI or API:
```bash
# Example profile from credentials file:
[production]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

3. Create via API:
```bash
curl -X POST http://localhost:8000/api/v1/aws-accounts/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production",
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  }'
```

### Backup Your Database

Before deploying to production, backup your database:

```bash
# Backup
docker-compose exec postgres pg_dump -U postgres aws_cost_dashboard > backup.sql

# Restore
docker-compose exec -T postgres psql -U postgres aws_cost_dashboard < backup.sql
```

## Architecture

### Data Flow

```
User enters credentials in UI
    ↓
Frontend → POST /api/v1/aws-accounts/
    ↓
Backend encrypts credentials (Fernet)
    ↓
Store in PostgreSQL (encrypted)
    ↓
Validate with AWS STS GetCallerIdentity
    ↓
Return account info to frontend
    ↓
User selects account in dropdown
    ↓
Frontend → GET /api/v1/costs/summary?profile_name=Production
    ↓
Backend retrieves account from database
    ↓
Decrypt credentials
    ↓
Create boto3 session
    ↓
Call AWS Cost Explorer API
    ↓
Return cost data to frontend
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **Database Model** | `models/aws_account.py` | SQLAlchemy model for accounts |
| **Encryption** | `core/encryption.py` | Fernet credential encryption |
| **Account Service** | `services/aws_account_service.py` | CRUD operations |
| **Session Manager** | `aws/session_manager_db.py` | Create boto3 sessions from DB |
| **Cost Processor** | `services/cost_processor_db.py` | Fetch costs using DB credentials |
| **API Endpoints** | `api/v1/endpoints/aws_accounts.py` | REST API |
| **Frontend UI** | `pages/AWSAccountsPage.tsx` | Account management page |
| **Profile Selector** | `components/common/ProfileSelector.tsx` | Account dropdown |

## Production Considerations

### 1. Change SECRET_KEY

The encryption key is derived from `SECRET_KEY`. In production:

```bash
# Generate a secure random key (32+ characters)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in .env
SECRET_KEY=your-secure-random-key-here
```

### 2. Use Environment Variables

Don't commit `.env` to git:

```bash
# .env
SECRET_KEY=production-secret-key-32chars-min
JWT_SECRET_KEY=production-jwt-secret-32chars-min
DATABASE_URL=postgresql://user:pass@db-host:5432/dbname
```

### 3. Enable HTTPS

All API calls should be over HTTPS in production:
- Use reverse proxy (Nginx, Cloudflare)
- Terminate SSL at load balancer
- Never send credentials over HTTP

### 4. Database Backups

Set up automated PostgreSQL backups:
- AWS RDS automated backups
- pg_dump cron jobs
- Point-in-time recovery

### 5. Audit Logging

Consider adding audit logs for:
- Account creation/deletion
- Credential updates
- Failed validation attempts

## Next Steps

Now that you have AWS accounts configured:

1. ✅ **Phase 2 Complete**: Cost visualization works with DB accounts
2. 🚀 **Phase 3**: Implement Budget Tracking
3. 🚀 **Phase 4**: Add FinOps Audits
4. 🚀 **Phase 5**: Export & Reporting
5. 🚀 **Phase 6**: Microsoft Teams Integration

## Need Help?

**Check Logs:**
```bash
# Backend logs
docker-compose logs -f backend

# Database logs
docker-compose logs -f postgres
```

**Test API:**
```bash
# Health check
curl http://localhost:8000/health

# System status
curl http://localhost:8000/api/v1/health/status

# List accounts
curl http://localhost:8000/api/v1/aws-accounts/
```

**Common Issues:**
- **404 errors**: Backend not running or routes not registered
- **500 errors**: Check backend logs for stack trace
- **403/401 errors**: AWS IAM permissions issue
- **Empty dropdown**: No accounts created yet

---

**You're all set!** Add your AWS accounts through the UI and start monitoring costs. 🎉
