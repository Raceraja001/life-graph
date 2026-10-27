"""approvals_waiting (docs/specs/web-chat-wave1.md F4): Jarvis lists only this
tenant's pending approvals, read-only."""

from __future__ import annotations

import json
import uuid

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"apw_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
@skip_on_db_error
async def test_only_this_tenants_pending_approvals():
    from life_graph.core.tenant import set_tenant_context
    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session
    from life_graph.tools.approvals import approvals_waiting

    async with async_session() as s:
        s.add_all(
            [
                Approval(tenant_id=TENANT, kind="driver_pr", title="Open PR: Tests for x", status="pending",
                         source="driver", payload={"verified": True, "change": {"files": ["tests/a.py"]}}),
                Approval(tenant_id=TENANT, kind="driver_pr", title="Old one", status="approved", source="driver"),
                Approval(tenant_id="someone_else", kind="driver_pr", title="Not yours", status="pending",
                         source="driver"),
            ]
        )
        await s.commit()
    set_tenant_context(TENANT, "system")
    out = json.loads(await approvals_waiting())
    assert out["total"] == 1
    assert [(i["title"], i["verified"], i["files"]) for i in out["items"]] == [("Open PR: Tests for x", True, 1)]
