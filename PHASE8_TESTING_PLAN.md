# Phase 8: Testing & Optimization - Implementation Plan

**Status**: In Progress
**Target Completion**: 2-3 weeks
**Current Coverage**: 0%
**Target Coverage**: >80%

---

## Overview

This plan implements comprehensive testing for the AWS Cost Dashboard to achieve production-ready quality.

### Testing Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Testing Pyramid                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│           E2E Tests (5%)                                    │
│          ┌──────────┐                                       │
│          │Playwright│                                       │
│          └──────────┘                                       │
│                                                             │
│        Integration Tests (15%)                              │
│      ┌──────────────────────┐                              │
│      │  API + DB + Cache    │                              │
│      └──────────────────────┘                              │
│                                                             │
│           Unit Tests (80%)                                  │
│  ┌────────────────────────────────────┐                    │
│  │ Services, Utils, Components, Hooks │                    │
│  └────────────────────────────────────┘                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Week 1: Backend Testing Foundation

### Day 1-2: Test Infrastructure Setup

#### 1.1. Install Testing Dependencies

```bash
cd backend

# Add to requirements.txt
cat >> requirements-test.txt <<EOF
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.25.2
moto[all]==4.2.9
fakeredis==2.20.1
factory-boy==3.3.0
faker==20.1.0
EOF

pip install -r requirements-test.txt
```

#### 1.2. Configure pytest

**File**: `backend/pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts =
    --verbose
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-report=xml
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
    aws: Tests requiring AWS credentials
```

#### 1.3. Create Test Configuration

**File**: `backend/tests/conftest.py`
```python
"""
Global test configuration and fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import fakeredis
from moto import mock_ce, mock_budgets, mock_ec2, mock_rds

from app.main import app
from app.database.base import Base
from app.core.database import get_db
from app.core.cache import get_redis_client


# Database fixtures
@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    """Create database session for each test."""
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# Redis fixtures
@pytest.fixture(scope="function")
def redis_client():
    """Create fake Redis client."""
    return fakeredis.FakeRedis()


# FastAPI test client
@pytest.fixture(scope="function")
def client(db_session, redis_client):
    """Create FastAPI test client with overrides."""
    def override_get_db():
        yield db_session

    def override_get_redis():
        return redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# AWS mocks
@pytest.fixture(scope="function")
def aws_credentials(monkeypatch):
    """Mock AWS credentials."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(scope="function")
def mock_cost_explorer(aws_credentials):
    """Mock AWS Cost Explorer."""
    with mock_ce():
        yield


@pytest.fixture(scope="function")
def mock_budgets_service(aws_credentials):
    """Mock AWS Budgets."""
    with mock_budgets():
        yield


@pytest.fixture(scope="function")
def mock_ec2_service(aws_credentials):
    """Mock AWS EC2."""
    with mock_ec2():
        yield
```

### Day 3-4: Core Service Tests

#### 1.4. Test AWS Session Manager

**File**: `backend/tests/test_aws/test_session_manager.py`
```python
"""
Tests for AWS session manager.
"""
import pytest
from moto import mock_sts
import boto3

from app.aws.session_manager import AWSSessionManager


class TestAWSSessionManager:
    """Test AWS session manager."""

    @mock_sts
    def test_get_session_default_profile(self, aws_credentials):
        """Test getting session with default profile."""
        manager = AWSSessionManager()
        session = manager.get_session()

        assert session is not None
        assert session.region_name == "us-east-1"

    @mock_sts
    def test_get_session_custom_profile(self, aws_credentials):
        """Test getting session with custom profile."""
        manager = AWSSessionManager()
        session = manager.get_session(profile_name="test-profile")

        assert session is not None

    @mock_sts
    def test_get_boto3_client(self, aws_credentials):
        """Test getting boto3 client."""
        manager = AWSSessionManager()
        client = manager.get_client("s3")

        assert client is not None
        assert client.meta.service_model.service_name == "s3"
```

#### 1.5. Test Cost Explorer Service

**File**: `backend/tests/test_aws/test_cost_explorer.py`
```python
"""
Tests for AWS Cost Explorer service.
"""
import pytest
from datetime import datetime, timedelta
from moto import mock_ce
import boto3

from app.aws.cost_explorer import CostExplorerService


class TestCostExplorerService:
    """Test Cost Explorer service."""

    @mock_ce
    def test_get_cost_and_usage(self, aws_credentials):
        """Test getting cost and usage data."""
        service = CostExplorerService()

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        result = service.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity="DAILY"
        )

        assert result is not None
        # Add more assertions based on expected structure

    @mock_ce
    def test_get_cost_forecast(self, aws_credentials):
        """Test getting cost forecast."""
        service = CostExplorerService()

        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=30)

        result = service.get_cost_forecast(
            start_date=start_date,
            end_date=end_date
        )

        assert result is not None
```

#### 1.6. Test Cache Service

**File**: `backend/tests/test_core/test_cache.py`
```python
"""
Tests for cache service.
"""
import pytest
from app.core.cache import CacheService


class TestCacheService:
    """Test cache service."""

    def test_set_and_get(self, redis_client):
        """Test setting and getting cache values."""
        cache = CacheService(redis_client)

        cache.set("test_key", "test_value", ttl=60)
        value = cache.get("test_key")

        assert value == "test_value"

    def test_delete(self, redis_client):
        """Test deleting cache values."""
        cache = CacheService(redis_client)

        cache.set("test_key", "test_value")
        cache.delete("test_key")
        value = cache.get("test_key")

        assert value is None

    def test_cache_decorator(self, redis_client):
        """Test cache decorator."""
        # Test implementation here
        pass
```

### Day 5: API Endpoint Tests

#### 1.7. Test Health Endpoints

**File**: `backend/tests/test_api/test_health.py`
```python
"""
Tests for health check endpoints.
"""
import pytest


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "version" in data

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
```

#### 1.8. Test Cost Endpoints

**File**: `backend/tests/test_api/test_costs.py`
```python
"""
Tests for cost endpoints.
"""
import pytest
from datetime import datetime, timedelta


class TestCostEndpoints:
    """Test cost endpoints."""

    @pytest.mark.aws
    def test_get_cost_summary(self, client, mock_cost_explorer):
        """Test getting cost summary."""
        response = client.get(
            "/api/v1/costs/summary",
            params={
                "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
                "end_date": datetime.now().isoformat()
            }
        )

        assert response.status_code == 200
        # Add more assertions

    @pytest.mark.aws
    def test_get_cost_by_service(self, client, mock_cost_explorer):
        """Test getting cost breakdown by service."""
        response = client.get("/api/v1/costs/by-service")

        assert response.status_code == 200
        # Add more assertions
```

---

## Week 2: Frontend Testing

### Day 1-2: Frontend Test Setup

#### 2.1. Install Testing Dependencies

```bash
cd frontend

npm install -D \
  vitest \
  @vitest/ui \
  @testing-library/react \
  @testing-library/jest-dom \
  @testing-library/user-event \
  jsdom \
  msw
```

#### 2.2. Configure Vitest

**File**: `frontend/vitest.config.ts`
```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mockData',
        'src/main.tsx',
      ],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

#### 2.3. Test Setup File

**File**: `frontend/src/test/setup.ts`
```typescript
import { expect, afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'

expect.extend(matchers)

afterEach(() => {
  cleanup()
})
```

### Day 3-4: Component Tests

#### 2.4. Test KPI Card Component

**File**: `frontend/src/components/dashboard/__tests__/KPICard.test.tsx`
```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KPICard } from '../KPICard'

describe('KPICard', () => {
  it('renders title and value', () => {
    render(
      <KPICard
        title="Total Cost"
        value="$1,234.56"
        trend={5.2}
        icon={<span>💰</span>}
      />
    )

    expect(screen.getByText('Total Cost')).toBeInTheDocument()
    expect(screen.getByText('$1,234.56')).toBeInTheDocument()
  })

  it('displays positive trend correctly', () => {
    render(
      <KPICard
        title="Cost"
        value="$100"
        trend={5.2}
      />
    )

    expect(screen.getByText(/5.2%/)).toBeInTheDocument()
    // Check for up arrow or positive indicator
  })

  it('displays negative trend correctly', () => {
    render(
      <KPICard
        title="Cost"
        value="$100"
        trend={-3.5}
      />
    )

    expect(screen.getByText(/3.5%/)).toBeInTheDocument()
    // Check for down arrow or negative indicator
  })
})
```

#### 2.5. Test Cost Trend Chart

**File**: `frontend/src/components/dashboard/__tests__/CostTrendChart.test.tsx`
```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CostTrendChart } from '../CostTrendChart'

// Mock Recharts
vi.mock('recharts', () => ({
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}))

describe('CostTrendChart', () => {
  const mockData = [
    { date: '2024-01-01', cost: 100 },
    { date: '2024-01-02', cost: 120 },
    { date: '2024-01-03', cost: 110 },
  ]

  it('renders chart with data', () => {
    render(<CostTrendChart data={mockData} />)

    expect(screen.getByTestId('line-chart')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    render(<CostTrendChart data={[]} loading={true} />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })
})
```

### Day 5: Hook Tests

#### 2.6. Test useCostData Hook

**File**: `frontend/src/hooks/__tests__/useCostData.test.ts`
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useCostData } from '../useCostData'

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

describe('useCostData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches cost data successfully', async () => {
    const { result } = renderHook(
      () => useCostData({ startDate: '2024-01-01', endDate: '2024-01-31' }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toBeDefined()
  })

  it('handles errors correctly', async () => {
    // Mock API to return error
    const { result } = renderHook(
      () => useCostData({ startDate: 'invalid', endDate: 'invalid' }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })
  })
})
```

---

## Week 3: Integration & E2E Tests

### Day 1-2: Integration Tests

#### 3.1. Test Full API Flow

**File**: `backend/tests/test_integration/test_cost_flow.py`
```python
"""
Integration tests for cost data flow.
"""
import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
class TestCostFlow:
    """Test complete cost data flow."""

    def test_cost_data_retrieval_and_caching(
        self,
        client,
        db_session,
        redis_client,
        mock_cost_explorer
    ):
        """Test cost data is fetched, cached, and retrieved."""
        # First request - should fetch from AWS
        response1 = client.get("/api/v1/costs/summary")
        assert response1.status_code == 200

        # Second request - should use cache
        response2 = client.get("/api/v1/costs/summary")
        assert response2.status_code == 200
        assert response1.json() == response2.json()

        # Verify cache was used
        # Check redis_client for cached data
```

### Day 3-5: E2E Tests

#### 3.2. Setup Playwright

```bash
cd frontend
npm install -D @playwright/test
npx playwright install
```

#### 3.3. Playwright Configuration

**File**: `frontend/playwright.config.ts`
```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
})
```

#### 3.4. E2E Test - Dashboard Flow

**File**: `frontend/e2e/dashboard.spec.ts`
```typescript
import { test, expect } from '@playwright/test'

test.describe('Dashboard Flow', () => {
  test('user can view cost dashboard', async ({ page }) => {
    await page.goto('/')

    // Should redirect to dashboard
    await expect(page).toHaveURL(/dashboard/)

    // Should see KPI cards
    await expect(page.getByText('Total Cost')).toBeVisible()
    await expect(page.getByText('30-Day Trend')).toBeVisible()

    // Should see charts
    await expect(page.locator('[data-testid="cost-trend-chart"]')).toBeVisible()
  })

  test('user can filter by date range', async ({ page }) => {
    await page.goto('/dashboard')

    // Click date picker
    await page.getByRole('button', { name: /date range/i }).click()

    // Select last 7 days
    await page.getByText('Last 7 days').click()

    // Chart should update
    await expect(page.locator('[data-testid="cost-trend-chart"]')).toBeVisible()
  })

  test('user can select AWS profile', async ({ page }) => {
    await page.goto('/dashboard')

    // Click profile selector
    await page.getByRole('combobox', { name: /profile/i }).click()

    // Select a profile
    await page.getByText('Production').click()

    // Data should refresh
    await expect(page.getByText(/loading/i)).toBeVisible()
    await expect(page.getByText(/loading/i)).not.toBeVisible({ timeout: 10000 })
  })
})
```

---

## Performance Optimization

### 4.1. Cache TTL Optimization

Based on testing, optimize cache TTL values in `backend/app/core/cache_config.py`:

```python
CACHE_TTL_CONFIG = {
    "cost_summary_current_month": 300,      # 5 min
    "cost_summary_historical": 86400,       # 24 hours
    "cost_by_service": 900,                 # 15 min
    "forecast": 3600,                       # 1 hour
    "budget_status": 600,                   # 10 min
    "audit_results": 1800,                  # 30 min
}
```

### 4.2. Database Query Optimization

Add indices for frequently queried fields:

```sql
-- In Alembic migration
CREATE INDEX idx_budget_account ON budgets(account_id);
CREATE INDEX idx_kpi_timestamp ON kpis(timestamp);
CREATE INDEX idx_aws_account_active ON aws_accounts(is_active);
```

### 4.3. Bundle Optimization

Update `frontend/vite.config.ts`:

```typescript
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'chart-vendor': ['recharts'],
          'query-vendor': ['@tanstack/react-query'],
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
})
```

---

## Testing Commands

### Backend
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api/test_costs.py

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run excluding slow tests
pytest -m "not slow"
```

### Frontend
```bash
# Run all tests
npm run test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch

# Run E2E tests
npm run test:e2e

# Run E2E in UI mode
npm run test:e2e:ui
```

---

## Success Criteria

- ✅ Backend test coverage >80%
- ✅ Frontend test coverage >70%
- ✅ All critical paths covered by E2E tests
- ✅ CI/CD pipeline passes all tests
- ✅ Performance benchmarks met:
  - Dashboard loads <3 seconds
  - API responses <1 second (cached)
  - Cache hit rate >70%

---

## Next Steps After Testing

1. ✅ Deploy to staging environment
2. ✅ Run load tests (k6 or Locust)
3. ✅ Security audit
4. ✅ Documentation review
5. ✅ Production deployment

---

**Status**: Ready to implement
**Priority**: Critical for production readiness
**Estimated Effort**: 2-3 weeks
