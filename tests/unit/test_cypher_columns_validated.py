"""Raw-Cypher result columns are identifiers only (audit 2026-11-19, M4).

``columns`` is spliced into ``AS (<col> agtype, ...)``; the write-keyword
filter only looks at ``cypher``, so an unchecked column could close the
column list and append SQL.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from life_graph.api.graph import CypherQuery
from life_graph.storage import graph as graph_storage
from life_graph.storage.graph import MAX_CYPHER_COLUMNS, GraphStore


@pytest.mark.parametrize(
    "columns",
    [
        ["v agtype) --"],
        ["v", "x agtype); DROP TABLE memories; --"],
        ["1v"],
        [""],
        [],
        [f"c{i}" for i in range(MAX_CYPHER_COLUMNS + 1)],
    ],
)
def test_model_rejects_bad_columns(columns):
    with pytest.raises(ValidationError):
        CypherQuery(cypher="MATCH (n) RETURN n", columns=columns)


def test_model_accepts_identifiers():
    q = CypherQuery(cypher="MATCH (a)-[r]->(b) RETURN a, r, b", columns=["a", "r", "b_2"])
    assert q.columns == ["a", "r", "b_2"]
    assert CypherQuery(cypher="MATCH (n) RETURN n").columns is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "columns",
    [["v agtype) --"], [], [f"c{i}" for i in range(MAX_CYPHER_COLUMNS + 1)]],
)
async def test_store_rejects_bad_columns_before_any_sql(monkeypatch, columns):
    pool = AsyncMock(side_effect=AssertionError("must not reach the pool"))
    monkeypatch.setattr(graph_storage, "_get_pool", pool)
    with pytest.raises(ValueError):
        await GraphStore().execute_cypher("MATCH (n) RETURN n", columns=columns)
    pool.assert_not_called()


@pytest.mark.asyncio
async def test_store_still_runs_with_valid_columns(monkeypatch):
    monkeypatch.setattr(graph_storage, "_get_pool", AsyncMock(return_value=None))
    assert await GraphStore().execute_cypher("MATCH (n) RETURN n", columns=["n"]) == []
