#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Stringed Harp Luthier Craft, Yazh Organology & Panar Modal Acoustics
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
        "id": "YZH-01",
        "title": "Arruppadai & Silappadikaram Yazh Poetics",
        "query": "Porunararruppadai Silappadikaram Arangerrukathai Yazh harp anatomy pathar porvai thivavu verses",
        "expected_slugs": [
            "text-arruppadai-and-silappadikaram-on-yazh-organology-and-panar-bards"
        ]
    },
    {
        "id": "YZH-02",
        "title": "Kumizh & Vengai Soundwood Acoustics",
        "query": "Kumizh Gmelina arborea vengai soundwood seasoning pathar cavity resonance membrane coupling",
        "expected_slugs": [
            "concept-kumizh-and-vengai-soundwood-seasoning-and-pathar-resonator-acoustics"
        ]
    },
    {
        "id": "YZH-03",
        "title": "Pathar Gouging & Thivavu Tuning Rings",
        "query": "Hollow pathar boat trough gouging porvai parchment stitching thivavu leather tuning collars",
        "expected_slugs": [
            "technology-yazh-carving-porvai-parchment-stitching-and-thivavu-tuning-rings"
        ]
    },
    {
        "id": "YZH-04",
        "title": "Four-Fold Yazh Harp Typology",
        "query": "Periyazh 21 strings Makarayazh 19 strings Sakodayazh 14 strings Seeriyazh 7 strings harp typology",
        "expected_slugs": [
            "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology"
        ]
    },
    {
        "id": "YZH-05",
        "title": "Vattappalai & Kural-Thiribu Modal Tuning",
        "query": "Vattappalai cycle of fifths kural ili consonance kural thiribu modal transposition palai scales",
        "expected_slugs": [
            "concept-vattappalai-cycle-of-fifths-and-kural-thiribu-modal-transposition"
        ]
    },
    {
        "id": "YZH-06",
        "title": "Panar & Viraliyar Bardic Guilds",
        "query": "Panar Viraliyar itinerant bardic guilds Perumpanar Sirupanar gold lotus Arruppadai patronage",
        "expected_slugs": [
            "institution-panar-and-viraliyar-bardic-guilds-and-royal-arruppadai-patronage"
        ]
    },
    {
        "id": "YZH-07",
        "title": "Narambu Gut & Silk String Spinning",
        "query": "Narambu gut sinew twisted silk string spinning stone weight gauge calibration beeswax polishing",
        "expected_slugs": [
            "technology-narambu-gut-and-twisted-silk-string-spinning-and-wax-polishing"
        ]
    },
    {
        "id": "YZH-08",
        "title": "Avudaiyarkoil Panar Acoustic Haven",
        "query": "Avudaiyarkoil Thirupperunthurai Panar Yazh acoustic haven monolithic stone kodungai mandapa",
        "expected_slugs": [
            "place-avudaiyarkoil-ancient-panar-yazh-and-acoustic-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Stringed Harp Luthier Craft, Yazh Organology & Panar Modal Acoustics")
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
