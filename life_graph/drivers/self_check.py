"""Run the tests an agent added or changed before its dispatch ends.

Live runs on 2026-10-16/17 failed on the agent's own new test each time:
gpt-oss:20b and qwen3-coder both had ``run_tests`` and never called it, and
the dispatcher's one bounce ran out while each attempt fixed only the error
it had been shown. The user chose (2026-10-17) to have the harness run those
tests itself and send failures back, at most :data:`MAX_SELF_CHECKS` times,
inside the dispatch. The dispatcher's one-bounce rule and verifier chain are
unchanged; this runs before them.

Only the agent's own test files are run (fast, and what it can act on), in
the check-phase sandbox through :func:`life_graph.tools.run_tests.run_tests`.
No sandbox, or no changed tests: no check, the dispatch ends as before.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path, PurePosixPath

logger = logging.getLogger(__name__)

MAX_SELF_CHECKS = 2


def _is_test_file(rel: str) -> bool:
    p = PurePosixPath(rel)
    return p.suffix == ".py" and (p.name.startswith("test_") or p.name.endswith("_test.py"))


async def changed_tests(workdir: Path) -> list[str]:
    """Test files added or modified in *workdir* since HEAD (relative paths)."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "status",
        "--porcelain",
        "--untracked-files=all",
        cwd=str(workdir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return []
    found = []
    for line in out.decode(errors="replace").splitlines():
        status, rel = line[:2], line[3:].strip()
        if " -> " in rel:  # rename: the new path
            rel = rel.split(" -> ", 1)[1]
        rel = rel.strip('"')
        if "D" in status or not _is_test_file(rel) or not (workdir / rel).is_file():
            continue
        found.append(rel)
    return sorted(found)


# The checks cheap enough to run inside the dispatch. Task 5c760cb6
# (2026-10-17) passed everything but one unused variable, and the bounce, a
# fresh run, re-read the task, found it done and fixed nothing; in-session
# the agent still has the context to fix a lint error in one edit.
CHEAP_CHECKS = ("lint_clean_diff", "diff_within_scope", "tests_exercise_code", "no_test_weakening")


def task_of(instruction: str | None) -> str:
    """The original task: a bounce's instruction ends with it after a marker."""
    from life_graph.services.verifiers import BOUNCE_TASK_MARKER

    text = instruction or ""
    return text.split(BOUNCE_TASK_MARKER, 1)[1].strip() if BOUNCE_TASK_MARKER in text else text


async def _test_feedback(workdir: Path, project_context: dict) -> str | None:
    from life_graph.tools._guards import confine_to
    from life_graph.tools.run_tests import project_settings, run_tests

    tests = await changed_tests(workdir)
    if not tests:
        return None
    with confine_to(workdir), project_settings(project_context):
        raw = await run_tests(tests)
    try:
        result = json.loads(raw)
    except ValueError:
        return None
    if "error" in result:
        # The sandbox is off or unavailable: nothing to act on here; the
        # verifier chain reports it.
        logger.info("self-check tests skipped: %s", result["error"])
        return None
    if result.get("passed"):
        return None
    return (
        "The tests you added or changed fail:\n\n"
        f"{result.get('output', '').strip()}\n\n"
        "Fix them (the test or the code, whichever is wrong)."
    )


async def _check_feedback(workdir: Path, project_context: dict, instruction: str) -> str | None:
    from life_graph.services.verifiers import failure_text, mechanical_autofix, verifier_chain

    ctx = {**project_context, "scope_instruction": task_of(instruction)}
    # Free first: what ruff fixes by itself is not worth the agent's turn.
    await mechanical_autofix(workdir, ctx)
    results = await verifier_chain.run_chain(list(CHEAP_CHECKS), workdir, ctx)
    failed = [r for r in results if not r.passed and not getattr(r, "inconclusive", False)]
    if not failed:
        return None
    return "These checks fail on your change:\n\n" + "\n".join(failure_text(r) for r in failed)


async def check(workdir: Path, project_context: dict, instruction: str | None = None) -> str | None:
    """Feedback for the agent if its changed tests or the cheap checks fail."""
    parts = [
        p
        for p in (
            await _test_feedback(workdir, project_context),
            await _check_feedback(workdir, project_context, instruction or ""),
        )
        if p
    ]
    if not parts:
        return None
    return (
        "The harness checked your change before handing it on.\n\n"
        + "\n\n".join(parts)
        + "\n\nFix these in the files as they are now, then stop."
    )
