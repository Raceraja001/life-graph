"""Audit H7: the slow steps of filing/opening a PR run with no open transaction.

``_create_pr_approval`` drafts the PR description and asks for a second
opinion (model calls); ``_auto_open_pr`` pushes the branch and runs
``gh pr create``. Each must start with the session's transaction committed,
or Postgres holds a snapshot (and the new approval row) for the whole call.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.drivers import dispatch_approvals as da


class _Session:
    """Tracks whether a transaction is open: any statement opens one."""

    def __init__(self):
        self.open = True  # arrives mid-transaction, like the resume path
        self.commits = 0
        self.added = []

    def in_transaction(self):
        return self.open

    async def commit(self):
        self.commits += 1
        self.open = False

    def add(self, obj):
        self.open = True
        self.added.append(obj)

    def begin_nested(self):
        session = self

        class _Nested:
            async def __aenter__(self):
                session.open = True

            async def __aexit__(self, *exc):
                return False

        return _Nested()


class _Host(da.ApprovalFilingMixin):
    async def _emit(self, *_a, **_k):
        return None


@pytest.fixture
def seen():
    return []


@pytest.fixture
def wired(monkeypatch, seen):
    from life_graph.services import approvals as approvals_mod
    from life_graph.services.dev import change_policy, github_pr, local_merge

    session = _Session()

    async def pr_mode(sess, *_a):
        sess.open = True  # a read
        return "github"

    async def auto_gate(sess, *_a):
        sess.open = True  # a read
        return True, "trusted", None

    async def open_pull_request(payload):
        seen.append(("open_pull_request", session.in_transaction()))
        return {"pr_url": "https://example.invalid/pr/1", "existing": False}

    async def describe_landing(*_a, **_k):
        seen.append(("describe_landing", session.in_transaction()))
        return {"base_commit": "a" * 40, "head_commit": "b" * 40, "base_branch": "master"}

    async def draft(self, *_a):
        seen.append(("draft_pr_description", session.in_transaction()))
        return "desc"

    async def describe_change(*_a, **_k):
        return {"kind": "docs", "files": ["README.md"], "lines": 1, "review_reasons": []}

    class _Approvals:
        def __init__(self, _s):
            pass

        def file_merge_approval(self, appr):
            return SimpleNamespace(status="approved", tenant_id=appr.tenant_id)

        async def maybe_auto_merge(self, *_a, **_k):
            return None

    monkeypatch.setattr(local_merge, "pr_mode", pr_mode)
    monkeypatch.setattr(change_policy, "auto_gate", auto_gate)
    monkeypatch.setattr(github_pr, "open_pull_request", open_pull_request)
    monkeypatch.setattr(github_pr, "describe_landing", describe_landing)
    monkeypatch.setattr(da.ApprovalFilingMixin, "_draft_pr_description", draft)
    monkeypatch.setattr(da, "describe_change", describe_change)
    monkeypatch.setattr(approvals_mod, "ApprovalService", _Approvals)
    return session


@pytest.mark.asyncio
async def test_pr_filing_and_auto_open_hold_no_transaction(wired, seen):
    session = wired
    await _Host()._create_pr_approval(
        tenant_id="t",
        task_id="00000000-0000-0000-0000-000000000001",
        driver_name="d",
        instruction="fix the readme",
        result=SimpleNamespace(output="ok", cost_usd=0.0),
        branch="lg/task-1",
        repo_path="/tmp/repo",
        checks=["pytest"],
        project_id=None,
        session=session,
        verified=True,
        auto_open_pr=True,
    )
    assert [name for name, _ in seen] == [
        "describe_landing",
        "draft_pr_description",
        "open_pull_request",
    ]
    for name, in_tx in seen:
        assert in_tx is False, f"{name} ran inside an open transaction"
    # The driver_pr approval was filed, then auto-opened.
    (appr,) = session.added
    assert appr.kind == "driver_pr" and appr.status == "approved"


@pytest.mark.asyncio
async def test_end_transaction_leaves_a_closed_session_alone():
    s = _Session()
    s.open = False
    await da.end_transaction(s)
    assert s.commits == 0
    await da.end_transaction(SimpleNamespace())  # no in_transaction: a mock
