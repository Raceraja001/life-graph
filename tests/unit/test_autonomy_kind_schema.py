from types import SimpleNamespace

from life_graph.autonomy.approvals.service import _serialize
from life_graph.autonomy.pipeline.schemas import AutoFixRequest


def test_autofix_request_defaults_to_command_kind():
    req = AutoFixRequest(
        agent_id="ops", project_id="ambient", action_type="restart", command="docker restart x"
    )
    assert req.kind == "command"
    assert req.instruction is None


def test_autofix_request_accepts_agent_task():
    req = AutoFixRequest(
        agent_id="cody",
        project_id="ambient",
        action_type="cody_fix",
        command=None,
        kind="agent_task",
        instruction="Fix the failing test in module X",
    )
    assert req.kind == "agent_task"
    assert req.instruction == "Fix the failing test in module X"
    assert req.command is None


def test_autofix_request_command_is_now_optional():
    # command may be None for agent_task; must not raise
    AutoFixRequest(
        agent_id="cody",
        project_id="ambient",
        action_type="t",
        kind="agent_task",
        instruction="do X",
    )


def _entry(**kw):
    """An ApprovalQueueEntry-shaped attribute bag for the serializer."""
    base = dict(
        id="aq-1",
        tenant_id="t1",
        agent_id="cody",
        project_id="ambient",
        action_name="cody_fix",
        action_command=None,
        kind="agent_task",
        instruction="Fix the failing test in module X",
        risk_level="moderate",
        category="pipeline",
        trigger_type="manual",
        trigger_detail="cody_fix",
        estimated_impact=None,
        status="pending",
        priority=50,
        resolved_by=None,
        resolution_note=None,
        resolved_at=None,
        expires_at=None,
        timeout_hours=24,
        escalation_sent=None,
        created_at=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_approval_queue_serializer_exposes_kind_and_instruction():
    """Final-review Minor #9: the autonomy-native approvals API returned a null
    action_command for agent_task entries with no way to tell what they were."""
    out = _serialize(_entry())
    assert out["kind"] == "agent_task"
    assert out["instruction"] == "Fix the failing test in module X"
    assert out["action_command"] is None


def test_approval_queue_serializer_defaults_kind_for_command_entries():
    out = _serialize(_entry(kind="command", instruction=None, action_command="docker restart x"))
    assert out["kind"] == "command"
    assert out["instruction"] is None
