"""Local LLM extraction must constrain output to its schema.

The request used to be ``json_object`` with the schema pasted into the prompt.
Small local models then often answered with the schema itself — measured on
qwen3:4b, 2 of 8 extractions were usable. The parser saw no ``facts`` list,
returned [], and the pipeline silently fell back to the regex tier, producing
mangled memories. Constrained decoding (``json_schema``) made it 8 of 8.
"""

from __future__ import annotations

import json

import pytest

from life_graph.config import settings
from life_graph.extraction.llm import _EXTRACTION_SCHEMA, LLMExtractor

_GOOD = json.dumps(
    {
        "facts": [
            {"content": "Uses uv", "fact_type": "preference", "confidence": 0.9, "entities": []}
        ]
    }
)


class _FakeClient:
    """Returns queued responses in order and records every request."""

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def chat(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self._responses.pop(0) if self._responses else ""


def _user_text(call: dict) -> str:
    return call["messages"][1]["content"]


@pytest.fixture
def structured(monkeypatch):
    monkeypatch.setattr(settings, "lm_structured_output", True)


@pytest.mark.asyncio
async def test_sends_json_schema_and_keeps_schema_out_of_prompt(structured):
    client = _FakeClient(_GOOD)

    facts = await LLMExtractor(lm_client=client)._extract_local("I use uv now.")

    assert [f.content for f in facts] == ["Uses uv"]
    assert len(client.calls) == 1
    fmt = client.calls[0]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["schema"] == _EXTRACTION_SCHEMA
    # The pasted schema is what small models copied back; it must not be sent.
    assert '"properties"' not in _user_text(client.calls[0])


@pytest.mark.asyncio
async def test_falls_back_to_json_object_when_runtime_returns_nothing(structured):
    """LMStudioClient.chat swallows errors and returns "", so an unsupported
    json_schema request surfaces as empty content, not as an exception."""
    client = _FakeClient("", _GOOD)

    facts = await LLMExtractor(lm_client=client)._extract_local("I use uv now.")

    assert [f.content for f in facts] == ["Uses uv"]
    assert [c["response_format"]["type"] for c in client.calls] == ["json_schema", "json_object"]
    assert '"properties"' in _user_text(client.calls[1])  # old mode keeps the schema


@pytest.mark.asyncio
async def test_disabled_setting_uses_json_object_only(monkeypatch):
    monkeypatch.setattr(settings, "lm_structured_output", False)
    client = _FakeClient(_GOOD)

    await LLMExtractor(lm_client=client)._extract_local("I use uv now.")

    assert [c["response_format"]["type"] for c in client.calls] == ["json_object"]


@pytest.mark.asyncio
async def test_schema_echo_is_logged_not_silent(structured, caplog):
    echoed = json.dumps(_EXTRACTION_SCHEMA)  # what qwen3:4b actually returned
    client = _FakeClient(echoed)

    facts = await LLMExtractor(lm_client=client)._extract_local("I use uv now.")

    assert facts == []
    assert "no 'facts' list" in caplog.text
