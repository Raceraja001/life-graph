#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "CLE-01",
        "query": "Mullaippattu nocturnal royal military tent water clock naazhigai kanakkar timekeepers",
        "expected_slugs": [
            "text-mullaippattu-naazhigai-vattil-water-clock-poetry"
        ],
        "category": "Horological Poetry"
    },
    {
        "id": "CLE-02",
        "query": "Perforated copper bowl sinking water clock naazhigai vattil hydrodynamic orifice inflow",
        "expected_slugs": [
            "concept-perforated-copper-bowl-sinking-clepsydra-hydrometry-naazhigai-vattil"
        ],
        "category": "Clepsydra Physics"
    },
    {
        "id": "CLE-03",
        "query": "Twenty-four minute naazhigai sexagesimal time metrology sixty naazhigai solar day",
        "expected_slugs": [
            "concept-twenty-four-minute-naazhigai-temporal-metrology-and-sixty-naazhigai-day"
        ],
        "category": "Sexagesimal Metrology"
    },
    {
        "id": "CLE-04",
        "query": "Vertical gnomon shadow stick sanku midday solar transit shadow length reckoning",
        "expected_slugs": [
            "concept-astronomical-gnomon-shadow-stick-reckoning-nizhal-kanal"
        ],
        "category": "Gnomon Astronomy"
    },
    {
        "id": "CLE-05",
        "query": "Temple bell strike cadences broadcasting naazhigai hours and maritime star navigation",
        "expected_slugs": [
            "concept-temple-bell-strike-cadence-and-nocturnal-maritime-chronometry"
        ],
        "category": "Public Chronometry"
    },
    {
        "id": "CLE-06",
        "query": "Kumbakonam Chola royal charters endowing temple astronomers and clepsydra horologists",
        "expected_slugs": [
            "insc-kumbakonam-chola-astronomical-chronometry-charters"
        ],
        "category": "Chola Horology Charters"
    },
    {
        "id": "CLE-07",
        "query": "Naazhigai kanakkar master horologist maintaining copper water clocks in Kumbakonam",
        "expected_slugs": [
            "char-kumbakonam-master-clepsydra-horologist-naazhigai-kanakkar"
        ],
        "category": "Master Horologists"
    },
    {
        "id": "CLE-08",
        "query": "Kumbakonam ancient Kaveri delta astronomical chronometry and water clock haven",
        "expected_slugs": [
            "place-kumbakonam-ancient-astronomical-chronometry-haven"
        ],
        "category": "Astronomical Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Clepsydra Horology & Shadow Gnomons")
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
