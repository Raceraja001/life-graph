"""Subscription budget (risk D4): plan-window share instead of dollars.

A subscription login reports $0 per run, so the Governor's monthly cap never
sees it, and nightly work could use up the owner's interactive quota. With
agent accounts on, an **unattended** run skips a subscription account whose
latest reading of any plan window (``agent_account_limits``, from the runs'
own output or the Codex probe) is at or above
``driver_accounts_subscription_max_share`` of its limit, and falls to the
next account in pool order. When every enabled account is over the share
(or cooling down) the run is refused as ``rate_limited`` with the earliest
window reset as ``resets_at``, which the task can park on.

Pure functions: the hook (drivers/accounts_hook.py) reads the rows.

A reading stops counting once its window has reset (``resets_at`` passed),
or, when it has no reset time, :data:`STALE_AFTER` after it was observed --
an old reading must not hold an account back forever. API-key and Vertex
accounts are billed per use and stay under the Governor's dollar cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

#: A reading without a reset time is believed for this long.
STALE_AFTER = timedelta(hours=5)


@dataclass(frozen=True)
class Reading:
    """The fullest window of one account, as the budget sees it."""

    account_id: Any
    name: str
    window: str
    used_percent: float
    resets_at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "account": self.name,
            "window": self.window,
            "used_percent": round(float(self.used_percent), 1),
            "resets_at": _iso(self.resets_at),
        }


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def live(limit: Any, now: datetime) -> bool:
    """Whether a stored window reading still describes the current window."""
    resets = _aware(getattr(limit, "resets_at", None))
    if resets is not None:
        return resets > now
    observed = _aware(getattr(limit, "observed_at", None))
    return observed is not None and now - observed < STALE_AFTER


def fullest(rows: list[Any], limits: list[Any], now: datetime) -> dict[Any, Reading]:
    """Each subscription account's fullest live window (accounts with none are absent)."""
    names = {r.id: r.name for r in rows if getattr(r, "kind", None) == "subscription"}
    out: dict[Any, Reading] = {}
    for lim in limits:
        if lim.account_id not in names or not live(lim, now):
            continue
        current = out.get(lim.account_id)
        if current is None or float(lim.used_percent) > current.used_percent:
            out[lim.account_id] = Reading(
                lim.account_id,
                names[lim.account_id],
                lim.window,
                float(lim.used_percent),
                _aware(lim.resets_at),
            )
    return out


def over_share(readings: dict[Any, Reading], share: float) -> dict[Any, Reading]:
    """The accounts whose fullest window is at or above *share* (0..1) of its limit."""
    if share >= 1.0:
        return {}
    limit = max(0.0, share) * 100
    return {k: r for k, r in readings.items() if r.used_percent >= limit}


def earliest_reset(over: dict[Any, Reading], now: datetime, default_minutes: int) -> datetime:
    """When the first over-share account's window resets (or now + the default)."""
    resets = [r.resets_at for r in over.values() if r.resets_at is not None]
    if resets:
        return min(resets)
    return now + timedelta(minutes=max(1, default_minutes))


def reason(over: dict[Any, Reading], share: float) -> str:
    """One line naming the accounts skipped and why."""
    parts = [f"{r.name} {r.window} {r.used_percent:.0f}%" for r in over.values()]
    return f"over {share * 100:.0f}% of the plan window: " + ", ".join(parts)
