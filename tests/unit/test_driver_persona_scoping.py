# tests/unit/test_driver_persona_scoping.py
"""Driver-layer regressions from the B2 final whole-branch review.

Two defects, both only visible once the ambient action pipeline actually
reaches ``TaskDispatcher.dispatch_task`` (every task-scoped review mocked
``dispatch_task`` wholesale, so neither showed up):

1. ``project_id="ambient"`` — the ambient pseudo-project id is a plain string,
   not a UUID. ``uuid.UUID("ambient")`` raised ``ValueError`` and aborted every
   approved agent_task dispatch.
2. ``LocalDriver`` ran with the FULL tool registry (including the host shell
   ``run_command``) and a generic system prompt, ignoring the pinned persona's
   ``allowed_tools`` / ``system_prompt`` entirely.
"""

from __future__ import annotations

import uuid

import pytest

import life_graph.drivers.dispatcher as disp_mod
from life_graph.core.budget import BudgetDecision
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import TaskDispatcher, _coerce_project_uuid
from life_graph.drivers.local import LocalDriver

# ── fakes ──────────────────────────────────────────────────────────────────


class _FakeResult:
    """Stands in for a SQLAlchemy Result across every accessor the dispatcher uses."""

    def __init__(self, persona=None, count: int = 0):
        self._persona = persona
        self._count = count

    def scalar(self):
        return self._count

    def scalar_one_or_none(self):
        return self._persona

    def one_or_none(self):
        return None


class _FakeSession:
    def __init__(self, persona=None):
        self._persona = persona

    async def execute(self, _stmt):
        return _FakeResult(persona=self._persona)

    def add(self, _obj):
        pass

    async def close(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class _SpyDriver:
    name = "spy"

    def __init__(self):
        self.packet: ContextPacket | None = None

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        self.packet = packet
        return DriverResult(success=True, output="ran", cost_usd=0.0)


class _FakePersona:
    """Minimal stand-in for an ``AgentPersona`` ORM row."""

    def __init__(self, system_prompt="You are cody.", allowed_tools=None, properties=None):
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools
        self.properties = properties or {}


async def _noop(*_a, **_k):
    return None


async def _allow(*_a, **_k):
    return BudgetDecision(
        allowed=True,
        throttled=False,
        reason="ok",
        spent_usd=0.0,
        cap_usd=10.0,
        remaining_usd=10.0,
    )


def _wire(disp: TaskDispatcher, monkeypatch, driver: _SpyDriver, capture: dict):
    """Stub out everything except the code under test (project-id normalization,
    persona resolution, packet scoping)."""

    async def _packet(*_a, **kwargs):
        capture["build_packet_project_id"] = kwargs.get("project_id")
        return ContextPacket(
            task_id=uuid.uuid4(),
            tenant_id=kwargs.get("tenant_id", "t1"),
            task_type=kwargs.get("task_type", "code"),
            instruction=kwargs.get("instruction", "do it"),
        )

    async def _pick(*_a, **kwargs):
        capture["select_driver_persona"] = kwargs.get("persona")
        return driver

    monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
    monkeypatch.setattr(disp, "_select_driver", _pick)
    monkeypatch.setattr(disp, "_emit", _noop)
    monkeypatch.setattr(disp, "_record_stats", _noop)
    monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
    monkeypatch.setattr(disp_mod.governor, "record", _noop)


# ── Critical #1: non-UUID project_id must not crash the dispatch ───────────


def test_coerce_project_uuid_handles_the_ambient_pseudo_project():
    from life_graph.services.action_proposal_bridge import AMBIENT_PROJECT_ID

    assert _coerce_project_uuid(AMBIENT_PROJECT_ID) is None  # "ambient" — not a UUID
    assert _coerce_project_uuid(None) is None
    real = uuid.uuid4()
    assert _coerce_project_uuid(real) == real
    assert _coerce_project_uuid(str(real)) == real


@pytest.mark.asyncio
async def test_dispatch_task_with_ambient_project_id_does_not_raise(monkeypatch):
    """The exact reproduction from the final review: an approved agent_task
    carries project_id="ambient" and used to die on uuid.UUID()."""
    driver = _SpyDriver()
    capture: dict = {}
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver, capture)

    result = await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix the flaky test",
        task_type="code",
        project_id="ambient",
        verify_chain=[],
    )

    assert result.success is True
    assert driver.packet is not None  # reached driver selection + dispatch
    assert capture["build_packet_project_id"] is None  # degraded to "no project"


@pytest.mark.asyncio
async def test_check_wip_limits_tolerates_non_uuid_project_id():
    """The other uuid.UUID() call site — it must not blow past the tenant check."""
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    # Must not raise; a non-UUID project simply gets no project-level WIP check.
    await disp._check_wip_limits("t1", "ambient", _FakeSession())


# ── Critical #2a: dispatch_task threads the persona onto the packet ────────


@pytest.mark.asyncio
async def test_dispatch_task_scopes_packet_to_persona(monkeypatch):
    driver = _SpyDriver()
    capture: dict = {}
    persona = _FakePersona(
        system_prompt="You are cody, a careful engineer.",
        allowed_tools=["file_read", "file_write"],
    )
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(persona), event_bus=None)
    _wire(disp, monkeypatch, driver, capture)

    await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="fix it",
        task_type="code",
        project_id="ambient",
        persona_name="cody",
        verify_chain=[],
    )

    assert driver.packet.persona_system_prompt == "You are cody, a careful engineer."
    assert driver.packet.allowed_tools == ["file_read", "file_write"]
    # resolved once and handed to _select_driver — not looked up twice
    assert capture["select_driver_persona"] is persona


@pytest.mark.asyncio
async def test_dispatch_task_without_persona_leaves_packet_unscoped(monkeypatch):
    """No persona_name => both fields stay None => every existing caller keeps
    exactly today's behavior."""
    driver = _SpyDriver()
    capture: dict = {}
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(_FakePersona()), event_bus=None)
    _wire(disp, monkeypatch, driver, capture)

    await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="do it",
        task_type="code",
        verify_chain=[],
    )

    assert driver.packet.persona_system_prompt is None
    assert driver.packet.allowed_tools is None
    assert capture["select_driver_persona"] is None


@pytest.mark.asyncio
async def test_dispatch_task_unknown_persona_does_not_raise(monkeypatch):
    """A missing persona logs a warning and dispatches unscoped — it must not
    break personaless/system dispatches."""
    driver = _SpyDriver()
    capture: dict = {}
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(None), event_bus=None)
    _wire(disp, monkeypatch, driver, capture)

    result = await disp.dispatch_task(
        tenant_id="t1",
        task_id=str(uuid.uuid4()),
        instruction="do it",
        task_type="code",
        persona_name="nope",
        verify_chain=[],
    )

    assert result.success is True
    assert driver.packet.allowed_tools is None
    assert driver.packet.persona_system_prompt is None


@pytest.mark.asyncio
async def test_bounce_packet_keeps_persona_scoping(monkeypatch):
    """A re-dispatch must not silently regain the full tool registry."""

    class _BounceDriver:
        name = "bounce"

        def __init__(self):
            self.packets: list[ContextPacket] = []

        def cost_per_task(self) -> float:
            return 0.0

        async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
            self.packets.append(packet)
            return DriverResult(success=True, output="ran")

    driver = _BounceDriver()
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    monkeypatch.setattr(disp, "_emit", _noop)

    packet = ContextPacket(
        task_id=uuid.uuid4(),
        tenant_id="t1",
        task_type="code",
        instruction="fix it",
        persona_system_prompt="You are cody.",
        allowed_tools=["file_read"],
    )

    from life_graph.services.verifiers import VerifierResult

    async def _chain(*_a, **_k):
        return [VerifierResult(verifier="build_ok", passed=True, evidence="")]

    monkeypatch.setattr(disp_mod.verifier_chain, "run_chain", _chain)

    await disp._bounce_task(
        tenant_id="t1",
        task_id="task-1",
        driver=driver,
        packet=packet,
        workdir=None,
        failure_report=[VerifierResult(verifier="lint_clean", passed=False, evidence="E501")],
        session=_FakeSession(),
        verify_chain=["build_ok"],
    )

    assert driver.packets[0].allowed_tools == ["file_read"]
    assert driver.packets[0].persona_system_prompt == "You are cody."


# ── Critical #2b: LocalDriver honours the packet's persona scoping ─────────


class _FakeOrchestrator:
    """Captures the kwargs LocalDriver hands to ``orchestrator.run``."""

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
    # Make sure real tools are registered so the allowlist filter has something
    # to filter (imports are idempotent — the registry dedupes by name).
    import life_graph.tools.datetime_tool  # noqa: F401
    import life_graph.tools.git  # noqa: F401
    import life_graph.tools.terminal  # noqa: F401

    return _FakeOrchestrator


def _packet(**kw) -> ContextPacket:
    base = {
        "task_id": uuid.uuid4(),
        "tenant_id": "t1",
        "task_type": "code",
        "instruction": "fix the flaky test",
    }
    base.update(kw)
    return ContextPacket(**base)


@pytest.mark.asyncio
async def test_local_driver_passes_only_the_personas_tools(fake_orchestrator, tmp_path):
    result = await LocalDriver().dispatch(
        _packet(allowed_tools=["git_status", "git_log"]), tmp_path
    )

    assert result.success is True
    kwargs = fake_orchestrator.calls[0]
    names = {t["function"]["name"] for t in kwargs["tools"]}
    assert names == {"git_status", "git_log"}
    assert "run_command" not in names  # the host shell is the whole point


@pytest.mark.asyncio
async def test_local_driver_empty_allowlist_means_no_tools(fake_orchestrator, tmp_path):
    """An explicit empty allowlist is an allowlist, not "unset"."""
    await LocalDriver().dispatch(_packet(allowed_tools=[]), tmp_path)

    assert fake_orchestrator.calls[0]["tools"] == []


@pytest.mark.asyncio
async def test_local_driver_without_allowlist_keeps_default_behavior(fake_orchestrator, tmp_path):
    """allowed_tools=None => no tools= kwarg at all => the orchestrator resolves
    the full registry, exactly as before this change."""
    await LocalDriver().dispatch(_packet(), tmp_path)

    assert "tools" not in fake_orchestrator.calls[0]


@pytest.mark.asyncio
async def test_local_driver_uses_the_persona_system_prompt(fake_orchestrator, tmp_path):
    await LocalDriver().dispatch(
        _packet(
            persona_system_prompt="You are cody, a careful engineer.",
            project_context={"name": "life-graph"},
        ),
        tmp_path,
    )

    prompt = fake_orchestrator.calls[0]["system_prompt"]
    assert prompt.startswith("You are cody, a careful engineer.")
    assert "You are an AI agent executing a task." not in prompt
    assert "life-graph" in prompt  # the context sections still append


@pytest.mark.asyncio
async def test_local_driver_falls_back_to_generic_prompt(fake_orchestrator, tmp_path):
    await LocalDriver().dispatch(_packet(), tmp_path)

    assert fake_orchestrator.calls[0]["system_prompt"].startswith(
        "You are an AI agent executing a task."
    )
