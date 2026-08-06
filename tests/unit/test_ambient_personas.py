"""Tests for ambient advisory personas and their findings JSON contract."""

from life_graph.kernel.personas import _BUILTIN_PERSONAS


def _p(name):
    """Helper to get a persona by name."""
    return next(p for p in _BUILTIN_PERSONAS if p["name"] == name)


def test_advisory_personas_declare_findings_json_contract():
    """Scout/admin/tutor prompts declare the JSON array contract."""
    for name in ("scout", "admin", "tutor"):
        sp = _p(name)["system_prompt"]
        assert "JSON array" in sp
        assert '"urgency"' in sp
        assert '"now"' in sp and '"brief"' in sp


def test_advisory_personas_stay_read_only():
    """Scout/admin/tutor allowed_tools contain no write tools."""
    write_tools = {"terminal", "git", "delegate_to_persona", "browse_web_write"}
    for name in ("scout", "admin", "tutor"):
        assert not (set(_p(name)["allowed_tools"]) & write_tools)
