"""Phase B: the documents API and the expiry-reminder sweep, against the DB."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = f"docs_{uuid.uuid4().hex[:8]}"
OTHER = f"docs_other_{uuid.uuid4().hex[:8]}"


class _FakeLM:
    async def chat_local_only(self, **_kw):
        return json.dumps(
            {
                "kind": "insurance",
                "title": "Car insurance",
                "issuer": "HDFC Ergo",
                "holder": "",
                "number": "POL-99887766",
                "issued": "",
                "expires": "",
            }
        )


@pytest.fixture
def fake_lm(monkeypatch):
    import life_graph.api.dependencies as deps

    monkeypatch.setattr(deps, "get_lm_client", lambda: _FakeLM())


def _client(tenant: str = TENANT) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "docs-test"},
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_file_from_text_list_edit_delete_and_isolation(fake_lm):
    async with _client() as c:
        r = await c.post(
            "/api/v1/documents",
            json={"text": "HDFC ERGO motor policy POL-99887766\nPolicy expiry: 20/12/2026"},
        )
        assert r.status_code == 201, r.text
        doc = r.json()["data"]
        assert doc["title"] == "Car insurance" and doc["kind"] == "insurance"
        assert doc["expires_on"] == "2026-12-20" and doc["number_last4"] == "7766"

        r = await c.post("/api/v1/documents", json={})
        assert r.status_code == 422

        r = await c.patch(f"/api/v1/documents/{doc['id']}", json={"expires_on": "2027-01-05"})
        assert r.json()["data"]["expires_on"] == "2027-01-05"
        listed = (await c.get("/api/v1/documents")).json()["data"]
        assert [d["id"] for d in listed] == [doc["id"]]

    async with _client(OTHER) as other:
        assert (await other.get("/api/v1/documents")).json()["data"] == []
        assert (await other.delete(f"/api/v1/documents/{doc['id']}")).status_code == 404

    async with _client() as c:
        assert (await c.delete(f"/api/v1/documents/{doc['id']}")).status_code == 200
        assert (await c.get("/api/v1/documents")).json()["data"] == []


class _Notes:
    def __init__(self):
        self.created = []

    async def create(self, tenant_id, title, **kw):
        self.created.append((tenant_id, title, kw))
        return {}


@pytest.mark.asyncio
@skip_on_db_error
async def test_sweep_sends_each_reminder_once():
    from life_graph.services import assistant_daily, documents
    from life_graph.storage.database import async_session

    tenant = f"docs_sweep_{uuid.uuid4().hex[:8]}"
    today = date(2026, 10, 14)
    async with async_session() as s:
        await documents.create(
            s,
            tenant,
            {"kind": "passport", "title": "Passport", "expires_on": today + timedelta(days=5)},
        )
        await documents.create(
            s,
            tenant,
            {"kind": "warranty", "title": "TV warranty", "expires_on": today + timedelta(days=400)},
        )
        await s.commit()

    notes = _Notes()
    report = await assistant_daily.run_daily(async_session, notes, today)
    mine = [n for n in notes.created if n[0] == tenant]
    assert [n[1] for n in mine] == ["Passport expires in 5 days (19 Oct 2026)"]
    assert mine[0][2]["priority"] == "important" and mine[0][2]["deliver_at_brief"] is False
    assert report["documents"]["sent"] >= 1

    notes2 = _Notes()
    await assistant_daily.run_daily(async_session, notes2, today + timedelta(days=1))
    assert [n for n in notes2.created if n[0] == tenant] == []  # 7-day reminder already sent

    lines = await assistant_daily.brief_lines(async_session, tenant, today)
    assert lines == ["Documents: passport in 5d"]
