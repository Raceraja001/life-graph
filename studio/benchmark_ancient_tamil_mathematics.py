#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Palm-Leaf Mathematics, Katapayadi Decimal Place-Value & Astronomical Ephemerides
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
        "id": "MTH-01",
        "title": "Kanakku Adhigaram Treatise",
        "query": "Kanakku Adhigaram Ennadi Chuvadi palm leaf versified mathematical treatises Kari Nayanar",
        "expected_slugs": [
            "text-kanakku-adhigaram-and-ennadi-chuvadi-mathematical-treatises"
        ]
    },
    {
        "id": "MTH-02",
        "title": "Katapayadi Encryption Metrics",
        "query": "Katapayadi alphanumeric mnemonic encryption base 10 decimal place value micro fractions keezh munthiri",
        "expected_slugs": [
            "concept-katapayadi-alphanumeric-encryption-and-decimal-place-value"
        ]
    },
    {
        "id": "MTH-03",
        "title": "Panchangam Ephemeris Computation",
        "query": "Panchangam astronomical ephemeris computation shadow gnomon kanku kool geometry tidal calendars",
        "expected_slugs": [
            "technology-panchangam-astronomical-ephemeris-computation-and-shadow-gnomon"
        ]
    },
    {
        "id": "MTH-04",
        "title": "Ezhuthani Stylus Artifact",
        "query": "Ezhuthani tempered iron stylus talipot palm leaf folios mathematical tables grid",
        "expected_slugs": [
            "artifact-ezhuthani-iron-stylus-palm-leaf-folios-and-astronomical-tables"
        ]
    },
    {
        "id": "MTH-05",
        "title": "Fractional Land Survey Geometry",
        "query": "Ancient Tamil fractional metrology land survey geometry agricultural taxation ulgalanda kool",
        "expected_slugs": [
            "concept-ancient-tamil-fraction-system-and-land-survey-geometry"
        ]
    },
    {
        "id": "MTH-06",
        "title": "Accountants Guild Corporation",
        "query": "Kanakkappillai corporation royal revenue accountants scribes village astronomers nilam kanakku",
        "expected_slugs": [
            "institution-kanakkappillai-corporation-of-royal-accountants-and-astronomers"
        ]
    },
    {
        "id": "MTH-07",
        "title": "Thinnai School Pedagogy",
        "query": "Mental arithmetic multiplication algorithms sand tray scribing Thinnai school pedagogy",
        "expected_slugs": [
            "technology-arithmetic-multiplication-algorithms-and-thinnai-pedagogy"
        ]
    },
    {
        "id": "MTH-08",
        "title": "Vedaranyam Astronomical Haven",
        "query": "Vedaranyam ancient Chola astronomical haven marine tide computation coastal solstice citadel",
        "expected_slugs": [
            "place-vedaranyam-ancient-chola-astronomical-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Palm-Leaf Mathematics, Katapayadi Decimal Place-Value & Astronomical Ephemerides")
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
