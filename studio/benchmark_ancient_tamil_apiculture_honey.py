#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "HNY-01",
        "category": "Sangam Botanical Verse",
        "query": "Kurinjipattu classical Sangam verses on mountain honey gathering forest foraging protocols",
        "expected_slugs": [
            "text-kurinjipattu-wild-honey-harvesting-and-mountain-foraging-poetry"
        ]
    },
    {
        "id": "HNY-02",
        "category": "Cliff Honey Harvesting",
        "query": "Precipice rock honey gathering green leaf smoke torches theevatti Apis dorsata combs",
        "expected_slugs": [
            "concept-precipice-rock-honey-gathering-with-smoked-torches-malai-thaen"
        ]
    },
    {
        "id": "HNY-03",
        "category": "Clay Pot Apiculture",
        "query": "Clay pot apiculture domestic hives and medicinal fermented honey infusions thaen ooral",
        "expected_slugs": [
            "concept-clay-pot-apiculture-and-medicinal-honey-infusions-thaen-koodu"
        ]
    },
    {
        "id": "HNY-04",
        "category": "Alpine Rigging",
        "query": "Bamboo rope ladder cliff scaling engineering aani eani wild forest creeper rigging",
        "expected_slugs": [
            "concept-bamboo-rope-ladder-cliff-scaling-acrobatics-aani-eani"
        ]
    },
    {
        "id": "HNY-05",
        "category": "Beeswax Commerce",
        "query": "Kaanavar highland forest honey guilds and pure beeswax cire perdue barter commerce",
        "expected_slugs": [
            "concept-kurinji-kaanavar-forest-honey-guilds-and-wax-trade-thaen-vanigam"
        ]
    },
    {
        "id": "HNY-06",
        "category": "Highland Epigraphy",
        "query": "Javvadhu hills forest epigraphs mountain tribe honey and temple nanda vilakku wax tributes",
        "expected_slugs": [
            "insc-javvadhumalai-kaanavar-forest-honey-and-wax-tribute-inscriptions"
        ]
    },
    {
        "id": "HNY-07",
        "category": "Guild Inscriptions",
        "query": "Pachaimalai highland inscriptions on forest honey guilds and medicinal dammar resin grants",
        "expected_slugs": [
            "insc-pachaimalai-hill-tribe-apiculture-and-medicinal-resin-endowments"
        ]
    },
    {
        "id": "HNY-08",
        "category": "Highland Topography",
        "query": "Pachaimalai ancient Kurinji cliff honey sanctuary and highland foraging haven Eastern Ghats",
        "expected_slugs": [
            "place-pachaimalai-ancient-kurinji-cliff-honey-and-forest-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Apiculture & Cliff Honey Gathering")
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
