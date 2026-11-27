"""Intake: sources → backlog → dev tasks, for one tenant.

One :meth:`Intake.poll` (the per-minute tick, or "poll now"):

1. **poll** each enabled source that is due (``pollMinutes``; all with
   ``force``) and add candidates whose key is new — a key is never added twice
   (``UNIQUE (tenant_id, external_key)``), whatever happened to its item; a
   still-open "Fix failing CI: <workflow>" item also covers newer failures of
   that workflow;
2. **sync** queued/running items from their dev task (and feed each outcome to
   the source's circuit breaker; post the optional issue comments);
3. **reconcile** the sources polled this round: a closed issue, a TODO gone
   from the base branch, a newer green run of the workflow or an intention no
   longer active → the task is cancelled and the item marked ``skipped``;
4. **start** ``new`` items while under ``maxConcurrent`` (intake items
   queued/running) and ``maxPerDay`` (items started since local midnight),
   skipping sources whose breaker tripped, and only when the start gate allows
   it (kill switch, Governor, subscription share).

Automatic starts queue the task (unattended: the dispatcher's budget checks
apply again when it runs). Nothing here approves anything: each task ends in
the normal ``driver_pr`` / ``driver_plan`` approvals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from life_graph.services.dev.automation import sources as src
from life_graph.services.dev.automation.breaker import Breaker, intake_key
from life_graph.services.dev.automation.clock import start_of_local_day
from life_graph.services.dev.automation.settings import tenant_zone
from life_graph.services.dev.automation.status import active, item_status_for

if TYPE_CHECKING:
    from datetime import datetime

    from life_graph.services.dev.automation.ports import (
        BacklogItem,
        Candidate,
        Exec,
        Gate,
        Intentions,
        Notifier,
        Store,
        Tasks,
    )
    from life_graph.services.dev.automation.settings import AutomationSettings, IntakeSource

logger = logging.getLogger(__name__)

DEFAULT_PERSONA = "code-fixer-local"
INSTRUCTION_MAX = 8000
_CLOSING = "Make a focused change; keep it minimal; make the tests pass."
RESTARTABLE = ("new", "failed", "skipped")
SKIPPABLE = ("new", "failed")

_KIND_LABEL = {
    "github_issues": "GitHub issues",
    "failing_ci": "Failing CI",
    "life_graph_intentions": "Life Graph intentions",
    "todo_comments": "TODO comments",
}

COMMENTS = {
    "picked": lambda task_id, _url=None: (
        f"life-graph picked this up: an agent is working on it (task {task_id}). "
        "The owner reviews the change before anything lands."
    ),
    "pr": lambda _task_id, url=None: f"life-graph opened a pull request for this: {url}",
    "done": lambda _task_id, url=None: (
        f"life-graph: the change for this was merged ({url})."
        if url
        else "life-graph: the change for this was merged."
    ),
}


class IntakeError(Exception):
    """A refused owner action; ``status`` is the HTTP status to answer with."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def source_label(source: IntakeSource | None, project_name: str | None = None) -> str:
    """The source's own name, else e.g. "GitHub issues · race-app"."""
    if source is None:
        return "Intake source"
    if source.name and source.name.strip():
        return source.name.strip()
    return f"{_KIND_LABEL.get(source.kind, source.kind)} · {project_name or source.project_id}"


def build_instruction(item: BacklogItem) -> str:
    """Title + body + source link + the standing guidance, within the task limit."""
    tail_parts = [p for p in (f"Source: {item.url}" if item.url else None, _CLOSING) if p]
    tail = "\n\n" + "\n\n".join(tail_parts)
    body = f"\n\n{item.body.strip()}" if item.body and item.body.strip() else ""
    room = INSTRUCTION_MAX - len(item.title) - len(tail)
    if len(body) > room:
        body = body[: max(0, room - 1)] + "…"
    return f"{item.title}{body}{tail}"


@dataclass
class PollReport:
    added: int = 0
    synced: int = 0
    reconciled: int = 0
    started: int = 0
    polled: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    blocked: list[str] = field(default_factory=list)

    def dump(self) -> dict[str, Any]:
        return {
            "added": self.added,
            "synced": self.synced,
            "reconciled": self.reconciled,
            "started": self.started,
            "polled": self.polled,
            "errors": self.errors,
            "blocked": self.blocked,
        }


@dataclass
class _Polled:
    source: IntakeSource
    project: dict[str, Any]
    candidates: list[Candidate]


class Intake:
    """Intake for one tenant at one instant (build one per tick or request)."""

    def __init__(
        self,
        *,
        tenant_id: str,
        doc: AutomationSettings,
        store: Store,
        tasks: Tasks,
        gate: Gate,
        notifier: Notifier,
        exec_: Exec,
        intentions: Intentions | None,
        now: datetime,
    ) -> None:
        self.tenant = tenant_id
        self.doc = doc
        self.store = store
        self.tasks = tasks
        self.gate = gate
        self.exec = exec_
        self.intentions = intentions
        self.now = now
        self.breaker = Breaker(store, notifier, tenant_id, doc.breaker, now)
        self._projects: dict[str, dict[str, Any] | None] = {}

    # ── helpers ──────────────────────────────────────────

    def _source(self, source_id: str | None) -> IntakeSource | None:
        return next((s for s in self.doc.intake.sources if s.id == source_id), None)

    async def _project(self, project_id: str) -> dict[str, Any] | None:
        if project_id not in self._projects:
            self._projects[project_id] = await self.tasks.project(self.tenant, project_id)
        return self._projects[project_id]

    async def _label(self, source: IntakeSource | None) -> str:
        project = await self._project(source.project_id) if source else None
        return source_label(source, project.get("name") if project else None)

    async def _open_items(self) -> list[BacklogItem]:
        """Every queued/running item (not just the newest page)."""
        out: list[BacklogItem] = []
        for status in ("queued", "running"):
            out.extend(await self.store.list_items(self.tenant, status=status, limit=500))
        return out

    def _due(self, source: IntakeSource) -> bool:
        if not source.last_polled_at:
            return True
        from datetime import datetime

        try:
            last = datetime.fromisoformat(source.last_polled_at)
        except ValueError:
            return True
        return (self.now - last).total_seconds() >= source.poll_minutes * 60

    # ── 1. poll ──────────────────────────────────────────

    async def _poll_sources(self, force: bool, report: PollReport) -> dict[str, _Polled]:
        polled: dict[str, _Polled] = {}
        for source in self.doc.intake.sources:
            if not source.enabled or not source.id or not (force or self._due(source)):
                continue
            project = await self._project(source.project_id)
            if not project or not project.get("is_active", True):
                report.errors[source.id] = "project not found"
                await self.store.mark_polled(self.tenant, source.id, self.now, "project not found")
                continue
            ctx = src.SourceContext(self.tenant, source, project, self.exec, self.intentions)
            try:
                candidates = await src.poll(ctx)
            except Exception as exc:  # noqa: BLE001 — one source's failure never stops the rest
                message = str(exc)[:300] or type(exc).__name__
                logger.warning("Intake poll of %s (%s) failed: %s", source.id, source.kind, message)
                report.errors[source.id] = message
                await self.store.mark_polled(self.tenant, source.id, self.now, message)
                continue
            await self.store.mark_polled(self.tenant, source.id, self.now, None)
            polled[source.id] = _Polled(source, project, candidates)
            report.polled.append(source.id)
            for c in candidates:
                if await self.store.has_key(self.tenant, c.external_key):
                    continue
                if source.kind == "failing_ci" and await self.store.has_open_title(
                    self.tenant, source.id, c.title
                ):
                    continue
                if await self.store.insert_item(self.tenant, source.id, c):
                    report.added += 1
        return polled

    # ── 2. sync ──────────────────────────────────────────

    async def _comment(self, item: BacklogItem, stage: str, url: str | None = None) -> None:
        """One outward issue comment for *stage*, only when the source opted in; never raises."""
        source = self._source(item.source_id)
        if source is None or source.kind != "github_issues" or not source.comment_on_issue:
            return
        if src.parse_issue_key(item.external_key) is None:
            return
        done = list(item.properties.get("comments") or [])
        if stage in done:
            return
        project = await self._project(source.project_id)
        if not project:
            return
        # Recorded before posting: a failure never repeats the comment.
        updated = await self.store.update_item(
            self.tenant, item.id, properties={**item.properties, "comments": [*done, stage]}
        )
        if updated is not None:
            item.properties = updated.properties
        try:
            text = COMMENTS[stage](item.task_id, url)
            await src.comment_on_issue(self.exec, project.get("path"), item.external_key, text)
        except Exception as exc:  # noqa: BLE001 - an outward comment is optional; never fail the sync
            logger.warning("Intake comment %s on %s failed: %s", stage, item.external_key, exc)

    async def sync(self) -> int:
        """Keep queued/running items in step with their tasks; returns how many changed."""
        items = await self._open_items()
        ids = [i.task_id for i in items if i.task_id]
        views = await self.tasks.views(self.tenant, ids) if ids else {}
        changed = 0
        for item in items:
            view = views.get(item.task_id) if item.task_id else None
            source = self._source(item.source_id)
            if view is not None and source is not None:
                await self.breaker.observe(intake_key(source.id), await self._label(source), view)
            if view and view.get("pr_url"):
                await self._comment(item, "pr", view.get("pr_url"))
            status, reason = item_status_for(view)
            if status == item.status:
                continue
            updated = await self.store.update_item(
                self.tenant, item.id, expect=(item.status,), status=status, reason=reason
            )
            if updated is None:
                continue
            changed += 1
            if status == "done":
                await self._comment(updated, "done", view.get("pr_url") if view else None)
        return changed

    # ── 3. reconcile ─────────────────────────────────────

    async def _stale_reason(self, item: BacklogItem, polled: _Polled) -> str | None:
        kind = polled.source.kind
        keys = {c.external_key for c in polled.candidates}
        if kind == "github_issues":
            return await src.issue_closed(self.exec, polled.project.get("path"), item.external_key)
        if kind == "todo_comments":
            ident = src.todo_identity(item.external_key)
            if ident is None:
                return None
            present = any(src.todo_identity(k) == ident for k in keys)
            branch = src.base_branch(polled.project)
            return None if present else f"The TODO comment is gone from {branch}."
        if kind == "failing_ci":
            return await src.ci_green(self.exec, polled.project, item.external_key, item.title)
        if kind == "life_graph_intentions":
            return None if item.external_key in keys else "The intention is no longer active."
        return None

    async def _reconcile(self, polled: dict[str, _Polled]) -> int:
        items = [
            i
            for i in await self._open_items()
            if i.status in ("queued", "running") and i.task_id and i.source_id in polled
        ]
        if not items:
            return 0
        views = await self.tasks.views(self.tenant, [i.task_id for i in items])
        cancelled = 0
        for item in items:
            if not active(views.get(item.task_id)):
                continue
            try:
                reason = await self._stale_reason(item, polled[item.source_id])
                if not reason:
                    continue
                await self.tasks.cancel(self.tenant, item.task_id)
                await self.store.update_item(self.tenant, item.id, status="skipped", reason=reason)
                cancelled += 1
                logger.info("Intake reconciled %s (task %s): %s", item.id, item.task_id, reason)
            except Exception as exc:  # noqa: BLE001 — a failed lookup leaves the item alone
                logger.warning("Intake reconcile of %s failed: %s", item.id, exc)
        return cancelled

    # ── 4. start ─────────────────────────────────────────

    async def _launch(self, item: BacklogItem, source: IntakeSource, *, by: str) -> BacklogItem:
        """Claim the item (``queued``) and create its task; a failure marks it failed."""
        claimed = await self.store.update_item(
            self.tenant,
            item.id,
            expect=RESTARTABLE,
            status="queued",
            reason=None,
            started_at=self.now,
            properties={**item.properties, "started_by": by},
        )
        if claimed is None:
            raise IntakeError(409, f"Backlog item {item.id} changed while starting.")
        label = await self._label(source)
        try:
            project = await self._project(source.project_id)
            if not project or not project.get("is_active", True):
                raise IntakeError(409, f"Project {source.project_id} not found")
            task = await self.tasks.create(
                self.tenant,
                project=project,
                instruction=build_instruction(claimed),
                persona=source.persona or DEFAULT_PERSONA,
                mode=source.mode,
                start_now=by != "auto",
                properties={
                    "origin": "intake",
                    "automation": {
                        "kind": "intake",
                        "source_id": source.id,
                        "backlog_id": item.id,
                        "external_key": item.external_key,
                        "mode": source.mode,
                    },
                    **({"requested_by": by} if by != "auto" else {}),
                },
            )
        except Exception as exc:
            message = str(exc)[:500] or type(exc).__name__
            await self.store.update_item(self.tenant, item.id, status="failed", reason=message)
            await self.breaker.record_failure(intake_key(source.id), label, message)
            logger.warning("Intake could not start %s: %s", item.id, message)
            raise
        task_id = str(task.get("duplicate_of") or task["id"])
        updated = await self.store.update_item(self.tenant, item.id, task_id=task_id)
        result = updated or claimed
        await self._comment(result, "picked")
        logger.info("Intake started %s as task %s (%s)", item.id, task_id, by)
        return result

    async def _start_eligible(self, report: PollReport) -> int:
        intake = self.doc.intake
        zone = tenant_zone(self.doc.timezone)
        concurrent_room = intake.max_concurrent - await self.store.count_active(self.tenant)
        daily_room = intake.max_per_day - await self.store.count_started_since(
            self.tenant, start_of_local_day(self.now, zone)
        )
        room = min(concurrent_room, daily_room)
        if room <= 0:
            return 0
        enabled = {s.id: s for s in intake.sources if s.enabled and s.id}
        tripped = {sid for sid in enabled if await self.breaker.is_tripped(intake_key(sid))}
        if tripped:
            report.blocked.append(f"breaker tripped: {', '.join(sorted(tripped))}")
        candidates = [
            i
            for i in await self.store.list_items(self.tenant, status="new", limit=500)
            if i.source_id in enabled and i.source_id not in tripped
        ]
        candidates.sort(key=lambda i: (i.created_at is None, i.created_at))
        started = 0
        checked: dict[str | None, list[str]] = {}
        for item in candidates:
            if room <= 0:
                break
            source = enabled[item.source_id]
            persona = source.persona or DEFAULT_PERSONA
            if persona not in checked:
                driver = await self.tasks.persona_driver(self.tenant, persona)
                checked[persona] = await self.gate.blockers(self.tenant, driver)
            if checked[persona]:
                report.blocked.extend(r for r in checked[persona] if r not in report.blocked)
                continue
            try:
                await self._launch(item, source, by="auto")
                started += 1
            except Exception:  # noqa: BLE001 — logged and marked failed in _launch
                pass
            room -= 1
        return started

    # ── entry points ─────────────────────────────────────

    async def poll(self, *, force: bool = False) -> PollReport:
        """Poll due sources (all with *force*), sync, reconcile, start eligible items."""
        report = PollReport()
        polled = await self._poll_sources(force, report)
        report.synced = await self.sync()
        if polled:
            report.reconciled = await self._reconcile(polled)
        report.started = await self._start_eligible(report)
        return report

    async def start(self, item_id: str, *, by: str = "owner") -> BacklogItem:
        """Owner "Start now": ignores maxConcurrent/maxPerDay and a tripped breaker;
        the kill switch still applies. A success later resets the breaker."""
        item = await self.store.get_item(self.tenant, item_id)
        if item is None:
            raise IntakeError(404, "Backlog item not found")
        if item.status not in RESTARTABLE:
            raise IntakeError(409, f"Cannot start a {item.status} backlog item.")
        source = self._source(item.source_id)
        if source is None:
            raise IntakeError(409, "The intake source of this item no longer exists.")
        if await self.gate.paused(self.tenant):
            raise IntakeError(409, "Not starting: autonomy is paused (kill switch).")
        try:
            return await self._launch(item, source, by=by)
        except IntakeError:
            raise
        except Exception as exc:
            raise IntakeError(409, f"Could not start: {str(exc)[:300]}") from exc

    async def skip(self, item_id: str) -> BacklogItem:
        """Owner "Skip": only a new or failed item (queued/running ones are reconciled)."""
        item = await self.store.get_item(self.tenant, item_id)
        if item is None:
            raise IntakeError(404, "Backlog item not found")
        if item.status == "skipped":
            return item
        if item.status not in SKIPPABLE:
            raise IntakeError(409, f"Cannot skip a {item.status} backlog item.")
        updated = await self.store.update_item(
            self.tenant, item_id, expect=SKIPPABLE, status="skipped", reason="skipped by the owner"
        )
        if updated is None:
            raise IntakeError(409, "Backlog item changed while skipping.")
        return updated
