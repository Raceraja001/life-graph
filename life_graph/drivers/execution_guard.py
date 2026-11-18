"""Durable Agent Execution Guard, Checkpoints, Idempotency & Independent Verification (P2 Order 5).

Enforces the core reliability invariants from docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md:
1. Durable task state & ordered stage checkpoints for restart recovery.
2. Idempotency key deduplication & bounded retry eligibility.
3. Independent verification of outputs: an agent's claim that it finished a task
   never, by itself, proves that the task succeeded.
4. Bounded delegation depth & typed, permissioned inter-agent artifact handoffs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

ORDERED_DISPATCH_STAGES: tuple[str, ...] = (
    "prepared",
    "budget_checked",
    "driver_executed",
    "worktree_verified",
    "files_checked",
    "verifier_completed",
    "landed",
    "finished",
)

MAX_DELEGATION_DEPTH = 3
MAX_SAFE_RETRIES = 2


@dataclass(frozen=True)
class StageCheckpoint:
    stage: str
    recorded_at: str
    attempt: int
    ok: bool
    detail: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class ExecutionCheckpointTracker:
    """Tracks ordered execution checkpoints and serializes them for durable task properties."""

    task_id: str
    tenant_id: str
    attempt: int = 1
    checkpoints: list[StageCheckpoint] = field(default_factory=list)

    def record(
        self,
        stage: str,
        *,
        ok: bool = True,
        detail: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StageCheckpoint:
        if stage not in ORDERED_DISPATCH_STAGES:
            raise ValueError(f"Unknown dispatch stage: {stage!r}")
        cp = StageCheckpoint(
            stage=stage,
            recorded_at=datetime.now(UTC).isoformat(),
            attempt=self.attempt,
            ok=ok,
            detail=detail,
            metadata=dict(metadata) if metadata else None,
        )
        self.checkpoints.append(cp)
        return cp

    def record_stage(
        self,
        stage: str,
        *,
        metadata: dict[str, Any] | None = None,
        ok: bool = True,
        detail: str | None = None,
    ) -> StageCheckpoint:
        """Record one checkpoint with the structured facts the stage observed.

        The call site the dispatcher uses: ``metadata`` keeps the evidence the
        stage actually saw (cost cap, workdir, how many files changed) next to
        the checkpoint, so a restart decision can be audited from the persisted
        task properties rather than the logs.
        """
        return self.record(stage, ok=ok, detail=detail, metadata=metadata)

    @property
    def last_completed_stage(self) -> str | None:
        for cp in reversed(self.checkpoints):
            if cp.ok:
                return cp.stage
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "attempt": self.attempt,
            "last_completed_stage": self.last_completed_stage,
            "checkpoints": [
                {
                    "stage": c.stage,
                    "recorded_at": c.recorded_at,
                    "attempt": c.attempt,
                    "ok": c.ok,
                    "detail": c.detail,
                    "metadata": c.metadata,
                }
                for c in self.checkpoints
            ],
        }


def compute_idempotency_key(tenant_id: str, task_id: str, instruction: str) -> str:
    """Deterministic idempotency key for a tenant task execution."""
    norm = " ".join((instruction or "").strip().split())
    digest = hashlib.sha256(f"{tenant_id}:{task_id}:{norm}".encode()).hexdigest()
    return f"idem_{digest[:32]}"


def can_safely_retry(
    *,
    attempt: int,
    max_retries: int = MAX_SAFE_RETRIES,
    already_succeeded: bool = False,
    failure_reason: str | None = None,
) -> tuple[bool, str]:
    """Decide whether a task retry is safe and idempotent."""
    if already_succeeded:
        return False, "task_already_verified_complete"
    if attempt > max_retries:
        return False, f"max_retries_exceeded ({attempt} > {max_retries})"
    non_retryable = ("permission_denied", "tenant_mismatch", "worktree_tampered", "budget_exceeded")
    if failure_reason and any(nr in failure_reason.lower() for nr in non_retryable):
        return False, f"non_retryable_failure ({failure_reason})"
    return True, "retry_permitted"


def _has_resume_data(checkpoint_data: dict[str, Any]) -> bool:
    for cp in checkpoint_data.get("checkpoints") or []:
        if (
            isinstance(cp, dict)
            and cp.get("stage") == "verifier_completed"
            and cp.get("ok")
            and isinstance((cp.get("metadata") or {}).get("resume"), dict)
        ):
            return True
    return False


def recover_interrupted_dispatch(checkpoint_data: dict[str, Any] | None) -> dict[str, Any]:
    """Inspect a persisted checkpoint dictionary after a worker/process restart."""
    if not isinstance(checkpoint_data, dict):
        return {"action": "start_fresh", "resume_from": "prepared", "already_landed": False}
    # A dispatch that reached its end and failed is decided: re-running it
    # would only pay to fail again, and reading it as "finished" called it
    # completed.
    for cp in reversed(checkpoint_data.get("checkpoints") or []):
        if isinstance(cp, dict) and cp.get("stage") == "finished":
            if cp.get("ok") is False:
                return {"action": "already_failed", "resume_from": None, "already_landed": False}
            break
    last_stage = checkpoint_data.get("last_completed_stage")
    # Landed but not finished: the crash may have come before the PR approval
    # was filed. With resume data (dispatcher, verifier_completed metadata) the
    # runner files it without re-running anything; without it, close it out.
    if last_stage == "landed" and _has_resume_data(checkpoint_data):
        return {"action": "land_only", "resume_from": "landed", "already_landed": True}
    if last_stage in ("landed", "finished"):
        return {
            "action": "skip_already_landed",
            "resume_from": None,
            "already_landed": True,
        }
    if last_stage == "verifier_completed":
        return {
            "action": "land_only",
            "resume_from": "landed",
            "already_landed": False,
        }
    return {
        "action": "re_dispatch_in_clean_worktree",
        "resume_from": "prepared",
        "last_stage_before_crash": last_stage,
        "already_landed": False,
    }


def verify_independent_completion(
    *,
    driver_claimed_success: bool,
    task_type: str,
    verifier_results: list[Any] | None,
    files_changed: list[str] | None = None,
    require_verifier_for_code: bool = True,
    require_file_changes_for_code: bool = True,
) -> tuple[bool, str]:
    """Enforce that an agent's self-reported success never proves completion without independent verification.

    ``require_file_changes_for_code`` is for the one caller that genuinely
    cannot observe a diff -- a dispatch with no git worktree behind it, where
    ``files_changed`` would be unknown rather than empty. Everyone who can see
    the file list leaves it on; claiming zero changed files is never a pass.
    """
    if not driver_claimed_success:
        return False, "driver_reported_failure"

    is_code = (task_type or "").lower() in ("code", "bugfix", "refactor", "feature")
    changed = [f for f in (files_changed or []) if str(f).strip()]
    if is_code and require_file_changes_for_code and not changed:
        return False, "code_task_modified_zero_files"

    verifiers = list(verifier_results or [])
    if is_code and require_verifier_for_code and not verifiers:
        return False, "missing_independent_verifier_for_code_task"

    for v in verifiers:
        passed = getattr(v, "passed", None)
        if passed is None and isinstance(v, dict):
            passed = v.get("passed")
        name = getattr(v, "verifier", None) or (
            v.get("verifier") if isinstance(v, dict) else "verifier"
        )
        if passed is not True:
            return False, f"independent_verifier_failed:{name}"

    return True, "independently_verified"


def validate_delegation_envelope(
    *,
    parent_tenant_id: str,
    child_tenant_id: str,
    parent_task_id: str,
    delegation_depth: int,
    allowed_tools: list[str] | None,
    requested_tools: list[str] | None,
    max_depth: int = MAX_DELEGATION_DEPTH,
) -> tuple[bool, str]:
    """Validate bounded delegation depth, tenant isolation, and tool privilege attenuation."""
    if not parent_tenant_id or parent_tenant_id != child_tenant_id:
        return False, "cross_tenant_delegation_denied"
    if not parent_task_id:
        return False, "missing_parent_task_ownership"
    if delegation_depth > max_depth:
        return False, f"delegation_depth_exceeded ({delegation_depth} > {max_depth})"
    if allowed_tools is not None and requested_tools is not None:
        disallowed = sorted(set(requested_tools) - set(allowed_tools))
        if disallowed:
            return False, f"privilege_escalation_denied:{','.join(disallowed)}"
    return True, "delegation_valid"
