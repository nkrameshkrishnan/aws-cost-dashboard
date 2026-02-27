# Testing Guide - AWS Cost Dashboard

## Quick Start

The API router has been configured and authentication temporarily disabled for testing. Follow these steps to test the dashboard:

### 1. Restart the Backend

The backend needs to be restarted to pick up the new router configuration:

```bash
cd aws-cost-dashboard
docker-compose restart backend
```

Or if running without Docker:
```bash
cd backend
# Kill the running process (Ctrl+C)
uvicorn app.main:app --reload
```

### 2. Verify Backend is Running

Check the API is accessible:

```bash
curl http://localhost:8000/
```

Expected response:
```json
{
  "name": "AWS Cost Dashboard",
  "version": "1.0.0",
  "status": "running",
  "environment": "development"
}
```

### 3. Check API Documentation

Visit http://localhost:8000/docs to see the Swagger UI with all available endpoints.

You should see:
- `/api/v1/costs/summary`
- `/api/v1/costs/daily`
- `/api/v1/costs/by-service`
- `/api/v1/costs/trend`
- `/api/v1/costs/mom-comparison`
- `/api/v1/costs/forecast`
- `/api/v1/costs/multi-profile`

### 4. Test a Cost Endpoint

Test the API directly:

```bash
curl "http://localhost:8000/api/v1/costs/summary?profile_name=default&start_date=2025-12-01&end_date=2025-12-31"
```

Expected response (if AWS credentials are configured):
```json
{
  "profile_name": "default",
  "start_date": "2025-12-01",
  "end_date": "2025-12-31",
  "total_cost": 1234.56,
  "currency": "USD",
  "period_count": 1
}
```

### 5. Access the Frontend

Open http://localhost:5173 in your browser.

The dashboard should now:
- Load without 404 errors
- Show real AWS cost data (if credentials configured)
- Display interactive charts
- Allow profile switching

## Troubleshooting

### Still Getting 404 Errors

1. **Check backend logs:**
```bash
docker-compose logs backend
```

Look for:
- Router registration confirmation
- Any import errors
- AWS credential issues

2. **Verify frontend is calling correct URL:**
- Open browser DevTools (F12)
- Go to Network tab
- Check API calls are going to `http://localhost:8000/api/v1/costs/*`

### AWS Credential Errors

If you see errors like "NoCredentialsError" or "ProfileNotFound":

1. **Check AWS credentials exist:**
```bash
cat ~/.aws/credentials
```

2. **Verify profile name:**
The default profile is "default". If you have a different profile name, update the frontend selector.

3. **Test AWS CLI:**
```bash
aws sts get-caller-identity --profile default
```

4. **Check IAM permissions:**
Ensure your AWS user has Cost Explorer permissions (see README.md).

### No Cost Data Available

If the API works but shows $0.00:

1. **Cost Explorer may not have data for the date range**
   - Try a different date range with known costs
   - Cost data typically has a 24-48 hour delay

2. **Cost Explorer may not be enabled**
   - Enable Cost Explorer in AWS Console
   - Wait 24 hours for data to appear

3. **Check the correct AWS account**
   - Verify you're using the right profile
   - Check account ID matches expected account

### Backend Won't Start

If you see import errors:

1. **Reinstall dependencies:**
```bash
cd backend
pip install -r requirements.txt
```

2. **Check Python version:**
```bash
python --version  # Should be 3.11+
```

3. **Verify all __init__.py files exist:**
```bash
find app -type d -exec ls {}/__init__.py \; 2>/dev/null
```

## What Changed

To fix the 404 error, the following files were created/modified:

1. **Created:** `backend/app/api/v1/router.py`
   - Aggregates all v1 endpoints
   - Registers costs router with `/costs` prefix

2. **Modified:** `backend/app/main.py`
   - Imported and registered API router
   - Endpoints now accessible at `/api/v1/*`

3. **Modified:** `backend/app/api/v1/endpoints/costs.py`
   - Temporarily disabled authentication for testing
   - Endpoints now work without JWT tokens

## Next Steps

Once you verify the cost data is working:

1. **Re-enable Authentication** (Phase 1 completion)
   - Implement user registration/login endpoints
   - Uncomment authentication dependencies
   - Update frontend to handle login

2. **Continue with Phase 3: Budget Tracking**
   - AWS Budgets API integration
   - Budget vs actual visualizations

3. **Test with Multiple Profiles**
   - Add more AWS profiles to `~/.aws/credentials`
   - Use ProfileSelector to switch between accounts

## Testing Checklist

- [ ] Backend starts without errors
- [ ] `/health` endpoint returns `{"status": "healthy"}`
- [ ] API docs accessible at `/docs`
- [ ] Cost summary endpoint returns data
- [ ] Frontend loads without console errors
- [ ] KPI cards show real cost values
- [ ] Cost trend chart displays line graph
- [ ] Service breakdown pie chart renders
- [ ] Profile selector works
- [ ] Can switch between profiles (if multiple configured)

## Need Help?

If you're still having issues:

1. Check the main [README.md](README.md) for setup instructions
2. Review backend logs: `docker-compose logs -f backend`
3. Check frontend console: Browser DevTools → Console
4. Verify AWS credentials: `aws configure list`
5. Test Cost Explorer access manually via AWS CLI

---

**Note:** Authentication is currently disabled for testing. In production, you should re-enable it by uncommenting the `current_user` dependencies in the costs endpoints and implementing proper login/registration flows.
