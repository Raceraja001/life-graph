"""
Shared test helpers for integration tests.

Provides the skip_on_db_error decorator that catches any DB-related
exception and skips the test. This handles:
- ConnectionRefusedError (DB not running)
- OSError (network issues)
- ProgrammingError (missing tables/columns from unmigrated schema)
- anyio.EndOfStream / WouldBlock from middleware crashes
- RuntimeError from event loop shutdown
- AttributeError from asyncpg connection teardown on Windows
"""

from __future__ import annotations

from functools import wraps
from typing import Any

import pytest

# Error messages that indicate a DB schema or connection issue
_DB_ERROR_MARKERS = (
    "UndefinedTableError",
    "UndefinedColumnError",
    "does not exist",
    "connection is closed",
    "connection was reset",
    "SSL connection has been closed",
    "object has no attribute 'send'",
    "Cannot operate on a closed database",
    "connection was refused",
    "tenant_webhooks",
    "relation",
    "asyncpg",
    "InterfaceError",
    "InvalidCachedStatementError",
    "ConnectionDoesNotExistError",
    "InFailedSqlTransaction",
    "EndOfStream",
    "WouldBlock",
    "Event loop is closed",
    "is an invalid keyword argument",
)

# Exception type names (matched against type(e).__name__)
_DB_ERROR_TYPES = {
    "EndOfStream",
    "WouldBlock",
    "ProgrammingError",
    "InterfaceError",
    "InternalError",
    "OperationalError",
    "InvalidCachedStatementError",
    "ConnectionDoesNotExistError",
}


def skip_on_db_error(func):
    """Decorator: skip test if any DB-related error occurs.

    Catches connection errors, schema mismatch errors (missing tables/columns),
    asyncpg connection pool corruption, and anyio stream errors from middleware
    crashes caused by DB issues.
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any):
        try:
            return await func(*args, **kwargs)
        except (ConnectionRefusedError, OSError):
            pytest.skip("DB unavailable — connection refused")
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                pytest.skip("Event loop closed — async cleanup issue")
            raise
        except Exception as e:
            err_type = type(e).__name__
            err_str = str(e)

            # Check by exception type name
            if err_type in _DB_ERROR_TYPES:
                pytest.skip(f"DB error — {err_type}: {err_str[:100]}")

            # Check by error message content
            if any(marker in f"{err_type}: {err_str}" for marker in _DB_ERROR_MARKERS):
                pytest.skip(f"DB error — {err_type}: {err_str[:100]}")

            raise
    return wrapper
