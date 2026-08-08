"""Live OpenRouter model catalog for the persona model picker.

Fetches OpenRouter's public model list, classifies Free/Paid from real
pricing data, and caches it in-process. Never raises — degrades to the
last-known-good cache, then to a static fallback list, so a persona's
model picker can never end up with zero options.
"""

from __future__ import annotations

import time

import httpx

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_KEY = "openrouter_models"
_TTL_SECONDS = 3600

FALLBACK_MODELS: list[dict] = [
    {"id": "openrouter/nvidia/nemotron-3-super-120b-a12b:free", "name": "Nemotron 3 Super 120B", "is_free": True},
    {"id": "openrouter/openai/gpt-oss-20b:free", "name": "GPT-OSS 20B", "is_free": True},
    {"id": "openrouter/google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "is_free": True},
    {"id": "openrouter/google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B A4B", "is_free": True},
    {"id": "gemini/gemini-3.6-flash", "name": "Gemini 3.6 Flash", "is_free": False},
    {"id": "gemini/gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite", "is_free": False},
    {"id": "openrouter/deepseek/deepseek-chat", "name": "DeepSeek Chat", "is_free": False},
]


def _is_free(pricing: dict) -> bool:
    return pricing.get("prompt") == "0" and pricing.get("completion") == "0"


async def get_model_catalog() -> list[dict]:
    """Returns [{id, name, is_free}, ...] — live OpenRouter catalog plus the
    Gemini direct models, cached for _TTL_SECONDS. Degrades to the last
    cached result, then to FALLBACK_MODELS, on any fetch failure."""
    now = time.monotonic()
    cached = _CACHE.get(_CACHE_KEY)
    if cached and now - cached[0] < _TTL_SECONDS:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            data = resp.json()["data"]
    except Exception:
        return cached[1] if cached else FALLBACK_MODELS

    models = [
        {
            "id": f"openrouter/{m['id']}",
            "name": m.get("name") or m["id"],
            "is_free": _is_free(m.get("pricing", {})),
        }
        for m in data
    ]
    # Gemini's direct models never appear in OpenRouter's catalog — carry
    # them over from the fallback list unconditionally so they don't
    # disappear just because the live fetch only covers OpenRouter.
    models += [m for m in FALLBACK_MODELS if not m["id"].startswith("openrouter/")]
    _CACHE[_CACHE_KEY] = (now, models)
    return models
