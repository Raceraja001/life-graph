#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Deep-Sea Shark Hunting, Thimil Outriggers & Harpooning Ballistics
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "SHK-01",
        "name": "Sangam Shark Verse",
        "query": "Natrinai classical Sangam verses on deep sea shark hunting and harpooning Parathavar ocean swell",
        "expected": [
            "text-natrinai-388-verses-on-deep-sea-shark-hunting-and-harpooning"
        ]
    },
    {
        "id": "SHK-02",
        "name": "Pelagic Shark Tactics",
        "query": "Sura vettai pelagic shark hunting tactics ocean currents and celestial navigation velli star",
        "expected": [
            "concept-sura-vettai-deep-sea-shark-hunting-and-pelagic-navigation"
        ]
    },
    {
        "id": "SHK-03",
        "name": "Thimil Surf Design",
        "query": "Thimil boat design heavy surf breaching outrigger hull stabilization stitched plank canoe",
        "expected": [
            "technology-thimil-boat-design-and-heavy-surf-hull-stabilization"
        ]
    },
    {
        "id": "SHK-04",
        "name": "Heavy Shark Hooks",
        "query": "Kodum thoondil forged iron shark hooks multi barbed bronze points chained traces",
        "expected": [
            "artifact-kodum-thoondil-forged-iron-shark-hooks-and-bronze-barbs"
        ]
    },
    {
        "id": "SHK-05",
        "name": "Shark Teeth Weapons",
        "query": "Sura kombu shark teeth weapons bone harpoon tips and rostral saw blades",
        "expected": [
            "concept-sura-kombu-and-pal-shark-teeth-weapons-and-bone-harpoon-tips"
        ]
    },
    {
        "id": "SHK-06",
        "name": "Harpooner Guilds",
        "query": "Valayar and Parathavar deep sea shark hunting brotherhood guild totems sura kombu nadukal",
        "expected": [
            "institution-valayar-and-neithal-parathavar-deep-sea-hunting-brotherhood"
        ]
    },
    {
        "id": "SHK-07",
        "name": "Shagreen Leather Abrasive",
        "query": "Sura pattu shark skin placoid scales abrasive rasping and shagreen leather tanning",
        "expected": [
            "technology-sura-pattu-shark-skin-abrasive-rasps-and-leather-tanning"
        ]
    },
    {
        "id": "SHK-08",
        "name": "Shark Hunting Haven",
        "query": "Poompuhar ancient Neithal shark hunting haven Kaveripoompattinam coastal offshore flotillas",
        "expected": [
            "place-poompuhar-ancient-neithal-shark-hunting-haven"
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
    print("BENCHMARK: Ancient Tamil Deep-Sea Shark Hunting, Thimil Outriggers & Harpooning Ballistics")
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
