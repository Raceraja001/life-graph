#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Jackfruit Agroforestry, Pala-Maram Acoustic Timber Luthiery, Latex Adhesives & Mukkani Preservation
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
        "id": "PLA-01",
        "title": "Sangam Literary References to Ver-Pala & Aasini-Pala",
        "query": "Kurinjippattu Akananuru Natrinai Purananuru Malaipadukadam ver-pala root-borne jackfruit aasini-pala muzhavu drum simile verses",
        "expected_slugs": [
            "text-sangam-literature-on-ver-pala-cauliflorous-jackfruits-aasini-pala-and-mukkani-hospitality"
        ]
    },
    {
        "id": "PLA-02",
        "title": "Pala-Maram Heartwood Acoustics & Flavone Oxidation",
        "query": "Artocarpus heterophyllus pala-maram heartwood acoustic radiation tyloses low shrinkage artocarpin morin flavone oxidation Luthiery",
        "expected_slugs": [
            "concept-artocarpus-heterophyllus-pala-heartwood-acoustic-impedance-and-luthiery-resonance"
        ]
    },
    {
        "id": "PLA-03",
        "title": "Thatti-Parthal Acoustic Ripeness Testing & Varikka Pectin",
        "query": "Thatti-parthal impulse acoustic ripeness testing hollow low-frequency resonance Varikka-Pala vs Koozha-Pala calcium protopectin chemistry",
        "expected_slugs": [
            "concept-pala-thatti-parthal-acoustic-ripeness-testing-and-varikka-vs-koozha-pectin-chemistry"
        ]
    },
    {
        "id": "PLA-04",
        "title": "Pala-Paal Polyisoprene Latex Solvation & Palakottai Starch",
        "query": "Pala-paal cis-1,4-polyisoprene latex triterpene resin non-polar gingelly coconut oil solvation palakottai resistant amylose starch jacalin",
        "expected_slugs": [
            "concept-pala-paal-cis-polyisoprene-latex-hydrophobicity-oil-solvation-and-palakottai-starch"
        ]
    },
    {
        "id": "PLA-05",
        "title": "Pala-Maram Kudam Gouging & Boiled Latex Putty",
        "query": "Senescent jackwood billet shade seasoning curved hollowing adze ul-vaachi kudam-kudaithal boiled pala-paal latex wood putty mezhugu",
        "expected_slugs": [
            "technology-pala-maram-kudam-hollowing-water-seasoning-and-pala-paal-wood-caulking"
        ]
    },
    {
        "id": "PLA-06",
        "title": "Oil-Lubricated Butchery, Pala-Vathal & Sand-Bed Seed Storage",
        "query": "Kaan central latex core excision paddy-straw wisp pala-chulai-varatti dry quartz river sand stratification palakottai storage",
        "expected_slugs": [
            "technology-oil-anointed-pala-butchery-chulai-preserve-drying-and-sand-bed-palakottai-storage"
        ]
    },
    {
        "id": "PLA-07",
        "title": "Ekanda Veena Kudams, Valangaiman Thavil Shells & Manai-Palagai",
        "query": "Monolithic Ekanda Thanjavur Veena kudam Valangaiman Thavil barrel Mridangam-kattai Kanjira hoop auspicious wedding manai-palagai",
        "expected_slugs": [
            "artifact-monolithic-pala-maram-veena-kudam-thavil-barrels-and-carved-manai-planks"
        ]
    },
    {
        "id": "PLA-08",
        "title": "Melpattambakkam–Panruti Gadilam Red-Loam Jackfruit Haven",
        "query": "Melpattambakkam Panruti Cuddalore 11.7780 79.6220 Gadilam River Cuddalore Sandstone red lateritic loam GI jackfruit pala timber haven",
        "expected_slugs": [
            "place-melpattambakkam-ancient-gadilam-jackfruit-grove-and-pala-timber-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Jackfruit Agroforestry, Pala-Maram Acoustic Timber Luthiery, Latex Adhesives & Mukkani Preservation")
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
