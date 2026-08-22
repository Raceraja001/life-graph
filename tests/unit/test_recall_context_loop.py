"""The context keys recall ranks on must be the keys ingestion stores.

RecallRanker gives context relevance _WEIGHT_CONTEXT (0.20) of the total score,
computed from four keys on the candidate: project, module, tools, files.
RecallEngine._retrieve_candidates reads all four out of Memory.properties.
Nothing wrote them: across 880 memories the live database held exactly three
distinct property keys — fact_type, extraction_confidence and entities.

So context_similarity returned 0.0 for every candidate, and 20% of the ranking
weight did no ranking. Nothing errored; results were just ordered as though
context did not exist.

MemoryManager.ingest() already merges its `context` argument into properties,
and POST /api/v1/agent/learn already accepts a context dict documented as
"(project, tool, etc.)". The endpoint pulled `source` out of it and discarded
the rest, so the same bridge that asked recall for project-scoped memories
stored those memories with no project.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.scoring.ranking import (
    _WEIGHT_CONTEXT,
    context_similarity,
)

# ── The contract between ranker and retriever ─────────────────────────

CONTEXT_KEYS = {"project", "module", "tools", "files"}


def test_ranker_scores_exactly_the_keys_retrieval_supplies():
    """A key one side adds and the other does not is silently dead weight."""
    import ast
    import textwrap

    from life_graph.services.recall import RecallEngine

    src = textwrap.dedent(inspect.getsource(RecallEngine._retrieve_candidates))
    built = {
        k.value
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.Dict)
        for k in node.keys
        if isinstance(k, ast.Constant) and isinstance(k.value, str)
    }

    ranker_src = textwrap.dedent(inspect.getsource(context_similarity))
    scored = {
        node.args[0].value
        for node in ast.walk(ast.parse(ranker_src))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    } & CONTEXT_KEYS

    assert scored <= built, (
        f"context_similarity scores {sorted(scored - built)}, which "
        "_retrieve_candidates never puts on a candidate"
    )


def test_context_similarity_is_dead_without_the_keys():
    """Documents the cost, so the number is not rediscovered by accident."""
    ctx = {
        "project": "life_graph",
        "module": "recall",
        "tools": ["pytest"],
        "files": ["a.py"],
    }
    empty = {"project": "", "module": "", "tools": [], "files": []}

    assert context_similarity(empty, ctx) == 0.0
    assert context_similarity(dict(ctx), ctx) == 1.0
    assert pytest.approx(0.20) == _WEIGHT_CONTEXT


# ── Ingestion carries context into properties ─────────────────────────


@pytest.mark.asyncio
async def test_bridge_learn_passes_context_to_ingest():
    from life_graph.services.agent_bridge import LifeGraphBridge

    manager = MagicMock()
    manager.ingest = AsyncMock(return_value=[])
    bridge = LifeGraphBridge(
        store=MagicMock(),
        recall_engine=MagicMock(),
        memory_manager=manager,
        intention_service=MagicMock(),
    )

    await bridge.learn_from_task(
        conversation="we chose Postgres",
        source="agent_task",
        context={"project": "life_graph", "module": "recall"},
    )

    kwargs = manager.ingest.await_args.kwargs
    assert kwargs["context"] == {"project": "life_graph", "module": "recall"}, (
        "the project the bridge recalls by is not the project it stores by"
    )


def test_learn_endpoint_forwards_the_whole_context():
    """The endpoint took `source` out of body.context and dropped the rest."""
    import ast
    import textwrap

    from life_graph.api import agent as agent_api

    src = textwrap.dedent(inspect.getsource(agent_api.learn_from_task))
    tree = ast.parse(src)

    forwards = any(
        isinstance(node, ast.keyword) and node.arg == "context" for node in ast.walk(tree)
    )
    assert forwards, (
        "POST /agent/learn accepts a context dict documented as "
        '"(project, tool, etc.)" but never forwards it to ingestion'
    )


@pytest.mark.asyncio
async def test_ingest_merges_context_into_properties():
    """Pins the mechanism the fix depends on."""
    import ast
    import textwrap

    from life_graph.core.memory_manager import MemoryManager

    src = textwrap.dedent(inspect.getsource(MemoryManager._process_fact))
    tree = ast.parse(src)

    merges = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "update"
        and isinstance(node.func.value, ast.Name)
        and "propert" in node.func.value.id.lower()
        for node in ast.walk(tree)
    )
    assert merges, "ingestion no longer merges context into properties"


# ── End to end: the loop closes ───────────────────────────────────────


def test_a_memory_stored_with_context_scores_against_that_context():
    """What the whole chain is for."""
    stored_properties = {"project": "life_graph", "module": "recall"}

    # what _retrieve_candidates builds from that row
    candidate = {
        "project": stored_properties.get("project", ""),
        "module": stored_properties.get("module", ""),
        "tools": stored_properties.get("tools", []),
        "files": stored_properties.get("files", []),
    }
    session_context = {"project": "life_graph", "module": "recall"}

    score = context_similarity(candidate, session_context)
    assert score == pytest.approx(0.5), "project (0.3) + module (0.2)"
    assert score * _WEIGHT_CONTEXT > 0
