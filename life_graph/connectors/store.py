"""Reads and writes of the connector item index.

Everything returned from here is a plain dict carrying ``account_name`` and
``account_exposure`` so ``exposure.view_items`` can decide what to show without
another query. Nothing here decides visibility.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased

from life_graph.config import settings
from life_graph.connectors.base import (
    DIR_INBOUND,
    DIR_INVITE,
    DIR_OWN,
    DIR_SENT,
    KIND_EMAIL,
    KIND_EVENT,
    Item,
)
from life_graph.connectors.models import ConnectorAccount, ConnectorItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Trust tier per direction (core/trust.py tiers). Anyone can send mail, so an
# inbound message is the most dangerous kind of content there is.
_TRUST = {
    DIR_SENT: "self",
    DIR_OWN: "verified",
    DIR_INVITE: "external",
    DIR_INBOUND: "hostile_possible",
}

_UPDATABLE = (
    "thread_key",
    "direction",
    "title",
    "sender_name",
    "sender_addr",
    "to_me",
    "starts_at",
    "ends_at",
    "location",
    "attendees",
    "local_detail",
    "trust_tier",
    "occurred_at",
    "fetched_at",
)


def _row_for(account: ConnectorAccount, item: Item, now: datetime) -> dict[str, Any]:
    flags = dict(item.flags)
    if item.all_day:
        flags["all_day"] = True
    return {
        "id": uuid.uuid4(),
        "tenant_id": account.tenant_id,
        "account_id": account.id,
        "kind": item.kind,
        "external_id": item.external_id[:512],
        "thread_key": (item.thread_key or None) and item.thread_key[:512],
        "direction": item.direction,
        "title": item.title,
        "sender_name": item.sender_name,
        "sender_addr": (item.sender_addr or "").lower() or None,
        "to_me": item.to_me,
        "starts_at": item.starts_at,
        "ends_at": item.ends_at,
        "location": item.location,
        "attendees": item.attendees,
        "local_detail": item.detail,
        "flags": flags,
        "trust_tier": _TRUST.get(item.direction, "external"),
        # Mail waits for the local summariser; events have nothing to summarise.
        "summary_state": "pending" if item.kind == KIND_EMAIL else "none",
        "occurred_at": item.occurred_at,
        "fetched_at": now,
    }


async def upsert_items(
    session: AsyncSession, account: ConnectorAccount, items: list[Item]
) -> list[uuid.UUID]:
    """Insert or refresh items; returns the ids of rows that are new.

    An existing row keeps its summary, category and embedding: those are
    derived by the local model once and do not change when the source re-sends
    the same message. Flags are merged, so ``asks_me`` set by the summariser
    survives a later sync that only knows ``automated``.
    """
    if not items:
        return []
    now = datetime.now(UTC)
    rows = [_row_for(account, it, now) for it in items]
    new_ids: list[uuid.UUID] = []
    # Chunked: asyncpg caps bind parameters per statement.
    for start in range(0, len(rows), 200):
        chunk = rows[start : start + 200]
        stmt = insert(ConnectorItem).values(chunk)
        excluded = stmt.excluded
        update = {col: getattr(excluded, col) for col in _UPDATABLE}
        update["flags"] = ConnectorItem.flags.op("||")(excluded.flags)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_connector_item_external", set_=update
        ).returning(ConnectorItem.id, ConnectorItem.fetched_at, ConnectorItem.summary_state)
        result = await session.execute(stmt)
        chunk_ids = {r["id"] for r in chunk}
        new_ids.extend(row.id for row in result if row.id in chunk_ids)
    return new_ids


async def delete_external(
    session: AsyncSession, account: ConnectorAccount, external_ids: list[str]
) -> int:
    if not external_ids:
        return 0
    result = await session.execute(
        delete(ConnectorItem).where(
            ConnectorItem.tenant_id == account.tenant_id,
            ConnectorItem.account_id == account.id,
            ConnectorItem.external_id.in_(external_ids),
        )
    )
    return result.rowcount or 0


async def delete_missing(
    session: AsyncSession, account: ConnectorAccount, kind: str, keep_external_ids: set[str]
) -> int:
    """Delete stored items of ``kind`` the source no longer lists (full-snapshot sources)."""
    stmt = delete(ConnectorItem).where(
        ConnectorItem.tenant_id == account.tenant_id,
        ConnectorItem.account_id == account.id,
        ConnectorItem.kind == kind,
    )
    if keep_external_ids:
        stmt = stmt.where(ConnectorItem.external_id.not_in(list(keep_external_ids)))
    result = await session.execute(stmt)
    return result.rowcount or 0


def _as_dict(item: ConnectorItem, account: ConnectorAccount) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "account_id": str(item.account_id),
        "account_name": account.display_name,
        "account_exposure": account.exposure,
        "connector": account.connector,
        "kind": item.kind,
        "external_id": item.external_id,
        "thread_key": item.thread_key,
        "direction": item.direction,
        "title": item.title,
        "sender_name": item.sender_name,
        "sender_addr": item.sender_addr,
        "to_me": item.to_me,
        "starts_at": item.starts_at,
        "ends_at": item.ends_at,
        "location": item.location,
        "attendees": item.attendees or [],
        "summary": item.summary,
        "category": item.category,
        "summary_state": item.summary_state,
        "flags": item.flags or {},
        "local_detail": item.local_detail,
        "trust_tier": item.trust_tier,
        "occurred_at": item.occurred_at,
    }


def _base(tenant_id: str):
    return (
        select(ConnectorItem, ConnectorAccount)
        .join(ConnectorAccount, ConnectorAccount.id == ConnectorItem.account_id)
        .where(ConnectorItem.tenant_id == tenant_id, ConnectorAccount.enabled.is_(True))
    )


async def events_between(
    session: AsyncSession, tenant_id: str, start: datetime, end: datetime, limit: int = 100
) -> list[dict[str, Any]]:
    """Events overlapping [start, end), in start order."""
    stmt = (
        _base(tenant_id)
        .where(
            ConnectorItem.kind == KIND_EVENT,
            ConnectorItem.starts_at < end,
            func.coalesce(ConnectorItem.ends_at, ConnectorItem.starts_at) >= start,
        )
        .order_by(ConnectorItem.starts_at)
        .limit(limit)
    )
    return [_as_dict(i, a) for i, a in (await session.execute(stmt)).all()]


async def waiting_on_me(
    session: AsyncSession, tenant_id: str, now: datetime | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Mail that needs the user's reply (docs/specs/connectors.md, Story 4).

    Inbound, addressed to the user directly, not automated, judged by the
    local model to ask something of the user, not answered later in the same
    thread from the same account, and between the configured minimum and
    maximum age. Oldest first: the longest wait is the most overdue.
    """
    now = now or datetime.now(UTC)
    newest = now - timedelta(hours=settings.connector_needs_reply_min_hours)
    oldest = now - timedelta(days=settings.connector_needs_reply_max_days)
    reply = aliased(ConnectorItem)
    answered = exists().where(
        reply.account_id == ConnectorItem.account_id,
        reply.thread_key == ConnectorItem.thread_key,
        reply.direction == DIR_SENT,
        reply.occurred_at > ConnectorItem.occurred_at,
    )
    stmt = (
        _base(tenant_id)
        .where(
            ConnectorItem.kind == KIND_EMAIL,
            ConnectorItem.direction == DIR_INBOUND,
            ConnectorItem.to_me.is_(True),
            ConnectorItem.flags["asks_me"].astext == "true",
            or_(
                ConnectorItem.flags["automated"].astext.is_(None),
                ConnectorItem.flags["automated"].astext != "true",
            ),
            ConnectorItem.occurred_at <= newest,
            ConnectorItem.occurred_at >= oldest,
            ~and_(ConnectorItem.thread_key.is_not(None), answered),
        )
        .order_by(ConnectorItem.occurred_at)
        .limit(limit)
    )
    out = []
    for item, account in (await session.execute(stmt)).all():
        row = _as_dict(item, account)
        row["flags"] = {**row["flags"], "needs_reply": True}
        out.append(row)
    return out


async def open_promises(
    session: AsyncSession, tenant_id: str, now: datetime | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Promises the user made in sent mail that are still open.

    From the last 14 days, not yet turned into a reminder or dismissed, and
    either due within the next week (or overdue) or, with no date, sent in
    the last week. Soonest due first.
    """
    now = now or datetime.now(UTC)
    due = ConnectorItem.flags["commitment_due"].astext
    stmt = (
        _base(tenant_id)
        .where(
            ConnectorItem.kind == KIND_EMAIL,
            ConnectorItem.direction == DIR_SENT,
            ConnectorItem.flags["commitment"].astext.is_not(None),
            ConnectorItem.flags["promise_state"].astext.is_(None),
            ConnectorItem.occurred_at >= now - timedelta(days=14),
            or_(
                and_(due.is_not(None), due <= (now + timedelta(days=7)).date().isoformat()),
                and_(due.is_(None), ConnectorItem.occurred_at >= now - timedelta(days=7)),
            ),
        )
        .order_by(due.asc().nulls_last(), ConnectorItem.occurred_at.desc())
        .limit(limit)
    )
    return [_as_dict(i, a) for i, a in (await session.execute(stmt)).all()]


async def set_flag(session: AsyncSession, tenant_id: str, item_id: str, **flags: Any) -> bool:
    got = await get_item(session, tenant_id, item_id)
    if not got:
        return False
    item = got[0]
    item.flags = {**(item.flags or {}), **flags}
    return True


async def search_email(
    session: AsyncSession,
    tenant_id: str,
    query: str,
    *,
    since: datetime | None = None,
    sender: str | None = None,
    embedding: list[float] | None = None,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Text match on subject/sender/summary, then nearest by embedding."""
    stmt = _base(tenant_id).where(ConnectorItem.kind == KIND_EMAIL)
    if since:
        stmt = stmt.where(ConnectorItem.occurred_at >= since)
    if sender:
        like = f"%{sender.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(ConnectorItem.sender_name).like(like),
                ConnectorItem.sender_addr.like(like),
            )
        )
    found: dict[str, dict[str, Any]] = {}
    terms = [t for t in query.split() if len(t) > 1][:6]
    if terms:
        conds = []
        for t in terms:
            like = f"%{t.lower()}%"
            conds.append(
                or_(
                    func.lower(ConnectorItem.title).like(like),
                    func.lower(ConnectorItem.summary).like(like),
                    func.lower(ConnectorItem.sender_name).like(like),
                    ConnectorItem.sender_addr.like(like),
                )
            )
        text_stmt = stmt.where(and_(*conds)).order_by(ConnectorItem.occurred_at.desc()).limit(limit)
        for item, account in (await session.execute(text_stmt)).all():
            found[str(item.id)] = _as_dict(item, account)
    if embedding is not None and len(found) < limit:
        vec_stmt = (
            stmt.where(ConnectorItem.embedding.is_not(None))
            .order_by(ConnectorItem.embedding.cosine_distance(embedding))
            .limit(limit - len(found))
        )
        for item, account in (await session.execute(vec_stmt)).all():
            found.setdefault(str(item.id), _as_dict(item, account))
    if not terms and embedding is None and sender:
        # Filter-only lookup ("latest mail from Priya").
        recent = stmt.order_by(ConnectorItem.occurred_at.desc()).limit(limit)
        for item, account in (await session.execute(recent)).all():
            found.setdefault(str(item.id), _as_dict(item, account))
    return list(found.values())[:limit]


async def get_item(
    session: AsyncSession, tenant_id: str, item_id: str
) -> tuple[ConnectorItem, ConnectorAccount] | None:
    try:
        iid = uuid.UUID(str(item_id))
    except ValueError:
        return None
    row = (await session.execute(_base(tenant_id).where(ConnectorItem.id == iid))).first()
    return (row[0], row[1]) if row else None


async def item_dict(session: AsyncSession, tenant_id: str, item_id: str) -> dict[str, Any] | None:
    got = await get_item(session, tenant_id, item_id)
    return _as_dict(*got) if got else None


async def pending_summaries(
    session: AsyncSession, account: ConnectorAccount, limit: int
) -> list[ConnectorItem]:
    """Mail still waiting for the local summariser, newest first."""
    stmt = (
        select(ConnectorItem)
        .where(
            ConnectorItem.tenant_id == account.tenant_id,
            ConnectorItem.account_id == account.id,
            ConnectorItem.kind == KIND_EMAIL,
            ConnectorItem.summary_state == "pending",
        )
        .order_by(ConnectorItem.occurred_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def purge_expired(session: AsyncSession, now: datetime | None = None) -> int:
    """Retention: old mail, old and far-future events, disabled accounts' items."""
    now = now or datetime.now(UTC)
    mail_cut = now - timedelta(days=settings.connector_email_retention_days)
    past_cut = now - timedelta(days=settings.connector_event_past_days)
    future_cut = now + timedelta(days=settings.connector_event_future_days)
    disabled = select(ConnectorAccount.id).where(ConnectorAccount.enabled.is_(False))
    result = await session.execute(
        delete(ConnectorItem).where(
            or_(
                and_(ConnectorItem.kind == KIND_EMAIL, ConnectorItem.occurred_at < mail_cut),
                and_(
                    ConnectorItem.kind == KIND_EVENT,
                    or_(
                        func.coalesce(ConnectorItem.ends_at, ConnectorItem.starts_at) < past_cut,
                        ConnectorItem.starts_at > future_cut,
                    ),
                ),
                ConnectorItem.account_id.in_(disabled),
            )
        )
    )
    return result.rowcount or 0


async def counts_by_account(session: AsyncSession, tenant_id: str) -> dict[str, dict[str, int]]:
    stmt = (
        select(ConnectorItem.account_id, ConnectorItem.kind, func.count())
        .where(ConnectorItem.tenant_id == tenant_id)
        .group_by(ConnectorItem.account_id, ConnectorItem.kind)
    )
    out: dict[str, dict[str, int]] = {}
    for account_id, kind, n in (await session.execute(stmt)).all():
        out.setdefault(str(account_id), {})[kind] = n
    return out
