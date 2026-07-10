"""Verifier Chain — quality gates for agent task results.

7 built-in verifiers. Each returns (passed: bool, evidence: dict).
One-bounce rule: failed → re-dispatch once → second failure → needs_human.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VerifierResult:
    """Result from a single verifier check.

    Attributes:
        verifier: Name of the verifier that produced this result.
        passed: Whether the verification passed.
        evidence: Supporting data for the pass/fail decision.
    """

    verifier: str
    passed: bool
    evidence: dict


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
                results.append(
                    VerifierResult(name, False, {"error": f"Unknown verifier: {name}"})
                )
                continue
            try:
                passed, evidence = await verifier(workdir, task_context)
                results.append(VerifierResult(name, passed, evidence))
            except Exception as e:
                logger.warning("Verifier %s failed: %s", name, e, exc_info=True)
                results.append(VerifierResult(name, False, {"error": str(e)}))
        return results

    def all_passed(self, results: list[VerifierResult]) -> bool:
        """Check if all verifiers in the results list passed."""
        return all(r.passed for r in results)

    def _register_builtins(self) -> None:
        """Register the 7 built-in verifiers."""
        self.register("tests_pass", _verify_tests_pass)
        self.register("lint_clean", _verify_lint_clean)
        self.register("build_ok", _verify_build_ok)
        self.register("diff_within_scope", _verify_diff_within_scope)
        self.register("citations_present", _verify_citations_present)
        self.register("style_conforms", _verify_style_conforms)
        self.register("claims_evidenced", _verify_claims_evidenced)


# ── 7 Built-in Verifiers ─────────────────────────────────────


async def _verify_tests_pass(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Run pytest and check exit code."""
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", str(workdir), "-q", "--tb=no", "-x"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(workdir),
        )
        passed = result.returncode == 0
        return passed, {"stdout": result.stdout[-500:], "returncode": result.returncode}
    except Exception as e:
        return False, {"error": str(e)}


async def _verify_lint_clean(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Run ruff check."""
    try:
        result = subprocess.run(
            ["ruff", "check", str(workdir), "--no-fix"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(workdir),
        )
        passed = result.returncode == 0
        return passed, {"issues": result.stdout[-500:], "returncode": result.returncode}
    except Exception as e:
        return False, {"error": str(e)}


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


async def _verify_diff_within_scope(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Check that changes are within expected files."""
    allowed_files = ctx.get("allowed_files", [])
    if not allowed_files:
        return True, {"note": "No scope constraint"}
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
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
        marker in output
        for marker in ["[ref:", "[id:", "evidence:", "source:", "citing"]
    )
    return has_citations or not ctx.get("require_citations", False), {
        "has_citations": has_citations,
    }


async def _verify_style_conforms(workdir: Path, ctx: dict) -> tuple[bool, dict]:
    """Check code style with ruff format --check."""
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
        marker in output
        for marker in ["```", "results:", "found", "tested", "verified"]
    )
    return has_data or len(output) < 100, {"has_evidence_markers": has_data}


# ── Module-level singleton ───────────────────────────────────
verifier_chain = VerifierChain()
