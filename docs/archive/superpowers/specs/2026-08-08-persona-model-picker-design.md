# Persona model picker — design

## Purpose

Let a persona's `model`, `temperature`, and `max_tokens` be edited from the
dashboard (mobile + desktop), so a dead/deprecated model id stuck on an
already-seeded persona row can be fixed with a tap instead of SSH access,
direct database surgery, and a redeploy.

Directly motivated by a real incident on 2026-08-08: Jarvis's persona row in
production has `model = "gemini/gemini-2.5-flash"` baked in from when it was
originally seeded (`life_graph/kernel/personas.py`'s built-in-persona seeder
hardcodes this literal, independent of `config.py`'s settings). Fixing the
seed default and backfilling the database gets today's specific case, but
doesn't give a way to fix the *next* deprecated model without another
manual intervention.

## Non-goals

- No persona create/delete UI — only editing the three fields on existing
  personas (built-in or custom).
- No editing of `system_prompt`, `allowed_tools`, `intent_tags`,
  `properties`, or any other persona field — model/temperature/max_tokens
  only.
- No confirmation dialog before selecting a paid model — the Free/Paid
  grouping in the picker is the only cost signal; no extra friction beyond
  that.
- No change to the global fallback chain (`config.py`'s
  `llm_fallback_chain`/`llm_model_cheap`/`llm_model_expensive`/
  `llm_paid_fallback_model`) — those stay `.env`-only, ops-level settings.
  This feature only changes a persona's *primary* model.
- No new backend CRUD beyond the one additive field-exposure change below —
  `PATCH /kernel/personas/{id}` already does everything else needed.

## Architecture

```
[Settings page: mobile /m/settings, desktop /settings]
  -> usePersonas()          GET  /kernel/personas   (list, now includes temperature/max_tokens)
  -> useUpdatePersona()     PATCH /kernel/personas/{id}   {model?, temperature?, max_tokens?}
       on success: invalidate ["personas"] query -> refetch -> card shows new values
       on error:   inline "Couldn't save — try again", inputs revert to last-known-good
```

One page per platform (`PersonaSettingsMobile` / `PersonaSettingsDesktop`),
each rendering a list of persona cards — no navigation, no modal, no
detail page. Both consume the same two hooks; the platforms differ only in
presentation (CSS-variable inline styles on mobile, Tailwind/zinc classes
on desktop), matching each platform's existing convention rather than
forcing one design system onto both.

## Backend: one additive change

`life_graph/api/kernel.py`'s `_persona_to_summary()` (lines 388-401)
currently omits `temperature` and `max_tokens` from the list response —
`GET /kernel/personas` only returns the narrow summary shape today. Since
this feature renders every persona as an independently-editable card in one
list (no per-persona detail fetch), the list response needs both fields
up front. Both are already stored on `AgentPersona` and already returned by
`_persona_to_dict()` (used by the single-persona `GET`/`PATCH` routes) — this
is purely adding two keys to an existing dict literal, not a schema or
validation change, and is backward-compatible (existing consumers of the
list endpoint gain two extra keys they can ignore).

`PATCH /kernel/personas/{id}` needs no changes — `PersonaUpdate` already
accepts `model: str | None`, `temperature: float | None = Field(None, ge=0.0,
le=2.0)`, and `max_tokens: int | None = Field(None, ge=1, le=128000)`, and
`PersonaService.update()`'s `allowed_fields` whitelist already includes all
three. Its response is narrow (`{id, name, updated_at, message}`, not the
full updated persona) — the frontend relies on query invalidation to pick
up the new values, not on the PATCH response body.

## Frontend

### Hooks — `dashboard/lib/mobile-api.ts`

Add `PersonaVM`, `mapPersona`, `usePersonas`, `useUpdatePersona`, following
the exact template already established by `AmbientJobVM`/`mapAmbientJob`/
`useAmbientSchedules`/`useUpdateAmbientSchedule` in the same file:

```typescript
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

function mapPersona(p: any): PersonaVM {
  return {
    id: p.id,
    name: p.name,
    displayName: p.display_name ?? null,
    icon: p.icon ?? null,
    model: p.model ?? "",
    temperature: typeof p.temperature === "number" ? p.temperature : 0.7,
    maxTokens: typeof p.max_tokens === "number" ? p.max_tokens : 4096,
    isBuiltin: Boolean(p.is_builtin),
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

### `dashboard/lib/api.ts`

Replace the stale `personas: () => GET<any[]>("/kernel/personas")` entry
(currently unused anywhere, and wrong about its own return shape — the real
response is `{data: {personas: [...], total}}`) with:

```typescript
personas: {
  list: () => GET<any>("/kernel/personas"),  // caller unwraps .data.personas
  update: (id: string, body: Record<string, unknown>) =>
    request<any>("PATCH", `/kernel/personas/${id}`, body),
},
```

### The curated model list — shared constant

A new small module, `dashboard/lib/model-options.ts`, exporting a single
grouped list both platform components import:

```typescript
export const MODEL_OPTIONS = {
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
} as const;
```

If a persona's current `model` value isn't in either list (e.g. an old
dead id, or something set outside the picker), the dropdown includes it as
a one-off extra option so the picker never silently misrepresents the
persona's actual current value — it just won't be grouped under Free/Paid.

### Mobile component — `dashboard/components/persona-settings.tsx`

Mirrors `ambient-roles.tsx`'s structure and idiom exactly: CSS-variable
inline styles, `cardStyle` shell, `busyId`-driven dimming
(`opacity: busy ? 0.7 : 1`) and `disabled` props during a pending mutation,
`LoadingCard`/`EmptyCard`/`ErrorCard` from `components/mobile/parts` for the
list-level states. Each persona card has:
- Display name + icon (read-only) + a small "Built-in" badge when
  `isBuiltin` (informational only — built-ins remain editable, since fixing
  a built-in persona's dead model is this feature's whole reason to exist).
- A `<select>` for `model`, `<optgroup>`s for Free/Paid.
- Two `<input type="number">`s for `temperature` (min 0, max 2, step 0.1)
  and `max_tokens` (min 1, max 128000).
- A Save button, enabled only when at least one field's local value differs
  from the card's last-known-good server value.
- On save failure: an inline red text line, "Couldn't save — try again",
  and all three fields reset to the last-known-good server value (not the
  failed attempt) so the card never shows a value that isn't actually
  persisted.

Wired into the app the same way `ambient-roles.tsx` is wired into
`app/(mobile)/m/schedules/page.tsx` — add a "Personas" section/card to
`app/(mobile)/m/settings/page.tsx` linking to a new
`app/(mobile)/m/personas/page.tsx` that's a one-line wrapper rendering
`<PersonaSettings />`.

### Desktop component — extend `dashboard/app/settings/page.tsx`

Same data (`usePersonas`/`useUpdatePersona`) and the same per-card
save/error/revert behavior, rendered with the page's existing Tailwind/zinc
conventions (`bg-white border border-zinc-200 rounded-xl`, `text-zinc-900`,
etc.) instead of CSS variables — added as a new section on the existing
page, below the current static "API Endpoint"/tenant info block, not a
new route.

## Error handling

| Failure | Behavior |
|---|---|
| `PATCH` returns 404 (persona deleted concurrently) | Inline error, same "Couldn't save — try again" message; a refetch (via the query invalidation that still fires) will drop the card from the list on next render if it's genuinely gone. |
| `PATCH` returns 422 (temperature/max_tokens out of range) | Same inline error message — the frontend's own `min`/`max`/`step` on the number inputs should make this rare, but the backend is the source of truth and the UI doesn't duplicate its exact validation logic. |
| Network failure / backend unreachable | Same inline error message (the generic `request()` helper's thrown `Error` covers this uniformly, same as every other mutation in the app). |
| Persona's current `model` isn't in the curated list | Shown as a selected one-off option (see above) rather than silently defaulting to blank or the first list entry — the picker must never misrepresent what's actually stored. |

## Testing

- Backend: one unit test asserting `GET /kernel/personas`'s response now
  includes `temperature`/`max_tokens` per persona (extend the existing
  persona API test file — mirrors the existing list/get/update test
  pattern already in that file).
- Frontend: this codebase's existing pattern doesn't unit-test individual
  dashboard components (no test files under `dashboard/components/` for
  `ambient-roles.tsx` or similar) — verification here is manual, in a real
  browser: load `/m/personas` and `/settings`, change a persona's model,
  save, confirm the change persists across a page reload, confirm a
  simulated failure (e.g. an invalid temperature via devtools) shows the
  inline error and reverts.

## Open items intentionally deferred

- A "test this model" button (send a throwaway prompt, show latency/success
  before committing) — real usability win, but a separate, larger feature.
- Surfacing `/api/v1/health/models`' live health data next to each model
  option in the dropdown (e.g. "currently cooling down") — would make the
  picker smarter, but ties it to the resilient-fallback work from earlier
  today in a way that adds real complexity; worth a follow-up once this
  simpler version is in use.
- Editing the global fallback chain from the dashboard — explicitly a
  non-goal above; still `.env`-only for now.
