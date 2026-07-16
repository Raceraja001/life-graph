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
    print(f"{'='*50}")
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
        key = m.get('content', '').lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(m)

    elapsed = time.time() - start_time

    print(f"\n{'='*50}")
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
        with open(output_path, 'w') as f:
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
        print(f"{'='*30}")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")
        print("Is the server running? (uvicorn life_graph.main:app)")


def cmd_reembed(args):
    """Re-embed the corpus with the configured model (after a model/dim change)."""
    import asyncio

    from life_graph.config import settings
    from life_graph.workers.reembed import reembed_all

    print(f"[*] Re-embedding corpus with: {settings.embedding_model} "
          f"(dim={settings.embedding_dimension})")
    result = asyncio.run(reembed_all(batch_size=args.batch_size))
    print(f"[*] Done: {result['total']} rows re-embedded across "
          f"{len(result['tables'])} tables")
    for t in result["tables"]:
        print(f"    {t['table']}: {t['processed']} done, {t['failed']} failed")


def cmd_judgment_stats(args):
    """Show judgment engine statistics and calibration summary."""
    import httpx

    base = args.url.rstrip('/')
    headers = {'X-Tenant-ID': args.tenant}

    def fetch(path):
        r = httpx.get(f"{base}/api/v1/judgment{path}", headers=headers, timeout=10)
        r.raise_for_status()
        payload = r.json()
        # Unwrap the {"success": ..., "data": ...} envelope if present
        return payload.get('data', payload) if isinstance(payload, dict) else payload

    try:
        stats = fetch('/stats')
        print(f"\n[*] Judgment Engine Stats (tenant: {args.tenant})")
        print(f"{'='*40}")
        for k, v in (stats or {}).items():
            print(f"  {k}: {v}")

        try:
            calibration = fetch('/calibration')
        except Exception:
            calibration = None
        if calibration:
            print("\n[*] Calibration")
            print(f"{'='*40}")
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


def main():
    """Entry point for the life-graph CLI."""
    parser = argparse.ArgumentParser(
        prog='life-graph',
        description='Life Graph -- Personal Memory System CLI',
    )
    subparsers = parser.add_subparsers(dest='command')

    # cold-start command
    cs = subparsers.add_parser('cold-start', help='Bootstrap from existing repos')
    cs.add_argument('repos', nargs='+', help='Paths to Git repositories')
    cs.add_argument('--author', '-a', help='Filter commits by author name')
    cs.add_argument('--output', '-o', help='Save results to JSON file')
    cs.add_argument('--verbose', '-v', action='store_true', help='Show extracted memories')
    cs.add_argument('--dry-run', action='store_true', help='Extract only, don\'t store')
    cs.set_defaults(func=cmd_cold_start)

    # stats command
    st = subparsers.add_parser('stats', help='Show system statistics')
    st.add_argument('--url', default='http://localhost:8000', help='API base URL')
    st.set_defaults(func=cmd_stats)

    # judgment command group
    jd = subparsers.add_parser('judgment', help='Judgment engine commands')
    jd_sub = jd.add_subparsers(dest='judgment_command')
    jd_stats = jd_sub.add_parser('stats', help='Show judgment stats and calibration')
    jd_stats.add_argument('--url', default='http://localhost:8000', help='API base URL')
    jd_stats.add_argument('--tenant', default='personal', help='Tenant ID')
    jd_stats.set_defaults(func=cmd_judgment_stats)

    # reembed command
    re = subparsers.add_parser('reembed', help='Re-embed the corpus with the configured model')
    re.add_argument('--batch-size', type=int, default=64, help='Rows per batch')
    re.set_defaults(func=cmd_reembed)

    args = parser.parse_args()
    if not getattr(args, 'func', None):
        parser.print_help()
        return

    args.func(args)


if __name__ == '__main__':
    main()
