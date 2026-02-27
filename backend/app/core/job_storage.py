"""
In-memory job storage for async audit jobs.
This can be upgraded to Redis for production use.
"""
from typing import Dict, Optional, Any
from datetime import datetime
from threading import Lock
import uuid


class JobStorage:
    """Thread-safe in-memory storage for async audit jobs."""

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def create_job(self, account_name: str, audit_types: list) -> str:
        """Create a new audit job and return job ID."""
        job_id = str(uuid.uuid4())

        with self._lock:
            self._jobs[job_id] = {
                'job_id': job_id,
                'account_name': account_name,
                'audit_types': audit_types,
                'status': 'pending',  # pending, running, completed, failed
                'progress': 0,  # 0-100
                'current_step': 'Initializing...',
                'results': None,
                'partial_results': {},  # Store results as they complete
                'error': None,
                'created_at': datetime.utcnow().isoformat(),
                'started_at': None,
                'completed_at': None,
            }

        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def update_job_status(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        error: Optional[str] = None,
        partial_results: Optional[Dict[str, Any]] = None
    ):
        """Update job status."""
        with self._lock:
            if job_id not in self._jobs:
                return

            job = self._jobs[job_id]

            if status:
                job['status'] = status
                if status == 'running' and not job['started_at']:
                    job['started_at'] = datetime.utcnow().isoformat()
                elif status in ['completed', 'failed']:
                    job['completed_at'] = datetime.utcnow().isoformat()

            if progress is not None:
                job['progress'] = min(100, max(0, progress))

            if current_step:
                job['current_step'] = current_step

            if error:
                job['error'] = error

            if partial_results is not None:
                job['partial_results'] = partial_results

    def update_partial_results(self, job_id: str, audit_type: str, results: Any):
        """Update partial results for a specific audit type."""
        with self._lock:
            if job_id not in self._jobs:
                return

            self._jobs[job_id]['partial_results'][audit_type] = results

    def set_final_results(self, job_id: str, results: Any):
        """Set final complete results."""
        with self._lock:
            if job_id not in self._jobs:
                return

            self._jobs[job_id]['results'] = results
            self._jobs[job_id]['status'] = 'completed'
            self._jobs[job_id]['progress'] = 100
            self._jobs[job_id]['completed_at'] = datetime.utcnow().isoformat()

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age_hours."""
        with self._lock:
            current_time = datetime.utcnow()
            jobs_to_remove = []

            for job_id, job in self._jobs.items():
                created_at = datetime.fromisoformat(job['created_at'])
                age_hours = (current_time - created_at).total_seconds() / 3600

                if age_hours > max_age_hours:
                    jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                del self._jobs[job_id]

            return len(jobs_to_remove)

    def list_jobs(self, account_name: Optional[str] = None, limit: int = 100) -> list:
        """List recent jobs, optionally filtered by account."""
        with self._lock:
            jobs = list(self._jobs.values())

            if account_name:
                jobs = [j for j in jobs if j['account_name'] == account_name]

            # Sort by created_at descending
            jobs.sort(key=lambda x: x['created_at'], reverse=True)

            return jobs[:limit]


# Global job storage instance
job_storage = JobStorage()
