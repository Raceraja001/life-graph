"""The owner's autonomy policy: auto-approval conditions, daily cap, review stages, fix rounds.

docs/specs/agent-drivers.md, "Autonomy policy" (2026-11-27, owner decision D2).
Stored in ``autonomy_policies`` (migration 063): one global row and at most
one per project, written only by the owner (api: autonomy/policy/router.py).

What it may do, and what it may not:

* **Conditions only narrow** ``change_policy.auto_gate`` (CHARTER invariant 5).
  auto_gate first applies its own rules (protected paths, size, proof checks,
  trust per kind of change); only if those pass are the owner's conditions
  asked, and each one can only add a refusal reason. The global and the
  project conditions are evaluated separately and *both* must hold, so a
  project policy can never loosen the global one.
* **Reviewers may only veto** (invariant 1): a review stage's objection sends
  the change to a person (or back to its author for a bounded fix round);
  a stage that did not run counts against auto-approval, never for it;
  ``require_no_reviewer_objection`` asks that some reviewer looked and none
  objected -- the trust gate stays the reason anything lands.
* **Rounds are bounded** (:data:`MAX_FIX_ROUNDS`), budget- and kill-switch
  gated by the dispatcher, recorded as verification attempts, and never
  approve anything. Default 0 = the one-bounce rule, unchanged.
* **No row = no change.** With no policy row for the tenant, every function
  here answers "nothing to add", and the dispatcher behaves as before.

Deterministic: no LLM is consulted here.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select

from life_graph.autonomy.kill_switch import autonomy_stopped
from life_graph.core.redaction import redact_secrets
from life_graph.models.db import Approval, AutonomyPolicy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

GLOBAL_SCOPE = "global"
MAX_FIX_ROUNDS = 3
MAX_STAGES = 4
MAX_GLOBS = 50
MAX_GLOB_LENGTH = 200
MAX_CHANGED_LINES = 100_000
MAX_FILES = 10_000
MAX_DAILY_CAP = 1000
MAX_STAGE_NAME = 60
MAX_REVIEWER = 120
MAX_STAGE_FOCUS = 2000
# payload.autonomy.policy_note: why auto-open/auto-merge was refused (plain text).
MAX_POLICY_NOTE = 300
# The approval kinds auto_gate decides; plans have their own policy (plan_policy.py).
AUTO_KINDS = ("driver_pr", "driver_merge")
HUMAN_REVIEWER = "human"
PR_AGENT_REVIEWER = "pr_agent"
MODEL_PREFIX = "model:"

RiskTolerance = Literal["any", "warnings", "none"]


# ── The stored shape (also the API's request/response body) ─────────


class AutoApprovalConditions(BaseModel):
    """Extra conditions an unattended open/merge must meet. Each one only narrows.

    ``None`` / empty / ``False`` / ``"any"`` = the condition is off.
    """

    model_config = ConfigDict(extra="forbid")

    max_changed_lines: int | None = Field(None, ge=0, le=MAX_CHANGED_LINES)
    max_files: int | None = Field(None, ge=0, le=MAX_FILES)
    # Every changed file must match one of these (fnmatch; * also crosses "/",
    # the same globs as protected_paths).
    paths_allowed: list[str] = Field(default_factory=list, max_length=MAX_GLOBS)
    # No changed file may match any of these.
    paths_forbidden: list[str] = Field(default_factory=list, max_length=MAX_GLOBS)
    require_verification_passed: bool = False
    # Some reviewer (a review stage, or the code second opinion) looked at the
    # change and none objected. An LLM can only veto: this never approves.
    require_no_reviewer_objection: bool = False
    # "warnings": a block finding refuses; "none": any finding refuses.
    risk_tolerance: RiskTolerance = "any"

    @field_validator("paths_allowed", "paths_forbidden")
    @classmethod
    def _clean_globs(cls, value: list[str]) -> list[str]:
        out = [str(v).strip() for v in value if str(v).strip()]
        if any(len(v) > MAX_GLOB_LENGTH for v in out):
            raise ValueError(f"a glob may be at most {MAX_GLOB_LENGTH} characters")
        return list(dict.fromkeys(out))

    def is_neutral(self) -> bool:
        """True when no condition is set (this object refuses nothing)."""
        return self == AutoApprovalConditions()


class ReviewStage(BaseModel):
    """One ordered review stage, run where the second-opinion review runs."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=MAX_STAGE_NAME)
    # "human", "pr_agent", or "model:<model id>" (a veto-only LLM pass).
    reviewer: str = Field(..., min_length=1, max_length=MAX_REVIEWER)
    focus: str = Field("", max_length=MAX_STAGE_FOCUS)

    @field_validator("reviewer")
    @classmethod
    def _known_reviewer(cls, value: str) -> str:
        value = value.strip()
        if value in (HUMAN_REVIEWER, PR_AGENT_REVIEWER):
            return value
        if value.startswith(MODEL_PREFIX) and len(value) > len(MODEL_PREFIX):
            return value
        raise ValueError(
            f"reviewer must be '{HUMAN_REVIEWER}', '{PR_AGENT_REVIEWER}' or "
            f"'{MODEL_PREFIX}<model id>'"
        )


def _unique_stage_names(stages: list[ReviewStage] | None) -> None:
    names = [s.name.strip().lower() for s in stages or []]
    if len(names) != len(set(names)):
        raise ValueError("review stage names must be unique")


class ProjectAutonomyPolicy(BaseModel):
    """A project's policy. ``None`` for stages/rounds = use the global value."""

    model_config = ConfigDict(extra="forbid")

    conditions: AutoApprovalConditions = Field(default_factory=AutoApprovalConditions)
    review_stages: list[ReviewStage] | None = Field(None, max_length=MAX_STAGES)
    verify_fix_rounds: int | None = Field(None, ge=0, le=MAX_FIX_ROUNDS)
    review_fix_rounds: int | None = Field(None, ge=0, le=MAX_FIX_ROUNDS)

    @model_validator(mode="after")
    def _stages_unique(self) -> ProjectAutonomyPolicy:
        _unique_stage_names(self.review_stages)
        return self


class GlobalAutonomyPolicy(BaseModel):
    """The tenant-wide policy, including the daily cap across projects."""

    model_config = ConfigDict(extra="forbid")

    conditions: AutoApprovalConditions = Field(default_factory=AutoApprovalConditions)
    # Unattended opens/merges per UTC day across all projects, counted by task.
    # None = no cap; 0 = no auto-approval at all.
    daily_auto_approval_cap: int | None = Field(None, ge=0, le=MAX_DAILY_CAP)
    review_stages: list[ReviewStage] = Field(default_factory=list, max_length=MAX_STAGES)
    verify_fix_rounds: int = Field(0, ge=0, le=MAX_FIX_ROUNDS)
    review_fix_rounds: int = Field(0, ge=0, le=MAX_FIX_ROUNDS)

    @model_validator(mode="after")
    def _stages_unique(self) -> GlobalAutonomyPolicy:
        _unique_stage_names(self.review_stages)
        return self


# ── The effective policy for one task ──────────────────────────────


@dataclass(frozen=True)
class EffectivePolicy:
    """What applies to one task: the global row merged with its project's.

    ``conditions`` keeps both sources apart (each must hold on its own).
    """

    configured: bool = False
    conditions: tuple[tuple[str, AutoApprovalConditions], ...] = ()
    daily_cap: int | None = None
    review_stages: tuple[ReviewStage, ...] = ()
    # A "human" stage in the global OR the project list: never auto-approve.
    human_stage: bool = False
    verify_fix_rounds: int = 0
    review_fix_rounds: int = 0
    sources: tuple[str, ...] = field(default_factory=tuple)


NEUTRAL = EffectivePolicy()


def _parse(model: type[BaseModel], raw: Any, scope: str) -> BaseModel | None:
    try:
        return model.model_validate(raw or {})
    except Exception:  # noqa: BLE001 - a corrupt row must fail closed, see merge()
        logger.warning("autonomy_policies row %s does not validate", scope, exc_info=True)
        return None


def merge(global_raw: dict | None, project_raw: dict | None) -> EffectivePolicy:
    """The effective policy from the two stored rows (``None`` = no row). Pure.

    A row that no longer validates fails closed: it is read as "refuse every
    auto-approval" (a ``max_files=0`` condition) with no rounds and no stages.
    """
    if global_raw is None and project_raw is None:
        return NEUTRAL
    corrupt = AutoApprovalConditions(max_files=0)
    conditions: list[tuple[str, AutoApprovalConditions]] = []
    sources: list[str] = []
    stages: list[ReviewStage] = []
    human = False
    cap: int | None = None
    verify_rounds = review_rounds = 0

    g: GlobalAutonomyPolicy | None = None
    if global_raw is not None:
        sources.append(GLOBAL_SCOPE)
        g = _parse(GlobalAutonomyPolicy, global_raw, GLOBAL_SCOPE)  # type: ignore[assignment]
        if g is None:
            conditions.append((GLOBAL_SCOPE, corrupt))
        else:
            conditions.append((GLOBAL_SCOPE, g.conditions))
            cap = g.daily_auto_approval_cap
            stages = list(g.review_stages)
            verify_rounds, review_rounds = g.verify_fix_rounds, g.review_fix_rounds
            human = any(s.reviewer == HUMAN_REVIEWER for s in g.review_stages)
    if project_raw is not None:
        sources.append("project")
        p = _parse(ProjectAutonomyPolicy, project_raw, "project")
        if p is None:
            conditions.append(("project", corrupt))
            verify_rounds = review_rounds = 0
            stages = []
        else:
            conditions.append(("project", p.conditions))  # type: ignore[union-attr]
            if p.review_stages is not None:  # type: ignore[union-attr]
                stages = list(p.review_stages)  # type: ignore[union-attr]
                human = human or any(s.reviewer == HUMAN_REVIEWER for s in stages)
            if p.verify_fix_rounds is not None:  # type: ignore[union-attr]
                verify_rounds = p.verify_fix_rounds  # type: ignore[union-attr]
            if p.review_fix_rounds is not None:  # type: ignore[union-attr]
                review_rounds = p.review_fix_rounds  # type: ignore[union-attr]
    return EffectivePolicy(
        configured=True,
        conditions=tuple(conditions),
        daily_cap=cap,
        review_stages=tuple(stages),
        human_stage=human,
        verify_fix_rounds=min(max(int(verify_rounds), 0), MAX_FIX_ROUNDS),
        review_fix_rounds=min(max(int(review_rounds), 0), MAX_FIX_ROUNDS),
        sources=tuple(sources),
    )


# ── Storage ──────────────────────────────────────────────────


def _scope(project_id: Any) -> str | None:
    return str(project_id) if project_id else None


async def load_rows(session: AsyncSession, tenant_id: str, project_id: Any = None) -> dict:
    """``{scope: row}`` for the global row and the project's (tenant-scoped).

    Raises on a database error: callers decide how to fail closed.
    """
    scopes = [GLOBAL_SCOPE]
    if _scope(project_id):
        scopes.append(_scope(project_id))
    rows = (
        (
            await session.execute(
                select(AutonomyPolicy).where(
                    AutonomyPolicy.tenant_id == tenant_id, AutonomyPolicy.scope.in_(scopes)
                )
            )
        )
        .scalars()
        .all()
    )
    return {r.scope: r for r in rows if getattr(r, "tenant_id", None) == tenant_id}


async def load_effective(
    session: AsyncSession, tenant_id: str, project_id: Any = None
) -> EffectivePolicy:
    """The effective policy for a task in *project_id*. Raises on a DB error."""
    rows = await load_rows(session, tenant_id, project_id)
    g = rows.get(GLOBAL_SCOPE)
    p = rows.get(_scope(project_id)) if _scope(project_id) else None
    return merge(g.policy if g is not None else None, p.policy if p is not None else None)


async def save(
    session: AsyncSession,
    tenant_id: str,
    scope: str,
    policy: GlobalAutonomyPolicy | ProjectAutonomyPolicy,
    updated_by: str,
) -> Any:
    """Insert or replace the row for *scope*. The caller commits."""
    row = (
        await session.execute(
            select(AutonomyPolicy).where(
                AutonomyPolicy.tenant_id == tenant_id, AutonomyPolicy.scope == scope
            )
        )
    ).scalar_one_or_none()
    data = policy.model_dump(mode="json")
    now = datetime.now(UTC)
    if row is None:
        row = AutonomyPolicy(
            tenant_id=tenant_id,
            scope=scope,
            policy=data,
            updated_by=updated_by,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.policy = data
        row.updated_by = updated_by
        row.updated_at = now
    return row


async def delete(session: AsyncSession, tenant_id: str, scope: str) -> bool:
    """Remove the row for *scope*; True if there was one. The caller commits."""
    result = await session.execute(
        sa_delete(AutonomyPolicy).where(
            AutonomyPolicy.tenant_id == tenant_id, AutonomyPolicy.scope == scope
        )
    )
    return bool(getattr(result, "rowcount", 0))


def _utc_midnight(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


async def auto_approvals_today(
    session: AsyncSession, tenant_id: str, exclude_task_id: str | None = None
) -> int:
    """Tasks with an unattended open or merge since UTC midnight, all projects.

    Counted by task, not by approval: auto-opening and then auto-merging one
    task is one auto-approval. The task being decided is left out, so its
    merge is not refused by its own open. Raises on a database error.
    """
    stmt = select(func.count(Approval.source_ref.distinct())).where(
        Approval.tenant_id == tenant_id,
        Approval.kind.in_(AUTO_KINDS),
        Approval.status == "approved",
        Approval.resolved_by.like("auto:%"),
        Approval.resolved_at >= _utc_midnight(),
    )
    if exclude_task_id:
        stmt = stmt.where(Approval.source_ref != str(exclude_task_id))
    return int((await session.execute(stmt)).scalar() or 0)


# ── Evaluation (pure) ────────────────────────────────────────


def _reviewed(payload: dict[str, Any], change: dict[str, Any]) -> tuple[bool, list[str]]:
    """Whether some reviewer looked; and every objection/unavailable stage."""
    stages = ((payload.get("autonomy") or {}).get("review_stages")) or []
    problems = []
    looked = False
    for s in stages:
        verdict = s.get("verdict")
        if verdict == "no_objection":
            looked = True
        elif verdict == "objection":
            problems.append(f"review stage '{s.get('name')}' objected")
        elif verdict == "unavailable":
            problems.append(f"review stage '{s.get('name')}' could not run")
    note = str(change.get("second_opinion") or "")
    if note.startswith("second opinion: ok"):
        looked = True
    return looked, problems


def _size_and_path_reasons(
    cond: AutoApprovalConditions, change: dict[str, Any], tag: str
) -> list[str]:
    reasons: list[str] = []
    files = list(change.get("files") or [])
    lines = int(change.get("lines") or 0)
    if cond.max_changed_lines is not None and lines > cond.max_changed_lines:
        reasons.append(f"{tag}: {lines} changed lines (at most {cond.max_changed_lines})")
    if cond.max_files is not None and len(files) > cond.max_files:
        reasons.append(f"{tag}: {len(files)} files changed (at most {cond.max_files})")
    if cond.paths_allowed:
        outside = [f for f in files if not any(fnmatch.fnmatch(f, g) for g in cond.paths_allowed)]
        if outside:
            reasons.append(f"{tag}: outside the allowed paths: {', '.join(outside[:5])}")
        if not files:
            reasons.append(f"{tag}: no changed files to check against the allowed paths")
    if cond.paths_forbidden:
        hit = [f for f in files if any(fnmatch.fnmatch(f, g) for g in cond.paths_forbidden)]
        if hit:
            reasons.append(f"{tag}: touches forbidden paths: {', '.join(hit[:5])}")
    return reasons


def _risk_reasons(cond: AutoApprovalConditions, payload: dict[str, Any], tag: str) -> list[str]:
    if cond.risk_tolerance == "any":
        return []
    risk = (payload.get("autonomy") or {}).get("risk")
    if not risk or not risk.get("complete"):
        return [f"{tag}: no complete risk report for this change"]
    reasons = []
    if int(risk.get("block") or 0):
        reasons.append(f"{tag}: {risk['block']} blocking risk finding(s)")
    if cond.risk_tolerance == "none" and int(risk.get("warn") or 0):
        reasons.append(f"{tag}: {risk['warn']} risk warning(s)")
    return reasons


def condition_reasons(
    cond: AutoApprovalConditions, change: dict[str, Any], payload: dict[str, Any], label: str
) -> list[str]:
    """Why *cond* refuses this change (empty = it holds). Pure."""
    if cond.is_neutral():
        return []
    tag = f"owner rule ({label})"
    reasons = _size_and_path_reasons(cond, change, tag)
    if cond.require_verification_passed:
        passed = (
            payload.get("verified") is True
            and bool(payload.get("checks"))
            and not payload.get("unverifiable_checks")
        )
        if not passed:
            reasons.append(f"{tag}: verification did not pass")
    if cond.require_no_reviewer_objection:
        looked, _problems = _reviewed(payload, change)
        if not looked:
            reasons.append(f"{tag}: no reviewer looked at this change without objecting")
    reasons.extend(_risk_reasons(cond, payload, tag))
    return reasons


def policy_reasons(
    policy: EffectivePolicy,
    change: dict[str, Any],
    payload: dict[str, Any],
    *,
    auto_today: int | None = None,
    paused: bool = False,
) -> list[str]:
    """Every reason the owner's policy refuses this unattended open/merge. Pure.

    Empty when no policy is configured, whatever the change.
    """
    if not policy.configured:
        return []
    reasons: list[str] = []
    if paused:
        reasons.append("autonomy is paused (kill switch)")
    autonomy = payload.get("autonomy") or {}
    if policy.human_stage or autonomy.get("human_stage"):
        reasons.append("a human review stage is configured: a person approves this task")
    _looked, problems = _reviewed(payload, change)
    reasons.extend(problems)
    for label, cond in policy.conditions:
        reasons.extend(condition_reasons(cond, change, payload, label))
    if policy.daily_cap is not None:
        if auto_today is None:
            reasons.append("today's auto-approvals could not be counted")
        elif auto_today >= policy.daily_cap:
            reasons.append(
                f"daily auto-approval cap reached ({auto_today} of {policy.daily_cap} today)"
            )
    return reasons


async def owner_policy_reasons(
    session: AsyncSession, tenant_id: str, payload: dict[str, Any], change: dict[str, Any]
) -> list[str]:
    """The owner's refusals for one unattended open/merge, read from the database.

    Fails closed: a policy that cannot be read refuses (auto-approval waits
    for a person); with no policy row at all nothing is added.
    """
    try:
        policy = await load_effective(session, tenant_id, payload.get("project_id"))
    except Exception:  # noqa: BLE001 - an unreadable policy means "a person decides"
        logger.warning("Autonomy policy unreadable for %s; refusing", tenant_id, exc_info=True)
        return ["the owner's autonomy policy could not be read"]
    if not policy.configured:
        return []
    auto_today: int | None = None
    if policy.daily_cap is not None:
        try:
            auto_today = await auto_approvals_today(session, tenant_id, payload.get("task_id"))
        except Exception:  # noqa: BLE001
            logger.warning("Could not count auto-approvals for %s", tenant_id, exc_info=True)
    paused = await autonomy_stopped(tenant_id)
    return policy_reasons(policy, change, payload, auto_today=auto_today, paused=paused)


def describe(policy: EffectivePolicy) -> dict[str, Any]:
    """The effective policy as JSON, for the API."""
    return {
        "configured": policy.configured,
        "sources": list(policy.sources),
        "conditions": [
            {"source": label, **cond.model_dump(mode="json")} for label, cond in policy.conditions
        ],
        "daily_auto_approval_cap": policy.daily_cap,
        "review_stages": [s.model_dump(mode="json") for s in policy.review_stages],
        "human_stage": policy.human_stage,
        "verify_fix_rounds": policy.verify_fix_rounds,
        "review_fix_rounds": policy.review_fix_rounds,
    }


def limits() -> dict[str, Any]:
    """Every bound the models above enforce, for a UI to validate before PUT.

    The flat keys are the original shape (kept); ``bounds`` is keyed by field
    path (``[]`` = each item); ``reviewer_format`` is the reviewer grammar.
    """
    rounds = {"min": 0, "max": MAX_FIX_ROUNDS}
    globs = {"max_items": MAX_GLOBS, "item_max_length": MAX_GLOB_LENGTH}
    return {
        "max_fix_rounds": MAX_FIX_ROUNDS,
        "max_review_stages": MAX_STAGES,
        "max_globs": MAX_GLOBS,
        "reviewers": [HUMAN_REVIEWER, PR_AGENT_REVIEWER, f"{MODEL_PREFIX}<model id>"],
        "reviewer_format": {
            "kinds": [HUMAN_REVIEWER, PR_AGENT_REVIEWER, "model"],
            "model_prefix": MODEL_PREFIX,
            "max_length": MAX_REVIEWER,
        },
        "risk_tolerances": ["any", "warnings", "none"],
        "bounds": {
            "conditions.max_changed_lines": {"min": 0, "max": MAX_CHANGED_LINES},
            "conditions.max_files": {"min": 0, "max": MAX_FILES},
            "conditions.paths_allowed": globs,
            "conditions.paths_forbidden": globs,
            "daily_auto_approval_cap": {"min": 0, "max": MAX_DAILY_CAP},
            "review_stages": {"max_items": MAX_STAGES},
            "review_stages[].name": {"min_length": 1, "max_length": MAX_STAGE_NAME},
            "review_stages[].reviewer": {"min_length": 1, "max_length": MAX_REVIEWER},
            "review_stages[].focus": {"max_length": MAX_STAGE_FOCUS},
            "verify_fix_rounds": rounds,
            "review_fix_rounds": rounds,
        },
    }


# ── The refusal, kept on the approval ───────────────────────────


def policy_note(reason: str) -> str:
    """*reason* as stored on an approval: secrets redacted, one line, capped."""
    text = " ".join(redact_secrets(str(reason or "")).split())
    if len(text) > MAX_POLICY_NOTE:
        text = text[: MAX_POLICY_NOTE - 1].rstrip() + "\u2026"
    return text


def with_policy_note(payload: dict[str, Any] | None, reason: str | None) -> dict[str, Any]:
    """A copy of *payload* with ``autonomy.policy_note`` set (or removed for None).

    Returns a new dict so a JSON column sees the change. Set when auto_gate
    refuses an unattended open/merge; removed when a later check passes, so
    the note is never a stale refusal.
    """
    out = dict(payload or {})
    autonomy = dict(out.get("autonomy") or {})
    if reason:
        autonomy["policy_note"] = policy_note(reason)
    else:
        autonomy.pop("policy_note", None)
    if autonomy:
        out["autonomy"] = autonomy
    else:
        out.pop("autonomy", None)
    return out
