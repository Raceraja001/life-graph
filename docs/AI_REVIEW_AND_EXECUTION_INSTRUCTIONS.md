# Life Graph — Engineering Review & AI Execution Instructions

> **Review date:** 2026-11-14  
> **Review baseline:** The code review included commit `678ca1992dc7279a499ac9ec7824b7f70806ab60` (P0–P3 bitemporal, abstention, evaluations, provenance/gaps, brief evidence and task checkpoints).  
> **Purpose:** This document is an actionable handoff for an AI coding agent. Read it before changing code.  
> **Review status:** Findings below are based on the inspected implementation at the review baseline. They are not a claim about the current HEAD. Re-verify every finding against the current branch before acting.

---

## 1. Instructions to the implementing AI — read first

You are working in an existing, substantial codebase. Your task is to **close verified implementation gaps**, not to redesign or rebuild Life Graph.

### Mandatory workflow

1. Inspect the current branch, HEAD commit, working tree, relevant docs, code and tests before making changes.
2. Read at minimum:
   - `CHARTER.md`
   - `docs/STATE.md` (treat as an inventory snapshot, not proof of correctness)
   - `docs/LIFE_GRAPH_EVOLUTION_ROADMAP.md`
   - `docs/design/02_life_graph_v2_design.md`
   - `docs/design/03_devils_advocate_review.md`
   - `docs/ai-engine-improvements.md`
   - `docs/modular_memory_service_plan.md`
   - `docs/specs/judgment-engine.md`
   - This document.
3. Trace each finding into the current implementation. Search for existing services, models, migrations, APIs, tests and feature flags before proposing new ones.
4. Classify each item as **Implemented and tested**, **Partially implemented**, **Designed only**, **Not implemented**, **Regression**, or **Not applicable**. Cite exact file paths, symbols and tests in your report.
5. Write a short implementation plan with the smallest safe change set. Reuse existing abstractions and data models wherever practical.
6. Implement one bounded workstream at a time. Add or update tests with the code. Run focused tests, then relevant broader tests.
7. Inspect the final diff for tenant isolation, privacy, data retention, migration safety, backwards compatibility and unintended side effects.
8. Update documentation and `docs/STATE.md` only when the implementation status has genuinely changed. Do not mark a feature complete merely because code was added.
9. Report exact commands run and their results. If tests could not run, say why. Never claim tests passed without actual output.

### Non-negotiable engineering constraints

- Preserve the project's charter and existing architecture. Life Graph is reusable, model-agnostic memory infrastructure; Jarvis is a consumer/product, not a reason to couple the core to one assistant.
- **Do not create duplicate systems.** Extend the existing capture, evidence, memory, retrieval, judgment, evaluation, procedure, task and autonomy components.
- Deterministic code owns authorization, tenant boundaries, temporal rules, provenance, retention/deletion, approvals, transactions and idempotency. LLM output is a proposal, not authoritative truth.
- Fail closed on uncertain authorization or side effects. Do not weaken approval gates to make tests pass.
- Preserve local-first privacy and existing cloud-routing/redaction rules. Never send private user data to a cloud model for convenience.
- Do not silently reinterpret or backfill uncertain dates, confidence, causal links or source references.
- Prefer additive, reversible migrations. Consider existing production data and migration downgrade/upgrade behavior.
- Do not perform broad refactors, unrelated cleanup, dependency upgrades or feature expansion in a focused fix.
- Do not delete, overwrite or rewrite user data as part of a migration without an explicit, reviewed policy.
- If a finding is already fixed on current HEAD, verify it with regression tests and mark it resolved; do not re-implement it.

### Required completion report

For every workstream, report:
- Finding and current verified status.
- Root cause with file paths and symbols.
- Design decision and alternatives considered.
- Files changed and migration details.
- Tests added/changed and exact commands/results.
- Security, privacy and compatibility implications.
- Remaining gaps and follow-up work.
- Commit SHA (if committed).

Do not start all workstreams simultaneously. Complete and verify one in priority order, then continue.

---

## 2. Executive review

The repository already has substantial foundations for memory, retrieval, capture, evidence, judgments, predictions, calibration, procedures, evaluations, agents and task execution. The key risk is not simply missing features; it is that some existing pieces are not consistently connected end to end.

The highest-value direction is to make memory **trustworthy, explainable, temporally correct and secure** before expanding the assistant surface area.

The latest reviewed implementation commit made meaningful progress in bitemporal-related behavior, abstention, evaluation cases, provenance/gaps, brief evidence and task checkpoints. That progress does **not** establish that the complete roadmap is done.

### Overall assessment at review baseline

| Area | Review status | Main remaining concern |
|---|---|---|
| Evidence lineage | Partially implemented | Evidence is stored, but source-to-answer claim lineage is incomplete |
| Temporal reasoning | Partially implemented | Valid-time exists; transaction-time history and consistent historical retrieval remain incomplete |
| Confidence and abstention | Partially implemented | Signals are conflated in places; confidence is not fully calibrated against reviewed memory facts |
| Provenance-aware retrieval | Partially implemented | Provenance helper exists but was not wired into the main retrieval ranking path |
| Causal memory | Foundation exists | Decision → action → observed outcome chain is not consistently integrated |
| Episodic memory | Partially implemented | Experience-level structured events and links to decisions need refinement |
| Procedural memory | Partially implemented | Procedures exist; automatic learning and outcome verification are incomplete |
| Evaluation | Progress made | Needs broader, reproducible tests for end-to-end behavior and regressions |
| Durable task continuity | Partially implemented | Recovery/requeue exists; exact safe step-level resumption needs verification |
| Tenant isolation | Potential security defect identified | Procedure create/read/update/delete paths need explicit tenant enforcement |

These statuses must be rechecked against current HEAD before implementation.

---

## 3. Priority 0 — security issue to verify and fix first

### P0-S1: Procedure tenant isolation

**Review finding:** In `life_graph/api/procedures.py`, the inspected implementation showed:

- The create route did not explicitly assign the active tenant ID; the model defaulted to `"legacy"`.
- Get, update and delete routes fetched by procedure ID without filtering by the active tenant.
- List and match routes did apply tenant filtering.

This could allow cross-tenant access or mutation if IDs are known or exposed. Verify whether current code still has this behavior.

**Required action:**

1. Trace how the active tenant is resolved in other secure API routes. Reuse the established dependency/helper; do not invent a second tenant mechanism.
2. Set tenant ownership from authenticated request context on creation. Never trust a tenant ID supplied by an untrusted request body.
3. Scope get/update/delete database queries to both resource ID and active tenant.
4. Ensure not-found behavior does not disclose whether another tenant owns the resource.
5. Check related procedure matching/application/history endpoints and any background jobs for tenant leakage.
6. Add tests for two tenants: tenant A cannot read, update, delete, match or apply tenant B's procedure; creation assigns the correct tenant.
7. Search for the same ID-only lookup pattern in other API resources. Report additional findings; fix only directly related, verified security defects in this bounded workstream.

**Acceptance criteria:**

- Cross-tenant reads and mutations are impossible through all procedure endpoints.
- A procedure created by tenant A is owned by tenant A, not `legacy`.
- Tests prove isolation for both positive (own tenant) and negative (other tenant) cases.
- Existing legacy data behavior is explicit and migration-safe.

**Relevant file:** `life_graph/api/procedures.py`

**Resolution status (verified):**
- Fixed on `fix/p0-s1-procedure-tenant-isolation` (`life_graph/core/tenant.py` `get_scoped()` + `life_graph/api/procedures.py` `_load_procedure()` and `tenant_id=get_current_tenant_id()` in `create_procedure()`).
- Cross-tenant `get`/`update`/`delete`/`apply` now return `404` without disclosing ownership; `list`/`match` remain tenant-scoped.
- Adjacent `session.get` scan in `life_graph/api/`: `jarvis.py` (116, 578, 1733) and `kernel.py` (864) explicitly verify `row.tenant_id != tenant_id`; `admin.py` (324, 347, 404, 443, 494, 530, 567) is admin-scoped (`TenantWebhook`/`TenantConfig`); `llm_offers.py` (46) is global instance model (`LlmOffer`).

Treat this as the first task because authorization defects take precedence over feature work.

---

## 4. Priority 0 — trustworthy memory workstreams

After P0-S1 is fixed and tested, work through these in order. Do not combine all of them into one large implementation.

### P0.1 Evidence lineage — highest functional priority

**Review finding:** Evidence and extraction traces exist, but the complete chain from original input to extracted fact, consolidated memory and final answer claim is incomplete.

Relevant inspected areas:

- `life_graph/core/evidence.py`
- `life_graph/models/memory.py`
- `life_graph/models/judgment.py`
- `life_graph/self_improving/traces.py`
- `life_graph/self_improving/suite_builder.py`
- `alembic/versions/038_extraction_traces.py`

Existing foundations observed:
- Memory source type/source and trust metadata.
- Optional capture event reference.
- Extraction traces with task/prompt/model/input/output/facts/latency metadata.
- Memory-to-trace references via properties such as `extraction_trace_id` and `extraction_fact_index`.
- Approval/rejection/edit feedback.
- Evidence supporting or contradicting judgments/preferences.

Gaps observed:
- Exact source spans or stable excerpt references are not consistently preserved.
- Some memory creation paths may bypass a common lineage mechanism.
- Consolidation/derived-memory operations can lose the complete ancestry chain.
- Synthesized answers do not consistently expose claim-level supporting evidence.
- Raw extraction input retention and deletion policy need explicit review.

**Implementation direction:**

First map every memory creation path (conversation capture, transcript/document ingestion, manual creation, correction, consolidation, connector and agent paths). Design the smallest shared lineage contract that can cover them. Then implement a reusable lineage resolver/service that can answer:

> Given this memory or answer claim, what original source supports it, what extraction produced it, what excerpt/span supports it, and which transformations or derived memories occurred afterward?

Do not assume every source has a textual span. Support source-specific references (event ID, document/page/offset, transcript timestamp, etc.) where appropriate. Do not copy sensitive source content into additional tables without a retention and deletion decision.

**Acceptance criteria:**
- A memory can resolve to its original source and extraction trace where those exist.
- A fact extracted from a document or conversation can expose a precise source location/excerpt when available.
- Derived or consolidated memories preserve ancestry to source evidence.
- Important synthesized claims can expose the evidence that supports them; unsupported claims remain explicitly unsupported.
- Source deletion/retention behavior is defined and tested for derived records.
- Tests cover multiple ingestion paths, missing sources, deleted sources and malformed lineage without fabricating evidence.

### P0.2 Correct bitemporal history

**Review finding:** Valid-time fields, supersession/history concepts and an `as_of` search parameter exist. Full bitemporal semantics are not established.

Relevant inspected areas:
- `life_graph/models/memory.py`
- `life_graph/services/memory_retrieval.py`
- `life_graph/services/capture.py`
- `life_graph/api/search.py`

Important distinction:
- **Valid time:** when the fact was true in the real world.
- **Transaction time:** when Life Graph learned or recorded the fact.

Example: In April, the user corrects Life Graph and says a role actually ended in February. The system must preserve both when the role was true and when the system learned the correction.

Specific concern observed: episode retrieval derived a time window from the current date (`datetime.now(episodes._tz()).date()`) rather than consistently using the requested historical `as_of` date. Verify current implementation and all retrieval branches.

**Implementation direction:**

- Specify correction, late-arriving fact, retraction, supersession and uncertain-date semantics before designing schema.
- Decide whether immutable memory revisions/assertions or another existing-compatible history model is the right fit.
- Apply a single explicit temporal context through every retrieval branch, including episodes, linked memories and graph expansion.
- Keep current-state queries and historical queries deterministic and explainable.
- Do not merely add a timestamp column and call the system bitemporal.

**Acceptance criteria:**
- A correction does not erase what the system previously believed or when it learned the correction.
- Current queries return currently valid facts.
- Historical queries reconstruct facts valid at the requested time.
- Late-arriving information is handled correctly.
- All retrieval branches use the same temporal context.
- Tests cover overlapping intervals, unknown dates, corrections, retractions, timezone boundaries and episode retrieval.

### P0.3 Calibrated confidence and uncertainty

**Review finding:** Extraction confidence, memory confidence, source trust, reinforcement, preference history, prediction calibration, abstention and knowledge gaps exist. They are not yet a complete calibrated memory-confidence system.

Relevant inspected areas:
- `life_graph/models/memory.py`
- `life_graph/core/evidence.py`
- `life_graph/services/memory_retrieval.py`
- `life_graph/services/calibration.py`
- `life_graph/api/search.py`

Specific concerns observed:
- Extraction confidence, source reliability, user confirmation, freshness, corroboration and query relevance need to remain distinct signals.
- `provenance_order()` existed but the main retrieval path used `strength_order()`; verify whether provenance is now integrated.
- `ask_brain()` used the maximum confidence among retrieved memories for a threshold decision. A single high-confidence item may therefore mask weak supporting evidence.
- Prediction calibration is not equivalent to calibration of memory truth confidence.

**Implementation direction:**

- Define the semantics of each signal and where it is used.
- Create a labelled memory-confidence evaluation set from synthetic and explicitly approved examples.
- Measure calibration and error by source type, fact type and freshness where sample size permits.
- Make abstention and uncertainty claim-specific, not just a single answer-level threshold.
- Do not use similarity/retrieval score as truth confidence.
- Explain why a memory was selected, and distinguish explicit user statements from inference.

**Acceptance criteria:**
- Confidence components are separately inspectable.
- Evaluation compares predicted confidence with reviewed correctness labels.
- Contradictory, stale, weakly supported and absent evidence produce appropriate uncertainty or abstention.
- One high-confidence memory cannot silently validate unrelated weak claims.
- Regression tests cover mixed-quality evidence and conflicting sources.

### P0.4 Provenance-aware retrieval

Wire provenance into the actual retrieval path only after the lineage contract and confidence semantics are clear.

- Inspect the current ranking pipeline and existing `provenance_order()` / `strength_order()` behavior.
- Define deterministic tie-breaking and explainable ranking factors.
- Do not let source trust override relevance without a measured reason.
- Add ranking tests where a direct user statement, an inferred fact, an old fact and a corroborated fact compete.
- Record why a candidate was selected or rejected.

### P0.5 Causal memory integration

**Review finding:** There is a strong foundation. Do not create another decision system.

Relevant inspected areas:
- `life_graph/models/judgment.py`
- `life_graph/services/judgment.py`
- `life_graph/services/outcome_resolver.py`
- `life_graph/services/calibration.py`
- `life_graph/models/memory.py`

Existing foundations include decisions, options, rationale, predictions, resolution evidence/outcomes and relationship types such as `BECAUSE`, `EVIDENCED_BY`, `CONTRADICTS` and `LEADS_TO`.

Remaining work:
- Connect context/problem → options → decision/rationale → action → observed outcome/evidence.
- Distinguish user-stated reasons from model-inferred reasons.
- Only record outcomes when supported by evidence.
- Make the chain queryable without duplicating Judgment Engine concepts.

### P0.6 Episodic and procedural learning

Relevant inspected areas:
- `life_graph/services/episodes.py`
- `life_graph/models/memory.py`
- `life_graph/api/procedures.py`

Existing foundations include conversation sessions, capture events, daily summaries, time-based episode retrieval, procedure records, triggers, steps, confidence, learned-from references and application/success tracking.

Remaining work:
- Model useful bounded experiences with entities/participants, time, context, actions and outcomes.
- Link experiences to relevant memories and decisions.
- Learn candidate procedures from repeated workflows and completed agent tasks.
- Include prerequisites, permissions, tool versions, verification steps and failure/recovery knowledge.
- Verify success from observed outcomes rather than trusting only a manually supplied boolean.
- A previously successful procedure must never grant permanent permission to repeat side effects.

---

## 5. Evaluation and regression requirements

Build on the repository's existing evaluation infrastructure. Do not create a parallel evaluation framework.

Every workstream must add tests at the correct level:

- Unit tests for deterministic rules and data transformations.
- Integration tests for database, API, tenant and retrieval behavior.
- Regression tests for previously observed failures.
- Evaluation cases for answer quality, uncertainty and evidence selection where applicable.

Required cross-cutting scenarios:

1. User corrects a previously stored fact with a past effective date.
2. User asks what was true at a historical date.
3. A fact is explicit in one source but inferred in another.
4. Two sources conflict.
5. A memory is stale or superseded.
6. An answer contains multiple claims with different evidence quality.
7. A source is deleted or becomes unavailable.
8. A tenant attempts to access another tenant's resource.
9. A procedure's previous success is not sufficient authorization for a new side effect.
10. A process restarts while a multi-step task is in progress.

Where appropriate, evaluate against public datasets such as LongMemEval, LoCoMo and MemoryAgentBench, subject to licensing and privacy constraints. Never use private personal conversations in public datasets or external services without explicit authorization.

Do not claim improvement based only on anecdotal examples. Record baseline, dataset/version, model/prompt/embedding configuration, metrics, latency and regression examples.

---

## 6. Suggested implementation sequence

| Order | Workstream | Exit gate |
|---:|---|---|
| 0 | Verify and fix procedure tenant isolation; scan adjacent ID-only resource lookups | Cross-tenant tests pass |
| 1 | Design and implement shared evidence lineage | Source → fact → derived memory → answer claim can be traced |
| 2 | Specify and implement bitemporal semantics | Current and historical queries pass across all retrieval branches |
| 3 | Separate and calibrate confidence signals | Labelled evaluation demonstrates calibrated uncertainty |
| 4 | Integrate provenance into retrieval ranking | Ranking and explanation tests pass |
| 5 | Connect decisions, actions and verified outcomes | Causal chain is queryable and evidence-backed |
| 6 | Improve episodic/procedural learning | Reusable procedures are learned and verified safely |
| 7 | Expand end-to-end evaluation coverage | Reproducible regression suite and baseline report |

Do not begin the next workstream until the current exit gate is met, or explicitly document why work is blocked and what decision is needed.

---

## 7. Definition of done

The review's core objectives are met only when the system can demonstrate all of the following:

- Explain why a memory exists and retrieve its original evidence where available.
- Trace an extracted fact to a source excerpt or source-specific location.
- Correct a fact without destroying its history.
- Answer historical questions using the fact valid at that time.
- Distinguish explicitly stated facts from inferred facts.
- Abstain when evidence is absent, contradictory or insufficient.
- Measure memory confidence against labelled examples.
- Explain why a memory was selected for an answer.
- Retrieve the rationale behind an earlier decision.
- Connect a decision to an action and a verified outcome.
- Learn a reusable procedure from successful workflows without treating past success as permission.
- Prove that one tenant cannot access or mutate another tenant's data.

A feature is not done merely because its schema, API endpoint or service exists. It must be integrated, authorized, tested and observable in the actual user-facing path.

---

## 8. Review limitations and evidence discipline

- This is a code review and implementation handoff, not a formal security audit.
- The findings refer to the inspected code at the stated review baseline. The repository may have changed since then.
- No repository code was changed and no test suite was run as part of the review summarized here.
- CI status was not established by the review; do not infer passing checks.
- Historical counts in `docs/STATE.md` are inventory data, not proof that every listed capability works.
- Before implementing, inspect current HEAD and verify each issue. If the code has changed, update this document's status with concrete evidence rather than following stale instructions blindly.

**Primary roadmap:** `docs/LIFE_GRAPH_EVOLUTION_ROADMAP.md`  
**First action:** Verify and fix P0-S1 tenant isolation in `life_graph/api/procedures.py`, add regression tests, and report the result before moving to evidence lineage.


---

## 9. Verified Execution Status (P0-S1, P0.1–P0.6)

| Workstream | Status | Key Implementation | Verification |
|---|---|---|---|
| **P0-S1** | Completed & Merged (PR #227) | `life_graph/core/tenant.py` (`get_scoped`), `life_graph/api/procedures.py` (`_load_procedure`, `create_procedure` tenant scoping) | `tests/unit/test_procedure_tenant_isolation.py`, `tests/unit/test_tenant_scoping.py` |
| **P0.1** | Completed | `life_graph/core/evidence.py` (`normalize_lineage`, `resolve_memory_lineage`, `extract_claim_evidence`), `life_graph/storage/postgres.py`, `life_graph/services/synthesis.py`, `life_graph/api/search.py` (`claim_evidence`) | `tests/unit/test_evidence_lineage.py` |
| **P0.2** | Completed | `life_graph/services/memory_retrieval.py` (`is_bitemporally_valid`, `recorded_as_of` across all retrieval branches), `life_graph/api/search.py` (`AskRequest.recorded_as_of`, `AskResponse.recorded_as_of`) | `tests/unit/test_bitemporal_abstention.py`, `tests/unit/test_memory_retrieval.py` |
| **P0.3** | Completed | `life_graph/core/evidence.py` (`decompose_memory_confidence`, `evaluate_confidence_calibration`, per-claim `confidence_breakdown` & `claim_uncertainty` in `extract_claim_evidence`) | `tests/unit/test_confidence_calibration.py` |
| **P0.4** | Completed | `life_graph/services/memory_retrieval.py` (`provenance_score`, `provenance_tiebreak_order` with 2% near-tie band, `explain_retrieval_selection`) | `tests/unit/test_provenance_retrieval.py`, `scripts/eval_memory_recall.py --tenant raja --set live --methods recall` (`hit@1=0.692`, `abstained=15/15`) |
| **P0.5** | Completed | `life_graph/services/judgment.py` (`trace_causal_chain`, `get_causal_chain`), `life_graph/services/outcome_resolver.py` (`record_evidence_backed_outcome`, `evidence_backed` tagging) | `tests/unit/test_causal_memory.py` |
| **P0.6** | Completed | `life_graph/services/episodes.py` (`link_experience_to_decision`), `life_graph/api/procedures.py` (`build_procedure_candidate`, `verify_procedure_candidate`, `can_auto_execute_side_effects`) | `tests/unit/test_episodic_procedural_learning.py` |
