#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Composite Bow Ballistics, Horn-Wood-Sinew Lamination & Sangam Archery Warfare
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "ARC-01",
        "name": "Valvil Ori Archery Verse",
        "query": "Purananuru 150 classical Sangam verses on Valvil Ori and lethal composite archery Vanparanar",
        "expected": [
            "text-purananuru-150-verses-on-valvil-ori-and-lethal-composite-archery"
        ]
    },
    {
        "id": "ARC-02",
        "name": "Composite Bow Physics",
        "query": "Composite bow dynamics horn wood and animal sinew lamination physics buffalo horn belly",
        "expected": [
            "concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics"
        ]
    },
    {
        "id": "ARC-03",
        "name": "Wootz Arrowhead Metallurgy",
        "query": "Wootz arrowheads high carbon steel metallurgy socketing and ballistic penetration bodkin",
        "expected": [
            "technology-wootz-steel-arrowhead-metallurgy-and-ballistic-penetration"
        ]
    },
    {
        "id": "ARC-04",
        "name": "Reed Shafts & Fletching",
        "query": "Kodu veng kana hardened reed arrow shafts and hawk feather fletching falcon eagle",
        "expected": [
            "artifact-kodu-veng-kana-hardened-reed-arrow-shafts-and-hawk-feather-fletching"
        ]
    },
    {
        "id": "ARC-05",
        "name": "Thumb Ring Release",
        "query": "Thumb ring release horn and agate archer rings and biomechanical draw kinematics viralkaap",
        "expected": [
            "concept-archer-thumb-ring-release-and-mongolian-draw-kinematics"
        ]
    },
    {
        "id": "ARC-06",
        "name": "Royal Bowmen Guild",
        "query": "Villaligal and Mazhavar guild corporation of royal bowmen scouts archery regiments",
        "expected": [
            "institution-mazhavar-and-villaligal-corporation-of-royal-archers-and-marksmen"
        ]
    },
    {
        "id": "ARC-07",
        "name": "Bowstring Twisting",
        "query": "Bowstring twisting wild Sann hemp rawhide and raw silk multi ply cordage beeswax",
        "expected": [
            "technology-bowstring-twisting-wild-hemp-deer-sinew-and-silk-binding"
        ]
    },
    {
        "id": "ARC-08",
        "name": "Archery Fortress Haven",
        "query": "Thagadur ancient Adigaman citadel and Mazhavar archery arsenal haven Dharmapuri",
        "expected": [
            "place-thagadur-ancient-adigaman-archery-and-fortress-haven"
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
    print("BENCHMARK: Ancient Tamil Composite Bow Ballistics, Horn-Wood-Sinew Lamination & Sangam Archery Warfare")
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
