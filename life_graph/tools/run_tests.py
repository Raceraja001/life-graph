"""run_tests — let a coding agent run tests on its own change, in the sandbox.

Without it the agent learns that its test fails only from the verifier, one
bounce later, and has a single bounce to act on it: live runs on 2026-10-16
(tasks 71046102, dbffae5f, 144b5ed2) each fixed the last error and hit the
next one with no attempts left.

Tests run only in the check-phase sandbox the ``tests_pass`` verifier uses
(read-only worktree, no network) and only inside a dev task's confined
worktree. Never on the host: with the sandbox off the tool refuses. This adds
no trust: the verifier still runs the whole suite afterwards, whatever the
agent saw here.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from life_graph.tools._guards import _task_roots, check_tenant
from life_graph.tools.registry import tool

if TYPE_CHECKING:
    from collections.abc import Iterator

RUN_TIMEOUT = 600

# The project's sandbox settings (sandbox_setup, sandbox_toolchain) for the
# dev task being run; set by the driver around the agent loop.
_project: ContextVar[dict | None] = ContextVar("run_tests_project", default=None)


@contextmanager
def project_settings(ctx: dict) -> Iterator[None]:
    token = _project.set(dict(ctx))
    try:
        yield
    finally:
        _project.reset(token)


def _clean(paths: list[str]) -> list[str] | str:
    out = []
    for raw in paths:
        node = str(raw).strip()
        file_part = node.split("::", 1)[0]
        p = PurePosixPath(file_part)
        if not file_part or p.is_absolute() or ".." in p.parts or node.startswith("-"):
            return f"Not a test path inside the project: {raw!r}"
        out.append(node)
    return out


@tool(
    name="run_tests",
    description=(
        "Run pytest on specific test files or test ids (e.g. tests/unit/test_x.py or"
        " tests/unit/test_x.py::test_name) in the project's sandbox, and see why they"
        " fail. Use it to check a test you wrote before you finish."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Test files or ids, relative to the project root.",
            },
        },
        "required": ["paths"],
    },
    timeout_seconds=RUN_TIMEOUT + 60,
)
async def run_tests(paths: list[str] | str) -> str:
    from life_graph.services import sandbox
    from life_graph.services.verifiers import _test_evidence

    check_tenant("run_tests")
    roots = _task_roots.get()
    ctx = _project.get()
    if not roots or ctx is None:
        return json.dumps({"error": "run_tests works only inside a dev task's worktree"})
    if not sandbox.enabled():
        return json.dumps({"error": "tests run only in the sandbox, which is off here"})
    if (ctx.get("sandbox_toolchain") or "python") != "python":
        return json.dumps({"error": "run_tests supports Python projects only"})
    cleaned = _clean([paths] if isinstance(paths, str) else list(paths))
    if isinstance(cleaned, str):
        return json.dumps({"error": cleaned})
    if not cleaned:
        return json.dumps({"error": "Name at least one test file"})
    workdir = roots[0]
    try:
        venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
        result = await sandbox.run(
            ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short", *cleaned],
            workdir,
            venv=venv,
            timeout=RUN_TIMEOUT,
        )
    except sandbox.SandboxUnavailableError as exc:
        return json.dumps({"error": f"sandbox unavailable: {exc}"})
    return json.dumps(
        {
            "passed": result.returncode == 0,
            "returncode": result.returncode,
            "output": _test_evidence(result.stdout + result.stderr),
        }
    )
