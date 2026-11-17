#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Mango Cultivar Biodiversity, Maavadu Brine Osmosis, Maavilai-Toranam Hygiene & Mukkani Orchard Lore
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
        "id": "MAA-01",
        "title": "Sangam Thema, Pulima & Maavadu Literary Accounts",
        "query": "Kuruntokai Ainkurunuru Perumpanarruppadai Purananuru thema pulima maanthalir maavadu mango verses",
        "expected_slugs": [
            "text-sangam-corpus-on-thema-pulima-mango-groves-and-maavadu-pickles"
        ]
    },
    {
        "id": "MAA-02",
        "title": "Mango Terpene Chemistry, Mangiferin & Prosodic Feet",
        "query": "Mangifera indica beta myrcene ocimene resin volatiles mangiferin xanthone Thema Pulima Yappilakkanam prosody",
        "expected_slugs": [
            "concept-mangifera-indica-myrcene-ocimene-aroma-mangiferin-xanthones-and-thema-pulima-prosody"
        ]
    },
    {
        "id": "MAA-03",
        "title": "Maavadu Pre-Lignified Endocarp & Hypertonic Brine Osmosis",
        "query": "Maavadu pre lignified endocarp 5 mm pedicel stem stub latex seal castor oil hypertonic salt brine osmosis plasmolysis",
        "expected_slugs": [
            "concept-maavadu-pre-lignified-endocarp-physiology-and-hypertonic-brine-osmosis"
        ]
    },
    {
        "id": "MAA-04",
        "title": "Approach-Grafting (Ottu-Kattuthal) & Orchard Smudge-Smoking",
        "query": "Naattu maa taproot rootstock ottu kattuthal inarching approach grafting pugai mooduthal ethylene smudge smoking mango hoppers",
        "expected_slugs": [
            "technology-naattu-maa-rootstock-inarching-approach-grafting-and-orchard-smudge-smoking"
        ]
    },
    {
        "id": "MAA-05",
        "title": "Three-Stage Mango Preservation Workflow",
        "query": "Three-stage seasonal summer mango glut post-harvest preservation workflow tossing 4 days exuded vadu-neer dry-pounded kadugu longitudinal wedges palmyra mat dehydration",
        "expected_slugs": [
            "technology-chithirai-maavadu-bharani-brine-curing-and-sun-dried-maa-vathal-preservation"
        ]
    },
    {
        "id": "MAA-06",
        "title": "Maangai-Pachadi Six Tastes & Maangottai Seed Flour",
        "query": "Chithirai Puthandu Maangai Pachadi six tastes Arusuvai decorticated maangottai paruppu chooranam dysentery",
        "expected_slugs": [
            "artifact-bharani-cured-maavadu-salted-maa-vathal-and-maambazha-thiraattai-fruit-leather"
        ]
    },
    {
        "id": "MAA-07",
        "title": "Maavilai-Toranam Antimicrobial Hygiene & Leaf Viability",
        "query": "Maavilai toranam coriaceous cuticle prolonged photosynthesis mangiferin terpene phytoncides threshold hygiene poorna kumbham",
        "expected_slugs": [
            "concept-maavilai-toranam-mangiferin-antimicrobial-hygiene-and-poorna-kumbham-symbolism"
        ]
    },
    {
        "id": "MAA-08",
        "title": "Krishnagiri Baramahal Mango Orchard & Grafting Haven",
        "query": "Krishnagiri Baramahal plateau Thenpennaiyar Kaveripattinam Santoshpuram approach grafting mango orchard haven 12.5180 78.2130",
        "expected_slugs": [
            "place-krishnagiri-ancient-baramahal-maa-mango-orchard-and-grafting-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Mango Cultivar Biodiversity, Maavadu Brine Osmosis, Maavilai-Toranam Hygiene & Mukkani Orchard Lore")
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
