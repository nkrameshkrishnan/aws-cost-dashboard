# Quick Diagnostic Guide

You're getting a 500 error. Let's diagnose the issue step by step.

## Step 1: Restart the Backend

The config has been updated with default values. Restart the backend:

```bash
cd aws-cost-dashboard
docker-compose restart backend
```

Wait 10 seconds for it to fully start, then check logs:

```bash
docker-compose logs backend | tail -20
```

Look for:
- ✅ "Starting AWS Cost Dashboard v1.0.0"
- ✅ "Application startup complete"
- ❌ Any error messages

## Step 2: Check System Status

Test the new health endpoint:

```bash
curl http://localhost:8000/api/v1/health/status
```

This will show:
- **AWS**: Are profiles detected?
- **Cache**: Is Redis connected?

Expected response:
```json
{
  "app": {
    "name": "AWS Cost Dashboard",
    "version": "1.0.0",
    "environment": "development"
  },
  "aws": {
    "configured": true,
    "profiles": ["default"],
    "error": null
  },
  "cache": {
    "connected": true,
    "stats": {...}
  }
}
```

### Common Issues & Fixes

**Issue: `"aws": {"configured": false, "error": "..."}`**

Fix: AWS credentials not configured
```bash
# Check if credentials file exists
ls -la ~/.aws/credentials

# If not, configure AWS CLI
aws configure
```

**Issue: `"cache": {"connected": false, "error": "..."}`**

Fix: Redis not running
```bash
# Check Redis container
docker-compose ps redis

# If not running, start it
docker-compose up -d redis
```

## Step 3: Test AWS Profile

If AWS shows as configured, test your default profile:

```bash
curl http://localhost:8000/api/v1/health/test-aws/default
```

Expected response:
```json
{
  "status": "success",
  "profile": "default",
  "account_id": "123456789012",
  "user_id": "AIDAI...",
  "arn": "arn:aws:iam::123456789012:user/yourname"
}
```

**If this fails:**
- Your AWS credentials may be invalid
- IAM user may not have permissions
- Profile name may be wrong

## Step 4: Test Cost Endpoint

If AWS profile test passes, try a cost query:

```bash
curl "http://localhost:8000/api/v1/costs/summary?profile_name=default&start_date=2026-01-01&end_date=2026-01-31"
```

**Possible responses:**

✅ **Success:**
```json
{
  "profile_name": "default",
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "total_cost": 0.0,
  "currency": "USD",
  "period_count": 1
}
```

❌ **AWS Permission Error:**
```json
{
  "detail": "An error occurred (AccessDeniedException) when calling the GetCostAndUsage operation: User: arn:aws:iam::... is not authorized to perform: ce:GetCostAndUsage"
}
```

**Fix:** Add Cost Explorer permissions to your IAM user (see README.md)

❌ **Cost Explorer Not Enabled:**
```json
{
  "detail": "Cost Explorer has not been enabled for this account"
}
```

**Fix:** Enable Cost Explorer in AWS Console:
1. Go to AWS Cost Management
2. Click "Cost Explorer"
3. Click "Enable Cost Explorer"
4. Wait 24 hours for data

## Step 5: Check Frontend

Once the backend is working, refresh your frontend:

```bash
# Open browser
open http://localhost:5173
```

Check browser console (F12):
- ✅ No errors
- ✅ API calls succeed (Network tab)
- ❌ Still errors? Clear cache and hard reload (Cmd+Shift+R)

## Quick Checklist

Run these commands in order:

```bash
# 1. Restart backend
docker-compose restart backend

# 2. Check system status
curl http://localhost:8000/api/v1/health/status

# 3. Test AWS profile
curl http://localhost:8000/api/v1/health/test-aws/default

# 4. Test cost endpoint
curl "http://localhost:8000/api/v1/costs/summary?profile_name=default&start_date=2026-01-01&end_date=2026-01-31"

# 5. Check frontend
open http://localhost:5173
```

## Still Having Issues?

### View Full Backend Logs

```bash
docker-compose logs -f backend
```

Look for the specific error message when you try to load the dashboard.

### Common Error Messages

**"NoCredentialsError"**
- AWS credentials not found
- Run: `aws configure`

**"ProfileNotFound: default"**
- Profile doesn't exist in ~/.aws/credentials
- Check: `cat ~/.aws/credentials`
- Or use a different profile name

**"AccessDeniedException"**
- IAM user lacks permissions
- Add Cost Explorer policy (see README.md)

**"Connection refused" (Redis)**
- Redis container not running
- Run: `docker-compose up -d redis`

**"pydantic_core._pydantic_core.ValidationError"**
- Environment variable missing
- This should be fixed now with default values

## What Changed

I've made these fixes:

1. **Added Health Endpoints:**
   - `/api/v1/health/status` - System status check
   - `/api/v1/health/test-aws/{profile}` - Test AWS connectivity

2. **Updated Config:**
   - Made SECRET_KEY, JWT_SECRET_KEY, and DATABASE_URL optional
   - Set development defaults
   - No .env file required for basic testing

3. **Better Error Messages:**
   - More detailed error responses
   - Logging for debugging

## Next Steps

Once you get past the 500 error and see cost data:

1. **Verify Charts Load:**
   - KPI cards show real values
   - Line chart renders
   - Pie chart shows services

2. **Test Profile Switching:**
   - If you have multiple AWS profiles
   - Use the dropdown in top-right

3. **Ready for Phase 3:**
   - Budget Tracking
   - FinOps Audits
   - Advanced features

---

**Need More Help?**

Share the output of:
```bash
curl http://localhost:8000/api/v1/health/status
docker-compose logs backend | tail -50
```
