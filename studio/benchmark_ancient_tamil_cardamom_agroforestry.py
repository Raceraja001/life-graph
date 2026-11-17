#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Cardamom & Hill-Forest Spice Agroforestry, Shade Curing & Kurinji Caravan Trade
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
        "id": "CRD-01",
        "title": "Sangam & Silappadikaram Hill Cardamom Accounts",
        "query": "Malaipadukadam Kurinjippattu Silappadikaram elam cardamom Kunra Kuravar Western Ghats forest aromatics",
        "expected_slugs": [
            "text-sangam-and-silappadikaram-on-elam-cardamom-and-kurinji-forest-aromatics"
        ]
    },
    {
        "id": "CRD-02",
        "title": "Elettaria cardamomum Shade Ecology & Terpinyl Acetate",
        "query": "Elettaria cardamomum evergreen shola canopy shade basal panicle pollination 1,8-cineole alpha-terpinyl acetate",
        "expected_slugs": [
            "concept-elettaria-cardamomum-understory-shade-ecology-and-terpinyl-acetate-chemistry"
        ]
    },
    {
        "id": "CRD-03",
        "title": "Selective Karukkai Picking & Alkaline Chlorophyll Wash",
        "query": "Selective hand picking karukkai stage cardamom capsules alkaline wood ash lye sodium bicarbonate chlorophyll retention wash",
        "expected_slugs": [
            "technology-basal-panicle-selective-picking-and-alkaline-ash-chlorophyll-washing"
        ]
    },
    {
        "id": "CRD-04",
        "title": "Odai Flue-Kiln Thermal Curing & Coir-Mat Polishing",
        "query": "Odai indirect wood flue pipe kiln curing chamber 45 to 55 degrees Celsius coir mat calyx rubbing winnowing",
        "expected_slugs": [
            "technology-odai-flue-kiln-thermal-curing-and-coir-mat-chaff-winnowing"
        ]
    },
    {
        "id": "CRD-05",
        "title": "Karukkai Ripeness, Litre-Weight Bulk Density & Sieve Grading",
        "query": "Vellai kai karukkai pazhakai ripeness grams per litre bulk density 8 mm extra bold round hole brass sieve grading",
        "expected_slugs": [
            "concept-karukkai-pazhakai-capsule-ripeness-chlorophyll-retention-and-grading-metrics"
        ]
    },
    {
        "id": "CRD-06",
        "title": "Eladhi Chooranam & Siddha Pitta Pharmacology",
        "query": "Eladhi Chooranam Kanimedhaviyar Pathinenkilkanakku Agathiyar Gunavagadam Siddha Pitta nausea digestive therapeutics",
        "expected_slugs": [
            "concept-eladhi-chooranam-siddha-pharmacology-and-tridosha-digestive-therapeutics"
        ]
    },
    {
        "id": "CRD-07",
        "title": "Kuravar Hill Gatherers & Pettai Spice Caravan Guilds",
        "query": "Kunra Kuravar Mannan shola canopy gap clearing thavalam barter Pettai merchant guilds cardamom trade",
        "expected_slugs": [
            "institution-kuravar-hill-spice-gatherers-and-ghat-pettai-caravan-guilds"
        ]
    },
    {
        "id": "CRD-08",
        "title": "Bodinayakanur Cardamom Hills Gateway & Spice Haven",
        "query": "Bodinayakanur Elamalai Cardamom Hills Bodimettu Kottagudi pass Theni Kurinji spice haven 10.0100 77.3500",
        "expected_slugs": [
            "place-bodinayakanur-ancient-cardamom-hills-and-kurinji-spice-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Cardamom & Hill-Forest Spice Agroforestry, Shade Curing & Kurinji Caravan Trade")
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
