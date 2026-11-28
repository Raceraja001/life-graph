"""Escalation ladder and deterministic starting floor (plain rules, no model).

docs/specs/agent-drivers.md, "Escalation ladder, starting floor, outcome log
(2026-11-28)"; decided in race-app docs/research/2026-11-28-router-council/
04-decision.md (steps 3-4).

* **Ladder.** An ordered list of rungs ``driver[:model]``, weakest first
  (``driver_escalation_ladder``; empty = :data:`DEFAULT_LADDER`). A bounce
  after failed verification moves one rung up instead of re-running the same
  driver; it never steps down. A ``pin_required`` driver (``cloud``) is never a
  rung, whatever the setting says: it only runs when a persona pins it.
* **Starting floor.** A code task that names a protected path, or whose
  project + instruction already failed recently, starts at the top rung instead
  of where cheapest-first selection put it.
* **Top-rung cap.** Of a tenant's dispatches today, at most
  ``driver_escalation_top_share`` (and always the first
  ``driver_escalation_top_daily_min``) may be sent to the top rung by the
  ladder or the floor, so the one subscription doesn't park everything.

The dispatcher (``drivers/dispatcher.py``) does the switching; this module
only holds the pure rules, so they are testable without a dispatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from life_graph.config import settings
from life_graph.services.dev.change_policy import protected_hits

#: The real ladder on this machine: a model swap on the local driver, then
#: the Claude subscription. ``cloud`` is deliberately absent (pin-only).
DEFAULT_LADDER: tuple[str, ...] = (
    "local:ollama_chat/qwen3:14b",
    "local:ollama_chat/qwen3-coder:30b",
    "claude_code",
)

TIER_CHEAP, TIER_BALANCED, TIER_BEST = "cheap", "balanced", "best"

#: A persona's ``properties`` key that lets its pinned driver climb anyway.
PIN_ALLOWS_KEY = "allow_escalation"


@dataclass(frozen=True)
class Rung:
    """One step of the ladder: a driver, optionally with the model it runs."""

    driver: str
    model: str | None = None

    @property
    def label(self) -> str:
        return f"{self.driver}:{self.model}" if self.model else self.driver


def parse_ladder(spec: str) -> list[Rung]:
    """``"local:ollama_chat/qwen3:14b, claude_code"`` -> rungs, in order.

    The driver is everything before the first ``:``; the rest (which may hold
    more colons, as Ollama tags do) is the model. Blank entries and exact
    duplicates are dropped.
    """
    rungs: list[Rung] = []
    for raw in (spec or "").split(","):
        item = raw.strip()
        if not item:
            continue
        driver, _, model = item.partition(":")
        rung = Rung(driver.strip(), model.strip() or None)
        if rung.driver and rung not in rungs:
            rungs.append(rung)
    return rungs


def configured_ladder(registry: Any) -> list[Rung]:
    """The ladder in effect: the setting (or the default), registered drivers only.

    A rung whose driver isn't registered is skipped, and a ``pin_required``
    driver is never a rung. Availability is checked when a rung is climbed,
    not here (it can change between dispatches).
    """
    spec = settings.driver_escalation_ladder or ",".join(DEFAULT_LADDER)
    ladder = []
    for rung in parse_ladder(spec):
        driver = registry.get(rung.driver)
        if driver is None or getattr(driver, "pin_required", False):
            continue
        ladder.append(rung)
    return ladder


def tier_of(index: int | None, size: int) -> str | None:
    """The tier name of a rung position: the top is ``best``, the bottom ``cheap``."""
    if index is None or size <= 0:
        return None
    if index >= size - 1:
        return TIER_BEST
    return TIER_CHEAP if index == 0 else TIER_BALANCED


def _norm_model(model: str | None) -> str | None:
    """``ollama_chat/qwen3:14b`` and ``qwen3:14b`` name the same local model."""
    if not model:
        return None
    return model.strip().rsplit("/", 1)[-1].lower() or None


def run_model(driver_name: str, persona_model: str | None) -> str | None:
    """The model a run on *driver_name* uses (the local driver's default included).

    A persona's model is a LiteLLM model name: only the LiteLLM-backed drivers
    (``local``, ``cloud``) run it. CLI drivers (claude_code, codex, gemini, opencode)
    choose their own model, so a persona model never labels their rung.
    """
    if driver_name not in _LITELLM_DRIVERS:
        return None
    if persona_model:
        return persona_model
    return settings.agent_llm_model if driver_name == "local" else None


#: Drivers that run the persona's LiteLLM model themselves.
_LITELLM_DRIVERS = frozenset({"local", "cloud"})


def position(ladder: list[Rung], driver_name: str, model: str | None) -> int | None:
    """Where a run on (*driver_name*, *model*) stands on *ladder*; None = off it.

    An exact driver+model rung wins, then a driver-only rung; a run whose model
    isn't on the ladder stands at its driver's lowest rung (so the climb goes
    to that driver's next stronger model, or the next driver).
    """
    want = _norm_model(model)
    for i, rung in enumerate(ladder):
        if rung.driver == driver_name and rung.model and _norm_model(rung.model) == want:
            return i
    for i, rung in enumerate(ladder):
        if rung.driver == driver_name and not rung.model:
            return i
    for i, rung in enumerate(ladder):
        if rung.driver == driver_name:
            return i
    return None


def pin_state(persona: Any, driver_pin: str | None) -> tuple[bool, bool]:
    """``(pinned, pin_allows_escalation)`` for a dispatch.

    An arena racer (*driver_pin*) never climbs. A persona that names a driver
    (not ``auto``) is pinned; it climbs only when its ``properties`` set
    ``allow_escalation: true``. A persona's *model* alone is not a pin.
    """
    if driver_pin:
        return True, False
    if persona is None:
        return False, True
    pinned = getattr(persona, "driver", None) or (getattr(persona, "properties", None) or {}).get(
        "driver"
    )
    if not pinned or pinned == "auto":
        return False, True
    return True, bool((getattr(persona, "properties", None) or {}).get(PIN_ALLOWS_KEY))


def top_cap_allows(top_today: int, total_today: int) -> bool:
    """Whether one more dispatch may be sent to the top rung today.

    The limit is the larger of ``driver_escalation_top_daily_min`` and
    ``driver_escalation_top_share`` of today's dispatches (this one included).
    """
    share = float(settings.driver_escalation_top_share)
    limit = max(int(settings.driver_escalation_top_daily_min), int(share * (total_today + 1)))
    return top_today < limit


# ── Starting floor ────────────────────────────────────────────

# Path-like tokens in an instruction: something with a "/" or a file suffix.
_PATH_TOKEN = re.compile(
    r"[\w.*-]+(?:/[\w.*-]+)+/?"  # has a directory: app/x.py, .github/workflows/ci.yml
    r"|\.?[\w*-][\w.*-]*\.[A-Za-z0-9]{1,8}\b"  # a file name: pyproject.toml, .env.local
    r"|(?<![\w.])\.[A-Za-z][\w-]*"  # a dot file: .env
)


def mentioned_paths(text: str | None) -> list[str]:
    """Repository paths named in *text* (an instruction), in order, de-duplicated."""
    found: list[str] = []
    for m in _PATH_TOKEN.finditer(text or ""):
        path = m.group(0).strip("`'\",;:()[]").rstrip(".").removeprefix("./")
        if path and "://" not in path and path not in found:
            found.append(path)
    return found


def protected_reason(
    instruction: str | None, files: list[str] | None = None, extra: list[str] | None = None
) -> str | None:
    """``"protected path: <file>"`` when the task names a protected path, else None.

    Before a run only the instruction and any declared files are known; the
    project's own ``protected_paths`` (*extra*) count with the defaults.
    """
    candidates = [*(files or []), *mentioned_paths(instruction)]
    hits = protected_hits(candidates, extra)
    return f"protected path: {', '.join(hits[:3])}" if hits else None


# ── SHADOW router (placeholder; never consulted) ─────────────


def shadow_tier(
    *, instruction: str | None, task_type: str, protected: bool, failed_before: bool
) -> tuple[str, list[str]]:
    """SHADOW ONLY: the tier a future rules router *would* pick, with its reasons.

    A deliberately simple placeholder (decision step 7 is "later, after ~4
    weeks of outcome data"): it is written to ``dev_outcome_log.shadow_tier``
    so the real router can be calibrated against outcomes, and nothing reads
    it to route.
    """
    reasons: list[str] = []
    if protected:
        reasons.append("protected path")
    if failed_before:
        reasons.append("failed before")
    if reasons:
        return TIER_BEST, reasons
    text = instruction or ""
    if task_type in ("code", "code_change", "bugfix", "refactor", "feature") and (
        len(text) > 600 or len(mentioned_paths(text)) >= 3
    ):
        return TIER_BALANCED, ["long or multi-file code task"]
    return TIER_CHEAP, ["default"]
