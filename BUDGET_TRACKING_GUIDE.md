# Budget Tracking - User Guide

## Overview

The AWS Cost Dashboard now includes comprehensive budget tracking features! You can now:
- ✅ Create monthly, quarterly, or yearly budgets for each AWS account
- ✅ Monitor actual spending vs budgeted amounts in real-time
- ✅ Get visual alerts when budgets reach warning/critical thresholds
- ✅ See spending projections to forecast budget overruns
- ✅ View budget summary on the dashboard

---

## Quick Start

### 1. Navigate to Budget Management

From the dashboard, click **"Manage Budgets"** in the Budget Overview section, or navigate to:
**http://localhost:5173/budgets**

### 2. Create Your First Budget

Click **"Create Budget"** and fill in the form:

**Required Fields:**
- **Budget Name**: Descriptive name (e.g., "February Production Budget")
- **AWS Account**: Select the account to track
- **Budget Amount**: Total budget in USD (e.g., 5000)
- **Period**: Monthly, Quarterly, or Yearly
- **Start Date**: When the budget period begins

**Optional Thresholds:**
- **Warning Threshold**: Default 80% - triggers yellow warning
- **Critical Threshold**: Default 100% - triggers orange/red alert

**Example:**
```
Budget Name: Production - February 2026
AWS Account: KloudKatana
Budget Amount: $5,000
Period: Monthly
Start Date: 2026-02-01
Warning Threshold: 80%
Critical Threshold: 100%
```

### 3. Monitor Budget Status

Once created, the budget card displays:
- **Current Spend**: Actual costs incurred so far
- **Progress Bar**: Visual representation with color-coded alerts
  - 🟢 Green: Under 80% (Normal)
  - 🟡 Yellow: 80-100% (Warning)
  - 🟠 Orange: Over 100% (Critical)
  - 🔴 Red: Exceeded budget
- **Remaining**: Amount left in budget
- **Days Left**: Days until budget period ends (if end date set)
- **Projection**: Estimated total spend based on current trend

---

## Features in Detail

### Budget Alert Levels

The system automatically calculates alert levels based on spending:

| Alert Level | Condition | Color | Icon |
|-------------|-----------|-------|------|
| **Normal** | < 80% used | Green | ✓ |
| **Warning** | ≥ 80% used | Yellow | ⚠ |
| **Critical** | ≥ 100% used | Orange | ⚠ |
| **Exceeded** | > 100% used | Red | ⚠ |

### Spending Projections

If your budget has an end date, the system calculates a linear projection:
- Tracks daily average spending
- Estimates total spend by end date
- Shows warning if projected to exceed budget

**Example:**
```
Budget: $5,000 for February (28 days)
Current Spend (Day 10): $2,000
Daily Average: $200
Projected Total: $5,600
Status: ⚠ Projected to exceed budget by $600
```

### Budget Summary Dashboard

The main dashboard shows a budget overview if you have active budgets:
- **Total Budget**: Sum of all active budgets
- **Current Spend**: Total spending across all budgets
- **Progress Bar**: Overall budget health
- **Alerts Count**: Number of budgets at each alert level

---

## Budget Periods

### Monthly Budget
- Tracks spending for a specific month
- Most common use case
- Resets each month (create new budget or use recurring)

### Quarterly Budget
- Tracks spending over 3 months
- Good for projects with longer cycles
- Example: Q1 2026 (Jan-Mar)

### Yearly Budget
- Annual spending limit
- Good for overall cost control
- Example: FY2026 budget

---

## API Endpoints

The budget system provides REST API access:

### Create Budget
```bash
POST /api/v1/budgets/
Content-Type: application/json

{
  "name": "Production Budget",
  "aws_account_id": 1,
  "amount": 5000,
  "period": "monthly",
  "start_date": "2026-02-01",
  "threshold_warning": 80,
  "threshold_critical": 100
}
```

### List Budgets
```bash
GET /api/v1/budgets/
GET /api/v1/budgets/?aws_account_id=1
GET /api/v1/budgets/?active_only=true
```

### Get Budget Status
```bash
GET /api/v1/budgets/{budget_id}/status
```

Response includes:
- Current spending
- Percentage used
- Alert level
- Projection data

### Get Budget Summary
```bash
GET /api/v1/budgets/summary
GET /api/v1/budgets/summary?aws_account_id=1
```

### Update Budget
```bash
PUT /api/v1/budgets/{budget_id}
Content-Type: application/json

{
  "amount": 6000,
  "threshold_warning": 85
}
```

### Delete Budget
```bash
DELETE /api/v1/budgets/{budget_id}
```

---

## Database Schema

Budgets are stored in PostgreSQL:

```sql
CREATE TABLE budgets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    aws_account_id INTEGER REFERENCES aws_accounts(id) ON DELETE CASCADE,
    amount FLOAT NOT NULL,
    period VARCHAR(20) NOT NULL, -- 'monthly', 'quarterly', 'yearly'
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    threshold_warning FLOAT DEFAULT 80.0,
    threshold_critical FLOAT DEFAULT 100.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

---

## Best Practices

### 1. Set Realistic Budgets
- Review historical spending patterns first
- Add 10-15% buffer for unexpected costs
- Adjust thresholds based on your risk tolerance

### 2. Use Warning Thresholds Wisely
- **80%**: Good default for early warning
- **90%**: For tighter control
- **70%**: For very strict budgets

### 3. Monthly Budgets for Predictable Workloads
- Production environments
- Steady-state applications
- Regular development costs

### 4. Quarterly Budgets for Projects
- New product launches
- Migration projects
- Seasonal workloads

### 5. Monitor Projections
- Check "projected to exceed" warnings
- Take action early to avoid overruns
- Optimize resources when trending high

### 6. Set End Dates for Fixed Budgets
- Project-based budgets
- Trial periods
- Temporary environments

### 7. Keep Budgets Active
- Inactive budgets don't show in dashboard
- Deactivate completed budgets
- Delete budgets you no longer need

---

## Troubleshooting

### Budget shows $0.00 spending
**Cause**: No cost data available for the period
**Solution**:
- Ensure AWS account has Cost Explorer permissions
- Check that costs have been incurred
- Verify start date is not in the future

### Budget not showing on dashboard
**Cause**: Budget is inactive or deleted
**Solution**:
- Go to /budgets and check budget status
- Ensure "is_active" is true
- Create a new budget if needed

### Projection not displaying
**Cause**: Budget has no end date
**Solution**:
- Add an end date to the budget
- Or accept that ongoing budgets don't show projections

### Alert level incorrect
**Cause**: Thresholds may need adjustment
**Solution**:
- Edit budget and adjust warning/critical thresholds
- Default is 80% warning, 100% critical

---

## Example Scenarios

### Scenario 1: Monthly Production Budget
```
Name: Production Environment - February
Account: Production AWS Account
Amount: $10,000
Period: Monthly
Start Date: 2026-02-01
End Date: 2026-02-28
Warning: 80% ($8,000)
Critical: 100% ($10,000)
```

**Use Case**: Monitor monthly production costs, get alerted at $8k

### Scenario 2: Project Budget
```
Name: Data Migration Project
Account: Development Account
Amount: $15,000
Period: Quarterly
Start Date: 2026-01-01
End Date: 2026-03-31
Warning: 75% ($11,250)
Critical: 90% ($13,500)
```

**Use Case**: Track project spending over 3 months with early warnings

### Scenario 3: Ongoing Development
```
Name: Dev Environment
Account: Dev Account
Amount: $2,000
Period: Monthly
Start Date: 2026-02-01
End Date: (none - ongoing)
Warning: 85%
Critical: 100%
```

**Use Case**: Recurring monthly budget with no end date

---

## What's Next?

Budget tracking is **Phase 3** complete! Coming next:

**Phase 4: FinOps Audits** - Identify cost waste:
- Idle EC2 instances
- Unattached EBS volumes
- Unattached Elastic IPs
- Untagged resources
- Savings recommendations

**Phase 5: Forecasting** - Advanced predictions
**Phase 6: Export & Reporting** - PDF, CSV, Excel reports
**Phase 7: Microsoft Teams Integration** - Budget alerts to Teams

---

## Need Help?

**View Budget API Docs**: http://localhost:8000/docs#/budgets
**Backend Logs**: `docker-compose logs backend`
**Frontend Logs**: Browser console (F12)

**Common Issues**:
- **500 errors**: Check backend logs for AWS permission issues
- **Empty budget list**: Create your first budget
- **No alerts**: Check if budgets are active and have spending data

---

**Congratulations!** You now have full budget tracking capabilities. Set budgets, monitor spending, and get alerted before costs spiral out of control! 🎉
