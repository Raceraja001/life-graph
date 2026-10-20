"""Job 1 — free LLM offers: found, read, evaluated, offered for adoption.

docs/specs/free-llm-offers.md. Code collects; a worker only judges:

* **Catalog diff** (plain code, daily): each provider's free models today vs
  yesterday's snapshot. A new one becomes an offer (``new``, evaluable); a
  missing one becomes ``gone`` and, if it was adopted, leaves the cloud list.
* **News scan** (every 6 h): SearXNG queries -> pages we have not read ->
  fetched by the safe fetcher -> the ``offer_reader`` worker (research
  envelope, no tools) -> validated offers. News offers are information
  (``noted``, or ``needs_signup`` when no key reaches the provider).
* **Evaluation** (hourly, at most ``offers_max_evals_per_day``): a smoke test,
  then the coding benchmark, on the cloud engine only.
* **Adoption** is an approval (``model_adoption``); approving adds the model to
  the free cloud list at once (compute_router.set_adopted).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import func, select

from life_graph.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

PROVIDERS = ("openrouter", "nvidia_nim")
_SNAPSHOTS_KEPT = 30
_PAGE_CHARS = 12_000
_PAGES_PER_WORKER = 2
_SEEN_KEY = "lg:offers:seen:{tenant_id}"
_SEEN_TTL = 30 * 86_400
EVALUABLE = ("new", "queued")


# ── Catalogs ─────────────────────────────────────────────────


def diff(previous: list[str], current: list[str]) -> tuple[list[str], list[str]]:
    """(new, gone) between two catalogs' free-model ids, both sorted."""
    before, after = set(previous), set(current)
    return sorted(after - before), sorted(before - after)


async def fetch_free_models(
    provider: str, client: httpx.AsyncClient | None = None
) -> list[str] | None:
    """A provider's free models as LiteLLM ids; None when it cannot be read
    (NVIDIA without a key is skipped, not failed)."""
    from life_graph.services.model_catalog import _is_free, _is_text_output

    own = client is None
    http = client or httpx.AsyncClient(timeout=20.0)
    try:
        if provider == "openrouter":
            resp = await http.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            return sorted(
                f"openrouter/{m['id']}"
                for m in resp.json().get("data", [])
                if _is_free(m.get("pricing") or {}) and _is_text_output(m)
            )
        if provider == "nvidia_nim":
            if not settings.nvidia_nim_api_key:
                return None
            resp = await http.get(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {settings.nvidia_nim_api_key}"},
            )
            resp.raise_for_status()
            return sorted(f"nvidia_nim/{m['id']}" for m in resp.json().get("data", []))
        return None
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("catalog %s unreadable: %s", provider, exc)
        return None
    finally:
        if own:
            await http.aclose()


def _model_url(model_id: str) -> str | None:
    if model_id.startswith("openrouter/"):
        return f"https://openrouter.ai/{model_id.removeprefix('openrouter/')}"
    if model_id.startswith("nvidia_nim/"):
        return f"https://build.nvidia.com/{model_id.removeprefix('nvidia_nim/')}"
    return None


async def catalog_diff(
    session_factory: async_sessionmaker[AsyncSession], tenants: list[str]
) -> dict[str, Any]:
    """Diff every readable catalog against its last snapshot; record offers."""
    from life_graph.models.assistant import LlmCatalogSnapshot, LlmOffer

    report: dict[str, Any] = {}
    for provider in PROVIDERS:
        current = await fetch_free_models(provider)
        if current is None:
            report[provider] = "skipped"
            continue
        async with session_factory() as session:
            previous = (
                await session.execute(
                    select(LlmCatalogSnapshot)
                    .where(LlmCatalogSnapshot.provider == provider)
                    .order_by(LlmCatalogSnapshot.taken_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            session.add(LlmCatalogSnapshot(provider=provider, model_ids=current))
            if previous is None:
                # The first snapshot is the baseline: what exists today is not "new".
                await session.commit()
                report[provider] = {"baseline": len(current)}
                continue
            new, gone = diff(list(previous.model_ids or []), current)
            for tenant_id in tenants:
                for model_id in new:
                    await _upsert(
                        session,
                        tenant_id,
                        dedup_key=f"{provider}|{model_id}",
                        provider=provider,
                        model_id=model_id,
                        kind="free_model",
                        title=model_id.split("/", 1)[1],
                        source="catalog_diff",
                        source_url=_model_url(model_id),
                        status="new",
                    )
                if gone:
                    rows = (
                        (
                            await session.execute(
                                select(LlmOffer).where(
                                    LlmOffer.tenant_id == tenant_id, LlmOffer.model_id.in_(gone)
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    for offer in rows:
                        if offer.status == "adopted":
                            await _notify(
                                tenant_id,
                                f"Adopted free model {offer.model_id} is gone",
                                f"{provider} no longer lists it as free; it was dropped "
                                "from the cloud model list.",
                            )
                        offer.status = "gone"
            await _prune_snapshots(session, provider)
            await session.commit()
            report[provider] = {"new": new, "gone": gone}
    async with session_factory() as session:
        await refresh_adopted(session)
    return report


async def _prune_snapshots(session: AsyncSession, provider: str) -> None:
    from life_graph.models.assistant import LlmCatalogSnapshot

    old = (
        (
            await session.execute(
                select(LlmCatalogSnapshot.id)
                .where(LlmCatalogSnapshot.provider == provider)
                .order_by(LlmCatalogSnapshot.taken_at.desc())
                .offset(_SNAPSHOTS_KEPT)
            )
        )
        .scalars()
        .all()
    )
    for snapshot_id in old:
        row = await session.get(LlmCatalogSnapshot, snapshot_id)
        if row is not None:
            await session.delete(row)


async def _upsert(session: AsyncSession, tenant_id: str, *, dedup_key: str, **fields) -> Any:
    """Create the offer, or refresh last_seen_at on one already known (its
    status is not reset: a rejected offer stays rejected)."""
    from life_graph.models.assistant import LlmOffer

    offer = (
        await session.execute(
            select(LlmOffer).where(LlmOffer.tenant_id == tenant_id, LlmOffer.dedup_key == dedup_key)
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if offer is not None:
        offer.last_seen_at = now
        if offer.status == "gone":
            offer.status = fields.get("status", "new")
        # A later page may state what an earlier one left out: fill only the
        # terms still unknown, never overwrite a stated one.
        merged = dict(offer.terms or {})
        for key, value in (fields.get("terms") or {}).items():
            if merged.get(key) in (None, "unknown") and value not in (None, "unknown"):
                merged[key] = value
        if merged != (offer.terms or {}):
            offer.terms = merged
        return offer
    offer = LlmOffer(id=uuid.uuid4(), tenant_id=tenant_id, dedup_key=dedup_key, **fields)
    offer.first_seen_at = offer.last_seen_at = now
    session.add(offer)
    return offer


# ── News ─────────────────────────────────────────────────────


async def _seen(tenant_id: str) -> tuple[Any, set[str]]:
    from life_graph.services import web_pages

    return await web_pages.seen(_SEEN_KEY.format(tenant_id=tenant_id))


async def _mark_seen(redis: Any, tenant_id: str, urls: list[str]) -> None:
    from life_graph.services import web_pages

    await web_pages.mark_seen(redis, _SEEN_KEY.format(tenant_id=tenant_id), urls, _SEEN_TTL)


async def candidate_pages(tenant_id: str) -> list[str]:
    """New result URLs for the news queries, capped at offers_max_pages."""
    from life_graph.services import web_pages

    _, seen = await _seen(tenant_id)
    hits = await web_pages.candidates(
        settings.offers_news_queries_list, limit=settings.offers_max_pages, skip=seen
    )
    return [h.url for h in hits]


async def read_pages(urls: list[str]) -> dict[str, str]:
    """The readable text of each page that could be fetched (url -> text)."""
    from life_graph.services import web_pages

    return await web_pages.read(urls, _PAGE_CHARS)


# Names the same provider goes by on different pages (normalised form -> key).
_PROVIDER_ALIASES = {
    "googleaistudio": "google",
    "googlegemini": "google",
    "gemini": "google",
    "geminiapi": "google",
    "googleai": "google",
    "groqcloud": "groq",
    "mistralai": "mistral",
    "lamiaplatform": "mistral",
    "togetherai": "together",
    "fireworksai": "fireworks",
    "awsbedrock": "aws",
    "amazonbedrock": "aws",
    "nvidianim": "nvidia",
    "nvidiabuild": "nvidia",
    "cloudflareworkersai": "cloudflare",
    "huggingfaceinference": "huggingface",
}


def provider_key(provider: str) -> str:
    """One key per provider however a page names it: 'Groq Cloud' and 'Groq'
    are both 'groq', 'Google AI Studio' and 'Gemini' both 'google'."""
    import re

    norm = re.sub(r"[^a-z0-9]", "", provider.lower())
    if norm in _PROVIDER_ALIASES:
        return _PROVIDER_ALIASES[norm]
    for suffix in ("labs", "ai", "inc", "cloud", "api"):
        if norm.endswith(suffix) and len(norm) > len(suffix) + 2:
            norm = norm[: -len(suffix)]
    return _PROVIDER_ALIASES.get(norm, norm)


def _known_provider(provider: str) -> str | None:
    p = provider.lower().replace(" ", "")
    if "openrouter" in p:
        return "openrouter"
    if "nvidia" in p:
        return "nvidia_nim"
    return None


async def news_scan(session_factory: async_sessionmaker[AsyncSession], tenant_id: str) -> dict:
    """Search, read new pages with the offer_reader worker, record offers."""
    from life_graph.services import web_pages
    from life_graph.services.compute_router import _has_key
    from life_graph.services.worker_templates import OFFER_READER, validate_offer
    from life_graph.services.workers import WorkerError, json_array, run_worker

    urls = await candidate_pages(tenant_id)
    pages = await read_pages(urls)
    redis, _ = await _seen(tenant_id)
    offers: list[dict] = []
    batch = list(pages.items())
    for i in range(0, len(batch), _PAGES_PER_WORKER):
        chunk = batch[i : i + _PAGES_PER_WORKER]
        inputs = web_pages.as_inputs(chunk)
        try:
            result = await run_worker(
                OFFER_READER.envelope,
                brief=OFFER_READER.brief,
                inputs=inputs,
                tools=OFFER_READER.tools,
                tenant_id=tenant_id,
                reasoning=OFFER_READER.reasoning,
            )
            if result.error or not result.text.strip():
                logger.info(
                    "offer reader on %s: %s %s",
                    [u for u, _ in chunk],
                    result.stopped,
                    result.error or "empty reply",
                )
        except WorkerError as exc:
            logger.info("offer reading stopped: %s", exc)
            break
        sources = {url for url, _ in chunk}
        offers += [o for o in (validate_offer(x, sources) for x in json_array(result.text)) if o]
    async with session_factory() as session:
        for offer in offers:
            known = _known_provider(offer["provider"])
            reachable = known == "openrouter" or (
                known == "nvidia_nim" and _has_key("nvidia_nim/x")
            )
            # One offer per provider and kind, wherever and however often it
            # is mentioned (the first live scan found Groq three times).
            key = f"news|{provider_key(offer['provider'])}|{offer['kind']}"
            await _upsert(
                session,
                tenant_id,
                dedup_key=key[:500],
                provider=known or offer["provider"][:64],
                model_id=None,
                kind=offer["kind"],
                title=offer["title"],
                summary=offer["summary"],
                source="news",
                source_url=offer["source"],
                terms=offer["terms"],
                status="noted" if reachable else "needs_signup",
            )
        await session.commit()
    await _mark_seen(redis, tenant_id, list(pages) + [u for u in urls if u not in pages])
    return {"searched": len(urls), "read": len(pages), "offers": len(offers)}


# ── Evaluation and adoption ──────────────────────────────────


def reachable(model_id: str | None) -> bool:
    """A free cloud model we hold a key for."""
    from life_graph.services.compute_router import _has_key, is_free_cloud_model

    return bool(model_id) and is_free_cloud_model(model_id) and _has_key(model_id)


async def evaluations_today(session: AsyncSession, tenant_id: str) -> int:
    from life_graph.models.assistant import LlmOffer

    today = datetime.now(UTC).date().isoformat()
    return (
        await session.execute(
            select(func.count(LlmOffer.id)).where(
                LlmOffer.tenant_id == tenant_id,
                LlmOffer.evaluation["benchmark_on"].astext == today,
            )
        )
    ).scalar() or 0


async def evaluate_next(session_factory: async_sessionmaker[AsyncSession], tenant_id: str) -> dict:
    """Evaluate the oldest waiting reachable offer, within the daily cap."""
    from life_graph.models.assistant import LlmOffer
    from life_graph.services import model_eval
    from life_graph.services.compute_router import cloud_models
    from life_graph.services.resilient_llm import provider_of, provider_usage

    async with session_factory() as session:
        if await evaluations_today(session, tenant_id) >= settings.offers_max_evals_per_day:
            return {"skipped": "daily evaluation cap reached"}
        waiting = (
            (
                await session.execute(
                    select(LlmOffer)
                    .where(LlmOffer.tenant_id == tenant_id, LlmOffer.status.in_(EVALUABLE))
                    .order_by(LlmOffer.first_seen_at)
                )
            )
            .scalars()
            .all()
        )
        offer = next((o for o in waiting if reachable(o.model_id)), None)
        if offer is None:
            return {"skipped": "nothing to evaluate"}
        used, limit = await provider_usage(provider_of(offer.model_id))
        if limit and used >= 0.8 * limit:
            return {"skipped": f"{provider_of(offer.model_id)} is near its daily limit"}
        offer.status = "evaluating"
        offer_id, model_id = offer.id, offer.model_id
        await session.commit()

    ok, detail = await model_eval.smoke_test(model_id)
    if ok is None:
        # Unreachable right now (rate-limited, down): not the model's failure.
        # Back in the queue for a later run, without spending the daily cap;
        # failed only after UNREACHABLE_TRIES attempts.
        async with session_factory() as session:
            offer = await session.get(LlmOffer, offer_id)
            tries = int((offer.evaluation or {}).get("unreachable") or 0) + 1
            offer.evaluation = {**(offer.evaluation or {}), "unreachable": tries, "last": detail}
            offer.status = "failed" if tries >= model_eval.UNREACHABLE_TRIES else "queued"
            await session.commit()
            return {
                "model": model_id,
                "status": offer.status,
                "unreachable": tries,
                "smoke": detail,
            }

    evaluation: dict[str, Any] = {}
    evaluation["smoke"] = {"ok": ok, "detail": detail}
    status = "failed"
    if ok:
        evaluation.update(await model_eval.run_benchmark(model_id))
        evaluation["benchmark_on"] = datetime.now(UTC).date().isoformat()
        status = "passed" if model_eval.meets_bar(evaluation) else "failed"

    async with session_factory() as session:
        offer = await session.get(LlmOffer, offer_id)
        offer.evaluation = evaluation
        offer.status = status
        proposed = False
        if status == "passed":
            adopted = (
                (
                    await session.execute(
                        select(LlmOffer.evaluation).where(LlmOffer.status == "adopted")
                    )
                )
                .scalars()
                .all()
            )
            if model_eval.worth_proposing(evaluation, len(cloud_models()), list(adopted)):
                await file_adoption(session, offer)
                proposed = True
        await session.commit()
    return {"model": model_id, "status": status, "proposed": proposed, "smoke": detail}


async def file_adoption(session: AsyncSession, offer: Any) -> None:
    """The model_adoption approval for a passed offer (one per offer)."""
    from life_graph.models.db import Approval

    existing = (
        await session.execute(
            select(Approval.id).where(
                Approval.kind == "model_adoption",
                Approval.source_ref == str(offer.id),
            )
        )
    ).first()
    if existing:
        return
    e, t = offer.evaluation or {}, offer.terms or {}
    detail = (
        f"{offer.model_id} passed {e.get('passed')}/{e.get('total')} coding tasks "
        f"(honest {e.get('honest')}/{e.get('total')}, {e.get('avg_s')} s average, "
        f"{e.get('edits_ok')} edits / {e.get('edits_failed')} refused). "
        f"Smoke test: {(e.get('smoke') or {}).get('detail')}. "
        f"Terms: trains on prompts: {t.get('trains_on_prompts', 'unknown')}; "
        f"commercial use: {t.get('commercial_use', 'unknown')}. "
        "Approve to add it to the free cloud model list (used for code and research, "
        "never personal data)."
    )
    session.add(
        Approval(
            tenant_id=offer.tenant_id,
            kind="model_adoption",
            source="llm_offers",
            source_ref=str(offer.id),
            title=f"Adopt free model {offer.model_id}",
            detail=detail,
            payload={"offer_id": str(offer.id), "model_id": offer.model_id, "evaluation": e},
        )
    )
    await _notify(offer.tenant_id, f"New free model worth adopting: {offer.model_id}", detail)


async def apply_adoption(session: AsyncSession, approval: Any, approve: bool) -> None:
    """Approve: the offer is adopted and joins the cloud list now. Reject: it
    is rejected and never proposed again."""
    from life_graph.models.assistant import LlmOffer

    offer_id = (approval.payload or {}).get("offer_id")
    offer = await session.get(LlmOffer, uuid.UUID(offer_id)) if offer_id else None
    if offer is None or offer.tenant_id != approval.tenant_id:
        return
    offer.status = "adopted" if approve else "rejected"
    await session.flush()
    await refresh_adopted(session)


async def refresh_adopted(session: AsyncSession) -> list[str]:
    """Load the adopted models (best first) into the compute router."""
    from life_graph.models.assistant import LlmOffer
    from life_graph.services import model_eval
    from life_graph.services.compute_router import set_adopted

    rows = (
        (await session.execute(select(LlmOffer).where(LlmOffer.status == "adopted")))
        .scalars()
        .all()
    )
    ranked = sorted(rows, key=lambda o: model_eval.score(o.evaluation or {}), reverse=True)
    models = [o.model_id for o in ranked if o.model_id]
    set_adopted(models)
    return models


# ── Reporting ────────────────────────────────────────────────


async def _notify(tenant_id: str, title: str, body: str) -> None:
    try:
        from life_graph.kernel.notification_engine import NotificationEngine
        from life_graph.storage.database import async_session

        await NotificationEngine(session_factory=async_session).create(
            tenant_id, title=title, body=body, priority="important", source_type="llm_offers"
        )
    except Exception:  # noqa: BLE001 - a notification never breaks the job
        logger.warning("llm offers notification failed", exc_info=True)


async def brief_lines(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str
) -> list[str]:
    """What changed in the last day, for the daily brief (AC-7.1)."""
    from life_graph.models.assistant import LlmOffer

    since = datetime.now(UTC) - timedelta(days=1)
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(LlmOffer).where(
                        LlmOffer.tenant_id == tenant_id, LlmOffer.updated_at >= since
                    )
                )
            )
            .scalars()
            .all()
        )
    if not rows:
        return []
    by: dict[str, list[str]] = {}
    for o in rows:
        label = o.model_id.split("/", 1)[-1] if o.model_id else f"{o.provider}: {o.title}"
        if o.status in ("passed", "failed") and o.evaluation.get("total"):
            label += f" ({o.evaluation.get('passed')}/{o.evaluation.get('total')})"
        by.setdefault(o.status, []).append(label)
    names = {
        "new": "new free models",
        "noted": "offers in the news",
        "needs_signup": "need your signup",
        "passed": "passed evaluation",
        "failed": "failed evaluation",
        "adopted": "adopted",
        "gone": "no longer free",
    }
    parts = [f"{names[s]}: {', '.join(v[:5])}" for s, v in by.items() if s in names]
    return [f"Free LLM offers — {'; '.join(parts)}"] if parts else []


def to_dict(offer: Any) -> dict[str, Any]:
    return {
        "id": str(offer.id),
        "provider": offer.provider,
        "model_id": offer.model_id,
        "kind": offer.kind,
        "title": offer.title,
        "summary": offer.summary,
        "source": offer.source,
        "source_url": offer.source_url,
        "terms": offer.terms or {},
        "status": offer.status,
        "evaluation": {k: v for k, v in (offer.evaluation or {}).items() if k != "rows"},
        "first_seen_at": offer.first_seen_at.isoformat() if offer.first_seen_at else None,
        "last_seen_at": offer.last_seen_at.isoformat() if offer.last_seen_at else None,
    }
