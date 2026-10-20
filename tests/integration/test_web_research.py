"""Jobs 6 and 10 against the database: the tech watch stores each source once,
the Monday digest sends each finding once, and the two APIs.

Search, fetch and the worker are replaced at the module boundary
(services/web_pages.py, services/workers.run_worker).
"""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"watch_{uuid.uuid4().hex[:8]}"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "watch-test"}
TOPIC = "AI coding agents"


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


def _fake_web(monkeypatch, pages: dict[str, str], findings: list[dict], calls: list):
    from life_graph.services import web_pages, workers

    async def seen(key):
        return None, set()

    async def candidates(queries, *, limit, skip=frozenset()):
        return [web_pages.Hit(url=u, title=u) for u in pages]

    async def read(urls, chars=0):
        return {u: pages[u] for u in urls}

    async def run_worker(envelope, *, brief, inputs, tools, tenant_id, reasoning=True):
        calls.append(inputs)
        here = [f for f in findings if f"SOURCE: {f['source']}" in inputs]
        return workers.WorkerResult(envelope=envelope, model="m", text=json.dumps(here))

    monkeypatch.setattr(web_pages, "seen", seen)
    monkeypatch.setattr(web_pages, "candidates", candidates)
    monkeypatch.setattr(web_pages, "read", read)
    monkeypatch.setattr(workers, "run_worker", run_worker)


@pytest.mark.asyncio
@skip_on_db_error
async def test_tech_watch_stores_once_and_digest_sends_once(monkeypatch, client):
    from life_graph.config import settings
    from life_graph.services import web_research
    from life_graph.storage.database import async_session

    today = date.today().isoformat()
    pages = {f"https://news.example.com/{i}": f"release {i}" for i in range(3)}
    findings = [
        {"title": f"Agent {i} released", "summary": "s", "source": u, "published_on": today}
        for i, u in enumerate(pages)
    ] + [
        # A second release on the same page is its own row.
        {"title": "Agent 0 plugin", "source": "https://news.example.com/0", "published_on": today},
        {"title": "Old news", "source": "https://news.example.com/0", "published_on": "2020-01-01"},
        {"title": "Undated", "source": "https://news.example.com/1"},
    ]
    calls: list = []
    _fake_web(monkeypatch, pages, findings, calls)

    first = await web_research.scan_topic(async_session, TENANT, TOPIC, ["q"])
    assert first == {"searched": 3, "read": 3, "found": 4, "stored": 4}
    assert len(calls) == 2  # two pages per reader call
    again = await web_research.scan_topic(async_session, TENANT, TOPIC, ["q"])
    assert again["stored"] == 0  # one row per item per page per topic

    api = await client.get("/api/v1/tech-watch", params={"topic": TOPIC})
    assert api.status_code == 200
    rows = api.json()["data"]
    assert sorted(r["title"] for r in rows) == [
        "Agent 0 plugin",
        *[f"Agent {i} released" for i in range(3)],
    ]
    assert rows[0]["published_on"] == today and rows[0]["sent_at"] is None
    assert (await client.get("/api/v1/tech-watch", params={"topic": "other"})).json()["data"] == []

    monkeypatch.setattr(settings, "tech_watch_digest_per_topic", 2)
    async with async_session() as s:
        lines = await web_research.digest_lines(s, TENANT)
    assert lines[0] == f"{TOPIC}:" and len(lines) == 3
    assert lines[1].startswith("  - Agent ") and " — https://news.example.com/" in lines[1]
    async with async_session() as s:
        rest = await web_research.digest_lines(s, TENANT)
    assert len(rest) == 3  # the two left over
    async with async_session() as s:
        assert await web_research.digest_lines(s, TENANT) == []  # nothing new: no section

    from life_graph.core.events import event_bus
    from life_graph.services.brief import BriefComposer

    assert await BriefComposer(async_session, event_bus)._tech_watch_lines(TENANT) == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_research_api(monkeypatch, client):
    page = "https://example.com/groq"
    reply = [{"text": "Groq allows 30 requests a minute.", "sources": [page]}]
    from life_graph.services import web_pages, workers

    async def candidates(queries, *, limit, skip=frozenset()):
        return [web_pages.Hit(url=page, title="Groq limits")]

    async def read(urls, chars=0):
        return {page: "30 requests a minute"}

    async def run_worker(envelope, *, brief, inputs, tools, tenant_id, reasoning=True):
        assert tenant_id == TENANT and envelope == "research" and tools == ()
        return workers.WorkerResult(envelope=envelope, model="m", text=json.dumps(reply))

    monkeypatch.setattr(web_pages, "candidates", candidates)
    monkeypatch.setattr(web_pages, "read", read)
    monkeypatch.setattr(workers, "run_worker", run_worker)

    resp = await client.post("/api/v1/research", json={"question": "Groq free limits?"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["answer"] == "- Groq allows 30 requests a minute. [1]"
    assert data["sources"] == [{"url": page, "title": "Groq limits"}]
    assert data["claims"] == reply and data["model"] == "m"
    assert (await client.post("/api/v1/research", json={"question": "x"})).status_code == 422
