"""The Governor — unified budget kernel over all autonomous spenders.

A spender calls :meth:`Governor.authorize` before spending and
:meth:`Governor.record` after. Authorization is refused or throttled once the
monthly budget is exhausted; interactive (user-initiated) requests are never
blocked. The decision logic itself lives in ``core/budget.py``; this service
adds month-to-date persistence and fail-open safety.

See docs/superpowers/specs/2026-07-15-governor-budget-kernel-design.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from life_graph.config import settings
from life_graph.core.budget import BudgetCategory, BudgetDecision, decide, priority_for
from life_graph.models.db import BudgetSpend
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


def _current_month() -> date:
    """First day of the current UTC month."""
    today = datetime.now(UTC).date()
    return today.replace(day=1)


@dataclass
class BudgetStatus:
    """A snapshot of the current month's budget, for briefs/dashboards."""

    spent_usd: float
    cap_usd: float
    remaining_usd: float
    by_category: dict[str, float] = field(default_factory=dict)


class Governor:
    """Budget authority. Stateless per call — opens its own session."""

    async def authorize(
        self,
        tenant_id: str,
        category: BudgetCategory,
        estimated_usd: float = 0.0,
        *,
        interactive: bool = False,
    ) -> BudgetDecision:
        """Decide whether a spend may proceed, pre-emptively.

        Evaluates *projected* spend (month-to-date + this estimate) against the
        monthly cap, so a spend that would cross the cap is caught before the
        money is committed. Fails open (allowed) with a loud log if the check
        itself errors — a storage hiccup must not freeze all autonomous work.
        """
        cap = settings.monthly_budget_usd
        soft = settings.budget_soft_threshold
        try:
            spent = await self._month_to_date(tenant_id)
        except Exception:
            logger.error(
                "Governor authorize failed for tenant=%s category=%s — failing OPEN. "
                "Budget enforcement is degraded; investigate.",
                tenant_id, category, exc_info=True,
            )
            return BudgetDecision(
                allowed=True, throttled=False,
                reason="governor unavailable — failed open",
                spent_usd=0.0, cap_usd=cap, remaining_usd=cap,
            )

        projected = spent + max(0.0, estimated_usd)
        return decide(
            projected, cap, priority_for(category),
            interactive=interactive, soft_threshold=soft,
        )

    async def record(
        self, tenant_id: str, category: BudgetCategory, actual_usd: float
    ) -> None:
        """Book an actual spend into this month's ledger (upsert + increment)."""
        if actual_usd <= 0:
            return
        month = _current_month()
        cat = category.value if isinstance(category, BudgetCategory) else str(category)
        try:
            async with async_session() as session:
                stmt = pg_insert(BudgetSpend).values(
                    tenant_id=tenant_id,
                    period_month=month,
                    category=cat,
                    spent_usd=actual_usd,
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_budget_spend_key",
                    set_={
                        "spent_usd": BudgetSpend.spent_usd + actual_usd,
                        "updated_at": datetime.now(UTC),
                    },
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:
            logger.error(
                "Governor failed to record $%.6f for tenant=%s category=%s",
                actual_usd, tenant_id, cat, exc_info=True,
            )

    async def status(self, tenant_id: str) -> BudgetStatus:
        """Month-to-date budget snapshot with a per-category breakdown."""
        cap = settings.monthly_budget_usd
        month = _current_month()
        async with async_session() as session:
            result = await session.execute(
                select(BudgetSpend.category, BudgetSpend.spent_usd).where(
                    BudgetSpend.tenant_id == tenant_id,
                    BudgetSpend.period_month == month,
                )
            )
            by_category = {row[0]: float(row[1]) for row in result.all()}
        spent = sum(by_category.values())
        return BudgetStatus(
            spent_usd=spent,
            cap_usd=cap,
            remaining_usd=max(0.0, cap - spent),
            by_category=by_category,
        )

    async def _month_to_date(self, tenant_id: str) -> float:
        """Sum of all category spend for the tenant this month."""
        month = _current_month()
        async with async_session() as session:
            result = await session.execute(
                select(func.coalesce(func.sum(BudgetSpend.spent_usd), 0)).where(
                    BudgetSpend.tenant_id == tenant_id,
                    BudgetSpend.period_month == month,
                )
            )
            return float(result.scalar_one())


# ── Module-level singleton ─────────────────────────────────────────────
governor = Governor()
