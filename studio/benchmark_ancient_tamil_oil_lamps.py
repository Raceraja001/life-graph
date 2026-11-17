#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Oil Lamp Luminaires, Capillary Wick Combustion, Pavai-Vilakku Self-Regulating Reservoirs & Karthigai Deepam Pyrotechnics
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
        "id": "VLK-01",
        "title": "Sangam & Bhakti Literary References to Pavai-Vilakku & Karthigai",
        "query": "Nedunalvadai Mullaippattu Perumpanarruppadai Akananuru Thevaram Pavai-Vilakku bronze figurine lamp Karthigai vilakkeedu verses",
        "expected_slugs": [
            "text-sangam-and-bhakti-literature-on-pavai-vilakku-agal-lamps-and-karthigai-deepam"
        ]
    },
    {
        "id": "VLK-02",
        "title": "Capillary Wick Washburn Flow & Pancha-Deepa Fuel Chemistry",
        "query": "Lucas-Washburn capillary rise Pancha-Deepa Ennai iluppai Madhuca sesame castor neem ghee lotus-stem calotropis vellerukku wick",
        "expected_slugs": [
            "concept-capillary-wick-washburn-transport-and-laminar-diffusion-flame-fuel-chemistry"
        ]
    },
    {
        "id": "VLK-03",
        "title": "Hydrostatic Mariotte-Bottle Physics of Self-Feeding Lamps",
        "query": "Mariotte bottle barometric seal hydrostatic pressure self-regulating Pavai-Vilakku Rishabha-Kunjaram Thookku-Vilakku bubble oil feed",
        "expected_slugs": [
            "concept-hydrostatic-mariotte-siphon-physics-of-self-regulating-pavai-and-thookku-vilakku"
        ]
    },
    {
        "id": "VLK-04",
        "title": "Chokkapanai Bonfire Potash Agronomy & Maavilakku",
        "query": "Karthigai Chokkapanai conical palmyra bonfire phototactic stem-borer moth trap potassium carbonate potash ash Samba paddy Maavilakku",
        "expected_slugs": [
            "concept-chokkapanai-palmyra-bonfire-potash-ash-agronomy-and-maavilakku-edible-lamp-symbolism"
        ]
    },
    {
        "id": "VLK-05",
        "title": "Kuthuvilakku Modular Casting, Screw Threads & Spout Filing",
        "query": "Nachiarkoil four-part Kuthuvilakku paadham thandu thagalhi annam integral cast helical screw threads marai anti-drip V-spout filing",
        "expected_slugs": [
            "technology-kuthuvilakku-modular-lost-wax-and-sand-casting-lathe-threading-and-spout-chasing"
        ]
    },
    {
        "id": "VLK-06",
        "title": "Off-the-Hump Agal Throwing & Mahadeepam Cauldron Rigging",
        "query": "Off-the-hump wheel throwing terracotta agal red ochre sengavi slip sealing 5.5-foot Mahadeepam kopparai 3500 kg ghee 1000m khadi wick",
        "expected_slugs": [
            "technology-wheel-thrown-terracotta-agal-pinching-and-giant-karthigai-mahadeepam-cauldron-rigging"
        ]
    },
    {
        "id": "VLK-07",
        "title": "Chola Nandavilakku 90-Ewe Endowments & Manradi Trusts",
        "query": "Chola Nandavilakku perpetual lamp sava-moova peradu 90 ewes 32 cows 1 uzhakku daily ghee Manradi shepherd trusts inscriptions",
        "expected_slugs": [
            "institution-chola-nandavilakku-perpetual-lamp-cattle-endowments-and-manradis-shepherd-trusts"
        ]
    },
    {
        "id": "VLK-08",
        "title": "Tiruvannamalai Arunachala Karthigai Mahadeepam Haven",
        "query": "Tiruvannamalai Arunachala Annamalai hill 12.2350 79.0670 Agni-Sthalam Bharani Deepam Karthigai Mahadeepam Parvatharajakula haven",
        "expected_slugs": [
            "place-tiruvannamalai-ancient-karthigai-mahadeepam-and-agal-lamp-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Oil Lamp Luminaires, Capillary Wick Combustion, Pavai-Vilakku Self-Regulating Reservoirs & Karthigai Deepam Pyrotechnics")
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
