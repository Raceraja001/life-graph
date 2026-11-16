#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "HYD-01",
        "category": "Sangam Riverine Poetry",
        "query": "Porunarattruppadai classical poetry Kaveri stone embankments sluices and inundation canals Karikala Chola",
        "expected_slugs": [
            "text-porunarattruppadai-chola-irrigation-sluices-and-river-embankment-verse"
        ]
    },
    {
        "id": "HYD-02",
        "category": "Piston Sluice Physics",
        "query": "Piston valve reservoir silt clearing underwater sluice architecture kumizhi thoombu engineering vortex",
        "expected_slugs": [
            "concept-piston-valve-reservoir-silt-clearing-sluice-engineering-kumizhi-thoombu"
        ]
    },
    {
        "id": "HYD-03",
        "category": "Cascade Tank Hydraulics",
        "query": "Interconnected cascade tank watershed architecture micro basin hydraulics eri network contour reservoirs",
        "expected_slugs": [
            "concept-interconnected-cascade-tank-watershed-architecture-eri-cascade"
        ]
    },
    {
        "id": "HYD-04",
        "category": "Spillway Masonry",
        "query": "Cut stone masonry overflow weirs and emergency flood channels kalingu flashboard slotted pillars",
        "expected_slugs": [
            "concept-masonry-overflow-weirs-and-emergency-flood-channels-kalingu"
        ]
    },
    {
        "id": "HYD-05",
        "category": "Subterranean Aqueducts",
        "query": "Sub surface terracotta pipe aqueducts and gravity sand filtration potable water cisterns urani",
        "expected_slugs": [
            "concept-sub-surface-terracotta-pipe-aqueducts-and-cistern-filtration-urani"
        ]
    },
    {
        "id": "HYD-06",
        "category": "Reservoir Epigraphy",
        "query": "Kaveripakkam imperial epigraphs lake sluice construction desilting boats eri variyam maintenance",
        "expected_slugs": [
            "insc-kaveripakkam-chola-sluice-construction-and-lake-endowment-epigraphs"
        ]
    },
    {
        "id": "HYD-07",
        "category": "Early Sluice Inscriptions",
        "query": "Porunthal archaeological epigraphs silt clearing stone sluices thoombu irrigation water endowments",
        "expected_slugs": [
            "insc-porunthal-lake-embankment-and-kumizhi-thoombu-sluice-charters"
        ]
    },
    {
        "id": "HYD-08",
        "category": "Hydraulic Topography",
        "query": "Kaveripakkam ancient cascade reservoir and piston sluice engineering haven Palar basin",
        "expected_slugs": [
            "place-kaveripakkam-ancient-chola-cascade-reservoir-and-sluice-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Hydraulic Sluices & Cascade Reservoirs")
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
