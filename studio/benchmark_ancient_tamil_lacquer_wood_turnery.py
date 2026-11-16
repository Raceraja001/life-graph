#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "LAC-01",
        "query": "Harvesting insect sticklac from forest host trees washing and purifying seedlac arakku",
        "expected_slugs": [
            "concept-forest-insect-lac-resin-harvesting-and-seedlac-purification-arakku"
        ],
        "category": "Resin Chemistry"
    },
    {
        "id": "LAC-02",
        "query": "Wood lathe turnery pressing pigmented lac sticks with frictional heat melting and screwpine polishing",
        "expected_slugs": [
            "concept-thermal-friction-lathe-turnery-with-pigmented-lac-sticks"
        ],
        "category": "Friction Turnery"
    },
    {
        "id": "LAC-03",
        "query": "Dissolving dammar resin kungiliyam in boiling castor oil for deep wood penetrating waterproof varnish",
        "expected_slugs": [
            "concept-resin-dammar-waterproof-varnishing-and-wood-sealing"
        ],
        "category": "Dammar Varnishing"
    },
    {
        "id": "LAC-04",
        "query": "Multi layer lacquer and resin weatherproofing for monumental wooden temple chariots and bow staves",
        "expected_slugs": [
            "concept-temple-chariot-and-weapon-shaft-weatherproof-lacquer-coatings"
        ],
        "category": "Monumental Preservation"
    },
    {
        "id": "LAC-05",
        "query": "Ambasamudram Pandya royal charters granting tax concessions to lacquer wood turners arakku thatchur",
        "expected_slugs": [
            "insc-ambasamudram-pandya-lacquer-wood-turners-charters"
        ],
        "category": "Turnery Epigraphy"
    },
    {
        "id": "LAC-06",
        "query": "Master wood turner arakku thatchur shaping turned lacquer cosmetic boxes on the Tambraparni",
        "expected_slugs": [
            "char-ambasamudram-master-lacquer-turner-arakku-thatchan"
        ],
        "category": "Master Turners"
    },
    {
        "id": "LAC-07",
        "query": "Royal temple chariot polisher mara varnakkaran applying resin sealants in Madurai",
        "expected_slugs": [
            "char-madurai-temple-wood-finisher-mara-varnakkaran"
        ],
        "category": "Temple Polishers"
    },
    {
        "id": "LAC-08",
        "query": "Ambasamudram ancient Tambraparni riverine lacquer woodcraft and turnery haven",
        "expected_slugs": [
            "place-ambasamudram-ancient-lacquer-turnery-haven"
        ],
        "category": "Woodcraft Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Natural Lacquer Finishing & Wood Turnery")
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
