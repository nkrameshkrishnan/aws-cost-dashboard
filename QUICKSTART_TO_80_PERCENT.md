# Quick Start Guide: Reach 80% Test Coverage

**Current**: 84/128 (66%)
**Target**: 103/128 (80%)
**Needed**: 19 tests

---

## 🚀 Fast Path (1 Hour)

### Step 1: Fix test_costs.py (16 tests) - 30 minutes

**Issue**: Mocking `@staticmethod` incorrectly

**Fix**: Change from `patch('module.Class')` to `patch.object(Class, 'method')`

```python
# ❌ Current (doesn't work)
with patch('app.api.v1.endpoints.costs.DatabaseCostProcessor') as mock_processor:
    mock_processor.get_cost_summary.return_value = {...}

# ✅ Correct
from unittest.mock import patch
from app.services.cost_processor_db import DatabaseCostProcessor

with patch.object(DatabaseCostProcessor, 'get_cost_summary', return_value={...}):
    response = client.get("/api/v1/costs/summary?...")
    assert response.status_code == 200
```

**File**: `backend/tests/test_api/test_costs.py`

**Apply this pattern to all 16 tests**:
- test_get_cost_summary
- test_get_cost_summary_with_date_range
- test_get_daily_costs
- test_get_costs_by_service
- test_get_cost_forecast
- test_get_cost_trend
- test_get_mom_comparison
- test_get_dashboard_data
- test_large_date_range_performance
- test_multi_profile_costs
- (plus 6 validation tests that already pass)

**Run tests**:
```bash
cd backend
source venv/bin/activate
pytest tests/test_api/test_costs.py -v
```

**Expected**: 16/16 passing → **100/128 total (78%)**

---

### Step 2: Fix 3 tests from test_budgets.py - 15 minutes

**Read the budget endpoints first**:
```bash
cat backend/app/api/v1/endpoints/budgets.py
```

**Then update 3 simplest tests**:

1. **test_list_budgets** - GET /api/v1/budgets
2. **test_get_budget_status** - GET /api/v1/budgets/{id}/status
3. **test_create_budget** - POST /api/v1/budgets

**Pattern** (same as costs):
```python
from app.services.budget_service import BudgetService

def test_list_budgets(client):
    with patch.object(BudgetService, 'get_all_budgets', return_value=[]):
        response = client.get("/api/v1/budgets?profile_name=default")
        assert response.status_code == 200
```

**Run tests**:
```bash
pytest tests/test_api/test_budgets.py -v -k "list_budgets or get_budget_status or create_budget"
```

**Expected**: 3/3 passing → **103/128 total (80%+)** ✅

---

## Alternative: Fix test_cost_explorer.py (12 tests)

If budgets are complex, fix AWS service tests instead:

**File**: `backend/tests/test_aws/test_cost_explorer.py`

**Pattern**: Use moto to mock boto3
```python
from moto import mock_ce
import boto3

@mock_ce
def test_get_cost_and_usage():
    # Moto automatically mocks boto3.client('ce')
    client = boto3.client('ce', region_name='us-east-1')
    response = client.get_cost_and_usage(...)
    assert response
```

**Run tests**:
```bash
pytest tests/test_aws/test_cost_explorer.py -v
```

**Expected**: 12/12 passing → **96/128 total (75%)**
Then need 7 more from budgets → **103/128 (80%)**

---

## Quick Commands Reference

### Check current status:
```bash
cd backend
source venv/bin/activate
pytest --co -q | tail -5
```

### Run all tests:
```bash
pytest tests/ -v --tb=line | grep -E "PASSED|FAILED|passed|failed"
```

### Run specific file:
```bash
pytest tests/test_api/test_costs.py -v
```

### Run with coverage:
```bash
pytest tests/ --cov=app --cov-report=term-missing
```

### Frontend tests:
```bash
cd ../frontend
npm test -- --run
```

---

## Checklist

- [ ] Step 1: Update test_costs.py with `patch.object()` pattern
- [ ] Run: `pytest tests/test_api/test_costs.py -v`
- [ ] Verify: 16/16 tests pass
- [ ] Step 2: Read budgets endpoints
- [ ] Update 3 budget tests
- [ ] Run: `pytest tests/test_api/test_budgets.py -v`
- [ ] Verify: 3+ tests pass
- [ ] Run all tests: `pytest tests/ -v`
- [ ] Confirm: **103+/128 (80%+)** ✅

---

## Success Criteria

✅ 103/128 tests passing (80% coverage)
✅ All frontend tests still passing (60/60)
✅ Backend tests at 43/68 (63%)
✅ Zero regressions

---

**Estimated Total Time**: 45-60 minutes
**Difficulty**: Medium (requires understanding Python mocking)
**Blocker**: None (all information available)

**Go forth and conquer! 🚀**
