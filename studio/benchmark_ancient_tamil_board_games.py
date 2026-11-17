#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Traditional Board Games, Strategy Geometry, Temple Flagstone Diagrams & Dice Craft
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
        "id": "GAM-01",
        "title": "Tirukkural & Sangam Gaming Verses",
        "query": "Tirukkural Soodhu chapter kavar dice kazhagam gaming halls Sangam kalarchikkai kazhangu",
        "expected_slugs": [
            "text-tirukkural-koodhu-and-sangam-literature-on-kavar-dice-and-gaming-halls"
        ]
    },
    {
        "id": "GAM-02",
        "title": "Pallanguzhi Combinatorics & Modulo-14",
        "query": "Pallanguzhi 14 cup mancala relay sowing thudaippu pasu capture rules mental arithmetic",
        "expected_slugs": [
            "concept-pallanguzhi-mancala-sowing-combinatorics-and-mental-modulo-arithmetic"
        ]
    },
    {
        "id": "GAM-03",
        "title": "Aadu-Puli-Aattam Predator-Prey Graph",
        "query": "Aadu Puli Aattam 3 tigers 15 goats 23 vertex triangular graph blockade strategy",
        "expected_slugs": [
            "concept-aadu-puli-aattam-asymmetric-graph-blockade-and-predator-prey-topology"
        ]
    },
    {
        "id": "GAM-04",
        "title": "Temple Flagstone Game Diagrams",
        "query": "Temple mandapa granite flagstone incised game boards chisel scoring cup pecking",
        "expected_slugs": [
            "technology-temple-mandapa-flagstone-game-board-incising-and-mason-layout"
        ]
    },
    {
        "id": "GAM-05",
        "title": "Chettinad Hinged Pallanguzhi Woodcarving",
        "query": "Hinged teakwood fish shaped Pallanguzhi woodcarving lacquered legs brass dice casting",
        "expected_slugs": [
            "technology-chettinad-wood-turning-hinged-pallanguzhi-carving-and-brass-thaayak-kattai"
        ]
    },
    {
        "id": "GAM-06",
        "title": "Thaayak-Kattai Stick Dice & Cowrie Lots",
        "query": "Thaayak kattai four sided oblong stick dice cowrie shell lots sozhi kundrimani counters",
        "expected_slugs": [
            "artifact-thaayak-kattai-stick-dice-cowrie-lots-and-folding-pallanguzhi-chests"
        ]
    },
    {
        "id": "GAM-07",
        "title": "Thaayam Race Topology & Dice Probability",
        "query": "Thaayam concentric spiral race track malai safe squares 16 state stick dice probability",
        "expected_slugs": [
            "concept-thaayam-cross-and-circle-race-kinematics-and-stick-dice-probability"
        ]
    },
    {
        "id": "GAM-08",
        "title": "Karaikudi Chettinad Gaming Craft Haven",
        "query": "Karaikudi Chettinad valavu courtyard Pallanguzhi woodcarving brass dice craft haven",
        "expected_slugs": [
            "place-karaikudi-ancient-chettinad-pallanguzhi-and-gaming-craft-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Traditional Board Games, Strategy Geometry, Temple Flagstone Diagrams & Dice Craft")
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
