#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Scent Distillation, Attar Extraction & Temple Aromatics
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "PRF-01",
        "name": "Sangam Perfumery Verse",
        "query": "Silappadikaram verses on perfume bazaars fragrant pastes and aromatics Ilango Adigal",
        "expected": [
            "text-silappadikaram-verses-on-perfume-bazaars-fragrant-pastes-and-aromatics"
        ]
    },
    {
        "id": "PRF-02",
        "name": "Hydro-Distillation Physics",
        "query": "Vasanai thailam steam hydro distillation volatilization kinetics and essential oil extraction",
        "expected": [
            "concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics"
        ]
    },
    {
        "id": "PRF-03",
        "name": "Retort Distillation Stills",
        "query": "Dega and bapka terracotta retort distillation stills bamboo conduits and water condensers",
        "expected": [
            "technology-dega-and-bapka-terracotta-retort-steam-distillation-pyrotechnics"
        ]
    },
    {
        "id": "PRF-04",
        "name": "Sandalwood Grinding Slabs",
        "query": "Chandana kallu and chimizh granite sandalwood grinding slabs flacons and unguent mortars",
        "expected": [
            "artifact-chandana-kallu-and-urundai-sandalwood-grinding-slabs-and-perfume-flacons"
        ]
    },
    {
        "id": "PRF-05",
        "name": "Cold Lipid Enfleurage",
        "query": "Enfleurage lipid aroma absorption cold sesame oil maceration and fixative fixation",
        "expected": [
            "concept-sugandha-thiraviyam-sesame-oil-enfleurage-and-lipid-aroma-fixation"
        ]
    },
    {
        "id": "PRF-06",
        "name": "Royal Perfumers Guild",
        "query": "Sugandha vanigar guild of master perfumers royal apothecaries and spice merchants",
        "expected": [
            "institution-vasanai-thattar-and-sugantha-vanigar-guild-of-perfumers-and-apothecaries"
        ]
    },
    {
        "id": "PRF-07",
        "name": "Civet Musk & Javvadu",
        "query": "Javvadu and punugu civet musk secretion herbal resin maceration and powder compounding",
        "expected": [
            "technology-javvadu-and-punugu-civet-musk-and-herbal-resin-maceration"
        ]
    },
    {
        "id": "PRF-08",
        "name": "Sandalwood Haven Kanniyakumari",
        "query": "Kanniyakumari ancient Ay sandalwood hills fragrant Podhigai slopes and perfumery haven",
        "expected": [
            "place-kanniyakumari-ancient-ay-sandalwood-and-perfumery-haven"
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
    print("BENCHMARK: Ancient Tamil Scent Distillation, Attar Extraction & Temple Aromatics")
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
