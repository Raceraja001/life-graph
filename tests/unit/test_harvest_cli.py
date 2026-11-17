"""``life-graph harvest-transcripts`` — argument parsing and the dry run.

The dry run is the contract worth testing hardest: it is what someone runs to
see what the harvester *would* do, so it must read real transcripts and write
absolutely nothing — no captures, no skills, no watermarks.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from life_graph.cli import harvest_transcripts as cli
from life_graph.cli.root import main as root_main
from life_graph.services.skill_distiller import DistillationResult
from life_graph.watchers.agent_transcripts.harvest import DEFAULT_FILE_LIMIT

TURN = [
    {
        "type": "user",
        "sessionId": "sess-cli",
        "cwd": "/home/raja/projects/life-graph",
        "timestamp": "2026-11-15T12:00:00.000Z",
        "message": {"role": "user", "content": "ruff fails with an unfixable import error"},
    },
    {
        "type": "assistant",
        "sessionId": "sess-cli",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "Bash",
                    "input": {"command": "ruff check life_graph/"},
                }
            ],
        },
    },
    {
        "type": "user",
        "sessionId": "sess-cli",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "content": "TC001 Move application import into a type-checking block",
                    "is_error": True,
                }
            ],
        },
    },
    {
        "type": "assistant",
        "sessionId": "sess-cli",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t2",
                    "name": "Edit",
                    "input": {"file_path": "/repo/life_graph/x.py"},
                }
            ],
        },
    },
    {
        "type": "user",
        "sessionId": "sess-cli",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "edited"}],
        },
    },
    {
        "type": "assistant",
        "sessionId": "sess-cli",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Moved the import under TYPE_CHECKING."}],
        },
    },
]


@pytest.fixture
def transcript(tmp_path):
    """A settled Claude Code transcript under *tmp_path*."""
    path = tmp_path / "-home-raja-projects-life-graph" / "sess-cli.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in TURN), encoding="utf-8")
    past = time.time() - 600
    os.utime(path, (past, past))
    return path


def argv_for(tmp_path, *extra):
    """The flags that keep a test off the real home directory and real state."""
    return [
        "--agent",
        "claude",
        "--base-dir",
        str(tmp_path),
        "--state-file",
        str(tmp_path / "state.json"),
        *extra,
    ]


# ── Parsing ──────────────────────────────────────────────────────────────


def test_defaults_are_a_single_live_pass_over_every_agent():
    args = cli.build_parser().parse_args([])
    assert args.dry_run is False
    assert args.agent is None
    assert args.once is False
    assert args.interval == 0
    assert args.limit == DEFAULT_FILE_LIMIT
    assert args.state_file is None
    assert args.base_dir is None
    assert args.tenant == "personal"
    assert args.no_distill is False
    assert args.verbose is False


def test_every_flag_from_the_spec_parses():
    args = cli.build_parser().parse_args(
        [
            "--dry-run",
            "--agent",
            "cursor",
            "--once",
            "--limit",
            "5",
            "--state-file",
            "/tmp/s.json",
        ]
    )
    assert (args.dry_run, args.agent, args.once, args.limit) == (True, "cursor", True, 5)
    assert args.state_file == "/tmp/s.json"


@pytest.mark.parametrize("agent", ["claude", "cursor", "antigravity", "codex"])
def test_the_four_agents_are_accepted(agent):
    assert cli.build_parser().parse_args(["--agent", agent]).agent == agent


def test_an_unknown_agent_is_refused_at_the_command_line(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.build_parser().parse_args(["--agent", "emacs"])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_base_dir_is_repeatable():
    args = cli.build_parser().parse_args(["--base-dir", "/a", "--base-dir", "/b"])
    assert args.base_dir == ["/a", "/b"]


def test_the_subcommand_is_wired_into_the_life_graph_parser(monkeypatch, capsys):
    """``life-graph harvest-transcripts`` must reach this module's command."""
    called = {}
    monkeypatch.setattr(cli, "cmd_harvest_transcripts", lambda args: called.setdefault("a", args))
    monkeypatch.setattr(
        "sys.argv", ["life-graph", "harvest-transcripts", "--dry-run", "--agent", "codex"]
    )
    root_main()
    assert called["a"].dry_run is True
    assert called["a"].agent == "codex"


# ── Dry run ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_dry_run_reports_the_turn_and_writes_nothing(tmp_path, transcript, capsys):
    args = cli.build_parser().parse_args(argv_for(tmp_path, "--dry-run"))
    report = await cli.harvest_once(args)

    assert report == {
        "files_seen": 1,
        "files_read": 1,
        "files_up_to_date": 0,
        "files_unsettled": 0,
        "turns": 1,
        "candidates": 1,
        "ingested": 0,
        "skills_created": 0,
        "skills_patched": 0,
        "dry_run": True,
    }
    out = capsys.readouterr().out
    assert "(dry run)" in out
    assert str(transcript) in out
    assert "SKILL?" in out
    assert "errors·fixed" in out
    assert "ruff fails with an unfixable import error" in out
    assert "no captures written" in out

    assert not (tmp_path / "state.json").exists()


@pytest.mark.asyncio
async def test_a_dry_run_never_reaches_the_database_or_the_model(tmp_path, transcript, monkeypatch):
    def explode(*_a, **_k):
        raise AssertionError("a dry run must not write or call out")

    monkeypatch.setattr(cli, "_ingest", explode)
    monkeypatch.setattr(cli, "_distiller", explode)

    await cli.harvest_once(cli.build_parser().parse_args(argv_for(tmp_path, "--dry-run")))


@pytest.mark.asyncio
async def test_a_dry_run_can_be_repeated_because_it_moves_no_watermark(
    tmp_path, transcript, capsys
):
    args = cli.build_parser().parse_args(argv_for(tmp_path, "--dry-run"))
    first = await cli.harvest_once(args)
    second = await cli.harvest_once(args)
    assert first == second


@pytest.mark.asyncio
async def test_verbose_prints_the_capture_that_would_be_written(tmp_path, transcript, capsys):
    await cli.harvest_once(
        cli.build_parser().parse_args(argv_for(tmp_path, "--dry-run", "--verbose"))
    )
    out = capsys.readouterr().out
    assert "# Coding session turn — life-graph (claude_code)" in out
    assert "## Tool sequence" in out
    assert "ruff check life_graph/" in out


@pytest.mark.asyncio
async def test_a_turn_the_gate_rejects_is_marked_as_no_skill(tmp_path, capsys):
    path = tmp_path / "-home-raja-projects-life-graph" / "chat.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "user",
                "sessionId": "s",
                "cwd": "/p",
                "message": {"role": "user", "content": "thanks!"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    past = time.time() - 600
    os.utime(path, (past, past))

    report = await cli.harvest_once(cli.build_parser().parse_args(argv_for(tmp_path, "--dry-run")))
    assert (report["turns"], report["candidates"]) == (1, 0)
    assert "SKILL?" not in capsys.readouterr().out


# ── Live pass ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_live_pass_ingests_distils_and_advances_the_watermark(
    tmp_path, transcript, monkeypatch, capsys
):
    ingested = []

    async def fake_ingest(tenant_id, session_slice):
        ingested.append((tenant_id, session_slice))
        return 1

    class StubDistiller:
        def __init__(self):
            self.seen = []

        async def distill(self, session_slice, *, dry_run=False):
            self.seen.append(session_slice)
            return DistillationResult(
                action="CREATE_SKILL",
                skill={"title": "ruff TC001 means the import is annotation-only"},
                memory_id="mem-7",
                persisted=True,
            )

    stub = StubDistiller()
    monkeypatch.setattr(cli, "_ingest", fake_ingest)
    monkeypatch.setattr(cli, "_distiller", lambda tenant: stub)

    report = await cli.harvest_once(
        cli.build_parser().parse_args(argv_for(tmp_path, "--tenant", "work"))
    )

    assert report["ingested"] == 1
    assert report["skills_created"] == 1
    assert [t for t, _ in ingested] == ["work"]
    assert [s.session_id for s in stub.seen] == ["sess-cli"]
    assert "new skill: ruff TC001" in capsys.readouterr().out

    state = json.loads((tmp_path / "state.json").read_text())
    assert state[str(transcript)]["last_byte_offset"] == transcript.stat().st_size
    assert state[str(transcript)]["session_id"] == "sess-cli"


@pytest.mark.asyncio
async def test_a_second_live_pass_finds_the_file_up_to_date(tmp_path, transcript, monkeypatch):
    monkeypatch.setattr(cli, "_ingest", lambda tenant, s: _one())
    monkeypatch.setattr(cli, "_distiller", lambda tenant: None)
    args = cli.build_parser().parse_args(argv_for(tmp_path))

    await cli.harvest_once(args)
    second = await cli.harvest_once(args)

    assert second["files_up_to_date"] == 1
    assert second["turns"] == 0


async def _one() -> int:
    return 1


@pytest.mark.asyncio
async def test_no_distill_ingests_without_building_a_distiller(tmp_path, transcript, monkeypatch):
    monkeypatch.setattr(cli, "_ingest", lambda tenant, s: _one())

    def explode(_tenant):
        raise AssertionError("--no-distill must not construct a distiller")

    monkeypatch.setattr(cli, "_distiller", explode)

    report = await cli.harvest_once(
        cli.build_parser().parse_args(argv_for(tmp_path, "--no-distill"))
    )
    assert (report["ingested"], report["skills_created"]) == (1, 0)


@pytest.mark.asyncio
async def test_a_failed_ingest_is_reported_and_does_not_raise(
    tmp_path, transcript, monkeypatch, capsys
):
    """The real ``_ingest``, with the database unreachable.

    Patched at ``storage.database.async_session`` rather than left to time out
    against a real socket: the point is the error path, and a unit test must
    not need (or wait for) Postgres.
    """

    def unreachable():
        raise ConnectionRefusedError("[Errno 111] Connect call failed")

    monkeypatch.setattr("life_graph.storage.database.async_session", unreachable)

    report = await cli.harvest_once(cli.build_parser().parse_args(argv_for(tmp_path)))
    assert report["ingested"] == 0
    assert "ingest failed" in capsys.readouterr().out
    # The watermark is not advanced for a turn that never landed.
    assert not (tmp_path / "state.json").exists()


# ── Entry point ──────────────────────────────────────────────────────────


def test_main_returns_zero_after_a_dry_run(tmp_path, transcript, capsys):
    assert cli.main(argv_for(tmp_path, "--dry-run")) == 0
    assert "Dry run" in capsys.readouterr().out


def test_main_runs_one_pass_when_once_is_given(tmp_path, transcript, monkeypatch):
    passes = []
    monkeypatch.setattr(cli, "harvest_once", _recorder(passes))
    assert cli.main(argv_for(tmp_path, "--once", "--interval", "60")) == 0
    assert len(passes) == 1


def _recorder(passes):
    async def harvest_once(args):
        passes.append(args)
        return {}

    return harvest_once


def test_limit_zero_means_no_limit(tmp_path, transcript, monkeypatch):
    seen = {}
    real = cli.collect_new_slices

    def spy(adapters, **kwargs):
        seen.update(kwargs)
        return real(adapters, **kwargs)

    monkeypatch.setattr(cli, "collect_new_slices", spy)
    cli.main(argv_for(tmp_path, "--dry-run", "--limit", "0"))
    assert seen["limit"] is None
