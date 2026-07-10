"""Exception types for the Life Graph SDK.

All API errors are parsed from the standard error envelope::

    {"error": {"code": "...", "message": "...", "request_id": "..."}}

Each exception carries the parsed ``error_code`` and ``request_id`` when
available so callers can log or retry intelligently.
"""

from __future__ import annotations


class LifeGraphError(Exception):
    """Base exception for all Life Graph API errors.

    Attributes:
        message: Human-readable error description.
        status_code: The HTTP status code returned by the API.
        error_code: Machine-readable error code from the API envelope
            (e.g. ``"TENANT_NOT_FOUND"``), or ``None`` when unavailable.
        request_id: Unique request identifier returned by the API, or
            ``None`` when unavailable.
    """

    def __init__(
        self,
        message: str,
        status_code: int,
        error_code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id

    def __repr__(self) -> str:
        parts = [
            f"status_code={self.status_code}",
            f"message={self.message!r}",
        ]
        if self.error_code is not None:
            parts.append(f"error_code={self.error_code!r}")
        if self.request_id is not None:
            parts.append(f"request_id={self.request_id!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"


class NotFoundError(LifeGraphError):
    """Raised when a requested resource is not found (HTTP 404)."""


class ValidationError(LifeGraphError):
    """Raised when the request is invalid (HTTP 400 / 422)."""


class ServerError(LifeGraphError):
    """Raised when the server encounters an internal error (HTTP 5xx)."""


class AuthenticationError(LifeGraphError):
    """Raised when authentication or authorisation fails (HTTP 401 / 403)."""


class RateLimitError(LifeGraphError):
    """Raised when the API rate limit is exceeded (HTTP 429).

    Attributes:
        retry_after: Seconds the caller should wait before retrying.
        limit: The rate-limit ceiling for the current window.
        remaining: Number of requests remaining (typically ``0``).
    """

    def __init__(
        self,
        message: str,
        status_code: int,
        error_code: str | None = None,
        request_id: str | None = None,
        retry_after: int = 0,
        limit: int = 0,
        remaining: int = 0,
    ) -> None:
        super().__init__(message, status_code, error_code, request_id)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining

    def __repr__(self) -> str:
        return (
            f"RateLimitError(status_code={self.status_code}, "
            f"retry_after={self.retry_after}, "
            f"limit={self.limit}, "
            f"remaining={self.remaining}, "
            f"message={self.message!r})"
        )


def _parse_error_envelope(response) -> tuple[str, str | None, str | None]:  # noqa: ANN001
    """Extract message, error_code, and request_id from the API error body.

    The API returns errors in the envelope::

        {"error": {"code": "...", "message": "...", "request_id": "..."}}

    If parsing fails the raw response text is used as the message.

    Args:
        response: An ``httpx.Response`` object.

    Returns:
        A three-tuple of ``(message, error_code, request_id)``.
    """
    try:
        body = response.json()
    except Exception:
        return response.text, None, None

    error_obj = body.get("error") if isinstance(body, dict) else None
    if isinstance(error_obj, dict):
        message = error_obj.get("message", response.text)
        error_code = error_obj.get("code")
        request_id = error_obj.get("request_id")
        return message, error_code, request_id

    # Fallback: legacy ``detail`` field or raw text.
    detail = body.get("detail", response.text) if isinstance(body, dict) else response.text
    return detail, None, None


def raise_for_status(response) -> None:  # noqa: ANN001 – avoids importing httpx at module level
    """Inspect an httpx response and raise the appropriate SDK exception.

    The function parses the standard error envelope returned by the Life Graph
    v1 API and maps HTTP status codes to typed exceptions.

    Args:
        response: An ``httpx.Response`` object.

    Raises:
        RateLimitError: If the response status is 429.
        AuthenticationError: If the response status is 401 or 403.
        NotFoundError: If the response status is 404.
        ValidationError: If the response status is 400 or 422.
        ServerError: If the response status is >= 500.
        LifeGraphError: For any other non-success status code.
    """
    if response.is_success:
        return

    status = response.status_code
    detail, error_code, request_id = _parse_error_envelope(response)
    message = f"[{status}] {detail}"

    if status == 429:
        retry_after = int(response.headers.get("Retry-After", 0))
        limit = int(response.headers.get("X-RateLimit-Limit", 0))
        remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
        raise RateLimitError(
            message,
            status,
            error_code=error_code,
            request_id=request_id,
            retry_after=retry_after,
            limit=limit,
            remaining=remaining,
        )
    if status in (401, 403):
        raise AuthenticationError(message, status, error_code, request_id)
    if status == 404:
        raise NotFoundError(message, status, error_code, request_id)
    if status in (400, 422):
        raise ValidationError(message, status, error_code, request_id)
    if status >= 500:
        raise ServerError(message, status, error_code, request_id)
    raise LifeGraphError(message, status, error_code, request_id)
