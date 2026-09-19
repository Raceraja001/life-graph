"""An optimized prompt must actually reach production extraction.

prompt_versions could be created and activated, but nothing read them, so a
"deployed" improvement changed nothing. These pin the wiring: extraction asks
the resolver, few-shot examples become real turns, traces are recorded, and
every failure path falls back to the built-in prompt.
"""

from __future__ import annotations

import json
import uuid

import pytest

from life_graph.config import settings
from life_graph.extraction import llm as llm_module
from life_graph.extraction.llm import LLMExtractor, build_extraction_messages, default_prompt
from life_graph.self_improving import prompt_resolver
from life_graph.self_improving.prompt_resolver import ResolvedPrompt, resolve_prompt

_GOOD = json.dumps(
    {
        "facts": [
            {"content": "Uses uv", "fact_type": "preference", "confidence": 0.9, "entities": []}
        ]
    }
)


def test_few_shot_examples_become_turns_before_the_real_request():
    example = {"input": "I use pnpm", "output": {"facts": [{"content": "Uses pnpm"}]}}
    messages = build_extraction_messages("SYS", [example], "I use uv", structured=True)

    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[0]["content"] == "SYS"
    assert "I use pnpm" in messages[1]["content"]
    assert json.loads(messages[2]["content"]) == example["output"]
    assert "I use uv" in messages[3]["content"]


@pytest.fixture(autouse=True)
def _clean_cache():
    prompt_resolver.invalidate()
    yield
    prompt_resolver.invalidate()


@pytest.mark.asyncio
async def test_kill_switch_forces_the_built_in_prompt(monkeypatch):
    monkeypatch.setattr(settings, "self_improving_prompts_enabled", False)

    async def _boom(*_):
        raise AssertionError("must not even look up a version")

    monkeypatch.setattr(prompt_resolver, "_load_active", _boom)
    assert (await resolve_prompt("t", "capture_extraction", "DEFAULT")).is_default


@pytest.mark.asyncio
async def test_lookup_failure_falls_back_to_the_built_in_prompt(monkeypatch):
    async def _boom(*_):
        raise RuntimeError("db down")

    monkeypatch.setattr(prompt_resolver, "_load_active", _boom)
    prompt = await resolve_prompt("t", "capture_extraction", "DEFAULT")
    assert prompt.is_default and prompt.prompt_text == "DEFAULT"


@pytest.mark.asyncio
async def test_active_version_is_cached_until_invalidated(monkeypatch):
    calls = []

    async def _load(tenant, task):
        calls.append(1)
        return ResolvedPrompt("v1", "OPTIMIZED", [])

    monkeypatch.setattr(prompt_resolver, "_load_active", _load)
    assert (await resolve_prompt("t", "x", "D")).version_id == "v1"
    await resolve_prompt("t", "x", "D")
    assert len(calls) == 1
    prompt_resolver.invalidate("t", "x")  # what activate() does
    await resolve_prompt("t", "x", "D")
    assert len(calls) == 2


class _Client:
    def __init__(self):
        self.messages = None

    async def chat(self, **kwargs):
        self.messages = kwargs["messages"]
        return _GOOD


@pytest.mark.asyncio
async def test_extraction_uses_the_active_version_and_records_a_trace(monkeypatch):
    example = {"input": "I use pnpm", "output": {"facts": []}}

    async def _resolve(tenant, task, default):
        return ResolvedPrompt("v7", "OPTIMIZED PROMPT", [example])

    recorded = {}
    trace_id = uuid.uuid4()

    async def _record(**kwargs):
        recorded.update(kwargs)
        return trace_id

    monkeypatch.setattr(llm_module, "resolve_prompt", _resolve)
    monkeypatch.setattr(llm_module, "record_trace", _record)
    monkeypatch.setattr(llm_module, "current_tenant_or_none", lambda: "t")
    client = _Client()

    facts = await LLMExtractor(lm_client=client)._extract_local("I use uv now.")

    assert client.messages[0]["content"] == "OPTIMIZED PROMPT"
    assert len(client.messages) == 4  # the few-shot turns were sent
    assert recorded["prompt_version_id"] == "v7"
    assert recorded["input_text"] == "I use uv now."
    assert [f["content"] for f in recorded["facts"]] == ["Uses uv"]
    assert facts[0].trace_id == str(trace_id) and facts[0].trace_index == 0


@pytest.mark.asyncio
async def test_no_tenant_means_default_prompt_and_no_trace(monkeypatch):
    async def _record(**kwargs):
        raise AssertionError("no trace without a tenant")

    monkeypatch.setattr(llm_module, "record_trace", _record)
    monkeypatch.setattr(llm_module, "current_tenant_or_none", lambda: None)
    client = _Client()

    facts = await LLMExtractor(lm_client=client)._extract_local("I use uv now.")

    assert client.messages[0]["content"] == default_prompt()
    assert facts and facts[0].trace_id == ""


@pytest.mark.asyncio
async def test_a_failed_trace_write_does_not_lose_the_facts(monkeypatch):
    async def _record(**kwargs):
        return None  # record_trace swallows errors and returns None

    monkeypatch.setattr(llm_module, "record_trace", _record)
    monkeypatch.setattr(llm_module, "current_tenant_or_none", lambda: "t")

    facts = await LLMExtractor(lm_client=_Client())._extract_local("I use uv now.")

    assert [f.content for f in facts] == ["Uses uv"]
    assert facts[0].trace_id == ""
