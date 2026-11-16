#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Coir Retting, Marine Cordage & Coconut Fiber Rigging
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "COI-01",
        "name": "Sangam Coir Verse",
        "query": "Akananuru classical Sangam verses on coconut fiber steeping and coastal lagoon retting",
        "expected": [
            "text-akanananuru-verses-on-coconut-fiber-steeping-and-coastal-lagoon-retting"
        ]
    },
    {
        "id": "COI-02",
        "name": "Brackish Retting Science",
        "query": "Naar azhukkal brackish anaerobic husk retting and microbial pectin decomposition biochemistry",
        "expected": [
            "concept-naar-azhukkal-anaerobic-saline-husk-retting-and-pectin-decomposition-biochemistry"
        ]
    },
    {
        "id": "COI-03",
        "name": "Marine Hawser Spinning",
        "query": "Kayiru thirippu spindle twisting and multi ply marine hawser lay braiding technology thakki",
        "expected": [
            "technology-kayiru-thirippu-spindle-twisting-and-multi-ply-marine-hawser-lay-braiding"
        ]
    },
    {
        "id": "COI-04",
        "name": "Catamaran Lashing Cables",
        "query": "Kattumaram thamban heavy salt resistant coir lashing cables and anchor hawsers shock absorption",
        "expected": [
            "artifact-kattumaram-thamban-salt-resistant-coir-lashing-cables-and-anchor-hawsers"
        ]
    },
    {
        "id": "COI-05",
        "name": "High Lignin Fiber Physics",
        "query": "Thengai naar high lignin cellular structure elasticity and saltwater immersion rot immunity",
        "expected": [
            "concept-thengai-naar-tensile-elasticity-and-saltwater-immersion-rot-resistance"
        ]
    },
    {
        "id": "COI-06",
        "name": "Coir Spinners Guild",
        "query": "Naar thirippor guild hereditary corporation of coir spinners and naval rigging masters",
        "expected": [
            "institution-valayar-and-naar-thirippor-hereditary-guild-of-coir-spinners-and-rigging-masters"
        ]
    },
    {
        "id": "COI-07",
        "name": "Sewn Boat Hull Planking",
        "query": "Parambu pinithal sewn plank naval architecture and coir stitched hull flexibility carvel",
        "expected": [
            "technology-parambu-pinithal-flexible-coir-stitching-of-ocean-going-hull-planking"
        ]
    },
    {
        "id": "COI-08",
        "name": "Coir Cordage Haven",
        "query": "Kollam ancient Venad maritime coir cordage and international rigging haven Ashtamudi",
        "expected": [
            "place-kollam-ancient-venad-coir-cordage-haven"
        ]
    }
]

def get_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Ollama embedding error: {res.text}")
    return res.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Coir Retting, Marine Cordage & Coconut Fiber Rigging")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        vec = get_embedding(tc["query"])
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector ASC
            LIMIT 5;
        """, (vec, vec))
        rows = cur.fetchall()
        top1 = rows[0][0] if rows else None
        top1_sim = rows[0][1] if rows else 0.0

        if top1 in tc["expected"]:
            passed += 1
            print(f"[PASS] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for r in rows:
                print(f"    - {r[0]} (Sim: {r[1]:.4f})")
        print("-" * 80)

    elapsed = time.time() - t0
    acc = (passed / len(TEST_CASES)) * 100
    print(f"RESULTS: {passed}/{len(TEST_CASES)} passed ({acc:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    if passed < len(TEST_CASES):
        sys.exit(1)

if __name__ == "__main__":
    main()
