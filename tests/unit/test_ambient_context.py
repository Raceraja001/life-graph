from unittest.mock import AsyncMock, patch

import pytest

from life_graph.services import ambient_context as ac


@pytest.mark.asyncio
async def test_build_scout_input_includes_topics_and_novelty():
    with patch.object(ac, "_recent_finding_titles", AsyncMock(return_value=["Old thing"])), \
         patch.object(ac, "_memory_signal_tags", AsyncMock(return_value=["pgvector"])):
        out = await ac.build_ambient_input("scout", {"topics": ["Caddy", "local LLMs"]}, "t1")
    msg = out["message"]
    assert "Caddy" in msg and "local LLMs" in msg      # watch-list present
    assert "Old thing" in msg                          # novelty (do-not-repeat) present
    assert "pgvector" in msg                           # memory signal present
    assert "JSON" in msg                               # output contract reminder present


@pytest.mark.asyncio
async def test_build_admin_input_has_no_topics_section():
    with patch.object(ac, "_recent_finding_titles", AsyncMock(return_value=[])), \
         patch.object(ac, "_memory_signal_tags", AsyncMock(return_value=[])):
        out = await ac.build_ambient_input("admin", {}, "t1")
    assert "watch-list" not in out["message"].lower()
    assert "message" in out
