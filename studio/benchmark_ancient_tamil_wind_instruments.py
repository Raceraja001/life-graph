#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Conical Bore Wind Instruments, Acha-Maram Nagaswaram Turning, Seevali Reed Acoustics & Brass Kombu-Tharai Craft
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
        "id": "WND-01",
        "title": "Silappadikaram & Sangam Poems on Vangiyam, Kuzhal & Kombu",
        "query": "Silappadikaram Aychiyar Kuravai Perumpanarruppadai eriyul thulai bamboo flute vangiyam kuzhal kombu tharai ekkalam",
        "expected_slugs": [
            "text-silappadikaram-kurinjippattu-and-chola-inscriptions-on-vangiyam-kuzhal-kombu-and-nagaswaram"
        ]
    },
    {
        "id": "WND-02",
        "title": "Conical Woodwind Bore Acoustics & Keyless Gamakas",
        "query": "Conical woodwind bore standing wave complete harmonic series octave overblowing seevali double reed keyless gamaka embouchure",
        "expected_slugs": [
            "concept-conical-woodwind-bore-standing-wave-acoustics-and-keyless-gamaka-embouchure"
        ]
    },
    {
        "id": "WND-03",
        "title": "Hardwickia binata (Acha-Maram) Century Seasoning & Bell",
        "query": "Hardwickia binata acha maram century seasoned heritage house pillar high density bore acoustic impedance Ficus religiosa arasu anasu",
        "expected_slugs": [
            "concept-hardwickia-binata-acha-maram-century-seasoning-density-and-acoustic-impedance"
        ]
    },
    {
        "id": "WND-04",
        "title": "Bari vs. Timiri Scaling & Brahma-Swaram Wax Vents",
        "query": "Timiri vs Bari Nagaswaram bore length scaling irandu kattai five lower brahma swaram vent holes beeswax mezhugu sruti tuning",
        "expected_slugs": [
            "concept-bari-vs-timiri-nagaswaram-scaling-and-brahma-swaram-wax-tuning-physics"
        ]
    },
    {
        "id": "WND-05",
        "title": "Two-Man Rope Lathe & Graduated Thamar Spoon-Augers",
        "query": "Two man strap rope lathe kadai maram eight graduated iron spoon augers thamar conical bore reaming Narasingapettai luthier",
        "expected_slugs": [
            "technology-narasingapettai-bow-lathe-turning-and-graduated-thamar-conical-auger-boring"
        ]
    },
    {
        "id": "WND-06",
        "title": "Korkai-Tattai Paddy-Granary Curing & Seevali Making",
        "query": "Phragmites karka korkai tattai river reed twelve month paddy granary nel kudhir curing rice starch boiling seevali kandai",
        "expected_slugs": [
            "technology-korkai-tattai-reed-paddy-curing-seevali-shaping-and-brass-kombu-brazing"
        ]
    },
    {
        "id": "WND-07",
        "title": "Pirai-Kombu Crescent Horns & Nedun-Tharai Trumpets",
        "query": "Three piece crescent Pirai Kombu S Kombu Thuthari brass tension strut straight telescoping Nedun Tharai Ekkalam temple horn",
        "expected_slugs": [
            "artifact-pirai-kombu-s-kombu-brass-horns-and-nedun-tharai-temple-trumpets"
        ]
    },
    {
        "id": "WND-08",
        "title": "Narasingapettai GI Acha-Maram Nagaswaram Haven",
        "query": "Narasingapettai Kumbakonam Thiruvavaduthurai Adheenam Ranganathan Achari GI tagged Bari Nagaswaram marutham luthier haven",
        "expected_slugs": [
            "place-narasingapettai-ancient-chola-acha-maram-nagaswaram-and-wind-instrument-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Conical Bore Wind Instruments, Acha-Maram Nagaswaram Turning, Seevali Reed Acoustics & Brass Kombu-Tharai Craft")
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
