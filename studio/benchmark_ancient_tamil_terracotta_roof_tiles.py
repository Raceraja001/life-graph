#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "TIL-01",
        "query": "Akananuru verses describing urban grooved tile roofs Varikkuda Koorai Odu and monsoon drainage",
        "expected_slugs": [
            "text-akanunuru-grooved-tile-roofs-and-monsoon-drainage-poetry"
        ],
        "category": "Literature & Architecture"
    },
    {
        "id": "TIL-02",
        "query": "Flanged and grooved interlocking terracotta roof tile molding mechanics excavated at Keezhadi",
        "expected_slugs": [
            "concept-flanged-and-grooved-interlocking-terracotta-roof-tile-molding"
        ],
        "category": "Tile Molding Mechanics"
    },
    {
        "id": "TIL-03",
        "query": "High silica alluvial clay levigation quartz tempering and tile clamp kiln firing at 850 C",
        "expected_slugs": [
            "concept-high-silica-alluvial-clay-levigation-and-tile-firing-pyrotechnics"
        ],
        "category": "Ceramic Pyrotechnics"
    },
    {
        "id": "TIL-04",
        "query": "Stormwater eaves terracotta gargoyles and interlocking downspout pipe drainage mechanics",
        "expected_slugs": [
            "concept-stormwater-eaves-gargoyles-and-slotted-tile-drainage-mechanics"
        ],
        "category": "Eaves & Drainage Engineering"
    },
    {
        "id": "TIL-05",
        "query": "Fireproof urban tile roofing municipal regulations and rooftop sand urns in Sangam metropolises",
        "expected_slugs": [
            "concept-fireproof-urban-tile-roofing-in-sangam-metropolises"
        ],
        "category": "Fire-Safety Regulations"
    },
    {
        "id": "TIL-06",
        "query": "Uraiyur Chola capital Tamil-Brahmi inscribed brick and tile kiln guild charters",
        "expected_slugs": [
            "insc-uraiyur-chola-capital-brick-and-tile-kiln-guild-charters"
        ],
        "category": "Capital Epigraphy"
    },
    {
        "id": "TIL-07",
        "query": "Master roof tile pyrotechnician Kuyavan Odu Kollan managing clamp kilns at Uraiyur",
        "expected_slugs": [
            "char-uraiyur-master-roof-tile-pyrotechnician-kuyavan-odu-kollan"
        ],
        "category": "Master Pyrotechnicians"
    },
    {
        "id": "TIL-08",
        "query": "Uraiyur ancient terracotta tile brick kiln and Chola capital haven on Kaveri floodplain",
        "expected_slugs": [
            "place-uraiyur-ancient-terracotta-tile-and-chola-capital-haven"
        ],
        "category": "Capital Haven Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Terracotta Roof Tile & Drainage")
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
