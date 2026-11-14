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

# The suite tests every domain, so it runs the full profile; the memory_core
# profile is tested in its own processes (tests/integration/test_memory_core_profile.py).
# Set before anything imports life_graph.config, which reads it once.
os.environ.setdefault("LIFE_GRAPH_PROFILE", "full")


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


import pytest  # noqa: E402

# Load the ORM base module first so that the models.db <-> autonomy.models
# re-export cycle resolves in the right order regardless of which test module
# pytest collects first (importing autonomy.models before models.db would fail).
import life_graph.models.db  # noqa: E402, F401


@pytest.fixture(autouse=True)
def _no_pr_description_model_calls(monkeypatch):
    """PR-description drafting is on by default and makes a real model call
    for every landed branch. Any test that lands a branch would otherwise call
    a live LLM. Tests of the feature turn it back on and inject a fake chat."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "driver_pr_description_enabled", False)


@pytest.fixture(autouse=True)
def _authorization_stores_stay_in_memory():
    """Put the process-wide authorisation stores back in memory after each test.

    ``capability_store`` and ``standing_rule_store`` are process-wide by
    design (autonomy/approvals/capability.py), and the app's startup attaches
    a Postgres backend to both when ``durable_authorization`` is on, which it
    is by default. Several tests boot the app — proving that wiring — and
    without this the *next* test to call ``capability_store.issue`` would
    quietly be talking to a database instead of a dict, which is how
    ``len(store._issued) == 1`` became ``0`` with nothing in the output to say
    why.

    Detaching afterwards rather than forbidding the attachment on purpose: a
    test that starts the app should attach, because that is the behaviour
    under test. The tests that exercise the durable store itself build their
    own (tests/unit/test_exact_bound_capabilities.py) and are unaffected.
    """
    from life_graph.autonomy.approvals.capability import capability_store, standing_rule_store

    before = (capability_store.durable, standing_rule_store._durable)
    try:
        yield
    finally:
        capability_store.attach_durable(before[0])
        standing_rule_store.attach_durable(before[1])


def fake_request(*, device_id: str | None = None, api_key: str | None = None):
    """The least of a ``Request`` that ``api/auth.py ingress_for`` reads.

    Provenance and owner confirmation are now decided from the authenticated
    ingress (core/trust.py ``classify_ingress``), so the endpoints that make
    those decisions take a ``Request``. Unit tests call them as functions, and
    what they need to vary is who the server says is calling: pass
    ``device_id`` for a paired phone, ``api_key`` for a key, neither for an
    unverified third party.
    """
    from types import SimpleNamespace

    from starlette.datastructures import Headers, QueryParams

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return SimpleNamespace(
        state=SimpleNamespace(device_id=device_id),
        headers=Headers(headers),
        query_params=QueryParams(),
    )
