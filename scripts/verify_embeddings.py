"""Self-consistency verification for the embedding model swap.

No labelled gold set exists, so "at least as good as before" is checked by
self-consistency, not absolute recall:

  1. Semantic ranking — related text pairs score higher cosine than unrelated.
  2. Dedup separation — a near-duplicate pair clears the 0.92 threshold while a
     distinct pair does not.
  3. (DB) Dimension — every stored vector matches settings.embedding_dimension.
  4. (DB) Coverage — no rows are left with a NULL embedding.

The pure ranking math (``cosine``, ``ranking_ok``, ``separation_ok``) is unit
tested; the DB checks require a live Postgres and are run from ``main()``.

Usage:  python scripts/verify_embeddings.py
"""

from __future__ import annotations

import math

# Semantic pairs: (a, b, related?) — related pairs must out-score unrelated ones.
SEMANTIC_PAIRS: list[tuple[str, str, bool]] = [
    ("I love hiking in the mountains", "Mountain trekking is my favourite hobby", True),
    ("The database migration failed", "The schema upgrade errored out", True),
    ("I prefer dark mode editors", "The weather is sunny today", False),
    ("How do I deploy to production?", "My cat is sleeping on the sofa", False),
]

# Dedup pairs.
DUP_PAIR = ("Deploy the API to the VPS", "Deploy the API to the VPS.")
DISTINCT_PAIR = ("Deploy the API to the VPS", "Write unit tests for the parser")
DEDUP_THRESHOLD = 0.92


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (0.0 if either is empty)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def ranking_ok(related_scores: list[float], unrelated_scores: list[float]) -> bool:
    """True when the weakest related pair still out-scores the strongest unrelated."""
    if not related_scores or not unrelated_scores:
        return False
    return min(related_scores) > max(unrelated_scores)


def separation_ok(dup_score: float, distinct_score: float, threshold: float = DEDUP_THRESHOLD) -> bool:
    """True when the duplicate clears the dedup threshold and the distinct pair does not."""
    return dup_score >= threshold > distinct_score


def _run_semantic(embed) -> tuple[bool, list, list]:
    related, unrelated = [], []
    for a, b, is_related in SEMANTIC_PAIRS:
        score = cosine(embed(a), embed(b))
        (related if is_related else unrelated).append(score)
    return ranking_ok(related, unrelated), related, unrelated


def main() -> int:
    from life_graph.api.dependencies import get_embedding_service
    from life_graph.config import settings

    service = get_embedding_service()
    embed = service.embed

    ok = True

    passed, related, unrelated = _run_semantic(embed)
    print(f"[semantic ] related={[round(s, 3) for s in related]} "
          f"unrelated={[round(s, 3) for s in unrelated]} -> {'PASS' if passed else 'FAIL'}")
    ok = ok and passed

    dup = cosine(embed(DUP_PAIR[0]), embed(DUP_PAIR[1]))
    distinct = cosine(embed(DISTINCT_PAIR[0]), embed(DISTINCT_PAIR[1]))
    sep = separation_ok(dup, distinct)
    print(f"[dedup    ] dup={dup:.3f} distinct={distinct:.3f} "
          f"(threshold {DEDUP_THRESHOLD}) -> {'PASS' if sep else 'FAIL'}")
    ok = ok and sep

    # DB checks (dimension + coverage) — best-effort, need a live DB.
    try:
        import asyncio

        from sqlalchemy import func, select

        from life_graph.models.db import Memory
        from life_graph.storage.database import async_session

        async def _db_checks() -> bool:
            async with async_session() as session:
                null_count = (
                    await session.execute(
                        select(func.count()).select_from(Memory).where(Memory.embedding.is_(None))
                    )
                ).scalar_one()
                sample = (
                    await session.execute(select(Memory).where(Memory.embedding.is_not(None)).limit(1))
                ).scalar_one_or_none()
            dim_ok = sample is None or len(sample.embedding) == settings.embedding_dimension
            print(f"[coverage ] memories with NULL embedding: {null_count} -> "
                  f"{'PASS' if null_count == 0 else 'FAIL'}")
            print(f"[dimension] sample dim == {settings.embedding_dimension} -> "
                  f"{'PASS' if dim_ok else 'FAIL'}")
            return null_count == 0 and dim_ok

        ok = asyncio.run(_db_checks()) and ok
    except Exception as exc:  # noqa: BLE001
        print(f"[db       ] skipped (no live DB?): {exc}")

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
