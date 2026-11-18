# Life Graph — Improvement Strategy & Engineering Prompt

**Status:** Proposed strategy  
**Purpose:** Record the architectural improvement recommendations from the Life Graph review and provide a reusable prompt for future engineering sessions.  
**Relationship to existing plans:** This document supplements `CHARTER.md`, `docs/STATE.md`, `docs/AI_WORK_ORDER.md`, and `docs/LIFE_GRAPH_EVOLUTION_ROADMAP.md`. It does not replace them or override the active work order.

---

## 1. Product direction

Evolve Life Graph toward a reliable, evidence-driven **Personal Agent OS** while preserving its identity as reusable memory and context infrastructure.

Keep the product boundary clear:

- **Life Graph:** model-agnostic memory, retrieval, knowledge graph, context, evidence, identity and decision intelligence.
- **Jarvis:** a personal assistant experience built on Life Graph: chat, voice, proactive help, integrations and controlled actions.
- **Agent execution:** task runtime, tools, delegation, durable workflows and recovery.
- **Governance:** trust, permissions, approvals, verification, audit and policy enforcement.

Life Graph should remain useful independently of Jarvis and should be consumable by other agents.

## 2. Core engineering priorities

### P0 — Safe execution and security

Complete the remaining high-priority security work before expanding autonomous computer use.

- Integrate real browser errands with a dedicated isolated browser runtime.
- Use a non-root browser container/process with minimal privileges.
- Enforce default-deny outbound networking through a controlled egress proxy.
- Protect against redirects to private/internal destinations, SSRF and DNS rebinding.
- Use an authenticated browser control channel.
- Prevent silent fallback to a less isolated browser driver.
- Test the actual execution path, tenant/session separation, cleanup and failure-closed behavior.
- Keep approvals bound to the exact action and consume one-use capabilities atomically.

**Important:** The latest reviewed work order reports exact-action approvals and durable authorization as implemented and tested, and (as of 2026-11-18) isolated browser runtime integration as complete. The current P0 is
the coding-agent execution runtime: `docs/work-orders/secure-execution-runtime.md`. Re-check the current default branch and deployed configuration before relying on that status.

### P1 — Trustworthy, explainable memory

Make it possible to answer not only *what does Life Graph remember?*, but also *why does it believe this, when was it true, and how certain is it?*

- Preserve source identity, source timestamps, ingestion timestamps and supporting spans where available.
- Maintain lineage from original evidence through extracted memories and derived summaries.
- Distinguish valid time (when something was true) from transaction time (when Life Graph learned it).
- Preserve corrections and historical states.
- Distinguish user-confirmed facts, inferred information and externally sourced information.
- Keep extraction confidence, source reliability, confirmation, freshness, contradiction status and retrieval relevance as separate signals.
- Do not present similarity or heuristic scores as calibrated factual confidence.
- Support abstention when evidence is missing, stale, conflicting or insufficient.
- Preserve deletion and retention semantics across original sources and derived artifacts.

### P1 — Evaluation laboratory

Prove that changes improve outcomes rather than relying on impressive demonstrations.

Evaluate:
- Extraction precision and recall.
- Retrieval precision/recall, including Recall@K.
- Temporal accuracy and historical retrieval.
- Correction and contradiction handling.
- Claim-level provenance/support.
- Abstention quality.
- Forgetting/deletion behavior.
- Security and authorization behavior.
- Latency, token use, CPU/RAM/VRAM and storage costs.

Build a private Life Graph regression set using synthetic and explicitly approved examples. Consider public research datasets such as LongMemEval, LoCoMo and MemoryAgentBench only after checking their current availability, licenses and suitability.

Compare the current baseline with alternatives one variable at a time:
1. Current retrieval baseline.
2. BM25/keyword changes.
3. Vector retrieval changes.
4. Graph expansion.
5. Reranking.
6. Multi-step retrieval.

Record dataset version, model/provider/version, prompt and extractor version, embedding model, configuration, metrics, cost, latency and failure examples. Keep tuning and held-out evaluation data separate.

### P2 — Decision and causal memory

Develop a coherent experience model that connects:

**Situation → Options → Decision → Rationale → Prediction → Outcome → Lesson**

- Preserve options considered and reasons for choosing one.
- Distinguish user-stated reasons from inferred explanations.
- Store predictions separately from facts.
- Record outcomes only when supported by evidence.
- Evaluate predictions against outcomes.
- Revisit old decisions when important circumstances change.
- Clearly label counterfactual reasoning as hypothetical, never as remembered fact.

The repository already has decision, prediction and calibration-related structures according to its reviewed state. Inspect and integrate those before proposing duplicate tables or services.

### P2 — Reliable agent execution

Borrow useful concepts from projects such as Nod and CompanyOS without copying their architectures wholesale.

- Durable task state and checkpoints.
- Explicit task ownership and completion conditions.
- Idempotency and safe retries.
- Recovery after process or machine restarts.
- Dependencies and bounded delegation.
- Typed, permissioned agent messages and shared artifacts.
- Independent verification of outputs.
- Clear separation between action authorization and result correctness.

An agent's claim that it finished a task must not, by itself, prove that the task succeeded.

### P3 — Local intelligence infrastructure

Use the local RTX 5080 (16 GB VRAM) as a measured experimental inference platform.

- Maintain a model registry with task capabilities and resource requirements.
- Benchmark separate models for reasoning, extraction, coding, embeddings, reranking, vision and speech.
- Measure VRAM/RAM use, latency, throughput and quality on actual Life Graph tasks.
- Explore model load/unload policies, priority queues and batch processing.
- Preserve strict local-only routing for personal information.
- Explain why a task waited, failed or used a particular backend.

Do not build a complex GPU scheduler until measurements demonstrate the need.

---

## 3. Research directions worth investigating

These are experiments, not immediate implementation commitments.

### A. Memory that understands its limitations

Life Graph should be able to explain whether a claim is explicitly stated, inferred, stale, contradicted or unsupported—and identify its evidence.

### B. Decision experience engine

Use accumulated decisions and observed outcomes to help users reason about future choices. Keep historical facts, predictions and hypothetical counterfactuals distinct.

### C. Retrieval that knows when to stop

Investigate adaptive retrieval: retrieve more when evidence is insufficient, stop when sufficient support is found, and abstain when more retrieval cannot resolve uncertainty. Evaluate quality, latency and cost together.

---

## 4. Recommended execution sequence

| Order | Work | Priority |
|---|---|---|
| 1 | Secure per-task execution runtime for coding agents (browser isolation: done) | P0 |
| 2 | Complete evidence-lineage and confidence evaluation | P1 |
| 3 | Establish reproducible memory benchmarks and regression datasets | P1 |
| 4 | Integrate decision, prediction and causal memory into one workflow | P2 |
| 5 | Improve durable agent execution, recovery and independent verification | P2 |
| 6 | Benchmark local models and introduce GPU-aware scheduling only if justified | P3 |

The active `docs/AI_WORK_ORDER.md` takes precedence for implementation sequencing where it defines a more specific security or correctness task.

---

## 5. Engineering method and definition of progress

Do not measure progress by feature count, endpoint count, table count, lines of code or test count alone.

For each significant improvement:

1. Understand the underlying computer science and security concepts.
2. Study at least two viable approaches.
3. Inspect relevant implementations in existing projects.
4. Inspect Life Graph's current implementation and tests.
5. Decide which approach fits the product constraints and explain why.
6. Write or update a focused technical specification.
7. Implement the smallest useful change.
8. Test normal cases, edge cases, failures, concurrency and adversarial cases as appropriate.
9. Measure correctness, latency, resource use and cost.
10. Record limitations, operational evidence and what would change the decision.

Use precise status labels:

- **Proposed:** an idea exists.
- **Designed:** a reviewed design/specification exists.
- **Implemented:** code/configuration exists.
- **Integrated:** the real application path uses it.
- **Unit-tested:** focused tests pass.
- **Integration-tested:** interacting components were exercised.
- **Adversarially tested:** relevant attack/failure scenarios were exercised.
- **Operationally verified:** deployed behavior was checked.
- **Complete:** all acceptance criteria have evidence.

A passing unit-test suite is not proof of production safety or operational correctness.

---

## 6. Reusable engineering prompt

Use the following prompt with a coding agent when starting a Life Graph improvement session. Replace the task line with one specific task.

```text
You are the senior engineer working on Raceraja001/life-graph.

TASK:
[Describe ONE specific improvement or investigation.]

GOAL:
Improve Life Graph as a reliable, evidence-driven Personal Agent OS without
adding features blindly or weakening existing design invariants.

MANDATORY FIRST STEPS:
1. Fetch and inspect the latest remote default branch and current commit SHA.
2. Synchronize the working tree safely. Never discard unrelated user changes.
3. Read CHARTER.md, docs/STATE.md, docs/AI_WORK_ORDER.md, and
   docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md.
4. Read the relevant specifications, architecture/security/operations docs,
   source code, migrations and tests.
5. Verify whether the task is already implemented, partially implemented,
   designed only, or genuinely missing. Do not duplicate existing capabilities.
6. Report the current state, evidence, risks and proposed smallest safe scope
   before editing.

ENGINEERING PRINCIPLES:
- Preserve the charter's design invariants and existing abstractions.
- Keep tenant isolation, authorization, privacy and retention deterministic.
- Treat model output, browser content, tool arguments and external data as
  untrusted.
- Keep action authorization separate from output verification.
- Fail closed for authorization, isolation, secret access and egress failures.
- Prefer small, reviewable changes over broad rewrites.
- Do not weaken, skip, delete or loosen tests to get a green result.
- Do not introduce a new table, service, framework or dependency unless the
  existing design cannot reasonably satisfy the requirement.
- Do not claim calibrated confidence, semantic entailment, production safety
  or operational verification without appropriate evidence.
- Keep documentation synchronized with actual implementation.

RESEARCH AND DESIGN:
1. Explain the underlying problem and relevant concepts.
2. Compare at least two reasonable approaches when alternatives exist.
3. Explain trade-offs: correctness, complexity, security, latency, cost,
   operability and future maintenance.
4. Recommend one approach and state what evidence could change that choice.
5. Define acceptance criteria and failure cases before implementation.

IMPLEMENTATION:
1. Make the smallest change that satisfies the agreed scope.
2. Add regression tests for confirmed bugs and security issues.
3. Test normal, boundary, failure, concurrency and adversarial cases as
   relevant.
4. Run focused tests first, then the appropriate broader test suite.
5. Report exact commands, results and known baseline failures.
6. Inspect the final diff for unrelated changes, secrets and weakened controls.

COMPLETION REPORT:
- Remote base commit and working commit.
- Files changed and behavior changed.
- Design choice and alternatives considered.
- Tests run with exact results.
- Security/privacy implications.
- Remaining gaps and risks.
- Status using: Proposed, Designed, Implemented, Integrated, Unit-tested,
  Integration-tested, Adversarially tested, Operationally verified, Complete.
- Documentation updated.
- Whether commit/push was performed; never claim it if it was not.

IMPORTANT:
Do not attempt to implement the entire roadmap in one session.
Work only on the specified task and its necessary dependencies.
If the task is too broad, break it into independently testable steps and
recommend the first step rather than starting a speculative rewrite.
```

---

## 7. Review note

This document records a strategic recommendation based on the repository review. It is not proof that every listed capability is missing. Always use the latest remote code, generated state, specifications and tests as the source of implementation truth.
