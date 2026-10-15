"""Phase H: invoices over the API, the overdue sweep, and the support desk's
file confinement."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error


@pytest.mark.asyncio
@skip_on_db_error
async def test_invoice_lifecycle_numbering_and_overdue_sweep():
    from life_graph.services import assistant_daily
    from life_graph.storage.database import async_session

    tenant = f"inv_{uuid.uuid4().hex[:8]}"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "inv-test"},
    ) as c:
        body = {
            "client_name": "Asha Traders",
            "client_email": "asha@example.com",
            "items": [{"description": "Website", "quantity": 1, "unit_price": 20000}],
            "tax_rate": 18,
            "due_days": 0,
        }
        first = (await c.post("/api/v1/invoices", json=body)).json()["data"]
        second = (await c.post("/api/v1/invoices", json=body)).json()["data"]
        year = date.today().year
        assert first["number"] == f"INV-{year}-0001" and second["number"] == f"INV-{year}-0002"
        assert first["total"] == 23600.0

        page = await c.get(f"/api/v1/invoices/{first['id']}/html")
        assert page.status_code == 200 and "Asha Traders" in page.text

        sent = (await c.post(f"/api/v1/invoices/{first['id']}/send")).json()["data"]
        assert sent["delivery"] == "manual" and sent["email"]["to"] == "asha@example.com"
        assert (await c.post(f"/api/v1/invoices/{first['id']}/send")).status_code == 409
        assert (
            await c.patch(f"/api/v1/invoices/{first['id']}", json={"notes": "x"})
        ).status_code == 422
        assert (await c.post(f"/api/v1/invoices/{second['id']}/void")).json()["data"][
            "status"
        ] == "void"

    class Notes:
        created: list = []

        async def create(self, tenant_id, title, **kw):
            self.created.append((tenant_id, title, kw))

    notes = Notes()
    later = date.today() + timedelta(days=3)
    await assistant_daily.run_daily(async_session, notes, later)
    mine = [n for n in notes.created if n[0] == tenant]
    assert len(mine) == 1 and "3 days overdue" in mine[0][1]
    assert mine[0][2]["metadata"]["email"]["subject"].startswith("Reminder: invoice")
    notes.created.clear()
    await assistant_daily.run_daily(async_session, notes, later + timedelta(days=1))
    assert [n for n in notes.created if n[0] == tenant] == []  # a week between chasers
    assert "Invoices: 1 overdue" in await assistant_daily.brief_lines(async_session, tenant, later)


@pytest.mark.asyncio
@skip_on_db_error
async def test_support_desk_reads_docs_only(tmp_path):
    from life_graph.models.db import AgentTask, Project
    from life_graph.services import persona_context
    from life_graph.storage.database import async_session
    from life_graph.tools import code as code_tools
    from life_graph.tools._guards import confine_to

    (tmp_path / "README.md").write_text("Reset your password from Settings → Account.\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "faq.md").write_text("Refunds take 5 days.\n")
    (tmp_path / "app.py").write_text("SECRET = 'x'\n")

    tenant = f"support_{uuid.uuid4().hex[:8]}"
    async with async_session() as s:
        project = Project(tenant_id=tenant, name="shop", path=str(tmp_path), is_active=True)
        s.add(project)
        await s.flush()
        task = AgentTask(
            tenant_id=tenant,
            agent_name="support-desk",
            input={"message": "how do I reset my password?"},
            status="running",
            project_id=project.id,
        )
        s.add(task)
        await s.commit()
        task_id = task.id

    roots = await persona_context.docs_roots(async_session, tenant, task_id)
    assert sorted(roots) == sorted([str(tmp_path / "README.md"), str(tmp_path / "docs")])
    assert await persona_context.docs_roots(async_session, tenant, uuid.uuid4()) == []

    with confine_to(*roots):
        ok = json.loads(await code_tools.code_read(str(tmp_path / "docs" / "faq.md")))
        denied = json.loads(await code_tools.code_read(str(tmp_path / "app.py")))
    assert "Refunds" in json.dumps(ok)
    assert "error" in denied and "SECRET" not in json.dumps(denied)
    with confine_to():
        nothing = json.loads(await code_tools.code_read(str(tmp_path / "README.md")))
    assert "error" in nothing
