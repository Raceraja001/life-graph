# Live OpenRouter model search — design

## Purpose

Replace the persona model picker's curated static Free/Paid dropdown
(`dashboard/lib/model-options.ts`) with a live, searchable list backed by
OpenRouter's real model catalog. The static list was a deliberate design
choice during the original picker build (simplicity, clear cost grouping),
but went stale within a day of shipping — missing several current free
models (Nemotron variants, Poolside, Cohere, etc.) because OpenRouter's
free-tier catalog changes often. This was explicitly flagged as a
follow-up in that design's "Open items intentionally deferred" section.

## Non-goals

- No per-keystroke server round-trip — the frontend fetches the full
  catalog once (cached) and filters client-side.
- No model pricing/context-length display in the dropdown yet — Free/Paid
  grouping only, matching today's UX. A richer model detail view is a
  separate, later feature if it turns out to be useful.
- No change to how a selection is saved — `PATCH /kernel/personas/{id}`
  and the `useUpdatePersona` hook are untouched; this only changes where
  the list of choices comes from.
- No new UI dependency — `cmdk` is already installed and already used for
  the command palette (`dashboard/components/command-palette.tsx`); this
  reuses it rather than adding a combobox library.

## Architecture

```
[Persona card: mobile persona-settings.tsx, desktop settings/page.tsx]
  -> useModelCatalog()          GET /kernel/models
       -> life_graph/services/model_catalog.py: get_model_catalog()
            in-memory TTL cache (1h)
              hit  -> return cached
              miss -> fetch https://openrouter.ai/api/v1/models (public, no key)
                        success -> classify Free/Paid from pricing, cache, return
                        failure -> serve last-good cache if any,
                                   else fall back to today's static MODEL_OPTIONS
  -> ModelCombobox (cmdk-based) replaces the <select><optgroup>
       inline expand: search input + Command.List grouped Free/Paid
       filters the already-fetched list client-side (cmdk's built-in match)
```

## Backend: `life_graph/services/model_catalog.py` (new)

```python
import time
import httpx

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_KEY = "openrouter_models"
_TTL_SECONDS = 3600

FALLBACK_MODELS = [
    {"id": "openrouter/nvidia/nemotron-3-super-120b-a12b:free", "name": "Nemotron 3 Super 120B", "is_free": True},
    {"id": "openrouter/openai/gpt-oss-20b:free", "name": "GPT-OSS 20B", "is_free": True},
    {"id": "openrouter/google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "is_free": True},
    {"id": "openrouter/google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B A4B", "is_free": True},
    {"id": "gemini/gemini-3.6-flash", "name": "Gemini 3.6 Flash", "is_free": False},
    {"id": "gemini/gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite", "is_free": False},
    {"id": "openrouter/deepseek/deepseek-chat", "name": "DeepSeek Chat", "is_free": False},
]


async def get_model_catalog() -> list[dict]:
    """Returns [{id, name, is_free}, ...]. Never raises — degrades to cache, then to FALLBACK_MODELS."""
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


def _is_free(pricing: dict) -> bool:
    return pricing.get("prompt") == "0" and pricing.get("completion") == "0"
```

Notes:
- OpenRouter's `/api/v1/models` returns bare ids (e.g. `"nvidia/nemotron-3-super-120b-a12b:free"`);
  this codebase's convention (per `resilient_llm.py` / litellm) prefixes OpenRouter
  models with `openrouter/`, so the mapping adds that prefix — this keeps
  saved `model` values consistent with what `ResilientLLM` already expects.
- Gemini's own direct models (`gemini/gemini-3.6-flash` etc.) aren't in
  OpenRouter's catalog at all — they're appended from `FALLBACK_MODELS`'
  paid entries unconditionally, so today's two Gemini options don't
  disappear just because the live fetch only covers OpenRouter.
- The in-memory cache is process-local (no Redis) — acceptable because a
  stale-by-up-to-an-hour model list is harmless, and it avoids adding a new
  Redis key namespace for a low-stakes catalog. A cold cache after a
  redeploy just means the first dashboard load after deploy pays one extra
  ~1s fetch.

## Backend: `life_graph/api/kernel.py`

New route, same auth/tenant pattern as the existing persona routes:

```python
@router.get("/models")
async def list_models():
    models = await get_model_catalog()
    return {"data": {"models": models}}
```

## Frontend

### `dashboard/lib/mobile-api.ts` — new hook

```typescript
export interface ModelOption {
  id: string;
  name: string;
  isFree: boolean;
}

export function useModelCatalog() {
  return useQuery({
    queryKey: ["model-catalog"],
    queryFn: () => api.kernel.models.list().then((r: any) => r?.data?.models ?? []),
    select: (rows: any[]): ModelOption[] =>
      rows.map((m) => ({ id: m.id, name: m.name, isFree: Boolean(m.is_free) })),
    staleTime: 60 * 60 * 1000, // 1h, matches backend cache TTL
  });
}
```

### `dashboard/lib/api.ts`

Add alongside the existing `personas` entry:

```typescript
kernel: {
  ...,
  models: { list: () => GET<any>("/kernel/models") },
},
```

### `dashboard/components/model-combobox.tsx` (new, shared by both platforms)

A single `cmdk`-based component, unstyled at the `Command`/`Command.Item`
level (matching `command-palette.tsx`'s use of `cmdk`), taking `value`,
`onChange`, `options: ModelOption[]`, and a `variant: "mobile" | "desktop"`
prop that switches between CSS-variable inline styles and Tailwind classes
— the same platform split every other picker component in this codebase
already makes, just contained in one file instead of duplicated across two.

Behavior:
- Renders as a button showing the current value; clicking expands an
  inline (not modal) search input + `Command.List` below it, closes on
  selection or click-outside.
- `Command.Group` headings "Free" / "Paid" from `option.isFree`.
- If the persona's current `model` isn't in `options` (stale/manual value,
  or the catalog hasn't loaded yet), it's shown pinned above the groups —
  same one-off-option behavior the static dropdown has today, so the
  picker never misrepresents what's actually stored.
- While `useModelCatalog()` is loading, the combobox shows the current
  value as a disabled button (no dropdown yet) rather than an empty list —
  avoids a flash of "no models found."
- On catalog fetch error client-side (network down before the request even
  reaches the backend), falls back to the same static `MODEL_OPTIONS`
  import used today, so a fully offline frontend still has *something*
  selectable.

### `dashboard/components/persona-settings.tsx` and `dashboard/app/settings/page.tsx`

Replace the `<select><optgroup>` block in each with
`<ModelCombobox variant="mobile" .../>` / `<ModelCombobox variant="desktop" .../>`
respectively. No other change to either file — the dirty-tracking,
save/revert, and error-message logic around the model field is untouched.

## Error handling

| Failure | Behavior |
|---|---|
| OpenRouter unreachable / non-200 / malformed JSON | Backend serves last-good in-memory cache; if none yet, serves `FALLBACK_MODELS` (today's curated list). Frontend never sees an error for this case. |
| `GET /kernel/models` itself unreachable (network/backend down) | React Query surfaces `isError`; `ModelCombobox` falls back to the static `MODEL_OPTIONS` import client-side. |
| Persona's current `model` not present in the fetched catalog | Pinned as a one-off selected option, same as today's "unknown model" handling. |
| OpenRouter catalog includes a model whose id collides in shape with a Gemini direct model already in `FALLBACK_MODELS`'s paid list | Not possible — OpenRouter ids are always prefixed `openrouter/`, Gemini direct ids never are; no collision surface. |

## Testing

- Backend: `tests/unit/test_model_catalog.py` (new) — mock `httpx.AsyncClient.get`
  to return a fake OpenRouter payload, assert Free/Paid classification from
  pricing fields and the `openrouter/` id prefix; assert the Gemini paid
  entries from `FALLBACK_MODELS` are always present on a successful fetch
  (not just on failure); assert cache-hit avoids a second HTTP call within
  the TTL; assert failure with no prior cache returns `FALLBACK_MODELS`;
  assert failure with a prior cache returns the stale cached list instead
  of failing.
- Frontend: manual browser verification only (no component test infra in
  this repo, same as the original persona picker) — load `/m/personas` and
  `/settings`, confirm the combobox lists live OpenRouter models grouped
  Free/Paid, search filters correctly, selecting and saving works, and a
  persona with an already-set unknown model still shows it pinned.

## Open items intentionally deferred

- Model pricing/context-length shown inline in the dropdown — non-goal
  above, real usability win but a separate feature.
- Server-side search instead of "fetch full catalog, filter client-side" —
  not worth the complexity at OpenRouter's current catalog size
  (low hundreds of models, tens of KB of JSON).
- Redis-backed cache instead of process-local — only matters once there
  are multiple app replicas serving cold caches independently; revisit if
  that becomes true.
