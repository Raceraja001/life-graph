# ADR: M8 — ingestion that produces structure (world time, supersession, typed links, decision lifecycle)

**Status:** Proposed 2026-11-28. Design only: no code, no migration, nothing deployed. The owner approves designs.
**Spec:** [docs/specs/personal-context-intelligence.md](../specs/personal-context-intelligence.md) §2 (invariants 3, 4, 6, 8, 9), §4.2, §4.3, §4.4
**Builds on:** [docs/audits/2026-11-26-m8-context-quality-evaluation.md](../audits/2026-11-26-m8-context-quality-evaluation.md) §4 (D1, D6, D8, D11), §5, §6 P2.3 and P2.4; [adr-m8-context-change-detection.md](adr-m8-context-change-detection.md) (Stage 2, D13 amendment)
**Baseline:** `origin/master` `a8be53f4`
**Out of scope:** goals, constraints, responsibilities and domains. They get a second ADR (§9).

## 1. Problem

The M8 read side is in place. The snapshot (`services/memory/snapshot.py`), change detection (`changes.py`) and the sufficiency check (`sufficiency.py`) read world time, supersession, typed links and decision status. On the synthetic data in the evaluation they work.

On real data almost none of that structure exists (audit §5, Stage 0):
- `valid_from` equals the recorded time on every active memory, so `world_time_known` is always false;
- 1 memory is superseded;
- all ~180 links are `ASSOCIATED`, so the typed relations from #419 never appear;
- all 11 decisions are `candidate`.

The read model can only be as good as what the save path writes. This ADR decides what the save path should write, and how we prove it.

## 2. Constraints

Each one is checked against the design in §7.

1. **Personal data stays local.** Everything here runs on the owner's machine.
2. **No cloud models.** Rules first. A model step is allowed only as a fallback, and only through `chat_local_only`.
3. **No new memory DB and no graph engine.** Only existing tables (`memories`, `memory_links`, `life_graph.decisions`, `approvals`) and their JSONB `properties`.
4. **No hardcoded domain enums in the schema-less core.** No DB enum or CHECK of attribute names, topics or domains. Slot keys stay data.
5. **Inferred context never becomes confirmed intent.** A model, an agent, a rule or an API key without the owner never moves anything to "confirmed".
6. **Tenant isolation unchanged.** Every new read and write is scoped by `get_current_tenant_id()`, with both ends of a link or chain checked.
7. **Nothing grants execution permissions.** No status written here is read by autonomy, approvals or any execution path.

## 3. Current state, with evidence

### 3.1 The save path, end to end

Every path that creates memories ends in `MemoryManager._process_fact` (`core/memory_manager.py:360-635`), except the Jarvis tool `memory_save` and the verbatim API store.

| Step | Where | What happens |
|---|---|---|
| Capture | `api/capture.py:57`, `api/jarvis.py:303` → `services/capture.py:110` | A `CaptureEvent` is stored and `CAPTURE_RECEIVED` is emitted. |
| Late capture | `services/capture_processors.py:177-179`, `core/said_at.py:22-31` | A capture that arrives more than 10 minutes late sets `said_at` to the time it was said. |
| Extraction | `capture_processors.py:208` → `extraction/pipeline.py` → `extraction/llm.py` (`chat_local_only`, `:457`) | The local model returns facts with `fact_type`, `confidence`, `entities`, `changes_over_time`, `valid_until`, `subject`, `polarity`, `certainty`, `reason`, `correction` and `slot` (schema `llm.py:57-103`; checks `_validity` `:697-709`, `_meaning` `:712-744`). The prompt is given "Today is …" (`:218-228`) and writes Tamil content in English (`:202`). |
| Persist | `capture_processors.py:393-409` → `MemoryManager.store_facts` (`memory_manager.py:187-226`) | Embed, dedup, contradiction check, store. Text paths use `MemoryManager.ingest` (`:96-185`): `api/memories.py:114`, `services/distillation.py:151`, `services/agent_bridge.py:165`, `services/multimodal.py:100`, `api/admin.py:269`. |
| Remember (MCP) | `mcp_server.py:144-189` → `POST /api/v1/memories/` (`api/memories.py:76-129`) | Free text goes through `ingest`. Short tagged input is stored verbatim (`:43-66`) with no extraction and no contradiction check. |
| Jarvis save | `tools/memory_search.py:402-529` | Stored directly by `store.store` (`:474-486`). It supersedes only what the model names in `replaces_id` (`:487-498`, `_supersede` `:602-636`). No contradiction check. |
| Write row | `storage/postgres.py:206-308` | Accepts `valid_until` (`:217`, `:280-281`). It has **no `valid_from` parameter**. |
| Links | `memory_manager.py:50-58` → `services/memory/associations.py:98-110` | Facts from one message are linked as `ASSOCIATED` (`LINK_TYPE`, `:32`). |
| Entities | `memory_manager.py:605-611` | Entities are linked to the memory (`memory_entities`), not to each other. |
| Decisions | `capture_processors.py:252-266` (regex `:62-71`, `_detect_decisions` `:541-552`) → `DECISION_CANDIDATE` → `services/judgment.py:833-871` | A `Decision` row is created with `status="candidate"` (`:855`). |

### 3.2 World time

- **Column:** `valid_from` is `NOT NULL` with a Python default of "now" (`models/memory.py:81-83`). `store()` never sets it (`postgres.py:263-277`), so it is the insert time.
- **Reader convention:** the snapshot treats `valid_from == recorded` (to the second) as "no world time of its own" (`snapshot.py:534-540`). That convention is how "unknown" is spelled today.
- **What the extractor gives:** only `valid_until`, the end of a fact ("until Friday"), turned into an end-of-day time (`memory_manager.py:594`, `:885-899`). There is no start field. The audit says `valid_until` is never set in prod. So the model rarely fills it, though the code path exists.
- **Late captures:** `_as_said` backdates `created_at`, `updated_at` and `last_accessed` to the time it was said (`memory_manager.py:319-346`, values at `:326`). It does **not** touch `valid_from`. So a late memory gets `valid_from` (arrival) *later* than its recorded time (said). The snapshot then reports `world_time_known: true` with a world time that is just the delivery time. See §10.
- **Read-side world time already used:** a day summary's `properties.date` is its valid time (`services/memory/retrieval.py:569-575`). `retrieval._temporal` lets `properties.valid_from` override the column (`:525-551`). Nothing writes it.
- **Deterministic date rules that exist, English only:** future windows in `services/commitments.py:33-39`, `:58-103` ("today", "tomorrow", "this week", "by Friday"); past windows in `services/episodes.py:312-345` ("yesterday", "3 days ago", "last month", "last year"); `extraction/intentions.py:56-104`; `services/reminders.py:59`. Tamil words for the past exist only in `services/profile_card.py:51-55` (`முன்பு`, `முன்னாடி`, `பழைய`). Tamil-safe tokenising exists in `snapshot.py:789` and `sufficiency.py:26-39`.

### 3.3 Supersession

Supersession on change **is already built** on the save path. It rarely completes. The writers:

1. **Same slot** (`memory_manager.py:551-554`, `_same_slot_active` `:755-804`): an active memory with the same `topic.field` slot (e.g. `home.city`, `family.anu.school`) is a supersede target.
2. **Contradiction detector** (`services/contradiction.py:240-304`): a negation flip, a preference change or a value change (2026-11-25), above `contradiction_similarity_threshold`. All three resolve to `supersede` (`:780-803`). A different project or module scope keeps both.
3. **Late values** (`memory_manager.py:557-563`, `:301-317`): an old value never replaces a newer one.
4. **Jarvis correction** (`tools/memory_search.py:487-498`).
5. **Approvals** (`services/approvals.py:1166-1271`): a deferred supersede is applied when the owner approves the new memory or the contradiction item. Rejecting the item undoes it.

The supersede is applied at once only when the new memory is active (`memory_manager.py:622-627`). Otherwise a contradiction approval with `applied: false` waits (`:637-701`). Two rules make "active" rare:
- `_auto_approved(..., contradicts=bool(other_clashes))` (`:564`, `:948`). A fact that clashes with anything except its own slot always waits for review.
- Only `self`-tier facts at confidence 0.9 or more, of type fact/preference/anti_preference/decision, skip review (`:903-952`). `intention` never does.

So most changes become a pending contradiction approval that the owner has not resolved. The old memory then stays active. Three things are missing:
- **No world-time end on the old fact.** Every writer sets `status`, `superseded_by` and `properties.superseded_at` (when we stopped believing it). None sets the old row's `valid_until` (when it stopped being true). The audit's D1 calls this out.
- **No link row.** The chain is `superseded_by` / `supersedes` columns, not a `SUPERSEDES` row in `memory_links`. This is fine: the snapshot reads the columns (`snapshot.py` conflict kind `supersession`). We keep it that way (§5.2).
- **Only English cues.** The negation and value-change detectors are regex over English. Tamil content reaches them only after the model has translated it.

### 3.4 Link types

- `VALID_LINK_TYPES` (`services/memory/links.py:41-52`): BECAUSE, EVIDENCED_BY, RELATED_TO, CONTRADICTS, SUPERSEDES, LEADS_TO, ASSOCIATED.
- **Writers:** `ASSOCIATED` only, from `associations.py` (said together, used together). `create_link` (`links.py:71-146`) is called only by the API route (`api/memory_links.py:55`). `auto_link_memories` (`links.py:312-378`) has no caller.
- **#419's reader** (`snapshot.py:1049-1109`): every type except ASSOCIATED between two included memories. CONTRADICTS becomes a `linked_contradiction` conflict; the others become `relations`.
- **What extraction already knows but drops:** `fact.reason` is stored as text in `properties.reason` (`memory_manager.py:523-524`). It is never linked to the fact that *is* the reason, even when both came from one message.

### 3.5 Decisions

- **Model** (`models/judgment.py:235-315`): `status` is a free `String(16)`, documented as candidate, decided, reviewed, superseded, discarded (`:258-263`). There is `superseded_by` (`:292-296`), `decided_at`, `review_at`, `reviewed_at` and `properties` (`:299-302`). There is no superseded-at time.
- **Writers:** the capture listener (always `candidate`, `judgment.py:855`) and `POST /judgment/decisions` (`api/judgment.py:89-117`). The API's `DecisionCreate.status` defaults to `"decided"` and is not validated (`models/schemas.py:1067`).
- **Transitions:** none in use. `supersede_decision` (`judgment.py:517-549`) has no caller, and there is no route that changes a decision after creation.
- **Not tied to memories:** the same sentence makes a `decision` memory (`fact_type`) and a `Decision` row, and nothing links the two.
- **Not trust-gated:** `_detect_decisions` runs on every extracted surface (`capture_processors.py:252-266`). Commitments are limited to the owner's own Jarvis words (`:316-321`), but a forwarded mail saying "we decided to…" makes a candidate decision.
- **Readers:** the snapshot (`snapshot.py:625-652`, `confirmed=False` always, `:639`), change detection (`changes.py:587-612`, `:770` holds candidates back), the brief (`services/brief.py:447-467`, `:45`) and failure mining (`services/failure_mining.py:33`, which expects `abandoned` / `reversed`, statuses nothing writes).

## 4. Decision (summary)

1. **World time from the fact's own words**, by deterministic rules (English, Tamil, Tanglish). The local model's existing extraction call may *propose* a start date, but rules decide. Unknown stays unknown (§5.1).
2. **Supersession completes more often, honestly.** One helper for all five writers also ends the old fact's world time on a real change, never on a correction. Confidence tiers decide between auto-apply (undoable), an owner review item, and nothing (§5.2).
3. **Typed links at extraction**, between facts of one message only: BECAUSE from the reason the extractor already returns, LEADS_TO only from an explicit sequence. No similarity links (§5.3).
4. **A decision lifecycle with owner-only promotion.** candidate → decided (confirmed) / discarded (rejected) / superseded, wired to `supersede_decision`. One nullable column, `decisions.superseded_at` (§5.4, §5.5).
5. **Every step behind its own default-off flag**, measured by an ingestion eval arm and a label-only shadow check before any flag goes on in prod (§6, §8).

## 5. Design

### 5.1 World time

**Where:** a new pure module `extraction/world_time.py` that returns `WorldTime(start, precision, rule, source) | None`. It is called in `_process_fact`, in `memory_save` and in the verbatim store. It is passed to `store()` through a new `valid_from` keyword, next to `valid_until`.

**What it reads, in order:**
1. **The fact's content**, the model's English sentence: dates the model kept ("since March 2024", "moved to Coimbatore last month").
2. **The fact's own sentence in `source_text`**, the owner's words, which may be Tamil or Tanglish. Used only when the message holds exactly one time phrase, so a date is never pinned on the wrong fact of a multi-fact message.
3. **Fallback, local model:** an optional `valid_from` field in the existing extraction schema, next to `valid_until`. It is read only when rules found nothing and the model's value is an ISO date that matches a time phrase the rules can see in the text, even one they cannot resolve ("last Pongal"). It is checked like `_validity` (`llm.py:697-709`). There is no extra model call, and a bare date with no phrase in the text is dropped.

**Rules** (anchored at `said_at` if set, else now, in `user_tz()`):

| Phrase | Start | Precision |
|---|---|---|
| ISO or written date: "on 3 May", "3/5/2025", "2024-05-03" | that day | day |
| "in March", "since March 2024", "from January" | first of the month (the past month when no year) | month |
| "in 2019", "since 2019" | 1 January | year |
| "yesterday", "day before yesterday", "N days ago" | that day | day |
| "last week" / "last month" / "last year" | start of that period | week / month / year |
| "this week" / "this month" / "this year", "now", "currently", "today" | start of the period; for "today" or "now", the said day | as named |
| Tamil: `நேற்று` (yesterday), `முந்தாநாள்` (day before), `இன்று` / `இன்னைக்கு` (today), `போன வாரம்` / `கடந்த வாரம்` (last week), `போன மாதம்` / `கடந்த மாதம்` (last month), `போன வருஷம்` / `கடந்த ஆண்டு` (last year), `N நாள் முன்` (N days ago) | as the English row | as the English row |
| Tanglish: "nethu", "innaiku", "pona vaaram", "pona maasam", "pona varusham" | as above | as above |
| Future phrases ("next week", "by Friday") | **no start**: a plan, not a world time. Intentions keep their own due time (`commitments.py`). | — |
| No phrase | **unknown** | — |

The Tamil and Tanglish list is data in the module, matched on whitespace and punctuation tokens. The `\w` split broke Tamil before (audit D10). The owner reviews the list in its PR.

**Stored as:**
- `valid_from` = the start, only when known.
- `properties.world_time = {"precision", "rule", "source": "content" | "source_text" | "model"}`, so a reader and a rollback can tell a rule-set start from the default.
- **Unknown** keeps today's spelling: `valid_from` = the recorded time, which every reader already reads as "no world time" (`snapshot.py:534-540`). We never write "now" as a claimed world time. Making the column nullable was considered and rejected. `is_valid_at` reads `None` as "always started" (`retrieval.py:579`), so an unknown fact would become true at any past `as_of`, which is worse.
- **Late captures:** `_as_said` also sets `valid_from` to the time it was said when the rules found nothing, so "unknown" stays "equal to recorded" (fix for §3.2).

**Never:** a hedged or negated fact does not get a start ("maybe since March"). An intention does not get a start. A day summary keeps `properties.date`.

### 5.2 Supersession

**Same subject and attribute** means, deterministically:
- **(S1)** the same canonical slot (`core/slots.py`, `entities.canonical_slot`). Subject and field are in the key (`family.anu.school`).
- **(S2)** a contradiction-detector hit (negation, value change, preference change) between two facts with the same `subject` and the same project/module scope.

Nothing else is a supersession. Plain similarity is not.

**One helper** `memory.supersession.apply(old, new, why)` replaces the five hand-written UPDATEs (`memory_manager.py:228-299`, `:319-346`, `tools/memory_search.py:602-636`, `approvals.py:1208-1243`, and the identity and consolidation paths). It writes, in one tenant-scoped transaction:
- what they write today: `status`, `superseded_by`, `supersedes`, `properties.superseded_at`;
- **new: the old fact's world-time end.** If the change is a world change (the new fact is not a `correction` and its world time is known), set `old.valid_until = new.valid_from` when it is not already set. A correction ("actually it's Anna Nagar") means the old value was never true. It keeps no `valid_until` and stays history of belief only (`superseded_at`). This fixes D1's second half: `as_of` questions about March see the March value.
- **No `SUPERSEDES` row in `memory_links`.** The columns are the link, the snapshot and changes read them, and two places would drift. CONTRADICTS rows are not written by ingestion either: an unresolved clash is an approval, which the snapshot already shows as `pending_contradiction`.

**Confidence tiers:**

| Tier | When (all must hold) | Action |
|---|---|---|
| **High** | S1 (same slot). The new fact is the owner's own (`trust_tier == "self"`), firm, affirmed, confidence ≥ 0.9, not said before the old one (`_older_and_newer`). The old one is active. | Applied at once. A contradiction approval is recorded with `applied: true`, so one tap undoes it (today's behaviour for slots, `memory_manager.py:622-627`). The new fact stays active. |
| **Medium** | S2, or S1 with confidence 0.8–0.9, or S1 where the new fact is pending. | No change to either memory. Contradiction approval with `applied: false` and `payload.confidence: "medium"` (today's behaviour). The owner's Keep applies it. |
| **Low** | Same subject and scope, `changes_over_time` true on both, similarity between `contradiction_similarity_threshold` and `dedup_threshold`, `differs_in_detail` true, but no detector cue and no slot. | **Never automatic.** A review item: a contradiction approval with `applied: false`, `payload.confidence: "low"`, title "Possible update to review". Capped at 5 a day per tenant, so the queue cannot jam again (3,668 pending on 2026-10-22). Over the cap it is counted, not queued. |
| **None** | Anything from an `external` or `hostile_possible` tier against a `self` memory. | No supersede and no low-tier item. A medium hit is still queued, as today, so the owner sees the clash. |

**Why not the #420 dispute marker.** `properties.disputed` is the owner's own "this memory was wrong" (`api/jarvis.py:1902-1940`). The change-detection ADR §5.4 rule 1 relies on "nothing else writes that key". A machine-suspected clash written there would read as an owner act. The contradiction approval is the right existing machinery: it carries both sides, an `applied` flag and undo (`approvals.py:1166-1206`). The snapshot shows it as a conflict, and changes reports `conflict_appeared` / `conflict_resolved`. When the owner later presses "this was wrong" on the surviving value, #420 works unchanged.

### 5.3 Typed links at extraction

Only between facts stored from **one message**, the ones `_link_said_together` already pairs. Each link carries `properties.why = "extraction:<rule>"` and `strength = min(confidence of both)`. It is written through `links.create_link`, which checks that both ends are in the tenant (`links.py:116`).

| Type | Rule | Source |
|---|---|---|
| `BECAUSE` | Fact A has `reason` R. Another fact B of the same message matches R: normalised token overlap ≥ 0.6 of R's content words, Tamil-safe tokens. Link A → B. | the extractor's existing `reason` field; deterministic match |
| `LEADS_TO` | The model fills a new optional field `leads_to: [index]` (another fact of the same output), **and** the owner's sentence has an explicit sequence or result cue between the two ("so", "then", "after that", "which is why", `அதனால`, `அப்புறம்`, "adhanala", "apram"). | local model proposes; a rule confirms |
| `EVIDENCED_BY` | Not at extraction. It needs documents and evidence records: second ADR. | — |
| `RELATED_TO` | **Not written.** `auto_link_memories` (cosine ≥ 0.8) stays unwired: similarity is what `ASSOCIATED` and spreading already do, and it would flood `relations` with noise. | — |
| `CONTRADICTS`, `SUPERSEDES` | Not written by ingestion (§5.2). | — |

A link is a relation between two records, never a claim that either is true. It changes no status. A link to a pending memory is written, but the snapshot only shows it when both ends are included items (`snapshot.py:1086`). A link from a rejected memory goes when the memory is rejected, through the existing reject path. The link types are the existing `VALID_LINK_TYPES`: no new vocabulary.

### 5.4 Decision lifecycle

The existing vocabulary is kept. "Confirmed" is `decided`; "rejected" is `discarded`. `reviewed` stays the owner's post-decision review.

```text
            owner                      owner (or mirrors an applied memory supersede)
candidate ─────────▶ decided ─────────────────────────────────────────▶ superseded
    │                   │  owner
    │ owner             └────────▶ reviewed ───────────────────────────▶ superseded
    ▼
discarded            candidate ──(mirrors an applied memory supersede)──▶ superseded
```

| Step | Who may | How | Never |
|---|---|---|---|
| create → `candidate` | the capture rules, **only on `self`-tier surfaces** (gated like commitments, `capture_processors.py:316-321`); an API or MCP caller; Jarvis | existing listener, `create_decision` | — |
| create → `decided` | the owner only | `POST /judgment/decisions` with `status="decided"` only when `api/approval_identity.require_owner` passes. Otherwise it is stored as `candidate`, and `status` is validated against the five values. | an agent, MCP or API key without the owner |
| `candidate` → `decided` | the owner only | (a) new `POST /judgment/decisions/{id}/confirm` behind `require_owner`; (b) the owner keeps the linked decision memory in review, with a review stamp `by` an owner actor. An auto-kept memory (`auto_kept`) is **not** an owner act. | a rule, the model, an auto-keep, a brief |
| `candidate` → `discarded` | the owner only | `POST …/{id}/discard`; or the owner drops the linked decision memory (`on_memory_rejected`) | the system never discards: a stale candidate is labelled, not removed |
| `decided` → `reviewed` | the owner only | existing semantics (`reviewed_at`), via `…/{id}/review` | — |
| `decided`/`reviewed` → `superseded` | the owner | `POST …/{id}/supersede {by}` → `supersede_decision`; or the owner approves the contradiction item between the two linked decision memories | the system on its own |
| `candidate` → `superseded` | the system, but only as a **mirror** of a memory supersede that was applied (High tier or owner-approved), and undone with it | the supersession helper (§5.2) calls `supersede_decision` for the decisions linked to the old and new memories | promotes nothing: the new decision keeps its own status |

**Wiring:**
- `supersede_decision` gets the checks it lacks. It checks that `new_id` exists in the same tenant (today only `old_id` is checked, `judgment.py:530-539`). It refuses a self-supersede or a chain that loops. It sets `superseded_at`.
- Every transition appends `{from, to, at, by}` to `decisions.properties.lifecycle`, an audit trail in the existing JSONB column with no migration. `by` comes from `approval_identity.resolver`, never from the request body.
- **Decision ↔ memory:** `Decision.properties.memory_id` and the memory's `properties.decision_id`, written when the capture creates both from one message. These are JSONB references in existing columns with no foreign key, read only inside the tenant.
- **Readers:** the snapshot's `decision_item` reports `confirmed = true` only for `decided`/`reviewed` with an owner `by` in the trail (`snapshot.py:639`). `changes.py` takes `at` for `decision_superseded` from `superseded_at`, and for `discarded` from the trail. It flags an owner-made transition `acknowledged` (closes ADR Appendix B item 10 for decisions).

### 5.5 Migration (proposed, not written)

The decision lifecycle needs one timestamp. Everything else fits existing columns.

| | |
|---|---|
| Revision | the next free number when built: `063_decision_superseded_at` today. The change-detection ADR Appendix A pencils `063_context_snapshot_refs`, deferred; whichever lands first takes 063. |
| Table | `life_graph.decisions` (schema-qualified, because of the `"$user"` search_path issue in D30) |
| Column | `superseded_at TIMESTAMPTZ NULL`, no default, no server default |
| Index | none: decisions are read by id or by `(tenant_id, status)`, which `ix_decisions_tenant_status` already covers |
| Backfill | **none.** Prod holds 0 superseded decisions (all 11 are `candidate`). A superseded row from any other environment keeps `NULL`, which means "time unknown". `changes.py` already handles `at = null`. We never invent a time. |
| Model | `superseded_at: Mapped[datetime \| None] = mapped_column(DateTime(timezone=True), nullable=True)` next to `reviewed_at` |
| Downgrade | drop the column. Status and `superseded_by` stay, so only the time is lost. |
| Why a column and not `properties` | Its siblings `decided_at` and `reviewed_at` are columns on the same table. Change detection compares it to a window, and a typed column cannot hold a malformed string. Memories keep `superseded_at` in `properties` for history; we do not move them. |

No other migration: `memories.valid_from` and `valid_until` exist, `memory_links` takes the types, and `properties` takes `world_time`, `lifecycle` and the cross-references.

## 6. Measurement

### 6.1 What moves today's evals cannot see

`scripts/eval_context_quality.py` seeds rows **with** the structure already present: `valid_from_d`, typed links, superseded rows (`seed`, `:207-303`). It measures the read side, so it cannot show that ingestion now writes structure. We add an **ingest arm**:
- each dataset record gains the owner's sentence (`said`, English, Tamil or Tanglish) and a said-at offset;
- the arm builds the world by sending those sentences through `MemoryManager.store_facts`, the capture listener and the decision routes, instead of seeding finished rows;
- in CI it is deterministic: the extractor's output for each sentence is a committed fixture (a recorded local-model run), and the hashing embedder is used;
- a live local-model run is an optional arm, like `answer`, with the model guard on (0 cloud constructions);
- the same 45 questions are then scored on that world.

**Metrics expected to move (ingest arm vs today's seeded-from-prod-shape world):**

| Metric | Today (prod shape) | Expected |
|---|---|---|
| `relationship_explicit` (O, B, D, E, F) | 0.00–0.50 hashing | ≥ 0.8 on pairs said in one message |
| `current_vs_historical`, `temporal` (E, O) | E2 depends on seeded `valid_from` | E2 correct from ingestion alone |
| `conflict_recall` (O, C) | 0.33 / 0.50 | medium-tier pairs present as `pending_contradiction` |
| O5 superseded decisions, O4 recent decisions | prod has no path | owner-confirmed via the arm's routes: 1/1, 2/2 |
| O6 change detection | 7/7 on seeded data | `decision_superseded` and `discarded` carry `at` |

**New ingestion metrics** in a small dedicated eval, `evals/ingestion_structure/cases.json` with `scripts/eval_ingestion_structure.py --verify` in CI. It holds at least 80 labelled sentences, at least a quarter Tamil or Tanglish:

| Metric | Target |
|---|---|
| world-time precision (start and precision right, when a start is set) | ≥ 0.95 |
| world-time recall (gold has a phrase) | ≥ 0.85 |
| **world time set where the gold is unknown** | **0** (zero tolerance) |
| future phrase given a start | 0 |
| supersession recall, S1 and S2 | ≥ 0.9 |
| **auto-applied supersede where the gold is "not the same attribute"** | **0** (zero tolerance) |
| low-tier review items per 100 facts | reported; ≤ 5 |
| correction given a `valid_until` | 0 |
| BECAUSE / LEADS_TO precision | ≥ 0.9; recall reported |
| **decision moved to decided without an owner identity** | **0** (zero tolerance) |
| cross-tenant link, chain or decision reference | 0 |
| cloud model constructions | 0 |

**Existing evals extended:**
- `evals/context_changes/cases.json`: `decision_superseded` with `at`; `discarded` with `at`; an owner `candidate → decided` flagged `acknowledged`; a world-change supersede reporting `expired` on the old fact via its new `valid_until`; must-stay-silent: a correction does not report `expired`.
- `evals/context/cases.json` (snapshot): `world_time_known` true for a rule-set start, false for the default and for a late capture; a decided decision with an owner trail is `confirmed: true`, and without one it is not.

Each new test is mutation-checked: it fails with its rule reverted.

### 6.2 Real-data shadow check (labels only)

The M8 shadow traces are on in prod. Each Jarvis turn stores the compact snapshot (references and labels, no content) at `agent_tasks.result->'trace'->'context_snapshot'`, and the change list at `…->'context_changes'`. A read-only script `scripts/shadow_context_structure.py` counts labels per day for one tenant, before and after each flag. It reads no memory text and writes nothing. It is run under the D30 rules with a read-only connection, and its output is counts only:

```sql
-- share of memory items with a world time of their own
SELECT date_trunc('day', t.created_at) AS day,
       count(*) FILTER (WHERE (i->>'world_time_known')::boolean) AS world_time_known,
       count(*) AS memory_items
FROM agent_tasks t
CROSS JOIN LATERAL jsonb_array_elements(t.result->'trace'->'context_snapshot'->'items') AS i
WHERE t.tenant_id = :tenant
  AND t.result->'trace'->'context_snapshot' ? 'items'
  AND i->>'ref' LIKE 'memory:%'
GROUP BY 1 ORDER BY 1;

-- relation types (#419) and conflict kinds per day
SELECT date_trunc('day', t.created_at), r->>'type', count(*)
FROM agent_tasks t
CROSS JOIN LATERAL jsonb_array_elements(t.result->'trace'->'context_snapshot'->'relations') AS r
WHERE t.tenant_id = :tenant GROUP BY 1, 2 ORDER BY 1, 2;
-- same shape for ->'conflicts' (c->>'kind'),
-- decision items by status (i->>'ref' LIKE 'decision:%', i->>'status', i->>'confirmed'),
-- and ->'context_changes'->'changes' by c->>'kind' and c->>'acknowledged'.
```

**Expected movement on prod**, compared with the 7 days before each flag:

| Label | Before (Stage 0 / audit) | Expected after |
|---|---|---|
| `world_time_known` share of memory items | ~0 | up, for facts said with a time; the late-capture fix *removes* false `true`s |
| `relations` per turn | 0 | > 0, all `BECAUSE` / `LEADS_TO` |
| conflict kind `supersession` | rare (1 superseded memory) | up |
| conflict kind `pending_contradiction` | as today | up (medium and low tiers), bounded by the cap |
| decision items `decided` / `confirmed` | 0 | only after the owner confirms; never without |
| change kinds `superseded`, `decision_status`, `decision_superseded` | ~0 | > 0, `acknowledged` when the owner made them |

A flag that moves nothing in 7 days, or that moves `pending_contradiction` above the cap, is turned off and reported.

## 7. Constraints check

| Constraint | How the design keeps it |
|---|---|
| Personal data stays local | Rules are pure code. The only model touch is the extraction call that already runs through `chat_local_only` (`llm.py:457`), with two optional fields added to it. The shadow script reads labels on the owner's machine. |
| No cloud models | No new model call. The ingest eval arm runs with the model guard that refuses cloud clients. A locality test patches every LLM constructor to raise and runs world time, supersession, links and transitions. |
| No new memory DB or graph engine | Existing tables and JSONB only. Links go through `links.create_link`. Its best-effort AGE sync (`links.py:381-415`) is unchanged and not relied on. One nullable column. |
| No hardcoded domain enums | No DB enum or CHECK. Slot keys, world-time `precision` and `rule` are strings in JSONB. Link types are the existing `VALID_LINK_TYPES`. Decision status is validated in code against the five documented values, not in the schema. The Tamil word list is data. |
| Inferred never becomes confirmed | Only `require_owner` routes or an owner-stamped review move a decision to `decided`. Auto-keep is excluded. The model can only propose a start date or a `leads_to` that a rule must confirm. Low-tier supersedes are never automatic. External text never supersedes owner facts. A zero-tolerance eval metric pins it. |
| Tenant isolation unchanged | Every write uses `get_current_tenant_id()`. Links check both ends (`links.py:116`). `supersede_decision` gains the missing check on `new_id`. Cross-references in `properties` are read only with a tenant filter. Integration tests use two tenants with the same slot and the same decision titles. |
| Nothing grants execution | Nothing in autonomy, approvals execution or drivers reads decision status, `valid_from` or links. Today's readers are the snapshot, changes, the brief and failure mining. An import-contract test keeps `models.judgment.Decision` out of `autonomy/` and `drivers/`. A confirmed decision is context, not permission (spec §2.2). |

## 8. Build order, rollback, risks

### 8.1 Small PRs (each from `origin/master`, none stacked)

1. **Late-capture world-time fix:** `_as_said` sets `valid_from` too. A bug fix with no flag, plus a test that a late memory has `world_time_known: false`.
2. **`extraction/world_time.py`:** pure rules, English, Tamil and Tanglish, unit tests, and `evals/ingestion_structure` world-time cases. Not wired.
3. **Wire world time:** `store(valid_from=…)`, `properties.world_time`, called from `_process_fact`, `memory_save` and the verbatim store. Flag `ingest_world_time` (default off). Adds the optional `valid_from` model field.
4. **Supersession helper:** one `supersession.apply` replaces the five UPDATEs, with no behaviour change, proven by the existing tests.
5. **World-change end and tiers:** `old.valid_until` on world change, medium/low tiers, daily cap. Flag `ingest_supersession_tiers` (default off).
6. **Typed links:** BECAUSE from `reason`, LEADS_TO with the rule check, optional `leads_to` field. Flag `ingest_typed_links` (default off).
7. **Migration `decisions.superseded_at`:** column and model only. Owner approval needed before merge.
8. **Decision lifecycle:** routes behind `require_owner`, `status` validation, `self`-tier gating of capture decisions, decision↔memory references, the wired `supersede_decision`, the lifecycle trail, and the snapshot/changes readers. Flag `decision_lifecycle` (default off) for the capture gating and the mirror; the owner routes are always on.
9. **Ingest eval arm** in `eval_context_quality.py`, fixtures, new baseline recorded on purpose.
10. **`scripts/shadow_context_structure.py`:** read-only counts.

Then one flag at a time in prod, 7 days of shadow counts each, logged as a decision in the operations log.

### 8.2 Rollback

- **Flags off:** new saves behave as today.
- **World time:** a rule-set row carries `properties.world_time`. A revert script (dry-run first, capped writes, tenant-scoped) sets `valid_from` back to the recorded time for those rows only.
- **Supersession:** each auto-apply has an `applied: true` approval, and rejecting it restores the old fact through the existing undo (`approvals.py:1186-1206`). The undo also clears a `valid_until` the helper set, which carries `properties.valid_until_by = "supersession"` so only those are cleared.
- **Links:** delete by `properties.why LIKE 'extraction:%'`.
- **Decisions:** the trail shows every transition and who made it, so each can be reversed. Migration downgrade drops `superseded_at`.

### 8.3 Risks

| Risk | Mitigation |
|---|---|
| A wrong date: "on Friday" read as past, a month with no year put in the wrong year | Future phrases never give a start. A month without a year is the most recent past one. Precision is stored. The zero-tolerance metric "set where unknown". |
| The Tamil and Tanglish list is incomplete | A miss gives "unknown", which is today's state. The owner reviews the list. A quarter of the eval is Tamil or Tanglish. |
| A date pinned on the wrong fact of a long message | `source_text` is used only with exactly one time phrase in the message. |
| The review queue floods again | Low tier capped at 5 a day, counted beyond that. Shadow checks `pending_contradiction`. Flag off if over. |
| The model invents `leads_to` or a start date | Each needs a rule to agree (a phrase in the text, a cue word). There are no free model links. |
| A world change and a correction mixed up | Only a known new start ends the old fact. A `correction` never does. Undo restores both. |
| Outside text rewrites the owner's facts | External or hostile tiers never supersede `self` facts and make no low-tier items (§5.2). Capture decisions are limited to `self` surfaces. |
| API behaviour change: `POST /decisions` no longer makes `decided` without the owner | Documented in PR 8. Callers get `candidate`, and the response says so. |
| Ingestion latency | Rules are microseconds. Links add at most a few inserts per message. There is no extra model call. |

## 9. Out of scope: a second ADR

Goals, constraints, responsibilities and domains are **not** decided here (audit §5, §6 P2.1–P2.2). Whether they become structured records or labelled memories, how a goal links to projects and tasks, and how domains are assigned as data (not an enum) need their own ADR. That ADR will reuse this one's mechanisms: world time, typed links between records of one message, and owner-only promotion. `EVIDENCED_BY` links from documents also belong there.

## 10. Where the code differs from the audit

Recorded so the next reader does not chase the wrong gap.

1. **"`valid_from` always equals the recorded time."** This is true for on-time saves. For a late capture `_as_said` backdates `created_at` but not `valid_from` (`core/memory_manager.py:326`). `valid_from` is then *later* than the recorded time, and `world_time_known` (`snapshot.py:534-540`) reports a world time that is only the delivery time. Fixed by PR 1.
2. **"Supersession on change needs to be built" (§6 P2.4).** It is built: same-slot replacement (`memory_manager.py:551-554`, `:755-804`), the contradiction detector with value change (`contradiction.py:240-304`, `:780-803`), corrections (`tools/memory_search.py:487-498`) and deferred approval (`approvals.py:1208-1271`). It rarely completes because a clashing fact is never auto-kept (`memory_manager.py:564`, `:948`), so it waits as a pending approval. And no writer ends the old fact's world time. This ADR completes it rather than building it.
3. **"`valid_until` only via /deny" (§5).** The save path does write it from the extractor's `valid_until` (`memory_manager.py:594`, `llm.py:64-70`). Prod shows the model never fills it.
4. **"The decision lifecycle is dead code."** Mostly true: `supersede_decision` has no caller and there is no update route. But `POST /judgment/decisions` creates `decided` rows by default, with `decided_at` set (`models/schemas.py:1067`, `judgment.py:446`), and `status` is not validated. So a caller without the owner can create a "decided" decision today. The brief reads candidates (`brief.py:447-467`). `supersede_decision` also does not check that `new_id` is the tenant's (`judgment.py:530-539`).
5. **Not in the audit:** capture decision detection is not trust-gated (`capture_processors.py:252-266`). Failure mining expects statuses `abandoned` / `reversed` that nothing writes (`failure_mining.py:33`).
