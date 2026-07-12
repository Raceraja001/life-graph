"""Unit tests for built-in persona definitions.

Pure-data tests — no database required. Verifies the operational
personas (uzhavu-ops, dependency-updater) added for the Agent Drivers
spec are present and well-formed, and that every built-in definition
carries the fields ``seed_builtins`` reads.
"""

from __future__ import annotations

from life_graph.kernel.personas import _BUILTIN_PERSONAS


def _by_name(name: str) -> dict:
    for defn in _BUILTIN_PERSONAS:
        if defn["name"] == name:
            return defn
    raise AssertionError(f"built-in persona {name!r} not found")


def test_core_personas_still_present() -> None:
    names = {p["name"] for p in _BUILTIN_PERSONAS}
    assert {"chief", "cody", "rex", "ops", "penny", "scribe"} <= names


def test_operational_personas_seeded() -> None:
    """uzhavu-ops and dependency-updater must be built-in (agent-drivers spec)."""
    names = {p["name"] for p in _BUILTIN_PERSONAS}
    assert "uzhavu-ops" in names
    assert "dependency-updater" in names


def test_uzhavu_ops_shape() -> None:
    p = _by_name("uzhavu-ops")
    assert p["driver"] == "claude_code"
    assert "deploy_check" in p["task_types"]
    assert "incident_fix" in p["task_types"]
    # verifier_chain must reference only registered verifier kinds
    assert p["verifier_chain"]
    assert p["context_profile"].get("domains")


def test_dependency_updater_shape() -> None:
    p = _by_name("dependency-updater")
    assert p["driver"] == "claude_code"
    assert "dependency_update" in p["task_types"]
    assert p["verifier_chain"]


def test_all_builtins_have_required_seed_fields() -> None:
    """seed_builtins reads these keys off every definition."""
    required = {
        "name",
        "display_name",
        "icon",
        "description",
        "system_prompt",
        "intent_tags",
        "temperature",
        "allowed_tools",
    }
    for defn in _BUILTIN_PERSONAS:
        missing = required - defn.keys()
        assert not missing, f"{defn.get('name')} missing {missing}"


def test_verifier_chains_reference_registered_kinds() -> None:
    """A persona's verifier_chain must only name verifiers that exist."""
    from life_graph.services.verifiers import VerifierChain

    registered = set(VerifierChain()._verifiers.keys())
    for defn in _BUILTIN_PERSONAS:
        for name in defn.get("verifier_chain", []) or []:
            assert name in registered, (
                f"{defn['name']} references unknown verifier {name!r}"
            )
