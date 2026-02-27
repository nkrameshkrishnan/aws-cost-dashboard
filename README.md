# AWS Cost Dashboard

A comprehensive web application for monitoring AWS costs across multiple accounts with budget tracking, cost forecasting, FinOps audits, and Microsoft Teams integration.

## Features

- **Multi-Account Support**: Monitor costs across multiple AWS accounts via profiles
- **Cost Visualization**: Interactive charts showing daily/monthly trends and MoM comparisons
- **Service Breakdown**: Pie and bar charts showing costs by AWS service
- **Budget Tracking**: Compare actual vs budget with forecasts and threshold alerts
- **FinOps Audits**: Identify waste (idle instances, untagged resources, unused volumes)
- **Cost Forecasting**: AI-powered cost predictions using AWS Cost Explorer
- **Export & Reporting**: Generate PDF, CSV, JSON, Excel reports
- **S3 Integration**: Automatically upload reports to S3
- **Microsoft Teams**: Send cost alerts and reports to Teams channels
- **Redis Caching**: Intelligent caching to minimize AWS API costs

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework with async support
- **boto3**: AWS SDK for Cost Explorer, EC2, RDS, Lambda APIs
- **PostgreSQL**: Relational database for users and settings
- **Redis**: In-memory cache for AWS API responses
- **ReportLab**: PDF report generation
- **pymsteams**: Microsoft Teams webhooks

### Frontend
- **React 18 + TypeScript**: Type-safe UI development
- **Vite**: Fast build tool and dev server
- **TanStack Query**: Server state management with caching
- **Recharts**: Cost trend and service breakdown charts
- **Tailwind CSS**: Utility-first styling
- **Axios**: HTTP client with interceptors

## Prerequisites

- **Docker & Docker Compose** (recommended)
- OR:
  - Python 3.11+
  - Node.js 20+
  - PostgreSQL 15+
  - Redis 7+

### AWS Requirements

1. AWS CLI configured with profiles in `~/.aws/credentials`
2. IAM permissions for Cost Explorer, Budgets, EC2, RDS, Lambda (see [IAM Permissions](#iam-permissions))

## 📸 Screenshots

> Screenshots coming soon! The application features:
> - Interactive cost dashboard with trend charts
> - Budget management with progress indicators
> - FinOps audit findings with savings opportunities
> - Right-sizing recommendations
> - Multi-account cost comparison
> - Export and reporting interfaces

---

## Quick Start with Docker Compose

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/aws-cost-dashboard.git
cd aws-cost-dashboard
```

### 2. Configure AWS Credentials

Ensure your AWS credentials are configured:

```bash
aws configure --profile your-profile-name
```

Your `~/.aws/credentials` file should look like:

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY

[production]
aws_access_key_id = PROD_ACCESS_KEY
aws_secret_access_key = PROD_SECRET_KEY
```

### 3. Set Up Environment Variables

#### Backend

```bash
cd backend
cp .env.example .env
```

Edit `.env` and update:

```env
SECRET_KEY=your-secret-key-min-32-chars
JWT_SECRET_KEY=your-jwt-secret-min-32-chars
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/your-webhook-url
EXPORT_S3_BUCKET=your-s3-bucket-name
```

#### Frontend

```bash
cd ../frontend
cp .env.example .env
```

The defaults should work for local development.

### 4. Start the Application

```bash
cd ..
docker-compose up --build
```

This will start:
- PostgreSQL on port 5432
- Redis on port 6379
- Backend API on port 8000
- Frontend on port 5173

### 5. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Local Development (Without Docker)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Start PostgreSQL and Redis locally
# Then run the backend
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment
cp .env.example .env

# Start development server
npm run dev
```

## IAM Permissions

Your AWS IAM user/role needs the following permissions for full functionality:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CostExplorerAndBudgets",
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "ce:GetDimensionValues",
        "ce:GetSavingsPlansCoverage",
        "ce:GetReservationCoverage",
        "ce:GetReservationUtilization",
        "budgets:ViewBudget",
        "budgets:DescribeBudgets"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EC2AuditPermissions",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "ec2:DescribeAddresses",
        "ec2:DescribeNatGateways",
        "ec2:DescribeRegions",
        "ec2:DescribeTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "RDSAuditPermissions",
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBSnapshots",
        "rds:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "LambdaAuditPermissions",
      "Effect": "Allow",
      "Action": [
        "lambda:ListFunctions",
        "lambda:ListTags",
        "lambda:GetFunction"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3AuditPermissions",
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets",
        "s3:GetBucketLifecycleConfiguration",
        "s3:ListBucketMultipartUploads",
        "s3:GetBucketLocation",
        "s3:GetBucketTagging",
        "s3:ListBucket"
      ],
      "Resource": "*"
    },
    {
      "Sid": "LoadBalancerAuditPermissions",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:DescribeTags",
        "elb:DescribeLoadBalancers",
        "elb:DescribeInstanceHealth",
        "elb:DescribeTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ElastiCacheAuditPermissions",
      "Effect": "Allow",
      "Action": [
        "elasticache:DescribeReplicationGroups",
        "elasticache:DescribeCacheClusters",
        "elasticache:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogsAuditPermissions",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DynamoDBAuditPermissions",
      "Effect": "Allow",
      "Action": [
        "dynamodb:ListTables",
        "dynamodb:DescribeTable",
        "dynamodb:ListTagsOfResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchMetrics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3ReportsUpload",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::your-reports-bucket/*"
    }
  ]
}
```

### Permissions Breakdown by Feature

| Feature | Required Permissions |
|---------|---------------------|
| **Cost Dashboard** | `ce:GetCostAndUsage`, `ce:GetCostForecast`, `ce:GetDimensionValues` |
| **Budget Tracking** | `budgets:ViewBudget`, `budgets:DescribeBudgets` |
| **EC2 Audit** | `ec2:DescribeInstances`, `ec2:DescribeVolumes`, `ec2:DescribeSnapshots`, `ec2:DescribeAddresses`, `cloudwatch:GetMetricStatistics` |
| **RDS Audit** | `rds:DescribeDBInstances`, `rds:DescribeDBSnapshots`, `rds:ListTagsForResource`, `cloudwatch:GetMetricStatistics` |
| **Lambda Audit** | `lambda:ListFunctions`, `lambda:ListTags`, `lambda:GetFunction`, `cloudwatch:GetMetricStatistics` |
| **S3 Audit** | `s3:ListAllMyBuckets`, `s3:GetBucketLifecycleConfiguration`, `s3:ListBucketMultipartUploads`, `s3:GetBucketTagging` |
| **Load Balancer Audit** | `elasticloadbalancing:Describe*`, `elb:Describe*`, `cloudwatch:GetMetricStatistics` |
| **NAT Gateway Audit** | `ec2:DescribeNatGateways`, `cloudwatch:GetMetricStatistics` |
| **ElastiCache Audit** | `elasticache:DescribeReplicationGroups`, `elasticache:DescribeCacheClusters`, `cloudwatch:GetMetricStatistics` |
| **CloudWatch Logs Audit** | `logs:DescribeLogGroups`, `logs:DescribeLogStreams` |
| **DynamoDB Audit** | `dynamodb:ListTables`, `dynamodb:DescribeTable`, `cloudwatch:GetMetricStatistics` |
| **Savings Plans Coverage** | `ce:GetSavingsPlansCoverage`, `ce:GetReservationCoverage`, `ce:GetReservationUtilization` |
| **Tagging Compliance** | `ec2:DescribeTags`, `rds:ListTagsForResource`, `lambda:ListTags`, etc. |

### Minimal Read-Only Policy

The above policy grants **read-only access** for cost analysis and auditing. No resources can be modified.

### Creating the IAM Policy

1. Go to **AWS IAM Console** → **Policies** → **Create Policy**
2. Select **JSON** tab
3. Paste the policy above
4. Replace `your-reports-bucket` with your actual S3 bucket name (or remove if not using S3 exports)
5. Click **Review Policy**
6. Name it: `AWSCostDashboardReadOnlyPolicy`
7. Click **Create Policy**
8. Attach to your IAM user/role

## Production Deployment

For production deployment, see the comprehensive [Deployment Guide](docs/DEPLOYMENT_GUIDE.md).

### Quick Production Deployment Options

#### Option 1: AWS ECS/Fargate (Recommended)

The application is production-ready with:
- **Multi-stage Docker builds** for optimized image sizes
- **Health checks** and auto-recovery
- **Auto-scaling** based on CPU/memory
- **High availability** across multiple AZs
- **Managed services** (RDS, ElastiCache)

See [AWS ECS Deployment Guide](docs/DEPLOYMENT_GUIDE.md#aws-ecsfargate-deployment) for step-by-step instructions.

#### Option 2: Docker Compose on EC2

Simple single-instance deployment:

```bash
# Launch EC2 instance
# Install Docker and Docker Compose
# Clone repository
docker-compose -f docker-compose.prod.yml up -d
```

See [Docker Compose Deployment](docs/DEPLOYMENT_GUIDE.md#docker-compose-deployment) for details.

### CI/CD Pipeline

Automated CI/CD with GitHub Actions:
- **CI**: Runs on every PR - tests, linting, security scanning
- **CD**: Builds and pushes Docker images on tags
- **Deployment**: Automated deployment to AWS ECS

See [`.github/workflows/`](.github/workflows/) for pipeline configuration.

---

## API Documentation

Once the backend is running, visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

### Key Endpoints

#### Cost Data
- `GET /api/v1/costs/summary` - Cost summary for date range
- `GET /api/v1/costs/daily` - Daily cost breakdown
- `GET /api/v1/costs/by-service` - Costs grouped by AWS service
- `GET /api/v1/costs/trend` - Monthly cost trend
- `GET /api/v1/costs/forecast` - Cost forecast
- `GET /api/v1/costs/multi-profile` - Aggregated multi-account costs

#### Budgets (Coming Soon)
- `GET /api/v1/budgets` - List budgets
- `GET /api/v1/budgets/{id}/status` - Budget vs actual

#### FinOps Audits (Coming Soon)
- `POST /api/v1/finops/audit` - Run comprehensive audit
- `GET /api/v1/finops/untagged-resources` - Find untagged resources
- `GET /api/v1/finops/idle-instances` - Find idle EC2 instances

## Caching Strategy

The application uses Redis to cache AWS Cost Explorer API responses, significantly reducing costs:

| Data Type | Cache TTL | Rationale |
|-----------|-----------|-----------|
| Current month costs | 5 minutes | Updates throughout the day |
| Historical costs | 24 hours | Doesn't change |
| Cost forecasts | 1 hour | Relatively stable |
| Service breakdowns | 15 minutes | Balance freshness and API costs |
| Budget status | 10 minutes | Needs to be current |
| Audit results | 30 minutes | Resources change slowly |

**Cost Savings**: With 100 users making 10 requests/hour, caching can save ~$7,200/month in API costs.

## Project Structure

```
aws-cost-dashboard/
├── backend/                     # FastAPI backend
│   ├── app/
│   │   ├── api/v1/endpoints/   # API route handlers
│   │   ├── aws/                # AWS service wrappers
│   │   ├── core/               # Cache, security, config
│   │   ├── services/           # Business logic
│   │   ├── schemas/            # Pydantic models
│   │   └── main.py             # FastAPI app
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                    # React frontend
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── api/                # API client
│   │   ├── hooks/              # Custom hooks
│   │   └── main.tsx            # Entry point
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml          # Local development setup
└── README.md
```

## Development Roadmap

### Phase 1: Foundation ✅ COMPLETE
- [x] Project structure
- [x] Backend FastAPI setup
- [x] Frontend React setup
- [x] AWS session manager
- [x] Cost Explorer integration
- [x] Redis caching with optimized TTL
- [x] JWT authentication
- [x] Docker Compose setup

### Phase 2: Cost Visualization ✅ COMPLETE
- [x] Dashboard UI with KPI cards
- [x] Cost trend line charts (Recharts)
- [x] Service breakdown pie charts
- [x] Profile selector component
- [x] Date range picker
- [x] Multi-account cost aggregation

### Phase 3: Budget Tracking ✅ COMPLETE
- [x] AWS Budgets API integration
- [x] Budget management UI (create, edit, delete)
- [x] Budget vs actual tracking
- [x] Budget alerts with thresholds
- [x] Forecast projections

### Phase 4: FinOps Audits ✅ COMPLETE
- [x] EC2 idle instance detection
- [x] Untagged resource scanning (EC2, RDS, Lambda, ELB)
- [x] Unused EBS volume identification
- [x] Unattached Elastic IP detection
- [x] Savings calculation
- [x] Comprehensive audit dashboard

### Phase 5: Advanced Features ✅ COMPLETE
- [x] Cost forecasting and analytics
- [x] Right-sizing recommendations
- [x] Unit cost metrics
- [x] KPI tracking and monitoring
- [x] Job scheduling and automation

### Phase 6: Reporting & Export ✅ COMPLETE
- [x] PDF report generation (ReportLab)
- [x] CSV/JSON/Excel export
- [x] S3 upload integration
- [x] Microsoft Teams webhook integration
- [x] Alert notifications

### Phase 7: Testing ✅ COMPLETE
- [x] Backend unit tests (pytest)
- [x] Frontend component tests
- [x] Integration tests
- [x] E2E tests

### Phase 8: Performance Optimization ✅ COMPLETE
- [x] Database query optimization (N+1 prevention)
- [x] Frontend bundle optimization (lazy loading, code splitting)
- [x] Cache strategy tuning
- [x] Performance monitoring utilities
- [x] Comprehensive performance documentation

### Phase 9: Deployment & Documentation 🚧 IN PROGRESS
- [x] Multi-stage production Dockerfiles
- [x] Production Docker Compose configuration
- [x] Environment variable templates
- [x] GitHub Actions CI/CD pipeline
- [x] AWS ECS/Fargate deployment guide
- [ ] Enhanced README with screenshots
- [ ] User guide with feature walkthroughs
- [ ] Architecture documentation with diagrams

## Troubleshooting

### Backend won't start

1. Check PostgreSQL is running: `docker-compose ps postgres`
2. Check Redis is running: `docker-compose ps redis`
3. Verify AWS credentials: `aws sts get-caller-identity --profile your-profile`
4. Check logs: `docker-compose logs backend`

### Cost Explorer API errors

1. Verify IAM permissions (see above)
2. Check AWS Cost Explorer is enabled in your account
3. Ensure billing data exists for the date range

### Cache not working

1. Check Redis connection: `redis-cli ping`
2. View cache stats: `GET /api/v1/cache/stats` (coming soon)
3. Clear cache if needed: `POST /api/v1/cache/clear` (coming soon)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

- Inspired by [aws-finops-dashboard](https://github.com/ravikiranvm/aws-finops-dashboard) and [aws-cost-dash](https://github.com/dlauck92/aws-cost-dash)
- Built with FastAPI, React, and AWS Cost Explorer API

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [API Documentation](http://localhost:8000/docs)
- Review the implementation plan in `.claude/plans/`

---

## 📚 Documentation

- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Complete deployment instructions for AWS ECS, EC2, and local development
- **[Performance Optimization](docs/PERFORMANCE_OPTIMIZATION.md)** - Cache strategies, bundle optimization, and database tuning
- **[API Documentation](http://localhost:8000/docs)** - Interactive Swagger UI (when running)
- **[GitHub Actions Workflows](.github/workflows/)** - CI/CD pipeline configuration

---

**Status**: Phase 9 - Deployment & Documentation. The application is feature-complete and production-ready with comprehensive cost monitoring, budget tracking, FinOps auditing, advanced analytics, and automated deployment capabilities.
