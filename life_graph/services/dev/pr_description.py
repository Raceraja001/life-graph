"""Draft a pull request description from the landed diff.

The PR body used to be the task instruction plus the driver's own narrative
summary ("Changed x: ..."), which describes what the agent *says* it did.
This drafts a description from what the diff actually contains, before the
``driver_pr`` approval is filed -- so the person approving sees the PR text
it will open with, and the PR itself is readable on GitHub.

Best-effort throughout: any failure (no model, timeout, a reply that didn't
follow the format) returns None and the PR falls back to the old body. A
drafted description must never be the reason a verified task fails to land.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

_MAX_DIFF_CHARS = 12000
_MAX_DESCRIPTION_CHARS = 4000
_TIMEOUT_SECONDS = 120
# Thinking models (Qwen3 on Ollama) can wrap reasoning in <think> tags in the
# content itself; it isn't part of the description.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_REQUIRED_HEADING = "## What changed"

_PROMPT = """You are writing the description for a pull request. Describe ONLY \
what the diff shows. Do not invent changes, tests, or motivations that are not \
in it.

Use exactly these Markdown sections, and keep them short:
## What changed
- one bullet per meaningful change, naming the file or function
## Why
one or two sentences, based on the task instruction
## Review notes
risky spots or behavior changes a reviewer should check; write "None" if nothing stands out

Task instruction:
{instruction}

Diff:
{diff}
"""

ChatFn = Callable[..., Awaitable[str]]


async def draft_pr_description(
    diff_text: str,
    instruction: str,
    *,
    chat: ChatFn,
    model: str | None = None,
    timeout: float = _TIMEOUT_SECONDS,
) -> str | None:
    """A Markdown PR description drafted from *diff_text*, or None."""
    if not diff_text or not diff_text.strip():
        return None
    diff = diff_text
    if len(diff) > _MAX_DIFF_CHARS:
        diff = diff[:_MAX_DIFF_CHARS] + "\n... (diff truncated)"
    prompt = _PROMPT.format(instruction=(instruction or "").strip()[:2000], diff=diff)
    try:
        raw = await asyncio.wait_for(
            chat(
                [{"role": "user", "content": prompt}],
                model=model,
                temperature=0.2,
                max_tokens=1500,
            ),
            timeout=timeout,
        )
    except Exception:
        logger.warning("PR description draft failed; using the default body", exc_info=True)
        return None

    text = _THINK_RE.sub("", raw or "").strip()
    if _REQUIRED_HEADING not in text:
        # Didn't follow the format: an unstructured blob is worse than the
        # plain default body, so don't put it in a PR.
        logger.info("PR description draft ignored: missing %r", _REQUIRED_HEADING)
        return None
    return text[text.index(_REQUIRED_HEADING) :][:_MAX_DESCRIPTION_CHARS]
