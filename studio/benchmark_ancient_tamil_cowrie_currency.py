#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Cowrie Shell Currency, Fractional Reckoning, Amuletic Regalia & Maldivian-Coromandel Maritime Trade
Generated automatically.
"""

import sys
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"

BENCHMARK_QUERIES = [
    {
        "id": "CWR-01",
        "title": "Kanakku Adhigaram & Ennadi Chuvadi Cowrie Reckoning",
        "query": "Kanakku Adhigaram Kariya Nayanar Ennadi Chuvadi palagarai sozhi fractional arithmetic tables munthiri kani",
        "expected_slugs": [
            "text-kanakku-adhigaram-and-ennadi-chuvadi-on-palagarai-cowrie-fractional-reckoning"
        ]
    },
    {
        "id": "CWR-02",
        "title": "Monetaria moneta Biology & Maldives Ballast Trade",
        "query": "Monetaria moneta money cowrie nacreous aragonite shell Munnir Palan Theevu Maldives rice ballast trade",
        "expected_slugs": [
            "concept-monetaria-moneta-nacreous-porcelain-biology-and-munnir-palan-theevu-ballast-trade"
        ]
    },
    {
        "id": "CWR-03",
        "title": "Palagarai Micro-Denomination Bazaar Economics",
        "query": "Palagarai micro denomination market liquidity copper kasu exchange ratio daily vegetable buttermilk ferry toll",
        "expected_slugs": [
            "concept-palagarai-micro-denomination-market-economics-and-copper-kasu-exchange-ratios"
        ]
    },
    {
        "id": "CWR-04",
        "title": "Lagoon Coconut-Frond Trapping & Sand-Pit Retting",
        "query": "Coral lagoon coconut palm frond cowrie trapping beach sand pit biological retting preserve porcelain glaze",
        "expected_slugs": [
            "technology-atoll-coconut-frond-cowrie-trapping-pit-retting-and-sieve-calibration"
        ]
    },
    {
        "id": "CWR-05",
        "title": "Cowrie Dorsum Grinding & Cotton-Cord Stringing",
        "query": "Cowrie dorsal hump chipping wet sandstone flat grinding saanai kal cotton cord currency string bundling",
        "expected_slugs": [
            "technology-cowrie-dorsum-grinding-aperture-piercing-and-cotton-cord-string-bundling"
        ]
    },
    {
        "id": "CWR-06",
        "title": "Sozhi-Katti Bull Harnesses & Boomathu-Maadu Regalia",
        "query": "Sozhi katti Kangayam bull horse forehead band netti pattai Boomathu Maadu oracle cattle evil eye harness",
        "expected_slugs": [
            "artifact-sozhi-katti-equine-bovine-amulet-harnesses-and-embroidered-ceremonial-textiles"
        ]
    },
    {
        "id": "CWR-07",
        "title": "Sozhi-Prashnam Binary Combinatorics & Eye Symbolism",
        "query": "Sozhi Prashnam malli aperture up kavizh dome up binary combinatorics Ashtamangala 108 shells kan drishti eye",
        "expected_slugs": [
            "concept-sozhi-prashnam-binary-aperture-divination-and-apotropaic-evil-eye-symbolism"
        ]
    },
    {
        "id": "CWR-08",
        "title": "Nagore Coromandel Cowrie Port & Trade Haven",
        "query": "Nagore Vettar estuary Nagapattinam Coromandel port Kaveri rice Maldivian cowrie entrepot haven 10.8160 79.8420",
        "expected_slugs": [
            "place-nagore-ancient-coromandel-cowrie-currency-and-indian-ocean-trade-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Cowrie Shell Currency, Fractional Reckoning, Amuletic Regalia & Maldivian-Coromandel Maritime Trade")
    print(f"Model: {MODEL_NAME} | Dimension: 1024 | Total Queries: {len(BENCHMARK_QUERIES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_QUERIES)

    for item in BENCHMARK_QUERIES:
        qid = item["id"]
        qtitle = item["title"]
        query = item["query"]
        expected = item["expected_slugs"]

        q_emb = get_embedding(query)
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
        """, (q_emb, q_emb))
        results = cur.fetchall()

        top1_slug, top1_sim = results[0]
        if top1_slug in expected:
            passed += 1
            print(f"[PASS] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for s, sim in results:
                print(f"    - {s} ({sim:.4f})")

    cur.close()
    conn.close()

    print("=" * 80)
    print(f"SUMMARY: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print("=" * 80)
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
