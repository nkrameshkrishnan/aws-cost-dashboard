# Dual-Track Quick Start: Testing + Staging Deployment

**Objective**: Implement testing while deploying to AWS staging in parallel
**Duration**: 2-3 weeks
**Outcome**: Production-ready application with >80% test coverage, validated on AWS

---

## Overview

This guide helps you execute two critical tasks simultaneously:

1. **Track 1: Testing** - Implement comprehensive tests (can run locally)
2. **Track 2: Staging Deployment** - Deploy to AWS to validate infrastructure

### Why Dual-Track?

- **Parallel Work**: Testing can happen locally while AWS resources provision
- **Faster Time to Production**: No sequential dependencies
- **Continuous Validation**: Test while infrastructure stabilizes
- **Risk Mitigation**: Identify issues early in both code and infrastructure

---

## Prerequisites

### For Testing (Track 1)
- ✅ Python 3.11+
- ✅ Node.js 18+
- ✅ Docker (for local testing)

### For Staging Deployment (Track 2)
- ✅ AWS Account with admin permissions
- ✅ AWS CLI configured
- ✅ Terraform >= 1.0
- ✅ Docker registry access (ECR/Docker Hub/GitHub)

---

## Day 1: Setup Both Tracks

### Morning: Testing Setup (2 hours)

```bash
# Quick setup using automated script
./scripts/setup-testing.sh all

# Verify backend testing
cd backend
source venv/bin/activate
pytest tests/test_api/test_health.py -v

# Verify frontend testing
cd ../frontend
npm test
```

**Expected Result**: Sample tests pass, framework is working

### Afternoon: Staging Deployment Prep (2 hours)

```bash
# 1. Generate secrets
python3 -c "import secrets; print('SECRET_KEY:', secrets.token_urlsafe(32))"
python3 -c "import secrets; print('JWT_SECRET_KEY:', secrets.token_urlsafe(32))"
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY:', Fernet.generate_key().decode())"
openssl rand -base64 32  # Database password

# Save these values!

# 2. Configure Terraform
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars  # Add your secrets

# 3. Build Docker images (if using ECR)
# See STAGING_DEPLOYMENT_GUIDE.md Section 2
```

**Expected Result**: Secrets generated, Terraform configured, ready to deploy

---

## Week 1: Backend Testing + AWS Deployment

### Track 1: Backend Testing (Days 2-6)

**Day 2-3: Core Service Tests**
```bash
cd backend

# Create test files (examples in PHASE8_TESTING_PLAN.md)
# - tests/test_aws/test_session_manager.py
# - tests/test_aws/test_cost_explorer.py
# - tests/test_core/test_cache.py

# Run tests
pytest -v --cov=app

# Target: 40% coverage by end of Day 3
```

**Day 4-5: API Endpoint Tests**
```bash
# Create API tests
# - tests/test_api/test_costs.py
# - tests/test_api/test_budgets.py
# - tests/test_api/test_finops.py

# Run tests
pytest -v --cov=app

# Target: 60% coverage by end of Day 5
```

**Day 6: Service Layer Tests**
```bash
# Create service tests
# - tests/test_services/test_cost_processor.py
# - tests/test_services/test_budget_service.py

# Run full test suite
pytest -v --cov=app --cov-report=html

# Target: 70% coverage
```

### Track 2: AWS Deployment (Days 2-6)

**Day 2: Initial Deployment**
```bash
cd infrastructure/terraform

# Initialize and validate
terraform init
terraform validate

# Plan deployment
terraform plan -out=staging.tfplan

# Review plan, then apply
terraform apply staging.tfplan
```

**Expected**: 15-20 minutes deployment time

**Day 3: Verify & Debug**
```bash
# Check deployment status
./scripts/health-check.sh staging $(terraform output -raw alb_url)

# If issues, check logs
aws logs tail /ecs/awscost-staging-backend --follow
```

**Day 4-5: Configure Application**
```bash
# Access application
open $(terraform output -raw alb_url)

# Configure:
# 1. Add AWS account credentials
# 2. Test cost data fetching
# 3. Create a test budget
# 4. Run FinOps audit
```

**Day 6: Monitor & Optimize**
```bash
# Check CloudWatch metrics
# Tune cache settings if needed
# Verify auto-scaling works
```

---

## Week 2: Frontend Testing + Staging Validation

### Track 1: Frontend Testing (Days 7-11)

**Day 7-8: Component Tests**
```bash
cd frontend

# Create component tests (see PHASE8_TESTING_PLAN.md)
# - src/components/dashboard/__tests__/KPICard.test.tsx
# - src/components/dashboard/__tests__/CostTrendChart.test.tsx

# Run tests
npm test

# Target: 50% coverage
```

**Day 9-10: Hook & Integration Tests**
```bash
# Create hook tests
# - src/hooks/__tests__/useCostData.test.ts
# - src/hooks/__tests__/useBudgets.test.ts

# Run with coverage
npm run test:coverage

# Target: 70% coverage
```

**Day 11: E2E Tests**
```bash
# Create E2E tests
# - e2e/dashboard.spec.ts
# - e2e/budgets.spec.ts

# Run E2E tests
npm run test:e2e
```

### Track 2: Staging Testing & Validation (Days 7-11)

**Day 7-8: Functional Testing**

Manual testing checklist:
- [ ] Login/Authentication works
- [ ] Cost data displays correctly
- [ ] Budget tracking functional
- [ ] FinOps audit runs successfully
- [ ] Forecasting shows predictions
- [ ] Export to CSV/Excel/PDF works
- [ ] Teams integration sends notifications
- [ ] Right-sizing recommendations appear
- [ ] Unit cost analysis displays
- [ ] Automation jobs can be created

**Day 9-10: Performance Testing**
```bash
# Install k6
brew install k6  # macOS
# OR
sudo apt install k6  # Ubuntu

# Create load test script
cat > load-test.js <<EOF
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 10,
  duration: '30s',
};

export default function () {
  const res = http.get('${ALB_URL}/api/v1/costs/summary');
  check(res, { 'status was 200': (r) => r.status == 200 });
  sleep(1);
}
EOF

# Run load test
k6 run load-test.js
```

**Day 11: Security Review**
```bash
# Scan dependencies
cd backend && pip-audit
cd ../frontend && npm audit

# Check for secrets in code
git secrets --scan

# Review IAM permissions
aws iam get-role-policy \
  --role-name awscost-staging-ecs-task-role \
  --policy-name awscost-staging-ecs-task-aws-access
```

---

## Week 3: Integration & Final Validation

### Track 1: Complete Testing (Days 12-16)

**Day 12-13: Fill Coverage Gaps**
```bash
# Identify untested code
pytest --cov=app --cov-report=term-missing

# Add tests for uncovered areas
# Priority: Critical paths, business logic
```

**Day 14: Integration Tests**
```bash
# Create integration tests
# - tests/test_integration/test_cost_flow.py
# - tests/test_integration/test_budget_alerts.py

pytest -m integration
```

**Day 15-16: CI/CD Validation**
```bash
# Push to GitHub
git push origin main

# Verify CI/CD pipeline passes
# - Check GitHub Actions
# - Review test results
# - Verify coverage reports
```

### Track 2: Staging Hardening (Days 12-16)

**Day 12-13: Monitoring Setup**
```bash
# Set up CloudWatch alarms
aws cloudwatch put-metric-alarm \
  --alarm-name staging-high-error-rate \
  --metric-name 5XXError \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold

# Configure log insights queries
# Set up billing alerts
```

**Day 14: Disaster Recovery Test**
```bash
# Create database backup
./scripts/backup-db.sh staging create

# Test restoration process
./scripts/backup-db.sh staging list

# Verify backup works
```

**Day 15-16: Documentation & Handoff**
```bash
# Document staging environment
# - URLs and endpoints
# - Test user accounts
# - Known issues/limitations
# - Performance baselines
# - Cost breakdown

# Create runbook for common operations
```

---

## Success Criteria

### Testing Track
- ✅ Backend test coverage >80%
- ✅ Frontend test coverage >70%
- ✅ E2E tests cover critical user flows
- ✅ CI/CD pipeline passes all tests
- ✅ No critical bugs found

### Staging Track
- ✅ All infrastructure deployed successfully
- ✅ Application accessible via ALB
- ✅ All core features functional
- ✅ Performance meets targets (<3s page load)
- ✅ Security scan passes
- ✅ Monitoring and alerts configured
- ✅ Cost within budget (~$200/month)

---

## Quick Command Reference

### Testing Commands
```bash
# Backend
cd backend && source venv/bin/activate
pytest -v --cov=app
pytest -m "not slow"  # Skip slow tests
pytest --lf  # Run last failed tests

# Frontend
cd frontend
npm test  # Run unit tests
npm run test:ui  # Interactive UI
npm run test:coverage  # With coverage
npm run test:e2e  # E2E tests
```

### Staging Commands
```bash
# Infrastructure
cd infrastructure/terraform
terraform plan
terraform apply
terraform output
terraform destroy  # CAUTION!

# Application
./scripts/health-check.sh staging $ALB_URL
./scripts/backup-db.sh staging create

# AWS
aws ecs list-tasks --cluster awscost-staging-cluster
aws logs tail /ecs/awscost-staging-backend --follow
aws cloudwatch get-metric-statistics --metric-name CPUUtilization ...
```

---

## Troubleshooting

### Testing Issues

**Issue**: `ModuleNotFoundError` in tests
```bash
# Solution: Ensure proper imports
cd backend
pip install -e .  # Install package in editable mode
```

**Issue**: Frontend tests fail with "Cannot find module"
```bash
# Solution: Check path aliases
npm install
# Verify vitest.config.ts has correct aliases
```

### Deployment Issues

**Issue**: ECS tasks not starting
```bash
# Check task definition
aws ecs describe-task-definition --task-definition awscost-staging-backend

# Check task failures
aws ecs describe-tasks --cluster ... --tasks ... --query 'tasks[0].stoppedReason'
```

**Issue**: 502 Bad Gateway from ALB
```bash
# Check target health
aws elbv2 describe-target-health --target-group-arn ...

# Verify security groups
aws ec2 describe-security-groups --group-ids ...
```

---

## Daily Standup Template

Track progress daily:

```
## Date: YYYY-MM-DD

### Track 1: Testing
- [ ] Backend coverage: ___%
- [ ] Frontend coverage: ___%
- [ ] Tests written today: ___
- [ ] Tests passing: ___/__
- Blockers: ___

### Track 2: Staging
- [ ] Infrastructure status: ___
- [ ] Features tested: ___
- [ ] Issues found: ___
- [ ] Performance: ___ (page load time)
- Blockers: ___

### Next 24 Hours
- Testing: ___
- Staging: ___
```

---

## Resources

### Documentation
- [PHASE8_TESTING_PLAN.md](PHASE8_TESTING_PLAN.md) - Detailed testing guide
- [STAGING_DEPLOYMENT_GUIDE.md](STAGING_DEPLOYMENT_GUIDE.md) - Complete deployment guide
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Current status

### Scripts
- `scripts/setup-testing.sh` - Automated testing setup
- `scripts/deploy.sh` - Deployment automation
- `scripts/health-check.sh` - Health verification

### External Resources
- [pytest documentation](https://docs.pytest.org/)
- [Vitest guide](https://vitest.dev/)
- [Playwright docs](https://playwright.dev/)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)

---

## Timeline Summary

| Week | Track 1: Testing | Track 2: Staging |
|------|------------------|------------------|
| **Week 1** | Backend tests (70% coverage) | Deploy + initial validation |
| **Week 2** | Frontend tests (70% coverage) | Functional + performance testing |
| **Week 3** | Integration + E2E tests | Hardening + documentation |

**Total Duration**: 2-3 weeks
**End Result**: Production-ready application with comprehensive tests and validated infrastructure

---

## Getting Started NOW

### Step 1: Testing Track (10 minutes)
```bash
./scripts/setup-testing.sh all
cd backend && source venv/bin/activate && pytest
cd ../frontend && npm test
```

### Step 2: Deployment Track (10 minutes)
```bash
# Generate secrets (save output!)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Configure Terraform
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars  # Add secrets
```

### Step 3: Kick Off Both Tracks
```bash
# Terminal 1: Start testing
cd backend && pytest --watch

# Terminal 2: Deploy to AWS
cd infrastructure/terraform && terraform apply
```

---

**Status**: Ready to start
**Estimated Completion**: 2-3 weeks
**Questions?** Check the detailed guides:
- Testing: `PHASE8_TESTING_PLAN.md`
- Deployment: `STAGING_DEPLOYMENT_GUIDE.md`
