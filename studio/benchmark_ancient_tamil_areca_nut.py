#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Areca Nut Horticulture, Kalipakku Tannin-Boiling Curing, Pakku-Vetti Lever Shears & Tambula Rituals
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
        "id": "PKU-01",
        "title": "Sangam & Silappadikaram Kamugu & Adaikkai Accounts",
        "query": "Perumpanarruppadai Pattinappalai Maduraikanchi Silappadikaram kamugu kazhugu areca palm adaikkai tambulam",
        "expected_slugs": [
            "text-sangam-and-silappadikaram-on-kamugu-areca-palms-and-adaikkai-tambulam"
        ]
    },
    {
        "id": "PKU-02",
        "title": "Areca Tannin, Arecoline & Alkaline Ortho-Quinone Reddening",
        "query": "Areca catechu ruminate endosperm catechin procyanidin tannins arecoline alkaloid alkaline slaked lime ortho quinone red color",
        "expected_slugs": [
            "concept-areca-catechu-condensed-tannin-arecoline-chemistry-and-alkaline-ortho-quinone-reddening"
        ]
    },
    {
        "id": "PKU-03",
        "title": "Kalipakku Copper-Cauldron & Kali-Neer Boiling Technology",
        "query": "Kalipakku copper cauldron kopparai boiling concentrated kali neer chogai tannin mother liquor ruby glaze sun curing",
        "expected_slugs": [
            "technology-kalipakku-copper-cauldron-tannin-mother-liquor-boiling-and-ruby-glaze-curing"
        ]
    },
    {
        "id": "PKU-04",
        "title": "Pakku-Vetti Class-2 Lever & Draw-Shear Mechanics",
        "query": "Pakku vetti adaikkai kolluthi forward hinge pin Class 2 lever mechanical advantage arcuate draw slice shear",
        "expected_slugs": [
            "concept-pakku-vetti-second-class-lever-mechanics-and-eccentric-pivot-slicing-geometry"
        ]
    },
    {
        "id": "PKU-05",
        "title": "Paakku-Mattai Leaf-Sheath Folding & Thermo-Pressing",
        "query": "Paakku mattai kamugu madal shed areca palm leaf sheath retting origami folding thermo mechanical die pressed biodegradable plates",
        "expected_slugs": [
            "technology-paakku-mattai-areca-leaf-sheath-retting-and-thermo-mechanical-platter-pressing"
        ]
    },
    {
        "id": "PKU-06",
        "title": "Zoomorphic Pakku-Vetti Shears, Chellam Box & Bronze Idiyural",
        "query": "Zoomorphic peacock brass pakku vetti compartmented chellam vetrilai petti tubular bronze idiyural betel pounder",
        "expected_slugs": [
            "artifact-brass-pakku-vetti-nut-shears-bronze-idiyural-betel-mortars-and-mattai-plates"
        ]
    },
    {
        "id": "PKU-07",
        "title": "Adaikkai-Vaanigar Guilds & Temple Adaikkai-Amudhu",
        "query": "Adaikkai Vaanigar merchant guilds adaikkai ayam pack load toll temple Adaikkai Amudhu liturgical offering",
        "expected_slugs": [
            "institution-adaikkai-vaanigar-areca-merchant-guilds-and-temple-adaikkai-amudhu-tenures"
        ]
    },
    {
        "id": "PKU-08",
        "title": "Mettupalayam Bhavani Kamugu Grove & Kalipakku Haven",
        "query": "Mettupalayam Bhavani River Nilgiri foothills Coimbatore kamugu toppu areca groves Kalipakku cheeval haven 11.3000 76.9400",
        "expected_slugs": [
            "place-mettupalayam-ancient-bhavani-kamugu-areca-grove-and-kalipakku-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Areca Nut Horticulture, Kalipakku Tannin-Boiling Curing, Pakku-Vetti Lever Shears & Tambula Rituals")
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
