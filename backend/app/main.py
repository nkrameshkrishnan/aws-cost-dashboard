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
# ASGI middleware to ensure Private Network Access header is present
class PrivateNetworkMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def send_wrapper(message):
            try:
                if message.get('type') == 'http.response.start':
                    headers = list(message.setdefault('headers', []))
                    # Add header to allow Private Network Access from public origins
                    headers.append((b'access-control-allow-private-network', b'true'))
                    message['headers'] = headers
            except Exception:
                pass
            await send(message)

        await self.app(scope, receive, send_wrapper)
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

    # Apply any pending Alembic migrations before serving traffic.
    # For a fresh database this creates all tables; for an existing database
    # it only applies migrations that haven't run yet.
    from app.database.base import upgrade_db
    try:
        upgrade_db()
        logger.info("Database schema is up to date")
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")

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

    # Dispose the SQLAlchemy connection pool so the process exits cleanly
    # without waiting for idle connections to time out.
    from app.database.base import engine
    try:
        engine.dispose()
        logger.info("Database connection pool disposed")
    except Exception as e:
        logger.error(f"Error disposing database connections: {e}")

    # Close the Redis connection that the global CacheManager holds.
    from app.core.cache import cache_manager
    try:
        if cache_manager.redis_client is not None:
            cache_manager.redis_client.close()
            logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")


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

# Wrap app with PrivateNetworkMiddleware so the header is added even for preflight responses
app = PrivateNetworkMiddleware(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
