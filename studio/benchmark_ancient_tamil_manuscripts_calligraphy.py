#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "SCR-01",
        "query": "Tholkappiyam Ezhuthathikaram sutras on letter drafting pulli dots and palm-leaf orthography",
        "expected_slugs": [
            "text-tholkappiyam-scribal-orthography-and-manuscript-preservation-protocols"
        ],
        "category": "Grammar & Orthography"
    },
    {
        "id": "SCR-02",
        "query": "Palmyrah leaf seasoning turmeric boiling and guillotine sizing for insect-resistant manuscripts",
        "expected_slugs": [
            "concept-palmyrah-leaf-seasoning-turmeric-boiling-and-guillotine-sizing"
        ],
        "category": "Leaf Seasoning"
    },
    {
        "id": "SCR-03",
        "query": "Incised iron stylus calligraphy ezhuthani and charred coconut lampblack inking mai-poosal",
        "expected_slugs": [
            "concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening"
        ],
        "category": "Stylus Calligraphy"
    },
    {
        "id": "SCR-04",
        "query": "Perforated cord binding chuvadi-kattu and teak wood protective boards kamba-palgai",
        "expected_slugs": [
            "concept-perforated-cord-binding-and-teak-wood-protective-boards-chuvadi"
        ],
        "category": "Manuscript Binding"
    },
    {
        "id": "SCR-05",
        "query": "Rolled palm-leaf missives surul-olai sealed with royal crests and epistolary couriers",
        "expected_slugs": [
            "concept-epistolary-scroll-couriers-and-cloth-wrapped-land-deeds-pattayam"
        ],
        "category": "Administrative Missives"
    },
    {
        "id": "SCR-06",
        "query": "Thanjavur Saraswathi Mahal inscriptions on scriptorium copyist land grants and lemongrass oil",
        "expected_slugs": [
            "insc-thanjavur-saraswathi-mahal-scribal-guild-and-manuscript-endowments"
        ],
        "category": "Scriptorium Inscriptions"
    },
    {
        "id": "SCR-07",
        "query": "Kanchipuram Ghatika collegiate manuscript archives and resident scholar-scribe charters",
        "expected_slugs": [
            "insc-kanchipuram-ghatika-manuscript-library-and-scriptorium-charters"
        ],
        "category": "Collegiate Archives"
    },
    {
        "id": "SCR-08",
        "query": "Madurai ancient Sangam scribal academy scriptorium and royal archival treasury haven",
        "expected_slugs": [
            "place-madurai-ancient-sangam-scribal-academy-and-scriptorium-haven"
        ],
        "category": "Scribal Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Palm-Leaf Manuscripts & Calligraphy")
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
