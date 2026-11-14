"""Unit tests for cloud spend accounting and caps (life_graph.services.spend_guardrails).

Pure in-process accounting — no DB, no network. The last section covers the
``LMStudioClient`` wiring: a tripped cap must degrade to local inference rather
than fail the call, and local calls must stay free of the guardrail entirely.
"""

from __future__ import annotations

import pytest

from life_graph.config import settings
from life_graph.services.spend_guardrails import (
    FREE,
    TOKENS_PER_MTOK,
    ModelPrice,
    SpendCapExceededError,
    SpendTracker,
    current_tenant_id,
    estimate_cost_usd,
    estimate_message_tokens,
    estimate_tokens,
    get_spend_tracker,
    is_free_model,
    is_local_model,
    price_for,
)

GPT_4O_MINI = "openrouter/openai/gpt-4o-mini"
DEEPSEEK = "openrouter/deepseek/deepseek-chat"


@pytest.fixture
def tracker():
    """An isolated tracker with explicit caps — never the process singleton."""
    return SpendTracker(monthly_cap_usd=10.0, per_task_cap_usd=0.50)


def _msgs(content: str = "x" * 400) -> list[dict[str, str]]:
    return [{"role": "user", "content": content}]


# ── Pricing ───────────────────────────────────────────────────────────


def test_model_price_cost_is_per_million_tokens():
    price = ModelPrice(1.0, 2.0)
    assert price.cost_usd(TOKENS_PER_MTOK, 0) == pytest.approx(1.0)
    assert price.cost_usd(0, TOKENS_PER_MTOK) == pytest.approx(2.0)
    assert price.cost_usd(TOKENS_PER_MTOK, TOKENS_PER_MTOK) == pytest.approx(3.0)


def test_model_price_ignores_negative_tokens():
    assert ModelPrice(1.0, 1.0).cost_usd(-5, -5) == 0.0


def test_exact_price_table_hit():
    assert price_for(GPT_4O_MINI) == ModelPrice(0.15, 0.60)
    assert price_for(DEEPSEEK) == ModelPrice(0.14, 0.28)


def test_exact_price_matches_advisor_table():
    """The two cost tables in the codebase must not disagree (one per 1K, one per 1M)."""
    from life_graph.services.multi_model_advisor import MODEL_COSTS

    for model, costs in MODEL_COSTS.items():
        price = price_for(model)
        assert price.input_per_mtok == pytest.approx(costs["input"] * 1000)
        assert price.output_per_mtok == pytest.approx(costs["output"] * 1000)


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("openrouter/openai/gpt-4o-mini-2024", ModelPrice(0.15, 0.60)),
        ("openai/gpt-4o", ModelPrice(2.50, 10.00)),
        ("gemini/gemini-2.5-flash-lite", ModelPrice(0.10, 0.40)),
        ("gemini/gemini-2.5-flash", ModelPrice(0.30, 2.50)),
    ],
)
def test_family_price_fallback(model, expected):
    assert price_for(model) == expected


def test_family_fallback_prefers_the_more_specific_family():
    """gpt-4o-mini must not be priced as gpt-4o, nor flash-lite as flash."""
    assert price_for("some/gpt-4o-mini-preview").input_per_mtok == 0.15
    assert price_for("some/gemini-9-flash-lite").input_per_mtok == 0.10


def test_unknown_model_uses_configured_default(monkeypatch):
    monkeypatch.setattr(settings, "spend_unknown_model_input_per_mtok", 7.0)
    monkeypatch.setattr(settings, "spend_unknown_model_output_per_mtok", 9.0)
    assert price_for("mystery/brand-new-model") == ModelPrice(7.0, 9.0)


def test_unknown_model_is_not_free():
    """A model id nobody has priced must not be able to spend invisibly."""
    price = price_for("mystery/brand-new-model")
    assert price.input_per_mtok > 0 and price.output_per_mtok > 0


# ── Local and free models ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "model",
    ["ollama/qwen3:14b", "ollama_chat/qwen3:14b", "lm_studio/qwen3", "local/whatever"],
)
def test_local_prefixes_detected(model):
    assert is_local_model(model)
    assert price_for(model) is FREE
    assert estimate_cost_usd(model, 1_000_000, 1_000_000) == 0.0


def test_bare_configured_local_model_is_local(monkeypatch):
    """Callers pass settings.lm_synthesis_model straight through, unprefixed."""
    monkeypatch.setattr(settings, "lm_synthesis_model", "qwen3:14b")
    assert is_local_model("qwen3:14b")
    assert estimate_cost_usd("qwen3:14b", 500, 500) == 0.0


def test_hosted_openai_inside_openrouter_id_is_not_local():
    """An "openai/" segment inside a hosted OpenRouter id must not read as local."""
    assert not is_local_model("openrouter/openai/gpt-oss-20b")
    assert not is_local_model(GPT_4O_MINI)


def test_none_and_empty_model_are_not_local():
    assert not is_local_model(None)
    assert not is_local_model("")


def test_free_openrouter_models_cost_nothing():
    assert is_free_model("openrouter/openai/gpt-oss-20b:free")
    assert estimate_cost_usd("openrouter/openai/gpt-oss-20b:free", 10**6, 10**6) == 0.0


# ── Token estimation ──────────────────────────────────────────────────


def test_estimate_tokens_from_characters():
    assert estimate_tokens("x" * 400) == 100
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
    assert estimate_tokens("hi") == 1  # never rounds a real string down to zero


def test_estimate_message_tokens_sums_contents():
    messages = [{"role": "system", "content": "y" * 40}, {"role": "user", "content": "z" * 80}]
    assert estimate_message_tokens(messages) == 30
    assert estimate_message_tokens([]) == 0
    assert estimate_message_tokens(None) == 0


def test_estimate_message_tokens_tolerates_missing_content():
    assert estimate_message_tokens([{"role": "assistant"}]) == 0


def test_estimate_cost_usd_math():
    # 1M in + 1M out on gpt-4o-mini = 0.15 + 0.60
    assert estimate_cost_usd(GPT_4O_MINI, 10**6, 10**6) == pytest.approx(0.75)


# ── record_usage ──────────────────────────────────────────────────────


def test_record_usage_returns_and_accumulates_cost(tracker):
    cost = tracker.record_usage(GPT_4O_MINI, prompt_tokens=10**6, completion_tokens=0)
    assert cost == pytest.approx(0.15)
    assert tracker.monthly_total() == pytest.approx(0.15)

    tracker.record_usage(GPT_4O_MINI, prompt_tokens=10**6, completion_tokens=0)
    assert tracker.monthly_total() == pytest.approx(0.30)


def test_record_usage_accepts_a_reported_cost(tracker):
    assert tracker.record_usage(GPT_4O_MINI, cost_usd=0.42) == pytest.approx(0.42)
    assert tracker.monthly_total() == pytest.approx(0.42)


def test_record_usage_clamps_negative_reported_cost(tracker):
    assert tracker.record_usage(GPT_4O_MINI, cost_usd=-1.0) == 0.0
    assert tracker.monthly_total() == 0.0


def test_local_usage_is_counted_as_a_call_but_costs_nothing(tracker):
    assert tracker.record_usage("ollama/qwen3:14b", 10**6, 10**6) == 0.0
    assert tracker.monthly_total() == 0.0
    assert tracker.snapshot().calls == 1


def test_record_text_usage_estimates_from_prompt_and_reply(tracker):
    cost = tracker.record_text_usage(GPT_4O_MINI, _msgs("a" * 4000), "b" * 4000)
    # 1000 prompt + 1000 completion tokens
    expected = (1000 * 0.15 + 1000 * 0.60) / TOKENS_PER_MTOK
    assert cost == pytest.approx(expected)
    assert tracker.monthly_total() == pytest.approx(expected)


def test_monthly_totals_are_bucketed_by_month(tracker):
    tracker.record_usage(GPT_4O_MINI, cost_usd=1.0)
    assert tracker.monthly_total() == pytest.approx(1.0)
    # A different month's bucket starts empty — rollover needs no scheduled reset.
    assert tracker.monthly_total(month="1999-01") == 0.0


# ── Per-task accounting ───────────────────────────────────────────────


def test_task_scope_attributes_spend_to_the_task(tracker):
    with SpendTracker.task_scope("task-a"):
        tracker.record_usage(GPT_4O_MINI, cost_usd=0.10)
    with SpendTracker.task_scope("task-b"):
        tracker.record_usage(GPT_4O_MINI, cost_usd=0.20)

    assert tracker.task_total("task-a") == pytest.approx(0.10)
    assert tracker.task_total("task-b") == pytest.approx(0.20)
    assert tracker.monthly_total() == pytest.approx(0.30)


def test_task_scope_is_restored_afterwards(tracker):
    with SpendTracker.task_scope("task-a"):
        assert tracker.snapshot().task_key == "task-a"
    assert tracker.snapshot().task_key is None


def test_nested_task_scopes_restore_the_outer_key(tracker):
    with SpendTracker.task_scope("outer"):
        with SpendTracker.task_scope("inner"):
            assert tracker.snapshot().task_key == "inner"
        assert tracker.snapshot().task_key == "outer"


def test_ambient_spend_counts_monthly_only(tracker):
    """No task context: the monthly ledger still sees it, no per-task bucket exists."""
    tracker.record_usage(GPT_4O_MINI, cost_usd=0.40)
    assert tracker.monthly_total() == pytest.approx(0.40)
    assert tracker.task_total() == 0.0


def test_kernel_task_context_supplies_the_task_key(tracker):
    import uuid

    from life_graph.core.task_context import set_task_context

    task_id = uuid.uuid4()
    set_task_context(task_id, "tenant-1")
    try:
        tracker.record_usage(GPT_4O_MINI, cost_usd=0.05)
        assert tracker.task_total(str(task_id)) == pytest.approx(0.05)
    finally:
        # The contextvar is per-coroutine; tests share a session-scoped loop.
        from life_graph.core.task_context import _task_context_var

        _task_context_var.set(None)


# ── check_budget ──────────────────────────────────────────────────────


def test_check_budget_passes_when_under_cap(tracker):
    tracker.record_usage(GPT_4O_MINI, cost_usd=1.0)
    tracker.check_budget(GPT_4O_MINI, 0.5)  # 1.5 of 10.0 — fine


def test_check_budget_raises_when_estimate_crosses_monthly_cap(tracker):
    tracker.record_usage(GPT_4O_MINI, cost_usd=9.9)
    with pytest.raises(SpendCapExceededError) as exc:
        tracker.check_budget(GPT_4O_MINI, 0.2)
    assert exc.value.scope == "monthly"
    assert exc.value.cap_usd == pytest.approx(10.0)
    assert exc.value.spent_usd == pytest.approx(9.9)
    assert exc.value.estimated_usd == pytest.approx(0.2)
    assert exc.value.model == GPT_4O_MINI


def test_check_budget_raises_once_exhausted_even_with_no_estimate(tracker):
    tracker.record_usage(GPT_4O_MINI, cost_usd=10.0)
    with pytest.raises(SpendCapExceededError):
        tracker.check_budget(GPT_4O_MINI, 0.0)


def test_check_budget_allows_a_call_landing_exactly_on_the_cap(tracker):
    tracker.record_usage(GPT_4O_MINI, cost_usd=9.5)
    tracker.check_budget(GPT_4O_MINI, 0.5)  # 10.0 == cap, not over


def test_per_task_cap_trips_before_the_monthly_cap(tracker):
    with SpendTracker.task_scope("hot-loop"):
        tracker.record_usage(GPT_4O_MINI, cost_usd=0.49)
        with pytest.raises(SpendCapExceededError) as exc:
            tracker.check_budget(GPT_4O_MINI, 0.05)
    assert exc.value.scope == "task"
    assert exc.value.task_key == "hot-loop"
    # Monthly budget is nowhere near exhausted.
    assert tracker.monthly_total() == pytest.approx(0.49)


def test_per_task_cap_does_not_leak_between_tasks(tracker):
    with SpendTracker.task_scope("task-a"):
        tracker.record_usage(GPT_4O_MINI, cost_usd=0.49)
        with pytest.raises(SpendCapExceededError):
            tracker.check_budget(GPT_4O_MINI, 0.05)
    with SpendTracker.task_scope("task-b"):
        tracker.check_budget(GPT_4O_MINI, 0.05)  # fresh budget


def test_per_task_cap_is_not_enforced_for_ambient_calls(tracker):
    """Ambient spend over the per-task cap is fine — only the monthly cap binds."""
    tracker.record_usage(GPT_4O_MINI, cost_usd=5.0)  # >> 0.50 per-task cap
    tracker.check_budget(GPT_4O_MINI, 0.1)


def test_local_and_free_models_are_never_gated(tracker):
    tracker.record_usage(GPT_4O_MINI, cost_usd=100.0)  # wildly over cap
    with SpendTracker.task_scope("task-a"):
        tracker.check_budget("ollama/qwen3:14b", 999.0)
        tracker.check_budget("openrouter/openai/gpt-oss-20b:free", 999.0)
    with pytest.raises(SpendCapExceededError):
        tracker.check_budget(GPT_4O_MINI, 0.01)


@pytest.mark.parametrize("cap", [0.0, -1.0])
def test_non_positive_cap_disables_enforcement(cap):
    """A misconfigured cap must not freeze the system (the Governor's posture)."""
    tracker = SpendTracker(monthly_cap_usd=cap, per_task_cap_usd=cap)
    tracker.record_usage(GPT_4O_MINI, cost_usd=1000.0)
    with SpendTracker.task_scope("task-a"):
        tracker.check_budget(GPT_4O_MINI, 500.0)


def test_estimate_call_cost_assumes_the_full_completion_budget(tracker):
    cost = tracker.estimate_call_cost(GPT_4O_MINI, _msgs("a" * 4000), max_tokens=1000)
    expected = (1000 * 0.15 + 1000 * 0.60) / TOKENS_PER_MTOK
    assert cost == pytest.approx(expected)


# ── Caps from settings ────────────────────────────────────────────────


def test_caps_default_to_settings(monkeypatch):
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 3.0)
    monkeypatch.setattr(settings, "per_task_spend_cap_usd", 0.25)
    tracker = SpendTracker()
    assert tracker.monthly_cap == pytest.approx(3.0)
    assert tracker.per_task_cap == pytest.approx(0.25)


def test_settings_changes_take_effect_without_rebuilding(monkeypatch):
    tracker = SpendTracker()
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 1.0)
    monkeypatch.setattr(settings, "per_task_spend_cap_usd", 0.0)
    tracker.record_usage(GPT_4O_MINI, cost_usd=0.5)
    tracker.check_budget(GPT_4O_MINI, 0.4)

    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 0.6)
    with pytest.raises(SpendCapExceededError):
        tracker.check_budget(GPT_4O_MINI, 0.4)


def test_explicit_caps_override_settings(monkeypatch):
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 999.0)
    assert SpendTracker(monthly_cap_usd=2.0).monthly_cap == pytest.approx(2.0)


def test_new_settings_exist_with_sane_defaults():
    assert settings.monthly_spend_cap_usd > 0
    assert settings.per_task_spend_cap_usd > 0
    assert settings.per_task_spend_cap_usd <= settings.monthly_spend_cap_usd


# ── Snapshot, reset, singleton ────────────────────────────────────────


def test_snapshot_reports_totals_caps_and_headroom(tracker):
    with SpendTracker.task_scope("task-a"):
        tracker.record_usage(GPT_4O_MINI, cost_usd=0.25)
        snap = tracker.snapshot()

    assert snap.monthly_usd == pytest.approx(0.25)
    assert snap.monthly_cap_usd == pytest.approx(10.0)
    assert snap.monthly_remaining_usd == pytest.approx(9.75)
    assert snap.task_key == "task-a"
    assert snap.task_usd == pytest.approx(0.25)
    assert snap.task_cap_usd == pytest.approx(0.50)
    assert snap.calls == 1
    assert snap.month == SpendTracker._month()


def test_snapshot_headroom_is_zero_when_uncapped():
    tracker = SpendTracker(monthly_cap_usd=0.0)
    assert tracker.snapshot().monthly_remaining_usd == 0.0


def test_reset_clears_everything(tracker):
    with SpendTracker.task_scope("task-a"):
        tracker.record_usage(GPT_4O_MINI, cost_usd=5.0)
    tracker.reset()
    assert tracker.monthly_total() == 0.0
    assert tracker.task_total("task-a") == 0.0
    assert tracker.snapshot().calls == 0


def test_get_spend_tracker_is_a_singleton():
    assert get_spend_tracker() is get_spend_tracker()
    assert isinstance(get_spend_tracker(), SpendTracker)


# ── LMStudioClient wiring ─────────────────────────────────────────────


@pytest.fixture
def cloud_client(monkeypatch):
    """An LMStudioClient in hybrid mode with a fake cloud chain and local path."""
    from life_graph.services import llm_client as llm_client_module

    monkeypatch.setattr(settings, "use_hybrid_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model_cheap", GPT_4O_MINI)

    calls: dict[str, int] = {"cloud": 0, "local": 0}

    class FakeResilient:
        async def chat(self, messages, **kwargs):
            calls["cloud"] += 1
            return "cloud reply " + "r" * 4000

    monkeypatch.setattr(llm_client_module, "get_resilient_llm", lambda: FakeResilient())

    client = llm_client_module.LMStudioClient()

    async def fake_local(messages, model, temperature, max_tokens, response_format):
        calls["local"] += 1
        return "local reply"

    monkeypatch.setattr(client, "_local_chat", fake_local)

    tracker = get_spend_tracker()
    tracker.reset()
    try:
        yield client, calls, tracker
    finally:
        tracker.reset()


async def test_cloud_chat_records_spend(cloud_client, monkeypatch):
    client, calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 10.0)
    monkeypatch.setattr(settings, "per_task_spend_cap_usd", 1.0)

    reply = await client.chat(_msgs("a" * 4000))

    assert reply.startswith("cloud reply")
    assert calls == {"cloud": 1, "local": 0}
    assert tracker.monthly_total() > 0


async def test_cloud_chat_falls_back_to_local_when_cap_is_exhausted(cloud_client, monkeypatch):
    client, calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 1.0)
    monkeypatch.setattr(settings, "per_task_spend_cap_usd", 0.0)
    tracker.record_usage(GPT_4O_MINI, cost_usd=1.0)  # at the cap

    reply = await client.chat(_msgs())

    assert reply == "local reply"
    assert calls == {"cloud": 0, "local": 1}


async def test_cap_exceeded_does_not_raise_out_of_chat(cloud_client, monkeypatch):
    """A tripped cap degrades quality; it must never surface as an exception."""
    client, _calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 0.001)
    tracker.record_usage(GPT_4O_MINI, cost_usd=1.0)

    assert await client.chat(_msgs()) == "local reply"


async def test_chat_local_only_is_never_gated(cloud_client, monkeypatch):
    """Local-only callers (mail bodies) bypass the guardrail even over cap."""
    client, calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 1.0)
    tracker.record_usage(GPT_4O_MINI, cost_usd=100.0)

    assert await client.chat_local_only(_msgs()) == "local reply"
    assert calls["cloud"] == 0
    # Local inference books nothing beyond what was already recorded.
    assert tracker.monthly_total() == pytest.approx(100.0)


async def test_local_mode_never_consults_the_tracker(cloud_client, monkeypatch):
    """With hybrid off, the cloud path (and its cap) is out of the picture."""
    client, calls, tracker = cloud_client
    monkeypatch.setattr(settings, "use_hybrid_llm", False)
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 0.0001)
    tracker.record_usage(GPT_4O_MINI, cost_usd=5.0)

    assert await client.chat(_msgs()) == "local reply"
    assert calls == {"cloud": 0, "local": 1}


async def test_per_task_cap_stops_a_runaway_loop(cloud_client, monkeypatch):
    """Repeated cloud calls inside one task hit the task cap and go local."""
    client, calls, _tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 1000.0)
    monkeypatch.setattr(settings, "per_task_spend_cap_usd", 0.01)

    with SpendTracker.task_scope("runaway"):
        replies = [await client.chat(_msgs("a" * 40000)) for _ in range(6)]

    assert "local reply" in replies  # the cap bit before the sixth call
    assert calls["cloud"] < 6


# ── Two-phase reservations ────────────────────────────────────────────


def test_reserve_then_reconcile_books_actual_spend(tracker):
    res = tracker.reserve(GPT_4O_MINI, 0.40)

    assert res.id and res.model == GPT_4O_MINI
    assert res.estimated_usd == pytest.approx(0.40)
    assert res.month == SpendTracker._month()
    assert tracker.reserved_total() == pytest.approx(0.40)
    # Nothing is booked until the call comes back.
    assert tracker.monthly_total() == 0.0

    booked = tracker.reconcile(res.id, actual_cost_usd=0.12)

    assert booked == pytest.approx(0.12)
    assert tracker.monthly_total() == pytest.approx(0.12)
    assert tracker.reserved_total() == 0.0
    assert tracker.active_reservations() == ()
    assert tracker.snapshot().calls == 1


def test_reconcile_derives_cost_from_tokens_when_none_is_reported(tracker):
    res = tracker.reserve(GPT_4O_MINI, 0.40)
    booked = tracker.reconcile(res.id, prompt_tokens=10**6, completion_tokens=0)
    assert booked == pytest.approx(0.15)  # priced off the reservation's model
    assert tracker.monthly_total() == pytest.approx(0.15)


def test_reconcile_clamps_a_negative_reported_cost(tracker):
    res = tracker.reserve(GPT_4O_MINI, 0.40)
    assert tracker.reconcile(res.id, actual_cost_usd=-5.0) == 0.0
    assert tracker.monthly_total() == 0.0


def test_reserve_then_release_books_nothing(tracker):
    res = tracker.reserve(GPT_4O_MINI, 0.40)
    assert tracker.reserved_total() == pytest.approx(0.40)

    tracker.release(res.id)

    assert tracker.reserved_total() == 0.0
    assert tracker.monthly_total() == 0.0
    assert tracker.active_reservations() == ()
    # A released call never happened, so it is not counted as one.
    assert tracker.snapshot().calls == 0


def test_release_is_idempotent_and_safe_after_reconcile(tracker):
    res = tracker.reserve(GPT_4O_MINI, 0.40)
    tracker.reconcile(res.id, actual_cost_usd=0.10)
    tracker.release(res.id)  # no-op: already settled
    tracker.release(res.id)
    tracker.release("never-existed")
    assert tracker.monthly_total() == pytest.approx(0.10)


def test_reservation_holds_headroom_against_a_second_reserve(tracker):
    """The whole point: an in-flight estimate is committed, not just pencilled in."""
    tracker.reserve(GPT_4O_MINI, 9.5)
    with pytest.raises(SpendCapExceededError) as exc:
        tracker.reserve(GPT_4O_MINI, 1.0)
    assert exc.value.scope == "monthly"
    assert exc.value.spent_usd == pytest.approx(9.5)  # committed, not booked


def test_reserve_reports_the_task_scope_when_the_task_cap_binds(tracker):
    with SpendTracker.task_scope("hot-loop"):
        tracker.reserve(GPT_4O_MINI, 0.49)
        with pytest.raises(SpendCapExceededError) as exc:
            tracker.reserve(GPT_4O_MINI, 0.05)
    assert exc.value.scope == "task"
    assert exc.value.task_key == "hot-loop"


def test_reserve_captures_the_ambient_task_key(tracker):
    with SpendTracker.task_scope("task-a"):
        res = tracker.reserve(GPT_4O_MINI, 0.10)
    assert res.task_key == "task-a"


def test_reconcile_books_to_the_reservations_task_not_the_current_one(tracker):
    """A call can outlive its task context; the money still lands in its bucket."""
    with SpendTracker.task_scope("task-a"):
        res = tracker.reserve(GPT_4O_MINI, 0.10)
    # Settled outside the scope entirely.
    tracker.reconcile(res.id, actual_cost_usd=0.07)
    assert tracker.task_total("task-a") == pytest.approx(0.07)
    assert tracker.monthly_total() == pytest.approx(0.07)


def test_reconcile_books_to_the_reservations_month(tracker):
    from dataclasses import replace

    res = tracker.reserve(GPT_4O_MINI, 0.10)
    # Pretend the reservation was taken out last month and the clock rolled over
    # mid-call: the spend belongs to the month the call started in.
    tracker._active_reservations[res.id] = replace(res, month="1999-01")
    tracker.reconcile(res.id, actual_cost_usd=0.07)
    assert tracker.monthly_total(month="1999-01") == pytest.approx(0.07)
    assert tracker.monthly_total() == 0.0


def test_reconciling_an_unknown_id_still_books_the_cost(tracker, caplog):
    """Money that left the account is booked even if the claim is gone — and warned about."""
    with caplog.at_level("WARNING"):
        booked = tracker.reconcile("no-such-reservation", actual_cost_usd=0.33)
    assert booked == pytest.approx(0.33)
    assert tracker.monthly_total() == pytest.approx(0.33)
    assert "unknown spend reservation" in caplog.text


def test_free_and_local_reservations_are_zero_cost_and_ungated(tracker):
    tracker.reserve(GPT_4O_MINI, 9.99)  # month effectively committed
    for model in ("ollama/qwen3:14b", "openrouter/openai/gpt-oss-20b:free"):
        res = tracker.reserve(model, 999.0)
        assert res.estimated_usd == 0.0
        tracker.reconcile(res.id, actual_cost_usd=0.0)
    assert tracker.monthly_total() == 0.0
    # The cloud reservation still holds its own headroom.
    assert tracker.reserved_total() == pytest.approx(9.99)


def test_reserving_an_unknown_model_consumes_budget(tracker):
    """An unpriced cloud model must reserve real dollars, not slip through free."""
    estimate = tracker.estimate_call_cost("mystery/brand-new-model", _msgs("a" * 4000), 1000)
    assert estimate > 0

    res = tracker.reserve("mystery/brand-new-model", estimate)

    assert res.estimated_usd == pytest.approx(estimate)
    assert tracker.reserved_total() == pytest.approx(estimate)


def test_unknown_model_price_logs_a_warning(caplog):
    from life_graph.services import spend_guardrails

    spend_guardrails._warned_unknown_models.discard("mystery/warn-me-once")
    with caplog.at_level("WARNING"):
        price_for("mystery/warn-me-once")
        price_for("mystery/warn-me-once")  # second call must not re-warn
    assert caplog.text.count("No price table entry") == 1


def test_non_positive_caps_do_not_gate_reservations():
    tracker = SpendTracker(monthly_cap_usd=0.0, per_task_cap_usd=0.0)
    with SpendTracker.task_scope("task-a"):
        tracker.reserve(GPT_4O_MINI, 10_000.0)
        tracker.reserve(GPT_4O_MINI, 10_000.0)


def test_check_budget_counts_in_flight_reservations(tracker):
    """The older check-then-record path cannot be waved through on promised headroom."""
    tracker.reserve(GPT_4O_MINI, 9.9)
    with pytest.raises(SpendCapExceededError):
        tracker.check_budget(GPT_4O_MINI, 0.2)


def test_snapshot_reports_reservations_separately_from_spend(tracker):
    res = tracker.reserve(GPT_4O_MINI, 2.0)
    tracker.reconcile(res.id, actual_cost_usd=1.0)
    tracker.reserve(GPT_4O_MINI, 3.0)

    snap = tracker.snapshot()

    assert snap.monthly_usd == pytest.approx(1.0)
    assert snap.reserved_usd == pytest.approx(3.0)
    assert snap.active_reservations == 1
    # Headroom is net of what is already promised to the call in flight.
    assert snap.monthly_remaining_usd == pytest.approx(6.0)


# ── Concurrency: the property a bare check cannot hold ────────────────


def _race(fn, threads: int):
    """Run *fn* on *threads* threads released together; return (results, refusals)."""
    import threading

    barrier = threading.Barrier(threads)
    results: list[object] = []
    refused: list[SpendCapExceededError] = []
    guard = threading.Lock()

    def run() -> None:
        barrier.wait()
        try:
            value = fn()
        except SpendCapExceededError as exc:
            with guard:
                refused.append(exc)
        else:
            with guard:
                results.append(value)

    workers = [threading.Thread(target=run) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
    assert not any(w.is_alive() for w in workers), "reserve() deadlocked"
    return results, refused


def test_three_threads_cannot_all_reserve_the_last_ten_cents():
    """$0.10 left, $0.04 each: two fit, the third is refused."""
    tracker = SpendTracker(monthly_cap_usd=0.10, per_task_cap_usd=0.0)

    granted, refused = _race(lambda: tracker.reserve(GPT_4O_MINI, 0.04), threads=3)

    assert len(granted) == 2
    assert len(refused) == 1
    assert refused[0].scope == "monthly"
    assert tracker.reserved_total() == pytest.approx(0.08)


def test_total_reservations_can_never_exceed_the_cap_under_contention():
    """Many callers racing for a small budget: the sum granted stays inside the cap."""
    tracker = SpendTracker(monthly_cap_usd=0.10, per_task_cap_usd=0.0)

    granted, refused = _race(lambda: tracker.reserve(GPT_4O_MINI, 0.04), threads=32)

    assert len(granted) == 2
    assert len(refused) == 30
    assert sum(r.estimated_usd for r in granted) <= 0.10


def test_concurrent_reservations_respect_already_booked_spend():
    tracker = SpendTracker(monthly_cap_usd=1.0, per_task_cap_usd=0.0)
    tracker.record_usage(GPT_4O_MINI, cost_usd=0.90)  # $0.10 left

    granted, _refused = _race(lambda: tracker.reserve(GPT_4O_MINI, 0.04), threads=16)

    assert len(granted) == 2
    assert tracker.monthly_total() + tracker.reserved_total() <= 1.0


def test_releases_during_contention_return_headroom_to_later_callers():
    tracker = SpendTracker(monthly_cap_usd=0.10, per_task_cap_usd=0.0)

    def reserve_and_release():
        res = tracker.reserve(GPT_4O_MINI, 0.04)
        tracker.release(res.id)
        return res

    _granted, _refused = _race(reserve_and_release, threads=8)

    assert tracker.reserved_total() == 0.0
    # Budget fully recovered: a fresh pair of reservations still fits.
    tracker.reserve(GPT_4O_MINI, 0.04)
    tracker.reserve(GPT_4O_MINI, 0.04)


# ── Failure paths: reservation_scope ─────────────────────────────────


def test_reservation_scope_releases_when_the_body_raises(tracker):
    with (
        pytest.raises(RuntimeError, match="provider exploded"),
        tracker.reservation_scope(GPT_4O_MINI, 9.5),
    ):
        raise RuntimeError("provider exploded")

    assert tracker.reserved_total() == 0.0
    assert tracker.monthly_total() == 0.0
    # The headroom came back, so an identically sized call now fits.
    tracker.reserve(GPT_4O_MINI, 9.5)


def test_reservation_scope_releases_an_unreconciled_reservation(tracker):
    """A body that simply forgets to reconcile must not strand the headroom."""
    with tracker.reservation_scope(GPT_4O_MINI, 9.5) as res:
        assert res.estimated_usd == pytest.approx(9.5)
        assert tracker.reserved_total() == pytest.approx(9.5)

    assert tracker.reserved_total() == 0.0
    assert tracker.monthly_total() == 0.0


def test_reservation_scope_does_not_double_book_a_reconciled_call(tracker):
    with tracker.reservation_scope(GPT_4O_MINI, 9.5) as res:
        tracker.reconcile(res.id, actual_cost_usd=0.25)

    assert tracker.monthly_total() == pytest.approx(0.25)
    assert tracker.reserved_total() == 0.0
    assert tracker.snapshot().calls == 1


def test_reservation_scope_prices_the_call_when_no_estimate_is_given(tracker):
    with tracker.reservation_scope(GPT_4O_MINI, messages=_msgs("a" * 4000), max_tokens=1000) as res:
        expected = (1000 * 0.15 + 1000 * 0.60) / TOKENS_PER_MTOK
        assert res.estimated_usd == pytest.approx(expected)


def test_reservation_scope_refuses_a_call_that_does_not_fit(tracker):
    tracker.record_usage(GPT_4O_MINI, cost_usd=9.9)
    with pytest.raises(SpendCapExceededError), tracker.reservation_scope(GPT_4O_MINI, 0.5):
        pytest.fail("the body must not run")


def test_a_cap_exceeded_reservation_leaves_nothing_in_flight(tracker):
    tracker.record_usage(GPT_4O_MINI, cost_usd=9.9)
    with pytest.raises(SpendCapExceededError):
        tracker.reserve(GPT_4O_MINI, 0.5)
    assert tracker.reserved_total() == 0.0
    assert tracker.active_reservations() == ()


# ── Recovering orphaned reservations ─────────────────────────────────


def _age(tracker: SpendTracker, reservation, seconds: float) -> None:
    """Backdate a stored reservation, as if its worker had hung that long ago."""
    import time as _time
    from dataclasses import replace

    tracker._active_reservations[reservation.id] = replace(
        reservation, created_at=_time.time() - seconds
    )


def test_purge_stale_reservations_recovers_the_budget(tracker):
    res = tracker.reserve(GPT_4O_MINI, 9.5)
    with pytest.raises(SpendCapExceededError):
        tracker.reserve(GPT_4O_MINI, 1.0)

    _age(tracker, res, 600.0)
    assert tracker.purge_stale_reservations(max_age_seconds=300.0) == 1

    assert tracker.reserved_total() == 0.0
    assert tracker.monthly_total() == 0.0  # purging books nothing
    tracker.reserve(GPT_4O_MINI, 9.5)  # headroom recovered


def test_purge_spares_reservations_inside_the_age_threshold(tracker):
    res = tracker.reserve(GPT_4O_MINI, 1.0)
    _age(tracker, res, 100.0)
    assert tracker.purge_stale_reservations(max_age_seconds=300.0) == 0
    assert tracker.reserved_total() == pytest.approx(1.0)


def test_purge_with_a_non_positive_threshold_is_disabled(tracker):
    res = tracker.reserve(GPT_4O_MINI, 1.0)
    _age(tracker, res, 10_000.0)
    assert tracker.purge_stale_reservations(max_age_seconds=0.0) == 0
    assert tracker.reserved_total() == pytest.approx(1.0)


def test_reserve_reclaims_stale_reservations_automatically(tracker, monkeypatch):
    """The self-healing path: no scheduled sweep needed to recover from a dead worker."""
    monkeypatch.setattr(settings, "spend_reservation_ttl_seconds", 300.0)
    orphan = tracker.reserve(GPT_4O_MINI, 9.5)
    _age(tracker, orphan, 600.0)

    res = tracker.reserve(GPT_4O_MINI, 9.5)  # would not fit beside the orphan

    assert tracker.reserved_total() == pytest.approx(9.5)
    assert [r.id for r in tracker.active_reservations()] == [res.id]


def test_reserve_does_not_reclaim_when_the_ttl_is_disabled(tracker, monkeypatch):
    monkeypatch.setattr(settings, "spend_reservation_ttl_seconds", 0.0)
    orphan = tracker.reserve(GPT_4O_MINI, 9.5)
    _age(tracker, orphan, 10_000.0)
    with pytest.raises(SpendCapExceededError):
        tracker.reserve(GPT_4O_MINI, 1.0)


def test_reservation_age_is_reported(tracker):
    res = tracker.reserve(GPT_4O_MINI, 1.0)
    assert 0.0 <= res.age_seconds < 5.0
    _age(tracker, res, 42.0)
    assert tracker.active_reservations()[0].age_seconds >= 42.0


# ── Per-tenant accounting ────────────────────────────────────────────


def test_reconcile_books_spend_against_the_tenant(tracker):
    res = tracker.reserve(GPT_4O_MINI, 0.20, tenant_id="tenant-1")
    assert res.tenant_id == "tenant-1"

    tracker.reconcile(res.id, actual_cost_usd=0.05)

    assert tracker.tenant_total("tenant-1") == pytest.approx(0.05)
    assert tracker.tenant_total("tenant-2") == 0.0
    assert tracker.monthly_total() == pytest.approx(0.05)


def test_tenant_cap_refuses_a_reservation_that_crosses_it():
    tracker = SpendTracker(monthly_cap_usd=100.0, per_task_cap_usd=0.0, per_tenant_cap_usd=0.10)
    tracker.reserve(GPT_4O_MINI, 0.04, tenant_id="tenant-1")
    tracker.reserve(GPT_4O_MINI, 0.04, tenant_id="tenant-1")

    with pytest.raises(SpendCapExceededError) as exc:
        tracker.reserve(GPT_4O_MINI, 0.04, tenant_id="tenant-1")

    assert exc.value.scope == "tenant"
    assert exc.value.tenant_id == "tenant-1"
    assert "tenant tenant-1" in str(exc.value)
    # A different tenant has its own ceiling.
    tracker.reserve(GPT_4O_MINI, 0.04, tenant_id="tenant-2")


def test_tenant_cap_is_disabled_by_default(tracker):
    """The single-tenant self-host must not acquire a new ceiling by surprise."""
    assert tracker.per_tenant_cap == 0.0
    for _ in range(5):
        tracker.reserve(GPT_4O_MINI, 1.0, tenant_id="tenant-1")


def test_ambient_calls_have_no_tenant_bucket(tracker):
    res = tracker.reserve(GPT_4O_MINI, 0.20)
    assert res.tenant_id is None
    tracker.reconcile(res.id, actual_cost_usd=0.05)
    assert tracker.tenant_total("tenant-1") == 0.0
    assert tracker.monthly_total() == pytest.approx(0.05)


def test_tenant_context_supplies_the_tenant_id(tracker):
    from life_graph.core.tenant import tenant_scope

    with tenant_scope("tenant-ctx"):
        assert current_tenant_id() == "tenant-ctx"
        res = tracker.reserve(GPT_4O_MINI, 0.20)
    tracker.reconcile(res.id, actual_cost_usd=0.05)

    assert res.tenant_id == "tenant-ctx"
    assert tracker.tenant_total("tenant-ctx") == pytest.approx(0.05)


def test_current_tenant_id_is_none_without_a_tenant_context():
    """Workers and CLI runs have no tenant; spend accounting must not raise there."""
    assert current_tenant_id() is None


def test_reset_clears_tenants_and_reservations(tracker):
    tracker.reserve(GPT_4O_MINI, 1.0, tenant_id="tenant-1")
    res = tracker.reserve(GPT_4O_MINI, 1.0, tenant_id="tenant-1")
    tracker.reconcile(res.id, actual_cost_usd=0.5)

    tracker.reset()

    assert tracker.tenant_total("tenant-1") == 0.0
    assert tracker.reserved_total() == 0.0
    assert tracker.active_reservations() == ()


# ── LMStudioClient wiring: the reservation must not leak ─────────────


async def test_cloud_chat_reserves_and_reconciles(cloud_client, monkeypatch):
    client, calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 10.0)
    monkeypatch.setattr(settings, "per_task_spend_cap_usd", 0.0)

    reply = await client.chat(_msgs("a" * 4000), max_tokens=4096)

    assert reply.startswith("cloud reply")
    assert calls == {"cloud": 1, "local": 0}
    # Reconciled: booked, with nothing left in flight.
    assert tracker.monthly_total() > 0
    assert tracker.reserved_total() == 0.0
    assert tracker.snapshot().active_reservations == 0


async def test_cloud_chat_reconciles_below_the_reserved_ceiling(cloud_client, monkeypatch):
    """The pre-flight estimate assumes the whole max_tokens; the reply used less."""
    client, _calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 10.0)
    monkeypatch.setattr(settings, "per_task_spend_cap_usd", 0.0)
    ceiling = tracker.estimate_call_cost(GPT_4O_MINI, _msgs("a" * 4000), 4096)

    await client.chat(_msgs("a" * 4000), max_tokens=4096)

    assert 0 < tracker.monthly_total() < ceiling


async def test_cloud_chat_releases_the_reservation_when_the_provider_fails(
    cloud_client, monkeypatch
):
    client, calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 10.0)

    from life_graph.services import llm_client as llm_client_module

    class ExplodingResilient:
        async def chat(self, messages, **kwargs):
            calls["cloud"] += 1
            raise RuntimeError("provider down")

    monkeypatch.setattr(llm_client_module, "get_resilient_llm", lambda: ExplodingResilient())

    assert await client.chat(_msgs("a" * 4000)) == "local reply"

    assert calls == {"cloud": 1, "local": 1}
    assert tracker.reserved_total() == 0.0  # released, not stranded
    assert tracker.monthly_total() == 0.0  # a failed call costs nothing


async def test_cloud_chat_releases_the_reservation_when_cancelled(cloud_client, monkeypatch):
    """Cancellation is not an Exception; it must still return the headroom."""
    import asyncio

    client, _calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 10.0)

    from life_graph.services import llm_client as llm_client_module

    class CancelledResilient:
        async def chat(self, messages, **kwargs):
            raise asyncio.CancelledError

    monkeypatch.setattr(llm_client_module, "get_resilient_llm", lambda: CancelledResilient())

    with pytest.raises(asyncio.CancelledError):
        await client.chat(_msgs("a" * 4000))

    assert tracker.reserved_total() == 0.0
    assert tracker.monthly_total() == 0.0


async def test_repeated_failures_do_not_exhaust_the_budget(cloud_client, monkeypatch):
    """Released reservations must not accumulate into a phantom spend ceiling."""
    client, _calls, tracker = cloud_client
    monkeypatch.setattr(settings, "monthly_spend_cap_usd", 1.0)
    monkeypatch.setattr(settings, "per_task_spend_cap_usd", 0.0)

    from life_graph.services import llm_client as llm_client_module

    class ExplodingResilient:
        async def chat(self, messages, **kwargs):
            raise RuntimeError("provider down")

    monkeypatch.setattr(llm_client_module, "get_resilient_llm", lambda: ExplodingResilient())
    for _ in range(50):
        assert await client.chat(_msgs("a" * 4000)) == "local reply"

    assert tracker.reserved_total() == 0.0
    # The budget is untouched, so a real cloud call is still allowed.
    tracker.reserve(GPT_4O_MINI, 0.9)
