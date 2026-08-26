# Vertex AI Provider (Gemini-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Gemini models callable through the work GCP project's Vertex AI API (`vertex_ai/gemini-*` model ids) as an additional, opt-in option alongside the existing OpenRouter/direct-Gemini setup — no existing default changes.

**Architecture:** Every LLM call already funnels through one choke point, `ResilientLLM.acompletion()` → `litellm.acompletion()` in `life_graph/services/resilient_llm.py`. LiteLLM natively parses a `vertex_ai/<model>` id. This plan adds: (1) three config settings, (2) a credential-bridging branch that sets the env vars `GOOGLE_APPLICATION_CREDENTIALS`/`VERTEXAI_PROJECT`/`VERTEXAI_LOCATION` from those settings, and (3) catalog entries so the six verified Gemini-via-Vertex models are selectable in personas/advisor/fallback-chain config. No new client class, no new call sites.

**Tech Stack:** Python 3.11+, FastAPI, LiteLLM, pydantic-settings, pytest + pytest-asyncio (backend); Next.js/TypeScript (dashboard, one static data file only).

## Global Constraints

- No existing default changes: `llm_model_expensive`, `agent_llm_model`, persona seed defaults, `llm_fallback_chain` stay exactly as they are today.
- `vertex_credentials_path` defaults to `""` — nothing about Vertex activates unless an operator sets it.
- Follow the existing `_bridge_provider_credentials()` idiom exactly: only set an env var when the setting has a value **and** the env var isn't already present (an operator's own ambient env always wins).
- `vertex_location` is `"global"` — verified live against `work-update-467706` to serve every Gemini model referenced below. No per-model region table.
- No live network call in the automated test suite (project convention — unit tests must not require network/DB).
- No new top-level dependency: confirmed `litellm.llms.vertex_ai.vertex_llm_base` imports cleanly with only `google-auth` present (already a transitive dependency); `google-cloud-aiplatform` is not required.
- Claude-via-Vertex is explicitly out of scope for this plan (see the spec's Non-goals) — do not add `vertex_ai/claude-*` anywhere in this work.

---

### Task 1: Vertex AI config settings

**Files:**
- Modify: `life_graph/config.py:117` (end of the OpenRouter block, before the blank line at 118)
- Modify: `.env.example:11` (end of the "LLM (via LiteLLM)" block, before the blank line at 12)
- Modify: `tests/unit/test_config_model_defaults.py` (append after line 21)

**Interfaces:**
- Produces: `settings.vertex_project: str` (default `"work-update-467706"`), `settings.vertex_location: str` (default `"global"`), `settings.vertex_credentials_path: str` (default `""`) — consumed by Task 2's credential bridging.

- [ ] **Step 1: Add the three settings to `config.py`**

In `life_graph/config.py`, immediately after the existing OpenRouter block (line 117, `use_hybrid_llm: bool = False`) and before the blank line that precedes the `# ── Personal AI: Advisor ──` comment (line 118-119), insert:

```python

    # ── Vertex AI (cloud inference — Gemini via a separate GCP project's
    # billing/quota; additive only, does not replace the OpenRouter/direct-
    # Gemini settings above) ──
    vertex_project: str = "work-update-467706"
    vertex_location: str = "global"
    vertex_credentials_path: str = ""  # Set LIFE_GRAPH_VERTEX_CREDENTIALS_PATH
```

- [ ] **Step 2: Document the new env vars in `.env.example`**

In `.env.example`, immediately after line 11 (`LIFE_GRAPH_LLM_DAILY_BUDGET_USD=1.0`) and before the blank line at 12, insert:

```bash

# Vertex AI (Gemini via a separate GCP project's billing/quota; additive —
# leave LIFE_GRAPH_VERTEX_CREDENTIALS_PATH empty to leave it fully inactive)
LIFE_GRAPH_VERTEX_PROJECT=work-update-467706
LIFE_GRAPH_VERTEX_LOCATION=global
LIFE_GRAPH_VERTEX_CREDENTIALS_PATH=
```

- [ ] **Step 3: Write the failing tests**

Append to `tests/unit/test_config_model_defaults.py` (after the existing `test_orchestrator_fallback_model_class_default_is_current` at line 21):

```python


def test_vertex_project_default_is_work_project():
    assert Settings().vertex_project == "work-update-467706"


def test_vertex_location_default_is_global():
    assert Settings().vertex_location == "global"


def test_vertex_credentials_path_defaults_empty():
    assert Settings().vertex_credentials_path == ""
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_config_model_defaults.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'vertex_project'` (and similarly for the other two) — the fields don't exist yet.

- [ ] **Step 5: Verify Step 1 makes them pass**

Run: `python -m pytest tests/unit/test_config_model_defaults.py -v`
Expected: PASS — 6 passed (the 3 existing + 3 new).

- [ ] **Step 6: Commit**

```bash
git add life_graph/config.py .env.example tests/unit/test_config_model_defaults.py
git commit -m "feat: add Vertex AI config settings (project, location, credentials path)"
```

---

### Task 2: Credential bridging in `ResilientLLM`

**Files:**
- Modify: `life_graph/services/resilient_llm.py:14` (imports), `life_graph/services/resilient_llm.py:33-50` (`_bridge_provider_credentials`)
- Modify: `tests/unit/test_resilient_llm.py` (append after line 184)

**Interfaces:**
- Consumes: `settings.vertex_project`, `settings.vertex_location`, `settings.vertex_credentials_path` (Task 1).
- Produces: when `_bridge_provider_credentials()` runs (on every `ResilientLLM()` construction, per the existing `__init__` at line 80), the env vars `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION` are populated for LiteLLM's Vertex handler to read — no other function signature changes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_resilient_llm.py`, immediately after the existing `test_bridge_noop_when_settings_empty` (ends at line 184) and before the streaming tests section (starts at line 188):

```python


def test_bridge_sets_vertex_env_from_settings_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("VERTEXAI_PROJECT", raising=False)
    monkeypatch.delenv("VERTEXAI_LOCATION", raising=False)
    key_file = tmp_path / "sa.json"
    key_file.write_text("{}")
    monkeypatch.setattr(rl.settings, "vertex_credentials_path", str(key_file), raising=False)
    monkeypatch.setattr(rl.settings, "vertex_project", "work-update-467706", raising=False)
    monkeypatch.setattr(rl.settings, "vertex_location", "global", raising=False)

    rl._bridge_provider_credentials()

    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(key_file.resolve())
    assert os.environ["VERTEXAI_PROJECT"] == "work-update-467706"
    assert os.environ["VERTEXAI_LOCATION"] == "global"


def test_bridge_does_not_overwrite_existing_vertex_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/pre-existing/key.json")
    monkeypatch.setenv("VERTEXAI_PROJECT", "pre-existing-project")
    monkeypatch.setenv("VERTEXAI_LOCATION", "us-central1")
    key_file = tmp_path / "sa.json"
    key_file.write_text("{}")
    monkeypatch.setattr(rl.settings, "vertex_credentials_path", str(key_file), raising=False)
    monkeypatch.setattr(rl.settings, "vertex_project", "should-not-win", raising=False)
    monkeypatch.setattr(rl.settings, "vertex_location", "should-not-win", raising=False)

    rl._bridge_provider_credentials()

    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == "/pre-existing/key.json"
    assert os.environ["VERTEXAI_PROJECT"] == "pre-existing-project"
    assert os.environ["VERTEXAI_LOCATION"] == "us-central1"


def test_bridge_credentials_env_noop_when_path_empty(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr(rl.settings, "vertex_credentials_path", "", raising=False)

    rl._bridge_provider_credentials()

    assert "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_resilient_llm.py -k vertex -v`
Expected: FAIL — `AttributeError` (settings has no `vertex_credentials_path` if Task 1 wasn't run first — it should be) or, if Task 1 is done, the assertions fail because `_bridge_provider_credentials()` doesn't set the Vertex env vars yet.

- [ ] **Step 3: Add the `Path` import**

In `life_graph/services/resilient_llm.py`, change line 14 from:

```python
import os
import time
```

to:

```python
import os
import time
from pathlib import Path
```

- [ ] **Step 4: Extend `_bridge_provider_credentials()`**

In `life_graph/services/resilient_llm.py`, replace the function at lines 33-50:

```python
def _bridge_provider_credentials() -> None:
    """Export LIFE_GRAPH_-configured provider creds to the env var names LiteLLM
    expects, so every provider in the fallback chain authenticates.

    Per-provider only — never forward one provider's credentials to another's
    attempt. Idempotent: only sets a var when settings has a value AND the env
    var isn't already set, so repeated construction (e.g. via the `lru_cache`d
    `get_resilient_llm()`) is harmless and an operator's own env wins.

    Gemini is intentionally left untouched: it already resolves via ambient
    `GEMINI_API_KEY` pre-branch (extraction called it with no explicit key), so
    only OpenRouter — previously passed explicitly by `LMStudioClient._cloud_chat`
    — needs bridging now that synthesis routes through this wrapper.
    """
    if settings.openrouter_api_key and not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    if settings.openrouter_url and not os.environ.get("OPENROUTER_API_BASE"):
        os.environ["OPENROUTER_API_BASE"] = settings.openrouter_url
```

with:

```python
def _bridge_provider_credentials() -> None:
    """Export LIFE_GRAPH_-configured provider creds to the env var names LiteLLM
    expects, so every provider in the fallback chain authenticates.

    Per-provider only — never forward one provider's credentials to another's
    attempt. Idempotent: only sets a var when settings has a value AND the env
    var isn't already set, so repeated construction (e.g. via the `lru_cache`d
    `get_resilient_llm()`) is harmless and an operator's own env wins.

    Gemini's direct API key is intentionally left untouched here: it already
    resolves via ambient `GEMINI_API_KEY` pre-branch. Vertex AI is a separate
    Gemini access path — billed to a different GCP project via a service
    account — so it needs its own credentials bridged, same as OpenRouter.
    """
    if settings.openrouter_api_key and not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    if settings.openrouter_url and not os.environ.get("OPENROUTER_API_BASE"):
        os.environ["OPENROUTER_API_BASE"] = settings.openrouter_url

    if settings.vertex_credentials_path and not os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    ):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
            Path(settings.vertex_credentials_path).resolve()
        )
    if settings.vertex_project and not os.environ.get("VERTEXAI_PROJECT"):
        os.environ["VERTEXAI_PROJECT"] = settings.vertex_project
    if settings.vertex_location and not os.environ.get("VERTEXAI_LOCATION"):
        os.environ["VERTEXAI_LOCATION"] = settings.vertex_location
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_resilient_llm.py -v`
Expected: PASS — every test in the file, including the 3 new ones (the full file, not just `-k vertex`, to confirm nothing else broke).

- [ ] **Step 6: Commit**

```bash
git add life_graph/services/resilient_llm.py tests/unit/test_resilient_llm.py
git commit -m "feat: bridge Vertex AI credentials in ResilientLLM"
```

---

### Task 3: Backend catalog entries

**Files:**
- Modify: `life_graph/services/model_catalog.py:23-40` (`FALLBACK_MODELS`)
- Modify: `tests/unit/test_model_catalog.py` (append after line 272)

**Interfaces:**
- Consumes: nothing new — `get_model_catalog()`'s existing carryover logic at `model_catalog.py:91` (`models += [m for m in FALLBACK_MODELS if not m["id"].startswith("openrouter/")]`) already includes any non-OpenRouter entry unconditionally.
- Produces: six new `{"id": "vertex_ai/gemini-...", "name": ..., "is_free": False}` entries in `FALLBACK_MODELS`, surfaced through `get_model_catalog()` on both the success and failure paths.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_model_catalog.py` (after the existing `test_claude_cli_entry_always_present_on_success` at line 271):

```python


@pytest.mark.asyncio
async def test_vertex_gemini_entries_always_present_on_success():
    _FakeAsyncClient.body = {"data": []}

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "vertex_ai/gemini-3.6-flash" in ids
    assert "vertex_ai/gemini-2.5-flash" in ids


@pytest.mark.asyncio
async def test_vertex_gemini_entries_present_on_total_failure():
    _FakeAsyncClient.raise_on_get = True

    models = await model_catalog.get_model_catalog()

    ids = {m["id"] for m in models}
    assert "vertex_ai/gemini-3.6-flash" in ids
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/unit/test_model_catalog.py -k vertex -v`
Expected: FAIL — `assert "vertex_ai/gemini-3.6-flash" in ids` fails (the id isn't in `FALLBACK_MODELS` yet).

- [ ] **Step 3: Add the six Vertex entries to `FALLBACK_MODELS`**

In `life_graph/services/model_catalog.py`, replace the closing of the `FALLBACK_MODELS` list at lines 35-40:

```python
    {
        "id": "claude-cli",
        "name": "Claude CLI (subscription, no tool-calling)",
        "is_free": False,
    },
]
```

with:

```python
    {
        "id": "claude-cli",
        "name": "Claude CLI (subscription, no tool-calling)",
        "is_free": False,
    },
    {"id": "vertex_ai/gemini-3.6-flash", "name": "Gemini 3.6 Flash (Vertex AI)", "is_free": False},
    {"id": "vertex_ai/gemini-3.5-flash", "name": "Gemini 3.5 Flash (Vertex AI)", "is_free": False},
    {
        "id": "vertex_ai/gemini-3.5-flash-lite",
        "name": "Gemini 3.5 Flash Lite (Vertex AI)",
        "is_free": False,
    },
    {"id": "vertex_ai/gemini-2.5-pro", "name": "Gemini 2.5 Pro (Vertex AI)", "is_free": False},
    {"id": "vertex_ai/gemini-2.5-flash", "name": "Gemini 2.5 Flash (Vertex AI)", "is_free": False},
    {
        "id": "vertex_ai/gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash Lite (Vertex AI)",
        "is_free": False,
    },
]
```

(All six model ids match exactly what was verified live against `work-update-467706`'s `global` Vertex endpoint during design — do not add or rename any.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/unit/test_model_catalog.py -v`
Expected: PASS — every test in the file (25 total: 23 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add life_graph/services/model_catalog.py tests/unit/test_model_catalog.py
git commit -m "feat: add Vertex AI Gemini entries to the backend model catalog"
```

---

### Task 4: Dashboard model picker entries

**Files:**
- Modify: `dashboard/lib/model-options.ts:11-16` (`MODEL_OPTIONS.Paid`)

**Interfaces:**
- Consumes: nothing — this is a standalone static data file with no imports from Tasks 1-3.
- Produces: six new entries in `MODEL_OPTIONS.Paid`, consumed wherever the dashboard renders the persona model picker (out of scope to trace further — this file is documented as the single source dashboard components read from).

- [ ] **Step 1: Add the six Vertex entries to `MODEL_OPTIONS.Paid`**

In `dashboard/lib/model-options.ts`, replace lines 11-16:

```typescript
  Paid: [
    "gemini/gemini-3.6-flash",
    "gemini/gemini-3.5-flash-lite",
    "openrouter/deepseek/deepseek-chat",
    "claude-cli",
  ],
```

with:

```typescript
  Paid: [
    "gemini/gemini-3.6-flash",
    "gemini/gemini-3.5-flash-lite",
    "openrouter/deepseek/deepseek-chat",
    "claude-cli",
    "vertex_ai/gemini-3.6-flash",
    "vertex_ai/gemini-3.5-flash",
    "vertex_ai/gemini-3.5-flash-lite",
    "vertex_ai/gemini-2.5-pro",
    "vertex_ai/gemini-2.5-flash",
    "vertex_ai/gemini-2.5-flash-lite",
  ],
```

- [ ] **Step 2: Lint the dashboard to catch any syntax error**

Run: `cd dashboard && npm run lint`
Expected: no new errors attributable to `model-options.ts` (pre-existing unrelated lint warnings elsewhere, if any, are not this task's concern).

- [ ] **Step 3: Commit**

```bash
git add dashboard/lib/model-options.ts
git commit -m "feat: add Vertex AI Gemini entries to the dashboard model picker"
```

---

### Task 5: Manual end-to-end verification (not part of the automated suite)

**Files:** none committed — this task runs existing code with real local credentials to confirm the full path works, matching the spec's "Post-implementation manual check."

**Interfaces:**
- Consumes: `ResilientLLM.acompletion(*, messages: list[dict], model: str | None = None, tier: str = "cheap", **kwargs) -> Any` (existing signature, `resilient_llm.py:129-131`, unchanged by this plan) and Tasks 1-4's config/bridging/catalog changes.

- [ ] **Step 1: Confirm the service-account key is present locally**

Run: `python -c "import pathlib; print(pathlib.Path('ext-assets/work-update-467706-fd81a28237dc.json').exists())"`
Expected: `True` (it was placed there before this plan was written; this step only confirms it's still there).

- [ ] **Step 2: Run a real Vertex call through `ResilientLLM`**

Run this from the repo root, with the venv active:

```bash
LIFE_GRAPH_VERTEX_CREDENTIALS_PATH=ext-assets/work-update-467706-fd81a28237dc.json python -c "
import asyncio
from life_graph.services.resilient_llm import ResilientLLM

async def main():
    llm = ResilientLLM()
    resp = await llm.acompletion(
        messages=[{'role': 'user', 'content': 'Reply with exactly: OK'}],
        model='vertex_ai/gemini-2.5-flash',
    )
    print(resp.choices[0].message.content)

asyncio.run(main())
"
```

(PowerShell equivalent: `$env:LIFE_GRAPH_VERTEX_CREDENTIALS_PATH="ext-assets/work-update-467706-fd81a28237dc.json"; python -c "..."` with the same script body.)

Expected: prints `OK` (or a close variant — Gemini doesn't always follow "exactly" verbatim, but the call must **succeed**, not raise). This exercises the real code path — config loading, `_bridge_provider_credentials()`, and LiteLLM's Vertex handler — end to end, the same thing verified via raw `curl` during design, now through the actual application code.

- [ ] **Step 3: Confirm no regressions in the full unit suite**

Run: `python -m pytest tests/unit/ -v`
Expected: PASS — all unit tests green (no DB needed, per `conftest.py`'s pgvector mock).

No commit for this task — it's a verification pass, not a code change.

---

## Plan self-review notes

- **Spec coverage:** every "Components" section in the spec (config, credential bridging, catalog, `.gitignore`) maps to Tasks 1-4; the spec's "Verification" section (unit tests + manual live check) maps to the test steps within each task plus Task 5. The `.gitignore` fix from the spec was already committed ahead of this plan (commit `95d406c`), so it isn't repeated here.
- **Placeholder scan:** no TBD/TODO; every code block is complete, copy-pasteable content, not a description of what to write.
- **Type/signature consistency:** `ResilientLLM.acompletion(*, messages, model=None, tier="cheap", **kwargs)` in Task 5 matches the real signature read from `resilient_llm.py:129-131`, not a guessed one. `_bridge_provider_credentials()` keeps its existing no-argument, no-return signature throughout.
- **Non-goals honored:** no task touches `multi_model_advisor.py`'s `MODEL_COSTS`, adds `vertex_ai/claude-*` anywhere, or changes any existing default model string.
