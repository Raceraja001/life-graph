"""The roster against the database (docs/design/11_persona_roster_plan.md):
retired built-ins are seeded off and switched off on existing tenants, a
persona the user switched off stays off, and every message routes to Jarvis."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import update

from tests.integration.conftest import skip_on_db_error


async def _set_active(tenant: str, name: str, active: bool) -> None:
    from life_graph.models.db import AgentPersona
    from life_graph.storage.database import async_session

    async with async_session() as s:
        await s.execute(
            update(AgentPersona)
            .where(AgentPersona.tenant_id == tenant, AgentPersona.name == name)
            .values(is_active=active)
        )
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_retired_personas_are_off_and_stay_off():
    from life_graph.api.dependencies import get_persona_service
    from life_graph.kernel.personas import _BUILTIN_PERSONAS, RETIRED_PERSONAS

    svc = get_persona_service()
    tenant = f"roster_{uuid.uuid4().hex[:8]}"
    assert await svc.seed_builtins(tenant) == len(_BUILTIN_PERSONAS)
    active = {p["name"] for p in (await svc.list_all(tenant))[0]}
    assert not active & RETIRED_PERSONAS
    assert {"jarvis", "scout", "admin", "tutor", "cody", "ops", "support-desk"} <= active

    # A tenant seeded before the retirement has them on: the next seed turns
    # them off. One the user switched off is not switched back on.
    await _set_active(tenant, "chief", True)
    await _set_active(tenant, "scout", False)
    svc._invalidate_tenant_cache(tenant)
    assert await svc.seed_builtins(tenant) == 1
    assert await svc.get_by_name(tenant, "chief") is None
    assert await svc.get_by_name(tenant, "scout") is None
    assert await svc.seed_builtins(tenant) == 0  # nothing left to change

    from life_graph.kernel.chief_router import ChiefRouter

    router = ChiefRouter(None, svc, None)
    for intent in ("code", "research", "data", "general", "deploy"):
        assert await router._resolve_agent(tenant, intent) == "jarvis"
