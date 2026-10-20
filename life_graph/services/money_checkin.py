"""Job 5 — the money check-in: where the money went, what changed, what is over.

docs/specs/money-checkin-and-app-health.md (Job 5 of
docs/design/11_persona_roster_plan.md). Plain code over the imported
transactions (services/money.py), no model: every figure is a sum of rows,
so it can be checked against them.

* **This period** is the month so far (the 1st to today); it is compared with
  the same days of last month, so the 20th is never set against a whole month.
* **Over budget** names each category at or past 100% of its monthly budget,
  and **near** those at 80% or more.
* **Changes** are the categories that moved most against last month.

Two renderings: the full one (amounts, merchants) for the dashboard and the
local model, and a cloud-safe one (categories and percentages only) for the
brief, which leaves the machine through Telegram and Web Push.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_NOT_SPENDING = ("transfers", "investments")
OVER, NEAR = 100, 80
_TOP = 3


def periods(today: date) -> tuple[tuple[date, date], tuple[date, date]]:
    """(this month so far, the same days of last month) as [start, end) pairs."""
    start = today.replace(day=1)
    last_end_month = start - timedelta(days=1)
    last_start = last_end_month.replace(day=1)
    # The 31st against a 30-day month compares with the whole of it.
    day = min(today.day, calendar.monthrange(last_start.year, last_start.month)[1])
    return (start, today + timedelta(days=1)), (
        last_start,
        last_start.replace(day=day) + timedelta(days=1),
    )


async def _spent(
    session: AsyncSession, tenant_id: str, start: date, end: date
) -> dict[str, Decimal]:
    from life_graph.models.assistant import MoneyTransaction as T

    rows = await session.execute(
        select(T.category, func.sum(T.amount))
        .where(
            T.tenant_id == tenant_id,
            T.occurred_on >= start,
            T.occurred_on < end,
            T.direction == "debit",
            T.category.not_in(_NOT_SPENDING),
        )
        .group_by(T.category)
    )
    return {cat: Decimal(total or 0) for cat, total in rows.all()}


def _pct_change(now: Decimal, before: Decimal) -> int | None:
    return None if not before else int(round((now - before) * 100 / before))


async def checkin(session: AsyncSession, tenant_id: str, today: date) -> dict[str, Any]:
    """The month so far against the same days last month, with budgets."""
    from life_graph.models.assistant import MoneyBudget
    from life_graph.models.assistant import MoneyTransaction as T

    (start, end), (last_start, last_end) = periods(today)
    now, before = (
        await _spent(session, tenant_id, start, end),
        await _spent(session, tenant_id, last_start, last_end),
    )
    count = (
        await session.execute(
            select(func.count()).where(
                T.tenant_id == tenant_id, T.occurred_on >= start, T.occurred_on < end
            )
        )
    ).scalar_one()
    merchants = (
        await session.execute(
            select(T.merchant, func.sum(T.amount))
            .where(
                T.tenant_id == tenant_id,
                T.occurred_on >= start,
                T.occurred_on < end,
                T.direction == "debit",
                T.category.not_in(_NOT_SPENDING),
                T.merchant.is_not(None),
            )
            .group_by(T.merchant)
            .order_by(func.sum(T.amount).desc())
            .limit(_TOP)
        )
    ).all()
    budgets = {
        b.category: b
        for b in (
            await session.execute(select(MoneyBudget).where(MoneyBudget.tenant_id == tenant_id))
        )
        .scalars()
        .all()
    }

    categories = []
    for cat in sorted(set(now) | set(before), key=lambda c: -now.get(c, Decimal(0))):
        spent, last = now.get(cat, Decimal(0)), before.get(cat, Decimal(0))
        budget = budgets.get(cat)
        pct = int(spent * 100 / budget.monthly_limit) if budget and budget.monthly_limit else None
        categories.append(
            {
                "category": cat,
                "spent": float(spent),
                "last_month": float(last),
                "change": float(spent - last),
                "change_percent": _pct_change(spent, last),
                "budget": float(budget.monthly_limit) if budget else None,
                "percent_of_budget": pct,
            }
        )
    total, last_total = sum(now.values(), Decimal(0)), sum(before.values(), Decimal(0))
    moved = sorted(categories, key=lambda c: -abs(c["change"]))
    return {
        "period": {"start": start.isoformat(), "end": today.isoformat()},
        "compared_with": {
            "start": last_start.isoformat(),
            "end": (last_end - timedelta(days=1)).isoformat(),
        },
        "transactions": int(count),
        "total_spent": float(total),
        "last_month_total": float(last_total),
        "total_change_percent": _pct_change(total, last_total),
        "categories": categories,
        "over_budget": [c["category"] for c in categories if (c["percent_of_budget"] or 0) >= OVER],
        "near_budget": [
            c["category"] for c in categories if NEAR <= (c["percent_of_budget"] or 0) < OVER
        ],
        "biggest_changes": [c["category"] for c in moved if c["change"]][:_TOP],
        "top_merchants": [{"merchant": m, "spent": float(s or 0)} for m, s in merchants],
    }


def _money(x: float) -> str:
    return f"₹{abs(x):,.0f}"


def lines(c: dict[str, Any], *, amounts: bool) -> list[str]:
    """The check-in in a few lines; without *amounts* it is cloud-safe
    (categories and percentages, no sums and no merchants). Nothing spent
    or imported -> []."""
    if not c["transactions"] and not c["last_month_total"]:
        return []
    by = {x["category"]: x for x in c["categories"]}
    out: list[str] = []
    change = c["total_change_percent"]
    trend = (
        "no spending last month to compare with"
        if change is None
        else "the same as the same days last month"
        if change == 0
        else f"{abs(change)}% {'more' if change > 0 else 'less'} than the same days last month"
    )
    head = f"Month to date ({c['period']['start'][8:]}–{c['period']['end'][8:]})"
    out.append(
        f"{head}: spent {_money(c['total_spent'])}, {trend}."
        if amounts
        else f"{head}: spending is {trend}."
    )

    def budget(cat: str) -> str:
        x = by[cat]
        return (
            f"{cat} {x['percent_of_budget']}% ({_money(x['spent'])} of {_money(x['budget'])})"
            if amounts
            else f"{cat} {x['percent_of_budget']}%"
        )

    if c["over_budget"]:
        out.append("Over budget: " + ", ".join(budget(cat) for cat in c["over_budget"]) + ".")
    if c["near_budget"]:
        out.append("Near budget: " + ", ".join(budget(cat) for cat in c["near_budget"]) + ".")

    def moved(cat: str) -> str:
        x = by[cat]
        pct = x["change_percent"]
        what = "new this month" if pct is None else f"{'up' if pct > 0 else 'down'} {abs(pct)}%"
        return f"{cat} {what}" + (
            f" ({'+' if x['change'] > 0 else '−'}{_money(x['change'])})" if amounts else ""
        )

    if c["biggest_changes"]:
        out.append(
            "Biggest changes: " + ", ".join(moved(cat) for cat in c["biggest_changes"]) + "."
        )
    if amounts and c["top_merchants"]:
        out.append(
            "Top merchants: "
            + ", ".join(f"{m['merchant']} {_money(m['spent'])}" for m in c["top_merchants"])
            + "."
        )
    return out
