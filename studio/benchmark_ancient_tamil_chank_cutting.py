#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Chank Cutting, Bangle Sawing & Marine Mollusc Shell Craft
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
        "id": "CHK-01",
        "title": "Sangam Shell Cutter Verses",
        "query": "Nattrinai Ahananuru sangu aruppor conch shell saw bangles Korkai artisan verses",
        "expected_slugs": [
            "text-nattrinai-and-ahananuru-on-conch-shell-cutters"
        ]
    },
    {
        "id": "CHK-02",
        "title": "Turbinella Shell Anatomy",
        "query": "Turbinella pyrum conch shell anatomy aragonite columella density fracture toughness",
        "expected_slugs": [
            "concept-turbinella-pyrum-shell-anatomy-and-columella-density"
        ]
    },
    {
        "id": "CHK-03",
        "title": "Crescent Saw Technology",
        "query": "Conch shell sawing kudhirai vaai aruval crescent saw sand slurry mandrel grinding",
        # This query mixes vocabulary from two legitimately distinct corpus nodes: "crescent saw
        # sand slurry" comes from the earlier Karuvadu leaf-saw concept node, while "kudhirai vaai"
        # and "mandrel grinding" come from the batch-41 technology node. Their chunks sit at 0.80
        # cosine -- well under the 0.92 dedup threshold -- so neither is redundant and both are
        # correct answers for a query phrased this broadly.
        "expected_slugs": [
            "technology-conch-shell-semicircular-saw-slicing-and-mandrel-grinding",
            "concept-transverse-and-spiral-chank-cutting-with-curved-leaf-saws"
        ]
    },
    {
        "id": "CHK-04",
        "title": "Shell Bangles Artifact",
        "query": "Sangu valaiyal shell bangles chevron engraved beads ceremonial trumpet conch",
        "expected_slugs": [
            "artifact-sangu-valaiyal-engraved-bangles-beads-and-conch-horns"
        ]
    },
    {
        "id": "CHK-05",
        "title": "Chank Debris Stratigraphy",
        "query": "Chank cutting industrial debris stratigraphy columella cores Korkai Alagankulam Arikamedu",
        "expected_slugs": [
            "concept-chank-cutting-waste-stratigraphy-in-korkai-and-alagankulam"
        ]
    },
    {
        "id": "CHK-06",
        "title": "Shell Cutters Guild",
        "query": "Sangu aruppor guild hereditary conch cutters shell carvers maritime traders",
        "expected_slugs": [
            "institution-sangu-aruppor-guild-of-hereditary-chank-cutters-and-traders"
        ]
    },
    {
        "id": "CHK-07",
        "title": "Vermilion Lac Insetting",
        "query": "Shell bangle groove incising cinnabar vermilion red lac insetting friction polish",
        "expected_slugs": [
            "technology-shell-groove-incising-vermilion-insetting-and-lac-polishing"
        ]
    },
    {
        "id": "CHK-08",
        "title": "Alagankulam Shell Haven",
        "query": "Alagankulam ancient Pandyan chank cutting haven Vaigai estuary Roman shell port",
        "expected_slugs": [
            "place-alagankulam-ancient-pandya-chank-cutting-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Chank Cutting, Bangle Sawing & Marine Mollusc Shell Craft")
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
