"""How an eval case is actually executed for each optimizable task.

``EvalService.run_eval`` takes an ``llm_fn(prompt_version_id, input_text)``
but nothing ever supplied one, so every run scored empty output. The runner
for a task reproduces what production does with a given prompt version: same
message construction (``build_extraction_messages``), same model, same
response format and fallback, and the same confidence floor production applies
before storing — so a candidate is scored on what it would really produce.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

LlmFn = Callable[[str, str], Awaitable[tuple[str, int, int, Decimal]]]


def _extraction_llm_fn() -> LlmFn:
    from life_graph.config import settings
    from life_graph.extraction.llm import (
        build_extraction_messages,
        default_prompt,
        response_format_for,
    )
    from life_graph.self_improving.fact_scoring import parse_facts
    from life_graph.self_improving.prompt_resolver import ResolvedPrompt, load_version

    prompts: dict[str, ResolvedPrompt] = {}

    async def run(prompt_version_id: str, input_text: str) -> tuple[str, int, int, Decimal]:
        from life_graph.api.dependencies import get_lm_client

        prompt = prompts.get(prompt_version_id)
        if prompt is None:
            prompt = await load_version(prompt_version_id, default_prompt())
            prompts[prompt_version_id] = prompt

        client = get_lm_client()

        async def call(structured: bool) -> str:
            return await client.chat(
                messages=build_extraction_messages(
                    prompt.prompt_text, prompt.few_shot, input_text, structured=structured
                ),
                model=settings.lm_extraction_model,
                temperature=0.1,
                max_tokens=1024,
                response_format=response_format_for(structured),
            )

        started = time.monotonic()
        raw = await call(settings.lm_structured_output)
        if not raw and settings.lm_structured_output:
            raw = await call(False)  # same fallback production uses
        latency_ms = int((time.monotonic() - started) * 1000)

        facts = parse_facts(raw)
        if facts is None:
            return raw or "", latency_ms, 0, Decimal("0")  # scored as invalid output
        kept: list[dict[str, Any]] = [
            f
            for f in facts
            if float(f.get("confidence", 0.5) or 0.0) >= settings.extraction_min_confidence
        ]
        return json.dumps({"facts": kept}, ensure_ascii=False), latency_ms, 0, Decimal("0")

    return run


_RUNNERS: dict[str, Callable[[], LlmFn]] = {
    "capture_extraction": _extraction_llm_fn,
}


def llm_fn_for(task_type: str) -> LlmFn | None:
    """A fresh runner for *task_type*, or None if the task has none."""
    factory = _RUNNERS.get(task_type)
    return factory() if factory else None


def optimizable_task_types() -> list[str]:
    """Task types the loop knows how to evaluate and optimize."""
    return list(_RUNNERS)
