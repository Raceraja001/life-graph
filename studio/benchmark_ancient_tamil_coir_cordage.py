#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Coir Cordage, Brackish Lagoon Coconut Fibre Retting & Marine Caulking Engineering
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
        "id": "COR-01",
        "title": "Sangam Coir Ships Verses",
        "query": "Perumpanarruppadai Pattinappalai coconut coir cordage stitched ships ocean vangams verses",
        "expected_slugs": [
            "text-perumpanarruppadai-and-pattinappalai-on-coir-stitched-ships"
        ]
    },
    {
        "id": "COR-02",
        "title": "Coconut Mesocarp Retting Chemistry",
        "query": "Cocos nucifera mesocarp lignocellulose anaerobic lagoon retting kinetics pectinolysis",
        "expected_slugs": [
            "concept-cocos-nucifera-mesocarp-lignocellulose-and-anaerobic-retting"
        ]
    },
    {
        "id": "COR-03",
        "title": "Mallet Defibration Spinning Wheel",
        "query": "Mallet defibration spinning wheel thiri reverse two ply cordage twisting raattai",
        "expected_slugs": [
            "technology-manual-beating-spinning-wheel-thiri-and-reverse-ply-cordage"
        ]
    },
    {
        "id": "COR-04",
        "title": "Stitched Ship Planks Artifact",
        "query": "Marakkalam stitched timber planks heavy coir rigging dammar tree resin caulking",
        "expected_slugs": [
            "artifact-marakkalam-stitched-planks-coir-rigging-and-resin-caulking"
        ]
    },
    {
        "id": "COR-05",
        "title": "Coir Tensile Mechanics",
        "query": "Coir fiber tensile mechanics saltwater wet elongation elasticity rot resistance",
        "expected_slugs": [
            "concept-coir-tensile-strength-saltwater-elongation-and-rot-resistance"
        ]
    },
    {
        "id": "COR-06",
        "title": "Coir Spinners Guild Corporation",
        "query": "Kayittru valaiignar vanga marakkar guild coir spinners shipwright corporation",
        "expected_slugs": [
            "institution-kayittru-valaiignar-and-vanga-marakkar-guild-of-coir-spinners"
        ]
    },
    {
        "id": "COR-07",
        "title": "Marine Caulking Pyrotechnics",
        "query": "Marine caulking pyrotechnics dammar pitch melting kungiliyam estuarine seam packing",
        "expected_slugs": [
            "technology-marine-caulking-resin-pitch-melting-and-seam-packing"
        ]
    },
    {
        "id": "COR-08",
        "title": "Kottaipattinam Coir Haven",
        "query": "Kottaipattinam ancient coir cordage haven Palk Strait lagoon stitched ship citadel",
        "expected_slugs": [
            "place-kottaipattinam-ancient-coir-cordage-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Coir Cordage, Brackish Lagoon Coconut Fibre Retting & Marine Caulking Engineering")
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
