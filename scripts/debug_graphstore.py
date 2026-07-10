"""Debug GraphStore specifically -- test the actual GraphStore class."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def test_graph_store():
    """Test the actual GraphStore class."""
    from life_graph.storage.graph import GraphStore

    print("[1] Creating GraphStore...")
    store = GraphStore()

    try:
        print("[2] Testing execute_cypher (MATCH count)...")
        results = await store.execute_cypher("MATCH (n) RETURN count(n)")
        print(f"    OK: Result = {results}")
    except Exception as e:
        print(f"    FAIL: {e}")

    try:
        print("[3] Testing upsert_vertex...")
        vid = await store.upsert_vertex(
            label="Technology",
            name="TestPython",
            properties={"test": True},
        )
        print(f"    OK: Vertex ID = {vid}")
    except Exception as e:
        print(f"    FAIL: {e}")

    try:
        print("[4] Checking vertex count after upsert...")
        results = await store.execute_cypher("MATCH (n) RETURN count(n)")
        print(f"    OK: Result = {results}")
    except Exception as e:
        print(f"    FAIL: {e}")

    # Cleanup test vertex
    try:
        print("[5] Cleaning up test vertex...")
        await store.execute_cypher(
            "MATCH (n:Technology) WHERE n.name = 'TestPython' DELETE n"
        )
        print("    OK: Cleaned up")
    except Exception as e:
        print(f"    FAIL: {e}")

    await store.close()
    print("[DONE]")


if __name__ == "__main__":
    asyncio.run(test_graph_store())
