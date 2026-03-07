# Shared API utilities for v1 endpoints

from fastapi import HTTPException, status, Response
import json
from typing import Any, Coroutine

async def json_response(data: Any, status_code: int = 200) -> Response:
    """Return a JSON Response object with the given data.

    This helper centralises the JSON encoding logic so that all endpoints can
    produce consistent responses and allows us to apply common headers or
    status‑code handling in a single place.
    """
    return Response(content=json.dumps(data), media_type="application/json", status_code=status_code)

async def handle_exceptions(coro: Coroutine) -> Any:
    """Wrap a coroutine with generic FastAPI error handling.

    The function re‑raises HTTPException so that explicit
    validation errors are preserved. Any other exception is
    converted into a 500 Internal Server Error.
    """
    try:
        return await coro
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))