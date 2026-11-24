"""L14 (2026-11-24 recheck): consolidation's similarity loops run on numpy.

``_cluster`` and ``_dedup_cluster`` used to call the pure-Python
``cosine_similarity`` once per pair. The numpy version must give the same
clusters, the same kept memories and the same (kept, duplicate, similarity)
pairs in the same order. The references below are the loops as they were.
"""

from __future__ import annotations

import random
import uuid

import pytest

from life_graph.core.utils import cosine_similarity
from life_graph.jobs.consolidation import ConsolidationPipeline, _CosineRows
from life_graph.models.db import Memory


def _pipeline(cluster=0.75, dedup=0.95) -> ConsolidationPipeline:
    pipeline = ConsolidationPipeline.__new__(ConsolidationPipeline)
    pipeline._CLUSTER_THRESHOLD = cluster
    pipeline._DEDUP_THRESHOLD = dedup
    return pipeline


def _mem(embedding, content="x") -> Memory:
    return Memory(id=uuid.uuid4(), content=content, tenant_id="t", embedding=embedding)


# ── reference implementations (the pre-L14 loops) ───────────────────


def _ref_cluster(memories, threshold):
    clusters = []
    for memory in memories:
        if memory.embedding is None:
            clusters.append([memory])
            continue
        placed = False
        for cluster in clusters:
            for member in cluster:
                if member.embedding is None:
                    continue
                if cosine_similarity(memory.embedding, member.embedding) > threshold:
                    cluster.append(memory)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            clusters.append([memory])
    return clusters


def _ref_dedup(cluster, threshold, pairs):
    if len(cluster) <= 1:
        return cluster
    sorted_mems = sorted(cluster, key=lambda m: len(m.content), reverse=True)
    kept, removed_ids = [], set()
    for mem in sorted_mems:
        if mem.id in removed_ids:
            continue
        for other in sorted_mems:
            if other.id == mem.id or other.id in removed_ids:
                continue
            if mem.embedding and other.embedding:
                sim = cosine_similarity(mem.embedding, other.embedding)
                if sim > threshold:
                    removed_ids.add(other.id)
                    pairs.append((mem, other, sim))
        kept.append(mem)
    return kept


# ── data ────────────────────────────────────────────────────────────


def _random_memories(seed: int, n: int = 60, dim: int = 12) -> list[Memory]:
    """Noisy copies of a few centres, so similarities straddle 0.75 and 0.95,
    plus the edge cases: None, empty, zero, wrong length, exact duplicates."""
    rng = random.Random(seed)
    centres = [[rng.gauss(0, 1) for _ in range(dim)] for _ in range(4)]
    out = []
    for _ in range(n):
        centre = rng.choice(centres)
        noise = rng.choice([0.02, 0.1, 0.3, 0.6, 1.5])
        vec = [c + rng.gauss(0, noise) for c in centre]
        out.append(_mem(vec, content="m" * rng.randint(1, 40)))
    dup = list(out[0].embedding)
    out += [
        _mem(None),
        _mem([]),
        _mem([0.0] * dim),
        _mem([0.0] * dim),
        _mem([1.0] * (dim + 1)),
        _mem(dup, content="dup"),
        _mem(dup, content="dup2"),
    ]
    rng.shuffle(out)
    return out


def _ids(clusters):
    return [[m.id for m in c] for c in clusters]


# ── tests ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("seed", range(8))
def test_cluster_matches_the_pairwise_reference(seed):
    memories = _random_memories(seed)
    got = _pipeline()._cluster(list(memories))
    want = _ref_cluster(list(memories), 0.75)
    assert _ids(got) == _ids(want)
    assert any(len(c) > 1 for c in got)  # the data really clusters


@pytest.mark.parametrize("seed", range(8))
def test_dedup_matches_the_pairwise_reference(seed):
    memories = _random_memories(seed)
    got_pairs: list = []
    want_pairs: list = []
    got = _pipeline()._dedup_cluster(list(memories), pairs=got_pairs)
    want = _ref_dedup(list(memories), 0.95, want_pairs)
    assert [m.id for m in got] == [m.id for m in want]
    assert [(a.id, b.id) for a, b, _ in got_pairs] == [(a.id, b.id) for a, b, _ in want_pairs]
    for (_, _, g), (_, _, w) in zip(got_pairs, want_pairs, strict=True):
        assert g == pytest.approx(w, abs=1e-12)
    assert want_pairs  # the data really has duplicates


def test_a_similarity_exactly_on_the_threshold_does_not_count():
    # [3, 4] . [4, 3] = 24 and both norms are 5, so cosine is exactly 0.96 in
    # both implementations; the comparison is a strict ">".
    a, b = _mem([3.0, 4.0], content="aa"), _mem([4.0, 3.0], content="b")
    assert cosine_similarity(a.embedding, b.embedding) == 0.96

    on = _pipeline(cluster=0.96, dedup=0.96)
    assert _ids(on._cluster([a, b])) == _ids(_ref_cluster([a, b], 0.96)) == [[a.id], [b.id]]
    pairs: list = []
    assert on._dedup_cluster([a, b], pairs=pairs) == [a, b]
    assert pairs == []

    below = _pipeline(cluster=0.9599, dedup=0.9599)
    assert _ids(below._cluster([a, b])) == [[a.id, b.id]]
    pairs = []
    assert below._dedup_cluster([a, b], pairs=pairs) == [a]
    assert pairs == [(a, b, 0.96)]


def test_cosine_rows_edge_cases_match_cosine_similarity():
    vectors = [[1.0, 2.0], None, [], [0.0, 0.0], [1.0, 2.0, 3.0], [-2.0, 1.0], [2.0, 4.0]]
    rows = _CosineRows(vectors)
    for i, a in enumerate(vectors):
        row = rows.row(i)
        for j, b in enumerate(vectors):
            want = 0.0 if a is None or b is None else cosine_similarity(a, b)
            assert row[j] == pytest.approx(want, abs=1e-12), (i, j)


def test_a_negative_threshold_still_skips_members_without_embeddings():
    # Zero similarity beats a negative threshold; a member with no embedding
    # must still never be matched (the reference skips it outright).
    memories = [_mem(None), _mem([1.0, 0.0]), _mem([0.0, 0.0]), _mem([0.0, 1.0])]
    got = _pipeline(cluster=-0.5)._cluster(list(memories))
    assert _ids(got) == _ids(_ref_cluster(list(memories), -0.5))
