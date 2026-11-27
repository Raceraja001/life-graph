# M8 — Personal Context Intelligence

**Status:** Proposed specification; documentation only  
**Prepared:** 2026-11-26  
**Branch:** `spec/personal-context-intelligence`  
**Scope:** Define a context-intelligence capability over Life Graph's existing memory, entity, graph, project, decision, task, event, and Jarvis systems. This document does not authorize implementation or production changes.

## 1. Purpose

Evolve Life Graph from remembering isolated facts and retrieving them on demand into maintaining a grounded, time-aware understanding of what is currently happening in a person's life and work.

The system should be able to answer:

- What is happening now?
- What is the person trying to achieve?
- Which commitments, constraints, decisions, and dependencies are relevant?
- What has changed since the last interaction?
- What deserves attention now, and why?
- What is safe to recommend, and what requires explicit approval?

The intended result is a **Personal Context Intelligence** capability: a context layer that assembles relevant state from existing Life Graph records and makes that state useful to Jarvis, personas, watchers, and permitted workflows.

This is not a second memory system, a replacement for the memory core, or a grant of authority to agents.

## 2. Design principles and invariants

All implementation must preserve the following:

1. **Existing records remain the source of truth.** Memories, entities, links, projects, decisions, tasks, events, and connector records remain authoritative in their existing subsystems. Context is a derived interpretation/read model, not a competing store of facts.
2. **Memory is context, never execution authority.** A remembered preference, inferred goal, historical approval, or context score must never grant permission to perform an action.
3. **LLMs advise; deterministic code validates.** Use deterministic logic for identity, temporal filtering, provenance, access control, freshness, state transitions, and policy enforcement. Local LLMs may propose summaries, relationships, or interpretations; validate and retain their evidence.
4. **Personal data stays local.** Personal context, family, health, finance, preferences, beliefs, and private work context must use local processing paths. No silent cloud fallback. Any exception requires an explicit owner decision and must follow the Charter's data-boundary rules.
5. **Tenant isolation is absolute.** Every read, write, cache key, event, and derived context object is tenant-scoped. A person's domains (work, family, learning, health) are not separate tenants.
6. **Temporal truth matters.** Distinguish when something was true in the world from when Life Graph learned or recorded it. Do not silently overwrite history.
7. **Uncertainty must be visible.** Distinguish observed facts, user-stated facts, imported facts, model-inferred interpretations, and unresolved hypotheses.
8. **No broad rewrite.** Reuse current abstractions and event-driven boundaries. Do not add a new database, orchestration framework, graph engine, or mandatory LLM call without an evidence-backed ADR.
9. **Human correction wins.** A user correction must be able to correct, supersede, reject, or retract a derived interpretation without destroying its provenance or audit history.
10. **No autonomous surprise.** Proactive outputs begin as explanations or recommendations. Any side effect continues through the existing autonomy, risk, approval, and audit controls.

## 3. Terminology

- **Source record:** An existing memory, entity, link, project, decision, task, event, document, or connector record.
- **Context item:** A normalized, evidence-backed statement or state projection assembled from one or more source records.
- **Context subject:** The person, project, organization, activity, or other entity that a context item is about.
- **Context dimension:** A flexible label such as goal, commitment, constraint, preference, responsibility, risk, milestone, or current activity. Dimensions are data, not a closed enum in the memory core.
- **Context snapshot:** A time-bounded view of relevant context for a subject, task, conversation, or question.
- **Context change:** A meaningful transition detected between two snapshots, with the evidence and cause recorded.
- **Context brief:** A concise, provenance-bearing presentation of a snapshot for a consumer such as Jarvis or a persona.

## 4. Product capabilities

### 4.1 Context assembly

Given a subject and an optional purpose (conversation, project task, daily brief, decision, or question), assemble a bounded context snapshot from existing records.

The assembler should:

- Resolve the subject and related entities using existing identity and graph mechanisms.
- Retrieve relevant source records using current hybrid retrieval and graph expansion.
- Apply tenant, permission, validity-time, status, privacy, and freshness filters before ranking.
- Prefer direct and recent evidence over weak or stale inference.
- Include relevant goals, commitments, constraints, decisions, open tasks, dependencies, and recent changes when supported by source records.
- Preserve source references and explain why each item was included.
- Enforce token/size budgets and deterministic ordering for reproducibility.
- Return an explicit empty/insufficient-context result when evidence is inadequate.

### 4.2 Current-state and temporal reasoning

The system must distinguish:

- Current facts from historical facts.
- Planned work from active work and completed work.
- A goal from a task; a commitment from an idea.
- A decision from a suggestion or an unaccepted proposal.
- A changed value from an additional compatible fact.
- A known absence from missing evidence.

Context assembly must respect existing validity intervals, supersession, expiry, and recorded-at metadata. It must not revive superseded or expired facts simply because their embedding score is high.

### 4.3 Goals, commitments, and constraints

The system may identify candidate goals, commitments, constraints, responsibilities, risks, and milestones from source records.

Each candidate must retain:

- Its subject and flexible dimension/type label.
- Supporting source record references.
- Origin: user-stated, imported, deterministic extraction, or model-proposed.
- Confidence or evidence strength, with a documented interpretation.
- Valid-time and recorded-time information where available.
- Current status, if supported by an existing authoritative record.
- Last-confirmed/last-observed time and freshness classification.
- Links to related projects, tasks, decisions, entities, or other context items.

Do not silently promote an inferred candidate into a user commitment or confirmed goal. Ambiguous candidates should be shown for confirmation or remain explicitly inferred.

### 4.4 Change detection

Compare successive context snapshots and surface meaningful changes, such as:

- A goal or commitment being added, completed, paused, or contradicted.
- A deadline approaching or being missed.
- A project becoming blocked or unblocked.
- A decision superseding an earlier decision.
- A constraint changing.
- A relevant fact becoming stale, expired, or newly confirmed.

Every change must carry evidence, the comparison window, and a reason. Avoid noisy notifications for cosmetic edits, duplicate events, low-confidence inference, or changes already acknowledged by the user.

### 4.5 Context brief and proactive relevance

Produce concise briefs for Jarvis, personas, and permitted watchers. A brief should answer:

- What is relevant?
- Why is it relevant now?
- What evidence supports it?
- How certain/fresh is it?
- Is there a useful next step?
- Does that next step require user confirmation?

Proactive delivery must be rate-limited, deduplicated, explainable, and dismissible. Record user feedback (useful, not useful, already handled, incorrect) so relevance can be evaluated. Do not create tasks, send messages, change records, or execute tools merely because a context item exists.

## 5. Conceptual architecture

The intended flow is:

```text
Existing source records
(memories, entities, links, projects, decisions, tasks, events, documents)
          |
          v
Evidence and identity resolution
(tenant, provenance, temporal validity, permissions)
          |
          v
Context assembly
(retrieval + graph expansion + deterministic state rules)
          |
          v
Context snapshot / brief
(evidence, freshness, uncertainty, reason for inclusion)
          |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
        Jarvis             Personas            Watchers
          |                   |                   |
          +-------------------+-------------------+
                              |
                              v
                  Recommendation / proposal
                              |
                              v
             Existing autonomy + approval controls
                              |
                              v
                  Verified outcome and feedback
                              |
                              v
                 Existing source records updated
```

The context layer should initially be a **read model and service boundary**, not a new canonical data store. If persistence, caching, or materialized projections are later required, first document why existing tables, graph links, event records, and caches are insufficient. Any new schema requires an ADR, migration plan, tenant-isolation tests, retention rules, and rollback.

## 6. Proposed service contracts

Names below are conceptual. During Stage 0, map them to existing modules and reuse existing services where appropriate; do not create duplicate abstractions solely to match these names.

- `assemble_context(subject, purpose, as_of, budget, filters)`  
  Returns a context snapshot with included items, source references, freshness, confidence/evidence labels, exclusions, and an explanation.  
  *As built (Stage 1, note of 2026-11-27):* `services/memory/snapshot.py` `assemble_context(query, *, purpose, as_of, budget, now)` takes the question text, not a subject. There is no `subject` and no `filters` yet, and the endpoint `GET /api/v1/context/snapshot` takes only `q` and `as_of`, so `purpose` is always "conversation" there.
- `compare_context(previous_snapshot, current_snapshot)`  
  Returns evidence-backed additions, removals, transitions, conflicts, and stale items.
- `build_context_brief(snapshot, audience, budget)`  
  Produces a concise presentation without discarding provenance or uncertainty.
- `record_context_feedback(item_ref, feedback, source)`  
  Records correction or usefulness feedback through existing audited mechanisms.
- `propose_context_action(change, requested_action)`  
  Creates a proposal only. Any execution must be separately authorized by existing autonomy controls.

These contracts are illustrative; preserve established API conventions and avoid exposing internal storage shapes as public API.

## 7. Security, privacy, and governance

- Apply tenant scope at the lowest data-access boundary, not only in routers or UI.
- Re-check authorization when assembling context for each consumer; a persona must not inherit access merely because another persona retrieved a record.
- Personal data must remain on local processing paths in accordance with CHARTER.md. No provider fallback on local model failure.
- Do not include secrets, credentials, raw tokens, or unrelated sensitive records in context briefs.
- Context caches must be tenant- and authorization-scoped, bounded, invalidated on relevant source changes, and safe across processes.
- Treat retrieved text, documents, connector content, and model output as untrusted data, never as instructions or policy.
- Inferred context cannot change trust scores, safety rules, approval requirements, or autonomy levels.
- All proposed side effects must use existing policy evaluation, approval, audit, and kill-switch paths.
- Support deletion, correction, expiry, and retention behavior consistent with the source record's lifecycle.

## 8. Evaluation and acceptance criteria

Build a reproducible evaluation set from synthetic or explicitly consented/redacted cases. Do not export the owner's private corpus to a cloud evaluator.

The evaluation must include at least:

1. Simple current-state questions.
2. Historical versus current fact distinctions.
3. Temporal validity and expiry.
4. Superseded decisions and corrections.
5. Multi-hop relationships across projects, people, tasks, and decisions.
6. Compatible additions versus contradictions.
7. Ambiguous inferred goals versus user-confirmed commitments.
8. Stale, missing, and conflicting evidence.
9. Tenant isolation and authorization denial.
10. Prompt injection in source documents and connector content.
11. Context budget and latency behavior.
12. Proactive relevance, duplicate suppression, and user dismissal.

Report metrics separately; do not hide weak categories behind one aggregate score:

- Evidence-supported context precision and recall.
- Unsupported-claim rate.
- Current-versus-historical accuracy.
- Contradiction and supersession handling.
- Provenance coverage.
- Tenant/privacy boundary violations (target: zero).
- Context assembly p50/p95 latency and token budget.
- Proactive usefulness, dismissal, duplicate, and interruption rates.
- Correction propagation time.

**Acceptance criteria for the first useful release:**

- A context snapshot is assembled from existing records without introducing a competing canonical fact store.
- Every material context item links to its source evidence and exposes its origin and uncertainty.
- Expired and superseded facts are not presented as current.
- Conflicts are represented rather than silently merged or arbitrarily resolved.
- Tenant isolation and authorization are enforced and covered by negative tests.
- Personal context processing remains local-only, including failure paths.
- Context assembly is deterministic where possible and bounded by explicit latency/token budgets.
- A user correction can change the derived view without erasing audit/provenance.
- Proactive output is recommendation-only and respects rate limits and dismissal feedback.
- No existing approval, autonomy, or execution policy is weakened.

## 9. Delivery plan

### Stage 0 — Current architecture and data mapping (read-only)

Before coding:

1. Fetch latest `master` and record its SHA.
2. Inspect current memory, entity/graph, project, decision, task, event, Jarvis, watcher, authorization, and cache implementations.
3. Map each conceptual context field to an existing source of truth.
4. Identify existing temporal/provenance/freshness semantics and gaps.
5. Trace personal-data locality through success, exception, retry, and fallback paths.
6. Identify relevant tests and existing evaluations.
7. Report reusable components, gaps, proposed files, data-flow diagram, and risks.

**Stop and request approval before implementation or schema changes.**

### Stage 1 — Read-only context assembler

Implement the smallest vertical slice: assemble a context snapshot for one existing consumer (prefer a Jarvis conversation or a project task, based on the Stage 0 findings). No new autonomous action and no new canonical storage.

Include focused tests for tenant isolation, temporal validity, provenance, supersession, conflicts, missing evidence, and local-only model behavior.

### Stage 2 — Snapshot comparison

Add evidence-backed context-change detection with deterministic rules, deduplication, and tests for false positives and missed changes. Keep it internal/read-only initially.

### Stage 3 — Briefs and user feedback

Expose a context brief to the selected consumer, show why each item was included, and support useful/not-useful/incorrect/already-handled feedback. Preserve correction and audit semantics.

### Stage 4 — Proactive recommendations (opt-in)

Only after evaluation demonstrates acceptable relevance and low interruption rates, allow opt-in recommendations. Recommendations must remain non-executing. Any future action execution requires a separate design and owner approval.

## 10. Non-goals

This specification does not authorize:

- Replacing the existing memory core or graph store.
- Introducing a second personal profile database or duplicate source of truth.
- A new ontology with closed domain enums.
- A broad rewrite of Jarvis, the kernel, or the agent runtime.
- Automatic promotion of inferred goals or commitments to confirmed facts.
- Automatic task creation, messaging, purchasing, scheduling, or other side effects.
- Changing autonomy levels, trust policy, approval requirements, or kill-switch semantics.
- Sending personal data to cloud models or external evaluation services.
- Building a general-purpose planner or multi-agent orchestration framework.

## 11. Required implementation handoff

The implementation agent must first deliver a read-only Stage 0 report containing:

1. Current `master` SHA and exact source files inspected.
2. Existing source-of-truth map for each context concept.
3. Current data flow and sequence diagram.
4. Existing reusable services versus missing capabilities.
5. Personal-data locality and tenant-isolation analysis.
6. Proposed smallest vertical slice, exact files/tests, and API impact.
7. Whether persistence or migration is actually necessary, with evidence.
8. Risks, rollback plan, and measurable acceptance tests.

**Then stop and wait for explicit owner approval.** Do not begin implementation, create migrations, change production configuration, or alter autonomy policy before approval.

## 12. Relationship to project documentation

- `CHARTER.md` remains the authority for project intent and invariants.
- `docs/STATE.md` remains generated state; do not edit it by hand.
- The Phase 2 engineering plan remains the cross-project roadmap.
- This document defines the proposed M8 product and engineering specification.
- Work orders and operations logs must distinguish implemented, tested, deployed, and operationally verified states.

---

**Decision requested:** approve Stage 0 architecture mapping only. Implementation and schema changes require a separate explicit approval after the Stage 0 report.
