#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "SUG-01",
        "category": "Sangam Cane Verse",
        "query": "Purananuru 392 classical Sangam verses on creaking sugarcane mills steaming boiling vats and jaggery Kovan Puthur Thevanar",
        "expected_slugs": [
            "text-purananuru-392-verses-on-creaking-sugarcane-presses-and-steaming-vats"
        ]
    },
    {
        "id": "SUG-02",
        "category": "Rotary Cane Crusher",
        "query": "Karumbu aalai rotary granite mortar and wooden pestle oxen driven cane crusher mechanics Iluppai",
        "expected_slugs": [
            "concept-karumbu-aalai-rotary-granite-mortar-and-wooden-pestle-cane-crushers"
        ]
    },
    {
        "id": "SUG-03",
        "category": "Boiling Battery Furnaces",
        "query": "Aduppu kottagai multi pan gravity stepped juice boiling clarification batteries and furnaces bagasse",
        "expected_slugs": [
            "technology-aduppu-kottagai-multi-pan-gravity-stepped-juice-clarification-furnaces"
        ]
    },
    {
        "id": "SUG-04",
        "category": "Jaggery Molds & Pans",
        "query": "Achuvellam and kopari solid jaggery casting molds and massive copper boiling pans strike point",
        "expected_slugs": [
            "artifact-achuvellam-and-kopari-solid-jaggery-molds-and-cast-copper-evaporation-pans"
        ]
    },
    {
        "id": "SUG-05",
        "category": "Juice Clarification Chemistry",
        "query": "Vendai mucilage and shell lime organic cane juice clarification and scum skimmer chemistry defecation",
        "expected_slugs": [
            "concept-vendai-mucilage-and-lime-natural-cane-juice-defecation-chemistry"
        ]
    },
    {
        "id": "SUG-06",
        "category": "Sugar Millers Guild",
        "query": "Karumbu velan kudi guild of sugarcane millers boiling house corporations and aalai vari charters",
        "expected_slugs": [
            "institution-karumbu-velan-kudi-guild-of-sugar-millers-and-boiling-house-masters"
        ]
    },
    {
        "id": "SUG-07",
        "category": "Roller Cane Mills",
        "query": "Karumbu pidzhi pori gear driven hardwood and iron roller cane crushers extraction efficiency",
        "expected_slugs": [
            "artifact-karumbu-pidzhi-pori-gear-driven-iron-and-hardwood-roller-crushers"
        ]
    },
    {
        "id": "SUG-08",
        "category": "Sugar Topography",
        "query": "Mohanur ancient Kaveri sugarcane milling haven alluvial sugar boiling hearths Kongu",
        "expected_slugs": [
            "place-mohanur-ancient-kaveri-sugarcane-milling-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Sugarcane Milling, Rotary Crushing & Boiling House Granulation")
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
