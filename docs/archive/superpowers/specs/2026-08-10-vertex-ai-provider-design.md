# Vertex AI as a second LLM provider (Gemini-only)

> **Date:** 2026-08-10
> **Status:** Approved design — ready for implementation planning
> **Scope:** `config.py` (three new settings), a credential-bridging branch in
> `services/resilient_llm.py`, catalog entries in `services/model_catalog.py` and
> `dashboard/lib/model-options.ts`. No new abstraction layer, no changes to any existing default.
> **Deferred:** Claude via Vertex Model Garden (purchased on the work project but blocked on a
> quota increase — see Non-goals).

## Problem

Life Graph currently calls Gemini through Google AI Studio's direct API (model strings like
`gemini/gemini-3.6-flash`, billed to a personal API key via ambient `GEMINI_API_KEY`). A separate,
work-owned GCP project (`work-update-467706`) has Vertex AI enabled and its own billing/credits.
The user wants the option to route Gemini calls through that project's Vertex AI API instead of —
or alongside — the personal direct-API key, without disturbing anything that works today.

## Decisions (locked with user)

- **Additive only.** No existing default (`llm_model_expensive`, `agent_llm_model`, persona seed
  defaults, `llm_fallback_chain`) changes. Vertex becomes an available `vertex_ai/gemini-...`
  model id that any persona or `advisor_models`/`llm_fallback_chain` entry can opt into manually.
- **No new provider abstraction.** Every LLM call already funnels through one choke point —
  `ResilientLLM.acompletion()` in `services/resilient_llm.py`, which calls
  `litellm.acompletion(model=..., **kwargs)` (see `docs/superpowers/specs/2026-07-31-llm-resilience-design.md`).
  LiteLLM natively parses the `vertex_ai/<model>` prefix, so this is a credential-bridging +
  config change, following the same idiom already used for OpenRouter.
- **Credentials via file path, not embedded JSON content.** The service-account key already lives
  in the repo at `ext-assets/work-update-467706-fd81a28237dc.json` (now git-ignored — was
  previously untracked with no `.gitignore` rule, fixed as part of this work). Config points at
  that path rather than embedding the key content in an env var, unlike the existing
  `google_credentials_json` (Gmail/Calendar OAuth) pattern.
- **`global` Vertex location, not a specific region.** Verified live against the real project: the
  `global` endpoint serves every Gemini model Life Graph's defaults already reference
  (`gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-2.5-pro`,
  `gemini-2.5-flash`, `gemini-2.5-flash-lite`). One location, no per-model region table.
- **Vertex-purchased Claude models are out of scope for this pass.** `claude-sonnet-5` and
  `claude-opus-5` are subscribed on the work project (confirmed live — the API moved from a
  403/access-request response to a 429 quota-exceeded response), but their default quota is 0
  requests/tokens-per-minute until a quota increase is requested in the Cloud Console. That's a
  capacity/spend commitment on a work-owned project the user needs to request themselves; not
  something to script here. Wiring Claude in is the same pattern as Gemini (catalog entries +
  advisor cost entries) once quota clears — a small fast-follow, not a new design.

## Non-goals (this pass)

- No Claude-via-Vertex wiring (blocked on the user's quota-increase request; see above).
- No change to which model any persona/tier defaults to.
- No automated transfer of the service-account key to the production VM — `ext-assets/` is now
  git-ignored, so normal `git pull` deploys won't carry it. Getting the key onto the VM (if/when
  Vertex calls need to work in production, not just locally) is a manual step for the user.
- No per-tenant Vertex config — this is global infrastructure config, same tier as the existing
  OpenRouter/Gemini settings.
- No quota-increase automation, no Marketplace/procurement API calls — confirmed those aren't
  scriptable via the service account we have (no `cloudcommerceconsumerprocurement.googleapis.com`
  / `cloudpartnerservices.googleapis.com` enabled; the access-request flow is a console
  questionnaire, not a plain API call).

## Architecture

```
persona.model / advisor_models / llm_fallback_chain entry = "vertex_ai/gemini-2.5-flash"
        │
        ▼
ResilientLLM.acompletion(model="vertex_ai/gemini-2.5-flash", messages=…)   [services/resilient_llm.py]
        │  (unchanged — same chain/cooldown/health logic as every other model)
        ▼
_bridge_provider_credentials()   — NEW branch, same idiom as the existing OpenRouter bridge:
   if settings.vertex_credentials_path and "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
       os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path(vertex_credentials_path).resolve())
   if settings.vertex_project and "VERTEXAI_PROJECT" not in os.environ:
       os.environ["VERTEXAI_PROJECT"] = settings.vertex_project
   if settings.vertex_location and "VERTEXAI_LOCATION" not in os.environ:
       os.environ["VERTEXAI_LOCATION"] = settings.vertex_location
        │
        ▼
litellm.acompletion(model="vertex_ai/gemini-2.5-flash", …)   — LiteLLM's own Vertex SDK path,
                                                                 unchanged, lazy-imports google-auth
```

No new call sites, no new client class. The six models tested live and confirmed working through
this exact path (`global` location, this project's service account) are the only ones the catalog
will list initially.

## Components

### 1. Config (`life_graph/config.py`)

Add alongside the existing OpenRouter block (near line 113-117):

- `vertex_project: str = "work-update-467706"`
- `vertex_location: str = "global"`
- `vertex_credentials_path: str = ""` — relative or absolute path to the service-account key;
  empty by default so nothing breaks for anyone without the file. `LIFE_GRAPH_`-prefixed env var
  override, consistent with every other setting.

### 2. Credential bridging (`services/resilient_llm.py::_bridge_provider_credentials()`)

Extend the existing function with a Vertex branch (see Architecture diagram above). Follows the
established rule: only set an env var when the setting has a value **and** the env var isn't
already present, so an operator's own ambient env always wins. Path is resolved to absolute before
being assigned to `GOOGLE_APPLICATION_CREDENTIALS`, since the process's working directory isn't
guaranteed to be the repo root.

### 3. Catalog (`services/model_catalog.py`, `dashboard/lib/model-options.ts`)

Append six `vertex_ai/gemini-*` entries to the existing hardcoded fallback list (the same list
that already carries direct-API Gemini entries, because — like Vertex's — they don't appear in
OpenRouter's live-fetched catalog):

`vertex_ai/gemini-3.6-flash`, `vertex_ai/gemini-3.5-flash`, `vertex_ai/gemini-3.5-flash-lite`,
`vertex_ai/gemini-2.5-pro`, `vertex_ai/gemini-2.5-flash`, `vertex_ai/gemini-2.5-flash-lite`.

This makes them selectable in the persona model picker and usable in `advisor_models`/
`llm_fallback_chain`, without adding a generic "provider" concept the rest of the catalog code
doesn't have.

### 4. `.gitignore`

Already patched (ahead of this doc, since it was a live secret-exposure risk found mid-design):
`ext-assets/`, `*.json.key`, `service-account*.json` added.

## Failure handling

| Case | Behaviour |
|---|---|
| `vertex_credentials_path` unset but a `vertex_ai/...` model is requested | LiteLLM/google-auth fails to find credentials; the failure flows through `ResilientLLM`'s existing classify/cooldown/fallback machinery exactly like any other provider error — no special-casing |
| Key file present but project/location wrong | Vertex API call errors (404/403 depending on cause); same generic `ResilientLLM` failure handling |
| Operator has their own `GOOGLE_APPLICATION_CREDENTIALS`/`VERTEXAI_PROJECT` already set in the environment | Bridging skips those vars — ambient env wins, same as the OpenRouter bridge today |
| A persona/advisor/fallback-chain entry references `vertex_ai/claude-*` | Out of scope for this pass — will 429 (quota) until the user requests a quota increase; not handled specially, just not shipped in the catalog yet |

## Verification

1. **Unit** (`tests/unit`, extending `test_resilient_llm.py`'s existing coverage style):
   - `vertex_credentials_path` set, no ambient `GOOGLE_APPLICATION_CREDENTIALS` → env var gets set
     to the resolved absolute path; `VERTEXAI_PROJECT`/`VERTEXAI_LOCATION` set from settings.
   - Ambient env vars already present → bridging leaves them untouched.
   - `vertex_credentials_path` empty (default) → no Vertex env vars set, no behavior change for
     existing callers.
2. **Manual live check (already performed during design, not part of CI):** confirmed via direct
   REST calls with the service-account token that all six listed Gemini models return real
   `candidates` content through the `global` Vertex endpoint on `work-update-467706`. No live
   Vertex call is added to the automated test suite, consistent with the project's no-network unit
   test convention.
3. **Post-implementation manual check:** run one real persona/advisor call configured with a
   `vertex_ai/gemini-2.5-flash` model locally (key file already present in `ext-assets/`) and
   confirm a normal response — the equivalent of the design-time curl check, exercised through the
   actual code path instead of raw REST.
