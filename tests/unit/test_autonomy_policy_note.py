"""payload.autonomy.policy_note: why auto-open/auto-merge was refused, kept on
the approval the owner sees (docs/specs/agent-drivers.md, "Autonomy policy").

Set when auto_gate refuses (on the driver_pr when auto-open is refused, on the
driver_merge when auto-merge is), removed when a later check passes, never
inherited by the merge approval, plain one-line text of at most 300 characters
with secrets redacted.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.drivers import dispatch_approvals as da
from life_graph.services import approvals as approvals_mod
from life_graph.services.approvals import ApprovalService
from life_graph.services.dev import autonomy_policy as ap
from life_graph.services.dev import change_policy, local_merge
from tests.unit.fakes import FakeSession

REFUSAL = "owner policy: owner rule (global): 412 changed lines (at most 300)"


# ── the helpers ──────────────────────────────────────────────


def test_note_is_set_without_touching_the_rest_of_autonomy():
    payload = {"task_id": "t", "autonomy": {"risk": {"block": 0}}}
    out = ap.with_policy_note(payload, REFUSAL)
    assert out["autonomy"] == {"risk": {"block": 0}, "policy_note": REFUSAL}
    assert out is not payload and "policy_note" not in payload["autonomy"]  # a copy


def test_no_reason_removes_the_note_and_an_empty_autonomy():
    assert ap.with_policy_note({"autonomy": {"policy_note": "x"}}, None) == {}
    kept = ap.with_policy_note({"autonomy": {"policy_note": "x", "risk": {}}}, None)
    assert kept == {"autonomy": {"risk": {}}}
    assert ap.with_policy_note(None, None) == {}


def test_note_is_capped_one_line_and_has_no_secrets():
    long = "needs review: " + "; ".join(f"reason {i}" for i in range(100))
    note = ap.policy_note(long)
    assert len(note) == ap.MAX_POLICY_NOTE == 300 and note.endswith("…")
    assert ap.policy_note("a\n  b\tc") == "a b c"
    leaky = "second opinion: hard-coded api_key=sk-abcdefghijklmnopqrstuvwxyz0123 in config"
    note = ap.policy_note(leaky)
    assert "sk-abcdefghijklmnopqrstuvwxyz0123" not in note and "[REDACTED]" in note


# ── auto-open (dispatch_approvals._auto_open_pr) ─────────────


class _Host(da.ApprovalFilingMixin):
    async def _emit(self, *_a, **_k):
        return None


def _gate(monkeypatch, allowed: bool, why: str = REFUSAL):
    async def auto_gate(*_a):
        return allowed, why, {}

    monkeypatch.setattr(change_policy, "auto_gate", auto_gate)


@pytest.fixture
def github(monkeypatch):
    async def pr_mode(*_a):
        return "github"

    monkeypatch.setattr(local_merge, "pr_mode", pr_mode)


async def test_a_refused_auto_open_keeps_the_reason_on_the_pr_approval(monkeypatch, github):
    _gate(monkeypatch, False)
    appr = SimpleNamespace(
        tenant_id="t", status="pending", payload={"task_id": "t1", "autonomy": {"risk": {}}}
    )
    await _Host()._auto_open_pr(appr, "codex", None, FakeSession())
    assert appr.status == "pending"
    assert appr.payload["autonomy"] == {"risk": {}, "policy_note": REFUSAL}
    assert appr.payload["task_id"] == "t1"


async def test_an_allowed_auto_open_clears_an_old_note(monkeypatch, github):
    from life_graph.services.dev import github_pr

    _gate(monkeypatch, True, "trusted")

    async def open_pull_request(_payload):
        raise github_pr.PullRequestError("push failed")

    monkeypatch.setattr(github_pr, "open_pull_request", open_pull_request)
    appr = SimpleNamespace(
        tenant_id="t", status="pending", detail="d", payload={"autonomy": {"policy_note": "old"}}
    )
    await _Host()._auto_open_pr(appr, "codex", None, FakeSession())
    assert appr.status == "pending"  # the open failed, but the gate did not refuse
    assert "autonomy" not in appr.payload


# ── auto-merge (ApprovalService.maybe_auto_merge) ────────────


async def test_a_refused_auto_merge_keeps_the_reason_on_the_merge_approval(monkeypatch):
    _gate(monkeypatch, False)
    merge = SimpleNamespace(tenant_id="t", status="pending", payload={"verified": True})
    await ApprovalService(FakeSession()).maybe_auto_merge(merge, "codex", "p1", True)
    assert merge.status == "pending"
    assert merge.payload == {"verified": True, "autonomy": {"policy_note": REFUSAL}}


async def test_a_retry_that_passes_the_gate_clears_the_note(monkeypatch):
    _gate(monkeypatch, True, "trusted")

    async def merge_fails(self, appr, approve):
        raise approvals_mod.ApprovalActionError("CI still running")

    monkeypatch.setattr(ApprovalService, "_apply_driver_merge", merge_fails)
    merge = SimpleNamespace(
        tenant_id="t", status="pending", payload={"autonomy": {"policy_note": REFUSAL}}
    )
    await ApprovalService(FakeSession()).maybe_auto_merge(merge, "codex", "p1", True)
    assert merge.status == "pending" and "autonomy" not in merge.payload


async def test_no_auto_merge_asked_means_no_gate_and_no_note(monkeypatch):
    async def boom(*_a):
        raise AssertionError("auto_gate must not run")

    monkeypatch.setattr(change_policy, "auto_gate", boom)
    merge = SimpleNamespace(tenant_id="t", status="pending", payload={})
    await ApprovalService(FakeSession()).maybe_auto_merge(merge, "codex", "p1", False)
    assert merge.payload == {}


def test_the_merge_approval_does_not_inherit_the_pr_approvals_note():
    pr = SimpleNamespace(
        tenant_id="t",
        source_ref="t1",
        payload={
            "task_id": "t1",
            "branch": "lg/task-1",
            "pr_url": "https://github.com/o/r/pull/1",
            "autonomy": {"policy_note": REFUSAL, "risk": {"block": 0}},
        },
    )
    merge = ApprovalService(FakeSession()).file_merge_approval(pr)
    assert merge.payload["autonomy"] == {"risk": {"block": 0}}
    assert pr.payload["autonomy"]["policy_note"] == REFUSAL  # the PR's own stays
