"""HTTP status comes from the exception's type, never its text (audit L3).

Routes used to read the message: ``"not found" in str(exc)`` → 404, and
``"unique" in str(exc)`` → 409 for a duplicate memory link. Rewording a message
changed the API, and a message that merely *mentioned* "not found" became a 404.
Services now raise core/errors.py types, and a duplicate is recognised by
PostgreSQL's SQLSTATE 23505, not by the words in the driver's message.
"""

from __future__ import annotations

import contextlib
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from life_graph.api import middleware
from life_graph.core.errors import (
    ConflictError,
    DomainError,
    InvalidInputError,
    NotFoundError,
    sqlstate,
)
from life_graph.main import app

TENANT = "domain-errors"


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setitem(middleware._tenant_status_cache, TENANT, (time.monotonic() + 3600, None))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as http:
        yield http
    app.dependency_overrides.clear()


# ── the types ──────────────────────────────────────────────


def test_types_are_value_errors_with_their_status():
    """Callers that catch ValueError (workers, tools) keep catching them."""
    for cls, status in ((InvalidInputError, 400), (NotFoundError, 404), (ConflictError, 409)):
        assert issubclass(cls, DomainError)
        assert issubclass(cls, ValueError)
        assert cls("x").status_code == status


def test_sqlstate_reads_the_driver_code_through_the_wrapper():
    class PgError(Exception):
        sqlstate = "23505"

    class PsycopgError(Exception):
        pgcode = "23503"

    assert sqlstate(IntegrityError("INSERT", {}, PgError("boom"))) == "23505"
    assert sqlstate(IntegrityError("INSERT", {}, PsycopgError("boom"))) == "23503"
    assert sqlstate(RuntimeError("no code")) is None


async def test_an_uncaught_domain_error_maps_centrally(client):
    """A DomainError that no route catches still gets its status and the envelope."""
    from life_graph.api.dependencies import get_store

    def gone():
        raise NotFoundError("no such thing")

    app.dependency_overrides[get_store] = gone
    response = await client.get(f"/api/v1/memories/{uuid.uuid4()}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["detail"] == "no such thing"


# ── memory links: SQLSTATE, not message text ───────────────


def _link_body() -> dict:
    return {
        "source_memory_id": str(uuid.uuid4()),
        "target_memory_id": str(uuid.uuid4()),
        "link_type": "RELATED_TO",
    }


def _session_whose_commit_raises(exc: Exception):
    session = MagicMock()
    session.commit = AsyncMock(side_effect=exc)

    @contextlib.asynccontextmanager
    async def factory():
        yield session

    return factory


@pytest.mark.parametrize(
    ("state", "expected"),
    [("23505", ConflictError), ("23503", NotFoundError)],
)
async def test_create_link_classifies_integrity_errors_by_sqlstate(monkeypatch, state, expected):
    from life_graph.services.memory import links

    class PgError(Exception):
        sqlstate = state

    # Deliberately no "unique"/"duplicate" in the text: the old route matched
    # those words and would have let this through as a 500.
    error = IntegrityError("INSERT INTO memory_links ...", {}, PgError("constraint violated"))
    monkeypatch.setattr(links, "async_session", _session_whose_commit_raises(error))
    monkeypatch.setattr(links, "_both_in_tenant", AsyncMock(return_value=True))

    with pytest.raises(expected):
        await links.create_link(uuid.uuid4(), uuid.uuid4(), "RELATED_TO", tenant_id=TENANT)


async def test_create_link_reraises_other_integrity_errors(monkeypatch):
    from life_graph.services.memory import links

    class PgError(Exception):
        sqlstate = "23514"  # check_violation: not ours to reinterpret

    error = IntegrityError("INSERT", {}, PgError("check"))
    monkeypatch.setattr(links, "async_session", _session_whose_commit_raises(error))
    monkeypatch.setattr(links, "_both_in_tenant", AsyncMock(return_value=True))

    with pytest.raises(IntegrityError):
        await links.create_link(uuid.uuid4(), uuid.uuid4(), "RELATED_TO", tenant_id=TENANT)


@pytest.mark.parametrize(
    ("raised", "status"),
    [
        (ConflictError("Link already exists"), 409),
        (NotFoundError("Memory not found"), 404),
        (InvalidInputError("Cannot link a memory to itself"), 400),
    ],
)
async def test_link_route_status_follows_the_type(client, monkeypatch, raised, status):
    from life_graph.api import memory_links

    monkeypatch.setattr(memory_links.link_service, "create_link", AsyncMock(side_effect=raised))
    response = await client.post(
        f"/api/v1/memories/{uuid.uuid4()}/links",
        json=_link_body(),
    )

    assert response.status_code == status, response.text
    assert response.json()["detail"] == str(raised)


async def test_link_route_does_not_turn_a_message_into_a_409(client, monkeypatch):
    """An unrelated failure that mentions "duplicate" is not a conflict."""
    from life_graph.api import memory_links

    monkeypatch.setattr(
        memory_links.link_service,
        "create_link",
        AsyncMock(side_effect=RuntimeError("duplicate connection pool shutdown")),
    )
    response = await client.post(
        f"/api/v1/memories/{uuid.uuid4()}/links",
        json=_link_body(),
    )

    assert response.status_code == 500


# ── connectors ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raised", "status"),
    [
        ("missing", 404),
        ("plugin_text", 400),
    ],
)
async def test_connector_account_status_follows_the_type(client, monkeypatch, raised, status):
    from life_graph.api import connectors as connectors_api
    from life_graph.connectors.runtime import AccountError, AccountNotFoundError

    exc = (
        AccountNotFoundError("account not found")
        if raised == "missing"
        # A plugin's own words; it says "not found" but the account exists.
        else AccountError("IMAP folder INBOX not found on the server")
    )
    runtime = MagicMock()
    runtime.update_account = AsyncMock(side_effect=exc)
    monkeypatch.setattr(connectors_api, "get_runtime", lambda: runtime)

    response = await client.patch(
        f"/api/v1/connectors/accounts/{uuid.uuid4()}", json={"display_name": "x"}
    )

    assert response.status_code == status, response.text


# ── judgment ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raised", "status"),
    [
        (NotFoundError("Prediction gone"), 404),
        # A plain ValueError that mentions the words is a bad request, not a 404.
        (ValueError("statement not found in the capture"), 400),
    ],
)
async def test_accept_prediction_status_follows_the_type(client, raised, status):
    from life_graph.api import judgment

    svc = MagicMock()
    svc.accept_suggestion = AsyncMock(side_effect=raised)

    async def override():
        yield svc

    app.dependency_overrides[judgment._get_judgment_service] = override
    response = await client.post(f"/api/v1/judgment/predictions/{uuid.uuid4()}/accept", json={})

    assert response.status_code == status, response.text


async def test_judgment_service_raises_not_found_by_type():
    from life_graph.services.judgment import JudgmentService

    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(NotFoundError):
        await JudgmentService(session).dismiss_suggestion(TENANT, uuid.uuid4())


# ── evidence ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raised", "status"),
    [
        (ConflictError("Evidence with source_url 'u' already exists"), 409),
        (NotFoundError("Preference p not found"), 404),
        (ValueError("summary too vague"), 400),
    ],
)
async def test_create_evidence_status_follows_the_type(client, raised, status):
    from life_graph.api.dependencies import get_evidence_store

    store = MagicMock()
    store.create = AsyncMock(side_effect=raised)
    app.dependency_overrides[get_evidence_store] = lambda: store

    response = await client.post(
        "/api/v1/evidence/",
        json={"preference_id": str(uuid.uuid4()), "source_type": "paper", "summary": "s"},
    )

    assert response.status_code == status, response.text
