"""
Budget API endpoints.
Provides REST API for budget management and status tracking.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import logging

from app.schemas.budget import (
    BudgetCreate,
    BudgetUpdate,
    BudgetResponse,
    BudgetStatus,
    BudgetSummary
)
from app.services.budget_service import BudgetService
from app.services.aws_budgets_service import AWSBudgetsService
from app.database.base import get_db
from sqlalchemy.orm import Session as DBSession

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sync-from-aws", status_code=200)
async def sync_budgets_from_aws(
    account_name: str = Query(..., description="AWS account name to sync budgets from"),
    overwrite: bool = Query(False, description="Overwrite existing budgets with same name"),
    db: DBSession = Depends(get_db)
):
    """
    Import budgets from AWS Budgets API.
    Fetches budgets from the specified AWS account and imports them into the database.
    """
    try:
        result = AWSBudgetsService.import_aws_budgets(db, account_name, overwrite)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error syncing budgets from AWS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/from-aws/{account_name}", status_code=200)
async def get_aws_budgets(
    account_name: str,
    db: DBSession = Depends(get_db)
):
    """
    Fetch budgets from AWS Budgets API without importing.
    Useful for previewing what budgets exist in AWS before importing.
    """
    try:
        budgets = AWSBudgetsService.fetch_aws_budgets(db, account_name)
        return {"account_name": account_name, "budgets_count": len(budgets), "budgets": budgets}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching AWS budgets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=BudgetResponse, status_code=201)
async def create_budget(
    budget_data: BudgetCreate,
    db: DBSession = Depends(get_db)
):
    """
    Create a new budget.
    """
    try:
        budget = BudgetService.create_budget(db, budget_data)
        return budget
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating budget: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[BudgetResponse])
async def list_budgets(
    aws_account_id: Optional[int] = Query(None, description="Filter by AWS account ID"),
    active_only: bool = Query(True, description="Only return active budgets"),
    db: DBSession = Depends(get_db)
):
    """
    List all budgets with optional filtering.
    """
    try:
        budgets = BudgetService.list_budgets(db, aws_account_id, active_only)
        return budgets
    except Exception as e:
        logger.error(f"Error listing budgets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=BudgetSummary)
async def get_budgets_summary(
    aws_account_id: Optional[int] = Query(None, description="Filter by AWS account ID"),
    db: DBSession = Depends(get_db)
):
    """
    Get summary statistics across all budgets.
    """
    try:
        summary = BudgetService.get_budgets_summary(db, aws_account_id)
        return summary
    except Exception as e:
        logger.error(f"Error getting budget summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: int,
    db: DBSession = Depends(get_db)
):
    """
    Get a specific budget by ID.
    """
    budget = BudgetService.get_budget(db, budget_id)

    if not budget:
        raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

    return budget


@router.get("/{budget_id}/status", response_model=BudgetStatus)
async def get_budget_status(
    budget_id: int,
    db: DBSession = Depends(get_db)
):
    """
    Get budget status with current spending and alert level.
    """
    try:
        status = BudgetService.get_budget_status(db, budget_id)

        if not status:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting budget status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: int,
    budget_data: BudgetUpdate,
    db: DBSession = Depends(get_db)
):
    """
    Update a budget.
    """
    try:
        budget = BudgetService.update_budget(db, budget_id, budget_data)

        if not budget:
            raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

        return budget
    except Exception as e:
        logger.error(f"Error updating budget: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{budget_id}", status_code=204)
async def delete_budget(
    budget_id: int,
    db: DBSession = Depends(get_db)
):
    """
    Delete a budget.
    """
    success = BudgetService.delete_budget(db, budget_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")

    return None
