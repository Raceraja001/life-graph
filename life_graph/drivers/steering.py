"""Steering messages inside a dispatch (docs/specs/agent-drivers.md,
"Steering messages (2026-11-28)").

A mixin: ``TaskDispatcher`` inherits these and provides ``_drive``,
``_continuation_call``, ``_round_allowed``, ``_book_spend`` and ``_emit_steps``
(drivers/run_health.py, drivers/review_stages.py).

* **At start** (:meth:`SteeringMixin._take_start_messages`): the messages the
  owner sent while the task was queued are appended to its instruction -- no
  extra turn -- and marked delivered once the driver has actually been called.
* **At the turn boundary** (:meth:`SteeringMixin._steer`): after a driver run
  ends successfully and before any check, waiting messages get one more turn
  in the same session (``driver.resume``) and workdir, at most
  ``driver_steer_max_turns`` per dispatch, each gated like every other extra
  round (kill switch, per-task cost cap, Governor / subscription share). A
  driver that cannot resume (or a run that left no session) gets the messages
  as a re-dispatch in the same worktree, the run-health fallback. A failed
  turn puts the worktree back as it was before the turn and keeps the
  pre-steer result; its messages stay undelivered, with the reason.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.drivers.base import DriverResult
from life_graph.drivers.run_health import subscription_run
from life_graph.drivers.workdir import worktree_intact
from life_graph.services.dev import task_events, task_messages

if TYPE_CHECKING:
    from life_graph.drivers.dispatcher import _DispatchRun

logger = logging.getLogger(__name__)


async def _git(workdir: Path, *args: str) -> str | None:
    """stdout of ``git *args`` in *workdir*, None when it failed."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args, cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )  # fmt: skip
        out, _ = await proc.communicate()
    except Exception:  # best-effort: no git (or no worktree) = no snapshot, never a failure
        return None
    return out.decode(errors="replace") if proc.returncode == 0 else None


def _intact(run: _DispatchRun) -> bool:
    # git only ever runs in a worktree still linked to its origin (Step 4b):
    # a planted .git would carry agent-chosen config.
    return bool(
        run.worktree is not None
        and run.worktree_origin
        and Path(run.worktree).is_dir()
        and worktree_intact(Path(run.worktree), run.worktree_origin)
    )


async def snapshot_tree(run: _DispatchRun) -> str | None:
    """The worktree's content as a git tree id (everything staged), or None."""
    if not _intact(run):
        return None
    wt = Path(run.worktree)
    if await _git(wt, "add", "-A") is None:
        return None
    tree = (await _git(wt, "write-tree") or "").strip()
    return tree or None


async def restore_tree(run: _DispatchRun, tree: str | None) -> bool:
    """Put the worktree back to *tree* (files the turn added are removed)."""
    if not tree or not _intact(run):
        return False
    wt = Path(run.worktree)
    for args in (("read-tree", "--reset", tree), ("checkout-index", "-a", "-f"), ("clean", "-fdq")):
        if await _git(wt, *args) is None:
            return False
    return True


def _emit(run: _DispatchRun, content: str, **data: Any) -> None:
    task_events.emit(run.tenant_id, run.task_id, "steer", content, data=data, source="dispatcher")


class SteeringMixin:
    """Deliver the owner's steering messages at start and at turn boundaries."""

    async def _take_start_messages(self, run: _DispatchRun, *, into: str = "instruction") -> str:
        """The block of waiting messages for the start of the run ('' when none).

        *into* names where it goes (``instruction`` for a fresh dispatch,
        ``continue`` for continue_task's feedback); they are marked delivered
        by :meth:`_settle_start_messages` once the driver was called.
        """
        messages = await task_messages.read_pending(
            self._session_factory, run.tenant_id, run.task_id
        )
        if not messages:
            return ""
        run.start_messages = [str(m["id"]) for m in messages]
        run.start_messages_via = into
        return task_messages.claim_block(messages)

    async def _settle_start_messages(self, run: _DispatchRun) -> None:
        ids = run.start_messages
        if not ids or run.result is None:
            return
        if (run.result.metadata or {}).get("exit_status") == "seed_failed":
            return  # the driver never ran: they are still to be delivered
        run.start_messages = []
        via = run.start_messages_via
        await task_messages.settle(self._session_factory, run.tenant_id, run.task_id, ids, via=via)
        where = "instruction" if via == "instruction" else "follow-up"
        _emit(run, f"{len(ids)} owner message(s) delivered with the {where}",
              state="delivered", ids=ids, via=via)  # fmt: skip
        run.autonomy.setdefault("steering", []).append({"via": via, "ids": ids})

    async def _not_delivered(
        self, run: _DispatchRun, ids: list[str], reason: str, *, state: str
    ) -> None:
        await task_messages.settle(
            self._session_factory, run.tenant_id, run.task_id, ids, via="turn", reason=reason
        )
        _emit(run, f"{len(ids)} owner message(s) not delivered: {reason}",
              state=state, ids=ids, reason=reason)  # fmt: skip
        run.autonomy.setdefault("steering", []).append(
            {"via": "turn", "ids": ids, "undelivered": reason}
        )

    async def _steer(self, run: _DispatchRun) -> None:
        """Steering turns: after a successful run, before any check."""
        limit = int(settings.driver_steer_max_turns or 0)
        if limit <= 0 or run.result is None:
            return
        while run.result.success and run.steer_turns < limit:
            messages = await task_messages.read_pending(
                self._session_factory, run.tenant_id, run.task_id
            )
            if not messages:
                return
            ids = [str(m["id"]) for m in messages]
            allowed, why = await self._round_allowed(run, subscription=subscription_run(run.result))
            if not allowed:
                await self._not_delivered(run, ids, str(why), state="skipped")
                return
            run.steer_turns += 1
            attempt = run.next_attempt
            run.next_attempt += 1
            _emit(run, f"delivering {len(ids)} owner message(s) (turn {run.steer_turns} of {limit})",
                  state="delivering", ids=ids, turn=run.steer_turns, of=limit,
                  attempt=attempt)  # fmt: skip
            before = run.result
            tree = await snapshot_tree(run)
            packet, resume = self._continuation_call(
                run, run.driver, run.packet, task_messages.steer_text(messages)
            )
            try:
                result, attempt = await self._drive(
                    run, run.driver, packet, run.workdir,
                    attempt=attempt, book_first=True, resume=resume,
                )  # fmt: skip
            except Exception as exc:
                logger.warning("Steering turn of task %s crashed", run.task_id, exc_info=True)
                result = DriverResult(success=False, error=f"crashed ({type(exc).__name__})")
            await self._emit_steps(run.tenant_id, run.task_id, run.driver.name, attempt, result)
            await self._book_spend(run, result, governor_too=True)
            if not result.success:
                restored = await restore_tree(run, tree)
                run.result = before
                reason = f"the steering turn failed: {(result.error or 'no reason')[:200]}"
                await self._not_delivered(run, ids, reason, state="failed")
                _emit(run, "kept the result from before the steering turn",
                      state="fallback", restored=restored)  # fmt: skip
                return
            run.result = result
            await task_messages.settle(
                self._session_factory, run.tenant_id, run.task_id, ids, via="turn"
            )
            _emit(run, f"{len(ids)} owner message(s) delivered (turn {run.steer_turns})",
                  state="delivered", ids=ids, via="turn", turn=run.steer_turns)  # fmt: skip
            run.autonomy.setdefault("steering", []).append(
                {"via": "turn", "ids": ids, "turn": run.steer_turns, "attempt": attempt}
            )
        # Out of turns, or the run did not succeed: what is left waits.
        left = await task_messages.read_pending(self._session_factory, run.tenant_id, run.task_id)
        if left:
            why = (
                f"the steering turn limit ({limit}) was reached"
                if run.result.success
                else "the run did not succeed"
            )
            await self._not_delivered(run, [str(m["id"]) for m in left], why, state="skipped")
