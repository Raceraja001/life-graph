#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Kolam Threshold Geometry, Pulli-Sikku Eulerian Graph Topology & Rice-Flour Ecology
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
        "id": "SIK-01",
        "title": "Nachiyar Tirumozhi & Classical Mezhukkidu References",
        "query": "Andal Nachiyar Tirumozhi Tiruppavai Purananuru mezhukkidu cow dung plastering threshold kolam thoyyil",
        "expected_slugs": [
            "text-nachiyar-tirumozhi-and-classical-tamil-references-to-mezhukkidu-and-threshold-kolam"
        ]
    },
    {
        "id": "SIK-02",
        "title": "Sikku-Kolam Pulli-Grid Eulerian Graph Topology",
        "query": "Sikku Kolam Neli Kolam continuous closed Eulerian circuit loop 4 regular planar graph ner pulli idukku pulli",
        "expected_slugs": [
            "concept-sikku-kolam-pulli-grid-eulerian-graph-topology-and-braid-theory"
        ]
    },
    {
        "id": "SIK-03",
        "title": "Dihedral Symmetry Groups, Fractals & Array Grammars",
        "query": "Dihedral symmetry groups D4 C4 Gift Siromoney array grammars L system fractal space filling Kolusu Pavithram",
        "expected_slugs": [
            "concept-dihedral-symmetry-groups-fractal-self-similarity-and-ethnomathematical-array-grammars"
        ]
    },
    {
        "id": "SIK-04",
        "title": "Rice-Flour Bhuta-Yajna Ecology & Saanam-Thelippu",
        "query": "Podi kolam dry rice flour bhuta yajna micro charity feeding ants sparrows saanam thelippu cow dung dust binding",
        "expected_slugs": [
            "concept-podi-kolam-rice-flour-bhuta-yajna-ecology-and-saanam-thelippu-microbial-hygiene"
        ]
    },
    {
        "id": "SIK-05",
        "title": "Podi-Kolam Thumb-Index Pinch Kinematics",
        "query": "Podi kolam thumb index finger pinch shear release viral idukku straight knee hip bend freehand pulli registration",
        "expected_slugs": [
            "technology-podi-kolam-thumb-index-pinch-kinematics-and-pulli-matrix-registration"
        ]
    },
    {
        "id": "SIK-06",
        "title": "Wet Maa-Kolam Rice Batter & Kaavi-Kodu Red Ochre",
        "query": "Maa kolam izhaik kolam wet stone ground raw rice paste cotton wick Padi Kolam kaavi kodu ferruginous red ochre border",
        "expected_slugs": [
            "technology-maa-kolam-wet-rice-paste-grinding-and-kaavi-red-ochre-border-framing"
        ]
    },
    {
        "id": "SIK-07",
        "title": "Margazhi Saana-Pillaiyar & Poosani-Poo Pumpkin Blossoms",
        "query": "Margazhi Saana Pillaiyar cow dung cone golden yellow poosani poo pumpkin flower Cucurbita maxima Bhogi varatti",
        "expected_slugs": [
            "artifact-margazhi-poosani-poo-pumpkin-blossoms-and-saana-pillaiyar-threshold-cones"
        ]
    },
    {
        "id": "SIK-08",
        "title": "Mylapore Kapaleeswarar Mada-Veedhi Kolam Haven",
        "query": "Mylapore Mayilappur Kapaleeswarar Temple Chitrakulam Mada Veedhi neithal Margazhi threshold Sikku Kolam haven",
        "expected_slugs": [
            "place-mylapore-ancient-kapaleeswarar-agrahara-kolam-and-threshold-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Kolam Threshold Geometry, Pulli-Sikku Eulerian Graph Topology & Rice-Flour Ecology")
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
