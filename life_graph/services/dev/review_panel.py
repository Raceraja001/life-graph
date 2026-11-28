"""Two-model review panel for risky diffs: independent local reviews, veto-only.

docs/specs/agent-drivers.md, "Review panel" (amendment 2026-11-28, step 6 of
the router/council decision, race-app
``docs/research/2026-11-28-router-council/04-decision.md``).

What it is. When a landing change is *risky* (:func:`risky_reasons`: the risk
report has a warn/block finding or is incomplete, the diff touches a protected
path, or it is larger than ``driver_review_panel_min_lines``), every model in
``driver_review_panel_models`` (default ``ollama_chat/qwen3:14b`` and
``ollama_chat/qwen3-coder:30b``) reviews the real diff **in parallel and blind
to the others** -- each answers ``objection``, ``approve`` or
``not_reviewed``, with a reason. The combine is deterministic
(:func:`aggregate`): **any objection = the panel objects; otherwise any
not-reviewed = the panel did not review; only all-approve approves.** No
chairman, no majority: a single dissenter cannot be outvoted.

Who it may stop (CHARTER invariant 1). The panel's "approve" never approves
anything: it adds no trust the change does not already need. Only an objection
or a not-reviewed verdict has an effect, and only in ``enforce`` mode, where it
routes the task to a person (drivers/review_stages.py). In ``shadow`` mode
(the first step, until outcome data shows the panel helps) the verdict is only
recorded, in the background, with a timeout, and gates nothing.

Where code goes (CHARTER invariant 7). Only local model ids run
(:func:`is_local_model`: ``ollama/``, ``ollama_chat/``); any other id in the
setting is refused and counts as ``not_reviewed`` for that member -- the
model is never called. Each call runs under ``only_models([model])``, so it
cannot fail over to a cloud or paid model. The prompt carries the task
instruction and the diff only: no memories, preferences or procedures.

The idea (independent proposers, no vote) comes from the Mixture-of-Agents
study (togethercomputer/MoA, Apache-2.0) and the multi-agent debate paper's
finding that reviewers who see each other agree too easily; no code was
ported from either.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from life_graph.config import settings
from life_graph.services.dev.change_policy import protected_hits
from life_graph.services.dev.risk_report import parse_unified_diff
from life_graph.services.llm.client import get_resilient_llm
from life_graph.services.llm.resilient import only_models

logger = logging.getLogger(__name__)

# Task property the panel's record is stored under (agent_tasks.properties).
PANEL_KEY = "review_panel"

OBJECTION = "objection"
APPROVE = "approve"
NOT_REVIEWED = "not_reviewed"
# Stored when the panel did not run on purpose (not risky, busy): not a verdict.
SKIPPED = "skipped"

MODES = ("off", "shadow", "enforce")

# Only runtimes on this machine. Deliberately not the configurable
# connector_local_model_prefixes: widening that list must not widen this one.
LOCAL_PREFIXES = ("ollama/", "ollama_chat/")

_DIFF_MAX = 30_000
_INSTRUCTION_MAX = 4_000
_REASON_MAX = 1_000
# Shadow panels in flight at once; more are recorded as skipped (one GPU).
MAX_SHADOW_IN_FLIGHT = 2

_PROMPT = """/no_think
You are one of several independent reviewers of a code change an AI agent \
made. You do not see the other reviewers. You can object; your approval alone \
never lands the change.

Review for:
- correctness: bugs, broken behaviour, missing error handling, wrong logic;
- security: injection, leaked secrets, missing authorisation or tenant checks, \
unsafe input handling;
- scope: changes the task did not ask for, or parts of the task left undone.

The task the agent was given:
{instruction}

The change (unified diff):
{diff}

Object only for a concrete, serious problem; name the file and what is wrong. \
Answer with JSON only: {{"verdict": "approve" or "object", "reason": "one or \
two sentences"}}"""

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

ChatFn = Callable[[str, str], Awaitable[str]]


@dataclass(frozen=True)
class MemberVerdict:
    """One panel member's review."""

    model: str
    verdict: str  # objection | approve | not_reviewed
    reason: str | None = None
    duration_ms: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "verdict": self.verdict,
            "reason": self.reason,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class PanelVerdict:
    """The panel's combined verdict (:func:`aggregate`)."""

    verdict: str  # objection | approve | not_reviewed
    reason: str | None = None
    members: tuple[MemberVerdict, ...] = field(default_factory=tuple)

    @property
    def needs_person(self) -> bool:
        """What ``enforce`` acts on: anything but a unanimous approval."""
        return self.verdict != APPROVE


def is_local_model(model: str | None) -> bool:
    """Whether *model* is a local runtime id the panel may call."""
    return bool(model) and str(model).strip().lower().startswith(LOCAL_PREFIXES)


def panel_models(raw: str | None = None) -> list[str]:
    """The configured member ids (``driver_review_panel_models``), in order, deduplicated."""
    text = settings.driver_review_panel_models if raw is None else raw
    out: list[str] = []
    for part in (text or "").split(","):
        model = part.strip()
        if model and model not in out:
            out.append(model)
    return out


# ── Which diffs the panel reviews (pure) ──────────────────────


def risky_reasons(
    report: Mapping[str, Any] | None,
    diff_text: str | None,
    *,
    protected_globs: list[str] | None = None,
    min_lines: int | None = None,
) -> list[str]:
    """Why this change is risky enough for the panel (empty = it is not).

    Reuses the risk report (services/dev/risk_report.py) and the gate's
    protected globs (change_policy.protected_hits). A missing or incomplete
    report counts as risky: "could not tell" is never "safe".
    """
    reasons: list[str] = []
    if not report:
        reasons.append("no risk report")
    else:
        if not report.get("complete", False):
            reasons.append("risk report incomplete")
        block, warn = int(report.get("block") or 0), int(report.get("warn") or 0)
        if block or warn:
            reasons.append(f"risk report: {block} block, {warn} warn")
    files = parse_unified_diff(diff_text or "")
    hits = protected_hits(list(files), protected_globs)
    if hits:
        reasons.append(f"touches protected paths: {', '.join(hits[:5])}")
    threshold = settings.driver_review_panel_min_lines if min_lines is None else min_lines
    lines = sum(len(info["added"]) + int(info["removed"]) for info in files.values())
    if lines > threshold:
        reasons.append(f"{lines} changed lines (panel threshold {threshold})")
    return reasons


# ── Aggregation (pure) ────────────────────────────────────────


def aggregate(members: list[MemberVerdict] | tuple[MemberVerdict, ...]) -> PanelVerdict:
    """Combine member verdicts: any objection objects; else any not-reviewed
    is not-reviewed; only a unanimous approval approves. No chairman, no vote.

    An empty panel did not review. An unknown member verdict counts as
    not-reviewed (never as approval).
    """
    ms = tuple(members)
    if not ms:
        return PanelVerdict(NOT_REVIEWED, "the panel has no members", ms)
    objections = [m for m in ms if m.verdict == OBJECTION]
    if objections:
        why = "; ".join(f"{m.model}: {m.reason or 'objection'}" for m in objections)
        return PanelVerdict(OBJECTION, why[:2000], ms)
    missing = [m for m in ms if m.verdict != APPROVE]
    if missing:
        why = "; ".join(f"{m.model}: {m.reason or 'not reviewed'}" for m in missing)
        return PanelVerdict(NOT_REVIEWED, why[:2000], ms)
    return PanelVerdict(APPROVE, None, ms)


def parse_member(model: str, text: str | None, duration_ms: int = 0) -> MemberVerdict:
    """A model's JSON answer as a member verdict; unreadable = not reviewed."""
    body = _THINK.sub("", text or "")
    match = re.search(r"\{.*\}", body, re.DOTALL)
    try:
        answer = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        answer = {}
    if not isinstance(answer, dict):
        answer = {}
    verdict = str(answer.get("verdict") or "").strip().lower()
    reason = str(answer.get("reason") or "").strip()[:_REASON_MAX] or None
    if verdict in ("approve", "approved", "ok"):
        return MemberVerdict(model, APPROVE, reason, duration_ms)
    if verdict in ("object", "objection", "block", "request_changes"):
        return MemberVerdict(model, OBJECTION, reason or "objection", duration_ms)
    return MemberVerdict(model, NOT_REVIEWED, "no readable verdict", duration_ms)


# ── Running it ────────────────────────────────────────────────


def build_prompt(instruction: str, diff_text: str) -> str:
    """The one prompt every member gets: the task instruction and the diff, nothing else."""
    return _PROMPT.format(
        instruction=(instruction or "").strip()[:_INSTRUCTION_MAX],
        diff=diff_text[:_DIFF_MAX],
    )


async def _chat_local(model: str, prompt: str) -> str:
    """One completion on *model* only (no failover to any other model)."""
    with only_models([model]):
        return await get_resilient_llm().chat(
            [{"role": "user", "content": prompt}],
            model=model,
            temperature=0,
            max_tokens=400,
        )


async def review_one(
    model: str,
    instruction: str,
    diff_text: str | None,
    *,
    timeout: float,
    chat: ChatFn | None = None,
) -> MemberVerdict:
    """One member's independent review. Never raises; any failure is not-reviewed."""
    if not is_local_model(model):
        return MemberVerdict(model, NOT_REVIEWED, "refused: not a local model")
    if not diff_text or not diff_text.strip():
        return MemberVerdict(model, NOT_REVIEWED, "no diff to review")
    call = chat or _chat_local
    start = time.monotonic()
    try:
        text = await asyncio.wait_for(call(model, build_prompt(instruction, diff_text)), timeout)
    except TimeoutError:
        ms = int((time.monotonic() - start) * 1000)
        return MemberVerdict(model, NOT_REVIEWED, f"timed out after {timeout:g}s", ms)
    except Exception as exc:  # noqa: BLE001 - any failure = this member did not review
        ms = int((time.monotonic() - start) * 1000)
        logger.warning("Review panel member %s unavailable: %s", model, exc)
        return MemberVerdict(model, NOT_REVIEWED, f"unavailable ({type(exc).__name__})", ms)
    return parse_member(model, text, int((time.monotonic() - start) * 1000))


async def run_panel(
    instruction: str,
    diff_text: str | None,
    *,
    models: list[str] | None = None,
    timeout: float | None = None,
    chat: ChatFn | None = None,
) -> PanelVerdict:
    """Every member reviews in parallel (blind to the others); then :func:`aggregate`."""
    ids = panel_models() if models is None else list(models)
    limit = float(settings.driver_review_panel_timeout_seconds if timeout is None else timeout)
    results = await asyncio.gather(
        *(review_one(m, instruction, diff_text, timeout=limit, chat=chat) for m in ids),
        return_exceptions=True,
    )
    members = [
        r
        if isinstance(r, MemberVerdict)
        else MemberVerdict(m, NOT_REVIEWED, f"unavailable ({type(r).__name__})")
        for m, r in zip(ids, results, strict=True)
    ]
    return aggregate(members)


# ── The stored record ─────────────────────────────────────────


def record(
    mode: str,
    verdict: PanelVerdict | None,
    *,
    risky: list[str] | None = None,
    skipped: str | None = None,
    gated: bool = False,
) -> dict[str, Any]:
    """What ``properties.review_panel`` holds for one dispatch.

    ``verdict`` is the panel's verdict, or ``skipped`` (with ``reason``) when
    it did not run on purpose. ``gated`` is True only when ``enforce`` acted
    on it (the task went to a person).
    """
    if verdict is None:
        return {
            "mode": mode,
            "verdict": SKIPPED,
            "reason": skipped,
            "risky": list(risky or []),
            "members": [],
            "gated": False,
            "at": datetime.now(UTC).isoformat(),
        }
    return {
        "mode": mode,
        "verdict": verdict.verdict,
        "reason": verdict.reason,
        "risky": list(risky or []),
        "members": [m.as_dict() for m in verdict.members],
        "gated": bool(gated),
        "at": datetime.now(UTC).isoformat(),
    }


def panel_for_outcome(task_properties: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The panel's verdict as the outcome log stores it, from a task's properties.

    For services/dev/outcomes.py: call with ``AgentTask.properties`` when the
    owner's decision is recorded, and store the result as the task's panel
    verdict next to that decision (what shadow mode is compared against).
    None when the panel never wrote a record for the task (mode off, or a
    shadow review still running). Pure, never raises.
    """
    try:
        rec = (task_properties or {}).get(PANEL_KEY)
        if not isinstance(rec, Mapping) or not rec.get("verdict"):
            return None
        members = [
            {"model": str(m.get("model")), "verdict": str(m.get("verdict"))}
            for m in rec.get("members") or []
            if isinstance(m, Mapping)
        ]
        return {
            "mode": str(rec.get("mode") or ""),
            "verdict": str(rec["verdict"]),
            "members": members,
            "risky": [str(r) for r in rec.get("risky") or []],
            "gated": bool(rec.get("gated")),
            "at": rec.get("at"),
        }
    except Exception:  # noqa: BLE001 - malformed stored JSON reads as "no record"
        return None


# ── Shadow runs (fire-and-record) ─────────────────────────────

_background: set[asyncio.Task[Any]] = set()


def in_flight() -> int:
    """Shadow panels still running."""
    return sum(not t.done() for t in _background)


def spawn(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    """Start a shadow panel without waiting for it (a strong reference is kept)."""
    task = asyncio.get_running_loop().create_task(coro, name="review-panel-shadow")
    _background.add(task)
    task.add_done_callback(_background.discard)
    return task


async def drain() -> None:
    """Wait for every shadow panel still running (tests, shutdown)."""
    while _background:
        await asyncio.gather(*list(_background), return_exceptions=True)
