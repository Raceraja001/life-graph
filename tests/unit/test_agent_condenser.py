"""docs/specs/agent-condenser.md: stuck detection and the context condenser (pure)."""

from __future__ import annotations

import json

import pytest

from life_graph.agents import condenser
from life_graph.agents.stuck import StuckDetector, is_error_result, nudge_text

# ── Stuck detection ─────────────────────────────────────────────────────────


def test_same_call_same_result_three_times_is_a_repeat():
    d = StuckDetector()
    assert d.record("code_read", {"path": "a.py"}, "same") is None
    assert d.record("code_read", {"path": "a.py"}, "same") is None
    found = d.record("code_read", {"path": "a.py"}, "same")
    assert found and found.pattern == "repeat" and found.tool == "code_read"
    assert "code_read" in nudge_text(found)


def test_argument_order_does_not_hide_a_repeat():
    d = StuckDetector()
    d.record("t", {"a": 1, "b": 2}, "r")
    d.record("t", {"b": 2, "a": 1}, "r")
    assert d.record("t", {"a": 1, "b": 2}, "r").pattern == "repeat"


def test_the_same_failing_call_with_changing_errors_is_an_error_repeat():
    d = StuckDetector()
    for i in range(2):
        assert (
            d.record("code_edit", {"path": "x"}, json.dumps({"error": f"no match ({i})"})) is None
        )
    found = d.record("code_edit", {"path": "x"}, json.dumps({"error": "no match (2)"}))
    assert found.pattern == "error_repeat"


def test_ping_pong():
    d = StuckDetector()
    found = None
    for _ in range(3):
        found = found or d.record("code_list", {"path": "."}, "listing")
        found = found or d.record("code_read", {"path": "README.md"}, "readme")
    assert found and found.pattern == "ping_pong"


def test_a_varied_run_is_never_stuck():
    d = StuckDetector()
    for i in range(30):
        assert d.record("code_read", {"path": f"f{i}.py"}, f"content {i}") is None


def test_no_progress_after_many_already_seen_results():
    d = StuckDetector()
    d.record("code_search", {"q": "a"}, "nothing")
    d.record("code_search", {"q": "b"}, "other")
    found = None
    for i in range(14):  # different queries, results all seen before
        found = found or d.record("code_search", {"q": f"z{i}"}, "nothing" if i % 2 else "other")
    assert found and found.pattern == "no_progress"


def test_detection_resets_the_window_and_counts():
    d = StuckDetector()
    for _ in range(3):
        d.record("t", {}, "r")
    assert d.detections == 1
    assert d.record("t", {}, "r") is None  # the nudge gets a fair chance
    d.record("t", {}, "r")
    assert d.record("t", {}, "r").pattern == "repeat" and d.detections == 2


@pytest.mark.parametrize(
    ("text", "error"),
    [('{"error": "x"}', True), ('{"error": ""}', False), ('{"ok": 1}', False), ("plain", False)],
)
def test_is_error_result(text, error):
    assert is_error_result(text) is error


# ── Condenser ───────────────────────────────────────────────────────────────


def _conversation(turns: int, result_chars: int = 4000) -> list[dict]:
    msgs = [
        {"role": "system", "content": "You are a careful coder. RULE: never touch .env"},
        {"role": "user", "content": "TASK: add a /health endpoint to app.py"},
    ]
    for i in range(turns):
        msgs.append(
            {
                "role": "assistant",
                "content": f"step {i}",
                "tool_calls": [
                    {
                        "id": f"c{i}",
                        "type": "function",
                        "function": {
                            "name": "code_read",
                            "arguments": json.dumps({"path": f"f{i}.py"}),
                        },
                    }
                ],
            }
        )
        msgs.append(
            {"role": "tool", "tool_call_id": f"c{i}", "content": f"[{i}] " + "x" * result_chars}
        )
    return msgs


@pytest.fixture(autouse=True)
def char_counting(monkeypatch):
    """Deterministic token counts, independent of litellm's tokenizer."""
    monkeypatch.setattr(
        condenser,
        "count_tokens",
        lambda messages, model=None: sum(len(condenser._text(m)) for m in messages) // 4,
    )


@pytest.mark.asyncio
async def test_under_budget_nothing_changes():
    msgs = _conversation(3, 100)
    out = await condenser.condense(msgs, budget=100_000)
    assert out.layer is None and out.messages is msgs


@pytest.mark.asyncio
async def test_masking_keeps_head_tail_and_protocol():
    msgs = _conversation(12)
    out = await condenser.condense(msgs, budget=6000)
    assert out.layer == "mask" and out.after_tokens <= 6000 < out.before_tokens
    assert out.messages[0]["content"].startswith("You are a careful coder")
    assert out.messages[1]["content"].startswith("TASK:")
    assert condenser.valid(out.messages)
    tools = [m for m in out.messages if m["role"] == "tool"]
    assert len(tools) == 12  # nothing removed, only elided
    assert tools[0]["content"].startswith("[earlier result elided: code_read f0.py, 4,004 chars")
    assert tools[-1]["content"].startswith("[11] xxx")  # the recent turns stay verbatim
    masked = sum(t["content"].startswith("[earlier") for t in tools)
    # Every middle result is masked, except recent reads given back while they fit.
    assert 0 < masked <= 12 - condenser.KEEP_RECENT_TURNS


@pytest.mark.asyncio
async def test_summary_replaces_the_middle_when_masking_is_not_enough():
    msgs = _conversation(60, 400)
    seen = {}

    async def summarise(middle):
        seen["n"] = len(middle)
        return "## Done so far\nRead f0..f55.\n## Open problems / next step\nEdit app.py"

    out = await condenser.condense(msgs, budget=2500, summarise=summarise)
    assert out.layer == "summary" and out.after_tokens <= 2500
    assert condenser.valid(out.messages)
    summary = out.messages[2]
    assert summary["role"] == "user" and summary["content"].startswith(condenser.SUMMARY_TAG)
    assert seen["n"] == len(msgs) - 2 - 2 * condenser.KEEP_RECENT_TURNS
    assert out.messages[1]["content"].startswith("TASK:")


@pytest.mark.asyncio
async def test_a_failing_summary_falls_back_to_truncation():
    async def broken(middle):
        raise RuntimeError("model down")

    out = await condenser.condense(_conversation(60, 400), budget=2500, summarise=broken)
    assert out.layer == "truncate" and condenser.valid(out.messages)
    assert out.messages[2]["content"] == condenser.DROPPED_TAG
    assert out.messages[1]["content"].startswith("TASK:")


@pytest.mark.asyncio
async def test_few_huge_turns_mask_all_but_the_latest():
    msgs = _conversation(3, 40_000)
    out = await condenser.condense(msgs, budget=12_000)
    assert out.layer == "mask" and condenser.valid(out.messages)
    tools = [m for m in out.messages if m["role"] == "tool"]
    assert tools[0]["content"].startswith("[earlier") and tools[-1]["content"].startswith("[2] ")


@pytest.mark.asyncio
async def test_a_nudge_before_the_tail_stays_with_it():
    msgs = _conversation(10, 2000)
    msgs.insert(
        -2 * condenser.KEEP_RECENT_TURNS, {"role": "user", "content": "[Loop detected: repeat]"}
    )
    out = await condenser.condense(msgs, budget=3000, summarise=None)
    assert condenser.valid(out.messages)
    assert any(m.get("content") == "[Loop detected: repeat]" for m in out.messages)


def test_valid_catches_broken_conversations():
    good = _conversation(2, 10)
    assert condenser.valid(good)
    assert not condenser.valid(good[:-1])  # a call without its result
    assert not condenser.valid(good[:2] + good[3:])  # an orphaned tool message
    bad = good[:3] + [{"role": "user", "content": "x"}] + good[3:]
    assert not condenser.valid(bad)


def test_cap_result_keeps_head_and_tail():
    text = "HEAD" + "m" * 50_000 + "TAIL"
    capped = condenser.cap_result(text, 1000)
    assert capped.startswith("HEAD") and capped.endswith("TAIL") and "characters cut" in capped
    assert len(capped) < 1200
    assert condenser.cap_result("short", 1000) == "short"


def test_budget_for():
    assert condenser.budget_for(32768, 4096) == int(32768 * 0.8) - 4096
    assert condenser.budget_for(2000, 4096) == 1024


def test_context_tokens_override(monkeypatch):
    from life_graph.config import Settings

    s = Settings(
        agent_context_tokens=32768, agent_context_tokens_by_model='{"ollama_chat/big": 65536}'
    )
    assert s.context_tokens_for("ollama_chat/big") == 65536
    assert s.context_tokens_for("other") == 32768
    assert Settings(agent_context_tokens_by_model="not json").context_tokens_for("x") > 0


@pytest.mark.asyncio
async def test_the_newest_read_of_each_file_survives_masking():
    msgs = _conversation(12, 1500)  # 8 masked-zone reads, each ~400 tokens
    # Turn 7 re-reads f1.py: that newest copy is given back; the turn-1 copy of
    # the same file stays masked even though there would be room for it.
    msgs[2 + 2 * 7]["tool_calls"][0]["function"]["arguments"] = json.dumps({"path": "f1.py"})
    out = await condenser.condense(msgs, budget=3000)
    assert out.layer == "mask" and condenser.valid(out.messages)
    by_id = {m["tool_call_id"]: m["content"] for m in out.messages if m["role"] == "tool"}
    assert by_id["c1"].startswith("[earlier result elided")
    assert by_id["c7"].startswith("[7] xxx")  # newest read of f1.py, kept verbatim
    assert by_id["c0"].startswith("[earlier result elided")


@pytest.mark.asyncio
async def test_newest_reads_are_masked_too_when_they_alone_do_not_fit():
    out = await condenser.condense(_conversation(12, 4000), budget=6000)
    assert out.layer == "mask" and out.after_tokens <= 6000
