"""The memory page's routes: registered before GET /memories/{memory_id}, and pure helpers."""

from __future__ import annotations

from types import SimpleNamespace


def test_overview_route_comes_before_the_memory_id_route():
    """GET /memories/{memory_id} (a UUID) would answer /memories/overview with 422."""
    import pathlib

    import life_graph.main

    source = pathlib.Path(life_graph.main.__file__).read_text(encoding="utf-8")
    page = source.index("v1_router.include_router(memory_page_api.router)")
    assert page < source.index("v1_router.include_router(memories.router)")


def test_like_escapes_wildcards():
    from life_graph.services.memory_page import _like

    assert _like("100%_a\\b") == "100\\%\\_a\\\\b"


def test_row_marks_only_owner_or_jarvis_corrections_undoable():
    from life_graph.services.memory_page import row

    def mem(**props):
        return SimpleNamespace(
            id="x",
            content="The owner works at Zoho",
            status="active",
            source_type="explicit",
            trust_tier="self",
            tags=[],
            properties=props,
            created_at=None,
            updated_at=None,
            confidence=0.9,
            importance=0.7,
        )

    corrected = row(mem(saved_by="owner", replaces_id="y", slot="work.employer"))
    assert corrected["undoable"] is True
    assert corrected["slot_label"] == "work · employer" and corrected["topic"] == "work"
    assert row(mem(replaces_id="y"))["undoable"] is False
    assert row(mem(saved_by="owner"))["undoable"] is False
    assert row(mem())["evidence"] == "said"
