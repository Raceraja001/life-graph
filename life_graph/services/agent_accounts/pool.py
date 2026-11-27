"""Pool order, selection and cooldown: pure functions, no database.

Per driver the enabled accounts form an ordered pool (``priority`` ascending,
then creation time, then name). A dispatch takes the first one that is not
cooling down. A run that fails ``rate_limited`` puts its account into
cooldown until the reset time the CLI gave (or a default), and the next
account in the pool is what a retry would use (Phase 3b part 2 re-dispatches;
this module only answers "which next").

Rebuilt from race-app's ``providers/local/fallback`` planner and
AGENT_CONNECTIONS.md §9 (the owner's code): only ``rate_limited`` moves to the
next account; an auth or other failure is the task's own failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

#: A reset further away than this is not believed (a parse of a stray date).
MAX_COOLDOWN = timedelta(days=8)


class PoolAccount(Protocol):
    """What selection reads from an account (the ORM row satisfies it)."""

    id: Any
    name: str
    enabled: bool
    priority: int
    cooldown_until: datetime | None
    created_at: datetime | None


@dataclass(frozen=True)
class Pick:
    """The outcome of a selection.

    ``state``: ``selected`` (``account`` set), ``none`` (no enabled account:
    the driver runs on its default login, as before accounts existed), or
    ``cooling`` (every enabled account is cooling down; ``retry_at`` is the
    earliest end, the time to park a task until).
    """

    state: str
    account: Any = None
    retry_at: datetime | None = None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def is_cooling(account: PoolAccount, now: datetime) -> bool:
    """True while *account*'s cooldown has not ended."""
    until = _aware(account.cooldown_until)
    return until is not None and until > now


def ordered(accounts: list[Any]) -> list[Any]:
    """The pool order: priority, then the older account, then the name."""
    far = datetime.max.replace(tzinfo=UTC)
    return sorted(
        accounts,
        key=lambda a: (a.priority, _aware(a.created_at) or far, a.name),
    )


def pick(accounts: list[Any], now: datetime, *, exclude: set | frozenset = frozenset()) -> Pick:
    """The first enabled account not cooling down and not in *exclude*."""
    pool = [a for a in ordered(accounts) if a.enabled and a.id not in exclude]
    if not pool:
        return Pick("none")
    for account in pool:
        if not is_cooling(account, now):
            return Pick("selected", account=account)
    retry = min(_aware(a.cooldown_until) for a in pool if a.cooldown_until is not None)
    return Pick("cooling", retry_at=retry)


def next_after(accounts: list[Any], current_id: Any, now: datetime) -> Pick:
    """What a retry after *current_id* was rate-limited would run on."""
    return pick(accounts, now, exclude={current_id})


def cooldown_until(
    failure: dict | None, now: datetime, *, default_minutes: int = 15
) -> datetime | None:
    """When a failed run's account may be tried again, or None (not a rate limit).

    The CLI's own ``resets_at`` when it is in the future and believable,
    else *now* + *default_minutes*.
    """
    if not isinstance(failure, dict) or failure.get("kind") != "rate_limited":
        return None
    resets = failure.get("resets_at")
    if isinstance(resets, str) and resets:
        try:
            when = datetime.fromisoformat(resets.replace("Z", "+00:00"))
        except ValueError:
            when = None
        when = _aware(when)
        if when is not None and now < when <= now + MAX_COOLDOWN:
            return when
    return now + timedelta(minutes=max(1, default_minutes))


def reorder(accounts: list[Any], order: list[Any]) -> dict[Any, int]:
    """New priorities for *order* (ids, first = 10, then 20, ...).

    Every id must be one of *accounts* and appear once; accounts not named
    keep their place after the named ones. Raises ValueError otherwise.
    """
    known = {a.id for a in accounts}
    if len(set(order)) != len(order):
        raise ValueError("an account appears twice in the order")
    unknown = [i for i in order if i not in known]
    if unknown:
        raise ValueError(f"unknown account ids: {[str(i) for i in unknown]}")
    rest = [a.id for a in ordered(accounts) if a.id not in set(order)]
    return {account_id: (n + 1) * 10 for n, account_id in enumerate([*order, *rest])}
