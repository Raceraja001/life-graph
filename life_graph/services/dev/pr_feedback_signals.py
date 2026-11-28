"""What is new on a watched pull request, and the one feedback message it becomes.

docs/specs/agent-drivers.md, "Phase 4b" (PR feedback loop). Pure: parsers of
``gh pr view --json state,mergeable,headRefOid,statusCheckRollup,reviews,comments``
and of ``gh api repos/<o>/<r>/pulls/<n>/comments`` (inline review comments),
the dedupe keys, and the message handed to ``continue_task``. The watcher
(services/dev/pr_watch.py) does the I/O.

Dedupe keys: ``check:<head sha>:<name>`` (a check failing again on a new head
is new), ``review:<id>`` / ``comment:<id>`` / ``inline:<id>``,
``conflict:<head sha>``. Rebuilt from race-app's
``automation/pr-watch/{gh-parse,signals}.ts`` (the owner's code).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

FAILED_CONCLUSIONS = frozenset(
    {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
)
FAILED_STATES = frozenset({"FAILURE", "ERROR"})
MAX_COMMENTS = 20
COMMENT_CHARS = 1500
MESSAGE_CHARS = 7900  # continue_task keeps at most 8000 characters of feedback
SUMMARY_CHARS = 300

_PR_URL_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)")
# What Life Graph itself writes on a PR (its PR body ends "opened by Life Graph
# after human approval"; anything it may comment starts with its name or the
# hidden marker) is not feedback.
_OWN_RE = re.compile(r"^\s*(?:life[ -]?graph\b|<!--\s*life-graph)", re.IGNORECASE)


@dataclass
class FailingCheck:
    """A failing check run or commit status on the PR's head."""

    name: str
    run_id: str | None = None
    url: str | None = None


@dataclass
class Comment:
    """A review, a PR comment or an inline review comment."""

    key: str
    kind: str  # review | comment | inline
    author: str
    body: str
    created_at: str | None = None
    review_state: str | None = None
    path: str | None = None
    line: int | None = None


@dataclass
class Snapshot:
    """One read of the PR."""

    state: str  # OPEN | MERGED | CLOSED
    mergeable: str
    head_sha: str
    failing_checks: list[FailingCheck] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)


@dataclass
class Signals:
    """What is new since the last round, and the keys to mark seen once sent."""

    checks: list[FailingCheck] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    conflict: bool = False
    keys: list[str] = field(default_factory=list)

    def any(self) -> bool:
        return bool(self.checks or self.comments or self.conflict)


def parse_pr_url(url: str) -> tuple[str, int] | None:
    """``https://github.com/o/r/pull/7`` -> ``("o/r", 7)``; anything else -> None."""
    m = _PR_URL_RE.match((url or "").strip())
    return (f"{m.group(1)}/{m.group(2)}", int(m.group(3))) if m else None


def is_own_comment(body: str) -> bool:
    """Life Graph's own text on a PR is not feedback."""
    return bool(_OWN_RE.match(body or ""))


def _obj(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _str(v: Any) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def _id(v: Any) -> str | None:
    return str(v) if isinstance(v, int) else _str(v)


def _login(v: Any) -> str:
    return _str(_obj(v).get("login")) or "someone"


def _run_id(url: str | None) -> str | None:
    m = re.search(r"/actions/runs/(\d+)", url or "")
    return m.group(1) if m else None


def parse_failing_checks(rollup: Any) -> list[FailingCheck]:
    """Failing entries of gh's ``statusCheckRollup`` (check runs and commit statuses)."""
    out: list[FailingCheck] = []
    names: set[str] = set()
    for entry in rollup if isinstance(rollup, list) else []:
        e = _obj(entry)
        is_status = e.get("__typename") == "StatusContext" or (
            e.get("context") is not None and not e.get("name")
        )
        failed = (
            str(e.get("state") or "").upper() in FAILED_STATES
            if is_status
            else str(e.get("conclusion") or "").upper() in FAILED_CONCLUSIONS
        )
        if not failed:
            continue
        base = _str(e.get("context") if is_status else e.get("name")) or "check"
        workflow = _str(e.get("workflowName"))
        name = f"{workflow} / {base}" if workflow and workflow != base else base
        if name in names:
            continue
        names.add(name)
        url = _str(e.get("targetUrl") if is_status else e.get("detailsUrl"))
        out.append(FailingCheck(name=name, run_id=_run_id(url), url=url))
    return out


def _reviews(raw: Any) -> list[Comment]:
    out = []
    for entry in raw if isinstance(raw, list) else []:
        r = _obj(entry)
        rid, state, body = _id(r.get("id")), str(r.get("state") or "").upper(), _str(r.get("body"))
        if not rid:
            continue
        # An approval is not a change request; an empty "commented" review only
        # wraps inline comments (read separately).
        if state != "CHANGES_REQUESTED" and not (state == "COMMENTED" and body):
            continue
        if body and is_own_comment(body):
            continue
        out.append(
            Comment(
                key=f"review:{rid}",
                kind="review",
                author=_login(r.get("author")),
                body=body or "",
                created_at=_str(r.get("submittedAt")),
                review_state=state,
            )  # fmt: skip
        )
    return out


def _issue_comments(raw: Any) -> list[Comment]:
    out = []
    for entry in raw if isinstance(raw, list) else []:
        c = _obj(entry)
        cid, body = _id(c.get("id")), _str(c.get("body"))
        if not cid or not body or is_own_comment(body):
            continue
        out.append(
            Comment(
                key=f"comment:{cid}",
                kind="comment",
                author=_login(c.get("author")),
                body=body,
                created_at=_str(c.get("createdAt")),
            )  # fmt: skip
        )
    return out


def parse_pr_view(data: Any) -> Snapshot:
    """``gh pr view --json ...`` (already JSON-decoded) -> :class:`Snapshot`."""
    pr = _obj(data)
    raw_state = str(pr.get("state") or "").upper()
    return Snapshot(
        state=raw_state if raw_state in ("MERGED", "CLOSED") else "OPEN",
        mergeable=str(pr.get("mergeable") or "UNKNOWN").upper(),
        head_sha=_str(pr.get("headRefOid")) or "",
        failing_checks=parse_failing_checks(pr.get("statusCheckRollup")),
        comments=[*_reviews(pr.get("reviews")), *_issue_comments(pr.get("comments"))],
    )


def parse_inline_comments(data: Any) -> list[Comment]:
    """The REST ``pulls/<n>/comments`` list -> inline :class:`Comment` rows."""
    out = []
    for entry in data if isinstance(data, list) else []:
        c = _obj(entry)
        cid, body = _id(c.get("id")), _str(c.get("body"))
        if not cid or not body or is_own_comment(body):
            continue
        line = c.get("line") if isinstance(c.get("line"), int) else None
        out.append(
            Comment(
                key=f"inline:{cid}",
                kind="inline",
                author=_login(c.get("user")),
                body=body,
                created_at=_str(c.get("created_at")),
                path=_str(c.get("path")),
                line=line,
            )  # fmt: skip
        )
    return out


def check_key(sha: str, name: str) -> str:
    return f"check:{sha}:{name}"


def conflict_key(sha: str) -> str:
    return f"conflict:{sha or 'unknown'}"


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def new_signals(
    snapshot: Snapshot,
    seen: set[str],
    since: datetime | None,
    *,
    on_checks: bool = True,
    on_comments: bool = True,
    on_conflicts: bool = True,
) -> Signals:
    """What on *snapshot* was not handed back yet (and is not older than *since*)."""
    out = Signals()
    if on_checks and snapshot.head_sha:
        for check in snapshot.failing_checks:
            key = check_key(snapshot.head_sha, check.name)
            if key not in seen:
                out.checks.append(check)
                out.keys.append(key)
    if on_comments:
        for c in snapshot.comments:
            if c.key in seen:
                continue
            at = _when(c.created_at)
            if at is not None and since is not None and at < since:
                continue
            out.comments.append(c)
            out.keys.append(c.key)
        out.comments.sort(key=lambda c: c.created_at or "")
    if on_conflicts and snapshot.mergeable == "CONFLICTING":
        key = conflict_key(snapshot.head_sha)
        if key not in seen:
            out.conflict = True
            out.keys.append(key)
    return out


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def summarize(signals: Signals) -> str:
    """e.g. ``2 failing checks: test, lint · 1 review comment · merge conflicts``."""
    parts = []
    if signals.checks:
        names = ", ".join(c.name for c in signals.checks)
        parts.append(f"{_plural(len(signals.checks), 'failing check')}: {names}")
    if signals.comments:
        parts.append(_plural(len(signals.comments), "review comment"))
    if signals.conflict:
        parts.append("merge conflicts")
    text = " · ".join(parts)
    return text if len(text) <= SUMMARY_CHARS else text[: SUMMARY_CHARS - 1] + "…"


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _comment_line(c: Comment) -> str:
    where = f" on {c.path}{f':{c.line}' if c.line else ''}" if c.kind == "inline" and c.path else ""
    what = " (changes requested)" if c.review_state == "CHANGES_REQUESTED" else ""
    body = _clip(c.body.replace("\r", ""), COMMENT_CHARS) if c.body else "(no text)"
    indented = "\n".join(f"  {line}" for line in body.split("\n"))
    return f"- @{c.author}{what}{where}:\n{indented}"


def build_feedback(
    *, pr_url: str, head_sha: str, base_branch: str, signals: Signals, logs: dict[str, str]
) -> str:
    """The one message a round hands to ``continue_task`` (≤ 7900 characters)."""
    out = [f"New feedback on your pull request {pr_url}."]
    if signals.checks:
        out.append(f"\n## Failing checks (head {head_sha[:8] or 'unknown'})")
        for check in signals.checks:
            out.append(f"- {check.name}" + (f" ({check.url})" if check.url else ""))
            log = logs.get(check.name)
            if log:
                out.append(f"  Failed step log (tail):\n```\n{log}\n```")
    if signals.comments:
        out.append("\n## Review comments")
        out.extend(_comment_line(c) for c in signals.comments[:MAX_COMMENTS])
        if len(signals.comments) > MAX_COMMENTS:
            out.append(f"- …and {len(signals.comments) - MAX_COMMENTS} more on the PR.")
    if signals.conflict:
        out.append(
            "\n## Merge conflicts\n"
            f"The branch conflicts with {base_branch}. Merge the base branch into this "
            f"branch (`git fetch origin {base_branch} && git merge origin/{base_branch}`), "
            "resolve every conflict, and make sure the build and tests still pass."
        )
    out.append(
        "\nAddress all of this in this worktree. Don't push or comment on the PR yourself: "
        "the owner reviews your change, and approving it updates the PR."
    )
    return _clip("\n".join(out), MESSAGE_CHARS)


def log_tail(text: str, lines: int = 60, chars: int = 3000) -> str:
    """The last *lines* lines of a log, at most *chars* characters."""
    tail = "\n".join(text.strip().splitlines()[-lines:])
    return tail[-chars:]
