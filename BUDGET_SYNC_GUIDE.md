# Budget Sync from AWS - Quick Guide

## What Changed

I've added two improvements to the budget system:

### 1. ✅ "Budgets" Button Always Visible
The **"Budgets"** button is now always visible in the dashboard header (next to "Accounts"), so you can access budget management anytime.

### 2. ✅ AWS Budgets Integration
You can now import budgets from AWS Billing and Cost Management console directly into the dashboard!

---

## How to Use

### Access Budget Management

**From Dashboard:**
- Click the **"Budgets"** button in the top-right header

**Direct URL:**
- Navigate to: http://localhost:5173/budgets

---

## Import Budgets from AWS Console

If you have budgets configured in AWS Billing and Cost Management, you can import them:

### Step 1: Navigate to Budget Management
Go to http://localhost:5173/budgets

### Step 2: Find the "Import Budgets from AWS" Section
You'll see a blue highlighted section at the top with a sync icon.

### Step 3: Select AWS Account
Choose the AWS account from the dropdown (e.g., "KloudKatana")

### Step 4: Click "Sync from AWS"
The system will:
1. Connect to AWS Budgets API
2. Fetch all budgets configured in AWS console
3. Import them into the dashboard database
4. Show a summary: "Found X, Imported Y, Skipped Z"

### Step 5: Choose Overwrite Option
When syncing, you'll be asked:
- **OK (Yes)**: Overwrite existing budgets with the same name
- **Cancel (No)**: Skip budgets that already exist in the database

---

## What Gets Imported

From each AWS Budget, the system imports:
- **Budget Name**: The name you gave it in AWS console
- **Budget Amount**: The dollar limit
- **Period**: Monthly, Quarterly, or Yearly
- **Start/End Dates**: Budget time period
- **Thresholds**: Warning and critical alert levels (from notification settings)
- **Description**: Auto-generated noting it was imported from AWS

---

## Required AWS Permissions

Your AWS IAM user needs these permissions to sync budgets:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "budgets:DescribeBudgets",
        "budgets:ViewBudget"
      ],
      "Resource": "*"
    }
  ]
}
```

**Note**: The `ce:GetCostAndUsage` permission you already added covers cost data, but budgets require the `budgets:*` permissions.

---

## API Endpoints

### Sync Budgets from AWS
```bash
POST /api/v1/budgets/sync-from-aws?account_name=KloudKatana&overwrite=false
```

**Response:**
```json
{
  "total_found": 3,
  "imported": 2,
  "updated": 0,
  "skipped": 1,
  "errors": []
}
```

### Preview AWS Budgets (without importing)
```bash
GET /api/v1/budgets/from-aws/KloudKatana
```

**Response:**
```json
{
  "account_name": "KloudKatana",
  "budgets_count": 3,
  "budgets": [...]
}
```

---

## Example: Creating a Budget in AWS Console

If you want to test this feature but don't have budgets in AWS:

### Via AWS Console:
1. Go to AWS Console → Billing and Cost Management → Budgets
2. Click **"Create budget"**
3. Choose **"Cost budget"**
4. Set amount (e.g., $1,000)
5. Set period (Monthly)
6. Configure alerts (optional)
7. Click **"Create budget"**

### Then Sync to Dashboard:
1. Go to http://localhost:5173/budgets
2. Select your AWS account
3. Click **"Sync from AWS"**
4. Your AWS budget will appear in the dashboard!

---

## Troubleshooting

### "Access Denied" Error When Syncing
**Cause**: Missing AWS Budgets permissions

**Solution**: Add these IAM permissions:
```bash
aws iam attach-user-policy \
  --user-name your-iam-user \
  --policy-arn arn:aws:iam::aws:policy/AWSBudgetsReadOnlyAccess
```

Or create a custom policy with `budgets:DescribeBudgets` and `budgets:ViewBudget`.

### "Account ID Missing" Error
**Cause**: AWS account hasn't been validated

**Solution**:
1. Go to http://localhost:5173/aws-accounts
2. Delete and re-add your AWS account
3. Ensure credentials are valid
4. The system will validate and store the account ID

### No Budgets Found
**Cause**: No budgets configured in AWS console for this account

**Solution**: Create a budget in AWS Billing and Cost Management console first.

### Sync Shows "Skipped: 3"
**Cause**: Budgets with those names already exist in the database

**Solution**:
- If you want to update them, sync again and click **OK** when asked about overwriting
- Or delete the existing budgets first, then sync

---

## How Budget Import Works

```
User clicks "Sync from AWS"
    ↓
Frontend sends POST /budgets/sync-from-aws
    ↓
Backend connects to AWS Budgets API
    ↓
Fetches all budgets for the account
    ↓
For each budget:
  - Parse name, amount, period, dates
  - Extract notification thresholds
  - Check if budget exists in database
    - If exists and overwrite=true → Update it
    - If exists and overwrite=false → Skip it
    - If new → Create it
    ↓
Return summary to frontend
    ↓
Dashboard refreshes and shows imported budgets
```

---

## Benefits

### ✅ Single Source of Truth
- Configure budgets once in AWS console
- Import to dashboard for visualization
- No need to manually recreate budgets

### ✅ Existing Budgets Integration
- Already have budgets in AWS? Import them!
- Keep using AWS console for budget management
- Dashboard provides better visualization

### ✅ Hybrid Approach
- Import AWS budgets for organization-wide limits
- Create custom budgets in dashboard for specific tracking
- Both work together seamlessly

---

## Next Steps

1. **Check AWS Console**: See if you have any budgets at https://console.aws.amazon.com/billing/home#/budgets

2. **Add IAM Permissions**: Ensure your IAM user has `budgets:DescribeBudgets` permission

3. **Sync Budgets**: Click "Sync from AWS" in the dashboard

4. **Monitor**: Both imported and manually created budgets appear together

5. **Create More**: Use either AWS console or dashboard to create new budgets

---

## Summary

**What You Can Do Now:**
- ✅ Click "Budgets" button anytime from dashboard
- ✅ Import budgets from AWS Billing and Cost Management
- ✅ View AWS budgets alongside custom dashboard budgets
- ✅ Track spending against both AWS and custom budgets
- ✅ Get alerts when any budget threshold is reached

**Dashboard Location**: http://localhost:5173/budgets

**AWS Console Budgets**: https://console.aws.amazon.com/billing/home#/budgets

Enjoy seamless budget integration! 🎉
