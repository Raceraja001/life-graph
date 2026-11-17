#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Beryl & Quartz Lapidary, Micro-Diamond Drilling & Gemstone Slicing
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
        "id": "GEM-01",
        "title": "Patittruppathu Gem Verses",
        "query": "Patittruppathu Kodumanam patta nankalam beryl slicing carnelian beads Chera verses",
        "expected_slugs": [
            "text-patittruppathu-on-kodumanam-gem-city-and-beryl-bead-craft"
        ]
    },
    {
        "id": "GEM-02",
        "title": "Pegmatite Beryl Mineralogy",
        "query": "Pegmatite beryl mineralogy aquamarine cleavage crystal optics cyclosilicate hexagonal prisms",
        "expected_slugs": [
            "concept-pegmatite-beryl-mineralogy-aquamarine-cleavage-and-crystal-optics"
        ]
    },
    {
        "id": "GEM-03",
        "title": "Bow-Drill Micro-Perforation",
        "query": "Double tipped bow drill micro perforation corundum slurry rotary lapidary wheels",
        # This query spans two legitimately distinct nodes: "double tipped bow drill" is unique to
        # the batch-43 technology node, while "rotary lapidary wheels" is vocabulary only the
        # earlier corundum-slurry concept node carries (it alone describes rotating wooden lap
        # wheels). Their en chunks sit at 0.80 cosine -- well under the 0.92 dedup threshold -- so
        # neither is redundant and both answer a query phrased this broadly.
        "expected_slugs": [
            "technology-double-tipped-bow-drill-micro-perforation-and-corundum-slurry",
            "concept-corundum-slurry-lapidary-wheels-and-gem-faceting"
        ]
    },
    {
        "id": "GEM-04",
        "title": "Etched Carnelian Artifact",
        "query": "Etched alkaline carnelian beads faceted quartz intaglios beryl prisms Kodumanal",
        "expected_slugs": [
            "artifact-etched-carnelian-beads-quartz-intaglios-and-beryl-prisms"
        ]
    },
    {
        "id": "GEM-05",
        "title": "Thermal Color Enhancement",
        "query": "Thermal color enhancement limonite hematite oxidation chalcedony agate baking",
        "expected_slugs": [
            "concept-thermal-color-enhancement-and-carnelian-iron-oxide-oxidation"
        ]
    },
    {
        "id": "GEM-06",
        "title": "Lapidary Guild Corporation",
        "query": "Mani vinaiignar akkasalai guild master lapidaries gem appraisers royal mint masters",
        "expected_slugs": [
            "institution-mani-vinaiignar-and-akkasalai-guild-of-master-lapidaries"
        ]
    },
    {
        "id": "GEM-07",
        "title": "Wire Sawing Lapidary",
        "query": "Groove slicing wire sawing quartz slurry abrasion agate grinding slabs",
        "expected_slugs": [
            "technology-groove-slicing-wire-sawing-and-agate-grinding-slabs"
        ]
    },
    {
        "id": "GEM-08",
        "title": "Padiyur Beryl Haven",
        "query": "Padiyur ancient Kongu beryl mining haven pegmatite aquamarine dikes Roman trade pit",
        # Padiyur is documented by two place nodes from different corpora -- the batch-43 Kongu
        # mining-haven framing and the earlier Kangeyam pegmatite-deposit framing (which alone
        # supplies the query's "dikes" vocabulary). Both describe the same beryl source and are
        # correct answers here; their en chunks sit at 0.79 cosine, under the 0.92 dedup
        # threshold, so neither node is redundant.
        "expected_slugs": [
            "place-padiyur-ancient-kongu-beryl-mining-haven",
            "place-padiyur-aquamarine-beryl-mines"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Beryl & Quartz Lapidary, Micro-Diamond Drilling & Gemstone Slicing")
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
