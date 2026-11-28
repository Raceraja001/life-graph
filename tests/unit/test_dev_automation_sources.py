"""Intake sources (services/dev/automation/sources.py): every poller with a fake exec."""

from __future__ import annotations

import json

import pytest

from life_graph.services.dev.automation import sources as src
from life_graph.services.dev.automation.settings import IntakeSource
from tests.unit.automation_fakes import PROJECT, PROJECT_ID, FakeExec, FakeIntentions, T


def _ctx(kind, exec_=None, filter=None, intentions=None):
    source = IntakeSource(id="s1", kind=kind, project_id=PROJECT_ID, filter=filter, enabled=True)
    return src.SourceContext(T, source, dict(PROJECT), exec_ or FakeExec(), intentions)


ISSUES = json.dumps(
    [
        {
            "number": 42,
            "title": "Crash on save",
            "body": "Steps…",
            "url": "https://github.com/raja/race-app/issues/42",
        },
        {"number": 7, "title": "  ", "url": "https://github.com/raja/race-app/issues/7"},
        {"number": "x", "title": "bad"},
        {"number": 9, "title": "No url"},
    ]
)


async def test_github_issues_polls_open_issues_with_the_label():
    exec_ = FakeExec().on("gh", "issue", "list", stdout=ISSUES)
    found = await src.poll(_ctx("github_issues", exec_, filter="bug"))
    assert [c.external_key for c in found] == ["github:raja/race-app#42", "github:race-app#9"]
    assert found[0].title == "Crash on save" and found[0].body == "Steps…"
    argv = exec_.calls[0]
    assert argv[argv.index("--label") + 1] == "bug"
    assert argv[argv.index("--state") + 1] == "open"
    assert "comment" not in argv  # read-only


async def test_github_issues_default_label_and_failure():
    exec_ = FakeExec().on("gh", "issue", "list", code=1, stderr="gh: not logged in")
    with pytest.raises(src.SourceError, match="exited 1: gh: not logged in"):
        await src.poll(_ctx("github_issues", exec_))
    assert exec_.calls[0][exec_.calls[0].index("--label") + 1] == src.DEFAULT_ISSUE_LABEL


async def test_github_issues_invalid_json_raises():
    exec_ = FakeExec().on("gh", "issue", "list", stdout="{nope")
    with pytest.raises(src.SourceError, match="invalid JSON"):
        await src.poll(_ctx("github_issues", exec_))


def test_issue_keys_round_trip():
    assert src.parse_issue_key("github:raja/race-app#42") == ("raja/race-app", 42)
    assert src.parse_issue_key("todo:a.py:1:abc") is None


async def test_issue_closed_and_comment():
    exec_ = FakeExec().on("gh", "issue", "view", stdout=json.dumps({"state": "CLOSED"}))
    reason = await src.issue_closed(exec_, "/repo", "github:raja/race-app#42")
    assert reason == "Issue raja/race-app#42 was closed."
    exec_.on("gh", "issue", "view", stdout=json.dumps({"state": "OPEN"}))
    assert await src.issue_closed(exec_, "/repo", "github:raja/race-app#42") is None
    exec_.on("gh", "issue", "view", code=1)
    assert await src.issue_closed(exec_, "/repo", "github:raja/race-app#42") is None
    exec_.on("gh", "issue", "comment")
    await src.comment_on_issue(exec_, "/repo", "github:raja/race-app#42", "hello")
    assert exec_.ran("comment", "42", "--body", "hello")


RUNS = json.dumps(
    [
        {"databaseId": 300, "workflowName": "CI", "displayTitle": "fix x", "headSha": "abcdef123"},
        {"databaseId": 200, "workflowName": "CI"},
        {"databaseId": 150, "workflowName": "Lint", "url": "https://gh/run/150"},
    ]
)


async def test_failing_ci_newest_failure_per_workflow_with_log_tail():
    log = "\n".join(f"line {i}" for i in range(200))
    exec_ = (
        FakeExec()
        .on("gh", "run", "list", stdout=RUNS)
        .on("gh", "run", "view", "300", stdout=log)
        .on("gh", "run", "view", "150", code=1)
    )
    found = await src.poll(_ctx("failing_ci", exec_))
    assert [c.external_key for c in found] == ["ci:300", "ci:150"]
    assert found[0].title == "Fix failing CI: CI"
    assert "failed on main at abcdef12" in found[0].body
    assert "line 199" in found[0].body and "line 100" not in found[0].body  # tail only
    assert "not available" in found[1].body and found[1].url == "https://gh/run/150"
    listed = exec_.calls[0]
    assert listed[listed.index("--branch") + 1] == "main"
    assert listed[listed.index("--status") + 1] == "failure"


async def test_ci_green_when_a_newer_run_passed():
    exec_ = FakeExec().on("gh", "run", "list", stdout=json.dumps([{"databaseId": 301}]))
    reason = await src.ci_green(exec_, PROJECT, "ci:300", "Fix failing CI: CI")
    assert reason == 'A newer run of "CI" passed on main.'
    exec_.on("gh", "run", "list", stdout=json.dumps([{"databaseId": 299}]))
    assert await src.ci_green(exec_, PROJECT, "ci:300", "Fix failing CI: CI") is None
    assert await src.ci_green(exec_, PROJECT, "ci:300", "Other title") is None


GREP = "\n".join(
    [
        "main:app/a.py:10:    # TODO(race): handle empty input",
        "main:app/b.ts:3:  // TODO(race): … placeholder",
        "main:docs/x.md:1:mentions TODO(race) only",
        "main:app/c.py:5:x = 1  # TODO(race): - drop this */",
    ]
)


async def test_todo_comments_git_grep_on_the_base_branch():
    exec_ = FakeExec().on("git", "grep", stdout=GREP)
    found = await src.poll(_ctx("todo_comments", exec_))
    assert len(found) == 2
    assert found[0].title == "handle empty input (app/a.py:10)"
    assert found[0].external_key.startswith("todo:app/a.py:10:")
    assert found[1].title == "drop this (app/c.py:5)"
    argv = exec_.calls[0]
    assert "TODO(race):" in argv and argv[-2:] == [
        "main",
        "--",
    ]  # the branch tree, not the checkout


async def test_todo_comments_no_match_and_error():
    exec_ = FakeExec().on("git", "grep", code=1)
    assert await src.poll(_ctx("todo_comments", exec_)) == []
    exec_.on("git", "grep", code=128, stderr="fatal: bad revision")
    with pytest.raises(src.SourceError, match="bad revision"):
        await src.poll(_ctx("todo_comments", exec_))


def test_todo_identity_ignores_line_moves():
    a = src.todo_identity("todo:app/a.py:10:abc123")
    assert a == src.todo_identity("todo:app/a.py:14:abc123") == "app/a.py#abc123"


async def test_intentions_native_tagged_for_dev_work(monkeypatch):
    rows = [
        {"id": "i1", "content": "Add dark mode #dev", "status": "pending"},
        {"id": "i2", "content": "Buy milk", "status": "pending"},
        {
            "id": "i3",
            "content": "Fix login",
            "status": "triggered",
            "context_match": {"tags": ["dev"]},
        },
        {
            "id": "i4",
            "content": "Refactor",
            "status": "pending",
            "context_match": {"project": "race-app"},
        },
        {"id": "i5", "content": "Done #dev", "status": "completed"},
        {
            "id": "i6",
            "content": "Rotate key\nuse sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA #dev",
            "status": "pending",
        },
    ]
    found = await src.poll(_ctx("life_graph_intentions", intentions=FakeIntentions(rows)))
    keys = [c.external_key for c in found]
    assert keys == ["lg:intention:i1", "lg:intention:i3", "lg:intention:i4", "lg:intention:i6"]
    assert "sk-ant-api03-AAAA" not in (found[-1].body or "")  # secrets redacted


async def test_intentions_custom_tag_and_unavailable():
    rows = [{"id": "i1", "content": "x #ops", "status": "pending"}]
    found = await src.poll(
        _ctx("life_graph_intentions", filter="ops", intentions=FakeIntentions(rows))
    )
    assert [c.external_key for c in found] == ["lg:intention:i1"]
    with pytest.raises(src.SourceError):
        await src.poll(_ctx("life_graph_intentions"))


def test_base_branch_fallbacks():
    assert src.base_branch({"scan_metadata": {"base_branch": "dev"}}) == "dev"
    assert src.base_branch({"git_branch": "trunk"}) == "trunk"
    assert src.base_branch({}) == "main"
