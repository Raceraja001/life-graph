"""``life-graph harvest-transcripts`` — harvest coding-agent transcripts by hand.

The same work the ``agent_transcripts`` watcher does every 15 minutes, run on
demand. Two reasons it exists as a command:

* ``--dry-run`` shows exactly what the next scheduled pass would ingest and
  distil, touching neither the database nor the watermark file. It needs no
  running stack at all, which makes it the way to check a new adapter against
  real transcripts.
* a first harvest of a years-old ``~/.claude/projects`` is a backlog, and
  draining it from a terminal with ``--limit`` is friendlier than waiting for
  the cron to walk it 25 files at a time.

Standalone too::

    python -m life_graph.cli.harvest_transcripts --dry-run --agent claude --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Any

from life_graph.core.tenant import set_tenant_context
from life_graph.watchers.agent_transcripts.adapters import AGENT_ALIASES, adapters_for
from life_graph.watchers.agent_transcripts.harvest import DEFAULT_FILE_LIMIT, collect_new_slices
from life_graph.watchers.agent_transcripts.watermark import (
    DEFAULT_SETTLING_SECONDS,
    WatermarkStore,
)

if TYPE_CHECKING:
    from life_graph.watchers.agent_transcripts.normalizer import NormalizedSessionSlice

logger = logging.getLogger(__name__)

#: Agent choices accepted by ``--agent``.
AGENT_CHOICES = sorted(AGENT_ALIASES)

#: Seconds between passes when ``--interval`` is given without ``--once``.
DEFAULT_INTERVAL_SECONDS = 900


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach the harvest flags to *parser* (shared with the ``life-graph`` subparser)."""
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be ingested and distilled; write nothing",
    )
    parser.add_argument(
        "--agent",
        choices=AGENT_CHOICES,
        help="Harvest one agent's transcripts only (default: all)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Single pass, even when --interval is given (the default anyway)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        metavar="SECONDS",
        help=f"Keep harvesting every SECONDS (default: one pass; "
        f"the watcher's own cadence is {DEFAULT_INTERVAL_SECONDS}s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_FILE_LIMIT,
        metavar="N",
        help=f"Transcript files to read per pass (default: {DEFAULT_FILE_LIMIT}; 0 = no limit)",
    )
    parser.add_argument(
        "--state-file",
        metavar="PATH",
        help="Watermark file to use (default: ~/.life-graph/agent_transcripts_state.json)",
    )
    parser.add_argument(
        "--base-dir",
        action="append",
        metavar="DIR",
        help="Search DIR instead of the agents' default locations (repeatable)",
    )
    parser.add_argument(
        "--settling-seconds",
        type=float,
        default=DEFAULT_SETTLING_SECONDS,
        help="Skip transcripts touched more recently than this (default: %(default)s)",
    )
    parser.add_argument("--tenant", default="personal", help="Tenant ID (default: %(default)s)")
    parser.add_argument(
        "--no-distill",
        action="store_true",
        help="Ingest turns only; never call the LLM distiller",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show every turn harvested")
    return parser


def build_parser() -> argparse.ArgumentParser:
    """The standalone ``python -m life_graph.cli.harvest_transcripts`` parser."""
    parser = argparse.ArgumentParser(
        prog="life-graph harvest-transcripts",
        description="Harvest coding-agent session transcripts into Life Graph",
    )
    return add_arguments(parser)


# ── One pass ─────────────────────────────────────────────────────────────


async def harvest_once(args: argparse.Namespace) -> dict[str, Any]:
    """One harvest pass. Returns the counters, and prints a report as it goes.

    On ``--dry-run`` nothing is imported that would need a database: the scan,
    the normalizer and the candidate gate are all local and free.
    """
    set_tenant_context(args.tenant)
    adapters = adapters_for(args.agent)
    store = WatermarkStore(state_path=args.state_file)
    limit = None if not args.limit or args.limit <= 0 else int(args.limit)

    scan = collect_new_slices(
        adapters,
        store=store,
        base_dirs=args.base_dir,
        limit=limit,
        settling_seconds=args.settling_seconds,
    )

    report = {
        "files_seen": scan.files_seen,
        "files_read": len(scan.harvests),
        "files_up_to_date": scan.files_up_to_date,
        "files_unsettled": scan.files_skipped_unsettled,
        "turns": 0,
        "candidates": 0,
        "ingested": 0,
        "skills_created": 0,
        "skills_patched": 0,
        "dry_run": bool(args.dry_run),
    }

    print(f"\n[*] Agent transcript harvest{' (dry run)' if args.dry_run else ''}")
    print(f"{'=' * 60}")
    print(f"  agents:     {', '.join(a.agent_type for a in adapters)}")
    print(f"  state file: {store.state_path}")
    print(
        f"  files:      {scan.files_seen} seen · {len(scan.harvests)} with new bytes · "
        f"{scan.files_up_to_date} up to date · {scan.files_skipped_unsettled} still being written"
    )

    distiller = None if args.dry_run or args.no_distill else _distiller(args.tenant)
    gate = _gate(args.tenant)

    advanced = False
    for file_harvest in scan.harvests:
        print(
            f"\n[>] {file_harvest.path} "
            f"({file_harvest.agent_type}, +{file_harvest.bytes_read} bytes, "
            f"{len(file_harvest.slices)} turn(s))"
        )
        landed = 0
        for session_slice in file_harvest.slices:
            report["turns"] += 1
            is_candidate = gate(session_slice)
            report["candidates"] += int(is_candidate)
            _print_slice(session_slice, is_candidate, verbose=args.verbose)

            if args.dry_run:
                continue
            ingested = await _ingest(args.tenant, session_slice)
            landed += ingested
            report["ingested"] += ingested
            # Distil only what was ingested: a turn whose capture failed will
            # be replayed next pass, and distilling it now would spend a model
            # call on a turn with no capture behind it.
            if distiller is not None and is_candidate and ingested:
                outcome = await _distill(distiller, session_slice)
                report["skills_created"] += int(bool(outcome and outcome.created))
                report["skills_patched"] += int(bool(outcome and outcome.patched))

        # The watermark advances only when every turn in the file landed —
        # same rule as the watcher: replay beats losing history.
        if not args.dry_run and landed == len(file_harvest.slices):
            store.update_watermark(
                file_harvest.path,
                file_harvest.new_offset,
                file_harvest.mtime,
                file_harvest.session_id,
            )
            advanced = True

    if advanced:
        store.save()

    print(f"\n{'=' * 60}")
    print(
        f"[=] {report['turns']} turn(s), {report['candidates']} distillation candidate(s), "
        f"{report['ingested']} ingested, {report['skills_created']} skill(s) created, "
        f"{report['skills_patched']} patched"
    )
    if args.dry_run:
        print("[i] Dry run — no captures written, no skills distilled, watermarks untouched.")
    return report


def _print_slice(
    session_slice: NormalizedSessionSlice, is_candidate: bool, *, verbose: bool
) -> None:
    """One line per turn — or the whole rendered capture when ``--verbose``."""
    flags = []
    if session_slice.has_errors:
        flags.append("errors")
    if session_slice.has_fixes:
        flags.append("fixed")
    mark = "SKILL?" if is_candidate else "  --  "
    prompt = " ".join((session_slice.user_prompt or "(no prompt)").split())[:88]
    print(
        f"    [{mark}] {len(session_slice.tool_calls):>2} tool(s)"
        f" {'·'.join(flags) or 'clean':<12} {prompt}"
    )
    if verbose:
        for line in session_slice.to_capture_content().splitlines():
            print(f"        {line}")


def _gate(tenant_id: str):
    """The candidate filter as a plain callable, so a dry run needs no engine state."""
    from life_graph.services.skill_distiller import SkillDistillationEngine

    return SkillDistillationEngine(tenant_id).filter_candidate


def _distiller(tenant_id: str):
    """The distillation engine, or None when it cannot be built (no stack, no keys)."""
    try:
        from life_graph.services.skill_distiller import SkillDistillationEngine

        return SkillDistillationEngine(tenant_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Distiller unavailable ({exc}) — ingesting only")
        return None


async def _ingest(tenant_id: str, session_slice: NormalizedSessionSlice) -> int:
    """Ingest one turn into the capture spine. Returns 1 when it landed."""
    from life_graph.services.capture import CaptureService, without_nul
    from life_graph.storage.database import async_session
    from life_graph.watchers.agent_transcripts.watcher import (
        MODALITY,
        SURFACE,
        AgentTranscriptWatcher,
    )

    try:
        async with async_session() as session:
            await CaptureService(session).ingest(
                tenant_id=tenant_id,
                surface=SURFACE,
                modality=MODALITY,
                content=without_nul(session_slice.to_capture_content()),
                occurred_at=session_slice.occurred_at,
                properties=without_nul(AgentTranscriptWatcher.capture_properties(session_slice)),
            )
            await session.commit()
        return 1
    except Exception as exc:  # noqa: BLE001 - one unreachable DB must not kill the pass
        print(f"    [!] ingest failed: {exc}")
        return 0


async def _distill(distiller, session_slice: NormalizedSessionSlice):
    """Distil one candidate, reporting the verdict. None when the call failed."""
    try:
        result = await distiller.distill(session_slice)
    except Exception as exc:  # noqa: BLE001
        print(f"    [!] distillation failed: {exc}")
        return None
    if result.created:
        print(f"    [+] new skill: {result.skill.get('title')} ({result.memory_id})")
    elif result.patched:
        print(f"    [~] patched skill {result.memory_id}")
    elif result.reasoning:
        print(f"    [=] no skill: {result.reasoning}")
    return result


# ── Entry points ─────────────────────────────────────────────────────────


def cmd_harvest_transcripts(args: argparse.Namespace) -> dict[str, Any]:
    """``life-graph harvest-transcripts`` — one pass, or every ``--interval`` seconds."""

    async def _run() -> dict[str, Any]:
        report = await harvest_once(args)
        interval = 0 if args.once else int(getattr(args, "interval", 0) or 0)
        while interval > 0:
            await asyncio.sleep(interval)
            report = await harvest_once(args)
        return report

    return asyncio.run(_run())


def main(argv: list[str] | None = None) -> int:
    """Standalone entry point. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        cmd_harvest_transcripts(args)
    except KeyboardInterrupt:  # pragma: no cover - interactive
        print("\n[=] Stopped.")
        return 130
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
