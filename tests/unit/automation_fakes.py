"""In-memory fakes of the dev automation ports (services/dev/automation/ports.py).

``MemStore`` keeps the same rules the Postgres store gets from its constraints
(a key is inserted once per tenant, a scheduled slot / chain claim once, item
transitions are compare-and-set), so the runner's logic is tested against
them without a database.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from life_graph.services.dev.automation.ports import BacklogItem, ExecResult, ScheduleRun
from life_graph.services.dev.automation.settings import AutomationSettings

T = "raja"
PROJECT_ID = str(uuid.UUID(int=1))
PROJECT = {
    "id": PROJECT_ID,
    "name": "race-app",
    "path": "/repo/race-app",
    "is_active": True,
    "scan_metadata": {"base_branch": "main"},
}


def at(text: str) -> datetime:
    """``"2026-11-27T10:00"`` (UTC) → aware datetime."""
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


class MemStore:
    def __init__(self, doc: AutomationSettings | None = None) -> None:
        self.docs: dict[str, AutomationSettings] = {T: doc or AutomationSettings()}
        self.state: dict[str, dict] = {}
        self.items: dict[str, BacklogItem] = {}
        self.breakers: dict[tuple[str, str], Any] = {}
        self.runs: list[tuple[str, ScheduleRun]] = []
        self.polled: dict[str, tuple[datetime, str | None]] = {}
        self.clock = at("2026-11-27T00:00")

    # settings
    async def tenants(self) -> list[str]:
        return list(self.docs)

    async def get_settings(self, tenant_id: str) -> AutomationSettings:
        doc = copy.deepcopy(self.docs.get(tenant_id) or AutomationSettings())
        for s in doc.intake.sources:
            if s.id in self.polled:
                s.last_polled_at = self.polled[s.id][0].isoformat()
        return doc

    async def save_settings(self, tenant_id, doc, updated_by):
        self.docs[tenant_id] = copy.deepcopy(doc)
        return await self.get_settings(tenant_id)

    async def get_state(self, tenant_id):
        return dict(self.state.get(tenant_id, {}))

    async def claim_digest(self, tenant_id, date, window_end):
        st = self.state.setdefault(tenant_id, {})
        if st.get("digest_date") == date:
            return False
        st.update(digest_date=date, digest_to=window_end.isoformat())
        return True

    async def mark_polled(self, tenant_id, source_id, at_, error):
        self.polled[source_id] = (at_, error)

    # backlog
    def add(self, tenant_id=T, **fields) -> BacklogItem:
        item = BacklogItem(
            id=fields.pop("id", str(uuid.uuid4())),
            tenant_id=tenant_id,
            source_id=fields.pop("source_id", None),
            external_key=fields.pop("external_key", f"k:{uuid.uuid4()}"),
            title=fields.pop("title", "A thing to fix"),
            created_at=fields.pop("created_at", self.clock),
            **fields,
        )
        self.items[item.id] = item
        return item

    async def insert_item(self, tenant_id, source_id, c):
        if await self.has_key(tenant_id, c.external_key):
            return False
        self.clock = self.clock.replace(microsecond=(self.clock.microsecond + 1) % 1_000_000)
        self.add(
            tenant_id,
            source_id=source_id,
            external_key=c.external_key,
            title=c.title,
            body=c.body,
            url=c.url,
        )
        return True

    async def has_key(self, tenant_id, key):
        return any(i.tenant_id == tenant_id and i.external_key == key for i in self.items.values())

    async def has_open_title(self, tenant_id, source_id, title):
        return any(
            i.tenant_id == tenant_id
            and i.source_id == source_id
            and i.title == title
            and i.status in ("new", "queued", "running")
            for i in self.items.values()
        )

    async def get_item(self, tenant_id, item_id):
        item = self.items.get(item_id)
        return replace(item) if item and item.tenant_id == tenant_id else None

    async def list_items(self, tenant_id, status=None, limit=200):
        rows = [
            replace(i)
            for i in self.items.values()
            if i.tenant_id == tenant_id and (status is None or i.status == status)
        ]
        return rows[:limit]

    async def update_item(self, tenant_id, item_id, *, expect=None, **fields):
        item = self.items.get(item_id)
        if item is None or item.tenant_id != tenant_id:
            return None
        if expect and item.status not in expect:
            return None
        for k, v in fields.items():
            setattr(item, k, v)
        return replace(item)

    async def count_active(self, tenant_id):
        return sum(
            1
            for i in self.items.values()
            if i.tenant_id == tenant_id and i.status in ("queued", "running")
        )

    async def count_started_since(self, tenant_id, since):
        return sum(
            1
            for i in self.items.values()
            if i.tenant_id == tenant_id and i.started_at and i.started_at >= since
        )

    # breakers
    async def get_breaker(self, tenant_id, key):
        state = self.breakers.get((tenant_id, key))
        return copy.deepcopy(state)

    async def update_breaker(self, tenant_id, key, fn):
        prev = copy.deepcopy(self.breakers.get((tenant_id, key)))
        nxt = fn(prev)
        if nxt is None:
            return prev
        self.breakers[(tenant_id, key)] = copy.deepcopy(nxt)
        return nxt

    async def list_breakers(self, tenant_id):
        return [copy.deepcopy(v) for (t, _), v in self.breakers.items() if t == tenant_id]

    # runs
    async def claim_run(
        self,
        tenant_id,
        schedule_id,
        slot_date,
        trigger,
        outcome,
        *,
        predecessor_task_id=None,
        detail=None,
    ):
        for t, r in self.runs:
            if t != tenant_id or r.schedule_id != schedule_id or r.trigger != trigger:
                continue
            if trigger == "scheduled" and r.slot_date == slot_date:
                return None
            if trigger == "chain" and r.predecessor_task_id == predecessor_task_id:
                return None
        self.clock = self.clock.replace(microsecond=(self.clock.microsecond + 1) % 1_000_000)
        run = ScheduleRun(
            id=str(uuid.uuid4()),
            schedule_id=schedule_id,
            slot_date=slot_date,
            trigger=trigger,
            outcome=outcome,
            predecessor_task_id=predecessor_task_id,
            detail=detail,
            created_at=self.run_time or self.clock,
        )
        self.runs.append((tenant_id, run))
        return run.id

    run_time: datetime | None = None

    def _run(self, tenant_id, run_id):
        return next((r for t, r in self.runs if t == tenant_id and r.id == run_id), None)

    async def finish_run(self, tenant_id, run_id, outcome, task_id, detail):
        run = self._run(tenant_id, run_id)
        if run:
            run.outcome, run.task_id, run.detail = outcome, task_id, detail

    async def release_run(self, tenant_id, run_id):
        self.runs = [(t, r) for t, r in self.runs if not (t == tenant_id and r.id == run_id)]

    async def has_slot(self, tenant_id, schedule_id, slot_date):
        return any(
            t == tenant_id
            and r.schedule_id == schedule_id
            and r.slot_date == slot_date
            and r.trigger == "scheduled"
            for t, r in self.runs
        )

    async def has_chain_claim(self, tenant_id, schedule_id, predecessor_task_id):
        return any(
            t == tenant_id
            and r.schedule_id == schedule_id
            and r.trigger == "chain"
            and r.predecessor_task_id == predecessor_task_id
            for t, r in self.runs
        )

    async def latest_run_with_task(self, tenant_id, schedule_id):
        runs = [
            r for t, r in self.runs if t == tenant_id and r.schedule_id == schedule_id and r.task_id
        ]
        return replace(runs[-1]) if runs else None

    async def list_runs(self, tenant_id, schedule_id, limit=50):
        return [
            r for t, r in reversed(self.runs) if t == tenant_id and r.schedule_id == schedule_id
        ][:limit]


class FakeTasks:
    """Dev tasks in a dict: ``views[task_id]`` is what tasks.serialize would return."""

    def __init__(self) -> None:
        self.projects = {PROJECT_ID: dict(PROJECT)}
        self.personas = {"code-fixer-local": "local", "code-fixer": "claude_code"}
        self.created: list[dict[str, Any]] = []
        self.cancelled: list[str] = []
        self.task_views: dict[str, dict[str, Any]] = {}
        self.fail_create: str | None = None

    async def project(self, tenant_id, project_id):
        return self.projects.get(project_id)

    async def persona_driver(self, tenant_id, persona):
        return self.personas.get(persona)

    async def create(
        self, tenant_id, *, project, instruction, persona, mode, start_now, properties
    ):
        if self.fail_create:
            raise RuntimeError(self.fail_create)
        task_id = str(uuid.uuid4())
        record = {
            "id": task_id,
            "tenant_id": tenant_id,
            "project": project["id"],
            "instruction": instruction,
            "persona": persona,
            "mode": mode,
            "start_now": start_now,
            "properties": properties,
        }
        self.created.append(record)
        self.task_views[task_id] = {"id": task_id, "status": "queued", "stage": "queued"}
        return {"id": task_id, "status": "queued"}

    def set(self, task_id, status, stage=None, **extra):
        self.task_views[task_id] = {
            "id": task_id,
            "status": status,
            "stage": stage or status,
            **extra,
        }

    async def cancel(self, tenant_id, task_id):
        self.cancelled.append(task_id)
        self.set(task_id, "cancelled")
        return {"id": task_id, "status": "cancelled"}

    async def views(self, tenant_id, task_ids):
        return {t: dict(self.task_views[t]) for t in task_ids if t in self.task_views}


class FakeGate:
    def __init__(self) -> None:
        self.is_paused = False
        self.reasons: list[str] = []
        self.asked: list[str | None] = []

    async def paused(self, tenant_id):
        return self.is_paused

    async def blockers(self, tenant_id, driver):
        self.asked.append(driver)
        return ["Autonomy is paused (kill switch)."] if self.is_paused else list(self.reasons)


class FakeNotifier:
    def __init__(self) -> None:
        self.notices: list[dict[str, Any]] = []

    async def publish(self, tenant_id, *, kind, title, body, data=None):
        self.notices.append(
            {"tenant_id": tenant_id, "kind": kind, "title": title, "body": body, **(data or {})}
        )


def _subsequence(words, argv) -> bool:
    it = iter(argv)
    return all(any(w == a for a in it) for w in words)


class FakeExec:
    """Answers a command by the longest registered word sequence it contains, in order."""

    def __init__(self, responses: dict[tuple, ExecResult] | None = None) -> None:
        self.responses = dict(responses or {})
        self.calls: list[list[str]] = []

    def on(self, *prefix: str, code: int = 0, stdout: str = "", stderr: str = "") -> FakeExec:
        self.responses[tuple(prefix)] = ExecResult(code=code, stdout=stdout, stderr=stderr)
        return self

    async def __call__(self, argv, *, cwd=None, timeout=30.0):
        self.calls.append(list(argv))
        best = None
        for words, result in self.responses.items():
            if _subsequence(words, argv) and (best is None or len(words) > len(best[0])):
                best = (words, result)
        if best is None:
            return ExecResult(code=127, stderr=f"unexpected command: {' '.join(argv)}")
        return best[1]

    def ran(self, *words: str) -> list[list[str]]:
        return [c for c in self.calls if all(w in c for w in words)]


class FakeIntentions:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])

    async def active(self, tenant_id):
        return [r for r in self.rows if r.get("status") in ("pending", "triggered")]
