"""
Standardized error handling utilities for API endpoints.

This module provides decorators and helper functions to reduce
boilerplate error handling code across endpoints.
"""
import logging
from functools import wraps
from typing import Callable, Optional, TypeVar, ParamSpec
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


def not_found(resource_type: str, resource_id: Optional[str] = None) -> None:
    """
    Raise a standardized 404 Not Found exception.

    Args:
        resource_type: Human-readable resource type (e.g., "AWS account", "Budget")
        resource_id: Optional resource identifier for more specific message

    Raises:
        HTTPException: 404 Not Found with standardized message
    """
    if resource_id:
        detail = f"{resource_type} with ID {resource_id} not found"
    else:
        detail = f"{resource_type} not found"
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def not_found_or_raise(resource: T, resource_type: str, resource_id: Optional[str] = None) -> T:
    """
    Return resource or raise 404 if None.

    Args:
        resource: The resource to check
        resource_type: Human-readable resource type
        resource_id: Optional resource identifier

    Returns:
        The resource if not None

    Raises:
        HTTPException: 404 if resource is None
    """
    if resource is None:
        not_found(resource_type, resource_id)
    return resource


def handle_errors(
    error_message: str,
    not_found_message: Optional[str] = None,
    log_traceback: bool = False
) -> Callable:
    """
    Decorator for consistent endpoint error handling.

    Catches common exceptions and converts them to appropriate HTTP responses:
    - ValueError -> 404 Not Found (for missing resources)
    - HTTPException -> Re-raised as-is
    - Exception -> 500 Internal Server Error

    Args:
        error_message: Prefix for error log messages
        not_found_message: Custom message for ValueError (optional)
        log_traceback: Whether to include traceback in logs (default: False)

    Returns:
        Decorated function with standardized error handling

    Example:
        @router.get("/items/{item_id}")
        @handle_errors("Error fetching item")
        async def get_item(item_id: int, db: Session = Depends(get_db)):
            return item_service.get(db, item_id)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except ValueError as e:
                detail = not_found_message or str(e)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=detail
                )
            except HTTPException:
                raise
            except Exception as e:
                if log_traceback:
                    logger.error(f"{error_message}: {e}", exc_info=True)
                else:
                    logger.error(f"{error_message}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except ValueError as e:
                detail = not_found_message or str(e)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=detail
                )
            except HTTPException:
                raise
            except Exception as e:
                if log_traceback:
                    logger.error(f"{error_message}: {e}", exc_info=True)
                else:
                    logger.error(f"{error_message}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class ErrorCode:
    """Standardized error codes for API responses."""
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def create_error_response(
    code: str,
    message: str,
    details: Optional[dict] = None
) -> dict:
    """
    Create a standardized error response structure.

    Args:
        code: Error code from ErrorCode constants
        message: Human-readable error message
        details: Optional additional details

    Returns:
        Standardized error response dictionary
    """
    response = {
        "error": {
            "code": code,
            "message": message
        }
    }
    if details:
        response["error"]["details"] = details
    return response