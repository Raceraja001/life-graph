"""Phase G: study cards over the API and the Telegram /review loop."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error


class _LM:
    async def chat_local_only(self, **_kw):
        return json.dumps(
            {
                "cards": [
                    {"front": "What does SM-2 schedule?", "back": "Card review intervals."},
                    {"front": "Minimum SM-2 ease?", "back": "1.3"},
                ]
            }
        )


class _Redis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)


@pytest.fixture
def fakes(monkeypatch):
    import life_graph.api.dependencies as deps
    import life_graph.storage.redis as r

    redis = _Redis()
    monkeypatch.setattr(deps, "get_lm_client", lambda: _LM())
    monkeypatch.setattr(r, "get_redis", lambda: redis)
    return redis


@pytest.mark.asyncio
@skip_on_db_error
async def test_generate_dedupe_grade_and_review_on_telegram(fakes):
    from life_graph.services import study

    tenant = f"study_{uuid.uuid4().hex[:8]}"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "study-test"},
    ) as c:
        assert (await c.post("/api/v1/study/generate", json={})).status_code == 422
        r = await c.post("/api/v1/study/generate", json={"text": "notes on SM-2", "deck": "memory"})
        assert r.json()["data"] == {"written": 2, "added": 2}
        again = await c.post("/api/v1/study/generate", json={"text": "notes on SM-2"})
        assert again.json()["data"]["added"] == 0  # same fronts: no duplicates

        due = (await c.get("/api/v1/study/due")).json()
        assert due["meta"]["due"] == 2
        first = due["data"][0]
        r = await c.post(f"/api/v1/study/cards/{first['id']}/grade", json={"grade": "good"})
        assert r.json()["data"]["interval_days"] == 1
        assert (
            await c.post(f"/api/v1/study/cards/{first['id']}/grade", json={"grade": "meh"})
        ).status_code == 422
        assert (await c.get("/api/v1/study/due")).json()["meta"]["due"] == 1
        decks = (await c.get("/api/v1/study/decks")).json()["data"]
        assert decks == [{"deck": "memory", "cards": 2, "due": 1, "reviewed": 1, "retention": 1.0}]

    chat = 9100001
    today = date.today()
    step = await study.telegram_review(chat, tenant, "", today)
    assert "Q: " in step and "1 due" in step
    shown = await study.telegram_review(chat, tenant, "show", today)
    assert shown.startswith("A: ")
    graded = await study.telegram_review(chat, tenant, "easy", today)
    assert graded.startswith("Next time: in 1 day") and "Nothing due" in graded
    assert (
        await study.telegram_review(chat, tenant, "show", today)
        == "No card in progress. /review to start."
    )
    tomorrow = await study.telegram_review(chat, tenant, "", today + timedelta(days=1))
    assert "2 due" in tomorrow
