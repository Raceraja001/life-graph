"""Phase C: statement import, dedup, learned categories, budgets and alerts."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

CSV = """Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/10/26,UPI-SWIGGY-swiggy@icici-ICIC0001-1,1,01/10/26,450.00,,10550.00
03/10/26,UPI-ZOMATO-zomato@hdfc-HDFC0001-2,2,03/10/26,4200.00,,6350.00
04/10/26,UPI-KUMAR STORES-kumar@okaxis-UTIB0001-3,3,04/10/26,800.00,,5550.00
05/10/26,UPI-KUMAR STORES-kumar@okaxis-UTIB0001-4,4,05/10/26,300.00,,5250.00
02/10/26,SALARY OCT 2026 ACME PVT LTD,9,02/10/26,,85000.00,90250.00
"""


class _NoModel:
    async def chat_local_only(self, **_kw):
        return ""


@pytest.fixture
def no_model(monkeypatch):
    import life_graph.api.dependencies as deps

    monkeypatch.setattr(deps, "get_lm_client", lambda: _NoModel())


def _client(tenant: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "money-test"},
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_import_dedup_learn_budget_and_alert(no_model):
    from life_graph.services import assistant_daily
    from life_graph.storage.database import async_session

    tenant = f"money_{uuid.uuid4().hex[:8]}"
    async with _client(tenant) as c:
        r = await c.post("/api/v1/money/import", json={"csv": CSV})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["added"] == 5
        again = (await c.post("/api/v1/money/import", json={"csv": CSV})).json()["data"]
        assert again["added"] == 0 and again["duplicates"] == 5

        alert = "Rs.120.00 debited from A/c XX1234 on 06-10-26 to VPA swiggy@icici UPI Ref 9."
        r = await c.post("/api/v1/money/alerts", json={"texts": [alert, "Your OTP is 1234"]})
        assert r.json()["data"]["added"] == 1 and r.json()["data"]["not_transactions"] == 1

        txns = (await c.get("/api/v1/money/transactions", params={"month": "2026-10"})).json()[
            "data"
        ]
        by_merchant = {t["merchant"]: t for t in txns}
        assert by_merchant["SWIGGY"]["category"] == "food"
        kumar = [t for t in txns if t["merchant"] == "KUMAR STORES"]
        assert {t["category"] for t in kumar} == {"uncategorised"}

        # Correcting one KUMAR STORES row files both, and future imports.
        r = await c.patch(
            f"/api/v1/money/transactions/{kumar[0]['id']}",
            json={"category": "groceries", "remember": True},
        )
        assert r.status_code == 200
        txns = (await c.get("/api/v1/money/transactions", params={"month": "2026-10"})).json()[
            "data"
        ]
        assert {t["category"] for t in txns if t["merchant"] == "KUMAR STORES"} == {"groceries"}
        assert (
            await c.patch(f"/api/v1/money/transactions/{kumar[0]['id']}", json={"category": "nope"})
        ).status_code == 422

        r = await c.put("/api/v1/money/budgets/food", json={"monthly_limit": 5000})
        assert r.status_code == 200
        summary = (await c.get("/api/v1/money/summary", params={"month": "2026-10"})).json()["data"]
        food = next(x for x in summary["categories"] if x["category"] == "food")
        assert food["spent"] == 4770.0 and food["percent_of_budget"] == 95
        assert summary["income"] == 85000.0

    class Notes:
        created: list = []

        async def create(self, tenant_id, title, **kw):
            self.created.append((tenant_id, title, kw))

    notes = Notes()
    await assistant_daily.run_daily(async_session, notes, date(2026, 10, 20))
    mine = [n for n in notes.created if n[0] == tenant]
    assert [n[1] for n in mine] == ["Food spending at 95% of budget"]
    notes.created.clear()
    await assistant_daily.run_daily(async_session, notes, date(2026, 10, 21))
    assert [n for n in notes.created if n[0] == tenant] == []

    lines = await assistant_daily.brief_lines(async_session, tenant, date(2026, 10, 21))
    assert "Budgets this month: food 95%" in lines

    async with _client(f"money_other_{uuid.uuid4().hex[:8]}") as other:
        assert (await other.get("/api/v1/money/transactions", params={"month": "2026-10"})).json()[
            "data"
        ] == []
