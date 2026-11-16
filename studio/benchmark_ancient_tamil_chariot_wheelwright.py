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
        "query": "Purananuru verses on master wheelwright Kaikol Thachan crafting eight battle chariots in a month",
        "expected_slugs": [
            "text-purananuru-chariot-wheelwright-and-eight-chariots-craftsmanship-poetry"
        ],
        "category": "Literature & Metaphor"
    },
    {
        "id": "CHA-02",
        "query": "Bent felloe wooden rim segmentation Nemi joinery and pre stressed bronze tire binding",
        "expected_slugs": [
            "concept-bent-felloe-wooden-rim-segmentation-and-joinery-nemiyum-kodum"
        ],
        "category": "Felloe Mechanics"
    },
    {
        "id": "CHA-03",
        "query": "Hardwood Vengai and teak radial spoke compression mechanics and aerodynamic diamond profile",
        "expected_slugs": [
            "concept-hardwood-vengai-and-teak-radial-spoke-compression-mechanics"
        ],
        "category": "Spoke Dynamics"
    },
    {
        "id": "CHA-04",
        "query": "Bronze axle bushing castor oil lubrication and forged Acchaani linchpin in Tirukkural",
        "expected_slugs": [
            "concept-bronze-axle-bushing-castor-oil-lubrication-and-hub-acchaani"
        ],
        "category": "Tribology & Linchpins"
    },
    {
        "id": "CHA-05",
        "query": "Battlefield chariot shock absorption with rawhide suspended floor and flexible bamboo draft pole",
        "expected_slugs": [
            "concept-battlefield-chariot-shock-absorption-and-yoke-harness-acrodynamics"
        ],
        "category": "Suspension Engineering"
    },
    {
        "id": "CHA-06",
        "query": "Vallam Thanjavur chariot guild epigraphs and Thachak Kaani hereditary land charters",
        "expected_slugs": [
            "insc-vallam-thanjavur-chariot-guild-and-wheelwright-endowment-charters"
        ],
        "category": "Epigraphy & Arsenal"
    },
    {
        "id": "CHA-07",
        "query": "Master chariot wheelwright Thaer Seivon Thachan testing timber acoustic resonance and balance",
        "expected_slugs": [
            "char-vallam-master-chariot-wheelwright-thaer-seivon-thachan"
        ],
        "category": "Master Wheelwrights"
    },
    {
        "id": "CHA-08",
        "query": "Vallam ancient chariot wheelwright arsenal and bronze fitting haven near Thanjavur",
        "expected_slugs": [
            "place-vallam-ancient-chariot-wheelwright-and-bronze-fitting-haven"
        ],
        "category": "Fortress Arsenal Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Chariot Wheelwright & Axle Engineering")
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
