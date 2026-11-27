# ADR: M8 Stage 2 — context change detection (snapshot comparison)

**Status:** Accepted 2026-11-26 (#397); option (a) built in Stage 2, see Appendix B. The ADR itself is design only.
**Spec:** [docs/specs/personal-context-intelligence.md](../specs/personal-context-intelligence.md) §4.4, §5, §7, §8, §9 Stage 2
**Builds on:** Stage 0 report [docs/audits/2026-11-26-m8-stage0-context.html](../audits/2026-11-26-m8-stage0-context.html) (§5, §11); Stage 1 code `life_graph/services/memory/snapshot.py` (#393); operations log D30 in [docs/operations-log/2026-11-19-runtime-rollout.md](../operations-log/2026-11-19-runtime-rollout.md)
**Baseline:** `origin/master` `da4fe05b`

## 1. Problem

Stage 1 can say "here is what Life Graph holds that bears on this question". It cannot say "here is what **changed** since the last time we looked". The spec (§4.4) asks for exactly that: a goal or commitment added or completed, a deadline coming up or missed, a decision superseded, a fact gone stale. Each change must carry its evidence, the comparison window and a reason. It must not be noisy.

Stage 2 adds the comparison. It stays internal and read-only: nothing is shown to the owner, no notification is sent, the prompt does not change.

## 2. Constraints

1. **Derived read model.** A change is computed from existing records (memories, decisions, intentions, approvals). It is never a new fact, and nothing reads a change as truth about the owner.
2. **No competing fact store.** Whatever is kept about an earlier snapshot is references, labels and fingerprints only. No content, no summaries, no "current state" table.
3. **Tenant isolation.** Every read, every stored reference and every event is scoped to one tenant. A previous snapshot of tenant B can never become tenant A's baseline.
4. **Local only.** No model call at all. Comparison is plain code over rows. The only model touch stays the one local query embedding Stage 1 already makes.
5. **Deterministic rules.** Same baseline, same rows, same clock: byte-identical result. No LLM decides whether something "really" changed.
6. **Internal / read-only first.** Output goes to the turn trace and the eval script only.
7. **Deduplication.** One real change is reported once, not once per turn and not once per hop of a chain.
8. **No proactive output yet.** Stage 4 decides delivery. Stage 2 only produces the list.

## 3. What exists today (facts)

- **Stage 1 snapshot** (`snapshot.py`). Items are references (`memory` / `decision` / `intention` + id) with status, origin, confirmed, evidence, freshness and reason. Conflicts are pairs of references. `compact()` drops content and the query. It also drops `reference_time` and each item's `recorded_at`, and has no content fingerprint, so today's compact form alone cannot tell an edit from no change.
- **Shadow hook** (`kernel/process_manager.py:840-854`, `:962-963`). On a personal, local Jarvis turn, when `settings.context_snapshot_shadow` is on, the compact snapshot is stored at `agent_tasks.result.trace.context_snapshot`. The flag is **off and not set in prod** (D30). So prod has **no stored snapshots** today.
- **Turn traces already hold memory snippets.** `services/turn_trace.py` `build_trace` keeps `memories[].snippet` for the memories put in front of the model. A fingerprint in the same trace adds no new kind of exposure.
- **Lookup is cheap.** `agent_tasks` has `ix_agent_tasks_session (session_id)` and `ix_agent_tasks_created_desc (tenant_id, created_at)`; `services/chat_turn.py` `load_chat_history` already reads a conversation's earlier turns by tenant and session.
- **Prod data is thin** (Stage 0 §2, §5). On every active memory `valid_from == created_at`, and `valid_until` is never set. There is 1 superseded memory, 11 decisions (all `candidate`), 1 intention and 0 predictions. Supersession is the only working temporal signal.
- **Row timestamps that exist:** memory `created_at`, `updated_at`, `last_reinforced`, `properties.superseded_at`, `properties.review.at` (only when a reviewer is named); decision `created_at`, `decided_at`, `review_at`, `reviewed_at` (no superseded-at time); intention `created_at`, `triggered_at`, `completed_at`, `expires_at`, `trigger_time`; approval `created_at`, `resolved_at`.
- **What leaves no trace:** a memory hard delete (`storage/postgres.py:423-443`), an in-place content edit (`MemoryUpdate.content`; no history), a memory archive or reject without a named reviewer, a decision status change (status overwritten in place).
- **Events** (`core/events.py`): see §7. In short, no memory-change event is emitted except `MEMORY_PENDING`, `MEMORY_APPROVED` and `MEMORY_REJECTED`; `MEMORY_UPDATED` and `MEMORY_DELETED` are defined but never emitted, and nothing guarantees `tenant_id` in a payload.

## 4. Decision (summary)

1. Add a pure function `compare_context(previous, current)` with the rules in §5.
2. **Absence is not removal.** A snapshot is "what bears on this query", so an item missing from the new snapshot usually just means a different question. The comparison therefore **re-reads every previous reference by id** (tenant-scoped) and reports a removal or transition only when the source row itself changed. An item that is only "not retrieved this time" is never a change.
3. **The previous snapshot comes from the Jarvis turn trace (option a)**, with the compact form extended by a few fields (no content). **No migration is needed for Stage 2.** A small reference-set table (option b) is designed in Appendix A, but it is **deferred** until a consumer that is not a conversation (daily brief, watcher) needs a baseline.
4. Stage 2 subscribes to **no events**. Comparison is pulled at turn time from row state. New events are listed in §7 for later stages only.
5. Behind its own default-off flag, inside the existing shadow path. Output is a compact change list in the trace: kinds, references and reasons, no content.

## 5. The `compare_context` contract

### 5.1 Inputs

```text
compare_context(previous: Baseline | None, current: ContextSnapshot,
                resolved: dict[ref_key, RowState], now: datetime) -> ContextChangeSet
```

- **`previous` (Baseline)**: the compact snapshot of an earlier turn: `reference_time`, items `{ref, status, fp, rec, freshness, origin, confirmed}`, conflict keys, plus where it came from (`task_id`). `None` means no usable baseline (see §5.5).
- **`current`**: the Stage 1 snapshot just assembled for this turn.
- **`resolved`**: the **live state of every previous reference**, read by id, scoped to the current tenant, in one query per kind (at most 40 ids per snapshot). A reference that is not found, or belongs to another tenant, resolves to `missing`. This read is the only extra I/O. It is done by a small async helper (`resolve_refs`), so `compare_context` itself stays pure and is easy to test.
- **`now`**: the clock, passed in so tests are exact.

### 5.2 Output

```text
ContextChangeSet
  window:      {from: baseline.reference_time, to: current.reference_time}
  baseline:    {source: "turn_trace", task_id, same_conversation: bool} | null
  changes:     [ContextChange]   # sorted by (priority, kind, ref); at most 20
  suppressed:  {reason: count}   # what the noise rules held back
  insufficient: bool             # no baseline, baseline too old, or a read failed
  explanation: str

ContextChange
  kind:        one of the kinds in 5.3
  ref:         "memory:<id>" | "decision:<id>" | "intention:<id>" | conflict key
  evidence:    [ref, ...]        # the rows that prove it (e.g. both sides of a supersession, the approval)
  before:      {status, fp?, freshness?} | null
  after:       {status, fp?, freshness?} | null
  at:          when the row says it happened, if the row has a time; else null
  reason:      short fixed sentence naming the rule, e.g. "status went candidate -> decided"
  origin:      the record's origin label from Stage 1
  acknowledged: bool             # the owner made this change himself (5.4)
  key:         stable dedup key: kind + ref + after-state
```

No content, no query text. `reason` is a fixed template filled with statuses and kinds, never with record text.

### 5.3 Change kinds and their rules

All rules are deterministic. "In window" means `from < t <= to`.

| Group | Kind | Rule (all must hold) | Evidence |
|---|---|---|---|
| Addition | `added` | In `current`, not in `previous`, **and** the row became visible in the window: recorded (`recorded_at`) in window, or became `active` in window (`properties.review.at` in window). | the item |
| Addition (not reported) | `newly_relevant` | In `current`, not in `previous`, but recorded before the window. Counted in `suppressed`, never a change. | — |
| Removal | `deleted` | Previous ref resolves to `missing`. | the previous ref only |
| Removal | `rejected` / `archived` | Previous memory status `active`, live status `rejected` / `archived`. | the item |
| Removal | `expired` | Live `valid_until` (memory) or `expires_at` (intention) is in window. | the item |
| Removal | `discarded` | Decision status went to `discarded`. | the item |
| Removal | `disputed` | *Added 2026-11-27 (D13).* Previous memory status `active`, live status `pending`, and `properties.disputed.at` (written only by the owner's "this memory was wrong", `api/jarvis.py` `memory_was_wrong`) in window. Always `acknowledged: true`. | the item |
| Transition | `superseded` | Previous memory now `superseded` or has `superseded_by`. Reports the newest current memory in the chain. | old + new refs |
| Transition | `confirmed` | Previous `confirmed=false`, live row is active and owner-confirmed. | the item (+ approval if any) |
| Transition | `edited` | Same ref, live fingerprint differs from `fp` (see 5.4, cosmetic edits). | the item |
| Transition | `decision_status` | Decision status changed (`candidate -> decided`, `decided -> reviewed`). | the decision |
| Transition | `decision_superseded` | Decision now `superseded` with `superseded_by`. | old + new decision |
| Transition | `decision_review_due` | A current decision's `review_at` is in window, or will come within 7 days of `to` and did not at `from`. | the decision |
| Transition | `intention_completed` | Intention status went to `completed` (`completed_at` in window if set). | the intention |
| Transition | `intention_expired` | Status `expired`, or `expires_at` passed in window. | the intention |
| Transition | `intention_dismissed` | Status went to `dismissed`. | the intention |
| Transition | `intention_approaching` | Open intention whose `trigger_time` or `expires_at` falls within 48 h of `to`, and did not at `from`. Reported once per threshold crossing. | the intention |
| Conflict | `conflict_appeared` | Conflict key in `current`, not in `previous`, and at least one side was recorded, or its approval created, in window. Otherwise `newly_relevant`. | both sides (+ approval id) |
| Conflict | `conflict_resolved` | Conflict key in `previous`, and a cause is found in the rows: the contradiction approval is resolved (`resolved_at` in window), or one side is now rejected / superseded / deleted. A conflict that is only not retrieved is not resolved. | both sides + approval |
| Staleness | `became_stale` | Ref in both, freshness was `fresh`/`recent`/`aging` at `from` and is `stale` at `to` (Stage 1 classes: 180 days). `aging` is not reported. | the item |
| Staleness | `reconfirmed` | Freshness was `stale` or `aging` and is now `fresh` because the owner reinforced or restated it (`last_reinforced` in window). | the item |

What Stage 2 does **not** detect, by design: a change to a record that is in neither snapshot. Comparison covers what bore on the previous or the current question, not the whole store. That is a whole-store diff, and it belongs to a later consumer (daily brief) with its own baseline (Appendix A).

"Goal / commitment / constraint" kinds from §4.4 have no records of their own (Stage 0 §2). They appear here only through the record behind them: a memory with that `dimension` label, a decision, an intention. The kind names above are about the record, not a claim about the owner's goals.

### 5.4 Noise rules

Applied after the rules above, in this order. Each held-back change is counted in `suppressed` under its reason, so the eval can see them.

1. **Hostile or pending:** a change whose subject is hostile-tier, or a pending memory, is dropped (`hostile`, `pending_only`). Same rule as Stage 1. *Amended 2026-11-27 (D13):* one exception. When the owner presses "this memory was wrong" on a reply, an active memory goes back to review (pending), and that is the owner's own correction, which spec §2.9 and §4.4 say must be seen. It is reported as `disputed` (see §5.3), acknowledged. The signal is deterministic and needs no migration: the endpoint merges `{"disputed": {"at", "task_id", "note"}}` into the memory's `properties` in the same UPDATE that sets `status = 'pending'`, and nothing else writes that key. The marker's `at` must be in the window, so an old marker on a memory that went back to pending some other way stays `pending_only`. Every other way to pending (an approval sent back, a sync) is still dropped. A hostile subject is still dropped first.
2. **Cosmetic edits:** the fingerprint is `sha256(id + "\n" + normalised content)` truncated to 16 hex characters. Normalising means lower case, Unicode NFKC, whitespace collapsed, punctuation and trailing full stops removed. A case, spacing or punctuation edit gives the same fingerprint, so it is not an edit. Tags, importance and `access_count` are not part of the fingerprint. Counted as `cosmetic` only when `updated_at` moved but the fingerprint did not.
3. **Duplicates:**
   - one change per `(kind, ref)` per comparison;
   - a supersession chain `A -> B -> C` inside one window collapses to one `superseded` from A to C;
   - `deleted` wins over every other kind for the same ref;
   - `superseded` wins over `edited`.
   Across turns, the baseline moves forward every turn (§5.5), so a change already reported is part of the next baseline and does not repeat. The `key` lets a later stage drop repeats when two consumers compare different windows.
4. **Low-confidence inference:** an `added` or `edited` item with origin `model_proposed` that is not `confirmed` is held back (`low_confidence`). So is a `candidate` decision appearing. *Amended 2026-11-27 (D4):* an **active** memory is not held back on origin alone. A model that extracts a fact from what the owner said (`extraction_tier` "llm") makes the origin `model_proposed`, and most chat facts are extracted that way. Such a memory is held back only when its evidence is Life Graph's own conclusion (`inferred`, a day `summary`) or is not known. Pending memories, and model-proposed decisions and intentions, are held back as before. Status changes of an authoritative record still count, even if the record was model-proposed: `candidate -> decided` is a real transition.
5. **Already acknowledged:** Stage 2 has no feedback store yet (Stage 3 adds one). Until then, a change is marked `acknowledged: true` when the owner made it himself:
   - a review stamp `by` the owner;
   - a correction he recorded (`corrections` row, `CORRECTION_RECORDED`);
   - a `/deny`;
   - a memory whose `source_session` is this conversation (he just said it).
   Acknowledged changes stay in the list, so the eval sees them, but they are flagged and never count towards a later "notable" list.
6. **Cap:** at most 20 changes, ordered by a fixed priority: removals and supersessions, then status transitions, then conflicts, then approaching or due, then additions, then staleness. The rest are counted as `over_budget`.

### 5.5 The comparison window

- `from` = the baseline's `reference_time`, `to` = the current snapshot's `reference_time`.
- **No baseline:** this is the first turn with a snapshot, or the last stored one is an error. The result is `insufficient: true` with the explanation "no earlier snapshot", and no changes. It is never "everything is new".
- **Baseline too old:** older than 30 days. The result is `insufficient`. Re-reading refs that old would report a month of unrelated edits as one burst.
- **Baseline choice:** the latest earlier turn **in the same conversation** that has a non-error snapshot. Failing that, the latest such turn of the tenant within 30 days, with `same_conversation: false`. The tenant-wide case only reports transitions and removals of its refs plus approaching items. Additions are counted as `newly_relevant`, because the questions differ.
- A regenerated turn uses the same baseline as the turn it replaces, not its own earlier version (as `load_chat_history` does).

### 5.6 Determinism, locality, cost

- `compare_context` is pure: no I/O, no clock read, no model. Sorting is by fixed keys.
- `resolve_refs` is tenant-scoped SQL by primary key, at most 3 small queries (memories, decisions, intentions) plus one for approvals by id. No embedding, no search.
- The baseline lookup is one indexed read on `agent_tasks` (`tenant_id, session_id`, newest first, limit 10, filter for `result->'trace'->'context_snapshot'` present).
- Expected cost: well under 50 ms on prod-sized data. It runs inside the existing 1 s shadow time box and never fails the turn.

### 5.7 Trace shape change (no migration)

`ContextSnapshot.compact()` gains, under a format marker `"v": 2`:
- `reference_time`;
- per item `fp` (the fingerprint above) and `rec` (recorded_at, ISO).

The change list is stored next to it as `trace.context_changes`: `window`, `baseline.task_id`, `changes` without `before.fp`/`after.fp`, `suppressed`, `insufficient`. A v1 trace (no `reference_time`) is not a usable baseline, so it is treated as "no baseline". This is a JSONB shape change only; old readers ignore unknown keys.

## 6. Where the previous snapshot comes from

### Option (a): the Jarvis turn trace only

`agent_tasks.result.trace.context_snapshot` of an earlier turn.

- **Can:** everything in §5.3 for the refs it holds, once `compact()` carries `reference_time`, `fp` and `rec` (§5.7). There is no new table. Tenant scope comes for free: `agent_tasks.tenant_id` is already filtered in every read, and `load_chat_history` shows the pattern. The baseline is the snapshot Life Graph built for Jarvis's last turn, which is the honest meaning of "since last interaction".

  *Correction (2026-11-27, M8 context-quality evaluation, PR #412):* this snapshot is **not** what Jarvis's prompt used. The two are built separately on the same turn:
  - **Jarvis's prompt** gets the owner's profile card plus `retrieve(cold=True)` with the local relevance judge on (`services/memory/context.py`, `_sections`).
  - **The snapshot** is `retrieve(judge=False)`, with no profile card and no cold tier, plus matching decisions and open intentions, which never reach the prompt (`services/memory/snapshot.py`, `_memories`, `_decisions`, `_intentions`).

  So the baseline is "what the snapshot held last turn". The two usually overlap, but a memory can be in one and not the other. Making the snapshot match the prompt, or labelling the difference, is P1 work in the evaluation (§6 there).
- **Cannot:** compare for a consumer that has no turn (daily brief, watcher, project task). It holds nothing while the shadow flag is off; prod has no snapshots today (D30). Its retention is whatever `agent_tasks` has: nothing purges traces, and a deleted memory's id (and, today, its snippet) stays in old traces.
- **Cost:** one indexed read per turn.

### Option (b): a small table of snapshot reference sets

One row per stored snapshot: tenant, subject/purpose key, time, and the refs with labels and fingerprints. No content. Full schema in Appendix A.

- **Can:** give any consumer a baseline by key (`brief:daily`, `project:<id>`, `conversation:<id>`), across conversations. It has its own retention, and deletion follows the source: refs are stripped when their source row is deleted. Purging is cleaner than with traces.
- **Cannot:** anything option (a) cannot for a Jarvis conversation; it adds nothing there. It needs a migration, a repository, a purge job and a delete hook in `storage/postgres.py` before it holds one useful row.
- **Cost:** a migration and its rollback, and a second place where refs live that must be kept in step with deletes.

### Option (c): recompute "as of" the last interaction from bitemporal data, store nothing

Run `assemble_context(query, as_of=T)` for the last-interaction time `T` (taken from `agent_tasks.created_at`), then compare the two snapshots.

What it can and cannot see on today's prod data:

| Change | Detectable by (c)? | Why |
|---|---|---|
| New memory, decision or intention recorded after `T` | Yes | `created_at` / `recorded_at` exist. But since `valid_from == created_at` on every active memory, "valid as of `T`" is the same as "recorded by `T`". Valid-time `as_of` adds nothing over recorded time. |
| Memory superseded after `T` | Partly | `properties.superseded_at` exists (`memory_manager.py:273`, `postgres.py:1302`). Prod has 1 superseded row. |
| Memory hard-deleted | **No** | The row is gone; nothing says it existed at `T`. |
| Memory content edited in place | **No** | No history; the `as_of` view shows today's text. |
| Memory rejected / archived | Only with a named reviewer | `properties.review.at` is set only when `decided_by` is known. |
| Decision status change | Partly | `decided_at` / `reviewed_at` exist. There is no superseded-at time, and `as_of` reads today's status anyway (`_matching_decisions` filters `created_at <= ref` only). All 11 prod decisions are `candidate`, so there is nothing to see yet. |
| Intention completed / expired | Partly | `completed_at` / `expires_at` exist, but `_open_intentions` filters on today's status, so an intention completed after `T` is missing from both sides instead of showing as a transition. |
| Conflict appeared / resolved | Partly | Approval `created_at` / `resolved_at` exist, but `_memory_conflicts` reads only pending approvals, i.e. today's state. |
| Freshness became stale | Yes | Pure function of time. |
| Expired by `valid_until` | In theory | `valid_until` is never set in prod. |

(c) also runs the full search twice per turn. D30 measured 1.3–1.6 s per prod snapshot against a 1 s target, so a second search would roughly double a cost that is already over budget. The `as_of` view is a reconstruction with today's embeddings and today's statuses, not what was actually seen, so it is not deterministic against later edits either. (c) is a useful **cross-check in the eval** (it needs no storage), but it is not a baseline.

### Comparison

| | (a) turn trace | (b) ref-set table | (c) recompute as-of |
|---|---|---|---|
| Migration | none | yes | none |
| Sees deletes and in-place edits | yes (re-read by id + `fp`) | yes | no |
| Baseline = what the last snapshot held (not the prompt, see the correction above) | yes | yes | no |
| Works outside Jarvis conversations | no | yes | yes |
| Extra cost per turn | 1 indexed read + ≤ 4 id reads | same + 1 insert | a second full search (~1.3 s on prod) |
| Retention follows source deletes | no (existing trace gap) | yes, by design | n/a |
| Useful today (shadow off in prod) | not until the flag is on | not until written | yes, but weak |

### Recommendation: (a), with (b) deferred

- Stage 2 is internal and its only consumer is the Jarvis shadow path. For that consumer the turn trace already is the right baseline. It is tenant-scoped, indexed and written every turn. It is the last turn's snapshot, not the prompt itself (see the correction under option (a)).
- With the re-read by id (§5.1) and a fingerprint (§5.7), (a) detects deletes and edits that (c) never can.
- (b) adds no capability for a conversation. It only pays off when a consumer without a turn needs a baseline, which is Stage 4 territory.

**Is a migration genuinely necessary for Stage 2? No.** The work is a JSONB shape change in an existing column plus pure code.

**When (b) becomes necessary.** Any one of these is a trigger for a short ADR amendment and the Appendix A migration:
- a daily-brief or watcher consumer wants "what changed since yesterday" for the tenant as a whole;
- Stage 3 feedback needs to point at a stored snapshot that outlives its conversation;
- trace retention is added to `agent_tasks` and would cut baselines short;
- the owner asks that derived references follow source deletion strictly. Traces do not do this today; this is an existing gap that Stage 1 and the `memories[].snippet` already have.

## 7. Events

**Stage 2 subscribes to no events.** It pulls row state at turn time (§5.1). That is more reliable than events here: most memory changes emit nothing, and the bus is in-process (the Redis bridge only relays to WebSocket clients).

What exists, for the record:

| Event | Emitted? | `tenant_id` in payload | Use for change detection |
|---|---|---|---|
| `memory:pending` | yes (`storage/postgres.py:297`, `cross_system_sync.py:236`) | yes | not needed: pending is reported only as an owner dispute (§5.4 rule 1), read from the row's `properties.disputed` |
| `memory:approved` / `memory:rejected` | yes (`services/memory/transitions.py:169,190`) | yes | could mark a "dirty" baseline later |
| `memory:updated` / `memory:deleted` | **defined, never emitted** | — | would be needed for push or cache invalidation |
| `memory:created` | only for shared context | — | no |
| `judgment:decision:superseded` | **in code only, never fires**: emitted only inside `JudgmentService.supersede_decision` (`services/judgment.py:517-549`), which nothing calls, and no API route changes a decision after it is created (`api/judgment.py`) | yes | covered by re-read, if a write path is ever added |
| `capture:correction:recorded` | yes (`services/capture.py:291`) | yes | covered by re-read (acknowledged rule) |
| `approval:resolved` | yes (`api/approvals.py:163`, `services/approvals.py:1514`) | yes | covered by re-read |
| `contradiction:detected`, `intention:triggered` | defined, not emitted by any caller found | — | no |

**Proposed for later stages only (not built in Stage 2).** These are needed when Stage 4 pushes a change or a cache must be invalidated. Each payload carries `tenant_id`, the record `id`, `old_status`, `new_status` and `at`, and never content:
- `memory:superseded` (`id`, `superseded_by`);
- `memory:deleted` (emitted by `PostgresMemoryStore.delete` after commit);
- `memory:updated` (emitted only when the fingerprint changes, so cosmetic edits stay silent);
- `intention:status` (`completed` / `expired` / `dismissed`).

## 8. Test and evaluation plan

### Unit tests (pure, `tests/unit/test_context_changes.py`)

One table-driven case per kind in §5.3 and per noise rule in §5.4, with a positive case and a near-miss negative case each. Among them:
- an item missing from `current` but unchanged in `resolved` gives no change (absence is not removal);
- `newly_relevant` is never reported;
- a whitespace, case or punctuation edit gives no `edited`; a word change does;
- a chain `A -> B -> C` gives one change;
- `deleted` beats `edited`;
- a `model_proposed` addition is held back, but `candidate -> decided` is reported;
- an owner correction is flagged `acknowledged`;
- the cap holds at 20, in priority order;
- running the comparison twice on the same input gives byte-identical output;
- a moved baseline does not repeat the change;
- `insufficient` results: no baseline, a v1 trace, a baseline over 30 days old, a resolve failure.

### Integration tests (`tests/integration/test_context_changes_pg.py`, unique tenant ids)

- `resolve_refs` against real rows: delete, reject, supersede, decision supersede, intention complete.
- Baseline lookup picks the same conversation first, skips error traces, and skips the turn being regenerated.
- **Tenant negative tests:**
  - tenant A's baseline lookup never returns tenant B's task, even with B's `session_id`;
  - a ref id of tenant B inside A's baseline resolves to `missing` and is reported as a plain `deleted` with no B data, never as B's live state;
  - a run with no tenant context raises.

### Locality test (`tests/unit/test_context_changes_locality.py`)

Patch every LLM client constructor to raise. Comparison and resolve run, including DB-failure paths, with zero constructions and zero embedding calls beyond Stage 1's single one.

### Synthetic eval (`evals/context_changes/cases.json`, `scripts/eval_context_changes.py --verify` in CI)

At least 60 labelled scenarios built on throwaway tenants:
- 40 **must-detect**, at least 2 per kind;
- 20 **must-stay-silent**: cosmetic edits, a duplicate event, a different question on unchanged data, an inferred (model-concluded) addition, an owner's own correction (flagged, not notable), a hostile-tier edit, a two-tenant leak attempt.

The report shows each kind and each noise category separately (spec §8), with option (c) as a side-by-side "what as-of recompute would have found" column for the record. No prod data leaves the machine; no cloud evaluator.

### Acceptance criteria

| Measure | Target |
|---|---|
| Missed changes on must-detect cases | 0 of 40 (recall 100%), every kind covered |
| False positives on must-stay-silent cases | 0 of 20 |
| False positives overall (changes not in the label set) | ≤ 5% of reported changes |
| Repeats after the baseline moves (dedup) | 0 |
| Changes without evidence refs and a reason | 0 (100% coverage) |
| Cross-tenant refs or data in any result | 0 in all negative tests |
| Model clients constructed | 0, including failure paths |
| Determinism | byte-identical output on repeat runs |
| Comparison latency (baseline read + resolve + compare) | p95 ≤ 50 ms synthetic; ≤ 150 ms on the prod tenant (read-only measurement) |
| Turn latency with the change flag on vs off | no growth beyond noise; shadow stays inside its 1 s box |

Each test is mutation-checked: it fails with its rule reverted.

## 9. Rollout

1. One PR: `compare_context`, `resolve_refs`, the trace v2 fields, the baseline lookup, tests and the eval. A new setting `context_change_shadow: bool = False` only has effect when `context_snapshot_shadow` is also on.
2. Shadow mode stays off in prod until the D30 latency miss (1.3–1.6 s vs 1 s) is explained, as D30 already requires. Turning both flags on in prod is a separate, logged decision.
3. No endpoint, no UI, no prompt change. A read-only inspection endpoint can be added later with the same auth as `GET /api/v1/context/snapshot` if the eval needs it.

## 10. Risks and rollback

| Risk | Mitigation |
|---|---|
| A different question reads as "things changed" | Absence is not removal (§4.2); `newly_relevant` is never reported; tenant-wide baselines report no additions |
| Thin prod data makes the feature look empty | Expected: 1 supersession, 11 candidate decisions, 1 intention. The eval is synthetic. `insufficient` and empty results say so plainly |
| Fingerprint seen as content | 64-bit, salted with the record id, kept only in the trace next to the existing snippets, never in the change list or an API; listed in the deletion gap below |
| Old traces keep refs of deleted records | Existing gap (Stage 1 and `memories[].snippet`). A deleted ref only ever resolves to `missing`, so it is never resurfaced. Strict deletion is a trigger for option (b) |
| Turn latency | Pure code + ≤ 5 indexed reads, inside the existing time box; measured before any prod flag change |
| Rules drift towards "smart" (LLM) judgement | Rule set fixed in this ADR; any model step needs an ADR amendment and `chat_local_only` with a locality test |
| Change list treated as permission to act | No consumer acts on it in Stage 2; Stage 4 stays recommendation-only through existing approvals |

**Rollback:** turn `context_change_shadow` off (it is off by default), and behaviour is exactly as today. Reverting the PR removes the code. The v2 trace fields stay in old rows and are harmless, since nothing else reads them. There is no migration to undo.

## 11. Open questions for later stages

- Stage 3: the feedback store ("already handled", "not useful") will replace the "owner made it himself" approximation of `acknowledged`, and may itself be the trigger for option (b).
- Should `agent_tasks` traces get a retention period? That would also close the snippet gap. It is a separate decision, not part of M8.

## Appendix A: deferred schema for option (b)

Not part of Stage 2. Pre-agreed here so that, when a trigger in §6 fires, the amendment only has to confirm it.

**Table** `life_graph.context_snapshot_refs` (schema-qualified explicitly, because of the `"$user"` search_path issue noted in D30):

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK, default `gen_random_uuid()` | |
| `tenant_id` | `varchar(64) NOT NULL` | always from the request contextvar, never from input |
| `subject_key` | `varchar(120) NOT NULL` | `CHECK (subject_key ~ '^[a-z_]{1,20}:[A-Za-z0-9_-]{1,96}$')`, e.g. `conversation:<uuid>`, `brief:daily`, `project:<uuid>`; never query text |
| `purpose` | `varchar(32) NOT NULL` | one of `snapshot.PURPOSES` (checked in code; no DB enum) |
| `reference_time` | `timestamptz NOT NULL` | the snapshot's reference time |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `expires_at` | `timestamptz NOT NULL` | `created_at + 30 days` |
| `format` | `smallint NOT NULL DEFAULT 1` | |
| `ref_keys` | `text[] NOT NULL` | `kind:id` of every item and conflict side, for delete lookup; `CHECK (cardinality(ref_keys) <= 128)` |
| `items` | `jsonb NOT NULL` | `[{ref, status, fp, rec, freshness, origin, confirmed}]`; `CHECK (jsonb_array_length(items) <= 64)` |
| `conflicts` | `jsonb NOT NULL DEFAULT '[]'` | `[{kind, refs}]` |
| `source_task_id` | `uuid NULL` FK `agent_tasks(id) ON DELETE SET NULL` | |

No content, no query, no summary columns. Review rule: a PR adding any text column to this table is refused.

**Indexes:**
- `ix_csr_tenant_subject_created (tenant_id, subject_key, created_at DESC)`: the baseline lookup;
- `ix_csr_expires (expires_at)`: the purge;
- `ix_csr_ref_keys` GIN on `ref_keys`: delete and correction propagation.

**Retention and deletion:**
- Keep the newest 5 rows per `(tenant_id, subject_key)`. Older rows are deleted in the same transaction as each insert.
- A nightly purge deletes rows with `expires_at < now()`.
- On a memory hard delete (`PostgresMemoryStore.delete`), the ref is stripped from `items`, `conflicts` and `ref_keys` of that tenant's rows, in the same transaction; a row left with no items is deleted. A reject, archive or correction does not strip: the ref then resolves to its new status, which is the change being detected.
- Deleting a tenant deletes its rows.

**Tenant-isolation tests:**
- two tenants with the same `subject_key`: each lookup sees only its own rows;
- an insert takes `tenant_id` only from the contextvar, and a call with no tenant raises;
- tenant A's purge and delete hook leave tenant B's rows untouched;
- a GIN lookup for B's ref from A returns nothing;
- the repository is the only writer (import contract).

**Migration and rollback:**
- Alembic `063_context_snapshot_refs`: create the table and the 3 indexes; no backfill; no other table touched.
- `downgrade()` drops the indexes and the table. Rows are derived and can be lost without losing any fact.
- Rollout behind a default-off flag. Rollback is flag off, then downgrade.

## Appendix B: as built (Stage 2, 2026-11-26)

Option (a) was built as decided: `life_graph/services/memory/changes.py`, the trace v2 fields in `snapshot.py`, the `context_change_shadow` setting (default off, effective only with `context_snapshot_shadow`), the eval `scripts/eval_context_changes.py` over `evals/context_changes/cases.json` (41 must-detect, 22 must-stay-silent) and its CI step. No migration, no table, no event. Where the build differs from the text above, and why:

1. **What is re-read.** `resolve_refs` reads the refs of both snapshots and of their conflict sides, plus the approvals of both (§5.1 says "every previous reference"). An addition needs the row's review stamp and who saved it; a conflict needs its sides' and its approval's times; a hostile side must be dropped. Still one query per kind.
2. **Chains.** A supersession chain is followed by up to 3 extra memory reads (`CHAIN_HOPS`), only when a chain exists. The usual case stays at ≤ 4 reads.
3. **Baseline lookup.** One read of the current turn, one of the conversation's last 30 top-level turns (all statuses, no JSON filter, so a regeneration chain through a failed version is still seen), and the tenant-wide fallback only when the conversation has no usable baseline. §5.6 said "one indexed read".
4. **Compact v2 also keeps** `sources` (so a failed snapshot, which has none, is never a baseline, while an empty but successful one is) and, per conflict, its sides' `statuses` and `approval` id (needed for `conflict_resolved`: "a side is now rejected/superseded" means "and was not before").
5. **One kind for an intention's expiry.** The table lists both `expired` (memory `valid_until` or intention `expires_at`) and `intention_expired`. An intention gets only `intention_expired`; `expired` is for memories.
6. **"Acknowledged" signals.** A `corrections` row names no memory id, and a memory has no `source_session`; `Intention.source_session` points at memory sessions, not conversations. So: a review stamp by the owner (`owner`, `owner:*`, `phone:*`, the api/approval_identity labels); a replacement tagged `correction` (memory_save and the memory page) or with source type `reinforcement` (a /deny replacement); a /deny itself (`valid_until` equal to `superseded_at`, set only by `deny`); a memory whose `properties.task_id` is a turn of this conversation; an approval resolved by the owner. `confirmed` and `reconfirmed` are always the owner's own act and are flagged.
7. **Duplicates across groups.** A `conflict_appeared` / `conflict_resolved` for a supersession that a `superseded` / `decision_superseded` change already reports is held as `duplicate`, as is the newer memory of the chain appearing as `added`. A conflict seen first through a baseline from another conversation is `newly_relevant`.
8. **Time box.** The comparison runs in what is left of the snapshot's 1 s box; with nothing left it records `{"error": "TimeoutError"}` without running.
9. **Defensive insufficient.** A baseline whose reference time is not earlier than this turn's is `insufficient`.
10. **"Acknowledged" covers memory changes only.** Decision and intention changes the owner made himself (deciding, completing, dismissing) are not flagged yet; Stage 3's feedback store is the place to add them.
11. **Failed comparisons and temporary chats (review of #405).** A turn whose own comparison failed (an error entry, or `read_failed` after a failed re-read) is skipped as a baseline, so the next window reaches back to the last turn whose comparison went through and no change is lost. A turn with no `context_changes` at all (the change flag was off) is a baseline: nothing was promised for it. A temporary chat's turns, and any turn of a conversation marked temporary, are never a baseline. `intention_approaching` needs the time to be still ahead at the end of the window.
12. **Eval method.** Snapshots are built from the seeded rows with Stage 1's own item builders, not by `assemble_context`, so the eval measures comparison, not retrieval, and needs no embedder. The option (c) column is the ADR §6 table, per kind, not a run. Latency p95 is gated at 50 ms; the ≤ 150 ms prod measurement is still to do (no prod access in the build).
13. **Low confidence by evidence, not origin (D4, 2026-11-27).** Rule 4 is amended as noted in §5.4: an active memory that a model extracted from the owner's words is reported as `added` or `edited`. The eval case `model-proposed-addition` (an active, LLM-extracted memory, which the amended rule reports) became `inferred-addition` (source `distillation`, evidence `inferred`); `llm-extracted-addition` and `llm-extracted-edit` (must detect) and `model-proposed-pending-addition` and `inferred-edit` (must stay silent) were added: 43 must-detect, 24 must-stay-silent.
14. **Owner disputes (D13, 2026-11-27).** A new kind, `disputed` (removal group, priority 0), as amended in §5.3 and §5.4 rule 1. `RowState.disputed_at` is read from `properties.disputed.at`. The eval case `sent-back-to-review` (an active memory set to pending: how the eval pinned the owner's dispute as silent) now carries the endpoint's marker and must be detected, as `owner-disputed` (`acknowledged: true`). `owner-disputed-other-conversation` (must detect) was added, so the kind has the two cases every kind needs. The old case without the marker stays silent as `sent-back-to-review-no-marker`, and `disputed-before-the-window` (must stay silent) was added: 45 must-detect, 25 must-stay-silent.
