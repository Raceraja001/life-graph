"""Agent run steps: what a driver did, in order, in one driver-neutral shape.

A step is a plain dict, so the same records come out of every driver:

    {"seq": 3, "kind": "tool_call", "tool": "Read", "content": "{...}",
     "at": "2026-10-13T09:40:32.579Z", "ref": "toolu_01..."}

``kind`` is an open string, not an enum (schema-less invariant). The values
in use are ``text`` (what the agent said), ``thinking`` (reasoning the model
exposed), ``tool_call`` (``content`` is the JSON input), ``tool_result``
(``content`` is the output, ``is_error`` set when the tool failed) and
``error``. ``at`` is the model-side timestamp when the driver has one and
None otherwise; ``ref`` ties a tool_result back to its tool_call.

Steps are captured verbatim here; redaction and size caps happen once, where
they are stored (services/trajectories.py).
"""

from __future__ import annotations

import json
from typing import Any


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        # tool_result content can be a list of {"type": "text", "text": ...} blocks
        parts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in value]
        if all(isinstance(b, dict) and b.get("type") == "text" for b in value):
            return "\n".join(parts)
    return json.dumps(value, default=str)


def parse_claude_stream(text: str) -> tuple[dict, list[dict]]:
    """Split ``claude -p --output-format stream-json`` stdout into (result, steps).

    ``result`` is the final ``{"type": "result"}`` event, which carries the
    same fields the old single-object ``--output-format json`` did (result,
    is_error, total_cost_usd, session_id, num_turns), plus ``model`` from the
    init event. Plain single-object JSON is still accepted, so a CLI or a
    test fake that prints the old format keeps working (with no steps).
    """
    text = (text or "").strip()
    if not text:
        return {}, []
    try:
        whole = json.loads(text)
    except json.JSONDecodeError:
        whole = None
    if isinstance(whole, dict):
        return whole, []
    if whole is not None:
        return {"result": whole}, []

    events: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    if not events:
        return {"result": text}, []

    result: dict = {}
    model = None
    steps: list[dict] = []
    for event in events:
        etype = event.get("type")
        if etype == "system" and event.get("subtype") == "init":
            model = event.get("model")
        elif etype == "result":
            result = dict(event)
        elif etype in ("assistant", "user"):
            at = event.get("timestamp")
            content = (event.get("message") or {}).get("content")
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            for block in content or []:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text" and etype == "assistant":
                    steps.append({"kind": "text", "content": block.get("text", ""), "at": at})
                elif btype == "thinking":
                    steps.append(
                        {"kind": "thinking", "content": block.get("thinking", ""), "at": at}
                    )
                elif btype == "tool_use":
                    steps.append(
                        {
                            "kind": "tool_call",
                            "tool": block.get("name"),
                            "content": json.dumps(block.get("input"), default=str),
                            "ref": block.get("id"),
                            "at": at,
                        }
                    )
                elif btype == "tool_result":
                    step = {
                        "kind": "tool_result",
                        "content": _as_text(block.get("content")),
                        "ref": block.get("tool_use_id"),
                        "at": at,
                    }
                    if block.get("is_error"):
                        step["is_error"] = True
                    steps.append(step)
    if not result:
        # No result event (killed mid-run): the steps still say what happened.
        result = {"is_error": True, "result": "claude_code stream ended without a result"}
    if model:
        result.setdefault("model", model)
    return result, number(steps, tool_names=True)


def number(steps: list[dict], *, tool_names: bool = False) -> list[dict]:
    """Assign ``seq`` in order; optionally fill a tool_result's ``tool`` from its call."""
    by_ref: dict[str, str] = {}
    for i, step in enumerate(steps, start=1):
        step["seq"] = i
        if tool_names:
            if step.get("kind") == "tool_call" and step.get("ref"):
                by_ref[step["ref"]] = step.get("tool") or ""
            elif step.get("kind") == "tool_result" and not step.get("tool"):
                step["tool"] = by_ref.get(step.get("ref") or "") or None
    return steps


class StepCollector:
    """Builds steps from the orchestrator's SSE events (the local driver).

    Consecutive ``token`` events are one ``text`` step; the orchestrator
    streams a reply token by token, but a reader wants the sentence.
    """

    def __init__(self) -> None:
        self.steps: list[dict] = []
        self._text: list[str] = []

    def _flush_text(self) -> None:
        if self._text:
            self.steps.append({"kind": "text", "content": "".join(self._text), "at": None})
            self._text = []

    def add(self, data: dict) -> None:
        kind = data.get("type")
        if kind == "token":
            if data.get("content"):
                self._text.append(data["content"])
            return
        if kind == "tool_call":
            self._flush_text()
            self.steps.append(
                {
                    "kind": "tool_call",
                    "tool": data.get("name"),
                    "content": json.dumps(data.get("arguments"), default=str),
                    "at": None,
                }
            )
        elif kind == "tool_result":
            self._flush_text()
            self.steps.append(
                {
                    "kind": "tool_result",
                    "tool": data.get("name"),
                    "content": _as_text(data.get("result")),
                    "at": None,
                }
            )
        elif kind in ("error", "partial_error"):
            self._flush_text()
            self.steps.append(
                {
                    "kind": "error",
                    "content": str(data.get("message") or data.get("error") or data),
                    "at": None,
                }
            )
        elif kind in ("condensed", "stuck"):
            # agents/condenser.py and agents/stuck.py: where a run's memory
            # was cut and where it went round in circles, kept for study.
            self._flush_text()
            detail = {k: v for k, v in data.items() if k != "type"}
            self.steps.append(
                {
                    "kind": kind,
                    "tool": data.get("tool") if kind == "stuck" else None,
                    "content": json.dumps(detail, default=str),
                    "at": None,
                }
            )

    def finish(self) -> list[dict]:
        self._flush_text()
        return number(self.steps)
