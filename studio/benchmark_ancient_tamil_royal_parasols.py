#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Ceremonial Parasols, Palmyra & Silk Umbrella Craft & Venkotrakkudai Regalia
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
        "id": "UMB-01",
        "title": "Sangam & Silappadikaram Venkotrakkudai Accounts",
        "query": "Purananuru Tirukkural Silappadikaram Indira Vizha Venkotrakkudai Kudai Natkol Muthukkudai literary verses",
        "expected_slugs": [
            "text-sangam-and-silappadikaram-on-venkotrakkudai-royal-parasol-and-muthukkudai"
        ]
    },
    {
        "id": "UMB-02",
        "title": "Venkotrakkudai Arul Shade & Senkol Cosmology",
        "query": "Venkotrakkudai royal white parasol protective shade arul mercy full moon symbolism Senkol justice pairing",
        "expected_slugs": [
            "concept-venkotrakkudai-protective-shade-arul-sovereignty-and-senkol-cosmology"
        ]
    },
    {
        "id": "UMB-03",
        "title": "Collapsible Radial Bamboo Rib & Runner Hub Mechanics",
        "query": "Collapsible radial bamboo rib kinematics kudai kambi sliding cylindrical runner hub dome biaxial tension",
        "expected_slugs": [
            "concept-collapsible-radial-bamboo-rib-kinematics-and-runner-hub-tension"
        ]
    },
    {
        "id": "UMB-04",
        "title": "Kudai-Kambi Splitting, Hub Turning & Silk Gore Stretching",
        "query": "Kudai kambi bamboo rib gauge scraping bow lathe turned wooden hub mortising triangular silk gore stretching",
        "expected_slugs": [
            "technology-kudai-kambi-bamboo-spindle-splitting-hub-mortising-and-silk-stretching"
        ]
    },
    {
        "id": "UMB-05",
        "title": "Olai-Kudai Palmyra Leaf Braiding & Agrarian Rain Hat",
        "query": "Olai kudai palmyra palm leaf braiding Borassus flabellifer rattan rim kambur hands free paddy rain umbrella",
        "expected_slugs": [
            "technology-olai-kudai-palmyra-leaf-braiding-and-monsoon-field-umbrella-weft"
        ]
    },
    {
        "id": "UMB-06",
        "title": "Muthukkudai Pearl Parasol, Irattai-Kudai & Kalasam Finials",
        "query": "Muthukkudai pearl fringed parasol Irattai Kudai twin processional temple umbrellas gilded brass kalasam finial",
        "expected_slugs": [
            "artifact-muthukkudai-pearl-fringed-parasol-irattai-kudai-and-kalasam-finials"
        ]
    },
    {
        "id": "UMB-07",
        "title": "Ullurai & Vithanam Canopy Iconography & Acoustic Damping",
        "query": "Ullurai underside lining Vithanam suspended ceiling canopy Ashtadikpalakas lotus mandala mandapa acoustic damping",
        "expected_slugs": [
            "concept-ullurai-and-vithanam-appliqued-ceiling-canopy-iconography-and-geometry"
        ]
    },
    {
        "id": "UMB-08",
        "title": "Thirunageswaram Chola Royal Parasol & Silk Canopy Haven",
        "query": "Thirunageswaram Kumbakonam Chola Naganathaswamy silk weaving temple applique canopy parasol haven 10.9630 79.4290",
        "expected_slugs": [
            "place-thirunageswaram-ancient-chola-royal-parasol-and-silk-canopy-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Ceremonial Parasols, Palmyra & Silk Umbrella Craft & Venkotrakkudai Regalia")
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
