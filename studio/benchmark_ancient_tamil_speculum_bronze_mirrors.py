#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Speculum Bronze Mirrors, High-Tin Bell-Metal Metallurgy & Optical Reflection
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "MIR-01",
        "name": "Sangam Mirror Verse",
        "query": "Nedunalvadai classical Sangam verses on polished speculum bronze mirrors and royal adornment Nakkirar",
        "expected": [
            "text-nedunalvadai-verses-on-polished-bronze-mirrors-and-royal-toilette"
        ]
    },
    {
        "id": "MIR-02",
        "name": "Speculum Delta Phase",
        "query": "Vengala kannadi high tin delta phase speculum metal and intermetallic crystal physics Cu31Sn8",
        "expected": [
            "concept-vengala-kannadi-high-tin-delta-phase-speculum-metallurgy"
        ]
    },
    {
        "id": "MIR-03",
        "name": "Two-Piece Mold Casting",
        "query": "Madhuchchishtam precision two piece clay mold casting and speculum pyrotechnics Pamba clay",
        "expected": [
            "technology-aranmula-madhuchchishtam-two-piece-mud-mold-casting-and-crucible-pyrotechnics"
        ]
    },
    {
        "id": "MIR-04",
        "name": "Handled Bronze Mirrors",
        "query": "Tharpana kannadi chased brass sun burst frames and handled speculum mirrors ashtamangalyam",
        "expected": [
            "artifact-tharpana-kannadi-circular-handled-speculum-mirrors-and-brass-diadem-frames"
        ]
    },
    {
        "id": "MIR-05",
        "name": "Velvet Lapping Science",
        "query": "Micro abrasive lapping Maruthu charcoal velvet cloth and oil burnish physics castor oil",
        "expected": [
            "concept-vellerukku-and-chunnambu-micro-abrasive-lapping-and-polishing-mechanics"
        ]
    },
    {
        "id": "MIR-06",
        "name": "Mirror Casters Guild",
        "query": "Kannadi thattar guild Viswakarma corporation of master speculum metallurgists royal charters",
        "expected": [
            "institution-kannadi-thattar-viswakarma-guild-of-master-speculum-metallurgists"
        ]
    },
    {
        "id": "MIR-07",
        "name": "Front-Surface Optics",
        "query": "Front surface optics non refractive optical physics and parallax elimination zero gap",
        "expected": [
            "technology-front-surface-optics-and-non-refractive-geometric-clarity"
        ]
    },
    {
        "id": "MIR-08",
        "name": "Speculum Mirror Haven",
        "query": "Aranmula ancient Pamba river speculum bronze mirror and metallurgical haven Pathanamthitta",
        "expected": [
            "place-aranmula-ancient-speculum-bronze-mirror-haven"
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
    print("BENCHMARK: Ancient Tamil Speculum Bronze Mirrors, High-Tin Bell-Metal Metallurgy & Optical Reflection")
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
        print("-" * 80)

    elapsed = time.time() - t0
    acc = (passed / len(TEST_CASES)) * 100
    print(f"RESULTS: {passed}/{len(TEST_CASES)} passed ({acc:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    if passed < len(TEST_CASES):
        sys.exit(1)

if __name__ == "__main__":
    main()
