"""The automation facade: what the API routes and the per-minute cron call.

:class:`AutomationService` holds the ports; each call builds the per-tenant
:class:`Intake` / :class:`Scheduler` / :class:`Digest` for "now" from the
tenant's current settings. :func:`get_service` is the process-wide instance
over Postgres and the real dev-task pipeline.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from life_graph.core.tenant import set_tenant_context
from life_graph.services import night_shift
from life_graph.services.dev.automation.breaker import Breaker
from life_graph.services.dev.automation.digest import Digest
from life_graph.services.dev.automation.intake import DEFAULT_PERSONA, Intake, IntakeError
from life_graph.services.dev.automation.scheduler import Scheduler
from life_graph.services.dev.automation.settings import assign_ids, settings_problem
from life_graph.services.dev.automation.store import SqlStore
from life_graph.services.dev.automation.wiring import (
    DevTasks,
    EventNotifier,
    NativeIntentions,
    StartGate,
    run_command,
)
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    from collections.abc import Callable

    from life_graph.services.dev.automation.digest import ReportFn
    from life_graph.services.dev.automation.ports import (
        Exec,
        Gate,
        Intentions,
        Notifier,
        Store,
        Tasks,
    )
    from life_graph.services.dev.automation.settings import AutomationSettings

logger = logging.getLogger(__name__)


class SettingsError(Exception):
    """A settings document the save refuses (HTTP 400)."""


class AutomationService:
    def __init__(
        self,
        *,
        store: Store,
        tasks: Tasks,
        gate: Gate,
        notifier: Notifier,
        exec_: Exec,
        intentions: Intentions | None,
        report_fn: ReportFn,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.tasks = tasks
        self.gate = gate
        self.notifier = notifier
        self.exec = exec_
        self.intentions = intentions
        self.report_fn = report_fn
        self.clock = clock or (lambda: datetime.now(UTC))

    # ── builders ─────────────────────────────────────────

    async def _intake(self, tenant_id: str, doc: AutomationSettings | None = None) -> Intake:
        return Intake(
            tenant_id=tenant_id,
            doc=doc or await self.store.get_settings(tenant_id),
            store=self.store,
            tasks=self.tasks,
            gate=self.gate,
            notifier=self.notifier,
            exec_=self.exec,
            intentions=self.intentions,
            now=self.clock(),
        )

    async def _scheduler(self, tenant_id: str, doc: AutomationSettings | None = None) -> Scheduler:
        return Scheduler(
            tenant_id=tenant_id,
            doc=doc or await self.store.get_settings(tenant_id),
            store=self.store,
            tasks=self.tasks,
            gate=self.gate,
            notifier=self.notifier,
            now=self.clock(),
        )

    async def _digest(self, tenant_id: str, doc: AutomationSettings | None = None) -> Digest:
        return Digest(
            tenant_id=tenant_id,
            doc=doc or await self.store.get_settings(tenant_id),
            store=self.store,
            notifier=self.notifier,
            report_fn=self.report_fn,
            now=self.clock(),
        )

    async def _breaker(self, tenant_id: str) -> Breaker:
        doc = await self.store.get_settings(tenant_id)
        return Breaker(self.store, self.notifier, tenant_id, doc.breaker, self.clock())

    # ── settings ─────────────────────────────────────────

    async def get_settings(self, tenant_id: str) -> AutomationSettings:
        return await self.store.get_settings(tenant_id)

    async def save_settings(
        self, tenant_id: str, doc: AutomationSettings, updated_by: str | None
    ) -> AutomationSettings:
        """Validate (ids, chains, projects, personas) and replace the document."""
        doc = assign_ids(doc)
        problem = settings_problem(doc)
        if problem:
            raise SettingsError(problem)
        projects: dict[str, bool] = {}
        personas: dict[str, bool] = {}
        for where, project_id, persona in [
            *(
                (f'source "{s.name or s.kind}"', s.project_id, s.persona)
                for s in doc.intake.sources
            ),
            *((f'job "{j.name}"', j.project_id, j.persona) for j in doc.schedules),
        ]:
            if project_id not in projects:
                project = await self.tasks.project(tenant_id, project_id)
                projects[project_id] = bool(project)
            if not projects[project_id]:
                raise SettingsError(f"{where}: project {project_id} not found")
            name = persona or DEFAULT_PERSONA
            if name not in personas:
                personas[name] = bool(await self.tasks.persona_driver(tenant_id, name))
            if not personas[name]:
                raise SettingsError(f"{where}: persona {name!r} not found or has no driver")
        return await self.store.save_settings(tenant_id, doc, updated_by)

    # ── intake ───────────────────────────────────────────

    async def list_backlog(
        self, tenant_id: str, status: str | None, limit: int = 200
    ) -> list[dict[str, Any]]:
        return [i.dump() for i in await self.store.list_items(tenant_id, status, limit)]

    async def poll(self, tenant_id: str, *, force: bool = True) -> dict[str, Any]:
        return (await (await self._intake(tenant_id)).poll(force=force)).dump()

    async def start_item(self, tenant_id: str, item_id: str, by: str) -> dict[str, Any]:
        return (await (await self._intake(tenant_id)).start(item_id, by=by)).dump()

    async def skip_item(self, tenant_id: str, item_id: str) -> dict[str, Any]:
        return (await (await self._intake(tenant_id)).skip(item_id)).dump()

    # ── schedules ────────────────────────────────────────

    async def run_now(self, tenant_id: str, job_id: str) -> dict[str, Any]:
        return await (await self._scheduler(tenant_id)).run_now(job_id)

    async def list_runs(self, tenant_id: str, job_id: str, limit: int = 50) -> list[dict]:
        doc = await self.store.get_settings(tenant_id)
        if not any(j.id == job_id for j in doc.schedules):
            raise IntakeError(404, "Scheduled job not found")
        return [r.dump() for r in await self.store.list_runs(tenant_id, job_id, limit)]

    # ── breakers ─────────────────────────────────────────

    async def list_breakers(self, tenant_id: str) -> list[dict[str, Any]]:
        return [b.dump() for b in await self.store.list_breakers(tenant_id)]

    async def reset_breaker(self, tenant_id: str, key: str) -> dict[str, Any]:
        state = await (await self._breaker(tenant_id)).reset(key)
        if state is None:
            raise IntakeError(404, f"No circuit breaker state for {key}")
        return state.dump()

    # ── digest ───────────────────────────────────────────

    async def digest_preview(self, tenant_id: str) -> dict[str, Any]:
        return await (await self._digest(tenant_id)).preview()

    # ── the per-minute tick ──────────────────────────────

    async def tick_tenant(self, tenant_id: str) -> dict[str, Any]:
        """Schedules, then intake (due sources), then the digest; each isolated."""
        doc = await self.store.get_settings(tenant_id)
        out: dict[str, Any] = {}
        for name, step in (
            ("schedules", lambda: self._scheduler(tenant_id, doc)),
            ("intake", lambda: self._intake(tenant_id, doc)),
            ("digest", lambda: self._digest(tenant_id, doc)),
        ):
            try:
                runner = await step()
                if name == "schedules":
                    out[name] = await runner.tick()
                elif name == "intake":
                    if any(s.enabled for s in doc.intake.sources):
                        out[name] = (await runner.poll(force=False)).dump()
                else:
                    out[name] = await runner.tick()
            except Exception as exc:  # noqa: BLE001 — one part's failure never stops the rest
                logger.exception("Dev automation %s tick failed for %s", name, tenant_id)
                out[name] = {"error": str(exc)[:300]}
        return out

    async def tick_all(self) -> dict[str, Any]:
        report: dict[str, Any] = {}
        for tenant_id in await self.store.tenants():
            set_tenant_context(tenant_id, "system")
            report[tenant_id] = await self.tick_tenant(tenant_id)
        return report


async def _night_shift_report(tenant_id: str, since: datetime) -> dict[str, Any]:
    async with async_session() as session:
        return await night_shift.report(session, tenant_id, since)


@lru_cache(maxsize=1)
def get_service() -> AutomationService:
    """The process-wide service over Postgres and the real dev-task pipeline."""
    return AutomationService(
        store=SqlStore(async_session),
        tasks=DevTasks(async_session),
        gate=StartGate(),
        notifier=EventNotifier(),
        exec_=run_command,
        intentions=NativeIntentions(async_session),
        report_fn=_night_shift_report,
    )
