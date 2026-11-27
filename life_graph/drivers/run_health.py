"""Run health inside a dispatch (Phase 3b part 2, owner decision D2).

A mixin: ``TaskDispatcher`` inherits these and provides ``_emit``,
``_emit_steps``, ``_round_allowed``, ``_check_worktree_link``,
``_observe_files_changed`` and ``_persist_task_props``.

Every driver call of a dispatch goes through :meth:`RunHealthMixin._drive`.
With the defaults (agent accounts off, ``max_stall_retries`` 0) that is the one
``driver.dispatch`` call it always was. What it may add, each one **bounded**,
**gated** (kill switch, per-task cost cap, Governor -- ``_round_allowed``,
checked before every extra call) and **recorded** as its own attempt (the
next ``run.next_attempt``: steps, a task event of kind ``round`` and an
EventBus event), never approving anything:

* **Re-dispatch on a rate limit** -- the run failed ``rate_limited`` and the
  account hook named a next account (``metadata.account.next.id``): run once
  more in the same worktree, pinned to that account, with "continue the
  interrupted work" and a hand-off note (the last agent messages, at most
  1500 characters). At most one attempt per account per task; never on an
  auth or other failure. Sessions live in an account's home, so this is a new
  session, not a resume.
* **Stall retry** (``max_stall_retries``) -- the driver timed out: wait 10 s x 2^n
  (at most 5 min), then resume the session (or re-dispatch when there is none)
  with "your previous run stopped responding".
* **Nudge** (``max_nudges``, :meth:`_nudge_until_changed`) -- an edit run changed
  no file and only described a plan or asked a question: one continuation turn
  "carry it out now" per nudge, before Step 4c fails the task.
* **Park** (``wait_for_reset``, :func:`park_decision`) -- still rate limited with
  no account left: the result carries ``metadata.park = {resume_at, reason}``
  and services/dev/tasks.py parks the task instead of failing it.

Subscription budget (risk D4): a run on a subscription *account* books no
dollars with the Governor (:meth:`_book_spend`); its unattended runs are gated
on plan-window share by the account hook instead. Without an account every
run books exactly as before.

Rebuilt from race-app's ``providers/local/run-health.ts`` (the owner's code).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.core.budget import BudgetCategory
from life_graph.core.events import EventType
from life_graph.drivers import accounts_hook
from life_graph.drivers.workdir import worktree_intact
from life_graph.services.agent_accounts.catalog import DRIVERS
from life_graph.services.dev import task_events
from life_graph.services.governor import governor

if TYPE_CHECKING:
    from life_graph.drivers.base import ContextPacket, DriverResult
    from life_graph.drivers.dispatcher import _DispatchRun

logger = logging.getLogger(__name__)

CONTINUE_AFTER_RATE_LIMIT = (
    "A previous attempt at this task was interrupted by a rate limit. Inspect the current "
    "changes in this working tree and continue the task from there; do not start over."
)
NUDGE_PLAN_TEXT = (
    "You described the plan but changed no files. Carry it out now; don't ask for confirmation."
)
STALL_TEXT = (
    "Your previous run stopped responding. Continue from the current state of the worktree."
)
HANDOFF_NOTE_MAX = 1500
STALL_BASE_SECONDS = 10.0
STALL_CAP_SECONDS = 300.0
#: A parked task resumes this long after the reset, so the window has really rolled.
PARK_GRACE = timedelta(seconds=60)

# A numbered or bulleted line: what a plan-only answer is made of.
_LIST_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+\S")

# Patched by tests: the stall backoff must not really sleep there.
_sleep = asyncio.sleep


# ── Pure helpers ─────────────────────────────────────────────


def classify_empty_turn(texts: list[str]) -> str:
    """``plan_only`` (listed steps or asked a question) or ``empty`` (anything else)."""
    lines = "\n".join(t for t in texts if t).split("\n")
    items = sum(1 for line in lines if _LIST_LINE.match(line))
    asks = any(line.strip().endswith("?") or re.search(r"\?\s+\S", line) for line in lines)
    return "plan_only" if items >= 2 or asks else "empty"


def stall_delay(n: int) -> float:
    """Seconds before stall retry *n* (0-based): 10 s x 2^n, at most 5 min."""
    return min(STALL_BASE_SECONDS * (2 ** max(0, n)), STALL_CAP_SECONDS)


def handoff_note(texts: list[str]) -> str:
    """The last agent messages, newest kept, at most :data:`HANDOFF_NOTE_MAX` characters."""
    joined = "\n".join(t.strip() for t in texts if t and t.strip())
    if len(joined) <= HANDOFF_NOTE_MAX:
        return joined
    return "…" + joined[-(HANDOFF_NOTE_MAX - 1) :]


def agent_texts(result: DriverResult) -> list[str]:
    """What the agent said in a run: its ``text`` steps, else the final output."""
    steps = (result.metadata or {}).get("steps") or []
    texts = [
        str(s.get("content") or "")
        for s in steps
        if isinstance(s, dict) and s.get("kind") == "text" and s.get("content")
    ]
    return texts or ([result.output] if result.output else [])


def continue_prompt(instruction: str, note: str) -> str:
    """The prompt for the next account after a rate limit."""
    parts = [CONTINUE_AFTER_RATE_LIMIT]
    if note:
        parts.append(f"Hand-off note -- the previous attempt's last messages:\n{note}")
    parts.append(f"The task:\n{instruction}")
    return "\n\n".join(parts)


def _failure(result: DriverResult) -> dict:
    failure = (result.metadata or {}).get("failure")
    return failure if isinstance(failure, dict) else {}


def rate_limited(result: DriverResult) -> bool:
    return not result.success and _failure(result).get("kind") == "rate_limited"


def next_account(result: DriverResult) -> dict | None:
    """The account the hook named for a retry (``{id, name, kind}``), or None."""
    account = (result.metadata or {}).get("account")
    nxt = account.get("next") if isinstance(account, dict) else None
    return nxt if isinstance(nxt, dict) and nxt.get("id") else None


def timed_out(result: DriverResult) -> bool:
    return not result.success and (result.metadata or {}).get("exit_status") == "timeout"


def subscription_run(result: DriverResult | None) -> bool:
    """A run on a subscription *account* (risk D4: no dollars to book)."""
    md = (result.metadata or {}) if result is not None else {}
    return isinstance(md.get("account"), dict) and md.get("billing") == "subscription"


def _when(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _iso(when: datetime) -> str:
    return when.astimezone(UTC).isoformat().replace("+00:00", "Z")


def park_decision(
    result: DriverResult, *, now: datetime | None = None, default_minutes: int = 15
) -> dict | None:
    """``{resume_at, reason, resets_at}`` for a rate-limited result, else None.

    ``resume_at`` = the earliest time any account (or the CLI's own limit)
    frees up, plus :data:`PARK_GRACE`; never in the past.
    """
    if not rate_limited(result):
        return None
    now = now or datetime.now(UTC)
    md = result.metadata or {}
    failure = _failure(result)
    account = md.get("account") if isinstance(md.get("account"), dict) else {}
    nxt = account.get("next") if isinstance(account.get("next"), dict) else {}
    pool_state = md.get("account_pool") if isinstance(md.get("account_pool"), dict) else {}
    candidates = [
        _when(account.get("cooldown_until")) or _when(failure.get("resets_at")),
        _when(nxt.get("retry_at")),
        _when(pool_state.get("retry_at")),
    ]
    future = [c for c in candidates if c is not None and c > now]
    resets = min(future) if future else now + timedelta(minutes=max(1, default_minutes))
    message = str(failure.get("message") or result.error or "rate limited")[:200]
    return {
        "resets_at": _iso(resets),
        "resume_at": _iso(max(resets, now) + PARK_GRACE),
        "reason": message,
        **({"budget": True} if failure.get("reason") == "subscription_budget" else {}),
    }


# ── The mixin ────────────────────────────────────────────────


class RunHealthMixin:
    """Account rotation, stall retries, nudges, parking and spend booking."""

    async def _book_spend(
        self, run: _DispatchRun, result: DriverResult, *, governor_too: bool
    ) -> None:
        """Book a driver call's spend: the Governor (when asked) and the per-task total.

        A run on a subscription account books nothing (risk D4): its cost is
        the plan's, gated on window share by the account hook.
        """
        if subscription_run(result):
            return
        if governor_too:
            await governor.record(run.tenant_id, BudgetCategory.DRIVER, result.cost_usd)
        run.spent_usd += float(result.cost_usd or 0.0)

    async def _call_driver(
        self,
        run: _DispatchRun | None,
        driver: Any,
        packet: ContextPacket,
        workdir: Path,
        resume: tuple[str, str, Any] | None = None,
    ) -> DriverResult:
        """One driver call: ``dispatch``, or ``resume`` of (session, prompt, account)."""
        from life_graph.drivers.dispatcher import _driver_timeout

        timeout = _driver_timeout(driver, run)
        if resume is not None:
            session_id, prompt, account_id = resume
            return await driver.resume(
                packet, workdir, session_id, prompt, timeout=timeout, account_id=account_id
            )
        return await driver.dispatch(packet, workdir, timeout=timeout)

    @staticmethod
    def _note_session(run: _DispatchRun, driver: Any, result: DriverResult) -> None:
        """Remember the latest CLI session and the accounts this task used."""
        md = result.metadata or {}
        account = md.get("account") if isinstance(md.get("account"), dict) else {}
        if account.get("id"):
            run.accounts_tried.add(str(account["id"]))
        if md.get("session_id"):
            run.session_ref = {
                "driver": getattr(driver, "name", None),
                "session_id": str(md["session_id"]),
                "account_id": account.get("id"),
            }

    async def _drive(
        self,
        run: _DispatchRun | None,
        driver: Any,
        packet: ContextPacket,
        workdir: Path,
        *,
        attempt: int,
        book_first: bool,
        resume: tuple[str, str, Any] | None = None,
    ) -> tuple[DriverResult, int]:
        """Run the driver, then any rotation / stall retry; ``(final result, its attempt)``.

        The caller emits the final result's steps and books its spend, as it
        always did; a result this replaces is emitted and booked here (the
        first one with the Governor only when *book_first*).
        """
        result = await self._call_driver(run, driver, packet, workdir, resume)
        if run is None:
            return result, attempt
        self._note_session(run, driver, result)
        stalls = 0
        while True:
            turn = await self._next_turn(run, driver, packet, workdir, result, stalls)
            if turn is None:
                return result, attempt
            kind, data, (next_packet, next_resume) = turn
            if kind == "stall_retry":
                stalls += 1
            await self._emit_steps(run.tenant_id, run.task_id, driver.name, attempt, result)
            await self._book_spend(run, result, governor_too=book_first)
            book_first = True
            attempt = run.next_attempt
            run.next_attempt += 1
            await self._record_round(run, kind, {**data, "attempt": attempt})
            result = await self._call_driver(run, driver, next_packet, workdir, next_resume)
            self._note_session(run, driver, result)

    async def _next_turn(
        self,
        run: _DispatchRun,
        driver: Any,
        packet: ContextPacket,
        workdir: Path,
        result: DriverResult,
        stalls: int,
    ) -> tuple[str, dict, tuple[ContextPacket, tuple | None]] | None:
        """The extra call *result* earns, as ``(kind, event data, (packet, resume))``."""
        nxt = next_account(result) if settings.driver_accounts_enabled else None
        if rate_limited(result) and nxt is not None:
            target = str(nxt["id"])
            if target in run.accounts_tried:
                return None
            allowed, why = await self._round_allowed(
                run, subscription=nxt.get("kind") == "subscription"
            )
            if not allowed:
                self._round_skipped(run, "rate_limit_switch", why)
                return None
            run.accounts_tried.add(target)
            account = (result.metadata or {}).get("account") or {}
            note = handoff_note(agent_texts(result))
            switched = replace(
                packet,
                instruction=continue_prompt(packet.instruction, note),
                account_id=target,
            )
            data = {
                "from": account.get("name"),
                "to": nxt.get("name"),
                "handoff_chars": len(note),
            }
            await self._emit(
                EventType.DRIVER_ACCOUNT_SWITCHED,
                {
                    "tenant_id": run.tenant_id,
                    "task_id": run.task_id,
                    "driver": driver.name,
                    "from_account": account.get("id"),
                    "to_account": target,
                },
            )
            return "rate_limit_switch", data, (switched, None)
        limit = run.policy.max_stall_retries
        if timed_out(result) and stalls < limit:
            allowed, why = await self._round_allowed(run, subscription=subscription_run(result))
            if not allowed:
                self._round_skipped(run, "stall_retry", why)
                return None
            delay = stall_delay(stalls)
            task_events.emit(
                run.tenant_id, run.task_id, "round",
                f"the driver stopped responding; retrying in {delay:.0f}s "
                f"({stalls + 1} of {limit})",
                data={"kind": "stall_wait", "seconds": delay, "round": stalls + 1, "of": limit},
                source="dispatcher",
            )  # fmt: skip
            await _sleep(delay)
            # The owner may have paused everything while we waited.
            allowed, why = await self._round_allowed(run, subscription=subscription_run(result))
            if not allowed:
                self._round_skipped(run, "stall_retry", why)
                return None
            data = {"round": stalls + 1, "of": limit, "delay_seconds": delay}
            return "stall_retry", data, self._continuation_call(run, driver, packet, STALL_TEXT)
        return None

    @staticmethod
    def _continuation_call(
        run: _DispatchRun, driver: Any, packet: ContextPacket, text: str
    ) -> tuple[ContextPacket, tuple | None]:
        """``(packet, resume)``: resume the run's session with *text*, else re-dispatch."""
        ref = run.session_ref or {}
        if ref.get("session_id") and getattr(driver, "supports_resume", False):
            return packet, (ref["session_id"], text, ref.get("account_id"))
        return replace(packet, instruction=f"{text}\n\n{packet.instruction}"), None

    async def _record_round(self, run: _DispatchRun, kind: str, data: dict) -> None:
        """One run-health round: a task event, the approval payload, an EventBus event."""
        labels = {
            "rate_limit_switch": "rate limited: continuing on the next account",
            "stall_retry": "stall retry",
            "nudge": "nudge: carry out the plan",
        }
        task_events.emit(
            run.tenant_id, run.task_id, "round", labels.get(kind, kind),
            data={"kind": kind, **data}, source="dispatcher",
        )  # fmt: skip
        rounds = run.autonomy.setdefault("run_health", [])
        rounds.append({"kind": kind, **{k: v for k, v in data.items() if k != "handoff_chars"}})
        await self._emit(
            EventType.DRIVER_RUN_HEALTH_ROUND,
            {"tenant_id": run.tenant_id, "task_id": run.task_id, "kind": kind, **data},
        )

    @staticmethod
    def _round_skipped(run: _DispatchRun, kind: str, why: str | None) -> None:
        task_events.emit(
            run.tenant_id, run.task_id, "round", f"not retrying automatically: {why}",
            data={"kind": kind, "skipped": True, "reason": why}, source="dispatcher",
        )  # fmt: skip

    async def _nudge_until_changed(self, run: _DispatchRun, change_required: bool) -> None:
        """Nudge an edit run that only described a plan, up to ``max_nudges`` times.

        Runs before Step 4c would fail the task for changing no file; after
        each nudge the worktree is re-checked (tamper, then the file list).
        """
        limit = run.policy.max_nudges
        while (
            limit
            and run.nudges < limit
            and change_required
            and run.result is not None
            and run.result.success
            and run.worktree is not None
            and not run.files_changed
        ):
            if classify_empty_turn([run.result.output or ""]) != "plan_only":
                return
            allowed, why = await self._round_allowed(run, subscription=subscription_run(run.result))
            if not allowed:
                self._round_skipped(run, "nudge", why)
                return
            run.nudges += 1
            attempt = run.next_attempt
            run.next_attempt += 1
            await self._record_round(
                run, "nudge", {"round": run.nudges, "of": limit, "attempt": attempt}
            )
            packet, resume = self._continuation_call(run, run.driver, run.packet, NUDGE_PLAN_TEXT)
            # A nudge that hits a rate limit or a stall gets the same handling.
            result, attempt = await self._drive(
                run, run.driver, packet, run.workdir,
                attempt=attempt, book_first=True, resume=resume,
            )  # fmt: skip
            await self._emit_steps(run.tenant_id, run.task_id, run.driver.name, attempt, result)
            await self._book_spend(run, result, governor_too=True)
            run.result = result
            await self._check_worktree_link(run)
            if not run.result.success:
                return
            await self._observe_files_changed(run)

    def _decide_park(self, run: _DispatchRun) -> None:
        """Mark a still-rate-limited result for parking when the owner asked for it."""
        if not run.policy.wait_for_reset or run.result is None:
            return
        park = park_decision(
            run.result, default_minutes=settings.driver_accounts_default_cooldown_minutes
        )
        if park is None:
            return
        run.result.metadata = {**(run.result.metadata or {}), "park": park}
        task_events.emit(
            run.tenant_id, run.task_id, "round",
            f"waiting for the plan limit to reset at {park['resets_at']}",
            data={"kind": "park", **park}, source="dispatcher",
        )  # fmt: skip

    async def _budget_preview(self, run: _DispatchRun) -> dict | None:
        """Which account the run will use and the D4 decision, as a task event.

        ``None`` when accounts are off or the driver has none (the Governor
        decides as before).
        """
        name = getattr(run.driver, "name", "")
        if not settings.driver_accounts_enabled or name not in DRIVERS:
            return None
        preview = await accounts_hook.preview(name, run.tenant_id, unattended=not run.interactive)
        if preview is None:
            return None
        decision = preview.get("budget") or {}
        state = preview.get("state")
        if state == "selected" and preview.get("kind") == "subscription":
            used = decision.get("used_percent")
            text = f"subscription account {preview.get('name')}: billed to the plan, not dollars"
            if used is not None:
                text += (
                    f" ({decision.get('window')} {used:.0f}% of the window,"
                    f" limit {decision.get('share_limit', 1) * 100:.0f}%)"
                )
        elif state == "selected":
            text = f"{preview.get('kind')} account {preview.get('name')}: dollar budget applies"
        elif state == "over_budget":
            text = f"no account may run unattended: {decision.get('reason')}"
        else:
            text = f"accounts {state}"
        if decision.get("reason") and state == "selected":
            text += f"; skipped {decision['reason']}"
        task_events.emit(
            run.tenant_id, run.task_id, "budget", text,
            data={"state": state, "kind": preview.get("kind"), "account": preview.get("name"),
                  **({"subscription_budget": decision} if decision else {})},
            source="dispatcher",
        )  # fmt: skip
        return preview

    # ── continue_task: keep the worktree and session ─────────────

    async def _retain_for_continuation(self, run: _DispatchRun) -> bool:
        """Keep the worktree for a later continue_task; True when it was kept.

        Only with ``driver_continue_enabled``, a CLI session to resume, an
        intact worktree and a task row to record it on.
        """
        ref = run.session_ref or {}
        if (
            not settings.driver_continue_enabled
            or run.worktree is None
            or not run.worktree_origin
            or not ref.get("session_id")
        ):
            return False
        if run.result is not None and (run.result.metadata or {}).get("park"):
            return False  # a parked task re-runs from a fresh worktree
        worktree = Path(run.worktree)
        if not worktree.is_dir() or not worktree_intact(worktree, run.worktree_origin):
            return False
        now = datetime.now(UTC)
        md = (run.result.metadata or {}) if run.result is not None else {}
        record = {
            "worktree": str(worktree),
            "origin": str(run.worktree_origin),
            "driver": ref.get("driver"),
            "session_id": ref["session_id"],
            "account_id": ref.get("account_id"),
            "branch": md.get("landed_branch") or run.landed_branch,
            "base_commit": run.base_commit,
            "verify_chain": list(run.verify_chain or []),
            "rounds": run.continuation_round,
            "kept_at": _iso(now),
            "keep_until": _iso(now + timedelta(hours=max(0, settings.driver_continue_keep_hours))),
        }
        return bool(await self._persist_task_props(run, {"continuation": record}))
