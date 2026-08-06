"""seed_ambient_autonomy — infra safety rules + ambient project L1 autonomy level.

Sub-project B (autonomous action roles) startup seeding: layers infra-specific safety
rules on top of SafetyRuleService.seed_defaults and sets the "ambient" project's
autonomy level to L1 so ops-ambient runs can auto-execute safe actions instead of
queuing forever at the default L0.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.autonomy.safety.ambient_rules import (
    CODY_SAFETY_RULES,
    INFRA_SAFETY_RULES,
    seed_ambient_autonomy,
)


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
async def test_seeds_defaults_and_infra_rules_and_sets_level(monkeypatch):
    session = _patch_services(monkeypatch, existing_names=[])

    await seed_ambient_autonomy("default")

    safety = _FakeSafetyRuleService.instances[0]
    safety.seed_defaults.assert_awaited_once_with("default")
    # Task 6: seed_ambient_autonomy also seeds cody's agent_task action rules in the
    # same pass (life_graph/autonomy/safety/ambient_rules.py CODY_SAFETY_RULES).
    assert safety.create_rule.await_count == len(INFRA_SAFETY_RULES) + len(CODY_SAFETY_RULES)
    assert session.committed is True

    level = _FakeAutonomyLevelService.instances[0]
    level.set_manual.assert_awaited_once()
    args = level.set_manual.await_args.args
    assert args[0] == "default"
    assert args[1] == "ambient"
    assert args[2] == 1


@pytest.mark.asyncio
async def test_infra_rules_have_expected_risk_categories_thresholds_and_guardrails(monkeypatch):
    _patch_services(monkeypatch, existing_names=[])

    await seed_ambient_autonomy("default")

    safety = _FakeSafetyRuleService.instances[0]
    calls = {c.kwargs["action_name"]: c.kwargs for c in safety.create_rule.await_args_list}

    for name in ("docker_ps", "disk_check", "memory_check", "git_status_check"):
        assert calls[name]["risk_level"] == "safe"
        assert calls[name]["trust_threshold"] == 0.3
        assert calls[name].get("is_guardrail", False) is False

    for name in ("restart_service", "docker_restart"):
        assert calls[name]["risk_level"] == "moderate"
        assert calls[name]["trust_threshold"] == 0.6

    for name in ("rm_command", "delete_infra", "drop_command", "migration_downgrade"):
        assert calls[name]["risk_level"] == "dangerous"
        assert calls[name]["is_guardrail"] is True


@pytest.mark.asyncio
async def test_skips_infra_rules_that_already_exist(monkeypatch):
    existing = [r["action_name"] for r in INFRA_SAFETY_RULES + CODY_SAFETY_RULES]
    _patch_services(monkeypatch, existing_names=existing)

    await seed_ambient_autonomy("default")

    safety = _FakeSafetyRuleService.instances[0]
    safety.create_rule.assert_not_awaited()
    safety.seed_defaults.assert_awaited_once()


@pytest.mark.asyncio
async def test_idempotent_on_second_call(monkeypatch):
    _patch_services(monkeypatch, existing_names=[])

    await seed_ambient_autonomy("default")
    await seed_ambient_autonomy("default")  # must not raise / must not error

    assert len(_FakeAutonomyLevelService.instances) == 2
    for level in _FakeAutonomyLevelService.instances:
        level.set_manual.assert_awaited_once()
    assert len(_FakeSafetyRuleService.instances) == 2
    for safety in _FakeSafetyRuleService.instances:
        safety.seed_defaults.assert_awaited_once()
