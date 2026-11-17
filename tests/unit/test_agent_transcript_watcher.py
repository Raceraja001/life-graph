"""``AgentTranscriptWatcher.execute()`` end to end over real files on disk.

Transcripts are written to ``tmp_path``, the capture spine runs for real
against a ``FakeSession``, and the distiller is a stub. What these tests are
actually guarding is the ordering: a watermark must never advance past bytes
whose turns were not ingested, and a distiller that falls over must not take
the ingest half down with it.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from life_graph.models.db import CaptureEvent
from life_graph.services import skill_distiller as distiller_module
from life_graph.watchers.agent_transcripts.watcher import (
    MODALITY,
    SURFACE,
    AgentTranscriptWatcher,
)
from life_graph.watchers.agent_transcripts.watermark import WatermarkStore
from life_graph.watchers.base import BaseWatcher, Severity
from tests.unit.fakes import FakeSession, session_factory

TENANT = "personal"

TURN = [
    {
        "type": "user",
        "sessionId": "sess-a",
        "cwd": "/home/raja/projects/life-graph",
        "timestamp": "2026-11-14T07:00:00.000Z",
        "message": {"role": "user", "content": "the alembic upgrade fails on a fresh database"},
    },
    {
        "type": "assistant",
        "sessionId": "sess-a",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "Bash",
                    "input": {"command": "alembic upgrade head"},
                }
            ],
        },
    },
    {
        "type": "user",
        "sessionId": "sess-a",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "content": "ERROR: relation 'memories' already exists",
                    "is_error": True,
                }
            ],
        },
    },
    {
        "type": "assistant",
        "sessionId": "sess-a",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t2",
                    "name": "Bash",
                    "input": {"command": "alembic stamp head"},
                }
            ],
        },
    },
    {
        "type": "user",
        "sessionId": "sess-a",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "done"}],
        },
    },
    {
        "type": "assistant",
        "sessionId": "sess-a",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Stamped the baseline, then upgraded."}],
        },
    },
]


class StubDistiller:
    """A distiller that accepts everything and records what it was handed."""

    def __init__(self, *, result=None, raises: Exception | None = None):
        self.seen = []
        self._result = result
        self._raises = raises

    def filter_candidate(self, session_slice) -> bool:
        return True

    async def distill(self, session_slice, *, dry_run: bool = False):
        self.seen.append(session_slice)
        if self._raises:
            raise self._raises
        return self._result or distiller_module.DistillationResult(action="NOOP")


def write_transcript(tmp_path, records=TURN, name="sess-a.jsonl", seconds_old=600):
    """A settled transcript file under a Claude-Code-shaped directory."""
    path = tmp_path / "-home-raja-projects-life-graph" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    past = time.time() - seconds_old
    os.utime(path, (past, past))
    return path


def make_watcher(tmp_path, session=None, **settings):
    """A watcher reading *tmp_path* with its state file beside it."""
    fake = session if session is not None else FakeSession()
    watcher = AgentTranscriptWatcher(
        tenant_id=TENANT,
        session_factory=session_factory(fake),
        settings={
            "base_dirs": [tmp_path],
            "state_path": str(tmp_path / "state.json"),
            "agents": ["claude"],
            "distill": False,
            **settings,
        },
    )
    return watcher, fake


def captures(fake: FakeSession) -> list[CaptureEvent]:
    return [obj for obj in fake.added if isinstance(obj, CaptureEvent)]


# ── Ingest ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_ingests_each_turn_as_one_capture_event(tmp_path):
    write_transcript(tmp_path)
    watcher, fake = make_watcher(tmp_path)

    await watcher.execute()

    assert len(captures(fake)) == 1
    event = captures(fake)[0]
    assert event.tenant_id == TENANT
    assert event.surface == SURFACE
    assert event.modality == MODALITY
    assert event.properties == {
        "agent_type": "claude_code",
        "project": "life-graph",
        "session_id": "sess-a",
        "has_errors": True,
        "has_fixes": True,
        "file_path": str(tmp_path / "-home-raja-projects-life-graph" / "sess-a.jsonl"),
        "tool_count": 2,
    }
    assert "alembic upgrade head" in event.content
    assert event.occurred_at.isoformat().startswith("2026-11-14T07:00")
    assert fake.commits == 1


@pytest.mark.asyncio
async def test_nul_bytes_in_tool_output_do_not_reach_postgres(tmp_path):
    """PostgreSQL text cannot hold U+0000; one such capture once blocked a queue."""
    records = [
        {
            "type": "user",
            "sessionId": "s",
            "cwd": "/p",
            "message": {"role": "user", "content": "run the binary and fix the crash"},
        },
        {
            "type": "assistant",
            "sessionId": "s",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t", "name": "Bash", "input": {"command": "./a.out"}}
                ],
            },
        },
        {
            "type": "user",
            "sessionId": "s",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t",
                        "content": "segfault\x00\x00at 0x0",
                        "is_error": True,
                    }
                ],
            },
        },
    ]
    write_transcript(tmp_path, records)
    watcher, fake = make_watcher(tmp_path)

    await watcher.execute()

    event = captures(fake)[0]
    assert "\x00" not in event.content
    assert "\x00" not in json.dumps(event.properties)


@pytest.mark.asyncio
async def test_a_second_pass_reads_only_the_new_bytes(tmp_path):
    path = write_transcript(tmp_path)
    watcher, fake = make_watcher(tmp_path)
    await watcher.execute()
    assert len(captures(fake)) == 1

    watcher2, fake2 = make_watcher(tmp_path)
    await watcher2.execute()
    assert captures(fake2) == []

    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": "sess-a",
                    "cwd": "/home/raja/projects/life-graph",
                    "message": {"role": "user", "content": "now add a downgrade step"},
                }
            )
            + "\n"
        )
    past = time.time() - 600
    os.utime(path, (past, past))

    watcher3, fake3 = make_watcher(tmp_path)
    await watcher3.execute()
    assert len(captures(fake3)) == 1
    assert "now add a downgrade step" in captures(fake3)[0].content


@pytest.mark.asyncio
async def test_a_transcript_still_being_written_is_left_alone(tmp_path):
    write_transcript(tmp_path, seconds_old=0)
    watcher, fake = make_watcher(tmp_path)

    events = await watcher.execute()

    assert captures(fake) == []
    assert events == []
    assert not (tmp_path / "state.json").exists()


@pytest.mark.asyncio
async def test_the_watermark_advances_only_after_the_turns_are_ingested(tmp_path):
    path = write_transcript(tmp_path)
    watcher, _ = make_watcher(tmp_path)
    await watcher.execute()

    store = WatermarkStore(state_path=tmp_path / "state.json")
    offset, mtime = store.get_watermark(path)
    assert offset == path.stat().st_size
    assert mtime == pytest.approx(path.stat().st_mtime)
    assert store.session_id(path) == "sess-a"


@pytest.mark.asyncio
async def test_a_file_whose_turns_could_not_be_ingested_is_not_marked_read(tmp_path):
    """A failing database must leave the bytes to be replayed next pass."""
    path = write_transcript(tmp_path)

    class Exploding(FakeSession):
        async def flush(self):
            raise RuntimeError("database is gone")

    watcher, _ = make_watcher(tmp_path, session=Exploding())
    events = await watcher.execute()

    assert events == []
    assert not (tmp_path / "state.json").exists()
    assert WatermarkStore(state_path=tmp_path / "state.json").get_watermark(path) == (0, 0.0)


@pytest.mark.asyncio
async def test_a_held_file_is_replayed_on_the_next_pass(tmp_path):
    """The whole point of holding the watermark: the turn still gets in."""
    write_transcript(tmp_path)

    class Exploding(FakeSession):
        async def flush(self):
            raise RuntimeError("database is gone")

    failing, _ = make_watcher(tmp_path, session=Exploding())
    await failing.execute()

    recovered, fake = make_watcher(tmp_path)
    await recovered.execute()

    assert len(captures(fake)) == 1
    assert "alembic upgrade head" in captures(fake)[0].content


@pytest.mark.asyncio
async def test_several_transcripts_are_harvested_in_one_pass(tmp_path):
    write_transcript(tmp_path, name="a.jsonl")
    write_transcript(tmp_path, name="b.jsonl")
    watcher, fake = make_watcher(tmp_path)

    await watcher.execute()

    assert len(captures(fake)) == 2


@pytest.mark.asyncio
async def test_the_file_limit_caps_one_pass(tmp_path):
    for name in ("a.jsonl", "b.jsonl", "c.jsonl"):
        write_transcript(tmp_path, name=name)
    watcher, fake = make_watcher(tmp_path, file_limit=2)

    await watcher.execute()

    assert len(captures(fake)) == 2


# ── Events ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_harvest_reports_what_it_read(tmp_path):
    write_transcript(tmp_path)
    watcher, _ = make_watcher(tmp_path)

    events = await watcher.execute()

    assert len(events) == 1
    event = events[0]
    assert event.severity is Severity.INFO
    assert "1 coding-session turn(s)" in event.title
    assert event.details["turns_captured"] == 1
    assert event.details["files_read"] == 1
    assert event.details["agents"] == ["claude_code"]
    assert event.details["skills_created"] == 0
    assert watcher._events == events


@pytest.mark.asyncio
async def test_a_pass_that_found_nothing_stays_silent(tmp_path):
    watcher, fake = make_watcher(tmp_path)
    assert await watcher.execute() == []
    assert fake.added == []


# ── Distillation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidates_are_handed_to_the_distiller_and_created_skills_announced(
    tmp_path, monkeypatch
):
    write_transcript(tmp_path)
    stub = StubDistiller(
        result=distiller_module.DistillationResult(
            action="CREATE_SKILL",
            skill={"title": "Stamp before upgrading an existing schema"},
            memory_id="mem-1",
            persisted=True,
        )
    )
    monkeypatch.setattr(AgentTranscriptWatcher, "_distiller", lambda self: stub)
    watcher, fake = make_watcher(tmp_path, distill=True)

    events = await watcher.execute()

    assert [s.session_id for s in stub.seen] == ["sess-a"]
    assert len(captures(fake)) == 1
    important = next(e for e in events if e.severity is Severity.IMPORTANT)
    assert "1 new procedural skill(s)" in important.title
    assert important.details["skills"] == ["Stamp before upgrading an existing schema"]
    info = next(e for e in events if e.severity is Severity.INFO)
    assert info.details["skills_created"] == 1
    assert info.details["distillation_candidates"] == 1


@pytest.mark.asyncio
async def test_a_patched_skill_is_counted_but_not_announced_as_new(tmp_path, monkeypatch):
    write_transcript(tmp_path)
    stub = StubDistiller(
        result=distiller_module.DistillationResult(
            action="PATCH_EXISTING", memory_id="mem-9", persisted=True
        )
    )
    monkeypatch.setattr(AgentTranscriptWatcher, "_distiller", lambda self: stub)
    watcher, _ = make_watcher(tmp_path, distill=True)

    events = await watcher.execute()

    assert [e.severity for e in events] == [Severity.INFO]
    assert events[0].details["skills_patched"] == 1


@pytest.mark.asyncio
async def test_a_distiller_that_explodes_does_not_lose_the_captures(tmp_path, monkeypatch):
    path = write_transcript(tmp_path)
    stub = StubDistiller(raises=RuntimeError("all models exhausted"))
    monkeypatch.setattr(AgentTranscriptWatcher, "_distiller", lambda self: stub)
    watcher, fake = make_watcher(tmp_path, distill=True)

    events = await watcher.execute()

    assert len(captures(fake)) == 1
    assert events[0].details["skills_created"] == 0
    store = WatermarkStore(state_path=tmp_path / "state.json")
    assert store.get_watermark(path)[0] == path.stat().st_size


@pytest.mark.asyncio
async def test_distillation_is_skipped_entirely_when_turned_off(tmp_path, monkeypatch):
    write_transcript(tmp_path)

    def explode(self):
        raise AssertionError("the distiller must not be constructed")

    monkeypatch.setattr(AgentTranscriptWatcher, "_distiller", explode)
    watcher, fake = make_watcher(tmp_path, distill=False)

    await watcher.execute()

    assert len(captures(fake)) == 1


@pytest.mark.asyncio
async def test_a_turn_the_gate_rejects_is_not_distilled(tmp_path, monkeypatch):
    write_transcript(tmp_path)

    class Rejecting(StubDistiller):
        def filter_candidate(self, session_slice) -> bool:
            return False

    stub = Rejecting()
    monkeypatch.setattr(AgentTranscriptWatcher, "_distiller", lambda self: stub)
    watcher, _ = make_watcher(tmp_path, distill=True)

    events = await watcher.execute()

    assert stub.seen == []
    assert events[0].details["distillation_candidates"] == 0


@pytest.mark.asyncio
async def test_the_real_distiller_is_built_against_the_watcher_tenant(tmp_path):
    watcher, _ = make_watcher(tmp_path)
    engine = watcher._distiller()
    assert isinstance(engine, distiller_module.SkillDistillationEngine)
    assert engine.tenant_id == TENANT


# ── Configuration ────────────────────────────────────────────────────────


def test_the_watcher_is_registered_with_the_framework_conventions():
    assert issubclass(AgentTranscriptWatcher, BaseWatcher)
    assert AgentTranscriptWatcher.name == "agent_transcripts"
    assert AgentTranscriptWatcher.display_name == "Agent Transcripts Harvester"
    assert AgentTranscriptWatcher.default_schedule == "*/15 * * * *"


def test_an_unknown_agent_name_in_the_config_falls_back_to_every_adapter():
    from life_graph.watchers.agent_transcripts.adapters import ADAPTER_CLASSES

    assert len(AgentTranscriptWatcher._adapters({"agents": ["emacs"]})) == len(ADAPTER_CLASSES)
    assert len(AgentTranscriptWatcher._adapters({})) == len(ADAPTER_CLASSES)
    assert [a.agent_type for a in AgentTranscriptWatcher._adapters({"agents": "cursor"})] == [
        "cursor"
    ]


def test_the_harvester_is_reachable_from_the_hourly_cron():
    """A watcher absent from ``run_watchers``' map never runs at all."""
    import inspect

    from life_graph.workers import tasks

    source = inspect.getsource(tasks.run_watchers)
    assert "AgentTranscriptWatcher.name: AgentTranscriptWatcher" in source


def test_the_framework_registers_the_harvester_by_default():
    from life_graph.watchers.framework import WatcherFramework

    framework = WatcherFramework(session_factory=None)
    framework.register_defaults()
    assert framework.get_registered()["agent_transcripts"] is AgentTranscriptWatcher
