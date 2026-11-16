#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "SAR-01",
        "query": "Manimekalai fivefold funerary practices including legged sarcophagi thaazhiyin kavippor",
        "expected_slugs": [
            "text-manimekalai-funerary-burial-types-and-sarcophagi-poetry"
        ],
        "category": "Funerary Literature"
    },
    {
        "id": "SAR-02",
        "query": "Multi-legged terracotta burial sarcophagus kavikkal with hollow vented legs and pit kiln firing",
        "expected_slugs": [
            "concept-multi-legged-terracotta-sarcophagus-molding-and-firing-kavikkal"
        ],
        "category": "Sarcophagus Pyrotechnics"
    },
    {
        "id": "SAR-03",
        "query": "Zoomorphic horned ram and elephant terracotta sarcophagus lid sculptures",
        "expected_slugs": [
            "concept-zoomorphic-ram-and-elephant-funerary-lid-sculpture"
        ],
        "category": "Funerary Iconography"
    },
    {
        "id": "SAR-04",
        "query": "Inverted fired black and red ware bowls socketed iron axes and tridents grave goods",
        "expected_slugs": [
            "concept-black-and-red-ware-funerary-vessels-and-iron-weapon-offerings"
        ],
        "category": "Grave Metallurgy"
    },
    {
        "id": "SAR-05",
        "query": "Granitic orthostats in swastika plan with circular port hole and levered capstone cist",
        "expected_slugs": [
            "concept-granitic-orthostat-chamber-and-capstone-cist-burial-mechanics"
        ],
        "category": "Cist Architecture"
    },
    {
        "id": "SAR-06",
        "query": "Master potter kavikkal kuyavan sculpting multi-legged clay sarcophagi at Paiyampalli",
        "expected_slugs": [
            "char-paiyampalli-master-sarcophagus-potter-kavikkal-kuyavan"
        ],
        "category": "Master Potters"
    },
    {
        "id": "SAR-07",
        "query": "Sanur megalithic stone mason kallaraignar raising orthostat chambers and capstones",
        "expected_slugs": [
            "char-sanur-megalithic-chamber-builder-kallaraignar"
        ],
        "category": "Megalithic Masons"
    },
    {
        "id": "SAR-08",
        "query": "Paiyampalli ancient Megalithic terracotta sarcophagus and iron smelting haven",
        "expected_slugs": [
            "place-paiyampalli-megalithic-sarcophagus-haven"
        ],
        "category": "Megalithic Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Megalithic Terracotta Sarcophagi & Iron Deposits")
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
