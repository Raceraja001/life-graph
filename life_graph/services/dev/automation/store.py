"""The Postgres :class:`~life_graph.services.dev.automation.ports.Store` (migration 066).

Every statement filters by ``tenant_id`` (CHARTER invariant 4). Claims are
done by the database, not by read-then-write: backlog keys by ``INSERT … ON
CONFLICT DO NOTHING`` on ``(tenant_id, external_key)``, schedule slots and
chain runs by partial unique indexes, item transitions by a conditional
``UPDATE … WHERE status IN (…)``, the digest day by a conditional update of
the settings row, and breaker changes under ``SELECT … FOR UPDATE``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, or_, select, true, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from life_graph.models.dev_automation import (
    DevAutomationBreaker,
    DevAutomationSettings,
    DevBacklogItem,
    DevIntakeSource,
    DevSchedule,
    DevScheduleRun,
)
from life_graph.services.dev.automation.breaker import BreakerState
from life_graph.services.dev.automation.ports import BacklogItem, Candidate, ScheduleRun
from life_graph.services.dev.automation.settings import (
    AutomationSettings,
    BreakerSettings,
    DigestSettings,
    IntakeSettings,
    IntakeSource,
    ScheduledDevJob,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_ITEM_FIELDS = frozenset(
    {"status", "task_id", "reason", "started_at", "properties", "title", "body", "url"}
)


def _uuid(value: Any) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _str(value: Any) -> str | None:
    return str(value) if value is not None else None


def item_from_row(row: DevBacklogItem) -> BacklogItem:
    return BacklogItem(
        id=str(row.id),
        tenant_id=row.tenant_id,
        source_id=_str(row.source_id),
        external_key=row.external_key,
        title=row.title,
        body=row.body,
        url=row.url,
        status=row.status,
        task_id=_str(row.task_id),
        reason=row.reason,
        started_at=row.started_at,
        properties=dict(row.properties or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def run_from_row(row: DevScheduleRun) -> ScheduleRun:
    return ScheduleRun(
        id=str(row.id),
        schedule_id=str(row.schedule_id),
        slot_date=row.slot_date,
        trigger=row.trigger,
        outcome=row.outcome,
        task_id=_str(row.task_id),
        predecessor_task_id=_str(row.predecessor_task_id),
        detail=row.detail,
        created_at=row.created_at,
    )


def breaker_from_row(row: DevAutomationBreaker) -> BreakerState:
    return BreakerState(
        key=row.key,
        label=row.label,
        tripped=bool(row.tripped),
        consecutive_failures=int(row.consecutive_failures or 0),
        last_reason=row.last_reason,
        tripped_at=row.tripped_at,
        updated_at=row.updated_at,
        counted=[str(x) for x in (row.counted or [])],
    )


def source_from_row(row: DevIntakeSource) -> IntakeSource:
    return IntakeSource(
        id=str(row.id),
        kind=row.kind,
        name=row.name,
        enabled=bool(row.enabled),
        project_id=str(row.project_id),
        filter=row.filter,
        persona=row.persona,
        mode=row.mode,
        comment_on_issue=bool(row.comment_on_issue),
        poll_minutes=int(row.poll_minutes),
        last_polled_at=row.last_polled_at.isoformat() if row.last_polled_at else None,
        last_error=row.last_error,
    )


def job_from_row(row: DevSchedule, last: DevScheduleRun | None = None) -> ScheduledDevJob:
    return ScheduledDevJob(
        id=str(row.id),
        name=row.name,
        enabled=bool(row.enabled),
        project_id=str(row.project_id),
        instruction=row.instruction,
        persona=row.persona,
        mode=row.mode,
        days=list(row.days or []),
        time=row.time,
        after=_str(row.after_id),
        last_run_at=last.created_at.isoformat() if last and last.created_at else None,
        last_task_id=_str(last.task_id) if last else None,
    )


class SqlStore:
    """The automation's rows in Postgres."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    # ── settings ─────────────────────────────────────────

    async def tenants(self) -> list[str]:
        """Tenants with anything automatic switched on."""
        async with self._sf() as session:
            rows = await session.execute(
                select(DevIntakeSource.tenant_id)
                .where(DevIntakeSource.enabled.is_(True))
                .union(
                    select(DevSchedule.tenant_id).where(DevSchedule.enabled.is_(True)),
                    select(DevAutomationSettings.tenant_id).where(
                        DevAutomationSettings.settings["digest"]["enabled"].astext == "true"
                    ),
                )
            )
            return sorted({r[0] for r in rows.all()})

    async def get_settings(self, tenant_id: str) -> AutomationSettings:
        async with self._sf() as session:
            row = await session.get(DevAutomationSettings, tenant_id)
            sources = (
                (
                    await session.execute(
                        select(DevIntakeSource)
                        .where(DevIntakeSource.tenant_id == tenant_id)
                        .order_by(DevIntakeSource.created_at, DevIntakeSource.id)
                    )
                )
                .scalars()
                .all()
            )
            jobs = (
                (
                    await session.execute(
                        select(DevSchedule)
                        .where(DevSchedule.tenant_id == tenant_id)
                        .order_by(DevSchedule.created_at, DevSchedule.id)
                    )
                )
                .scalars()
                .all()
            )
            last_runs: dict[Any, DevScheduleRun] = {}
            if jobs:
                runs = (
                    (
                        await session.execute(
                            select(DevScheduleRun)
                            .where(
                                DevScheduleRun.tenant_id == tenant_id,
                                DevScheduleRun.task_id.isnot(None),
                            )
                            .distinct(DevScheduleRun.schedule_id)
                            .order_by(DevScheduleRun.schedule_id, DevScheduleRun.created_at.desc())
                        )
                    )
                    .scalars()
                    .all()
                )
                last_runs = {r.schedule_id: r for r in runs}
        raw = dict(row.settings or {}) if row is not None else {}
        return AutomationSettings(
            intake=IntakeSettings(
                **{k: v for k, v in (raw.get("intake") or {}).items() if k != "sources"},
                sources=[source_from_row(s) for s in sources],
            ),
            schedules=[job_from_row(j, last_runs.get(j.id)) for j in jobs],
            digest=DigestSettings(**(raw.get("digest") or {})),
            breaker=BreakerSettings(**(raw.get("breaker") or {})),
            timezone=raw.get("timezone"),
        )

    async def save_settings(
        self, tenant_id: str, doc: AutomationSettings, updated_by: str | None
    ) -> AutomationSettings:
        """Replace the document: sources/jobs are upserted by id, missing ones deleted."""
        body = {
            "intake": {
                "maxConcurrent": doc.intake.max_concurrent,
                "maxPerDay": doc.intake.max_per_day,
            },
            "digest": doc.digest.model_dump(by_alias=True),
            "breaker": doc.breaker.model_dump(by_alias=True),
            "timezone": doc.timezone,
        }
        async with self._sf() as session:
            stmt = pg_insert(DevAutomationSettings).values(
                tenant_id=tenant_id, settings=body, state={}, updated_by=updated_by
            )
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["tenant_id"],
                    set_={"settings": body, "updated_by": updated_by, "updated_at": func.now()},
                )
            )
            keep_sources = [_uuid(s.id) for s in doc.intake.sources]
            await session.execute(
                delete(DevIntakeSource).where(
                    DevIntakeSource.tenant_id == tenant_id,
                    DevIntakeSource.id.notin_(keep_sources) if keep_sources else true(),
                )
            )
            for s in doc.intake.sources:
                values = {
                    "kind": s.kind,
                    "name": s.name,
                    "project_id": _uuid(s.project_id),
                    "filter": s.filter,
                    "persona": s.persona,
                    "mode": s.mode,
                    "enabled": s.enabled,
                    "poll_minutes": s.poll_minutes,
                    "comment_on_issue": s.comment_on_issue,
                }
                ins = pg_insert(DevIntakeSource).values(
                    id=_uuid(s.id), tenant_id=tenant_id, **values
                )
                await session.execute(
                    ins.on_conflict_do_update(
                        index_elements=["id"],
                        set_={**values, "updated_at": func.now()},
                        where=DevIntakeSource.tenant_id == tenant_id,
                    )
                )
            keep_jobs = [_uuid(j.id) for j in doc.schedules]
            await session.execute(
                delete(DevSchedule).where(
                    DevSchedule.tenant_id == tenant_id,
                    DevSchedule.id.notin_(keep_jobs) if keep_jobs else true(),
                )
            )
            # Two passes: every job exists before any ``after`` points at it.
            for j in doc.schedules:
                values = {
                    "name": j.name,
                    "project_id": _uuid(j.project_id),
                    "instruction": j.instruction,
                    "persona": j.persona,
                    "mode": j.mode,
                    "days": list(j.days),
                    "time": j.time,
                    "enabled": j.enabled,
                }
                ins = pg_insert(DevSchedule).values(id=_uuid(j.id), tenant_id=tenant_id, **values)
                await session.execute(
                    ins.on_conflict_do_update(
                        index_elements=["id"],
                        set_={**values, "updated_at": func.now()},
                        where=DevSchedule.tenant_id == tenant_id,
                    )
                )
            for j in doc.schedules:
                await session.execute(
                    update(DevSchedule)
                    .where(DevSchedule.tenant_id == tenant_id, DevSchedule.id == _uuid(j.id))
                    .values(after_id=_uuid(j.after))
                )
            await session.commit()
        return await self.get_settings(tenant_id)

    async def get_state(self, tenant_id: str) -> dict[str, Any]:
        async with self._sf() as session:
            row = await session.get(DevAutomationSettings, tenant_id)
            return dict(row.state or {}) if row is not None else {}

    async def claim_digest(self, tenant_id: str, date: str, window_end: datetime) -> bool:
        patch = {"digest_date": date, "digest_to": window_end.isoformat()}
        async with self._sf() as session:
            result = await session.execute(
                update(DevAutomationSettings)
                .where(
                    DevAutomationSettings.tenant_id == tenant_id,
                    or_(
                        DevAutomationSettings.state["digest_date"].astext.is_(None),
                        DevAutomationSettings.state["digest_date"].astext != date,
                    ),
                )
                .values(
                    state=DevAutomationSettings.state.op("||")(
                        func.jsonb_build_object(
                            "digest_date", date, "digest_to", patch["digest_to"]
                        )
                    )
                )
            )
            await session.commit()
            return bool(result.rowcount)

    async def mark_polled(
        self, tenant_id: str, source_id: str, at: datetime, error: str | None
    ) -> None:
        async with self._sf() as session:
            await session.execute(
                update(DevIntakeSource)
                .where(
                    DevIntakeSource.tenant_id == tenant_id, DevIntakeSource.id == _uuid(source_id)
                )
                .values(last_polled_at=at, last_error=error)
            )
            await session.commit()

    # ── backlog ──────────────────────────────────────────

    async def insert_item(self, tenant_id: str, source_id: str, c: Candidate) -> bool:
        async with self._sf() as session:
            result = await session.execute(
                pg_insert(DevBacklogItem)
                .values(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    source_id=_uuid(source_id),
                    external_key=c.external_key[:300],
                    title=c.title[:300],
                    body=(c.body or None) and c.body[:8000],
                    url=c.url,
                    status="new",
                    properties={},
                )
                .on_conflict_do_nothing(constraint="uq_dev_backlog_tenant_key")
            )
            await session.commit()
            return bool(result.rowcount)

    async def has_key(self, tenant_id: str, external_key: str) -> bool:
        async with self._sf() as session:
            found = await session.execute(
                select(DevBacklogItem.id).where(
                    DevBacklogItem.tenant_id == tenant_id,
                    DevBacklogItem.external_key == external_key,
                )
            )
            return found.first() is not None

    async def has_open_title(self, tenant_id: str, source_id: str, title: str) -> bool:
        async with self._sf() as session:
            found = await session.execute(
                select(DevBacklogItem.id).where(
                    DevBacklogItem.tenant_id == tenant_id,
                    DevBacklogItem.source_id == _uuid(source_id),
                    DevBacklogItem.title == title,
                    DevBacklogItem.status.in_(("new", "queued", "running")),
                )
            )
            return found.first() is not None

    async def get_item(self, tenant_id: str, item_id: str) -> BacklogItem | None:
        try:
            pk = _uuid(item_id)
        except ValueError:
            return None
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(DevBacklogItem).where(
                        DevBacklogItem.tenant_id == tenant_id, DevBacklogItem.id == pk
                    )
                )
            ).scalar_one_or_none()
            return item_from_row(row) if row is not None else None

    async def list_items(
        self, tenant_id: str, status: str | None = None, limit: int = 200
    ) -> list[BacklogItem]:
        stmt = select(DevBacklogItem).where(DevBacklogItem.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(DevBacklogItem.status == status)
        async with self._sf() as session:
            rows = (
                (
                    await session.execute(
                        stmt.order_by(DevBacklogItem.created_at.desc()).limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return [item_from_row(r) for r in rows]

    async def update_item(
        self,
        tenant_id: str,
        item_id: str,
        *,
        expect: tuple[str, ...] | None = None,
        **fields: Any,
    ) -> BacklogItem | None:
        unknown = set(fields) - _ITEM_FIELDS
        if unknown:
            raise ValueError(f"unknown backlog fields: {sorted(unknown)}")
        if "task_id" in fields:
            fields["task_id"] = _uuid(fields["task_id"])
        stmt = (
            update(DevBacklogItem)
            .where(DevBacklogItem.tenant_id == tenant_id, DevBacklogItem.id == _uuid(item_id))
            .values(**fields, updated_at=func.now())
            .returning(DevBacklogItem)
        )
        if expect:
            stmt = stmt.where(DevBacklogItem.status.in_(expect))
        async with self._sf() as session:
            row = (await session.execute(stmt)).scalar_one_or_none()
            await session.commit()
            return item_from_row(row) if row is not None else None

    async def count_active(self, tenant_id: str) -> int:
        async with self._sf() as session:
            return int(
                (
                    await session.execute(
                        select(func.count(DevBacklogItem.id)).where(
                            DevBacklogItem.tenant_id == tenant_id,
                            DevBacklogItem.status.in_(("queued", "running")),
                        )
                    )
                ).scalar()
                or 0
            )

    async def count_started_since(self, tenant_id: str, since: datetime) -> int:
        async with self._sf() as session:
            return int(
                (
                    await session.execute(
                        select(func.count(DevBacklogItem.id)).where(
                            DevBacklogItem.tenant_id == tenant_id,
                            DevBacklogItem.started_at >= since,
                        )
                    )
                ).scalar()
                or 0
            )

    # ── breakers ─────────────────────────────────────────

    async def get_breaker(self, tenant_id: str, key: str) -> BreakerState | None:
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(DevAutomationBreaker).where(
                        DevAutomationBreaker.tenant_id == tenant_id,
                        DevAutomationBreaker.key == key,
                    )
                )
            ).scalar_one_or_none()
            return breaker_from_row(row) if row is not None else None

    async def update_breaker(
        self,
        tenant_id: str,
        key: str,
        fn: Callable[[BreakerState | None], BreakerState | None],
    ) -> BreakerState | None:
        """Apply *fn* to the current state under a row lock; returns the stored state."""
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(DevAutomationBreaker)
                    .where(
                        DevAutomationBreaker.tenant_id == tenant_id,
                        DevAutomationBreaker.key == key,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            prev = breaker_from_row(row) if row is not None else None
            nxt = fn(prev)
            if nxt is None:
                await session.rollback()
                return prev
            if row is None:
                row = DevAutomationBreaker(id=uuid.uuid4(), tenant_id=tenant_id, key=key)
                session.add(row)
            row.label = nxt.label
            row.tripped = nxt.tripped
            row.consecutive_failures = nxt.consecutive_failures
            row.last_reason = nxt.last_reason
            row.tripped_at = nxt.tripped_at
            row.counted = list(nxt.counted)
            if nxt.updated_at is not None:
                row.updated_at = nxt.updated_at
            try:
                await session.commit()
            except IntegrityError:
                # A first failure recorded by two ticks at once: the other one won.
                await session.rollback()
                return await self.get_breaker(tenant_id, key)
            return nxt

    async def list_breakers(self, tenant_id: str) -> list[BreakerState]:
        async with self._sf() as session:
            rows = (
                (
                    await session.execute(
                        select(DevAutomationBreaker)
                        .where(DevAutomationBreaker.tenant_id == tenant_id)
                        .order_by(
                            DevAutomationBreaker.tripped.desc(),
                            DevAutomationBreaker.updated_at.desc(),
                        )
                    )
                )
                .scalars()
                .all()
            )
            return [breaker_from_row(r) for r in rows]

    # ── schedule runs ────────────────────────────────────

    async def claim_run(
        self,
        tenant_id: str,
        schedule_id: str,
        slot_date: str,
        trigger: str,
        outcome: str,
        *,
        predecessor_task_id: str | None = None,
        detail: str | None = None,
    ) -> str | None:
        run_id = uuid.uuid4()
        async with self._sf() as session:
            exists = (
                await session.execute(
                    select(DevSchedule.id).where(
                        DevSchedule.tenant_id == tenant_id, DevSchedule.id == _uuid(schedule_id)
                    )
                )
            ).first()
            if exists is None:
                return None
            result = await session.execute(
                pg_insert(DevScheduleRun)
                .values(
                    id=run_id,
                    tenant_id=tenant_id,
                    schedule_id=_uuid(schedule_id),
                    slot_date=slot_date,
                    trigger=trigger,
                    outcome=outcome,
                    predecessor_task_id=_uuid(predecessor_task_id),
                    detail=detail,
                )
                .on_conflict_do_nothing()
            )
            await session.commit()
            return str(run_id) if result.rowcount else None

    async def finish_run(
        self,
        tenant_id: str,
        run_id: str,
        outcome: str,
        task_id: str | None,
        detail: str | None,
    ) -> None:
        async with self._sf() as session:
            await session.execute(
                update(DevScheduleRun)
                .where(DevScheduleRun.tenant_id == tenant_id, DevScheduleRun.id == _uuid(run_id))
                .values(
                    outcome=outcome, task_id=_uuid(task_id), detail=detail, updated_at=func.now()
                )
            )
            await session.commit()

    async def release_run(self, tenant_id: str, run_id: str) -> None:
        async with self._sf() as session:
            await session.execute(
                delete(DevScheduleRun).where(
                    DevScheduleRun.tenant_id == tenant_id, DevScheduleRun.id == _uuid(run_id)
                )
            )
            await session.commit()

    async def has_slot(self, tenant_id: str, schedule_id: str, slot_date: str) -> bool:
        async with self._sf() as session:
            found = await session.execute(
                select(DevScheduleRun.id).where(
                    DevScheduleRun.tenant_id == tenant_id,
                    DevScheduleRun.schedule_id == _uuid(schedule_id),
                    DevScheduleRun.slot_date == slot_date,
                    DevScheduleRun.trigger == "scheduled",
                )
            )
            return found.first() is not None

    async def has_chain_claim(
        self, tenant_id: str, schedule_id: str, predecessor_task_id: str
    ) -> bool:
        async with self._sf() as session:
            found = await session.execute(
                select(DevScheduleRun.id).where(
                    DevScheduleRun.tenant_id == tenant_id,
                    DevScheduleRun.schedule_id == _uuid(schedule_id),
                    DevScheduleRun.trigger == "chain",
                    DevScheduleRun.predecessor_task_id == _uuid(predecessor_task_id),
                )
            )
            return found.first() is not None

    async def latest_run_with_task(self, tenant_id: str, schedule_id: str) -> ScheduleRun | None:
        async with self._sf() as session:
            row = (
                await session.execute(
                    select(DevScheduleRun)
                    .where(
                        DevScheduleRun.tenant_id == tenant_id,
                        DevScheduleRun.schedule_id == _uuid(schedule_id),
                        DevScheduleRun.task_id.isnot(None),
                    )
                    .order_by(DevScheduleRun.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return run_from_row(row) if row is not None else None

    async def list_runs(
        self, tenant_id: str, schedule_id: str, limit: int = 50
    ) -> list[ScheduleRun]:
        async with self._sf() as session:
            rows = (
                (
                    await session.execute(
                        select(DevScheduleRun)
                        .where(
                            DevScheduleRun.tenant_id == tenant_id,
                            DevScheduleRun.schedule_id == _uuid(schedule_id),
                        )
                        .order_by(DevScheduleRun.created_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return [run_from_row(r) for r in rows]
