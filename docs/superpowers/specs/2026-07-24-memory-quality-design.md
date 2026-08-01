# Memory Quality — clean, consolidated captures instead of noisy fragments

> **Date:** 2026-07-24
> **Status:** Approved design — ready for implementation planning
> **Scope:** `extraction/pipeline.py`, `extraction/nlp.py`, `extraction/rules.py`, `extraction/llm.py`,
> `core/memory_manager.py`, `config.py`, a new cleanup ARQ job, dashboard memory edit UI.
> Deployed at `brain.raceraja001.in`.
> **Roadmap:** memory-quality → notifications → reliability debt → reactive UI → distillation.
> **Depends on:** approval gate (merged) + background capture ingest (merged) + the chat branch's
> shared `MemorySheet` (the edit UI extends it).

## Problem

Captured memories are noisy, fragmented, and sometimes garbled. Observed live: "I like fastapi"
becomes **three** memories (`fastapi → my fav`, `Tech mention: fastapi`, `Entity (ORG): fastapi`);
Tamil text produces junk (`Entity (PERSON): பலன ல கவன்‌ வத`); and contradictory facts coexist
unnoticed (`my name → Riz Aljaf` **and** `My name → Raja`). When the user asked the new chat "what
is my name," it hedged — not because retrieval failed, but because the stored memories were fragments
and contradictions. **Fixing capture quality lifts chat, search, and browsing simultaneously.**

Root causes (from code investigation):
- **Fan-out:** `nlp.py` emits one memory *per entity* (`Entity (LABEL): x`) and *per tech term*
  (`Tech mention: x`); `rules.py`'s broad "X is Y" regex emits an `X → Y` fragment. One utterance →
  many rows.
- **No language guard:** `en_core_web_sm` runs unconditionally on all text, including Tamil → garbage.
- **Clean path bypassed:** the `llm.py` tier writes clean single-statement facts but only fires on
  long (≥20-word), low-confidence text, so short casual captures never reach it.
- **Weak dedup:** pipeline dedup is exact-string only; cross-tier fragments of one utterance survive.
- **No edit UI:** `PATCH /memories/{id}` works but the dashboard never exposes it.
- **Untunable:** tier thresholds are private constants in `pipeline.py`, not in `config.py`.

## Decisions (locked with user)

- **LLM-clean captures.** Route captures through the LLM extraction tier (free OpenRouter models,
  runs in the already-async background ingest) to produce a small set of clean, self-contained facts,
  with entities/tech as **tags/properties on the fact — never standalone memories**. Rules become the
  offline/LLM-unavailable fallback. This is a deliberate, capture-path-only relaxation of the
  "LLM as advisor, not authority" principle, justified by free models + background ingest.
- **Language guard.** Detect script before spaCy; non-Latin/mixed text skips English NER and goes to
  the LLM path.
- **One-time cleanup job.** An on-demand ARQ job re-runs existing memories through the new logic,
  consolidating fragments and dropping garbage; conflicts/dupes (e.g. the two names) are **queued as
  merge/keep decisions into the existing approvals queue**, not auto-resolved.
- **Edit-in-app.** Tap a memory → edit content/tags → `PATCH /memories/{id}`, mobile + desktop.
- Clean memories still land as `pending` (approval gate unchanged); cleanup merges also route through
  approvals — nothing is silently rewritten.

## Non-goals (v1)

- No embedding-model change; LLM-clean uses the free models already configured.
- No new real-time contradiction detector for identity facts — conflicts surface via the cleanup
  job's merge-approvals (and future captures that contradict are a later concern).
- No thread/branch history on edits (edit overwrites; no revision log).
- No bulk multi-select cleanup UI — the cleanup job is API/worker-triggered, results reviewed via the
  existing approvals feed + the new edit affordance.
- Rules tiers are not deleted (offline fallback) — only demoted/suppressed.

## Architecture

```
Capture ──→ background ARQ ingest (existing)
                 │
   ExtractionPipeline.extract(text)
                 │
     ┌───────────┴─────────────┐
   online + LLM ok            offline / LLM error
     ▼                          ▼
  LLM tier (llm.py)          rules + nlp (noise-suppressed):
  clean facts, 1..N           - language guard: non-Latin skips NER
  entities/tech → tags        - entity/tech → TAGS on one fact, not rows
                              - confidence floor drops weakest fragments
     └───────────┬─────────────┘
                 ▼
   dedup (exact hash + cosine ≥ threshold) → embed → store pending
```

## Components

### 1. LLM-first capture path (`extraction/pipeline.py`)

- Add settings (to `config.py`, replacing the private constants): `extraction_llm_for_capture: bool = True`,
  `extraction_min_confidence: float` (store-confidence floor), `extraction_llm_min_words: int`,
  `extraction_llm_confidence_threshold: float`.
- New capture path: when `extraction_llm_for_capture` and the LLM client is reachable, run the `llm.py`
  tier as the **primary** extractor for capture ingests (not just the ≥20-word/low-confidence gate).
  Its clean facts are used directly. Rules/nlp run only as fallback when the LLM path returns nothing
  or errors. The existing 3-tier behavior remains available for non-capture callers / offline.
- The pipeline signature/entry may need a `mode`/`prefer_llm` flag so `MemoryManager.ingest` (capture)
  opts in while other callers keep current behavior. (Plan resolves the exact wiring.)

### 2. Language guard (`extraction/nlp.py`)

- Before `nlp(text)`, a cheap script check: if the text is predominantly non-Latin (e.g. >~30% of
  letters outside Basic Latin), skip entity/tech extraction entirely and return no nlp facts (the LLM
  path handles it). Pure-ASCII/Latin text is unaffected. No new heavy dependency — a Unicode
  block/codepoint ratio check suffices (langdetect optional, not required).

### 3. Noise-suppressed rules fallback (`extraction/nlp.py`, `rules.py`, `pipeline.py`)

- `_extract_entities` / `_extract_tech_mentions`: stop emitting standalone `ExtractedFact`s. Instead
  contribute their findings as **tags/properties** merged onto the primary fact(s) for that utterance.
  (If there is no primary fact — e.g. a bare entity list — emit at most ONE consolidated fact, not one
  per entity.)
- `pipeline._deduplicate` / store path: apply `extraction_min_confidence` as a floor — facts below it
  are dropped (the 0.55–0.60 entity/tech fragments go away).
- `rules.py` broad "X is Y" arrow pattern: keep for the offline path but gate behind the confidence
  floor and prefer the LLM's cleaner phrasing when both exist for the same utterance.

### 4. One-time cleanup job (`workers/` + a trigger endpoint)

- New ARQ job `cleanup_memories(ctx, tenant_id)`: iterate the tenant's active memories, group obvious
  same-utterance fragments (shared source/entities or high mutual cosine), and for each group either
  (a) consolidate into one clean memory (re-extract via the LLM path on the combined text) or (b) if
  two memories conflict/duplicate, create a `kind="merge"` (or a new `kind="cleanup"`) `Approval` row
  for the user to pick — reusing the existing approvals machinery (`services/merge_suggestions.py`
  patterns). Never silently deletes; consolidations produce a new pending memory + supersede the
  fragments on approval.
- Trigger: an admin/maintenance endpoint (`POST /admin/cleanup-memories` or reuse an existing admin
  route) that enqueues the job by its full dotted name (per the ARQ-registration gotcha). Idempotent —
  safe to run repeatedly.

### 5. Edit-in-app (dashboard)

- `dashboard/lib/api.ts`: `api.memories.update(id, {content?, tags?})` → `PATCH /memories/{id}`.
- Mobile: the shared `MemorySheet` (from the chat branch) gains an Edit mode — tap Edit → editable
  content textarea + tags → Save (PATCH) → invalidate `["memories"]`/`["memory-search"]`. Cancel
  reverts.
- Desktop: `components/memory-detail.tsx` gains the same edit affordance.
- Uzhavu tokens (mobile) / Tailwind zinc (desktop). Approval status is not editable here (the PATCH
  guard already blocks status changes).

## Failure handling

| Case | Behaviour |
|---|---|
| LLM unreachable at capture | Fall back to noise-suppressed rules/nlp; memory still stored (pending) |
| Non-Latin/Tamil text | Skips English NER (no garbage); LLM path produces clean facts; offline → stored raw as one fact |
| Cleanup finds a conflict (two names) | Queues a merge/keep Approval; user decides; nothing auto-deleted |
| Edit saves invalid/empty content | 422 from PATCH; inline error, memory unchanged |
| Cleanup job re-run | Idempotent — already-clean memories produce no new fragments/approvals |
| Edit a memory mid-approval | Content editable; status stays pending (PATCH guard unchanged) |

## Verification

1. Unit: "I like fastapi" through the LLM-capture path → ONE clean fact (e.g. "The user likes
   FastAPI"), entities/tech as tags, not 3 rows. Offline path → noise-suppressed rules (no
   `Entity (...)`/`Tech mention:` standalone rows, confidence floor applied). Language guard: Tamil
   input → no spaCy entities emitted. Config knobs honored.
2. Cleanup job unit: a set of fragment memories → consolidated result / merge-Approval created;
   idempotent on a clean set.
3. Live E2E: capture "I like fastapi and use Postgres" → one/few clean pending memories, no
   `Tech mention:`/`Entity (...)` rows; approve → chat "what do I use for databases?" answers cleanly.
   Capture Tanglish → clean memory, no garbled entities. Run cleanup job on the existing 26 → fragments
   consolidated, the two-names conflict appears as an approval. Edit a memory in the app → content
   updates. Ask "what is my name" after resolving → single clean answer.
