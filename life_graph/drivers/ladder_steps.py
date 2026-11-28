"""The escalation ladder, starting floor and outcome log inside a dispatch.

A mixin: ``TaskDispatcher`` inherits these and provides ``_session_factory``.
The rules themselves are pure functions in ``drivers/escalation.py``; the
rows are written by ``services/dev/outcome_log.py``. docs/specs/agent-drivers.md,
"Escalation ladder, starting floor, outcome log (2026-11-28)".

* :meth:`LadderMixin._apply_start_floor` -- Step 3a, after selection: a code
  task naming a protected path, or whose project + instruction failed
  recently, starts at the top rung. Persona/arena pins win.
* :meth:`LadderMixin._climb` -- before each bounce / fix round: one rung up,
  skipping rungs that are unavailable, metered (unless allowed), over the
  subscription share or over the daily top-rung cap. A blocked climb leaves
  the driver as it was (today's same-driver bounce). The bounce limits and the
  owner's rounds (D2) are not touched: the ladder only picks *who* runs a
  bounce that would have run anyway.
* :meth:`LadderMixin._log_outcome` -- once per dispatch, on every terminal path.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from life_graph.autonomy.kill_switch import autonomy_stopped
from life_graph.config import settings
from life_graph.core.budget import BudgetCategory
from life_graph.drivers import accounts_hook, escalation
from life_graph.drivers.registry import billing_of, driver_registry
from life_graph.services.dev import outcome_log, task_events
from life_graph.services.governor import governor

if TYPE_CHECKING:
    from life_graph.drivers.dispatcher import _DispatchRun
    from life_graph.services.dev.verifiers import VerifierResult

logger = logging.getLogger(__name__)

# The task types the floor applies to (they are the ones that touch paths).
_FLOOR_TASK_TYPES = ("code", "code_change", "bugfix", "refactor", "feature")


def _clip(value: Any, size: int) -> str | None:
    return str(value)[:size] if value else None


#: The outcome log's reviewer verdicts. ``not_reviewed``: a review was due and
#: produced no verdict (failed, timed out, unreadable: fail-closed, it is never
#: an approval). ``skipped``: no review was on, or there was nothing to review.
REVIEW_VERDICTS = ("approved", "objected", "not_reviewed", "skipped")


def _review_entry(reviewer: str, verdict: Any) -> dict[str, Any]:
    """One reviewer's verdict for the outcome log (see :data:`REVIEW_VERDICTS`).

    Reads the verdict's ``status`` (services/dev/second_opinion.ReviewStatus)
    when it has one, else the legacy ``ran``/``approved`` pair.
    """
    status = str(getattr(verdict, "status", "") or "")
    if status not in REVIEW_VERDICTS:
        ran = bool(getattr(verdict, "ran", False))
        approved = bool(getattr(verdict, "approved", False))
        if ran:
            status = "approved" if approved else "objected"
        else:
            status = "skipped" if approved else "not_reviewed"
    entry: dict[str, Any] = {"reviewer": reviewer, "verdict": status}
    concern = getattr(verdict, "concern", None)
    if concern:
        entry["concern"] = str(concern)[:300]
    return entry


_STAGE_VERDICTS = {
    "no_objection": "approved",
    "objection": "objected",
    "unavailable": "not_reviewed",
    "human": "objected",
    "skipped": "skipped",
}


def _reviews(run: _DispatchRun) -> tuple[list[dict[str, Any]], str]:
    """Every reviewer verdict of the dispatch and the overall one.

    Overall: ``objected`` if any reviewer objected, else ``not_reviewed`` if a
    due review produced no verdict, else ``approved`` if one approved, else
    ``skipped`` (no review ran: off, nothing to review, or never reached).
    """
    reviews: list[dict[str, Any]] = []
    if run.second_opinion:
        reviews.append(dict(run.second_opinion))
    for rec in run.review_results or []:
        reviews.append(
            {
                "reviewer": f"stage:{rec.get('name') or rec.get('index')}",
                "verdict": _STAGE_VERDICTS.get(str(rec.get("verdict")), "not_reviewed"),
                **({"concern": str(rec["concern"])[:300]} if rec.get("concern") else {}),
            }
        )
    verdicts = {r["verdict"] for r in reviews}
    for overall in ("objected", "not_reviewed", "approved"):
        if overall in verdicts:
            return reviews, overall
    return reviews, "skipped"


def _final_outcome(run: _DispatchRun, error: BaseException | None) -> str:
    """landed | succeeded | no_changes | needs_human | parked | budget_denied | failed | error."""
    result = run.result
    if error is not None or result is None:
        return "error"
    md = result.metadata or {}
    if result.success:
        return "landed" if md.get("landed_branch") else "succeeded"
    if not result.error and md.get("outcome") == "no_changes":  # dispatcher.is_no_changes
        return "no_changes"
    if md.get("park"):
        return "parked"
    if md.get("budget_throttled"):
        return "budget_denied"
    if md.get("needs_human"):
        return "needs_human"
    return "failed"


def _verification(run: _DispatchRun) -> str:
    """passed | failed | unverifiable | not_run, from the latest verdicts."""
    if run.unverifiable:
        return "unverifiable"
    results = run.verifier_results or []
    if not results:
        return "not_run"
    return "passed" if all(r.passed is True for r in results) else "failed"


class LadderMixin:
    """Starting floor, escalation ladder and outcome log for a dispatch."""

    # ── Shared helpers (patchable in tests) ───────────────────

    @staticmethod
    def _ladder() -> list[escalation.Rung]:
        return escalation.configured_ladder(driver_registry)

    async def _recent_failure(self, run: _DispatchRun) -> bool:
        return await outcome_log.recent_failure(
            self._session_factory,
            run.tenant_id,
            run.project_uuid,
            outcome_log.instruction_fingerprint(run.instruction),
            days=settings.driver_start_floor_failure_days,
        )

    async def _top_usage(self, run: _DispatchRun) -> tuple[int, int] | None:
        return await outcome_log.top_tier_usage(self._session_factory, run.tenant_id)

    @staticmethod
    def _current_model(run: _DispatchRun) -> str | None:
        name = getattr(run.driver, "name", "")
        persona_model = run.packet.persona_model if run.packet is not None else None
        return escalation.run_model(name, persona_model)

    def _position(self, run: _DispatchRun, ladder: list[escalation.Rung]) -> int | None:
        return escalation.position(
            ladder, getattr(run.driver, "name", ""), self._current_model(run)
        )

    async def _rung_blocker(
        self, run: _DispatchRun, rung: escalation.Rung, *, is_top: bool
    ) -> tuple[Any, str | None]:
        """``(driver, None)`` when *rung* may run this task now, else ``(None, why)``."""
        driver = driver_registry.get(rung.driver)
        if driver is None or getattr(driver, "pin_required", False):
            return None, "not registered"
        try:
            if not await driver.available():
                return None, "not available"
        except Exception:
            return None, "availability check failed"
        billing = billing_of(driver)
        if billing == "api":
            if not settings.driver_escalation_allow_metered:
                return None, "metered (driver_escalation_allow_metered is off)"
            try:
                decision = await governor.authorize(
                    run.tenant_id,
                    BudgetCategory.DRIVER,
                    estimated_usd=driver.cost_per_task(),
                    interactive=run.interactive,
                )
            except Exception as exc:
                return None, f"budget could not be checked ({type(exc).__name__})"
            if not decision.allowed:
                return None, f"budget: {decision.reason}"
            if run.spent_usd + driver.cost_per_task() > run.cost_cap_usd:
                return None, "per-task cost cap"
        elif billing == "subscription" and settings.driver_accounts_enabled:
            preview = await accounts_hook.preview(
                rung.driver, run.tenant_id, unattended=not run.interactive
            )
            if preview is not None and preview.get("state") in ("over_budget", "cooling", "error"):
                return None, f"subscription accounts {preview.get('state')}"
        if is_top and billing != "local":
            # The cap protects the subscription (or the API budget); a ladder
            # whose top rung runs on this machine has nothing to protect.
            usage = await self._top_usage(run)
            if usage is None:
                return None, "top-rung use could not be counted"
            if not escalation.top_cap_allows(*usage):
                return None, f"top-rung cap reached ({usage[0]} of {usage[1]} today)"
        return driver, None

    def _switch_to(self, run: _DispatchRun, driver: Any, rung: escalation.Rung) -> None:
        """Put *run* on *rung*: its driver, and its model (or the persona's own)."""
        run.driver = driver
        if run.packet is not None:
            run.packet.persona_model = rung.model or run.persona_model

    # ── Step 3a: starting floor ───────────────────────────────

    async def _apply_start_floor(self, run: _DispatchRun) -> None:
        """Start at the top rung for a protected path or a recent failure.

        Records where the dispatch started and why either way. A pin (persona
        driver, arena racer) wins; a top rung that may not run now (cap,
        subscription share, availability) leaves today's selection, with the
        refusal in the start reason.
        """
        run.persona_model = run.packet.persona_model if run.packet is not None else None
        run.pinned, run.pin_allows_escalation = escalation.pin_state(run.persona, run.driver_pin)
        run.start_reason = "pinned" if run.pinned else "selection"
        try:
            await self._floor(run)
        except Exception:
            logger.warning("Starting floor failed for task %s", run.task_id, exc_info=True)
        run.start_driver = getattr(run.driver, "name", None)
        run.start_model = self._current_model(run)

    async def _floor(self, run: _DispatchRun) -> None:
        if run.task_type not in _FLOOR_TASK_TYPES:
            return
        ctx = run.packet.project_context if run.packet is not None else {}
        declared = [
            str(f) for h in (run.seed or {}).get("handoffs") or [] for f in (h.get("files") or [])
        ]
        run.floor_trigger = escalation.protected_reason(
            run.instruction, declared, [str(p) for p in (ctx or {}).get("protected_paths") or []]
        )
        run.failed_before = await self._recent_failure(run)
        if run.floor_trigger is None and run.failed_before:
            run.floor_trigger = "failed before (same project and instruction)"
        why = run.floor_trigger
        if why is None or run.pinned or not settings.driver_start_floor_enabled:
            return
        ladder = self._ladder()
        if not ladder or self._position(run, ladder) == len(ladder) - 1:
            return
        top = ladder[-1]
        driver, blocked = await self._rung_blocker(run, top, is_top=True)
        if driver is None:
            run.start_reason = f"selection (floor {why}: {top.label} {blocked})"
            task_events.emit(
                run.tenant_id, run.task_id, "escalation",
                f"starting floor not applied: {top.label} {blocked}",
                data={"kind": "floor", "applied": False, "why": why, "blocked": blocked},
                source="dispatcher",
            )  # fmt: skip
            return
        was = getattr(run.driver, "name", None)
        self._switch_to(run, driver, top)
        run.reached_top = True
        run.start_reason = f"floor: {why}"
        task_events.emit(
            run.tenant_id, run.task_id, "escalation", f"starting floor: {top.label} ({why})",
            data={"kind": "floor", "applied": True, "why": why, "from": was, "to": top.label},
            source="dispatcher",
        )  # fmt: skip

    # ── Before each bounce: the ladder ────────────────────────

    async def _climb(
        self, run: _DispatchRun, attempt: int, failures: list[VerifierResult] | None = None
    ) -> None:
        """Move *run* one rung up for this bounce/round, or leave it where it is."""
        if not settings.driver_escalation_enabled:
            return
        if run.pinned and not run.pin_allows_escalation:
            return
        try:
            ladder = self._ladder()
            here = self._position(run, ladder)
            if here is None or here >= len(ladder) - 1:
                return
            failed = [r.verifier for r in failures or [] if not r.passed]
            reason = f"verification failed ({', '.join(failed[:3]) or 'checks'})"
            frm = escalation.Rung(getattr(run.driver, "name", "?"), self._current_model(run)).label
            if await autonomy_stopped(run.tenant_id):
                self._note_escalation(run, attempt, frm, None, reason, "autonomy is paused")
                return
            refused: list[str] = []
            for idx in range(here + 1, len(ladder)):
                rung = ladder[idx]
                is_top = idx == len(ladder) - 1
                driver, blocked = await self._rung_blocker(run, rung, is_top=is_top)
                if driver is None:
                    refused.append(f"{rung.label}: {blocked}")
                    continue
                self._switch_to(run, driver, rung)
                if is_top:
                    run.reached_top = True
                self._note_escalation(run, attempt, frm, rung.label, reason, None, refused)
                return
            self._note_escalation(run, attempt, frm, None, reason, "; ".join(refused))
        except Exception:
            logger.warning("Escalation check failed for task %s", run.task_id, exc_info=True)

    @staticmethod
    def _note_escalation(
        run: _DispatchRun,
        attempt: int,
        frm: str,
        to: str | None,
        reason: str,
        blocked: str | None,
        skipped: list[str] | None = None,
    ) -> None:
        entry: dict[str, Any] = {"attempt": attempt, "from": frm, "to": to, "reason": reason}
        if blocked:
            entry["blocked"] = blocked
        if skipped:
            entry["skipped"] = skipped
        run.escalations.append(entry)
        text = (
            f"escalated {frm} -> {to}: {reason}"
            if to
            else f"no escalation from {frm} ({blocked}); bouncing on the same driver"
        )
        task_events.emit(
            run.tenant_id, run.task_id, "escalation", text,
            data={"kind": "ladder", **entry}, source="dispatcher",
        )  # fmt: skip

    # ── Outcome log ───────────────────────────────────────────

    def _outcome_row(self, run: _DispatchRun, error: BaseException | None) -> dict[str, Any]:
        ladder = self._ladder()
        size = len(ladder)
        if run.start_driver is None and run.driver is not None:
            # A resumed landing or a continuation: no selection ran, it starts
            # (and ends) on the driver it was given.
            run.start_driver, run.start_model = run.driver.name, self._current_model(run)
            if run.start_reason == "selection":
                run.start_reason = "continuation" if run.continuation_round else "resumed"
        start_pos = (
            escalation.position(ladder, run.start_driver, run.start_model)
            if run.start_driver
            else None
        )
        final_pos = self._position(run, ladder) if run.driver is not None else None
        reviews, verdict = _reviews(run)
        protected = bool(run.floor_trigger and run.floor_trigger.startswith("protected"))
        shadow, shadow_reasons = escalation.shadow_tier(
            instruction=run.instruction,
            task_type=run.task_type,
            protected=protected,
            failed_before=run.failed_before,
        )
        result = run.result
        cost = float(getattr(result, "cost_usd", 0.0) or 0.0)
        msg = str(error) if error is not None else getattr(result, "error", None)
        return {
            "tenant_id": run.tenant_id,
            "task_id": str(run.task_id),
            "project_id": run.project_uuid,
            "task_type": run.task_type,
            "persona": run.persona_name,
            "instruction_sha": outcome_log.instruction_fingerprint(run.instruction),
            "start_driver": run.start_driver,
            "start_model": _clip(run.start_model, 120),
            "start_tier": escalation.tier_of(start_pos, size),
            "start_reason": (run.start_reason or "")[:300],
            "final_driver": getattr(run.driver, "name", None),
            "final_model": _clip(self._current_model(run) if run.driver is not None else None, 120),
            "final_tier": escalation.tier_of(final_pos, size),
            "escalations": list(run.escalations),
            "reached_top": bool(run.reached_top),
            "rounds_used": max(0, run.next_attempt - 2),
            "verification": _verification(run),
            "reviews": reviews,
            "review_verdict": verdict,
            "outcome": _final_outcome(run, error),
            "duration_ms": int(
                getattr(result, "duration_ms", 0) or (time.monotonic() - run.started_at) * 1000
            ),
            "cost_usd": max(cost, float(run.spent_usd or 0.0)),
            "shadow_tier": shadow,
            "shadow_reasons": shadow_reasons,
            "error": _clip(msg, 300),
            "properties": {
                k: v
                for k, v in {
                    "floor_trigger": run.floor_trigger,
                    "pinned": run.pinned or None,
                    "continuation": run.continuation_round or None,
                    "second_opinion": (run.second_opinion or {}).get("verdict"),
                }.items()
                if v is not None
            },
        }

    async def _log_outcome(self, run: _DispatchRun, error: BaseException | None = None) -> None:
        """Write the dispatch's outcome row once (best-effort, never raises).

        Also puts the start reason and escalations on the result's metadata,
        so the task row shows them.
        """
        if run.outcome_logged:
            return
        run.outcome_logged = True
        try:
            if run.result is not None and (run.escalations or run.start_reason != "selection"):
                run.result.metadata = {
                    **(run.result.metadata or {}),
                    "ladder": {"start_reason": run.start_reason, "escalations": run.escalations},
                }
            row = self._outcome_row(run, error)
        except Exception:
            logger.warning("Could not build the outcome row for %s", run.task_id, exc_info=True)
            return
        await self._write_outcome(row)

    async def _write_outcome(self, row: dict[str, Any]) -> None:
        await outcome_log.write(self._session_factory, row)
