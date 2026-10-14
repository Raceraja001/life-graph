"""Phases F and G: phone conversation (ask, speak, modes) and SM-2 study cards."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from life_graph.config import settings
from life_graph.services import assistant_chat, study

# ── F: conversation ─────────────────────────────────────────────────────────


class FakePM:
    def __init__(self, statuses, result=None, error=None):
        self.statuses = list(statuses)
        self.result, self.error = result, error
        self.spawned = []

    async def spawn(self, **kw):
        self.spawned.append(kw)
        return {"task_id": "t1"}

    async def get_task(self, tenant_id, task_id):
        status = self.statuses.pop(0) if self.statuses else "running"
        return SimpleNamespace(status=status, result=self.result, error=self.error)


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(assistant_chat, "POLL_SECONDS", 0.01)


@pytest.mark.asyncio
async def test_ask_runs_the_assistant_persona_and_returns_its_answer(fast, monkeypatch):
    monkeypatch.setattr(settings, "telegram_assistant_persona", "assistant")
    pm = FakePM(["running", "completed"], result={"response": " Two meetings tomorrow. "})
    assert await assistant_chat.ask("raja", "what's tomorrow?", pm=pm) == "Two meetings tomorrow."
    assert pm.spawned[0]["agent_name"] == "assistant"
    assert pm.spawned[0]["input_data"] == {"message": "what's tomorrow?"}


@pytest.mark.asyncio
async def test_ask_reports_failure_and_timeouts(fast):
    failed = FakePM(["failed"], error="model unavailable")
    assert "failed" in await assistant_chat.ask("t", "q", pm=failed)
    slow = FakePM([])
    assert "longer than expected" in await assistant_chat.ask("t", "q", pm=slow, timeout=0.05)


def test_spoken_text_has_no_markup_links_or_code():
    text = "**Today**: see https://x.example/a and `code`\n```py\nprint(1)\n```\n# Done"
    out = assistant_chat.spoken(text)
    assert "**" not in out and "http" not in out and "print(1)" not in out
    assert "(link)" in out and "(code omitted)" in out


@pytest.mark.asyncio
async def test_speak_is_off_without_a_tts_server(monkeypatch):
    monkeypatch.setattr(settings, "tts_base_url", "")
    assert await assistant_chat.speak("hello") is None


@pytest.mark.asyncio
async def test_speak_calls_an_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "tts_base_url", "http://localhost:8010")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read()
        return httpx.Response(200, content=b"OggS-audio")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        audio = await assistant_chat.speak("Hi **there**", client=client)
    assert audio == b"OggS-audio" and seen["path"] == "/v1/audio/speech"
    assert b'"response_format":"opus"' in seen["body"].replace(b" ", b"")

    def broken(request):
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as client:
        assert await assistant_chat.speak("x", client=client) is None


@pytest.mark.asyncio
async def test_mode_defaults_to_capture_without_redis(monkeypatch):
    import life_graph.storage.redis as r

    monkeypatch.setattr(r, "get_redis", lambda: None)
    assert await assistant_chat.get_mode(1) == "capture"
    assert await assistant_chat.set_mode(1, "chat") is False


# ── G: SM-2 ─────────────────────────────────────────────────────────────────

TODAY = date(2026, 10, 14)


def test_sm2_good_answers_space_out():
    ease, interval, reps = 2.5, 0, 0
    gaps = []
    for _ in range(4):
        ease, interval, reps, due = study.schedule(ease, interval, reps, "good", TODAY)
        gaps.append(interval)
    assert gaps == [1, 6, 15, 38]
    assert ease == 2.5  # "good" (q=4) leaves ease unchanged


def test_sm2_again_resets_and_lowers_ease():
    ease, interval, reps, due = study.schedule(2.5, 15, 3, "again", TODAY)
    assert (interval, reps, due) == (1, 0, date(2026, 10, 15))
    assert ease < 2.5
    floor = 1.3
    for _ in range(10):
        ease, *_ = study.schedule(ease, 1, 0, "again", TODAY)
    assert ease == floor


def test_easy_raises_ease_and_hard_lowers_it():
    assert study.schedule(2.5, 6, 2, "easy", TODAY)[0] > 2.5
    assert study.schedule(2.5, 6, 2, "hard", TODAY)[0] < 2.5


def test_dedup_key_ignores_case_and_punctuation():
    assert study.dedup_key("What is SM-2?") == study.dedup_key("what is sm 2")
    assert study.dedup_key("a") != study.dedup_key("b")


@pytest.mark.asyncio
async def test_write_cards_filters_bad_output():
    class LM:
        async def chat_local_only(self, **_kw):
            return '{"cards": [{"front": "Q1?", "back": "A1"}, {"front": "", "back": "x"}]}'

    assert await study.write_cards("notes", client=LM()) == [{"front": "Q1?", "back": "A1"}]

    class Broken:
        async def chat_local_only(self, **_kw):
            return "nope"

    assert await study.write_cards("notes", client=Broken()) == []
    assert await study.write_cards("   ", client=LM()) == []


def test_brief_line():
    assert study.brief_line(0) is None
    assert study.brief_line(1) == "Study: 1 card due — /review on Telegram"
