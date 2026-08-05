# Transcript Distillation — Quality Fix (conversation-aware extraction)

**Goal:** Make Claude Code transcript distillation produce clean, useful memories — durable decisions, preferences, project/domain facts, and open tasks in the user's voice — instead of the harness-text leakage and fragmented `X → Y` noise the note-tuned extractor currently emits.

**Status:** Approved design (Approach A — conversation-aware LLM extraction). Ready for implementation plan.

## Why (the finding this fixes)

A live sanity-check backfill of 3 real sessions produced 47 `pending` memories, mostly junk of two kinds:
1. **Harness/skill text leaked in as "user facts"** — e.g. `"The terminal state → invoking writing-plans"`, `"merging into the wrong base → expensive to undo"` (verbatim skill-instruction text and `<system-reminder>` content, not things the user said). The current parser drops a turn only when it is *entirely* a `<system-reminder>` wrapper, so skill bodies and reminders appended to real prompts slip through.
2. **Fragmented nonsense** — `"Need to → OPI"`, `"We can → GCP"`, `"how do you → it"`. Tier-1 regex and Tier-2 spaCy fire on conversational prose and shred it, with enough "confidence" that the LLM tier (Tier-3) often never runs.

Only a small slice was genuine (`"client wants TPV in cashfree and razorpay"`). Extrapolated, an 808-session backfill would create ~10,000+ mostly-junk pending memories. The plumbing works end-to-end; the extraction quality does not. This spec fixes the extraction for transcripts only.

## Architecture

For transcripts, replace the note-tuned Tier-1/Tier-2 extraction with a **conversation-aware LLM extractor**. `TranscriptDistiller` cleans the dialogue (stripping harness/skill/tool content, gisting assistant turns for context), chunks it to fit the free model's context, makes one LLM call per chunk to emit categorized facts, and persists those facts through the **existing store-side machinery** (embedding + SHA/vector dedup + importance scoring + `status="pending"` + tags). Note ingestion (voice/image/document/manual) is untouched — this path is transcript-only.

**Data flow:**
```
turns → clean (strip harness/skill/tool; gist assistant to ~400 chars)
      → chunk (~2.5k tokens, small overlap)
      → LLM extract per chunk (categorized facts, ResilientLLM cheap tier)
      → ExtractedFact[]
      → MemoryManager store-side (_process_fact per fact: embed + dedup + score + pending + tag)
      → pending memories
```

## Global Constraints

- Work on branch `feat/transcript-quality`, worktree `scratchpad/transcript-wt`, off `origin/master` (currently `e4012b2`).
- Tenant scoping: unchanged — the distiller runs under `set_tenant_context`; all stores filter `tenant_id`.
- Distilled transcript memories stay **`status="pending"`** (the approval gate) — the backfill safety net.
- Extractor uses the **free OpenRouter model** via `settings.llm_model_cheap` / `ResilientLLM` cheap tier (same as the extraction primary). No new model config.
- No secret in git or chat. Commit trailer exactly: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Ruff line-length 100, double quotes; repo enforces UP035/TC003 (type-only imports under `TYPE_CHECKING`).
- Test convention: unit tests need no Postgres; LLM/network is mocked; valid input never `422`.
- Python interpreter for local runs: `/c/Python314/python.exe`.
- Reused interfaces (exist — do not reimplement):
  - `life_graph.extraction.rules.ExtractedFact(content, fact_type, confidence, entities, source_text)`.
  - `life_graph.core.memory_manager.MemoryManager`: `ingest(text, context, source, ...)` and the per-fact store-side method `_process_fact(fact, context, source, skip_dedup, trust_tier) -> Memory | None` (embeds, dedups, scores, sets pending). This spec **adds a thin public wrapper** `store_facts(facts: list[ExtractedFact], context, source) -> list[Memory]` that loops `_process_fact` — so the distiller never reaches into a private method.
  - `life_graph.services.resilient_llm.ResilientLLM.chat(messages, model=None, tier="cheap", temperature, max_tokens, response_format) -> str` (via `get_resilient_llm()`).
  - `life_graph.extraction.transcript_parsers.base.Turn` (`role`/`text`/`ts`) and the `PARSERS` registry.
  - `TranscriptDistiller` (`services/transcript_distiller.py`): reads staging, parses turns, currently calls `manager.ingest(user_text, ...)`; this spec changes only the extraction step.

## Component 1 — Parser hardening (`extraction/transcript_parsers/claude_code.py`)

Today `ClaudeCodeParser.parse` keeps `user` turns (external, non-sidechain) and drops a turn only if `_harness_only(text)` (entirely a `<system-reminder>` / `<local-command-` wrapper). Harden it:

**1a. Strip injected blocks from within a user turn** (new helper `_strip_injected(text) -> str`), removing these spans wherever they appear, then using the remaining prose:
- `<system-reminder> … </system-reminder>` (non-greedy, dot-all)
- `<command-name> … </command-name>`, `<command-message> … </command-message>`, `<command-args> … </command-args>`, `<local-command-stdout> … </local-command-stdout>` and any `<local-command-*> … </local-command-*>`
- `<ide_selection> … </ide_selection>`, `<ide_opened_file> … </ide_opened_file>`
After stripping, if only whitespace remains, the turn yields nothing.

**1b. Drop turns that are harness/skill/command injections** (extend `_harness_only`, rename to `_is_injected(text)`), when the *stripped* text begins with or is dominated by an unambiguous marker:
- Skill delivery: starts with `Base directory for this skill:`, `(Re-invocation of`, or contains `Launching skill:` as its leading content
- Command caveat: `Caveat: The messages below were generated by the user while running local commands`
- Compaction handoff: `This session is being continued from a previous conversation`
- Background task: starts with `[SYSTEM NOTIFICATION` or contains `<task-notification>`
- Local-command wrapper: starts with `<local-command-`

**1c. Emit assistant turns as context gists.** Add `assistant` turns to the output (they were dropped before). For an `assistant` line, concatenate only `type=="text"` blocks (drop `thinking`/`tool_use`), strip, and **truncate to 400 chars** (`… ` suffix if truncated). Skip empty. These are context only — the extractor is told not to mine them for facts.

The parser stays pure (`Iterable[str] -> list[Turn]`); `Turn.role` is `"user"` or `"assistant"`. Order preserved (turn-index marker still valid).

## Component 2 — Conversation-aware extractor (`extraction/transcript_extract.py`)

```python
async def extract_transcript_facts(turns: list[Turn], *, resilient_llm=None) -> list[ExtractedFact]: ...
```

**Chunking** (`_chunk(turns, max_chars=10_000, overlap_turns=2) -> list[list[Turn]]`): greedily pack turns until ~10k chars (≈2.5k tokens, safe for the free model), carrying `overlap_turns` trailing turns into the next chunk so a decision split across the boundary isn't lost. A single oversized turn becomes its own chunk (its user text is truncated to `max_chars`).

**Per-chunk LLM call** via `ResilientLLM.chat(tier="cheap", response_format={"type":"json_object"}, temperature=0.1, max_tokens=1024)`:
- **System prompt:** "You extract durable personal-knowledge facts from a developer's conversation with an AI coding assistant. The user's turns are labelled `USER:`; assistant turns (labelled `ASSISTANT:`) are context only — never extract facts from them. Emit ONLY things worth remembering long-term, in the user's voice: (1) decisions the user made, (2) preferences they expressed, (3) concrete project or domain facts, (4) open tasks / TODOs they raised. Do NOT emit: code, commands, file paths, shell output, error text, or anything about the AI-assistant process itself (skills, plans, reviews, tool mechanics). Each fact is one standalone sentence understandable without the conversation. If there is nothing durable, return an empty list."
- **User message:** the chunk rendered as `USER: …` / `ASSISTANT: …` lines.
- **Output schema:** `{"facts": [{"content": str, "category": "decision"|"preference"|"fact"|"task"}]}`.
- **Parse** into `ExtractedFact(content=content, fact_type=<mapped>, confidence=0.7, entities=[], source_text=content)` — mapping `decision→decision`, `preference→preference`, `fact→fact`, `task→intention` (existing `fact_type` values). Skip malformed items; a chunk whose call fails (after `ResilientLLM` failover) is logged and skipped (its facts are lost for this run but the marker only advances on the distiller's normal path — see error handling).

The extractor is independently testable with a stubbed `resilient_llm` (no network).

## Component 3 — Rewire `TranscriptDistiller`

In `TranscriptDistiller.distill`, replace the Tier-1 block:

*Before:* `text = "\n".join(redact(t["text"]) for t in new_user_turns)`; `memories = await self._manager.ingest(text, ...)`.

*After:*
1. Build the **extraction window** — do NOT re-extract the whole session each run. Window = `turns[max(0, es.last_turn_index - CONTEXT_LOOKBACK):]` with `CONTEXT_LOOKBACK = 4` (a couple of preceding user/assistant turns so a new user turn's context is present). This scopes LLM calls to new content; the small overlap re-extracted from the lookback region is collapsed by dedup. (Marker/advance logic unchanged: still gated on new *user* turns existing in `turns[es.last_turn_index:]`; `last_turn_index` still advances to `len(turns)`.)
2. **Redact** each turn's text (still before extraction and archive).
3. `facts = await extract_transcript_facts(turns, resilient_llm=self._llm)` — add a `resilient_llm` dependency to `TranscriptDistiller.__init__` (from `get_resilient_llm()`), wired in `get_transcript_distiller()`.
4. Persist: `memories = await self._manager.store_facts(facts, context={"source_session": session_id, "tool": es.tool}, source="transcript")` (new thin public wrapper looping `_process_fact`), then tag each `es.tool`/`"transcript"` as today.
5. Archive (redacted thread) and marker advance unchanged.

**No-op / skip semantics unchanged:** if there are no new user turns, advance marker and return `skipped`. If extraction returns `[]`, `new_facts=0` but archive + marker still proceed (a session with no durable facts is a valid outcome, not an error).

## Data model

No schema changes. Reuse `memories` (pending, tagged) and `external_sessions` (turn-index marker). No migration.

## Error handling

- **LLM failure per chunk:** `ResilientLLM` fails over across the free-model chain; if a chunk still can't be extracted, log and skip that chunk (partial extraction is better than failing the whole session). The distiller does not raise — it stores whatever facts succeeded.
- **Malformed JSON** from a chunk: parse defensively, skip unparseable items, keep valid ones.
- **Marker:** advances only on the distiller's committed path, exactly as today (never regresses on a MinIO read failure — that fix stands).
- **Redaction:** unchanged — before both extraction and archive.
- **Idempotency:** re-distilling re-extracts, but dedup (SHA + vector) collapses repeats and the turn-index marker prevents reprocessing already-distilled turns.

## Testing

- **Parser** (`tests/unit/test_claude_code_parser.py`, extend): a fixture turn with a real prompt + an appended `<system-reminder>` → the reminder is stripped, the prompt survives; a skill-body turn (`Base directory for this skill:`) → dropped; a `[SYSTEM NOTIFICATION` turn → dropped; an assistant turn with `thinking`+`text` → emitted as a ≤400-char gist; existing drops (tool_result/sidechain/attachment) still hold.
- **Extractor** (`tests/unit/test_transcript_extract.py`, new): with a stubbed `resilient_llm.chat` returning canned JSON, assert `extract_transcript_facts` returns mapped `ExtractedFact`s; a chunk that references only assistant context yields nothing; a raising `chat` is swallowed (other chunks still extracted); `_chunk` packs to the char budget with overlap.
- **Distiller** (`tests/unit/test_transcript_distiller.py`, extend): stub the extractor to return 2 facts; assert `store_facts` is called and memories are tagged `claude-code`/`transcript`; a no-durable-facts session returns `new_facts=0` but still archives + advances the marker.
- **The real gate (manual, before backfill):** re-ship the same 3 real sessions used in the sanity check; inspect the resulting `pending` memories; only proceed to the 808-session backfill if they read as clean decisions/preferences/facts/tasks with no harness/code/`X → Y` noise.

## Scope (in / out)

**In:** parser hardening; conversation-aware transcript extractor; `TranscriptDistiller` rewire + `store_facts` wrapper; tests; the manual re-test gate.

**Out (YAGNI):** any change to note ingestion (voice/image/document/manual) or the 3-tier pipeline; Codex/Antigravity; dashboard changes; a stronger model for the backfill (free model chosen); new DB columns; automatic backfill kickoff (still user-triggered after the re-test passes).
