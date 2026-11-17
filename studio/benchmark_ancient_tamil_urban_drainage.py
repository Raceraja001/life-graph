#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Terracotta Ring Wells, Sluice Cisterns & Urban Subterranean Drainage
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
        "id": "DRN-01",
        "title": "Maduraikanchi Drainage Verses",
        "query": "Maduraikanchi Nedunalvaadai covered brick drains ring wells kazhivu neer vaikkal verses",
        "expected_slugs": [
            "text-maduraikanchi-and-nedunalvaadai-on-brick-drains-and-water-cisterns"
        ]
    },
    {
        "id": "DRN-02",
        "title": "Soil Mechanics Ring Caissons",
        "query": "Soil mechanics terracotta ring caisson hydrodynamics alluvial aquifer filtration urai kinaru",
        "expected_slugs": [
            "concept-soil-mechanics-ring-caisson-structural-engineering-and-aquifer-filtration"
        ]
    },
    {
        "id": "DRN-03",
        "title": "Burnt-Brick Drainage Vaults",
        "query": "Burnt brick covered drainage vaults interlocking socket spigot terracotta pipes sand traps",
        "expected_slugs": [
            "technology-burnt-brick-drainage-vaults-socket-spigot-terracotta-piping"
        ]
    },
    {
        "id": "DRN-04",
        "title": "Well Rings Artifact",
        "query": "Flanged terracotta well rings socket drain pipes stacked soakage jars Keezhadi",
        "expected_slugs": [
            "artifact-terracotta-well-rings-spigot-drain-pipes-and-soakage-jars"
        ]
    },
    {
        "id": "DRN-05",
        "title": "Hydraulic Gradient Kinetics",
        "query": "Hydraulic gradient head loss gravity drainage kinetics sediment self cleansing velocity",
        "expected_slugs": [
            "concept-hydraulic-gradient-gravity-flow-and-manning-roughness-kinetics"
        ]
    },
    {
        "id": "DRN-06",
        "title": "Sanitation Assembly Corporation",
        "query": "Ur manram vaikkal kuzhu corporation municipal assemblies sanitation inspectors ditch wardens",
        "expected_slugs": [
            "institution-ur-manram-and-kuzhu-corporation-of-civic-sanitation-masters"
        ]
    },
    {
        "id": "DRN-07",
        "title": "Brick Corbel Vaulting",
        "query": "Brick corbel vaulting hydraulic lime plaster waterproofing cisterns settling tanks",
        "expected_slugs": [
            "technology-brick-corbelling-lime-plaster-waterproofing-cisterns"
        ]
    },
    {
        "id": "DRN-08",
        "title": "Manalur Drainage Haven",
        "query": "Manalur ancient Vaigai urban drainage haven brick sanitation citadels ring well cluster",
        "expected_slugs": [
            "place-manalur-ancient-vaigai-urban-drainage-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Terracotta Ring Wells, Sluice Cisterns & Urban Subterranean Drainage")
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
