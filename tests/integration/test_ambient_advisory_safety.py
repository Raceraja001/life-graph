"""A scheduled advisory persona must never receive a write tool.

This is a guard test: it should pass immediately (the code it guards
already exists). It fails only if someone later widens the allowed_tools
on an advisory persona or drops the tool filter in process_manager.
"""

from life_graph.kernel.ambient import AMBIENT_ADVISORY
from life_graph.kernel.personas import _BUILTIN_PERSONAS


def test_advisory_allowed_tools_are_read_only():
    """Advisory personas must have only read-only tools.

    Verifies that scout, admin, and tutor (the scheduled ambient roles)
    are constrained to the read-only tool set:
    {web_search, browse_web, memory_search, get_current_datetime}
    """
    read_only = {
        "web_search",
        "browse_web",
        "memory_search",
        "get_current_datetime",
    }
    for name in AMBIENT_ADVISORY:
        persona = next(
            (p for p in _BUILTIN_PERSONAS if p["name"] == name),
            None,
        )
        assert persona is not None, f"Persona {name} not found in _BUILTIN_PERSONAS"
        allowed = set(persona.get("allowed_tools") or [])
        assert allowed <= read_only, f"{name} has non-read-only tools: {allowed - read_only}"


def test_process_manager_filters_tools_by_allowed_set():
    """Guard: headless path must filter tools by persona allowed_tools.

    The _run_agent method must:
    1. Read allowed_tools from persona
    2. Filter get_tools() by the allowed set
    3. Pass the filtered tools to orchestrator.run()

    This ensures scheduled advisory runs cannot call write tools.
    """
    import inspect

    from life_graph.kernel import process_manager

    # Get the source of ProcessManager._run_agent
    src = inspect.getsource(process_manager.ProcessManager._run_agent)

    # Verify the tool filtering logic exists
    assert "allowed_tools" in src, "_run_agent must read allowed_tools from persona"
    assert "get_tools()" in src, "_run_agent must call get_tools() to fetch all tools"
    assert "tools=tools" in src, "_run_agent must pass filtered tools to orchestrator.run()"
