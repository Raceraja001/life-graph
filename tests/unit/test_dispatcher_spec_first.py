"""spec_first: the driver writes a short plan before touching anything, and
it's surfaced on the task result rather than lost in a narrative blob.
"""

from __future__ import annotations

import uuid

import pytest

import life_graph.drivers.dispatcher as disp_mod
from life_graph.core.budget import BudgetDecision
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.dispatcher import _SPEC_FIRST_PREFIX, TaskDispatcher, _extract_spec


class _FakeResult:
    def scalar(self):
        return 0

    def scalar_one_or_none(self):
        return None


class _FakeSession:
    async def execute(self, _stmt):
        return _FakeResult()

    def add(self, _obj):
        pass

    async def close(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class _SpecWritingDriver:
    name = "spec-writer"

    def __init__(self, output: str):
        self._output = output
        self.instruction_seen: str | None = None

    def cost_per_task(self) -> float:
        return 0.0

    async def dispatch(self, packet, workdir, timeout=300) -> DriverResult:
        self.instruction_seen = packet.instruction
        return DriverResult(success=True, output=self._output, cost_usd=0.0)


async def _noop(*_a, **_k):
    return None


async def _allow(*_a, **_k):
    return BudgetDecision(
        allowed=True, throttled=False, reason="ok",
        spent_usd=0.0, cap_usd=10.0, remaining_usd=10.0,
    )


def _wire(disp, monkeypatch, driver):
    async def _packet(*_a, **kwargs):
        return ContextPacket(
            task_id=uuid.uuid4(), tenant_id="t1", task_type="code",
            instruction="Add a helper function", project_context={},
        )

    async def _pick(*_a, **_k):
        return driver

    monkeypatch.setattr(disp._context_builder, "build_packet", _packet)
    monkeypatch.setattr(disp, "_select_driver", _pick)
    monkeypatch.setattr(disp, "_emit", _noop)
    monkeypatch.setattr(disp, "_record_stats", _noop)
    monkeypatch.setattr(disp_mod.governor, "authorize", _allow)
    monkeypatch.setattr(disp_mod.governor, "record", _noop)


def test_extract_spec_pulls_the_section_out():
    output = (
        "## Spec\n"
        "**Requirements:** must not break existing callers.\n"
        "**Tasks:** 1. add function 2. add test\n\n"
        "## Implementation\n"
        "Added `helper()` to utils.py."
    )
    assert _extract_spec(output) == (
        "**Requirements:** must not break existing callers.\n"
        "**Tasks:** 1. add function 2. add test"
    )


def test_extract_spec_none_when_absent():
    assert _extract_spec("Just did the thing, no headings.") is None
    assert _extract_spec(None) is None


@pytest.mark.asyncio
async def test_spec_first_prefixes_the_instruction_sent_to_the_driver(monkeypatch):
    driver = _SpecWritingDriver("## Spec\nplan\n\n## Implementation\ndone")
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)

    await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="Add a helper function",
        verify_chain=[], spec_first=True,
    )

    assert driver.instruction_seen.startswith(_SPEC_FIRST_PREFIX)
    assert driver.instruction_seen.endswith("Add a helper function")


@pytest.mark.asyncio
async def test_spec_first_off_leaves_the_instruction_untouched(monkeypatch):
    driver = _SpecWritingDriver("did it")
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)

    await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="Add a helper function",
        verify_chain=[], spec_first=False,
    )

    assert driver.instruction_seen == "Add a helper function"


@pytest.mark.asyncio
async def test_spec_surfaces_in_result_metadata(monkeypatch):
    driver = _SpecWritingDriver(
        "## Spec\n**Tasks:** 1. do the thing\n\n## Implementation\ndone"
    )
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="Add a helper function",
        verify_chain=[], spec_first=True,
    )

    assert result.metadata["spec"] == "**Tasks:** 1. do the thing"


@pytest.mark.asyncio
async def test_no_spec_section_leaves_metadata_without_a_spec_key(monkeypatch):
    """The driver ignored the instruction (or the model didn't comply) --
    don't fabricate an empty spec entry, just omit it."""
    driver = _SpecWritingDriver("Just did it, no spec section.")
    disp = TaskDispatcher(session_factory=lambda: _FakeSession(), event_bus=None)
    _wire(disp, monkeypatch, driver)

    result = await disp.dispatch_task(
        tenant_id="t1", task_id=str(uuid.uuid4()), instruction="Add a helper function",
        verify_chain=[], spec_first=True,
    )

    assert "spec" not in (result.metadata or {})
