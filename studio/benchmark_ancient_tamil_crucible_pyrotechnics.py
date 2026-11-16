#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "CRU-01",
        "query": "Refractory clay crucible moosai modeling rice husk temper high silica mullite porosity",
        "expected_slugs": [
            "concept-refractory-clay-crucible-modeling-and-rice-husk-temper-moosai"
        ],
        "category": "Refractory Materials"
    },
    {
        "id": "CRU-02",
        "query": "Natural crystalline flake graphite slip lining preventing feo slag corrosion and carbon control",
        "expected_slugs": [
            "concept-graphite-slip-coating-and-carbon-diffusion-barrier-mechanics"
        ],
        "category": "Graphite Linings"
    },
    {
        "id": "CRU-03",
        "query": "Forced draft terracotta tuyere nozzle thoombu venturi acceleration high velocity air jet",
        "expected_slugs": [
            "concept-forced-draft-terracotta-tuyere-nozzle-aerodynamics-thoombu"
        ],
        "category": "Tuyere Aerodynamics"
    },
    {
        "id": "CRU-04",
        "query": "Sunken cylindrical pit furnace thermal insulation fourteen hundred degree crucible steel melting",
        "expected_slugs": [
            "concept-fourteen-hundred-degree-crucible-steel-thermal-furnace-insulation"
        ],
        "category": "Furnace Insulation"
    },
    {
        "id": "CRU-05",
        "query": "Perumpanarruppadai verses on iron forge blast furnaces roaring bellows and scarlet crucibles",
        "expected_slugs": [
            "text-perumpanarruppadai-iron-furnaces-and-crucible-poetry"
        ],
        "category": "Foundry Literature"
    },
    {
        "id": "CRU-06",
        "query": "Guttur Dharmapuri excavated wootz steel sunken furnace pits and refractory crucibles",
        "expected_slugs": [
            "insc-guttur-dharmapuri-crucible-steel-furnace-charters"
        ],
        "category": "Excavated Furnaces"
    },
    {
        "id": "CRU-07",
        "query": "Master crucible maker moosai kuyavan shaping rice-husk kaolin crucibles at Guttur",
        "expected_slugs": [
            "char-guttur-master-crucible-maker-moosai-kuyavan"
        ],
        "category": "Master Potters"
    },
    {
        "id": "CRU-08",
        "query": "Guttur ancient Dharmapuri iron basin crucible wootz steel foundry haven",
        "expected_slugs": [
            "place-guttur-ancient-crucible-furnace-haven"
        ],
        "category": "Foundry Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Crucible Pyrotechnics & Tuyeres")
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
