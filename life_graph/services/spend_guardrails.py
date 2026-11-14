"""Cloud API cost accounting and spend caps — the call-site backstop.

Every cloud chat completion passes through a :class:`SpendTracker` before it is
sent and again after it returns: :meth:`SpendTracker.check_budget` refuses a
call that would cross a cap, :meth:`SpendTracker.record_usage` books what the
call actually cost. Local inference (LM Studio / Ollama) is priced at $0.00 and
never gated — the guardrail exists to bound *money*, and a local token is free.

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
    ``"monthly"`` or ``"task"``.
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
    ) -> None:
        self.scope = scope
        self.model = model
        self.spent_usd = spent_usd
        self.estimated_usd = estimated_usd
        self.cap_usd = cap_usd
        self.task_key = task_key
        where = f"{scope} cap" + (f" (task {task_key})" if task_key else "")
        super().__init__(
            f"{where} exceeded: ${spent_usd:.4f} spent"
            f" + ${estimated_usd:.4f} estimated > ${cap_usd:.4f} cap"
            f" (model={model})"
        )


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

    @property
    def monthly_remaining_usd(self) -> float:
        """Headroom left this month (0.0 when uncapped or exhausted)."""
        if self.monthly_cap_usd <= 0:
            return 0.0
        return max(0.0, self.monthly_cap_usd - self.monthly_usd)


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
    _monthly: dict[str, float] = field(default_factory=dict, repr=False)
    _per_task: dict[str, float] = field(default_factory=dict, repr=False)
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

    def snapshot(self, task_key: str | None = None) -> SpendSnapshot:
        """Current totals and caps as a plain value object."""
        key = task_key or current_task_key()
        month = self._month()
        with self._lock:
            return SpendSnapshot(
                month=month,
                monthly_usd=self._monthly.get(month, 0.0),
                monthly_cap_usd=self.monthly_cap,
                task_key=key,
                task_usd=self._per_task.get(key, 0.0) if key else 0.0,
                task_cap_usd=self.per_task_cap,
                calls=self._calls,
            )

    def reset(self) -> None:
        """Forget all accumulated spend (test helper / process-level reset)."""
        with self._lock:
            self._monthly.clear()
            self._per_task.clear()
            self._calls = 0

    # ── The two entry points ──────────────────────────────────────

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
        """
        if is_local_model(model) or is_free_model(model):
            return

        estimated = max(0.0, estimated_usd)
        key = task_key or current_task_key()
        month = self._month()

        with self._lock:
            monthly = self._monthly.get(month, 0.0)
            task = self._per_task.get(key, 0.0) if key else 0.0

        # Per-task first: the tighter, more actionable cap, and the one that
        # catches a runaway loop before it eats the month's budget.
        if key is not None:
            self._enforce("task", self.per_task_cap, task, estimated, model, key)
        self._enforce("monthly", self.monthly_cap, monthly, estimated, model, key)

    @staticmethod
    def _enforce(
        scope: str,
        cap: float,
        spent: float,
        estimated: float,
        model: str | None,
        task_key: str | None,
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
        month = self._month()

        with self._lock:
            self._calls += 1
            if cost > 0:
                self._monthly[month] = self._monthly.get(month, 0.0) + cost
                if key is not None:
                    self._per_task[key] = self._per_task.get(key, 0.0) + cost

        if cost > 0:
            logger.debug(
                "Cloud spend: $%.6f (model=%s, in=%d, out=%d, task=%s)",
                cost,
                model,
                prompt_tokens,
                completion_tokens,
                key,
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
