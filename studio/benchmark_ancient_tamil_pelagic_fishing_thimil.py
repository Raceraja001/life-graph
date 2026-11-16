#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "PEL-01",
        "category": "Sangam Pelagic Verse",
        "query": "Akananuru Parathavar deep sea shark hunting and thimil longboats poetry kuraal",
        "expected_slugs": [
            "text-akanannuru-parathavar-pelagic-shark-hunting-and-thimil-poetry"
        ]
    },
    {
        "id": "PEL-02",
        "category": "Thimil Naval Architecture",
        "query": "Plank built thimil longboats and seagoing wave hydrodynamics jackfruit stitched coir seams",
        "expected_slugs": [
            "concept-plank-built-thimil-longboats-and-twin-outrigger-hydrodynamics"
        ]
    },
    {
        "id": "PEL-03",
        "category": "Shark Harpoon Ballistics",
        "query": "Deep sea shark and sawfish harpoon ballistics kuraal vaall detachable barbed iravu koli",
        "expected_slugs": [
            "concept-deep-sea-shark-and-sawfish-harpoonry-kuraal-vaall"
        ]
    },
    {
        "id": "PEL-04",
        "category": "Torchlight Night Fishing",
        "query": "Nocturnal ocean fishing with cast torches theevatti meenpidi fish liver oil and kungiliyam",
        "expected_slugs": [
            "concept-bioluminescent-night-fishing-with-oil-torches-theevatti-meenpidi"
        ]
    },
    {
        "id": "PEL-05",
        "category": "Net Knotting & Curing",
        "query": "Sun hemp drift net weaving mangrove bark boiling and beach fish curing karuvadu thattigal",
        "expected_slugs": [
            "concept-hemp-fiber-drift-net-knotting-and-beach-fish-curing-karuvadu"
        ]
    },
    {
        "id": "PEL-06",
        "category": "Pandya Coastal Epigraphy",
        "query": "Uvari Pandya inscriptions Parathavar fishing fleets and oceanic fish tithes thimil charters",
        "expected_slugs": [
            "insc-uvari-pandya-parathavar-fishing-fleet-and-salt-tithe-charters"
        ]
    },
    {
        "id": "PEL-07",
        "category": "Korkai Harpooner Charters",
        "query": "Korkai inscriptions on maritime fisher guilds and harpooner privileges valaiyar kottam",
        "expected_slugs": [
            "insc-korkai-pearl-diver-and-deep-sea-fisher-guild-epigraphs"
        ]
    },
    {
        "id": "PEL-08",
        "category": "Pelagic Topography",
        "query": "Uvari ancient Neithal thimil harpoon and pelagic fishery haven Gulf of Mannar",
        "expected_slugs": [
            "place-uvari-ancient-neithal-thimil-harpoon-and-pelagic-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Pelagic Fishing & Thimil Harpoonry")
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
