#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Palmyra Palm-Leaf Manuscript Writing, Iron Stylus Ezhuthani Engraving & Chuvadi Scriptorium Guild Traditions
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "MSX-01",
        "name": "Tolkappiyam Scribal Colophon",
        "query": "Tolkappiyam colophon olai chuvadi engraving palm leaf scribes iron stylus Sangam manuscript",
        "expected": [
            "text-tolkappiyam-and-agastiyam-colophons-on-olai-chuvadi-engraving-and-manuscript-preservation"
        ]
    },
    {
        "id": "MSX-02",
        "name": "Palmyra Silica Phytolith Biology",
        "query": "Borassus palmyra leaf silica phytoliths vascular bundle hardness stylus engraving mechanics",
        "expected": [
            "concept-borassus-palmyra-leaf-cellular-structure-and-stylus-engraving-mechanics"
        ]
    },
    {
        "id": "MSX-03",
        "name": "Olai Leaf Preparation",
        "query": "Olai palm leaf harvesting boiling turmeric salt smoking neem pressing manuscript substrate",
        "expected": [
            "technology-olai-leaf-harvesting-boiling-smoking-and-pressing-for-manuscript-preparation"
        ]
    },
    {
        "id": "MSX-04",
        "name": "Ezhuthani Stylus Artifact",
        "query": "Ezhuthani iron engraving stylus carbon soot karumbu podi deer hide rubbing pad manuscript toolkit",
        "expected": [
            "artifact-ezhuthani-iron-stylus-knife-and-soot-rubbing-pad"
        ]
    },
    {
        "id": "MSX-05",
        "name": "Archival Chemistry",
        "query": "Palm leaf manuscript humidity silica cracking fungal decay preservation turmeric neem oil archival chemistry",
        "expected": [
            "concept-palm-leaf-manuscript-humidity-temperature-and-long-term-archival-chemistry"
        ]
    },
    {
        "id": "MSX-06",
        "name": "Hair Cord Binding",
        "query": "Chuvadi binding dual hole threading mayir kayiru hair cord wooden cover boards humidity adaptive",
        "expected": [
            "technology-chuvadi-binding-threading-hair-cord-and-wooden-cover-boards"
        ]
    },
    {
        "id": "MSX-07",
        "name": "Alwarthirunagari Scriptorium Guild",
        "query": "Alwarthirunagari scriptorium guild master scribes Naalayira Divyaprabandham Nammalwar Vaishnava manuscripts",
        "expected": [
            "institution-alwarthirunagari-chuvadi-scriptorium-guild-of-master-scribes-and-copyists"
        ]
    },
    {
        "id": "MSX-08",
        "name": "Scriptorium Haven Place",
        "query": "Alwarthirunagari ancient Tamil palm leaf scriptorium haven Tamirabarani River Tirunelveli",
        "expected": [
            "place-alwarthirunagari-ancient-palm-leaf-scriptorium-haven"
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
    print("BENCHMARK: Ancient Tamil Palmyra Palm-Leaf Manuscript Writing, Iron Stylus Ezhuthani Engraving & Chuvadi Scriptorium Guild Traditions")
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
