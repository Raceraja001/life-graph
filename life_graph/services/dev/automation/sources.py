"""Intake sources: what each kind polls, read-only, and how it is keyed.

- ``github_issues`` — open issues with a label (default ``life-graph``) in the
  project's repo, via the owner's ``gh`` (as services/dev/github_pr.py does;
  the GitHub connector plugin is token-based and never fetches bodies).
  Key ``github:<owner/repo>#<n>``. Commenting back is a separate, outward
  call made only when the source has ``commentOnIssue`` on.
- ``failing_ci`` — failed GitHub Actions runs on the project's base branch,
  the newest per workflow, with the failed jobs' log tail as the body.
  Key ``ci:<run id>``.
- ``life_graph_intentions`` — the tenant's active intentions (pending or
  triggered) the owner tagged for dev work, read from the ``intentions``
  table directly. Key ``lg:intention:<id>``.
- ``todo_comments`` — ``git grep`` for a marker (default ``TODO(race)``) in the
  base branch's tree, not the working copy (local uncommitted edits never
  become work; the nightly suggestions scan a worktree of ``HEAD`` and any
  TODO, which is a different job). Key ``todo:<path>:<line>:<hash>``.

Every poll raises on a failed command, so the runner can log it per source.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from life_graph.services.dev.automation.ports import Candidate
from life_graph.services.redaction import redact

if TYPE_CHECKING:
    from life_graph.services.dev.automation.ports import Exec, ExecResult, Intentions
    from life_graph.services.dev.automation.settings import IntakeSource

GH_TIMEOUT = 30.0
DEFAULT_ISSUE_LABEL = "life-graph"
DEFAULT_TODO_MARKER = "TODO(race)"
DEFAULT_INTENTION_TAG = "dev"
MAX_ITEMS = 50
LOG_LINES = 80
LOG_CHARS = 5000
TITLE_MAX = 300
BODY_MAX = 8000

_ISSUE_URL = re.compile(r"github\.com/([^/\s]+/[^/\s]+)/issues/(\d+)")
_ISSUE_KEY = re.compile(r"^github:([^#\s]+/[^#\s]+)#(\d+)$")
_TODO_KEY = re.compile(r"^todo:(.+):(\d+):([0-9a-f]+)$")
_GREP_LINE = re.compile(r"^(.+?):(\d+):(.*)$")
_PLACEHOLDER = re.compile(r"^(…|\.\.\.)")


class SourceError(RuntimeError):
    """A poll failed (the message is safe to log and show)."""


@dataclass
class SourceContext:
    tenant_id: str
    source: IntakeSource
    project: dict[str, Any]
    exec: Exec
    intentions: Intentions | None = None


def base_branch(project: dict[str, Any]) -> str:
    """The branch dev tasks are cut from: ``scan_metadata.base_branch``, else the
    registered branch, else ``main``."""
    meta = project.get("scan_metadata") or {}
    return str(meta.get("base_branch") or project.get("git_branch") or "main")


def _failure(argv: list[str], result: ExecResult) -> SourceError:
    what = " ".join(argv[:3])
    if result.timed_out:
        return SourceError(f"{what} timed out")
    detail = " ".join(result.stderr.strip().splitlines()[-3:])[:300]
    return SourceError(f"{what} exited {result.code}{': ' + detail if detail else ''}")


def tail(text: str, max_lines: int = LOG_LINES, max_chars: int = LOG_CHARS) -> str:
    lines = text.replace("\r", "").rstrip().split("\n")
    out = "\n".join(lines[-max_lines:])
    return out if len(out) <= max_chars else "…" + out[-(max_chars - 1) :]


def _json_list(stdout: str, what: str) -> list:
    try:
        raw = json.loads(stdout or "[]")
    except json.JSONDecodeError as exc:
        raise SourceError(f"{what} returned invalid JSON") from exc
    return raw if isinstance(raw, list) else []


def _str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


# ── github_issues ────────────────────────────────────────────


def issue_key(number: int, url: str | None, fallback_repo: str) -> str:
    match = _ISSUE_URL.search(url or "")
    return (
        f"github:{match.group(1) if match else fallback_repo}#{match.group(2) if match else number}"
    )


def parse_issue_key(key: str) -> tuple[str, int] | None:
    """``github:owner/repo#42`` → (repo, 42); None for any other key."""
    match = _ISSUE_KEY.match(key or "")
    return (match.group(1), int(match.group(2))) if match else None


def parse_issues(stdout: str, fallback_repo: str) -> list[Candidate]:
    out: list[Candidate] = []
    for issue in _json_list(stdout, "gh issue list"):
        if not isinstance(issue, dict):
            continue
        try:
            number = int(issue.get("number"))
        except (TypeError, ValueError):
            continue
        title = _str(issue.get("title"))
        if number <= 0 or not title:
            continue
        url = _str(issue.get("url"))
        out.append(
            Candidate(
                external_key=issue_key(number, url, fallback_repo),
                title=title[:TITLE_MAX],
                body=(_str(issue.get("body")) or None),
                url=url,
            )
        )
    return out


async def poll_github_issues(ctx: SourceContext) -> list[Candidate]:
    label = (ctx.source.filter or "").strip() or DEFAULT_ISSUE_LABEL
    argv = [
        "gh",
        "issue",
        "list",
        "--label",
        label,
        "--state",
        "open",
        "--limit",
        str(MAX_ITEMS),
        "--json",
        "number,title,body,url",
    ]
    result = await ctx.exec(argv, cwd=ctx.project.get("path"), timeout=GH_TIMEOUT)
    if result.code != 0:
        raise _failure(argv, result)
    return parse_issues(result.stdout, ctx.project.get("name") or ctx.project["id"])


async def issue_closed(exec_: Exec, cwd: str | None, key: str) -> str | None:
    """A reason when the issue behind *key* is closed; None when open or unknown."""
    issue = parse_issue_key(key)
    if issue is None:
        return None
    repo, number = issue
    argv = ["gh", "issue", "view", str(number), "--repo", repo, "--json", "state"]
    result = await exec_(argv, cwd=cwd, timeout=GH_TIMEOUT)
    if result.code != 0:
        return None
    try:
        state = json.loads(result.stdout or "{}").get("state")
    except (json.JSONDecodeError, AttributeError):
        return None
    return f"Issue {repo}#{number} was closed." if state == "CLOSED" else None


async def comment_on_issue(exec_: Exec, cwd: str | None, key: str, body: str) -> None:
    """Post one comment on the issue behind *key* (outward: callers gate on the setting)."""
    issue = parse_issue_key(key)
    if issue is None:
        raise SourceError(f"not a GitHub issue key: {key}")
    repo, number = issue
    argv = ["gh", "issue", "comment", str(number), "--repo", repo, "--body", body]
    result = await exec_(argv, cwd=cwd, timeout=GH_TIMEOUT)
    if result.code != 0:
        raise _failure(argv, result)


# ── failing_ci ───────────────────────────────────────────────

CI_TITLE_PREFIX = "Fix failing CI: "


def ci_title(workflow: str) -> str:
    return f"{CI_TITLE_PREFIX}{workflow}"[:TITLE_MAX]


def parse_runs(stdout: str) -> list[dict[str, str]]:
    """The newest failed run per workflow (``gh run list`` lists newest first)."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for run in _json_list(stdout, "gh run list"):
        if not isinstance(run, dict):
            continue
        run_id = run.get("databaseId")
        run_id = str(run_id) if isinstance(run_id, int) else _str(run_id)
        workflow = _str(run.get("workflowName")) or "CI"
        if not run_id or workflow in seen:
            continue
        seen.add(workflow)
        out.append(
            {
                "id": run_id,
                "workflow": workflow,
                "title": _str(run.get("displayTitle")) or "",
                "url": _str(run.get("url")) or "",
                "sha": _str(run.get("headSha")) or "",
            }
        )
    return out


def ci_body(run: dict[str, str], branch: str, log: str) -> str:
    head = [
        f'Workflow "{run["workflow"]}" failed on {branch}'
        + (f" at {run['sha'][:8]}" if run.get("sha") else "")
        + ".",
    ]
    if run.get("title"):
        head.append(f"Run: {run['title']}")
    if run.get("url"):
        head.append(f"Link: {run['url']}")
    log_part = (
        f"\n\nFailed job log (tail):\n```\n{tail(log)}\n```"
        if log.strip()
        else "\n\n(The failed job log was not available.)"
    )
    return "\n".join(head) + log_part


async def poll_failing_ci(ctx: SourceContext) -> list[Candidate]:
    branch = base_branch(ctx.project)
    cwd = ctx.project.get("path")
    argv = [
        "gh",
        "run",
        "list",
        "--branch",
        branch,
        "--status",
        "failure",
        "--limit",
        "10",
        "--json",
        "databaseId,workflowName,displayTitle,url,headSha",
    ]
    result = await ctx.exec(argv, cwd=cwd, timeout=GH_TIMEOUT)
    if result.code != 0:
        raise _failure(argv, result)
    out: list[Candidate] = []
    for run in parse_runs(result.stdout):
        log = await ctx.exec(
            ["gh", "run", "view", run["id"], "--log-failed"], cwd=cwd, timeout=GH_TIMEOUT
        )
        out.append(
            Candidate(
                external_key=f"ci:{run['id']}",
                title=ci_title(run["workflow"]),
                body=ci_body(run, branch, log.stdout if log.code == 0 else ""),
                url=run.get("url") or None,
            )
        )
    return out


async def ci_green(exec_: Exec, project: dict[str, Any], key: str, title: str) -> str | None:
    """A reason when a newer run of the item's workflow passed on the base branch."""
    try:
        run_id = int(key.removeprefix("ci:"))
    except ValueError:
        return None
    if not title.startswith(CI_TITLE_PREFIX):
        return None
    workflow = title[len(CI_TITLE_PREFIX) :]
    branch = base_branch(project)
    argv = [
        "gh",
        "run",
        "list",
        "--branch",
        branch,
        "--workflow",
        workflow,
        "--status",
        "success",
        "--limit",
        "1",
        "--json",
        "databaseId",
    ]
    result = await exec_(argv, cwd=project.get("path"), timeout=GH_TIMEOUT)
    if result.code != 0:
        return None
    try:
        runs = json.loads(result.stdout or "[]")
        newest = int(runs[0]["databaseId"]) if runs else None
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, IndexError):
        return None
    if newest is not None and newest > run_id:
        return f'A newer run of "{workflow}" passed on {branch}.'
    return None


# ── todo_comments ────────────────────────────────────────────


def marker_pattern(marker: str) -> str:
    """The grep pattern: the marker followed by a colon (``TODO(race):``)."""
    return marker if marker.endswith(":") else f"{marker}:"


def todo_text(line: str, marker: str) -> str:
    """The comment's own words after the marker, without comment closers."""
    at = line.find(marker)
    if at < 0:
        return ""
    rest = line[at + len(marker) :]
    rest = re.sub(r"^[\s:\-–—]+", "", rest)
    return re.sub(r"\s*(\*/|-->|#\})\s*$", "", rest).strip()


def todo_identity(key: str) -> str | None:
    """``todo:path:line:hash`` → ``path#hash`` (the line may move without the TODO changing)."""
    match = _TODO_KEY.match(key or "")
    return f"{match.group(1)}#{match.group(3)}" if match else None


def parse_git_grep(stdout: str, branch: str, marker: str) -> list[Candidate]:
    """Parse ``git grep -n <pattern> <branch>`` output (``branch:path:line:text``)."""
    out: list[Candidate] = []
    prefix = f"{branch}:"
    for raw in stdout.splitlines():
        if not raw.strip():
            continue
        line = raw[len(prefix) :] if raw.startswith(prefix) else raw
        match = _GREP_LINE.match(line)
        if not match:
            continue
        path, line_no, text = match.group(1), match.group(2), match.group(3).strip()
        words = todo_text(text, marker_pattern(marker))
        if not words or _PLACEHOLDER.match(words):
            continue
        digest = hashlib.sha1(text.encode()).hexdigest()[:10]
        out.append(
            Candidate(
                external_key=f"todo:{path}:{line_no}:{digest}",
                title=f"{words} ({path}:{line_no})"[:TITLE_MAX],
                body=(
                    f"{marker.rstrip(':')} comment in {path}:{line_no} on {branch}:\n\n{text}\n\n"
                    "Resolve it and remove the comment."
                ),
            )
        )
        if len(out) >= MAX_ITEMS:
            break
    return out


async def poll_todo_comments(ctx: SourceContext) -> list[Candidate]:
    marker = (ctx.source.filter or "").strip() or DEFAULT_TODO_MARKER
    branch = base_branch(ctx.project)
    path = ctx.project.get("path")
    argv = [
        "git",
        "-C",
        str(path),
        "-c",
        "core.fsmonitor=false",
        "grep",
        "-n",
        "-I",
        "-F",
        "-e",
        marker_pattern(marker),
        branch,
        "--",
    ]
    result = await ctx.exec(argv, cwd=path, timeout=GH_TIMEOUT)
    if result.code == 1 and not result.stderr.strip():
        return []  # no matches
    if result.code != 0:
        raise _failure(argv, result)
    return parse_git_grep(result.stdout, branch, marker)


# ── life_graph_intentions ────────────────────────────────────


def _intention_tags(context_match: Any) -> list[str]:
    if not isinstance(context_match, dict):
        return []
    tags = context_match.get("tags") or context_match.get("labels") or []
    if isinstance(tags, str):
        tags = [tags]
    return [str(t) for t in tags if isinstance(t, str)]


def match_intentions(
    rows: list[dict[str, Any]], tag: str, project: dict[str, Any]
) -> list[Candidate]:
    """Active intentions the owner tagged for dev work.

    An intention matches when its ``context_match`` names the project (by id or
    name) under ``project``, carries *tag* in ``tags``, or its text has
    ``#<tag>`` — an explicit opt-in per intention; nothing else is read.
    Secrets are redacted from the text before it becomes an instruction.
    """
    wanted = {tag.lower()}
    targets = {str(project.get("id") or "").lower(), str(project.get("name") or "").lower()}
    targets.discard("")
    out: list[Candidate] = []
    for row in rows:
        if row.get("status") not in ("pending", "triggered"):
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        cm = row.get("context_match") if isinstance(row.get("context_match"), dict) else {}
        named = str(cm.get("project") or "").lower()
        hit = (
            (named and named in targets | wanted)
            or any(t.lower() in wanted for t in _intention_tags(cm))
            or f"#{tag.lower()}" in content.lower()
        )
        if not hit:
            continue
        text = redact(content)
        out.append(
            Candidate(
                external_key=f"lg:intention:{row['id']}",
                title=text.splitlines()[0][:TITLE_MAX],
                body=text if "\n" in text or len(text) > TITLE_MAX else None,
            )
        )
        if len(out) >= MAX_ITEMS:
            break
    return out


async def poll_intentions(ctx: SourceContext) -> list[Candidate]:
    if ctx.intentions is None:
        raise SourceError("intentions are not available in this process")
    tag = (ctx.source.filter or "").strip() or DEFAULT_INTENTION_TAG
    rows = await ctx.intentions.active(ctx.tenant_id)
    return match_intentions(rows, tag, ctx.project)


POLLERS = {
    "github_issues": poll_github_issues,
    "failing_ci": poll_failing_ci,
    "todo_comments": poll_todo_comments,
    "life_graph_intentions": poll_intentions,
}


async def poll(ctx: SourceContext) -> list[Candidate]:
    """Poll one source (raises :class:`SourceError` or the exec's error on failure)."""
    return await POLLERS[ctx.source.kind](ctx)
