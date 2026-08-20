import life_graph.tools.browser  # noqa: F401
import life_graph.tools.calculator  # noqa: F401
import life_graph.tools.datetime_tool  # noqa: F401
import life_graph.tools.delegate  # noqa: F401
import life_graph.tools.filesystem  # noqa: F401
import life_graph.tools.git  # noqa: F401
import life_graph.tools.system_inspect  # noqa: F401
import life_graph.tools.terminal  # noqa: F401
import life_graph.tools.web_search  # noqa: F401
from life_graph.kernel.personas import _BUILTIN_PERSONAS
from life_graph.tools.registry import registry


def _jarvis():
    return next(p for p in _BUILTIN_PERSONAS if p["name"] == "jarvis")


def test_jarvis_prompt_discourages_redundant_delegation():
    sp = _jarvis()["system_prompt"].lower()
    assert "at most once" in sp or "do not delegate to the same" in sp
    assert "named" in sp  # must honor roles the user named


def test_jarvis_has_every_registered_tool_plus_delegation():
    """Jarvis is the most powerful persona, not just a coordinator — he holds
    every real registered tool directly and only reaches for
    delegate_to_persona when a subtask needs a specialist's own driver/
    verifier chain (e.g. cody's tests_pass check). Deliberately assertive
    against the tool registry, not a fixed snapshot list, so a newly added
    tool must be explicitly granted to Jarvis too rather than silently
    left out."""
    allowed = set(_jarvis()["allowed_tools"])
    registered = set(registry.tool_names)
    missing = registered - allowed
    assert not missing, f"Jarvis is missing registered tools: {missing}"
    assert "delegate_to_persona" in allowed
