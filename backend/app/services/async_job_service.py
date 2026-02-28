"""
Async Job Service for processing long-running tasks.
"""
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.async_job import AsyncJob, JobStatus, JobType
from app.services.unit_cost_service import UnitCostService

logger = logging.getLogger(__name__)


class AsyncJobService:
    """Service for managing async jobs."""

    def __init__(self, db: Session):
        self.db = db

    def create_job(self, job_type: JobType, parameters: Dict[str, Any]) -> str:
        """Create a new async job."""
        job_id = str(uuid.uuid4())

        job = AsyncJob(
            id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            parameters=json.dumps(parameters),
        )

        self.db.add(job)
        self.db.commit()

        logger.info(f"Created job {job_id} of type {job_type}")
        return job_id

    def get_job(self, job_id: str) -> Optional[AsyncJob]:
        """Get job by ID."""
        return self.db.query(AsyncJob).filter(AsyncJob.id == job_id).first()

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status."""
        job = self.get_job(job_id)
        if not job:
            return None

        response = {
            "job_id": job.id,
            "status": job.status.value,
            "job_type": job.job_type.value,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }

        if job.status == JobStatus.COMPLETED and job.result:
            response["result"] = json.loads(job.result)
        elif job.status == JobStatus.FAILED and job.error:
            response["error"] = job.error

        return response

    def process_job(self, job_id: str):
        """Process a job in the background."""
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        try:
            # Update status to running
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Processing job {job_id} of type {job.job_type}")

            # Parse parameters
            parameters = json.loads(job.parameters)

            # Process based on job type
            if job.job_type == JobType.UNIT_COST_CALCULATE:
                result = self._process_unit_cost_calculate(parameters)
            elif job.job_type == JobType.UNIT_COST_TREND:
                result = self._process_unit_cost_trend(parameters)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")

            # Update job with result
            job.status = JobStatus.COMPLETED
            job.result = json.dumps(result)
            job.completed_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)

            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            self.db.commit()

    def _process_unit_cost_calculate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process unit cost calculation job."""
        service = UnitCostService(self.db)
        result = service.calculate_unit_costs(
            profile_name=parameters["profile_name"],
            start_date=parameters["start_date"],
            end_date=parameters["end_date"],
            region=parameters.get("region", "us-east-2")
        )
        return self._serialize_result(result)

    def _process_unit_cost_trend(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process unit cost trend job."""
        service = UnitCostService(self.db)
        result = service.get_unit_cost_trend(
            profile_name=parameters["profile_name"],
            metric_type=parameters["metric_type"],
            months=parameters.get("months", 6),
            region=parameters.get("region", "us-east-2")
        )
        return self._serialize_result(result)

    @staticmethod
    def _serialize_result(result: Any) -> Dict[str, Any]:
        """Convert Pydantic model or dict-like result to dictionary."""
        if hasattr(result, 'dict'):
            return result.dict()
        if isinstance(result, dict):
            return result
        raise TypeError(f"Cannot serialize result of type {type(result)}")
