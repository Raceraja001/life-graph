"""Proof the owner authorised *this* action: an opaque, server-held capability.

``policy_checker`` decides from structure rather than from prose, which stops
a page from arguing its way to a verdict. It does not, on its own, stop a page
from *supplying* the structure. An :class:`~.policy_checker.OwnerRequest` is a
plain dataclass of action types; a run that read a hostile page and then
assembled an action payload could put one there, and the checker would read it
as the owner's mandate — because a structurally valid owner request is not
proof that the owner actually asked.

So authority is not a field any more. It is a record only this server holds:

* :func:`CapabilityStore.issue` is reachable only from trusted,
  owner-authenticated code (the dashboard's approve, a paired phone's
  resolve). It mints a :class:`AuthorizationCapability` bound to a tenant, an
  optional task, the action types allowed, the origins allowed, an expiry and
  an optional amount ceiling, and returns it.
* What travels afterwards is the ``capability_id`` alone — an opaque
  ``secrets``-grade string that means nothing anywhere else. A model or a page
  can put whatever it likes in that field; an id the store never issued does
  not resolve, and the action is denied.
* :meth:`CapabilityStore.verify` re-checks every binding at the point of
  execution, so a mandate cannot be widened after the fact: a later model
  response asking for ``transfer_money`` against a capability issued for
  ``browser_navigate`` is refused by the capability, not by a judgement about
  the response.
* :meth:`CapabilityStore.revoke` ends one immediately, and every check is
  recomputed from the record each time, so revocation takes effect on the next
  action rather than at the next restart.

Standing rules get the same treatment for the same reason
(:class:`StandingRuleStore`): they are the owner's lasting "always / never",
so they are loaded per tenant from a store trusted code writes, and
:func:`~.policy_checker.request_from_payload` drops any that arrive in a
payload.

Deliberately in-process and non-durable, like the checker it serves: a
capability is short-lived by design, and a restart that forgets every
outstanding mandate fails closed. Durable issuance, when the approval queue
needs it, belongs in a table — see the note on :class:`CapabilityStore`.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from life_graph.autonomy.approvals.policy_checker import StandingRule

if TYPE_CHECKING:
    from collections.abc import Iterable

#: How long an issued capability lives when the caller does not say. Short on
#: purpose: a mandate is for the action the owner just authorised, not a
#: standing permission, and a forgotten one should expire rather than linger.
DEFAULT_TTL = timedelta(minutes=15)

#: Longest life any capability may be issued for, whatever the caller asks.
MAX_TTL = timedelta(hours=24)

# ── Why a capability did or did not authorise an action ──────────────────

VALID = "capability_valid"
UNKNOWN = "capability_unknown"
EXPIRED = "capability_expired"
REVOKED = "capability_revoked"
TENANT_MISMATCH = "capability_tenant_mismatch"
TASK_MISMATCH = "capability_task_mismatch"
ACTION_NOT_AUTHORIZED = "capability_action_not_authorized"
ORIGIN_NOT_AUTHORIZED = "capability_origin_not_authorized"
AMOUNT_OVER_CAPABILITY = "capability_amount_exceeded"

#: Every reason a capability check can give. The failures are all denials:
#: there is no "probably fine" for a credential.
CHECK_REASONS = (
    VALID,
    UNKNOWN,
    EXPIRED,
    REVOKED,
    TENANT_MISMATCH,
    TASK_MISMATCH,
    ACTION_NOT_AUTHORIZED,
    ORIGIN_NOT_AUTHORIZED,
    AMOUNT_OVER_CAPABILITY,
)


@dataclass(frozen=True, slots=True)
class CapabilityCheck:
    """The outcome of verifying a capability: valid, or why not."""

    ok: bool
    reason: str

    def __bool__(self) -> bool:
        return self.ok


_VALID_CHECK = CapabilityCheck(True, VALID)


# ── The capability ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AuthorizationCapability:
    """One mandate the owner issued, as the server recorded it.

    Every field is a binding that :meth:`check` re-tests at execution time.
    ``target_origins`` of ``None`` means "wherever" — the owner authorised the
    action itself rather than the action against one site; an empty frozenset
    means no origin is authorised, which is a capability that can never fire
    and is therefore never issued by :meth:`CapabilityStore.issue`.

    ``actor`` is how the server recognised the owner when it issued this
    (``device:<id>``, ``owner:api_key``), matching
    :class:`~life_graph.core.trust.Ingress.actor`, so an audit trail names a
    credential and not the bare word "owner".
    """

    capability_id: str
    tenant_id: str
    task_id: str | None
    action_types: frozenset[str]
    target_origins: frozenset[str] | None
    expires_at: datetime
    revoked: bool = False
    max_amount: float | None = None
    actor: str = "owner"

    def is_expired(self, now: datetime | None = None) -> bool:
        """True once :attr:`expires_at` has passed."""
        return _utc(now or datetime.now(UTC)) >= _utc(self.expires_at)

    def authorizes(self, action_type: str, target_origin: str | None = None) -> bool:
        """True when this mandate covers *action_type* against *target_origin*.

        Scope only — says nothing about expiry, revocation or tenant. Use
        :meth:`check` to decide whether an action may run.
        """
        if (action_type or "").strip() not in self.action_types:
            return False
        if self.target_origins is None:
            return True
        return (target_origin or "").strip().lower() in self.target_origins

    def check(
        self,
        *,
        tenant_id: str,
        action_type: str,
        target_origin: str | None = None,
        task_id: str | None = None,
        amount: float | None = None,
        now: datetime | None = None,
    ) -> CapabilityCheck:
        """Verify every binding. Fails closed, and says which binding failed.

        Order is deliberate: the reasons that are true of the capability
        itself (revoked, expired, wrong tenant) come before the ones about the
        action being attempted, so an audit trail of refusals reads as "this
        credential is no good" rather than "this action was not covered".
        """
        if self.revoked:
            return CapabilityCheck(False, REVOKED)
        if self.is_expired(now):
            return CapabilityCheck(False, EXPIRED)
        if self.tenant_id != tenant_id:
            return CapabilityCheck(False, TENANT_MISMATCH)
        if self.task_id is not None and task_id != self.task_id:
            # Issued for one task: another task presenting it is either a
            # mistake or a lifted credential, and neither may run.
            return CapabilityCheck(False, TASK_MISMATCH)
        if (action_type or "").strip() not in self.action_types:
            return CapabilityCheck(False, ACTION_NOT_AUTHORIZED)
        if self.target_origins is not None and (
            (target_origin or "").strip().lower() not in self.target_origins
        ):
            return CapabilityCheck(False, ORIGIN_NOT_AUTHORIZED)
        if self.max_amount is not None and amount is not None and amount > self.max_amount:
            return CapabilityCheck(False, AMOUNT_OVER_CAPABILITY)
        return _VALID_CHECK


def _utc(value: datetime) -> datetime:
    """*value* as an aware UTC datetime — a naive one is read as UTC.

    An expiry that silently compared naive to aware would raise at the worst
    possible moment, inside the check that decides whether money moves.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _origins(values: Iterable[str] | None) -> frozenset[str] | None:
    if values is None:
        return None
    return frozenset((str(v) or "").strip().lower() for v in values if str(v).strip())


# ── The store ────────────────────────────────────────────────────────────


class CapabilityStore:
    """Issues, resolves and revokes capabilities. The server's side of the pair.

    In-process and lock-guarded. Two consequences worth stating rather than
    discovering: a capability does not survive a restart (fail closed — the
    owner re-authorises), and it is not shared between workers, so the
    issuing process must be the executing one. A durable version is a
    tenant-scoped table with the same five checks in its query; nothing in
    :class:`~.policy_checker.ActionPolicyChecker` depends on which it is,
    because it only ever calls :meth:`verify`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._issued: dict[str, AuthorizationCapability] = {}

    # -- issuing (trusted callers only) -----------------------------------

    def issue(
        self,
        *,
        tenant_id: str,
        action_types: Iterable[str],
        target_origins: Iterable[str] | None = None,
        task_id: str | None = None,
        ttl: timedelta | None = None,
        max_amount: float | None = None,
        actor: str = "owner",
        now: datetime | None = None,
    ) -> AuthorizationCapability:
        """Mint a capability. Call this only from owner-authenticated code.

        There is no way to arrive here from a request payload:
        :func:`~.policy_checker.request_from_payload` does not construct
        capabilities, and the id this returns is the only thing that resolves.

        Raises:
            ValueError: if *tenant_id* or *action_types* is empty, or
                *target_origins* is given but empty — a capability that
                authorises nothing is a bug at the call site, not a safe
                default to hand back.
        """
        tenant = (tenant_id or "").strip()
        if not tenant:
            raise ValueError("a capability must be bound to a tenant")
        actions = frozenset(str(a).strip() for a in action_types if str(a).strip())
        if not actions:
            raise ValueError("a capability must authorise at least one action type")
        origins = _origins(target_origins)
        if origins is not None and not origins:
            raise ValueError("target_origins is empty: use None for 'any origin'")

        # Not ``ttl or DEFAULT_TTL``: ``timedelta(0)`` is falsy, so a caller
        # asking for a capability that is already expired would have been
        # handed the default fifteen minutes instead of the ValueError below.
        span = min(DEFAULT_TTL if ttl is None else ttl, MAX_TTL)
        if span <= timedelta(0):
            raise ValueError("a capability must expire in the future")
        capability = AuthorizationCapability(
            capability_id=f"cap_{secrets.token_urlsafe(24)}",
            tenant_id=tenant,
            task_id=task_id,
            action_types=actions,
            target_origins=origins,
            expires_at=_utc(now or datetime.now(UTC)) + span,
            max_amount=_as_amount(max_amount),
            actor=actor,
        )
        with self._lock:
            self._issued[capability.capability_id] = capability
        return capability

    # -- resolving and verifying ------------------------------------------

    def get(self, capability_id: str | None) -> AuthorizationCapability | None:
        """The capability with this id, or ``None`` if this server never issued it."""
        if not capability_id:
            return None
        with self._lock:
            return self._issued.get(str(capability_id))

    def verify(
        self,
        capability_id: str | None,
        *,
        tenant_id: str,
        action_type: str,
        target_origin: str | None = None,
        task_id: str | None = None,
        amount: float | None = None,
        now: datetime | None = None,
    ) -> tuple[AuthorizationCapability | None, CapabilityCheck]:
        """``(the capability, the verdict)`` for an id presented with an action.

        An id this server did not issue — a forgery, a stale one, a string a
        model invented — resolves to ``None`` and :data:`UNKNOWN`. That is the
        property the whole model rests on: the attacker can write the field,
        and writing it buys nothing.
        """
        capability = self.get(capability_id)
        if capability is None:
            return None, CapabilityCheck(False, UNKNOWN)
        return capability, capability.check(
            tenant_id=tenant_id,
            action_type=action_type,
            target_origin=target_origin,
            task_id=task_id,
            amount=amount,
            now=now,
        )

    # -- revoking ---------------------------------------------------------

    def revoke(self, capability_id: str | None) -> bool:
        """End one capability. True if it existed and was not already revoked."""
        if not capability_id:
            return False
        with self._lock:
            existing = self._issued.get(str(capability_id))
            if existing is None or existing.revoked:
                return False
            self._issued[existing.capability_id] = replace(existing, revoked=True)
        return True

    def revoke_all(self, *, tenant_id: str, task_id: str | None = None) -> int:
        """Revoke a tenant's capabilities (optionally one task's). Returns the count.

        What the kill switch and "stop this task" call: a task that is being
        abandoned should not leave a live mandate behind it.
        """
        count = 0
        with self._lock:
            for key, cap in list(self._issued.items()):
                if cap.revoked or cap.tenant_id != tenant_id:
                    continue
                if task_id is not None and cap.task_id != task_id:
                    continue
                self._issued[key] = replace(cap, revoked=True)
                count += 1
        return count

    # -- housekeeping -----------------------------------------------------

    def purge_expired(self, now: datetime | None = None) -> int:
        """Drop expired records. Returns the count.

        Housekeeping only — an expired capability is already refused by
        :meth:`AuthorizationCapability.check`, so this frees memory and never
        changes a decision.
        """
        when = _utc(now or datetime.now(UTC))
        with self._lock:
            gone = [k for k, c in self._issued.items() if c.is_expired(when)]
            for key in gone:
                del self._issued[key]
        return len(gone)

    def clear(self) -> None:
        """Forget everything. For tests and for a deliberate full revocation."""
        with self._lock:
            self._issued.clear()


def _as_amount(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


#: The process-wide store. Trusted code issues against this one; the checker
#: verifies against whichever store it was built with, so a test can pass its
#: own without reaching for module state.
capability_store = CapabilityStore()


# ── Standing rules: the owner's configuration, per tenant ────────────────


@dataclass
class StandingRuleStore:
    """The owner's lasting rules, per tenant, from somewhere trusted.

    The rules are the owner's "always / never", so where they come from is the
    whole question. They are set here by trusted code — tenant configuration,
    the dashboard's rules screen — and read back per tenant;
    :func:`~.policy_checker.request_from_payload` drops any that arrive in a
    request payload, so an agent or a page cannot add an ALLOW to the set that
    judges it.
    """

    _rules: dict[str, tuple[StandingRule, ...]] = field(default_factory=dict)

    def set_rules(self, tenant_id: str, rules: Iterable[StandingRule]) -> None:
        """Replace *tenant_id*'s rules. Trusted callers only."""
        tenant = (tenant_id or "").strip()
        if not tenant:
            raise ValueError("standing rules must be tenant-scoped")
        kept = tuple(r for r in rules if isinstance(r, StandingRule))
        self._rules[tenant] = kept

    def rules_for(self, tenant_id: str | None) -> tuple[StandingRule, ...]:
        """*tenant_id*'s rules, or none at all for an unknown tenant.

        Default-deny in the sense that matters here: no rules means nothing is
        pre-authorised, so an action falls through to needing the owner.
        """
        return self._rules.get((tenant_id or "").strip(), ())

    def clear(self, tenant_id: str | None = None) -> None:
        """Forget one tenant's rules, or every tenant's."""
        if tenant_id is None:
            self._rules.clear()
        else:
            self._rules.pop((tenant_id or "").strip(), None)


#: The process-wide rule store, mirroring :data:`capability_store`.
standing_rule_store = StandingRuleStore()


def rules_from_config(tenant_id: str | None) -> tuple[StandingRule, ...]:
    """A tenant's standing rules from the trusted store.

    The single place :class:`~.policy_checker.ActionPolicyChecker` callers
    should get rules from, so "never from a payload" has one answer.
    """
    return standing_rule_store.rules_for(tenant_id)


__all__ = [
    "ACTION_NOT_AUTHORIZED",
    "AMOUNT_OVER_CAPABILITY",
    "CHECK_REASONS",
    "DEFAULT_TTL",
    "EXPIRED",
    "MAX_TTL",
    "ORIGIN_NOT_AUTHORIZED",
    "REVOKED",
    "TASK_MISMATCH",
    "TENANT_MISMATCH",
    "UNKNOWN",
    "VALID",
    "AuthorizationCapability",
    "CapabilityCheck",
    "CapabilityStore",
    "StandingRuleStore",
    "capability_store",
    "rules_from_config",
    "standing_rule_store",
]
