#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Palmyrah Sugar Jaggery, Toddy Tapping Ladders & Leaf Basketry
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "JAG-01",
        "name": "Sangam Palmyra Verse",
        "query": "Porunarattruppadai Sangam verses on sweet palmyra sap padhani and crystalline jaggery",
        "expected": [
            "text-porunarattruppadai-verses-on-palmyra-sap-and-crystallized-jaggery"
        ]
    },
    {
        "id": "JAG-02",
        "name": "Palmyra Sugar Chemistry",
        "query": "Karu patti palmyrah sap evaporation sucrose condensation and mineral rich crystallization chemistry",
        "expected": [
            "concept-karu-patti-palmyrah-sap-evaporation-and-crystallization-chemistry"
        ]
    },
    {
        "id": "JAG-03",
        "name": "Lime Coating Biochemistry",
        "query": "Padhani chunnambu slaked lime coating on earthen pots arresting wild yeast sap fermentation",
        "expected": [
            "technology-padhani-chunnambu-slaked-lime-sap-inversion-inhibition-and-calcium-saturation"
        ]
    },
    {
        "id": "JAG-04",
        "name": "Palm Climbing Loops",
        "query": "Panai yerum thalai aerial climbing loops and leather chest harness for towering palm trunks",
        "expected": [
            "artifact-panai-yerum-thalai-and-thottil-aerial-palm-climbing-loops-and-leather-straps"
        ]
    },
    {
        "id": "JAG-05",
        "name": "Arid Agroforestry Physiology",
        "query": "Panai maram arid zone agroforestry deep taproot groundwater interception zero irrigation",
        "expected": [
            "concept-panai-maram-arid-zone-agroforestry-and-zero-irrigation-survival"
        ]
    },
    {
        "id": "JAG-06",
        "name": "Palmyra Guilds",
        "query": "Panai eri and Saanaar hereditary guild of palmyra climbers tree tenure rights",
        "expected": [
            "institution-panai-eri-and-saanaar-guild-of-hereditary-palmyra-climbers"
        ]
    },
    {
        "id": "JAG-07",
        "name": "Palm Leaf Basketry",
        "query": "Panai olai vaai weaving airtight grain storage kottai and moisture proof packaging",
        "expected": [
            "technology-panai-olai-vaai-weaving-and-tight-grain-storage-kottai"
        ]
    },
    {
        "id": "JAG-08",
        "name": "Palm Sugar Haven",
        "query": "Udangudi ancient red sand dune Palmyra karupatti haven Thoothukudi teri palm groves",
        "expected": [
            "place-udangudi-ancient-palmyra-karupatti-haven"
        ]
    }
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Ollama embedding error: {res.text}")
    return res.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Palmyrah Sugar Jaggery, Toddy Tapping Ladders & Leaf Basketry")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        vec = get_bge_embedding(tc["query"])
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector ASC
            LIMIT 5;
        """, (vec, vec))
        rows = cur.fetchall()
        top1 = rows[0][0] if rows else None
        top1_sim = rows[0][1] if rows else 0.0

        if top1 in tc["expected"]:
            passed += 1
            print(f"[PASS] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for r in rows:
                print(f"    - {r[0]} (Sim: {r[1]:.4f})")

    elapsed = time.time() - t0
    acc = (passed / len(TEST_CASES)) * 100
    print("=" * 80)
    print(f"SUMMARY: {passed}/{len(TEST_CASES)} passed ({acc:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    cur.close()
    conn.close()

    if passed < len(TEST_CASES):
        sys.exit(1)

if __name__ == "__main__":
    main()
