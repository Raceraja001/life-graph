#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Seashell & Kankar Lime Calcination, Chunnambu-Kalavasal Kilns, Slaking Kinetics & Sudhai Stucco Sculpting
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
        "id": "CHN-01",
        "title": "Sangam Literary References to Ven-Sudhai White Mansions",
        "query": "Pattinappalai Nedunalvadai Maduraikanchi Perumpanarruppadai ven-sudhai-maadam white seashell lime plastered mansions nilaa-mutram verses",
        "expected_slugs": [
            "text-sangam-literature-on-ven-sudhai-white-lime-mansions-and-stucco-palaces"
        ]
    },
    {
        "id": "CHN-02",
        "title": "Thermodynamics of Seashell & Kankar Calcination & Slaking",
        "query": "Biogenic aragonite kilinjal shells vs pedogenic kankar belite C2S calcination 900 to 1000 C exothermic slaking 65 kJ/mol portlandite recarbonation",
        "expected_slugs": [
            "concept-calcium-carbonate-calcination-thermodynamics-exothermic-slaking-and-recarbonation"
        ]
    },
    {
        "id": "CHN-03",
        "title": "Kadukkai Tannin, Karuppatti Sucrate & Ovalbumin Mortar Chemistry",
        "query": "Terminalia chebula kadukkai gallotannin fermented palm jaggery karuppatti calcium sucrate vilvam gum egg-white ovalbumin palingu lime mortar",
        "expected_slugs": [
            "concept-kadukkai-tannin-karuppatti-sucrose-and-vilvam-biopolymer-lime-mortar-chemistry"
        ]
    },
    {
        "id": "CHN-04",
        "title": "Sudhai-Sirpam Gopuram Mechanics & Edible Vetrilai-Chunnambu",
        "query": "Gopuram Sudhai-Sirpam low dead-load cut-brick salakai armature graded modulus edible vetrilai-chunnambu arecoline hydrolysis thamboolam",
        "expected_slugs": [
            "concept-sudhai-sirpam-stucco-statuary-mechanics-and-edible-vetrilai-chunnambu-alkalinity"
        ]
    },
    {
        "id": "CHN-05",
        "title": "Chunnambu-Kalavasal Shaft Kiln & Curd-Coconut Slaking",
        "query": "Chunnambu-kalavasal vertical shaft kiln stratified charcoal shell charging thuruthi bellows buttermilk tender coconut water slaking neertruthal",
        "expected_slugs": [
            "technology-chunnambu-kalavasal-draft-kiln-charging-and-water-curd-slaking-protocols"
        ]
    },
    {
        "id": "CHN-06",
        "title": "Chunnambu-Chekku Edge-Runner Milling & Palingu Burnishing",
        "query": "Bullock-drawn annular stone trough chunnambu-chekku kaal-vai 1-ton granite wheel wet attrition grinding five-coat troweling palingu-kal burnishing",
        "expected_slugs": [
            "technology-chunnambu-chekku-circular-stone-edge-runner-grinding-and-palingu-burnishing"
        ]
    },
    {
        "id": "CHN-07",
        "title": "Kilinjal Clam Shells, Kankar Nodules & Brass Chunnambu-Dappa",
        "query": "Meretrix Anadara estuarine kilinjal shells Pinctada mutthu-chippi kankar nodules chained brass pocket lime casket chunnambu-dappa",
        "expected_slugs": [
            "artifact-kilinjal-clam-shells-kankar-nodules-and-brass-vetrilai-chunnambu-dappa-caskets"
        ]
    },
    {
        "id": "CHN-08",
        "title": "Muthupet Kaveri Delta Lagoon Seashell & Lime Kiln Haven",
        "query": "Muthupet Tiruvarur district 10.4000 79.5000 Koraiyar Paminiyar Palk Strait mangrove lagoon sub-fossil kilinjal shell beds chunnambu haven",
        "expected_slugs": [
            "place-muthupet-ancient-lagoon-seashell-calcination-and-chunnambu-kiln-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Seashell & Kankar Lime Calcination, Chunnambu-Kalavasal Kilns, Slaking Kinetics & Sudhai Stucco Sculpting")
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
