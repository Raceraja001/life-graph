#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Black Pepper & Spice Cultivation, Curing and the Yavana Pepper Trade
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
        "id": "PEP-01",
        "title": "Classical Tamil Testimony to the Pepper Trade",
        "query": "Which classical Tamil anthology poems mention milagu as hill produce and foreign ships arriving with gold to load pepper at the Chera port?",
        "expected_slugs": [
            "text-sangam-verses-on-milagu-pepper-and-yavanar-gold-ships"
        ]
    },
    {
        "id": "PEP-02",
        "title": "Pepper Vine Botany and Living Supports",
        "query": "How does the black pepper climber grip its host trunk with clinging root cushions, and why were jackfruit, Erythrina and Garcinia trees left standing as living supports?",
        "expected_slugs": [
            "concept-piper-nigrum-vine-botany-and-standard-tree-trellis-agronomy"
        ]
    },
    {
        "id": "PEP-03",
        "title": "Why Peppercorns Turn Black and Pungent",
        "query": "What makes a drying peppercorn go black and wrinkled, and is its pungent alkaloid created by drying or already present in the green fruit?",
        "expected_slugs": [
            "concept-piperine-chemistry-and-enzymatic-blackening-of-sun-dried-pepper"
        ]
    },
    {
        "id": "PEP-04",
        "title": "Roman Bullion Paid for Spice",
        "query": "Why did Mediterranean buyers settle for Tamil spice in coin rather than goods, and what do the Egyptian cargo document and Pliny's complaint say about that one-way flow of gold?",
        "expected_slugs": [
            "concept-yavanar-pon-bullion-exchange-and-muziris-pepper-customs-testimony"
        ]
    },
    {
        "id": "PEP-05",
        "title": "Harvest, Blanching and the Drying Floor",
        "query": "When was the pepper crop cut relative to berries reddening on the spike, and how were threshed green corns dipped in hot water and spread on mats to cure?",
        "expected_slugs": [
            "technology-monsoon-timed-pepper-harvest-blanching-and-drying-yards"
        ]
    },
    {
        "id": "PEP-06",
        "title": "Sorting Cured Corns by Weight per Volume",
        "query": "How did traders separate hollow light berries from sound heavy ones using a winnowing fan, nested sieves and a float test, and what did garbled versus ungarbled mean?",
        "expected_slugs": [
            "technology-pepper-density-grading-winnowing-and-sieve-calibration"
        ]
    },
    {
        "id": "PEP-07",
        "title": "Baskets, Beam Weights and Sealed Jars",
        "query": "What containers and weighing gear carried and held cured peppercorns: paired bamboo pannier baskets on a pack bullock, stone and bronze balance weights, and luted clay jars against monsoon damp?",
        "expected_slugs": [
            "artifact-milagu-koodai-panniers-stone-weights-and-sealed-pepper-jars"
        ]
    },
    {
        "id": "PEP-08",
        "title": "The Elephant Hills Spice Country",
        "query": "Which Elephant Hills massif and the plain at its eastern foot in the Coimbatore-Tiruppur district belt formed the Kongu country's pepper tract, and what thinai and elevation band of lateritic slope suits the vine there?",
        "expected_slugs": [
            "place-anamalai-ancient-kongu-pepper-and-spice-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Black Pepper & Spice Cultivation, Curing and the Yavana Pepper Trade")
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
