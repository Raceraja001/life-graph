"""cody ambient action role — membership, seeded job, propose contract, safety rules.

Sub-project B Phase B2 Task 6: enrolls the ``cody`` persona into the ambient
(scheduled, propose-only) role system alongside ``ops``. cody proposes
``agent_task`` (open-ended, natural-language) actions rather than shell
commands — Task 2's router forces those to queue regardless of the risk
badge these safety rules set, so the rules here only affect what's displayed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.autonomy.safety.ambient_rules import (
    CODY_SAFETY_RULES,
    INFRA_SAFETY_RULES,
    seed_ambient_autonomy,
)


def test_cody_in_ambient_action():
    from life_graph.kernel.ambient import AMBIENT_ACTION

    assert "cody" in AMBIENT_ACTION


def test_cody_ambient_job_seeded_inactive():
    from life_graph.kernel.ambient import AMBIENT_JOBS

    job = next(j for j in AMBIENT_JOBS if j["name"] == "cody-ambient")
    assert job["active"] is False
    assert job["agent_name"] == "cody"


def test_cody_ambient_job_cron_does_not_collide_with_ops():
    from life_graph.kernel.ambient import AMBIENT_JOBS

    ops = next(j for j in AMBIENT_JOBS if j["name"] == "ops-ambient")
    cody = next(j for j in AMBIENT_JOBS if j["name"] == "cody-ambient")
    assert cody["cron_expression"] != ops["cron_expression"]


def test_cody_persona_has_agent_task_propose_contract():
    from life_graph.kernel.personas import _BUILTIN_PERSONAS

    cody = next(p for p in _BUILTIN_PERSONAS if p["name"] == "cody")
    assert "agent_task" in cody["system_prompt"]
    assert "instruction" in cody["system_prompt"]


# ── seed_ambient_autonomy: cody safety rules ──────────────────────────────
# Mirrors tests/unit/test_action_roles_seeding.py's fakes for the ops infra rules.


class _FakeSession:
    """Stands in for the AsyncSession used to look up existing rule names."""

    def __init__(self, existing_names=None):
        self.committed = False
        self._existing = existing_names or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = self._existing
        return result

    async def commit(self):
        self.committed = True


class _FakeSafetyRuleService:
    instances: list[_FakeSafetyRuleService] = []

    def __init__(self, session):
        self.session = session
        self.seed_defaults = AsyncMock()
        self.create_rule = AsyncMock()
        _FakeSafetyRuleService.instances.append(self)


class _FakeAutonomyLevelService:
    instances: list[_FakeAutonomyLevelService] = []

    def __init__(self, session_factory=None, **kwargs):
        self.session_factory = session_factory
        self.set_manual = AsyncMock(return_value=1)
        _FakeAutonomyLevelService.instances.append(self)


@pytest.fixture(autouse=True)
def _reset_fakes():
    _FakeSafetyRuleService.instances.clear()
    _FakeAutonomyLevelService.instances.clear()
    yield


def _patch_services(monkeypatch, existing_names=None):
    session = _FakeSession(existing_names)
    monkeypatch.setattr("life_graph.autonomy.safety.ambient_rules.async_session", lambda: session)
    monkeypatch.setattr(
        "life_graph.autonomy.safety.ambient_rules.SafetyRuleService",
        _FakeSafetyRuleService,
    )
    monkeypatch.setattr(
        "life_graph.autonomy.safety.ambient_rules.AutonomyLevelService",
        _FakeAutonomyLevelService,
    )
    return session


@pytest.mark.asyncio
async def test_seed_ambient_autonomy_creates_cody_rules(monkeypatch):
    _patch_services(monkeypatch, existing_names=[])

    await seed_ambient_autonomy("default")

    safety = _FakeSafetyRuleService.instances[0]
    calls = {c.kwargs["action_name"]: c.kwargs for c in safety.create_rule.await_args_list}

    cody_rule = next(r for r in CODY_SAFETY_RULES if r["action_name"].startswith("cody_"))
    assert cody_rule["action_name"] in calls
    assert calls[cody_rule["action_name"]]["risk_level"] in ("safe", "moderate", "dangerous")

    # Both infra (ops) and cody rules are created in the same pass.
    assert safety.create_rule.await_count == len(INFRA_SAFETY_RULES) + len(CODY_SAFETY_RULES)


@pytest.mark.asyncio
async def test_seed_ambient_autonomy_skips_existing_cody_rules(monkeypatch):
    existing = [r["action_name"] for r in INFRA_SAFETY_RULES + CODY_SAFETY_RULES]
    _patch_services(monkeypatch, existing_names=existing)

    await seed_ambient_autonomy("default")

    safety = _FakeSafetyRuleService.instances[0]
    safety.create_rule.assert_not_awaited()
