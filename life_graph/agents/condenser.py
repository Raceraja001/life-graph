"""Keep a long agent conversation inside the model's context window.

docs/specs/agent-condenser.md. Ollama serves models with a fixed context
(``OLLAMA_CONTEXT_LENGTH``, 32k here) and, given a longer prompt, drops tokens
from the *start*, which holds the system prompt and the task. Every tool result
stays in the conversation, so a long coding run used to forget what it was
asked to do. Before each model call the conversation is measured and, when
over budget, condensed in layers, cheapest first:

1. **Mask** old tool results: their content becomes a one-line stub. The
   message itself (and its ``tool_call_id``) stays, so the conversation is
   still valid and the model still sees what it did.
2. **Summarise** the middle: the span between the task and the recent turns
   becomes one "summary of the work so far" message, written by the model.
3. **Truncate** the middle, with a note, if summarising fails or is not
   enough. Losing the middle beats Ollama silently losing the beginning.

Always kept verbatim: the system prompt(s), the first user message (the
task) and the last ``KEEP_RECENT_TURNS`` assistant turns with their tool
results. An assistant message that made tool calls is never separated from
its results, and the kept tail never starts with an orphaned tool message.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

Message = dict[str, Any]
Summarise = Callable[[list[Message]], Awaitable[str]]

KEEP_RECENT_TURNS = 4
MAX_RESULT_CHARS = 12_000
CHARS_PER_TOKEN = 3.5
BUDGET_FRACTION = 0.8
SUMMARY_MAX_TOKENS = 800
SUMMARY_TAG = "[Summary of the work so far]"
DROPPED_TAG = "[Earlier steps were dropped to fit the context window]"

SUMMARY_PROMPT = (
    "You are condensing the earlier part of an AI agent's working session so it"
    " can continue within its memory limit. Write a compact summary under these"
    " headings:\n"
    "## Done so far\n## Files read / changed\n## Current state\n## Open problems / next step\n"
    "Keep exact file paths, function and variable names, commands, and error"
    " messages. Do not invent anything that is not in the session. Do not address"
    " the agent; just state the facts. At most 300 words."
)


@dataclass
class Condensed:
    messages: list[Message]
    layer: str | None  # None = nothing done; "mask" | "summary" | "truncate"
    before_tokens: int
    after_tokens: int


def count_tokens(messages: list[Message], model: str | None = None) -> int:
    """Token estimate for ``messages``; litellm's counter when it works, else chars/3.5."""
    try:
        import litellm

        return int(litellm.token_counter(model=model or "gpt-4o", messages=messages))
    except Exception:  # noqa: BLE001 — an estimate is all the budget needs
        chars = sum(len(_text(m)) for m in messages)
        return int(chars / CHARS_PER_TOKEN) + 4 * len(messages)


def _text(m: Message) -> str:
    content = m.get("content")
    text = content if isinstance(content, str) else json.dumps(content or "", default=str)
    if m.get("tool_calls"):
        text += json.dumps(m["tool_calls"], default=str)
    return text


def budget_for(context_tokens: int, max_tokens: int) -> int:
    return max(1024, int(context_tokens * BUDGET_FRACTION) - max_tokens)


def cap_result(result: str, limit: int = MAX_RESULT_CHARS) -> str:
    """One huge tool result keeps its head and tail, not the whole window."""
    if len(result) <= limit:
        return result
    head = int(limit * 0.6)
    tail = limit - head
    cut = len(result) - head - tail
    return (
        f"{result[:head]}\n\n[... {cut:,} characters cut from the middle ...]\n\n{result[-tail:]}"
    )


# ── Structure ───────────────────────────────────────────────────────────────


def _split(messages: list[Message]) -> tuple[list[Message], list[Message], list[Message]]:
    """(head, middle, tail): head = system messages + the first user message;
    tail = the last KEEP_RECENT_TURNS assistant turns with their tool results,
    starting at an assistant message so no tool message is orphaned."""
    head_end = 0
    while head_end < len(messages) and messages[head_end].get("role") == "system":
        head_end += 1
    if head_end < len(messages) and messages[head_end].get("role") == "user":
        head_end += 1
    rest = messages[head_end:]
    assistant_at = [i for i, m in enumerate(rest) if m.get("role") == "assistant"]
    if len(assistant_at) <= KEEP_RECENT_TURNS:
        return messages[:head_end], [], rest
    tail_start = assistant_at[-KEEP_RECENT_TURNS]
    # A user message just before the kept turns (a nudge, a follow-up) belongs
    # with them.
    while tail_start > 0 and rest[tail_start - 1].get("role") == "user":
        tail_start -= 1
    return messages[:head_end], rest[:tail_start], rest[tail_start:]


def _tool_names(messages: list[Message]) -> dict[str, tuple[str, str]]:
    """tool_call_id -> (tool name, short argument summary)."""
    names: dict[str, tuple[str, str]] = {}
    for m in messages:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args = fn.get("arguments") or ""
            try:
                parsed = json.loads(args) if args else {}
                hint = next((str(v) for v in parsed.values() if isinstance(v, str)), "")
            except (ValueError, AttributeError):
                hint = ""
            names[tc.get("id", "")] = (fn.get("name", "tool"), hint[:80])
    return names


READ_TOOLS = frozenset({"code_read", "file_read"})


def latest_reads(messages: list[Message], names: dict[str, tuple[str, str]]) -> list[str]:
    """tool_call_ids of the most recent read of each file, newest first.

    An edit needs the file's exact text. Masking the only copy of a file the
    model is about to change makes it guess, and its edits then fail with
    "`old` not found".
    """
    newest: dict[str, str] = {}
    for m in messages:
        if m.get("role") == "tool":
            tool, hint = names.get(m.get("tool_call_id", ""), ("", ""))
            if tool in READ_TOOLS and hint:
                newest[hint] = m["tool_call_id"]
    order = [m.get("tool_call_id") for m in messages if m.get("role") == "tool"]
    return sorted(newest.values(), key=order.index, reverse=True)


def mask(
    middle: list[Message], names: dict[str, tuple[str, str]], keep: set[str] | None = None
) -> list[Message]:
    out = []
    for m in middle:
        if keep and m.get("tool_call_id") in keep:
            out.append(m)
            continue
        if m.get("role") == "tool" and not str(m.get("content", "")).startswith("[earlier result"):
            tool, hint = names.get(m.get("tool_call_id", ""), ("tool", ""))
            size = len(str(m.get("content") or ""))
            where = f" {hint}" if hint else ""
            m = {
                **m,
                "content": f"[earlier result elided: {tool}{where}, {size:,} chars."
                " Call the tool again if you need it]",
            }
        out.append(m)
    return out


def valid(messages: list[Message]) -> bool:
    """Every assistant tool call is answered, and no tool message is orphaned."""
    pending: set[str] = set()
    for m in messages:
        role = m.get("role")
        if role == "assistant":
            if pending:
                return False
            pending = {tc.get("id", "") for tc in m.get("tool_calls") or []}
        elif role == "tool":
            if m.get("tool_call_id") not in pending:
                return False
            pending.discard(m.get("tool_call_id"))
        elif pending:
            return False  # a user/system message between a call and its result
    return not pending


def _transcript(middle: list[Message]) -> str:
    lines = []
    for m in middle:
        role = m.get("role")
        if role == "assistant":
            if m.get("content"):
                lines.append(f"AGENT: {m['content']}")
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                lines.append(f"CALL {fn.get('name')}({fn.get('arguments', '')[:400]})")
        elif role == "tool":
            lines.append(f"RESULT: {str(m.get('content') or '')[:1500]}")
        elif role == "user":
            lines.append(f"USER: {str(m.get('content') or '')[:1500]}")
    return "\n".join(lines)


# ── Entry point ─────────────────────────────────────────────────────────────


async def condense(
    messages: list[Message],
    *,
    budget: int,
    summarise: Summarise | None = None,
    model: str | None = None,
) -> Condensed:
    """Fit ``messages`` into ``budget`` tokens, cheapest layer first."""
    before = count_tokens(messages, model)
    if before <= budget:
        return Condensed(messages, None, before, before)
    head, middle, tail = _split(messages)
    if not middle:
        # Too few turns to cut between (a handful of huge results): mask the
        # results of every turn but the latest, which the model is acting on.
        last = max((i for i, m in enumerate(tail) if m.get("role") == "assistant"), default=0)
        candidate = head + mask(tail[:last], _tool_names(tail)) + tail[last:]
        after = count_tokens(candidate, model)
        return Condensed(candidate, "mask" if after < before else None, before, after)

    names = _tool_names(messages)
    masked = head + mask(middle, names) + tail
    after = count_tokens(masked, model)
    if after <= budget:
        # Give back the newest read of each file, most recent first, while it
        # still fits: an edit needs the file's exact text.
        kept: set[str] = set()
        for call_id in latest_reads(middle, names):
            trial = head + mask(middle, names, kept | {call_id}) + tail
            trial_tokens = count_tokens(trial, model)
            if trial_tokens <= budget:
                kept.add(call_id)
                masked, after = trial, trial_tokens
        return Condensed(masked, "mask", before, after)

    if summarise is not None:
        try:
            summary = (await summarise(middle)).strip()
        except Exception:  # noqa: BLE001 — fall through to truncation
            logger.warning("Condenser summary failed", exc_info=True)
            summary = ""
        if summary:
            from life_graph.services.redaction import redact

            candidate = (
                head + [{"role": "user", "content": f"{SUMMARY_TAG}\n{redact(summary)}"}] + tail
            )
            after = count_tokens(candidate, model)
            if after <= budget:
                return Condensed(candidate, "summary", before, after)

    candidate = head + [{"role": "user", "content": DROPPED_TAG}] + tail
    return Condensed(candidate, "truncate", before, count_tokens(candidate, model))


def summariser_for(acompletion: Callable[..., Awaitable[Any]], model: str) -> Summarise:
    """A Summarise that asks ``model`` (non-streaming, no tools) for the summary."""

    async def run(middle: list[Message]) -> str:
        response = await acompletion(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": _transcript(middle)[:40_000]},
            ],
            temperature=0.1,
            max_tokens=SUMMARY_MAX_TOKENS,
            stream=False,
        )
        return response.choices[0].message.content or ""

    return run
