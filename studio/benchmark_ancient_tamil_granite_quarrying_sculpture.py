#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "QUR-01",
        "category": "Pandya Epigraphs",
        "query": "Epigraphical inscriptions and charters on early Pandya monolithic sculptors and granite rock cut shrines perun thatchur",
        "expected_slugs": [
            "text-chulavamsa-and-epigraphs-on-pandya-monolithic-sculptors-and-granite-caves"
        ]
    },
    {
        "id": "QUR-02",
        "category": "Wedge Quarrying",
        "query": "Aappu vettuthal dry wooden wedge water swelling and thermal quench granite quarrying mortise",
        "expected_slugs": [
            "technology-aappu-vettuthal-dry-wooden-wedge-water-swelling-and-fire-quench-quarrying"
        ]
    },
    {
        "id": "QUR-03",
        "category": "Monolithic Rock Cutting",
        "query": "Vettuvan Koil top down monolithic trench rock cutting engineering Kalugumalai stupi shikhara",
        "expected_slugs": [
            "technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering"
        ]
    },
    {
        "id": "QUR-04",
        "category": "Wootz Chisels",
        "query": "Wootz karunkal uli tempered hypereutectoid crucible steel stone carving chisels cementite hardness",
        "expected_slugs": [
            "artifact-wootz-karunkal-uli-tempered-hypereutectoid-steel-stone-carving-chisels"
        ]
    },
    {
        "id": "QUR-05",
        "category": "Iconometric Canons",
        "query": "Talamana proportional iconometric grid system and Silpa measurement canons angula tala Dasa-Tala",
        "expected_slugs": [
            "concept-talamana-proportional-iconometric-grid-and-measurement-canons"
        ]
    },
    {
        "id": "QUR-06",
        "category": "Sculptor Guilds",
        "query": "Perun thatchar silpi guild master granite sculptor corporations and royal stone endowments sthapathi",
        "expected_slugs": [
            "institution-perun-thatchar-silpi-guild-master-granite-sculptor-guilds"
        ]
    },
    {
        "id": "QUR-07",
        "category": "Abrasive Polishing",
        "query": "Kal palupu quartz sand abrasive stone polishing and fine relief burnishing corundum emery",
        "expected_slugs": [
            "concept-kal-palupu-quartz-sand-abrasive-polishing-and-relief-burnishing"
        ]
    },
    {
        "id": "QUR-08",
        "category": "Sculpture Topography",
        "query": "Kalugumalai ancient Pandya monolithic granite sculpture haven Vettuvan Koil Ellora of the South",
        "expected_slugs": [
            "place-kalugumalai-ancient-pandya-monolithic-granite-sculpture-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Granite Quarrying, Wedge-Splitting & Monolithic Sculpting")
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
