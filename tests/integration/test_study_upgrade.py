"""Study upgrade end to end (docs/research/study-helper-spec-2026-10.html):
drafts from a saved document, edit/accept/reject, grading writes the review
log, progress, tenant isolation, and the daily nudge."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error


class _LM:
    def __init__(self):
        self.calls = []

    async def chat_local_only(self, **kw):
        self.calls.append(kw)
        return json.dumps(
            {
                "cards": [
                    {"front": "How long is the knee-surgery waiting period?", "back": "2 years."},
                    {"front": "What is the cover?", "back": "5 lakh."},
                ]
            }
        )


@pytest.fixture
def lm(monkeypatch):
    import life_graph.api.dependencies as deps

    client = _LM()
    monkeypatch.setattr(deps, "get_lm_client", lambda: client)
    return client


def _client(tenant: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "study-test"},
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_drafts_review_progress_and_isolation(lm):
    a, b = f"studya_{uuid.uuid4().hex[:8]}", f"studyb_{uuid.uuid4().hex[:8]}"
    async with _client(a) as ca, _client(b) as cb:
        doc = (
            await ca.post(
                "/api/v1/documents",
                json={
                    "kind": "policy",
                    "title": "Health insurance",
                    "notes": "Covers 5 lakh; waiting period 2 years for knee surgery.",
                },
            )
        ).json()["data"]

        # Tenant B cannot study tenant A's document: nothing reaches the model.
        r = await cb.post(
            "/api/v1/study/drafts", json={"source": "document", "source_id": doc["id"]}
        )
        assert r.status_code == 201 and r.json()["data"]["drafted"] == 0
        assert lm.calls == []

        assert (
            await ca.post("/api/v1/study/drafts", json={"source": "document"})
        ).status_code == 422
        r = await ca.post(
            "/api/v1/study/drafts", json={"source": "document", "source_id": doc["id"]}
        )
        out = r.json()["data"]
        assert out["drafted"] == 2 and "waiting period" in lm.calls[0]["messages"][1]["content"]
        assert {d["deck"] for d in out["drafts"]} == {"Health insurance"}

        drafts = (await ca.get("/api/v1/study/drafts")).json()["data"]
        assert [d["status"] for d in drafts] == ["draft", "draft"]
        assert (await ca.get("/api/v1/study/due")).json()["meta"]["due"] == 0
        assert (await cb.get("/api/v1/study/drafts")).json()["data"] == []

        first, second = drafts
        r = await ca.patch(
            f"/api/v1/study/cards/{first['id']}", json={"back": "Two years.", "deck": "insurance"}
        )
        assert r.json()["data"]["back"] == "Two years."
        clash = await ca.patch(
            f"/api/v1/study/cards/{second['id']}", json={"front": first["front"]}
        )
        assert clash.status_code == 409
        assert (
            await cb.patch(f"/api/v1/study/cards/{first['id']}", json={"back": "x"})
        ).status_code == 404

        assert (await ca.post("/api/v1/study/drafts/accept", json={})).status_code == 422
        # B accepting A's draft changes nothing.
        r = await cb.post("/api/v1/study/drafts/accept", json={"ids": [first["id"]]})
        assert r.json()["data"]["accepted"] == 0
        r = await ca.post("/api/v1/study/drafts/accept", json={"ids": [first["id"]]})
        assert r.json()["data"]["accepted"] == 1
        r = await ca.post("/api/v1/study/drafts/reject", json={"all": True})
        assert r.json()["data"]["rejected"] == 1
        assert (await ca.get("/api/v1/study/drafts")).json()["data"] == []

        due = (await ca.get("/api/v1/study/due")).json()
        assert due["meta"]["due"] == 1 and due["data"][0]["deck"] == "insurance"
        g = await ca.post(f"/api/v1/study/cards/{first['id']}/grade", json={"grade": "good"})
        assert g.json()["data"]["interval_days"] == 1 and g.json()["data"]["maturity"] == "young"

        p = (await ca.get("/api/v1/study/progress")).json()["data"]
        assert p["streak"] == 1 and p["reviewed_today"] == 1 and p["learned"] == 1
        assert p["accuracy"] == 1.0 and p["due"] == 0
        assert p["decks"] == [{"deck": "insurance", "reviews": 1, "accuracy": 1.0}]
        pb = (await cb.get("/api/v1/study/progress")).json()["data"]
        assert pb["reviewed_today"] == 0 and pb["streak"] == 0 and pb["decks"] == []

        r = await ca.patch(f"/api/v1/study/cards/{first['id']}", json={"status": "suspended"})
        assert r.json()["data"]["status"] == "suspended"
        p = (await ca.get("/api/v1/study/progress")).json()["data"]
        assert p["suspended"] == 1 and p["learned"] == 0


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_daily_nudge_goes_once(lm):
    from sqlalchemy import select

    from life_graph.api.assistant import _today
    from life_graph.config import settings
    from life_graph.models.db import Notification
    from life_graph.services import study, study_nudge
    from life_graph.storage.database import async_session

    tenant = f"studyn_{uuid.uuid4().hex[:8]}"
    today = _today()
    async with async_session() as session:
        await study.add_cards(
            session, tenant, [{"front": "Q one?", "back": "A"}], deck="x", today=today
        )
        await session.commit()
    tz = ZoneInfo(settings.user_timezone)
    now = datetime.combine(today, time(19, 0), tzinfo=tz)
    async with async_session() as session:
        assert await study_nudge.run_tenant(session, tenant, now, tz, hour=18) == 1
    async with async_session() as session:
        assert await study_nudge.run_tenant(session, tenant, now, tz, hour=18) == 0
        rows = (
            (await session.execute(select(Notification).where(Notification.tenant_id == tenant)))
            .scalars()
            .all()
        )
    assert len(rows) == 1 and rows[0].body.startswith("1 card due today")
