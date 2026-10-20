"""What an agent's change is, and whether it may land without a person.

Trust used to be one record per (driver, project): five easy test PRs a night
raised the local model's merge rate, and that same rate then let it
auto-merge changes to production code. The owner's rule (2026-10-20): agents
must not change our code without proof they understood it, and quality is
not traded for speed. So every landed change is described here, once, at
landing time, and both auto-open and auto-merge go through :func:`auto_gate`:

* **Kind of change** — ``tests``, ``docs`` or ``code``, from the files it
  touches. Each kind earns its own trust record
  (``agent_id = "<driver>:<kind>"``); test and doc trust fall back to the
  driver's older record (built almost entirely from test PRs), code trust
  never does, and needs :data:`CODE_MIN_OUTCOMES` merged PRs of its own.
* **Protected paths** — changes that touch them may be proposed, never landed
  unattended: auth and tenant scoping, the autonomy gate, the agent harness
  and the checks that judge it, migrations, CI, dependencies, configuration
  and the agent instructions. Defaults below, plus a project's own
  ``protected_paths``.
* **Size** — at most ``auto_merge_max_lines`` changed lines and
  ``auto_merge_max_files`` files land without a person.

None of this blocks the work: a change that fails the gate waits for review
as if auto-open/auto-merge were off, and the approval says why.
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

KINDS = ("tests", "docs", "code")
AUTO_MAX_LINES = 150
AUTO_MAX_FILES = 3
# Code trust is earned separately and needs more than the general bar of 3.
CODE_MIN_OUTCOMES = 5
# A code change lands unattended only if these ran (and passed: a landing
# with a failed or inconclusive check is never verified).
CODE_PROOF_CHECKS = ("diff_coverage", "change_explained")
_REVIEW_DIFF_MAX = 30_000

# Paths no agent change lands on unattended, in any project (fnmatch globs,
# where * also crosses "/").
DEFAULT_PROTECTED = (
    ".github/*",
    ".gitlab-ci.yml",
    "*migrations/*",
    "*alembic/*",
    "alembic.ini",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements*.txt",
    "uv.lock",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Dockerfile*",
    "docker-compose*",
    "*.env",
    ".env*",
    "AGENTS.md",
    "CLAUDE.md",
    "CHARTER.md",
)

_DOC_SUFFIXES = (".md", ".rst", ".txt")


def _is_test(rel: str) -> bool:
    from life_graph.services.verifiers import _is_test_path

    return _is_test_path(rel)


def _is_doc(rel: str) -> bool:
    p = PurePosixPath(rel)
    return (p.parts and p.parts[0] == "docs") or p.suffix.lower() in _DOC_SUFFIXES


def classify(files: list[str]) -> str:
    """``tests`` if every file is a test, ``docs`` if every file is
    documentation, else ``code``. Mixed tests+docs counts as tests; anything
    touching non-test, non-doc files is code. No files is code (nothing proven)."""
    if not files:
        return "code"
    if all(_is_test(f) for f in files):
        return "tests"
    if all(_is_doc(f) for f in files):
        return "docs"
    if all(_is_test(f) or _is_doc(f) for f in files):
        return "tests"
    return "code"


def protected_hits(files: list[str], extra: list[str] | None = None) -> list[str]:
    """The files that match a protected glob (defaults plus *extra*)."""
    patterns = [*DEFAULT_PROTECTED, *(extra or [])]
    return [f for f in files if any(fnmatch.fnmatch(f, p) for p in patterns)]


def policy_from_project(project_context: dict[str, Any] | None) -> dict[str, Any]:
    """The project's own settings for the gate (registry ``scan_metadata``)."""
    ctx = project_context or {}
    return {
        "protected_paths": [str(p) for p in ctx.get("protected_paths") or []],
        "max_lines": int(ctx.get("auto_merge_max_lines") or AUTO_MAX_LINES),
        "max_files": int(ctx.get("auto_merge_max_files") or AUTO_MAX_FILES),
    }


def review_reasons(change: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    """Why this change needs a person regardless of trust (empty = none)."""
    reasons = []
    if change.get("protected"):
        shown = ", ".join(change["protected"][:5])
        reasons.append(f"touches protected paths: {shown}")
    if change.get("lines", 0) > policy["max_lines"]:
        reasons.append(f"{change['lines']} changed lines (unattended limit {policy['max_lines']})")
    if len(change.get("files") or []) > policy["max_files"]:
        reasons.append(
            f"{len(change['files'])} files changed (unattended limit {policy['max_files']})"
        )
    return reasons


async def describe_change(
    repo_path: str,
    base_commit: str | None,
    head_commit: str | None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The landed change's files, size, kind and protected paths, from git.

    On any git failure the change is described as unknown ``code`` with a
    review reason, so the gate fails closed.
    """
    from life_graph.services.github_pr import _SHA_RE, _git

    policy = policy or policy_from_project(None)
    files: list[str] = []
    lines = 0
    ok = bool(_SHA_RE.match(base_commit or "") and _SHA_RE.match(head_commit or ""))
    if ok:
        code, out, _ = await _git(repo_path, "diff", "--numstat", base_commit, head_commit)
        ok = code == 0
        for row in out.splitlines() if ok else []:
            parts = row.split("\t")
            if len(parts) != 3:
                continue
            added, deleted, path = parts
            # "old => new" renames: judge the new path.
            path = path.split(" => ")[-1].replace("{", "").replace("}", "")
            files.append(path)
            lines += (int(added) if added.isdigit() else 0) + (
                int(deleted) if deleted.isdigit() else 0
            )
    change: dict[str, Any] = {
        "files": files,
        "lines": lines,
        "kind": classify(files),
        "protected": protected_hits(files, policy.get("protected_paths")),
    }
    reasons = review_reasons(change, policy)
    if not ok:
        reasons.append("the landed diff could not be read")
    change["review_reasons"] = reasons
    return change


def trust_key(driver: str, kind: str) -> str:
    """The TrustScore agent id one kind of change earns trust under."""
    return f"{driver}:{kind}"


async def kind_record(
    session: AsyncSession, tenant_id: str, driver: str, kind: str, project_id: str | None
) -> dict[str, Any]:
    """The track record that decides auto-open/auto-merge for this kind.

    Tests and docs fall back to the driver's older, undivided record until
    they have an established one of their own (that history is nearly all
    test PRs). Code never falls back, and needs CODE_MIN_OUTCOMES.
    """
    from life_graph.services.dev_outcomes import track_record

    record = await track_record(session, tenant_id, trust_key(driver, kind), project_id)
    if kind == "code":
        record = {**record, "established": record["total"] >= CODE_MIN_OUTCOMES}
    elif not record["established"]:
        legacy = await track_record(session, tenant_id, driver, project_id)
        if legacy["established"]:
            record = {**legacy, "fallback": True}
    return {**record, "kind": kind}


async def auto_gate(
    session: AsyncSession, tenant_id: str, payload: dict[str, Any]
) -> tuple[bool, str, dict[str, Any]]:
    """Whether a landed change may be opened/merged without a person.

    Returns ``(allowed, reason, record)``; the reason is for the approval's
    note either way. A payload from before this module (no ``change``) is
    described from git now, under the default policy.
    """
    from life_graph.drivers.dispatcher import AUTO_PR_MERGE_RATE

    change = payload.get("change")
    if not change:
        change = await describe_change(
            str(payload.get("repo_path") or ""),
            payload.get("base_commit"),
            payload.get("head_commit"),
        )
    reasons = list(change.get("review_reasons") or [])
    if change.get("kind", "code") == "code":
        # Production code lands unattended only with proof it is covered and
        # understood (services/proof_checks.py), never on "tests pass" alone.
        checks = set(payload.get("checks") or [])
        missing = [c for c in CODE_PROOF_CHECKS if c not in checks]
        if missing:
            reasons.append(f"no proof checks ran for this code change: {', '.join(missing)}")
    if reasons:
        return False, "needs review: " + "; ".join(reasons), {}
    driver = payload.get("driver") or "unknown"
    record = await kind_record(
        session, tenant_id, driver, change.get("kind", "code"), payload.get("project_id")
    )
    rate = record.get("merge_rate") or 0
    label = f"{driver} has {record['merged']}/{record['total']} {record['kind']} PRs merged"
    if not (record["established"] and rate >= AUTO_PR_MERGE_RATE):
        return False, f"not yet trusted for {record['kind']} changes: {label}", record
    return True, label, record


_REVIEW_PROMPT = """You review a code change an AI agent made, before it may be merged \
without a person looking at it. You can stop it; you cannot approve it on your own.

The task the agent was given:
{instruction}

The change (unified diff):
{diff}

Block it if any of these is true:
- it does more than, or something other than, what the task asks;
- it changes behaviour the task did not ask to change;
- it removes or weakens a check, validation, test, tenant filter or error handling;
- it could expose one tenant's or user's data to another;
- it is hard to follow, or looks wrong.

Answer with JSON only: {{"verdict": "ok" or "block", "reason": "one sentence"}}"""


async def second_opinion(instruction: str, diff: str) -> tuple[bool, str]:
    """An independent model's read of a code change that is about to land
    unattended. Advisory in one direction only (CHARTER invariant 1): "block"
    sends it to a person, "ok" adds nothing to the trust it already needed.

    Runs on the configured ``change_review_model``, else the free cloud
    models, else the local agent model, never a paid fallback. Fails closed:
    if no model answers, or the answer cannot be read, the change waits.
    """
    from life_graph.api.dependencies import get_resilient_llm
    from life_graph.config import settings
    from life_graph.services.compute_router import cloud_models
    from life_graph.services.resilient_llm import only_models

    models = [m for m in (settings.change_review_model, *cloud_models()) if m] or [
        settings.agent_llm_model
    ]
    prompt = _REVIEW_PROMPT.format(
        instruction=(instruction or "")[:4000], diff=(diff or "")[:_REVIEW_DIFF_MAX]
    )
    try:
        with only_models(models):
            text = await get_resilient_llm().chat(
                [{"role": "user", "content": prompt}],
                model=models[0],
                temperature=0,
                max_tokens=300,
            )
    except Exception as exc:  # noqa: BLE001 - any failure means "a person decides"
        logger.warning("Second-opinion review unavailable: %s", exc)
        return False, f"second-opinion review unavailable ({type(exc).__name__})"
    import json
    import re

    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    try:
        answer = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        answer = {}
    verdict = str(answer.get("verdict") or "").lower()
    reason = str(answer.get("reason") or "").strip()[:300]
    if verdict == "ok":
        return True, f"second opinion: ok ({reason})" if reason else "second opinion: ok"
    if verdict == "block":
        return False, f"second opinion: {reason or 'blocked'}"
    return False, "second-opinion review gave no readable verdict"
