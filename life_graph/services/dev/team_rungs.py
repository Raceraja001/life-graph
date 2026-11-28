"""Which escalation rung a team worker runs on: a requested tier, or a retry.

docs/specs/agent-drivers.md, "Team upgrades (2026-11-28)". Reuses the
escalation ladder (drivers/escalation.py) and the very same per-rung checks
the dispatcher's climb uses (``LadderMixin._rung_blocker`` in
drivers/ladder_steps.py: registered + available, metered only when allowed and
within the Governor and the per-task cap, the subscription share, and the
daily top-rung cap) -- so a team can never put a worker where the ladder
itself could not.

* **Tier** (a plan line's ``Tier:`` or the plan's ``team_worker_tier``):
  ``cheap`` = the bottom rung, ``best`` = the top, ``balanced`` = the middle
  (``(n - 1) // 2``). A rung that may not run now falls to the next lower one
  (so ``best`` over the cap lands on the highest rung allowed), then upward;
  every refusal is reported.
* **Retry**: the first allowed rung above the one the failed attempt ran on;
  none (top already, all refused, ladder off, kill switch) = the same rung.

The chosen rung is written on the worker as ``driver_pin`` (honoured by the
dispatcher today) and ``team_rung`` ``{driver, model, label, tier, why}``.
A pinned worker does not climb inside its run: the team's retry is its climb.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from life_graph.autonomy.kill_switch import autonomy_stopped
from life_graph.config import settings
from life_graph.drivers import escalation
from life_graph.drivers.ladder_steps import LadderMixin
from life_graph.drivers.plan_spec import TIERS
from life_graph.drivers.registry import billing_of, driver_registry
from life_graph.kernel.personas import PersonaService
from life_graph.models.db import AgentTask
from life_graph.models.dev_outcomes import DevOutcomeLog
from life_graph.services.dev import outcome_log

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

#: The per-task cost cap a probed rung is checked against (the dispatcher's default).
_COST_CAP_USD = 2.0


@dataclass
class RungChoice:
    """Where a worker will run, and the story of how that was decided."""

    rung: escalation.Rung | None = None
    index: int | None = None
    tier: str | None = None
    why: str = ""
    refused: list[str] = field(default_factory=list)

    def pin(self) -> dict[str, Any]:
        """The worker properties that put it on this rung ({} = today's selection)."""
        if self.rung is None:
            return {}
        return {
            "driver_pin": self.rung.driver,
            "team_rung": {
                "driver": self.rung.driver,
                "model": self.rung.model,
                "label": self.rung.label,
                "tier": self.tier,
                "why": self.why[:300],
            },
        }


def tier_index(tier: str | None, size: int) -> int | None:
    """The ladder position a tier asks for on a ladder of *size* rungs."""
    if tier not in TIERS or size <= 0:
        return None
    if tier == "cheap":
        return 0
    if tier == "best":
        return size - 1
    return (size - 1) // 2


class _Probe(LadderMixin):
    """The dispatcher's per-rung checks, outside a dispatch.

    ``pending_top`` counts top-rung picks this probe already made (one fan-out
    choosing ``best`` for three workers must not see the same free cap three
    times).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.pending_top = 0

    async def _top_usage(self, run: Any) -> tuple[int, int] | None:
        usage = await outcome_log.top_tier_usage(self._session_factory, run.tenant_id)
        if usage is None:
            return None
        return usage[0] + self.pending_top, usage[1] + self.pending_top

    async def blocker(
        self, tenant_id: str, rung: escalation.Rung, *, is_top: bool
    ) -> tuple[Any, str | None]:
        run = SimpleNamespace(
            tenant_id=tenant_id, interactive=False, spent_usd=0.0, cost_cap_usd=_COST_CAP_USD
        )
        return await self._rung_blocker(run, rung, is_top=is_top)  # type: ignore[arg-type]


class RungPicker:
    """Resolves tiers and retry rungs for one team (one probe, one cap count)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.probe = _Probe(session_factory)
        self._ladder: list[escalation.Rung] | None = None

    def ladder(self) -> list[escalation.Rung]:
        if self._ladder is None:
            self._ladder = escalation.configured_ladder(driver_registry)
        return self._ladder

    async def _first_allowed(self, order: list[int]) -> tuple[int | None, list[str]]:
        ladder = self.ladder()
        refused: list[str] = []
        for idx in order:
            rung = ladder[idx]
            is_top = idx == len(ladder) - 1
            try:
                driver, why = await self.probe.blocker(self.tenant_id, rung, is_top=is_top)
            except Exception as exc:  # fail-open: a refused rung, never a broken team
                driver, why = None, f"check failed ({type(exc).__name__})"
            if driver is None:
                refused.append(f"{rung.label}: {why}")
                continue
            if is_top and billing_of(driver) != "local":
                self.probe.pending_top += 1
            return idx, refused
        return None, refused

    async def for_tier(self, tier: str) -> RungChoice:
        """The rung for a requested *tier* (see the module doc); no rung = selection."""
        ladder = self.ladder()
        target = tier_index(tier, len(ladder))
        if target is None:
            return RungChoice(why="no escalation ladder" if not ladder else "unknown tier")
        order = [*range(target, -1, -1), *range(target + 1, len(ladder))]
        idx, refused = await self._first_allowed(order)
        if idx is None:
            return RungChoice(why=f"tier {tier}: no rung may run now", refused=refused)
        got = escalation.tier_of(idx, len(ladder))
        why = f"tier {tier}" if idx == target else f"tier {tier} -> {got} (fell back)"
        return RungChoice(ladder[idx], idx, got, why, refused)

    async def for_retry(self, ran_on: escalation.Rung | None) -> RungChoice:
        """The rung a retry runs on: one above *ran_on*, else the same rung."""
        ladder = self.ladder()
        here = escalation.position(ladder, ran_on.driver, ran_on.model) if ran_on else None
        if here is None:
            # Off the ladder (or not known): rerun as before, nothing to climb.
            return RungChoice(why="retry: not on the ladder, same driver selection")
        same = RungChoice(ladder[here], here, escalation.tier_of(here, len(ladder)))
        if not settings.driver_escalation_enabled:
            same.why = "retry on the same rung (escalation is off)"
            return same
        if here >= len(ladder) - 1:
            same.why = "retry on the same rung (already the top)"
            return same
        try:
            stopped = await autonomy_stopped(self.tenant_id)
        except Exception:  # expected: an unreadable kill switch means no climb (fail closed)
            stopped = True
        if stopped:
            same.why = "retry on the same rung (autonomy is paused)"
            return same
        idx, refused = await self._first_allowed(list(range(here + 1, len(ladder))))
        if idx is None:
            same.why = (
                "retry on the same rung (no higher rung may run: " + "; ".join(refused)[:200] + ")"
            )
            same.refused = refused
            return same
        return RungChoice(
            ladder[idx],
            idx,
            escalation.tier_of(idx, len(ladder)),
            f"retry one rung up from {ladder[here].label}",
            refused,
        )


def pinned_model(props: dict[str, Any] | None) -> str | None:
    """The model a team worker's rung asks for (None = the persona's own).

    For the dispatcher hook: a worker whose ``team_rung`` names a model (a
    ``local:<model>`` rung) should run that model, as the ladder's own
    ``_switch_to`` does.
    """
    rung = (props or {}).get("team_rung") or {}
    if not isinstance(rung, dict) or not (props or {}).get("driver_pin"):
        return None
    return str(rung["model"]) if rung.get("model") else None


async def apply_team_rung(run: Any) -> None:
    """The dispatcher hook (``TaskDispatcher.dispatch``, Step 3, right before
    ``_apply_start_floor``): a team worker pinned to a rung also runs that
    rung's model, and a pin to a non-local top rung counts against the daily
    top-rung cap (``reached_top``), as a climb there would. Never raises; a
    task that is not a rung-pinned team worker is left alone.
    """
    try:
        if not getattr(run, "driver_pin", None) or getattr(run, "packet", None) is None:
            return
        task = await run.session.get(AgentTask, uuid.UUID(str(run.task_id)))
        if task is None or task.tenant_id != run.tenant_id:
            return
        props = task.properties or {}
        rung = props.get("team_rung") or {}
        if not isinstance(rung, dict) or rung.get("driver") != run.driver_pin:
            return
        model = pinned_model(props)
        if model:
            run.packet.persona_model = model
        if rung.get("tier") == escalation.TIER_BEST and billing_of(run.driver) != "local":
            run.reached_top = True
    except Exception:
        logger.warning(
            "Could not apply the team rung of %s", getattr(run, "task_id", "?"), exc_info=True
        )


async def ran_on(session: AsyncSession, tenant_id: str, task: Any) -> escalation.Rung | None:
    """The rung a finished task last ran on: its latest outcome row, else its pin."""
    try:
        row = (
            await session.execute(
                select(DevOutcomeLog.final_driver, DevOutcomeLog.final_model)
                .where(DevOutcomeLog.tenant_id == tenant_id, DevOutcomeLog.task_id == str(task.id))
                .order_by(DevOutcomeLog.created_at.desc())
                .limit(1)
            )
        ).first()
    except Exception:
        logger.debug("Could not read the outcome row of %s", task.id, exc_info=True)
        row = None
    if row is not None and row[0]:
        return escalation.Rung(str(row[0]), str(row[1]) if row[1] else None)
    pin = (task.properties or {}).get("team_rung") or {}
    if isinstance(pin, dict) and pin.get("driver"):
        return escalation.Rung(str(pin["driver"]), pin.get("model") or None)
    metadata = (task.result or {}).get("metadata") or {}
    if metadata.get("driver"):
        return escalation.Rung(str(metadata["driver"]), None)
    return None


async def get_persona(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str, name: str
) -> dict[str, Any] | None:
    """An active persona of this tenant that can run dev tasks (has a driver), or None."""
    try:
        persona = await PersonaService(session_factory=session_factory).get_by_name(tenant_id, name)
    except Exception:
        logger.debug("Could not look up persona %s", name, exc_info=True)
        return None
    if not persona or not persona.get("is_active", True) or not persona.get("driver"):
        return None
    return persona


def persona_pins(persona: dict[str, Any] | None) -> str | None:
    """The driver a persona pins (and may not climb from), or None."""
    if not persona:
        return None
    driver = persona.get("driver") or (persona.get("properties") or {}).get("driver")
    if not driver or driver == "auto":
        return None
    if (persona.get("properties") or {}).get(escalation.PIN_ALLOWS_KEY):
        return None
    return str(driver)
