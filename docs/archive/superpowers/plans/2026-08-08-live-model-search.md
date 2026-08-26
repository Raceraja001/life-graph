# Live OpenRouter Model Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the persona model picker's curated static Free/Paid dropdown with a live, searchable list backed by OpenRouter's real model catalog, cached server-side with a static-list fallback so the picker can never break.

**Architecture:** A new backend service (`life_graph/services/model_catalog.py`) fetches and caches OpenRouter's public `/api/v1/models` catalog in-process (1h TTL), classifying Free/Paid from real pricing data and always carrying over the two Gemini direct models (never in OpenRouter's catalog). A new `GET /kernel/models` route exposes it. The frontend gets a new `useModelCatalog()` hook and a shared `ModelCombobox` component (built on the `cmdk` library already used by the command palette) that replaces the `<select><optgroup>` block in both the mobile and desktop persona cards.

**Tech Stack:** FastAPI + httpx (backend), Next.js/React + TanStack Query + `cmdk` (frontend) — all already in use, no new dependencies.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-08-08-live-model-search-design.md` — read for full rationale.
- OpenRouter's `/api/v1/models` endpoint is public and unauthenticated — no API key needed.
- OpenRouter model ids from this codebase are always prefixed `openrouter/` (matches `resilient_llm.py`/litellm convention) — the catalog must apply this prefix.
- The two Gemini direct models (`gemini/gemini-3.6-flash`, `gemini/gemini-3.5-flash-lite`) never appear in OpenRouter's catalog and must always be present in the returned list, on both the success and failure paths.
- On any fetch failure with no prior cache, fall back to exactly the `FALLBACK_MODELS` list (mirrors today's `dashboard/lib/model-options.ts` curated list) — the picker must never end up with zero options.
- No new UI dependency — use `cmdk` (already installed, already used in `dashboard/components/command-palette.tsx`).
- No change to how a model selection is saved — `PATCH /kernel/personas/{id}` and `useUpdatePersona` are untouched.
- Follow this repo's existing response wrapper (`success_response(data=...)`) and router/DI conventions in `life_graph/api/kernel.py`.
- No frontend component test infra exists in this repo — frontend tasks are verified manually in a real browser, matching the original persona-picker plan's convention.

---

### Task 1: Backend — model catalog service + `/kernel/models` route

**Files:**
- Create: `life_graph/services/model_catalog.py`
- Modify: `life_graph/api/kernel.py:556-559` (insert a new section between `delete_persona` and `# ── Router Schemas ──`)
- Test: `tests/unit/test_model_catalog.py`

**Interfaces:**
- Produces: `async def get_model_catalog() -> list[dict]` where each dict is `{"id": str, "name": str, "is_free": bool}`. `FALLBACK_MODELS: list[dict]` (same shape) is also exported — Task 2 does not consume it directly, but Task 3/4's manual verification may reference it.
- Produces: `GET /kernel/models` → `{"data": {"models": [...]}}` (same shape as the personas list route's wrapper).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_model_catalog.py`:

```python
import pytest

from life_graph.services import model_catalog


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._body


class _FakeAsyncClient:
    last_request: dict | None = None
    body: dict = {"data": []}
    raise_on_get: bool = False

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        _FakeAsyncClient.last_request = {"url": url}
        if _FakeAsyncClient.raise_on_get:
            raise RuntimeError("network down")
        return _FakeResponse(_FakeAsyncClient.body)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    model_catalog._CACHE.clear()
    _FakeAsyncClient.body = {"data": []}
    _FakeAsyncClient.raise_on_get = False
    _FakeAsyncClient.last_request = None
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    yield


@pytest.mark.asyncio
async def test_classifies_free_and_paid_from_pricing():
    _FakeAsyncClient.body = {
        "data": [
            {
                "id": "nvidia/nemotron-3-super-120b-a12b:free",
                "name": "Nemotron 3 Super",
                "pricing": {"prompt": "0", "completion": "0"},
            },
            {
                "id": "openai/gpt-5",
                "name": "GPT-5",
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            },
        ]
    }

    models = await model_catalog.get_model_catalog()

    free = next(m for m in models if m["id"] == "openrouter/nvidia/nemotron-3-super-120b-a12b:free")
    paid = next(m for m in models if m["id"] == "openrouter/openai/gpt-5")
    assert free["is_free"] is True
    assert paid["is_free"] is False


@pytest.mark.asyncio
async def test_gemini_fallback_entries_always_present_on_success():
    _FakeAsyncClient.body = {"data": []}

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "gemini/gemini-3.6-flash" in ids
    assert "gemini/gemini-3.5-flash-lite" in ids


@pytest.mark.asyncio
async def test_cache_hit_avoids_second_http_call():
    _FakeAsyncClient.body = {
        "data": [{"id": "a/b", "name": "A B", "pricing": {"prompt": "0", "completion": "0"}}]
    }

    await model_catalog.get_model_catalog()
    assert _FakeAsyncClient.last_request is not None
    _FakeAsyncClient.last_request = None

    await model_catalog.get_model_catalog()
    assert _FakeAsyncClient.last_request is None


@pytest.mark.asyncio
async def test_failure_with_no_prior_cache_returns_fallback():
    _FakeAsyncClient.raise_on_get = True

    models = await model_catalog.get_model_catalog()

    assert models == model_catalog.FALLBACK_MODELS


@pytest.mark.asyncio
async def test_failure_with_prior_cache_returns_stale_cache():
    _FakeAsyncClient.body = {
        "data": [{"id": "a/b", "name": "A B", "pricing": {"prompt": "0", "completion": "0"}}]
    }
    first = await model_catalog.get_model_catalog()

    cached_at, _ = model_catalog._CACHE[model_catalog._CACHE_KEY]
    model_catalog._CACHE[model_catalog._CACHE_KEY] = (
        cached_at - model_catalog._TTL_SECONDS - 1,
        first,
    )
    _FakeAsyncClient.raise_on_get = True

    models = await model_catalog.get_model_catalog()

    assert models == first
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_model_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'life_graph.services.model_catalog'`

- [ ] **Step 3: Create the service**

Create `life_graph/services/model_catalog.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_model_catalog.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Add the `GET /kernel/models` route**

In `life_graph/api/kernel.py`, add this import alongside the existing ones (near line 34):

```python
from life_graph.services.model_catalog import get_model_catalog
```

Then insert this new section between the end of `delete_persona` (line 556, `return success_response(data=result)`) and the `# ── Router Schemas ──` comment (line 559):

```python
# ── Model Catalog Endpoint ───────────────────────────────────


@router.get(
    "/models",
    summary="List available LLM models for the persona picker",
)
async def list_models():
    """Live OpenRouter model catalog (cached), for the persona model picker.

    Never fails — degrades to a cached or static list on fetch errors.
    """
    models = await get_model_catalog()
    return success_response(data={"models": models})
```

- [ ] **Step 6: Manually verify the route**

Run: `python -m uvicorn life_graph.main:app --port 8080 &` then
`curl -s -H "X-API-Key: <your local key>" -H "X-Tenant-ID: default" http://localhost:8080/api/v1/kernel/models | head -c 500`
Expected: JSON with `"data": {"models": [...]}`, each entry has `id`/`name`/`is_free`.

- [ ] **Step 7: Run the full unit suite and commit**

Run: `python -m pytest tests/unit/ -v`
Expected: PASS, no new failures.

```bash
git add life_graph/services/model_catalog.py life_graph/api/kernel.py tests/unit/test_model_catalog.py
git commit -m "feat: live OpenRouter model catalog + GET /kernel/models"
```

---

### Task 2: Frontend data layer — `useModelCatalog` hook

**Files:**
- Modify: `dashboard/lib/api.ts:177-181` (the `kernel.personas` block)
- Modify: `dashboard/lib/mobile-api.ts` (end of file, after `useUpdatePersona`, currently ending at line 485)

**Interfaces:**
- Consumes: `success_response(data={"models": [...]})` shape from Task 1's `GET /kernel/models`.
- Produces: `export interface ModelOption { id: string; name: string; isFree: boolean }` and `export function useModelCatalog()` returning a TanStack Query result whose `.data` is `ModelOption[] | undefined`. Task 3 consumes both.

- [ ] **Step 1: Add the API client method**

In `dashboard/lib/api.ts`, inside the `kernel` object (around line 177-181), add a `models` entry next to `personas`:

```typescript
    personas: {
      list: () => GET<any>("/kernel/personas"),  // caller unwraps .data.personas
      update: (id: string, body: Record<string, unknown>) =>
        request<any>("PATCH", `/kernel/personas/${id}`, body),
    },
    models: {
      list: () => GET<any>("/kernel/models"),  // caller unwraps .data.models
    },
```

- [ ] **Step 2: Add the hook**

Append to the end of `dashboard/lib/mobile-api.ts` (after `useUpdatePersona`, which currently ends the file at line 485):

```typescript

// ── Model catalog (live OpenRouter search for the persona picker) ──────
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
      rows.map((m) => ({ id: String(m.id ?? ""), name: m.name ?? m.id ?? "", isFree: Boolean(m.is_free) })),
    staleTime: 60 * 60 * 1000,
  });
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no new type errors.

- [ ] **Step 4: Manually verify the hook**

With the backend running (Task 1's Step 6), start the dashboard (`npm run dev`), open the browser console on any page, and confirm no network errors — `useModelCatalog` isn't consumed by any component yet, so add a temporary `console.log` in a page you're viewing if you want to eyeball the shape, then remove it before committing.

- [ ] **Step 5: Commit**

```bash
git add dashboard/lib/api.ts dashboard/lib/mobile-api.ts
git commit -m "feat: model catalog API client + useModelCatalog hook"
```

---

### Task 3: `ModelCombobox` shared component

**Files:**
- Create: `dashboard/components/model-combobox.tsx`

**Interfaces:**
- Consumes: `useModelCatalog()` and `ModelOption` from `dashboard/lib/mobile-api.ts` (Task 2). `MODEL_OPTIONS` from `dashboard/lib/model-options.ts` (existing, used only as the client-side network-failure fallback).
- Produces: `export function ModelCombobox(props: { value: string; onChange: (id: string) => void; disabled?: boolean; variant: "mobile" | "desktop" }): JSX.Element`. Task 4 renders this in place of the existing `<select>`.

- [ ] **Step 1: Create the component**

Create `dashboard/components/model-combobox.tsx`:

```tsx
"use client";
// Searchable model picker backed by the live OpenRouter catalog
// (useModelCatalog). Replaces the static <select><optgroup> dropdown.
// Built on cmdk (already used by command-palette.tsx) — no new dependency.
import { useEffect, useRef, useState } from "react";
import { Command } from "cmdk";
import { useModelCatalog, type ModelOption } from "@/lib/mobile-api";
import { MODEL_OPTIONS } from "@/lib/model-options";

const STATIC_FALLBACK: ModelOption[] = [
  ...MODEL_OPTIONS.Free.map((id) => ({ id, name: id, isFree: true })),
  ...MODEL_OPTIONS.Paid.map((id) => ({ id, name: id, isFree: false })),
];

interface ModelComboboxProps {
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
  variant: "mobile" | "desktop";
}

export function ModelCombobox({ value, onChange, disabled, variant }: ModelComboboxProps) {
  const catalog = useModelCatalog();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const options: ModelOption[] = catalog.isError
    ? STATIC_FALLBACK
    : catalog.data ?? [];
  const loading = catalog.isLoading;

  const known = options.some((m) => m.id === value);
  const pinned: ModelOption | null = value && !known ? { id: value, name: value, isFree: false } : null;
  const free = options.filter((m) => m.isFree);
  const paid = options.filter((m) => !m.isFree);

  const isMobile = variant === "mobile";
  const buttonStyle = isMobile
    ? {
        width: "100%",
        textAlign: "left" as const,
        padding: "8px 10px",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--border)",
        background: "var(--surface)",
        color: "var(--text)",
        fontSize: "var(--text-xs)",
      }
    : undefined;
  const buttonClassName = isMobile
    ? undefined
    : "w-full mt-1 text-left text-sm text-zinc-800 bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100";

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <button
        type="button"
        disabled={disabled || loading}
        onClick={() => setOpen((o) => !o)}
        style={buttonStyle}
        className={buttonClassName}
      >
        {loading ? "Loading models…" : value || "Select a model"}
      </button>

      {open && !loading && (
        <div
          style={
            isMobile
              ? {
                  position: "absolute",
                  zIndex: 20,
                  top: "100%",
                  left: 0,
                  right: 0,
                  marginTop: "4px",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                  boxShadow: "var(--shadow-md, 0 4px 12px rgba(0,0,0,0.1))",
                }
              : undefined
          }
          className={
            isMobile
              ? undefined
              : "absolute z-20 top-full left-0 right-0 mt-1 bg-white border border-zinc-200 rounded-lg shadow-lg"
          }
        >
          <Command>
            <Command.Input
              autoFocus
              placeholder="Search models…"
              style={
                isMobile
                  ? {
                      width: "100%",
                      padding: "8px 10px",
                      border: "none",
                      borderBottom: "1px solid var(--border)",
                      background: "transparent",
                      color: "var(--text)",
                      fontSize: "var(--text-xs)",
                      outline: "none",
                    }
                  : undefined
              }
              className={
                isMobile
                  ? undefined
                  : "w-full px-3 py-2 text-sm border-b border-zinc-100 outline-none"
              }
            />
            <Command.List style={{ maxHeight: "220px", overflowY: "auto", padding: "4px" }}>
              <Command.Empty
                style={isMobile ? { padding: "10px", fontSize: "var(--text-xs)", color: "var(--text-muted)" } : undefined}
                className={isMobile ? undefined : "px-3 py-4 text-sm text-zinc-400 text-center"}
              >
                No models found.
              </Command.Empty>

              {pinned && (
                <Command.Group heading="Current">
                  <ModelItem model={pinned} isMobile={isMobile} onSelect={onChange} setOpen={setOpen} />
                </Command.Group>
              )}
              <Command.Group heading="Free">
                {free.map((m) => (
                  <ModelItem key={m.id} model={m} isMobile={isMobile} onSelect={onChange} setOpen={setOpen} />
                ))}
              </Command.Group>
              <Command.Group heading="Paid">
                {paid.map((m) => (
                  <ModelItem key={m.id} model={m} isMobile={isMobile} onSelect={onChange} setOpen={setOpen} />
                ))}
              </Command.Group>
            </Command.List>
          </Command>
        </div>
      )}
    </div>
  );
}

function ModelItem({
  model,
  isMobile,
  onSelect,
  setOpen,
}: {
  model: ModelOption;
  isMobile: boolean;
  onSelect: (id: string) => void;
  setOpen: (open: boolean) => void;
}) {
  return (
    <Command.Item
      value={`${model.id} ${model.name}`}
      onSelect={() => {
        onSelect(model.id);
        setOpen(false);
      }}
      style={
        isMobile
          ? {
              padding: "6px 8px",
              borderRadius: "var(--radius-sm, 4px)",
              fontSize: "var(--text-xs)",
              color: "var(--text)",
              cursor: "pointer",
            }
          : undefined
      }
      className={
        isMobile
          ? undefined
          : "px-3 py-1.5 rounded text-sm text-zinc-700 cursor-pointer data-[selected=true]:bg-emerald-50 data-[selected=true]:text-emerald-700"
      }
    >
      {model.name}
    </Command.Item>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no new type errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/components/model-combobox.tsx
git commit -m "feat: ModelCombobox — searchable live model picker (cmdk-based)"
```

---

### Task 4: Wire `ModelCombobox` into the mobile and desktop persona cards

**Files:**
- Modify: `dashboard/components/persona-settings.tsx:108-130` (the `<select>` block)
- Modify: `dashboard/app/settings/page.tsx:104-128` (the `<select>` block)

**Interfaces:**
- Consumes: `ModelCombobox` from `dashboard/components/model-combobox.tsx` (Task 3).

- [ ] **Step 1: Replace the mobile `<select>`**

In `dashboard/components/persona-settings.tsx`, add the import near the top (after the existing `MODEL_OPTIONS` import on line 11):

```typescript
import { ModelCombobox } from "@/components/model-combobox";
```

Replace lines 108-130 (from `<label style={labelStyle}>Model</label>` through the closing `</select>`):

```tsx
      <label style={labelStyle}>Model</label>
      <div style={{ marginBottom: "10px" }}>
        <ModelCombobox value={model} onChange={setModel} disabled={busy} variant="mobile" />
      </div>
```

The `isUnknownModel`/`knownModels` computation above it (lines 84-85) is now dead code — remove it:

```typescript
  const knownModels = [...MODEL_OPTIONS.Free, ...MODEL_OPTIONS.Paid];
  const isUnknownModel = Boolean(persona.model) && !knownModels.includes(persona.model);
```

`ModelCombobox` handles the "unknown model" pinning internally now (see Task 3), so these two lines and the now-unused `MODEL_OPTIONS` import at the top of the file should be deleted.

- [ ] **Step 2: Replace the desktop `<select>`**

In `dashboard/app/settings/page.tsx`, add the import (replacing the `MODEL_OPTIONS` import on line 4):

```typescript
import { ModelCombobox } from "@/components/model-combobox";
```

Replace lines 104-128 (from `<div>` wrapping the Model `<label>` through its closing `</div>`):

```tsx
      <div>
        <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Model</label>
        <div className="mt-1">
          <ModelCombobox value={model} onChange={setModel} disabled={busy} variant="desktop" />
        </div>
      </div>
```

Remove the now-dead `knownModels`/`isUnknownModel` lines (87-88) the same way as Step 1.

- [ ] **Step 3: Verify it compiles**

Run: `cd dashboard && npx tsc --noEmit`
Expected: no type errors (confirms no other file still imports the now-removed `MODEL_OPTIONS` usage from these two files).

- [ ] **Step 4: Manual browser verification**

With the backend running (`python -m uvicorn life_graph.main:app --port 8080`) and the dashboard running (`npm run dev`):

1. Open `/m/personas` (mobile route) — confirm the Model field is now a button; click it, confirm a search box + Free/Paid grouped list appears with real OpenRouter models (more than the 7 in the old static list).
2. Type a search term (e.g. "gemma") — confirm the list filters.
3. Select a different model, confirm the Save button enables, save, confirm the change persists after a page reload.
4. Open `/settings` (desktop route) — repeat steps 1-3 there.
5. Pick a persona whose current `model` value is NOT in the live catalog (or temporarily set one via the API to a made-up string) — confirm it shows pinned under "Current" instead of being silently dropped.
6. With the backend still running (stopping it entirely would also fail
   `usePersonas()` itself, so no card would render to test against): open
   Chrome DevTools → Network tab, find the `models` request to
   `/api/v1/kernel/models`, right-click it → "Block request URL", then
   reload `/m/personas`. Confirm the persona cards still render (the
   personas list request is unaffected) and the Model combobox still shows
   the static fallback list rather than being empty. Unblock the request
   afterward.

- [ ] **Step 5: Run the full test suite and commit**

Run: `python -m pytest tests/unit/ -v` and `cd dashboard && npx tsc --noEmit`
Expected: both pass, no new failures.

```bash
git add dashboard/components/persona-settings.tsx dashboard/app/settings/page.tsx
git commit -m "feat: wire ModelCombobox into mobile and desktop persona cards"
```
