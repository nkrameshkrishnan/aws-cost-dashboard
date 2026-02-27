"""
API v1 router - aggregates all v1 endpoints.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import costs, health, aws_accounts, budgets, finops, teams, automation, analytics, kpi, export, unit_costs, rightsizing, debug, performance

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(aws_accounts.router, prefix="/aws-accounts", tags=["aws-accounts"])
api_router.include_router(costs.router, prefix="/costs", tags=["costs"])
api_router.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
api_router.include_router(finops.router, prefix="/finops", tags=["finops"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(automation.router, prefix="/automation", tags=["automation"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(kpi.router, prefix="/kpi", tags=["kpi"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(unit_costs.router, prefix="/unit-costs", tags=["unit-costs"])
api_router.include_router(rightsizing.router, prefix="/rightsizing", tags=["rightsizing"])
api_router.include_router(debug.router, prefix="/debug", tags=["debug"])
api_router.include_router(performance.router, prefix="/performance", tags=["performance"])

# TODO: Add more routers as they are implemented
# api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
