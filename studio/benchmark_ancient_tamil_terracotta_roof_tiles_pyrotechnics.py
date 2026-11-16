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
        "category": "Sangam Tiled Mansions",
        "query": "Pattinappalai classical Sangam verses on tiled mansions fireproof urban roofs and Kaveripoompattinam Uruthirankannanar",
        "expected_slugs": [
            "text-pattinappalai-verses-on-tiled-mansions-and-fireproof-urban-roofs"
        ]
    },
    {
        "id": "TIL-02",
        "category": "Interlocking Tile Geometry",
        "query": "Oodu veythal interlocking clay pantile roofing and water runoff slope geometry mechanics kaal oodu",
        "expected_slugs": [
            "concept-oodu-veythal-interlocking-clay-pantile-roofing-and-water-runoff-geometry"
        ]
    },
    {
        "id": "TIL-03",
        "category": "Downdraft Kiln Pyrotechnics",
        "query": "Soozhai subterranean downdraft tile firing kiln pyrotechnics rice husk thermal insulation 900C",
        "expected_slugs": [
            "technology-soozhai-subterranean-downdraft-tile-firing-kiln-pyrotechnics"
        ]
    },
    {
        "id": "TIL-04",
        "category": "Drainage Tiles & Ridge Caps",
        "query": "Kaal oodu and muthugu oodu grooved flanged drainage tiles and ridge cap seals hanging nibs",
        "expected_slugs": [
            "artifact-kaal-oodu-and-muthugu-oodu-grooved-drainage-tiles-and-ridge-cap-seals"
        ]
    },
    {
        "id": "TIL-05",
        "category": "Clay Levigation Science",
        "query": "Man padham Vaigai alluvial clay aging levigation and quartz grog tempering shrinkage kazhimann",
        "expected_slugs": [
            "concept-man-padham-vaigai-alluvial-clay-aging-levigation-and-grog-tempering"
        ]
    },
    {
        "id": "TIL-06",
        "category": "Master Tile Guilds",
        "query": "Kuyavar chakri guild hereditary corporation of master tile makers and potters charters kuyavan kani",
        "expected_slugs": [
            "institution-kuyavar-chakri-guild-hereditary-corporation-of-master-tile-makers"
        ]
    },
    {
        "id": "TIL-07",
        "category": "Tile Molding Presses",
        "query": "Achchu palagai hardwood tile molding frames wire cut clay presses and drying racks Teak",
        "expected_slugs": [
            "technology-achchu-palagai-hardwood-tile-molding-presses-and-wire-cutters"
        ]
    },
    {
        "id": "TIL-08",
        "category": "Ceramic Topography",
        "query": "Manamadurai ancient terracotta tile and kiln haven Vaigai riverbed ceramic craftsmanship",
        "expected_slugs": [
            "place-manamadurai-ancient-terracotta-tile-and-kiln-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Terracotta Roof Tiling, Interlocking Pantiles & Kiln Pyrotechnics")
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
