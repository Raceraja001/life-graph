import life_graph.tools.assistant  # noqa: F401
import life_graph.tools.browser  # noqa: F401
import life_graph.tools.calculator  # noqa: F401
import life_graph.tools.code  # noqa: F401
import life_graph.tools.datetime_tool  # noqa: F401
import life_graph.tools.delegate  # noqa: F401
import life_graph.tools.filesystem  # noqa: F401
import life_graph.tools.git  # noqa: F401
import life_graph.tools.run_tests  # noqa: F401
import life_graph.tools.system_inspect  # noqa: F401
import life_graph.tools.terminal  # noqa: F401
import life_graph.tools.web_search  # noqa: F401
from life_graph.kernel.personas import _BUILTIN_PERSONAS, HOST_TOOLS
from life_graph.tools.registry import registry


def _persona(name):
    return next(p for p in _BUILTIN_PERSONAS if p["name"] == name)


def _jarvis():
    return _persona("jarvis")


def test_jarvis_prompt_discourages_redundant_delegation():
    sp = _jarvis()["system_prompt"].lower()
    assert "at most once" in sp or "do not delegate to the same" in sp
    assert "named" in sp  # must honor roles the user named


def test_jarvis_has_every_registered_tool_except_the_host_ones():
    """Jarvis holds every registered tool except the ones that touch files,
    code, the shell or the host. Asserted against the registry, not a fixed
    list, so a newly added tool must be either granted to Jarvis or named a
    host tool on purpose."""
    allowed = set(_jarvis()["allowed_tools"])
    registered = set(registry.tool_names)
    missing = registered - allowed - HOST_TOOLS
    assert not missing, f"Jarvis is missing registered tools: {missing}"
    assert "delegate_to_persona" in allowed


def test_jarvis_cannot_touch_files_code_or_the_shell():
    """Jarvis reads email and web pages and answers a phone token: injected text
    must not be able to write hooks or workflows, run commands or read files
    (security review 2026-10-24, C1)."""
    assert not set(_jarvis()["allowed_tools"]) & HOST_TOOLS
    assert HOST_TOOLS.issubset(registry.tool_names)  # names real tools


def test_code_and_system_work_has_somewhere_to_go():
    # The workers Jarvis hands code and system work to still hold their tools.
    assert {"file_read", "file_write", "run_command"} <= set(_persona("cody")["allowed_tools"])
    assert "run_command" in _persona("ops")["allowed_tools"]
    sp = _jarvis()["system_prompt"]
    assert "the code." not in sp and "cody" in sp and "ops" in sp
