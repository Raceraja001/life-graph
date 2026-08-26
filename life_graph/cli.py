"""Life Graph CLI — Cold start bootstrap and utilities."""

import argparse
import json
import sys
import time
from pathlib import Path


def cmd_cold_start(args):
    """Run cold start bootstrap on specified repositories."""
    from life_graph.cold_start.code_analyzer import CodeAnalyzer
    from life_graph.cold_start.config_parser import ConfigParser
    from life_graph.cold_start.git_analyzer import GitAnalyzer

    repos = args.repos
    author = args.author
    verbose = args.verbose

    print("\n[*] Life Graph Cold Start")
    print(f"{'=' * 50}")
    print(f"Repos: {', '.join(repos)}")
    if author:
        print(f"Author filter: {author}")
    print()

    all_memories = []
    start_time = time.time()

    for repo_path in repos:
        repo_path = str(Path(repo_path).resolve())
        print(f"\n[>] Analyzing: {repo_path}")

        # Git analysis
        try:
            git = GitAnalyzer()
            git_memories = git.analyze(repo_path, author_filter=author)
            print(f"  +-- Git history: {len(git_memories)} memories")
            all_memories.extend(git_memories)
        except Exception as e:
            print(f"  +-- Git history: skipped ({e})")

        # Config parsing
        try:
            config = ConfigParser()
            config_memories = config.parse(repo_path)
            print(f"  +-- Config files: {len(config_memories)} memories")
            all_memories.extend(config_memories)
        except Exception as e:
            print(f"  +-- Config files: skipped ({e})")

        # Code analysis
        try:
            code = CodeAnalyzer()
            code_memories = code.analyze(repo_path)
            print(f"  +-- Code patterns: {len(code_memories)} memories")
            all_memories.extend(code_memories)
        except Exception as e:
            print(f"  +-- Code patterns: skipped ({e})")

    # Deduplicate
    seen = set()
    unique = []
    for m in all_memories:
        key = m.get("content", "").lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(m)

    elapsed = time.time() - start_time

    print(f"\n{'=' * 50}")
    print("[=] Results:")
    print(f"  Total extracted: {len(all_memories)}")
    print(f"  After dedup: {len(unique)}")
    print(f"  Time: {elapsed:.1f}s")
    print("  LLM calls: 0 (all local analysis)")

    if verbose:
        print("\n[i] Extracted Memories:")
        for i, m in enumerate(unique, 1):
            print(f"  {i}. [{m.get('type_tag', 'unknown')}] {m.get('content', '')[:80]}")

    # Output as JSON if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(unique, f, indent=2, default=str)
        print(f"\n[+] Saved to: {output_path}")

    if not args.dry_run:
        print("\n[!] To store these in the database, run with --store flag")
        print("   (requires docker compose up -d && alembic upgrade head first)")

    return unique


def cmd_stats(args):
    """Show system statistics."""
    import httpx

    base = args.url
    try:
        r = httpx.get(f"{base}/admin/stats")
        stats = r.json()
        print("\n[*] Life Graph Stats")
        print(f"{'=' * 30}")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")
        print("Is the server running? (uvicorn life_graph.main:app)")


def _resolve_alembic_dir():
    """Locate the migration scripts, preferring the ones inside the package.

    A wheel force-includes ``alembic/`` as ``life_graph/_alembic/`` (see
    ``[tool.hatch.build.targets.wheel.force-include]``), so an installed copy
    has the revisions on disk but no repo-relative ``alembic/`` to point at.
    A source checkout has the opposite. Returns ``(path, origin)`` where
    ``origin`` is ``"packaged"`` or ``"source checkout"``.
    """
    from importlib.resources import files
    from pathlib import Path as _Path

    try:
        packaged = _Path(str(files("life_graph") / "_alembic"))
    except (ModuleNotFoundError, TypeError):  # pragma: no cover
        packaged = None
    if packaged is not None and (packaged / "env.py").is_file():
        return packaged, "packaged"

    import life_graph

    source = _Path(life_graph.__file__).resolve().parent.parent / "alembic"
    if (source / "env.py").is_file():
        return source, "source checkout"
    return None, "missing"


def _alembic_config(script_location, sql: bool):
    """Build an Alembic ``Config`` pointed at ``script_location``.

    ``script_location`` and ``sqlalchemy.url`` are both overridden on the
    object: the shipped ``alembic.ini`` carries the repo-relative
    ``script_location = alembic`` and a placeholder URL, neither of which is
    right once installed.
    """
    from alembic.config import Config

    from life_graph.config import settings

    ini = script_location / "alembic.ini"
    cfg = Config(str(ini)) if ini.is_file() else Config()
    cfg.set_main_option("script_location", str(script_location))
    if not sql:
        cfg.set_main_option("sqlalchemy.url", settings.database_url_sync)
    return cfg


def cmd_migrate(args):
    """Apply Alembic migrations using the revisions shipped with the package."""
    from alembic import command

    script_location, origin = _resolve_alembic_dir()
    if script_location is None:
        print("[!] No Alembic migrations found.")
        print("    Looked for life_graph/_alembic/ (installed) and ./alembic/ (checkout).")
        sys.exit(1)

    revision = args.revision or "head"
    if args.sql and ":" not in revision:
        # Offline mode cannot read the current revision from a database, so it
        # needs an explicit range to emit SQL for.
        revision = f"base:{revision}"

    versions = script_location / "versions"
    count = len(list(versions.glob("*.py"))) if versions.is_dir() else 0
    print(f"[*] Alembic scripts: {script_location} ({origin}, {count} revisions)")

    if args.sql:
        print(f"[*] Offline mode — emitting SQL for {revision}, no database connection\n")
    else:
        from life_graph.config import settings

        url = settings.database_url_sync
        safe = url.split("@")[-1] if "@" in url else url
        print(f"[*] Target database: …@{safe}")
        print(f"[*] Upgrading to: {revision}")

    try:
        command.upgrade(_alembic_config(script_location, args.sql), revision, sql=args.sql)
    except Exception as e:
        print(f"\n[!] Migration failed: {e}")
        sys.exit(1)

    if not args.sql:
        print("\n[+] Database is up to date.")


def cmd_reembed(args):
    """Re-embed the corpus with the configured model (after a model/dim change)."""
    import asyncio

    from life_graph.config import settings
    from life_graph.workers.reembed import reembed_all

    print(
        f"[*] Re-embedding corpus with: {settings.embedding_model} "
        f"(dim={settings.embedding_dimension})"
    )
    result = asyncio.run(reembed_all(batch_size=args.batch_size))
    print(f"[*] Done: {result['total']} rows re-embedded across {len(result['tables'])} tables")
    for t in result["tables"]:
        print(f"    {t['table']}: {t['processed']} done, {t['failed']} failed")


def cmd_judgment_stats(args):
    """Show judgment engine statistics and calibration summary."""
    import httpx

    base = args.url.rstrip("/")
    headers = {"X-Tenant-ID": args.tenant}

    def fetch(path):
        r = httpx.get(f"{base}/api/v1/judgment{path}", headers=headers, timeout=10)
        r.raise_for_status()
        payload = r.json()
        # Unwrap the {"success": ..., "data": ...} envelope if present
        return payload.get("data", payload) if isinstance(payload, dict) else payload

    try:
        stats = fetch("/stats")
        print(f"\n[*] Judgment Engine Stats (tenant: {args.tenant})")
        print(f"{'=' * 40}")
        for k, v in (stats or {}).items():
            print(f"  {k}: {v}")

        try:
            calibration = fetch("/calibration")
        except Exception:
            calibration = None
        if calibration:
            print("\n[*] Calibration")
            print(f"{'=' * 40}")
            if isinstance(calibration, dict):
                for k, v in calibration.items():
                    print(f"  {k}: {v}")
            else:
                for row in calibration:
                    print(f"  {row}")
    except Exception as e:
        print(f"Error: {e}")
        print("Is the server running? (uvicorn life_graph.main:app)")
        sys.exit(1)


def _hooks_paths(args):
    """Resolve the settings path and load it, exiting cleanly on bad JSON."""
    from pathlib import Path as _Path

    from life_graph.integrations.claude_code.installer import (
        default_settings_path,
        load_settings,
    )

    path = _Path(args.settings).expanduser() if args.settings else default_settings_path()
    try:
        return path, load_settings(path)
    except (OSError, ValueError) as e:
        print(f"[!] Cannot read {path}: {e}")
        print("    Refusing to touch a settings file that does not parse.")
        sys.exit(1)


def cmd_hooks_install(args):
    """Merge the Claude Code lifecycle hooks into a settings.json."""
    from life_graph.integrations.claude_code.installer import apply, hook_command, merge_install

    path, settings = _hooks_paths(args)
    try:
        merged = merge_install(settings, python_exe=args.python)
    except ValueError as e:
        print(f"[!] {path} has an unexpected hooks shape: {e}")
        sys.exit(1)

    if args.dry_run:
        print(json.dumps(merged, indent=2))
        return

    backup_path = apply(path, merged)
    print(f"[+] Installed Life Graph hooks into {path}")
    if backup_path:
        print(f"    Backup: {backup_path}")
    print(f"    Command: {hook_command(args.python)}")
    print("    Restart Claude Code (or start a new session) to pick them up.")


def cmd_hooks_uninstall(args):
    """Remove only the Life Graph entries from a settings.json."""
    from life_graph.integrations.claude_code.installer import apply, merge_uninstall

    path, settings = _hooks_paths(args)
    cleaned = merge_uninstall(settings)

    if args.dry_run:
        print(json.dumps(cleaned, indent=2))
        return

    if cleaned == settings:
        print(f"[=] No Life Graph hooks found in {path} — nothing to do.")
        return

    backup_path = apply(path, cleaned)
    print(f"[+] Removed Life Graph hooks from {path}")
    if backup_path:
        print(f"    Backup: {backup_path}")


def cmd_hooks_status(args):
    """Report which events are wired and where captures would be sent."""
    from life_graph.integrations.claude_code.config import load_config
    from life_graph.integrations.claude_code.installer import status

    path, settings = _hooks_paths(args)
    report = status(settings)
    cfg = load_config()

    print(f"\n[*] Life Graph Claude Code hooks — {path}")
    print(f"{'=' * 50}")
    if report["installed_events"]:
        for event, command in sorted(report["installed_events"].items()):
            print(f"  [+] {event}: {command}")
    else:
        print("  [-] not installed (run: life-graph hooks install)")
    if report["missing_events"]:
        print(f"  [!] missing: {', '.join(report['missing_events'])}")
    if report["other_hook_events"]:
        print(f"  [i] other (non-Life-Graph) hooks on: {', '.join(report['other_hook_events'])}")

    print("\n  Backend:  " + cfg.capture_url)
    print("  Tenant:   " + cfg.tenant_id)
    print("  State:    " + str(cfg.state_dir))
    print(f"  Disabled: {cfg.disabled}")
    try:
        from life_graph.integrations.claude_code.policy import DailyCounter

        print(f"  Sent today (tool exhaust): {DailyCounter(cfg.counter_path).current()}")
    except Exception:
        pass
    try:
        from life_graph.integrations.claude_code.transport import CaptureQueue

        if cfg.spool_path.exists():
            print(f"  Spooled (undelivered): {CaptureQueue(cfg.spool_path).pending_count()}")
    except Exception:
        pass


def main():
    """Entry point for the life-graph CLI."""
    parser = argparse.ArgumentParser(
        prog="life-graph",
        description="Life Graph -- Personal Memory System CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # cold-start command
    cs = subparsers.add_parser("cold-start", help="Bootstrap from existing repos")
    cs.add_argument("repos", nargs="+", help="Paths to Git repositories")
    cs.add_argument("--author", "-a", help="Filter commits by author name")
    cs.add_argument("--output", "-o", help="Save results to JSON file")
    cs.add_argument("--verbose", "-v", action="store_true", help="Show extracted memories")
    cs.add_argument("--dry-run", action="store_true", help="Extract only, don't store")
    cs.set_defaults(func=cmd_cold_start)

    # stats command
    st = subparsers.add_parser("stats", help="Show system statistics")
    st.add_argument("--url", default="http://localhost:8000", help="API base URL")
    st.set_defaults(func=cmd_stats)

    # judgment command group
    jd = subparsers.add_parser("judgment", help="Judgment engine commands")
    jd_sub = jd.add_subparsers(dest="judgment_command")
    jd_stats = jd_sub.add_parser("stats", help="Show judgment stats and calibration")
    jd_stats.add_argument("--url", default="http://localhost:8000", help="API base URL")
    jd_stats.add_argument("--tenant", default="personal", help="Tenant ID")
    jd_stats.set_defaults(func=cmd_judgment_stats)

    # migrate command — runs the revisions shipped inside the package
    mg = subparsers.add_parser("migrate", help="Apply database migrations (default: upgrade head)")
    mg.add_argument(
        "--revision",
        "-r",
        default="head",
        help="Target revision, or a base:target range in --sql mode (default: head)",
    )
    mg.add_argument(
        "--sql",
        action="store_true",
        help="Offline mode: print the SQL instead of connecting to a database",
    )
    mg.set_defaults(func=cmd_migrate)

    # hooks command group — Claude Code lifecycle integration
    hk = subparsers.add_parser("hooks", help="Claude Code lifecycle hook integration")
    hk_sub = hk.add_subparsers(dest="hooks_command")

    def _hook_common(p):
        p.add_argument(
            "--settings",
            help="Settings file to operate on (default: ~/.claude/settings.json)",
        )
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the resulting JSON instead of writing it",
        )
        return p

    hk_install = _hook_common(hk_sub.add_parser("install", help="Merge hooks into settings.json"))
    hk_install.add_argument(
        "--python",
        help="Interpreter for the hook command (default: the current one)",
    )
    hk_install.set_defaults(func=cmd_hooks_install)

    hk_uninstall = _hook_common(
        hk_sub.add_parser("uninstall", help="Remove only the Life Graph hook entries")
    )
    hk_uninstall.set_defaults(func=cmd_hooks_uninstall)

    hk_status = hk_sub.add_parser("status", help="Show hook installation and capture status")
    hk_status.add_argument("--settings", help="Settings file to inspect")
    hk_status.set_defaults(dry_run=False, func=cmd_hooks_status)

    # reembed command
    re = subparsers.add_parser("reembed", help="Re-embed the corpus with the configured model")
    re.add_argument("--batch-size", type=int, default=64, help="Rows per batch")
    re.set_defaults(func=cmd_reembed)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
