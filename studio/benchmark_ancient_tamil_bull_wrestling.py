#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "BUL-01",
        "query": "Kalithogai Mullaikkali verses on brave Ayar youths embracing charging bulls by the hump",
        "expected_slugs": [
            "text-kalithogai-mullai-pastoral-bull-wrestling-and-bravery-poetry"
        ],
        "category": "Sangam Pastoral Verse"
    },
    {
        "id": "BUL-02",
        "query": "Selective breeding of humped war bulls Pulikulam and Kangayam cattle genetics",
        "expected_slugs": [
            "concept-selective-breeding-of-humped-war-bulls-pulikulam-and-kangayam"
        ],
        "category": "Bovine Genetics"
    },
    {
        "id": "BUL-03",
        "query": "Pastoral cattle raids Vetchi and armed herd recovery Karanthai warfare protocols",
        "expected_slugs": [
            "concept-pastoral-cattle-raids-aanirai-kavarral-and-heroic-recovery-karanthai"
        ],
        "category": "Cattle Warfare"
    },
    {
        "id": "BUL-04",
        "query": "Bare handed war bull embracing Yeru-Thazhuvuthal and Manju-Virattu arena biomechanics",
        "expected_slugs": [
            "concept-bare-handed-war-bull-embracing-arena-combats-yeru-thazhuvuthal"
        ],
        "category": "Arena Biomechanics"
    },
    {
        "id": "BUL-05",
        "query": "Bovine herbal drenches horn cautery and traditional Siddha veterinary care for cattle",
        "expected_slugs": [
            "concept-bovine-herbal-drenches-horn-cautery-and-pastoral-veterinary-care"
        ],
        "category": "Pastoral Veterinary"
    },
    {
        "id": "BUL-06",
        "query": "Alanganallur hero stones commemorating bull wrestlers and arena tournament grants",
        "expected_slugs": [
            "insc-alanganallur-hero-stone-bull-wrestler-and-arena-endowments"
        ],
        "category": "Hero Stone Epigraphy"
    },
    {
        "id": "BUL-07",
        "query": "Kangayam Chola inscriptions on communal cattle pastures and breeding bull endowments",
        "expected_slugs": [
            "insc-kangayam-chola-cattle-pasture-and-breeding-herd-charters"
        ],
        "category": "Pastoral Charters"
    },
    {
        "id": "BUL-08",
        "query": "Alanganallur ancient Mullai bull wrestling arena and pastoral haven Vaigai basin",
        "expected_slugs": [
            "place-alanganallur-ancient-mullai-bull-wrestling-and-pastoral-haven"
        ],
        "category": "Pastoral Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Bovine Husbandry & Bull Wrestling")
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
