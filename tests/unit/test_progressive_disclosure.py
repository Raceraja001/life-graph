"""Recall is a token budget, and nothing was counting it.

MemoryResponse has twenty fields. Exactly one of them — ``content`` — is what
a model reads; the rest is bookkeeping: three UUIDs, three ISO timestamps,
five floats and an unbounded JSONB blob. A four-bucket RecallContext of five
such objects is several hundred tokens where an index of the same five is a
few dozen.

This file pins the three pieces of the fix:

* the compact projection (``scoring/ranking.to_index``) — what survives, and
  that it is genuinely smaller;
* the accounting (``api/token_meta``) — that ``tokens_saved`` is the real
  difference and is zero when nothing was saved;
* the expand contract (``POST /api/v1/memories/batch``) — capped, and the
  place surfacing is now recorded.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from life_graph.api.memories import _BATCH_EXPAND_MAX, MemoryBatchRequest
from life_graph.api.token_meta import payload_tokens, token_meta
from life_graph.models.schemas import (
    MemoryIndexItem,
    MemoryResponse,
    RecallContext,
    SearchQuery,
)
from life_graph.scoring.ranking import INDEX_CONTENT_CHARS, to_index


def _candidate(**kw):
    return {
        "id": kw.get("id", str(uuid.uuid4())),
        "content": kw.get("content", "The developer prefers self-hosted infrastructure."),
        "tags": kw.get("tags", ["identity", "preference"]),
        "status": kw.get("status", "active"),
        "final_score": kw.get("final_score", 0.7123456),
        # Everything below is what the index deliberately drops.
        "properties": {"project": "life-graph", "module": "recall", "files": ["a.py"]},
        "importance": 0.8,
        "confidence": 0.9,
        "trust_score": 0.5,
        "impact_score": 0.5,
        "access_count": 3,
        "source_type": "explicit",
        "created_at": datetime.now(UTC),
        "last_accessed": datetime.now(UTC),
        "reinforced_count": 0,
    }


def _response(cand):
    from life_graph.services.recall import _dict_to_memory_response

    return _dict_to_memory_response(cand)


# ── The projection ────────────────────────────────────────────────────


def test_index_keeps_exactly_the_five_fields_that_earn_their_place():
    item = to_index([_candidate()])[0]
    assert set(item) == {"id", "content", "tags", "score", "status"}


def test_status_survives_the_projection():
    """The approval gate is asserted through search output; dropping status
    would leave `tests/integration/test_memory_approval.py` no handle on
    whether an item is pending."""
    assert to_index([_candidate(status="pending")])[0]["status"] == "pending"


def test_long_content_is_truncated_and_marked():
    item = to_index([_candidate(content="x" * 500)])[0]
    assert len(item["content"]) == INDEX_CONTENT_CHARS + 1  # + the ellipsis
    assert item["content"].endswith("…")


def test_short_content_is_left_alone():
    assert to_index([_candidate(content="short")])[0]["content"] == "short"


def test_order_is_preserved():
    cands = [_candidate(content=str(i)) for i in range(5)]
    assert [i["content"] for i in to_index(cands)] == ["0", "1", "2", "3", "4"]


def test_a_candidate_missing_everything_does_not_raise():
    """Retrieval is schema-less; a sparse dict must project, not explode."""
    item = to_index([{}])[0]
    assert item["content"] == "" and item["tags"] == [] and item["score"] == 0.0


def test_the_index_is_substantially_cheaper_than_the_full_payload():
    """Measured, not assumed: ~3x on a five-item recall of ordinary memories
    (~65-90 index tokens per item against ~200-250 full), rising with content
    length because the full payload carries all of it and the index carries
    120 characters. The floor here is 2.5x — below that the second round trip
    an expand costs stops paying for itself."""
    cands = [_candidate() for _ in range(5)]
    full = RecallContext(identity=[_response(c) for c in cands])
    index = RecallContext(
        result_mode="index",
        index=[MemoryIndexItem.model_validate(i) for i in to_index(cands)],
    )

    full_tokens = payload_tokens(full)
    index_tokens = payload_tokens(index)
    assert index_tokens * 2.5 < full_tokens, (
        f"index cost {index_tokens} tokens against {full_tokens} full — the "
        "projection is not buying enough to be worth a second round trip"
    )


def test_the_saving_grows_with_content_length():
    """The index is a fixed-width projection; the full payload is not. Long
    memories are exactly where progressive disclosure earns the most."""
    short = [_candidate(content="short note") for _ in range(5)]
    long = [_candidate(content="x" * 600) for _ in range(5)]

    def ratio(cands):
        full = payload_tokens(RecallContext(identity=[_response(c) for c in cands]))
        idx = payload_tokens(
            RecallContext(
                result_mode="index",
                index=[MemoryIndexItem.model_validate(i) for i in to_index(cands)],
            )
        )
        return full / idx

    assert ratio(long) > ratio(short)


def test_the_index_still_carries_the_content_a_model_needs():
    """Cheap is easy; cheap and useless is the failure mode to avoid."""
    cand = _candidate(content="Deploys go to the self-hosted VPS, never to Vercel.")
    assert "self-hosted VPS" in to_index([cand])[0]["content"]


# ── The accounting ────────────────────────────────────────────────────


def test_tokens_saved_is_zero_when_the_full_payload_was_sent():
    meta = token_meta(RecallContext(identity=[_response(_candidate())]))
    assert meta["tokens_saved"] == 0
    assert meta["tokens_injected"] > 0


def test_tokens_saved_is_the_actual_difference():
    cands = [_candidate() for _ in range(5)]
    full = RecallContext(identity=[_response(c) for c in cands])
    index = RecallContext(
        result_mode="index",
        index=[MemoryIndexItem.model_validate(i) for i in to_index(cands)],
    )

    meta = token_meta(index, full)
    assert meta["tokens_injected"] == payload_tokens(index)
    assert meta["tokens_saved"] == payload_tokens(full) - payload_tokens(index)
    assert meta["tokens_saved"] > 0


def test_tokens_saved_never_goes_negative():
    """A 'full' payload smaller than what was sent is a nonsense to report."""
    big = RecallContext(identity=[_response(_candidate()) for _ in range(3)])
    small = RecallContext()
    assert token_meta(big, small)["tokens_saved"] == 0


def test_extra_meta_keys_ride_along():
    meta = token_meta(RecallContext(), result_mode="index")
    assert meta["result_mode"] == "index"


def test_an_unserializable_payload_is_estimated_not_fatal():
    """Accounting is bookkeeping; it must never cost the caller its response."""
    assert token_meta(object())["tokens_injected"] > 0


def test_empty_payload_costs_something_not_nothing():
    assert payload_tokens([]) >= 1


# ── The flags ─────────────────────────────────────────────────────────


def test_index_only_defaults_off_everywhere():
    """Existing callers parse `memories`; they must keep getting it."""
    from life_graph.api.search import AskRequest, MidSessionRecallRequest, RecallRequest

    assert SearchQuery(query="q").index_only is False
    assert RecallRequest(context={}).index_only is False
    assert MidSessionRecallRequest(context={}, event="e").index_only is False
    assert AskRequest(question="q").index_only is False


def test_the_flag_explains_itself():
    """The house pattern (see SearchQuery.include_pending): the description
    carries the reason, because it is what a caller reads."""
    description = SearchQuery.model_fields["index_only"].description or ""
    assert "batch" in description, "the description must point at the expand step"
    assert len(description) > 80


def test_the_mode_actually_used_is_echoed_back():
    """Same convention as search_mode: report what happened, not what was asked."""
    assert RecallContext().result_mode == "full"
    assert "result_mode" in RecallContext.model_fields


# ── The expand contract ───────────────────────────────────────────────


def test_batch_expand_is_capped():
    with pytest.raises(ValidationError):
        MemoryBatchRequest(ids=[uuid.uuid4() for _ in range(_BATCH_EXPAND_MAX + 1)])


def test_batch_expand_rejects_an_empty_request():
    with pytest.raises(ValidationError):
        MemoryBatchRequest(ids=[])


def test_batch_expand_records_access_by_default():
    """Expanding IS the disclosure; that is the whole point of moving it here."""
    assert MemoryBatchRequest(ids=[uuid.uuid4()]).record_access is True


def test_the_batch_store_read_is_tenant_scoped():
    import inspect

    from life_graph.storage.postgres import PostgresMemoryStore

    src = inspect.getsource(PostgresMemoryStore.retrieve_many)
    assert "get_current_tenant_id" in src, (
        "an id is guessable; a batch read by id must not be a way across tenants"
    )


def test_memory_response_is_still_the_expanded_shape():
    """The index is a summary of something; expanding must return the thing."""
    full = _response(_candidate())
    assert isinstance(full, MemoryResponse)
    assert len(MemoryResponse.model_fields) >= 18
