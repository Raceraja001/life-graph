"""One rule for which tools an agent run gets (audit M14).

``kernel/process_manager.py::_run_agent`` cut the owner's personal tools from
a general cloud run and the write tools from a temporary chat;
``drivers/local.py::dispatch`` said it mirrored that code and did neither, so
a dispatched task on a cloud model (an explicit cloud ``persona_model``, or
the cloud default ``agent_llm_model``) was handed ``memory_search``,
``email_read`` and the rest. Both now call ``lead.resolve_run_tools``.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from life_graph.drivers.base import ContextPacket
from life_graph.drivers.local import LocalDriver
from life_graph.services import lead
from life_graph.services.lead import PERSONAL_TOOLS, TEMPORARY_BLOCKED_TOOLS, resolve_run_tools

REGISTRY = ["git_status", "memory_search", "email_read", "memory_save", "file_write", "web_get"]
_REG = SimpleNamespace(tool_names=REGISTRY)

# (persona tools, override, cloud, temporary, expected)
CASES = [
    # No cut: what the persona (or the override) says, None stays "all tools".
    (None, None, False, False, None),
    (["git_status", "memory_search"], None, False, False, ["git_status", "memory_search"]),
    ([], None, False, False, []),
    (["git_status"], ["web_get"], False, False, ["web_get"]),  # override REPLACES
    (["git_status"], [], False, False, []),  # an empty override is an allowlist
    # Cloud: personal tools go, whatever asked for them.
    (None, None, True, False, ["git_status", "file_write", "web_get"]),
    (["git_status", "memory_search"], None, True, False, ["git_status"]),
    (["git_status"], ["memory_search", "email_read"], True, False, []),  # override can't
    (["memory_save", "file_write"], None, True, False, ["file_write"]),
    # Temporary: nothing left behind.
    (None, None, False, True, ["git_status", "memory_search", "email_read", "web_get"]),
    (["memory_save", "file_write", "git_status"], None, False, True, ["git_status"]),
    (["git_status"], ["code_edit", "web_get"], False, True, ["web_get"]),
    # Both.
    (None, None, True, True, ["git_status", "web_get"]),
    (["memory_search", "file_write", "web_get"], None, True, True, ["web_get"]),
]


@pytest.mark.parametrize(("persona_tools", "override", "cloud", "temporary", "expected"), CASES)
def test_resolve_run_tools(persona_tools, override, cloud, temporary, expected):
    got = resolve_run_tools(
        {"allowed_tools": persona_tools},
        override,
        cloud=cloud,
        temporary=temporary,
        registry=_REG,
    )
    assert got == expected


def test_no_persona_is_all_tools():
    assert resolve_run_tools(None, cloud=False, temporary=False) is None


def test_the_cut_never_adds_a_tool():
    for persona_tools, override, cloud, temporary, _ in CASES:
        got = resolve_run_tools(
            {"allowed_tools": persona_tools},
            override,
            cloud=cloud,
            temporary=temporary,
            registry=_REG,
        )
        asked = override if override is not None else persona_tools
        if got is not None:
            assert set(got) <= set(asked if asked is not None else REGISTRY)
            if cloud:
                assert not set(got) & PERSONAL_TOOLS
            if temporary:
                assert not set(got) & TEMPORARY_BLOCKED_TOOLS


def test_all_tools_defaults_to_the_live_registry(monkeypatch):
    import importlib

    # The module, not the package attribute of the same name (the instance).
    registry_mod = importlib.import_module("life_graph.tools.registry")

    class _Reg:
        tool_names = ["memory_search", "datetime_now"]

    monkeypatch.setattr(registry_mod, "registry", _Reg())
    assert resolve_run_tools(None, cloud=True, temporary=False) == ["datetime_now"]


# ── both callers use it ─────────────────────────────────────────────────────


def test_both_run_paths_call_the_one_rule():
    import inspect

    from life_graph.drivers import local
    from life_graph.kernel import process_manager

    assert "resolve_run_tools(" in inspect.getsource(process_manager.ProcessManager._run_agent)
    assert "resolve_run_tools(" in inspect.getsource(local.LocalDriver.dispatch)
    # The copies are gone: neither filters on the constants itself any more.
    for mod in (process_manager, local):
        src = inspect.getsource(mod)
        assert "lead.PERSONAL_TOOLS" not in src
        assert "lead.TEMPORARY_BLOCKED_TOOLS" not in src
    assert lead.resolve_run_tools is resolve_run_tools


# ── drivers/local.py: a cloud model never gets the personal tools ───────────


class _FakeOrchestrator:
    calls: list[dict] = []

    def __init__(self, *_a, **_k):
        pass

    def run(self, **kwargs):
        _FakeOrchestrator.calls.append(kwargs)

        async def _gen():
            yield 'data: {"type": "token", "content": "done"}'

        return _gen()


@pytest.fixture
def fake_orchestrator(monkeypatch):
    _FakeOrchestrator.calls = []
    monkeypatch.setattr("life_graph.agents.orchestrator.AgentOrchestrator", _FakeOrchestrator)
    import life_graph.tools.git  # noqa: F401
    import life_graph.tools.memory_search  # noqa: F401  (registers memory_search)

    return _FakeOrchestrator


@pytest.fixture
def local_fallbacks(monkeypatch):
    """Fail-over stays local, so only the run's own model decides."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "llm_fallback_chain", "")
    monkeypatch.setattr(settings, "llm_paid_fallback_model", None)


def _packet(**kw) -> ContextPacket:
    return ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="research",
        instruction="summarise the notes",
        **kw,
    )


def _names(call: dict) -> set[str]:
    return {t["function"]["name"] for t in call["tools"]}


@pytest.mark.asyncio
async def test_a_cloud_persona_model_loses_the_personal_tools(
    fake_orchestrator, local_fallbacks, tmp_path
):
    await LocalDriver().dispatch(
        _packet(allowed_tools=["git_status", "memory_search"], persona_model="gemini/x"),
        tmp_path,
    )
    assert _names(fake_orchestrator.calls[0]) == {"git_status"}


@pytest.mark.asyncio
async def test_a_local_persona_model_keeps_them(fake_orchestrator, local_fallbacks, tmp_path):
    await LocalDriver().dispatch(
        _packet(
            allowed_tools=["git_status", "memory_search"],
            persona_model="ollama_chat/qwen3:14b",
        ),
        tmp_path,
    )
    assert _names(fake_orchestrator.calls[0]) == {"git_status", "memory_search"}


@pytest.mark.asyncio
async def test_an_unscoped_dispatch_on_the_cloud_default_loses_them(
    fake_orchestrator, local_fallbacks, monkeypatch, tmp_path
):
    """No persona and the default agent model is a cloud one: the whole
    registry minus the personal tools, not the whole registry."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "agent_llm_model", "gemini/gemini-3.6-flash")
    await LocalDriver().dispatch(_packet(), tmp_path)

    names = _names(fake_orchestrator.calls[0])
    assert "git_status" in names
    assert not names & PERSONAL_TOOLS


@pytest.mark.asyncio
async def test_a_cloud_fallback_counts_as_cloud(fake_orchestrator, monkeypatch, tmp_path):
    """A local model that may fail over to a cloud one is not a local run."""
    from life_graph.config import settings

    monkeypatch.setattr(settings, "llm_fallback_chain", "gemini/gemini-3.5-flash-lite")
    await LocalDriver().dispatch(
        _packet(
            allowed_tools=["git_status", "memory_search"],
            persona_model="ollama_chat/qwen3:14b",
        ),
        tmp_path,
    )
    assert _names(fake_orchestrator.calls[0]) == {"git_status"}
