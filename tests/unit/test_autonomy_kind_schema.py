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
