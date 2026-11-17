#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Riverine Coracles, Split-Bamboo Basket-Boats, Ford Crossings & Gorge Navigation
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
        "id": "PRS-01",
        "title": "Sangam & Historical River Craft Accounts",
        "query": "Sangam Kuruntokai Ahananuru ambhi punai thoni Kaveri hide covered coracle accounts",
        "expected_slugs": [
            "text-sangam-and-historical-accounts-of-ambhi-punai-and-kaveri-coracles"
        ]
    },
    {
        "id": "PRS-02",
        "title": "Parisal Paraboloid Buoyancy & Eddy Stability",
        "query": "Parisal paraboloid shell buoyancy ultra shallow draft keel less whirlpool eddy stability",
        "expected_slugs": [
            "concept-parisal-paraboloid-buoyancy-shallow-draft-and-eddy-stability"
        ]
    },
    {
        "id": "PRS-03",
        "title": "Split-Bamboo Lattice & Waterproof Sheathing",
        "query": "Split bamboo radial lattice weaving earthen mound mold buffalo hide pitch waterproofing parisal",
        "expected_slugs": [
            "technology-split-bamboo-hexagonal-lattice-weaving-and-hide-pitch-waterproofing"
        ]
    },
    {
        "id": "PRS-04",
        "title": "Single-Paddle Figure-Eight Bow Sculling",
        "query": "Single paddle bow sculling mun thuzhaavu figure eight stroke circular coracle propulsion",
        "expected_slugs": [
            "technology-single-paddle-sculling-figure-eight-draw-stroke-and-gorge-ferrying"
        ]
    },
    {
        "id": "PRS-05",
        "title": "Parisal Hulls, Paddles & Gorge Cast-Nets",
        "query": "Portable bamboo Parisal shell broad bladed thuduppu paddle veechu valai cast net",
        "expected_slugs": [
            "artifact-parisal-bamboo-hull-wooden-sculling-paddles-and-coracle-cast-nets"
        ]
    },
    {
        "id": "PRS-06",
        "title": "Thoni-Thurai Stone Ferry-Ghat Hydraulics",
        "query": "Thoni thurai stepped granite ferry ghat slack water eddy siting diagonal drift offset",
        "expected_slugs": [
            "concept-thoni-thurai-stone-ford-hydraulics-and-seasonal-flood-ferry-routes"
        ]
    },
    {
        "id": "PRS-07",
        "title": "Odaikkarar Ferrymen Guilds & Charters",
        "query": "Odaikkarar hereditary ferrymen guilds thurai manyam grain shares chathiram free ferry endowments",
        "expected_slugs": [
            "institution-odaikkarar-ferrymen-guilds-and-royal-thurai-toll-charters"
        ]
    },
    {
        "id": "PRS-08",
        "title": "Hogenakkal Kaveri Gorge Coracle Haven",
        "query": "Hogenakkal Kaveri charnockite canyon gorge whirlpool rapids Parisal coracle haven Dharmapuri",
        "expected_slugs": [
            "place-hogenakkal-ancient-kaveri-gorge-parisal-coracle-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Riverine Coracles, Split-Bamboo Basket-Boats, Ford Crossings & Gorge Navigation")
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
