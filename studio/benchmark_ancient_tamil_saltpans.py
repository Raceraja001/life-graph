#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Saltpan Hydraulic Canals, Solar Halite Crystallization & Umanar Caravans
Generated automatically.
"""

import sys
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"

BENCHMARK_QUERIES = [
    {
        "id": "SLT-01",
        "title": "Sangam Umanar Salt Verses",
        "query": "Ahananuru Narrinai Umanar salt caravans white halite crystals barter trade verses",
        "expected_slugs": [
            "text-ahananuru-and-narrinai-on-umanar-salt-caravans-and-salterns"
        ]
    },
    {
        "id": "SLT-02",
        "title": "Seawater Solar Evaporation Kinetics",
        "query": "Seawater solar evaporation Baume density gradients halite precipitation kinetics alam",
        "expected_slugs": [
            "concept-seawater-evaporation-salinity-gradients-and-halite-crystallization"
        ]
    },
    {
        "id": "SLT-03",
        "title": "Tidal Feeder Canals Salterns",
        "query": "Tidal sluice feeder canals compacted impermeable clay pans wooden salt scrapers mara vaari",
        "expected_slugs": [
            "technology-tidal-feeder-canals-tamped-clay-pans-and-wooden-salt-scrapers"
        ]
    },
    {
        "id": "SLT-04",
        "title": "Salt Carts & Measures Artifact",
        "query": "Heavy wooden wheeled salt carts palmyra woven salt baskets volumetric marakkals",
        "expected_slugs": [
            "artifact-umanar-bullock-carts-palm-leaf-salt-sacks-and-measuring-marakkals"
        ]
    },
    {
        "id": "SLT-05",
        "title": "Oppu-Nel Salt Barter Economics",
        "query": "Ancient Tamil salt barter economics oppu nel parity trans thinai trade networks",
        "expected_slugs": [
            "concept-ancient-tamil-salt-barter-economics-and-oppu-nel-parity"
        ]
    },
    {
        "id": "SLT-06",
        "title": "Umanar Guild Corporation",
        "query": "Umanar kudi corporation hereditary saltern masters salt boilers caravan guilds",
        "expected_slugs": [
            "institution-umanar-kudi-corporation-of-salt-makers-and-caravan-traders"
        ]
    },
    {
        "id": "SLT-07",
        "title": "Solar Bittern Drainage",
        "query": "Solar wind desiccation kinetics conical mound stacking bittern liquor drainage",
        "expected_slugs": [
            "technology-solar-wind-drying-mound-stacking-and-bittern-drainage"
        ]
    },
    {
        "id": "SLT-08",
        "title": "Kovalam Saltern Haven",
        "query": "Kovalam ancient Thondai saltern haven Buckingham estuarine pans Umanar coastal emporium",
        "expected_slugs": [
            "place-kovalam-ancient-thondai-saltern-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Saltpan Hydraulic Canals, Solar Halite Crystallization & Umanar Caravans")
    print(f"Model: {MODEL_NAME} | Dimension: 1024 | Total Queries: {len(BENCHMARK_QUERIES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_QUERIES)

    for item in BENCHMARK_QUERIES:
        qid = item["id"]
        qtitle = item["title"]
        query = item["query"]
        expected = item["expected_slugs"]

        q_emb = get_embedding(query)
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
        """, (q_emb, q_emb))
        results = cur.fetchall()

        top1_slug, top1_sim = results[0]
        if top1_slug in expected:
            passed += 1
            print(f"[PASS] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for s, sim in results:
                print(f"    - {s} ({sim:.4f})")

    cur.close()
    conn.close()

    print("=" * 80)
    print(f"SUMMARY: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print("=" * 80)
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
