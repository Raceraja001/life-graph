#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "CHA-01",
        "category": "Saivite Chariot Hymn",
        "query": "Tevaram Saivite hymns on colossal Azhi Ther of Tiruvarur and sacred chariot processions Sundarar Appar",
        "expected_slugs": [
            "text-tevaram-tiruvarur-hymns-on-azhi-ther-processional-grandeur"
        ]
    },
    {
        "id": "CHA-02",
        "category": "Chariot Architecture",
        "query": "Ther thatchu ancient Tamil sacred temple chariot architecture Vastu and modular woodcraft mortise tenon",
        "expected_slugs": [
            "concept-ther-thatchu-ancient-tamil-sacred-temple-chariot-architecture-and-woodcraft"
        ]
    },
    {
        "id": "CHA-03",
        "category": "Colossal Car Mechanics",
        "query": "Azhi ther structural mechanics dynamic load distribution and colossal wooden car engineering 300 tons",
        "expected_slugs": [
            "technology-azhi-ther-colossal-multitiered-wooden-processional-car-mechanics"
        ]
    },
    {
        "id": "CHA-04",
        "category": "Composite Wheels",
        "query": "Urulai and achu composite segmented wooden wheels forged iron hoop tires and axle mechanics Iluppai",
        "expected_slugs": [
            "technology-urulai-and-achu-composite-wooden-wheel-and-axle-load-bearing-system"
        ]
    },
    {
        "id": "CHA-05",
        "category": "Hauling Cables",
        "query": "Ther vadam monumental braided coconut coir processional pull ropes dynamic tensile rigging 600 kN",
        "expected_slugs": [
            "artifact-ther-vadam-massive-braided-coconut-coir-processional-pull-ropes"
        ]
    },
    {
        "id": "CHA-06",
        "category": "Kinetic Braking Wedges",
        "query": "Aappu and thadukku hardwood kinetic braking wedges and manual chariot steering chocks tamarind",
        "expected_slugs": [
            "technology-aappu-thadukku-wooden-wedge-kinetic-braking-and-steering-chocks"
        ]
    },
    {
        "id": "CHA-07",
        "category": "Wheelwright Guilds",
        "query": "Ratha kara silpi guild chariot wheelwright master carpenter and smith corporations Chola thatcha kaani",
        "expected_slugs": [
            "institution-ratha-kara-silpi-guild-chariot-wheelwright-and-carpentry-guilds"
        ]
    },
    {
        "id": "CHA-08",
        "category": "Chariot Topography",
        "query": "Tiruvarur ancient monumental temple chariot wheelwrighting and Azhi Ther haven Kaveri delta",
        "expected_slugs": [
            "place-tiruvarur-ancient-monumental-temple-chariot-and-wheelwright-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Temple Chariot Wheelwrighting, Timber Mechanics & Hydraulic Braking")
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
