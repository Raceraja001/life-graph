#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Palmyra Palm Wine Toddy Tapping, Fermentation Pyrotechnics & Madu-Maram Hydraulics
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "TDY-01",
        "name": "Sangam Palm Wine Verse",
        "query": "Porunararruppadai Kuruntokai panang kallu toddy bazaars sweet fermented palm wine Sangam",
        "expected": [
            "text-porunararruppadai-and-kuruntokai-verses-on-fermented-sweet-palm-wine"
        ]
    },
    {
        "id": "TDY-02",
        "name": "Spadix Phloem Physiology",
        "query": "Borassus spadix inflorescence physiology phloem sap translocation sucrose osmosis pressure",
        "expected": [
            "concept-borassus-spadix-inflorescence-sap-phloem-translocation-and-sucrose-osmosis"
        ]
    },
    {
        "id": "TDY-03",
        "name": "Spadix Bruising Technology",
        "query": "Panang kallu spadix bruising wooden pincer slicing earthen pot tapping technology",
        "expected": [
            "technology-panang-kallu-spadix-bruising-lime-coating-and-earthen-pot-tapping"
        ]
    },
    {
        "id": "TDY-04",
        "name": "Tapping Pots & Tools",
        "query": "Kallu muttai terracotta pots bone spadix pincers climbing foot loops seevuk kathi",
        "expected": [
            "artifact-kallu-muttai-chunnambu-coated-clay-pots-bone-bruisers-and-climbing-loops"
        ]
    },
    {
        "id": "TDY-05",
        "name": "Yeast Fermentation Kinetics",
        "query": "Palm wine fermentation Saccharomyces cerevisiae Zymomonas mobilis ethanol bio kinetics",
        "expected": [
            "concept-spontaneous-yeast-fermentation-saccharomyces-and-zymomonas-bio-kinetics"
        ]
    },
    {
        "id": "TDY-06",
        "name": "Palmyra Tappers Guild",
        "query": "Saanar panai yerigal guild master palmyra climbers tapping guilds tree taxes",
        "expected": [
            "institution-saanar-and-panai-yerigal-guild-of-master-palmyra-climbers-and-tappers"
        ]
    },
    {
        "id": "TDY-07",
        "name": "Padhaneer Lime Stabilization",
        "query": "Padhaneer sweet sap calcium hydroxide lime coating anti fermentation preservation",
        "expected": [
            "technology-padhaneer-sweet-sap-thermal-concentration-and-anti-fermentation-lime"
        ]
    },
    {
        "id": "TDY-08",
        "name": "Udangudi Palmyra Haven",
        "query": "Udangudi ancient Pandyan palmyra basin haven Teri dune sand aquifers tapping sanctuary",
        "expected": [
            "place-udangudi-ancient-pandya-palmyra-toddy-haven"
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
    print("BENCHMARK: Ancient Tamil Palmyra Palm Wine Toddy Tapping, Fermentation Pyrotechnics & Madu-Maram Hydraulics")
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
