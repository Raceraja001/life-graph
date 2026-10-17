"""Verifier Chain — quality gates for agent task results.

11 built-in verifiers. Each returns (passed: bool, evidence: dict).
One-bounce rule: failed → re-dispatch once → second failure → needs_human.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from life_graph.services import sandbox
from life_graph.services.acceptance import is_js_test_ref, is_safe_test_ref

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VerifierResult:
    """Result from a single verifier check.

    Attributes:
        verifier: Name of the verifier that produced this result.
        passed: Whether the verification passed. Always ``False`` when
            ``inconclusive``, so existing ``all_passed``-style checks stay
            correct without knowing about the third state.
        evidence: Supporting data for the pass/fail decision.
        inconclusive: The check could not be performed at all — the tool it
            needs is not installed, or is a different tool than the project
            uses. This is NOT a pass and NOT a failure of the agent's work.

            Without this state each verifier had to squeeze "could not
            check" into a boolean and they disagreed: lint_clean_diff
            returned True (a missing linter silently satisfied the gate),
            while lint_clean and tests_pass returned False (indistinguishable
            from the agent genuinely breaking the build, and unfixable by the
            re-dispatch it triggered).
    """

    verifier: str
    passed: bool
    evidence: dict
    inconclusive: bool = False


class VerifierChain:
    """Registry of verifiers that validate agent output.

    Verifiers are functions that accept a workdir and task context
    and return (passed, evidence). The chain runs them in order
    and collects results.
    """

    def __init__(self) -> None:
        self._verifiers: dict[str, callable] = {}
        self._register_builtins()

    def register(self, name: str, func: callable) -> None:
        """Register a named verifier function.

        Args:
            name: Unique verifier name.
            func: Async callable(workdir, ctx) -> (bool, dict).
        """
        self._verifiers[name] = func

    async def run_chain(
        self, chain: list[str], workdir: Path, task_context: dict
    ) -> list[VerifierResult]:
        """Run specified verifiers concurrently. Returns results in chain order.

        Verifiers are independent, read-only checks against the same
        workdir — none reads another's output or depends on another having
        run first — so there is nothing to serialize on. ``asyncio.gather``
        preserves input order in its result list regardless of completion
        order, so a caller indexing ``results[i]`` against ``chain[i]``
        (several do) keeps working unchanged.

        This is a real wall-clock win for sandboxed checks (``services.
        sandbox``, real async subprocesses — several Docker containers
        genuinely run at once). A verifier using a blocking ``subprocess.
        run`` still occupies the event loop for its own duration either
        way, so on a non-sandboxed host this is no worse than the previous
        sequential behavior, not a regression.

        Args:
            chain: Verifier names to run (order preserved in the result).
            workdir: Working directory for file-based checks.
            task_context: Task metadata (output, allowed_files, etc.).

        Returns:
            List of VerifierResult, one per verifier in chain, same order.
        """

        async def _run_one(name: str) -> VerifierResult:
            verifier = self._verifiers.get(name)
            if not verifier:
                return VerifierResult(name, False, {"error": f"Unknown verifier: {name}"})
            try:
                passed, evidence = await verifier(workdir, task_context)
            except Exception as e:
                logger.warning("Verifier %s failed: %s", name, e, exc_info=True)
                return VerifierResult(name, False, {"error": str(e)})
            if passed is None:
                # Sentinel: the verifier could not run its tool. Kept as a
                # 2-tuple so third-party verifiers registered against the
                # documented (bool, dict) contract keep working unchanged.
                return VerifierResult(name, False, evidence, inconclusive=True)
            return VerifierResult(name, bool(passed), evidence)

        return list(await asyncio.gather(*(_run_one(name) for name in chain)))

    def all_passed(self, results: list[VerifierResult]) -> bool:
        """Whether every verifier actually ran AND passed.

        An inconclusive check is not a pass: the gate did not happen.
        """
        return all(r.passed and not r.inconclusive for r in results)

    @staticmethod
    def inconclusive(results: list[VerifierResult]) -> list[VerifierResult]:
        """Checks that could not be performed. Re-dispatching cannot fix these."""
        return [r for r in results if r.inconclusive]

    @property
    def names(self) -> frozenset[str]:
        """Registered verifier names."""
        return frozenset(self._verifiers)

    def _register_builtins(self) -> None:
        """Register the built-in verifiers."""
        self.register("tests_pass", _verify_tests_pass)
        self.register("lint_clean", _verify_lint_clean)
        self.register("build_ok", _verify_build_ok)
        self.register("build_ok_diff", _verify_build_ok_diff)
        self.register("lint_clean_diff", _verify_lint_clean_diff)
        self.register("no_secrets_in_diff", _verify_no_secrets_in_diff)
        self.register("no_vulnerable_deps_in_diff", _verify_no_vulnerable_deps_in_diff)
        self.register("diff_within_scope", _verify_diff_within_scope)
        self.register("tests_exercise_code", _verify_tests_exercise_code)
        self.register("citations_present", _verify_citations_present)
        self.register("style_conforms", _verify_style_conforms)
        self.register("claims_evidenced", _verify_claims_evidenced)
        self.register("no_diff_in_plan", _verify_no_diff_in_plan)
        self.register("acceptance_tests_pass", _verify_acceptance_tests_pass)
        self.register("app_e2e_pass", _verify_app_e2e_pass)


# ── 9 Built-in Verifiers ─────────────────────────────────────
# ── Toolchain resolution ─────────────────────────────────────
#
# A verifier must run the TARGET project's toolchain, not Life Graph's and
# not whatever the server process happens to have on PATH. Running the wrong
# interpreter is worse than running none: Life Graph's venv has pytest but
# not the project's dependencies, so every test would fail on ImportError and
# the agent would be blamed for it. When no suitable tool is found the
# verifier reports inconclusive rather than guessing.

_VENV_DIRS: tuple[str, ...] = (".venv", "venv", "env")
_BIN_DIRS: tuple[str, ...] = ("bin", "Scripts")


def _project_tool(workdir: Path, tool: str) -> str | None:
    """Find *tool* in the project's own virtualenv, else on PATH."""
    for venv in _VENV_DIRS:
        for bindir in _BIN_DIRS:
            for name in (tool, f"{tool}.exe"):
                candidate = workdir / venv / bindir / name
                if candidate.is_file():
                    return str(candidate)
    return shutil.which(tool)


def _project_python(workdir: Path) -> str | None:
    """The interpreter the project's tests should run under."""
    for venv in _VENV_DIRS:
        for bindir, name in (("bin", "python"), ("Scripts", "python.exe")):
            candidate = workdir / venv / bindir / name
            if candidate.is_file():
                return str(candidate)
    # Deliberately NOT sys.executable: that is Life Graph's interpreter, which
    # carries none of the target project's dependencies.
    return shutil.which("python") or shutil.which("python3")


async def mechanical_autofix(workdir: Path, ctx: dict) -> dict:
    """Best-effort ``ruff --fix`` + ``ruff format`` on files changed since HEAD.

    Called by the dispatcher right before the one-bounce rule would spend a
    real driver call re-dispatching a failure — a lint/format issue a
    formatter fixes for free shouldn't burn a frontier call. Runs directly
    against *workdir* rather than through the check-phase sandbox
    (:func:`sandbox.run`), which mounts it read-only and cannot write a fix
    back; ruff is a trusted, well-known static tool operating only on the
    diff, not the agent's own code, so this crosses the same trust boundary
    the landing commit's git commands already do.

    Best-effort throughout: any failure here (no ruff available, a syntax
    error ruff can't parse, a timeout, ...) is swallowed and reported in the
    returned dict rather than raised — this must never be the reason a task
    fails when it otherwise wouldn't have.
    """
    changed = _changed_python_files(workdir)
    if not changed:
        return {"ran": False, "note": "no changed .py files"}

    ruff: str | None = None
    if sandbox.enabled():
        try:
            venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
            candidate = venv / "bin" / "ruff"
            ruff = str(candidate) if candidate.is_file() else None
        except sandbox.SandboxUnavailableError:
            ruff = None
    else:
        ruff = _project_tool(workdir, "ruff")

    if ruff is None:
        return {"ran": False, "note": "ruff not available for this project"}

    rel = [str(f.relative_to(workdir)) for f in changed]
    try:
        subprocess.run(
            [ruff, "check", "--fix", "--fix-only", "--", *rel],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(workdir),
        )
        subprocess.run(
            [ruff, "format", "--", *rel],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(workdir),
        )
    except Exception as exc:
        return {"ran": True, "fixed": False, "error": str(exc)}
    return {"ran": True, "fixed": True, "candidates": rel, "tool": ruff}


def _missing_module(result: subprocess.CompletedProcess, module: str) -> bool:
    """Whether the run failed because *module* is not installed.

    ``python -m pytest`` exits 1 for "No module named pytest" — the same code
    as a genuine test failure. Read literally that made an uninstalled test
    runner look exactly like broken code.
    """
    blob = f"{result.stdout}\n{result.stderr}"
    return f"No module named {module}" in blob


# ── Sandboxed execution ──────────────────────────────────────
#
# With LIFE_GRAPH_VERIFIER_SANDBOX=docker the checks that execute anything run
# in a container (services/sandbox.py). Inside it the toolchain is the
# project's cached venv, else the image's own — never a binary from the
# worktree: a fresh worktree has no .venv, so one found there was planted.

# The git queries below stay on the host (they only list files); a repo's
# config must not make them execute anything.
_HARDENED_GIT = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null"]


_DEFAULT_TEST_ARGV = [
    "python",
    "-m",
    "pytest",
    ".",
    "-q",
    "--tb=no",
    "-x",
    "-p",
    "no:cacheprovider",
]
_DEFAULT_TEST_TIMEOUT = 300
# A Node project's own `test` script (package.json) is "the tests".
_DEFAULT_NODE_TEST_ARGV = ["npm", "test", "--silent"]


async def _sandboxed_tests(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    # The project registry may narrow what "the tests" are — a suite whose
    # integration tests need a database cannot pass in a network-less sandbox,
    # which made tests_pass unusable for such projects. Never read from the
    # worktree: the agent controls it.
    command = ctx.get("sandbox_test_command")
    node = sandbox.node_toolchain(ctx)
    default = _DEFAULT_NODE_TEST_ARGV if node else _DEFAULT_TEST_ARGV
    try:
        argv = shlex.split(command) if command else default
    except ValueError as exc:
        return None, {"note": f"sandbox_test_command does not parse: {exc}"}
    if not argv:
        argv = default
    timeout = int(ctx.get("sandbox_test_timeout") or _DEFAULT_TEST_TIMEOUT)
    try:
        if node:
            deps = await sandbox.prepare_node_env(workdir, ctx.get("sandbox_setup"))
            result = await sandbox.run(argv, workdir, node_deps=deps, timeout=timeout)
        else:
            venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
            result = await sandbox.run(argv, workdir, venv=venv, timeout=timeout)
    except sandbox.SandboxUnavailableError as exc:
        return None, {"note": str(exc), "sandbox": "docker", "command": argv}
    if not node and _missing_module(result, "pytest"):
        return None, {"note": "pytest is not installed in the project environment"}
    return result.returncode == 0, {
        "stdout": _test_evidence(result.stdout),
        "returncode": result.returncode,
        "sandbox": "docker",
        "command": argv,
    }


def _ruff_issues(stdout: str, limit: int = 2000) -> str:
    """Every finding, from the top. The last 500 characters of ruff's full
    output held one finding and "Found 4 errors": the agent fixed that one
    and bounced on the rest (task 6f442de2, 2026-10-16)."""
    if len(stdout) <= limit:
        return stdout
    cut = stdout.rfind("\n", 0, limit)
    head = stdout[: cut if cut > 0 else limit]
    return f"{head}\n… ({stdout.count(chr(10)) - head.count(chr(10))} more lines)"


def _test_evidence(stdout: str, limit: int = 2000) -> str:
    """Why the tests failed, not only which. The last 500 characters of a
    pytest run are its warnings and the FAILED names; the agent rewrote its
    test twice without seeing the assertion (task 71046102, 2026-10-16). Keep
    the FAILURES/ERRORS section from the top, without the warnings summary,
    and the final summary line."""
    starts = [i for i in (stdout.find("= FAILURES ="), stdout.find("= ERRORS =")) if i >= 0]
    if not starts:
        return stdout[-500:]
    section = stdout[stdout.rfind("\n", 0, min(starts)) + 1 :]
    w = section.find(" warnings summary ")
    if w >= 0:
        docs = section.find("-- Docs:", w)
        cut = section.rfind("\n", 0, w)
        rest = section[section.find("\n", docs) + 1 :] if docs >= 0 else ""
        section = section[: cut + 1 if cut >= 0 else 0] + rest
    lines = section.rstrip("\n").split("\n")
    summary = lines[-1] if lines else ""
    if len(section) > limit:
        head = section[: limit - len(summary) - 4]
        section = head[: head.rfind("\n") + 1] + "…\n" + summary
    return section


async def _sandboxed_ruff(workdir: Path, args: list[str]) -> tuple[bool | None, dict]:
    if args[0] == "check":
        # One line per finding, so all of them fit in the evidence.
        args = [args[0], "--output-format=concise", *args[1:]]
    try:
        # --no-cache right after the subcommand: anything after "--" is a path.
        result = await sandbox.run(["ruff", args[0], "--no-cache", *args[1:]], workdir, timeout=120)
    except sandbox.SandboxUnavailableError as exc:
        return None, {"note": str(exc), "sandbox": "docker"}
    return result.returncode == 0, {
        "issues": _ruff_issues(result.stdout),
        "returncode": result.returncode,
        "sandbox": "docker",
    }


async def _verify_tests_pass(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """Run the project's test suite. Inconclusive if it has no runner."""
    if sandbox.enabled():
        return await _sandboxed_tests(workdir, ctx)
    python = _project_python(workdir)
    if python is None:
        return None, {"note": "no Python interpreter found for this project"}
    try:
        result = subprocess.run(
            [python, "-m", "pytest", str(workdir), "-q", "--tb=line", "-x"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(workdir),
        )
    except FileNotFoundError:
        return None, {"note": f"interpreter {python!r} disappeared before it could run"}
    except Exception as e:
        return False, {"error": str(e)}

    if _missing_module(result, "pytest"):
        # Not a test failure: this project's environment has no test runner.
        return None, {
            "note": "pytest is not installed in the project environment",
            "python": python,
        }
    passed = result.returncode == 0
    return passed, {
        "stdout": _test_evidence(result.stdout),
        "returncode": result.returncode,
        "python": python,
    }


async def _verify_acceptance_tests_pass(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """Run exactly the tests bound to this task's acceptance criteria.

    The plan's spec binds each AC-n to a pytest path/node id, and the task
    that cites a criterion is told to write or update that test. A bound test
    that doesn't exist is a FAILURE, not inconclusive -- the task was supposed
    to create it. Only a missing runner (no pytest / no interpreter) is
    inconclusive, same as tests_pass.
    """
    refs = list(ctx.get("acceptance_tests") or [])
    if not refs:
        return True, {"note": "no acceptance tests bound to this task"}
    # Re-checked here, not just at plan time: these are agent-authored and
    # become pytest arguments.
    unsafe = [r for r in refs if not is_safe_test_ref(r)]
    if unsafe:
        return False, {"error": "unsafe test reference(s)", "refs": unsafe}
    missing = [r for r in refs if not (workdir / r.split("::", 1)[0]).is_file()]
    if missing:
        return False, {"missing": missing, "note": "bound test file(s) were never written"}
    if any(is_js_test_ref(r) for r in refs):
        return await _js_acceptance_tests(workdir, ctx, refs)

    args = ["-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", *refs]
    if sandbox.enabled():
        try:
            venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
            timeout = int(ctx.get("sandbox_test_timeout") or _DEFAULT_TEST_TIMEOUT)
            result = await sandbox.run(["python", *args], workdir, venv=venv, timeout=timeout)
        except sandbox.SandboxUnavailableError as exc:
            return None, {"note": str(exc), "sandbox": "docker"}
    else:
        python = _project_python(workdir)
        if python is None:
            return None, {"note": "no Python interpreter found for this project"}
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [python, *args],
                capture_output=True,
                text=True,
                timeout=_DEFAULT_TEST_TIMEOUT,
                cwd=str(workdir),
            )
        except FileNotFoundError:
            return None, {"note": f"interpreter {python!r} disappeared before it could run"}

    if _missing_module(result, "pytest"):
        return None, {"note": "pytest is not installed in the project environment"}
    # 0 = passed. 4 (a node id that doesn't exist) and 5 (nothing collected)
    # both mean a bound test isn't really there -- a failure, not a pass.
    return result.returncode == 0, {
        "tests": refs,
        "returncode": result.returncode,
        "stdout": _test_evidence(result.stdout),
    }


_JS_RUNNERS = {
    # One file, optionally narrowed to one test by (regex-escaped) name.
    "vitest": lambda file, name: [
        "vitest",
        "run",
        file,
        *(["-t", re.escape(name)] if name else []),
    ],
    "jest": lambda file, name: ["jest", "--ci", file, *(["-t", re.escape(name)] if name else [])],
}


async def _js_acceptance_tests(
    workdir: Path, ctx: dict, refs: list[str]
) -> tuple[bool | None, dict]:
    """Bound JS/TS tests, one runner invocation each, in the Node sandbox.

    Inconclusive (not failed) without the sandbox or the Node toolchain: on
    the host there is no isolated way to install and run the project's code.
    """
    if not sandbox.enabled():
        return None, {"note": "JS acceptance tests run only in the docker sandbox"}
    if not sandbox.node_toolchain(ctx):
        return None, {"note": "JS test refs, but the project is not on sandbox_toolchain=node"}
    runner = (ctx.get("sandbox_js_test_runner") or "vitest").strip().lower()
    if runner not in _JS_RUNNERS:
        return None, {"note": f"unknown sandbox_js_test_runner {runner!r}"}
    timeout = int(ctx.get("sandbox_test_timeout") or _DEFAULT_TEST_TIMEOUT)
    try:
        deps = await sandbox.prepare_node_env(workdir, ctx.get("sandbox_setup"))
    except sandbox.SandboxUnavailableError as exc:
        return None, {"note": str(exc), "sandbox": "docker"}
    runs = []
    for ref in refs:
        file, _, name = ref.partition("::")
        try:
            result = await sandbox.run(
                _JS_RUNNERS[runner](file, name or None), workdir, node_deps=deps, timeout=timeout
            )
        except sandbox.SandboxUnavailableError as exc:
            return None, {"note": str(exc), "sandbox": "docker"}
        out = f"{result.stdout}\n{result.stderr}"
        # vitest/jest exit 0 when -t matched nothing (every test "skipped"); a
        # bound test that does not exist must fail, as pytest's exit 5 does.
        # So require at least one test to have actually passed: vitest prints
        # "Tests  1 passed | 2 skipped (3)", jest "Tests: 1 passed, 2 skipped".
        ran = re.search(r"Tests:?\s+(\d+) passed", out)
        matched = not name or bool(ran and int(ran.group(1)) > 0)
        runs.append(
            {
                "test": ref,
                "returncode": result.returncode,
                "passed": result.returncode == 0 and matched,
                "stdout": out[-400:],
            }
        )
    return all(r["passed"] for r in runs), {"tests": refs, "runner": runner, "runs": runs}


_E2E_DEFAULT_TIMEOUT = 300


async def _verify_app_e2e_pass(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """Start the app inside the sandbox and run its end-to-end checks against it.

    Reads three settings from the project registry, never from the worktree
    (the agent controls it):
    - ``sandbox_start_command`` starts the app (e.g. ``npm start``);
    - ``sandbox_app_port`` is the port it listens on;
    - ``sandbox_e2e_command`` drives it (Playwright, or plain HTTP checks).

    Server and checks share one container, so the sandbox keeps its
    no-network rule: they talk over the container's own loopback.
    Inconclusive when not configured or when the sandbox is off.
    """
    start, e2e = ctx.get("sandbox_start_command"), ctx.get("sandbox_e2e_command")
    if not (start and e2e):
        return None, {"note": "no sandbox_start_command / sandbox_e2e_command for this project"}
    if not sandbox.enabled():
        return None, {"note": "end-to-end checks run only in the docker sandbox"}
    try:
        port = int(ctx.get("sandbox_app_port") or 3000)
    except (TypeError, ValueError):
        return None, {"note": "sandbox_app_port is not a number"}
    if not 1 <= port <= 65535:
        return None, {"note": "sandbox_app_port is out of range"}
    timeout = int(ctx.get("sandbox_e2e_timeout") or _E2E_DEFAULT_TIMEOUT)
    # start/e2e are registry strings set by the project's owner, the same
    # trust level as sandbox_test_command; they run inside the sandbox only.
    script = (
        f"export PORT={port}\n"
        f"({start}) >/tmp/app.log 2>&1 &\napp=$!\n"
        "up=0\nfor i in $(seq 1 60); do\n"
        f"  if (echo > /dev/tcp/127.0.0.1/{port}) 2>/dev/null; then up=1; break; fi\n"
        "  kill -0 $app 2>/dev/null || break\n  sleep 1\ndone\n"
        'if [ "$up" != 1 ]; then echo "APP_DID_NOT_START"; tail -n 40 /tmp/app.log; exit 97; fi\n'
        f"({e2e})\nrc=$?\n"
        'kill $app 2>/dev/null; [ "$rc" = 0 ] || tail -n 40 /tmp/app.log\nexit $rc\n'
    )
    try:
        if sandbox.node_toolchain(ctx):
            deps = await sandbox.prepare_node_env(workdir, ctx.get("sandbox_setup"))
            result = await sandbox.run(
                ["bash", "-c", script], workdir, node_deps=deps, timeout=timeout
            )
        else:
            venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
            result = await sandbox.run(["bash", "-c", script], workdir, venv=venv, timeout=timeout)
    except sandbox.SandboxUnavailableError as exc:
        return None, {"note": str(exc), "sandbox": "docker"}
    started = "APP_DID_NOT_START" not in result.stdout
    return result.returncode == 0, {
        "returncode": result.returncode,
        "app_started": started,
        "port": port,
        "stdout": f"{result.stdout}\n{result.stderr}"[-800:],
        "sandbox": "docker",
    }


async def _verify_lint_clean(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """Run ruff over the project. Inconclusive if ruff is not available."""
    if sandbox.enabled():
        return await _sandboxed_ruff(workdir, ["check", ".", "--no-fix"])
    ruff = _project_tool(workdir, "ruff")
    if ruff is None:
        return None, {"note": "ruff not available for this project"}
    try:
        result = subprocess.run(
            [ruff, "check", str(workdir), "--no-fix"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(workdir),
        )
    except FileNotFoundError:
        return None, {"note": f"ruff at {ruff!r} disappeared before it could run"}
    except Exception as e:
        return False, {"error": str(e)}
    passed = result.returncode == 0
    return passed, {"issues": result.stdout[-500:], "returncode": result.returncode, "ruff": ruff}


async def _verify_build_ok(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Check Python syntax by compiling all .py files."""
    import py_compile

    errors = []
    for py_file in workdir.rglob("*.py"):
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(str(e))
    passed = len(errors) == 0
    return passed, {"errors": errors[:10]}


def _changed_files(workdir: Path) -> list[Path]:
    """Files changed since HEAD (tracked modifications) UNION untracked new
    files (``git ls-files --others``), resolved under ``workdir``. Empty
    list (never raises) on any git failure — e.g. the scratch-temp-dir
    fallback, which is never a git repo at all.

    Both tracked modifications AND new untracked files must be included —
    a change that only ADDS a file (no modification to any existing tracked
    file) would otherwise be invisible to ``git diff --name-only HEAD``,
    which reports NOTHING for untracked files, making build_ok_diff /
    lint_clean_diff pass vacuously on exactly the kind of change they exist
    to verify. Nothing in the agent-tool pipeline stages files (there is no
    git-add tool, and LocalDriver never stages), so "new file" is the normal
    case, not an edge case.
    """
    changed_names: set[str] = set()
    try:
        tracked = subprocess.run(
            [*_HARDENED_GIT, "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(workdir),
        )
        changed_names.update(f.strip() for f in tracked.stdout.strip().split("\n") if f.strip())
        untracked = subprocess.run(
            [*_HARDENED_GIT, "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(workdir),
        )
        changed_names.update(f.strip() for f in untracked.stdout.strip().split("\n") if f.strip())
    except Exception:
        return []
    return [workdir / f for f in changed_names if (workdir / f).is_file()]


def _changed_python_files(workdir: Path) -> list[Path]:
    """:func:`_changed_files`, filtered to ``*.py``."""
    return [f for f in _changed_files(workdir) if f.suffix == ".py"]


async def _verify_no_diff_in_plan(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """A plan dispatch must only write a spec — no file changes at all.

    Not inconclusive: a driver that edits files when told only to plan is a
    real correctness problem (it didn't follow the instruction), so this
    bounces once with the touched files named, then escalates — the same
    one-bounce rule as any other failure, not the "tool unavailable" path.
    """
    changed = _changed_files(workdir)
    if changed:
        return False, {"touched": [str(f.relative_to(workdir)) for f in changed]}
    return True, {}


async def _verify_build_ok_diff(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Like build_ok, but only compiles files changed since HEAD."""
    import py_compile

    errors = []
    changed = _changed_python_files(workdir)
    for py_file in changed:
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(str(e))
    passed = len(errors) == 0
    return passed, {"errors": errors[:10], "checked": len(changed)}


_MAX_SCANNED_FILE_BYTES = 2_000_000

# High-confidence secret patterns only — no generic "long base64 string" or
# entropy heuristics, which false-positive constantly on hashes, minified
# assets and test fixtures. Each pattern here is a real credential format
# that has no other legitimate reason to appear in a diff. Named so the
# evidence can say *what* matched without ever echoing the matched text.
_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("aws_access_key_id", r"AKIA[0-9A-Z]{16}"),
    ("private_key_block", r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ("github_pat_classic", r"ghp_[A-Za-z0-9]{36}"),
    ("github_pat_fine_grained", r"github_pat_[A-Za-z0-9_]{22,}"),
    ("slack_token", r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    ("stripe_live_key", r"sk_live_[A-Za-z0-9]{24,}"),
    ("anthropic_api_key", r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    ("openai_api_key", r"sk-proj-[A-Za-z0-9\-_]{20,}"),
    ("google_api_key", r"AIza[0-9A-Za-z\-_]{35}"),
    ("npm_token", r"npm_[A-Za-z0-9]{36}"),
)
_SECRET_RE = [(name, re.compile(pat)) for name, pat in _SECRET_PATTERNS]

# AWS's own documented placeholder, used in nearly every S3/IAM tutorial and
# copied into countless test fixtures. It matches aws_access_key_id but is
# not a credential — the one deliberate exception to "no allowlisting"
# elsewhere in this file, because the false-positive rate without it would
# train people to approve past this check rather than read it.
_AWS_EXAMPLE_KEY = "AKIAIOSFODNN7EXAMPLE"


async def _verify_no_secrets_in_diff(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Refuse to land a change whose diff contains something that looks
    like a real credential.

    Pure regex over each changed file's current content — no subprocess, no
    sandbox, so it runs identically whether sandboxing is on or not and adds
    no meaningful latency. High-confidence patterns only (see
    :data:`_SECRET_PATTERNS`); this catches an agent that echoed a live key
    into a config file or committed a staged credentials file, not every
    possible secret shape.

    Evidence never includes the matched text itself, only the file, line
    number, and which pattern matched — a false positive is diagnosable
    without the report becoming a second place the secret now lives.
    """
    findings: list[dict] = []
    changed = _changed_files(workdir)
    for path in changed:
        try:
            if path.stat().st_size > _MAX_SCANNED_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable — nothing here to regex over
        rel = str(path.relative_to(workdir))
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _AWS_EXAMPLE_KEY in line:
                continue
            for name, pattern in _SECRET_RE:
                if pattern.search(line):
                    findings.append({"file": rel, "line": lineno, "pattern": name})
    return not findings, {"findings": findings[:20], "checked": len(changed)}


_DEPENDENCY_MANIFESTS = frozenset(
    {
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
        "pyproject.toml",
        "uv.lock",
        "poetry.lock",
        "Pipfile",
        "Pipfile.lock",
        "setup.py",
        "setup.cfg",
    }
)


async def _verify_no_vulnerable_deps_in_diff(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """Refuse to land a change that adds a dependency with a known CVE.

    Skipped entirely (a real pass, not inconclusive) unless the diff touches
    a dependency manifest — most tasks never do, and an audit costs a real
    network round-trip that isn't worth paying otherwise.

    Runs on the host, never inside the check-phase sandbox: unlike every
    other verifier here, this one genuinely needs outbound network access
    (querying the OSV/PyPI vulnerability database), which the sandbox denies
    by design (``services/sandbox.py``'s ``--network none`` check phase).
    That's safe specifically for this check: pip-audit only reads installed
    package name/version metadata and queries a vulnerability database, it
    never executes anything from the diff itself — unlike tests_pass or
    lint_clean_diff, which run the agent's actual code and must stay
    contained. Still uses the sandbox's own cached, dependency-resolved venv
    (``prepare_env``, built during the network-on setup phase) rather than
    assuming a stray ``workdir/.venv`` exists, which it usually won't for an
    ephemeral worktree.
    """
    changed_names = {f.name for f in _changed_files(workdir)}
    touched = sorted(_DEPENDENCY_MANIFESTS & changed_names)
    if not touched:
        return True, {"note": "no dependency manifest changed", "touched": []}

    pip_audit: str | None = None
    if sandbox.enabled():
        try:
            venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
            candidate = venv / "bin" / "pip-audit"
            pip_audit = str(candidate) if candidate.is_file() else None
        except sandbox.SandboxUnavailableError:
            pip_audit = None
    else:
        # Deliberately NOT _project_tool's shutil.which(tool) last resort
        # here. ruff/pytest take an explicit target path, so even a
        # "wrong" ambient binary still operates on the right directory;
        # pip-audit with no arguments audits whatever Python environment
        # IT is bound to, with no target argument to correct that. Found
        # live: this API server's own venv happened to have pip-audit
        # installed and was first on PATH, so the shutil.which fallback
        # quietly audited life-graph's own dependencies while claiming to
        # have checked a completely different project's — a false pass
        # that is worse than the inconclusive result it was standing in
        # for. Only a venv actually inside this project's own workdir can
        # be trusted to be *this* project's environment.
        for venv_dir in _VENV_DIRS:
            for bindir in _BIN_DIRS:
                candidate = workdir / venv_dir / bindir / "pip-audit"
                if candidate.is_file():
                    pip_audit = str(candidate)
                    break
            if pip_audit:
                break

    if pip_audit is None:
        logger.warning("no_vulnerable_deps_in_diff: pip-audit not available — check not performed")
        return None, {"note": "pip-audit not available for this project", "touched": touched}

    try:
        result = subprocess.run(
            [pip_audit, "--format", "json", "--progress-spinner", "off"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return None, {
            "note": f"pip-audit at {pip_audit!r} disappeared before it could run",
            "touched": touched,
        }
    except subprocess.TimeoutExpired:
        return None, {
            "note": "pip-audit timed out (needs network, not sandboxed)",
            "touched": touched,
        }

    if result.returncode not in (0, 1):
        # 0: no vulnerabilities. 1: vulnerabilities found. Anything else is
        # pip-audit itself failing (bad env, no network, ...) — not a
        # verdict on the dependencies.
        return None, {
            "note": f"pip-audit could not run: {result.stderr[-300:]}",
            "touched": touched,
        }

    try:
        report = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None, {"note": "pip-audit produced unparseable output", "touched": touched}

    vulns = [
        {"package": dep.get("name"), "version": dep.get("version"), "id": v.get("id")}
        for dep in report.get("dependencies") or []
        for v in dep.get("vulns") or []
    ]
    return not vulns, {"touched": touched, "vulnerabilities": vulns[:20]}


async def _verify_lint_clean_diff(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """Like lint_clean, but only lints files changed since HEAD."""
    changed = _changed_python_files(workdir)
    if not changed:
        return True, {"note": "No changed .py files"}

    if sandbox.enabled():
        rel = [str(f.relative_to(workdir)) for f in changed]
        return await _sandboxed_ruff(workdir, ["check", "--no-fix", "--", *rel])

    ruff = _project_tool(workdir, "ruff")
    if ruff is None:
        # A missing linter is not a lint failure — but it is not a pass
        # either. This used to return True, so on any host without ruff (the
        # production image installs no dev tooling) the lint gate silently
        # reported success on every dispatch while checking nothing.
        logger.warning("lint_clean_diff: ruff not available — check not performed")
        return None, {"note": "ruff not available for this project"}
    try:
        result = subprocess.run(
            [ruff, "check", "--no-fix", "--output-format=concise", *[str(f) for f in changed]],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(workdir),
        )
    except FileNotFoundError:
        return None, {"note": f"ruff at {ruff!r} disappeared before it could run"}
    except Exception as e:
        return False, {"error": str(e)}
    passed = result.returncode == 0
    return passed, {
        "issues": _ruff_issues(result.stdout),
        "returncode": result.returncode,
        "ruff": ruff,
    }


def _local_modules(workdir: Path) -> set[str]:
    """Top-level importable names defined by the project itself."""
    names = set()
    for entry in workdir.iterdir():
        if entry.name in ("tests", "test") or entry.name.startswith("."):
            continue
        if entry.is_dir() and (entry / "__init__.py").is_file():
            names.add(entry.name)
        elif entry.suffix == ".py" and entry.name not in ("setup.py", "conftest.py"):
            names.add(entry.stem)
    return names


def _test_smells(source: str, local: set[str]) -> list[str]:
    """Why a test file does not exercise the code, or ``[]``."""
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # build_ok_diff reports it
    smells = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            literals = [a.value for a in node.args if isinstance(a, ast.Constant)]
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                target = literals[0] if literals else None
            elif isinstance(node.func, ast.Attribute) and node.func.attr in (
                "read_text",
                "read_bytes",
                "open",
            ):
                inner = node.func.value
                target = (
                    inner.args[0].value
                    if isinstance(inner, ast.Call)
                    and inner.args
                    and isinstance(inner.args[0], ast.Constant)
                    else None
                )
            else:
                continue
            if isinstance(target, str) and target.endswith(".py") and not _is_test_path(target):
                smells.append(f"reads the source file {target!r} instead of running it")
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in local:
            imported |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.Import):
            imported |= {
                (a.asname or a.name).split(".")[0]
                for a in node.names
                if a.name.split(".")[0] in local
            }
    if imported:
        used = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Call, ast.ClassDef)):
                # Called, passed along, or subclassed (a stub of the class under test).
                parts = (
                    [*node.bases]
                    if isinstance(node, ast.ClassDef)
                    else [node.func, *node.args, *(k.value for k in node.keywords)]
                )
                for part in parts:
                    for sub in ast.walk(part):
                        if isinstance(sub, ast.Name) and sub.id in imported:
                            used = True
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # patch("pkg.mod.name") targets the code by its dotted path.
                if node.value.split(".")[0] in local and "." in node.value:
                    used = True
        if not used:
            smells.append(f"imports {', '.join(sorted(imported))} but never calls or patches it")
    return smells


async def _verify_tests_exercise_code(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """A test the agent added or changed must run the code, not read it.

    OpenCode passed every check on task d917e132 (2026-10-17) with a "test"
    that opened memory_search.py and asserted strings in it, and only checked
    the imported function ``is not None``: it could not fail for any change
    in behaviour. Static and cheap: an AST look at changed test files only.
    """
    tests = [
        f for f in _changed_python_files(workdir) if _is_test_path(str(f.relative_to(workdir)))
    ]
    if not tests:
        return True, {"note": "no changed test files"}
    local = _local_modules(workdir)
    found = {}
    for f in tests:
        try:
            smells = _test_smells(f.read_text(encoding="utf-8", errors="replace"), local)
        except OSError:
            continue
        if smells:
            found[str(f.relative_to(workdir))] = smells
    evidence: dict = {"checked": [str(f.relative_to(workdir)) for f in tests], "problems": found}
    if found:
        evidence["hint"] = (
            "Write the test to call the code it is about (with mocks or fixtures for "
            "its dependencies) and assert on what it does, so it fails if the change "
            "is reverted."
        )
    return not found, evidence


_NAMED_PATH = re.compile(
    r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.(?:py|pyi|ts|tsx|js|jsx|mjs|md|toml|ya?ml|json|sql|sh|cfg|ini|txt|html|css))(?![\w/-])"
)


def named_paths(instruction: str) -> list[str]:
    """File paths an instruction names, e.g. ``life_graph/tools/memory_search.py``."""
    return sorted({m.group(1).removeprefix("./") for m in _NAMED_PATH.finditer(instruction or "")})


def _is_test_path(rel: str) -> bool:
    p = PurePosixPath(rel)
    name = p.name
    return (
        (p.parts and p.parts[0] in ("tests", "test", "__tests__"))
        or (name.startswith("test_") and name.endswith(".py"))
        or name.endswith(("_test.py", ".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.js"))
    )


async def _verify_diff_within_scope(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Check that changes stay within the files the task is about.

    The scope is ``allowed_files`` when given; otherwise the files the task's
    own instruction names (``scope_instruction``, the original text, not a
    bounce's, whose failure output names unrelated paths). A task that names
    no file has no constraint. Tests may always be added or changed. On
    2026-10-17 gpt-oss:20b edited api/dependencies.py to make its broken
    test import, on a task that said "change nothing else", and OpenCode left
    a run_test.sh behind; neither was checked.
    """
    allowed = list(ctx.get("allowed_files") or named_paths(ctx.get("scope_instruction") or ""))
    if not allowed:
        return True, {"note": "No scope constraint"}
    changed = [str(f.relative_to(workdir)) for f in _changed_files(workdir)]
    bare = {a for a in allowed if "/" not in a}
    out_of_scope = [
        f
        for f in changed
        if f not in allowed and PurePosixPath(f).name not in bare and not _is_test_path(f)
    ]
    evidence: dict = {"allowed": allowed, "changed": changed, "out_of_scope": out_of_scope}
    if out_of_scope:
        evidence["hint"] = (
            "These files are outside the task. Revert them; if the task really "
            "needs them, say why in your summary instead of changing them."
        )
    return not out_of_scope, evidence


async def _verify_citations_present(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Check that output contains citations/references."""
    output = ctx.get("output", "")
    has_citations = any(
        marker in output for marker in ["[ref:", "[id:", "evidence:", "source:", "citing"]
    )
    return has_citations or not ctx.get("require_citations", False), {
        "has_citations": has_citations,
    }


async def _verify_style_conforms(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    """Check code style with ruff format --check."""
    if sandbox.enabled():
        return await _sandboxed_ruff(workdir, ["format", "--check", "."])
    try:
        result = subprocess.run(
            ["ruff", "format", "--check", str(workdir)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(workdir),
        )
        passed = result.returncode == 0
        return passed, {"issues": result.stdout[-500:]}
    except Exception as e:
        return True, {"note": f"Style check unavailable: {e}"}


async def _verify_claims_evidenced(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Verify that claims in the output have supporting evidence."""
    output = ctx.get("output", "")
    if not output:
        return True, {"note": "No output to check"}
    has_data = any(
        marker in output for marker in ["```", "results:", "found", "tested", "verified"]
    )
    return has_data or len(output) < 100, {"has_evidence_markers": has_data}


# ── Module-level singleton ───────────────────────────────────
verifier_chain = VerifierChain()
