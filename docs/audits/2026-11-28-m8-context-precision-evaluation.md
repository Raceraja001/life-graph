# M8 context precision evaluation, 2026-11-28

**Scope:** an evaluation and engineering study. It made no change to production behaviour, configuration, flags, prompts or schema, and no memory was merged or deleted. Everything ran on synthetic data on the test DB (`life_graph_dev_test`), embedded with `bge-m3` on local Ollama, which is the production embedder. It made no cloud model calls.

**Code:**
- Master is `f534b7ac`.
- The experiment options are in **PR #454** (`eval/m8-precision-experiments`, unmerged).
- The baseline was run on master. The experiments were run on #454, where every option is off by default and a sha256 identity test pins the snapshot that today's settings produce.

## 0. Answers

1. **Why is precision low?** Mainly because of how the snapshot is built, not because retrieval is weak.
   - Every snapshot carries about 19 items, whatever the question: 10 search hits, the expansions, all current decisions, and every intention due within 14 days.
   - A question's relevant set has a median of 5 records, so even a perfect picker could not score above about 0.30 at that size.
   - 49% of all noise is the standing decision/intention block. Its precision is 0.12.
2. **Which improvement gives the largest measurable gain?** **B (query-type gating)**, combined with **F (an adaptive relevance cut on raw cosine)**.
   - Neither works well alone: B alone moves precision 0.21 → 0.31, and F alone 0.21 → 0.25 at a recall cost.
   - Together on the tune split, precision goes 0.21 → 0.47.
   - **C (typed links)** adds no precision, but it is what keeps recall up: it fixes F2.
3. **Which improvements give precision at the cost of recall?**
   - **F (cut)**, and a **fixed cap**: `--max-items 10` takes recall from 0.96 to 0.67.
   - **G (hub penalty)**, when it is combined with F.
   - The losses fall on broad owner questions that need many records, such as O9 and O10 ("my finances").
4. **Can we reach the targets without weakening safety?** **No, not with deterministic rules.**
   - The best safe configuration reaches about **0.47–0.55 precision** across all 45 questions, against a target of 0.70.
   - Its recall is **0.93**, so the target of ≥ 0.90 is met; on the held-out split it is 0.88.
   - Every safety metric holds in every run: leaks 0, cloud calls 0, forbidden-as-current 0, provenance 1.00, abstention 1.00.
   - Reaching 0.70 needs ranking that tells near-topic memories apart, and no score threshold separates them. That requires a local reranker or the existing judge. Either one breaks the snapshot's deterministic "no model, same output" contract, which is an owner decision (§6).
   - **The critical-question target (≥ 0.95) is not met even by the baseline** (0.88 on the owner's ten).
5. **Does it now retrieve the right context rather than merely similar memories?** It is better, but only partly.
   - With B + C + F, snapshots shrink from 18.6 to 8.4 items. Precision roughly doubles on every split, and the owner's-ten precision goes 0.41 → 0.70.
   - The decision and intention noise is mostly gone.
   - Loose semantic neighbours and the "hub" records remain. Three baseline misses remain too (O1, O2, O3), because retrieval ignores the type of a record, and an intention with no due time is unreachable.
6. **What should the next M8 milestone implement?** See §7. In short:
   - promote B + C + F behind a default-off setting, with its own shadow comparison;
   - fix the three structural recall misses;
   - then decide on a local reranker, measured against these numbers.
7. **Is Life Graph ready for proactive context briefs?** **Not yet.**
   - Critical-question recall is 0.74–0.88, under the 0.95 target.
   - Precision is about 0.5, so briefs would carry about one irrelevant record per relevant one.
   - None of these improvements is in production or verified on real data.

| Status | Item |
|---|---|
| Implemented | options A–G, the eval flags `--experiments`, `--xp-set`, `--split` and `--max-items`, per-item logs, and precision without the standing block (PR #454) |
| Tested | unit tests (56 experiment and identity tests) and integration tests (CI); the full eval matrix below on the test DB |
| Merged | **nothing**: #454 and this audit wait for owner approval |
| Deployed | **nothing** |
| Operationally verified | **nothing**: no real-data run; production snapshots are unchanged (shadow mode as before) |
| Not verified | how these options behave on the owner's real memories; the cost of the G probes at scale; the reranker option |

## 1. Current state, inspected first

- **Already landed since the 2026-11-26 audit:**
  - P0 fixes D1–D10 (#413–#417);
  - typed relations and CONTRADICTS conflicts (#419);
  - owner disputes (#420);
  - the sufficiency check (#421);
  - the ingestion ADR steps (#429–#441);
  - the ingest eval arm (#443, #445);
  - the gap fixes (#447–#450).

  What the earlier audit listed as forbidden-as-current, temporal and abstention defects are now at target in this eval.
- **Production right now:**
  - releases up to `prod-20261128-1110`;
  - flags on: `ingest_world_time`, `ingest_world_end`, both M8 shadow flags;
  - embedder `bge-m3` on Ollama.
- **Retrieval settings in production:** no prod setting changes snapshot retrieval apart from the embedder, which was checked against the prod `.env`. So the `bge-m3` arm is production-equivalent.
- **Open PRs:** none affecting this area, apart from #454.

## 2. Baseline (master, bge-m3, all 45 questions)

Columns:
- **P** is precision;
- **P w/o standing** is precision with the standing decision/intention items left out;
- **R** is recall;
- **cur/hist** is the current-vs-historical check;
- **rel both / rel explicit** are relationship accuracy;
- **prov** is provenance accuracy;
- **abstain** is abstention accuracy.

| category | n | P | P w/o standing | R | noise | cur/hist | temporal | rel both | rel explicit | conflicts | prov | origin | abstain | leaks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O owner's ten | 10 | 0.41 | 0.41 | 0.88 | 112 | 0.95 | 0.96 | 0.50 | 0.50 | 0.67 | 1.00 | 1.00 | 1.00 | 0 |
| A personal | 5 | 0.16 | 0.26 | 1.00 | 81 | – | – | – | – | – | 1.00 | 1.00 | 1.00 | 0 |
| B professional | 5 | 0.24 | 0.38 | 1.00 | 73 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| C financial | 5 | 0.20 | 0.35 | 1.00 | 80 | 1.00 | 1.00 | – | – | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| D learning | 4 | 0.23 | 0.38 | 1.00 | 61 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| E temporal | 5 | 0.16 | 0.26 | 1.00 | 53 | 1.00 | 1.00 | 1.00 | 0.00 | – | 1.00 | 1.00 | 1.00 | 0 |
| F relationships | 5 | 0.26 | 0.38 | 0.93 | 72 | – | 1.00 | 0.78 | 0.44 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| G uncertainty | 6 | 0.16 | 0.27 | 1.00 | 97 | – | – | – | – | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| **micro, all 45** | 45 | **0.25** | 0.34 | **0.94** | 629 | | | | | | | | | 0 |

- **Snapshot size:** 18.6 items per question.
- **Latency over 132 runs:** p50 33.5 ms, p95 40.7 ms.
- **Zero-tolerance checks:** leaks 0, cloud calls 0, forbidden-as-current 0, rows left 0.
- **O6 change detection:** 7/7.
- **Per question:** relevant and irrelevant records retrieved and missing required records are in Appendix A. Every noise item is classified in the root-cause file (Appendix B).

## 3. Root causes

The full per-item analysis is in Appendix B, `root_causes.md` (629 noise items, each with one primary cause, the reproduction question, file:line and the proposed correction).

| Cause | Noise items | Share | Example | Why it got in | Correction | Regression risk |
|---|---|---|---|---|---|---|
| 7. Decision/intention block mixed in | 311 | 49% | O2 "my goals": 3 decisions and 5 intentions are added | `snapshot.py:1235-1245`, `:1268-1273`: every current decision and every intention due within 14 days are added to every snapshot | **B**: keep them when the question asks for that kind or their words support the question | Recall falls if this is done blindly; B keeps the standing items the question asks for (A2, F1, F2, D1 covered) |
| 1. Loose semantic similarity | 103 | 16% | O2: `p_constraint_travel` | 10 search slots always filled; the RRF score has no floor (`retrieval.py:33`, `postgres.py:642-649`) | **F**: a cut on raw cosine relative to the top hit | Broad questions lose required items (O9, O10) |
| 10. Top-K fill | 73 | 12% | O3: `f_fund_old` | `CANDIDATES=10` regardless of question | **F** | as above |
| 8. Generic "hub" personal records | 60 | 10% | `p_constraint_travel` in 21 questions | generic constraints are close to many questions | **G**: penalise similarity to generic probes; works only with F | It took F2 `w_proj_rp` and O7 `w_proj_billing` in the tuned setting |
| 2. Keyword overlap, different meaning | 60 | 10% | take / take-home, book / booking, leave / leaving, "000" in ₹ amounts | the keyword path matches any word | **B's** support rule: a whole word, or two words of a longer term | small |
| 11. Gold too narrow (scoring artefact) | 10 | 2% | O1 `w_not_leaving` | defensible context outside the gold set | none; widening the gold adds only about +0.012 | – |
| 9. Query ambiguity | 8 | 1% | O3 "commitments" read as financial | – | B type classes | – |
| 3. Historical competing with current | 4 | 1% | `w_dep` resolved but still active | a missing supersession at ingestion (ingestion ADR) | ingestion, not retrieval | – |
| 4 pending/superseded/expired, 5 duplicates, 6 missing relationship | 0 | – | – | the state filters work. Cause 6 shows up only as **recall** misses: F2 `w_task_demo` is reachable only by a typed link, and O3 `i_aws_book` has no due time | **C** for F2; a structural fix for O3 | – |

**The embedder is not the lever.** Decision and intention noise is identical in the hashing and bge-m3 arms (323 vs 323). bge-m3 mostly buys recall: 81/97 → 91/97 required records found.

## 4. Experiments

### 4.1 Method

- **Splits:** a fixed split by sha256 of the question id: 24 questions for **tune** and 21 for **test**.
- **Tuning:** options and constants were chosen on the **tune** split only. The two candidate configurations were run **once** on the held-out test split, and on all 45 for the category tables.
- **Independence:** each option was run alone first, then in combinations.
- **Reproducing:** commands are in §8. Every run records its options and constants in `report["run"]`.

### 4.2 One option at a time (tune split, 24 questions, bge-m3)

| Run | P | R | P w/o standing | items/q | p95 ms | Note |
|---|---|---|---|---|---|---|
| baseline | 0.208 | 0.957 | 0.293 | 18.9 | 39 | |
| A rank | 0.208 | 0.957 | 0.293 | 18.9 | 50 | reorders only; needs a cut to matter |
| B query_type | **0.306** | 0.957 | 0.310 | 11.3 | 47 | the largest single gain, with no recall loss |
| C links | 0.207 | **0.978** | 0.293 | 18.8 | 47 | recall only: fixes F2 |
| D dedupe | 0.208 | 0.957 | 0.293 | 18.9 | 41 | no duplicates exist in the data, so no effect |
| E evidence | 0.208 | 0.957 | 0.293 | 18.9 | 39 | tie-breaks only; no effect alone |
| F budget (cosine cut) | 0.247 | 0.913 | 0.458 | 14.0 | 44 | costs recall alone |
| F + G (hub) | 0.267 | 0.913 | 0.578 | 12.6 | 55 | |
| A + E, fixed `--max-items 10` | 0.277 | **0.674** | 0.277 | 9.6 | 34 | **a fixed cap is harmful** |

### 4.3 Combinations and tuning (tune split)

| Run | P | R | items/q | p95 ms |
|---|---|---|---|---|
| B + F | 0.465 | 0.913 | 6.5 | 45 |
| B + C + F | 0.453 | 0.935 | 6.7 | 53 |
| all of A–G | 0.397 | 0.935 | 7.9 | 60 |
| B + C + F, `COSINE_FLOOR=0.70` | 0.401 | **0.978** | 8.2 | 40 |
| B + C + F, floor 0.75 | 0.434 | 0.935 | 7.3 | 47–52 |
| B + C + F + G, floor 0.75 | **0.493** | 0.935 | 6.2 | 63 |
| B + C + E + F, floor 0.75 | 0.358 | 0.935 | 9.1 | 54 |
| B + C + F, `MIN_KEEP` 4 / 5 | 0.434 / 0.407 | 0.935 | 7.3 / 7.9 | 41 / 42 |

- `COSINE_GAP` (0.08–0.16) had no effect.
- E lowers precision when combined, because it protects both sides of conflicts.

Two candidates were taken forward:
- **"recall config":** B + C + F with floor 0.70;
- **"precision config":** B + C + F + G with floor 0.75.

### 4.4 Held-out test split (21 questions, run once)

| Run | P | R | P w/o standing | items/q | p95 ms |
|---|---|---|---|---|---|
| baseline | 0.301 | 0.922 | 0.403 | 18.4 | 34 |
| recall config | **0.539** | 0.882 | 0.513 | 8.6 | 48 |
| precision config | **0.597** | 0.824 | 0.576 | 6.9 | 57 |

Tuned gains carry over to the unseen questions. The precision gain holds, and **the recall cost is larger on held-out questions** (−0.04 / −0.10) than on tune.

### 4.5 All 45 questions, by category (baseline → recall config → precision config)

| category | P base | P recall cfg | P prec cfg | R base | R recall cfg | R prec cfg |
|---|---|---|---|---|---|---|
| O owner's ten (critical) | 0.41 | **0.70** | 0.75 | 0.88 | 0.83 | **0.74** |
| A personal | 0.16 | 0.38 | 0.50 | 1.00 | 1.00 | 1.00 |
| B professional | 0.24 | 0.44 | 0.49 | 1.00 | 1.00 | 1.00 |
| C financial | 0.20 | 0.47 | 0.60 | 1.00 | 1.00 | 1.00 |
| D learning | 0.23 | 0.49 | 0.49 | 1.00 | 1.00 | 1.00 |
| E temporal | 0.16 | 0.30 | 0.42 | 1.00 | 1.00 | 1.00 |
| F relationships | 0.26 | 0.37 | 0.44 | 0.93 | **1.00** | 0.93 |
| G uncertainty | 0.16 | 0.35 | 0.44 | 1.00 | 1.00 | 1.00 |
| **micro, all 45** | **0.250** | **0.467** | **0.545** | **0.938** | **0.928** | **0.876** |

**The other metrics for the recall config:**
- temporal 0.96 on O, 1.00 elsewhere;
- current-vs-historical 0.95 on O;
- relations explicit: O 0.50, F 0.56 (up from 0.44);
- conflicts unchanged;
- provenance 1.00 and abstention 1.00 everywhere;
- leaks 0, cloud calls 0, forbidden-as-current 0, rows left 0;
- latency p50 36.5 ms, p95 41.6 ms.

**The precision config** drops O's explicit relations to 0.00, and its latency is p50 50.6 ms, p95 57.3 ms (the G probe embeddings).

**Required records lost or gained, compared with the baseline:**

| q | Baseline missed | Recall config | Precision config |
|---|---|---|---|
| F2 | `w_task_demo` | **fixed** (C) | fixed, but loses `w_proj_rp` |
| O1 | `l_aws_goal`, `w_blocker` | same | same |
| O2 | `l_aws_goal` | same | same |
| O3 | `i_aws_book` | same | same |
| O7 | – | – | loses `w_proj_billing` |
| O9 | – | loses `f_emi` | loses `f_emi`, `f_fund_goal`, `f_husband_income_new` |
| O10 | `f_fund_old` | adds `f_husband_income_new` | adds `f_husband_income_new`, `f_salary_new` |

### 4.6 Baseline → recall config, every target metric

| Metric | Target | Baseline | Recall config | Met? |
|---|---|---|---|---|
| Overall precision | ≥ 0.70 | 0.250 | 0.467 (test 0.539) | **no** |
| Overall recall | ≥ 0.90 | 0.938 | 0.928 (test 0.882) | yes on all 45; **no** on held-out |
| Critical (owner's ten) recall | ≥ 0.95 | 0.88 | 0.83 | **no** (the baseline misses it too) |
| Cross-tenant leakage | 0 | 0 | 0 | yes |
| Cloud model calls | 0 | 0 | 0 | yes |
| Forbidden-as-current | 0 | 0 | 0 | yes |
| Provenance accuracy | 1.00 | 1.00 | 1.00 | yes |
| Abstention accuracy | ≥ 0.95 | 1.00 | 1.00 | yes |
| Temporal correctness | ≥ 0.95 | 0.96–1.00 | 0.96–1.00 | yes |

**No benchmark gaming:**
- no gold set was widened, and no case was added;
- the standing items are still scored;
- precision without the standing block is reported separately;
- tuning was done on a split, and the test split was run once.

## 5. Why 0.70 is out of reach for rules

- **The remaining noise, mostly loose neighbours and hubs, overlaps the relevant set in score.** No cosine floor or elbow separates them: the gap constant had no effect, and each step in the floor trades precision for recall nearly one-for-one (§4.3).
- **The remaining recall misses are structural, not ranking:**
  - goals are stored as ordinary memories with no type the retriever uses (O1, O2);
  - an intention with no due time is unreachable except by shared words (O3);
  - broad "overview" questions need many records, and a relevance cut removes the tail (O9, O10).
- **The next step up needs a judgement of relevance per record.** That means a local cross-encoder reranker, or the existing local judge used in `/search`, applied to the top ~20.
  - It stays local-only, but the snapshot stops being deterministic and gains latency.
  - That is an architectural decision for the owner, not something to slip in.

## 6. Recommended ranking and selection architecture

1. **Candidate generation (unchanged):**
   - hybrid search with `bge-m3`;
   - ASSOCIATED expansions, **plus typed-link expansion (C)** from the top 5 hits, tenant-checked, active, non-hostile, valid now.
2. **Query-type gate (B):**
   - deterministic, English, Tamil and Tanglish;
   - decisions and intentions are included when the question asks for their kind, or when their own words support a question term;
   - standing items the question asks for count as answering.
3. **Relevance cut on raw cosine (F):**
   - relative to the top hit, floor ≈ 0.70, always keeping ≥ 3;
   - only search hits and learned neighbours are cut, never conflicts, exclusions or abstention logic.
4. **Evidence and safety pass (unchanged):** provenance, origin labels, hostile handling, tenant filter, contradictions kept visible.
5. **Optional, needs an owner decision:** a local reranker over the top ~20 before step 3, with the determinism and latency trade-off measured against this audit's numbers.
6. **Do not adopt:**
   - **fixed caps**, which cost recall;
   - **G**, while it costs owner-question recall and about 15 ms;
   - **D**, which has nothing to dedupe today;
   - **E as a cut**: keep it only as a tie-break.

## 7. Prioritised implementation plan (each its own PR, no merge or deploy without approval)

1. **Merge #454** (experiment options, eval-only; default path byte-identical). Owner approval needed.
2. **Typed-link expansion (C) as a default-off setting** `context_typed_link_expansion`.
   - It is recall-only: +0.02 on tune, and fixes F2.
   - It is the smallest safe change.
   - It would be compared in shadow before any switch.
3. **The query-type gate and cosine cut (B + F) as one default-off setting** `context_precision_mode`.
   - Its own shadow comparison: the trace records both item counts, labels only.
   - The `shadow_context_structure.py` counts are extended.
4. **Structural recall fixes:**
   - give goals a type the retriever can use;
   - let open intentions with no due time be retrieved by meaning, not only words (O3);
   - make "overview" questions (O9 and O10 style) raise the cut's minimum. B already classifies them.
5. **Reranker ADR:** a local cross-encoder versus the existing judge, the determinism contract, latency budget and failure mode.
6. **Owner-question recall ≥ 0.95** as a gate before any proactive brief.

## 8. Reproducing

Run in a worktree of PR #454, with only the DB and Redis variables loaded and local Ollama `bge-m3`:

```
python scripts/eval_context_quality.py --arms hashing,bge-m3 --repeat 3 --output base.json               # baseline (also on master)
python scripts/eval_context_quality.py --arms bge-m3 --split tune --experiments B --output B_tune.json  # one option
python scripts/eval_context_quality.py --arms bge-m3 --experiments B,C,F --xp-set COSINE_FLOOR=0.70 --split test --output recall_test.json
python scripts/eval_context_quality.py --arms bge-m3 --experiments B,C,F,G --xp-set COSINE_FLOOR=0.75 --split test --output prec_test.json
```

The result JSONs for every run in this audit are committed under `evals/context_quality/precision-2026-11-28/`.

## Appendix A: per question, all 45 (bge-m3)

Each cell gives items / relevant / precision / recall.

| q | base items / rel / P / R | recall-cfg items / rel / P / R | prec-cfg items / rel / P / R | base missed | base noise |
|---|---|---|---|---|---|
| O1 | 19 / 13 / 0.68 / 0.75 | 15 / 10 / 0.67 / 0.75 | 15 / 10 / 0.67 / 0.75 | l_aws_goal, w_blocker | 6 |
| O2 | 19 / 7 / 0.37 / 0.75 | 3 / 3 / 1.00 / 0.75 | 3 / 3 / 1.00 / 0.75 | l_aws_goal | 12 |
| O3 | 20 / 6 / 0.30 / 0.83 | 6 / 6 / 1.00 / 0.83 | 6 / 6 / 1.00 / 0.83 | i_aws_book | 14 |
| O4 | 19 / 6 / 0.32 / 1.00 | 4 / 4 / 1.00 / 1.00 | 4 / 4 / 1.00 / 1.00 | – | 13 |
| O5 | 21 / 6 / 0.29 / 1.00 | 4 / 4 / 1.00 / 1.00 | 4 / 4 / 1.00 / 1.00 | – | 15 |
| O6 | 12 / 11 / 0.92 / 1.00 | 12 / 11 / 0.92 / 1.00 | 12 / 11 / 0.92 / 1.00 | – | 1 |
| O7 | 20 / 8 / 0.40 / 1.00 | 13 / 4 / 0.31 / 1.00 | 6 / 2 / 0.33 / 0.50 | – | 12 |
| O8 | 22 / 7 / 0.32 / 1.00 | 8 / 7 / 0.88 / 1.00 | 8 / 7 / 0.88 / 1.00 | – | 15 |
| O9 | 19 / 9 / 0.47 / 1.00 | 11 / 7 / 0.64 / 0.86 | 8 / 4 / 0.50 / 0.57 | – | 10 |
| O10 | 20 / 6 / 0.30 / 0.75 | 10 / 4 / 0.40 / 0.50 | 6 / 3 / 0.50 / 0.25 | f_fund_old | 14 |
| A1 | 20 / 1 / 0.05 / 1.00 | 7 / 1 / 0.14 / 1.00 | 3 / 1 / 0.33 / 1.00 | – | 19 |
| A2 | 19 / 6 / 0.32 / 1.00 | 13 / 5 / 0.38 / 1.00 | 9 / 5 / 0.56 / 1.00 | – | 13 |
| A3 | 19 / 4 / 0.21 / 1.00 | 4 / 3 / 0.75 / 1.00 | 4 / 3 / 0.75 / 1.00 | – | 15 |
| A4 | 20 / 1 / 0.05 / 1.00 | 3 / 1 / 0.33 / 1.00 | 3 / 1 / 0.33 / 1.00 | – | 19 |
| A5 | 19 / 4 / 0.21 / 1.00 | 10 / 4 / 0.40 / 1.00 | 9 / 4 / 0.44 / 1.00 | – | 15 |
| B1 | 19 / 3 / 0.16 / 1.00 | 12 / 4 / 0.33 / 1.00 | 11 / 4 / 0.36 / 1.00 | – | 16 |
| B2 | 19 / 3 / 0.16 / 1.00 | 12 / 3 / 0.25 / 1.00 | 10 / 2 / 0.20 / 1.00 | – | 16 |
| B3 | 19 / 7 / 0.37 / 1.00 | 7 / 6 / 0.86 / 1.00 | 6 / 5 / 0.83 / 1.00 | – | 12 |
| B4 | 19 / 6 / 0.32 / 1.00 | 8 / 5 / 0.62 / 1.00 | 8 / 5 / 0.62 / 1.00 | – | 13 |
| B5 | 20 / 4 / 0.20 / 1.00 | 11 / 4 / 0.36 / 1.00 | 4 / 3 / 0.75 / 1.00 | – | 16 |
| C1 | 20 / 5 / 0.25 / 1.00 | 6 / 3 / 0.50 / 1.00 | 3 / 3 / 1.00 / 1.00 | – | 15 |
| C2 | 20 / 3 / 0.15 / 1.00 | 8 / 3 / 0.38 / 1.00 | 3 / 2 / 0.67 / 1.00 | – | 17 |
| C3 | 20 / 3 / 0.15 / 1.00 | 3 / 2 / 0.67 / 1.00 | 3 / 2 / 0.67 / 1.00 | – | 17 |
| C4 | 20 / 4 / 0.20 / 1.00 | 10 / 3 / 0.30 / 1.00 | 8 / 3 / 0.38 / 1.00 | – | 16 |
| C5 | 20 / 5 / 0.25 / 1.00 | 7 / 5 / 0.71 / 1.00 | 3 / 2 / 0.67 / 1.00 | – | 15 |
| D1 | 20 / 6 / 0.30 / 1.00 | 12 / 6 / 0.50 / 1.00 | 12 / 6 / 0.50 / 1.00 | – | 14 |
| D2 | 20 / 4 / 0.20 / 1.00 | 3 / 3 / 1.00 / 1.00 | 3 / 3 / 1.00 / 1.00 | – | 16 |
| D3 | 20 / 5 / 0.25 / 1.00 | 10 / 5 / 0.50 / 1.00 | 10 / 5 / 0.50 / 1.00 | – | 15 |
| D4 | 19 / 3 / 0.16 / 1.00 | 10 / 3 / 0.30 / 1.00 | 10 / 3 / 0.30 / 1.00 | – | 16 |
| E1 | 1 / 1 / 1.00 / 1.00 | 1 / 1 / 1.00 / 1.00 | 1 / 1 / 1.00 / 1.00 | – | 0 |
| E2 | 3 / 1 / 0.33 / 1.00 | 3 / 1 / 0.33 / 1.00 | 3 / 1 / 0.33 / 1.00 | – | 2 |
| E3 | 21 / 2 / 0.10 / 1.00 | 5 / 2 / 0.40 / 1.00 | 3 / 2 / 0.67 / 1.00 | – | 19 |
| E4 | 19 / 1 / 0.05 / 1.00 | 12 / 1 / 0.08 / 1.00 | 6 / 1 / 0.17 / 1.00 | – | 18 |
| E5 | 19 / 5 / 0.26 / 1.00 | 6 / 3 / 0.50 / 1.00 | 6 / 3 / 0.50 / 1.00 | – | 14 |
| F1 | 19 / 6 / 0.32 / 1.00 | 15 / 5 / 0.33 / 1.00 | 13 / 5 / 0.38 / 1.00 | – | 13 |
| F2 | 20 / 7 / 0.35 / 0.80 | 14 / 7 / 0.50 / 1.00 | 9 / 5 / 0.56 / 0.80 | w_task_demo | 13 |
| F3 | 19 / 2 / 0.11 / 1.00 | 14 / 2 / 0.14 / 1.00 | 7 / 2 / 0.29 / 1.00 | – | 17 |
| F4 | 20 / 7 / 0.35 / 1.00 | 8 / 5 / 0.62 / 1.00 | 8 / 5 / 0.62 / 1.00 | – | 13 |
| F5 | 19 / 3 / 0.16 / 1.00 | 8 / 3 / 0.38 / 1.00 | 8 / 3 / 0.38 / 1.00 | – | 16 |
| G1 | 19 / 3 / 0.16 / 1.00 | 9 / 3 / 0.33 / 1.00 | 4 / 3 / 0.75 / 1.00 | – | 16 |
| G2 | 20 / 1 / 0.05 / 1.00 | 4 / 1 / 0.25 / 1.00 | 4 / 1 / 0.25 / 1.00 | – | 19 |
| G3 | 20 / 0 / 0.00 / 1.00 | 10 / 0 / 0.00 / 1.00 | 8 / 0 / 0.00 / 1.00 | – | 20 |
| G4 | 19 / 5 / 0.26 / 1.00 | 9 / 6 / 0.67 / 1.00 | 4 / 4 / 1.00 / 1.00 | – | 14 |
| G5 | 19 / 5 / 0.26 / 1.00 | 14 / 4 / 0.29 / 1.00 | 11 / 4 / 0.36 / 1.00 | – | 14 |
| G6 | 19 / 5 / 0.26 / 1.00 | 3 / 3 / 1.00 / 1.00 | 3 / 3 / 1.00 / 1.00 | – | 14 |

## Appendix B: root-cause analysis

`evals/context_quality/precision-2026-11-28/root_causes.md`: every noise item with its cause, file:line and proposed correction.
