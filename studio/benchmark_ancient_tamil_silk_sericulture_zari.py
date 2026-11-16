#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "SLK-01",
        "category": "Sangam Silk Verse",
        "query": "Porunarattruppadai classical Sangam verses on gossamer silk and serpent slough robes aravuriyan",
        "expected_slugs": [
            "text-porunarattruppadai-verses-on-gossamer-silk-and-serpent-slough-robes"
        ]
    },
    {
        "id": "SLK-02",
        "category": "Sericulture Agro-Science",
        "query": "Pattu nool thozhil ancient Tamil mulberry sericulture silkworm rearing and filament reeling kamblipoochi",
        "expected_slugs": [
            "concept-pattu-nool-thozhil-ancient-tamil-mulberry-sericulture-and-filament-reeling"
        ]
    },
    {
        "id": "SLK-03",
        "category": "Pit-Loom Mechanics",
        "query": "Kuzhi thari and adai earthen pit loom mechanics shedding treadles and harness pattern weaving Jacquard",
        "expected_slugs": [
            "technology-kuzhi-thari-and-adai-ground-pit-loom-and-jacquard-harness-mechanics"
        ]
    },
    {
        "id": "SLK-04",
        "category": "Korvai Craftsmanship",
        "query": "Korvai interlocked weft temple spire contrast border weaving craftsmanship reku mottu triple shuttle",
        "expected_slugs": [
            "technology-korvai-interlocked-weft-temple-border-weaving-craftsmanship"
        ]
    },
    {
        "id": "SLK-05",
        "category": "Gold Zari Metallurgy",
        "query": "Thanga zari flattened silver gold micro wire wound on mulberry silk brocade core badla 24 karat",
        "expected_slugs": [
            "artifact-thanga-zari-beaten-gold-wrapped-pure-silk-brocade-threads"
        ]
    },
    {
        "id": "SLK-06",
        "category": "Botanical Silk Dyeing",
        "query": "Iyarkai vanna nool botanical silk dyeing alum mordanting and fermented madder chayaver avuri",
        "expected_slugs": [
            "concept-iyarkai-vanna-nool-natural-botanical-mordanting-and-silk-yarn-dyeing"
        ]
    },
    {
        "id": "SLK-07",
        "category": "Imperial Weavers Guild",
        "query": "Kaikkolar and pattu saliya guild imperial Chola royal silk weavers guild and tax charters thari irai",
        "expected_slugs": [
            "institution-kaikkolar-pattu-saliya-guild-imperial-silk-weavers-guild"
        ]
    },
    {
        "id": "SLK-08",
        "category": "Silk Topography",
        "query": "Tirubhuvanam ancient Chola silk weaving pure zari brocade and textile haven Kaveri Kumbakonam",
        "expected_slugs": [
            "place-tirubhuvanam-ancient-silk-weaving-and-zari-brocade-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Silk Sericulture, Mulberry Cultivation & Gold Zari Brocading")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        emb = get_bge_embedding(tc["query"])
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"

        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
        """, (emb_str, emb_str))
        results = cur.fetchall()

        top_slug = results[0][0]
        top_sim = results[0][1]
        is_hit = top_slug in tc["expected_slugs"]
        status = "PASS" if is_hit else "FAIL"
        if is_hit:
            passed += 1

        print(f"[{status}] {tc['id']} ({tc['category']})")
        print(f"  Query:    '{tc['query']}'")
        print(f"  Expected: {tc['expected_slugs']}")
        print(f"  Top-1:    {top_slug} (Sim: {top_sim:.4f})")
        if not is_hit:
            print("  Top-5:")
            for rank, (r_slug, r_sim) in enumerate(results, 1):
                print(f"    {rank}. {r_slug} ({r_sim:.4f})")
        print("-" * 80)

    elapsed = time.time() - t0
    accuracy = (passed / len(TEST_CASES)) * 100
    print(f"RESULTS: {passed}/{len(TEST_CASES)} passed ({accuracy:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    cur.close()
    conn.close()
    if passed != len(TEST_CASES):
        exit(1)

if __name__ == "__main__":
    main()
