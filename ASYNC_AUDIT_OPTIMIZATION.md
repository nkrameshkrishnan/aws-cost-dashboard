# AWS FinOps Audit - Async Optimization Implementation

## Overview

This document describes the async audit optimization system that enables progressive loading, incremental processing, and improved user experience for AWS FinOps audits.

---

## Implementation Status

### ✅ Completed

1. **Backend Job Storage System**
   - Created `backend/app/core/job_storage.py`
   - Thread-safe in-memory job storage
   - Supports job CRUD operations
   - Auto-cleanup of old jobs (24h TTL)
   - Can be upgraded to Redis for production

2. **Enhanced Audit Job Schema**
   - Updated `AuditJobStatus` in `backend/app/schemas/audit.py`
   - Added fields: `progress`, `current_step`, `partial_results`
   - Full status tracking from creation to completion

3. **Async API Endpoints**
   - Added to `backend/app/api/v1/endpoints/finops.py`:
     - `POST /audit/async` - Start async audit, return job ID (202 Accepted)
     - `GET /audit/status/{job_id}` - Poll job status and progress
     - `GET /audit/results/{job_id}` - Get complete results when ready
     - `GET /audit/jobs` - List recent audit jobs
   - Background thread execution with threading module

### 🚧 In Progress

4. **Audit Service Progress Tracking**
   - Modify `run_full_audit()` to accept optional `job_id`
   - Report progress during region scanning
   - Update partial results as each audit type completes
   - Calculate progress percentage based on:
     - Number of regions scanned
     - Number of audit types completed per region

### 📋 Todo

5. **Frontend Progressive Loading**
   - Update `FinOpsAudit.tsx` to use async endpoints
   - Implement polling mechanism (2-3 second intervals)
   - Show progress bar and current step
   - Display partial results as they arrive
   - Update UI incrementally

6. **Progress Indicators**
   - Show loading skeleton while audit initializes
   - Display progress bar with percentage
   - Show current step (e.g., "Scanning us-east-1...")
   - Animate audit cards as results arrive

7. **Result Caching**
   - Cache results in localStorage
   - Show cached data while refreshing
   - Indicate data freshness/age

---

## Architecture

### Backend Flow

```
1. User clicks "Run Audit"
   ↓
2. POST /audit/async
   - Create job in job_storage
   - Start background thread
   - Return job_id immediately (202 Accepted)
   ↓
3. Background Thread:
   - Update status to 'running'
   - Scan regions in parallel (ThreadPoolExecutor)
   - Report progress after each region
   - Update partial_results as audits complete
   - Set final results when complete
   ↓
4. Frontend Polls:
   - GET /audit/status/{job_id} (every 2s)
   - Check progress and status
   - Display partial results
   ↓
5. Audit Complete:
   - GET /audit/results/{job_id}
   - Display final results
```

### Frontend Flow

```
1. User Interface Loads:
   - Show audit UI skeleton immediately
   - Check localStorage for cached results
   - Display cached data with age indicator
   ↓
2. Start Async Audit:
   - POST /audit/async → job_id
   - Start polling timer (every 2s)
   - Show progress bar
   ↓
3. Poll for Updates:
   - GET /audit/status/{job_id}
   - Update progress bar
   - Display current step
   - Show partial results incrementally
   ↓
4. Results Complete:
   - GET /audit/results/{job_id}
   - Display all findings
   - Cache results in localStorage
   - Stop polling
```

---

## API Endpoints

### POST /api/v1/finops/audit/async
Start an async audit job.

**Request:**
```json
{
  "account_name": "production",
  "audit_types": ["ec2", "ebs", "rds", ...],
  "regions": []  // Empty = all regions
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "a1b2c3d4-e5f6-...",
  "status": "pending",
  "message": "Audit job started",
  "status_url": "/api/v1/finops/audit/status/a1b2c3d4-e5f6-...",
  "results_url": "/api/v1/finops/audit/results/a1b2c3d4-e5f6-..."
}
```

### GET /api/v1/finops/audit/status/{job_id}
Poll job status and progress.

**Response:**
```json
{
  "job_id": "a1b2c3d4-e5f6-...",
  "account_name": "production",
  "audit_types": ["ec2", "ebs", ...],
  "status": "running",  // pending, running, completed, failed
  "progress": 45,  // 0-100
  "current_step": "Scanning us-west-2 (3/8 regions)...",
  "created_at": "2026-02-12T00:10:00",
  "started_at": "2026-02-12T00:10:01",
  "completed_at": null,
  "partial_results": {
    "ec2_audit": {...},  // Completed audits
    "ebs_audit": {...}
  },
  "error": null
}
```

### GET /api/v1/finops/audit/results/{job_id}
Get final results when complete.

**Response (200 OK):**
```json
{
  "account_name": "production",
  "audit_timestamp": "2026-02-12T00:15:30",
  "ec2_audit": {...},
  "ebs_audit": {...},
  // ... all audit results
  "summary": {
    "total_findings": 1500,
    "total_potential_savings": 12500.50
  }
}
```

**Response (202 Accepted):**
If job not complete yet:
```json
{
  "detail": "Audit job still running (45%)"
}
```

**Response (500 Error):**
If job failed:
```json
{
  "detail": "Audit job failed: Connection timeout"
}
```

---

## Progress Calculation

Progress is calculated based on:

### Formula:
```
progress = (base_setup + regions_progress + results_aggregation)

Where:
- base_setup = 5%  (initial setup)
- regions_progress = (completed_regions / total_regions) * 85%
- results_aggregation = 10% (final aggregation and summary)
```

### Example for 8 regions:
```
Start:              5%  "Initializing..."
After region 1:     15% "Scanned us-east-1 (1/8 regions)"
After region 2:     26% "Scanned us-west-2 (2/8 regions)"
...
After region 8:     90% "Scanned all regions (8/8)"
Aggregating:        95% "Aggregating results..."
Complete:          100% "Audit complete"
```

---

## Benefits

### User Experience
✅ **Immediate Response** - No waiting for full audit to complete
✅ **Progressive Loading** - See results as they arrive
✅ **Clear Progress** - Know exactly what's happening
✅ **Better Performance** - UI never freezes
✅ **Cancellation Support** - Can navigate away and check back later

### Technical Benefits
✅ **Non-blocking** - FastAPI continues serving other requests
✅ **Scalable** - Handle multiple concurrent audits
✅ **Resilient** - Job state persists in storage
✅ **Monitorable** - Track progress and errors
✅ **Cacheable** - Results can be cached separately from execution

---

## Future Enhancements

### Phase 2 (Optional)
1. **WebSocket Support** - Real-time push updates instead of polling
2. **Redis Job Storage** - Persistent job state across server restarts
3. **Job Cancellation** - Cancel running audits
4. **Priority Queue** - Prioritize high-value audits (EC2, RDS first)
5. **Retry Logic** - Auto-retry failed regions
6. **Email Notifications** - Alert when audit completes
7. **Audit Scheduling** - Cron-based scheduled audits

---

## Testing

### Backend Testing
```bash
# Start async audit
curl -X POST "http://localhost:8000/api/v1/finops/audit/async" \
  -H "Content-Type: application/json" \
  -d '{"account_name": "test", "audit_types": ["ec2", "ebs"]}'

# Response: {"job_id": "abc123", ...}

# Poll status
curl "http://localhost:8000/api/v1/finops/audit/status/abc123"

# Get results (when complete)
curl "http://localhost:8000/api/v1/finops/audit/results/abc123"

# List jobs
curl "http://localhost:8000/api/v1/finops/audit/jobs?limit=10"
```

### Frontend Testing
1. Click "Run Audit"
2. Observe progress bar updating
3. Watch partial results appear
4. Verify final results match backend
5. Test refresh - should show cached data

---

## Files Modified/Created

### Backend
- ✅ **Created**: `backend/app/core/job_storage.py` (150 lines)
- ✅ **Modified**: `backend/app/schemas/audit.py` (AuditJobStatus enhanced)
- ✅ **Modified**: `backend/app/api/v1/endpoints/finops.py` (+130 lines, 4 new endpoints)
- 🚧 **To Modify**: `backend/app/services/audit_service.py` (add progress tracking)

### Frontend
- 📋 **To Modify**: `frontend/src/api/finops.ts` (add async methods)
- 📋 **To Modify**: `frontend/src/pages/FinOpsAudit.tsx` (async UI)
- 📋 **To Create**: `frontend/src/components/audit/ProgressBar.tsx`
- 📋 **To Create**: `frontend/src/hooks/useAuditPolling.ts`

---

## Next Steps

1. Complete audit service progress tracking
2. Update frontend to use async endpoints
3. Add progress indicators and loading states
4. Implement result caching
5. Test with real AWS account
6. Measure performance improvement

---

**Status**: Backend 70% complete, Frontend 0% complete
**Est. Time Remaining**: 2-3 hours
**Priority**: High - Significantly improves UX for long-running audits
