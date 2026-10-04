# Can a relevance score tell us when to say "I don't know"?

Measured 2026-10-04 against the live instance (601 memories, tenant `raja`,
hybrid search, `include_pending`), using the 23 questions in `recall_gold.yaml`
— 20 the store can answer and 3 it cannot.

**Answer: no. Not from ranking scores alone.**

Recording it because the opposite is an attractive assumption. `/search/`
returns `limit` rows for any query, so the obvious next step after exposing a
score is "reject anything below X", and a plausible-looking X is easy to pick
and impossible to justify.

## What was measured

For every question, the top-10 scores, reduced four ways:

| signal | what it asks |
|---|---|
| `top` | is the best result good in absolute terms? |
| `margin` | does the winner stand clear of second place? |
| `ratio` | is the winner better than the pack, proportionally? |
| `spread` | …and in absolute terms? |

The last three test the shape rather than the level: the intuition that when a
store holds an answer one result stands out, and when it does not, the top ten
are uniformly mediocre.

## Results

| signal | answerable (min/median/max) | unanswerable (min/median/max) | separable? |
|---|---|---|---|
| `top` | 0.2717 / 0.3923 / 0.5285 | 0.3103 / 0.3170 / 0.3221 | **no** |
| `margin` | 0.0002 / 0.0156 / 0.1690 | 0.0062 / 0.0185 / 0.0464 | **no** |
| `ratio` | 1.0336 / 1.1442 / 1.6511 | 1.0352 / 1.1265 / 1.1989 | **no** |
| `spread` | 0.0122 / 0.0506 / 0.2080 | 0.0108 / 0.0349 / 0.0534 | **no** |

Every one overlaps. The clearest case is `top`: "what is my favourite
restaurant", which the store knows nothing about, scores **0.3221** — higher
than `domain-focus` at **0.2717**, a question it answers correctly at rank 2.
Any floor that rejects the restaurant also rejects a real answer.

## Why

Cosine similarity between a query and arbitrary text does not approach zero
with a modern embedding model; it sits in a narrow band. With 600 memories,
*something* is always moderately close to any sentence. The hybrid score adds
`ts_rank`, which contributes nothing when none of the query's words appear —
exactly the case where a strong signal is wanted.

## What this does and does not license

The score is still worth returning, and it is returned:

- it **orders** results honestly, which is what a ranking score is for;
- a caller can compare scores **within one response**;
- the UI can show relative confidence.

It does **not** support a global threshold, and `MemoryResponse.score` says so
in its own description. The abstention cases in `recall_gold.yaml` therefore
stay reported rather than scored.

## What would work

Not pursued here, in rough order of cost:

1. **Ask the model.** `/search/ask` already sends retrieved memories to a local
   model; instructing it to answer "I don't know" when they do not address the
   question moves the judgement to something that reads meaning rather than
   distance. Cheapest real option.
2. **A cross-encoder rerank** of the top-k. Scores a query and a passage
   together instead of comparing two independent embeddings, and is far better
   separated at the low end. Costs a model and ~100ms.
3. **A calibrated classifier** over the signals above plus features the ranker
   does not use (query term coverage, result agreement). Needs labelled data
   this instance does not have yet — which is what the gold set would grow into.

## Reproducing

The two scripts live in the session scratchpad rather than the repo; both are
about twenty lines of httpx over `recall_gold.yaml`, and the numbers above are
the whole of their output. Re-measure after any change to the ranker weights,
the embedding model, or the corpus size — this result is a property of all
three, not a law.
