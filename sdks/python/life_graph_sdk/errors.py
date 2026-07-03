"""Exception types for the Life Graph SDK."""

from __future__ import annotations


class LifeGraphError(Exception):
    """Base exception for all Life Graph API errors.

    Attributes:
        message: Human-readable error description.
        status_code: The HTTP status code returned by the API.
    """

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(status_code={self.status_code}, message={self.message!r})"


class NotFoundError(LifeGraphError):
    """Raised when a requested resource is not found (HTTP 404)."""


class ValidationError(LifeGraphError):
    """Raised when the request is invalid (HTTP 422 / 400)."""


class ServerError(LifeGraphError):
    """Raised when the server encounters an internal error (HTTP 5xx)."""


def raise_for_status(response) -> None:  # noqa: ANN001 – avoids importing httpx at module level
    """Inspect an httpx response and raise the appropriate SDK exception.

    Args:
        response: An ``httpx.Response`` object.

    Raises:
        NotFoundError: If the response status is 404.
        ValidationError: If the response status is 400 or 422.
        ServerError: If the response status is >= 500.
        LifeGraphError: For any other non-success status code.
    """
    if response.is_success:
        return

    status = response.status_code
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text

    message = f"[{status}] {detail}"

    if status == 404:
        raise NotFoundError(message, status)
    if status in (400, 422):
        raise ValidationError(message, status)
    if status >= 500:
        raise ServerError(message, status)
    raise LifeGraphError(message, status)
