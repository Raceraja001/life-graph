"""Unit tests for P2 Order 5: Durable Agent Execution, Recovery, and Independent Verification."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.drivers.execution_guard import (
    ExecutionCheckpointTracker,
    can_safely_retry,
    compute_idempotency_key,
    recover_interrupted_dispatch,
    validate_delegation_envelope,
    verify_independent_completion,
)


def test_agent_self_claim_never_proves_completion_without_independent_verification():
    # Agent claims success on code task, but changed 0 files -> rejected
    ok, reason = verify_independent_completion(
        driver_claimed_success=True,
        task_type="code",
        verifier_results=[SimpleNamespace(verifier="pytest", passed=True)],
        files_changed=[],
    )
    assert ok is False
    assert reason == "code_task_modified_zero_files"

    # Agent claims success on code task, changed files, but no independent verifier ran -> rejected
    ok, reason = verify_independent_completion(
        driver_claimed_success=True,
        task_type="code",
        verifier_results=[],
        files_changed=["life_graph/main.py"],
    )
    assert ok is False
    assert reason == "missing_independent_verifier_for_code_task"

    # Agent claims success, but ruff/pytest verifier failed -> rejected
    ok, reason = verify_independent_completion(
        driver_claimed_success=True,
        task_type="code",
        verifier_results=[
            SimpleNamespace(verifier="ruff", passed=True),
            SimpleNamespace(verifier="pytest", passed=False),
        ],
        files_changed=["life_graph/main.py"],
    )
    assert ok is False
    assert reason == "independent_verifier_failed:pytest"

    # All independent verifiers pass + non-empty file diff -> accepted
    ok, reason = verify_independent_completion(
        driver_claimed_success=True,
        task_type="code",
        verifier_results=[
            SimpleNamespace(verifier="ruff", passed=True),
            SimpleNamespace(verifier="pytest", passed=True),
        ],
        files_changed=["life_graph/main.py"],
    )
    assert ok is True
    assert reason == "independently_verified"


def test_ordered_checkpoints_and_restart_recovery_decisions():
    tracker = ExecutionCheckpointTracker(task_id="t-100", tenant_id="default", attempt=1)
    tracker.record("prepared")
    tracker.record("budget_checked")
    tracker.record("driver_executed")
    state = tracker.to_dict()
    assert state["last_completed_stage"] == "driver_executed"

    # Crash after driver_executed (before verification) -> must re-dispatch cleanly
    rec1 = recover_interrupted_dispatch(state)
    assert rec1["action"] == "re_dispatch_in_clean_worktree"
    assert rec1["already_landed"] is False

    # Crash after verifier_completed -> can proceed directly to landing
    tracker.record("worktree_verified")
    tracker.record("files_checked")
    tracker.record("verifier_completed")
    rec2 = recover_interrupted_dispatch(tracker.to_dict())
    assert rec2["action"] == "land_only"
    assert rec2["resume_from"] == "landed"

    # Crash after landed -> idempotent skip
    tracker.record("landed")
    rec3 = recover_interrupted_dispatch(tracker.to_dict())
    assert rec3["action"] == "skip_already_landed"
    assert rec3["already_landed"] is True

    with pytest.raises(ValueError, match="Unknown dispatch stage"):
        tracker.record("nonexistent_stage")


def test_idempotency_key_and_safe_retry_bounds():
    k1 = compute_idempotency_key("tenant_a", "task_1", "Fix   login   timeout")
    k2 = compute_idempotency_key("tenant_a", "task_1", "Fix login timeout")
    k3 = compute_idempotency_key("tenant_b", "task_1", "Fix login timeout")
    assert k1 == k2
    assert k1 != k3

    assert can_safely_retry(attempt=1, already_succeeded=True) == (
        False,
        "task_already_verified_complete",
    )
    assert can_safely_retry(attempt=3, max_retries=2) == (
        False,
        "max_retries_exceeded (3 > 2)",
    )
    assert can_safely_retry(attempt=1, failure_reason="worktree_tampered") == (
        False,
        "non_retryable_failure (worktree_tampered)",
    )
    assert can_safely_retry(attempt=1, failure_reason="timeout") == (
        True,
        "retry_permitted",
    )


def test_bounded_delegation_and_privilege_attenuation():
    # Cross-tenant delegation denied
    ok, reason = validate_delegation_envelope(
        parent_tenant_id="tenant_a",
        child_tenant_id="tenant_b",
        parent_task_id="p1",
        delegation_depth=1,
        allowed_tools=["file_read"],
        requested_tools=["file_read"],
    )
    assert ok is False
    assert reason == "cross_tenant_delegation_denied"

    # Depth exceeded denied
    ok, reason = validate_delegation_envelope(
        parent_tenant_id="tenant_a",
        child_tenant_id="tenant_a",
        parent_task_id="p1",
        delegation_depth=4,
        allowed_tools=["file_read"],
        requested_tools=["file_read"],
    )
    assert ok is False
    assert "delegation_depth_exceeded" in reason

    # Child requesting tools not held by parent denied
    ok, reason = validate_delegation_envelope(
        parent_tenant_id="tenant_a",
        child_tenant_id="tenant_a",
        parent_task_id="p1",
        delegation_depth=1,
        allowed_tools=["file_read"],
        requested_tools=["file_read", "run_command"],
    )
    assert ok is False
    assert reason == "privilege_escalation_denied:run_command"

    # Valid attenuated delegation permitted
    ok, reason = validate_delegation_envelope(
        parent_tenant_id="tenant_a",
        child_tenant_id="tenant_a",
        parent_task_id="p1",
        delegation_depth=2,
        allowed_tools=["file_read", "memory_search"],
        requested_tools=["file_read"],
    )
    assert ok is True
    assert reason == "delegation_valid"
