"""The candidate gate, the prompt, and the three actions of the distiller.

No database, no embedding model and no LLM: every collaborator is injected.
The gate tests matter most — it is the only thing standing between a corpus
of reusable procedures and a corpus of "ran ls, saw files".
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.models.db import Memory
from life_graph.services.skill_distiller import (
    FACT_TYPE,
    SOURCE_TYPE,
    DistillationResult,
    SkillDistillationEngine,
    parse_llm_json,
    render_skill,
)
from life_graph.watchers.agent_transcripts.normalizer import NormalizedSessionSlice
from tests.unit.fakes import FakeSession, session_factory

TENANT = "personal"

SKILL_REPLY = {
    "action": "CREATE_SKILL",
    "reasoning": "This environment failure recurs across projects.",
    "skill": {
        "title": "pytest cannot import pgvector",
        "context_symptoms": "pytest aborts with ModuleNotFoundError: No module named 'pgvector'",
        "workflow_commands": "pip install -e '.[dev]'\npytest tests/unit -q",
        "pitfalls": "A shell with the wrong venv active reinstalls into the system python.",
        "tags": ["pytest", "Python Env"],
    },
    "target_memory_id": None,
    "patch_notes": None,
}


def slice_of(**overrides) -> NormalizedSessionSlice:
    """A slice that passes the gate, unless *overrides* break it."""
    defaults = {
        "session_id": "sess-1",
        "project_name": "life-graph",
        "agent_type": "claude_code",
        "user_prompt": "pytest fails with ModuleNotFoundError: No module named pgvector",
        "tool_calls": [
            {
                "tool_name": "Bash",
                "command": "pytest -q",
                "output_snippet": "ModuleNotFoundError: No module named 'pgvector'",
                "is_error": True,
                "exit_code": 1,
            },
            {
                "tool_name": "Bash",
                "command": "pip install -e '.[dev]'",
                "output_snippet": "Successfully installed pgvector-0.3.6",
                "is_error": False,
                "exit_code": 0,
            },
        ],
        "resolution_summary": "Installed the dev extra into the venv; the suite passes.",
        "has_errors": True,
        "has_fixes": True,
        "file_path": "/home/raja/.claude/projects/p/sess-1.jsonl",
    }
    return NormalizedSessionSlice(**{**defaults, **overrides})


def engine(
    *,
    reply=None,
    related=None,
    session=None,
    llm=None,
) -> tuple[SkillDistillationEngine, FakeSession, MagicMock]:
    """An engine wired to fakes, with the session and llm handed back for asserts."""
    fake_session = session if session is not None else FakeSession()
    if llm is None:
        llm = MagicMock()
        payload = reply if isinstance(reply, str) else json.dumps(reply or SKILL_REPLY)
        llm.chat = AsyncMock(return_value=payload)
    query_engine = MagicMock()
    query_engine.tri_search = AsyncMock(return_value={"memories": related or []})
    embeddings = MagicMock()
    embeddings.embed_async = AsyncMock(return_value=[0.25] * 8)
    return (
        SkillDistillationEngine(
            TENANT,
            session_factory=session_factory(fake_session),
            resilient_llm=llm,
            query_engine=query_engine,
            embedding_service=embeddings,
        ),
        fake_session,
        llm,
    )


# ── Gate: what gets through ──────────────────────────────────────────────


def test_a_bug_fix_with_an_error_and_a_recovery_is_a_candidate():
    assert engine()[0].filter_candidate(slice_of()) is True


def test_a_multi_step_build_change_with_no_failure_is_a_candidate():
    assert (
        engine()[0].filter_candidate(
            slice_of(
                user_prompt="split the docker build into a slim runtime stage",
                has_errors=False,
                has_fixes=False,
                tool_calls=[
                    {"tool_name": "Edit", "command": "Dockerfile", "output_snippet": "ok"},
                    {"tool_name": "Bash", "command": "docker build .", "output_snippet": "built"},
                    {"tool_name": "Bash", "command": "docker run app", "output_snippet": "up"},
                ],
                resolution_summary="Multi-stage build in place; the image is 140MB smaller.",
            )
        )
        is True
    )


@pytest.mark.parametrize(
    "prompt",
    ["hi", "thanks!", "ok", "continue", "/compact", "yes"],
)
def test_greetings_and_acknowledgements_are_rejected(prompt):
    assert engine()[0].filter_candidate(slice_of(user_prompt=prompt)) is False


def test_a_turn_with_no_tool_calls_is_rejected():
    assert (
        engine()[0].filter_candidate(slice_of(tool_calls=[], has_errors=False, has_fixes=False))
        is False
    )


def test_a_read_only_question_is_rejected():
    assert (
        engine()[0].filter_candidate(
            slice_of(
                user_prompt="where is the tenant middleware defined?",
                has_errors=False,
                has_fixes=False,
                tool_calls=[
                    {"tool_name": "Grep", "command": "TenantMiddleware", "output_snippet": "x"},
                    {"tool_name": "Read", "command": "/repo/main.py", "output_snippet": "y"},
                    {"tool_name": "Glob", "command": "**/*.py", "output_snippet": "z"},
                ],
                resolution_summary="It lives in core/tenant.py.",
            )
        )
        is False
    )


def test_an_abandoned_session_whose_error_was_never_resolved_is_rejected():
    assert engine()[0].filter_candidate(slice_of(has_errors=True, has_fixes=False)) is False


def test_routine_work_with_no_failure_and_no_signal_is_rejected():
    assert (
        engine()[0].filter_candidate(
            slice_of(
                user_prompt="bump the copyright year in the footer component",
                has_errors=False,
                has_fixes=False,
                tool_calls=[{"tool_name": "Edit", "command": "footer.tsx", "output_snippet": "ok"}],
                resolution_summary="Done.",
            )
        )
        is False
    )


def test_a_clean_multi_step_turn_with_no_closing_message_is_rejected():
    assert (
        engine()[0].filter_candidate(
            slice_of(
                has_errors=False,
                has_fixes=False,
                resolution_summary="",
                tool_calls=[
                    {"tool_name": "Bash", "command": "pytest", "output_snippet": "ok"},
                    {"tool_name": "Edit", "command": "a.py", "output_snippet": "ok"},
                    {"tool_name": "Edit", "command": "b.py", "output_snippet": "ok"},
                ],
            )
        )
        is False
    )


def test_read_only_tool_names_are_matched_however_they_are_spelled():
    gate = engine()[0]
    for name in ("Read", "read_file", "GlobTool", "codebase-search", "WebFetch"):
        assert gate._is_read_only(name) is True, name
    for name in ("Bash", "Edit", "Write", "terminal", "shell"):
        assert gate._is_read_only(name) is False, name


# ── Prompt ───────────────────────────────────────────────────────────────


def test_the_prompt_carries_the_turn_the_tools_and_the_existing_skills():
    distiller = engine()[0]
    prompt = distiller.build_prompt(
        slice_of(),
        [{"id": "mem-1", "content": "# pip install basics", "tags": ["skill"]}],
    )
    assert "pytest fails with ModuleNotFoundError" in prompt
    assert "1. Bash [ERROR, exit 1]: pytest -q" in prompt
    assert "ModuleNotFoundError" in prompt
    assert "Installed the dev extra" in prompt
    assert "id=mem-1" in prompt
    assert "# pip install basics" in prompt


def test_the_prompt_says_so_when_nothing_is_stored_yet():
    assert "(none stored yet)" in engine()[0].build_prompt(slice_of(), [])


def test_only_the_most_recent_tool_calls_reach_the_prompt():
    many = [
        {"tool_name": "Bash", "command": f"step-{i}", "output_snippet": "", "is_error": False}
        for i in range(30)
    ]
    prompt = engine()[0].build_prompt(slice_of(tool_calls=many), [])
    assert "step-29" in prompt
    assert "step-0\n" not in prompt


@pytest.mark.asyncio
async def test_unrelated_memories_are_not_offered_as_existing_skills():
    distiller, _, llm = engine(
        related=[
            {
                "id": "m1",
                "content": "# Fix the venv",
                "tags": ["skill"],
                "source_type": SOURCE_TYPE,
            },
            {"id": "m2", "content": "Raja prefers Gemini Flash", "tags": ["preference"]},
        ]
    )
    result = await distiller.distill(slice_of())
    prompt = llm.chat.await_args.kwargs["messages"][1]["content"]
    assert "id=m1" in prompt
    assert "id=m2" not in prompt
    assert result.related_skill_ids == ["m1"]


@pytest.mark.asyncio
async def test_a_failing_related_search_does_not_stop_distillation():
    distiller, fake, _ = engine()
    distiller._query_engine.tri_search = AsyncMock(side_effect=RuntimeError("no pgvector"))
    result = await distiller.distill(slice_of())
    assert result.action == "CREATE_SKILL"
    assert result.persisted is True
    assert len(fake.added) == 1


# ── CREATE_SKILL ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_skill_writes_one_memory_stamped_as_a_procedural_skill():
    distiller, fake, _ = engine()
    result = await distiller.distill(slice_of())

    assert (result.action, result.persisted, result.created) == ("CREATE_SKILL", True, True)
    assert len(fake.added) == 1
    assert fake.commits == 1

    memory = fake.added[0]
    assert isinstance(memory, Memory)
    assert memory.tenant_id == TENANT
    assert memory.source_type == SOURCE_TYPE
    assert memory.status == "active"
    assert memory.source == "skill_distiller:claude_code"
    assert memory.properties == {
        "surface": "cli",
        "fact_type": FACT_TYPE,
        "origin_agent": "claude_code",
        "session_id": "sess-1",
        "transcript_path": "/home/raja/.claude/projects/p/sess-1.jsonl",
        "distilled_at": memory.properties["distilled_at"],
    }
    assert memory.tags == ["skill", "dev-agent", "life-graph", "pytest", "python-env"]
    assert memory.embedding == [0.25] * 8
    assert memory.reasoning == "This environment failure recurs across projects."
    assert str(memory.id) == result.memory_id


@pytest.mark.asyncio
async def test_the_stored_recipe_has_the_four_fixed_sections():
    distiller, fake, _ = engine()
    await distiller.distill(slice_of())
    content = fake.added[0].content
    assert content.splitlines()[0] == "# pytest cannot import pgvector"
    assert "## Context & Symptoms" in content
    assert "## Reusable Workflow / Commands" in content
    assert "## Pitfalls / Edge Cases" in content
    assert "pip install -e '.[dev]'" in content


@pytest.mark.asyncio
async def test_an_unknown_project_name_is_not_tagged():
    distiller, fake, _ = engine()
    await distiller.distill(slice_of(project_name="unknown"))
    assert fake.added[0].tags == ["skill", "dev-agent", "pytest", "python-env"]


@pytest.mark.asyncio
async def test_a_skill_is_still_stored_when_embedding_is_unavailable():
    distiller, fake, _ = engine()
    distiller._embedding_service.embed_async = AsyncMock(side_effect=RuntimeError("no model"))
    result = await distiller.distill(slice_of())
    assert result.persisted is True
    assert fake.added[0].embedding is None


@pytest.mark.asyncio
async def test_create_skill_without_a_body_degrades_to_noop():
    distiller, fake, _ = engine(
        reply={"action": "CREATE_SKILL", "reasoning": "looked promising", "skill": {}}
    )
    result = await distiller.distill(slice_of())
    assert result.action == "NOOP"
    assert "no skill body" in result.reasoning
    assert fake.added == []


# ── PATCH_EXISTING ───────────────────────────────────────────────────────

PATCH_REPLY = {
    "action": "PATCH_EXISTING",
    "reasoning": "Covered already; this adds the uv case.",
    "target_memory_id": "",
    "patch_notes": "With uv, `uv pip install -e '.[dev]'` is needed too.",
}


@pytest.mark.asyncio
async def test_patch_appends_to_the_existing_skill_and_counts_the_patch():
    target_id = uuid.uuid4()
    existing = Memory(
        id=target_id,
        tenant_id=TENANT,
        content="# pytest cannot import pgvector\n## Context & Symptoms\nold body",
        tags=["skill"],
        properties={"fact_type": FACT_TYPE},
        source_type=SOURCE_TYPE,
    )
    fake = FakeSession(existing)
    distiller, _, _ = engine(
        reply={**PATCH_REPLY, "target_memory_id": str(target_id)}, session=fake
    )

    result = await distiller.distill(slice_of())

    assert (result.action, result.persisted, result.patched) == ("PATCH_EXISTING", True, True)
    assert result.memory_id == str(target_id)
    assert existing.content.startswith("# pytest cannot import pgvector")
    assert "uv pip install" in existing.content
    assert "claude_code/life-graph" in existing.content
    assert existing.properties["patch_count"] == 1
    assert existing.properties["last_patch_session"] == "sess-1"
    assert existing.properties["fact_type"] == FACT_TYPE
    assert existing.tags == ["skill", "dev-agent"]
    assert existing.embedding == [0.25] * 8
    assert fake.commits == 1
    assert fake.added == []


@pytest.mark.asyncio
async def test_patching_a_memory_of_another_tenant_finds_nothing_and_noops():
    fake = FakeSession(None)
    distiller, _, _ = engine(
        reply={**PATCH_REPLY, "target_memory_id": str(uuid.uuid4())}, session=fake
    )
    result = await distiller.distill(slice_of())
    assert result.action == "NOOP"
    assert "not found" in result.reasoning
    assert fake.commits == 0
    # The lookup is tenant-scoped, which is what made it miss.
    from tests.unit.fakes import sql

    assert f"'{TENANT}'" in sql(fake.statements[0])


@pytest.mark.asyncio
async def test_a_patch_without_a_target_or_notes_noops():
    for reply in (
        {**PATCH_REPLY, "target_memory_id": None},
        {**PATCH_REPLY, "target_memory_id": str(uuid.uuid4()), "patch_notes": None},
    ):
        distiller, fake, _ = engine(reply=reply)
        result = await distiller.distill(slice_of())
        assert result.action == "NOOP"
        assert fake.commits == 0


@pytest.mark.asyncio
async def test_a_target_id_that_is_not_a_uuid_noops_without_a_query():
    distiller, fake, _ = engine(reply={**PATCH_REPLY, "target_memory_id": "the second one"})
    result = await distiller.distill(slice_of())
    assert result.action == "NOOP"
    assert "not a uuid" in result.reasoning
    assert fake.statements == []


# ── NOOP and bad replies ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_noop_writes_nothing():
    distiller, fake, _ = engine(reply={"action": "NOOP", "reasoning": "one-off, project-specific"})
    result = await distiller.distill(slice_of())
    assert (result.action, result.persisted) == ("NOOP", False)
    assert result.reasoning == "one-off, project-specific"
    assert fake.added == [] and fake.commits == 0


@pytest.mark.asyncio
async def test_a_slice_the_gate_rejects_never_reaches_the_model():
    distiller, fake, llm = engine()
    result = await distiller.distill(slice_of(user_prompt="hi"))
    assert result.action == "NOOP"
    assert "candidate gate" in result.reasoning
    llm.chat.assert_not_awaited()
    assert fake.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply",
    ["", "not json at all", "{", json.dumps({"action": "DELETE_EVERYTHING"}), json.dumps([1, 2])],
)
async def test_an_unusable_reply_is_treated_as_noop(reply):
    distiller, fake, _ = engine(reply=reply)
    result = await distiller.distill(slice_of())
    assert result.action == "NOOP"
    assert fake.added == []


@pytest.mark.asyncio
async def test_an_exhausted_llm_does_not_raise():
    llm = MagicMock()
    llm.chat = AsyncMock(side_effect=RuntimeError("All models exhausted"))
    distiller, fake, _ = engine(llm=llm)
    result = await distiller.distill(slice_of())
    assert result.action == "NOOP"
    assert "LLM unavailable" in result.reasoning
    assert fake.added == []


# ── Dry run ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_dry_run_renders_the_skill_but_writes_nothing():
    distiller, fake, llm = engine()
    result = await distiller.distill(slice_of(), dry_run=True)
    assert (result.action, result.dry_run, result.persisted) == ("CREATE_SKILL", True, False)
    assert "## Pitfalls / Edge Cases" in result.content
    assert result.tags == ["skill", "dev-agent", "life-graph", "pytest", "python-env"]
    assert result.memory_id is None
    assert fake.added == [] and fake.commits == 0
    llm.chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_dry_run_patch_touches_no_memory():
    target_id = uuid.uuid4()
    existing = Memory(id=target_id, tenant_id=TENANT, content="# old", tags=["skill"])
    fake = FakeSession(existing)
    distiller, _, _ = engine(
        reply={**PATCH_REPLY, "target_memory_id": str(target_id)}, session=fake
    )
    result = await distiller.distill(slice_of(), dry_run=True)
    assert result.persisted is False
    assert existing.content == "# old"
    assert fake.statements == [] and fake.commits == 0


# ── Pure helpers ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        '{"action": "NOOP"}',
        '```json\n{"action": "NOOP"}\n```',
        '```\n{"action": "NOOP"}\n```',
        'Sure! Here you go:\n{"action": "NOOP"}\nHope that helps.',
    ],
)
def test_parse_llm_json_survives_fences_and_chatter(raw):
    assert parse_llm_json(raw)["action"] == "NOOP"


@pytest.mark.parametrize("raw", ["", "   ", "no json here", "[1, 2]", "{oops}"])
def test_parse_llm_json_returns_an_empty_dict_when_nothing_parses(raw):
    assert parse_llm_json(raw) == {}


def test_render_skill_tolerates_missing_fields():
    rendered = render_skill({"title": "   "})
    assert rendered.startswith("# Untitled procedure")
    assert rendered.count("##") == 3


def test_a_fresh_result_claims_nothing():
    result = DistillationResult()
    assert (result.action, result.created, result.patched) == ("NOOP", False, False)
