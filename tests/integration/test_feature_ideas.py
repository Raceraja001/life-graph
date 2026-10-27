"""The feature watch against the database (AC-10.7 to AC-10.12): findings are rated and
assessed, pricing never reaches the model, the same feature from two sites is one idea,
ideas sort by worth, decisions work, and the brief leaves out what should not go.

Search, fetch and the worker are replaced at the module boundary, as in test_web_research.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"ideas_{uuid.uuid4().hex[:8]}"
TOPIC = "New features in AI assistant apps"
TODAY = date.today().isoformat()
OFFICIAL = "https://help.openai.com/notes"
TRACKER = "https://releasebot.io/updates/openai/chatgpt"
LURE = "https://github.com/mapchancellorhaul/open-webui-2026"
PAGES = {OFFICIAL: "locked chats; MoMo payments", TRACKER: "lock chats; try-on", LURE: "Open WebUI 2026"}
FINDINGS = [
    {"title": "ChatGPT adds locked chats", "summary": "hide chats behind a PIN", "source": OFFICIAL, "published_on": TODAY},
    {"title": "ChatGPT accepts MoMo payments", "summary": "a payment method for subscriptions", "source": OFFICIAL, "published_on": TODAY},
    {"title": "ChatGPT can now lock chats with a PIN", "summary": "the same, other words", "source": TRACKER, "published_on": TODAY},
    {"title": "ChatGPT adds virtual try-on for clothes", "summary": "see an outfit on you", "source": TRACKER, "published_on": TODAY},
    {"title": "Open WebUI 2026 for Windows released", "summary": "download", "source": LURE, "published_on": TODAY},
]


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as c:
        yield c


def _fake(monkeypatch, assessed: list):
    from life_graph.services import feature_ideas, web_pages, workers

    async def seen(key):
        return None, set()

    async def candidates(queries, *, limit, skip=frozenset(), **_kw):
        return [web_pages.Hit(url=u, title=u) for u in PAGES]

    async def read(urls, chars=0):
        return {u: PAGES[u] for u in urls}

    async def run_worker(envelope, *, brief, inputs, tools, tenant_id, reasoning=True):
        if brief.startswith(feature_ideas.ASSESSOR_BRIEF[:40]):
            assert tools == ()  # the assessor acts on nothing
            items = json.loads(inputs)["FINDINGS"]
            assessed.extend(i["title"] for i in items)
            first_lock = next(i["id"] for i in items if "adds locked" in i["title"])
            out = []
            for i in items:
                lock = "lock" in i["title"]
                out.append(
                    {
                        "id": i["id"],
                        "is_feature": True,
                        "app": "ChatGPT",
                        "fit": "part" if lock else "new",
                        "suggestion": "A temporary chat with a PIN." if lock else "Try clothes on.",
                        "worth": "high" if lock else "low",
                        "why": "privacy" if lock else "shopping",
                        "same_as": first_lock if lock and i["id"] != first_lock else None,
                    }
                )
            return workers.WorkerResult(envelope=envelope, model="m", text=json.dumps(out))
        here = [f for f in FINDINGS if f"SOURCE: {f['source']}" in inputs]
        return workers.WorkerResult(envelope=envelope, model="m", text=json.dumps(here))

    monkeypatch.setattr(web_pages, "seen", seen)
    monkeypatch.setattr(web_pages, "candidates", candidates)
    monkeypatch.setattr(web_pages, "read", read)
    monkeypatch.setattr(workers, "run_worker", run_worker)


@pytest.mark.asyncio
@skip_on_db_error
async def test_feature_watch_rates_assesses_lists_decides_and_briefs(monkeypatch, client):
    from life_graph.config import settings
    from life_graph.services import web_research
    from life_graph.storage.database import async_session

    monkeypatch.setattr(
        settings, "tech_watch_topics", json.dumps({TOPIC: {"ideas": True, "queries": ["q"]}})
    )
    assessed: list = []
    _fake(monkeypatch, assessed)

    out = await web_research.tech_watch(async_session, TENANT)
    assert out[TOPIC]["stored"] == 5
    assert out[TOPIC]["assessed"] == {"to_assess": 3, "assessed": 3, "pricing": 1}
    assert "Open WebUI 2026 for Windows released" not in assessed  # suspicious: never sent
    assert "ChatGPT accepts MoMo payments" not in assessed  # pricing: decided in code

    ideas = (await client.get("/api/v1/tech-watch/ideas")).json()["data"]
    # Most worth first; the second report of locked chats is not its own idea.
    assert [i["title"] for i in ideas] == [
        "ChatGPT adds locked chats",
        "ChatGPT adds virtual try-on for clothes",
    ]
    idea = ideas[0]
    assert (idea["trust"], idea["fit"], idea["worth"], idea["worth_why"]) == ("official", "part", "high", "privacy")
    assert idea["also_from"] == [TRACKER]  # both sources, one idea
    flagged = (await client.get("/api/v1/tech-watch/ideas", params={"status": "flagged"})).json()["data"]
    assert [f["trust"] for f in flagged] == ["suspicious"]

    # The brief: the two features once each, with fit and suggestion; no pricing, no repeat, no lure.
    async with async_session() as s:
        lines = await web_research.digest_lines(s, TENANT, mark=False)
    assert lines[0] == f"{TOPIC}:" and len(lines) == 3
    assert any("[part for Jarvis: A temporary chat with a PIN.]" in line for line in lines)
    assert not any("MoMo" in line or "lock chats with a PIN" in line for line in lines)

    r = await client.post(f"/api/v1/tech-watch/{idea['id']}/decision", json={"decision": "consider"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "considering"
    open_now = (await client.get("/api/v1/tech-watch/ideas")).json()["data"]
    assert [i["title"] for i in open_now] == ["ChatGPT adds virtual try-on for clothes"]
    considering = (await client.get("/api/v1/tech-watch/ideas", params={"status": "considering"})).json()["data"]
    assert [c["id"] for c in considering] == [idea["id"]]

    await client.post(f"/api/v1/tech-watch/{idea['id']}/decision", json={"decision": "not_for_us"})
    async with async_session() as s:
        left = await web_research.digest_lines(s, TENANT, mark=False)
    assert not any("adds locked chats" in line for line in left)  # ruled out: not sent

    assert (await client.post(f"/api/v1/tech-watch/{idea['id']}/decision", json={"decision": "build it"})).status_code == 422
    assert (await client.post(f"/api/v1/tech-watch/{uuid.uuid4()}/decision", json={"decision": "dismiss"})).status_code == 404
    other = await client.post(
        f"/api/v1/tech-watch/{idea['id']}/decision", json={"decision": "dismiss"}, headers={"X-Tenant-ID": "someone_else"}
    )
    assert other.status_code == 404  # another tenant's finding


@pytest.mark.asyncio
@skip_on_db_error
async def test_redo_judges_undecided_ideas_again_and_keeps_decided_ones(monkeypatch, client):
    from life_graph.models.assistant import TopicFinding
    from life_graph.services import feature_ideas
    from life_graph.storage.database import async_session

    tenant = f"{TENANT}_redo"
    assessed: list = []
    _fake(monkeypatch, assessed)
    async with async_session() as s:
        for i, (title, status) in enumerate([("ChatGPT adds locked chats", "new"), ("ChatGPT adds virtual try-on for clothes", "not_for_us")]):
            s.add(TopicFinding(tenant_id=tenant, topic=TOPIC, dedup_key=f"k{i}", title=title, summary="s",
                               source_url=OFFICIAL, published_on=date.today(), status=status, is_feature=True, fit="new"))
        await s.commit()

    first = await feature_ideas.assess(async_session, tenant, TOPIC)
    assert first["to_assess"] == 0  # already assessed
    redo = await feature_ideas.assess(async_session, tenant, TOPIC, redo=True)
    assert redo["to_assess"] == 1 and assessed == ["ChatGPT adds locked chats"]  # the decided one is kept
