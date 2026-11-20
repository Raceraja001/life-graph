"""The skills review surface: ``api/skills.py`` and the persona block.

No database — ``tests/unit/fakes.py`` stands in for the session, and
``sql(stmt)`` renders the statement the endpoint actually built, so a filter
that is silently dropped (or a ``tenant_id`` that is silently not applied)
fails here rather than leaking in production.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from life_graph.api import skills as skills_api
from life_graph.core.tenant import tenant_scope
from life_graph.models.db import Memory
from life_graph.services import persona_context
from life_graph.services.skill_distiller import FACT_TYPE, SOURCE_TYPE
from tests.conftest import fake_request
from tests.unit.fakes import FakeResult, FakeSession, sql

TENANT = "personal"
OTHER_TENANT = "someone-else"

SKILL_MD = (
    "# pytest cannot import pgvector\n"
    "## Context & Symptoms\n"
    "pytest aborts with ModuleNotFoundError: No module named 'pgvector'\n"
    "## Reusable Workflow / Commands\n"
    "pip install -e '.[dev]'\n"
    "## Pitfalls / Edge Cases\n"
    "A shell with the wrong venv active reinstalls into the system python.\n"
)


def skill(
    *,
    tenant_id: str = TENANT,
    content: str = SKILL_MD,
    status: str = "active",
    tags: list[str] | None = None,
    props: dict | None = None,
    importance: float = 0.7,
) -> Memory:
    """A procedural-skill row, as the distiller writes one."""
    return Memory(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        content=content,
        tags=["skill", "dev-agent", *(tags or [])],
        properties={
            "fact_type": FACT_TYPE,
            "origin_agent": "claude_code",
            "session_id": "sess-1",
            **(props or {}),
        },
        source_type=SOURCE_TYPE,
        status=status,
        importance=importance,
        confidence=0.6,
        created_at=datetime(2026, 11, 1, tzinfo=UTC),
        updated_at=datetime(2026, 11, 2, tzinfo=UTC),
    )


def use(monkeypatch, session: FakeSession) -> FakeSession:
    """Point the endpoints' ``async_session()`` at *session*."""
    monkeypatch.setattr(skills_api, "async_session", lambda: session)
    return session


# ── GET /skills/ ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_is_tenant_scoped_and_only_returns_skills(monkeypatch):
    row = skill()
    session = use(monkeypatch, FakeSession(FakeResult([1]), [row]))

    with tenant_scope(TENANT):
        response = await skills_api.list_skills()

    data = response["data"]
    assert data["total"] == 1
    assert [i["id"] for i in data["items"]] == [str(row.id)]
    assert data["items"][0]["title"] == "pytest cannot import pgvector"
    assert data["items"][0]["origin_agent"] == "claude_code"

    # Both statements (the count and the page) carry the tenant and the
    # three ways a row counts as a skill.
    for statement in session.statements:
        text = sql(statement)
        assert f"'{TENANT}'" in text
        assert f"'{SOURCE_TYPE}'" in text
        assert f"'{FACT_TYPE}'" in text
        assert "'skill'" in text


@pytest.mark.asyncio
async def test_list_filters_by_status_tag_project_and_search(monkeypatch):
    session = use(monkeypatch, FakeSession(FakeResult([0]), []))

    with tenant_scope(TENANT):
        response = await skills_api.list_skills(
            status_filter="needs_review",
            tag="pytest",
            project="life-graph",
            search="pgvector",
        )

    assert response["data"]["items"] == []
    text = sql(session.statements[1])
    assert "'needs_review'" in text
    assert "'pytest'" in text
    assert "'life-graph'" in text
    assert "ilike" in text.lower() and "%pgvector%" in text


@pytest.mark.asyncio
async def test_list_without_a_status_filter_spans_every_status(monkeypatch):
    session = use(monkeypatch, FakeSession(FakeResult([0]), []))

    with tenant_scope(TENANT):
        await skills_api.list_skills()

    text = sql(session.statements[1])
    assert "memories.status =" not in text
    # The 768-dim vector is never sent to the dashboard, so it is not read.
    assert "memories.embedding," not in text


@pytest.mark.asyncio
async def test_list_paginates(monkeypatch):
    rows = [skill(), skill()]
    session = use(monkeypatch, FakeSession(FakeResult([7]), rows))

    with tenant_scope(TENANT):
        response = await skills_api.list_skills(limit=2, offset=4)

    # total is the whole filtered set, not the page.
    assert response["data"]["total"] == 7
    assert response["data"]["limit"] == 2
    assert response["data"]["offset"] == 4
    assert len(response["data"]["items"]) == 2
    text = sql(session.statements[1])
    assert "LIMIT 2" in text and "OFFSET 4" in text


# ── GET /skills/{id} ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_the_full_recipe(monkeypatch):
    row = skill(tags=["pytest"], props={"project": "life-graph", "patch_count": 2})
    use(monkeypatch, FakeSession(objects={(Memory, row.id): row}))

    with tenant_scope(TENANT):
        response = await skills_api.get_skill(row.id)

    item = response["data"]
    assert item["content"] == SKILL_MD
    assert item["body"].startswith("## Context & Symptoms")
    assert item["project"] == "life-graph"
    assert item["patch_count"] == 2
    assert item["reviewable"] is False


@pytest.mark.asyncio
async def test_get_missing_skill_is_404(monkeypatch):
    use(monkeypatch, FakeSession())

    with tenant_scope(TENANT), pytest.raises(HTTPException) as caught:
        await skills_api.get_skill(uuid.uuid4())

    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_another_tenants_skill_is_404(monkeypatch):
    row = skill(tenant_id=OTHER_TENANT)
    use(monkeypatch, FakeSession(objects={(Memory, row.id): row}))

    with tenant_scope(TENANT), pytest.raises(HTTPException) as caught:
        await skills_api.get_skill(row.id)

    assert caught.value.status_code == 404
    # Reading it is refused, so approving and archiving it are too.
    with tenant_scope(TENANT), pytest.raises(HTTPException) as caught:
        await skills_api.approve_skill(row.id, fake_request())
    assert caught.value.status_code == 404
    with tenant_scope(TENANT), pytest.raises(HTTPException) as caught:
        await skills_api.archive_skill(row.id)
    assert caught.value.status_code == 404
    assert row.status == "active"


# ── POST /skills/{id}/approve ─────────────────────────────────


@pytest.mark.asyncio
async def test_approve_activates_a_pending_skill(monkeypatch):
    row = skill(status="pending")
    session = use(monkeypatch, FakeSession(objects={(Memory, row.id): row}))

    from life_graph.api.approval_identity import resolver

    request = fake_request()
    with tenant_scope(TENANT):
        response = await skills_api.approve_skill(row.id, request)

    assert row.status == "active"
    # Who approved, as the server saw the caller (test_owner_gates.py covers keys).
    assert row.properties["approved_by"] == resolver(request)
    # The distiller's own properties survive the approval.
    assert row.properties["fact_type"] == FACT_TYPE
    assert session.commits == 1
    assert response["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_approve_a_needs_review_skill(monkeypatch):
    row = skill(status="needs_review")
    use(monkeypatch, FakeSession(objects={(Memory, row.id): row}))

    with tenant_scope(TENANT):
        response = await skills_api.approve_skill(row.id, fake_request())

    assert response["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_approving_an_active_skill_writes_nothing(monkeypatch):
    row = skill(status="active")
    session = use(monkeypatch, FakeSession(objects={(Memory, row.id): row}))

    with tenant_scope(TENANT):
        response = await skills_api.approve_skill(row.id, fake_request())

    assert session.commits == 0
    assert response["data"]["status"] == "active"


# ── DELETE /skills/{id} ───────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_archives_rather_than_deleting(monkeypatch):
    row = skill(status="active")
    session = use(monkeypatch, FakeSession(objects={(Memory, row.id): row}))

    with tenant_scope(TENANT):
        response = await skills_api.archive_skill(row.id)

    assert row.status == "archived"
    assert session.deleted == []
    assert session.commits == 1
    assert response["data"] == {"id": str(row.id), "status": "archived"}


@pytest.mark.asyncio
async def test_an_archived_skill_is_reviewable_again(monkeypatch):
    row = skill(status="archived")
    use(monkeypatch, FakeSession(objects={(Memory, row.id): row}))

    with tenant_scope(TENANT):
        await skills_api.approve_skill(row.id, fake_request())

    assert row.status == "active"


# ── The persona block ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_procedural_skills_block_reads_only_active_skills():
    row = skill()
    session = FakeSession([row])

    block = await persona_context.procedural_skills_block(lambda: session, TENANT)

    assert block.startswith("## Learned Procedural Skills & Workflows")
    assert "Apply these previously distilled fixes" in block
    # The title becomes the heading; its own "# " line is not repeated.
    assert "### pytest cannot import pgvector" in block
    assert "\n# pytest cannot import pgvector" not in block
    assert "pip install -e '.[dev]'" in block

    text = sql(session.statements[0])
    assert f"'{TENANT}'" in text and "'active'" in text


@pytest.mark.asyncio
async def test_procedural_skills_block_is_empty_with_no_skills():
    assert await persona_context.procedural_skills_block(lambda: FakeSession([]), TENANT) == ""


@pytest.mark.asyncio
async def test_procedural_skills_block_reads_a_window_wider_than_the_limit():
    session = FakeSession([])

    await persona_context.procedural_skills_block(lambda: session, TENANT, limit=5)

    assert f"LIMIT {5 * persona_context.SKILL_WINDOW}" in sql(session.statements[0])


def test_the_projects_own_skills_come_first_then_general_ones():
    mine = skill(content="# project fix\nbody\n", tags=["uzhavu"])
    general = skill(content="# git fix\nbody\n", tags=["git"])
    other = skill(content="# someone elses\nbody\n", tags=["chit-fin"])

    block = persona_context.render_skills([other, general, mine], "uzhavu", limit=3)

    assert block.index("project fix") < block.index("git fix") < block.index("someone elses")


def test_a_project_stored_only_in_properties_still_ranks_first():
    mine = skill(content="# property project\nbody\n", props={"project": "uzhavu"})
    general = skill(content="# git fix\nbody\n", tags=["git"])

    block = persona_context.render_skills([general, mine], "uzhavu", limit=2)

    assert block.index("property project") < block.index("git fix")


def test_render_skills_honours_the_limit_and_clips_long_recipes():
    long_skill = skill(content="# long one\n" + ("x" * (persona_context.SKILL_CHARS + 500)))

    block = persona_context.render_skills([long_skill, skill(), skill()], None, limit=1)

    assert block.count("### ") == 1
    assert "[truncated]" in block
    assert len(block) < persona_context.SKILL_CHARS + 300
