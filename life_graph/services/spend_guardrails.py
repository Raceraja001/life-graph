"""Cloud API cost accounting and spend caps — the call-site backstop.

Every cloud chat completion passes through a :class:`SpendTracker` before it is
sent and again after it returns. The pre-flight step is a *reservation*, not a
check: :meth:`SpendTracker.reserve` atomically books a conservative estimate of
the call's cost against the monthly, per-task and per-tenant ceilings, and the
call is refused if that reservation would not fit. When the call returns,
:meth:`SpendTracker.reconcile` swaps the estimate for the real figure; if it
fails, :meth:`SpendTracker.release` hands the headroom back. Local inference
(LM Studio / Ollama) is priced at $0.00 and never gated — the guardrail exists
to bound *money*, and a local token is free.

Why two phases rather than check-then-record: a bare check reads the balance
and the caller spends later, so *n* concurrent callers can all pass the same
check against the same remaining dollar and overspend it *n* times. A
reservation is counted as committed from the moment it is granted, so the sum
of granted reservations plus booked spend can never exceed a cap. The older
:meth:`check_budget` / :meth:`record_usage` pair remains for callers that only
account after the fact; ``check_budget`` counts active reservations too, so the
two styles cannot overspend past each other.

Relationship to the Governor (``core/budget.py`` + ``services/governor.py``):
the Governor is the policy layer that arbitrates *between* autonomous spenders
against a Postgres ledger, deciding who gets throttled first as a shared budget
fills. This module is a layer below it — no DB, no I/O, no policy — answering
only "what did this call cost, and is the ceiling breached?". They compose: the
Governor decides whether a worker may run at all, this stops a runaway loop
inside one that is already authorized.

Two deliberate properties:

* **In-process.** Totals live in memory and reset when the process restarts, so
  this is a backstop against a runaway loop, not a billing system of record —
  ``BudgetSpend`` (via the Governor) is the durable ledger.
* **Estimated.** Cost is derived from token counts and a static price table.
  The resilient cloud chain can fail over to a different model mid-call, and
  callers that only get text back (not a usage object) have their tokens
  estimated from character counts. Figures are good to a few percent, which is
  what a guardrail needs; they are not an invoice.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from life_graph.config import settings

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

logger = logging.getLogger(__name__)

# Prices are quoted per million tokens, the unit every provider publishes.
TOKENS_PER_MTOK = 1_000_000

# Roughly how many characters make a token for English prose. Only used when a
# caller has no usage object to report (see module docstring).
CHARS_PER_TOKEN = 4

# Providers served from this machine: free, and never gated. Kept in sync with
# ``resilient_llm.LOCAL_PROVIDERS`` — note the absence of "openai/", which in
# this codebase appears *inside* hosted OpenRouter ids like
# "openrouter/openai/gpt-oss-20b:free".
LOCAL_MODEL_PREFIXES = ("ollama/", "ollama_chat/", "lm_studio/", "local/")

# Model ids already warned about as unpriced, so the warning lands once per
# process rather than once per call.
_warned_unknown_models: set[str] = set()


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """USD per million input / output tokens."""

    input_per_mtok: float
    output_per_mtok: float

    def cost_usd(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Cost of a call with these token counts."""
        return (
            max(0, prompt_tokens) * self.input_per_mtok
            + max(0, completion_tokens) * self.output_per_mtok
        ) / TOKENS_PER_MTOK


FREE = ModelPrice(0.0, 0.0)

# Exact model ids, USD per 1M tokens. The three OpenRouter entries carry the
# same figures as ``services/multi_model_advisor.MODEL_COSTS`` (which quotes per
# 1K), so the two tables can't disagree.
MODEL_PRICES: dict[str, ModelPrice] = {
    "openrouter/openai/gpt-4o-mini": ModelPrice(0.15, 0.60),
    "openrouter/deepseek/deepseek-chat": ModelPrice(0.14, 0.28),
    "openrouter/meta-llama/llama-3.1-8b-instruct": ModelPrice(0.05, 0.08),
}

# Fallback by model *family*, matched as a substring of the id once no exact
# entry hits. Ordered longest-intent-first: "gpt-4o-mini" must beat "gpt-4o",
# "flash-lite" must beat "flash".
MODEL_FAMILY_PRICES: tuple[tuple[str, ModelPrice], ...] = (
    ("gpt-4o-mini", ModelPrice(0.15, 0.60)),
    ("gpt-4o", ModelPrice(2.50, 10.00)),
    ("deepseek", ModelPrice(0.14, 0.28)),
    ("llama", ModelPrice(0.05, 0.08)),
    ("flash-lite", ModelPrice(0.10, 0.40)),
    ("flash", ModelPrice(0.30, 2.50)),
)


class SpendCapExceededError(RuntimeError):
    """A cloud call was refused because it would cross a spend cap.

    Carries the numbers so callers can log or surface them. ``scope`` is
    ``"monthly"``, ``"task"`` or ``"tenant"``. ``spent_usd`` is the *committed*
    figure — spend already booked plus reservations still in flight — which is
    what the cap is actually enforced against.
    """

    def __init__(
        self,
        scope: str,
        *,
        model: str,
        spent_usd: float,
        estimated_usd: float,
        cap_usd: float,
        task_key: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        self.scope = scope
        self.model = model
        self.spent_usd = spent_usd
        self.estimated_usd = estimated_usd
        self.cap_usd = cap_usd
        self.task_key = task_key
        self.tenant_id = tenant_id
        subject = (
            f" (task {task_key})" if task_key else f" (tenant {tenant_id})" if tenant_id else ""
        )
        where = f"{scope} cap{subject}"
        super().__init__(
            f"{where} exceeded: ${spent_usd:.4f} spent"
            f" + ${estimated_usd:.4f} estimated > ${cap_usd:.4f} cap"
            f" (model={model})"
        )


@dataclass(frozen=True, slots=True)
class Reservation:
    """Headroom claimed for one in-flight cloud call.

    Granted by :meth:`SpendTracker.reserve` and settled by exactly one of
    :meth:`SpendTracker.reconcile` (the call happened — book the real cost) or
    :meth:`SpendTracker.release` (it did not — give the headroom back). While it
    is outstanding, ``estimated_usd`` counts as committed against every cap it
    was checked against, which is what makes the ceilings hold under
    concurrency.

    ``month``, ``task_key`` and ``tenant_id`` are captured at reservation time
    so settlement attributes the spend where the call was *started*, even if
    the UTC month rolls over or the context changes mid-call.
    """

    id: str
    model: str
    estimated_usd: float
    task_key: str | None
    tenant_id: str | None
    month: str
    created_at: float

    @property
    def age_seconds(self) -> float:
        """How long this reservation has been outstanding."""
        return max(0.0, time.time() - self.created_at)


@dataclass(frozen=True, slots=True)
class SpendSnapshot:
    """A read-only view of the tracker, for logs, briefs and dashboards."""

    month: str
    monthly_usd: float
    monthly_cap_usd: float
    task_key: str | None
    task_usd: float
    task_cap_usd: float
    calls: int
    tenant_id: str | None = None
    tenant_usd: float = 0.0
    tenant_cap_usd: float = 0.0
    # Estimated cost of calls that are in flight right now: already committed
    # against the caps, not yet booked as spend.
    reserved_usd: float = 0.0
    active_reservations: int = 0

    @property
    def monthly_remaining_usd(self) -> float:
        """Headroom left this month (0.0 when uncapped or exhausted).

        Net of in-flight reservations — this is what a new call can actually
        claim, not what has been billed.
        """
        if self.monthly_cap_usd <= 0:
            return 0.0
        return max(0.0, self.monthly_cap_usd - self.monthly_usd - self.reserved_usd)


# ── Pricing ───────────────────────────────────────────────────────────


def is_local_model(model: str | None) -> bool:
    """Whether *model* is served from this machine (and therefore free).

    Matches the local provider prefixes, and also the bare model names
    configured for the local runtime (``qwen3:14b``), which arrive without a
    prefix when a caller passes ``settings.lm_synthesis_model`` straight
    through.
    """
    if not model:
        return False
    name = model.strip().lower()
    if name.startswith(LOCAL_MODEL_PREFIXES):
        return True
    local_names = {
        (settings.lm_synthesis_model or "").strip().lower(),
        (settings.lm_embedding_model or "").strip().lower(),
    }
    return name in local_names - {""}


def is_free_model(model: str | None) -> bool:
    """Whether *model* is an explicitly free hosted model (OpenRouter ``:free``)."""
    return bool(model) and model.strip().lower().endswith(":free")


def price_for(model: str | None) -> ModelPrice:
    """Price for *model* — exact entry, then family, then the unknown default.

    Local and ``:free`` models price at zero. Anything else unrecognised falls
    back to the configured unknown-model price rather than zero, so a new model
    id can't spend invisibly.
    """
    if is_local_model(model) or is_free_model(model):
        return FREE
    if not model:
        return FREE
    name = model.strip().lower()
    exact = MODEL_PRICES.get(name)
    if exact is not None:
        return exact
    for family, price in MODEL_FAMILY_PRICES:
        if family in name:
            return price
    if name not in _warned_unknown_models:
        # set.add is atomic under the GIL; a duplicate warning in a race is
        # harmless, and the point is to stop the log filling up.
        _warned_unknown_models.add(name)
        logger.warning(
            "No price table entry for cloud model %r — charging the unknown-model"
            " default of $%.2f/$%.2f per 1M tokens. Add it to MODEL_PRICES or"
            " MODEL_FAMILY_PRICES to account for it accurately.",
            model,
            settings.spend_unknown_model_input_per_mtok,
            settings.spend_unknown_model_output_per_mtok,
        )
    return ModelPrice(
        settings.spend_unknown_model_input_per_mtok,
        settings.spend_unknown_model_output_per_mtok,
    )


def estimate_tokens(text: str | None) -> int:
    """Approximate the token count of *text* from its length."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_message_tokens(messages: Sequence[dict[str, Any]] | None) -> int:
    """Approximate the prompt tokens of an OpenAI-style message list."""
    if not messages:
        return 0
    return sum(estimate_tokens(str(m.get("content") or "")) for m in messages)


def estimate_cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimated USD cost of a call. Always 0.0 for local and free models."""
    return price_for(model).cost_usd(prompt_tokens, completion_tokens)


# ── Per-task scoping ──────────────────────────────────────────────────

_scope_var: ContextVar[str | None] = ContextVar("spend_scope", default=None)


def current_task_key() -> str | None:
    """The task this coroutine is spending under, or None when ambient.

    Prefers an explicit :meth:`SpendTracker.task_scope`, then the kernel's
    ``TaskContext``. None means "not inside a task" — such calls count toward
    the monthly total but are not subject to the per-task cap.
    """
    explicit = _scope_var.get()
    if explicit:
        return explicit
    try:
        from life_graph.core.task_context import get_current_task_context

        ctx = get_current_task_context()
    except Exception:  # pragma: no cover - defensive; contextvar lookup is safe
        return None
    return str(ctx.task_id) if ctx else None


def current_tenant_id() -> str | None:
    """The tenant this call is spending on behalf of, or None when ambient.

    ``core.tenant.get_current_tenant_id`` *raises* when no tenant context is
    set, which is the normal state inside a worker or a CLI run. Spend
    accounting must not fail there, so this returns None instead and the call
    counts toward the monthly total without a per-tenant bucket.
    """
    try:
        from life_graph.core.tenant import get_current_tenant_id

        return get_current_tenant_id() or None
    except Exception:
        return None


# ── The tracker ───────────────────────────────────────────────────────


@dataclass
class SpendTracker:
    """In-process accounting of cloud spend, per task and per month.

    Caps default to ``None``, meaning "read ``settings`` at call time" — so
    config changes and test monkeypatching both take effect without rebuilding
    the tracker. Pass explicit values for an isolated tracker (as the tests do).

    Monthly totals are bucketed by UTC month, so a rollover starts a fresh
    budget without a scheduled reset.
    """

    monthly_cap_usd: float | None = None
    per_task_cap_usd: float | None = None
    per_tenant_cap_usd: float | None = None
    _monthly: dict[str, float] = field(default_factory=dict, repr=False)
    _per_task: dict[str, float] = field(default_factory=dict, repr=False)
    _per_tenant: dict[str, float] = field(default_factory=dict, repr=False)
    _active_reservations: dict[str, Reservation] = field(default_factory=dict, repr=False)
    _calls: int = field(default=0, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ── Effective caps ────────────────────────────────────────────

    @property
    def monthly_cap(self) -> float:
        """Monthly cap in effect (<= 0 disables monthly enforcement)."""
        if self.monthly_cap_usd is not None:
            return self.monthly_cap_usd
        return float(settings.monthly_spend_cap_usd)

    @property
    def per_task_cap(self) -> float:
        """Per-task cap in effect (<= 0 disables per-task enforcement)."""
        if self.per_task_cap_usd is not None:
            return self.per_task_cap_usd
        return float(settings.per_task_spend_cap_usd)

    @property
    def per_tenant_cap(self) -> float:
        """Per-tenant monthly cap in effect (<= 0 disables it).

        Zero by default: on a single-tenant self-host the monthly cap is already
        the tenant cap. A shared deployment sets it so one tenant cannot drain
        the whole month.
        """
        if self.per_tenant_cap_usd is not None:
            return self.per_tenant_cap_usd
        return float(settings.per_tenant_spend_cap_usd)

    # ── Scoping ───────────────────────────────────────────────────

    @staticmethod
    @contextmanager
    def task_scope(task_key: str) -> Iterator[str]:
        """Attribute spend inside this block to *task_key*.

        For work that isn't running under a kernel ``TaskContext`` but still
        wants a per-task ceiling (a CLI run, a one-off backfill).
        """
        token = _scope_var.set(task_key)
        try:
            yield task_key
        finally:
            _scope_var.reset(token)

    @staticmethod
    def _month(now: datetime | None = None) -> str:
        return f"{now or datetime.now(UTC):%Y-%m}"

    # ── Reads ─────────────────────────────────────────────────────

    def monthly_total(self, *, month: str | None = None) -> float:
        """Spend booked in *month* (default: the current UTC month)."""
        with self._lock:
            return self._monthly.get(month or self._month(), 0.0)

    def task_total(self, task_key: str | None = None) -> float:
        """Spend booked against *task_key* (default: the current task)."""
        key = task_key or current_task_key()
        if key is None:
            return 0.0
        with self._lock:
            return self._per_task.get(key, 0.0)

    def tenant_total(self, tenant_id: str | None = None) -> float:
        """Spend booked against *tenant_id* (default: the current tenant)."""
        key = tenant_id or current_tenant_id()
        if key is None:
            return 0.0
        with self._lock:
            return self._per_tenant.get(key, 0.0)

    def reserved_total(self, *, month: str | None = None) -> float:
        """Estimated cost of the calls in flight right now for *month*."""
        target = month or self._month()
        with self._lock:
            return sum(
                r.estimated_usd for r in self._active_reservations.values() if r.month == target
            )

    def active_reservations(self) -> tuple[Reservation, ...]:
        """The outstanding reservations, for diagnostics."""
        with self._lock:
            return tuple(self._active_reservations.values())

    def snapshot(
        self, task_key: str | None = None, *, tenant_id: str | None = None
    ) -> SpendSnapshot:
        """Current totals, caps and in-flight reservations as a value object."""
        key = task_key or current_task_key()
        tenant = tenant_id or current_tenant_id()
        month = self._month()
        with self._lock:
            in_flight = [r for r in self._active_reservations.values() if r.month == month]
            return SpendSnapshot(
                month=month,
                monthly_usd=self._monthly.get(month, 0.0),
                monthly_cap_usd=self.monthly_cap,
                task_key=key,
                task_usd=self._per_task.get(key, 0.0) if key else 0.0,
                task_cap_usd=self.per_task_cap,
                calls=self._calls,
                tenant_id=tenant,
                tenant_usd=self._per_tenant.get(tenant, 0.0) if tenant else 0.0,
                tenant_cap_usd=self.per_tenant_cap,
                reserved_usd=sum(r.estimated_usd for r in in_flight),
                active_reservations=len(in_flight),
            )

    def reset(self) -> None:
        """Forget all accumulated spend (test helper / process-level reset).

        Drops in-flight reservations too, so a reconcile arriving afterwards
        books against a clean ledger rather than a half-cleared one.
        """
        with self._lock:
            self._monthly.clear()
            self._per_task.clear()
            self._per_tenant.clear()
            self._active_reservations.clear()
            self._calls = 0

    # ── Estimation ────────────────────────────────────────────────

    def estimate_call_cost(
        self,
        model: str | None,
        messages: Sequence[dict[str, Any]] | None = None,
        max_tokens: int = 0,
    ) -> float:
        """Worst-case cost of a call before it is sent.

        Prompt tokens come from *messages*; the completion is assumed to use the
        whole ``max_tokens`` budget, which is what makes this a ceiling rather
        than a guess.
        """
        return estimate_cost_usd(model, estimate_message_tokens(messages), max_tokens)

    def estimate_reply_cost(
        self,
        model: str | None,
        messages: Sequence[dict[str, Any]] | None,
        reply: str | None,
    ) -> float:
        """Estimated cost of a completed call from its prompt and reply text.

        What a caller has when the resilient chain hands back a bare string and
        no usage object: tokens are inferred from character counts. Still an
        estimate — see the module docstring — but a far tighter one than the
        pre-flight ceiling, since the completion length is now known.
        """
        return estimate_cost_usd(model, estimate_message_tokens(messages), estimate_tokens(reply))

    # ── Two-phase reservations ────────────────────────────────────

    def reserve(
        self,
        model: str | None,
        estimated_usd: float,
        *,
        task_key: str | None = None,
        tenant_id: str | None = None,
    ) -> Reservation:
        """Claim *estimated_usd* of headroom for a call about to be made.

        The atomic half of the guardrail: the caps are evaluated and the claim
        recorded under one lock, so two callers racing for the same remaining
        dollar cannot both be granted it. Settle the returned reservation with
        :meth:`reconcile` (the call completed) or :meth:`release` (it did not) —
        an unsettled reservation holds its headroom until
        :meth:`purge_stale_reservations` reclaims it.

        Free paths (local runtimes, ``:free`` models) are granted a $0.00
        reservation without consulting any cap, so wiring this in front of local
        inference stays a no-op. ``task_key`` and ``tenant_id`` default to the
        ambient context; None for either means that scope's cap does not apply.

        Raises:
            SpendCapExceededError: the reservation would cross a cap.
        """
        is_free = is_local_model(model) or is_free_model(model)
        estimated = 0.0 if is_free else max(0.0, estimated_usd)
        key = task_key or current_task_key()
        tenant = tenant_id or current_tenant_id()
        month = self._month()
        reservation = Reservation(
            id=uuid.uuid4().hex,
            model=model or "unknown",
            estimated_usd=estimated,
            task_key=key,
            tenant_id=tenant,
            month=month,
            created_at=time.time(),
        )

        if estimated <= 0.0:
            # Tracked anyway, so reconcile/release behave identically on every
            # path, but it commits nothing and no cap is consulted. Still swept,
            # so an unsettled free reservation cannot grow the dict forever.
            with self._lock:
                self._purge_locked(float(settings.spend_reservation_ttl_seconds))
                self._active_reservations[reservation.id] = reservation
            return reservation

        with self._lock:
            # Opportunistic: reclaim headroom from workers that died holding a
            # reservation, so the budget heals without a scheduled sweep.
            self._purge_locked(float(settings.spend_reservation_ttl_seconds))
            monthly, task, tenant_spend = self._committed_locked(month, key, tenant)

            # Tightest, most actionable scope first — a runaway loop should be
            # named as a task overrun, not as the month running dry.
            if key is not None:
                self._enforce("task", self.per_task_cap, task, estimated, model, task_key=key)
            if tenant is not None:
                self._enforce(
                    "tenant",
                    self.per_tenant_cap,
                    tenant_spend,
                    estimated,
                    model,
                    tenant_id=tenant,
                )
            self._enforce("monthly", self.monthly_cap, monthly, estimated, model)

            self._active_reservations[reservation.id] = reservation

        logger.debug(
            "Reserved $%.6f (model=%s, task=%s, tenant=%s, id=%s)",
            estimated,
            model,
            key,
            tenant,
            reservation.id,
        )
        return reservation

    def reconcile(
        self,
        reservation_id: str,
        actual_cost_usd: float | None = None,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model: str | None = None,
    ) -> float:
        """Settle a reservation with what the call really cost, and book it.

        Drops the reservation's estimate and replaces it with *actual_cost_usd*
        — the provider-reported figure where there is one. Without it, the cost
        is derived from the token counts and the price table, which is an
        estimate, not an invoice.

        Spend is attributed to the task, tenant and month captured when the
        reservation was granted, not to the ambient context at settlement, so a
        call that outlives its task context still lands in the right bucket.

        Reconciling an id that is no longer active (already settled, or
        reclaimed as stale) still books the cost — the money left the account
        either way — against the current context, and warns. Over-counting is
        the safe direction for a guardrail; silently dropping real spend is not.

        Returns:
            The cost booked, in USD.
        """
        unknown = False
        with self._lock:
            reservation = self._active_reservations.pop(reservation_id, None)
            if reservation is None:
                unknown = True
                priced_model = model
                key = current_task_key()
                tenant = current_tenant_id()
                month = self._month()
            else:
                priced_model = model or reservation.model
                key = reservation.task_key
                tenant = reservation.tenant_id
                month = reservation.month

            cost = (
                max(0.0, actual_cost_usd)
                if actual_cost_usd is not None
                else estimate_cost_usd(priced_model, prompt_tokens, completion_tokens)
            )

            self._calls += 1
            if cost > 0:
                self._monthly[month] = self._monthly.get(month, 0.0) + cost
                if key is not None:
                    self._per_task[key] = self._per_task.get(key, 0.0) + cost
                if tenant is not None:
                    self._per_tenant[tenant] = self._per_tenant.get(tenant, 0.0) + cost

        if unknown:
            logger.warning(
                "Reconciling unknown spend reservation %s (already settled or"
                " reclaimed as stale): booking $%.6f against the current context"
                " (task=%s, tenant=%s)",
                reservation_id,
                cost,
                key,
                tenant,
            )
        elif cost > 0:
            logger.debug(
                "Cloud spend: $%.6f reconciled from $%.6f reserved (model=%s, task=%s, tenant=%s)",
                cost,
                reservation.estimated_usd if reservation else 0.0,
                priced_model,
                key,
                tenant,
            )
        return cost

    def release(self, reservation_id: str) -> None:
        """Drop a reservation without booking any spend.

        For a call that never reached the provider, or failed before it could
        cost anything: the headroom goes straight back. Unknown ids are a no-op,
        so releasing twice (or releasing after reconciling) is safe — which is
        what lets :meth:`reservation_scope` release unconditionally.
        """
        with self._lock:
            reservation = self._active_reservations.pop(reservation_id, None)
        if reservation is not None and reservation.estimated_usd > 0:
            logger.debug(
                "Released $%.6f reserved for %s (id=%s)",
                reservation.estimated_usd,
                reservation.model,
                reservation_id,
            )

    def purge_stale_reservations(self, max_age_seconds: float = 300.0) -> int:
        """Reclaim headroom from reservations older than *max_age_seconds*.

        A reservation is only ever settled by the code that made it, so a worker
        that is cancelled or crashes mid-call leaves its claim outstanding and
        the budget looks smaller than it is. This is the recovery path. The age
        threshold must stay above the slowest cloud call's timeout, or a
        legitimately slow call loses the reservation it is still using.

        Returns:
            How many reservations were reclaimed.
        """
        with self._lock:
            return self._purge_locked(max_age_seconds)

    @contextmanager
    def reservation_scope(
        self,
        model: str | None,
        estimated_usd: float | None = None,
        *,
        messages: Sequence[dict[str, Any]] | None = None,
        max_tokens: int = 0,
        task_key: str | None = None,
        tenant_id: str | None = None,
    ) -> Iterator[Reservation]:
        """Reserve for the duration of the block; never leak the reservation.

        Reserves before the ``yield`` (raising ``SpendCapExceededError`` if it
        does not fit) and releases afterwards no matter how the block ends. The
        body is expected to call :meth:`reconcile` once the real cost is known;
        the release is then a no-op, because reconciling has already settled the
        id. A body that raises, returns early, or simply forgets gives the
        headroom back instead of stranding it.

        Pass *estimated_usd*, or leave it None to price the call from *messages*
        and *max_tokens*.
        """
        estimate = (
            self.estimate_call_cost(model, messages, max_tokens)
            if estimated_usd is None
            else estimated_usd
        )
        reservation = self.reserve(model, estimate, task_key=task_key, tenant_id=tenant_id)
        try:
            yield reservation
        finally:
            self.release(reservation.id)

    # ── Internals (callers hold ``self._lock``) ───────────────────

    def _committed_locked(
        self, month: str, task_key: str | None, tenant_id: str | None
    ) -> tuple[float, float, float]:
        """Booked spend plus in-flight reservations, per scope.

        This sum — not the booked total alone — is what the caps are enforced
        against. Counting reservations is the whole point: money that is
        promised to a call in flight is as spent as money already billed.
        """
        monthly = self._monthly.get(month, 0.0)
        task = self._per_task.get(task_key, 0.0) if task_key else 0.0
        tenant = self._per_tenant.get(tenant_id, 0.0) if tenant_id else 0.0
        for reservation in self._active_reservations.values():
            if reservation.month == month:
                monthly += reservation.estimated_usd
            if task_key is not None and reservation.task_key == task_key:
                task += reservation.estimated_usd
            if tenant_id is not None and reservation.tenant_id == tenant_id:
                tenant += reservation.estimated_usd
        return monthly, task, tenant

    def _purge_locked(self, max_age_seconds: float) -> int:
        """Drop reservations older than *max_age_seconds*. Returns the count."""
        if max_age_seconds <= 0:
            return 0
        cutoff = time.time() - max_age_seconds
        stale = [r for r in self._active_reservations.values() if r.created_at < cutoff]
        for reservation in stale:
            del self._active_reservations[reservation.id]
        if stale:
            logger.warning(
                "Reclaimed %d stale spend reservation(s) worth $%.6f, unsettled for"
                " over %.0fs — a worker likely died mid-call",
                len(stale),
                sum(r.estimated_usd for r in stale),
                max_age_seconds,
            )
        return len(stale)

    # ── After-the-fact accounting ─────────────────────────────────

    def check_budget(
        self,
        model: str | None = None,
        estimated_usd: float = 0.0,
        *,
        task_key: str | None = None,
    ) -> None:
        """Raise :class:`SpendCapExceededError` if this call must not be made.

        A call is refused when the relevant scope is already at its cap, or when
        this call's estimate would push it over. Free paths (local models,
        ``:free`` models, a zero estimate against an unexhausted budget) always
        pass, so wiring this in front of local inference is a no-op.

        Reservations in flight count toward the committed total here too, so a
        caller on this older path cannot be waved through on headroom that
        :meth:`reserve` has already promised to someone else. It remains the
        weaker of the two: the check and the spend are separate steps, so
        concurrent callers on *this* path still race each other. New code should
        use :meth:`reserve`.
        """
        if is_local_model(model) or is_free_model(model):
            return

        estimated = max(0.0, estimated_usd)
        key = task_key or current_task_key()
        tenant = current_tenant_id()
        month = self._month()

        with self._lock:
            monthly, task, tenant_spend = self._committed_locked(month, key, tenant)

        # Per-task first: the tighter, more actionable cap, and the one that
        # catches a runaway loop before it eats the month's budget.
        if key is not None:
            self._enforce("task", self.per_task_cap, task, estimated, model, task_key=key)
        if tenant is not None:
            self._enforce(
                "tenant", self.per_tenant_cap, tenant_spend, estimated, model, tenant_id=tenant
            )
        self._enforce("monthly", self.monthly_cap, monthly, estimated, model, task_key=key)

    @staticmethod
    def _enforce(
        scope: str,
        cap: float,
        spent: float,
        estimated: float,
        model: str | None,
        *,
        task_key: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Compare one scope against its cap. A cap <= 0 means unenforced."""
        if cap <= 0:
            return
        if spent >= cap or spent + estimated > cap:
            raise SpendCapExceededError(
                scope,
                model=model or "unknown",
                spent_usd=spent,
                estimated_usd=estimated,
                cap_usd=cap,
                task_key=task_key if scope == "task" else None,
                tenant_id=tenant_id if scope == "tenant" else None,
            )

    def record_usage(
        self,
        model: str | None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        *,
        cost_usd: float | None = None,
        task_key: str | None = None,
    ) -> float:
        """Book a completed call and return what it cost.

        Pass *cost_usd* when the provider reported a real figure; otherwise it is
        derived from the token counts and the price table. Local and free models
        book $0.00 — recorded as a call, but never against a cap.
        """
        cost = (
            max(0.0, cost_usd)
            if cost_usd is not None
            else estimate_cost_usd(model, prompt_tokens, completion_tokens)
        )
        key = task_key or current_task_key()
        tenant = current_tenant_id()
        month = self._month()

        with self._lock:
            self._calls += 1
            if cost > 0:
                self._monthly[month] = self._monthly.get(month, 0.0) + cost
                if key is not None:
                    self._per_task[key] = self._per_task.get(key, 0.0) + cost
                if tenant is not None:
                    self._per_tenant[tenant] = self._per_tenant.get(tenant, 0.0) + cost

        if cost > 0:
            logger.debug(
                "Cloud spend: $%.6f (model=%s, in=%d, out=%d, task=%s, tenant=%s)",
                cost,
                model,
                prompt_tokens,
                completion_tokens,
                key,
                tenant,
            )
        return cost

    def record_text_usage(
        self,
        model: str | None,
        messages: Sequence[dict[str, Any]] | None,
        reply: str | None,
        *,
        task_key: str | None = None,
    ) -> float:
        """Book a call whose only artefacts are its prompt and its reply text.

        The shape ``LMStudioClient`` is in: the resilient chain hands back a
        string, so tokens are estimated from characters.
        """
        return self.record_usage(
            model,
            prompt_tokens=estimate_message_tokens(messages),
            completion_tokens=estimate_tokens(reply),
            task_key=task_key,
        )


# ── Module-level singleton ────────────────────────────────────────────

_tracker = SpendTracker()


def get_spend_tracker() -> SpendTracker:
    """The process-wide tracker (mirrors ``governor``'s singleton pattern)."""
    return _tracker
