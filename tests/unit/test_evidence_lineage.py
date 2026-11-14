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
