# tests/integration/test_agent_task_real_workdir_e2e.py
"""End-to-end test for Tasks 1-8's tool-scoping/real-workdir chain.

Mocks only the LLM/orchestrator boundary (``TaskDispatcher.dispatch_task``,
mirroring ``test_action_roles_agent_task_e2e.py``'s (B2) own mocking style)
and the DB session (fake session boxes, same convention as
``tests/unit/test_agent_task_dispatch_failure.py``) — everything else,
including real ``git`` subprocesses for worktree isolation and the diff-scoped
verifier chain, is real.

Three scenarios:

  1. A ``Project`` row named ``"life-graph"`` is registered for the tenant
     (mocked session returns it) -> ``AutoFixService._resolve_repo_project_id``
     reaches it -> ``_run_action``'s call into ``TaskDispatcher.dispatch_task``
     carries ``project_id`` equal to that project's real UUID,
     ``isolate_workdir=True``, and ``verify_chain=["build_ok_diff",
     "lint_clean_diff"]``.

  2. No registered project -> the same call carries ``project_id=None`` and
     the dispatch still succeeds — today's fallback behavior, unbroken.

  3. A real, non-mocked flow: a temp git repo -> ``resolve_workdir`` (Task 6)
     with ``isolation=True`` produces a real git worktree containing the
     repo's committed files -> stage one new clean ``.py`` file into that
     worktree -> ``verifier_chain.run_chain(["build_ok_diff",
     "lint_clean_diff"], ...)`` (Task 5) passes against it — proving the
     "isolate -> verify only the diff" path holds together with no
     dispatcher/service mocking in the middle.
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.selectable import Select

from life_graph.autonomy.pipeline.service import AutoFixService
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.workdir import remove_worktree, resolve_workdir
from life_graph.services.verifiers import verifier_chain

if TYPE_CHECKING:
    from pathlib import Path

TENANT = "test_agent_task_real_workdir_e2e_tenant"


# ── Scenarios 1 & 2: _run_action -> dispatch_task kwargs ───────────────────


class _FakeResult:
    """Stand-in for a SQLAlchemy Result — both scalar accessors return the
    boxed value, matching the fake-result convention used throughout this
    branch's other fake-session test doubles."""

    def __init__(self, obj):
        self._obj = obj

    def scalar_one(self):
        return self._obj

    def scalar_one_or_none(self):
        return self._obj


class _FakeSession:
    """Async-context-manager session serving both queries ``_run_action``
    issues through ``self._session_factory()``:

    - ``select(Project.id).where(...)`` (from ``_resolve_repo_project_id``) ->
      returns whatever ``project_id`` this instance was built with (a real
      UUID, or ``None`` for the "no registered project" scenario).
    - ``update(AutoAction).where(...).values(...)`` (the final status/exit
      code persist) -> applied onto the single boxed ``AutoAction``, mirroring
      ``test_action_roles_agent_task_e2e.py``'s ``_DispatchFakeSession``.
    """

    def __init__(self, box: dict, project_id: uuid.UUID | None):
        self._box = box
        self._project_id = project_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def commit(self):
        pass

    async def execute(self, stmt):
        if isinstance(stmt, Update):
            action = self._box["action"]
            for key, value in stmt.compile().params.items():
                if hasattr(action, key):
                    setattr(action, key, value)
            return _FakeResult(action)
        if isinstance(stmt, Select):
            return _FakeResult(self._project_id)
        raise AssertionError(f"unexpected statement type in test double: {stmt!r}")


def _make_pending_agent_task_auto_action():
    """Bare object with the attributes ``_run_action`` reads/writes — mirrors
    ``test_action_roles_agent_task_e2e.py``'s helper of the same name."""
    return MagicMock(
        id="auto-1",
        tenant_id=TENANT,
        kind="agent_task",
        instruction="Investigate and fix the flaky test_worker_retry test",
        action_command=None,
        action_name="fix_flaky_test",
        agent_id="cody",
        project_id="ambient",
        risk_level="moderate",
        status="pending",
        approval_id=None,
        rollback_command=None,
        trigger_type="manual",
        trigger_detail="fix_flaky_test",
        started_at=None,
        completed_at=None,
        exit_code=None,
        stdout=None,
        stderr=None,
        error_message=None,
        duration_ms=None,
        created_at=datetime.now(UTC),
    )


def _make_service(session, dispatcher) -> AutoFixService:
    svc = AutoFixService.__new__(AutoFixService)
    svc._session_factory = lambda: session
    svc._executor = MagicMock()
    svc._audit_service = AsyncMock()
    svc._level_service = None
    svc._project_locks = {}
    svc._dispatcher = dispatcher
    return svc


@pytest.mark.asyncio
async def test_registered_project_resolves_real_uuid_and_requests_isolation():
    """A registered ``"life-graph"`` Project row -> _resolve_repo_project_id
    reaches it -> dispatch_task receives its real UUID, isolate_workdir=True,
    and the diff-scoped verify chain."""
    real_project_id = uuid.uuid4()
    auto_action = _make_pending_agent_task_auto_action()
    box = {"action": auto_action}
    session = _FakeSession(box, project_id=real_project_id)

    disp = MagicMock()
    disp.dispatch_task = AsyncMock(
        return_value=DriverResult(success=True, output="fixed it", cost_usd=0.01, duration_ms=1000)
    )
    svc = _make_service(session, disp)

    status, exit_code = await svc._run_action(TENANT, auto_action, timeout_seconds=60)

    disp.dispatch_task.assert_awaited_once()
    _, kwargs = disp.dispatch_task.await_args
    assert kwargs["project_id"] == str(real_project_id)
    assert kwargs["isolate_workdir"] is True
    assert kwargs["verify_chain"] == ["build_ok_diff", "lint_clean_diff"]
    assert kwargs["tenant_id"] == TENANT
    assert kwargs["persona_name"] == "cody"
    assert kwargs["interactive"] is False

    assert status == "success"
    assert exit_code == 0
    assert auto_action.status == "success"


@pytest.mark.asyncio
async def test_no_registered_project_falls_back_to_none_and_still_succeeds():
    """No registered project -> project_id=None on the dispatch call, and
    the dispatch still succeeds — today's fallback behavior, unbroken."""
    auto_action = _make_pending_agent_task_auto_action()
    box = {"action": auto_action}
    session = _FakeSession(box, project_id=None)

    disp = MagicMock()
    disp.dispatch_task = AsyncMock(
        return_value=DriverResult(success=True, output="fixed it", cost_usd=0.01, duration_ms=1000)
    )
    svc = _make_service(session, disp)

    status, exit_code = await svc._run_action(TENANT, auto_action, timeout_seconds=60)

    disp.dispatch_task.assert_awaited_once()
    _, kwargs = disp.dispatch_task.await_args
    assert kwargs["project_id"] is None
    assert (
        kwargs["isolate_workdir"] is True
    )  # requested unconditionally; workdir resolution degrades on its own
    assert kwargs["verify_chain"] == ["build_ok_diff", "lint_clean_diff"]

    assert status == "success"
    assert exit_code == 0
    assert auto_action.status == "success"


# ── Scenario 3: real resolve_workdir + real diff-scoped verify chain ───────


def _init_repo_with_committed_file(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    (repo / "committed.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "committed.py"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "seed"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


@pytest.mark.asyncio
async def test_real_isolate_then_diff_scoped_verify_holds_together(tmp_path):
    """Real git repo -> real worktree isolation -> real diff-scoped verify.

    No dispatcher, no AutoFixService, no mocked session anywhere in this
    scenario — it drives resolve_workdir and verifier_chain directly to
    confirm the isolate -> verify-only-the-diff path is sound end to end.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_committed_file(repo)

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    packet = ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id=TENANT,
        task_type="code",
        instruction="add a helper function",
        project_context={"path": str(repo), "isolation": True},
    )

    workdir, worktree = await resolve_workdir(packet, scratch)

    # A real worktree, distinct from the original repo and the scratch dir,
    # containing the repo's committed file.
    assert worktree is not None
    assert workdir == worktree
    assert workdir != repo
    assert (workdir / ".git").exists()
    assert (workdir / "committed.py").is_file()
    assert (workdir / "committed.py").read_text(encoding="utf-8") == "VALUE = 1\n"

    try:
        # One new, clean .py file — staged (not just written) so it shows up
        # in `git diff --name-only HEAD`: an untracked file would NOT appear
        # there at all, which is exactly the diff-scoped verifiers' contract
        # (see tests/unit/test_diff_scoped_verifiers.py).
        (workdir / "new_feature.py").write_text("def helper():\n    return 42\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "new_feature.py"],
            cwd=str(workdir),
            check=True,
            capture_output=True,
        )

        results = await verifier_chain.run_chain(["build_ok_diff", "lint_clean_diff"], workdir, {})

        assert [r.verifier for r in results] == ["build_ok_diff", "lint_clean_diff"]
        assert all(r.passed for r in results), results
    finally:
        await remove_worktree(packet, workdir)

    assert not workdir.exists()
