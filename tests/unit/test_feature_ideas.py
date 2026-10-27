"""The feature watch's parts that need no database (docs/specs/research-and-tech-watch.md,
AC-10.6 to AC-10.8): source trust, spreading results, the assessment check, the topic setting."""

import json

import pytest

from life_graph.services.feature_ideas import is_leisure, is_pricing, validate
from life_graph.services.source_trust import source_trust


@pytest.mark.parametrize(
    ("url", "trust"),
    [
        ("https://help.openai.com/en/articles/123-release-notes", "official"),
        ("https://www.anthropic.com/news/claude", "official"),
        ("https://blog.google/products/gemini/new", "official"),
        ("https://github.com/open-webui/open-webui/releases", "official"),
        ("https://github.com/danny-avila/LibreChat/releases", "official"),
        # The lure the first run reported as "Open WebUI 2026 for Windows released".
        ("https://github.com/mapchancellorhaul/open-webui-2026", "suspicious"),
        ("https://github.com/someone/chatgpt-desktop-free", "suspicious"),
        ("https://github.com/someone/unrelated-tool", "unknown"),
        ("https://releasebot.io/updates/openai/chatgpt", "unknown"),
        ("https://openai.com.evil.example/fake", "unknown"),
        ("not a url", "unknown"),
    ],
)
def test_source_trust(url, trust):
    assert source_trust(url) == trust


def test_an_assessment_is_kept_only_for_a_finding_of_the_batch():
    ids = {"a", "b"}
    assert validate({"id": "z", "is_feature": True, "fit": "new"}, ids) is None
    assert validate("not a dict", ids) is None
    ok = validate(
        {"id": "a", "is_feature": True, "app": "ChatGPT", "fit": "PART", "suggestion": "x" * 500},
        ids,
    )
    assert ok["fit"] == "part" and ok["app"] == "ChatGPT" and len(ok["suggestion"]) == 300


def test_not_a_feature_carries_no_fit_or_suggestion():
    v = validate(
        {"id": "b", "is_feature": False, "fit": "new", "suggestion": "pay with MoMo"}, {"b"}
    )
    assert v == {
        "id": "b",
        "is_feature": False,
        "app": None,
        "fit": None,
        "suggestion": None,
        "worth": None,
        "why": None,
        "same_as": None,
    }
    # Anything but a JSON true is not a feature; an unknown fit is dropped.
    assert validate({"id": "b", "is_feature": "yes"}, {"b"})["is_feature"] is False
    assert validate({"id": "b", "is_feature": True, "fit": "maybe"}, {"b"})["fit"] is None


def test_worth_needs_a_known_level_and_carries_its_reason():
    v = validate({"id": "a", "is_feature": True, "worth": "HIGH", "why": "privacy"}, {"a"})
    assert (v["worth"], v["why"]) == ("high", "privacy")
    v = validate({"id": "a", "is_feature": True, "worth": "huge", "why": "x"}, {"a"})
    assert (v["worth"], v["why"]) == (None, None)


def test_same_as_names_another_finding_of_the_batch_or_a_known_idea():
    ids = {"a", "b"}
    assert validate({"id": "b", "is_feature": True, "same_as": "a"}, ids)["same_as"] == "a"
    assert validate({"id": "b", "is_feature": True, "same_as": "k"}, ids, {"k"})["same_as"] == "k"
    assert validate({"id": "b", "is_feature": True, "same_as": "b"}, ids)["same_as"] is None
    assert validate({"id": "b", "is_feature": True, "same_as": "zz"}, ids)["same_as"] is None
    assert validate({"id": "b", "is_feature": False, "same_as": "a"}, ids)["same_as"] is None


@pytest.mark.parametrize(
    ("title", "summary", "pricing"),
    [
        ("ChatGPT Pro 500 tier introduced", "", True),
        ("ChatGPT accepts MoMo payments", "a payment method for subscriptions", True),
        ("Claude Team plan now $25", "", True),
        ("Gemini pricing changes in Europe", "", True),
        ("ChatGPT adds locked chats", "hide chats behind a PIN", False),
        ("Gemini can schedule actions", "run a prompt every morning", False),
        ("Open WebUI adds audio uploads", "transcribe a recording", False),
        # Who gets a feature is not what it costs (the second run hid both).
        ("ChatGPT adds audio uploads", "available on all subscriptions", False),
        ("GPT-6 with Intelligent UI released", "rolling out to every tier", False),
        ("ChatGPT adds Slides", "free, then $20 per month", True),
    ],
)
def test_pricing_is_told_apart_in_code(title, summary, pricing):
    assert is_pricing(title, summary) is pricing


@pytest.mark.parametrize(
    ("title", "leisure"),
    [
        ("ChatGPT adds virtual try-on for clothes and accessories", True),
        ("Gemini adds games in chat", True),
        ("ChatGPT adds locked chats", False),
        ("Dots (always-on agents) released", False),
    ],
)
def test_shopping_and_games_are_told_apart_in_code(title, leisure):
    assert is_leisure(title) is leisure


def test_the_ideas_flag_is_read_from_the_topic_setting(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(
        settings,
        "tech_watch_topics",
        json.dumps({"Features": {"ideas": True, "queries": ["q"]}, "Models": {"queries": ["m"]}}),
    )
    specs = settings.tech_watch_topic_specs
    assert specs["Features"]["ideas"] is True and specs["Models"]["ideas"] is False


@pytest.mark.asyncio
async def test_spread_takes_a_query_at_a_time_and_caps_each_site(monkeypatch):
    import life_graph.tools.web_search as ws
    from life_graph.services import web_pages

    results = {
        "chatgpt": [f"https://tracker.example/{i}" for i in range(5)],
        "claude": ["https://tracker.example/c", "https://www.anthropic.com/news/a"],
        "gemini": ["https://blog.google/g"],
    }

    async def search(q):
        return {"results": [{"url": u, "title": u} for u in results[q]]}

    monkeypatch.setattr(ws, "search", search)
    plain = await web_pages.candidates(["chatgpt", "claude", "gemini"], limit=4)
    assert [h.url for h in plain] == [f"https://tracker.example/{i}" for i in range(4)]

    spread = await web_pages.candidates(["chatgpt", "claude", "gemini"], limit=4, spread=True)
    assert [h.url for h in spread] == [
        "https://tracker.example/0",
        "https://tracker.example/c",
        "https://blog.google/g",
        "https://www.anthropic.com/news/a",  # the tracker is at its two pages
    ]
