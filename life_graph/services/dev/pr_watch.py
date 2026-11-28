"""PR feedback loop: hand a PR's failing checks, reviews and conflicts back to its task.

docs/specs/agent-drivers.md, "Phase 4b". Off by default
(``driver_pr_feedback_enabled``). It watches dev tasks whose pull request is
open (stage ``pr_open`` / ``awaiting_merge``) and whose worktree and CLI
session were kept for ``continue_task`` (``driver_continue_enabled``, Phase 3b
part 2). Every ``driver_pr_feedback_poll_minutes`` (ARQ cron
``poll_pr_feedback``, or ``POST /kernel/drivers/pr-watch/poll``) it reads the
PR with ``gh`` -- read only: ``gh pr view``, ``gh api .../pulls/<n>/comments``,
``gh run view --log-failed`` -- and turns what is new (failing checks on the
head commit with their failed-step log tail, review comments inline and in
review bodies except Life Graph's own, a ``CONFLICTING`` merge state) into
**one** feedback message for ``continue_task``. The task then runs in its own
session and worktree, lands on its branch, and files an "Update PR" approval:
nothing is pushed until the owner approves.

* One round in flight per PR: ``feeding_back`` until the continued task has
  finished and its update approval was decided (approving pushes it).
* ``max_rounds`` per PR; one more round of feedback after that turns the
  watch to ``needs_you`` with one notification.
* Merged or closed stops the watch; a missing worktree or session stops it
  with the reason; the owner can stop it (``POST .../pr-watch/{task}/stop``).
* The dedupe keys (``seen``) and rounds live in ``pr_watches`` (066), so a
  restart never sends the same feedback twice.
* Before each round: the kill switch, the subscription share and the
  Governor (services/dev/automation_gate.py); a refusal waits and says why.

Rebuilt from race-app's ``automation/pr-watch/watcher.ts`` (the owner's code).
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.models.db import AgentTask, Approval, PrWatch
from life_graph.services.dev import pr_feedback_signals as sig
from life_graph.services.dev import task_events
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev.automation_gate import blockers
from life_graph.services.dev.continuation import ContinueError, continue_task
from life_graph.services.dev.github_pr import _run as gh_run

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

ACTIVE_STATES = ("watching", "feeding_back")
_BUSY = frozenset({"queued", "running", "parked"})
_WATCH_STAGES = frozenset({"pr_open", "awaiting_merge"})
MAX_LOG_CHECKS = 3


@dataclass(frozen=True)
class PrFeedbackSettings:
    """The loop's switches (env ``LIFE_GRAPH_DRIVER_PR_FEEDBACK_*``)."""

    enabled: bool
    poll_minutes: int
    max_rounds: int
    on_failing_checks: bool
    on_review_comments: bool
    on_conflicts: bool

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def current_settings() -> PrFeedbackSettings:
    """The settings as configured now."""
    return PrFeedbackSettings(
        enabled=bool(settings.driver_pr_feedback_enabled),
        poll_minutes=max(1, int(settings.driver_pr_feedback_poll_minutes)),
        max_rounds=max(0, int(settings.driver_pr_feedback_max_rounds)),
        on_failing_checks=bool(settings.driver_pr_feedback_on_failing_checks),
        on_review_comments=bool(settings.driver_pr_feedback_on_review_comments),
        on_conflicts=bool(settings.driver_pr_feedback_on_conflicts),
    )


class GhReader(Protocol):
    """The three read-only gh calls the loop makes."""

    async def pr_view(self, url: str, cwd: str | None) -> dict: ...

    async def inline_comments(self, repo: str, number: int, cwd: str | None) -> list: ...

    async def failed_log(self, run_id: str, repo: str, cwd: str | None) -> str | None: ...


PR_VIEW_FIELDS = "state,mergeable,headRefOid,statusCheckRollup,reviews,comments"


class CliGh:
    """:class:`GhReader` over the ``gh`` CLI (argv only, never a shell)."""

    async def _gh(self, args: list[str], cwd: str | None) -> str:
        code, out, err = await gh_run([settings.driver_gh_bin, *args], cwd=cwd)
        if code != 0:
            raise RuntimeError(f"gh {args[0]} {args[1] if len(args) > 1 else ''} failed: "
                               f"{(err or out)[-200:]}")  # fmt: skip
        return out

    async def pr_view(self, url: str, cwd: str | None) -> dict:
        out = await self._gh(["pr", "view", url, "--json", PR_VIEW_FIELDS], cwd)
        return json.loads(out or "{}")

    async def inline_comments(self, repo: str, number: int, cwd: str | None) -> list:
        out = await self._gh(["api", f"repos/{repo}/pulls/{number}/comments?per_page=100"], cwd)
        data = json.loads(out or "[]")
        return data if isinstance(data, list) else []

    async def failed_log(self, run_id: str, repo: str, cwd: str | None) -> str | None:
        try:
            out = await self._gh(["run", "view", run_id, "--repo", repo, "--log-failed"], cwd)
        except Exception:  # best-effort: the check is still reported, without its log
            return None
        return sig.log_tail(out) if out.strip() else None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _pr_approval(approvals: list[Approval]) -> Approval | None:
    """The task's newest driver_pr approval that opened a PR."""

    with_url = [a for a in approvals if a.kind == "driver_pr" and (a.payload or {}).get("pr_url")]
    return max(with_url, key=dev_tasks._created_key) if with_url else None


def _kept_worktree(task: AgentTask) -> dict | None:
    record = (task.properties or {}).get("continuation")
    if not isinstance(record, dict) or not record.get("session_id"):
        return None
    worktree = record.get("worktree")
    return record if worktree and Path(worktree).is_dir() else None


def view(row: PrWatch) -> dict[str, Any]:
    """A watch as the API shows it (no paths)."""
    return {
        "task_id": str(row.task_id),
        "pr_url": row.pr_url,
        "state": row.state,
        "rounds": row.rounds,
        "max_rounds": current_settings().max_rounds,
        "seen": len(row.seen or []),
        "since": row.since.isoformat() if row.since else None,
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "last_feedback": row.last_feedback,
        "last_error": row.last_error,
        "notified_at": row.notified_at.isoformat() if row.notified_at else None,
    }


async def discover(
    session: AsyncSession, *, now: datetime, tenant_id: str | None = None
) -> list[str]:
    """Start watching every task with an open PR and a kept worktree; the new task ids."""

    where = [
        dev_tasks._kind_filter(),
        AgentTask.status == "completed",
        AgentTask.properties.has_key("continuation"),
    ]
    if tenant_id is not None:
        where.append(AgentTask.tenant_id == tenant_id)
    tasks = (await session.execute(select(AgentTask).where(*where).limit(500))).scalars().all()
    if not tasks:
        return []
    by_tenant: dict[str, list[AgentTask]] = {}
    for t in tasks:
        by_tenant.setdefault(t.tenant_id, []).append(t)
    created: list[str] = []
    for tenant, rows in by_tenant.items():
        ids = [r.id for r in rows]
        watched = set(
            (
                await session.execute(
                    select(PrWatch.task_id).where(
                        PrWatch.tenant_id == tenant, PrWatch.task_id.in_(ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        approvals = await dev_tasks._approvals_by_task(session, tenant, [str(i) for i in ids])
        for task in rows:
            if task.id in watched or _kept_worktree(task) is None:
                continue
            mine = approvals.get(str(task.id), [])
            pr = _pr_approval(mine)
            if pr is None or dev_tasks._stage(task, mine) not in _WATCH_STAGES:
                continue
            since = _aware(pr.resolved_at) or _aware(task.completed_at) or now
            await session.execute(
                pg_insert(PrWatch)
                .values(
                    id=uuid.uuid4(),
                    tenant_id=tenant,
                    task_id=task.id,
                    pr_url=str(pr.payload["pr_url"])[:300],
                    state="watching",
                    rounds=0,
                    seen=[],
                    since=since,
                    properties={},
                    created_at=now,
                    updated_at=now,
                )  # fmt: skip
                .on_conflict_do_nothing(constraint="uq_pr_watches_task")
            )
            created.append(str(task.id))
    return created


async def _notify_needs_you(row: PrWatch, reason: str) -> None:

    try:
        await event_bus.emit(
            EventType.APPROVAL_FILED,
            {
                "tenant_id": row.tenant_id,
                "kind": "pr_feedback",
                "title": "A pull request needs you",
                "detail": f"{row.pr_url} -- {reason}",
                "task_id": str(row.task_id),
            },
            source="pr_watch",
        )
    except Exception:
        logger.warning("Could not send the PR-feedback notification", exc_info=True)


async def _emit(name: str, payload: dict[str, Any]) -> None:

    await dev_tasks._emit_bus(name, payload)


def _timeline(row: PrWatch, text: str, data: dict | None = None) -> None:

    task_events.emit(
        row.tenant_id, str(row.task_id), "pr_watch", text, data=data, source="pr_watch"
    )


async def _needs_you(row: PrWatch, reason: str, now: datetime) -> None:
    row.state = "needs_you"
    row.last_feedback = reason[:300]
    _timeline(row, f"PR feedback stopped: {reason}"[:200], {"state": "needs_you"})
    await _emit(
        "PR_WATCH_NEEDS_YOU",
        {"tenant_id": row.tenant_id, "task_id": str(row.task_id), "reason": reason[:300]},
    )
    if row.notified_at is None:
        row.notified_at = now
        await _notify_needs_you(row, reason)


async def _stop(row: PrWatch, state: str, reason: str | None = None) -> None:
    row.state = state
    if reason:
        row.last_error = reason[:300]
    _timeline(row, f"PR feedback stopped ({state})", {"state": state, "reason": reason})
    await _emit(
        "PR_WATCH_STOPPED",
        {"tenant_id": row.tenant_id, "task_id": str(row.task_id), "state": state,
         "reason": reason},
    )  # fmt: skip


@dataclass
class _Round:
    """What one check carries between its steps."""

    session_factory: Any
    settings: PrFeedbackSettings
    gh: GhReader
    now: datetime
    continue_fn: Any
    gate: Any


def _in_flight(row: PrWatch, task: AgentTask, stage: str) -> str | None:
    """The outcome when no round may start now (``None`` = go on); may reset the row."""
    if row.state == "feeding_back":
        if task.status in _BUSY or stage == "awaiting_pr":
            return "in_flight"  # the round runs, or its update awaits the owner
        if task.status != "completed":
            return "round_failed"
        row.state = "watching"
        return "round_done"  # the round's push may already have new results
    if task.status != "completed" or stage == "awaiting_pr":
        return "in_flight"
    return None


async def _read(
    rnd: _Round, row: PrWatch, task: AgentTask
) -> tuple[str | None, sig.Snapshot | None, tuple[str, int] | None]:
    """Read the PR: ``(outcome if it ends here, snapshot, (repo, number))``."""
    ref = sig.parse_pr_url(row.pr_url)
    if ref is None:
        await _stop(row, "stopped", "Not a GitHub pull request URL.")
        return "stopped", None, None
    repo, number = ref
    cwd = ((task.properties or {}).get("continuation") or {}).get("origin") or None
    snapshot = sig.parse_pr_view(await rnd.gh.pr_view(row.pr_url, cwd))
    if rnd.settings.on_review_comments and snapshot.state == "OPEN":
        snapshot.comments.extend(
            sig.parse_inline_comments(await rnd.gh.inline_comments(repo, number, cwd))
        )
    row.last_checked_at = rnd.now
    row.last_error = None
    if snapshot.state != "OPEN":
        await _stop(row, "merged" if snapshot.state == "MERGED" else "closed")
        return row.state, snapshot, ref
    return None, snapshot, ref


async def _hand_back(
    rnd: _Round,
    row: PrWatch,
    task: AgentTask,
    approvals: list[Approval],
    snapshot: sig.Snapshot,
    signals: sig.Signals,
    repo: str,
) -> str:
    """Gate the round, build the one message and give it to ``continue_task``."""

    short = sig.summarize(signals)
    record = (task.properties or {}).get("continuation") or {}
    if _kept_worktree(task) is None:
        row.last_feedback = short
        await _stop(row, "stopped", "The task's worktree or session is gone.")
        return "stopped"
    if row.rounds >= rnd.settings.max_rounds:
        plural = "" if row.rounds == 1 else "s"
        await _needs_you(row, f"still {short} after {row.rounds} feedback round{plural}.", rnd.now)
        return "needs_you"
    reasons = await rnd.gate(
        row.tenant_id, driver=record.get("driver"), account_id=record.get("account_id")
    )
    if reasons:
        row.last_error = f"Waiting: {' '.join(reasons)}"[:300]
        return "blocked"
    logs: dict[str, str] = {}
    for check in [c for c in signals.checks if c.run_id][:MAX_LOG_CHECKS]:
        text = await rnd.gh.failed_log(str(check.run_id), repo, record.get("origin") or None)
        if text:
            logs[check.name] = text
    pr = _pr_approval(approvals)
    base = ((pr.payload or {}).get("base_branch") if pr is not None else None) or "main"
    feedback = sig.build_feedback(
        pr_url=row.pr_url, head_sha=snapshot.head_sha, base_branch=base, signals=signals,
        logs=logs,
    )  # fmt: skip
    # The watch row stays locked across the hand-over, so a second poll cannot
    # send the same round; continue_task locks only the task row.
    try:
        await rnd.continue_fn(
            rnd.session_factory, row.tenant_id, str(task.id), feedback,
            f"pr_feedback: {short}"[:200],
        )  # fmt: skip
    except ContinueError as exc:
        if exc.code == "busy":
            return "in_flight"
        if exc.code == "paused":
            row.last_error = f"Waiting: {exc}"[:300]
            return "blocked"
        await _stop(row, "stopped", f"{exc.code}: {exc}")
        return "stopped"
    row.state = "feeding_back"
    row.rounds = int(row.rounds or 0) + 1
    row.last_feedback = short
    row.seen = [*(row.seen or []), *signals.keys]
    _timeline(row, f"PR feedback round {row.rounds}: {short}"[:200], {"round": row.rounds})
    await _emit(
        "PR_WATCH_FEEDBACK",
        {"tenant_id": row.tenant_id, "task_id": str(task.id), "round": row.rounds,
         "summary": short, "pr_url": row.pr_url},
    )  # fmt: skip
    return "sent"


async def _check(rnd: _Round, session: AsyncSession, row: PrWatch, force: bool) -> str:

    task = (
        await session.execute(
            select(AgentTask).where(
                AgentTask.id == row.task_id,
                AgentTask.tenant_id == row.tenant_id,
                dev_tasks._kind_filter(),
            )
        )
    ).scalar_one_or_none()
    if task is None:
        await _stop(row, "stopped", "The task no longer exists.")
        return "stopped"
    approvals = (await dev_tasks._approvals_by_task(session, row.tenant_id, [str(task.id)])).get(
        str(task.id), []
    )
    held = _in_flight(row, task, dev_tasks._stage(task, approvals))
    if held == "round_failed":
        await _needs_you(row, f"the feedback round ended {task.status}.", rnd.now)
        return "needs_you"
    if held == "round_done":
        force = True
    elif held is not None:
        return held
    last = _aware(row.last_checked_at)
    if (
        not force
        and last is not None
        and rnd.now - last < timedelta(minutes=rnd.settings.poll_minutes)
    ):
        return "not_due"
    ended, snapshot, ref = await _read(rnd, row, task)
    if ended is not None or snapshot is None or ref is None:
        return ended or "stopped"
    signals = sig.new_signals(
        snapshot,
        set(row.seen or []),
        _aware(row.since),
        on_checks=rnd.settings.on_failing_checks,
        on_comments=rnd.settings.on_review_comments,
        on_conflicts=rnd.settings.on_conflicts,
    )
    if not signals.any():
        return "quiet"
    return await _hand_back(rnd, row, task, approvals, snapshot, signals, ref[0])


async def check_one(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str,
    watch_id: Any,
    s: PrFeedbackSettings,
    *,
    force: bool,
    gh: GhReader,
    now: datetime,
    continue_fn,
    gate,
) -> str:
    """Check one watched PR; what happened (``sent``, ``in_flight``, ``quiet``, ...).

    The watch row is locked (``SKIP LOCKED``) for the whole check, so an API
    poll and the cron never handle the same PR at once.
    """
    rnd = _Round(session_factory, s, gh, now, continue_fn, gate)
    async with session_factory() as session:
        row = (
            await session.execute(
                select(PrWatch)
                .where(PrWatch.id == watch_id, PrWatch.tenant_id == tenant_id)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if row is None or row.state not in ACTIVE_STATES:
            return "skipped"
        outcome = await _check(rnd, session, row, force)
        await session.commit()
        return outcome


async def poll(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    force: bool = False,
    tenant_id: str | None = None,
    gh: GhReader | None = None,
    now: datetime | None = None,
    continue_fn=None,
    gate=None,
) -> dict[str, Any]:
    """Discover new watches, then check every active one that is due (all with *force*)."""
    s = current_settings()
    if not s.enabled:
        return {"enabled": False, "checked": 0, "outcomes": {}}
    continue_fn = continue_fn or continue_task
    gate = gate or blockers
    gh = gh or CliGh()
    now = now or datetime.now(UTC)
    async with session_factory() as session:
        new = await discover(session, now=now, tenant_id=tenant_id)
        await session.commit()
        where = [PrWatch.state.in_(ACTIVE_STATES)]
        if tenant_id is not None:
            where.append(PrWatch.tenant_id == tenant_id)
        # Install-wide for the cron (tenant_id None); each row keeps its tenant.
        rows = (
            await session.execute(select(PrWatch.id, PrWatch.tenant_id).where(*where).limit(200))
        ).all()
    outcomes: dict[str, int] = {}
    for watch_id, watch_tenant in rows:
        try:
            outcome = await check_one(
                session_factory, watch_tenant, watch_id, s, force=force, gh=gh, now=now,
                continue_fn=continue_fn, gate=gate,
            )  # fmt: skip
        except Exception as exc:
            logger.warning("PR watch %s failed", watch_id, exc_info=True)
            outcome = "error"
            await _record_error(session_factory, watch_tenant, watch_id, str(exc), now)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    checked = sum(n for k, n in outcomes.items() if k not in ("skipped", "not_due", "in_flight"))
    return {"enabled": True, "discovered": len(new), "checked": checked, "outcomes": outcomes}


async def _record_error(
    session_factory, tenant_id: str, watch_id: Any, message: str, now: datetime
) -> None:
    try:
        async with session_factory() as session:
            row = (
                await session.execute(
                    select(PrWatch).where(PrWatch.id == watch_id, PrWatch.tenant_id == tenant_id)
                )
            ).scalar_one_or_none()
            if row is not None:
                row.last_checked_at = now
                row.last_error = message[:300]
                await session.commit()
    except Exception:  # best-effort: the next poll records it again
        logger.debug("Could not record the PR-watch error", exc_info=True)


async def list_watches(session: AsyncSession, tenant_id: str) -> list[dict[str, Any]]:
    """This tenant's watched PRs, newest first."""
    rows = (
        (
            await session.execute(
                select(PrWatch)
                .where(PrWatch.tenant_id == tenant_id)
                .order_by(PrWatch.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return [view(r) for r in rows]


async def stop_watch(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str, task_id: str
) -> dict[str, Any] | None:
    """The owner stops watching a task's PR; None when it is not watched."""
    try:
        pk = uuid.UUID(str(task_id))
    except ValueError:
        return None
    async with session_factory() as session:
        row = (
            await session.execute(
                select(PrWatch)
                .where(PrWatch.tenant_id == tenant_id, PrWatch.task_id == pk)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        if row.state in ACTIVE_STATES or row.state == "needs_you":
            await _stop(row, "stopped", "Stopped by the owner.")
        await session.commit()
        return view(row)
