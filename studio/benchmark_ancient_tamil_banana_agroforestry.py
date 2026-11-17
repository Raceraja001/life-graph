#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Banana Cultivar Biodiversity, Vazhai-Naar Pseudostem Fiber Craft, Vazhai-Ilai Dining Science & Mukkani Agroforestry
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
        "id": "VZH-01",
        "title": "Sangam Vazhai & Mukkani Fruit Trinity Accounts",
        "query": "Kurinjippattu Malaipadukadam Ainkurunuru Purananuru malai vazhai Mukkani Maa Pala Vazhai verses",
        "expected_slugs": [
            "text-sangam-corpus-on-vazhai-plantains-mukkani-trinity-and-kurinji-hill-groves"
        ]
    },
    {
        "id": "VZH-02",
        "title": "Tamil Musa Cultivar Biodiversity & Landraces",
        "query": "Tamil Musa cultivar biodiversity Sirumalai Virupakshi hill banana Sevvazhai Kanyakumari Matti Poovan Monthan ecotypes",
        "expected_slugs": [
            "concept-tamil-musa-cultivar-biodiversity-sirumalai-virupakshi-sevvazhai-and-matti-ecotypes"
        ]
    },
    {
        "id": "VZH-03",
        "title": "Thalai-Vazhai Ilai Epicuticular Wax & Dining Etiquette",
        "query": "Thalai vazhai ilai hydrophobic epicuticular wax epigallocatechin gallate polyphenols narrow tip pointing left virundhu dining geometry",
        "expected_slugs": [
            "concept-thalai-vazhai-ilai-epicuticular-wax-chemistry-and-virundhu-course-geometry"
        ]
    },
    {
        "id": "VZH-04",
        "title": "Vazhai-Naar Pseudostem Fiber & Poo-Kattuthal Garland Tying",
        "query": "Vazhai naar pseudostem leaf sheath stripping vazhai pattai decortication poo kattuthal jasmine flower garland knotting",
        "expected_slugs": [
            "technology-vazhai-naar-pseudostem-sheath-stripping-decortication-and-flower-garland-knotting"
        ]
    },
    {
        "id": "VZH-05",
        "title": "Eetti-Kandru Sword Suckers & Smoke-Chamber Ripening",
        "query": "Eetti kandru sword sucker selection earthen pit pugai moodam ethylene smoke ripening waterless Panchamirtham preservation",
        "expected_slugs": [
            "technology-kandru-sucker-selection-smoke-pit-ripening-and-panchamirtham-fruit-maceration"
        ]
    },
    {
        "id": "VZH-06",
        "title": "Kula-Vazhai Gateway Pillars, Vazhaipoo & Vazhaithandu",
        "query": "Twin kula vazhai fruited wedding pandal gateway pillars purple vazhaipoo inflorescence kalan pistil removal vazhaithandu core",
        "expected_slugs": [
            "artifact-kula-vazhai-fruited-gateway-pillars-vazhaipoo-inflorescence-and-vazhaithandu-cores"
        ]
    },
    {
        "id": "VZH-07",
        "title": "Vazhaithandu Kidney-Stone Dissolution & Vazhaiyadi-Vazhai",
        "query": "Vazhaithandu juice potassium citrate kalladaippu calcium oxalate kidney stone dissolution vazhaiyadi vazhai rhizome lineage symbolism",
        "expected_slugs": [
            "concept-vazhaithandu-lithotriptic-potassium-citrate-and-kula-vazhai-rhizome-lineage-symbolism"
        ]
    },
    {
        "id": "VZH-08",
        "title": "Sirumalai Pandya Hill-Plantain & Vazhai Biodiversity Haven",
        "query": "Sirumalai hills Dindigul Madurai GI tagged Sirumalai Malai Vazhai Pandya Kurinji orchard haven 10.1940 77.9960",
        "expected_slugs": [
            "place-sirumalai-ancient-pandya-hill-plantain-and-vazhai-biodiversity-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Banana Cultivar Biodiversity, Vazhai-Naar Pseudostem Fiber Craft, Vazhai-Ilai Dining Science & Mukkani Agroforestry")
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
