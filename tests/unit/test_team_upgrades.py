"""Team upgrades (2026-11-28): worker retry, per-worker agent/tier, notes board.

docs/specs/agent-drivers.md, "Team upgrades (2026-11-28)". Fakes only: no
database, no driver, no network.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pydantic import ValidationError

from life_graph.config import settings
from life_graph.drivers.escalation import Rung
from life_graph.drivers.plan_spec import (
    parse_task_agent,
    parse_task_files,
    parse_task_tier,
    plan_only_prefix,
)
from life_graph.models.db import AgentTask, DevTaskGroup
from life_graph.services.dev import tasks as dev_tasks
from life_graph.services.dev import team_notes, team_retry, team_rungs, teams
from tests.unit.fakes import FakeSession, session_factory

LADDER = [
    Rung("local", "ollama_chat/qwen3:14b"),
    Rung("local", "ollama_chat/qwen3-coder:30b"),
    Rung("claude_code"),
]


# ── Plan lines: Agent: / Tier: ────────────────────────────────


def test_a_plan_line_names_its_agent_and_tier():
    item = "Add the parser (AC-1) Files: a.py, tests/x.py Agent: code-fixer-auto Tier: best"
    assert parse_task_files(item) == ["a.py", "tests/x.py"]  # Agent/Tier are not paths
    assert parse_task_agent(item) == "code-fixer-auto"
    assert parse_task_tier(item) == "best"
    assert parse_task_tier("**Tier:** `Cheap`.") == "cheap"
    assert parse_task_agent("Persona: `reviewer`.") == "reviewer"
    # Unknown values come back as written, for the team's warning.
    assert parse_task_tier("Tier: superb") == "superb"
    assert parse_task_agent("plain task Files: a.py") is None
    assert parse_task_tier("plain task") is None
    assert "Tier: best" in plan_only_prefix(True)
    assert "Tier:" not in plan_only_prefix(False)


@pytest.mark.parametrize(
    ("tier", "size", "index"),
    [
        ("cheap", 3, 0),
        ("balanced", 3, 1),
        ("best", 3, 2),
        ("balanced", 2, 0),
        ("best", 2, 1),
        ("balanced", 4, 1),
        ("best", 1, 0),
        ("superb", 3, None),
        ("best", 0, None),
    ],
)
def test_tiers_map_to_ladder_positions(tier, size, index):
    assert team_rungs.tier_index(tier, size) == index


# ── Rung choice ───────────────────────────────────────────────


@pytest.fixture
def ladder(monkeypatch):
    """The 3-rung default ladder; ``refuse`` = labels the per-rung check refuses."""
    refuse: dict[str, str] = {}
    stopped = {"on": False}

    async def blocker(self, tenant_id, rung, *, is_top):
        why = refuse.get(rung.label)
        billing = "subscription" if rung.driver == "claude_code" else "local"
        return (None, why) if why else (SimpleNamespace(name=rung.driver, billing=billing), None)

    async def autonomy(_t):
        return stopped["on"]

    monkeypatch.setattr(team_rungs.escalation, "configured_ladder", lambda _r: list(LADDER))
    monkeypatch.setattr(team_rungs._Probe, "blocker", blocker)
    monkeypatch.setattr(team_rungs, "autonomy_stopped", autonomy)
    return SimpleNamespace(refuse=refuse, stopped=stopped)


async def test_a_best_tier_over_the_cap_falls_to_the_highest_allowed_rung(ladder):
    picker = team_rungs.RungPicker(session_factory(FakeSession()), "t1")
    ok = await picker.for_tier("best")
    assert ok.rung == LADDER[2] and ok.tier == "best" and not ok.refused
    ladder.refuse["claude_code"] = "top-rung cap reached (2 of 4 today)"
    capped = await picker.for_tier("best")
    assert capped.rung == LADDER[1] and capped.tier == "balanced"
    assert capped.refused == ["claude_code: top-rung cap reached (2 of 4 today)"]
    assert capped.pin()["driver_pin"] == "local"
    assert capped.pin()["team_rung"]["model"] == "ollama_chat/qwen3-coder:30b"
    cheap = await picker.for_tier("cheap")
    assert cheap.rung == LADDER[0]
    for label in ("local:ollama_chat/qwen3:14b", "local:ollama_chat/qwen3-coder:30b"):
        ladder.refuse[label] = "not available"
    none = await picker.for_tier("balanced")
    assert none.rung is None and none.pin() == {} and len(none.refused) == 3


async def test_the_probe_counts_its_own_top_rung_picks_against_the_cap(monkeypatch):
    async def usage(_sf, _t):
        return 0, 0

    class _Claude:
        name, billing = "claude_code", "subscription"

        async def available(self):
            return True

    monkeypatch.setattr(team_rungs.outcome_log, "top_tier_usage", usage)
    monkeypatch.setattr(
        team_rungs.escalation, "configured_ladder", lambda _r: [Rung("claude_code")]
    )
    monkeypatch.setattr("life_graph.drivers.ladder_steps.driver_registry.get", lambda _n: _Claude())
    monkeypatch.setattr(settings, "driver_accounts_enabled", False)
    monkeypatch.setattr(settings, "driver_escalation_top_daily_min", 1)
    monkeypatch.setattr(settings, "driver_escalation_top_share", 0.0)
    picker = team_rungs.RungPicker(session_factory(FakeSession()), "t1")
    first = await picker.for_tier("best")
    second = await picker.for_tier("best")
    assert first.rung == Rung("claude_code")
    assert second.rung is None and "top-rung cap reached" in second.refused[0]


async def test_a_retry_climbs_one_rung_or_stays_when_it_may_not(ladder):
    picker = team_rungs.RungPicker(session_factory(FakeSession()), "t1")
    up = await picker.for_retry(Rung("local", "qwen3:14b"))
    assert up.rung == LADDER[1] and up.why.startswith("retry one rung up")
    ladder.refuse["local:ollama_chat/qwen3-coder:30b"] = "not available"
    ladder.refuse["claude_code"] = "subscription accounts over_budget"
    same = await picker.for_retry(Rung("local", "qwen3:14b"))
    assert same.rung == LADDER[0] and "no higher rung may run" in same.why
    top = await picker.for_retry(Rung("claude_code"))
    assert top.rung == LADDER[2] and "already the top" in top.why
    ladder.refuse.clear()
    ladder.stopped["on"] = True
    paused = await picker.for_retry(Rung("local", "qwen3:14b"))
    assert paused.rung == LADDER[0] and "paused" in paused.why
    off = await picker.for_retry(Rung("cloud"))
    assert off.rung is None and off.pin() == {}


def test_the_model_a_pinned_worker_runs():
    assert team_rungs.pinned_model({"driver_pin": "local", "team_rung": {"model": "m"}}) == "m"
    assert team_rungs.pinned_model({"team_rung": {"model": "m"}}) is None
    assert team_rungs.pinned_model({"driver_pin": "claude_code", "team_rung": {}}) is None


def test_a_persona_that_names_a_driver_pins_it():
    assert team_rungs.persona_pins({"driver": "claude_code"}) == "claude_code"
    assert team_rungs.persona_pins({"driver": "auto"}) is None
    assert (
        team_rungs.persona_pins({"driver": "local", "properties": {"allow_escalation": True}})
        is None
    )
    assert team_rungs.persona_pins(None) is None


# ── Notes board: parsing ──────────────────────────────────────


def test_notes_are_read_from_the_last_notes_section_bounded_and_redacted():
    output = (
        "Done.\n## Notes for the team\n- old note\n\n"
        "## Summary\nstuff\n"
        "## Notes for the team\n"
        "intro text is ignored\n"
        "- The parser returns `Node`,\n  not a dict.\n"
        "* token is api_key=sk-abcdefghijklmnopqrstuvwxyz012345\n"
        f"- {'x' * 700}\n" + "".join(f"- n{i}\n" for i in range(30)) + "## After\n- not a note\n"
    )
    notes = team_notes.parse_notes(output)
    assert len(notes) == team_notes.MAX_NOTES_PER_WORKER
    assert notes[0] == "The parser returns `Node`, not a dict."
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in notes[1] and "REDACTED" in notes[1]
    assert len(notes[2]) == team_notes.MAX_NOTE_CHARS and notes[2].endswith("…")
    assert "not a note" not in notes and "old note" not in notes
    assert team_notes.parse_notes("no section") == []
    assert team_notes.parse_notes(None) == []


def test_the_notes_block_is_replaced_not_stacked():
    one = [{"author_index": 1, "author_title": "Add a", "text": "a is async"}]
    text = team_notes.with_notes("Do the task.", one)
    assert team_notes.BLOCK_START in text and "[task 1 (Add a)] a is async" in text
    two = [*one, {"author_index": 2, "text": "b too"}]
    again = team_notes.with_notes(text, two)
    assert again.count(team_notes.BLOCK_START) == 1 and "b too" in again
    assert team_notes.with_notes(again, []) == "Do the task."
    assert team_notes.notes_for([{"author_wave": 0}, {"author_wave": 1}], 1) == [{"author_wave": 0}]
    assert team_notes.notes_for([{"author_wave": 0}], None, integration=True) == [
        {"author_wave": 0}
    ]
    assert team_notes.wave_of([[0, 2], [1]], 2) == 1


def test_workers_are_told_they_may_leave_notes():
    text = teams.worker_instruction("Build", "spec", "1. a", 1, 2, ["a.py"])
    assert team_notes.NOTES_HEADING in text and "Never put secrets" in text


# ── Fixtures for team rows ────────────────────────────────────


def _task(group, role="worker", index=1, status="queued", **props) -> AgentTask:
    return AgentTask(
        id=uuid.uuid4(), tenant_id="t1", agent_name="dev_task", status=status,
        properties={"kind": "dev_task", "run_mode": "queue", "team_role": role,
                    "plan_group_id": str(group.id), "plan_task_index": index,
                    "plan_task_id": PLAN_ID, "project_name": "p", **props},
        status_history=[], assigned_agent="code-fixer-auto", project_id=uuid.uuid4(),
        title=f"task {index}", instructions=f"Do task {index}.", task_type="code_change",
    )  # fmt: skip


PLAN_ID = str(uuid.uuid4())


def _group(status="running", **props) -> DevTaskGroup:
    return DevTaskGroup(
        id=uuid.uuid4(), tenant_id="t1", kind="team", status=status, source_ref=PLAN_ID,
        properties={"waves": [[0], [1]], **props},
    )  # fmt: skip


@pytest.fixture
def made(monkeypatch, ladder):
    """Fake task creation, persona lookup and the "ran on" read; records calls."""
    calls: list[dict] = []
    events: list[tuple[str, str]] = []

    async def create(_sf, tenant_id, **kw):
        calls.append({"tenant_id": tenant_id, **kw})
        return {"id": str(uuid.uuid4())}

    async def persona(_sf, _t, name):
        return None if name == "ghost" else {"driver": "auto", "is_active": True}

    async def ran_on(_s, _t, task):
        return Rung("local", "qwen3:14b")

    async def quiet(*_a, **_k):
        return None

    monkeypatch.setattr(dev_tasks, "create_dev_task", create)
    monkeypatch.setattr(dev_tasks, "_emit_bus", quiet)
    monkeypatch.setattr(dev_tasks, "request_cancel", lambda *_a: quiet())
    monkeypatch.setattr(team_rungs, "get_persona", persona)
    monkeypatch.setattr(team_rungs, "ran_on", ran_on)
    monkeypatch.setattr(teams, "_notify_failed", quiet)
    monkeypatch.setattr(
        team_retry.task_events, "emit", lambda _t, tid, kind, content, **_k: events.append(
            (tid, content))
    )  # fmt: skip
    return SimpleNamespace(calls=calls, events=events, ladder=ladder)


def _team(**gprops):
    group = _group(**gprops)
    a = _task(group, index=1, status="failed", team_attempt=1)
    a.error = "verification failed (pytest)"
    b = _task(group, index=2, depends_on=[str(a.id)], seed_from=[str(a.id)], deps_pending=True,
              dependency_wait={"waiting_on": [str(a.id)], "since": "x"})  # fmt: skip
    integ = _task(group, role="integration", index=3, depends_on=[str(a.id), str(b.id)],
                  seed_from=[str(a.id), str(b.id)], deps_pending=True)  # fmt: skip
    group.properties["worker_ids"] = [str(a.id), str(b.id)]
    group.properties["integration_task_id"] = str(integ.id)
    return group, a, b, integ


# ── Retry in the runner loop ──────────────────────────────────


async def test_a_failed_worker_is_retried_one_rung_up_and_the_team_keeps_going(made):
    group, a, b, integ = _team()
    rows = [a, b, integ]
    session = FakeSession([group], rows, [], [group], rows)

    changes = await teams.reconcile(session_factory(session))

    assert changes == [] and group.status == "running"
    (call,) = made.calls
    props = call["properties"]
    assert props["team_attempt"] == 2 and props["team_replaces"] == str(a.id)
    assert props["driver_pin"] == "local"
    assert props["team_rung"]["label"] == "local:ollama_chat/qwen3-coder:30b"
    assert props["team_retry_reason"] == "verification failed (pytest)"
    assert props["team_retry_by"] == "team"
    assert team_retry.FAILURE_START in call["instruction"]
    assert "verification failed (pytest)" in call["instruction"]
    assert call["depends_on"] is None and call["start"] is False
    new = props and made.calls[0]
    assert new is not None
    # The dependents now wait on the retry instead of being cancelled.
    retry_id = next(iter(group.properties["worker_ids"]))
    assert retry_id != str(a.id)
    assert b.properties["depends_on"] == [retry_id]
    assert b.properties["seed_from"] == [retry_id]
    assert b.properties["dependency_wait"]["waiting_on"] == [retry_id]
    assert integ.properties["depends_on"][0] == retry_id
    assert group.properties["retry_pending"] == {}
    assert "worker 1 retried (attempt 2" in group.properties["history"][-1]["why"]
    assert any("retry as" in text for _tid, text in made.events)


async def test_a_retry_stays_on_the_same_rung_when_no_higher_one_may_run(made):
    made.ladder.refuse["local:ollama_chat/qwen3-coder:30b"] = "not available"
    made.ladder.refuse["claude_code"] = "top-rung cap reached (3 of 4 today)"
    group, a, b, integ = _team()
    rows = [a, b, integ]
    await teams.reconcile(session_factory(FakeSession([group], rows, [], [group], rows)))
    props = made.calls[0]["properties"]
    assert props["team_rung"]["label"] == "local:ollama_chat/qwen3:14b"
    assert "no higher rung may run" in props["team_retry_why"]
    assert group.status == "running"


async def test_a_worker_out_of_retries_fails_the_team(made):
    group, a, b, integ = _team()
    a2 = _task(group, index=1, status="failed", team_attempt=2, team_replaces=str(a.id))
    rows = [a, a2, b, integ]
    session = FakeSession([group], rows, [])

    changes = await teams.reconcile(session_factory(session))

    assert made.calls == []
    assert group.status == "failed" and changes[0]["status"] == "failed"
    assert group.properties["failed_task_id"] == str(a2.id)
    assert sorted(group.properties["team_cancelled"]) == sorted([str(b.id), str(integ.id)])
    # b was re-pointed at the newest attempt before the team failed.
    assert b.properties["depends_on"] == [str(a2.id)]


async def test_a_cancelled_worker_is_never_retried(made):
    group, a, b, integ = _team()
    a.status = "cancelled"  # the owner's cancel, or the kill switch's
    await teams.reconcile(session_factory(FakeSession([group], [a, b, integ], [])))
    assert made.calls == [] and group.status == "failed"


async def test_retries_off_is_the_old_behaviour(made, monkeypatch):
    monkeypatch.setattr(settings, "driver_team_worker_retries", 0)
    group, a, b, integ = _team()
    await teams.reconcile(session_factory(FakeSession([group], [a, b, integ], [])))
    assert made.calls == [] and group.status == "failed"


async def test_a_retry_that_could_not_be_queued_fails_the_team_next_pass(made):
    group, a, b, integ = _team(retry_pending={})
    group.properties["retry_pending"] = {str(a.id): "earlier"}
    await teams.reconcile(session_factory(FakeSession([group], [a, b, integ], [])))
    assert made.calls == [] and group.status == "failed"


# ── The owner's retry ─────────────────────────────────────────


def _failed_team():
    group, a, b, integ = _team()
    group.status = "failed"
    b.status, integ.status = "cancelled", "cancelled"
    group.properties.update(
        {"failed_task_id": str(a.id), "reason": f"worker {str(a.id)[:8]} failed",
         "team_cancelled": [str(b.id), str(integ.id)]}
    )  # fmt: skip
    return group, a, b, integ


async def test_the_owner_retry_reopens_a_team_that_failed_on_that_worker(made):
    group, a, b, integ = _failed_team()
    session = FakeSession(a, group, [a, b, integ])

    data = await team_retry.owner_retry(
        session_factory(session), "t1", PLAN_ID, str(a.id), tier="best", by="owner"
    )

    assert data["reopened"] is True and group.status == "running"
    retry, b2, i2 = made.calls
    assert retry["properties"]["team_replaces"] == str(a.id)
    assert retry["properties"]["team_attempt"] == 2
    assert retry["properties"]["team_tier"] == {"requested": "best", "resolved": "best"}
    assert retry["properties"]["driver_pin"] == "claude_code"
    assert retry["properties"]["team_retry_by"] == "owner"
    retry_id = data["retry"]["task_id"]
    # The siblings the team cancelled are queued again, wired to the retry.
    assert b2["properties"]["team_replaces"] == str(b.id)
    assert b2["properties"]["team_attempt"] == 1
    assert b2["depends_on"] == [retry_id]
    assert i2["properties"]["team_role"] == "integration"
    b2_id = data["requeued"][0]["task_id"]
    assert i2["depends_on"] == [retry_id, b2_id]
    props = group.properties
    assert props["worker_ids"] == [retry_id, b2_id]
    assert props["integration_task_id"] == data["requeued"][1]["task_id"]
    assert "failed_task_id" not in props and "reason" not in props
    assert props["team_cancelled"] == [] and props["reopened"] == 1
    assert props["history"][-1]["why"].startswith("reopened")


async def test_the_owner_retry_is_refused_when_it_cannot_help(made):
    group, a, b, integ = _failed_team()
    sf = session_factory(FakeSession(b, group, [a, b, integ]))
    with pytest.raises(team_retry.TeamError) as err:
        await team_retry.owner_retry(sf, "t1", PLAN_ID, str(b.id))
    assert err.value.code == "failed_elsewhere" and err.value.http_status == 409

    group2, a2, b2, integ2 = _team()
    sf = session_factory(FakeSession(b2, group2, [a2, b2, integ2]))
    with pytest.raises(team_retry.TeamError) as err:
        await team_retry.owner_retry(sf, "t1", PLAN_ID, str(b2.id))  # b2 is queued
    assert err.value.code == "not_failed"

    newer = _task(group2, index=1, status="queued", team_replaces=str(a2.id))
    sf = session_factory(FakeSession(a2, group2, [a2, newer, b2, integ2]))
    with pytest.raises(team_retry.TeamError) as err:
        await team_retry.owner_retry(sf, "t1", PLAN_ID, str(a2.id))
    assert err.value.code == "superseded"

    sf = session_factory(FakeSession(a2, group2, [a2, b2, integ2]))
    with pytest.raises(team_retry.TeamError) as err:
        await team_retry.owner_retry(sf, "t1", str(uuid.uuid4()), str(a2.id))
    assert err.value.http_status == 404

    with pytest.raises(team_retry.TeamError) as err:
        await team_retry.owner_retry(sf, "t1", PLAN_ID, str(a2.id), persona="ghost")
    assert err.value.code == "unknown_persona" and err.value.http_status == 422
    assert made.calls == []


async def test_the_owner_retry_of_a_running_team_does_not_reopen_anything(made):
    group, a, b, integ = _team()
    data = await team_retry.owner_retry(
        session_factory(FakeSession(a, group, [a, b, integ])), "t1", PLAN_ID, str(a.id),
        persona="code-fixer-auto",
    )  # fmt: skip
    assert data["reopened"] is False and data["requeued"] == []
    assert len(made.calls) == 1 and made.calls[0]["persona_name"] == "code-fixer-auto"
    assert b.properties["depends_on"] == [data["retry"]["task_id"]]  # waits on the retry
    assert group.properties["worker_ids"][0] == data["retry"]["task_id"]


# ── Agent / Tier at fan-out ───────────────────────────────────


class _Store(FakeSession):
    async def get(self, model, pk, **_k):
        return next((o for o in self.added if getattr(o, "id", None) == pk), None)


async def _fan_out(items, *, persona="code-fixer-auto", plan=None):
    store = _Store(plan)
    team = await teams.fan_out(
        session_factory(store), "t1", plan_task_id=str(plan.id) if plan else "plan-1",
        project={"id": str(uuid.uuid4()), "name": "p"}, persona_name=persona,
        instruction="Build", spec="spec", items=items, cited=[[] for _ in items], defined=[],
        criteria_block=lambda _ids: "", bound_tests=lambda _ids: [],
    )  # fmt: skip
    group = next(o for o in store.added if isinstance(o, DevTaskGroup))
    return team, group


async def test_agent_and_tier_lines_choose_each_workers_persona_and_rung(made):
    made.ladder.refuse["claude_code"] = "top-rung cap reached (2 of 2 today)"
    team, group = await _fan_out(
        [
            "Add a Files: a.py Agent: ghost",
            "Add b Files: b.py Tier: superb",
            "Add c Files: c.py Tier: best Agent: code-fixer-opus",
            "Add d Files: d.py",
        ]
    )
    w1, w2, w3, w4, integ = made.calls
    assert w1["persona_name"] == "code-fixer-auto"
    assert w1["properties"]["team_agent"] == {"requested": "ghost", "resolved": "code-fixer-auto"}
    assert "driver_pin" not in w2["properties"]
    assert w3["persona_name"] == "code-fixer-opus"
    assert w3["properties"]["team_tier"] == {"requested": "best", "resolved": "balanced"}
    assert w3["properties"]["team_rung"]["label"] == "local:ollama_chat/qwen3-coder:30b"
    assert "driver_pin" not in w4["properties"]  # no Agent/Tier: today's selection
    assert w4["properties"]["team_agent"]["requested"] is None
    warnings = group.properties["warnings"]
    assert any("unknown agent 'ghost'" in w for w in warnings)
    assert any("unknown tier 'superb'" in w for w in warnings)
    assert any("tier best -> local:ollama_chat/qwen3-coder:30b" in w for w in warnings)
    assert team["warnings"] == warnings


async def test_a_persona_pin_wins_over_a_tier_and_plan_defaults_apply(made, monkeypatch):
    async def persona(_sf, _t, name):
        return {"driver": "claude_code"} if name == "code-fixer" else {"driver": "auto"}

    monkeypatch.setattr(team_rungs, "get_persona", persona)
    plan = AgentTask(
        id=uuid.uuid4(), tenant_id="t1", agent_name="dev_task", status="completed",
        properties={"kind": "dev_task", "team_worker_persona": "code-fixer-auto",
                    "team_worker_tier": "cheap"},
    )  # fmt: skip
    _team_data, group = await _fan_out(
        ["Add a Files: a.py", "Add b Files: b.py Agent: code-fixer Tier: best"], plan=plan
    )
    w1, w2, _integ = made.calls
    assert w1["persona_name"] == "code-fixer-auto"
    assert w1["properties"]["team_rung"]["label"] == "local:ollama_chat/qwen3:14b"
    assert w1["properties"]["team_tier"] == {"requested": "cheap", "resolved": "cheap"}
    assert w2["persona_name"] == "code-fixer" and "driver_pin" not in w2["properties"]
    assert any(
        "persona code-fixer pins driver claude_code" in w for w in group.properties["warnings"]
    )
    assert group.properties["defaults"] == {"persona": "code-fixer-auto", "tier": "cheap"}


# ── Notes board in the runner loop ────────────────────────────


async def test_notes_reach_later_waves_and_the_integration_task_only_in_their_team(made):
    group = _group(waves=[[0, 2], [1]])
    w1 = _task(group, index=1, status="completed")
    w1.result = {"output": "Done.\n## Notes for the team\n- `parse()` now returns Node\n"}
    w2 = _task(group, index=2, depends_on=[str(w1.id)], deps_pending=True)
    w3 = _task(group, index=3)  # same wave as the author
    integ = _task(group, role="integration", index=4, deps_pending=True)
    other = _group(waves=[[0], [1]])
    stranger = _task(other, index=2)
    session = FakeSession([group, other], [w1, w2, w3, integ], [], [stranger])

    await teams.reconcile(session_factory(session))

    assert "`parse()` now returns Node" in w2.instructions
    assert team_notes.BLOCK_START in integ.instructions
    assert w3.instructions == "Do task 3."
    assert stranger.instructions == "Do task 2."
    (note,) = group.properties["notes"]
    assert note["author_index"] == 1 and note["task_id"] == str(w1.id)
    assert group.properties["notes_read"] == [str(w1.id)]
    assert other.properties.get("notes") is None
    # Read once: a second pass adds nothing.
    await teams.reconcile(session_factory(FakeSession([group], [w1, w2, w3, integ], [])))
    assert len(group.properties["notes"]) == 1
    assert w2.instructions.count(team_notes.BLOCK_START) == 1


async def test_a_retry_gets_the_notes_of_earlier_waves(made):
    group, a, b, integ = _team()
    b.status = "failed"
    b.properties.update({"deps_pending": None, "team_attempt": 1})
    a.status = "completed"
    group.properties["notes"] = [
        {"author_index": 1, "author_wave": 0, "text": "use Node", "task_id": str(a.id)}
    ]
    group.properties["notes_read"] = [str(a.id)]
    rows = [a, b, integ]
    await teams.reconcile(session_factory(FakeSession([group], rows, [], [group], rows)))
    (call,) = made.calls
    assert "use Node" in call["instruction"] and call["depends_on"] == [str(a.id)]


# ── Team view ─────────────────────────────────────────────────


async def test_the_team_view_shows_attempts_rungs_agents_notes_and_warnings():
    group = _group(
        notes=[{"author_index": 1, "author_title": "t", "task_id": "x", "text": "n", "at": "z",
                "author_wave": 0}],
        warnings=["task 2: unknown tier 'superb' (use cheap, balanced, best); ignored"],
    )  # fmt: skip
    a1 = _task(group, index=1, status="failed", team_attempt=1,
               team_tier={"requested": "cheap", "resolved": "cheap"})  # fmt: skip
    a2 = _task(
        group, index=1, status="running", team_attempt=2, team_replaces=str(a1.id),
        team_retry_reason="verification failed", team_retry_by="team",
        team_retry_why="retry one rung up from local:qwen3:14b", driver_pin="local",
        team_rung={"label": "local:ollama_chat/qwen3-coder:30b"},
        team_agent={"requested": None, "resolved": "code-fixer-auto"},
    )  # fmt: skip
    integ = _task(group, role="integration", index=2)
    session = FakeSession(
        [(str(a1.id), "local", "ollama_chat/qwen3:14b")], objects={(DevTaskGroup, group.id): group}
    )

    view = await teams.team_view(session, "t1", [a1, a2, integ], {})

    (row,) = view["workers"]
    assert row["task_id"] == str(a2.id) and row["attempts"] == 2
    assert row["attempt_task_ids"] == [str(a1.id), str(a2.id)]
    assert row["rungs"] == ["local:ollama_chat/qwen3:14b", "local:ollama_chat/qwen3-coder:30b"]
    assert row["agent"] == {"requested": None, "resolved": "code-fixer-auto"}
    assert row["retry_reasons"] == [
        {"attempt": 2, "reason": "verification failed", "by": "team",
         "why": "retry one rung up from local:qwen3:14b"}
    ]  # fmt: skip
    assert row["rung"] == "local:ollama_chat/qwen3-coder:30b"
    assert view["notes"] == [
        {"author_index": 1, "author_title": "t", "task_id": "x", "text": "n", "at": "z"}
    ]
    assert view["warnings"][0].startswith("task 2: unknown tier")
    assert view["integration"]["attempts"] == 1
    assert view["retries_per_worker"] == settings.driver_team_worker_retries


# ── API ───────────────────────────────────────────────────────


OWNER_KEY = "owner-key-0123456789"
SERVICE_KEY = "svc-key-9876543210"


@pytest_asyncio.fixture
async def client(monkeypatch):
    from life_graph.api import drivers_automation as api
    from life_graph.api.middleware import TenantMiddleware
    from life_graph.core.tenant import get_current_tenant_id

    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{SERVICE_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    seen: dict = {}

    async def retry(_sf, tenant_id, plan_id, task_id, **kw):
        seen.update(kw, tenant=tenant_id, plan=plan_id, task=task_id)
        if kw.get("persona") == "busy":
            raise team_retry.TeamError("team_busy", "the team is integrating")
        return {"reopened": True, "retry": {"task_id": "new"}}

    monkeypatch.setattr(api._team_retry, "owner_retry", retry)
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_current_tenant_id] = lambda: "raja"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield SimpleNamespace(http=c, seen=seen)


def _as(key):
    return {"Authorization": f"Bearer {key}", "X-Tenant-ID": "raja"}


async def test_the_worker_retry_route(client):
    c = client.http
    plan, task = str(uuid.uuid4()), str(uuid.uuid4())
    url = f"/api/v1/kernel/drivers/plans/{plan}/workers/{task}/retry"
    r = await c.post(url, json={}, headers=_as(SERVICE_KEY))
    assert r.status_code == 403
    r = await c.post(url, json={"tier": "best"}, headers=_as(OWNER_KEY))
    assert r.status_code == 202 and r.json()["data"]["reopened"] is True
    assert client.seen["tier"] == "best" and client.seen["persona"] is None
    assert client.seen["plan"] == plan and client.seen["tenant"] == "raja"
    r = await c.post(url, headers=_as(OWNER_KEY))  # no body
    assert r.status_code == 202 and client.seen["tier"] is None
    r = await c.post(url, json={"persona": "busy"}, headers=_as(OWNER_KEY))
    assert r.status_code == 409 and r.json()["detail"].startswith("team_busy")
    r = await c.post(url, json={"tier": "superb"}, headers=_as(OWNER_KEY))
    assert r.status_code == 422
    r = await c.post(url, json={"model": "x"}, headers=_as(OWNER_KEY))
    assert r.status_code == 422
    bad = f"/api/v1/kernel/drivers/plans/nope/workers/{task}/retry"
    r = await c.post(bad, json={}, headers=_as(OWNER_KEY))
    assert r.status_code == 400


def test_a_plan_task_takes_the_team_worker_defaults():
    from life_graph.api.drivers import DevTaskCreate

    body = DevTaskCreate(
        instruction="plan it", project_id="p", plan_only=True,
        team_worker_persona="code-fixer-auto", team_worker_tier="balanced",
    )  # fmt: skip
    assert body.team_worker_tier == "balanced"
    assert DevTaskCreate(instruction="plan it", project_id="p").team_worker_tier is None
    with pytest.raises(ValidationError):
        DevTaskCreate(instruction="plan it", project_id="p", team_worker_tier="superb")


# ── The dispatcher hook ───────────────────────────────────────


async def test_the_dispatcher_hook_runs_the_rungs_model_and_counts_the_top():
    group = _group()
    worker = _task(group, driver_pin="local",
                   team_rung={"driver": "local", "model": "ollama_chat/qwen3-coder:30b",
                              "tier": "balanced"})  # fmt: skip
    top = _task(
        group, driver_pin="claude_code", team_rung={"driver": "claude_code", "tier": "best"}
    )

    def run_for(task, driver):
        return SimpleNamespace(
            driver_pin=task.properties["driver_pin"], packet=SimpleNamespace(persona_model=None),
            session=FakeSession(objects={(AgentTask, task.id): task}), task_id=str(task.id),
            tenant_id="t1", driver=SimpleNamespace(billing=driver), reached_top=False,
        )  # fmt: skip

    run = run_for(worker, "local")
    await team_rungs.apply_team_rung(run)
    assert run.packet.persona_model == "ollama_chat/qwen3-coder:30b" and run.reached_top is False
    run = run_for(top, "subscription")
    await team_rungs.apply_team_rung(run)
    assert run.packet.persona_model is None and run.reached_top is True
    run = run_for(top, "subscription")
    run.tenant_id = "t2"  # another tenant's row is never read as this run's
    await team_rungs.apply_team_rung(run)
    assert run.reached_top is False
    run.driver_pin = None
    await team_rungs.apply_team_rung(run)  # not pinned: nothing to do
