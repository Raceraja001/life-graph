from types import SimpleNamespace

from life_graph.services.dev_tasks import driver_of

# Helper to create a task-like object


def make_task(result: dict | None = None, assigned_agent: str | None = None):
    return SimpleNamespace(result=result or {}, assigned_agent=assigned_agent)


def test_driver_from_metadata():
    task = make_task(result={"metadata": {"driver": "my_custom_driver"}})
    assert driver_of(task) == "my_custom_driver"


def test_session_id_in_metadata():
    task = make_task(result={"metadata": {"session_id": "abc"}})
    assert driver_of(task) == "claude_code"


def test_num_turns_in_metadata():
    task = make_task(result={"metadata": {"num_turns": 5}})
    assert driver_of(task) == "claude_code"


def test_tool_calls_in_metadata():
    task = make_task(result={"metadata": {"tool_calls": []}})
    assert driver_of(task) == "local"


def test_pinned_driver_returns_driver():
    # "uzhavu-ops" persona pins "claude_code"
    task = make_task(assigned_agent="uzhavu-ops")
    assert driver_of(task) == "claude_code"


def test_pinned_driver_returns_none():
    task = make_task(assigned_agent="unknown-persona")
    assert driver_of(task) is None
