"""Standardized API response models for Life Graph SaaS.

All API responses use a consistent envelope format:
  - Success: {"data": ..., "meta": {...}}
  - Error:   {"error": {"code": "...", "message": "...", "details": [...]}}

This module provides Pydantic models, helper functions, and
pagination utilities for building responses.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Pagination ───────────────────────────────────────────────


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    total: int | None = Field(None, description="Total number of items (if known)")
    page_size: int = Field(description="Number of items per page")
    next_cursor: str | None = Field(None, description="Cursor for next page")
    has_more: bool = Field(description="Whether more results exist")


def encode_cursor(sort_key: str, item_id: str) -> str:
    """Encode a cursor from sort key and item ID."""
    payload = json.dumps({"k": sort_key, "id": item_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> dict[str, str]:
    """Decode a cursor back to sort key and item ID.

    Returns:
        Dict with 'k' (sort key) and 'id' fields.

    Raises:
        ValueError: If the cursor is invalid.
    """
    try:
        payload = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(payload)
    except Exception:
        raise ValueError("Invalid cursor format")


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
