"""Unit test for the distill_transcript ARQ job wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.workers import distill_transcript as job


@pytest.mark.asyncio
async def test_job_sets_tenant_and_calls_distiller(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        job,
        "set_tenant_context",
        lambda tid, actor: calls.update(tenant=tid, actor=actor),
    )
    distiller = MagicMock()
    distiller.distill = AsyncMock(return_value={"new_facts": 3})
    monkeypatch.setattr("life_graph.api.dependencies.get_transcript_distiller", lambda: distiller)

    result = await job.distill_transcript({}, "sess-1", "personal")

    assert result == {"new_facts": 3}
    assert calls["tenant"] == "personal"
    distiller.distill.assert_awaited_once_with("sess-1")


def test_job_name_constant_matches_dotted_path():
    assert job.DISTILL_TRANSCRIPT_JOB == "life_graph.workers.distill_transcript.distill_transcript"
