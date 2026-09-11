"""Top-level conftest — mock heavy optional dependencies before they're imported.

pgvector is only needed at database runtime, not for unit-testing pure
Python logic like the query router or extraction pipeline. We patch
sys.modules before any life_graph import so SQLAlchemy can build its
models without the real pgvector driver installed.
"""

import os
import sys
from unittest.mock import MagicMock

import sqlalchemy


class _FakeVector(sqlalchemy.types.UserDefinedType):
    """Minimal Vector stand-in so SQLAlchemy can map Mapped[list[float]] columns."""

    cache_ok = True

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim

    def get_col_spec(self) -> str:
        if self.dim:
            return f"VECTOR({self.dim})"
        return "VECTOR"

    def bind_processor(self, dialect):  # noqa: ANN001
        return None

    def result_processor(self, dialect, coltype):  # noqa: ANN001
        return None


# Only patch if pgvector isn't actually installed.
#
# This used to ask `if "pgvector" not in sys.modules`, which is a different
# question and always true here: conftest is the first thing pytest imports,
# so nothing has imported pgvector yet whether or not it exists. The mock was
# therefore installed unconditionally, and the integration tests ran against
# _FakeVector even on a machine with the real driver.
#
# That went unnoticed only because _FakeVector.bind_processor returns None and
# no embedding was ever produced to bind — the configured embedding backend
# was unreachable, so every vector came back empty. The moment embeddings
# started working, 44 integration tests failed inside asyncpg with
# "invalid input for query argument: expected str, got list".
#
# Ask whether the module can be imported, which is what the comment always
# claimed and what the unit tests actually need.
try:
    import pgvector.sqlalchemy  # noqa: F401
except ImportError:
    _pgvector_mock = MagicMock()
    _sa_mock = MagicMock()
    _sa_mock.Vector = _FakeVector
    _pgvector_mock.sqlalchemy = _sa_mock

    sys.modules["pgvector"] = _pgvector_mock
    sys.modules["pgvector.sqlalchemy"] = _sa_mock


# ── Test database isolation ───────────────────────────────────
#
# The integration suite drives the real app against a real Postgres, and
# life_graph.storage.database builds its engine at import time from
# settings.database_url. Unredirected, that is the *development* database:
# a test run writes personas, memories, approvals and audit rows into it
# under tenant ids like "test_tenant" and never takes them out again. That
# is how 14,825 rows across 28 tables accumulated in the dev database, 8,390
# of them personas re-seeded once per tenant per run.
#
# So move the whole process to a sibling database — "<name>_test" — here,
# before anything imports storage.database and freezes the URL. Both URLs
# have to move together: the async one is the app's, the sync one is
# alembic's (see alembic/env.py), and migrating one database while testing
# against the other is worse than not separating them at all.
#
# Set LIFE_GRAPH_TEST_DATABASE_SUFFIX="" to opt out and run against whatever
# is configured. That is for deliberately debugging against real data; it
# reintroduces exactly the pollution described above.


def _with_suffix(url: str, suffix: str) -> str:
    """Return *url* with *suffix* appended to its database name."""
    head, sep, tail = url.rpartition("/")
    if not sep or not tail:
        return url
    name, qmark, query = tail.partition("?")
    if not name or name.endswith(suffix):
        return url
    return f"{head}/{name}{suffix}{qmark}{query}"


TEST_DB_SUFFIX = os.environ.get("LIFE_GRAPH_TEST_DATABASE_SUFFIX", "_test")

if TEST_DB_SUFFIX:
    from life_graph.config import settings  # noqa: E402

    settings.database_url = _with_suffix(settings.database_url, TEST_DB_SUFFIX)
    settings.database_url_sync = _with_suffix(settings.database_url_sync, TEST_DB_SUFFIX)


# Load the ORM base module first so that the models.db <-> autonomy.models
# re-export cycle resolves in the right order regardless of which test module
# pytest collects first (importing autonomy.models before models.db would fail).
import life_graph.models.db  # noqa: E402, F401
