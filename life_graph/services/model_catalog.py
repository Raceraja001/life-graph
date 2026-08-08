"""Live OpenRouter model catalog for the persona model picker.

Fetches OpenRouter's public model list, classifies Free/Paid from real
pricing data, and caches it in-process. Never raises — degrades to the
last-known-good cache, then to a static fallback list, so a persona's
model picker can never end up with zero options.
"""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_CACHE: dict[str, tuple[float, list[dict], float]] = {}
_CACHE_KEY = "openrouter_models"
_TTL_SECONDS = 3600
_FAILURE_CACHE_SECONDS = 60

FALLBACK_MODELS: list[dict] = [
    {
        "id": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
        "name": "Nemotron 3 Super 120B",
        "is_free": True,
    },
    {"id": "openrouter/openai/gpt-oss-20b:free", "name": "GPT-OSS 20B", "is_free": True},
    {"id": "openrouter/google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "is_free": True},
    {"id": "openrouter/google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B A4B", "is_free": True},
    {"id": "gemini/gemini-3.6-flash", "name": "Gemini 3.6 Flash", "is_free": False},
    {"id": "gemini/gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite", "is_free": False},
    {"id": "openrouter/deepseek/deepseek-chat", "name": "DeepSeek Chat", "is_free": False},
    {
        "id": "claude-cli",
        "name": "Claude CLI (subscription, no tool-calling)",
        "is_free": False,
    },
]


def _is_free(pricing: dict) -> bool:
    return pricing.get("prompt") == "0" and pricing.get("completion") == "0"


def _is_text_output(model: dict) -> bool:
    """True only if the model explicitly declares a text-producing modality
    (e.g. "text->text", "text+image->text"). Models missing the
    architecture/modality field are excluded conservatively — we'd rather
    hide an unknown model than let an image/audio-output model break a
    persona at runtime."""
    architecture = model.get("architecture")
    if not isinstance(architecture, dict):
        return False
    modality = architecture.get("modality")
    return isinstance(modality, str) and modality.endswith("->text")


async def get_model_catalog() -> list[dict]:
    """Returns [{id, name, is_free}, ...] — live OpenRouter catalog plus the
    Gemini direct models, cached for _TTL_SECONDS. Never raises — degrades to
    the last-known-good cache, then to FALLBACK_MODELS, on any failure
    (fetch, or malformed response body), so a persona's model picker can
    never end up with zero options. Failures are themselves cached briefly
    (_FAILURE_CACHE_SECONDS) so an outage doesn't force every request to pay
    a full HTTP timeout."""
    now = time.monotonic()
    cached = _CACHE.get(_CACHE_KEY)
    if cached and now - cached[0] < cached[2]:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            data = resp.json()["data"]

        models = [
            {
                "id": f"openrouter/{m['id']}",
                "name": m.get("name") or m["id"],
                "is_free": _is_free(m.get("pricing", {})),
            }
            for m in data
            if isinstance(m, dict) and m.get("id") and _is_text_output(m)
        ]
        # Gemini's direct models never appear in OpenRouter's catalog — carry
        # them over from the fallback list unconditionally so they don't
        # disappear just because the live fetch only covers OpenRouter.
        models += [m for m in FALLBACK_MODELS if not m["id"].startswith("openrouter/")]
    except Exception as exc:
        logger.warning("model_catalog fetch failed: %s", exc)
        fallback = cached[1] if cached else FALLBACK_MODELS
        _CACHE[_CACHE_KEY] = (now, fallback, _FAILURE_CACHE_SECONDS)
        return fallback

    _CACHE[_CACHE_KEY] = (now, models, _TTL_SECONDS)
    return models
