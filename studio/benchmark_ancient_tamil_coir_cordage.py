#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "COI-01",
        "query": "Pattinappalai verses on ocean ships Vangam moored with coir hawsers in Kaveripattinam",
        "expected_slugs": [
            "text-pattinappalai-ship-rigging-and-coir-cordage-poetry"
        ],
        "category": "Literature & Rigging"
    },
    {
        "id": "COI-02",
        "query": "Brackish estuarine coconut husk retting halophilic bacterial pectin hydrolysis in lagoons",
        "expected_slugs": [
            "concept-brackish-estuarine-coconut-husk-retting-and-pectin-hydrolysis"
        ],
        "category": "Retting Biochemistry"
    },
    {
        "id": "COI-03",
        "query": "Triple strand coir hawser spinning Muvizhai Kayiru and surge energy absorption mechanics",
        "expected_slugs": [
            "concept-triple-strand-coir-hawser-spinning-and-tensile-cordage-mechanics"
        ],
        "category": "Hawser Engineering"
    },
    {
        "id": "COI-04",
        "query": "Vegetable dammar resin and castor oil waterproofing impregnation for marine rigging",
        "expected_slugs": [
            "concept-vegetable-tallow-and-tar-waterproofing-for-marine-rigging"
        ],
        "category": "Cordage Waterproofing"
    },
    {
        "id": "COI-05",
        "query": "Traditional coconut fiber net weaving needles and nonslip anchor knotting mechanics",
        "expected_slugs": [
            "concept-traditional-coconut-fiber-net-weaving-and-hawser-knotting"
        ],
        "category": "Netting & Knotting"
    },
    {
        "id": "COI-06",
        "query": "Manappadu Pandya port epigraphs on cordage guilds and naval cable quotas",
        "expected_slugs": [
            "insc-manappadu-pandya-port-cordage-and-rope-guild-charters"
        ],
        "category": "Port Epigraphy"
    },
    {
        "id": "COI-07",
        "query": "Master coir spinner Kayittru Vanikan managing 100-meter ropewalks at Manappadu",
        "expected_slugs": [
            "char-manappadu-master-coir-spinner-kayittru-vanikan"
        ],
        "category": "Master Artisans"
    },
    {
        "id": "COI-08",
        "query": "Manappadu ancient coir cordage estuarine retting and marine rigging haven",
        "expected_slugs": [
            "place-manappadu-ancient-coir-cordage-and-rigging-haven"
        ],
        "category": "Estuarine Haven Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Coir Cordage & Marine Rigging")
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
