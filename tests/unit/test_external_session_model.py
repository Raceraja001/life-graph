"""Unit tests for the ExternalSession model shape."""

from __future__ import annotations

from life_graph.models.db import ExternalSession


def test_columns_present():
    cols = set(ExternalSession.__table__.columns.keys())
    assert {
        "id",
        "tenant_id",
        "tool",
        "external_id",
        "source_path",
        "raw_key",
        "line_count",
        "last_turn_index",
        "last_distilled_at",
        "created_at",
        "updated_at",
    } <= cols


def test_unique_constraint_on_tenant_tool_external_id():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in ExternalSession.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("tenant_id", "tool", "external_id") in uniques
