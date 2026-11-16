#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "WEI-01",
        "query": "Perumpanarruppadai verses on woven grass fences and nocturnal estuarine mullet fish trapping",
        "expected_slugs": [
            "text-perumpanarruppadai-lagoon-fish-weir-and-parathavar-trapping-poetry"
        ],
        "category": "Sangam Maritime Verse"
    },
    {
        "id": "WEI-02",
        "query": "Bamboo slat tidal fish weir engineering with V-shaped sirahu wings and padugai traps",
        "expected_slugs": [
            "concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai"
        ],
        "category": "Weir Engineering"
    },
    {
        "id": "WEI-03",
        "query": "Coir staked estuarine pound net katti valai hydraulics in brackish mangrove creeks",
        "expected_slugs": [
            "concept-coir-staked-estuarine-pound-net-hydraulics-katti-valai"
        ],
        "category": "Pound-Net Hydraulics"
    },
    {
        "id": "WEI-04",
        "query": "Lunar cycle spring tide nocturnal prawn and mullet trapping with flare torches",
        "expected_slugs": [
            "concept-lunar-cycle-nocturnal-brackish-lagoon-prawn-and-mullet-trapping"
        ],
        "category": "Lunar Trapping"
    },
    {
        "id": "WEI-05",
        "query": "Smoke cured estuarine fish preservation in salt brine and mangrove wood smoke karuvadu",
        "expected_slugs": [
            "concept-smoke-cured-estuarine-fish-preservation-and-salt-brine-maturation"
        ],
        "category": "Fish Preservation"
    },
    {
        "id": "WEI-06",
        "query": "Pazhaverkadu Pulicat inscriptions on rotational lagoon weir fishing rights and fish taxes",
        "expected_slugs": [
            "insc-pulicat-pazhaverkadu-lagoon-fishery-and-weir-tax-charters"
        ],
        "category": "Fishery Charters"
    },
    {
        "id": "WEI-07",
        "query": "Muttukadu coastal estuarine weir endowments and fishermen guild temple lamps",
        "expected_slugs": [
            "insc-muttukadu-coastal-estuarine-fish-weir-endowments"
        ],
        "category": "Estuarine Epigraphs"
    },
    {
        "id": "WEI-08",
        "query": "Pazhaverkadu ancient estuarine lagoon and tidal bamboo fish weir haven Pulicat Lake",
        "expected_slugs": [
            "place-pazhaverkadu-ancient-estuarine-lagoon-and-fish-weir-haven"
        ],
        "category": "Lagoon Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Tidal Estuarine Fish-Weirs & Stake-Nets")
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
