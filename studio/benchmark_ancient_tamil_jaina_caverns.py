#!/usr/bin/env python3
# benchmark_ancient_tamil_jaina_caverns.py
# Benchmark suite for Ancient Tamil Jaina Caverns, Granitic Rock Splitting & Drip-Ledge Epigraphy

import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "JAI-01",
        "query": "Mankulam Nedunchezhiyan Kadalan Vazhuthi Tamil-Brahmi rock shelter inscription",
        "expected_slugs": ["insc-mankulam-nedunchezhiyan-pandya-jaina-cavern-charters"],
        "category": "Epigraphy"
    },
    {
        "id": "JAI-02",
        "query": "Granite rock splitting dry wooden wedges soaked in water expansion fractures",
        "expected_slugs": ["concept-granitic-rock-cleaving-wooden-wedge-swelling-mechanics"],
        "category": "Granitic Engineering"
    },
    {
        "id": "JAI-03",
        "query": "Drip ledge brow cut chisel groove preventing rainwater entering cavern shelter",
        "expected_slugs": ["concept-drip-ledge-rain-deflection-grooves-kavadi-engineering"],
        "category": "Cavern Hydraulics"
    },
    {
        "id": "JAI-04",
        "query": "Kal-padukai smooth polished rock beds carved for Jaina ascetic monks",
        "expected_slugs": ["concept-chisel-dressed-polished-granite-monk-beds-kal-padukai"],
        "category": "Monastic Architecture"
    },
    {
        "id": "JAI-05",
        "query": "Asokan script divergence and early Tamil-Brahmi orthography with dot pulli notation",
        "expected_slugs": ["concept-tamil-brahmi-epigraphical-palaeography-and-asokan-divergence", "concept-tamil-brahmi-tamili-paleography"],
        "category": "Epigraphical Palaeography"
    },
    {
        "id": "JAI-06",
        "query": "Master rock-cut cavern sculptor carving drip-ledges and stone beds at Mankulam",
        "expected_slugs": ["char-mankulam-master-cavern-sculptor-kudaivarai-sirpan"],
        "category": "Cavern Sculptors"
    },
    {
        "id": "JAI-07",
        "query": "Jaina monastic acharya leading Sallekhana meditation retreats in granite hills",
        "expected_slugs": ["char-madurai-jaina-monastic-acharya-kanikkayar"],
        "category": "Monastic Acharyas"
    },
    {
        "id": "JAI-08",
        "query": "Mankulam granite cavern monastic sanctuary and royal donative haven",
        "expected_slugs": ["place-mankulam-ancient-jaina-cavern-haven"],
        "category": "Sanctuary Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Jaina Caverns, Granitic Cleaving & Drip-Ledge Epigraphy")
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
