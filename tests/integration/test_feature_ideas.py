"""The feature watch against the database (AC-10.7 to AC-10.10): findings are rated and
assessed, the ideas list and decisions work, and the brief leaves out what should not go.

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
PAGES = {
    "https://help.openai.com/notes": "locked chats; MoMo payments",
    "https://github.com/mapchancellorhaul/open-webui-2026": "Open WebUI 2026 for Windows",
}
FINDINGS = [
    {
        "title": "ChatGPT adds locked chats",
        "summary": "hide chats behind a PIN",
        "source": "https://help.openai.com/notes",
        "published_on": TODAY,
    },
    {
        "title": "ChatGPT accepts MoMo payments",
        "summary": "a payment method in Vietnam",
        "source": "https://help.openai.com/notes",
        "published_on": TODAY,
    },
    {
        "title": "Open WebUI 2026 for Windows released",
        "summary": "download",
        "source": "https://github.com/mapchancellorhaul/open-webui-2026",
        "published_on": TODAY,
    },
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
            items = json.loads(inputs)
            assessed.extend(i["title"] for i in items)
            out = [
                {
                    "id": i["id"],
                    "is_feature": "locked" in i["title"],
                    "app": "ChatGPT",
                    "fit": "part",
                    "suggestion": "A temporary chat with a PIN.",
                }
                for i in items
            ]
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
    assert out[TOPIC]["stored"] == 3
    assert out[TOPIC]["assessed"] == {"to_assess": 2, "assessed": 2}
    assert (
        "Open WebUI 2026 for Windows released" not in assessed
    )  # suspicious: never sent to the model

    ideas = (await client.get("/api/v1/tech-watch/ideas")).json()["data"]
    assert [i["title"] for i in ideas] == [
        "ChatGPT adds locked chats"
    ]  # payments are not a feature
    idea = ideas[0]
    assert (idea["trust"], idea["fit"], idea["app"], idea["status"]) == (
        "official",
        "part",
        "ChatGPT",
        "new",
    )
    flagged = (await client.get("/api/v1/tech-watch/ideas", params={"status": "flagged"})).json()[
        "data"
    ]
    assert [f["trust"] for f in flagged] == ["suspicious"]

    # The brief: only the feature, with its fit and suggestion.
    async with async_session() as s:
        lines = await web_research.digest_lines(s, TENANT, mark=False)
    assert lines[0] == f"{TOPIC}:" and len(lines) == 2
    assert "[part for Jarvis: A temporary chat with a PIN.]" in lines[1]

    r = await client.post(
        f"/api/v1/tech-watch/{idea['id']}/decision", json={"decision": "consider"}
    )
    assert r.status_code == 200 and r.json()["data"]["status"] == "considering"
    assert (await client.get("/api/v1/tech-watch/ideas")).json()["data"] == []
    considering = (
        await client.get("/api/v1/tech-watch/ideas", params={"status": "considering"})
    ).json()["data"]
    assert [c["id"] for c in considering] == [idea["id"]]

    await client.post(f"/api/v1/tech-watch/{idea['id']}/decision", json={"decision": "not_for_us"})
    async with async_session() as s:
        assert await web_research.digest_lines(s, TENANT, mark=False) == []  # ruled out: not sent

    assert (
        await client.post(
            f"/api/v1/tech-watch/{idea['id']}/decision", json={"decision": "build it"}
        )
    ).status_code == 422
    assert (
        await client.post(
            f"/api/v1/tech-watch/{uuid.uuid4()}/decision", json={"decision": "dismiss"}
        )
    ).status_code == 404
    other = await client.post(
        f"/api/v1/tech-watch/{idea['id']}/decision",
        json={"decision": "dismiss"},
        headers={"X-Tenant-ID": "someone_else"},
    )
    assert other.status_code == 404  # another tenant's finding
