#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "JAV-01",
        "query": "Silappathikaram verses on fragrant cosmetic bazaars selling civet musk and sandalwood",
        "expected_slugs": [
            "text-silappathikaram-fragrant-cosmetic-streets-and-javvadu-bazaars"
        ],
        "category": "Epic Literature"
    },
    {
        "id": "JAV-02",
        "query": "Civet musk secretion harvesting from Punugu-Poonai and sacerdotal Javvadu blending",
        "expected_slugs": [
            "concept-civet-musk-extraction-and-sacerdotal-aromatic-blending-javvadu"
        ],
        "category": "Civet Perfumery"
    },
    {
        "id": "JAV-03",
        "query": "Sandalwood heartwood circular stone mortaring on Santhana-Kal for cooling therapeutics",
        "expected_slugs": [
            "concept-sandalwood-heartwood-stone-mortaring-and-cooling-paste-santhanam"
        ],
        "category": "Sandalwood Paste"
    },
    {
        "id": "JAV-04",
        "query": "Aromatic agarwood Akil resins Kungiliyam and charcoal dhoopam temple fumigation",
        "expected_slugs": [
            "concept-aromatic-resin-incense-fixation-and-temple-fumigation-akil-dhoop"
        ],
        "category": "Temple Fumigation"
    },
    {
        "id": "JAV-05",
        "query": "Royal cosmetic unguent anointing vetiver wild turmeric and post-bath somatic cooling",
        "expected_slugs": [
            "concept-royal-cosmetic-unguent-anointing-and-cooling-therapeutics"
        ],
        "category": "Cosmetic Therapeutics"
    },
    {
        "id": "JAV-06",
        "query": "Thiruvannamalai Chola inscriptions perpetual endowments for daily sandalwood and civet musk",
        "expected_slugs": [
            "insc-thiruvannamalai-chola-fragrant-resin-and-sandalwood-endowments"
        ],
        "category": "Temple Epigraphy"
    },
    {
        "id": "JAV-07",
        "query": "Kudumiyanmalai stone charters granting land to hereditary temple sandalwood paste grinders",
        "expected_slugs": [
            "insc-kudumiyanmalai-aromatic-paste-grinder-and-temple-perfumer-charters"
        ],
        "category": "Artisan Charters"
    },
    {
        "id": "JAV-08",
        "query": "Javvadi Hills ancient sandalwood forests civet sanctuary and eponymous aromatic haven",
        "expected_slugs": [
            "place-javvadhumalai-ancient-sandalwood-civet-and-aromatic-haven"
        ],
        "category": "Highland Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Civet Musk & Sandalwood Unguents")
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
