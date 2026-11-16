#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Bronze Icon Lost-Wax Casting & Cire-Perdue Metallurgy
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "BRZ-01",
        "name": "Karanagama Lost-Wax Verse",
        "query": "Karanagama classical Agamic verses on cire perdue lost wax bronze casting and devalaya icons",
        "expected": [
            "text-karanagama-and-silpa-sastras-on-lost-wax-cire-perdue-bronze-iconography"
        ]
    },
    {
        "id": "BRZ-02",
        "name": "Panchaloha Five-Metal Metallurgy",
        "query": "Panchaloha five metal sacred alloy metallurgy phase diagrams and dendritic solidification",
        "expected": [
            "concept-panchaloha-five-metal-sacred-alloy-metallurgy-and-dendritic-microstructure"
        ]
    },
    {
        "id": "BRZ-03",
        "name": "Madhuchchishtam Lost-Wax Process",
        "query": "Madhuchchishtam beeswax armature modeling Kaveri alluvial slurry investment core baking",
        "expected": [
            "technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry"
        ]
    },
    {
        "id": "BRZ-04",
        "name": "Crucibles & Wax Tools",
        "query": "Karuvool and uzhari refractory graphite crucibles bronze wax spatulas and funnel sprues",
        "expected": [
            "artifact-karuvool-crucibles-wax-spatulas-and-lost-wax-sprue-runners"
        ]
    },
    {
        "id": "BRZ-05",
        "name": "Nataraja Dynamic Equilibrium",
        "query": "Ananda Tandava Chola Nataraja center of gravity dynamics prabha radiance and dynamic equilibrium",
        "expected": [
            "concept-anandatandava-chola-nataraja-cosmic-equilibrium-and-dynamic-bronze-balance"
        ]
    },
    {
        "id": "BRZ-06",
        "name": "Swamimalai Sthapathi Guild",
        "query": "Swamimalai sthapathis hereditary Chola guild of master bronze casters and sacred iconographers",
        "expected": [
            "institution-swamimalai-sthapathi-guild-of-hereditary-imperial-chola-bronze-casters"
        ]
    },
    {
        "id": "BRZ-07",
        "name": "Chasing & Patination",
        "query": "Chasing and burnishing cold hammered tooling agate burnishing and organic oil patination",
        "expected": [
            "technology-chasing-and-burnishing-cold-hammered-detail-engraving-and-patination"
        ]
    },
    {
        "id": "BRZ-08",
        "name": "Bronze Casting Haven",
        "query": "Swamimalai ancient Chola panchaloha bronze casting haven Kaveri delta sthapathi citadel",
        "expected": [
            "place-swamimalai-ancient-chola-panchaloha-icon-casting-haven"
        ]
    }
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Ollama embedding error: {res.text}")
    return res.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Bronze Icon Lost-Wax Casting & Cire-Perdue Metallurgy")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        vec = get_bge_embedding(tc["query"])
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

    elapsed = time.time() - t0
    acc = (passed / len(TEST_CASES)) * 100
    print("=" * 80)
    print(f"SUMMARY: {passed}/{len(TEST_CASES)} passed ({acc:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    cur.close()
    conn.close()

    if passed < len(TEST_CASES):
        sys.exit(1)

if __name__ == "__main__":
    main()
