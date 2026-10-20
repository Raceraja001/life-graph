"""Workers: short-lived agents Jarvis creates for one task, inside an envelope.

docs/design/11_persona_roster_plan.md: one lead (Jarvis); everything else is a
worker made for the task at hand, the way Grok Heavy and Kimi's agent swarm
create agents per question, instead of a fixed roster. What a worker may touch
is not up to its brief: it is the **envelope's**, and enforced here.

* **Tools** — the brief's tools ∩ the envelope's; nothing else is offered.
* **Models** — the envelope's model class only. Research runs on the free
  cloud models, failing over among them only (``only_models``): never the GPU
  the owner is using, never a paid model.
* **What leaves the machine** — a brief for a cloud model passes
  :func:`life_graph.services.scrub.scrub` (secrets and personal details). The
  first defence is the caller's: build the brief from only what the worker needs.
* **Budget** — a cap on tool rounds and on time; over it the worker stops and
  returns what it has.
* **No nesting** — a worker cannot start a worker.
* **Untrusted output** — what comes back was shaped by web pages and other
  people's text. It is data for the caller to validate, never instructions.

Job 1 (free LLM offers) is the first user: the ``offer_reader`` template
(services/worker_templates.py) runs in the research envelope with no tools at
all — plain code fetches the pages; the worker only reads what it is given.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class WorkerError(RuntimeError):
    """A worker could not run (no model for its envelope, nested, ...)."""


@dataclass(frozen=True)
class Envelope:
    """The fixed boundary a worker runs in."""

    name: str
    tools: frozenset[str]
    scrub_brief: bool
    max_tool_calls: int
    timeout_s: int


ENVELOPES: dict[str, Envelope] = {
    "research": Envelope(
        name="research",
        tools=frozenset({"web_search", "browse_web", "get_current_datetime", "calculator"}),
        scrub_brief=True,
        max_tool_calls=12,
        timeout_s=180,
    ),
}


@dataclass
class WorkerResult:
    """What a worker returned. ``text`` is UNTRUSTED: validate before use."""

    envelope: str
    model: str | None
    text: str
    tool_calls: int = 0
    fetched_urls: list[str] = field(default_factory=list)
    stopped: str = "done"  # done | budget | timeout | error
    error: str | None = None
    seconds: float = 0.0
    untrusted: bool = True


_in_worker: contextvars.ContextVar[bool] = contextvars.ContextVar("in_worker", default=False)


def envelope_models(envelope: Envelope) -> list[str]:
    """The models a worker in *envelope* may run on, in failover order."""
    from life_graph.services.compute_router import cloud_models

    # Research is public information: the free cloud models only. Personal
    # envelopes (local model only) arrive with the jobs that need them.
    return cloud_models()


def envelope_tools(envelope: Envelope, requested: list[str] | tuple[str, ...]) -> list[dict]:
    """Tool schemas for the requested tools that the envelope allows."""
    from life_graph.tools.registry import registry as tool_registry

    allowed = envelope.tools & set(requested)
    return [t for t in tool_registry.get_tools() if t["function"]["name"] in allowed]


async def run_worker(
    envelope_name: str,
    *,
    brief: str,
    inputs: str,
    tools: list[str] | tuple[str, ...] = (),
    tenant_id: str,
    reasoning: bool = True,
) -> WorkerResult:
    """Run one worker in an envelope: *brief* is its system prompt, *inputs* the
    material for this task. Returns its reply as untrusted data.

    Raises:
        WorkerError: unknown envelope, a nested call, or no model to run on.
    """
    from contextlib import nullcontext

    from life_graph.agents.orchestrator import AgentOrchestrator
    from life_graph.core.tenant import set_tenant_context
    from life_graph.services.resilient_llm import only_models, reasoning_off
    from life_graph.services.scrub import scrub

    envelope = ENVELOPES.get(envelope_name)
    if envelope is None:
        raise WorkerError(f"unknown envelope {envelope_name!r}")
    if _in_worker.get():
        raise WorkerError("a worker cannot start a worker")
    models = envelope_models(envelope)
    if not models:
        raise WorkerError(f"no model available for the {envelope.name} envelope")

    if envelope.scrub_brief:
        brief, inputs = scrub(brief), scrub(inputs)
    schemas = envelope_tools(envelope, tools)
    # Room for a long answer: a dense page can hold a dozen offers.
    orchestrator = AgentOrchestrator(model=models[0], temperature=0.1, max_tokens=8000)
    orchestrator.MAX_ITERATIONS = envelope.max_tool_calls

    result = WorkerResult(envelope=envelope.name, model=models[0], text="")
    parts: list[str] = []
    started = time.monotonic()

    async def collect() -> None:
        async for event in orchestrator.run(
            [{"role": "user", "content": inputs}],
            system_prompt=brief,
            # An empty list is "no tools", not "every tool": never None here.
            tools=schemas,
        ):
            try:
                data: dict[str, Any] = json.loads(event.removeprefix("data: ").strip())
            except (ValueError, AttributeError):
                continue
            kind = data.get("type")
            if kind == "token":
                parts.append(str(data.get("content") or ""))
            elif kind == "tool_call":
                result.tool_calls += 1
            elif kind == "tool_result" and data.get("name") == "browse_web":
                url = _fetched_url(data.get("result"))
                if url:
                    result.fetched_urls.append(url)
            elif kind in ("error", "partial_error"):
                result.stopped, result.error = "error", str(data.get("message") or data)
            elif kind == "done" and data.get("stop_reason") in ("max_iterations", "stuck"):
                result.stopped = "budget"

    token = _in_worker.set(True)
    set_tenant_context(tenant_id)
    try:
        with only_models(models), nullcontext() if reasoning else reasoning_off():
            await asyncio.wait_for(collect(), timeout=envelope.timeout_s)
    except TimeoutError:
        result.stopped = "timeout"
    except Exception as exc:  # noqa: BLE001 - a worker failure is reported, not raised
        logger.warning("worker in %s failed", envelope.name, exc_info=True)
        result.stopped, result.error = "error", f"{type(exc).__name__}: {exc}"[:300]
    finally:
        _in_worker.reset(token)
    result.text = "".join(parts)
    result.seconds = round(time.monotonic() - started, 1)
    return result


def _fetched_url(raw: Any) -> str | None:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return None
    return data.get("url") if isinstance(data, dict) else None


def json_array(text: str) -> list[dict]:
    """The JSON array of objects in an untrusted reply (a fenced block, else
    the outermost brackets), or [] when there is none."""
    import re

    s = text or ""
    candidates = re.findall(r"```(?:json)?\s*([\s\S]*?)```", s)
    start, end = s.find("["), s.rfind("]")
    if start != -1 and end > start:
        candidates.append(s[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate.strip())
        except ValueError:
            continue
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
