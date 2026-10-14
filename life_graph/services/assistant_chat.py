"""Conversation with the assistant from a phone (Telegram), by text or voice.

Phase F of docs/specs/assistant-capabilities.md. Until now the Telegram
bridge could only *capture*: every message became a memory and nothing
answered. This adds:

- :func:`ask`: run the assistant persona (``telegram_assistant_persona``,
  default ``assistant``) through the kernel, exactly like a dashboard chat, and
  wait for its answer. The run is an ordinary AgentTask, so it is recorded and
  observable like every other;
- a per-chat **mode** (``capture`` or ``chat``) kept in Redis: in chat mode a
  plain message or a voice note is a question rather than a memory;
- :func:`speak`: text to speech through an OpenAI-compatible
  ``/v1/audio/speech`` endpoint (speaches on this machine). When
  ``tts_base_url`` is empty, replies are text only; that is the stub.

Without Redis, the mode falls back to ``capture``, which is the old
behaviour, so nothing is lost when the cache is down.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from life_graph.config import settings

logger = logging.getLogger(__name__)

MODE_KEY = "telegram:mode:{chat_id}"
MODES = ("capture", "chat")
_TERMINAL = {"completed", "failed", "timeout", "cancelled"}
POLL_SECONDS = 1.5
MAX_SPOKEN_CHARS = 1200


async def get_mode(chat_id: int) -> str:
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return "capture"
    try:
        raw = await redis.get(MODE_KEY.format(chat_id=chat_id))
    except Exception:  # noqa: BLE001 — capture is the safe default
        return "capture"
    value = raw.decode() if isinstance(raw, bytes) else raw
    return value if value in MODES else "capture"


async def set_mode(chat_id: int, mode: str) -> bool:
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None or mode not in MODES:
        return False
    try:
        await redis.set(MODE_KEY.format(chat_id=chat_id), mode)
    except Exception:  # noqa: BLE001
        logger.warning("telegram: could not store chat mode", exc_info=True)
        return False
    return True


def answer_text(result: dict[str, Any] | None) -> str:
    """The reply text of a finished persona task."""
    if not isinstance(result, dict):
        return ""
    return str(result.get("response") or "").strip()


async def ask(tenant_id: str, question: str, *, pm=None, timeout: float | None = None) -> str:
    """Ask the assistant persona and wait for its answer."""
    if pm is None:
        from life_graph.api.dependencies import get_process_manager

        pm = get_process_manager()
    timeout = timeout or settings.telegram_ask_timeout_seconds
    spawn = await pm.spawn(
        tenant_id=tenant_id,
        agent_name=settings.telegram_assistant_persona,
        input_data={"message": question},
        task_name=f"telegram:{settings.telegram_assistant_persona}",
        max_retries=0,
    )
    task_id = spawn["task_id"]
    waited = 0.0
    while waited < timeout:
        task = await pm.get_task(tenant_id, task_id)
        if task is not None and task.status in _TERMINAL:
            if task.status == "completed":
                return answer_text(task.result) or "(no answer)"
            return f"I couldn't finish that ({task.status}). {task.error or ''}".strip()
        await asyncio.sleep(POLL_SECONDS)
        waited += POLL_SECONDS
    return "That is taking longer than expected; the answer will appear in the dashboard."


def spoken(text: str) -> str:
    """Text fit to read aloud: no markdown symbols, links or code, and not too long."""
    import re

    out = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.S)
    out = re.sub(r"https?://\S+", "(link)", out)
    out = re.sub(r"[*_`#>|]+", "", out)
    out = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", out)
    out = re.sub(r"\s+", " ", out).strip()
    if len(out) > MAX_SPOKEN_CHARS:
        cut = out[:MAX_SPOKEN_CHARS]
        out = cut[: cut.rfind(". ") + 1] or cut
    return out


async def speak(text: str, *, client: httpx.AsyncClient | None = None) -> bytes | None:
    """OGG/Opus audio for ``text``, or None when TTS is off or fails."""
    if not settings.tts_base_url or not text.strip():
        return None
    own = client is None
    http = client or httpx.AsyncClient(timeout=60.0)
    try:
        resp = await http.post(
            settings.tts_base_url.rstrip("/") + "/v1/audio/speech",
            json={
                "model": settings.tts_model,
                "voice": settings.tts_voice,
                "input": spoken(text),
                "response_format": "opus",
            },
        )
        resp.raise_for_status()
        return resp.content or None
    except Exception:  # noqa: BLE001 — text is always sent; voice is a bonus
        logger.warning("TTS failed", exc_info=True)
        return None
    finally:
        if own:
            await http.aclose()
