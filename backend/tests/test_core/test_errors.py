"""
Unit tests for app.core.errors — standardized error handling utilities.
"""
import pytest
import asyncio
from fastapi import HTTPException, status

from app.core.errors import (
    not_found,
    not_found_or_raise,
    handle_errors,
    ErrorCode,
    create_error_response,
)


# ---------------------------------------------------------------------------
# not_found
# ---------------------------------------------------------------------------

class TestNotFound:
    def test_raises_404(self):
        with pytest.raises(HTTPException) as exc_info:
            not_found("Budget")
        assert exc_info.value.status_code == 404

    def test_message_without_id(self):
        with pytest.raises(HTTPException) as exc_info:
            not_found("Budget")
        assert "Budget" in exc_info.value.detail
        assert "not found" in exc_info.value.detail

    def test_message_with_id(self):
        with pytest.raises(HTTPException) as exc_info:
            not_found("Budget", "42")
        assert "42" in exc_info.value.detail

    def test_various_resource_types(self):
        for resource in ["AWS account", "Cost record", "User"]:
            with pytest.raises(HTTPException) as exc_info:
                not_found(resource)
            assert resource in exc_info.value.detail


# ---------------------------------------------------------------------------
# not_found_or_raise
# ---------------------------------------------------------------------------

class TestNotFoundOrRaise:
    def test_returns_resource_when_present(self):
        obj = {"id": 1}
        result = not_found_or_raise(obj, "Item")
        assert result is obj

    def test_raises_404_when_none(self):
        with pytest.raises(HTTPException) as exc_info:
            not_found_or_raise(None, "Budget", "99")
        assert exc_info.value.status_code == 404
        assert "99" in exc_info.value.detail

    def test_returns_non_none_falsy_value(self):
        """Empty list is not None — should be returned."""
        result = not_found_or_raise([], "List")
        assert result == []

    def test_returns_zero(self):
        result = not_found_or_raise(0, "Count")
        assert result == 0


# ---------------------------------------------------------------------------
# handle_errors — sync functions
# ---------------------------------------------------------------------------

class TestHandleErrorsSync:
    def _make_handler(self, error_message="test error", not_found_message=None):
        @handle_errors(error_message, not_found_message=not_found_message)
        def sync_fn(raise_type=None, msg="error"):
            if raise_type == "value":
                raise ValueError(msg)
            elif raise_type == "http":
                raise HTTPException(status_code=422, detail="unprocessable")
            elif raise_type == "generic":
                raise RuntimeError(msg)
            return "ok"

        return sync_fn

    def test_returns_value_normally(self):
        fn = self._make_handler()
        assert fn() == "ok"

    def test_value_error_becomes_404(self):
        fn = self._make_handler()
        with pytest.raises(HTTPException) as exc_info:
            fn(raise_type="value", msg="item missing")
        assert exc_info.value.status_code == 404
        assert "item missing" in exc_info.value.detail

    def test_value_error_uses_not_found_message(self):
        fn = self._make_handler(not_found_message="Custom not found")
        with pytest.raises(HTTPException) as exc_info:
            fn(raise_type="value")
        assert exc_info.value.detail == "Custom not found"

    def test_http_exception_reraises(self):
        fn = self._make_handler()
        with pytest.raises(HTTPException) as exc_info:
            fn(raise_type="http")
        assert exc_info.value.status_code == 422

    def test_generic_exception_becomes_500(self):
        fn = self._make_handler()
        with pytest.raises(HTTPException) as exc_info:
            fn(raise_type="generic", msg="boom")
        assert exc_info.value.status_code == 500
        assert "boom" in exc_info.value.detail


# ---------------------------------------------------------------------------
# handle_errors — async functions
# ---------------------------------------------------------------------------

class TestHandleErrorsAsync:
    def _make_async_handler(self, error_message="test error", not_found_message=None):
        @handle_errors(error_message, not_found_message=not_found_message)
        async def async_fn(raise_type=None, msg="error"):
            if raise_type == "value":
                raise ValueError(msg)
            elif raise_type == "http":
                raise HTTPException(status_code=422, detail="unprocessable")
            elif raise_type == "generic":
                raise RuntimeError(msg)
            return "ok"

        return async_fn

    def test_returns_value_normally(self):
        fn = self._make_async_handler()
        result = asyncio.get_event_loop().run_until_complete(fn())
        assert result == "ok"

    def test_value_error_becomes_404(self):
        fn = self._make_async_handler()
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(fn(raise_type="value", msg="missing"))
        assert exc_info.value.status_code == 404

    def test_http_exception_reraises(self):
        fn = self._make_async_handler()
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(fn(raise_type="http"))
        assert exc_info.value.status_code == 422

    def test_generic_exception_becomes_500(self):
        fn = self._make_async_handler()
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(fn(raise_type="generic", msg="crash"))
        assert exc_info.value.status_code == 500

    def test_log_traceback_flag(self):
        @handle_errors("error", log_traceback=True)
        async def fn():
            raise RuntimeError("traceback test")

        with pytest.raises(HTTPException):
            asyncio.get_event_loop().run_until_complete(fn())


# ---------------------------------------------------------------------------
# ErrorCode
# ---------------------------------------------------------------------------

class TestErrorCode:
    def test_all_constants_are_strings(self):
        for attr in ["NOT_FOUND", "VALIDATION_ERROR", "UNAUTHORIZED",
                     "FORBIDDEN", "INTERNAL_ERROR", "SERVICE_UNAVAILABLE"]:
            assert isinstance(getattr(ErrorCode, attr), str)


# ---------------------------------------------------------------------------
# create_error_response
# ---------------------------------------------------------------------------

class TestCreateErrorResponse:
    def test_basic_structure(self):
        resp = create_error_response(ErrorCode.NOT_FOUND, "item not found")
        assert "error" in resp
        assert resp["error"]["code"] == ErrorCode.NOT_FOUND
        assert resp["error"]["message"] == "item not found"

    def test_with_details(self):
        resp = create_error_response(
            ErrorCode.VALIDATION_ERROR,
            "invalid input",
            details={"field": "name", "issue": "too long"},
        )
        assert resp["error"]["details"]["field"] == "name"

    def test_without_details_no_key(self):
        resp = create_error_response(ErrorCode.INTERNAL_ERROR, "crash")
        assert "details" not in resp["error"]
