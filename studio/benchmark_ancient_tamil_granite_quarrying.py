#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Granite Stone Quarrying, Wedging Pyrotechnics & Monolithic Sculpting
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "QUR-01",
        "name": "Mandagapattu Inscription Verse",
        "query": "Mandagapattu inscription royal epigraph on King Vichitrachitta brickless architecture living rock shrines",
        "expected": [
            "text-mandagapattu-inscription-verses-on-mahendravarman-brickless-rock-cut-shrines"
        ]
    },
    {
        "id": "QUR-02",
        "name": "Granite Cleavage & Wedging",
        "query": "Kal thatchu granite cleavage planes fire setting thermal spalling hydraulic dry wood wedging",
        "expected": [
            "concept-kal-thatchu-granite-cleavage-planes-thermal-expansion-and-hydraulic-wedging"
        ]
    },
    {
        "id": "QUR-03",
        "name": "Rock-Cut Cave Excavation",
        "query": "Kudavarai subtractive monolithic excavation perimeter trenching and bas relief carving",
        "expected": [
            "technology-kudavarai-monolithic-cave-excavation-trenching-and-relief-sculpting"
        ]
    },
    {
        "id": "QUR-04",
        "name": "Wootz Steel Chisels",
        "query": "Uluki and sitra crucible wootz steel stone chisels hardened drifts and plumb bobs",
        "expected": [
            "artifact-uluki-and-sitra-hardened-steel-chisels-iron-drifts-and-measuring-plumb-lines"
        ]
    },
    {
        "id": "QUR-05",
        "name": "Talamana Sculptural Canon",
        "query": "Talamana metrology canonical anthropometric proportions angula units and granite aesthetics",
        "expected": [
            "concept-sirpa-sastra-talamana-iconographic-proportions-and-granite-crystallography"
        ]
    },
    {
        "id": "QUR-06",
        "name": "Pallava Stonemasons Guild",
        "query": "Kal thatchar corporation of royal Pallava stonemasons quarrymen and master sculptors",
        "expected": [
            "institution-kal-thatchar-corporation-of-pallava-master-sculptors-and-quarrymen"
        ]
    },
    {
        "id": "QUR-07",
        "name": "Pancha Ratha Monoliths",
        "query": "Pancha Ratha monoliths freestanding monolith carving entablature cantilever open air bas reliefs",
        "expected": [
            "technology-ratha-monolith-entablature-cantilever-and-bas-relief-undercutting"
        ]
    },
    {
        "id": "QUR-08",
        "name": "Granite Sculpting Haven",
        "query": "Mamallapuram ancient Pallava ocean citadel living rock sculpting haven UNESCO landmark",
        "expected": [
            "place-mamallapuram-ancient-pallava-granite-sculpting-haven"
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
    print("BENCHMARK: Ancient Tamil Granite Stone Quarrying, Wedging Pyrotechnics & Monolithic Sculpting")
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
