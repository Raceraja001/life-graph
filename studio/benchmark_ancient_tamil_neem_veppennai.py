#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Neem Agroforestry, Veppennai Sekku Cold-Pressing, Azadirachtin Antifeedant Phytochemistry & Mariamman Prophylactic Ecology
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
        "id": "VMB-01",
        "title": "Sangam Verses on Pandya Veppam Flower Chaplets & Bitter Margosa",
        "query": "Purananuru Nedunchezhiyan Talaiyalanganam veppam pum kanni neem flower battle chaplet bitter cure Kuruntokai Akananuru",
        "expected_slugs": [
            "text-sangam-corpus-purananuru-and-marutham-poems-on-veppam-garlands-and-medicinal-bitterness"
        ]
    },
    {
        "id": "VMB-02",
        "title": "Azadirachtin Limonoid Stereochemistry & Ecdysteroid Inhibition",
        "query": "Azadirachtin C35H44O16 seco tetranortriterpenoid limonoids prothoracicotropic PTTH ecdysone 20-hydroxyecdysone eclosion inhibition antifeedant",
        "expected_slugs": [
            "concept-azadirachtin-tetranortriterpenoid-limonoid-eclosion-inhibition-and-antifeedant-action"
        ]
    },
    {
        "id": "VMB-03",
        "title": "Gedunin, Nimbidin Triterpenes & Siddha Dermatological Pharmacology",
        "query": "Gedunin nimbidin nimbolide triterpenes Trichophyton rubrum dermatophytic fungi scabies Sarcoptes scabiei Siddha Gunavagadam",
        "expected_slugs": [
            "concept-veppam-bitter-triterpenes-gedunin-nimbidin-and-dermatological-antimicrobial-pharmacology"
        ]
    },
    {
        "id": "VMB-04",
        "title": "Veppam Seed Depulping & Vagai Wood Sekku Cold Pressing",
        "query": "Veppam seed depulping water soaking kalam drying moisture 8 percent Albizia lebbeck vagai wood sekku cold pressing 45C",
        "expected_slugs": [
            "technology-veppam-seed-depulping-sun-drying-and-vagai-wood-sekku-cold-pressing"
        ]
    },
    {
        "id": "VMB-05",
        "title": "Veppilai Smoke Fumigation, NSKE Aqueous Spray & Granary Defense",
        "query": "Veppilai herbal smoke pugai fumigation crude aqueous extract spray 5 percent NSKE cow dung kuthir granary Sitophilus oryzae",
        "expected_slugs": [
            "technology-veppilai-herbal-fumigation-crude-water-extract-spray-and-grain-protection"
        ]
    },
    {
        "id": "VMB-06",
        "title": "Bitter Veppennai Oil, Pinnakku Seed Cake & Glazed Earthen Jars",
        "query": "Cold pressed sulfurous pungent veppennai de-oiled veppam pinnakku seed cake Nitrosomonas nitrification inhibitor mankaala jaadi",
        "expected_slugs": [
            "artifact-cold-pressed-bitter-veppennai-seed-cake-fertilizer-and-earthen-storage-jars"
        ]
    },
    {
        "id": "VMB-07",
        "title": "Mariamman Foliar Cooling, Variola Quarantine & Ritual Hygiene",
        "query": "Mariamman temple cooling foliar prophylaxis Variola smallpox muthu kuthal veppilai kothu doorway quarantine ammai fermented koozh",
        "expected_slugs": [
            "concept-mariamman-shrine-cooling-foliar-prophylaxis-epidemic-quarantine-and-ritual-ecology"
        ]
    },
    {
        "id": "VMB-08",
        "title": "Samayapuram Mariamman Neem Agroforestry & Oil Haven",
        "query": "Samayapuram Mariamman temple Kaveri delta 10.9280 78.7420 sacred margosa grove Poo-Chorithal festival sekku veppennai haven",
        "expected_slugs": [
            "place-samayapuram-ancient-kaveri-veppam-agroforestry-and-veppennai-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Neem Agroforestry, Veppennai Sekku Cold-Pressing, Azadirachtin Antifeedant Phytochemistry & Mariamman Prophylactic Ecology")
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
