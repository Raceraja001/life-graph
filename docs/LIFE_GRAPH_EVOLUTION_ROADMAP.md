# Life Graph & Jarvis — Evolution Roadmap

> **Status:** Proposal for review  
> **Purpose:** Consolidate the architectural opportunities and feature ideas identified during the Life Graph repository review into one actionable planning document.  
> **Scope:** Both Life Graph (reusable memory infrastructure) and Jarvis (the personal assistant that consumes it), with a clear boundary between them.  
> **Important:** This is a proposal, not a statement that every item is missing. Check the current implementation and feature specifications before creating migrations or duplicating existing capabilities.

---

## 1. Product direction

Evolve the system toward a **Personal Intelligence Operating System (PIOS)**:

- **Life Graph** is a model-agnostic, reusable memory and context infrastructure for agents.
- **Jarvis** is the personal assistant experience built on Life Graph, with voice/chat, proactive help, integrations and controlled actions.

Life Graph should remain useful independently of Jarvis. Jarvis should demonstrate what becomes possible when an assistant has persistent, temporal, explainable memory.

### Guiding principles

Preserve the repository's existing principles:

1. **Memory-first, not model-first:** model providers are replaceable; memory and domain logic are durable.
2. **LLM as advisor, not authority:** probabilistic model output must not silently become verified truth.
3. **Fail-closed autonomy:** unknown or unclassified side effects require human approval.
4. **Privacy and locality:** personal data stays on the local path according to the project's privacy rules. Cloud work must remain constrained by the existing routing, tool restrictions and redaction policy.
5. **Explainability:** important claims should be traceable to evidence and time.
6. **Measurable improvement:** new features need evaluation cases and regression tests.
7. **Ruthless sequencing:** improve the core before expanding the surface area.

---

## 2. Existing foundation — do not rebuild blindly

The repository's generated `docs/STATE.md` (generated 2026-11-03 from master at the time of review) reported a substantial existing system, including:

- Memory CRUD, correction, approval, archive/restore and links.
- Vector, hybrid and graph search; ask, proactive recall and event-driven recall.
- Capture and transcript ingestion.
- Intentions, identity/belief tracking and knowledge gaps.
- Contradiction detection, memory decay and consolidation.
- Evidence, decisions, predictions, calibration and verification-related structures.
- Agent personas, workflows, tools, watchers, notifications and autonomy/approval infrastructure.
- Multimodal ingestion and integrations.
- Evaluation suites, cases and results.

The generated inventory at that point reported 68 database tables, 79 event types, 65 HTTP operations, 34 scheduled jobs and 4,078 test functions. These are historical inventory figures, not a claim that every feature is complete or currently passing.

**Review rule:** Before implementing an item in this roadmap, inspect the current code, `docs/STATE.md`, `docs/specs/` and relevant design documents. Mark it as:
- Already implemented and tested.
- Partially implemented / needs refinement.
- Designed but not implemented.
- New proposal.
- Not currently valuable.

---

## 3. Priority roadmap

### P0 — Trustworthy, explainable memory

**Goal:** Make it possible to answer not only *what does the system remember?*, but also *why does it believe this, when was it true, and how certain is it?*

#### 3.1 Provenance and evidence lineage

For every important extracted memory or claim, preserve a trace to its origin.

Candidate evidence metadata:
- Source type: conversation, transcript, document, image, event, connector or user correction.
- Source identifier and source timestamp.
- Recorded/ingested timestamp.
- Relevant source span or excerpt, subject to privacy and retention policy.
- Extraction model and prompt/pipeline version.
- Whether the user explicitly confirmed or corrected it.
- Links to derived memories and summaries.

**Acceptance criteria**
- A memory detail view can show its source and extraction history.
- A synthesized answer can identify which evidence supports each important claim.
- Derived summaries do not lose the ability to trace back to original evidence.
- Deleted source material follows the project's deletion and retention policy.

#### 3.2 Temporal and bitemporal reasoning

Represent two different times:

- **Valid time:** when the fact was true in the real world.
- **Transaction/recorded time:** when Life Graph learned or stored the fact.

Support late-arriving corrections, historical queries and changing state without treating old facts as current.

Example:
- A project was active from January to March.
- Life Graph learns in April that it actually ended in March.
- The system should answer both “What is the current project?” and “What project was active in February?” correctly.

**Acceptance criteria**
- Current-state queries prefer the currently valid fact.
- “As of date” queries can reconstruct prior state.
- Corrections retain history rather than erasing it.
- Uncertain or missing dates are represented explicitly, not invented.

#### 3.3 Confidence calibration and uncertainty

Keep separate signals rather than collapsing everything into one opaque confidence number:
- Extraction confidence.
- Source reliability / directness.
- User-confirmation status.
- Temporal freshness.
- Corroboration and contradiction status.
- Retrieval relevance (query-specific; not the same as truth confidence).

Add calibrated abstention: when evidence is stale, conflicting or absent, Jarvis should say so and optionally ask a targeted follow-up.

**Acceptance criteria**
- Confidence scores are evaluated against labelled examples.
- The assistant can distinguish “not found” from “known to be false”.
- It does not present a similarity score as factual certainty.
- Stale facts can be surfaced with an explicit freshness warning.

#### 3.4 Causal memory

Represent the reasoning chain behind important decisions and outcomes, not just the final preference.

Example:
- Context/problem: asynchronous workload became important.
- Options considered: Flask and FastAPI.
- Decision: switch to FastAPI.
- Rationale: async support and project requirements.
- Outcome: observed result, if later supplied.
- Evidence: source conversation or decision record.

**Acceptance criteria**
- Decision rationale can be queried separately from the decision.
- The system distinguishes user-stated reasons from inferred reasons.
- Outcomes are only recorded when evidence exists.
- Changed circumstances can trigger a review rather than blindly enforcing old decisions.

#### 3.5 Episodic and procedural memory refinement

- **Episodic:** a bounded experience with participants/entities, time, context, actions and outcome.
- **Procedural:** a reusable method or sequence learned from successful/failed tasks, including prerequisites, tool versions and verification steps.

Avoid storing every interaction as a permanent high-value memory. Preserve source events and derive compact, useful abstractions.

---

### P1 — Evaluation laboratory

**Goal:** Prove that memory changes improve real user outcomes and do not introduce regressions.

Build on the existing evaluation infrastructure rather than creating a parallel system.

#### 3.6 Evaluation dimensions

| Dimension | Example question |
|---|---|
| Extraction precision/recall | Did the system capture the facts actually stated, without inventing details? |
| Retrieval recall | Did it find the necessary evidence? |
| Retrieval precision | Did it avoid irrelevant or misleading memories? |
| Temporal accuracy | Did it select the fact valid at the requested time? |
| Update handling | Did a correction supersede current state while preserving history? |
| Contradiction handling | Did it identify genuine conflicts without inventing them? |
| Abstention | Did it admit when the answer was not supported? |
| Provenance | Can each claim be traced to its source? |
| Forgetting/deletion | Does deleted or expired information stop resurfacing as required? |
| Efficiency | What are latency, tokens, CPU/RAM/VRAM and storage costs? |

#### 3.7 Benchmark datasets and test design

Evaluate against suitable public research benchmarks, where licensing and dataset terms permit:
- LongMemEval — long-term conversational memory, updates, temporal reasoning and abstention.
- LoCoMo — long conversational histories and multi-session recall.
- MemoryAgentBench — memory learning, retrieval and long-range agent tasks.

Also build a **Life Graph private regression set** from synthetic and owner-approved examples:
- Changing preferences and project status.
- Late corrections.
- Similar but distinct entities.
- Conflicting sources.
- Missing information.
- Sensitive data and privacy-routing edge cases.
- User requests to forget/delete.
- Tamil-English and multilingual inputs if those are in the supported product scope.

Do not put private personal conversations into public benchmark datasets or external model services without explicit authorization.

#### 3.8 Controlled experiments

Compare the current baseline with one change at a time:
1. Current Life Graph baseline.
2. Baseline + temporal-aware retrieval.
3. Baseline + provenance-aware ranking.
4. Baseline + reranker.
5. Baseline + graph expansion.
6. Baseline + multi-step/agentic retrieval.

Record:
- Dataset and test-set version.
- Model/provider and exact model version.
- Prompt/extractor version.
- Embedding model and dimension/version.
- Retrieval settings and ranking weights.
- Metrics, latency, token usage and hardware.
- Failure examples and regression deltas.

**Acceptance criteria**
- Every new memory feature adds positive and negative test cases.
- Results are reproducible from a recorded configuration.
- A change cannot be called an improvement based only on anecdotal examples.
- Existing tests and evaluation cases remain green or have explained, reviewed changes.

---

### P2 — Personal intelligence / evolving life graph

**Goal:** Connect relevant information across domains without turning the core memory schema into a rigid list of life categories.

Potential domains include career, projects, learning, finance, family, technology, health and personal goals. These are examples, not mandatory top-level schema enums.

#### 3.9 Cross-domain context

Enable questions that require combining evidence from multiple domains.

Example: “Should I buy another GPU?” may require:
- Existing hardware and workload.
- Current projects and actual compute needs.
- Electricity and infrastructure constraints.
- Budget and existing commitments.
- Alternatives and expected utilization.

The assistant should show the evidence and assumptions behind its recommendation. It should not infer sensitive details or treat stale information as current.

#### 3.10 Goals, milestones and life timeline

Refine existing project/intention/decision concepts into a coherent timeline:
- Goals and desired outcomes.
- Milestones and dependencies.
- Progress evidence.
- Blockers and unresolved decisions.
- Changes of direction.
- Related events and commitments.

Keep goals distinct from predictions and intentions. A goal is desired; a prediction is expected; an intention is a planned action.

#### 3.11 Knowledge gaps and follow-up questions

Turn knowledge gaps into an explicit uncertainty-management workflow:
- Identify information needed for a decision or answer.
- Determine whether it is missing, stale or contradictory.
- Ask the smallest useful question.
- Store the answer with provenance.
- Avoid repeatedly asking for information already supplied.

#### 3.12 Challenge mode

Avoid turning past preferences into a filter bubble. Periodically identify important, old assumptions worth reconsidering:
- Is the preference still current?
- Have requirements changed?
- Is there new evidence or a better alternative?
- Is this a stable value or merely a past situational choice?

The system should propose a review, not silently rewrite a user's preference.

---

### P3 — Jarvis as a continuous personal assistant

**Goal:** Move from request/response to context-aware assistance while preserving user control.

#### 3.13 Proactive briefing and event-aware help

Build on existing watchers, intentions, schedules, notifications and connectors:
- Morning or start-of-session briefing.
- Project status changes and blockers.
- Upcoming commitments and deadlines.
- Follow-up reminders linked to the original conversation.
- Relevant learning revision prompts.
- Decision reminders when a known condition changes.

Controls:
- User-configurable quiet hours and frequency.
- Relevance thresholds and anti-annoyance rules.
- Explain “why am I seeing this?” with evidence.
- Snooze, dismiss, correct and disable.
- Measure useful notifications versus ignored/dismissed notifications.

#### 3.14 Durable task continuity

For long-running tasks, persist:
- Task goal and user authorization.
- Plan and dependencies.
- Completed steps and verified outputs.
- Current checkpoint.
- Files/artifacts changed.
- Errors and recovery attempts.
- Pending approvals.
- Resume instructions and idempotency keys.

**Acceptance criteria**
- A process or machine restart does not lose task state.
- Completed steps are not repeated unsafely.
- Each resumed action rechecks preconditions.
- Side effects still pass through the existing autonomy and approval gate.

#### 3.15 Learned procedures and experience memory

After a task, propose a reusable procedure containing:
- Preconditions and required permissions.
- Steps and tool versions.
- Expected output.
- Verification method.
- Known failure modes and recovery steps.
- Provenance and success/failure history.

A successful past execution is evidence, not blanket permission to repeat the action. Revalidate permissions and safety every time.

#### 3.16 Specialist-agent collaboration

Use specialist personas for bounded tasks, but make shared memory explicit:
- What context can be shared?
- Which agent is allowed to read/write it?
- Is the information verified or merely a hypothesis?
- Who owns a task and its final result?
- How are conflicting agent conclusions handled?

Prefer shared, permissioned artifacts and typed messages over unrestricted shared memory.

---

### P4 — Multimodal experience memory

**Goal:** Make experiences searchable across text, voice, documents and visual inputs.

Potential capabilities:
- Voice transcription with timestamps and speaker labels where reliable.
- Document extraction for facts, decisions, dates and entities.
- Image and screenshot understanding.
- Video summarisation with timestamped key moments.
- Linking visual evidence to the conversation or task that produced it.
- Search by semantic description and by source/time.

Example: find the screenshot of an error from a prior debugging session, then retrieve the conversation, cause and verified fix.

Important design points:
- Store original media separately from derived text and embeddings.
- Preserve timestamps and source links.
- Make OCR/transcription uncertainty visible.
- Apply retention, access control and deletion to originals and derived artifacts.
- Do not assume a visual model's interpretation is ground truth.

---

### P5 — RTX 5080 local intelligence infrastructure

**Goal:** Use the local PC as a privacy-preserving, multi-workload AI server.

The RTX 5080 configuration discussed for this project has 16 GB VRAM. Plan around that constraint; do not assume several large models can remain resident simultaneously.

#### 3.17 Task-specific model roles

Benchmark separate models for:
- Main reasoning and planning.
- Fast classification and extraction.
- Coding and repository work.
- Embeddings.
- Reranking.
- Vision and document understanding.
- Speech recognition and synthesis.

Choose models from measured task performance, latency, memory use and licensing—not leaderboard position alone.

#### 3.18 GPU-aware scheduler

Potential capabilities:
- Model registry and capability metadata.
- VRAM and system-memory monitoring.
- Priority queues for interactive versus background work.
- Model load/unload and keep-alive policies.
- Quantisation and context-length profiles.
- CPU fallback for appropriate lightweight tasks.
- Batch extraction/embedding during idle periods.
- Interactive workload reservation.
- Backpressure when memory or compute is constrained.
- Per-task latency and resource telemetry.

#### 3.19 Inference backend abstraction

Keep the application independent of a single serving runtime. Benchmark appropriate options such as Ollama, llama.cpp and vLLM against the actual models and workloads. Keep routing compatible with existing LiteLLM and locality rules.

**Acceptance criteria**
- No sensitive prompt silently falls back to a cloud provider.
- The scheduler reports why a task waited, moved or failed.
- Interactive tasks are not starved by batch work.
- Resource contention is measurable and recoverable.

---

### P6 — Experimental research directions

These are research candidates, not committed implementation requirements.

#### 3.20 Counterfactual decision memory

Preserve options considered, expected outcomes and actual outcomes. Later answer “what might have happened if I had chosen the alternative?” as a clearly labelled hypothetical, never as a remembered fact.

#### 3.21 Concept evolution

Detect recurring patterns across episodes and propose higher-level concepts. Require evidence and allow user review before turning a hypothesis into a stable belief.

#### 3.22 Predictive memory

Predict recurring needs or likely future events from history. Store prediction, evidence, horizon, confidence and eventual outcome separately from facts. Evaluate calibration and false alarms.

#### 3.23 Experience-based computer use

Learn which application workflows and commands worked in previous tasks. Store verified procedures and UI observations, but recheck the current screen, application version, permissions and action safety before execution.

---

## 4. Architecture recommendations

### 4.1 Keep deterministic boundaries around probabilistic intelligence

Keep these operations deterministic and auditable wherever possible:
- Tenant isolation and authorization.
- Data access and retention.
- Temporal validity rules.
- Provenance links.
- User corrections and deletion.
- Permission checks and action approvals.
- Transaction boundaries and idempotency.
- Audit logging.

Use models as proposal generators for:
- Extraction and classification.
- Semantic interpretation.
- Causal-link suggestions.
- Summarisation.
- Reranking.
- Planning.

Validate model output before it changes authoritative state.

### 4.2 Make memory explainable

A conceptual memory record should be able to expose something like:

```yaml
claim: "Prefers FastAPI for backend APIs"
source:
  type: conversation
  id: "<source-id>"
  occurred_at: "<source-time>"
  recorded_at: "<ingestion-time>"
extraction:
  model: "<model-version>"
  pipeline: "<pipeline-version>"
  confidence: 0.0
confirmation:
  status: unconfirmed
temporal:
  valid_from: null
  valid_until: null
relationships:
  derived_from: []
  related_to: []
```

This is an illustrative contract, not a prescribed database schema. Reuse current fields and tables where they already satisfy the requirement.

### 4.3 Version model-dependent artifacts

Embedding and extraction outputs depend on model and pipeline versions. Record those versions and plan safe re-embedding/re-extraction, including a way to compare old and new results before switching active versions.

### 4.4 Keep storage replaceable

Avoid unnecessary dependence on one storage or graph implementation. Preserve repository abstractions and test contracts. Only split storage systems when measured scale, operational risk or workload isolation justifies the added complexity.

### 4.5 Security and privacy are cross-cutting requirements

- Preserve the project's local-only handling of personal data.
- Treat redaction as defence-in-depth, not a guarantee that arbitrary personal context is safe to send externally.
- Keep personal tools unavailable to cloud-routed models.
- Keep unclassified side effects fail-closed.
- Require approval for sensitive or irreversible actions.
- Audit access, export, correction and deletion.
- Test prompt injection and untrusted instructions in imported documents, web pages, emails and tool outputs.
- Ensure memory retrieval does not bypass source permissions.

---

## 5. Suggested implementation sequence

Do not attempt all phases simultaneously. A practical sequence:

| Step | Work | Exit condition |
|---|---|---|
| 0 | Audit current implementation and specs against this roadmap | Every item labelled implemented / partial / designed / new / defer |
| 1 | Select one representative memory flow and trace source → extraction → storage → retrieval → answer | End-to-end evidence and failure map |
| 2 | Add/verify provenance and temporal correctness | Historical and current-state tests pass |
| 3 | Add calibrated abstention and conflict tests | Unsupported answers are measurably reduced |
| 4 | Establish benchmark baseline | Reproducible baseline report |
| 5 | Implement one retrieval improvement at a time | Improvement demonstrated without regression |
| 6 | Connect cross-domain context and knowledge gaps | Multi-domain test cases pass |
| 7 | Add durable assistant task checkpoints | Restart/resume and safety tests pass |
| 8 | Expand multimodal and GPU scheduling workloads | Resource, privacy and quality targets pass |

### First milestone recommendation

**Milestone 1: Trustworthy Memory Baseline**

Scope:
1. Audit one end-to-end memory path.
2. Verify provenance fields and source retention.
3. Verify temporal updates and correction history.
4. Add test cases for stale, conflicting and missing facts.
5. Establish recall, extraction and abstention metrics.
6. Produce a baseline report before changing ranking or model strategy.

Deliverables:
- Architecture/code audit notes.
- Gap list linked to concrete modules and tests.
- Benchmark dataset and reproducible runner.
- Baseline metrics and failure examples.
- Small, reviewable implementation PRs.

---

## 6. Definition of done for roadmap items

Every feature should have:

1. **Problem statement:** a real failure or user need.
2. **Current-state audit:** proof it is not already implemented adequately.
3. **Design:** data contract, API/events, trust boundary and failure modes.
4. **Privacy/security review:** locality, access, retention, deletion and prompt-injection implications.
5. **Evaluation:** representative positive, negative and adversarial cases.
6. **Operational metrics:** latency, resource use, errors and cost where relevant.
7. **Documentation:** update the authoritative spec and generated state as appropriate.
8. **Migration/recovery plan:** if persisted data or schema changes.
9. **Small implementation steps:** one independently reviewable change at a time.

---

## 7. Risks and anti-goals

### Risks to actively manage

- **Overbuilding:** too many subsystems before validating daily usefulness.
- **False certainty:** treating LLM output or semantic similarity as truth.
- **Temporal confusion:** surfacing an old fact as current.
- **Filter bubbles:** reinforcing old preferences without reconsideration.
- **Memory poisoning:** untrusted imported content becoming authoritative memory.
- **Privacy leakage:** personal details reaching cloud models through free text or tool context.
- **GPU contention:** background work degrading interactive latency.
- **Operational complexity:** too many databases, models and services for a single-PC deployment.
- **Unmeasured complexity:** adding features without proving their value.

### Anti-goals

- Do not add another vector database just because it is popular.
- Do not add more personas without a demonstrated task need.
- Do not make every conversation detail a permanent memory.
- Do not let a model directly rewrite authoritative facts without validation.
- Do not treat predictions, hypotheses, inferred preferences and verified facts as equivalent.
- Do not grant persistent action permissions merely because a similar task succeeded previously.
- Do not optimize benchmark scores at the expense of real user usefulness and privacy.

---

## 8. Research references to investigate

These are starting points for evaluation and design research, not endorsements or proof that a particular implementation is best.

- **LongMemEval:** long-term conversational memory evaluation — https://github.com/xiaowu0162/LongMemEval
- **LoCoMo:** long conversational memory benchmark — https://snap-research.github.io/locomo/
- **MemoryAgentBench:** benchmark for memory in agent systems — https://github.com/HUST-AI-HUST/MemoryAgentBench
- **Mem0:** memory framework and implementation to compare — https://github.com/mem0ai/mem0
- **Zep / Graphiti:** temporal knowledge graph memory approaches — https://github.com/getzep/graphiti
- **Letta:** agent-managed memory/runtime concepts — https://github.com/letta-ai/letta
- **Ollama:** local model runtime — https://github.com/ollama/ollama
- **llama.cpp:** local inference and quantisation — https://github.com/ggml-org/llama.cpp
- **vLLM:** inference serving and scheduling — https://github.com/vllm-project/vllm

Before adopting any external dataset, library or model, verify current maintenance, licence, data terms, hardware requirements and security posture.

---

## 9. Review checklist

Use this checklist during repository review and planning:

- [ ] Audit each proposal against current code and specs.
- [ ] Mark existing features that already satisfy the requirement.
- [ ] Identify the highest-impact memory correctness failure.
- [ ] Trace one memory from source to final assistant answer.
- [ ] Confirm temporal and provenance behaviour.
- [ ] Establish a benchmark baseline.
- [ ] Select one small P0 implementation.
- [ ] Add regression tests before changing behaviour.
- [ ] Verify local/cloud routing and privacy boundaries.
- [ ] Verify fail-closed action approval and task recovery.
- [ ] Reassess roadmap priorities after real usage.

**Recommended starting point:** Complete the current-state audit and trustworthy-memory baseline before implementing the more experimental features.
