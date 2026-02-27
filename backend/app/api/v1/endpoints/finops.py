"""
FinOps audit API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from pydantic import BaseModel
import logging

from app.database.base import get_db
from app.schemas.audit import (
    AuditRequest,
    FullAuditResults,
    AuditJobStatus,
)
from app.services.audit_service import AuditService
from app.services.audit_notification_service import AuditNotificationService
from app.core.job_storage import job_storage
import threading

router = APIRouter()
logger = logging.getLogger(__name__)


class SendAuditToTeamsRequest(BaseModel):
    """Request body for sending audit results to Teams."""
    audit_results: Optional[FullAuditResults] = None
    webhook_id: Optional[int] = None


@router.post("/audit", response_model=FullAuditResults, status_code=200)
async def run_audit(
    audit_request: AuditRequest,
    db: DBSession = Depends(get_db)
):
    """
    Run a comprehensive FinOps audit on an AWS account.

    Args:
        audit_request: Audit configuration and parameters
        db: Database session

    Returns:
        Complete audit results with findings and recommendations
    """
    try:
        logger.info(f"Received audit request for account: {audit_request.account_name}")
        results = AuditService.run_full_audit(db, audit_request)
        return results
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error running audit: {e}")
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


@router.post("/audit/async", response_model=dict, status_code=202)
async def start_async_audit(
    audit_request: AuditRequest,
    db: DBSession = Depends(get_db)
):
    """
    Start an asynchronous audit job and return immediately with job ID.

    This endpoint initiates the audit in the background and returns a job ID
    that can be used to poll for status and results.

    Args:
        audit_request: Audit configuration and parameters
        db: Database session

    Returns:
        Job ID and status URL
    """
    try:
        # Create job in storage
        job_id = job_storage.create_job(
            account_name=audit_request.account_name,
            audit_types=audit_request.audit_types
        )

        logger.info(f"Created async audit job {job_id} for account: {audit_request.account_name}")

        # Start audit in background thread
        def run_audit_job():
            # Create a new database session for the background thread
            from app.database.base import SessionLocal
            thread_db = SessionLocal()
            try:
                job_storage.update_job_status(job_id, status='running', progress=5, current_step='Starting audit...')
                results = AuditService.run_full_audit(thread_db, audit_request, job_id=job_id)
                job_storage.set_final_results(job_id, results.dict())
                logger.info(f"Completed async audit job {job_id}")
            except Exception as e:
                logger.error(f"Error in async audit job {job_id}: {e}")
                job_storage.update_job_status(job_id, status='failed', error=str(e))
            finally:
                thread_db.close()

        thread = threading.Thread(target=run_audit_job, daemon=True)
        thread.start()

        return {
            'job_id': job_id,
            'status': 'pending',
            'message': 'Audit job started',
            'status_url': f'/api/v1/finops/audit/status/{job_id}',
            'results_url': f'/api/v1/finops/audit/results/{job_id}'
        }

    except Exception as e:
        logger.error(f"Error starting async audit: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start audit: {str(e)}")


@router.get("/audit/status/{job_id}", response_model=AuditJobStatus)
async def get_audit_status(job_id: str):
    """
    Get the status of an async audit job.

    Args:
        job_id: The job ID returned from the async audit endpoint

    Returns:
        Job status including progress, current step, and partial results
    """
    job = job_storage.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Use model_validate to properly deserialize nested models
    return AuditJobStatus.model_validate(job)


@router.get("/audit/results/{job_id}", response_model=FullAuditResults)
async def get_audit_results(
    job_id: str,
    include_partial: bool = Query(default=True, description="Include partial results if audit is still running")
):
    """
    Get the results of an audit job.
    Returns final results if completed, or partial results if still running.

    Args:
        job_id: The job ID returned from the async audit endpoint
        include_partial: Whether to return partial results for in-progress audits

    Returns:
        Complete audit results if job is finished, partial results if still running (when include_partial=True)
    """
    job = job_storage.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job['status'] == 'failed':
        raise HTTPException(status_code=500, detail=f"Audit job failed: {job.get('error', 'Unknown error')}")

    # Return final results if completed
    if job['status'] == 'completed':
        if not job['results']:
            raise HTTPException(status_code=404, detail="Results not available")
        return FullAuditResults.model_validate(job['results'])

    # Return partial results if requested and available
    if include_partial and job.get('partial_results'):
        logger.info(f"Returning partial results for job {job_id} (status: {job['status']}, progress: {job['progress']}%)")
        return FullAuditResults.model_validate(job['partial_results'])

    # Still running without partial results
    raise HTTPException(
        status_code=202,
        detail=f"Audit job still {job['status']} ({job['progress']}%). Partial results not yet available."
    )


@router.get("/audit/jobs")
async def list_audit_jobs(
    account_name: Optional[str] = None,
    limit: int = Query(default=20, le=100)
):
    """
    List recent audit jobs.

    Args:
        account_name: Optional filter by account name
        limit: Maximum number of jobs to return

    Returns:
        List of recent audit jobs
    """
    jobs = job_storage.list_jobs(account_name=account_name, limit=limit)
    return {'jobs': jobs, 'count': len(jobs)}


@router.get("/audit/idle-instances/{account_name}")
async def get_idle_instances(
    account_name: str,
    cpu_threshold: float = Query(default=5.0, ge=0, le=100),
    db: DBSession = Depends(get_db)
):
    """
    Get idle EC2 instances for an account.

    Args:
        account_name: AWS account name
        cpu_threshold: CPU utilization threshold (%)
        db: Database session

    Returns:
        List of idle EC2 instances
    """
    try:
        audit_request = AuditRequest(
            account_name=account_name,
            audit_types=["ec2"],
            cpu_threshold=cpu_threshold
        )
        results = AuditService.run_full_audit(db, audit_request)
        return {
            "idle_instances": results.ec2_audit.idle_instances,
            "total_cost": results.ec2_audit.total_idle_cost
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting idle instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/unattached-volumes/{account_name}")
async def get_unattached_volumes(
    account_name: str,
    days_threshold: int = Query(default=7, ge=0),
    db: DBSession = Depends(get_db)
):
    """
    Get unattached EBS volumes for an account.

    Args:
        account_name: AWS account name
        days_threshold: Days unattached threshold
        db: Database session

    Returns:
        List of unattached EBS volumes
    """
    try:
        audit_request = AuditRequest(
            account_name=account_name,
            audit_types=["ebs"],
            days_unattached_threshold=days_threshold
        )
        results = AuditService.run_full_audit(db, audit_request)
        return {
            "unattached_volumes": results.ebs_audit.unattached_volumes,
            "total_cost": results.ebs_audit.total_unattached_cost
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting unattached volumes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/unattached-ips/{account_name}")
async def get_unattached_ips(
    account_name: str,
    db: DBSession = Depends(get_db)
):
    """
    Get unattached Elastic IPs for an account.

    Args:
        account_name: AWS account name
        db: Database session

    Returns:
        List of unattached Elastic IPs
    """
    try:
        audit_request = AuditRequest(
            account_name=account_name,
            audit_types=["eip"]
        )
        results = AuditService.run_full_audit(db, audit_request)
        return {
            "unattached_ips": results.eip_audit.unattached_ips,
            "total_cost": results.eip_audit.total_cost
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting unattached IPs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit/untagged-resources/{account_name}")
async def get_untagged_resources(
    account_name: str,
    required_tags: Optional[str] = Query(default="Environment,Owner,Project"),
    db: DBSession = Depends(get_db)
):
    """
    Get untagged resources for an account.

    Args:
        account_name: AWS account name
        required_tags: Comma-separated list of required tags
        db: Database session

    Returns:
        List of untagged resources
    """
    try:
        tags_list = [tag.strip() for tag in required_tags.split(',')]
        audit_request = AuditRequest(
            account_name=account_name,
            audit_types=["tagging"],
            required_tags=tags_list
        )
        results = AuditService.run_full_audit(db, audit_request)
        return {
            "untagged_resources": results.tagging_audit.untagged_resources,
            "total_untagged": results.tagging_audit.total_untagged,
            "compliance_percentage": results.tagging_audit.compliance_percentage
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting untagged resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regions/{account_name}")
async def get_available_regions(
    account_name: str,
    db: DBSession = Depends(get_db)
):
    """
    Get list of enabled AWS regions for an account.
    Uses smart filtering to return only regions with recent activity.

    Args:
        account_name: AWS account name
        db: Database session

    Returns:
        List of enabled and active regions
    """
    try:
        from app.aws.session_manager_db import db_session_manager

        # Create session for the account
        base_session = db_session_manager.get_session(db, account_name)

        # Get all enabled regions
        ec2_client = base_session.client('ec2')
        regions_response = ec2_client.describe_regions(
            Filters=[{'Name': 'opt-in-status', 'Values': ['opt-in-not-required', 'opted-in']}]
        )
        all_regions = [region['RegionName'] for region in regions_response['Regions']]

        logger.info(f"Found {len(all_regions)} enabled regions for account: {account_name}")

        # Apply smart filtering to get active regions
        active_regions = AuditService._filter_active_regions(
            base_session,
            all_regions,
            min_monthly_cost=1.0
        )

        return {
            "account_name": account_name,
            "total_regions": len(all_regions),
            "active_regions": len(active_regions),
            "regions": active_regions
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting regions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audit/send-to-teams")
async def send_audit_to_teams(
    request: SendAuditToTeamsRequest,
    job_id: Optional[str] = Query(None, description="Audit job ID (optional if audit_results provided)"),
    db: DBSession = Depends(get_db)
):
    """
    Send audit report to configured Teams webhooks.

    Args:
        request: Request body containing optional audit results and webhook ID
        job_id: Optional audit job ID. Required only if audit_results not provided in request body
        db: Database session

    Returns:
        Results of sending notifications
    """
    try:
        # Get audit results from request body or job lookup
        if request.audit_results:
            # Use provided audit results directly
            audit_results = request.audit_results
            logger.info(f"Using audit results from request body for account: {audit_results.account_name}")
        elif job_id:
            # Fall back to job ID lookup
            job = job_storage.get_job(job_id)

            if not job:
                raise HTTPException(status_code=404, detail=f"Audit job {job_id} not found")

            if job['status'] != 'completed':
                raise HTTPException(status_code=400, detail=f"Audit job is not completed yet (status: {job['status']})")

            if not job.get('results'):
                raise HTTPException(status_code=404, detail="Audit results not available")

            # Convert results dict to FullAuditResults object
            audit_results = FullAuditResults(**job['results'])
            logger.info(f"Using audit results from job {job_id} for account: {audit_results.account_name}")
        else:
            raise HTTPException(
                status_code=400,
                detail="Either audit_results in request body or job_id query parameter must be provided"
            )

        # Send to Teams
        result = AuditNotificationService.send_audit_report_to_teams(
            db=db,
            audit_results=audit_results,
            webhook_id=request.webhook_id
        )

        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to send audit report'))

        return {
            "success": True,
            "message": f"Audit report sent to {result['notifications_sent']} webhook(s)",
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending audit to Teams: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send audit report: {str(e)}")
