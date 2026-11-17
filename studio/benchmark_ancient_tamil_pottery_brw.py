#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Megalithic Black-and-Red Ware (BRW) Pyrotechnics & Urn Burials
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
        "id": "BRW-01",
        "title": "Kalam-Sey-Kooce Sangam Verse",
        "query": "Purananuru Kalam Sey Kooce potter giant burial urn Mudhumakkal Thaazhi verses",
        "expected_slugs": [
            "text-purananuru-verses-addressing-the-potter-kalam-sey-kooce",
            # Same Purananuru urn-elegy material, ingested earlier by batch 9.
            "text-purananuru-mudumakkal-thaazhi-funerary-poetry"
        ]
    },
    {
        "id": "BRW-02",
        "title": "Clay Mineralogy Levigation",
        "query": "Alluvial clay mineralogy levigation settling tanks quartz sand tempering plasticity",
        "expected_slugs": [
            "concept-clay-mineralogy-levigation-tempering-and-plasticity-kinetics"
        ]
    },
    {
        "id": "BRW-03",
        "title": "Inverted Firing BRW Pyrotechnics",
        "query": "Inverted firing dual atmosphere pyrotechnics Black and Red Ware carbon reduction oxidation",
        "expected_slugs": [
            "technology-inverted-firing-dual-atmosphere-pyrotechnics-black-and-red-ware",
            # Same reduction/oxidation mechanism, ingested earlier by batches 4 and 10.
            "concept-black-and-red-ware-inverted-firing",
            "concept-black-and-red-ware-inverted-firing-pyrotechnics"
        ]
    },
    {
        "id": "BRW-04",
        "title": "Burial Urns Artifact",
        "query": "Mudhumakkal Thaazhi giant burial urns Black and Red Ware pottery ring stands graffiti",
        "expected_slugs": [
            "artifact-mudhumakkal-thaazhi-giant-urn-burials-and-black-and-red-ware-pots"
        ]
    },
    {
        "id": "BRW-05",
        "title": "Kiln Thermodynamics",
        "query": "Kiln thermal gradient thermodynamics hematite magnetite reduction slip vitrification",
        "expected_slugs": [
            "concept-kiln-thermal-gradient-thermodynamics-and-hematite-reduction"
        ]
    },
    {
        "id": "BRW-06",
        "title": "Potters Guild Corporation",
        "query": "Kalam Sey Kooce corporation hereditary potters guild clay rights communal kilns",
        "expected_slugs": [
            "institution-kalam-sey-kooce-corporation-of-hereditary-potters-and-kiln-masters"
        ]
    },
    {
        "id": "BRW-07",
        "title": "Wheel Throwing Paddle Anvil",
        "query": "Fast wheel throwing paddle thattu kal anvil aazhi wall thinning burnishing",
        "expected_slugs": [
            "technology-fast-wheel-throwing-paddle-and-anvil-wall-thinning"
        ]
    },
    {
        "id": "BRW-08",
        "title": "Adichanallur Pottery Haven",
        "query": "Adichanallur ancient Pandyan urn burial pottery haven Thamirabarani Megalithic necropolis",
        "expected_slugs": [
            "place-adichanallur-ancient-pandya-urn-burial-pottery-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Megalithic Black-and-Red Ware (BRW) Pyrotechnics & Urn Burials")
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
