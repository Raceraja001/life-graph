#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "BAR-01",
        "query": "Tirumurukarruppadai verses mountain hermits draped in supple beaten tree-bark garments maravuri",
        "expected_slugs": [
            "text-tirumurukarruppadai-hermit-bark-garments-maravuri-poetry"
        ],
        "category": "Bark Cloth Poetry"
    },
    {
        "id": "BAR-02",
        "query": "Ficus and antiaris secondary phloem inner bast peeling and stream water retting mechanics",
        "expected_slugs": [
            "concept-ficus-and-antiaris-inner-bast-peeling-and-retting-mechanics"
        ],
        "category": "Bast Harvesting"
    },
    {
        "id": "BAR-03",
        "query": "Grooved hardwood mallet thattu-thadi tapa beating and stone anvil mechanical felting expansion",
        "expected_slugs": [
            "concept-grooved-hardwood-mallet-tapa-beating-and-fiber-felting-thattu-thadi"
        ],
        "category": "Mechanical Felting"
    },
    {
        "id": "BAR-04",
        "query": "Botanical rice starch sizing and tamarind seed gum pasai finishing sealing bark cloth pores",
        "expected_slugs": [
            "concept-botanical-starch-sizing-and-herbal-mastic-pasai-finishing"
        ],
        "category": "Botanical Sizing"
    },
    {
        "id": "BAR-05",
        "query": "Ascetic hermit bark vestments and proto-paper writing surfaces for medical recipes maravuri",
        "expected_slugs": [
            "concept-ascetic-hermit-bark-vestments-and-proto-paper-writing-sheets-maravuri"
        ],
        "category": "Ascetic Culture"
    },
    {
        "id": "BAR-06",
        "query": "Sirumalai Pandya inscriptions recording forest bast-fiber cordage and bark cloth tribute",
        "expected_slugs": [
            "insc-sirumalai-pandya-forest-fiber-tribute-charters"
        ],
        "category": "Forest Tribute Charters"
    },
    {
        "id": "BAR-07",
        "query": "Master bark cloth beater maravuri thozhilan shaping supple forest garments in Sirumalai",
        "expected_slugs": [
            "char-sirumalai-master-bark-cloth-beater-maravuri-thozhilan"
        ],
        "category": "Master Bark Beaters"
    },
    {
        "id": "BAR-08",
        "query": "Sirumalai ancient montane biosphere bast-fiber and beaten bark-cloth haven",
        "expected_slugs": [
            "place-sirumalai-ancient-bast-fiber-and-bark-haven"
        ],
        "category": "Forest Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Beaten Bark-Cloth Manufacture")
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
