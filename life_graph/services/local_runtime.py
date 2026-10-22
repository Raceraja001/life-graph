"""How Life Graph asks Ollama to hold its local models: context size and keep-alive.

Measured 2026-10-22 on the 16 GB GPU this runs on: loading qwen3:14b takes
11-17 s; once loaded it writes 73 tokens/s and reads a cached 7,500-token
prompt in 0.05 s. A personal Jarvis answer took 30-37 s because the model kept
being reloaded:

* Ollama's shared default context (32k) makes qwen3:14b 14.4 GB, so nothing
  else fits beside it; at 16k it is 11.7 GB (Jarvis's fixed prompt is ~4,700
  tokens, so 16k is plenty) and the embedding model and speech fit too.
* Requests that ask for a different context size load a second copy, so every
  Life Graph caller must ask for the same one. Ollama's OpenAI-style /v1
  endpoint ignores ``num_ctx`` and ``keep_alive`` altogether
  (services/llm_client.py uses the native API for that reason).
* Ollama unloads a model 5 minutes after its last request, and the phone is
  used now and then, so nearly every phone question started cold. In the
  owner's waking hours the model is now held until the end of them; at night
  it is released after a few minutes so the coding agents get the GPU.

These are per-request options: the shared Ollama's own settings, and every
other program using it, are unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from life_graph.config import settings


def num_ctx() -> int:
    """The context size every Life Graph request to a local model asks for."""
    return settings.local_llm_num_ctx


def _window(spec: str) -> tuple[int, int] | None:
    try:
        start, end = (int(p) % 24 for p in spec.split("-", 1))
    except ValueError:
        return None
    return None if start == end else (start, end)


def keep_alive(now: datetime | None = None) -> str:
    """How long Ollama should hold the model after this request.

    Inside ``local_llm_warm_hours`` (user_timezone): until the window ends, so
    a question at 10:00 keeps it until 23:00. Outside it, or with no window,
    ``local_llm_idle_keep_alive``.
    """
    idle = settings.local_llm_idle_keep_alive
    window = _window(settings.local_llm_warm_hours or "")
    if window is None:
        return idle
    try:
        tz = ZoneInfo(settings.user_timezone)
    except Exception:  # noqa: BLE001 - unknown zone: UTC
        tz = ZoneInfo("UTC")
    local = (now or datetime.now(UTC)).astimezone(tz)
    start, end = window
    hour = local.hour
    inside = start <= hour < end if start < end else (hour >= start or hour < end)
    if not inside:
        return idle
    end_at = local.replace(hour=end, minute=0, second=0, microsecond=0)
    if end_at <= local:
        end_at += timedelta(days=1)
    seconds = int((end_at - local).total_seconds())
    return f"{max(seconds, 300)}s"


def ollama_base() -> str:
    """Ollama's root URL (no /v1)."""
    return settings.ollama_api_base.rstrip("/")


async def warm(chat_model: str, embedding_model: str) -> None:
    """Load the chat and embedding models now, with Life Graph's options.

    For the phone app opening (POST /jarvis/warm): by the time the owner has
    typed or spoken, the ~15 s load has already happened. Best-effort.
    """
    import logging

    import httpx

    body_options = {"num_ctx": num_ctx()}
    name = chat_model.removeprefix("ollama_chat/").removeprefix("ollama/")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # No prompt: Ollama loads the model and returns.
            await client.post(
                f"{ollama_base()}/api/generate",
                json={"model": name, "keep_alive": keep_alive(), "options": body_options},
            )
            await client.post(
                f"{ollama_base()}/api/embed",
                json={"model": embedding_model, "input": "warm", "keep_alive": keep_alive()},
            )
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("Warming local models failed: %s", exc)


def is_ollama(base_url: str | None) -> bool:
    """Whether *base_url* (e.g. lm_studio_url) points at the configured Ollama."""
    if not base_url:
        return False
    a, b = urlparse(base_url), urlparse(ollama_base())
    return (a.hostname, a.port) == (b.hostname, b.port)
