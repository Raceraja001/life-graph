"""Job 1, free LLM offers, against the database: catalog diff, news scan,
evaluation, the adoption approval, the API and the brief line.

Network and models are replaced at the module boundary (catalog fetch, page
search/read, the worker, the smoke test and benchmark); everything stored and
every rule about statuses, adoption and the cloud list runs for real.
"""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"offers_{uuid.uuid4().hex[:8]}"
TENANT_HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "offers-test"}


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=TENANT_HEADERS
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def _keys_and_reset(monkeypatch):
    from life_graph.config import settings
    from life_graph.services import compute_router

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "dev_cloud_models", "openrouter/base:free")
    yield
    compute_router.set_adopted([])


async def _offers(**where):
    from life_graph.models.assistant import LlmOffer
    from life_graph.storage.database import async_session

    async with async_session() as s:
        q = select(LlmOffer).where(LlmOffer.tenant_id == TENANT)
        for k, v in where.items():
            q = q.where(getattr(LlmOffer, k) == v)
        return (await s.execute(q.order_by(LlmOffer.first_seen_at))).scalars().all()


async def _add_offer(model_id: str, status: str = "new", evaluation: dict | None = None):
    from life_graph.models.assistant import LlmOffer
    from life_graph.storage.database import async_session

    async with async_session() as s:
        offer = LlmOffer(
            tenant_id=TENANT,
            dedup_key=f"openrouter|{model_id}|{uuid.uuid4().hex[:6]}",
            provider="openrouter",
            model_id=model_id,
            kind="free_model",
            title=model_id,
            source="catalog_diff",
            status=status,
            evaluation=evaluation or {},
        )
        s.add(offer)
        await s.commit()
        return offer.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_catalog_diff_baseline_new_and_gone(monkeypatch):
    from life_graph.services import compute_router, llm_offers
    from life_graph.storage.database import async_session

    provider = f"test{uuid.uuid4().hex[:6]}"  # never the real catalogs' snapshots
    monkeypatch.setattr(llm_offers, "PROVIDERS", (provider,))
    catalogs = iter(
        [
            ["openrouter/a:free", "openrouter/b:free"],
            ["openrouter/a:free", "openrouter/b:free", "openrouter/c:free"],
            ["openrouter/a:free", "openrouter/b:free"],
        ]
    )

    async def fetch(p, client=None):
        return next(catalogs)

    monkeypatch.setattr(llm_offers, "fetch_free_models", fetch)
    notes = []

    async def notify(tenant_id, title, body):
        notes.append(title)

    monkeypatch.setattr(llm_offers, "_notify", notify)

    first = await llm_offers.catalog_diff(async_session, [TENANT])
    assert first[provider] == {"baseline": 2}  # today's models are not "new"
    assert await _offers() == []

    second = await llm_offers.catalog_diff(async_session, [TENANT])
    assert second[provider] == {"new": ["openrouter/c:free"], "gone": []}
    (offer,) = await _offers()
    assert (offer.model_id, offer.status, offer.kind) == ("openrouter/c:free", "new", "free_model")

    from life_graph.models.assistant import LlmOffer

    async with async_session() as s:
        row = await s.get(LlmOffer, offer.id)
        row.status = "adopted"
        await s.commit()
        await llm_offers.refresh_adopted(s)
    assert "openrouter/c:free" in compute_router.cloud_models()

    third = await llm_offers.catalog_diff(async_session, [TENANT])
    assert third[provider] == {"new": [], "gone": ["openrouter/c:free"]}
    (offer,) = await _offers()
    assert offer.status == "gone"
    assert "openrouter/c:free" not in compute_router.cloud_models()  # dropped from the list
    assert notes == ["Adopted free model openrouter/c:free is gone"]


@pytest.mark.asyncio
@skip_on_db_error
async def test_news_scan_records_validated_offers(monkeypatch):
    from life_graph.services import llm_offers, workers
    from life_graph.storage.database import async_session

    page = "https://example.com/groq-free"
    monkeypatch.setattr(llm_offers, "candidate_pages", lambda t: _coro([page]))
    monkeypatch.setattr(llm_offers, "read_pages", lambda urls: _coro({page: "Groq: free tier"}))
    seen = {}

    async def fake_worker(envelope, *, brief, inputs, tools, tenant_id, reasoning=True):
        seen.update(envelope=envelope, tools=tools, inputs=inputs)
        return workers.WorkerResult(
            envelope=envelope,
            model="openrouter/r:free",
            text=json.dumps(
                [
                    {
                        "provider": "Groq",
                        "kind": "free_tier",
                        "title": "Groq free tier",
                        "source": page,
                    },
                    {
                        "provider": "OpenRouter",
                        "kind": "credits",
                        "title": "OR credits",
                        "source": page,
                    },
                    {
                        "provider": "Fake",
                        "kind": "promo",
                        "title": "x",
                        "source": "https://other.io",
                    },
                ]
            ),
        )

    monkeypatch.setattr(workers, "run_worker", fake_worker)
    report = await llm_offers.news_scan(async_session, TENANT)
    assert report == {"searched": 1, "read": 1, "offers": 2}  # the unfetched source is dropped
    assert seen["envelope"] == "research" and seen["tools"] == ()
    assert seen["inputs"].startswith(f"SOURCE: {page}")
    rows = {o.title: o for o in await _offers(source="news")}
    assert rows["Groq free tier"].status == "needs_signup"  # no key reaches Groq
    assert rows["OR credits"].status == "noted"


async def _coro(value):
    return value


@pytest.mark.asyncio
@skip_on_db_error
async def test_evaluation_files_an_adoption_and_approving_adopts(monkeypatch):
    from life_graph.models.assistant import LlmOffer
    from life_graph.models.db import Approval
    from life_graph.services import compute_router, llm_offers, model_eval
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    offer_id = await _add_offer("openrouter/good:free")
    monkeypatch.setattr(model_eval, "smoke_test", lambda m: _coro((True, "add(2, 3) called")))
    benched = []

    async def bench(model_id, timeout=900):
        benched.append(model_id)
        return {
            "passed": 6,
            "total": 6,
            "honest": 6,
            "avg_s": 40.0,
            "edits_ok": 9,
            "edits_failed": 0,
        }

    monkeypatch.setattr(model_eval, "run_benchmark", bench)
    monkeypatch.setattr(llm_offers, "_notify", lambda *a: _coro(None))

    result = await llm_offers.evaluate_next(async_session, TENANT)
    assert result == {
        "model": "openrouter/good:free",
        "status": "passed",
        "proposed": True,
        "smoke": "add(2, 3) called",
    }
    assert benched == ["openrouter/good:free"]
    async with async_session() as s:
        appr = (
            await s.execute(
                select(Approval).where(
                    Approval.kind == "model_adoption", Approval.source_ref == str(offer_id)
                )
            )
        ).scalar_one()
        assert "passed 6/6" in appr.detail and "trains on prompts" in appr.detail
        await ApprovalService(s).resolve(TENANT, str(appr.id), "approve")
        await s.commit()
        assert (await s.get(LlmOffer, offer_id)).status == "adopted"
    assert "openrouter/good:free" in compute_router.cloud_models()  # effective at once


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_failed_smoke_test_costs_nothing_more(monkeypatch):
    from life_graph.services import llm_offers, model_eval
    from life_graph.storage.database import async_session

    await _add_offer("openrouter/mute:free")
    monkeypatch.setattr(model_eval, "smoke_test", lambda m: _coro((False, "no tool call")))

    async def must_not_bench(*a, **k):
        raise AssertionError("benchmark ran after a failed smoke test")

    monkeypatch.setattr(model_eval, "run_benchmark", must_not_bench)
    result = await llm_offers.evaluate_next(async_session, TENANT)
    assert (result["status"], result["proposed"]) == ("failed", False)
    (offer,) = await _offers(model_id="openrouter/mute:free")
    assert offer.evaluation["smoke"] == {"ok": False, "detail": "no tool call"}


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_daily_cap_holds(monkeypatch):
    from life_graph.config import settings
    from life_graph.services import llm_offers
    from life_graph.storage.database import async_session

    monkeypatch.setattr(settings, "offers_max_evals_per_day", 0)
    await _add_offer("openrouter/later:free")
    assert await llm_offers.evaluate_next(async_session, TENANT) == {
        "skipped": "daily evaluation cap reached"
    }


@pytest.mark.asyncio
@skip_on_db_error
async def test_api_lists_and_queues(client):
    reachable_id = await _add_offer("openrouter/q:free", status="failed")
    unreachable_id = await _add_offer("groq/llama")
    listed = await client.get("/api/v1/llm-offers")
    assert listed.status_code == 200
    ids = {o["id"] for o in listed.json()["data"]}
    assert {str(reachable_id), str(unreachable_id)} <= ids

    queued = await client.post(f"/api/v1/llm-offers/{reachable_id}/evaluate")
    assert queued.status_code == 200 and queued.json()["data"]["status"] == "queued"
    refused = await client.post(f"/api/v1/llm-offers/{unreachable_id}/evaluate")
    assert refused.status_code == 409
    assert (await client.post(f"/api/v1/llm-offers/{uuid.uuid4()}/evaluate")).status_code == 404


@pytest.mark.asyncio
@skip_on_db_error
async def test_brief_line_reports_what_changed():
    from life_graph.services import llm_offers
    from life_graph.storage.database import async_session

    await _add_offer("openrouter/fresh:free", status="new")
    await _add_offer("openrouter/fine:free", status="passed", evaluation={"passed": 6, "total": 6})
    (line,) = await llm_offers.brief_lines(async_session, TENANT)
    assert line.startswith("Free LLM offers — ")
    assert "new free models: " in line and "fresh:free" in line
    assert "fine:free (6/6)" in line


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_same_provider_twice_is_one_offer_with_merged_terms(monkeypatch):
    from life_graph.services import llm_offers, workers
    from life_graph.storage.database import async_session

    pages = {"https://a.com/x": "a", "https://b.com/y": "b"}
    monkeypatch.setattr(llm_offers, "candidate_pages", lambda t: _coro(list(pages)))
    monkeypatch.setattr(llm_offers, "read_pages", lambda urls: _coro(dict(pages)))
    replies = iter(
        [
            [
                {
                    "provider": "Groq Cloud",
                    "kind": "free_tier",
                    "title": "Groq",
                    "source": "https://a.com/x",
                    "needs_card": False,
                },
                {
                    "provider": "Groq",
                    "kind": "free_tier",
                    "title": "Groq again",
                    "source": "https://b.com/y",
                    "trains_on_prompts": False,
                },
            ]
        ]
    )

    async def fake_worker(envelope, *, brief, inputs, tools, tenant_id, reasoning=True):
        return workers.WorkerResult(envelope=envelope, model="m", text=json.dumps(next(replies)))

    monkeypatch.setattr(workers, "run_worker", fake_worker)
    await llm_offers.news_scan(async_session, TENANT)
    groq = [o for o in await _offers(source="news") if o.dedup_key == "news|groq|free_tier"]
    assert len(groq) == 1
    assert groq[0].terms["needs_card"] is False and groq[0].terms["trains_on_prompts"] is False


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unreachable_model_is_retried_not_failed(monkeypatch):
    from life_graph.services import llm_offers, model_eval
    from life_graph.storage.database import async_session

    await _add_offer("openrouter/busy:free")
    monkeypatch.setattr(
        model_eval, "smoke_test", lambda m: _coro((None, "no answer: RateLimitError"))
    )
    for tries in (1, 2):
        result = await llm_offers.evaluate_next(async_session, TENANT)
        assert (result["status"], result["unreachable"]) == ("queued", tries)
    result = await llm_offers.evaluate_next(async_session, TENANT)
    assert (result["status"], result["unreachable"]) == ("failed", 3)
