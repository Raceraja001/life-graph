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
from typing import TYPE_CHECKING, Protocol

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

# The exact-action bindings. A capability is proof the owner approved *one*
# action, so each of these is a way the action being attempted is not that
# one — a replay, a re-numbered step, a swapped button, an edited value.
ALREADY_CONSUMED = "capability_already_consumed"
ERRAND_MISMATCH = "capability_errand_mismatch"
STEP_MISMATCH = "capability_step_mismatch"
SELECTOR_MISMATCH = "capability_selector_mismatch"
PARAMETERS_MISMATCH = "capability_parameters_mismatch"

#: The durable store could not be reached. A denial, not an error: an
#: authorisation decision that cannot be made is not an authorisation.
STORE_UNAVAILABLE = "capability_store_unavailable"

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
    ALREADY_CONSUMED,
    ERRAND_MISMATCH,
    STEP_MISMATCH,
    SELECTOR_MISMATCH,
    PARAMETERS_MISMATCH,
    STORE_UNAVAILABLE,
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
    #: The errand run this was approved inside, if any. A capability minted
    #: for errand A does not authorise the identical-looking step of errand B:
    #: the owner saw one run's plan, not every run that could ask the same.
    errand_id: str | None = None
    #: The notification the owner actually tapped. Recorded so an audit trail
    #: can name the card, and so one card cannot mint twice.
    approval_id: str | None = None
    #: The position in that errand's step list. A plan whose steps were
    #: re-ordered after approval is not the plan that was approved.
    step_index: int | None = None
    #: The element the owner was shown — the stable selector, not the label.
    target_selector: str | None = None
    #: SHA-256 over the canonicalised parameters of the one action approved
    #: (see ``services.browser_errand.canonical_parameters_hash``). An edited
    #: form value changes the digest, so the approval no longer covers it.
    parameters_hash: str | None = None
    #: Spent by its first successful use. The default, because the actions
    #: these gate are outward and irreversible.
    one_use: bool = True
    #: When it was spent. ``None`` until :meth:`CapabilityStore.consume`
    #: succeeds, and only that method ever sets it.
    consumed_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        """True once :attr:`expires_at` has passed."""
        return _utc(now or datetime.now(UTC)) >= _utc(self.expires_at)

    @property
    def is_consumed(self) -> bool:
        """True once a one-use capability has been spent."""
        return self.one_use and self.consumed_at is not None

    def check_bindings(
        self,
        *,
        tenant_id: str,
        errand_id: str | None = None,
        step_index: int | None = None,
        target_selector: str | None = None,
        parameters_hash: str | None = None,
        now: datetime | None = None,
    ) -> CapabilityCheck:
        """The bindings that identify *one exact action*, re-tested.

        Separate from :meth:`check` because consumption has no action type or
        origin to test — those were settled by the policy before anything got
        this far — and because the ordering matters: a capability that is
        revoked, expired or already spent is refused as a credential before
        anything is said about which action was attempted.

        A binding the capability does not carry is not tested. ``None`` on the
        record means "not scoped to one of these", which is how a mandate for
        a non-errand action (a transfer the owner authorised directly) is
        still usable. A binding the record *does* carry is compared strictly,
        so a caller that fails to assert it is refused rather than waved
        through: ``None != "errand_x"``.
        """
        if self.revoked:
            return CapabilityCheck(False, REVOKED)
        if self.is_expired(now):
            return CapabilityCheck(False, EXPIRED)
        if self.tenant_id != tenant_id:
            return CapabilityCheck(False, TENANT_MISMATCH)
        if self.is_consumed:
            return CapabilityCheck(False, ALREADY_CONSUMED)
        if self.errand_id is not None and errand_id != self.errand_id:
            return CapabilityCheck(False, ERRAND_MISMATCH)
        if self.step_index is not None and step_index != self.step_index:
            return CapabilityCheck(False, STEP_MISMATCH)
        if self.target_selector is not None and target_selector != self.target_selector:
            return CapabilityCheck(False, SELECTOR_MISMATCH)
        if self.parameters_hash is not None and parameters_hash != self.parameters_hash:
            return CapabilityCheck(False, PARAMETERS_MISMATCH)
        return _VALID_CHECK

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
        errand_id: str | None = None,
        step_index: int | None = None,
        target_selector: str | None = None,
        parameters_hash: str | None = None,
        read_only: bool = False,
        now: datetime | None = None,
    ) -> CapabilityCheck:
        """Verify every binding. Fails closed, and says which binding failed.

        Order is deliberate: the reasons that are true of the capability
        itself (revoked, expired, wrong tenant) come before the ones about the
        action being attempted, so an audit trail of refusals reads as "this
        credential is no good" rather than "this action was not covered".

        *read_only* says the action being judged changes nothing and reaches
        no one — a navigate, a page read. Those need no mandate at all, so the
        exact-action bindings (step, selector, parameters, consumption) are not
        tested for them: an errand that spent its capability on the click it
        was approved for must still be able to read the page that came back,
        and a resumed errand must be able to navigate to the step it paused
        on. What is still tested is that the credential itself is good and is
        this tenant's — a handle refused for the origin refuses the whole
        errand, including its first navigate.
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
        if not read_only:
            bindings = self.check_bindings(
                tenant_id=tenant_id,
                errand_id=errand_id,
                step_index=step_index,
                target_selector=target_selector,
                parameters_hash=parameters_hash,
                now=now,
            )
            if not bindings.ok:
                return bindings
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


# ── What a durable backend has to be able to do ──────────────────────────


class DurableBackend(Protocol):
    """A table :class:`CapabilityStore` writes through to.

    Narrow on purpose, and in terms of whole records rather than SQL, so the
    in-process store stays the reference implementation of the semantics and
    the durable one (``approvals/durable_store.py``) only has to be the same
    semantics in a transaction. Every method is synchronous: the calls happen
    inside :meth:`ActionPolicyChecker.evaluate`, which is sync and is on the
    hot path of every action, so an implementation uses a sync driver rather
    than reaching for the app's async engine from inside a running loop.

    Every method fails closed. A read that cannot reach the database returns
    ``None`` (which the caller reads as :data:`UNKNOWN`), a consume returns
    :data:`STORE_UNAVAILABLE`, and an insert raises — because an issue that
    silently did not persist would tell the owner their tap worked. A revoke
    raises too, for the same reason in reverse: "nothing to revoke" for an
    outage would tell the owner a mandate was ended when it was still live.
    """

    def insert(self, capability: AuthorizationCapability) -> None:
        """Write a newly minted capability. Raises if it cannot."""
        ...

    def select(self, capability_id: str) -> AuthorizationCapability | None:
        """The record with this id, or ``None`` (unknown *or* unreachable)."""
        ...

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
        """Spend it in one atomic conditional update, or say why not."""
        ...

    def revoke(self, capability_id: str) -> bool:
        """End one capability. True if this call was the one that ended it.

        Raises when the store cannot be reached; never ``False`` for an outage.
        """
        ...

    def revoke_all(self, *, tenant_id: str, task_id: str | None = None) -> int:
        """Revoke a tenant's (optionally one task's) live capabilities.

        Raises when the store cannot be reached; never ``0`` for an outage.
        """
        ...

    def purge_expired(self, now: datetime) -> int:
        """Delete expired rows. Housekeeping; never changes a decision."""
        ...

    def clear(self) -> None:
        """Delete every row. For tests and deliberate full revocation."""
        ...


class DurableRuleBackend(Protocol):
    """The same arrangement for standing rules (:class:`StandingRuleStore`)."""

    def replace_rules(self, tenant_id: str, rules: tuple[StandingRule, ...]) -> None:
        """Make *rules* the whole of *tenant_id*'s set. Raises if it cannot."""
        ...

    def rules_for(self, tenant_id: str) -> tuple[StandingRule, ...]:
        """*tenant_id*'s rules. ``()`` when unreachable — which is default-deny."""
        ...

    def clear(self, tenant_id: str | None = None) -> None:
        """Forget one tenant's rules, or every tenant's."""
        ...


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

    def __init__(self, durable: DurableBackend | None = None) -> None:
        self._lock = threading.Lock()
        self._issued: dict[str, AuthorizationCapability] = {}
        self._durable: DurableBackend | None = durable

    # -- the durable backend ----------------------------------------------

    @property
    def durable(self) -> DurableBackend | None:
        """The table this store writes through to, or ``None`` for in-process."""
        return self._durable

    def attach_durable(self, backend: DurableBackend | None) -> None:
        """Route every operation through *backend* (or back to memory with ``None``).

        Called once from the app's startup (``main.py``) so that the
        process-wide :data:`capability_store` every caller already imports
        becomes the durable one without any of them changing. Tests attach
        their own, or none.
        """
        with self._lock:
            self._durable = backend

    # -- issuing (trusted callers only) -----------------------------------

    def issue(
        self,
        *,
        tenant_id: str,
        action_types: Iterable[str],
        target_origins: Iterable[str] | None = None,
        task_id: str | None = None,
        errand_id: str | None = None,
        approval_id: str | None = None,
        step_index: int | None = None,
        target_selector: str | None = None,
        parameters_hash: str | None = None,
        one_use: bool = True,
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
            errand_id=_binding(errand_id),
            approval_id=_binding(approval_id),
            step_index=_step(step_index),
            target_selector=_binding(target_selector, limit=255),
            parameters_hash=_binding(parameters_hash, limit=64),
            one_use=bool(one_use),
        )
        backend = self._durable
        if backend is not None:
            # Fails closed by raising: a mandate that was not written down is
            # not a mandate, and handing back an id that no worker can resolve
            # would look like success to the owner.
            backend.insert(capability)
            return capability
        with self._lock:
            self._issued[capability.capability_id] = capability
        return capability

    # -- resolving and verifying ------------------------------------------

    def get(self, capability_id: str | None) -> AuthorizationCapability | None:
        """The capability with this id, or ``None`` if this server never issued it."""
        if not capability_id:
            return None
        backend = self._durable
        if backend is not None:
            return backend.select(str(capability_id))
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
        errand_id: str | None = None,
        step_index: int | None = None,
        target_selector: str | None = None,
        parameters_hash: str | None = None,
        read_only: bool = False,
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
            errand_id=errand_id,
            step_index=step_index,
            target_selector=target_selector,
            parameters_hash=parameters_hash,
            read_only=read_only,
            now=now,
        )

    # -- consuming (one use, once, by one caller) --------------------------

    def consume(
        self,
        capability_id: str | None,
        *,
        tenant_id: str,
        errand_id: str | None = None,
        step_index: int | None = None,
        target_selector: str | None = None,
        parameters_hash: str | None = None,
        now: datetime | None = None,
    ) -> tuple[AuthorizationCapability | None, CapabilityCheck]:
        """Spend the capability on *this exact action*, or refuse it.

        ``(the capability as it now is, the verdict)``. The check and the
        write are one step — under the lock here, a single conditional
        ``UPDATE`` in the durable backend — so two workers racing to perform
        the same approved click cannot both win. Exactly one gets
        :data:`VALID`; the other gets :data:`ALREADY_CONSUMED`, and the second
        of the two is told which capability it lost so an audit trail can say
        what was replayed.

        A refusal leaves the record untouched: a mismatched selector does not
        burn the owner's approval, so the real step can still run.

        No action type or origin here on purpose. Those are the policy's
        question and were answered before execution began
        (``policy_checker.ActionPolicyChecker.evaluate``); this is the
        narrower one of whether *this* run, at *this* step, with *these*
        parameters, is the thing the owner tapped.
        """
        if not capability_id:
            return None, CapabilityCheck(False, UNKNOWN)
        when = _utc(now or datetime.now(UTC))
        backend = self._durable
        if backend is not None:
            return backend.consume(
                str(capability_id),
                tenant_id=tenant_id,
                errand_id=errand_id,
                step_index=step_index,
                target_selector=target_selector,
                parameters_hash=parameters_hash,
                now=when,
            )
        with self._lock:
            existing = self._issued.get(str(capability_id))
            if existing is None:
                return None, CapabilityCheck(False, UNKNOWN)
            check = existing.check_bindings(
                tenant_id=tenant_id,
                errand_id=errand_id,
                step_index=step_index,
                target_selector=target_selector,
                parameters_hash=parameters_hash,
                now=when,
            )
            if not check.ok:
                return existing, check
            if not existing.one_use:
                # Re-usable within its expiry: nothing to spend, so nothing is
                # written and a concurrent caller is not blocked.
                return existing, check
            spent = replace(existing, consumed_at=when)
            self._issued[spent.capability_id] = spent
        return spent, check

    # -- revoking ---------------------------------------------------------

    def revoke(self, capability_id: str | None) -> bool:
        """End one capability. True if it existed and was not already revoked."""
        if not capability_id:
            return False
        backend = self._durable
        if backend is not None:
            return backend.revoke(str(capability_id))
        with self._lock:
            existing = self._issued.get(str(capability_id))
            if existing is None or existing.revoked:
                return False
            self._issued[existing.capability_id] = replace(existing, revoked=True)
        return True

    def revoke_all(self, *, tenant_id: str, task_id: str | None = None) -> int:
        """Revoke a tenant's capabilities (optionally one task's). Returns the count.

        Meant for the kill switch and "stop this task" — a task that is being
        abandoned should not leave a live mandate behind it — but neither
        calls it yet: pausing autonomy (autonomy/kill_switch.py) does not
        revoke capabilities today. With a durable backend, an unreachable
        database raises ``StoreUnavailableError`` rather than returning 0.
        """
        backend = self._durable
        if backend is not None:
            return backend.revoke_all(tenant_id=tenant_id, task_id=task_id)
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
        backend = self._durable
        if backend is not None:
            return backend.purge_expired(when)
        with self._lock:
            gone = [k for k, c in self._issued.items() if c.is_expired(when)]
            for key in gone:
                del self._issued[key]
        return len(gone)

    def clear(self) -> None:
        """Forget everything. For tests and for a deliberate full revocation."""
        backend = self._durable
        if backend is not None:
            backend.clear()
        with self._lock:
            self._issued.clear()


def _binding(value: object, limit: int = 120) -> str | None:
    """A bound identifier, trimmed and bounded, or ``None`` for "not scoped".

    Empty string becomes ``None`` deliberately: a caller passing ``""`` has no
    binding to assert, and storing it would make every later comparison
    against a real value a mismatch for no reason.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _step(value: object) -> int | None:
    """A step index, or ``None``. A non-integer is no binding, not step zero."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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
    _durable: DurableRuleBackend | None = None

    def attach_durable(self, backend: DurableRuleBackend | None) -> None:
        """Route reads and writes through *backend*, mirroring the capability store."""
        self._durable = backend

    def set_rules(self, tenant_id: str, rules: Iterable[StandingRule]) -> None:
        """Replace *tenant_id*'s rules. Trusted callers only."""
        tenant = (tenant_id or "").strip()
        if not tenant:
            raise ValueError("standing rules must be tenant-scoped")
        kept = tuple(r for r in rules if isinstance(r, StandingRule))
        if self._durable is not None:
            self._durable.replace_rules(tenant, kept)
            return
        self._rules[tenant] = kept

    def rules_for(self, tenant_id: str | None) -> tuple[StandingRule, ...]:
        """*tenant_id*'s rules, or none at all for an unknown tenant.

        Default-deny in the sense that matters here: no rules means nothing is
        pre-authorised, so an action falls through to needing the owner. That
        is also what a database outage gives, which is why the durable
        backend is allowed to answer ``()`` rather than raise.
        """
        tenant = (tenant_id or "").strip()
        if self._durable is not None:
            return self._durable.rules_for(tenant)
        return self._rules.get(tenant, ())

    def clear(self, tenant_id: str | None = None) -> None:
        """Forget one tenant's rules, or every tenant's."""
        if self._durable is not None:
            self._durable.clear(tenant_id)
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
    "ALREADY_CONSUMED",
    "AMOUNT_OVER_CAPABILITY",
    "CHECK_REASONS",
    "DEFAULT_TTL",
    "ERRAND_MISMATCH",
    "EXPIRED",
    "MAX_TTL",
    "ORIGIN_NOT_AUTHORIZED",
    "PARAMETERS_MISMATCH",
    "REVOKED",
    "SELECTOR_MISMATCH",
    "STEP_MISMATCH",
    "STORE_UNAVAILABLE",
    "TASK_MISMATCH",
    "TENANT_MISMATCH",
    "UNKNOWN",
    "VALID",
    "AuthorizationCapability",
    "CapabilityCheck",
    "CapabilityStore",
    "DurableBackend",
    "DurableRuleBackend",
    "StandingRuleStore",
    "capability_store",
    "rules_from_config",
    "standing_rule_store",
]
