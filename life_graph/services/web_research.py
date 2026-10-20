"""Jobs 6 and 10 — research on demand and the tech watch.

docs/specs/research-and-tech-watch.md. As in Job 1, code collects and a worker
only reads: plain code searches and fetches (services/web_pages.py), a worker
in the research envelope (free cloud model, no tools, reasoning off) reads the
pages it is handed, and its reply is validated against those pages.

* **Research** (on demand): the owner's question, scrubbed, is searched; up to
  ``research_max_pages`` pages are read; the ``researcher`` answers in claims,
  each citing the pages that state it. A claim citing nothing that was read
  is dropped, so every sentence of the answer has a fetched source.
* **Tech watch** (daily): per topic, its queries -> pages not read yet -> the
  ``topic_reader`` -> findings stored once per source per topic. On Mondays
  the brief lists the ones not sent yet.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

NOT_FOUND = "I could not find this in the pages I read."
_PAGES_PER_WORKER = 2
_SEEN_KEY = "lg:techwatch:seen:{tenant_id}:{topic}"


# ── Job 6: research on demand ────────────────────────────────


async def research(question: str, tenant_id: str) -> dict[str, Any]:
    """Answer *question* from pages fetched now, every claim cited (AC-6.1/6.2).

    Raises:
        WorkerError: no free model is available for the research envelope.
    """
    from life_graph.services import web_pages
    from life_graph.services.scrub import scrub
    from life_graph.services.worker_templates import RESEARCHER, validate_claims
    from life_graph.services.workers import json_array, run_worker

    # The query goes to a search engine and the pages to a cloud model:
    # personal details are hidden first (AC-6.3). The worker scrubs its
    # inputs too; the search query never passes through it.
    asked = scrub(question.strip())
    hits = await web_pages.candidates([asked], limit=settings.research_max_pages)
    pages = await web_pages.read([h.url for h in hits], settings.research_page_chars)
    titles = {h.url: h.title for h in hits}
    read = [{"url": u, "title": titles.get(u) or u} for u in pages]
    out: dict[str, Any] = {
        "question": asked,
        "answer": NOT_FOUND,
        "sources": [],
        "claims": [],
        "pages_read": read,
        "model": None,
    }
    if not pages:
        return out
    result = await run_worker(
        RESEARCHER.envelope,
        brief=RESEARCHER.brief,
        inputs=f"QUESTION: {asked}\n\n{web_pages.as_inputs(list(pages.items()))}",
        tools=RESEARCHER.tools,
        tenant_id=tenant_id,
        reasoning=RESEARCHER.reasoning,
    )
    out["model"] = result.model
    if result.error:
        out["error"] = result.error
    claims = validate_claims(json_array(result.text), set(pages))
    if not claims:
        return out
    order = list(dict.fromkeys(u for c in claims for u in c["sources"]))
    number = {u: i + 1 for i, u in enumerate(order)}
    out["claims"] = claims
    out["sources"] = [{"url": u, "title": titles.get(u) or u} for u in order]
    out["answer"] = "\n".join(
        f"- {c['text']} " + "".join(f"[{number[u]}]" for u in c["sources"]) for c in claims
    )
    return out


# ── Job 10: tech watch ───────────────────────────────────────


def _topic_slug(topic: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60]


def finding_key(source: str, title: str) -> str:
    """One row per item per page: a blog index holds many releases (the first
    live scan found 16 on ollama.com/blog), so the page alone is not the key."""
    from life_graph.services.sources import normalise

    return f"{normalise(source)[:400]}#{_topic_slug(title)}"[:500]


def dated_queries(queries: list[str], today: date | None = None) -> list[str]:
    """``{month}`` in a query becomes this month ("October 2026"): undated
    queries return evergreen "best of" lists whose items are months old."""
    today = today or datetime.now(UTC).date()
    return [q.replace("{month}", today.strftime("%B %Y")) for q in queries]


async def scan_topic(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    topic: str,
    queries: list[str],
    *,
    kind: str | None = None,
    max_memory_gb: float | None = None,
) -> dict[str, int]:
    """Read the topic's new pages and store what is new on it (AC-10.2/10.3)."""
    from sqlalchemy.dialects.postgresql import insert

    from life_graph.models.assistant import TopicFinding
    from life_graph.services import web_pages
    from life_graph.services.worker_templates import topic_reader, validate_finding
    from life_graph.services.workers import WorkerError, json_array, run_worker

    key = _SEEN_KEY.format(tenant_id=tenant_id, topic=_topic_slug(topic))
    redis, seen = await web_pages.seen(key)
    hits = await web_pages.candidates(
        dated_queries(queries), limit=settings.tech_watch_max_pages, skip=seen
    )
    urls = [h.url for h in hits]
    pages = await web_pages.read(urls)
    reader = topic_reader(topic)
    findings: list[dict] = []
    batch = list(pages.items())
    for i in range(0, len(batch), _PAGES_PER_WORKER):
        chunk = batch[i : i + _PAGES_PER_WORKER]
        try:
            result = await run_worker(
                reader.envelope,
                brief=reader.brief,
                inputs=web_pages.as_inputs(chunk),
                tools=reader.tools,
                tenant_id=tenant_id,
                reasoning=reader.reasoning,
            )
        except WorkerError as exc:
            logger.info("tech watch reading stopped: %s", exc)
            break
        if result.error or not result.text.strip():
            logger.info("topic reader on %s: %s", [u for u, _ in chunk], result.error or "empty")
        sources = {u for u, _ in chunk}
        findings += [
            f
            for f in (
                validate_finding(x, sources, kind=kind, max_memory_gb=max_memory_gb)
                for x in json_array(result.text)
            )
            if f
        ]

    # The same release under the same title on two pages of one run is one
    # finding (the eval: "Wren 9B released" from the blog and from a guide).
    # Different wordings still make two; see the spec's known gaps.
    seen_titles: set[str] = set()
    unique = []
    for f in findings:
        slug = _topic_slug(f["title"])
        if slug not in seen_titles:
            seen_titles.add(slug)
            unique.append(f)
    findings = unique

    stored = 0
    async with session_factory() as session:
        for f in findings:
            row = (
                insert(TopicFinding)
                .values(
                    tenant_id=tenant_id,
                    topic=topic,
                    dedup_key=finding_key(f["source"], f["title"]),
                    title=f["title"],
                    summary=f["summary"],
                    source_url=f["source"],
                    published_on=date.fromisoformat(f["published_on"]),
                )
                .on_conflict_do_nothing(index_elements=["tenant_id", "topic", "dedup_key"])
                .returning(TopicFinding.id)
            )
            if (await session.execute(row)).first():
                stored += 1
        await session.commit()
    await web_pages.mark_seen(redis, key, urls)
    return {"searched": len(urls), "read": len(pages), "found": len(findings), "stored": stored}


async def tech_watch(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str
) -> dict[str, Any]:
    """Every configured topic, one after the other; one failing skips that one."""
    out: dict[str, Any] = {}
    for topic, spec in settings.tech_watch_topic_specs.items():
        try:
            out[topic] = await scan_topic(
                session_factory,
                tenant_id,
                topic,
                spec["queries"],
                kind=spec["kind"],
                max_memory_gb=spec["max_memory_gb"],
            )
        except Exception as exc:  # noqa: BLE001 - the next topic still runs
            logger.warning("tech watch on %r failed", topic, exc_info=True)
            out[topic] = {"error": str(exc)[:300]}
    return out


async def digest_lines(session: AsyncSession, tenant_id: str, *, mark: bool = True) -> list[str]:
    """The Monday "Tech watch" section: findings not sent yet, up to
    ``tech_watch_digest_per_topic`` per topic, newest first (AC-10.4). Marks
    them sent unless *mark* is False. Nothing new -> []."""
    from life_graph.models.assistant import TopicFinding

    rows = (
        (
            await session.execute(
                select(TopicFinding)
                .where(TopicFinding.tenant_id == tenant_id, TopicFinding.sent_at.is_(None))
                .order_by(TopicFinding.topic, TopicFinding.found_at.desc())
            )
        )
        .scalars()
        .all()
    )
    per = settings.tech_watch_digest_per_topic
    by: dict[str, list[Any]] = {}
    for row in rows:
        if len(by.setdefault(row.topic, [])) < per:
            by[row.topic].append(row)
    lines: list[str] = []
    now = datetime.now(UTC)
    for topic, picked in by.items():
        lines.append(f"{topic}:")
        for row in picked:
            lines.append(f"  - {row.title} — {row.source_url}")
            if mark:
                row.sent_at = now
    if mark and lines:
        await session.commit()
    return lines


def to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "topic": row.topic,
        "title": row.title,
        "summary": row.summary,
        "source_url": row.source_url,
        "published_on": row.published_on.isoformat() if row.published_on else None,
        "found_at": row.found_at.isoformat() if row.found_at else None,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
    }
