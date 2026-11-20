"""The owner's authority in a table, so every worker sees the same one.

:class:`~life_graph.autonomy.approvals.capability.CapabilityStore` is correct
and it is in one process's memory. That fails closed over a restart — the
owner re-approves — but two consequences are not acceptable once the approval
queue is real:

* the worker that minted a mandate had to be the worker that executed it, so
  an approval tapped on a phone and resumed by an ARQ worker could not be
  found at all;
* "one use" was one use *per process*. Two workers racing on the same approved
  click each held their own copy of the record, and each would have spent it.

So the record lives in ``capabilities`` (migration 059) and consumption
becomes a single conditional statement:

.. code-block:: sql

    UPDATE capabilities SET consumed_at = :now
     WHERE capability_id = :id AND tenant_id = :tenant
       AND consumed_at IS NULL AND revoked = false AND expires_at > :now
       AND (errand_id IS NULL OR errand_id = :errand_id)
       ...
    RETURNING *

Postgres decides who wins, once, for the whole deployment. The loser gets no
row back and is told :data:`~.capability.ALREADY_CONSUMED` — after a second
read establishes *why* there was no row, so a mismatched selector is not
reported as a replay.

**Synchronous on purpose.** These calls happen inside
``ActionPolicyChecker.evaluate``, which is sync and sits on the hot path of
every action. Reaching for the app's async engine from inside a running loop
would mean ``run_until_complete`` on an already-running loop, so this module
uses its own small ``psycopg2`` pool against ``settings.database_url_sync``.

**Fails closed, in the three different ways that are each right:**

* an insert that cannot reach the database *raises* — an issue that silently
  did not persist would tell the owner their tap worked;
* a read that cannot reach it returns ``None``, which the caller reads as
  :data:`~.capability.UNKNOWN` and denies;
* a consume that cannot reach it returns
  :data:`~.capability.STORE_UNAVAILABLE`, which is a denial and not an
  exception, so one database blip aborts a step rather than a process.

A revoke that cannot reach it also *raises*, like an insert: its return value
says how much was revoked, and "nothing" is not an honest answer for an
outage that left every mandate live.

**Clock skew.** Every expiry and consumption comparison is made against the
database's own ``now()``-free parameter: the caller's ``now`` is passed in and
compared inside the statement, so a worker with a skewed clock cannot widen
an expiry by being wrong — but two workers with different clocks do see the
same row, and the conditional update is still the thing that serialises them.
Issuance bounds the TTL (``MAX_TTL``) before it gets here.

Standing rules get :class:`DurableStandingRuleStore` for the same sharing
reason. A rule is the owner's lasting "always / never", so only
owner-authenticated code may write one; nothing here is reachable from a
payload, and ``request_from_payload`` drops rules that arrive in one.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from life_graph.autonomy.approvals.capability import (
    ALREADY_CONSUMED,
    EXPIRED,
    REVOKED,
    STORE_UNAVAILABLE,
    TENANT_MISMATCH,
    UNKNOWN,
    AuthorizationCapability,
    CapabilityCheck,
)
from life_graph.autonomy.approvals.policy_checker import StandingRule

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

#: Columns a capability row round-trips through, in one place so the INSERT,
#: the SELECT and the consuming UPDATE cannot drift apart.
_COLUMNS = (
    "capability_id",
    "tenant_id",
    "task_id",
    "errand_id",
    "approval_id",
    "step_index",
    "action_types",
    "target_origins",
    "target_selector",
    "parameters_hash",
    "one_use",
    "consumed_at",
    "expires_at",
    "revoked",
    "actor",
    "max_amount",
)

_RETURNING = ", ".join(_COLUMNS)


class StoreUnavailableError(RuntimeError):
    """The durable store could not be written to. Raised by issuance only."""


# ── The engine ───────────────────────────────────────────────────────────

_engine_lock = threading.Lock()
_engine: Engine | None = None


def sync_engine() -> Engine:
    """The process's synchronous engine for authorisation queries.

    Built once, lazily, so importing this module costs nothing and a test that
    never touches the durable path never opens a connection. ``pool_pre_ping``
    because these connections are long-idle between approvals and a stale one
    must not turn into a denial.
    """
    global _engine
    with _engine_lock:
        if _engine is None:
            from sqlalchemy import create_engine

            from life_graph.config import settings, sqlalchemy_sync_url

            # sqlalchemy_sync_url names the psycopg2 driver: on SQLAlchemy
            # 2.1 a bare postgresql:// means psycopg (v3), which is not
            # installed, and every approval would fail closed.
            _engine = create_engine(
                sqlalchemy_sync_url(settings.database_url_sync),
                pool_size=2,
                max_overflow=3,
                pool_pre_ping=True,
                pool_recycle=1800,
                future=True,
            )
        return _engine


def reset_engine() -> None:
    """Drop the engine so the next call rebuilds it. For tests."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None


# ── Rows in, capabilities out ────────────────────────────────────────────


def _utc(value: datetime | None) -> datetime | None:
    """An aware UTC datetime, reading a naive one as UTC (never raising)."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _row_to_capability(row: Mapping[str, Any]) -> AuthorizationCapability:
    """One ``capabilities`` row as the dataclass the checker tests.

    ``target_origins`` keeps the NULL/empty distinction the column comments
    describe: NULL is "any origin", and the store never writes an empty array
    because a capability authorising no origin can never fire.
    """
    origins = row["target_origins"]
    expires_at = _utc(row["expires_at"])
    assert expires_at is not None  # NOT NULL in the schema
    return AuthorizationCapability(
        capability_id=row["capability_id"],
        tenant_id=row["tenant_id"],
        task_id=row["task_id"],
        action_types=frozenset(row["action_types"] or ()),
        target_origins=None if origins is None else frozenset(origins),
        expires_at=expires_at,
        revoked=bool(row["revoked"]),
        max_amount=None if row["max_amount"] is None else float(row["max_amount"]),
        actor=row["actor"],
        errand_id=row["errand_id"],
        approval_id=row["approval_id"],
        step_index=row["step_index"],
        target_selector=row["target_selector"],
        parameters_hash=row["parameters_hash"],
        one_use=bool(row["one_use"]),
        consumed_at=_utc(row["consumed_at"]),
    )


# ── The capability store ─────────────────────────────────────────────────


class DurableCapabilityStore:
    """``capabilities`` as a
    :class:`~life_graph.autonomy.approvals.capability.DurableBackend`.

    Attached to the process-wide
    :data:`~life_graph.autonomy.approvals.capability.capability_store` at
    startup, so every caller that already imports that object becomes durable
    without changing. Holds no state of its own beyond the engine: each method
    is one short transaction, which is what lets two workers agree.
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine

    @property
    def engine(self) -> Engine:
        return self._engine if self._engine is not None else sync_engine()

    # -- issuing ----------------------------------------------------------

    def insert(self, capability: AuthorizationCapability) -> None:
        """Write a minted capability, or raise.

        Raising is the fail-closed answer here and the only place it is: the
        caller is about to hand an id back to the owner's phone as proof their
        tap worked, and an id no worker can resolve is worse than an error.
        """
        origins = capability.target_origins
        params = {
            "capability_id": capability.capability_id,
            "tenant_id": capability.tenant_id,
            "task_id": capability.task_id,
            "errand_id": capability.errand_id,
            "approval_id": capability.approval_id,
            "step_index": capability.step_index,
            "action_types": sorted(capability.action_types),
            "target_origins": None if origins is None else sorted(origins),
            "target_selector": capability.target_selector,
            "parameters_hash": capability.parameters_hash,
            "one_use": capability.one_use,
            "consumed_at": capability.consumed_at,
            "expires_at": capability.expires_at,
            "revoked": capability.revoked,
            "actor": capability.actor,
            "max_amount": capability.max_amount,
        }
        statement = text(
            f"INSERT INTO capabilities ({_RETURNING}) VALUES ("
            + ", ".join(f":{c}" for c in _COLUMNS)
            + ")"
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(statement, params)
        except Exception as exc:
            # No capability id and no detail: the message is logged and the
            # caller turns it into a sentence for the owner.
            logger.error("Durable capability store could not record a mandate: %s", exc)
            raise StoreUnavailableError(
                "the authorization store is unavailable; the approval was not recorded"
            ) from exc

    # -- reading ----------------------------------------------------------

    def select(self, capability_id: str) -> AuthorizationCapability | None:
        """The record with this id, or ``None``.

        ``None`` for both "never issued" and "cannot reach the database". The
        caller reads either as :data:`~.capability.UNKNOWN` and denies, which
        is the same answer, so the two are deliberately not distinguished to
        the caller — only to the log.
        """
        try:
            with self.engine.connect() as conn:
                row = (
                    conn.execute(
                        text(
                            f"SELECT {_RETURNING} FROM capabilities "
                            "WHERE capability_id = :capability_id"
                        ),
                        {"capability_id": capability_id},
                    )
                    .mappings()
                    .first()
                )
        except Exception as exc:
            logger.error("Durable capability store unreachable on read: %s", exc, exc_info=True)
            return None
        return None if row is None else _row_to_capability(row)

    # -- consuming --------------------------------------------------------

    def consume(
        self,
        capability_id: str,
        *,
        tenant_id: str,
        errand_id: str | None = None,
        step_index: int | None = None,
        target_selector: str | None = None,
        parameters_hash: str | None = None,
        now: datetime,
    ) -> tuple[AuthorizationCapability | None, CapabilityCheck]:
        """Spend it, atomically, on this exact action — or say why not.

        One statement does the deciding. The ``WHERE`` clause is every binding
        at once, so there is no window between checking and writing for a
        second worker to fit into, and ``consumed_at IS NULL`` is what makes
        exactly one of two racing workers get a row back.

        ``X IS NULL OR X = :x`` on each binding mirrors
        :meth:`AuthorizationCapability.check_bindings`: a binding the record
        does not carry is not scoped, and one it does carry is compared
        strictly — a caller that passes ``None`` for a bound column does not
        match it.

        When no row comes back, a second read says why, so the denial names
        the real reason (a mismatched selector is not reported as a replay). A
        record that has vanished between the two reads is :data:`UNKNOWN`.
        """
        params = {
            "capability_id": capability_id,
            "tenant_id": tenant_id,
            "errand_id": errand_id,
            "step_index": step_index,
            "target_selector": target_selector,
            "parameters_hash": parameters_hash,
            "now": now,
        }
        statement = text(
            f"UPDATE capabilities SET consumed_at = :now WHERE capability_id = :capability_id "
            "AND tenant_id = :tenant_id "
            "AND consumed_at IS NULL AND revoked = false AND expires_at > :now "
            "AND (errand_id IS NULL OR errand_id = :errand_id) "
            "AND (step_index IS NULL OR step_index = :step_index) "
            "AND (target_selector IS NULL OR target_selector = :target_selector) "
            "AND (parameters_hash IS NULL OR parameters_hash = :parameters_hash) "
            f"RETURNING {_RETURNING}"
        )
        try:
            with self.engine.begin() as conn:
                row = conn.execute(statement, params).mappings().first()
        except Exception as exc:
            logger.error("Durable capability store unreachable on consume: %s", exc, exc_info=True)
            return None, CapabilityCheck(False, STORE_UNAVAILABLE)
        if row is not None:
            return _row_to_capability(row), CapabilityCheck(True, "capability_valid")
        # Nothing was spent. Find out why, so the audit trail is honest about
        # which of the bindings refused rather than blaming the last one.
        existing = self.select(capability_id)
        if existing is None:
            return None, CapabilityCheck(False, UNKNOWN)
        return existing, existing.check_bindings(
            tenant_id=tenant_id,
            errand_id=errand_id,
            step_index=step_index,
            target_selector=target_selector,
            parameters_hash=parameters_hash,
            now=now,
        )

    # -- revoking ---------------------------------------------------------

    def revoke(self, capability_id: str) -> bool:
        """End one capability. True when this call was the one that ended it.

        Conditional on ``revoked = false``, so a double tap on a kill switch
        reports one revocation rather than two.

        Raises :class:`StoreUnavailableError` when the database cannot be
        reached. ``False`` means "it was already revoked", so returning it for
        an outage would tell the owner a live mandate was ended when it was
        not; a revocation that did not happen must be reported.
        """
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text(
                        "UPDATE capabilities SET revoked = true "
                        "WHERE capability_id = :capability_id AND revoked = false"
                    ),
                    {"capability_id": capability_id},
                )
        except Exception as exc:
            logger.error("Durable capability store unreachable on revoke: %s", exc)
            raise StoreUnavailableError(
                "the authorization store is unavailable; nothing was revoked"
            ) from exc
        return bool(result.rowcount)

    def revoke_all(self, *, tenant_id: str, task_id: str | None = None) -> int:
        """Revoke a tenant's live capabilities (optionally one task's).

        Called by the kill switch's pause and by cancelling a dev task
        (autonomy/kill_switch.py ``revoke_live_capabilities``). Tenant-scoped
        in the statement, not in the
        caller: a missing filter here would be a cross-tenant revocation.

        Raises :class:`StoreUnavailableError` when the database cannot be
        reached: ``0`` means "nothing was live", and reporting that for an
        outage would leave every mandate standing behind a kill switch that
        said it had worked.
        """
        clause = "UPDATE capabilities SET revoked = true WHERE tenant_id = :tenant_id "
        clause += "AND revoked = false"
        params: dict[str, Any] = {"tenant_id": tenant_id}
        if task_id is not None:
            clause += " AND task_id = :task_id"
            params["task_id"] = task_id
        try:
            with self.engine.begin() as conn:
                result = conn.execute(text(clause), params)
        except Exception as exc:
            logger.error("Durable capability store unreachable on revoke_all: %s", exc)
            raise StoreUnavailableError(
                "the authorization store is unavailable; nothing was revoked"
            ) from exc
        return int(result.rowcount or 0)

    # -- housekeeping -----------------------------------------------------

    def purge_expired(self, now: datetime) -> int:
        """Delete expired rows. Retention only; never changes a decision.

        An expired capability is already refused by the check and by the
        consuming statement's ``expires_at > :now``, so this is about not
        keeping a record of every approval the owner ever tapped.
        """
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("DELETE FROM capabilities WHERE expires_at <= :now"), {"now": now}
                )
        except Exception as exc:
            logger.error("Durable capability store unreachable on purge: %s", exc, exc_info=True)
            return 0
        return int(result.rowcount or 0)

    def clear(self) -> None:
        """Delete every row. For tests and a deliberate full revocation."""
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM capabilities"))


# ── The standing-rule store ──────────────────────────────────────────────


class DurableStandingRuleStore:
    """``standing_rules`` as a
    :class:`~life_graph.autonomy.approvals.capability.DurableRuleBackend`.

    Writes raise and reads do not. A rule the owner set that was not saved
    must be reported, but a rule set that cannot be read is simply absent —
    and absent rules are default-deny (nothing is pre-authorised, so an action
    falls through to needing the owner), which is the safe reading of an
    outage. The inverse would not be safe, which is why there is no cache.

    The table holds the action, the effect and one origin — the three things
    a rule is matched on. :attr:`StandingRule.note` is audit-only and is not
    stored. :attr:`StandingRule.max_amount` is *refused* rather than dropped:
    a ceiling that did not survive a reload would come back as no ceiling at
    all, which is a widening, and silently widening the owner's rule is
    exactly the failure this whole module exists to prevent. A spend limit
    belongs with the spend controls, not in a match rule.
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine

    @property
    def engine(self) -> Engine:
        return self._engine if self._engine is not None else sync_engine()

    def replace_rules(self, tenant_id: str, rules: Iterable[StandingRule]) -> None:
        """Make *rules* the whole of *tenant_id*'s set, in one transaction.

        Delete-then-insert rather than upsert: the owner's rules screen sends
        the set it wants, and a rule they removed has to actually go. Both
        halves are in one transaction so there is no moment at which the
        tenant has no rules — which would read as default-deny and refuse an
        action the owner had allowed.

        Raises:
            ValueError: if a rule carries a ``max_amount``. See the class
                docstring — the column does not exist, and persisting the
                rule without its ceiling would widen it.
        """
        capped = [r.action_type for r in rules if getattr(r, "max_amount", None) is not None]
        if capped:
            raise ValueError(
                "standing rules with a max_amount cannot be persisted durably "
                f"(would drop the ceiling): {sorted(set(capped))}"
            )
        rows = [
            {
                "tenant_id": tenant_id,
                "action_type": rule.action_type,
                "effect": rule.effect,
                # One origin per row, and NULL for "anywhere". ``_expand`` has
                # already made every rule single-origin, so this reads the one.
                "target_origin": next(iter(rule.origins)) if rule.origins else None,
            }
            for rule in _expand(rules, tenant_id)
        ]
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM standing_rules WHERE tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id},
                )
                if rows:
                    conn.execute(
                        text(
                            "INSERT INTO standing_rules "
                            "(tenant_id, action_type, effect, target_origin) VALUES "
                            "(:tenant_id, :action_type, :effect, :target_origin)"
                        ),
                        rows,
                    )
        except Exception as exc:
            logger.error("Durable standing-rule store could not record rules: %s", exc)
            raise StoreUnavailableError(
                "the authorization store is unavailable; the rules were not saved"
            ) from exc

    def rules_for(self, tenant_id: str) -> tuple[StandingRule, ...]:
        """*tenant_id*'s rules, or ``()`` — which is default-deny."""
        try:
            with self.engine.connect() as conn:
                rows = (
                    conn.execute(
                        text(
                            "SELECT action_type, effect, target_origin FROM standing_rules "
                            "WHERE tenant_id = :tenant_id ORDER BY action_type, target_origin"
                        ),
                        {"tenant_id": tenant_id},
                    )
                    .mappings()
                    .all()
                )
        except Exception as exc:
            logger.error("Durable standing-rule store unreachable on read: %s", exc, exc_info=True)
            return ()
        return tuple(
            StandingRule(
                action_type=row["action_type"],
                effect=row["effect"],
                # An *empty* frozenset is how StandingRule spells "whatever it
                # targets" (see its docstring) — not ``None``, which would
                # happen to behave the same in ``applies_to`` and be the wrong
                # type everywhere else.
                origins=(
                    frozenset()
                    if row["target_origin"] is None
                    else frozenset({row["target_origin"]})
                ),
            )
            for row in rows
        )

    def clear(self, tenant_id: str | None = None) -> None:
        """Forget one tenant's rules, or every tenant's."""
        with self.engine.begin() as conn:
            if tenant_id is None:
                conn.execute(text("DELETE FROM standing_rules"))
            else:
                conn.execute(
                    text("DELETE FROM standing_rules WHERE tenant_id = :tenant_id"),
                    {"tenant_id": tenant_id},
                )


def _expand(rules: Iterable[StandingRule], tenant_id: str) -> list[StandingRule]:
    """One row per (action, origin), since the table holds one origin per row.

    A :class:`StandingRule` may name several origins; the schema's unique
    index is on ``(tenant, action, origin)`` so that "which effect applies"
    never depends on row order. A rule over three origins is therefore three
    rows, and reading them back gives three single-origin rules that match
    exactly what the one rule matched.

    An *empty* ``origins`` is :class:`StandingRule`'s own spelling of "this
    action, whatever it targets" — not "no origins". Reading it the other way
    round produced no rows at all, so the owner's broadest rule was the one
    that silently did not persist.
    """
    out: list[StandingRule] = []
    seen: set[tuple[str, str | None]] = set()
    for rule in rules:
        if not isinstance(rule, StandingRule):
            continue
        origins: tuple[str | None, ...] = (
            (None,) if not rule.origins else tuple(sorted(rule.origins))
        )
        for origin in origins:
            key = (rule.action_type, origin)
            if key in seen:
                # The unique index would reject the duplicate and take the
                # whole transaction with it, losing rules the owner did set.
                logger.warning(
                    "Standing rule for %s on %s given twice for tenant %s; keeping the first",
                    rule.action_type,
                    origin or "any origin",
                    tenant_id,
                )
                continue
            seen.add(key)
            out.append(
                StandingRule(
                    action_type=rule.action_type,
                    effect=rule.effect,
                    origins=frozenset() if origin is None else frozenset({origin}),
                    max_amount=rule.max_amount,
                    note=rule.note,
                )
            )
    return out


# ── Attaching them ───────────────────────────────────────────────────────


def attach_durable_stores(engine: Engine | None = None) -> None:
    """Make the process-wide stores durable. Called once from startup.

    Idempotent, and deliberately not conditional on a successful probe: the
    backends reconnect per operation and each fails closed on its own, so a
    database that is down at boot does not have to mean a process that issues
    in-memory mandates nobody else can see.
    """
    from life_graph.autonomy.approvals.capability import capability_store, standing_rule_store

    capability_store.attach_durable(DurableCapabilityStore(engine))
    standing_rule_store.attach_durable(DurableStandingRuleStore(engine))


def detach_durable_stores() -> None:
    """Put the process-wide stores back in memory. For tests."""
    from life_graph.autonomy.approvals.capability import capability_store, standing_rule_store

    capability_store.attach_durable(None)
    standing_rule_store.attach_durable(None)


__all__ = [
    "ALREADY_CONSUMED",
    "EXPIRED",
    "REVOKED",
    "TENANT_MISMATCH",
    "DurableCapabilityStore",
    "DurableStandingRuleStore",
    "StoreUnavailableError",
    "attach_durable_stores",
    "detach_durable_stores",
    "reset_engine",
    "sync_engine",
]
