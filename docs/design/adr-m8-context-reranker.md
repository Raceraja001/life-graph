# ADR: local reranker for the M8 context snapshot

- Status: **decided — not adopted now** (2026-11-28). Revisit after the structural recall fixes land.
- Decider: the lead engineer, under the owner's "you decide and proceed" (2026-11-28).
- Context: [precision audit](../audits/2026-11-28-m8-context-precision-evaluation.md) §5 and §5.1.

## Question

Should the snapshot rescore its candidates with a local cross-encoder before the relevance cut, to lift precision towards the 0.70 target?

## What was measured

Everything ran on the 45-question synthetic eval set, never on owner memories.

- **Model:** `BAAI/bge-reranker-v2-m3` (Apache-2.0, multilingual). It runs fp16 on the local RTX 5080 from the Hugging Face cache, offline.
- **Candidates:** the snapshot under B + C, with no relevance cut. That gives 10.9 items per question at recall 0.946.
- **Comparison:** the cross-encoder's order against the existing bge-m3 cosine order, at the same number of items. Cut policies tried were top-k, absolute probability, and a logit margin from the top hit.
- **Script and results:** `evals/context_quality/precision-2026-11-28/rerank/`.

| Policy (all 45 questions) | Precision | Recall | Items per question | Owner's ten P / R |
|---|---|---|---|---|
| Candidates, no cut | 0.356 | 0.946 | 10.9 | 0.57 / 0.87 |
| Top 5, cosine order | 0.577 | 0.677 | 4.7 | 0.76 / 0.55 |
| Top 5, reranker order | 0.642 | 0.763 | 4.7 | 0.78 / 0.58 |
| Top 8, cosine order | 0.435 | 0.763 | 7.4 | 0.69 / 0.71 |
| Top 8, reranker order | 0.483 | 0.860 | 7.4 | 0.69 / 0.74 |
| Reranker, logit margin 8, keep ≥ 5 | 0.457 | 0.925 | 8.0 | 0.57 / 0.82 |
| Rules, recall config (B + C + F, floor 0.70) | 0.467 | 0.928 | 8.4 | 0.70 / 0.83 |

Other properties measured:

- **Determinism:** identical scores on two full passes (maximum difference 0.0).
- **Latency:** p50 19 ms, p95 52 ms per question, on top of the snapshot's ~40 ms.
- **Absolute probabilities are uninformative:** almost every pair scores below 0.005. Only rank and margin policies work.
- **Zero-tolerance metrics:** forbidden-as-current stays 0, because a reranker only removes items.

## Decision

**Do not add the reranker to the snapshot now.**

1. **It orders better, but does not move the precision–recall frontier.**
   - At equal size it beats cosine by about 5–6 precision points and 6–10 recall points.
   - At recall ≥ 0.90, though, it lands where the deterministic rules already are (0.46 vs 0.47).
   - It does not reach 0.70 precision at any recall the targets allow.
2. **The gap is structural, not ranking.**
   - Broad questions ("my current priorities", "my finances") need 6–8 records each.
   - Several of those records share no words or meaning with the question. They are goals, open intentions with no due time, and linked records.
   - A per-record relevance score cannot find them. Types and links can.
3. **Cost without gain.** The reranker would add:
   - a 2.3 GB GPU model, on a GPU that yields to speech;
   - a torch runtime dependency, which Life Graph does not have today;
   - a failure mode (GPU busy or out of memory) to the snapshot path;
   - all for no improvement at the recall the targets require.

## What would change this

Re-run `rerank/rr_score.py` on the new candidates after the structural recall fixes land (goal kind, intentions with no due time, overview questions). Revisit if a reranker then reaches precision ≥ 0.60 at recall ≥ 0.92 on the held-out split.

If adopted, it must meet all of these:

- **Local-only:** the model is served on 127.0.0.1, never a cloud endpoint, and never the :11435 chat server.
- **Determinism contract:** a fixed model revision and fp16 batch order, with a test that two passes give identical scores.
- **Fail-open to the rules path:** on a timeout (budget 80 ms) or error, the snapshot falls back to the B + C + F result and records the reason in the trace, with no content.
- **Default-off:** behind a setting, with a shadow comparison first.

## Alternatives considered

- **The existing local LLM judge (from `/search`):**
  - It is non-deterministic and takes hundreds of milliseconds per call.
  - It does not address the structural gap.
  - Rejected for the snapshot.
- **A fixed cap:** it costs recall (0.96 → 0.67 at 10 items). Rejected in the audit.
