#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Soapstone Cookware, Talc-Schist Quarrying, Lathe Turnery, Oil-Rice Starch Curing & Thermal Heat Retention
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
        "id": "KLC-01",
        "title": "Steatite Quarrying, Kudhirai Spindle Lathe & Valai-Uli Hollowing",
        "query": "Steatite talc schist metamorphic quarrying kudhirai wooden spindle lathe turnery cord bow valai uli gouge hollowing",
        "expected_slugs": [
            "technology-steatite-talc-schist-quarrying-lathe-turnery-and-chisel-hollowing"
        ]
    },
    {
        "id": "KLC-02",
        "title": "Kalchatti Pazhakkuthal Curing, Kanji Thanneer & Hydrophobic Patina",
        "query": "Kalchatti seasoning pazhakkuthal warm castor oil turmeric coating fermented kanji thanneer rice starch gruel soaking 10 days hydrophobic patina",
        "expected_slugs": [
            "technology-kalchatti-mustard-oil-curing-rice-starch-simmering-and-thermal-seasoning"
        ]
    },
    {
        "id": "KLC-03",
        "title": "Carved Steatite Vessels, Kuzhambu Kalchatti & Vadai-Chatti Morphology",
        "query": "Carved soapstone culinary vessels globular kuzhambu kalchatti flared rim rasam pot wide shallow vadai chatti deep frying stone lid",
        "expected_slugs": [
            "artifact-carved-steatite-kalchatti-cooking-pots-vadai-chatti-and-kuzhambu-vessels"
        ]
    },
    {
        "id": "KLC-04",
        "title": "Soapstone Turner Toolkit, Kudhirai Mandrel & Ficus Polishing Leaves",
        "query": "Traditional soapstone turner toolkit wooden chuck mandrel kudhirai pidi leather driving thong tempered valai uli kothu uli Ficus exasperata ottan ilai abrasive leaves",
        "expected_slugs": [
            "artifact-traditional-soapstone-lathe-mandrels-tempered-steel-gouges-and-polishing-leaves"
        ]
    },
    {
        "id": "KLC-05",
        "title": "Steatite Thermodynamics, Volumetric Heat Capacity & Phyllosilicate Shock Resistance",
        "query": "Steatite thermodynamics volumetric heat capacity Cv 2.7 MJ m3 K thermal conductivity 3.3 W m K phyllosilicate talc platelet thermal shock resistance",
        "expected_slugs": [
            "concept-steatite-talc-chlorite-high-volumetric-heat-capacity-and-thermal-shock-resistance"
        ]
    },
    {
        "id": "KLC-06",
        "title": "Magnesium Silicate Acid Inertness & Tamarind Preservation Without Spoilage",
        "query": "Magnesium silicate inertness tartaric acid tamarind puli kuzhambu no verdigris copper toxicity 48 hours food preservation without spoiling",
        "expected_slugs": [
            "concept-non-reactive-magnesium-silicate-chemistry-and-tamarind-acid-preservation"
        ]
    },
    {
        "id": "KLC-07",
        "title": "Aduppanai-Pin-Kodhippu Post-Fire Simmer & Thermolabile Nutrient Conservation",
        "query": "Kalchatti post fire heat retention aduppanai pin kodhippu 30 minutes thenal residual simmer thermolabile curcumin piperine nutrient preservation",
        "expected_slugs": [
            "concept-post-fire-heat-retention-eutectic-simmer-and-herbal-nutrient-preservation"
        ]
    },
    {
        "id": "KLC-08",
        "title": "Omalur & Shevaroy Ultramafic Steatite Quarrying Haven",
        "query": "Omalur Mecheri Shevaroy hills Salem 11.7450 78.0420 ultramafic talcose schist deposits steatite kalchatti quarry craft haven",
        "expected_slugs": [
            "place-omalur-ancient-shevaroy-steatite-quarry-and-kalchatti-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Soapstone Cookware, Talc-Schist Quarrying, Lathe Turnery, Oil-Rice Starch Curing & Thermal Heat Retention")
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
