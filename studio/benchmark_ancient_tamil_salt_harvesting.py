#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Tidal Salt Harvesting, Solar Evaporation Pan Hydraulics & Brine Chemistry
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "SLT-01",
        "name": "Sangam Salt Verse",
        "query": "Perumpanattruppadai classical Sangam verses on white salt mounds and Eyilpattinam pan workers",
        "expected": [
            "text-perumpanattruppadai-verses-on-white-salt-mounds-and-eyilpattinam-pan-workers"
        ]
    },
    {
        "id": "SLT-02",
        "name": "Saltern Thermodynamics",
        "query": "Uppalam tidal saltern thermodynamics fractional evaporation and halite precipitation sodium chloride",
        "expected": [
            "concept-uppalam-tidal-solar-evaporation-and-brine-crystallization-thermodynamics"
        ]
    },
    {
        "id": "SLT-03",
        "name": "Pan Clay Engineering",
        "query": "Alalam and paathi puddled clay saltern engineering bund construction and tidal sluice gates",
        "expected": [
            "technology-alalam-and-paathi-clay-bund-pan-engineering-and-saline-sluicing"
        ]
    },
    {
        "id": "SLT-04",
        "name": "Wooden Salt Scrapers",
        "query": "Uppu thadavai and marakkal hardwood brine scrapers drainage rakes and certified dry measures",
        "expected": [
            "artifact-uppu-thadavai-and-marakkal-wooden-scraping-boards-and-salt-measures"
        ]
    },
    {
        "id": "SLT-05",
        "name": "Halophilic Microbiology",
        "query": "Alalam saline microbiology halophilic archaea Dunaliella salina solar energy absorption",
        "expected": [
            "concept-alalam-saline-microbiology-and-halophilic-crystal-purification"
        ]
    },
    {
        "id": "SLT-06",
        "name": "Umanar Salt Guild",
        "query": "Umanar trans peninsular salt caravans bullock transport guilds and paddy barter economies",
        "expected": [
            "institution-umanar-and-uppu-vanigar-guild-of-salt-merchants-and-bullock-caravaners"
        ]
    },
    {
        "id": "SLT-07",
        "name": "Monsoon Salt Mounds",
        "query": "Uppu kuval conical palm thatch storage mounds moisture drainage and monsoon protection",
        "expected": [
            "technology-uppu-kuval-thatched-palm-mat-stacking-and-monsoon-drainage-mounds"
        ]
    },
    {
        "id": "SLT-08",
        "name": "Saltern Haven Marakkanam",
        "query": "Marakkanam ancient Eyilpattinam saltern haven Sopatma lagoons and salt guild citadel",
        "expected": [
            "place-marakkanam-ancient-eyilpattinam-salt-pan-haven"
        ]
    }
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Ollama embedding error: {res.text}")
    return res.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Tidal Salt Harvesting, Solar Evaporation Pan Hydraulics & Brine Chemistry")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        vec = get_bge_embedding(tc["query"])
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector ASC
            LIMIT 5;
        """, (vec, vec))
        rows = cur.fetchall()
        top1 = rows[0][0] if rows else None
        top1_sim = rows[0][1] if rows else 0.0

        if top1 in tc["expected"]:
            passed += 1
            print(f"[PASS] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for r in rows:
                print(f"    - {r[0]} (Sim: {r[1]:.4f})")

    elapsed = time.time() - t0
    acc = (passed / len(TEST_CASES)) * 100
    print("=" * 80)
    print(f"SUMMARY: {passed}/{len(TEST_CASES)} passed ({acc:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    cur.close()
    conn.close()

    if passed < len(TEST_CASES):
        sys.exit(1)

if __name__ == "__main__":
    main()
