"""What the automation needs from the rest of the system, as small interfaces.

The intake runner, the scheduler, the breaker and the digest are written
against these, so their rules are unit-tested with in-memory fakes; the real
implementations are ``store.SqlStore`` (Postgres), ``wiring`` (dev tasks,
the start gate, notices, ``gh``/``git``, intentions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from life_graph.services.dev.automation.breaker import BreakerState
    from life_graph.services.dev.automation.settings import AutomationSettings


@dataclass
class Candidate:
    """What a source poll yields; new keys become backlog items."""

    external_key: str
    title: str
    body: str | None = None
    url: str | None = None


@dataclass
class BacklogItem:
    id: str
    tenant_id: str
    source_id: str | None
    external_key: str
    title: str
    body: str | None = None
    url: str | None = None
    status: str = "new"
    task_id: str | None = None
    reason: str | None = None
    started_at: datetime | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def dump(self) -> dict[str, Any]:
        """The API shape (race-app ``BacklogItem``)."""
        return {
            "id": self.id,
            "sourceId": self.source_id,
            "externalKey": self.external_key,
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "status": self.status,
            "taskId": self.task_id,
            "reason": self.reason,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "startedBy": self.properties.get("started_by"),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class ScheduleRun:
    id: str
    schedule_id: str
    slot_date: str
    trigger: str  # scheduled | chain | manual
    outcome: str
    task_id: str | None = None
    predecessor_task_id: str | None = None
    detail: str | None = None
    created_at: datetime | None = None

    def dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "jobId": self.schedule_id,
            "date": self.slot_date,
            "trigger": self.trigger,
            "outcome": self.outcome,
            "taskId": self.task_id,
            "afterTaskId": self.predecessor_task_id,
            "detail": self.detail,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Store(Protocol):
    """Persistence, every call tenant-scoped."""

    async def tenants(self) -> list[str]: ...
    async def get_settings(self, tenant_id: str) -> AutomationSettings: ...
    async def save_settings(
        self, tenant_id: str, doc: AutomationSettings, updated_by: str | None
    ) -> AutomationSettings: ...
    async def get_state(self, tenant_id: str) -> dict[str, Any]: ...
    async def claim_digest(self, tenant_id: str, date: str, window_end: datetime) -> bool: ...
    async def mark_polled(
        self, tenant_id: str, source_id: str, at: datetime, error: str | None
    ) -> None: ...

    async def insert_item(self, tenant_id: str, source_id: str, c: Candidate) -> bool: ...
    async def has_key(self, tenant_id: str, external_key: str) -> bool: ...
    async def has_open_title(self, tenant_id: str, source_id: str, title: str) -> bool: ...
    async def get_item(self, tenant_id: str, item_id: str) -> BacklogItem | None: ...
    async def list_items(
        self, tenant_id: str, status: str | None = None, limit: int = 200
    ) -> list[BacklogItem]: ...
    async def update_item(
        self,
        tenant_id: str,
        item_id: str,
        *,
        expect: tuple[str, ...] | None = None,
        **fields: Any,
    ) -> BacklogItem | None: ...
    async def count_active(self, tenant_id: str) -> int: ...
    async def count_started_since(self, tenant_id: str, since: datetime) -> int: ...

    async def get_breaker(self, tenant_id: str, key: str) -> BreakerState | None: ...
    async def update_breaker(
        self,
        tenant_id: str,
        key: str,
        fn: Callable[[BreakerState | None], BreakerState | None],
    ) -> BreakerState | None: ...
    async def list_breakers(self, tenant_id: str) -> list[BreakerState]: ...

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
    ) -> str | None: ...
    async def finish_run(
        self,
        tenant_id: str,
        run_id: str,
        outcome: str,
        task_id: str | None,
        detail: str | None,
    ) -> None: ...
    async def release_run(self, tenant_id: str, run_id: str) -> None: ...
    async def has_slot(self, tenant_id: str, schedule_id: str, slot_date: str) -> bool: ...
    async def has_chain_claim(
        self, tenant_id: str, schedule_id: str, predecessor_task_id: str
    ) -> bool: ...
    async def latest_run_with_task(
        self, tenant_id: str, schedule_id: str
    ) -> ScheduleRun | None: ...
    async def list_runs(
        self, tenant_id: str, schedule_id: str, limit: int = 50
    ) -> list[ScheduleRun]: ...


class Tasks(Protocol):
    """Dev tasks, projects and personas (services/dev/tasks.py and the registries)."""

    async def project(self, tenant_id: str, project_id: str) -> dict[str, Any] | None: ...
    async def persona_driver(self, tenant_id: str, persona: str) -> str | None: ...
    async def create(
        self,
        tenant_id: str,
        *,
        project: dict[str, Any],
        instruction: str,
        persona: str,
        mode: str,
        start_now: bool,
        properties: dict[str, Any],
    ) -> dict[str, Any]: ...
    async def cancel(self, tenant_id: str, task_id: str) -> dict[str, Any] | None: ...
    async def views(self, tenant_id: str, task_ids: list[str]) -> dict[str, dict[str, Any]]: ...


class Gate(Protocol):
    """May automated work start now? (kill switch, Governor, subscription share)."""

    async def paused(self, tenant_id: str) -> bool: ...
    async def blockers(self, tenant_id: str, driver: str | None) -> list[str]: ...


class Notifier(Protocol):
    async def publish(
        self,
        tenant_id: str,
        *,
        kind: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> None: ...


@dataclass
class ExecResult:
    code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class Exec(Protocol):
    async def __call__(
        self, argv: list[str], *, cwd: str | None = None, timeout: float = 30.0
    ) -> ExecResult: ...


class Intentions(Protocol):
    """The tenant's active intentions, read natively (no HTTP hop)."""

    async def active(self, tenant_id: str) -> list[dict[str, Any]]: ...
