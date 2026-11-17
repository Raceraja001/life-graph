#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Bamboo & Rattan Basketry, Muram Winnowing Aerodynamics, Grain Silos & Medavar Plaiting Craft
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
        "id": "BSK-01",
        "title": "Sangam Literary References to Muram Winnowing & Millet Chaffing",
        "query": "Purananuru Kurinjippattu Natrinai Akananuru muram winnowing fan murathal puli oottiya tiger Kurinji thinai millet verses",
        "expected_slugs": [
            "text-sangam-literature-on-muram-winnowing-fans-kurinji-millet-chaffing-and-bamboo-baskets"
        ]
    },
    {
        "id": "BSK-02",
        "title": "Muram Trapezoidal Aerodynamics & Granular Percolation",
        "query": "Muram trapezoidal winnowing tray aerodynamics counter-rotating front-lip air vortex pudaitthal kozhippu Brazil-nut granular percolation",
        "expected_slugs": [
            "concept-muram-trapezoidal-aerodynamics-granular-brazil-nut-segregation-and-vortex-winnowing"
        ]
    },
    {
        "id": "BSK-03",
        "title": "Kal-Moongil Vascular Bundle Gradient & Twill Mechanics",
        "query": "Dendrocalamus strictus kal-moongil Bambusa bambos perumoongil opal silica outer epidermis mel-pattai sclerenchyma 2/2 twill anisotropy",
        "expected_slugs": [
            "concept-dendrocalamus-strictus-kal-moongil-vascular-bundle-mechanics-and-twill-anisotropy"
        ]
    },
    {
        "id": "BSK-04",
        "title": "Cow-Dung Red-Earth Composite Sealing & Thombai Respiration",
        "query": "Pasu-saanam cow dung lignocellulose mucoprotein semman red earth composite coating Sitophilus weevil barrier thombai silo respiration",
        "expected_slugs": [
            "concept-cow-dung-red-earth-composite-sealing-and-thombai-bamboo-silo-hygroscopic-respiration"
        ]
    },
    {
        "id": "BSK-05",
        "title": "Thumb-Guarded Splint Gauging, Herringbone Twill Plaiting & Corner Folding",
        "query": "Moongil splitting thumb-guarded splint gauging herringbone twill plaiting 45-degree muram gusset corner folding vilimbu-kattuthal rim hooping",
        "expected_slugs": [
            "technology-moongil-splitting-thumb-guarded-splint-gauging-and-herringbone-twill-plaiting"
        ]
    },
    {
        "id": "BSK-06",
        "title": "Muram, Valli-Koodai Panniers & Kozhi-Koodu Poultry Domes",
        "query": "Kala-muram siru-muram radial-ribbed valli-koodai head-load pannier open-hexagonal kozhi-koodu poultry coop seer-muram typology",
        "expected_slugs": [
            "artifact-muram-winnowing-trays-kozhi-koodu-poultry-domes-and-valli-koodai-harvest-baskets"
        ]
    },
    {
        "id": "BSK-07",
        "title": "Medavar & Kuravar Bamboo Guilds & Ritual Grain Shares",
        "query": "Medavar Mahendra Malai-Kuravar bamboo-weaving guilds clump thinning ethics wedding seer-muram threshing floor sudhanthiram grain share",
        "expected_slugs": [
            "institution-medavar-and-kuravar-bamboo-plaiting-guilds-and-malai-moongil-forest-coupes"
        ]
    },
    {
        "id": "BSK-08",
        "title": "Anaimalai–Vettaikaranpudur Foothill Bamboo Basketry Haven",
        "query": "Anaimalai Vettaikaranpudur Pollachi Coimbatore 10.5580 76.9360 Topslip Aliyar foothill bamboo basketry muram weaving haven",
        "expected_slugs": [
            "place-anaimalai-ancient-vettai-karan-pudur-bamboo-basketry-and-muram-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Bamboo & Rattan Basketry, Muram Winnowing Aerodynamics, Grain Silos & Medavar Plaiting Craft")
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
