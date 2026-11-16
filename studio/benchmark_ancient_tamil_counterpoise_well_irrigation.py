#!/usr/bin/env python3
# benchmark_ancient_tamil_counterpoise_well_irrigation.py
# Benchmark suite for Ancient Tamil Counterpoise Well Irrigation, Picottah Levers & Kapilai Water Lifts

import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "IRR-01",
        "query": "First-class lever counterpoise beam ettam picottah well water lift mechanics",
        "expected_slugs": ["concept-first-class-lever-mechanics-and-ettam-counterpoise-balance"],
        "category": "Lever Mechanics"
    },
    {
        "id": "IRR-02",
        "query": "Kapilai pair of oxen walking down inclined ramp pulling heavy leather water bucket",
        "expected_slugs": ["concept-kapilai-oxen-driven-inclined-ramp-and-leather-bucket-hydraulics"],
        "category": "Oxen Hydraulics"
    },
    {
        "id": "IRR-03",
        "query": "Dry-stone mortarless masonry cylindrical well lining tapping deep aquifers",
        "expected_slugs": ["concept-dry-stone-cylindrical-well-lining-and-aquifer-tapping-kinaru"],
        "category": "Well Masonry"
    },
    {
        "id": "IRR-04",
        "query": "Thoppu orchard furrow irrigation network dividing well discharge into basins",
        "expected_slugs": ["concept-garden-furrow-distribution-and-thoppu-irrigation-networks"],
        "category": "Furrow Hydraulics"
    },
    {
        "id": "IRR-05",
        "query": "Master carpenter shaping balanced wooden picottah lever beams and fulcrum axles",
        "expected_slugs": ["char-thiruvallam-master-picottah-carpenter-ettath-thatchan"],
        "category": "Master Carpenters"
    },
    {
        "id": "IRR-06",
        "query": "Leather craftsman stitching heavy bullock water bags sal for kapilai irrigation",
        "expected_slugs": ["char-kovilpatti-master-leather-water-bag-craftsman-sal-kollan"],
        "category": "Leather Craftsmen"
    },
    {
        "id": "IRR-07",
        "query": "Thiruvallam ancient river basin picottah well irrigation haven",
        "expected_slugs": ["place-thiruvallam-ancient-picottah-haven"],
        "category": "Irrigation Topography"
    },
    {
        "id": "IRR-08",
        "query": "Pallava inscriptions granting tax exemptions for ettam well water lifts",
        "expected_slugs": ["insc-thiruvallam-pallava-well-irrigation-and-picottah-charters"],
        "category": "Irrigation Epigraphy"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Counterpoise Well Irrigation, Picottah Levers & Kapilai Water Lifts")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        emb = get_bge_embedding(tc["query"])
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"

        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
        """, (emb_str, emb_str))
        results = cur.fetchall()

        top_slug = results[0][0]
        top_sim = results[0][1]
        is_hit = top_slug in tc["expected_slugs"]
        status = "PASS" if is_hit else "FAIL"
        if is_hit:
            passed += 1

        print(f"[{status}] {tc['id']} ({tc['category']})")
        print(f"  Query:    '{tc['query']}'")
        print(f"  Expected: {tc['expected_slugs']}")
        print(f"  Top-1:    {top_slug} (Sim: {top_sim:.4f})")
        if not is_hit:
            print("  Top-5:")
            for rank, (r_slug, r_sim) in enumerate(results, 1):
                print(f"    {rank}. {r_slug} ({r_sim:.4f})")
        print("-" * 80)

    elapsed = time.time() - t0
    accuracy = (passed / len(TEST_CASES)) * 100
    print(f"RESULTS: {passed}/{len(TEST_CASES)} passed ({accuracy:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    cur.close()
    conn.close()
    if passed != len(TEST_CASES):
        exit(1)

if __name__ == "__main__":
    main()
