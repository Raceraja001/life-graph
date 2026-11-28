"""Precision modes (snapshot_experiments.MODES) and their shadow comparison.

The settings ``context_precision_mode`` ("" by default) and
``context_precision_shadow`` (off by default) are the only way production
code reaches the precision experiments, and only as fixed, named sets. This
covers: the frozen table and its validation, that a mode is exactly its
experiment set with its own values (passed per call, never by writing the
module), that "" is today's snapshot, and that the shadow comparison keeps
refs, labels and counts only, is time-boxed and never raises. No database.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from datetime import timedelta
from types import SimpleNamespace

import pydantic
import pytest

from life_graph import runtime
from life_graph.config import Settings, settings
from life_graph.config.memory import PRECISION_MODES
from life_graph.services.memory import changes, snapshot
from life_graph.services.memory import snapshot_experiments as xp
from life_graph.services.memory.snapshot import (
    DEFAULT_BUDGET,
    ContextItem,
    ContextSnapshot,
    SourceRef,
    assemble_context,
)
from tests.unit import test_context_snapshot as base
from tests.unit import test_context_snapshot_default_identity as ident
from tests.unit import test_context_snapshot_shadow as kernel
from tests.unit.test_context_snapshot_experiments import xwired  # noqa: F401 — fixture

NOW = base.NOW
wired = base.wired


@pytest.fixture(autouse=True)
def _no_structural_reads(monkeypatch):
    """The modes include H and I: their reads are stand-ins here (no database)."""

    async def none(*a, **kw):
        return []

    monkeypatch.setattr(snapshot, "_undated_intentions", none)
    monkeypatch.setattr(snapshot, "_goal_memories", none)


# ── The table ─────────────────────────────────────────────────


def test_the_modes_are_the_measured_configurations():
    recall, precision = xp.MODES["recall"], xp.MODES["precision"]
    structural = {xp.UNDATED, xp.GOALS, xp.OVERVIEW, xp.DOMAIN}
    assert recall.experiments == {xp.QUERY_TYPE, xp.LINKS, xp.BUDGET} | structural
    assert precision.experiments == {xp.QUERY_TYPE, xp.LINKS, xp.BUDGET, xp.HUB} | structural
    # Only the cosine floor differs from the module's defaults (the eval's --xp-set).
    assert recall.tunables == dataclasses.replace(xp.DEFAULT_TUNABLES, cosine_floor=0.70)
    assert precision.tunables == dataclasses.replace(xp.DEFAULT_TUNABLES, cosine_floor=0.75)
    assert "0.547" in recall.measured and "0.605" in precision.measured


def test_the_table_is_frozen():
    with pytest.raises(TypeError):
        xp.MODES["fast"] = xp.MODES["recall"]  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        xp.MODES["recall"].tunables.cosine_floor = 0.1  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        xp.MODES["recall"].experiments = frozenset()  # type: ignore[misc]


def test_the_setting_takes_exactly_the_modes():
    assert PRECISION_MODES == xp.MODE_NAMES == ("", "recall", "precision")


def test_mode_lookup():
    assert xp.mode("") is None and xp.mode(None) is None  # type: ignore[arg-type]
    assert xp.mode(" Recall ") is xp.MODES["recall"]
    with pytest.raises(ValueError, match="unknown precision mode"):
        xp.mode("fast")


def test_settings_default_off_and_validate():
    fresh = Settings()
    assert fresh.context_precision_mode == "" and fresh.context_precision_shadow is False
    assert Settings(context_precision_mode=" PRECISION ").context_precision_mode == "precision"
    with pytest.raises(pydantic.ValidationError):
        Settings(context_precision_mode="fast")


# ── Tunables are values ───────────────────────────────────────


def test_tunables_default_to_the_constants_and_name_every_tunable():
    named = xp.DEFAULT_TUNABLES.named()
    assert list(named) == list(xp.TUNABLE)
    assert named == {n: getattr(xp, n) for n in xp.TUNABLE}


def test_with_values_casts_and_refuses_unknown_names():
    t = xp.DEFAULT_TUNABLES.with_values({"min_keep": "4.0", "COSINE_FLOOR": "0.7"})
    assert t.min_keep == 4 and isinstance(t.min_keep, int) and t.cosine_floor == 0.7
    assert xp.DEFAULT_TUNABLES.min_keep == xp.MIN_KEEP  # the default is untouched
    with pytest.raises(ValueError, match="unknown tunable"):
        xp.DEFAULT_TUNABLES.with_values({"NOPE": 1})


def _hit(n: int, score: float):
    return SimpleNamespace(
        source_ref=SourceRef("memory", f"m{n}"), reason=xp.SEARCH_HIT, score=score
    )


def test_a_cut_reads_the_values_it_is_given_not_the_module():
    scores = (1.0, 0.97, 0.94, 0.9, 0.86, 0.82, 0.76, 0.72)
    items = [_hit(n, s) for n, s in enumerate(scores)]
    relevance = {i.source_ref.key(): i.score for i in items}
    loose, _ = xp.adaptive_cut(items, set(), relevance, t=xp.MODES["recall"].tunables)
    strict, _ = xp.adaptive_cut(items, set(), relevance)
    assert len(loose) == 8 and len(strict) == 6
    assert xp.COSINE_FLOOR == 0.8


# ── assemble_context(mode=...) ────────────────────────────────


@pytest.mark.parametrize(("query", "as_of_days"), ident.QUESTIONS)
async def test_no_mode_is_the_pinned_default(wired, monkeypatch, query, as_of_days):
    ident.build_world(wired)
    ident.install_conflict(monkeypatch)
    snap = await ident.snapshot_of(query, as_of_days, mode="")
    assert (ident._digest(snap.to_dict()), ident._digest(snap.compact())) == ident.EXPECTED[query]


def _without_note(snap: ContextSnapshot) -> dict:
    out = snapshot.without_timings(snap.to_dict())
    out["explanation"] = out["explanation"].split(" Precision mode ")[0]
    out["explanation"] = out["explanation"].split(" Eval-only experiments on: ")[0]
    return out


@pytest.mark.parametrize("name", ["recall", "precision"])
@pytest.mark.parametrize(("query", "as_of_days"), ident.QUESTIONS)
async def test_a_mode_is_its_experiment_set_with_its_own_values(
    xwired,  # noqa: F811 — the fixture
    monkeypatch,
    name,
    query,
    as_of_days,
):
    ident.build_world(xwired)
    ident.install_conflict(monkeypatch)
    m = xp.MODES[name]
    by_mode = await ident.snapshot_of(query, as_of_days, mode=name)
    by_hand = await ident.snapshot_of(
        query, as_of_days, experiments=m.experiments, tunables=m.tunables
    )
    assert _without_note(by_mode) == _without_note(by_hand)
    assert f"Precision mode {name}: {', '.join(xp.letters(m.experiments))}." in (
        by_mode.explanation
    )
    assert "Eval-only" not in by_mode.explanation


async def test_a_mode_with_free_experiments_or_values_is_refused(wired):
    with pytest.raises(ValueError, match="cannot be combined"):
        await assemble_context("q", now=NOW, mode="recall", experiments=frozenset({"A"}))
    with pytest.raises(ValueError, match="cannot be combined"):
        await assemble_context("q", now=NOW, mode="recall", tunables=xp.DEFAULT_TUNABLES)
    with pytest.raises(ValueError, match="unknown precision mode"):
        await assemble_context("q", now=NOW, mode="fast")


async def test_the_api_uses_the_configured_mode(monkeypatch):
    from life_graph.api import context as api

    seen_kw: list[dict] = []

    async def fake(query, **kw):
        seen_kw.append(kw)
        return _snap([])

    monkeypatch.setattr(api, "assemble_context", fake)
    monkeypatch.setattr(settings, "context_precision_mode", "")
    await api.context_snapshot(q="x", as_of=None)
    monkeypatch.setattr(settings, "context_precision_mode", "recall")
    await api.context_snapshot(q="x", as_of=None)
    assert [k["mode"] for k in seen_kw] == ["", "recall"]


# ── The comparison record ─────────────────────────────────────

SECRET = "SECRET-CONTENT the owner's insurance number"


def _item(mid: str, reason: str = "search_hit") -> ContextItem:
    return ContextItem(
        source_ref=SourceRef("memory", mid),
        dimension="preference",
        origin="user_stated",
        confirmed=True,
        evidence="said",
        label="owner said",
        status="active",
        reason=reason,
        score=0.8,
        valid_from=None,
        recorded_at=None,
        world_time_known=False,
        freshness="fresh",
        content=SECRET,
        fingerprint="abcdef0123456789",
    )


def _snap(items: list[ContextItem], **kw) -> ContextSnapshot:
    return ContextSnapshot(
        query="SECRET-QUERY",
        purpose="conversation",
        as_of=None,
        reference_time="2026-11-20T12:00:00+00:00",
        budget=DEFAULT_BUDGET,
        items=tuple(items),
        exclusions=(("experiment_budget", 2),),
        insufficient=False,
        explanation="SECRET-EXPLANATION",
        missing=("SECRET-TERM",),
        timings_ms=(("embed", 1.0), ("total", 3.0)),
        **kw,
    )


ALLOWED_KEYS = {
    "v",
    "mode",
    "experiments",
    "items",
    "counts",
    "kept",
    "dropped",
    "added",
    "exclusions",
    "timings_ms",
}


def _all_keys(obj) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _all_keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _all_keys(v)}
    return set()


def test_the_comparison_keeps_refs_labels_and_counts_only():
    default = _snap([_item("a"), _item("b"), _item("c")])
    moded = _snap([_item("c"), _item("a"), _item("d", "linked_evidence")])
    out = snapshot.precision_comparison(default, moded, "recall")
    assert set(out) == ALLOWED_KEYS
    assert (
        out["v"] == 1
        and out["mode"] == "recall"
        and out["experiments"] == ["B", "C", "F", "H", "I", "J", "K"]
    )
    assert out["kept"] == ["memory:a", "memory:c"]
    assert out["dropped"] == ["memory:b"]
    assert out["added"] == ["memory:d"]
    assert out["counts"] == {"default": 3, "mode": 3, "kept": 2, "dropped": 1, "added": 1}
    assert out["items"] == moded.compact()["items"]
    assert out["items"][2]["fp"] == "abcdef0123456789"
    assert out["exclusions"] == {"experiment_budget": 2}
    dumped = json.dumps(out)
    assert "SECRET" not in dumped
    assert not _all_keys(out) & {"content", "query", "missing", "explanation", "label"}


# ── shadow_precision: time-boxed, never raises ────────────────


@pytest.fixture
def fake_assemble(monkeypatch):
    calls: list[tuple[str, dict]] = []
    state = {"snap": _snap([_item("a")]), "raise": None, "sleep": 0.0}

    async def fake(query, **kw):
        calls.append((query, kw))
        if state["sleep"]:
            await asyncio.sleep(state["sleep"])
        if state["raise"] is not None:
            raise state["raise"]
        return state["snap"]

    monkeypatch.setattr(snapshot, "assemble_context", fake)
    return SimpleNamespace(calls=calls, state=state)


async def test_shadow_precision_builds_the_mode_at_the_default_reference_time(fake_assemble):
    default = dataclasses.replace(_snap([_item("a"), _item("b")]), query_embedding=(0.1, 0.2))
    out = await snapshot.shadow_precision(
        "t1", "personal: SECRET-QUERY?", None, "precision", default, timeout=1.0
    )
    assert out["counts"]["dropped"] == 1 and isinstance(out["ms"], int)
    assert out["mode"] == "precision"
    ((_, kw),) = fake_assemble.calls
    assert kw["mode"] == "precision"
    assert kw["now"].isoformat() == default.reference_time
    # The default snapshot's query embedding is reused, not made again.
    assert kw["query_embedding"] == (0.1, 0.2)
    assert "SECRET" not in json.dumps(out)


async def test_a_slow_mode_snapshot_is_cut_off(fake_assemble):
    fake_assemble.state["sleep"] = 0.5
    out = await snapshot.shadow_precision(
        "t1", "q", None, "recall", _snap([_item("a")]), timeout=0.01
    )
    assert out == {"error": "TimeoutError", "mode": "recall", "ms": out["ms"]}


async def test_no_time_left_builds_nothing(fake_assemble):
    out = await snapshot.shadow_precision("t1", "q", None, "recall", _snap([]), timeout=0)
    assert out["error"] == "TimeoutError" and fake_assemble.calls == []


async def test_a_failing_mode_snapshot_is_recorded_without_content(fake_assemble):
    fake_assemble.state["raise"] = RuntimeError(SECRET)
    out = await snapshot.shadow_precision("t1", "q", None, "recall", _snap([]), timeout=1.0)
    assert out["error"] == "RuntimeError" and "SECRET" not in json.dumps(out)


async def test_no_default_snapshot_means_no_comparison(fake_assemble):
    out = await snapshot.shadow_precision("t1", "q", None, "recall", None, timeout=1.0)
    assert out["error"] == snapshot.NO_BASELINE and fake_assemble.calls == []


async def test_an_unknown_mode_is_an_error_not_a_raise(fake_assemble):
    out = await snapshot.shadow_precision("t1", "q", None, "SECRET-mode", _snap([]), timeout=1.0)
    assert out["error"] == "ValueError" and out["mode"] == "other"
    assert fake_assemble.calls == []


# ── shadow_trace and the kernel gate ──────────────────────────


async def test_shadow_trace_adds_the_comparison_only_when_asked(monkeypatch):
    async def shadow_snapshot(tenant_id, message, history=None, **kw):
        return _snap([_item("a")]), {"items": []}

    async def shadow_precision(tenant_id, message, history, mode_name, default, *, timeout):
        assert default is not None and timeout == snapshot.SHADOW_PRECISION_TIMEOUT_S
        return {"mode": mode_name, "ms": 0}

    monkeypatch.setattr(snapshot, "shadow_snapshot", shadow_snapshot)
    monkeypatch.setattr(snapshot, "shadow_precision", shadow_precision)
    off = await changes.shadow_trace("t1", "q")
    assert set(off) == {"context_snapshot"}
    on = await changes.shadow_trace("t1", "q", precision="recall")
    assert on["context_precision"] == {"mode": "recall", "ms": 0}


@pytest.fixture
def kernel_built(monkeypatch):
    calls: list[dict] = []

    async def fake_assemble(query, **kw):
        calls.append(kw)
        ref = (NOW + timedelta(0)).isoformat()
        return dataclasses.replace(_snap([_item("a")]), reference_time=ref)

    monkeypatch.setattr(snapshot, "assemble_context", fake_assemble)
    return calls


async def test_kernel_precision_shadow_needs_the_snapshot_shadow(monkeypatch, kernel_built):
    monkeypatch.setattr(settings, "context_snapshot_shadow", False)
    monkeypatch.setattr(settings, "context_precision_shadow", True)
    result = await kernel._run(kernel.PERSONAL, {"allowed_tools": None})
    assert "context_precision" not in result["trace"] and kernel_built == []


async def test_kernel_precision_shadow_off_leaves_the_trace(monkeypatch, kernel_built):
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    monkeypatch.setattr(settings, "context_precision_shadow", False)
    result = await kernel._run(kernel.PERSONAL, {"allowed_tools": None})
    assert "context_precision" not in result["trace"]
    assert [kw.get("mode", "") for kw in kernel_built] == [""]


@pytest.mark.parametrize(("configured", "expected"), [("", "recall"), ("precision", "precision")])
async def test_kernel_precision_shadow_compares_the_configured_mode(
    monkeypatch, kernel_built, configured, expected
):
    monkeypatch.setattr(settings, "context_snapshot_shadow", True)
    monkeypatch.setattr(settings, "context_change_shadow", False)
    monkeypatch.setattr(settings, "context_precision_shadow", True)
    monkeypatch.setattr(settings, "context_precision_mode", configured)
    result = await kernel._run(kernel.PERSONAL, {"allowed_tools": None})
    record = result["trace"]["context_precision"]
    assert record["mode"] == expected and record["counts"]["kept"] == 1
    assert set(record) == ALLOWED_KEYS | {"ms"}
    assert "SECRET" not in json.dumps(result["trace"])
    # The default snapshot (the one change detection compares) is built without a mode.
    assert [kw.get("mode", "") for kw in kernel_built] == ["", expected]
    assert result["response"] == "ok"


# ── Review follow-ups: degraded baselines, own time box, embedding reuse, probe cache ──


async def test_a_degraded_default_snapshot_is_no_baseline(fake_assemble):
    degraded = dataclasses.replace(_snap([]), degraded=True)
    out = await snapshot.shadow_precision("t1", "q", None, "recall", degraded, timeout=1.0)
    assert out["error"] == snapshot.NO_BASELINE and fake_assemble.calls == []


async def test_failed_snapshots_say_degraded_and_a_real_one_does_not(wired, monkeypatch):
    class _NoVector:
        async def generate_embedding(self, text_):
            return None

    ok = await assemble_context("salary", now=NOW)
    assert ok.degraded is False and ok.query_embedding == (0.1, 0.2)
    empty = await assemble_context("   ", now=NOW)
    assert empty.degraded is True

    async def broken(*a, **kw):
        raise RuntimeError("read")

    monkeypatch.setattr(snapshot, "_decisions", broken)
    failed_read = await assemble_context("salary", now=NOW)
    assert failed_read.degraded is True and failed_read.items == ()
    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _NoVector())
    no_vector = await assemble_context("salary", now=NOW)
    assert no_vector.degraded is True
    # Neither field is part of the serialised forms (the pinned hashes hold).
    for snap in (ok, no_vector):
        assert "degraded" not in snap.to_dict() and "query_embedding" not in snap.to_dict()
        assert "degraded" not in snap.compact() and "query_embedding" not in snap.compact()


async def test_a_given_query_embedding_is_not_made_again(wired, monkeypatch):
    calls: list[str] = []

    class _Counting:
        async def generate_embedding(self, text_):
            calls.append(text_)
            return [0.1, 0.2]

    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Counting())
    snap = await assemble_context("salary", now=NOW, query_embedding=(0.1, 0.2))
    assert calls == [] and "embed" not in dict(snap.timings_ms)
    assert snap.degraded is False


async def test_compare_and_precision_each_get_their_own_box(monkeypatch):
    """A slow default snapshot no longer starves the comparison; the total stays bounded."""
    monkeypatch.setattr(snapshot, "SHADOW_TIMEOUT_S", 0.3)
    monkeypatch.setattr(snapshot, "SHADOW_PRECISION_TIMEOUT_S", 0.3)
    state = {"precision_sleep": 0.15}

    async def shadow_snapshot(tenant_id, message, history=None, **kw):
        await asyncio.sleep(0.25)  # most of the first box
        return _snap([_item("a"), _item("b")]), {"items": []}

    async def shadow_changes(tenant_id, snap, task_id, *, timeout):
        assert 0 < timeout <= 0.3
        await asyncio.sleep(0.01)
        return {"changes": [], "ms": 10}

    async def fake_assemble(query, **kw):
        await asyncio.sleep(state["precision_sleep"])
        return _snap([_item("a")])

    monkeypatch.setattr(snapshot, "shadow_snapshot", shadow_snapshot)
    monkeypatch.setattr(changes, "shadow_changes", shadow_changes)
    monkeypatch.setattr(snapshot, "assemble_context", fake_assemble)

    started = asyncio.get_running_loop().time()
    out = await changes.shadow_trace("t1", "q", compare=True, precision="recall")
    elapsed = asyncio.get_running_loop().time() - started
    assert out["context_changes"]["changes"] == []
    # Under the old shared box only ~0.04 s was left: this would have timed out.
    assert out["context_precision"]["counts"]["dropped"] == 1
    assert elapsed < 0.3 + 0.3 + 0.2

    state["precision_sleep"] = 5.0
    started = asyncio.get_running_loop().time()
    slow = await changes.shadow_trace("t1", "q", compare=True, precision="recall")
    elapsed = asyncio.get_running_loop().time() - started
    assert slow["context_precision"]["error"] == "TimeoutError"
    assert "changes" in slow["context_changes"]
    assert elapsed < 0.3 + 0.3 + 0.2


async def test_hub_probes_are_embedded_once_per_embedder(
    xwired,  # noqa: F811 — the fixture
    monkeypatch,
):
    probes: list[str] = []

    class _Counting:
        async def generate_embedding(self, text_):
            if text_ in xp.HUB_PROBES:
                probes.append(text_)
                return [0.3, 0.4]
            return [0.1, 0.2]

    one = _Counting()
    monkeypatch.setattr(runtime, "get_memory_manager", lambda: one)
    snapshot.clear_probe_cache()
    hits = [base._mem(f"hit {n}", id=ident._id(n)) for n in range(1, 6)]
    xwired["found"] = hits
    xwired["cosines"] = {str(h.id): 0.7 - n / 100 for n, h in enumerate(hits)}
    xwired["probe_cosines"] = {str(h.id): 0.1 for h in hits}
    first = await assemble_context("q", now=NOW, mode="precision")
    second = await assemble_context("q", now=NOW, mode="precision")
    assert len(probes) == len(xp.HUB_PROBES)
    assert _without_note(first) == _without_note(second)
    other = _Counting()  # another embedder: its own probe vectors
    monkeypatch.setattr(runtime, "get_memory_manager", lambda: other)
    await assemble_context("q", now=NOW, mode="precision")
    assert len(probes) == 2 * len(xp.HUB_PROBES)
    snapshot.clear_probe_cache()
    await assemble_context("q", now=NOW, mode="precision")
    assert len(probes) == 3 * len(xp.HUB_PROBES)
    await assemble_context("q", now=NOW, mode="recall")  # no hub penalty: no probes
    assert len(probes) == 3 * len(xp.HUB_PROBES)
