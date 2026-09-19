"""fact_set_f1 — score an extraction as a set of facts, not a string.

Two extractions that say the same things in different words, or in a
different order, are equally good; none of the string scorers (exact_match,
contains, regex) can see that. Here each side is parsed into fact texts, both
are embedded with the app's own embedding model, and predicted facts are
matched one-to-one to expected facts greedily by cosine similarity above a
threshold. Precision, recall and F1 follow from the matches.

Deterministic and local (Charter invariant 1: the LLM is not the judge of
its own output), and it reuses the embedding backend already required to run.
"""

from __future__ import annotations

import json
import math
from collections.abc import Awaitable, Callable
from typing import Any

Embed = Callable[[list[str]], Awaitable[list[list[float]]]]


def parse_facts(raw: str) -> list[dict[str, Any]] | None:
    """``{"facts": [...]}`` -> list of fact dicts; None if not valid output."""
    try:
        data = json.loads(raw or "")
    except (json.JSONDecodeError, TypeError):
        return None
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, list):
        return None
    return [f for f in facts if isinstance(f, dict) and str(f.get("content", "")).strip()]


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


async def fact_set_f1(
    predicted: list[str],
    expected: list[str],
    embed: Embed,
    threshold: float,
) -> dict[str, float]:
    """Greedy one-to-one matching of predicted to expected facts.

    Both empty is a perfect score: "nothing worth keeping here" is a correct
    answer the user confirmed by rejecting everything.
    """
    if not predicted and not expected:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "matched": 0}
    if not predicted or not expected:
        return {
            "precision": 0.0 if predicted else 1.0,
            "recall": 0.0 if expected else 1.0,
            "f1": 0.0,
            "matched": 0,
        }

    vectors = await embed(predicted + expected)
    if len(vectors) != len(predicted) + len(expected) or any(not v for v in vectors):
        raise RuntimeError("embedding backend returned no vectors")
    pred_vecs = [_normalise(v) for v in vectors[: len(predicted)]]
    exp_vecs = [_normalise(v) for v in vectors[len(predicted) :]]

    pairs = sorted(
        (
            (sum(a * b for a, b in zip(p, e, strict=False)), i, j)
            for i, p in enumerate(pred_vecs)
            for j, e in enumerate(exp_vecs)
        ),
        reverse=True,
    )
    used_pred: set[int] = set()
    used_exp: set[int] = set()
    matched = 0
    for similarity, i, j in pairs:
        if similarity < threshold:
            break
        if i in used_pred or j in used_exp:
            continue
        used_pred.add(i)
        used_exp.add(j)
        matched += 1

    precision = matched / len(predicted)
    recall = matched / len(expected)
    f1 = 0.0 if matched == 0 else 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "matched": matched}


async def score_extraction(
    expected_raw: str, actual_raw: str, embed: Embed, threshold: float, pass_f1: float
) -> tuple[bool, float, str | None]:
    """EvalScorer-shaped result for one extraction case."""
    expected = parse_facts(expected_raw)
    if expected is None:
        return False, 0.0, "expected output is not a facts list"
    actual = parse_facts(actual_raw)
    if actual is None:
        return False, 0.0, "model output is not a valid facts list"
    result = await fact_set_f1(
        [str(f["content"]) for f in actual],
        [str(f["content"]) for f in expected],
        embed,
        threshold,
    )
    passed = result["f1"] >= pass_f1
    reason = (
        None
        if passed
        else (
            f"F1 {result['f1']:.2f} (precision {result['precision']:.2f}, "
            f"recall {result['recall']:.2f}; {result['matched']} of {len(expected)} "
            f"expected matched, {len(actual)} predicted)"
        )
    )
    return passed, round(result["f1"], 4), reason
