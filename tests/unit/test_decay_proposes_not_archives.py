"""Decay demotes a memory; removing it is a separate, approved decision.

Two paths used to flip status to 'archived' automatically — the nightly
consolidation step and the decay sweep worker. Every recall query filters on
status = 'active', so a decayed memory silently disappeared from recall with
no record of the decision and no way back short of a manual unarchive().

Nothing was actually deleted — archive is a soft state — but from the user's
side a memory that cannot be recalled is gone. Every non-critical memory
crossed that line 24-51 days after its last access.

Demotion is already handled by ranking: the recency and frequency signals are
computed from the same inputs decay uses, so a memory nobody touches sinks in
the order on its own, without anything hiding it. What decay contributes now
is a *proposal*, queued as an approval exactly the way workers/cleanup.py
queues merges, and nothing changes status until someone resolves it.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
import uuid
from unittest.mock import MagicMock

import pytest

# ── Neither decay path may archive on its own ─────────────────────────


def _source(fn) -> str:
    return textwrap.dedent(inspect.getsource(fn))


def test_consolidation_no_longer_archives():
    from life_graph.jobs.consolidation import ConsolidationPipeline

    src = _source(ConsolidationPipeline._update_decay_scores)
    assert 'status="archived"' not in src, (
        "the nightly consolidation must not hide memories by itself"
    )
    assert "update(Memory)" not in src, "no status write belongs in this step"


def test_decay_sweep_no_longer_archives():
    from life_graph.workers import decay

    # Parse rather than string-match: the explanatory comment in that
    # function legitimately quotes the SQL it replaced, and comments do not
    # survive into the AST.
    tree = ast.parse(_source(decay.run_decay_sweep))
    sql = " ".join(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )
    assert "SET status = 'archived'" not in sql
    assert "_queue_archive_proposals" in _source(decay.run_decay_sweep), (
        "it should propose instead"
    )


def test_decay_sweep_skips_critical_memories():
    from life_graph.workers import decay

    src = _source(decay.run_decay_sweep)
    assert "importance_tier <> 'critical'" in src, (
        "critical memories were exempt from archival and must stay exempt "
        "from proposals too"
    )


def test_proposals_are_capped():
    """An unbounded first sweep would bury the approval queue."""
    from life_graph.config import settings
    from life_graph.workers import decay

    assert settings.decay_proposal_limit > 0
    assert "decay_proposal_limit" in _source(decay.run_decay_sweep)


def test_proposals_are_idempotent_on_source_ref():
    from life_graph.workers import decay

    src = _source(decay._queue_archive_proposals)
    assert "source_ref" in src
    assert "Approval.kind ==" in src or 'kind="archive"' in src


def test_proposal_carries_what_a_reviewer_needs():
    from life_graph.workers import decay

    tree = ast.parse(_source(decay._queue_archive_proposals))
    payload_keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "payload" and isinstance(
            node.value, ast.Dict
        ):
            payload_keys |= {
                k.value for k in node.value.keys if isinstance(k, ast.Constant)
            }
    assert {"memory_id", "effective_importance", "importance_tier"} <= payload_keys


# ── Resolution ────────────────────────────────────────────────────────


class _FakeMemory:
    def __init__(self, tenant_id="acme", status="active"):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.status = status


def _service(memory):
    from life_graph.services.approvals import ApprovalService

    session = MagicMock()

    async def _get(_model, _pk):
        return memory

    session.get = _get
    svc = ApprovalService.__new__(ApprovalService)
    svc.session = session
    return svc


def _approval(memory, tenant_id="acme"):
    appr = MagicMock()
    appr.kind = "archive"
    appr.payload = {"memory_id": str(memory.id)}
    appr.tenant_id = tenant_id
    return appr


@pytest.mark.asyncio
async def test_approving_archives_the_memory():
    mem = _FakeMemory()
    await _service(mem)._apply_archive("acme", _approval(mem), approve=True)
    assert mem.status == "archived"


@pytest.mark.asyncio
async def test_rejecting_leaves_it_active():
    mem = _FakeMemory()
    await _service(mem)._apply_archive("acme", _approval(mem), approve=False)
    assert mem.status == "active"


@pytest.mark.asyncio
async def test_a_memory_recalled_since_the_proposal_is_spared():
    """Status changed under us — the proposal is stale, not authoritative."""
    mem = _FakeMemory(status="superseded")
    await _service(mem)._apply_archive("acme", _approval(mem), approve=True)
    assert mem.status == "superseded"


@pytest.mark.asyncio
async def test_another_tenants_memory_is_never_touched():
    mem = _FakeMemory(tenant_id="globex")
    await _service(mem)._apply_archive("acme", _approval(mem), approve=True)
    assert mem.status == "active"


@pytest.mark.asyncio
async def test_a_malformed_payload_is_survivable():
    mem = _FakeMemory()
    appr = _approval(mem)
    appr.payload = {"memory_id": "not-a-uuid"}
    await _service(mem)._apply_archive("acme", appr, approve=True)
    assert mem.status == "active"

    appr.payload = {}
    await _service(mem)._apply_archive("acme", appr, approve=True)
    assert mem.status == "active"


def test_resolve_routes_the_archive_kind():
    from life_graph.services.approvals import ApprovalService

    src = _source(ApprovalService.resolve)
    assert '"archive"' in src, "resolve() must dispatch the kind decay queues"


# ── Archiving stays reversible ────────────────────────────────────────


def test_archive_is_reversible_not_deletion():
    from life_graph.storage.postgres import PostgresMemoryStore

    assert hasattr(PostgresMemoryStore, "unarchive")


def test_no_decay_path_deletes_a_memory():
    from life_graph.jobs.consolidation import ConsolidationPipeline
    from life_graph.workers import decay

    for fn in (
        ConsolidationPipeline._update_decay_scores,
        decay.run_decay_sweep,
        decay._queue_archive_proposals,
    ):
        src = _source(fn)
        assert "delete(" not in src and "DELETE" not in src, (
            f"{fn.__qualname__} must never delete a memory"
        )
