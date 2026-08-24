"""Which checks a dispatch runs, and who decides.

Two defects met here:

* ``DEFAULT_VERIFY_CHAIN`` was ``["build_ok", "lint_clean"]`` — the whole-repo
  variants. On any codebase with pre-existing lint debt those fail on files
  the agent never touched, so the task bounced once (a wasted frontier call)
  and escalated to needs_human every single time. A verifier chain has to
  judge the diff, not the repo.
* ``agent_personas.verifier_chain`` was never read. dependency-updater asks
  for ``tests_pass`` because its entire job is "run the project's tests before
  landing"; it silently got build+lint instead and its tests never ran. The
  autonomous pipeline also pinned a chain at the call site, overriding every
  persona that wanted something stricter.
"""

import subprocess
from pathlib import Path

import pytest

from life_graph.drivers.dispatcher import DEFAULT_VERIFY_CHAIN, _resolve_verify_chain
from life_graph.services.verifiers import verifier_chain


class _Persona:
    def __init__(self, verifier_chain=None):
        self.verifier_chain = verifier_chain


# ── Precedence ────────────────────────────────────────────────────────


def test_caller_argument_wins():
    chain = _resolve_verify_chain(["citations_present"], _Persona(["tests_pass"]))
    assert chain == ["citations_present"]


def test_persona_chain_beats_the_default():
    chain = _resolve_verify_chain(None, _Persona(["tests_pass", "diff_within_scope"]))
    assert chain == ["tests_pass", "diff_within_scope"]


def test_default_applies_with_no_persona():
    assert _resolve_verify_chain(None, None) == DEFAULT_VERIFY_CHAIN


def test_persona_without_a_chain_falls_through():
    assert _resolve_verify_chain(None, _Persona(None)) == DEFAULT_VERIFY_CHAIN
    assert _resolve_verify_chain(None, _Persona([])) == DEFAULT_VERIFY_CHAIN


def test_resolution_never_aliases_the_default():
    """A caller mutating its chain must not rewrite the module constant."""
    chain = _resolve_verify_chain(None, None)
    chain.append("mutated")
    assert "mutated" not in DEFAULT_VERIFY_CHAIN


def test_the_seeded_personas_chains_are_real_verifiers():
    """A typo in a persona's chain would silently register as unknown."""
    from life_graph.kernel.personas import _BUILTIN_PERSONAS

    known = set(verifier_chain._verifiers)
    for defn in _BUILTIN_PERSONAS:
        for name in defn.get("verifier_chain") or []:
            assert name in known, f"persona {defn['name']!r} names unknown verifier {name!r}"


# ── The default must judge the diff, not the repo ─────────────────────


def test_default_chain_is_diff_scoped():
    assert all(v.endswith("_diff") for v in DEFAULT_VERIFY_CHAIN), (
        "whole-repo verifiers fail on pre-existing debt in files the agent "
        "never touched, bouncing and escalating every dispatch"
    )


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


@pytest.mark.asyncio
async def test_pre_existing_debt_does_not_fail_a_clean_change(tmp_path):
    """Regression, reproduced end to end against real ruff."""
    (tmp_path / "legacy.py").write_text("import os\n")  # debt, untouched
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
    _git("init", "-q", ".", cwd=tmp_path)
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i", cwd=tmp_path)

    (tmp_path / "agent_added.py").write_text("y = 2\n")  # the change: clean

    results = await verifier_chain.run_chain(list(DEFAULT_VERIFY_CHAIN), Path(tmp_path), {})
    if any(r.inconclusive for r in results):
        pytest.skip("ruff not available in this environment")
    assert verifier_chain.all_passed(results), (
        "the agent's change is clean; only legacy.py has issues and it was "
        f"never touched: {[(r.verifier, r.evidence) for r in results if not r.passed]}"
    )
