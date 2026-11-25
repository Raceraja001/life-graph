"""Production-path retrieval arm for the memory lab (M3, 2026-11-25).

The memory lab (life_graph/evals/memory_benchmark.py) ranks with its own BM25
and n-gram code, so its scores say nothing about the search Life Graph ships.
This arm runs the shipped code instead. It writes the lab's synthetic messages
as memories of a throwaway tenant, asks every question through:

* ``storage_hybrid_search``: ``PostgresMemoryStore.hybrid_search`` (pgvector
  cosine + Postgres full-text, rank fused), the store call itself;
* ``retrieve_judge_disabled``: ``services.memory.retrieval.retrieve``, the whole
  production path (strength order, provenance tie-break, early-exit
  assessment, bitemporal filter, day summaries, entity and link candidates)
  with the relevance judge answering "unavailable", so retrieve takes its own
  fallback and returns the search order;

and scores the answers with the lab's own scorer (``score_question``), so the
numbers sit next to the lab's methods. Then it deletes every row of the tenant.

What is not production here, on purpose:

* The embedder is ``fake_embedding``: a deterministic hashing of words and
  character trigrams. No network, no GPU, the same vector every run. It is a
  weak embedder, so the vector leg is a lower bound on a real model's.
* The judge is disabled. Production keeps only the memories the local model
  says help; that step needs a model and is not measured here.
* The tenant has no entity index or memory links, so those expansions find
  nothing. The memories are the raw messages, not extracted facts.

Numbers move a little from run to run (measured 2026-11-25 over four runs:
held-out R@5 0.769-0.787, tuning R@5 steady at 0.744). The vector leg orders
by pgvector's HNSW index (iterative scan, relaxed order), which is
approximate: which near neighbours it returns can differ between builds.
Compare runs by their range, not by the last digit.

Needs Postgres (run it through scripts/eval_production_retrieval.py, which
points at the integration test database). It is not part of the unit gate.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import re
import time
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest import mock

from sqlalchemy import func, select, text

from life_graph import runtime
from life_graph.config import settings
from life_graph.core.tenant import set_tenant_context
from life_graph.evals import memory_benchmark as lab
from life_graph.models.db import Memory
from life_graph.services.memory import retrieval
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

ARMS = ("storage_hybrid_search", "retrieve_judge_disabled")
#: How many results each arm is asked for; metrics are reported at 1, 3 and 5.
RESULT_LIMIT = 10
PRECISION_KS = (1, 3, 5)
#: Prefix of every throwaway tenant, so a leftover is easy to find and remove.
TENANT_PREFIX = "m3eval_"

_WORD = re.compile(r"[\w஀-௿]+")


def fake_embedding(text_: str, dim: int | None = None) -> list[float]:
    """A deterministic unit vector for *text_*: hashed words and character trigrams.

    blake2b, not ``hash()``, so the vector is the same in every process.
    Words count twice as much as trigrams; each feature lands on one signed
    dimension. Texts that share words or spellings point the same way, which
    is all the vector leg needs to be exercised without a model.
    """
    dim = dim or settings.embedding_dimension
    vec = [0.0] * dim
    lowered = text_.lower()
    feats: list[tuple[str, float]] = [(f"w:{w}", 2.0) for w in _WORD.findall(lowered)]
    squashed = " ".join(lowered.split())
    feats += [(f"c:{squashed[i : i + 3]}", 1.0) for i in range(max(0, len(squashed) - 2))]
    for feat, weight in feats:
        h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        vec[idx] += weight if h[4] & 1 else -weight
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def new_tenant() -> str:
    return f"{TENANT_PREFIX}{uuid.uuid4().hex[:12]}"


def _noon(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, tzinfo=UTC)


async def seed_corpus(tenant_id: str, data: dict[str, Any]) -> int:
    """Write the dataset's messages as active memories of *tenant_id*.

    Stored the way the lab models them (memory_benchmark._as_evidence_memory):
    the owner's own words, verbatim, dated by the message.
    """
    async with async_session() as s:
        for m in data["messages"]:
            when = _noon(date.fromisoformat(m["date"]))
            s.add(
                Memory(
                    tenant_id=tenant_id,
                    content=m["text"],
                    content_hash=hashlib.sha256(m["text"].strip().lower().encode()).hexdigest(),
                    properties={
                        "kind": "fact",
                        "source_excerpt": m["text"],
                        "benchmark_id": m["id"],
                    },
                    importance=0.5,
                    confidence=1.0,
                    source_type="chat",
                    trust_tier="self",
                    status="active",
                    created_at=when,
                    updated_at=when,
                    valid_from=when,
                    embedding=fake_embedding(m["text"]),
                )
            )
        await s.commit()
    return len(data["messages"])


async def _tenant_tables() -> list[str]:
    async with async_session() as s:
        rows = await s.execute(
            text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = 'tenant_id'"
            )
        )
        return sorted({r[0] for r in rows})


async def cleanup_tenant(tenant_id: str) -> int:
    """Delete every row of *tenant_id* from every table that has a tenant_id.

    Only throwaway tenants (``TENANT_PREFIX``) are accepted. Memories go last
    so rows that point at them are gone first; a table that fails is retried
    on the next pass. Returns how many memories are left (0 when clean).
    """
    if not tenant_id.startswith(TENANT_PREFIX):
        raise ValueError(f"refusing to clean a non-throwaway tenant: {tenant_id!r}")
    tables = [t for t in await _tenant_tables() if t != "memories"] + ["memories"]
    pending = list(tables)
    for _ in range(3):
        failed: list[str] = []
        for table in pending:
            try:
                async with async_session() as s:
                    # Identifier from information_schema, never from input.
                    await s.execute(
                        text(f'DELETE FROM "{table}" WHERE tenant_id = :t'), {"t": tenant_id}
                    )
                    await s.commit()
            except Exception:  # noqa: BLE001 — retried; a foreign key may need another pass
                failed.append(table)
        if not failed:
            break
        pending = failed
    async with async_session() as s:
        left = await s.scalar(
            select(func.count()).select_from(Memory).where(Memory.tenant_id == tenant_id)
        )
    return int(left or 0)


async def _fake_generate_embedding(text_: str) -> list[float]:
    return fake_embedding(text_)


async def _judge_unavailable(question: str, contents: list[str]) -> None:
    """The judge as retrieve sees it when the local model gives no answer."""
    return None


@contextlib.contextmanager
def production_fakes() -> Iterator[None]:
    """The fake embedder and the disabled judge, for the length of the block."""
    manager = SimpleNamespace(generate_embedding=_fake_generate_embedding)
    with (
        mock.patch.object(runtime, "get_memory_manager", lambda: manager),
        mock.patch.object(retrieval, "judge", _judge_unavailable),
    ):
        yield


async def _ask(arm: str, question: str) -> tuple[list[Any], bool]:
    """(memories best first, retrieve's abstention indicator) for one question."""
    if arm == "storage_hybrid_search":
        hits = await runtime.get_store().hybrid_search(
            embedding=fake_embedding(question), query_text=question, limit=RESULT_LIMIT
        )
        return [m for m, _ in hits], False
    result = await retrieval.retrieve(question, limit=RESULT_LIMIT)
    if result is None:
        return [], False
    return list(result), bool(getattr(result, "abstain", False))


def _is_relevant(q: dict[str, Any], mem: lab.EnrichedMemory) -> bool:
    groups = q.get("must") or []
    traps = [t.lower() for t in (q.get("must_not") or [])]
    return any(lab._memory_matches_group(mem, g) for g in groups) and not any(
        t in mem.raw_text.lower() for t in traps
    )


def _abstention(rows: list[tuple[bool, bool]]) -> dict[str, Any]:
    """Precision/recall of retrieve's abstention indicator on (gold, flagged) rows."""
    gold = sum(1 for g, _ in rows if g)
    flagged = sum(1 for _, f in rows if f)
    tp = sum(1 for g, f in rows if g and f)
    return {
        "flagged": flagged,
        "abstain_questions": gold,
        "precision": round(tp / flagged, 4) if flagged else 0.0,
        "recall": round(tp / gold, 4) if gold else 0.0,
    }


async def evaluate_arm(
    arm: str,
    data: dict[str, Any],
    corpus: list[lab.EnrichedMemory],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    """One arm over *questions*, scored with the lab's scorer."""
    by_id = {m.id: m for m in corpus}
    scored: list[dict[str, Any]] = []
    latencies: list[float] = []
    precision_sums = dict.fromkeys(PRECISION_KS, 0.0)
    answerable = 0
    abstain_rows: list[tuple[bool, bool]] = []
    unmapped = 0
    for q in questions:
        t0 = time.perf_counter()
        rows, flagged = await _ask(arm, q["q"])
        latencies.append((time.perf_counter() - t0) * 1000.0)
        enriched = []
        for row in rows:
            bid = (row.properties or {}).get("benchmark_id")
            if bid in by_id:
                enriched.append(by_id[bid])
            else:
                unmapped += 1
        # Ranking quality is scored as retrieval, never as a refusal: the
        # abstention indicator is reported on its own below.
        scored.append(lab.score_question(q, enriched, False))
        abstain_rows.append((bool(q.get("abstain")), flagged))
        if not q.get("abstain"):
            answerable += 1
            for k in PRECISION_KS:
                top = enriched[:k]
                precision_sums[k] += sum(1 for m in top if _is_relevant(q, m)) / k
    summary = lab.summarize_scores(scored, latencies)
    overall = summary["overall"]
    for k in PRECISION_KS:
        overall[f"precision_at_{k}"] = round(precision_sums[k] / max(1, answerable), 4)
    # The lab's own abstention fields mean "the method refused"; this arm never
    # refuses, so they are replaced by the production indicator's numbers.
    overall.pop("abstention_precision", None)
    overall.pop("abstention_recall", None)
    return {
        "overall": overall,
        "by_kind": summary["by_kind"],
        "latency_ms": lab.latency_stats(latencies),
        "abstention_indicator": _abstention(abstain_rows),
        "unmapped_results": unmapped,
        "sample_failures": summary["sample_failures"],
    }


async def evaluate_split_production(
    split_name: str,
    dataset_path: Path,
    *,
    max_questions: int | None = None,
    arms: tuple[str, ...] = ARMS,
) -> dict[str, Any]:
    """Seed a throwaway tenant with one split, run the arms, always clean up."""
    raw = dataset_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    corpus = lab.build_corpus(data)
    questions = data["questions"][:max_questions] if max_questions else data["questions"]
    tenant = new_tenant()
    set_tenant_context(tenant)
    reports: dict[str, Any] = {}
    try:
        seeded = await seed_corpus(tenant, data)
        with production_fakes():
            for arm in arms:
                reports[arm] = await evaluate_arm(arm, data, corpus, questions)
    finally:
        left = await cleanup_tenant(tenant)
    try:
        dataset_file = str(dataset_path.relative_to(lab.ROOT))
    except ValueError:
        dataset_file = str(dataset_path)
    return {
        "split": split_name,
        "dataset_file": dataset_file,
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "memories_seeded": seeded,
        "question_count": len(questions),
        "memories_left_after_cleanup": left,
        "arms": reports,
    }


async def run_production_arm(*, max_questions: int | None = None) -> dict[str, Any]:
    """Both lab splits through the production retrieval path."""
    splits = {
        "tuning_dev": await evaluate_split_production(
            "tuning_dev", lab.TUNING_DATASET, max_questions=max_questions
        ),
        "held_out": await evaluate_split_production(
            "held_out", lab.HELDOUT_DATASET, max_questions=max_questions
        ),
    }
    return {
        "benchmark": "life_graph_memory_production_arm_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "embedder": (
            f"fake_embedding: hashed words + character trigrams, dim "
            f"{settings.embedding_dimension}, deterministic, no network"
        ),
        "judge": "disabled: retrieve's judge-unavailable fallback (search order)",
        "entity_index": "empty (fresh tenant); memory links: none",
        "result_limit": RESULT_LIMIT,
        "splits": splits,
    }
