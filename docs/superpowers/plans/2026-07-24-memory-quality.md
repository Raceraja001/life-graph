# Memory Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Captures produce one (or a few) clean, consolidated memories via the free LLM instead of many noisy fragments; non-Latin text no longer garbles; existing noise is cleanable; users can edit memories in-app.

**Architecture:** Make the LLM extraction tier the PRIMARY extractor on the capture path (free models, already-async background ingest), with the rules/nlp tiers as a noise-suppressed offline fallback. Add a language guard, promote extraction thresholds to `config.py`, add a one-time cleanup ARQ job that routes conflicts through the existing approvals queue, and expose the existing `PATCH /memories/{id}` in the UI.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async, ARQ, pgvector, Next.js 16 dashboard, pytest.

## Global Constraints

- Python: async everywhere, type hints + docstrings on public APIs, double quotes, ruff line-length 100.
- Tenant only from the contextvar (`get_current_tenant_id()`); every query/job tenant-scoped.
- LLM-clean is capture-path-only; non-capture callers keep current 3-tier behavior. Rules/nlp remain as the offline/LLM-unavailable fallback — never deleted.
- Clean memories still land as `pending` (approval gate unchanged). Cleanup consolidations/merges route through `Approval` rows — never silent-delete or silent-rewrite.
- ARQ: register jobs in `workers/settings.py` `functions` list by FULL dotted name; `pool.enqueue_job(...)` uses the BARE function name (arq resolves against the functions list). Mirror `/jobs/consolidate` in `api/admin.py`.
- Frontend: mobile inline styles + CSS vars (uzhavu); desktop Tailwind zinc idiom. No new npm deps.
- Commits end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Windows: ruff binary blocked — verify with `python -m py_compile` + pytest from the worktree ROOT (`python -m pytest tests/unit/ -v`; unit tests need no Postgres, conftest mocks pgvector). `dashboard/`: `npm run build` passes, lint adds zero new problems.
- Worktree: `<scratchpad>/hotfix-wt`, branch `feat/memory-quality` (spec committed; branch off the chat branch HEAD).
- Deploy target: GCP VM `deploy@34.14.194.65` (key `D:\DevTools\gcloud-config\lg_deploy`). Base64 remote bash. Build BOTH images (`build app worker`). After `--force-recreate` of app: `docker network connect web life_graph_app`. Remove stale containers with `docker stop`+`docker rm` (no `-f`).

## Key facts (from code investigation)

- `ExtractedFact` (`extraction/rules.py` or a shared module): fields `content: str`, `fact_type: str`, `confidence: float`, `entities: list[str] = []`, `source_text: str = ""`. No `tags`/`properties`.
- `ExtractionPipeline.extract(self, text) -> ExtractionResult` (`extraction/pipeline.py:89`); `ExtractionResult` = `facts, tier1_count, tier2_count, tier3_count, llm_invoked`. Tier-3 gate at pipeline.py:120 uses `self._confidence_threshold`/`self._min_words_for_llm` (ctor params, default module constants `_LLM_CONFIDENCE_THRESHOLD=0.5`/`_MIN_WORDS_FOR_LLM=20`).
- `LLMExtractor.extract(self, text) -> list[ExtractedFact]` (`extraction/llm.py:115`) — clean facts, sets content/fact_type/confidence/entities/source_text, NOT tags.
- `SpacyExtractor._extract_entities` (nlp.py:151 builds `f"Entity ({label}): {text}"`) and `_extract_tech_mentions` (nlp.py:197 builds `f"Tech mention: {term}"`) each append standalone facts. `_extract_relations` (nlp.py:210+) is the substantive one (keep).
- `MemoryManager.ingest(text, context, source, skip_dedup, trust_tier)` (memory_manager.py:68) calls `self._extractor.extract(text)` (:99); `_process_fact` maps fact→MemoryCreate at :290-297 with `tags=_infer_tags(fact, tier)`, `properties` incl. `fact_type`/`extraction_confidence`/`entities`.
- `config.py`: pydantic `Settings(BaseSettings)`, env prefix `LIFE_GRAPH_`; dedup knobs at lines 65-73.
- Merge Approval pattern: `merge_suggestions.py:83-100` (`Approval(tenant_id, kind="merge", source="curator", source_ref, title, detail, payload={memory_id_a, memory_id_b, similarity})`), idempotent via `source_ref` seen-set, `session.flush()` (caller commits). ARQ jobs `run_tenant_merge_suggestions`/`run_all_merge_suggestions` in `workers/tasks.py:157`, registered in `workers/settings.py` functions list.
- Admin enqueue: `api/admin.py:835` `/jobs/consolidate` (`create_pool(parse_redis_settings())` → `enqueue_job("run_tenant_consolidation", tid)` → `pool.close()`).
- Edit UI: `api.memories` block `api.ts:83-97` (no update method; add `update` via `request("PATCH", ...)`); `useResolveMemory` hook `mobile-api.ts:160` (mirror for `useUpdateMemory`); `memory-sheet.tsx` (mobile, content at :91) + `memory-detail.tsx` (desktop, content at :21). Backend `PATCH /memories/{id}` exists (`api/memories.py:210`).

---

### Task 1: Extraction config knobs

**Files:**
- Modify: `life_graph/config.py` (add a Capture Quality block near the dedup knobs)
- Modify: `life_graph/extraction/pipeline.py` (read the constants from settings)
- Test: `tests/unit/test_extraction_config.py` (new)

**Interfaces:**
- Produces settings: `capture_llm_clean: bool = True`, `extraction_language_guard: bool = True`, `extraction_tag_only_entities: bool = True`, `extraction_min_confidence: float = 0.45`, `extraction_llm_min_words: int = 20`, `extraction_llm_confidence_threshold: float = 0.5`. Tasks 2–4 read these.

- [ ] **Step 1: Failing test** `tests/unit/test_extraction_config.py`:

```python
"""Extraction quality knobs exist on Settings with sane defaults."""

from life_graph.config import settings


def test_capture_quality_settings_exist():
    assert isinstance(settings.capture_llm_clean, bool)
    assert isinstance(settings.extraction_language_guard, bool)
    assert isinstance(settings.extraction_tag_only_entities, bool)
    assert 0.0 <= settings.extraction_min_confidence <= 1.0
    assert settings.extraction_llm_min_words >= 1
    assert 0.0 <= settings.extraction_llm_confidence_threshold <= 1.0
```

- [ ] **Step 2: Run to verify failure** — `python -m pytest tests/unit/test_extraction_config.py -v` → FAIL (AttributeError).

- [ ] **Step 3: Add settings** in `config.py` after the dedup block (~line 73):

```python
    # ── Capture Quality ──────────────────────────────────────
    capture_llm_clean: bool = True  # LLM as primary extractor on the capture path
    extraction_language_guard: bool = True  # skip English NER on non-Latin text
    extraction_tag_only_entities: bool = True  # entities/tech become tags, not memories
    extraction_min_confidence: float = 0.45  # drop facts below this before storing
    extraction_llm_min_words: int = 20  # legacy 3-tier LLM gate (non-capture callers)
    extraction_llm_confidence_threshold: float = 0.5  # legacy 3-tier LLM gate
```

In `pipeline.py`, change the ctor defaults (lines ~73-87) to read from settings instead of the private module constants:

```python
        self._confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.extraction_llm_confidence_threshold
        )
        self._min_words_for_llm = (
            min_words_for_llm
            if min_words_for_llm is not None
            else settings.extraction_llm_min_words
        )
```

(Import `settings` in pipeline.py if not already; keep the module constants as fallback literals only if referenced elsewhere — otherwise remove.)

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_extraction_config.py tests/unit/ -v` → green. `python -m py_compile life_graph/config.py life_graph/extraction/pipeline.py`.

- [ ] **Step 5: Commit**

```bash
git add life_graph/config.py life_graph/extraction/pipeline.py tests/unit/test_extraction_config.py
git commit -m "feat(quality): promote extraction thresholds to config + capture-quality knobs"
```

---

### Task 2: LLM-primary capture path

**Files:**
- Modify: `life_graph/extraction/pipeline.py` (add a capture mode)
- Modify: `life_graph/core/memory_manager.py` (thread a capture flag into `ingest`/extract)
- Test: `tests/unit/test_pipeline_capture.py` (new)

**Interfaces:**
- Consumes: Task 1 settings; `LLMExtractor.extract`.
- Produces: `ExtractionPipeline.extract(self, text, *, capture: bool = False) -> ExtractionResult`. When `capture and settings.capture_llm_clean` and the LLM path yields facts, those clean facts are used as PRIMARY (rules/nlp only fill in if the LLM path returns empty or raises). `MemoryManager.ingest(..., capture: bool = False)` passes `capture=True` from capture callers; `_process_fact` unchanged. Task 5's cleanup reuses `capture=True`.

- [ ] **Step 1: Failing test** `tests/unit/test_pipeline_capture.py` — with a fake LLM extractor returning one clean fact and fakes for rules/nlp returning noisy facts, assert that `extract(text, capture=True)` returns the LLM fact and NOT the noisy `Entity (...)`/`Tech mention:` facts; and that on LLM failure it falls back to rules/nlp. Full test:

```python
"""Capture mode uses the LLM as primary extractor; rules/nlp are fallback."""

import pytest

from life_graph.extraction.pipeline import ExtractionPipeline
from life_graph.extraction.rules import ExtractedFact


class _Rules:
    def extract(self, text):
        return [ExtractedFact(content="fastapi → my fav", fact_type="fact", confidence=0.6)]


class _Spacy:
    def extract(self, text):
        return [ExtractedFact(content="Tech mention: fastapi", fact_type="fact", confidence=0.6)]


class _LLMok:
    async def extract(self, text):
        return [ExtractedFact(content="The user likes FastAPI", fact_type="preference",
                              confidence=0.9, entities=["FastAPI"])]


class _LLMdown:
    async def extract(self, text):
        raise RuntimeError("llm down")


@pytest.mark.asyncio
async def test_capture_prefers_llm():
    p = ExtractionPipeline(rules=_Rules(), spacy=_Spacy(), llm=_LLMok())
    result = await p.extract("i like fastapi", capture=True)
    contents = [f.content for f in result.facts]
    assert "The user likes FastAPI" in contents
    assert all("Tech mention" not in c and "→" not in c for c in contents)


@pytest.mark.asyncio
async def test_capture_falls_back_on_llm_error():
    p = ExtractionPipeline(rules=_Rules(), spacy=_Spacy(), llm=_LLMdown())
    result = await p.extract("i like fastapi", capture=True)
    assert result.facts  # rules/nlp fallback still produced something
```

(Match `ExtractionPipeline.__init__`'s real param names — the plan-writer's scout says ctor takes rules/spacy/llm; adapt the test's kwargs to reality.)

- [ ] **Step 2: Run to verify failure** — FAIL (`capture` kwarg unknown; LLM not preferred).

- [ ] **Step 3: Implement** — in `pipeline.py extract`, add `*, capture: bool = False`. Near the top of the method:

```python
        if capture and settings.capture_llm_clean:
            try:
                llm_facts = await self._llm.extract(text)
            except Exception:
                logger.warning("LLM capture extraction failed; falling back to rules/nlp", exc_info=True)
                llm_facts = []
            if llm_facts:
                merged = _deduplicate(llm_facts)
                return ExtractionResult(
                    facts=merged, tier1_count=0, tier2_count=0,
                    tier3_count=len(llm_facts), llm_invoked=True,
                )
        # ... existing tier1/tier2/gate/tier3 logic unchanged (the fallback) ...
```

In `memory_manager.py`, add `capture: bool = False` to `ingest(...)` and pass it: `extraction_result = await self._extractor.extract(text, capture=capture)`. Find capture callers (`services/multimodal.py` `ingest_or_fallback`, `workers/ingest_capture.py`, `api/memories.py` create) and pass `capture=True` where the input is a user capture (NOT for system/bulk paths). The plan-writer: grep `\.ingest(` and mark each call site capture vs not in the task.

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_pipeline_capture.py tests/unit/ -v` → green (existing extraction/memory-manager tests must still pass; non-capture `extract(text)` unchanged). `python -m py_compile` changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/extraction/pipeline.py life_graph/core/memory_manager.py tests/unit/test_pipeline_capture.py
git commit -m "feat(quality): LLM as primary extractor on the capture path (rules fallback)"
```

---

### Task 3: Language guard

**Files:**
- Modify: `life_graph/extraction/nlp.py`
- Test: `tests/unit/test_language_guard.py` (new)

**Interfaces:**
- Consumes: `settings.extraction_language_guard`.
- Produces: `SpacyExtractor.extract` returns `[]` (no entities/tech/relations) when the text is predominantly non-Latin and the guard is on. Latin/ASCII text unaffected.

- [ ] **Step 1: Failing test** `tests/unit/test_language_guard.py`:

```python
"""Non-Latin text skips English NER (which only produces garbage)."""

from life_graph.extraction.nlp import SpacyExtractor, is_predominantly_non_latin


def test_script_detector():
    assert is_predominantly_non_latin("பலன் இல் கவனம் வைத்து")  # Tamil
    assert not is_predominantly_non_latin("I like FastAPI and Postgres")
    assert not is_predominantly_non_latin("naalaikku insurance kattanum")  # romanized Tamil = Latin


def test_extract_skips_non_latin():
    ex = SpacyExtractor()
    assert ex.extract("இந்த உரை தமிழில் உள்ளது ஆகவே ஆங்கில") == []
```

- [ ] **Step 2: Run to verify failure** — FAIL (`is_predominantly_non_latin` undefined).

- [ ] **Step 3: Implement** — add to `nlp.py`:

```python
def is_predominantly_non_latin(text: str, threshold: float = 0.3) -> bool:
    """True if more than `threshold` of the letters fall outside Basic Latin.

    Romanized text (Tanglish written in ASCII) stays Latin and is NOT skipped;
    only genuine non-Latin scripts (Tamil, Devanagari, CJK, …) trip this.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    non_latin = sum(1 for c in letters if ord(c) > 0x24F)  # beyond Latin Extended-B
    return (non_latin / len(letters)) > threshold
```

At the top of `SpacyExtractor.extract`:

```python
        from life_graph.config import settings

        if settings.extraction_language_guard and is_predominantly_non_latin(text):
            return []
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_language_guard.py tests/unit/ -v` → green. `python -m py_compile life_graph/extraction/nlp.py`.

- [ ] **Step 5: Commit**

```bash
git add life_graph/extraction/nlp.py tests/unit/test_language_guard.py
git commit -m "feat(quality): language guard skips English NER on non-Latin text"
```

---

### Task 4: Suppress entity/tech fan-out + confidence floor

**Files:**
- Modify: `life_graph/extraction/nlp.py` (`_extract_entities`, `_extract_tech_mentions`, `extract`)
- Modify: `life_graph/extraction/pipeline.py` (apply the confidence floor)
- Test: extend `tests/unit/test_pipeline_capture.py` or a new `tests/unit/test_extraction_noise.py`

**Interfaces:**
- Consumes: `settings.extraction_tag_only_entities`, `settings.extraction_min_confidence`.
- Produces: when `extraction_tag_only_entities`, `SpacyExtractor.extract` no longer emits `Entity (...)`/`Tech mention:` standalone facts — instead their names are attached as `entities` on the relation-facts it does emit (or dropped if none). The pipeline drops any fact with `confidence < settings.extraction_min_confidence` before returning (both capture and fallback paths).

- [ ] **Step 1: Failing test** `tests/unit/test_extraction_noise.py`:

```python
"""Fallback path no longer emits Entity(...)/Tech mention: fragments, and floors confidence."""

from life_graph.extraction.nlp import SpacyExtractor
from life_graph.extraction.pipeline import _drop_low_confidence
from life_graph.extraction.rules import ExtractedFact


def test_no_standalone_entity_or_tech_facts():
    ex = SpacyExtractor()
    facts = ex.extract("I switched from MySQL to Postgres and use FastAPI")
    assert all("Entity (" not in f.content and "Tech mention:" not in f.content for f in facts)


def test_confidence_floor():
    facts = [
        ExtractedFact(content="keep", fact_type="fact", confidence=0.6),
        ExtractedFact(content="drop", fact_type="fact", confidence=0.3),
    ]
    kept = _drop_low_confidence(facts, 0.45)
    assert [f.content for f in kept] == ["keep"]
```

- [ ] **Step 2: Run to verify failure** — FAIL (`_drop_low_confidence` undefined; entity/tech facts still present).

- [ ] **Step 3: Implement** —
`nlp.py`: gate `_extract_entities`/`_extract_tech_mentions` so that when `settings.extraction_tag_only_entities` they return `[]` as facts but their found names are collected and merged into the `entities` list of the `_extract_relations` facts (if any). Simplest: in `extract`, compute `relation_facts = self._extract_relations(...)`; compute `entity_names`/`tech_names`; if tag-only, append those names to each relation fact's `entities` (dedup) and DON'T append the entity/tech facts; else keep current behavior. If there are no relation facts and tag-only is on, return `[]` (the LLM path or a raw fallback handles bare entity lists).
`pipeline.py`: add module-level `_drop_low_confidence(facts, floor)` and call it on `merged` right before every `return ExtractionResult(...)` (capture and fallback), using `settings.extraction_min_confidence`.

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_extraction_noise.py tests/unit/ -v` → green. Confirm existing nlp/pipeline tests still pass (some may assert old entity-fact behavior — update them to the new tag-only contract, noting the change). `python -m py_compile` changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/extraction/nlp.py life_graph/extraction/pipeline.py tests/
git commit -m "feat(quality): entities/tech become tags not memories; confidence floor"
```

---

### Task 5: One-time cleanup job + trigger

**Files:**
- Create: `life_graph/workers/cleanup.py` (`cleanup_memories_tenant`, `cleanup_memories_all`)
- Modify: `life_graph/workers/settings.py` (register both by full dotted name)
- Modify: `life_graph/api/admin.py` (trigger endpoint)
- Test: `tests/unit/test_cleanup_job.py` (new)

**Interfaces:**
- Consumes: `PostgresMemoryStore`, `find_similar`, the `Approval` model + merge pattern, `set_tenant_context`, `capture=True` re-extraction.
- Produces: `cleanup_memories_tenant(ctx, tenant_id) -> dict` (counts: consolidated, merge_approvals_queued). `POST /admin/jobs/cleanup-memories?tenant_id=` enqueues it (bare name). Idempotent.

- [ ] **Step 1: Failing test** `tests/unit/test_cleanup_job.py` — with a fake store returning a set of fragment memories and a fake session, assert the job queues a merge Approval for a high-similarity conflicting pair and is idempotent (re-run queues nothing new). Mirror `test_conversation_service.py`'s fake-session style. (Keep the assertion focused on the Approval-queuing + idempotency, not the LLM re-extraction which is mocked.)

- [ ] **Step 2: Run to verify failure** — FAIL (module absent).

- [ ] **Step 3: Implement** `workers/cleanup.py` mirroring `run_tenant_merge_suggestions` (tasks.py:157) and the `Approval(...)` construction (merge_suggestions.py:83-100), but with `source="cleanup"`, `source_ref` = a stable hash of the memory-id pair (idempotency via a seen-set query on `source="cleanup"`), and `kind="merge"`. For obvious same-utterance fragment groups (shared `properties.entities` overlap AND cosine ≥ `settings.merge_review_low`), queue a merge Approval. Do NOT auto-consolidate destructively in v1 — queue for approval (the spec allows consolidation-on-approval, handled by the existing merge approval resolver). Add `cleanup_memories_all(ctx)` iterating distinct tenants like `run_all_merge_suggestions`.
`workers/settings.py`: add `"life_graph.workers.cleanup.cleanup_memories_tenant"` and `"life_graph.workers.cleanup.cleanup_memories_all"` to the `functions` list.
`api/admin.py`: add `POST /jobs/cleanup-memories` mirroring `/jobs/consolidate` (create_pool → `enqueue_job("cleanup_memories_tenant", tenant_id)` or `"cleanup_memories_all"` → close), returning `{job_id, status}`.

- [ ] **Step 4: Run tests** — `python -m pytest tests/unit/test_cleanup_job.py tests/unit/ -v` → green. Verify registration: `python -c "from life_graph.workers.settings import WorkerSettings; print([f for f in WorkerSettings.functions if 'cleanup' in f])"` prints both dotted names. `python -m py_compile` changed files.

- [ ] **Step 5: Commit**

```bash
git add life_graph/workers/cleanup.py life_graph/workers/settings.py life_graph/api/admin.py tests/unit/test_cleanup_job.py
git commit -m "feat(quality): one-time memory cleanup job queues merges via approvals"
```

---

### Task 6: Edit-in-app

**Files:**
- Modify: `dashboard/lib/api.ts` (add `memories.update`)
- Modify: `dashboard/lib/mobile-api.ts` (`useUpdateMemory`)
- Modify: `dashboard/components/mobile/memory-sheet.tsx` (edit mode)
- Modify: `dashboard/components/memory-detail.tsx` (edit mode)
- Test: `npm run build` + lint

**Interfaces:**
- Consumes: `PATCH /memories/{id}` (existing).
- Produces: `api.memories.update(id, {content?, tags?})`; `useUpdateMemory()` invalidating `["memories"]`/`["memory-search"]`.

- [ ] **Step 1: API client** — add to the `memories` block in `api.ts`:

```ts
  update: (id: string, body: { content?: string; tags?: string[] }) =>
    request<any>("PATCH", `/memories/${id}`, body),
```

- [ ] **Step 2: Hook** — in `mobile-api.ts`, mirror `useResolveMemory`:

```ts
export function useUpdateMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, content, tags }: { id: string; content?: string; tags?: string[] }) =>
      api.memories.update(id, { content, tags }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memories"] });
      qc.invalidateQueries({ queryKey: ["memory-search"] });
    },
  });
}
```

- [ ] **Step 3: Mobile sheet edit mode** — `memory-sheet.tsx`: add an Edit button; in edit mode replace the content `<p>` (line ~91) with a `<textarea>` (uzhavu tokens) prefilled with `mem.content`, plus a comma-separated tags input; Save calls `useUpdateMemory().mutate({id, content, tags})` then closes edit mode; Cancel reverts. Disable Save while pending.

- [ ] **Step 4: Desktop detail edit mode** — `memory-detail.tsx`: same pattern with Tailwind (textarea + tags input + Save/Cancel), calling the same hook.

- [ ] **Step 5: Verify** — `cd dashboard && npm run build` passes; lint zero new (scoped eslint-disable only if the `<any>` client idiom forces it, per prior tasks).

- [ ] **Step 6: Commit**

```bash
git add dashboard/lib/api.ts dashboard/lib/mobile-api.ts dashboard/components/mobile/memory-sheet.tsx dashboard/components/memory-detail.tsx
git commit -m "feat(quality): edit a memory's content and tags in-app"
```

---

### Task 7: Deploy + E2E + PR

**Files:** none (VM ops + PR)

- [ ] **Step 1: Push & deploy** — push `feat/memory-quality`; on the VM: fetch + checkout + pull, `build app worker`, `up -d --force-recreate --no-deps app worker`, `docker network connect web life_graph_app`, dashboard rebuild + swap, smoke 200s. (No migration this feature.)

- [ ] **Step 2: Live E2E** (base64 remote bash):
  1. Capture "I like FastAPI and use Postgres for databases" → GET recent memories → expect ONE (or few) clean memory (e.g. "The user likes FastAPI"), NO `Tech mention:`/`Entity (...)` rows.
  2. Capture a Tanglish line → clean memory, no garbled `Entity (PERSON): …`.
  3. `POST /admin/jobs/cleanup-memories?tenant_id=personal` → wait → GET `/approvals?status=pending`: the two-names conflict (`Riz Aljaf` vs `Raja`) appears as a merge approval; fragment groups queued.
  4. Approve the correct name / resolve merges → GET memories: fragments consolidated.
  5. Ask (chat) "what is my name" → single clean answer.
- [ ] **Step 3: Edit E2E (user, phone)** — open a noisy memory → Edit → fix its text → Save → it updates.
- [ ] **Step 4: PR**

```bash
gh pr create --repo Raceraja001/life-graph --base master --head feat/memory-quality \
  --title "feat: memory quality — LLM-clean captures, language guard, cleanup, edit" \
  --body "Implements docs/superpowers/specs/2026-07-24-memory-quality-design.md ..."
```

User merges via GitHub UI; sync the VM clone back onto `master`.

---

## Self-review notes

- Spec coverage: LLM-primary capture (T2) with config knobs (T1); language guard (T3); entity/tech→tags + confidence floor (T4); cleanup job via approvals (T5); edit-in-app (T6); deploy+E2E incl. cleanup + edit (T7). ✅
- Type consistency: `capture: bool` flag flows `ingest → pipeline.extract` (T2); settings names identical across T1/T2/T3/T4; `api.memories.update` (T6) ↔ existing PATCH contract; cleanup Approval mirrors merge_suggestions `source`/`payload` shape (T5). ✅
- Known judgment calls: cleanup queues merges rather than destructive auto-consolidation (spec: nothing silently rewritten); rules/nlp kept as fallback (offline capture must still work); `capture=True` only on genuine user-capture ingest call sites, not bulk/system (T2 Step 3 marks them).
