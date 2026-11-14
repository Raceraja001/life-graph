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
