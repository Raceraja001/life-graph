#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "COR-01",
        "query": "Submarine coral reef harvesting free diving with stone sinkers and bamboo prying chisels",
        "expected_slugs": [
            "concept-submarine-reef-coral-harvesting-and-bamboo-pole-prying"
        ],
        "category": "Submarine Harvesting"
    },
    {
        "id": "COR-02",
        "query": "Post harvest coral branch sweet water lye washing and wet sandstone abrasive grinding",
        "expected_slugs": [
            "concept-calcareous-coral-branch-seasoning-and-sandstone-abrasive-smoothing"
        ],
        "category": "Coral Seasoning"
    },
    {
        "id": "COR-03",
        "query": "High speed bow drill perforation of brittle coral beads with corundum abrasive slurry",
        "expected_slugs": [
            "concept-coral-bead-perforation-and-quartz-micro-drill-lapidary"
        ],
        "category": "Micro-Lapidary Drilling"
    },
    {
        "id": "COR-04",
        "query": "Scarlet coral necklaces pavazhamalai and pearls gifted in Thanjavur temple endowments",
        "expected_slugs": [
            "concept-scarlet-coral-necklaces-pavazhamalai-and-chola-temple-donations"
        ],
        "category": "Prestige Adornment"
    },
    {
        "id": "COR-05",
        "query": "Akananuru maritime poetry Parathavar divers harvesting branching red corals and pearls",
        "expected_slugs": [
            "text-akanannuru-coral-reef-diving-and-fisherfolk-pearl-poetry"
        ],
        "category": "Littoral Literature"
    },
    {
        "id": "COR-06",
        "query": "Manamelkudi Pandya royal charters customs duties on harvested marine coral boatloads",
        "expected_slugs": [
            "insc-manamelkudi-pandyar-coral-fishery-and-marine-revenue-charters"
        ],
        "category": "Customs Charters"
    },
    {
        "id": "COR-07",
        "query": "Veteran Parathavar coral diver and reef pilot Thathan Parathavan of Pamban Island",
        "expected_slugs": [
            "char-pamban-master-coral-diver-and-reef-navigator-pavazha-parathavar"
        ],
        "category": "Master Navigators"
    },
    {
        "id": "COR-08",
        "query": "Pamban ancient coral reef island haven and marine gem trading center Gulf of Mannar",
        "expected_slugs": [
            "place-pamban-ancient-coral-reef-haven-and-marine-gem-center"
        ],
        "category": "Reef Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Coral Reef Diving & Marine Gemmology")
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
