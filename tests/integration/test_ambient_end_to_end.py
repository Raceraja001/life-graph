# tests/integration/test_ambient_end_to_end.py
"""Seed → ticker → advisory task completes → findings become notifications."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_findings_bridge_end_to_end_creates_and_pushes(monkeypatch):
    from life_graph.services.findings_bridge import FindingsBridge

    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n"})
    push = AsyncMock()
    push.send_to_tenant = AsyncMock(return_value=1)
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    result_text = (
        "Scouted your topics.\n"
        '[{"title":"pgvector 0.9 HNSW","detail":"faster recall","urgency":"brief"},'
        '{"title":"Cert expires in 3 days","detail":"renew now","urgency":"now"}]'
    )
    created = await bridge.process_result(
        "personal", "scout", "44444444-4444-4444-4444-444444444444", result_text
    )
    assert created == 2
    # urgent pushed, brief held
    assert push.send_to_tenant.await_count == 1
    briefs = [c for c in engine.create.await_args_list if c.kwargs["deliver_at_brief"]]
    assert len(briefs) == 1
