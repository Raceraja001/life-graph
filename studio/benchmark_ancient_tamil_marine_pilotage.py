#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "PIL-01",
        "query": "Akananuru poetry maritime pilots in shallow skiffs sounding estuarine sandbars for ocean ships",
        "expected_slugs": [
            "text-akanunuru-maritime-pilotage-and-sandbar-sounding-poetry"
        ],
        "category": "Pilotage Poetry"
    },
    {
        "id": "PIL-02",
        "query": "Bamboo sounding pole thandukal and tallow tipped lead fathom bathymetry detecting shoals",
        "expected_slugs": [
            "concept-bamboo-sounding-pole-and-lead-fathom-bathymetry-thandukal"
        ],
        "category": "Nautical Bathymetry"
    },
    {
        "id": "PIL-03",
        "query": "Direction finding coastal crows disak kaakkai released from ship masts to locate shore",
        "expected_slugs": [
            "concept-direction-finding-shore-sighting-birds-disak-kaakkai-navigation"
        ],
        "category": "Avian Navigation"
    },
    {
        "id": "PIL-04",
        "query": "Estuarine sandbar littoral drift and riding flood tidal surge pongu-mugam across rivermouth bars",
        "expected_slugs": [
            "concept-estuarine-sandbar-shoal-dynamics-and-tidal-surge-fluvial-drift"
        ],
        "category": "Tidal Navigation"
    },
    {
        "id": "PIL-05",
        "query": "Nocturnal bioluminescent plankton dinoflagellate glowing wake tracking rip tides kadal meruku",
        "expected_slugs": [
            "concept-nocturnal-bioluminescent-plankton-current-tracking-kadal-meruku"
        ],
        "category": "Bioluminescent Tracking"
    },
    {
        "id": "PIL-06",
        "query": "Devipattinam Pandya inscriptions recording harbor pilotage rights and mooring posts",
        "expected_slugs": [
            "insc-devipattinam-pandya-harbor-pilot-and-mooring-charters"
        ],
        "category": "Port Epigraphy"
    },
    {
        "id": "PIL-07",
        "query": "Master estuarine harbor pilot kadal kaan thalaivan guiding foreign ships at Devipattinam",
        "expected_slugs": [
            "char-devipattinam-master-estuarine-pilot-kadal-kaan-thalaivan"
        ],
        "category": "Master Harbor Pilots"
    },
    {
        "id": "PIL-08",
        "query": "Devipattinam ancient Palk Bay estuarine harbor pilotage and navapashanam haven",
        "expected_slugs": [
            "place-devipattinam-ancient-estuarine-pilotage-haven"
        ],
        "category": "Harbor Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Marine Pilotage & Navigation")
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
