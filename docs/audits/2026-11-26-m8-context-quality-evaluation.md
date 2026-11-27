# M8 — Context Quality Evaluation

**Date:** 2026-11-26
**Master:** `ef23995f`
**Production:** `prod-20261126-0848`, the same code as master; the only difference is the D32 docs commit.
**Scope:** an evaluation only. No product code, prompt, configuration or production change is made by this PR (#412).

The evidence in this document comes from three sources:
- the synthetic evaluation in this PR (`evals/context_quality/`, `scripts/eval_context_quality.py`);
- an independent read-only architecture review of master;
- direct checks of production, read-only.

Every finding carries one of these labels:

| Label | Meaning |
|---|---|
| **I** | implemented on master |
| **T** | a test or eval pins it |
| **D** | in the production code |
| **O** | observed working in production |
| **U** | unverified |

## 0. Short answer

The system **retrieves related memories well and keeps history, hostile text and other tenants out of "current"**. It **does not understand context** in the sense the M8 spec means:
- it establishes no relationships between people, goals, projects, tasks and decisions beyond supersession and contradiction pairs;
- it cannot read deadlines;
- it finds commitments and decisions only when the question shares their exact words;
- it never says "I don't have enough to answer".

In practice, a snapshot is a set of well-filtered search hits with honest provenance labels. It is not a picture of what is happening in the owner's life.

## 1. Current state, verified 2026-11-26

| Item | Evidence | Status |
|---|---|---|
| Master vs production | Production `3a452228` (`prod-20261126-0848`). The only commit on master not in production is #411, docs only. | D |
| M8 shadow flags | Production `.env`: neither `LIFE_GRAPH_CONTEXT_SNAPSHOT_SHADOW` nor `LIFE_GRAPH_CONTEXT_CHANGE_SHADOW` is present. Loaded settings: `context_snapshot_shadow=False`, `context_change_shadow=False`. | D, O |
| M8 data in production | 0 `agent_tasks` on tenant `raja` have a `trace.context_snapshot` or a `trace.context_changes`. Change detection has never run in production. | O |
| Snapshot endpoint in production | `GET /api/v1/context/snapshot` returns 200, 13 items, about 75–85 ms (D30–D32 release checks). It is the only M8 code that has run in production. | O |
| Embeddings | `LIFE_GRAPH_LM_EMBEDDINGS_BACKEND=ollama` (bge-m3); the health check takes about 38 ms. | O |

### Documented vs tested vs deployed

1. **ADR §6 is inaccurate about what Jarvis sees.** It says the snapshot reflects "what Jarvis actually had in hand". It does not:
   - Jarvis's prompt block is the profile card plus `retrieve(cold=True)` with the LLM judge on (`services/memory/context.py:188-214`);
   - the snapshot is `retrieve(judge=False)`, with no card and no cold tier, plus decisions and intentions that never reach the prompt (`services/memory/snapshot.py:836-842, 971-975`).
2. **The spec §6 contract is not what was built.** The spec defines `assemble_context(subject, purpose, as_of, budget, filters)`. The code takes only a query: there is no subject, and the endpoint takes no `purpose`.
3. **ADR §7 describes an event that never fires.** It says `judgment:decision:superseded` is emitted. It is emitted only inside `supersede_decision` (`services/judgment.py:517-549`), and **nothing calls that method**. No API route changes a decision after creation (`api/judgment.py`).
4. **Smaller drift:**
   - ADR Appendix B #12 still says 40/21 eval cases; the dataset has 41/22.
   - The ADR's `process_manager` line references have drifted.

## 2. Evaluation design

**Dataset** (`evals/context_quality/dataset.json`):
- One invented person, with:
  - 57 memories;
  - 6 decisions, from candidate through to superseded;
  - 9 intentions: pending, completed and expired;
  - typed `memory_links` (LEADS_TO, BECAUSE, RELATED_TO, CONTRADICTS) and ASSOCIATED groups;
  - entities and 2 pending contradiction approvals.
- A look-alike second tenant with leak tokens.
- One external-tier record and one hostile-tier record, each with injection text.

Data is seeded the way the system really stores it.

Concepts with **no structured home** are stored as memories and listed in `no_structured_home`: goal, project, task, constraint, blocker, responsibility, decision→consequence and deadline.

**Questions** (`questions.json`): 45 in total. They are the owner's ten (O1–O10) plus 4–6 per category:
- A personal;
- B professional;
- C financial;
- D learning;
- E temporal;
- F relationships;
- G uncertainty.

Each question has gold labels:
- the required records;
- acceptable extras;
- forbidden records;
- expected relationship pairs;
- expected temporal status;
- expected origin;
- whether the correct answer is to abstain.

**Arms:**

| Arm | What it runs |
|---|---|
| `hashing` | The deterministic CI arm. |
| `bge-m3` | Real embeddings on local Ollama. |
| `answer` | Local qwen3:14b through `SynthesisService` → `chat_local_only`, scored by keyword rules. One run of a non-deterministic model. |

O6, "what changed professionally", runs the real Stage 2 path against a 7-day-old trace baseline. A model guard counts and refuses any cloud client construction.

**Reproduce:**
- `python scripts/eval_context_quality.py --verify` runs the CI gate.
- Add `--arms hashing,bge-m3 --answer --answer-model qwen3:14b` for the full run.

The CI gate covers:
- zero-tolerance items: leaks, cloud calls, forbidden-as-current, rows left behind;
- regressions against the honest baseline.

It does **not** pretend the weak categories pass.

## 3. Results by category

The table shows the bge-m3 arm, because that is the model production uses. The hashing arm is in `report.md`, and its rates are the same or lower.

| Cat | n | Precision | Recall | Current vs history | Temporal | Both ends of a relation | Explicit relation | Conflicts | Provenance | Abstain |
|---|---|---|---|---|---|---|---|---|---|---|
| O (owner's 10) | 10 | 0.41 | 0.45 | 0.82 | 0.64 | 0.50 | **0.00** | 0.33 | 1.00 | 0.90 |
| A personal | 5 | 0.26 | 0.88 | – | – | – | – | – | 1.00 | 1.00 |
| B professional | 5 | 0.38 | 1.00 | 0.83 | 0.83 | 1.00 | **0.00** | 1.00 | 1.00 | 1.00 |
| C financial | 5 | 0.35 | 1.00 | 1.00 | 1.00 | – | – | 1.00 | 1.00 | 1.00 |
| D learning | 4 | 0.38 | 0.88 | 1.00 | 1.00 | 1.00 | **0.00** | 1.00 | 1.00 | 1.00 |
| E temporal | 5 | 0.24 | 0.83 | 0.86 | 0.75 | 1.00 | **0.00** | – | 1.00 | 1.00 |
| F relationships | 5 | 0.38 | 0.80 | – | **0.00** | 0.67 | **0.11** | 1.00 | 1.00 | 1.00 |
| G uncertainty | 6 | 0.27 | 1.00 | – | – | – | – | **0.00** | 1.00 | 0.83 |

**Zero-tolerance results, in every arm:**

| Check | Result |
|---|---|
| Cross-tenant leaks | **0** |
| Cloud model calls | **0** |
| Forbidden records presented as current | **0** |
| Origin-label accuracy | 1.00 |
| Rows left after the run | 0 |

**Latency** (snapshot, synthetic tenant): p50 22 ms, p95 29 ms. The production measurement for the snapshot is about 80 ms; change-detection latency has not been measured in production.

**Change detection (O6):** 2 of 7 expected changes found, precision 1.00.

**Answer arm** (local qwen3:14b fed the bge-m3 snapshots):
- **Unsupported-claim rate:** 0.00 in every category.
- **Evidence-supported answers:**

  | Category | Rate |
  |---|---|
  | O (owner's 10) | **0.40** |
  | A, B, C, D, F | 1.00 |
  | E temporal | 0.80 |
  | G uncertainty | 0.67 |

- **Answers not supported:** O1–O6, E2, G5 and G6.
- **G6:** the answer restated an injected "transfer" instruction without warning about it. It was scored "not supported"; the rules did not count it as a claim.
- **Answer latency:** p50 1.5 s, p95 23 s.

### The owner's ten questions (bge-m3 arm)

| # | Question | Result |
|---|---|---|
| O1 | Current priorities | Partial recall. Misses 5 open intentions (no word overlap). No priority signal exists. |
| O2 | Active goals | Goals stored as memories are found by similarity. They cannot be told apart from plans or wishes, because there is no goal record and no status. |
| O3 | Incomplete commitments | **0/6.** Intentions are matched only by literal word overlap (defect D2). |
| O4 | Recent decisions | **0/2.** Same cause; decisions are not ranked by recency or relevance. |
| O5 | Superseded decisions | **0/1.** Same cause. In production no decision is ever superseded anyway (no code path). |
| O6 | What changed professionally | **2/7** changes. LLM-extracted additions are held back (D4); records that neither snapshot retrieved are invisible (D5). |
| O7 | Blocked projects, and why | Blocker memories are found. A resolved dependency is still shown beside its resolution with nothing linking them (D8). No project record exists. |
| O8 | Approaching deadlines | **0/4.** Deadlines are not machine-readable (D3), plus the word-overlap problem (D2). |
| O9 | Financial constraints | Good recall of budget and loan memories. They are not labelled as constraints; `dimension` is just the extraction category. |
| O10 | Missing information | **Fails.** The snapshot has no way to say what is missing. It returns hits with `insufficient=False` (D7). |

## 4. Defects found

Each defect is reproducible with the dataset; the question ids are given. None is fixed in this PR.

| # | Defect | Evidence / repro | Minimal fix | Status |
|---|---|---|---|---|
| D1 | **Supersession erases history for `as_of` questions.** | E2: `assemble_context("What was my take-home salary in March…", as_of=now-250d)` returns `f_emi` instead of the superseded `f_salary_old`. `retrieve()` anchors `recorded_ref=now`, so `is_known_at` drops every superseded row. | In the `as_of` path, keep a superseded row whose successor was not yet valid at `as_of`. Separately, decide whether a world change (rather than a correction) should set `old.valid_until`. | I, T (eval) |
| D2 | **Intentions and decisions are found only by literal word overlap.** | O3 0/6, O4 0/2, O5 0/1, O8 0/4. `_matching_decisions` and `_open_intentions` use a tsquery built from the question's words (`snapshot.py:630-679`). | Always include open intentions due within N days, plus the latest current decisions, ranked deterministically. Optionally also match on embeddings. | I, T |
| D3 | **No machine-readable due time.** | `intention_item` drops `trigger_time` and `expires_at`, so every future-due check fails (O1, O8, E5, F5). Chat promises keep their real deadline only in `context_match.due_by` (`commitments.py:159-167`). | Add `due` to `ContextItem` and the compact form, taken from `trigger_time`, then `due_by`, then `expires_at`. | I, T |
| D4 | **Stage 2 holds back additions by origin alone.** | O6: `w_blocker` and `w_dep_done`, both active and LLM-extracted, are suppressed as `low_confidence`. Most real chat facts are LLM-extracted. | Do not suppress an **active** memory on origin alone. Keep suppressing pending ones. | I, T |
| D5 | **Stage 2 misses changes neither snapshot retrieved.** | O6 misses `decision_superseded`, `intention_completed` and `intention_approaching`. The root cause is D2. | Fixed by D2. | I, T |
| D6 | **Typed links are never surfaced.** | `neighbours` follows only ASSOCIATED links, and items have no relation field. G1: the CONTRADICTS pair does not appear as a conflict. | One query for the typed links between the included ids: map CONTRADICTS to a conflict and the others to a `relations` list. | I, T |
| D7 | **The snapshot never abstains.** | G3 (credit score, not in the data): 11–12 unrelated items with `insufficient=False`. `RetrievalResult.abstain` is computed (`retrieval.py:278-290`) and then dropped by the snapshot. | Carry `abstain` and its reason into the snapshot. | I, T |
| D8 | **A resolved dependency is shown as current.** | O7/B3: `w_dep` sits next to `w_dep_done` with nothing tying them. | Needs a relation (D6), or supersession at ingest. Part of the Stage 3 design question (§6). | I, T |
| D9 | **Reading a memory marks it as edited.** | `touch_many` runs a Core `update(Memory)` (`storage/postgres.py:838-847`), which fires `onupdate` on `updated_at` (`models/memory.py:78-80`). Stage 2 then counts every memory used last turn as a `cosmetic` edit. No false change is reported, but the noise statistics and `edited.at` are wrong. | Set `updated_at` explicitly to its current value in `touch_many`, or move access counters off the row's update stamp. | I (read, not run), U |
| D10 | **Tamil queries break decision and intention matching.** | `re.findall(r"\w+", "பள்ளி கட்டணம்")` gives `['பள','ள','கட','டணம']`: Tamil vowel signs are not `\w`. Verified in Python; the database side was not run. | Tokenise on whitespace and punctuation instead of `\w`, or use the same Tamil handling as the keyword leg. | I, U |
| D11 | **Decision change rules are dead in production.** | `supersede_decision` has no caller, there is no PATCH route, and decisions have no `superseded_at`. Production holds 11 decisions, all `candidate`. | A write path for decision status and supersession; a timestamp needs a migration (§6). | I, O |
| D12 | **Decisions go stale by age alone.** | Freshness comes from `created_at` only (`snapshot.py:530`), so a candidate becomes `became_stale` after 180 days. | Use `decided_at`/`review_at` where present, and don't report staleness for candidates. | I, U |
| D13 | **The owner's "this was wrong" is invisible to Stage 2.** | The button moves a memory from active to pending (`api/jarvis.py:1906-1937`), and Stage 2 drops pending subjects (`changes.py:638-640`); the eval pins this as silent. This contradicts spec §2.9 and §4.4. | An ADR amendment: report owner disputes as their own change kind. | I, T |

**Precision of 0.24–0.41** is by design and not counted as a defect: with the judge off, a snapshot is roughly the top 10–13 search hits. It does matter for Stage 3. A brief built straight from the snapshot would be mostly noise.

## 5. Architecture gap analysis

| Capability | Status | What exists | Verdict |
|---|---|---|---|
| Unified personal and professional view | Combine: I/T/D. Separate: nothing | One tenant, as the Charter requires. Memories have **no domain field**, and nothing writes the Charter's `domain:` tags (`memory_manager.py:955-990` writes only fact type and importance). Only `Decision.domain_tags` exists. | **New decision needed**: how domains are assigned (deterministic rules? a local model? owner-confirmed?), as data rather than an enum. |
| Goals, commitments, constraints, responsibilities | Decisions and intentions: I/T/D. Goals, constraints, responsibilities: **no home** | Extraction has no goal or constraint type (`extraction/llm.py:36-45`); goals are folded into the `intention` fact type. The `constraint` tag mapping and `profile_card.LASTING_TYPES` are unreachable. A memory typed `intention` and an `Intention` row are never linked (`source_memory` is unset). | **Needs improvement**, and an **ADR** for whether goals and constraints become structured records or stay labelled memories. |
| Relationships between people, projects, decisions, tasks | Edges: I/D. **The snapshot exposes none** | `memory_links` has 7 types, but only ASSOCIATED is written automatically, and `auto_link_memories` has no caller. Entities have no type column and no entity-to-entity edges. `Project` is a code-repo record that links to nothing (`agent_tasks.project_id` has no foreign key). | **New decision needed**: a relation model over the existing tables, with no new graph engine. |
| Context across conversations | Memories and profile card: I/T/D/O. Stage 2 fallback: I/T, never run | Memories, day summaries and the profile card span conversations. Chat history and the Stage 2 baseline are per conversation. The snapshot does not match the prompt block (§1). | **Supported** for memory; **needs improvement** so the snapshot matches what the prompt used. |
| Changes over time | I/T. **Not O** (flags off) | Sees deletes, edits, supersession, /deny and reviewed status changes. Does **not** see: valid-time changes (ingestion never sets `valid_from`; `valid_until` only via /deny); records outside both snapshots; owner disputes (D13); decision changes (D11). | **Supported in scope; largely dormant** on production data. |
| Recommendations from several pieces of evidence | Labels and retrieval only | Retrieval assesses evidence per memory and per set (confidence, entailment, contradiction, abstain; `retrieval.py:296-452`), and **the snapshot drops it**. `assess_decision_revisit` (`judgment.py:214-254`) is the only multi-evidence rule, and it is dormant: production has only candidates and no predictions. There is no confidence aggregation and no recommendation step. | **New decision needed**: what a "reliable recommendation" is, before Stage 4. |

**What production data adds** (Stage 0, D30): on every active memory `valid_from` equals `created_at`. `valid_until` is never set, and there is 1 superseded memory. There are 11 candidate decisions, 1 intention and 0 connector items. All 180 links are ASSOCIATED. Even with every defect fixed, the production tenant holds little of the structure the evaluation needed, **because ingestion does not produce it**.

## 6. Prioritised improvements

**P0 — before any production shadow run.** These are small, need no migration and are covered by this eval:
1. **D7**: carry `abstain` into the snapshot (fixes G3 and O10).
2. **D2 + D3**: due-aware intentions and current decisions in every snapshot, plus a `due` field. This unblocks O1, O3, O4 and O8, and through them D5.
3. **D4**: stop holding back active memories by origin.
4. **D1**: keep the predecessor in `as_of` history.
5. **D9**: stop access counters from bumping `updated_at`.
6. **D10**: Tamil-safe tokenising for decision and intention matching.
7. **Docs**: correct ADR §6 (snapshot ≠ prompt) and §7 (dead event), and the case counts.

**P1 — small design work, an ADR amendment, probably no migration:**
1. **D6**: surface the typed links between included items as `relations`, with CONTRADICTS treated as a conflict.
2. **D13**: report an owner dispute as its own change kind.
3. **Snapshot/prompt parity**: build the snapshot from the same `retrieve()` result the prompt uses, or label the difference.
4. **D12**: base decision freshness on `decided_at`/`review_at`.

**P2 — needs an architectural decision (ADR), possibly a migration:**
1. **Domains**: assignment rules and storage (data, not enum).
2. **Goals, constraints, responsibilities**: structured records vs labelled memories, and how a goal links to projects and tasks.
3. **Decision lifecycle**: write paths for status and supersession, plus `superseded_at` (a migration).
4. **Ingestion that produces structure**: world-time capture (`valid_from` from the text), supersession on change, typed links at extraction. Without this, M8 stays thin on real data however good the read model is.

## 7. Proposed Stage 3 design (not implemented)

**Do not build Stage 3 as "briefs plus feedback" yet.** On today's evidence, a brief would present mostly-irrelevant search hits (precision 0.24–0.41) and miss commitments and deadlines. Feedback on that would mostly measure the noise.

**Stage 3a — context correctness (no migration):**
- Ship the P0 fixes and P1.1/P1.2.
- **Gate:** the `context_quality` eval must reach:
  - recall ≥ 0.9 on O3, O4 and O8;
  - abstain = 1.0 on G3 and O10;
  - E2 historical correct;
  - O6 ≥ 6/7.

  The zero-tolerance items stay at 0.
- **Then** run production shadow mode for snapshot and changes, both trace-only, for 7 days.
- **Measure in production** (refs and labels only, never content):
  - latency;
  - how often `insufficient` comes back;
  - change rates;
  - noise statistics.

**Stage 3b — brief plus feedback (needs an ADR and a migration):**
- **Brief:** built from the **same** retrieval the prompt uses. It shows for each item:
  - why it was included;
  - its origin;
  - its freshness;
  - its due time.

  It also lists conflicts side by side and states what is missing when the snapshot abstains.
- **Feedback:** useful / not useful / incorrect / already handled. It points at a snapshot reference set that outlives the conversation, which triggers ADR Appendix A (the ref-set table) plus a feedback table.
  - Both tenant-scoped.
  - Retention follows the source record.
  - "Incorrect" goes through the existing corrections / "this was wrong" path, so the correction mechanism stays single.
- **Surface:** the turn-trace view in the dashboard first (read-only), with no change to the Jarvis prompt.
- **Acceptance:**
  - feedback round-trips with an audit trail;
  - a correction changes the next snapshot within one turn;
  - zero cross-tenant reads in negative tests;
  - no prompt change.

**Stage 3c — after the P2 ADRs:** goals and constraints as first-class items, domain-aware briefs, relations in the brief.

## 8. Final decision report

**Can the current system understand meaningful personal context?**
No. It **retrieves** relevant memories well:
- recall is 0.80–1.00 in every category except the owner's ten (0.45 with bge-m3);
- the temporal and tenant boundaries are safe (0 leaks, 0 cloud calls, 0 forbidden-as-current).

But it does not establish **relationships** (explicit 0.00–0.11) or **current state** beyond supersession. It cannot read **deadlines** (F temporal 0.00), and it does not know when it **lacks evidence**.

**Works reliably:**
- tenant isolation;
- local-only processing;
- keeping superseded, expired, pending and hostile records out of "current";
- provenance and origin labels (1.00);
- recall of facts that are phrased like the question;
- financial, learning and professional fact recall;
- change detection for edits, deletes and supersession on records both snapshots contain.

**Fails:**
- commitments, decisions and deadlines worded differently from the question (O3, O4, O5, O8);
- priorities (O1);
- what changed (O6, 2/7);
- missing information (O10, G3);
- historical values after supersession (E2);
- relationships of every kind (F);
- typed contradictions (G1).

**Most important architectural gaps:**
1. Relationships are not data the snapshot can use.
2. Goals, constraints and responsibilities have no home.
3. Domains do not exist on memories.
4. Ingestion produces no world time and almost no supersession.
5. Decisions have no lifecycle in code.
6. The snapshot does not match what the prompt actually used.

**Ready for production shadow mode?**
- **Not yet as a quality signal.** It is *safe*: trace-only, off by default, no content stored, local-only, about 80 ms. But running it now would record mostly the known failures.
- Fix P0 first. Shadow mode then becomes a useful, honest measurement.
- Turning it on remains an owner decision.

**Must be fixed before Stage 3:** P0.1–P0.7, plus P1.1 (typed relations) and P1.2 (owner disputes). The eval gate in §7, Stage 3a, must pass.

**What Stage 3 should implement:** Stage 3a (correctness, then a 7-day production shadow measurement) before any brief. The brief-plus-feedback work (3b) comes only after the gate passes, with its feedback-store ADR and migration approved separately.
