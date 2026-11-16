#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Terracotta Well-Ring Hydraulics, Groundwater Filtration & Subterranean Pot-Wells
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "RIN-01",
        "name": "Sangam Ring-Well Verse",
        "query": "Purananuru 305 classical Sangam verses on terracotta ring wells and clear potable water",
        "expected": [
            "text-purananuru-305-verses-on-terracotta-ring-wells-and-clear-potable-water"
        ]
    },
    {
        "id": "RIN-02",
        "name": "Caisson Ring Mechanics",
        "query": "Urai kinaru terracotta ring mechanics caisson sinking and hydrostatic sand stabilization",
        "expected": [
            "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization"
        ]
    },
    {
        "id": "RIN-03",
        "name": "Heavy Ring Wheel Throwing",
        "query": "Urai vanaithal heavy wheel throwing segmented coiling and low temperature kiln firing quartz",
        "expected": [
            "technology-potter-wheel-ring-molding-and-open-air-bonfire-pyrotechnics"
        ]
    },
    {
        "id": "RIN-04",
        "name": "Radial Wedge Bricks",
        "query": "Chengal kinaru radial wedge bricks and interlocking architectural well shafts Keezhadi",
        "expected": [
            "artifact-chengal-kinaru-interlocking-wedge-shaped-curved-brick-masonry-wells"
        ]
    },
    {
        "id": "RIN-05",
        "name": "Sand Bed Filtration",
        "query": "Nilathadi neer natural sand bed slow filtration microbial clarification and potable springs",
        "expected": [
            "concept-nilathadi-neer-natural-alluvial-aquifer-filtration-and-sand-matrix-purification"
        ]
    },
    {
        "id": "RIN-06",
        "name": "Well Sinkers Guild",
        "query": "Neer thattar and kuyavar guild corporation of well sinkers and hydraulic ceramists dowsing",
        "expected": [
            "institution-neer-thattar-and-kuyavar-guild-well-sinkers-and-ceramic-engineers"
        ]
    },
    {
        "id": "RIN-07",
        "name": "Urban Soak-Pit Drainage",
        "query": "Soak pit hydraulics terracotta ring drainage pits and urban liquid waste dispersion Keezhadi",
        "expected": [
            "technology-urai-kinaru-drainage-soak-pits-and-urban-sanitation-networks"
        ]
    },
    {
        "id": "RIN-08",
        "name": "Metropolitan Ring-Well Haven",
        "query": "Palayarai ancient Chola metropolitan citadel and ring well hydraulic haven Kumbakonam",
        "expected": [
            "place-palayarai-ancient-chola-metropolitan-reservoir-haven"
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
    print("BENCHMARK: Ancient Tamil Terracotta Well-Ring Hydraulics, Groundwater Filtration & Subterranean Pot-Wells")
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
