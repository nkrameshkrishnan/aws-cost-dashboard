# Deployment Guide

Complete guide for deploying the AWS Cost Dashboard in local, staging, and production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Production Deployment](#production-deployment)
4. [Environment Variables](#environment-variables)
5. [Database Setup](#database-setup)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Docker** and **Docker Compose** v2.0+ (recommended)
- **Python** 3.11+ (if running backend without Docker)
- **Node.js** 18+ (if running frontend without Docker)
- **PostgreSQL** 15+
- **Redis** 7+

### AWS Requirements

- AWS Account with configured credentials
- IAM user/role with required permissions (see [AWS_SETUP.md](AWS_SETUP.md))
- AWS Cost Explorer enabled
- AWS Compute Optimizer enabled (optional, for right-sizing)

---

## Local Development

### Using Docker Compose (Recommended)

**1. Clone and Setup**

```bash
# Clone repository
git clone https://github.com/yourusername/aws-cost-dashboard.git
cd aws-cost-dashboard

# Create environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

**2. Configure AWS Credentials**

Ensure your `~/.aws/credentials` file exists:

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY

[production]
aws_access_key_id = PROD_ACCESS_KEY
aws_secret_access_key = PROD_SECRET_KEY
```

The Docker Compose file automatically mounts `~/.aws` directory.

**3. Start Services**

```bash
# Start all services (postgres, redis, backend, frontend)
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

**4. Access Application**

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

**5. Stop Services**

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clears database)
docker-compose down -v
```

### Manual Setup (Without Docker)

**Backend Setup**

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings:
#   DATABASE_URL=postgresql://user:pass@localhost:5432/awscosts
#   REDIS_HOST=localhost
#   REDIS_PORT=6379

# Run database migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend Setup**

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env:
#   VITE_API_BASE_URL=http://localhost:8000

# Start development server
npm run dev
```

---

## Production Deployment

### Option 1: Docker Compose Production

**1. Prepare Environment**

```bash
# Create production environment file
cat > .env.prod <<EOF
# Database (Use managed RDS in production)
DATABASE_URL=postgresql://user:password@rds-endpoint:5432/awscosts

# Redis (Use managed ElastiCache)
REDIS_HOST=elasticache-endpoint
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING

# Security - Generate strong secrets!
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)

# CORS - Your frontend URL
CORS_ORIGINS=["https://yourdomain.com"]

# AWS
AWS_REGION=us-east-1
EOF
```

**2. Build and Deploy**

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Scale backend if needed
docker-compose -f docker-compose.prod.yml up -d --scale backend=3
```

**3. Setup Reverse Proxy (Nginx)**

```nginx
# /etc/nginx/sites-available/awscost-dashboard
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option 2: AWS ECS/Fargate

**1. Create ECR Repositories**

```bash
# Create repositories
aws ecr create-repository --repository-name aws-cost-dashboard-backend
aws ecr create-repository --repository-name aws-cost-dashboard-frontend

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

**2. Build and Push Images**

```bash
# Build backend
cd backend
docker build -t aws-cost-dashboard-backend .
docker tag aws-cost-dashboard-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/aws-cost-dashboard-backend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/aws-cost-dashboard-backend:latest

# Build frontend
cd ../frontend
docker build -t aws-cost-dashboard-frontend .
docker tag aws-cost-dashboard-frontend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/aws-cost-dashboard-frontend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/aws-cost-dashboard-frontend:latest
```

**3. Create ECS Cluster**

```bash
# Create cluster
aws ecs create-cluster --cluster-name aws-cost-dashboard

# Create task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create service
aws ecs create-service \
  --cluster aws-cost-dashboard \
  --service-name backend-service \
  --task-definition aws-cost-backend:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

---

## Environment Variables

### Backend Environment Variables

| Variable | Description | Required | Default | Example |
|----------|-------------|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Yes | - | `postgresql://user:pass@localhost:5432/awscosts` |
| `REDIS_HOST` | Redis server hostname | Yes | - | `localhost` |
| `REDIS_PORT` | Redis server port | No | `6379` | `6379` |
| `REDIS_DB` | Redis database number | No | `0` | `0` |
| `REDIS_PASSWORD` | Redis password | No | - | `your-password` |
| `ENVIRONMENT` | Environment name | No | `development` | `production` |
| `DEBUG` | Debug mode | No | `True` | `False` |
| `LOG_LEVEL` | Logging level | No | `INFO` | `WARNING` |
| `SECRET_KEY` | Application secret key | Yes | - | `<generated>` |
| `JWT_SECRET_KEY` | JWT signing key | Yes | - | `<generated>` |
| `ENCRYPTION_KEY` | Encryption key for sensitive data | Yes | - | `<generated>` |
| `CORS_ORIGINS` | Allowed CORS origins | Yes | - | `["https://yourdomain.com"]` |
| `AWS_REGION` | Default AWS region | No | `us-east-1` | `us-west-2` |

### Frontend Environment Variables

| Variable | Description | Required | Default | Example |
|----------|-------------|----------|---------|---------|
| `VITE_API_BASE_URL` | Backend API URL | Yes | - | `http://localhost:8000` |
| `VITE_API_VERSION` | API version | No | `v1` | `v1` |

---

## Database Setup

### Initial Setup

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE awscosts;

# Create user
CREATE USER awscost_user WITH PASSWORD 'secure_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE awscosts TO awscost_user;

# Exit
\q
```

### Run Migrations

```bash
cd backend

# Activate virtual environment
source venv/bin/activate

# Run migrations
alembic upgrade head

# Check migration status
alembic current

# Create new migration (if needed)
alembic revision --autogenerate -m "Description of changes"
```

### Backup and Restore

**Backup**

```bash
# Backup database
pg_dump -U postgres -d awscosts -F c -b -v -f awscosts_backup_$(date +%Y%m%d).dump

# Backup with Docker
docker-compose exec postgres pg_dump -U postgres awscosts > backup.sql
```

**Restore**

```bash
# Restore database
pg_restore -U postgres -d awscosts -v awscosts_backup_20260223.dump

# Restore with Docker
docker-compose exec -T postgres psql -U postgres awscosts < backup.sql
```

---

## Monitoring

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Performance metrics
curl http://localhost:8000/api/v1/performance/stats

# Database status
docker-compose exec postgres pg_isready

# Redis status
docker-compose exec redis redis-cli ping
```

### Logging

**View Logs**

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend

# With timestamps
docker-compose logs -f -t backend
```

**Log Levels**

Set via `LOG_LEVEL` environment variable:
- `DEBUG`: Detailed information
- `INFO`: General information (recommended for development)
- `WARNING`: Warning messages (recommended for production)
- `ERROR`: Error messages only
- `CRITICAL`: Critical errors only

### Metrics and Monitoring

**Prometheus + Grafana Setup**

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  prometheus_data:
  grafana_data:
```

---

## Troubleshooting

### Backend Won't Start

**Check logs:**
```bash
docker-compose logs backend
```

**Common issues:**

1. **Database connection failed**
   - Verify PostgreSQL is running
   - Check `DATABASE_URL` in `.env`
   - Ensure database exists

2. **Redis connection failed**
   - Verify Redis is running
   - Check `REDIS_HOST` and `REDIS_PORT`

3. **Port already in use**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   # Kill process
   kill -9 <PID>
   ```

### Frontend Build Fails

**Clear cache and rebuild:**
```bash
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

### Database Migration Issues

**Reset database (⚠️ destroys data):**
```bash
cd backend
alembic downgrade base
alembic upgrade head
```

**Check migration history:**
```bash
alembic history
alembic current
```

### Performance Issues

**Check performance metrics:**
```bash
curl http://localhost:8000/api/v1/performance/stats | jq
```

**Check cache hit rate:**
```bash
curl http://localhost:8000/api/v1/performance/cache | jq '.application_level.hit_rate_percent'
```

**Database queries:**
```bash
curl http://localhost:8000/api/v1/performance/slow-queries | jq
```

---

## Production Checklist

Before deploying to production:

- [ ] Change all default passwords and secrets
- [ ] Set `DEBUG=False`
- [ ] Configure proper CORS origins
- [ ] Set up SSL/TLS certificates
- [ ] Configure database backups
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Review and apply security headers
- [ ] Set up rate limiting
- [ ] Configure firewall rules
- [ ] Test disaster recovery procedures
- [ ] Document deployment process
- [ ] Set up CI/CD pipeline

---

## Additional Resources

- [AWS Setup Guide](AWS_SETUP.md)
- [Performance Monitoring](../backend/docs/PERFORMANCE_MONITORING.md)
- [API Documentation](API.md)
- [Architecture Overview](ARCHITECTURE.md)
