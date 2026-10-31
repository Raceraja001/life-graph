"""Agent tools for the assistant's non-development work.

docs/specs/assistant-capabilities.md. Each tool reads the caller's tenant
from the request context and shapes its output for the audience
(connectors/locality.py): a local model sees everything, a cloud model sees
what the user would put on a postcard (kinds, dates, percentages), never
amounts, numbers or names of counterparties.
"""

from __future__ import annotations

import json
from typing import Any

from life_graph.connectors.locality import LOCAL, current_audience
from life_graph.tools.registry import tool

# Tools here that only read. The others (watch_page, make_study_cards) write
# rows, so scheduled advisory personas must not hold them
# (tests/integration/test_ambient_advisory_safety.py); the user-driven
# assistant persona does.
READ_ONLY_TOOLS = frozenset(
    {
        "documents_expiring",
        "spending_summary",
        "money_checkin",
        "app_health",
        "list_page_monitors",
        "study_cards_due",
        "study_progress",
        "invoices_status",
    }
)


def _tenant() -> str | None:
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context

    return get_current_tenant_id() if has_tenant_context() else None


def _today():
    from datetime import datetime

    from life_graph.connectors.tools import user_tz

    return datetime.now(user_tz()).date()


def _out(payload: dict[str, Any]) -> str:
    payload["audience"] = current_audience()
    return json.dumps(payload, default=str)


@tool(
    name="documents_expiring",
    description=(
        "The user's documents (passport, licence, insurance, warranties…) that expire"
        " within the given number of days, soonest first, with days left."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "minimum": 1, "maximum": 3650, "default": 90},
        },
    },
)
async def documents_expiring(days: int = 90) -> str:
    from life_graph.services import documents
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    today = _today()
    async with async_session() as session:
        rows = await documents.expiring(
            session, tenant, today, within_days=max(1, min(int(days), 3650))
        )
    local = current_audience() == LOCAL
    items = []
    for doc in rows:
        d = documents.to_dict(doc, today)
        if not local:
            d = {k: d[k] for k in ("kind", "title", "expires_on", "days_left")}
        items.append(d)
    return _out({"today": today.isoformat(), "documents": items})


@tool(
    name="spending_summary",
    description=(
        "The user's spending per category for a month (default this month) against"
        " their budgets. Cloud models see percentages only."
    ),
    parameters_schema={
        "type": "object",
        "properties": {"month": {"type": "string", "description": "YYYY-MM; default this month"}},
    },
)
async def spending_summary(month: str | None = None) -> str:
    from life_graph.services import money
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    try:
        async with async_session() as session:
            data = await money.summary(session, tenant, month, _today())
    except ValueError:
        return json.dumps({"error": "month must be YYYY-MM"})
    return _out(data if current_audience() == LOCAL else money.cloud_view(data))


@tool(
    name="money_checkin",
    description=(
        "The user's money check-in: spending this month so far against the same days"
        " last month, categories over or near budget, the biggest changes and top"
        " merchants. Cloud models see categories and percentages only."
    ),
    parameters_schema={"type": "object", "properties": {}},
)
async def money_checkin() -> str:
    from life_graph.services import money_checkin as mc
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    async with async_session() as session:
        data = await mc.checkin(session, tenant, _today())
    local = current_audience() == LOCAL
    return _out({"lines": mc.lines(data, amounts=local), **({"checkin": data} if local else {})})


@tool(
    name="app_health",
    description=(
        "Whether the user's apps are up: each watched app's last health check, TLS"
        " certificate days left and backup check, from the hourly uptime watcher."
    ),
    parameters_schema={"type": "object", "properties": {}},
)
async def app_health() -> str:
    from life_graph.services import app_health as svc
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    async with async_session() as session:
        apps = await svc.report(session, tenant)
    if not apps:
        return _out({"apps": [], "note": "No app has a health URL or backup check set."})
    return _out({"apps": apps, "lines": svc.lines(apps)})


@tool(
    name="watch_page",
    description=(
        "Set up a monitor on a web page: tell the user when it changes (mode change),"
        " when the price drops under a threshold (mode price_below), or when some text"
        " appears (mode contains, with pattern). Only when the user asks to watch something."
        " selector: optional simple CSS selector (e.g. span.price, [itemprop=price]) or"
        " regex:<pattern>."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "name": {"type": "string", "description": "Short name, e.g. 'Pixel 9 price'"},
            "mode": {"type": "string", "enum": ["change", "price_below", "contains"]},
            "threshold": {"type": "number", "description": "For price_below"},
            "pattern": {"type": "string", "description": "For contains"},
            "selector": {"type": "string"},
            "interval_minutes": {"type": "integer", "minimum": 30, "default": 180},
        },
        "required": ["url", "mode"],
    },
)
async def watch_page(
    url: str,
    mode: str = "change",
    name: str | None = None,
    threshold: float | None = None,
    pattern: str | None = None,
    selector: str | None = None,
    interval_minutes: int = 180,
) -> str:
    from life_graph.services import page_monitors
    from life_graph.services.safe_fetch import FetchBlockedError
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    try:
        async with async_session() as session:
            monitor = await page_monitors.create(
                session,
                tenant,
                url=url,
                name=name,
                mode=mode,
                threshold=threshold,
                pattern=pattern,
                selector=selector,
                interval_minutes=interval_minutes,
            )
            event = await page_monitors.check(monitor, page_monitors.now_utc())
            await session.commit()
            await session.refresh(monitor)
    except (ValueError, FetchBlockedError) as exc:
        return json.dumps({"error": str(exc)})
    return _out(
        {
            "created": page_monitors.to_dict(monitor),
            "first_check": event or "baseline recorded",
        }
    )


@tool(
    name="list_page_monitors",
    description="The pages the user is watching, with the last value seen.",
    parameters_schema={"type": "object", "properties": {}},
)
async def list_page_monitors() -> str:
    from sqlalchemy import select

    from life_graph.models.assistant import PageMonitor
    from life_graph.services import page_monitors
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    async with async_session() as session:
        rows = (
            (await session.execute(select(PageMonitor).where(PageMonitor.tenant_id == tenant)))
            .scalars()
            .all()
        )
    return _out({"monitors": [page_monitors.to_dict(m) for m in rows]})


@tool(
    name="make_study_cards",
    description=(
        "Write spaced-repetition flashcards for the user, from notes they give you"
        " (text) or from their saved memories about a topic. Only when they ask to study."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "text": {"type": "string", "description": "Notes to make cards from"},
            "deck": {"type": "string"},
        },
    },
)
async def make_study_cards(
    topic: str | None = None, text: str | None = None, deck: str | None = None
) -> str:
    from life_graph.services import study
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    if not (topic or text):
        return json.dumps({"error": "give a topic or some text"})
    async with async_session() as session:
        out = await study.generate(
            session, tenant, today=_today(), text=text, topic=topic, deck=deck
        )
        await session.commit()
    return _out(out)


@tool(
    name="study_cards_due",
    description="How many study cards are due today, and the first few questions.",
    parameters_schema={"type": "object", "properties": {}},
)
async def study_cards_due() -> str:
    from life_graph.services import study
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    today = _today()
    async with async_session() as session:
        cards = await study.due_cards(session, tenant, today, limit=5)
        total = await study.count_due(session, tenant, today)
    return _out({"due": total, "next": [{"deck": c.deck, "front": c.front} for c in cards]})


@tool(
    name="study_progress",
    description=(
        "The user's study progress: streak, cards due today, new/learning/mature counts,"
        " drafts waiting to be checked, and accuracy over 30 days (per deck for a local model)."
    ),
    parameters_schema={"type": "object", "properties": {}},
)
async def study_progress() -> str:
    from life_graph.services import study
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    async with async_session() as session:
        p = await study.progress(session, tenant, _today())
    if current_audience() != LOCAL:
        # Deck names are the owner's topics: a cloud model gets the counts.
        p = {k: v for k, v in p.items() if k != "decks"}
    return _out(p)


@tool(
    name="draft_study_cards",
    description=(
        "Draft flashcards from one thing the user saved — a memory (source_id), a document"
        " (source_id), their memories on a topic, or notes they paste (text) — for them to"
        " check and accept before the cards are scheduled (/drafts on Telegram). Written by"
        " the local model. Only when they ask to study or be quizzed on something."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "source": {"type": "string", "enum": ["memory", "document", "topic", "text"]},
            "source_id": {"type": "string", "description": "Memory or document id"},
            "topic": {"type": "string"},
            "text": {"type": "string", "description": "Notes to make cards from"},
            "deck": {"type": "string"},
        },
        "required": ["source"],
    },
)
async def draft_study_cards(
    source: str,
    source_id: str | None = None,
    topic: str | None = None,
    text: str | None = None,
    deck: str | None = None,
) -> str:
    import uuid

    from life_graph.services import study
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    if source not in study.SOURCE_KINDS:
        return json.dumps({"error": f"source must be one of {', '.join(study.SOURCE_KINDS)}"})
    sid = None
    if source in ("memory", "document"):
        try:
            sid = uuid.UUID(str(source_id))
        except ValueError:
            return json.dumps({"error": f"a {source} needs its id (source_id)"})
    async with async_session() as session:
        out = await study.draft(
            session,
            tenant,
            today=_today(),
            source=source,
            source_id=sid,
            topic=topic,
            text=text,
            deck=deck,
        )
        await session.commit()
    drafts = out.pop("drafts", [])
    if current_audience() == LOCAL:
        out["drafts"] = [
            {"front": d["front"], "back": d["back"], "deck": d["deck"]} for d in drafts
        ]
    out["next_step"] = "The user checks them with /drafts on Telegram or in the app."
    return _out(out)


@tool(
    name="invoices_status",
    description=(
        "The user's invoices to clients: drafts, sent and unpaid (with overdue ones"
        " flagged), and recently paid. Cloud models see counts only."
    ),
    parameters_schema={"type": "object", "properties": {}},
)
async def invoices_status() -> str:
    from life_graph.services import invoices
    from life_graph.storage.database import async_session

    tenant = _tenant()
    if not tenant:
        return json.dumps({"error": "no tenant context"})
    today = _today()
    async with async_session() as session:
        rows = await invoices.list_all(session, tenant)
    unpaid = [i for i in rows if i.status == "sent"]
    overdue = [i for i in unpaid if i.due_on < today]
    if current_audience() != LOCAL:
        return _out(
            {
                "drafts": sum(i.status == "draft" for i in rows),
                "unpaid": len(unpaid),
                "overdue": len(overdue),
                "note": "Clients and amounts are kept on the user's device.",
            }
        )
    view = lambda i: {  # noqa: E731
        k: v
        for k, v in invoices.to_dict(i).items()
        if k in ("number", "client_name", "total", "currency", "status", "due_on")
    }
    return _out(
        {
            "today": today.isoformat(),
            "drafts": [view(i) for i in rows if i.status == "draft"],
            "unpaid": [{**view(i), "overdue": i.due_on < today} for i in unpaid],
            "recently_paid": [view(i) for i in rows if i.status == "paid"][:5],
        }
    )
