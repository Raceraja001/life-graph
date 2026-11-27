"""Dev-task schedules and chains, for one tenant.

One :meth:`Scheduler.tick` (every minute, from the ARQ cron):

1. feed each job's latest run task to its circuit breaker (``schedule:<id>``,
   each task once);
2. **chains** — an enabled job with ``after`` starts once per predecessor
   task, when the predecessor job's latest run task *finished its work*
   (status/stage in ``status.FINISHED_STAGES``) and that run is less than
   24 h old. While the start is refused (kill switch, breaker, budget, the
   job's previous task still going) nothing is claimed, so it is **held** and
   retried each tick inside the 24 h window;
3. **slots** — an enabled job without ``after`` runs once per tenant-local
   day at ``time`` on its ``days``; a slot up to 2 h late (the worker was
   down) is caught up, later ones are recorded ``missed``. The slot is claimed
   in ``dev_schedule_runs`` before the start (a partial unique index), so
   overlapping ticks and restarts never run it twice. A refused slot is
   recorded with its reason (``skipped_*``) and not retried.

"Run now" (:meth:`run_now`) bypasses the breaker and the budget (the owner
asked: it starts at once, interactive); the kill switch and the overlap check
still apply. Tasks are normal dev tasks: nothing here approves anything.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from life_graph.services.dev.automation.breaker import Breaker, schedule_key
from life_graph.services.dev.automation.clock import (
    CATCH_UP_MINUTES,
    decide_slot,
    local_parts,
    previous_local_parts,
)
from life_graph.services.dev.automation.intake import DEFAULT_PERSONA
from life_graph.services.dev.automation.settings import tenant_zone
from life_graph.services.dev.automation.status import active, finished

if TYPE_CHECKING:
    from life_graph.services.dev.automation.ports import Gate, Notifier, Store, Tasks
    from life_graph.services.dev.automation.settings import AutomationSettings, ScheduledDevJob

logger = logging.getLogger(__name__)

#: A predecessor run older than this never triggers its chain.
CHAIN_WINDOW = timedelta(hours=24)


class ScheduleError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class StartResult:
    outcome: str
    task_id: str | None = None
    detail: str | None = None

    def dump(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "taskId": self.task_id, "detail": self.detail}


class Scheduler:
    """The scheduler of one tenant at one instant (build one per tick or request)."""

    def __init__(
        self,
        *,
        tenant_id: str,
        doc: AutomationSettings,
        store: Store,
        tasks: Tasks,
        gate: Gate,
        notifier: Notifier,
        now: datetime,
        catch_up_minutes: int = CATCH_UP_MINUTES,
    ) -> None:
        self.tenant = tenant_id
        self.doc = doc
        self.store = store
        self.tasks = tasks
        self.gate = gate
        self.now = now
        self.catch_up = catch_up_minutes
        self.zone = tenant_zone(doc.timezone)
        self.breaker = Breaker(store, notifier, tenant_id, doc.breaker, now)

    def _job(self, job_id: str) -> ScheduledDevJob | None:
        return next((j for j in self.doc.schedules if j.id == job_id), None)

    async def _latest_view(self, job: ScheduledDevJob) -> tuple[Any, dict[str, Any] | None]:
        run = await self.store.latest_run_with_task(self.tenant, job.id)
        if run is None or not run.task_id:
            return run, None
        views = await self.tasks.views(self.tenant, [run.task_id])
        return run, views.get(run.task_id)

    async def _observe(self, job: ScheduledDevJob) -> None:
        _, view = await self._latest_view(job)
        if view is not None:
            await self.breaker.observe(schedule_key(job.id), job.name, view)

    async def _refusal(self, job: ScheduledDevJob, automatic: bool) -> StartResult | None:
        if await self.gate.paused(self.tenant):
            return StartResult("skipped_kill_switch", detail="Autonomy is paused (kill switch).")
        if automatic and await self.breaker.is_tripped(schedule_key(job.id)):
            return StartResult(
                "skipped_breaker",
                detail="Paused by the circuit breaker after repeated identical failures.",
            )
        _, view = await self._latest_view(job)
        if active(view):
            return StartResult(
                "skipped_overlap", detail="The previous run of this job is still going."
            )
        if automatic:
            driver = await self.tasks.persona_driver(self.tenant, job.persona or DEFAULT_PERSONA)
            reasons = await self.gate.blockers(self.tenant, driver)
            if reasons:
                return StartResult("skipped_budget", detail="; ".join(reasons)[:500])
        return None

    async def _create(
        self, job: ScheduledDevJob, run_id: str, *, automatic: bool, after_task: str | None
    ) -> StartResult:
        try:
            project = await self.tasks.project(self.tenant, job.project_id)
            if not project or not project.get("is_active", True):
                raise ScheduleError(409, f"Project {job.project_id} not found")
            task = await self.tasks.create(
                self.tenant,
                project=project,
                instruction=job.instruction,
                persona=job.persona or DEFAULT_PERSONA,
                mode=job.mode,
                start_now=not automatic,
                properties={
                    "origin": "schedule",
                    "automation": {
                        "kind": "schedule",
                        "job_id": job.id,
                        "run_id": run_id,
                        "mode": job.mode,
                        **({"after_task_id": after_task} if after_task else {}),
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)[:500] or type(exc).__name__
            await self.breaker.record_failure(schedule_key(job.id), job.name, detail)
            return StartResult("failed", detail=detail)
        return StartResult("started", task_id=str(task.get("duplicate_of") or task["id"]))

    async def _start(
        self, job: ScheduledDevJob, run_id: str, *, automatic: bool, after_task: str | None = None
    ) -> StartResult:
        await self._observe(job)  # count the previous run before a newer one is the latest
        result = await self._refusal(job, automatic)
        if result is None:
            result = await self._create(job, run_id, automatic=automatic, after_task=after_task)
        await self.store.finish_run(
            self.tenant, run_id, result.outcome, result.task_id, result.detail
        )
        log = logger.info if result.outcome == "started" else logger.warning
        log("Schedule %s (%s): %s %s", job.id, job.name, result.outcome, result.detail or "")
        return result

    async def _chains(self, date: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for job in self.doc.schedules:
            if not job.enabled or not job.after or not job.id:
                continue
            run = await self.store.latest_run_with_task(self.tenant, job.after)
            if run is None or not run.task_id or run.created_at is None:
                continue
            if self.now - run.created_at > CHAIN_WINDOW:
                continue
            views = await self.tasks.views(self.tenant, [run.task_id])
            if not finished(views.get(run.task_id)):
                continue
            if await self.store.has_chain_claim(self.tenant, job.id, run.task_id):
                continue
            # Blocked: claim nothing, so a later tick retries while inside the window.
            if await self._refusal(job, True):
                continue
            run_id = await self.store.claim_run(
                self.tenant,
                job.id,
                date,
                "chain",
                "starting",
                predecessor_task_id=run.task_id,
            )
            if run_id is None:
                continue  # an overlapping tick claimed it
            result = await self._start(job, run_id, automatic=True, after_task=run.task_id)
            if result.outcome.startswith("skipped"):
                # Refused between the check and the start: release so it retries.
                await self.store.release_run(self.tenant, run_id)
            results.append({"jobId": job.id, "date": date, **result.dump()})
        return results

    async def tick(self) -> list[dict[str, Any]]:
        """Start every due job and chain; returns what happened per handled slot."""
        today = local_parts(self.now, self.zone)
        yesterday = previous_local_parts(self.now, self.zone)
        for job in self.doc.schedules:
            if job.id:
                await self._observe(job)
        results = await self._chains(today.date)
        for job in self.doc.schedules:
            if not job.id:
                continue
            handled: dict[str, bool] = {}
            for date in {today.date, yesterday.date}:
                handled[date] = await self.store.has_slot(self.tenant, job.id, date)
            decision = decide_slot(
                enabled=job.enabled,
                days=job.days,
                time=job.time,
                after=job.after,
                today=today,
                yesterday=yesterday,
                handled=lambda d, h=handled: h.get(d, False),
                catch_up_minutes=self.catch_up,
            )
            if decision.kind == "not_due" or decision.date is None:
                continue
            if decision.kind == "missed":
                detail = (
                    f"Missed by {decision.late_minutes} min (the worker was not running); skipped."
                )
                if await self.store.claim_run(
                    self.tenant, job.id, decision.date, "scheduled", "missed", detail=detail
                ):
                    results.append(
                        {
                            "jobId": job.id,
                            "date": decision.date,
                            "outcome": "missed",
                            "detail": detail,
                        }
                    )
                continue
            run_id = await self.store.claim_run(
                self.tenant, job.id, decision.date, "scheduled", "starting"
            )
            if run_id is None:
                continue  # another tick claimed it
            result = await self._start(job, run_id, automatic=True)
            results.append({"jobId": job.id, "date": decision.date, **result.dump()})
        return results

    async def run_now(self, job_id: str) -> dict[str, Any]:
        """Owner "Run now": 404 unknown job, 409 when refused."""
        job = self._job(job_id)
        if job is None:
            raise ScheduleError(404, "Scheduled job not found")
        date = local_parts(self.now, self.zone).date
        run_id = await self.store.claim_run(self.tenant, job.id, date, "manual", "starting")
        if run_id is None:
            raise ScheduleError(409, "Could not record the run.")
        result = await self._start(job, run_id, automatic=False)
        if result.outcome != "started" or not result.task_id:
            raise ScheduleError(409, result.detail or "The job could not start.")
        return {"taskId": result.task_id, "runId": run_id}
