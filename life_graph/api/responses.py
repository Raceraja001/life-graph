"""Standardized API response models for Life Graph SaaS.

All API responses use a consistent envelope format:
  - Success: {"data": ..., "meta": {...}}
  - Error:   {"error": {"code": "...", "message": "...", "details": [...],
                        "request_id": "..."}, "detail": ...}

``detail`` duplicates the message in FastAPI's older shape for clients that
still read it (see ``http_error_body``).

This module provides Pydantic models, helper functions, and
pagination utilities for building responses.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any, TypeVar

from pydantic import BaseModel, Field

# The cursor helpers live in core/pagination.py so the storage layer can
# decode a cursor without importing the API (audit M12). Re-exported here,
# as the same objects, for the routers and clients that import them from here
# (main.py's InvalidCursorError handler must match what storage raises).
from life_graph.core.pagination import InvalidCursorError as InvalidCursorError
from life_graph.core.pagination import decode_cursor as decode_cursor
from life_graph.core.pagination import encode_cursor as encode_cursor

T = TypeVar("T")


# ── Pagination ───────────────────────────────────────────────


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    total: int | None = Field(None, description="Total number of items (if known)")
    page_size: int = Field(description="Number of items per page")
    next_cursor: str | None = Field(None, description="Cursor for next page")
    has_more: bool = Field(description="Whether more results exist")


# ── Response Helpers ─────────────────────────────────────────


class ErrorDetail(BaseModel):
    """Individual error detail (e.g., field validation error)."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorBody(BaseModel):
    """Structured error response body."""

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    error: ErrorBody


def success_response(
    data: Any,
    meta: dict | None = None,
) -> dict:
    """Build a success response envelope.

    Args:
        data: The response payload (single object or list).
        meta: Optional metadata (pagination, timing, etc.).

    Returns:
        Dict ready to be returned from a FastAPI endpoint.
    """
    response: dict[str, Any] = {"data": data}
    if meta:
        response["meta"] = meta
    return response


def paginated_response(
    data: list[Any],
    total: int | None = None,
    page_size: int = 20,
    next_cursor: str | None = None,
    has_more: bool = False,
) -> dict:
    """Build a paginated response envelope.

    Args:
        data: List of items for this page.
        total: Total count (if available).
        page_size: Items per page.
        next_cursor: Cursor for fetching the next page.
        has_more: Whether more results exist.

    Returns:
        Dict with data and pagination meta.
    """
    return {
        "data": data,
        "meta": {
            "total": total,
            "page_size": page_size,
            "next_cursor": next_cursor,
            "has_more": has_more,
        },
    }


def error_response(
    code: str,
    message: str,
    details: list[dict] | None = None,
    request_id: str | None = None,
) -> dict:
    """Build an error response envelope.

    Args:
        code: Machine-readable error code (e.g., "NOT_FOUND").
        message: Human-readable error message.
        details: Optional list of field-level errors.
        request_id: Request ID for correlation.

    Returns:
        Dict with error envelope.
    """
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        body["error"]["details"] = details
    if request_id:
        body["error"]["request_id"] = request_id
    return body


# ── HTTP errors → the error envelope ─────────────────────────

# Machine-readable code per HTTP status. Statuses not listed fall back to the
# standard reason phrase (``HTTPStatus(n).name``), then to ``HTTP_<n>``.
_STATUS_ERROR_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    410: "GONE",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def error_code_for_status(status_code: int) -> str:
    """The envelope's ``error.code`` for an HTTP status."""
    if status_code in _STATUS_ERROR_CODES:
        return _STATUS_ERROR_CODES[status_code]
    try:
        return HTTPStatus(status_code).name
    except ValueError:
        return f"HTTP_{status_code}"


def http_error_body(
    status_code: int,
    detail: Any,
    request_id: str | None = None,
    *,
    code: str | None = None,
) -> dict:
    """The body for an ``HTTPException``: the error envelope plus ``detail``.

    ``{"error": {code, message, request_id}}`` is what api/responses.py has
    always documented and what the TypeScript SDK reads (audit M2). The
    top-level ``detail`` is FastAPI's old shape, kept unchanged (string, list
    or dict, whatever the route raised) because the dashboard, life-graph-ui,
    the Android app and the Python SDK read ``detail`` first.

    A dict ``detail`` may name its own ``code`` and ``message``.
    """
    message: str
    if isinstance(detail, str):
        message = detail
    elif isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("error") or detail)
        if code is None and isinstance(detail.get("code"), str):
            code = detail["code"]
    elif detail is None:
        try:
            message = HTTPStatus(status_code).phrase
        except ValueError:
            message = ""
    else:
        message = str(detail)
    body = error_response(
        code=code or error_code_for_status(status_code),
        message=message,
        request_id=request_id,
    )
    body["detail"] = detail
    return body
