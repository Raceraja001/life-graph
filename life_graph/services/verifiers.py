"""Verifier Chain — quality gates for agent task results.

11 built-in verifiers. Each returns (passed: bool, evidence: dict).
One-bounce rule: failed → re-dispatch once → second failure → needs_human.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from life_graph.services import sandbox

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
        """Run specified verifiers in order. Returns results for each.

        Args:
            chain: Ordered list of verifier names to run.
            workdir: Working directory for file-based checks.
            task_context: Task metadata (output, allowed_files, etc.).

        Returns:
            List of VerifierResult, one per verifier in chain.
        """
        results = []
        for name in chain:
            verifier = self._verifiers.get(name)
            if not verifier:
                results.append(VerifierResult(name, False, {"error": f"Unknown verifier: {name}"}))
                continue
            try:
                passed, evidence = await verifier(workdir, task_context)
                if passed is None:
                    # Sentinel: the verifier could not run its tool. Kept as a
                    # 2-tuple so third-party verifiers registered against the
                    # documented (bool, dict) contract keep working unchanged.
                    results.append(VerifierResult(name, False, evidence, inconclusive=True))
                else:
                    results.append(VerifierResult(name, bool(passed), evidence))
            except Exception as e:
                logger.warning("Verifier %s failed: %s", name, e, exc_info=True)
                results.append(VerifierResult(name, False, {"error": str(e)}))
        return results

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
        self.register("citations_present", _verify_citations_present)
        self.register("style_conforms", _verify_style_conforms)
        self.register("claims_evidenced", _verify_claims_evidenced)


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


async def _sandboxed_tests(workdir: Path, ctx: dict) -> tuple[bool | None, dict]:
    # The project registry may narrow what "the tests" are — a suite whose
    # integration tests need a database cannot pass in a network-less sandbox,
    # which made tests_pass unusable for such projects. Never read from the
    # worktree: the agent controls it.
    command = ctx.get("sandbox_test_command")
    try:
        argv = shlex.split(command) if command else _DEFAULT_TEST_ARGV
    except ValueError as exc:
        return None, {"note": f"sandbox_test_command does not parse: {exc}"}
    if not argv:
        argv = _DEFAULT_TEST_ARGV
    timeout = int(ctx.get("sandbox_test_timeout") or _DEFAULT_TEST_TIMEOUT)
    try:
        venv = await sandbox.prepare_env(workdir, ctx.get("sandbox_setup"))
        result = await sandbox.run(argv, workdir, venv=venv, timeout=timeout)
    except sandbox.SandboxUnavailableError as exc:
        return None, {"note": str(exc), "sandbox": "docker", "command": argv}
    if _missing_module(result, "pytest"):
        return None, {"note": "pytest is not installed in the project environment"}
    return result.returncode == 0, {
        "stdout": result.stdout[-500:],
        "returncode": result.returncode,
        "sandbox": "docker",
        "command": argv,
    }


async def _sandboxed_ruff(workdir: Path, args: list[str]) -> tuple[bool | None, dict]:
    try:
        # --no-cache right after the subcommand: anything after "--" is a path.
        result = await sandbox.run(["ruff", args[0], "--no-cache", *args[1:]], workdir, timeout=120)
    except sandbox.SandboxUnavailableError as exc:
        return None, {"note": str(exc), "sandbox": "docker"}
    return result.returncode == 0, {
        "issues": result.stdout[-500:],
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
            [python, "-m", "pytest", str(workdir), "-q", "--tb=no", "-x"],
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
        "stdout": result.stdout[-500:],
        "returncode": result.returncode,
        "python": python,
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
    if pip_audit is None:
        pip_audit = _project_tool(workdir, "pip-audit")

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
        return None, {"note": "pip-audit timed out (needs network, not sandboxed)", "touched": touched}

    if result.returncode not in (0, 1):
        # 0: no vulnerabilities. 1: vulnerabilities found. Anything else is
        # pip-audit itself failing (bad env, no network, ...) — not a
        # verdict on the dependencies.
        return None, {"note": f"pip-audit could not run: {result.stderr[-300:]}", "touched": touched}

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
            [ruff, "check", "--no-fix", *[str(f) for f in changed]],
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


async def _verify_diff_within_scope(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Check that changes are within expected files."""
    allowed_files = ctx.get("allowed_files", [])
    if not allowed_files:
        return True, {"note": "No scope constraint"}
    try:
        result = subprocess.run(
            [*_HARDENED_GIT, "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(workdir),
        )
        changed = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        out_of_scope = [f for f in changed if f not in allowed_files]
        passed = len(out_of_scope) == 0
        return passed, {"changed": changed, "out_of_scope": out_of_scope}
    except Exception as e:
        return True, {"note": f"Git check failed: {e}"}


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
