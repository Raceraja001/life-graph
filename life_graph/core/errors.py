"""Domain exceptions that say which HTTP status they mean (audit L3).

Routes used to pick a status by reading the error's text (``"not found" in
str(exc)`` → 404), so rewording a message changed the API. A service raises
one of these instead, and main.py maps each type to its status with one
handler; a route that catches one can read ``status_code`` off it.

All three subclass ``ValueError``: every existing ``except ValueError`` around
a service call keeps catching them, so converting a raise site is safe for
callers that are not routes (workers, tools, other services).

No HTTP or web-framework import here — services raise these.
"""

from __future__ import annotations


class DomainError(ValueError):
    """A request the domain refuses; ``status_code`` is the HTTP meaning."""

    status_code: int = 400
    code: str = "BAD_REQUEST"


class InvalidInputError(DomainError):
    """The input is wrong for this operation (400)."""

    status_code = 400
    code = "BAD_REQUEST"


class NotFoundError(DomainError):
    """The thing named does not exist for this tenant (404)."""

    status_code = 404
    code = "NOT_FOUND"


class ConflictError(DomainError):
    """The operation clashes with existing state, e.g. a duplicate (409)."""

    status_code = 409
    code = "CONFLICT"


# PostgreSQL SQLSTATEs (https://www.postgresql.org/docs/current/errcodes-appendix.html).
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"


def sqlstate(exc: BaseException) -> str | None:
    """The PostgreSQL SQLSTATE behind a SQLAlchemy/asyncpg/psycopg error, if any.

    SQLAlchemy wraps the driver error as ``exc.orig``; asyncpg's adapter keeps
    the code on ``sqlstate`` (and on the original asyncpg error, its
    ``__cause__``), psycopg2 on ``pgcode``.
    """
    seen: set[int] = set()
    todo: list[BaseException | None] = [exc]
    while todo:
        err = todo.pop()
        if err is None or id(err) in seen:
            continue
        seen.add(id(err))
        for attr in ("sqlstate", "pgcode"):
            code = getattr(err, attr, None)
            if isinstance(code, str) and code:
                return code
        todo.extend([getattr(err, "orig", None), err.__cause__])
    return None
