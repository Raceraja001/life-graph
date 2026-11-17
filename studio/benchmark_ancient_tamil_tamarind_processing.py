#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Tamarind Orchard Agroforestry, Tartaric Acid Preservation, Seed Starch Sizing & Culinary-Metallurgical Chemistry
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
        "id": "TAM-01",
        "title": "Sangam Poetic References to Puli Stews & Puli-Choru",
        "query": "Purananuru Akananuru Perumpanarruppadai Kuruntokai Natrinai puli tamarind broth puli-choru caravan rations literary references",
        "expected_slugs": [
            "text-sangam-literature-on-puli-tamarind-broths-puli-choru-and-arid-zone-cuisine"
        ]
    },
    {
        "id": "TAM-02",
        "title": "D-Tartaric Acid Biochemistry & Pazhampuli Maillard Aging",
        "query": "D-tartaric acid 12 to 18 percent malic acid pectin pazhampuli aged black tamarind Maillard browning melanoidins HMF",
        "expected_slugs": [
            "concept-tamarind-d-tartaric-acid-biochemistry-and-pazhampuli-maillard-aging"
        ]
    },
    {
        "id": "TAM-03",
        "title": "Puliyankottai Xyloglucan Polysaccharide Warp-Sizing Chemistry",
        "query": "Puliyankottai tamarind kernel powder xyloglucan polysaccharide beta-1-4-glucan handloom cotton warp sizing paavu-kanji mural gesso",
        "expected_slugs": [
            "concept-puliyankottai-xyloglucan-seed-polysaccharide-rheology-and-binding-chemistry"
        ]
    },
    {
        "id": "TAM-04",
        "title": "Tamarind-Salt Copper Oxide Chelation & Bronze Pickling",
        "query": "Sour tamarind pulp rock salt copper oxide carbonate kalimbu tarnish removal bidentate copper tartrate chelation panchaloha bronze pickling",
        "expected_slugs": [
            "concept-tamarind-tartrate-copper-oxide-chelation-and-bronze-icon-acid-pickling"
        ]
    },
    {
        "id": "TAM-05",
        "title": "Puli-Ulaithal Harvesting, Shell Cracking & Stone-Anvil Deseeding",
        "query": "Puli-ulaithal bamboo hook canopy shaking odu-thattuthal shell cracking naar-eduthal fiber stripping kottai-thattuthal deseeding workflow",
        "expected_slugs": [
            "technology-puli-ulaithal-harvesting-shell-cracking-and-stone-anvil-seed-decortication"
        ]
    },
    {
        "id": "TAM-06",
        "title": "Puliyankottai Sand-Roasting, Testa Removal & Famine Flour",
        "query": "Puliyankottai hot quartz sand roasting astringent tannin testa removal wood-ash water leaching drought famine cakes",
        "expected_slugs": [
            "technology-puliyankottai-roasting-wet-milling-warp-sizing-and-famine-flour-leaching"
        ]
    },
    {
        "id": "TAM-07",
        "title": "Saalai-Puli-Maram Highway Avenues & Puli-Vari Tree Taxes",
        "query": "Saalai-puli-maram wayside highway shade avenues Queen Mangammal puli-vari marap-padai tree tax inscriptions puli-kuthagai auctions",
        "expected_slugs": [
            "institution-saalai-puli-maram-avenue-endowments-and-marap-puli-vari-tree-tax-tenures"
        ]
    },
    {
        "id": "TAM-08",
        "title": "Usilampatti Madurai Dryland Tamarind Grove Haven",
        "query": "Usilampatti Madurai district 9.9650 77.7880 mullai dryland tamarind grove puliyanthoppu Andipatti gap processing haven",
        "expected_slugs": [
            "place-usilampatti-ancient-madurai-tamarind-grove-and-puli-processing-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Tamarind Orchard Agroforestry, Tartaric Acid Preservation, Seed Starch Sizing & Culinary-Metallurgical Chemistry")
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
