"""Debug AGE -- test search_path persistence issue."""

import asyncio
import asyncpg
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    dsn = "postgresql://life_graph:life_graph@localhost:5432/life_graph"
    
    # Test 1: Single connection, multiple queries
    print("[1] Single connection, multiple queries...")
    conn = await asyncpg.connect(dsn)
    await conn.execute('SET search_path = ag_catalog, "$user", public')
    
    for i in range(3):
        try:
            sql = "SELECT * FROM cypher('life_graph', $$ MATCH (n) RETURN count(n) $$) AS (v agtype)"
            rows = await conn.fetch(sql)
            print(f"    Query {i+1} OK: {rows}")
        except Exception as e:
            print(f"    Query {i+1} FAIL: {e}")
    await conn.close()

    # Test 2: Pool, run LOAD+SET in init, multiple acquires
    print()
    print("[2] Pool with init, sequential acquire...")

    async def init_conn(c):
        await c.execute('SET search_path = ag_catalog, "$user", public')

    pool = await asyncpg.create_pool(
        dsn=dsn, min_size=1, max_size=1,
        init=init_conn,
        statement_cache_size=0,
    )

    for i in range(3):
        async with pool.acquire() as conn:
            try:
                sql = "SELECT * FROM cypher('life_graph', $$ MATCH (n) RETURN count(n) $$) AS (v agtype)"
                rows = await conn.fetch(sql)
                print(f"    Query {i+1} OK: {rows}")
            except Exception as e:
                print(f"    Query {i+1} FAIL: {e}")
    await pool.close()

    # Test 3: Pool with min_size=1, max_size=1, re-set search_path before each query
    print()
    print("[3] Pool, SET search_path before each query...")
    pool = await asyncpg.create_pool(
        dsn=dsn, min_size=1, max_size=1,
        statement_cache_size=0,
    )

    for i in range(3):
        async with pool.acquire() as conn:
            await conn.execute('SET search_path = ag_catalog, "$user", public')
            try:
                sql = "SELECT * FROM cypher('life_graph', $$ MATCH (n) RETURN count(n) $$) AS (v agtype)"
                rows = await conn.fetch(sql)
                print(f"    Query {i+1} OK: {rows}")
            except Exception as e:
                print(f"    Query {i+1} FAIL: {e}")
    await pool.close()

    # Test 4: Check if search_path resets after release
    print()
    print("[4] Check search_path after release...")
    pool = await asyncpg.create_pool(
        dsn=dsn, min_size=1, max_size=1,
        init=init_conn,
        statement_cache_size=0,
    )

    async with pool.acquire() as conn:
        sp = await conn.fetchval("SHOW search_path")
        print(f"    search_path BEFORE query: {sp}")
        rows = await conn.fetch(
            "SELECT * FROM cypher('life_graph', $$ MATCH (n) RETURN count(n) $$) AS (v agtype)"
        )
        print(f"    Query OK: {rows}")

    async with pool.acquire() as conn:
        sp = await conn.fetchval("SHOW search_path")
        print(f"    search_path AFTER release+reacquire: {sp}")
        try:
            rows = await conn.fetch(
                "SELECT * FROM cypher('life_graph', $$ MATCH (n) RETURN count(n) $$) AS (v agtype)"
            )
            print(f"    Query OK: {rows}")
        except Exception as e:
            print(f"    Query FAIL: {e}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
