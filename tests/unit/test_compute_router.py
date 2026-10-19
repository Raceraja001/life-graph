"""Routing queued coding work between the local GPU, free cloud models and later."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from life_graph.config import settings
from life_graph.services import compute_router as cr
from life_graph.services.compute_router import Snapshot, decide
from tests.unit.fakes import FakeSession, session_factory, sql

AWAY = Snapshot(active=None, local_hours=True, free_gb=30.0, cloud=())
CLOUD = ("openrouter/poolside/laguna-s-2.1:free",)


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(settings, "dev_route_queue", True)
    monkeypatch.setattr(settings, "dev_local_hours", "")
    monkeypatch.setattr(settings, "opencode_min_free_gb", 12.0)
    monkeypatch.setattr(settings, "user_active_minutes", 30)
    monkeypatch.setattr(settings, "user_timezone", "UTC")


@pytest.mark.parametrize(
    ("model", "free"),
    [
        ("openrouter/poolside/laguna-s-2.1:free", True),
        ("nvidia_nim/meta/llama-3.3-70b-instruct", True),
        ("openrouter/deepseek/deepseek-chat", False),
        ("ollama_chat/gpt-oss:20b", False),
        ("gemini/gemini-3.6-flash", False),
        (None, False),
    ],
)
def test_is_free_cloud_model(model, free):
    assert cr.is_free_cloud_model(model) is free


def test_cloud_models_need_a_key_and_must_be_free(monkeypatch):
    monkeypatch.setattr(
        settings,
        "dev_cloud_models",
        "openrouter/a:free, openrouter/paid, nvidia_nim/b, ollama_chat/c",
    )
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "")
    assert cr.cloud_models() == []
    monkeypatch.setattr(settings, "openrouter_api_key", "k")
    assert cr.cloud_models() == ["openrouter/a:free"]
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "k")
    assert cr.cloud_models() == ["openrouter/a:free", "nvidia_nim/b"]


@pytest.mark.parametrize(
    ("hour", "spec", "inside"),
    [
        (3, "", True),
        (23, "23-7", True),
        (2, "23-7", True),
        (7, "23-7", False),
        (12, "23-7", False),
        (10, "9-17", True),
        (17, "9-17", False),
        (12, "nonsense", True),
        (12, "5-5", True),
    ],
)
def test_in_local_hours(hour, spec, inside):
    assert cr.in_local_hours(hour, spec) is inside


def test_free_memory_gb(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 32000000 kB\nMemAvailable: 13631488 kB\n")
    assert cr.free_memory_gb(meminfo) == pytest.approx(13.0)
    assert cr.free_memory_gb(tmp_path / "missing") is None


def test_away_runs_locally():
    route = decide("code-fixer-local", {"origin": "nightly"}, AWAY)
    assert (route.where, route.persona) == ("local", "code-fixer-local")


def test_active_goes_to_a_free_cloud_model():
    snap = Snapshot(active="voice 3 min ago", local_hours=True, free_gb=30.0, cloud=CLOUD)
    route = decide("code-fixer-local", {}, snap)
    assert (route.where, route.persona) == ("cloud", cr.CLOUD_PERSONA)
    assert "voice 3 min ago" in route.reason


def test_active_without_a_cloud_model_waits():
    snap = Snapshot(active="switch says active", local_hours=True, free_gb=30.0, cloud=())
    route = decide("code-fixer-local", {}, snap)
    assert (route.where, route.persona) == ("wait", "code-fixer-local")
    assert "no free cloud model" in route.reason


def test_local_only_never_goes_to_the_cloud():
    snap = Snapshot(active="chat 1 min ago", local_hours=True, free_gb=30.0, cloud=CLOUD)
    assert decide("code-fixer-opencode", {"local_only": True}, snap).where == "wait"


def test_outside_local_hours_is_like_active(monkeypatch):
    monkeypatch.setattr(settings, "dev_local_hours", "23-7")
    snap = Snapshot(active=None, local_hours=False, free_gb=30.0, cloud=CLOUD)
    assert decide("code-fixer-local", {}, snap).where == "cloud"


def test_opencode_waits_for_free_memory():
    low = Snapshot(active=None, local_hours=True, free_gb=6.0, cloud=())
    route = decide("code-fixer-opencode", {"local_only": True}, low)
    assert route.where == "wait" and "6.0 GB" in route.reason
    # The 20B local persona does not need that much.
    assert decide("code-fixer-local", {}, low).where == "local"
    # Unknown memory (no /proc/meminfo) does not block it.
    unknown = Snapshot(active=None, local_hours=True, free_gb=None, cloud=())
    assert decide("code-fixer-opencode", {}, unknown).where == "local"


@pytest.mark.parametrize("persona", ["code-fixer", "code-fixer-cloud", "uzhavu-ops"])
def test_other_personas_run_as_assigned(persona):
    busy = Snapshot(active="voice", local_hours=True, free_gb=1.0, cloud=())
    assert decide(persona, {}, busy).where == "as_assigned"


def test_a_task_someone_started_is_not_moved():
    busy = Snapshot(active="voice", local_hours=True, free_gb=30.0, cloud=CLOUD)
    assert decide("code-fixer-local", {"interactive": True}, busy).where == "as_assigned"


def test_routing_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(settings, "dev_route_queue", False)
    busy = Snapshot(active="voice", local_hours=True, free_gb=30.0, cloud=CLOUD)
    assert decide("code-fixer-local", {}, busy).where == "as_assigned"


def _facts(monkeypatch, *, switch="auto", speech=None, cooling=False, models=CLOUD):
    async def presence(_t):
        return {"mode": switch, "expires_in": None}

    async def speech_in_use():
        return speech

    async def cloud_cooling():
        return cooling

    monkeypatch.setattr(cr, "get_presence", presence)
    monkeypatch.setattr(cr, "speech_in_use", speech_in_use)
    monkeypatch.setattr(cr, "cloud_cooling", cloud_cooling)
    monkeypatch.setattr(cr, "cloud_models", lambda: list(models))


NOW = datetime(2026, 10, 19, 15, 0, tzinfo=UTC)


async def test_snapshot_recent_chat_means_active(monkeypatch):
    _facts(monkeypatch)
    # Each of the three activity queries returns this timestamp.
    session = FakeSession(NOW - timedelta(minutes=4))
    snap = await cr.snapshot(session_factory(session), "raja", now=NOW)
    assert snap.active == "chat 4 min ago"
    assert snap.cloud == CLOUD
    assert len(session.statements) == 3
    assert all("'raja'" in sql(s) for s in session.statements)


async def test_snapshot_old_activity_means_away(monkeypatch):
    _facts(monkeypatch)
    session = FakeSession(NOW - timedelta(hours=2))
    assert (await cr.snapshot(session_factory(session), "raja", now=NOW)).active is None


async def test_snapshot_loaded_speech_model_means_active(monkeypatch):
    _facts(monkeypatch, speech="gemma3:12b")
    session = FakeSession(None)
    snap = await cr.snapshot(session_factory(session), "raja", now=NOW)
    assert snap.active == "gemma3:12b is loaded"
    assert session.statements == []  # no need to look further


async def test_snapshot_switch_overrides_detection(monkeypatch):
    _facts(monkeypatch, switch="away", speech="gemma3:12b")
    session = FakeSession(NOW)
    assert (await cr.snapshot(session_factory(session), "raja", now=NOW)).active is None
    _facts(monkeypatch, switch="active")
    snap = await cr.snapshot(session_factory(FakeSession(None)), "raja", now=NOW)
    assert snap.active == "switch says active"


async def test_snapshot_benched_cloud_route_has_no_models(monkeypatch):
    _facts(monkeypatch, cooling=True)
    snap = await cr.snapshot(session_factory(FakeSession(None)), "raja", now=NOW)
    assert snap.cloud == ()


async def test_last_activity_picks_the_latest_source():
    from life_graph.services.compute_router import last_activity

    chat, telegram, voice = NOW - timedelta(minutes=50), None, NOW - timedelta(minutes=5)
    session = FakeSession(chat, telegram, voice.replace(tzinfo=None))
    at, where = await last_activity(session, "raja")
    assert (at, where) == (voice, "voice")
    assert "'voice'" in sql(session.statements[2])
    assert "role = 'user'" in sql(session.statements[0])


class _FakeRedis:
    def __init__(self):
        self.data, self.ttls = {}, {}

    async def get(self, k):
        return self.data.get(k)

    async def ttl(self, k):
        return self.ttls.get(k, -1)

    async def set(self, k, v, ex=None):
        self.data[k] = v
        if ex:
            self.ttls[k] = ex

    async def delete(self, k):
        self.data.pop(k, None)

    async def exists(self, k):
        return int(k in self.data)


async def test_presence_switch_round_trip(monkeypatch):
    from life_graph.storage import redis as redis_mod

    fake = _FakeRedis()
    monkeypatch.setattr(redis_mod, "get_redis", lambda: fake)
    assert await cr.get_presence("raja") == {"mode": "auto", "expires_in": None}
    assert await cr.set_presence("raja", "away", 120)
    assert await cr.get_presence("raja") == {"mode": "away", "expires_in": 7200}
    assert await cr.set_presence("raja", "auto")
    assert (await cr.get_presence("raja"))["mode"] == "auto"
    with pytest.raises(ValueError):
        await cr.set_presence("raja", "sleeping")

    assert not await cr.cloud_cooling()
    await cr.cool_cloud_route(60)
    assert await cr.cloud_cooling()


async def test_presence_without_redis(monkeypatch):
    from life_graph.storage import redis as redis_mod

    monkeypatch.setattr(redis_mod, "get_redis", lambda: None)
    assert (await cr.get_presence("raja"))["mode"] == "auto"
    assert await cr.set_presence("raja", "away") is False
    assert await cr.cloud_cooling() is False
