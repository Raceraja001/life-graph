#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "CAS-01",
        "category": "Sangam Damming Verse",
        "query": "Purananuru 18 Pandyan Nedunchezhian verses on damming valleys and creating immense reservoirs Kudapulaviyanar",
        "expected_slugs": [
            "text-purananuru-18-nedunchezhian-verses-on-valley-damming-and-reservoir-hydraulics"
        ]
    },
    {
        "id": "CAS-02",
        "category": "Cascade Hydrology",
        "query": "Eri ayam interconnected tank cascade hydrology and catchment runoff management meso-watershed",
        "expected_slugs": [
            "concept-eri-ayam-interconnected-tank-cascade-catchment-hydrology"
        ]
    },
    {
        "id": "CAS-03",
        "category": "Silt Sluice Mechanics",
        "query": "Kumizhi thumbu subaquatic silt clearing dual aperture piston sluice mechanics hydraulic vortex suction",
        "expected_slugs": [
            "technology-kumizhi-thumbu-subaquatic-silt-clearing-piston-sluice-mechanics"
        ]
    },
    {
        "id": "CAS-04",
        "category": "Granite Surplus Weirs",
        "query": "Kalingu dressed granite curved crest surplus escape weir overflow hydraulics flash-boards",
        "expected_slugs": [
            "technology-kalingu-dressed-granite-curved-crest-surplus-escape-weirs"
        ]
    },
    {
        "id": "CAS-05",
        "category": "Subterranean Conduits",
        "query": "Madhavai and sirai subterranean dressed stone gravity conduit channels barrel flumes",
        "expected_slugs": [
            "technology-madhavai-and-sirai-subterranean-dressed-stone-gravity-conduits"
        ]
    },
    {
        "id": "CAS-06",
        "category": "Village Tank Committee",
        "query": "Eri variyam Chola village republic irrigation supervision committee and desilting charters kudavolai",
        "expected_slugs": [
            "institution-eri-variyam-chola-village-republic-irrigation-supervision-committee"
        ]
    },
    {
        "id": "CAS-07",
        "category": "Intake Sluice Plugs",
        "query": "Thumbu kal perforated granite intake cylinder plugs and floating wooden pistons kumizhi kambu",
        "expected_slugs": [
            "artifact-thumbu-kal-perforated-granite-intake-plugs-and-wooden-pistons"
        ]
    },
    {
        "id": "CAS-08",
        "category": "Cascade Topography",
        "query": "Madurantakam ancient Chola reservoir cascade and monumental kalingu haven Palar basin",
        "expected_slugs": [
            "place-madurantakam-ancient-chola-reservoir-cascade-and-kalingu-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Megalithic Rock Sluice Hydraulic Engineering & Tank Cascades")
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
