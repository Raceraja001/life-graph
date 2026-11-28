"""Seed a fresh task worktree with other tasks' landed changes (Phase 4b).

docs/specs/agent-drivers.md, "Phase 4b". A parallel plan's workers each end
on their own ``lg/task-*`` branch (branch hand-off: committed locally, no PR,
no approval). Two things then start from those branches:

* a worker that depends on an earlier, overlapping worker starts from that
  worker's change: it is applied and **committed** as a seed commit, so the
  worker's own branch adds only its own delta on top;
* the plan's one **integration** task starts from every worker's change,
  applied in plan order and left **uncommitted**: the agent sees the whole
  change set as its working tree, resolves what conflicts, the normal verifier
  chain runs on all of it, and landing commits it as the plan's single PR.

Each change is ``git diff --binary <base> <head>`` of one hand-off (its own
delta) applied with ``git apply --3way``. A conflict leaves markers in the
files for the agent to resolve; the index is reset afterwards so the worktree
holds plain working-tree changes either way. The branches themselves are never
touched. Same hardened git as landing (no hooks, no fsmonitor): it runs on
the host inside a worktree the agent writes to. Rebuilt from race-app's
``agents/worktree-seed.ts`` (the owner's code).
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_BRANCH_RE = re.compile(r"^lg/task-[0-9a-f-]{1,36}$")
# A line git writes for a conflict (ours / theirs; the base marker with diff3).
_MARKER_RE = re.compile(r"^(<{7}|>{7}|\|{7})(?: |$)", re.MULTILINE)
_GIT_TIMEOUT = 120
_MAX_MARKER_FILE_BYTES = 2_000_000


@dataclass
class SeedResult:
    """What applying one hand-off did: ``applied`` | ``conflicts`` | ``empty`` | ``failed``."""

    task_id: str
    branch: str
    status: str
    files: list[str] = field(default_factory=list)
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["files"] = self.files[:50]
        if data["message"] is None:
            data.pop("message")
        return data


async def _git(cwd: Path | str, *args: str, timeout: int = _GIT_TIMEOUT) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args,
            cwd=str(cwd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )  # fmt: skip
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except (OSError, TimeoutError) as exc:
        return 1, "", str(exc)
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


async def apply_handoff(worktree: Path, handoff: dict[str, Any]) -> SeedResult:
    """Apply one hand-off's own change (``base..head``) to *worktree* with ``--3way``.

    *handoff* is a worker's ``result.metadata.handoff``: ``{task_id, branch,
    base_commit, head_commit}``. Never raises.
    """
    task_id = str(handoff.get("task_id") or "")
    branch = str(handoff.get("branch") or "")
    base, head = str(handoff.get("base_commit") or ""), str(handoff.get("head_commit") or "")

    def failed(message: str) -> SeedResult:
        return SeedResult(task_id, branch, "failed", message=message[:300])

    if not _BRANCH_RE.match(branch):
        return failed(f"not a task branch: {branch!r}")
    if not (_SHA_RE.match(base) and _SHA_RE.match(head)):
        return failed("the hand-off has no base/head commit")
    code, _o, _e = await _git(worktree, "cat-file", "-e", f"{head}^{{commit}}")
    if code != 0:
        return failed(f"commit {head[:8]} of {branch} does not exist")
    code, names, err = await _git(worktree, "diff", "--name-only", base, head)
    if code != 0:
        return failed(f"git diff failed: {err.strip()[:200]}")
    files = _lines(names)
    if not files:
        return SeedResult(task_id, branch, "empty")
    code, patch, err = await _git(worktree, "diff", "--binary", base, head)
    if code != 0:
        return failed(f"git diff failed: {err.strip()[:200]}")

    with tempfile.TemporaryDirectory(prefix="lg-seed-") as tmp:
        patch_file = Path(tmp) / "seed.patch"
        patch_file.write_text(patch, encoding="utf-8")
        # --3way needs index == working tree (an earlier seed left plain changes).
        code, _o, err = await _git(worktree, "add", "-A")
        if code != 0:
            return failed(f"git add failed: {err.strip()[:200]}")
        applied, _o, apply_err = await _git(
            worktree, "apply", "--3way", "--whitespace=nowarn", str(patch_file)
        )
        code, unmerged, _e = await _git(worktree, "diff", "--name-only", "--diff-filter=U")
        conflicted = _lines(unmerged) if code == 0 else []
        # Plain working-tree changes (markers included), never a half-merged index.
        await _git(worktree, "reset", "-q")
    if conflicted:
        return SeedResult(task_id, branch, "conflicts", files=conflicted)
    if applied != 0:
        return failed(f"git apply failed: {apply_err.strip()[:200]}")
    return SeedResult(task_id, branch, "applied", files=files)


async def apply_handoffs(worktree: Path, handoffs: list[dict[str, Any]]) -> list[SeedResult]:
    """Apply each hand-off in order (plan order); every result, failures included."""
    return [await apply_handoff(worktree, h) for h in handoffs]


async def commit_seed(worktree: Path, message: str) -> str | None:
    """Commit the seeded changes in *worktree* (a dependent worker's start); the new HEAD."""
    code, _o, _e = await _git(worktree, "add", "-A")
    if code != 0:
        return None
    code, _o, _e = await _git(worktree, "diff", "--cached", "--quiet")
    if code == 0:
        return None  # nothing seeded
    code, _o, err = await _git(
        worktree, "-c", "user.email=life-graph@localhost", "-c", "user.name=Life Graph",
        "commit", "--no-verify", "-m", message[:72],
    )  # fmt: skip
    if code != 0:
        logger.warning("Could not commit the seed in %s: %s", worktree, err.strip()[:200])
        return None
    code, out, _e = await _git(worktree, "rev-parse", "HEAD")
    return out.strip() if code == 0 else None


def unresolved_markers(worktree: Path, files: list[str]) -> list[str]:
    """Of *files* (worktree-relative), those that still hold conflict markers."""
    base = Path(worktree).resolve()
    left: list[str] = []
    for rel in files:
        path = (base / rel).resolve()
        if base not in path.parents or not path.is_file() or path.is_symlink():
            continue
        try:
            if path.stat().st_size > _MAX_MARKER_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _MARKER_RE.search(text):
            left.append(rel)
    return left


def seed_report(results: list[SeedResult]) -> str:
    """The note the agent gets: what applied cleanly and what conflicts."""
    lines = []
    for r in results:
        if r.status == "applied":
            lines.append(f"- {r.branch}: applied cleanly ({len(r.files)} file(s))")
        elif r.status == "conflicts":
            lines.append(
                f"- {r.branch}: CONFLICTS in {', '.join(r.files[:20])} -- the files hold "
                "<<<<<<< / >>>>>>> markers; resolve every one, keeping both changes' intent"
            )
        elif r.status == "empty":
            lines.append(f"- {r.branch}: no changes")
        else:
            lines.append(f"- {r.branch}: could not be applied ({r.message})")
    return "\n".join(lines)
