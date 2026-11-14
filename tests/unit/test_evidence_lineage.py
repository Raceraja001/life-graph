"""Unit tests for P0.1 evidence lineage contract, resolver, and claim evidence."""

from __future__ import annotations

from life_graph.core.evidence import (
    extract_claim_evidence,
    normalize_lineage,
    resolve_memory_lineage,
)


def test_normalize_lineage_preserves_span_trace_and_derivation():
    lineage = normalize_lineage(
        {
            "extraction_trace_id": "trace-42",
            "extraction_fact_index": 2,
            "source_excerpt": "  Lives in Chennai.  ",
            "source_location": {"document_id": "doc-1", "page": 3, "offset": 120},
            "derived_from": ["mem-1", "mem-2"],
        },
        capture_event_id="cap-99",
        source_type="document",
        supersedes="mem-0",
    )
    assert lineage["capture_event_id"] == "cap-99"
    assert lineage["extraction_trace_id"] == "trace-42"
    assert lineage["extraction_fact_index"] == 2
    assert lineage["excerpt"] == "Lives in Chennai."
    assert lineage["location"] == {"document_id": "doc-1", "page": 3, "offset": 120}
    assert lineage["derived_from"] == ["mem-1", "mem-2"]
    assert lineage["supersedes"] == "mem-0"


def test_resolve_lineage_handles_missing_deleted_and_malformed_without_fabricating():
    # Deleted source
    deleted = resolve_memory_lineage(
        {
            "id": "m-del",
            "source_type": "capture",
            "trust_tier": "self",
            "capture_event_id": "cap-gone",
            "properties": {"lineage": "malformed-not-a-dict", "extraction_fact_index": "bad"},
        },
        source_available=False,
    )
    assert deleted["memory_id"] == "m-del"
    assert deleted["source_available"] is False
    assert deleted["lineage"]["capture_event_id"] == "cap-gone"
    assert "extraction_fact_index" not in deleted["lineage"]

    # Missing source entirely: never fabricates source_available=True
    missing = resolve_memory_lineage({"id": "m-none", "source_type": "unknown", "properties": {}})
    assert missing["source_available"] is False
    assert missing["lineage"] == {"source_type": "unknown"}

    # Derived memory preserves ancestry
    derived = resolve_memory_lineage(
        {"id": "m-derived", "source_type": "consolidation", "trust_tier": "verified", "properties": {"derived_from": ["m1"]}},
        ancestors=[{"id": "m1"}, {"id": "m0"}],
    )
    assert derived["evidence_kind"] == "inferred"
    assert derived["ancestry"] == ["m1", "m0"]


def test_extract_claim_evidence_separates_supported_and_unsupported_claims():
    memories = [
        {
            "id": "m1",
            "source_type": "chat",
            "trust_tier": "self",
            "capture_event_id": "cap-1",
            "properties": {"source_excerpt": "Uses Realme X2 Pro."},
        }
    ]
    claims = extract_claim_evidence(
        "You use a Realme X2 Pro [Memory 1]. You also own a helicopter.",
        memories,
    )
    assert len(claims) == 2
    assert claims[0]["supported"] is True
    assert claims[0]["memory_ids"] == ["m1"]
    assert claims[0]["evidence"][0]["lineage"]["excerpt"] == "Uses Realme X2 Pro."
    assert claims[1]["supported"] is False
    assert claims[1]["memory_ids"] == []


# ── P5.2 Claim entailment: a citation marker is not proof ────────────────


def _cited(mid: str, text: str, **over):
    """A retrieved memory as the answer synthesizer sees it, with readable source text."""
    row = {
        "id": mid,
        "source_type": "chat",
        "trust_tier": "self",
        "capture_event_id": f"cap-{mid}",
        "content": text,
        "properties": {},
    }
    row.update(over)
    return row


def test_p5_2_citation_marker_alone_is_not_support():
    """[Memory 1] pointing at unrelated text must not make a claim supported."""
    memories = [_cited("m1", "Likes painting watercolours on weekends.")]

    claims = extract_claim_evidence("You live in London [Memory 1].", memories)
    assert len(claims) == 1
    claim = claims[0]
    assert claim["support_status"] == "unsupported"
    assert claim["supported"] is False
    assert claim["memory_ids"] == []  # an irrelevant citation earns no lineage
    assert claim["entailment_score"] == 0.0

    # The per-citation detail says which citation failed and why.
    (detail,) = claim["citation_support"]
    assert detail["citation"] == 1
    assert detail["memory_id"] == "m1"
    assert detail["support_status"] == "unsupported"
    assert detail["detail"] == "Citation does not entail claim"

    # The same marker over text that does say it comes back supported.
    ok = extract_claim_evidence(
        "You live in London [Memory 1].", [_cited("m1", "Raja lives in London, UK.")]
    )
    assert ok[0]["support_status"] == "supported"
    assert ok[0]["supported"] is True
    assert ok[0]["memory_ids"] == ["m1"]
    assert ok[0]["entailment_score"] >= 0.45


def test_p5_2_contradictory_citation_is_marked_contradicted():
    """Cited text that asserts a different value for the same fact disagrees."""
    memories = [
        _cited("m1", "Raja lives in Chennai, Tamil Nadu."),
        _cited("m2", "Raja does not drink coffee."),
    ]

    conflicting_value = extract_claim_evidence("You live in London [Memory 1].", memories)[0]
    assert conflicting_value["support_status"] == "contradicted"
    assert conflicting_value["supported"] is False
    assert conflicting_value["citation_support"][0]["detail"].startswith("Citation contradicts claim")

    opposite_polarity = extract_claim_evidence("You drink coffee [Memory 2].", memories)[0]
    assert opposite_polarity["support_status"] == "contradicted"
    assert opposite_polarity["supported"] is False

    # Contradiction is more severe than support: a good co-citation cannot
    # launder a claim that one of its own sources disagrees with.
    mixed = extract_claim_evidence(
        "You live in London [Memory 1][Memory 3].",
        [*memories, _cited("m3", "Raja lives in London for work.")],
    )[0]
    assert mixed["support_status"] == "contradicted"
    assert mixed["supported"] is False


def test_p5_2_unresolvable_citation_is_marked_unresolved_source():
    """A reference string is not a source: the source has to actually resolve."""
    memories = [_cited("m1", "Raja lives in Chennai.")]

    # Out of range: the answer cited a memory that was never retrieved.
    dangling = extract_claim_evidence("You live in Chennai [Memory 7].", memories)[0]
    assert dangling["support_status"] == "unresolved_source"
    assert dangling["supported"] is False
    assert dangling["citation_support"][0]["detail"] == "Cited source could not be resolved"
    assert dangling["confidence_breakdown"] == []  # nothing to decompose

    # Resolves to a tombstone: the row is there, the source is gone.
    deleted = extract_claim_evidence(
        "You live in Chennai [Memory 1].",
        [_cited("m1", "Raja lives in Chennai.", status="deleted")],
    )[0]
    assert deleted["support_status"] == "unresolved_source"
    assert deleted["supported"] is False

    # Resolves, but carries no text at all: honestly reported as unverified
    # context rather than as either support or a false accusation.
    textless = extract_claim_evidence(
        "You live in Chennai [Memory 1].",
        [{"id": "m1", "source_type": "chat", "trust_tier": "self", "properties": {}}],
    )[0]
    assert textless["support_status"] == "context"
    assert textless["entailment_score"] is None
    assert "entailment not verified" in textless["citation_support"][0]["detail"]


def test_p5_2_entailment_scorer_is_injectable_and_failures_do_not_grant_support():
    """A semantic scorer can replace the lexical proxy; a broken one must not help."""
    from life_graph.core.evidence import verify_claim_support

    memory = _cited("m1", "Enjoys watercolour painting.")

    # A semantic model sees the paraphrase the lexical proxy misses.
    semantic = verify_claim_support("You paint with watercolours", memory, scorer=lambda c, s: 0.91)
    assert semantic["support_status"] == "supported"
    assert semantic["entailment_score"] == 0.91

    # A scorer that raises falls back to the lexical proxy; it never defaults
    # to "supported" just because the check could not be run.
    def _broken(claim, source):
        raise RuntimeError("model unavailable")

    unrelated = verify_claim_support("You live in London", memory, scorer=_broken)
    assert unrelated["support_status"] == "unsupported"
    assert unrelated["entailment_score"] == 0.0
