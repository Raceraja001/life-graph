#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "GRA-01",
        "query": "Purananuru verses describing towering mountain like granaries Kalanjiyam and grain security",
        "expected_slugs": [
            "text-purananuru-towering-granaries-and-grain-security-poetry"
        ],
        "category": "Literature & Grain Security"
    },
    {
        "id": "GRA-02",
        "query": "Subterranean clay lined grain storage silos Pathayam and anoxia pest eradication mechanics",
        "expected_slugs": [
            "concept-subterranean-clay-lined-grain-storage-silos-pathayam-and-kuzhi"
        ],
        "category": "Hermetic Silos"
    },
    {
        "id": "GRA-03",
        "query": "Elevated timber slatted aerated granary architecture Kalanjiyam with rodent guard stone discs",
        "expected_slugs": [
            "concept-elevated-timber-slatted-aerated-granary-architecture-kalanjiyam"
        ],
        "category": "Aerated Granary Architecture"
    },
    {
        "id": "GRA-04",
        "query": "Neem leaf turmeric and wood ash entomological pest repellent systems in grain columns",
        "expected_slugs": [
            "concept-neem-leaf-turmeric-and-wood-ash-entomological-pest-repellents"
        ],
        "category": "Botanical Pest Control"
    },
    {
        "id": "GRA-05",
        "query": "Monsoon humidity barrier and woven bamboo silo linings Nel Kuthir composite plaster",
        "expected_slugs": [
            "concept-monsoon-humidity-barrier-and-woven-bamboo-silo-linings"
        ],
        "category": "Vernacular Kuthir Silos"
    },
    {
        "id": "GRA-06",
        "query": "Tirukkampuliyur Kaveri delta royal granary endowments and excavated circular brick foundations",
        "expected_slugs": [
            "insc-tirukkampuliyur-kaveri-delta-royal-granary-endowments"
        ],
        "category": "Granary Epigraphy"
    },
    {
        "id": "GRA-07",
        "query": "Master granary architect Kalanchiya Sirpachari engineering damp proof timber silos",
        "expected_slugs": [
            "char-tirukkampuliyur-master-granary-architect-kalanchiya-sirpachari"
        ],
        "category": "Master Architects"
    },
    {
        "id": "GRA-08",
        "query": "Tirukkampuliyur ancient granary brick silo and Kaveri agrarian haven",
        "expected_slugs": [
            "place-tirukkampuliyur-ancient-granary-and-agrarian-haven"
        ],
        "category": "Agrarian Haven Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Granary Engineering & Aeration")
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
