"""Run the graph migration job to populate AGE graph from existing memories.

Usage:
    python scripts/run_graph_migration.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure the project root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def run():
    """Execute the graph migration pipeline."""
    from life_graph.storage.database import async_session
    from life_graph.jobs.graph_migration import GraphMigrationJob

    print("\n[*] Life Graph — Graph Migration")
    print("=" * 50)

    job = GraphMigrationJob(session_factory=async_session)
    report = await job.run()

    print(f"\n{'=' * 50}")
    print(f"[=] Graph Migration Report:")
    print(f"  Memories processed:  {report.memories_processed}")
    print(f"  Entities extracted:  {report.entities_extracted}")
    print(f"  Vertices created:    {report.vertices_created}")
    print(f"  Edges created:       {report.edges_created}")
    print(f"  Errors:              {report.errors}")
    print(f"  Duration:            {report.duration_seconds:.2f}s")

    # Clean up graph store connection pool
    if job._graph_store:
        await job._graph_store.close()

    return report


if __name__ == "__main__":
    asyncio.run(run())
