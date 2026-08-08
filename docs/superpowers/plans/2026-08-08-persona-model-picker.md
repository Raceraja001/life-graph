# Persona Model Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a persona's `model`/`temperature`/`max_tokens` be edited from the dashboard (mobile + desktop) via the already-existing `PATCH /kernel/personas/{id}` endpoint, so a dead model id on an already-seeded persona can be fixed without SSH/DB access/redeploy.

**Architecture:** One additive backend change (expose `temperature`/`max_tokens` on the persona list response, which today only has them on the single-persona fetch) plus a shared React Query data layer (`usePersonas`/`useUpdatePersona`) consumed by two platform-specific presentational components — a mobile one mirroring `ambient-roles.tsx`'s CSS-variable idiom, a desktop one mirroring `settings/page.tsx`'s Tailwind/zinc idiom.

**Tech Stack:** FastAPI + Pydantic (backend), Next.js 16 / React 19 + TanStack Query (dashboard), `httpx.AsyncClient` + `ASGITransport` for backend tests (no dashboard unit-test convention exists in this repo — frontend verification is manual, in a real browser, per existing project convention).

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-08-08-persona-model-picker-design.md` (committed `0391b68`) — every task implements one section of it.
- Curated model list, exact values:
  - Free: `openrouter/nvidia/nemotron-3-super-120b-a12b:free`, `openrouter/openai/gpt-oss-20b:free`, `openrouter/google/gemma-4-31b-it:free`, `openrouter/google/gemma-4-26b-a4b-it:free`
  - Paid: `gemini/gemini-3.6-flash`, `gemini/gemini-3.5-flash-lite`, `openrouter/deepseek/deepseek-chat`
- Field bounds (already enforced backend-side by `PersonaUpdate` in `life_graph/api/kernel.py`): `temperature` 0.0–2.0 step 0.1, `max_tokens` 1–128000. Frontend number inputs use the same bounds so a bad value is caught before the request, not just by a 422.
- Response shapes to respect exactly:
  - `GET /kernel/personas` → `{"data": {"personas": [...], "total": n}}` (nested — unwrap `res.data.personas`).
  - `GET /kernel/personas/{id}` → `{"data": {...full persona...}}` (not nested under a named key).
  - `PATCH /kernel/personas/{id}` → `{"data": {"id", "name", "updated_at", "message"}}` — narrow. Never read updated field values from this response; rely on query invalidation + refetch instead.
- Built-in personas (`is_builtin: true`) remain fully editable through this feature — no blocking, just an informational "Built-in" badge. Fixing a built-in persona's dead model is this feature's entire reason to exist.
- Error message text, exact: `"Couldn't save — try again"`.
- Mobile components use the CSS-custom-property inline-style idiom (`var(--surface)`, `var(--text-xs)`, etc.) established by `dashboard/components/ambient-roles.tsx` and `dashboard/components/mobile/parts.tsx` — no Tailwind classes in mobile code. Desktop components use the Tailwind/zinc idiom established by `dashboard/app/settings/page.tsx` — no CSS variables in desktop code. Do not cross the two.
- Test command for backend: run from repo root using `/c/Python314/python.exe -m pytest tests/integration/test_kernel_personas.py -v` (this dev environment has multiple Pythons on PATH; bare `python`/`pytest` resolve to the wrong interpreter).
- No persona create/delete UI, no editing of `system_prompt`/`allowed_tools`/`intent_tags`/`properties`, no confirmation dialog before picking a paid model, no changes to the global fallback chain (`config.py`'s `llm_fallback_chain` etc.) — all explicitly out of scope per the design's Non-goals.

---

### Task 1: Backend — expose temperature/max_tokens on the persona list response

**Files:**
- Modify: `life_graph/api/kernel.py:370-401` (the `PersonaSummary` model and `_persona_to_summary` function)
- Test: `tests/integration/test_kernel_personas.py` (extend `class TestListPersonas`)

**Interfaces:**
- Consumes: nothing new.
- Produces: `GET /kernel/personas`'s response now includes `"temperature": float` and `"max_tokens": int` per persona, alongside the existing summary fields. Task 2's `mapPersona()` reads these two new keys directly from the list response (no per-persona detail fetch).

The current code (`life_graph/api/kernel.py:370-401`):

```python
class PersonaSummary(BaseModel):
    """Compact persona representation for list responses."""

    id: str
    name: str
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    model: str
    intent_tags: list[str] | None = None
    is_builtin: bool = False
    is_active: bool = True
    use_count: int = 0


# ── Persona Endpoints ────────────────────────────────────────


def _persona_to_summary(p: dict) -> dict:
    """Extract summary fields from a persona dict."""
    return {
        "id": p["id"],
        "name": p["name"],
        "display_name": p.get("display_name"),
        "description": p.get("description"),
        "icon": p.get("icon"),
        "model": p.get("model", ""),
        "intent_tags": p.get("intent_tags"),
        "is_builtin": p.get("is_builtin", False),
        "is_active": p.get("is_active", True),
        "use_count": p.get("use_count", 0),
    }
```

- [ ] **Step 1: Write the failing test**

Add this test method inside `class TestListPersonas` in `tests/integration/test_kernel_personas.py`, right after the existing `test_list_personas_include_inactive` method (matching that class's existing decorator/fixture/tolerant-status-code conventions exactly):

```python
    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_list_personas_includes_temperature_and_max_tokens(
        self, client: AsyncClient,
    ):
        """List response includes temperature/max_tokens per persona, not just
        the narrow summary fields — the model picker renders every persona as
        an editable card from this one list call, with no per-persona detail
        fetch, so both fields must be present here."""
        response = await client.get("/api/v1/kernel/personas")
        assert response.status_code in (200, 500)

        if response.status_code == 200:
            body = response.json()
            personas = body["data"]["personas"]
            if personas:
                first = personas[0]
                assert "temperature" in first
                assert "max_tokens" in first
                assert isinstance(first["temperature"], float)
                assert isinstance(first["max_tokens"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_kernel_personas.py -v -k test_list_personas_includes_temperature_and_max_tokens`
Expected: FAIL with `AssertionError` (`'temperature' in first` is `False`) if the DB is reachable and at least one persona exists; if the DB is unreachable, the test's own `response.status_code in (200, 500)` tolerance means it may not fail — in that case, note in your report that the RED step was inconclusive due to no DB, and rely on Step 4's GREEN run instead (same DB-availability caveat applies there too, and is expected in this environment per the project's own test conventions — see `tests/integration/conftest.py`'s `skip_on_db_error`).

- [ ] **Step 3: Implement the fix**

Replace `life_graph/api/kernel.py:370-401` with:

```python
class PersonaSummary(BaseModel):
    """Compact persona representation for list responses."""

    id: str
    name: str
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    intent_tags: list[str] | None = None
    is_builtin: bool = False
    is_active: bool = True
    use_count: int = 0


# ── Persona Endpoints ────────────────────────────────────────


def _persona_to_summary(p: dict) -> dict:
    """Extract summary fields from a persona dict."""
    return {
        "id": p["id"],
        "name": p["name"],
        "display_name": p.get("display_name"),
        "description": p.get("description"),
        "icon": p.get("icon"),
        "model": p.get("model", ""),
        "temperature": p.get("temperature", 0.7),
        "max_tokens": p.get("max_tokens", 4096),
        "intent_tags": p.get("intent_tags"),
        "is_builtin": p.get("is_builtin", False),
        "is_active": p.get("is_active", True),
        "use_count": p.get("use_count", 0),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_kernel_personas.py -v -k test_list_personas_includes_temperature_and_max_tokens`
Expected: PASS (or skip/tolerant-500 if DB unavailable in this environment — see Step 2's caveat).

- [ ] **Step 5: Run the full persona test file to confirm no regressions**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_kernel_personas.py -v`
Expected: all tests PASS (or skip, per this file's DB-availability tolerance) — adding two fields to a response dict is additive and shouldn't affect any existing assertion in this file (none of the existing tests assert an exact/closed set of keys in the summary response).

- [ ] **Step 6: Commit**

```bash
git add life_graph/api/kernel.py tests/integration/test_kernel_personas.py
git commit -m "feat: expose temperature/max_tokens on persona list response

The model picker renders every persona as an independently-editable
card from one list call — both fields were previously only available
via the single-persona detail fetch."
```

---

### Task 2: Frontend data layer — API client, hooks, curated model list

**Files:**
- Modify: `dashboard/lib/api.ts` (the `personas` entry inside the `kernel` object)
- Create: `dashboard/lib/model-options.ts`
- Modify: `dashboard/lib/mobile-api.ts` (append a new Personas section)

**Interfaces:**
- Consumes: Task 1's `GET /kernel/personas` response now including `temperature`/`max_tokens`.
- Produces: `api.kernel.personas.list()`, `api.kernel.personas.update(id, body)` (both `dashboard/lib/api.ts`); `MODEL_OPTIONS: {Free: string[], Paid: string[]}` (`dashboard/lib/model-options.ts`); `PersonaVM` type, `usePersonas()`, `useUpdatePersona()` (`dashboard/lib/mobile-api.ts`) — Tasks 3 and 4 both import all of these directly, by these exact names.

- [ ] **Step 1: Fix the stale `personas` entry in `dashboard/lib/api.ts`**

Find this line inside the `kernel` object (currently a bare function that lies about its own return shape — nothing in the app currently calls it):

```typescript
    personas: () => GET<any[]>("/kernel/personas"),
```

Replace it with:

```typescript
    personas: {
      list: () => GET<any>("/kernel/personas"),  // caller unwraps .data.personas
      update: (id: string, body: Record<string, unknown>) =>
        request<any>("PATCH", `/kernel/personas/${id}`, body),
    },
```

- [ ] **Step 2: Create the curated model list**

Create `dashboard/lib/model-options.ts`:

```typescript
// Curated model choices for the persona model picker. Grouped by cost so a
// cost-conscious choice is visible at a glance. Adding a genuinely new model
// here is a small dashboard-only code change — no backend redeploy needed.
export const MODEL_OPTIONS: { Free: string[]; Paid: string[] } = {
  Free: [
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/openai/gpt-oss-20b:free",
    "openrouter/google/gemma-4-31b-it:free",
    "openrouter/google/gemma-4-26b-a4b-it:free",
  ],
  Paid: [
    "gemini/gemini-3.6-flash",
    "gemini/gemini-3.5-flash-lite",
    "openrouter/deepseek/deepseek-chat",
  ],
};
```

- [ ] **Step 3: Add the Personas section to `dashboard/lib/mobile-api.ts`**

Append this block at the end of the file (after the existing `useGradeShadowRun` block — appending at end-of-file avoids disturbing the internal cohesion of the preceding Ambient/Findings/Shadow sections):

```typescript
// ── Personas (model picker) ─────────────────────────────
// Lets a persona's model/temperature/max_tokens be edited from the
// dashboard — fixes a persona stuck on a dead/deprecated model id without
// SSH or direct database access.
export interface PersonaVM {
  id: string;
  name: string;
  displayName: string | null;
  icon: string | null;
  model: string;
  temperature: number;
  maxTokens: number;
  isBuiltin: boolean;
}

export function mapPersona(raw: any): PersonaVM {
  return {
    id: String(raw?.id ?? ""),
    name: raw?.name ?? "",
    displayName: raw?.display_name ?? null,
    icon: raw?.icon ?? null,
    model: raw?.model ?? "",
    temperature: typeof raw?.temperature === "number" ? raw.temperature : 0.7,
    maxTokens: typeof raw?.max_tokens === "number" ? raw.max_tokens : 4096,
    isBuiltin: Boolean(raw?.is_builtin),
  };
}

export function usePersonas() {
  return useQuery({
    queryKey: ["personas"],
    queryFn: () => api.kernel.personas.list().then((r: any) => r?.data?.personas ?? []),
    select: (rows: any[]) => rows.map(mapPersona),
  });
}

export function useUpdatePersona() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.kernel.personas.update(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["personas"] }),
  });
}
```

- [ ] **Step 4: Verify it builds**

Run: `cd dashboard && npm run build`
Expected: build succeeds with no TypeScript errors. If `personas.list`/`personas.update` or the new `mobile-api.ts` exports produce a type error, fix it before proceeding — do not silence with `// @ts-ignore`.

- [ ] **Step 5: Commit**

```bash
git add dashboard/lib/api.ts dashboard/lib/model-options.ts dashboard/lib/mobile-api.ts
git commit -m "feat: persona data layer — API client, hooks, curated model list

usePersonas/useUpdatePersona + the Free/Paid model list, ready for the
mobile and desktop picker UIs to consume. Also fixes the stale
personas API entry, which lied about its own return shape and was
unused anywhere in the app."
```

---

### Task 3: Mobile UI

**Files:**
- Create: `dashboard/components/persona-settings.tsx`
- Create: `dashboard/app/(mobile)/m/personas/page.tsx`
- Modify: `dashboard/app/(mobile)/m/settings/page.tsx` (add a link to the new page)

**Interfaces:**
- Consumes: `usePersonas()`, `useUpdatePersona()`, `PersonaVM` (Task 2, `dashboard/lib/mobile-api.ts`); `MODEL_OPTIONS` (Task 2, `dashboard/lib/model-options.ts`); `LoadingCard`/`EmptyCard`/`ErrorCard`/`SectionEyebrow` (existing, `dashboard/components/mobile/parts.tsx`).
- Produces: a default-exported `PersonaSettings` component, and the route `/m/personas`. Nothing in a later task depends on this.

- [ ] **Step 1: Create the mobile component**

Create `dashboard/components/persona-settings.tsx`:

```tsx
"use client";
// Persona model/temperature/max_tokens editor — fixes a persona stuck on a
// dead/deprecated model id without SSH or direct database access. Mirrors
// ambient-roles.tsx's card/CSS-variable conventions, but gives each card its
// own useUpdatePersona() mutation instance (rather than one shared mutation
// at the list level) so busy/error state is naturally scoped per card, with
// no need to compare a shared mutation's `variables.id` against each row.
import { useState, type CSSProperties } from "react";
import { LoadingCard, EmptyCard, ErrorCard, SectionEyebrow } from "@/components/mobile/parts";
import { usePersonas, useUpdatePersona, type PersonaVM } from "@/lib/mobile-api";
import { MODEL_OPTIONS } from "@/lib/model-options";

const cardStyle: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-lg)",
  boxShadow: "var(--shadow-xs)",
  padding: "14px",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: "var(--radius-md)",
  border: "1px solid var(--border)",
  background: "var(--surface)",
  color: "var(--text)",
  fontSize: "var(--text-xs)",
};

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: "var(--text-xs)",
  color: "var(--text-muted)",
  marginBottom: "4px",
};

export default function PersonaSettings() {
  const personas = usePersonas();
  const rows = personas.data ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <SectionEyebrow>Personas</SectionEyebrow>
      {personas.isLoading && <LoadingCard label="Loading personas…" />}
      {personas.isError && <ErrorCard>Can&rsquo;t reach personas — is the backend running?</ErrorCard>}
      {!personas.isLoading && !personas.isError && rows.length === 0 && (
        <EmptyCard>No personas configured yet.</EmptyCard>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {rows.map((p) => (
          <PersonaCard key={p.id} persona={p} />
        ))}
      </div>
    </div>
  );
}

function PersonaCard({ persona }: { persona: PersonaVM }) {
  const update = useUpdatePersona();
  const busy = update.isPending;

  const [model, setModel] = useState(persona.model);
  const [temperature, setTemperature] = useState(persona.temperature);
  const [maxTokens, setMaxTokens] = useState(persona.maxTokens);

  const dirty =
    model !== persona.model || temperature !== persona.temperature || maxTokens !== persona.maxTokens;

  function revert() {
    setModel(persona.model);
    setTemperature(persona.temperature);
    setMaxTokens(persona.maxTokens);
  }

  function save() {
    const body: Record<string, unknown> = {};
    if (model !== persona.model) body.model = model;
    if (temperature !== persona.temperature) body.temperature = temperature;
    if (maxTokens !== persona.maxTokens) body.max_tokens = maxTokens;
    update.mutate({ id: persona.id, body }, { onError: () => revert() });
  }

  const knownModels = [...MODEL_OPTIONS.Free, ...MODEL_OPTIONS.Paid];
  const isUnknownModel = Boolean(persona.model) && !knownModels.includes(persona.model);

  return (
    <section style={{ ...cardStyle, opacity: busy ? 0.7 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "10px" }}>
        <span style={{ fontSize: "var(--ui-text)", fontWeight: "var(--fw-bold)" }}>
          {persona.displayName ?? persona.name}
        </span>
        {persona.isBuiltin && (
          <span
            style={{
              fontSize: "var(--text-2xs)",
              color: "var(--text-subtle)",
              border: "1px solid var(--border)",
              borderRadius: "999px",
              padding: "1px 7px",
            }}
          >
            Built-in
          </span>
        )}
      </div>

      <label style={labelStyle}>Model</label>
      <select
        value={model}
        disabled={busy}
        onChange={(e) => setModel(e.target.value)}
        style={{ ...inputStyle, marginBottom: "10px" }}
      >
        {isUnknownModel && <option value={persona.model}>{persona.model}</option>}
        <optgroup label="Free">
          {MODEL_OPTIONS.Free.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </optgroup>
        <optgroup label="Paid">
          {MODEL_OPTIONS.Paid.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </optgroup>
      </select>

      <div style={{ display: "flex", gap: "10px", marginBottom: "10px" }}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Temperature</label>
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            disabled={busy}
            onChange={(e) => setTemperature(Number(e.target.value))}
            style={inputStyle}
          />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Max tokens</label>
          <input
            type="number"
            min={1}
            max={128000}
            value={maxTokens}
            disabled={busy}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
            style={inputStyle}
          />
        </div>
      </div>

      {update.isError && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--danger, #dc2626)", marginBottom: "8px" }}>
          Couldn&rsquo;t save — try again
        </p>
      )}

      <button
        type="button"
        disabled={!dirty || busy}
        onClick={save}
        style={{
          width: "100%",
          padding: "8px",
          borderRadius: "var(--radius-md)",
          border: "none",
          background: dirty && !busy ? "var(--accent, #2563eb)" : "var(--border)",
          color: dirty && !busy ? "#fff" : "var(--text-subtle)",
          fontSize: "var(--text-xs)",
          fontWeight: "var(--fw-semibold)",
          cursor: dirty && !busy ? "pointer" : "default",
        }}
      >
        Save
      </button>
    </section>
  );
}
```

- [ ] **Step 2: Create the route wrapper**

Create `dashboard/app/(mobile)/m/personas/page.tsx`:

```tsx
"use client";
import PersonaSettings from "@/components/persona-settings";

export default function MobilePersonas() {
  return <PersonaSettings />;
}
```

- [ ] **Step 3: Add a "Personas" link to the mobile settings hub**

In `dashboard/app/(mobile)/m/settings/page.tsx`, find the existing `<Link href="/m/schedules" ...>...</Link>` block (a card linking to "Ambient roles"). Immediately after its closing `</Link>` (and before the following `<Link href="/m/shadow" ...>` block, or after it — either position is fine, place it directly after the schedules link), insert a new link in the exact same shape:

```tsx
      <Link
        href="/m/personas"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "11px",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-xs)",
          padding: "12px 14px",
          textDecoration: "none",
          color: "var(--text)",
        }}
      >
        <span style={{ minWidth: 0, flex: 1 }}>
          <span style={{ display: "block", fontSize: "var(--ui-text)", fontWeight: "var(--fw-semibold)" }}>
            Personas
          </span>
          <span style={{ display: "block", fontSize: "var(--text-2xs)", color: "var(--text-subtle)", marginTop: "1px" }}>
            Model, temperature &amp; max tokens per persona
          </span>
        </span>
        <ChevronRight width={16} height={16} style={{ color: "var(--text-subtle)", flexShrink: 0 }} />
      </Link>
```

(`ChevronRight` and `Link` are already imported in this file, since the schedules/shadow links already use them — no new imports needed for this step.)

- [ ] **Step 4: Verify it builds**

Run: `cd dashboard && npm run build`
Expected: build succeeds with no TypeScript/JSX errors.

- [ ] **Step 5: Manual verification in a real browser**

Run: `cd dashboard && npm run dev`, then in a browser:
1. Navigate to `/m/settings`, confirm a "Personas" card is visible and links to `/m/personas`.
2. Navigate to `/m/personas` directly, confirm it loads a list of persona cards (jarvis, scout, rex, etc. — whatever exists in your dev DB), each showing its current model/temperature/max_tokens.
3. Change a persona's model via the dropdown, confirm the Save button becomes enabled (it should be disabled beforehand).
4. Click Save, confirm the button briefly dims/disables, then the new value persists after the page is reloaded.
5. Change a value, then use browser devtools to force the next request to fail (e.g. go offline momentarily) and click Save — confirm the inline "Couldn't save — try again" message appears and the field reverts to its last-saved value.

Record the outcome of this manual check in your report — this is the verification for a task with no unit-test convention in this codebase.

- [ ] **Step 6: Commit**

```bash
git add dashboard/components/persona-settings.tsx "dashboard/app/(mobile)/m/personas/page.tsx" "dashboard/app/(mobile)/m/settings/page.tsx"
git commit -m "feat: mobile persona model picker

Lets a persona's model/temperature/max_tokens be edited from
/m/personas, linked from the mobile settings hub."
```

---

### Task 4: Desktop UI

**Files:**
- Modify: `dashboard/app/settings/page.tsx`

**Interfaces:**
- Consumes: `usePersonas()`, `useUpdatePersona()`, `PersonaVM` (Task 2, `dashboard/lib/mobile-api.ts`); `MODEL_OPTIONS` (Task 2, `dashboard/lib/model-options.ts`).
- Produces: nothing further downstream — this is the last task in the plan.

The current file is a static server component (no `"use client"`, no hooks). Adding interactive persona editing requires converting it to a client component.

- [ ] **Step 1: Replace the file**

Replace the full contents of `dashboard/app/settings/page.tsx` (currently):

```tsx
export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Settings</h2>
        <p className="text-sm text-zinc-500">System configuration</p>
      </div>
      <div className="bg-white border border-zinc-200 rounded-xl p-6 space-y-5">
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">API Endpoint</label>
          <p className="text-sm text-zinc-800 mt-1 font-mono bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100">
            {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Tenant ID</label>
          <p className="text-sm text-zinc-800 mt-1 font-mono bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100">
            {process.env.NEXT_PUBLIC_TENANT_ID || "default"}
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Version</label>
          <p className="text-sm text-zinc-800 mt-1">Life Graph Dashboard v0.1.0</p>
        </div>
      </div>
    </div>
  );
}
```

with:

```tsx
"use client";
import { useState } from "react";
import { usePersonas, useUpdatePersona, type PersonaVM } from "@/lib/mobile-api";
import { MODEL_OPTIONS } from "@/lib/model-options";

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Settings</h2>
        <p className="text-sm text-zinc-500">System configuration</p>
      </div>
      <div className="bg-white border border-zinc-200 rounded-xl p-6 space-y-5">
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">API Endpoint</label>
          <p className="text-sm text-zinc-800 mt-1 font-mono bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100">
            {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Tenant ID</label>
          <p className="text-sm text-zinc-800 mt-1 font-mono bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100">
            {process.env.NEXT_PUBLIC_TENANT_ID || "default"}
          </p>
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Version</label>
          <p className="text-sm text-zinc-800 mt-1">Life Graph Dashboard v0.1.0</p>
        </div>
      </div>
      <PersonaSettings />
    </div>
  );
}

function PersonaSettings() {
  const personas = usePersonas();
  const rows = personas.data ?? [];

  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-zinc-900">Personas</h3>
        <p className="text-xs text-zinc-500">Model, temperature &amp; max tokens per persona</p>
      </div>
      {personas.isLoading && <p className="text-sm text-zinc-500">Loading personas…</p>}
      {personas.isError && (
        <p className="text-sm text-red-600">Can&rsquo;t reach personas — is the backend running?</p>
      )}
      {!personas.isLoading && !personas.isError && rows.length === 0 && (
        <p className="text-sm text-zinc-500">No personas configured yet.</p>
      )}
      <div className="space-y-3">
        {rows.map((p) => (
          <PersonaCard key={p.id} persona={p} />
        ))}
      </div>
    </div>
  );
}

function PersonaCard({ persona }: { persona: PersonaVM }) {
  const update = useUpdatePersona();
  const busy = update.isPending;

  const [model, setModel] = useState(persona.model);
  const [temperature, setTemperature] = useState(persona.temperature);
  const [maxTokens, setMaxTokens] = useState(persona.maxTokens);

  const dirty =
    model !== persona.model || temperature !== persona.temperature || maxTokens !== persona.maxTokens;

  function revert() {
    setModel(persona.model);
    setTemperature(persona.temperature);
    setMaxTokens(persona.maxTokens);
  }

  function save() {
    const body: Record<string, unknown> = {};
    if (model !== persona.model) body.model = model;
    if (temperature !== persona.temperature) body.temperature = temperature;
    if (maxTokens !== persona.maxTokens) body.max_tokens = maxTokens;
    update.mutate({ id: persona.id, body }, { onError: () => revert() });
  }

  const knownModels = [...MODEL_OPTIONS.Free, ...MODEL_OPTIONS.Paid];
  const isUnknownModel = Boolean(persona.model) && !knownModels.includes(persona.model);

  return (
    <div
      className="border border-zinc-100 rounded-lg p-4 space-y-3"
      style={{ opacity: busy ? 0.7 : 1 }}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-zinc-900">{persona.displayName ?? persona.name}</span>
        {persona.isBuiltin && (
          <span className="text-xs text-zinc-500 border border-zinc-200 rounded-full px-2 py-0.5">
            Built-in
          </span>
        )}
      </div>

      <div>
        <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Model</label>
        <select
          value={model}
          disabled={busy}
          onChange={(e) => setModel(e.target.value)}
          className="w-full mt-1 text-sm text-zinc-800 bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100"
        >
          {isUnknownModel && <option value={persona.model}>{persona.model}</option>}
          <optgroup label="Free">
            {MODEL_OPTIONS.Free.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </optgroup>
          <optgroup label="Paid">
            {MODEL_OPTIONS.Paid.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </optgroup>
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Temperature</label>
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            disabled={busy}
            onChange={(e) => setTemperature(Number(e.target.value))}
            className="w-full mt-1 text-sm text-zinc-800 bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Max tokens</label>
          <input
            type="number"
            min={1}
            max={128000}
            value={maxTokens}
            disabled={busy}
            onChange={(e) => setMaxTokens(Number(e.target.value))}
            className="w-full mt-1 text-sm text-zinc-800 bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100"
          />
        </div>
      </div>

      {update.isError && <p className="text-xs text-red-600">Couldn&rsquo;t save — try again</p>}

      <button
        type="button"
        disabled={!dirty || busy}
        onClick={save}
        className={
          dirty && !busy
            ? "w-full py-2 text-sm font-semibold rounded-lg bg-blue-600 text-white cursor-pointer"
            : "w-full py-2 text-sm font-semibold rounded-lg bg-zinc-100 text-zinc-400 cursor-default"
        }
      >
        Save
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify it builds**

Run: `cd dashboard && npm run build`
Expected: build succeeds with no TypeScript/JSX errors.

- [ ] **Step 3: Manual verification in a real browser**

Run: `cd dashboard && npm run dev`, then in a browser:
1. Navigate to `/settings` (desktop), confirm the existing API Endpoint/Tenant ID/Version card still renders unchanged, and a new "Personas" card appears below it with the same persona list as `/m/personas`.
2. Repeat the same change/save/reload/failure checks from Task 3 Step 5, on the desktop page this time.
3. Confirm editing a persona on `/settings` and then reloading `/m/personas` (or vice versa) shows the updated value — both pages read the same backend data.

Record the outcome in your report.

- [ ] **Step 4: Commit**

```bash
git add dashboard/app/settings/page.tsx
git commit -m "feat: desktop persona model picker

Adds the same model/temperature/max_tokens editing to /settings,
sharing usePersonas/useUpdatePersona with the mobile picker."
```
