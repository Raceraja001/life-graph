"""Context window management — prevent exceeding model token limits.

Provides utilities to estimate token counts and trim conversation
history when approaching context limits.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Approximate model context windows (in tokens)
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "gemini/gemini-2.5-flash": 1_000_000,
    "gemini/gemini-2.5-pro": 1_000_000,
    "gemini/gemini-2.0-flash": 1_000_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "claude-sonnet-4-20250514": 200_000,
}

# Reserve tokens for response generation
RESPONSE_RESERVE = 4096

def estimate_tokens(text: str) -> int:
    """Content-aware token estimation.

    Uses heuristics based on content type for better accuracy:
    - JSON/code: ~3 chars/token (more special characters)
    - English text: ~4 chars/token
    - Non-ASCII (Tamil, Hindi, etc.): ~2 chars/token
    """
    if not text:
        return 0

    # Detect content type and use appropriate ratio
    ascii_ratio = sum(1 for c in text[:200] if ord(c) < 128) / min(len(text), 200)

    if ascii_ratio < 0.5:
        # Heavy non-ASCII (Tamil, Hindi, etc.)
        chars_per_token = 2.0
    elif '{' in text[:100] or text.strip().startswith('['):
        # JSON/structured data
        chars_per_token = 3.0
    elif '```' in text or 'def ' in text or 'function ' in text:
        # Code
        chars_per_token = 3.0
    else:
        # English prose
        chars_per_token = 4.0

    return max(1, int(len(text) / chars_per_token))


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Estimate total tokens across all messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "") or ""
        total += estimate_tokens(content)
        total += 4  # role + message overhead
    return total


def get_context_limit(model: str) -> int:
    """Get the context limit for a model."""
    for key, limit in MODEL_CONTEXT_LIMITS.items():
        if key in model or model in key:
            return limit
    return 128_000  # safe default


def trim_messages(
    messages: list[dict],
    system_prompt: str | None = None,
    model: str = "gemini/gemini-2.5-flash",
    max_memory_results: int = 5,
) -> tuple[list[dict], int]:
    """Trim conversation history to fit within context window.

    Strategy:
    1. Always keep the system prompt (not in messages list)
    2. Always keep the last 2 messages (current user + previous assistant)
    3. If over limit: drop oldest messages first
    4. If still over limit: summarize dropped messages into a single context message

    Returns:
        Tuple of (trimmed messages, suggested max_memory_results)
    """
    context_limit = get_context_limit(model)
    available = context_limit - RESPONSE_RESERVE

    # Account for system prompt
    system_tokens = estimate_tokens(system_prompt or "")
    available -= system_tokens

    total_tokens = estimate_messages_tokens(messages)

    if total_tokens <= available:
        return messages, max_memory_results

    logger.warning(
        "Context window pressure: %d tokens estimated, %d available (model: %s)",
        total_tokens, available, model,
    )

    # Reduce memory results when context is tight
    ratio = total_tokens / available
    if ratio > 1.5:
        max_memory_results = 2
    elif ratio > 1.2:
        max_memory_results = 3

    # Keep system messages and last N messages, trim from the front
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    # Always keep the last 4 messages (2 turns)
    keep_tail = min(4, len(non_system))
    tail = non_system[-keep_tail:]
    trimmable = non_system[:-keep_tail] if keep_tail < len(non_system) else []

    # Start with required messages
    trimmed = system_msgs + tail
    current_tokens = estimate_messages_tokens(trimmed)

    if current_tokens <= available and trimmable:
        # Add back older messages from most recent, until we hit the limit
        for msg in reversed(trimmable):
            msg_tokens = estimate_tokens(msg.get("content", "") or "")
            if current_tokens + msg_tokens > available * 0.9:  # 90% to leave headroom
                break
            trimmed.insert(len(system_msgs), msg)  # Insert after system messages
            current_tokens += msg_tokens

    if len(trimmed) < len(messages):
        dropped = len(messages) - len(trimmed)
        logger.info(
            "Trimmed %d messages to fit context window (%d -> %d tokens)",
            dropped, total_tokens, current_tokens,
        )
        # Add a summary note
        summary_msg = {
            "role": "system",
            "content": f"[Note: {dropped} earlier messages were trimmed to fit the context window. Focus on the recent conversation.]",
        }
        trimmed.insert(len(system_msgs), summary_msg)

    return trimmed, max_memory_results
