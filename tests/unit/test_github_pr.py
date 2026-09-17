"""Approved task branches → pushed branch + pull request.

A local bare repository stands in for GitHub and a stub script stands in for
``gh``, so these exercise the real git plumbing without network access.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from types import SimpleNamespace

import pytest

from life_graph.services import approvals as approvals_mod
from life_graph.services import github_pr
from life_graph.services.github_pr import PullRequestError, describe_landing, open_pull_request


def git(cwd, *args):
    out = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """origin (bare) ← clone with master pushed, plus a landed lg/task branch."""
    from life_graph.config import settings

    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    repo = tmp_path / "root" / "repo"
    repo.parent.mkdir()
    git(tmp_path, "clone", "-q", str(origin), str(repo))
    git(repo, "checkout", "-q", "-b", "master")
    (repo / "f.txt").write_text("base\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    git(repo, "push", "-q", "origin", "master")

    branch = "lg/task-abcd1234"
    git(repo, "branch", branch)
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), branch)
    (wt / "f.txt").write_text("agent change\n")
    git(wt, "commit", "-qam", "agent change")
    git(repo, "worktree", "remove", "--force", str(wt))

    calls = tmp_path / "gh_calls.jsonl"
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:3] == ['pr', 'view']:\n"
        "    import os\n"
        f"    if not os.path.exists({str(tmp_path / 'pr_exists')!r}): sys.exit(1)\n"
        "    print('https://github.com/me/repo/pull/3'); sys.exit(0)\n"
        "if sys.argv[1:3] == ['pr', 'create']:\n"
        "    print('https://github.com/me/repo/pull/7')\n"
    )
    gh.chmod(0o755)
    monkeypatch.setattr(settings, "driver_gh_bin", str(gh))
    monkeypatch.setattr(settings, "tool_fs_roots", str(tmp_path / "root"))

    return SimpleNamespace(repo=repo, origin=origin, branch=branch, calls=calls, tmp=tmp_path)


async def _payload(s, **overrides):
    info = await describe_landing(s.repo, s.branch)
    return {
        "task_id": str(uuid.uuid4()),
        "driver": "claude_code",
        "instruction": "Fix the thing\nwith details",
        "summary": "Changed f.txt",
        "branch": s.branch,
        "repo_path": str(s.repo),
        "checks": ["tests_pass"],
        **info,
        **overrides,
    }


def _gh_calls(s):
    if not s.calls.exists():
        return []
    return [json.loads(line) for line in s.calls.read_text().splitlines()]


async def test_describe_landing_pins_commits_and_base(setup):
    info = await describe_landing(setup.repo, setup.branch)
    assert info["head_commit"] == git(setup.repo, "rev-parse", setup.branch)
    assert info["base_commit"] == git(setup.repo, "rev-parse", "master")
    assert info["base_branch"] == "master"


async def test_approve_pushes_exact_commit_and_opens_pr(setup):
    payload = await _payload(setup)
    out = await open_pull_request(payload)
    assert out == {"pr_url": "https://github.com/me/repo/pull/7", "existing": False}
    assert git(setup.origin, "rev-parse", setup.branch) == payload["head_commit"]
    create = next(c for c in _gh_calls(setup) if c[:2] == ["pr", "create"])
    assert create[create.index("--base") + 1] == "master"
    assert create[create.index("--head") + 1] == setup.branch
    assert create[create.index("--title") + 1] == "Fix the thing"
    assert "`tests_pass`" in create[create.index("--body") + 1]


async def test_existing_pr_is_returned_not_duplicated(setup):
    (setup.tmp / "pr_exists").write_text("")
    out = await open_pull_request(await _payload(setup))
    assert out["existing"] is True
    assert not any(c[:2] == ["pr", "create"] for c in _gh_calls(setup))


async def test_branch_moved_after_verification_is_not_pushed(setup):
    payload = await _payload(setup)
    wt = setup.tmp / "wt2"
    git(setup.repo, "worktree", "add", "-q", str(wt), setup.branch)
    (wt / "f.txt").write_text("unverified\n")
    git(wt, "commit", "-qam", "sneaky")
    with pytest.raises(PullRequestError, match="moved since it was verified"):
        await open_pull_request(payload)
    assert (
        subprocess.run(
            ["git", "rev-parse", "--verify", "-q", setup.branch], cwd=setup.origin
        ).returncode
        != 0
    )


async def test_unpushed_base_commits_block_the_pr(setup):
    """The PR would otherwise carry the user's own local commits."""
    git(setup.repo, "checkout", "-q", "master")
    (setup.repo / "local.txt").write_text("not pushed\n")
    git(setup.repo, "add", "-A")
    git(setup.repo, "commit", "-qm", "local only")
    git(setup.repo, "branch", "-f", setup.branch, "master")
    wt = setup.tmp / "wt3"
    git(setup.repo, "worktree", "add", "-q", str(wt), setup.branch)
    (wt / "f.txt").write_text("agent\n")
    git(wt, "commit", "-qam", "agent")
    git(setup.repo, "worktree", "remove", "--force", str(wt))

    with pytest.raises(PullRequestError, match="push that branch first"):
        await open_pull_request(await _payload(setup))


@pytest.mark.parametrize(
    "override, match",
    [
        ({"branch": "main"}, "unexpected branch"),
        ({"branch": "lg/task-x; rm -rf /"}, "unexpected branch"),
        ({"head_commit": "HEAD"}, "verified commit ids"),
        ({"base_branch": ""}, "detached HEAD"),
    ],
)
async def test_malformed_payload_refused(setup, override, match):
    with pytest.raises(PullRequestError, match=match):
        await open_pull_request(await _payload(setup, **override))


async def test_repo_outside_roots_refused(setup, tmp_path):
    with pytest.raises(PullRequestError, match="outside the permitted roots"):
        await open_pull_request(await _payload(setup, repo_path=str(tmp_path)))


# ── Approval handler ─────────────────────────────────────────


def _approval(payload):
    from life_graph.models.db import Approval

    return Approval(
        id=uuid.uuid4(),
        tenant_id="t",
        kind="driver_pr",
        title="Open PR",
        status="pending",
        source="driver",
        payload=payload,
    )


class _Session:
    def __init__(self, obj):
        self.obj = obj

    async def get(self, model, pk):
        return self.obj

    async def flush(self):
        pass


async def test_failed_pr_raises_so_approval_stays_retryable(monkeypatch):
    async def boom(payload):
        raise PullRequestError("gh is not installed")

    monkeypatch.setattr(github_pr, "open_pull_request", boom)
    appr = _approval({"branch": "lg/task-1"})
    service = approvals_mod.ApprovalService(_Session(appr))
    with pytest.raises(approvals_mod.ApprovalActionError, match="gh is not installed"):
        await service.resolve("t", str(appr.id), "approve")


async def test_successful_pr_records_url(monkeypatch):
    async def ok(payload):
        return {"pr_url": "https://github.com/me/repo/pull/9", "existing": False}

    monkeypatch.setattr(github_pr, "open_pull_request", ok)
    appr = _approval({"branch": "lg/task-1"})
    result = await approvals_mod.ApprovalService(_Session(appr)).resolve(
        "t", str(appr.id), "approve"
    )
    assert result["status"] == "approved"
    assert appr.payload["pr_url"].endswith("/pull/9")
    assert "pull/9" in appr.resolution_note


async def test_reject_never_pushes(monkeypatch):
    async def must_not_run(payload):
        raise AssertionError("rejecting must not push")

    monkeypatch.setattr(github_pr, "open_pull_request", must_not_run)
    appr = _approval({"branch": "lg/task-1"})
    result = await approvals_mod.ApprovalService(_Session(appr)).resolve(
        "t", str(appr.id), "reject"
    )
    assert result["status"] == "rejected"


# ── Dispatcher files the approval ────────────────────────────


class _NestedSession:
    def __init__(self):
        self.added = []

    def begin_nested(self):
        session = self

        class _CM:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *exc):
                return False

        return _CM()

    def add(self, obj):
        self.added.append(obj)


async def test_landed_task_files_driver_pr_approval_with_pinned_commits(setup):
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher

    session = _NestedSession()
    dispatcher = TaskDispatcher.__new__(TaskDispatcher)
    await dispatcher._create_pr_approval(
        tenant_id="raja",
        task_id="abcd1234-0000-0000-0000-000000000000",
        driver_name="claude_code",
        instruction="Add a helper\nmore",
        result=DriverResult(success=True, output="did it", cost_usd=0.12),
        branch=setup.branch,
        repo_path=str(setup.repo),
        checks=["build_ok_diff", "lint_clean_diff"],
        project_id=None,
        session=session,
    )
    (appr,) = session.added
    assert (appr.kind, appr.source, appr.tenant_id) == ("driver_pr", "driver", "raja")
    assert appr.title == "Open PR: Add a helper"
    p = appr.payload
    assert p["head_commit"] == git(setup.repo, "rev-parse", setup.branch)
    assert p["base_commit"] == git(setup.repo, "rev-parse", f"{setup.branch}^")
    assert p["base_branch"] == "master"
    # The filed payload is exactly what the approve handler accepts.
    out = await open_pull_request(p)
    assert out["pr_url"].endswith("/pull/7")
