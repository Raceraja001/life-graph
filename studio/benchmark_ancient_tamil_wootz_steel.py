#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Crucible Wootz Steel Smelting, Bloomery Pyrotechnics & Ultra-High Carbon Damascus Metallurgy
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
        "id": "WTZ-01",
        "title": "Blacksmiths Bellows Sangam Verses",
        "query": "Purananuru Patittruppathu blacksmiths skin bellows wootz steel swords uruku kollan verses",
        "expected_slugs": [
            "text-purananuru-and-patittruppathu-on-blacksmiths-bellows-and-steel-swords"
        ]
    },
    {
        "id": "WTZ-02",
        "title": "Ultra-High Carbon Metallurgy",
        "query": "Ultra high carbon steel metallurgy iron carbon phase cementite spheroidization wootz",
        "expected_slugs": [
            "concept-ultra-high-carbon-steel-metallurgy-cementite-spheroidization"
        ]
    },
    {
        "id": "WTZ-03",
        "title": "Closed Crucible Pyrotechnics",
        "query": "Closed refractory crucible steel pyrotechnics rice husk clay saggers natural tuyeres",
        "expected_slugs": [
            "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers"
        ]
    },
    {
        "id": "WTZ-04",
        "title": "Wootz Ingots Artifact",
        "query": "Ukku steel crucibles conical button ingots damascus blades water marked swords",
        "expected_slugs": [
            "artifact-ukku-steel-crucibles-button-ingots-and-damascus-blades"
        ]
    },
    {
        "id": "WTZ-05",
        "title": "Magnetite Sand Reduction",
        "query": "Magnetite placer sand reduction carbon monoxide gas dynamics sponge iron bloom",
        "expected_slugs": [
            "concept-magnetite-iron-sand-reduction-bloomery-sponge-iron-chemistry"
        ]
    },
    {
        "id": "WTZ-06",
        "title": "Steelmakers Guild Corporation",
        "query": "Uruku kollan corporation hereditary steelmakers bloomery masters royal armorers",
        "expected_slugs": [
            "institution-uruku-kollan-corporation-of-hereditary-steelmakers-and-armorers"
        ]
    },
    {
        "id": "WTZ-07",
        "title": "Thermo-Mechanical Forging",
        "query": "Thermo mechanical forging cherry red temperature clay quenching oil tempering wootz",
        "expected_slugs": [
            "technology-thermo-mechanical-forging-and-clay-quenching-heat-treatment"
        ]
    },
    {
        "id": "WTZ-08",
        "title": "Mel-Siruvalur Steel Haven",
        "query": "Mel Siruvalur ancient crucible steel haven Thenpennai iron belt sagger smelting citadel",
        "expected_slugs": [
            "place-mel-siruvalur-ancient-crucible-steel-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Crucible Wootz Steel Smelting, Bloomery Pyrotechnics & Ultra-High Carbon Damascus Metallurgy")
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
