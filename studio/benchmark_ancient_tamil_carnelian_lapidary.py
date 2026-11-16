#!/usr/bin/env python3
# benchmark_ancient_tamil_carnelian_lapidary.py
# Benchmark suite for Ancient Tamil Carnelian Lapidary, Alkaline Chemical Etching & Micro-Drilling

import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "CAR-01",
        "query": "Alkaline plant juice slurry washing soda natron white etched carnelian beads",
        "expected_slugs": ["concept-alkaline-chemical-etching-plant-soda-slurry-and-heating"],
        "category": "Chemical Etching"
    },
    {
        "id": "CAR-02",
        "query": "Twin diamond-tipped drill bits bow drill perforating hard carnelian beads",
        "expected_slugs": ["concept-micro-diamond-twin-mandrel-bow-drilling-mechanics"],
        "category": "Micro-Drilling"
    },
    {
        "id": "CAR-03",
        "query": "Heating yellowish chalcedony to oxidize iron into deep red carnelian hematite",
        "expected_slugs": ["concept-agate-and-carnelian-iron-oxide-thermal-reddening-pyrotechnics"],
        "category": "Thermal Pyrotechnics"
    },
    {
        "id": "CAR-04",
        "query": "Tumble polishing gemstone beads in wooden troughs with corundum emery slurry",
        "expected_slugs": ["concept-tumble-polishing-hardwood-grooves-and-corundum-slurry"],
        "category": "Mechanical Polishing"
    },
    {
        "id": "CAR-05",
        "query": "Kalluppu achari master craftsman applying plant soda alkali for etched carnelian",
        "expected_slugs": ["char-kodumanal-master-carnelian-etcher-kalluppu-achari", "char-kodumanal-master-lapidary-artisan"],
        "category": "Master Etchers"
    },
    {
        "id": "CAR-06",
        "query": "Mani thulaithor lapidary craftsman specialized in twin-diamond micro drilling at Porunthal",
        "expected_slugs": ["char-porunthal-gemstone-micro-driller-mani-thulaithor", "concept-micro-diamond-twin-mandrel-bow-drilling-mechanics"],
        "category": "Master Drillers"
    },
    {
        "id": "CAR-07",
        "query": "Kangeyam beryl carnelian and quartz lapidary gem mining haven",
        "expected_slugs": ["place-kangeyam-ancient-gem-lapidary-haven"],
        "category": "Lapidary Topography"
    },
    {
        "id": "CAR-08",
        "query": "Kodumanal etched carnelian bead workshop merchant guild graffiti epigraphs",
        "expected_slugs": ["insc-kodumanal-etched-carnelian-merchant-guild-epigraphs"],
        "category": "Guild Epigraphy"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Carnelian Lapidary, Alkaline Chemical Etching & Micro-Drilling")
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
