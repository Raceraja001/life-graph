#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "COP-01",
        "category": "Sacred Copper Verse",
        "query": "Thirumandiram classical verses on copperplate inscriptions and sacred yantra metallurgy Thirumoolar",
        "expected_slugs": [
            "text-thirumandiram-copperplate-mystical-diagrams-and-sacred-yantras-verse"
        ]
    },
    {
        "id": "COP-02",
        "category": "Dynastic Seal Ring Casting",
        "query": "Lost wax dynastic royal seal ring metallurgy ilanchinai valayam mudhirai tiger and twin fish crests",
        "expected_slugs": [
            "concept-lost-wax-dynastic-seal-ring-casting-ilanchinai-valayam"
        ]
    },
    {
        "id": "COP-03",
        "category": "Copper Engraving Art",
        "query": "Cold hammered copper plate engraving with hardened steel burins seppedu ezhuthu koli calligraphic incising",
        "expected_slugs": [
            "concept-cold-hammered-copper-plate-engraving-with-steel-burins-seppedu"
        ]
    },
    {
        "id": "COP-04",
        "category": "Meykeerthi Diplomatics",
        "query": "Imperial epigraphical diplomatics and poetic royal eulogies meykeerthi architecture Rajaraja Chola",
        "expected_slugs": [
            "concept-chola-epigraphical-diplomatics-and-poetic-preambles-meykeerthi"
        ]
    },
    {
        "id": "COP-05",
        "category": "Archival Vaults",
        "query": "Temple archival copperplate vaults and document repositories sasana kottam cedar boxes",
        "expected_slugs": [
            "concept-temple-archival-copperplate-vaults-and-ring-sealing-sasanam"
        ]
    },
    {
        "id": "COP-06",
        "category": "Chancery Epigraphy",
        "query": "Thiruvidaimaruthur Chola epigraphs on royal copperplate scriptorium and chancery grants",
        "expected_slugs": [
            "insc-thiruvidaimaruthur-chola-royal-copperplate-scriptorium-charters"
        ]
    },
    {
        "id": "COP-07",
        "category": "Thirty One Plate Charter",
        "query": "Thiruvalangadu imperial thirty one plate copperplate charter and seal ring epigraphs Rajendra Chola",
        "expected_slugs": [
            "insc-thiruvalangadu-imperial-thirty-one-plate-charter-and-seal-epigraphs"
        ]
    },
    {
        "id": "COP-08",
        "category": "Scriptorium Topography",
        "query": "Thiruvidaimaruthur ancient Chola copperplate scriptorium and chancery haven Mahalingaswamy",
        "expected_slugs": [
            "place-thiruvidaimaruthur-ancient-chola-copperplate-scriptorium-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Copperplate Charters & Royal Seals")
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
