#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Temple Stone Inscription Epigraphy, Vatteluttu Chisel Engraving & Copper-Plate Scribing
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "EPG-01",
        "name": "Velvikudi Grant Charter",
        "query": "Velvikudi grant copper plate charter Jatila Parantaka Nedunjadayan Pandya bilingual",
        "expected": [
            "text-velvikudi-grant-bilingual-sanskrit-tamil-copper-plate-charter-of-nedunjadayan"
        ]
    },
    {
        "id": "EPG-02",
        "name": "Vatteluttu Chisel Kinematics",
        "query": "Tamil epigraphical palaeography Vatteluttu chisel incising kinematics granite stone chipping",
        "expected": [
            "concept-epigraphical-palaeography-vatteluttu-evolution-and-chisel-incising-kinematics"
        ]
    },
    {
        "id": "EPG-03",
        "name": "Copper Plate Metallurgy",
        "query": "Chembettu copper plate cold hammering annealing bronze ring soldering royal seal casting",
        "expected": [
            "technology-copper-plate-lost-wax-sheet-hammering-ring-soldering-and-royal-seal-casting"
        ]
    },
    {
        "id": "EPG-04",
        "name": "Copper Charters Artifact",
        "query": "Chembettu copper charters cast bronze Pandya bull seal hardened steel burin gravers",
        "expected": [
            "artifact-chembettu-copper-plates-bronze-bull-seals-and-hardened-steel-gravers"
        ]
    },
    {
        "id": "EPG-05",
        "name": "Inscriptional Diplomatics",
        "query": "Inscriptional diplomatics royal Meykeerthi eulogies pidi soozhndhu elephant boundary walk",
        "expected": [
            "concept-inscriptional-legal-diplomatics-meykeerthi-praises-and-boundary-survey-verifications"
        ]
    },
    {
        "id": "EPG-06",
        "name": "Sasana Kollan Epigraphers",
        "query": "Sasana kollan perun thatchar guild royal court epigraphers calligraphers coppersmiths",
        "expected": [
            "institution-sasana-kollan-and-perun-thatchar-corporation-of-royal-court-epigraphers"
        ]
    },
    {
        "id": "EPG-07",
        "name": "Lithic Epigraphy Technology",
        "query": "Lithic epigraphy granite surface polishing grid chalking relief chisel engraving temple wall",
        "expected": [
            "technology-granite-dressed-surface-drafting-grid-chalking-and-relief-chisel-engraving"
        ]
    },
    {
        "id": "EPG-08",
        "name": "Velvikudi Charter Haven",
        "query": "Velvikudi ancient Pandyan royal charter haven Vaigai inscriptional archives epigraphical",
        "expected": [
            "place-velvikudi-ancient-pandya-copper-plate-grant-haven"
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
    print("BENCHMARK: Ancient Tamil Temple Stone Inscription Epigraphy, Vatteluttu Chisel Engraving & Copper-Plate Scribing")
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
