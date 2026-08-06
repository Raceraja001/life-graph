from life_graph.kernel.ambient import AMBIENT_ACTION, AMBIENT_ACTION_READONLY_TOOLS, AMBIENT_JOBS
from life_graph.kernel.personas import _BUILTIN_PERSONAS


def test_ops_declares_action_proposal_contract():
    ops = next(p for p in _BUILTIN_PERSONAS if p["name"] == "ops")
    sp = ops["system_prompt"]
    assert "JSON array" in sp and '"command"' in sp and '"risk_hint"' in sp
    assert "propose" in sp.lower()


def test_readonly_toolset_has_no_write_tools():
    for t in AMBIENT_ACTION_READONLY_TOOLS:
        assert t not in ("run_command", "terminal", "docker", "ssh", "git", "browser_agent", "delegate_to_persona")


def test_ops_ambient_job_seeded_inactive():
    job = next(j for j in AMBIENT_JOBS if j["name"] == "ops-ambient")
    assert job["agent_name"] == "ops"
    assert job["active"] is False
    assert job["cron_expression"] == "0 1 * * *"


def test_ambient_action_contains_ops():
    # Task 6: cody joined ops as an ambient action-propose persona.
    assert frozenset({"ops", "cody"}) == AMBIENT_ACTION
