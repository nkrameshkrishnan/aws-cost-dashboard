# Testing Phase 2 Audit Types

## Backend Changes
The following new audit types have been implemented:
- **RDS**: Idle instances, stopped instances, old snapshots
- **Lambda**: Unused functions, over-provisioned functions
- **S3**: Buckets without lifecycle policies, incomplete multipart uploads
- **Load Balancers**: LBs with no targets, low-traffic LBs

## How to Test

### 1. Start Backend
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --reload
```

### 2. Start Frontend
```bash
cd frontend
npm run dev
```

### 3. Run Audit Test

1. Navigate to: http://localhost:5173/finops-audit
2. Click "Run Audit" button
3. Wait for audit to complete (should take 15-30 seconds with caching)
4. Open browser console (F12 > Console tab)
5. Check for console logs showing new audit results

### 4. Verify Results in Console

You should see logs like:
```
=== AUDIT RESULTS ===
RDS Audit: { idle_instances: [...], stopped_instances: [...], old_snapshots: [...], ... }
Lambda Audit: { unused_functions: [...], over_provisioned_functions: [...], ... }
S3 Audit: { buckets_without_lifecycle: [...], incomplete_multipart_uploads: [...], ... }
Load Balancer Audit: { lbs_no_targets: [...], lbs_low_traffic: [...], ... }
Summary: { total_findings: X, total_potential_savings: $XXX, ... }
```

### 5. Check Backend Logs

In the backend terminal, you should see:
```
INFO: Scanning X regions in parallel with Y workers
INFO: Scanning region: us-east-1
INFO: Scanning region: us-west-2
...
INFO: Completed scanning region: us-east-1
INFO: Audit complete across X region(s). Total findings: X, Potential savings: $X/month
```

### 6. Verify Caching

Run the audit again - it should complete in <1 second:
```
INFO: Cache hit for audit: <your-account-name>
```

## Expected Behavior

### First Run (No Cache)
- Duration: 15-30 seconds (depends on number of regions and resources)
- Scans all enabled AWS regions in parallel
- Checks EC2, EBS, EIP, RDS, Lambda, S3, Load Balancers, and tagging compliance

### Second Run (Cached)
- Duration: <1 second
- Returns cached results (30-minute TTL)
- Backend log shows "Cache hit"

## What to Look For

### ✅ Success Indicators
- No errors in browser console
- Audit completes successfully
- New audit types appear in console logs
- Summary includes all new categories
- Caching works on second run

### ❌ Potential Issues
- **404 errors**: Check backend is running
- **500 errors**: Check AWS credentials are valid
- **Empty results**: Check AWS account has resources
- **Timeout**: Check AWS API rate limits

## Troubleshooting

### No RDS/Lambda/S3/LB Results?
This is normal if your AWS account doesn't have:
- Any RDS instances
- Lambda functions
- S3 buckets
- Load Balancers

The audit will still work and show empty arrays for these types.

### Backend Errors
Check backend logs for specific error messages:
- **Credential errors**: AWS credentials not configured correctly
- **Permission errors**: IAM permissions missing (see README for required permissions)
- **Region errors**: Some regions may not be enabled in your account

### Performance Issues
- First run with many resources: 30-60 seconds is normal
- Parallel scanning uses 10 workers max
- Check backend logs for "Scanning region" messages

## Next Steps

Once testing is successful:
1. Update frontend UI to display new audit types
2. Add pagination to all tables
3. Add filtering/sorting for new audit types
4. Update summary cards to include new types

## AWS IAM Permissions Required

Make sure your AWS credentials have these permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBSnapshots",
        "lambda:ListFunctions",
        "lambda:ListTags",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLifecycleConfiguration",
        "s3:ListBucketMultipartUploads",
        "s3:GetBucketLocation",
        "s3:GetBucketTagging",
        "s3:ListBucket",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:DescribeTags",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```
