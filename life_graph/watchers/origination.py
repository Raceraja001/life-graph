"""Watcher → Task origination (Agent Drivers spec, Story 6).

Turns actionable watcher findings into kernel agent tasks so recurring
operational work originates from the system — not from the user typing
requests. Given a ``WATCHER_COMPLETED`` payload, each actionable finding
is mapped to a persona + task_type via pipeline rules, gated by per-tenant
and per-project WIP limits, deduped against already-open tasks, and spawned
via the :class:`ProcessManager`.

The hourly watcher cron (``workers/tasks.py::run_watchers``) calls
:meth:`originate` directly after collecting findings. The event-driven
:meth:`subscribe` path is provided for the in-process framework path and
tests; it is intentionally *not* wired in the API process, because the
Redis bridge is publish-only and would not deliver worker-emitted events
to an API-process subscriber (which would also risk double-spawning).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import func, select

from life_graph.core.events import Event, EventBus, EventType, event_bus
from life_graph.models.db import AgentTask
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

DEFAULT_TENANT_WIP = 5
DEFAULT_PROJECT_WIP = 2
ACTIONABLE_SEVERITIES = {"critical", "important"}
_OPEN_STATUSES = ("queued", "running")

# Pipeline rules: watcher_name → (agent_name, task_type).
# A finding may override these with its own ``agent_name`` / ``task_type``.
PIPELINE_RULES: dict[str, tuple[str, str]] = {
    "dependency": ("dependency-updater", "dependency_update"),
    "dependency_watcher": ("dependency-updater", "dependency_update"),
    "server_health": ("uzhavu-ops", "incident_fix"),
}


class TaskOriginationService:
    """Spawns kernel tasks from actionable watcher findings."""

    def __init__(
        self,
        process_manager: Any,
        *,
        session_factory: Any = async_session,
        bus: EventBus | None = None,
        tenant_wip: int = DEFAULT_TENANT_WIP,
        project_wip: int = DEFAULT_PROJECT_WIP,
        rules: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self._pm = process_manager
        self._session_factory = session_factory
        self._bus = bus or event_bus
        self._tenant_wip = tenant_wip
        self._project_wip = project_wip
        self._rules = rules if rules is not None else PIPELINE_RULES
        self._subscribed = False

    # ── Subscription lifecycle (event-driven path) ────────────

    def subscribe(self) -> None:
        """Register as a WATCHER_COMPLETED handler. Idempotent."""
        if self._subscribed:
            return
        self._bus.subscribe(EventType.WATCHER_COMPLETED, self._on_watcher_completed)
        self._subscribed = True

    def unsubscribe(self) -> None:
        """Remove the WATCHER_COMPLETED handler. Idempotent."""
        if not self._subscribed:
            return
        self._bus.unsubscribe(EventType.WATCHER_COMPLETED, self._on_watcher_completed)
        self._subscribed = False

    async def _on_watcher_completed(self, event: Event) -> None:
        try:
            await self.originate(event.payload)
        except Exception:  # never let origination break the emitter
            logger.warning("Task origination failed", exc_info=True)

    # ── Core logic ────────────────────────────────────────────

    @staticmethod
    def is_actionable(finding: Any) -> bool:
        """A finding is actionable if explicitly flagged or high-severity."""
        if not isinstance(finding, dict):
            return False
        if finding.get("actionable") is True:
            return True
        return str(finding.get("severity", "")).lower() in ACTIONABLE_SEVERITIES

    def select_rule(
        self, watcher_name: str, finding: dict
    ) -> tuple[str, str] | None:
        """Resolve (agent_name, task_type) for a finding.

        A finding may pin its own ``agent_name`` + ``task_type``; otherwise
        the watcher-level pipeline rule applies. Returns None if neither
        yields a mapping.
        """
        agent = finding.get("agent_name")
        task_type = finding.get("task_type")
        if agent and task_type:
            return (agent, task_type)
        return self._rules.get(watcher_name)

    @staticmethod
    def fingerprint(
        tenant_id: str, watcher_name: str, agent_name: str, finding: dict
    ) -> str:
        """Stable id for a finding so re-runs don't spawn duplicates."""
        key = (
            finding.get("fingerprint")
            or finding.get("title")
            or str(finding.get("details", ""))
        )
        raw = f"{tenant_id}|{watcher_name}|{agent_name}|{key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def originate(self, payload: dict) -> list[dict]:
        """Spawn tasks for the actionable findings in a WATCHER_COMPLETED payload.

        Returns a list of ``{task_id, agent_name, project_id}`` for each task
        spawned. Enforces per-tenant and per-project WIP limits and skips
        findings that already have an open task (dedup).
        """
        tenant_id = payload.get("tenant_id")
        watcher_name = payload.get("watcher_name")
        findings = payload.get("findings") or []
        if not tenant_id or not watcher_name:
            return []

        actionable = [f for f in findings if self.is_actionable(f)]
        if not actionable:
            return []

        tenant_open = await self._open_task_count(tenant_id)
        spawned: list[dict] = []

        for finding in actionable:
            rule = self.select_rule(watcher_name, finding)
            if rule is None:
                continue
            agent_name, task_type = rule

            # Per-tenant WIP ceiling (count existing + spawned this run).
            if tenant_open + len(spawned) >= self._tenant_wip:
                logger.info(
                    "Tenant %s at WIP limit (%d) — deferring remaining findings",
                    tenant_id, self._tenant_wip,
                )
                break

            project_id = finding.get("project_id") or payload.get("project_id")
            if project_id is not None:
                proj_open = await self._open_task_count(
                    tenant_id, project_id=project_id
                )
                proj_spawned = sum(
                    1 for s in spawned if s.get("project_id") == project_id
                )
                if proj_open + proj_spawned >= self._project_wip:
                    logger.info(
                        "Project %s at WIP limit (%d) — skipping finding",
                        project_id, self._project_wip,
                    )
                    continue

            fp = self.fingerprint(tenant_id, watcher_name, agent_name, finding)
            if await self._has_open_task(tenant_id, fp):
                logger.debug(
                    "Open task already exists for finding %s — skip", fp[:12]
                )
                continue

            severity = str(finding.get("severity", "")).lower()
            input_data = {
                "origin": "watcher",
                "watcher_name": watcher_name,
                "task_type": task_type,
                "finding": finding,
                "fingerprint": fp,
            }
            result = await self._pm.spawn(
                tenant_id=tenant_id,
                agent_name=agent_name,
                input_data=input_data,
                task_name=f"{task_type}: {str(finding.get('title', ''))[:80]}",
                priority="high" if severity == "critical" else "normal",
            )
            spawned.append(
                {
                    "task_id": result.get("task_id"),
                    "agent_name": agent_name,
                    "project_id": project_id,
                }
            )

        if spawned:
            logger.info(
                "Originated %d task(s) from %s findings for tenant %s",
                len(spawned), watcher_name, tenant_id,
            )
        return spawned

    # ── DB access (overridden in unit tests) ──────────────────

    async def _open_task_count(
        self, tenant_id: str, project_id: Any = None
    ) -> int:
        """Count queued/running tasks for a tenant (optionally a project)."""
        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(AgentTask)
                .where(
                    AgentTask.tenant_id == tenant_id,
                    AgentTask.status.in_(_OPEN_STATUSES),
                )
            )
            if project_id is not None:
                stmt = stmt.where(AgentTask.project_id == project_id)
            result = await session.execute(stmt)
            return int(result.scalar() or 0)

    async def _has_open_task(self, tenant_id: str, fingerprint: str) -> bool:
        """True if an open task already carries this finding fingerprint."""
        async with self._session_factory() as session:
            stmt = (
                select(AgentTask.id)
                .where(
                    AgentTask.tenant_id == tenant_id,
                    AgentTask.status.in_(_OPEN_STATUSES),
                    AgentTask.input["fingerprint"].astext == fingerprint,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None
