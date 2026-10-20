"""Job 5 against the database: the check-in's figures are the sums of the rows,
transfers are not spending, overruns are named, and the API and the tool
show amounts only where they may."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"checkin_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "checkin-test"}


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


async def _add(rows):
    from life_graph.models.assistant import MoneyTransaction
    from life_graph.storage.database import async_session

    async with async_session() as s:
        for day, amount, category, merchant, direction in rows:
            s.add(
                MoneyTransaction(
                    tenant_id=TENANT,
                    occurred_on=day,
                    amount=Decimal(amount),
                    direction=direction,
                    description=f"{merchant} {amount}",
                    merchant=merchant,
                    category=category,
                    dedup_hash=uuid.uuid4().hex,
                )
            )
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_checkin_figures_match_the_rows(client):
    from life_graph.services import money, money_checkin
    from life_graph.storage.database import async_session

    today = date.today()
    this = today.replace(day=1)
    last = (this - timedelta(days=1)).replace(day=1)
    late_last = last.replace(day=28)  # after "the same days" unless today is the 28th or later
    await _add(
        [
            (this, "900.00", "food", "Swiggy", "debit"),
            (today, "350.50", "food", "Zomato", "debit"),
            (today, "5000.00", "transfers", None, "debit"),  # not spending
            (today, "2000.00", "income", None, "credit"),  # not spending
            (this, "1200.00", "travel", "Uber", "debit"),
            (last, "400.00", "food", "Swiggy", "debit"),
            (late_last, "777.00", "food", "Swiggy", "debit"),
        ]
    )
    async with async_session() as s:
        await money.set_budget(s, TENANT, "food", Decimal("1000"))
        await s.commit()
        c = await money_checkin.checkin(s, TENANT, today)

    food = next(x for x in c["categories"] if x["category"] == "food")
    assert food["spent"] == 1250.50  # 900 + 350.50
    expected_last = 400.0 + (777.0 if today.day >= 28 else 0.0)
    assert food["last_month"] == expected_last
    assert c["total_spent"] == 1250.50 + 1200.0  # transfers and income left out
    assert c["over_budget"] == ["food"] and food["percent_of_budget"] == 125
    assert c["transactions"] == 5
    assert c["top_merchants"][0] == {"merchant": "Uber", "spent": 1200.0}

    api = (await client.get("/api/v1/money/checkin")).json()["data"]
    assert api["total_spent"] == c["total_spent"]
    assert any(
        line.startswith("Over budget: food 125% (₹1,250 of ₹1,000)") for line in api["lines"]
    )

    from life_graph.connectors.locality import CLOUD, LOCAL, audience
    from life_graph.core.tenant import set_tenant_context
    from life_graph.tools.assistant import money_checkin as tool

    set_tenant_context(TENANT, "checkin-test")
    with audience(CLOUD):
        cloud = json.loads(await tool())
    assert "checkin" not in cloud and "₹" not in json.dumps(cloud, ensure_ascii=False)
    assert "Over budget: food 125%." in cloud["lines"]
    with audience(LOCAL):
        local = json.loads(await tool())
    assert local["checkin"]["total_spent"] == c["total_spent"]
