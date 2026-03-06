"""
Main FastAPI application entry point.
Sets up the application, middleware, and routes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AWS Cost Dashboard API for multi-account cost monitoring and FinOps",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add performance monitoring middleware
from app.core.performance import PerformanceMiddleware
app.add_middleware(
    PerformanceMiddleware,
    slow_request_threshold_ms=1000  # Log requests taking >1 second
)
logger.info("Performance monitoring middleware enabled")

@app.on_event("startup")
async def startup_event():
    """Run tasks on application startup."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize database tables
    from app.database.base import init_db
    try:
        init_db()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    # Initialize scheduler for automated jobs
    from app.services.scheduler_service import SchedulerService
    try:
        SchedulerService.initialize(settings.DATABASE_URL)
        SchedulerService.start()
        logger.info("Scheduler service initialized and started")

        # Schedule default budget alerts job (every 6 hours)
        SchedulerService.schedule_budget_alerts(
            job_id="budget-alerts-default",
            cron_expression="0 */6 * * *",  # Every 6 hours
            enabled=True
        )
        logger.info("Default budget alerts job scheduled")

    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")

    # TODO: Initialize Redis connection pool
    # TODO: Verify AWS credentials


@app.on_event("shutdown")
async def shutdown_event():
    """Run tasks on application shutdown."""
    logger.info(f"Shutting down {settings.APP_NAME}")

    # Shutdown scheduler
    from app.services.scheduler_service import SchedulerService
    try:
        SchedulerService.shutdown(wait=True)
        logger.info("Scheduler service shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")

    # TODO: Close database connections
    # TODO: Close Redis connections


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION
    }


# Include API routers
from app.api.v1.router import api_router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
