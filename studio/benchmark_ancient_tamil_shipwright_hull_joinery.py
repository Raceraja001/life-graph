#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "SHP-01",
        "category": "Sangam Shipwright Verse",
        "query": "Perumpanattruppadai classical Sangam verses on oceanic masted vessels and bustling shipwright harbors Uruthirankannanar",
        "expected_slugs": [
            "text-perumpanattruppadai-verses-on-oceanic-masted-vessels-and-shipwright-harbors"
        ]
    },
    {
        "id": "SHP-02",
        "category": "Hull Joinery Mechanics",
        "query": "Kappal kattu edge joined pegged mortise tenon and sewn plank hull mechanics naval architecture maravani",
        "expected_slugs": [
            "concept-kappal-kattu-ancient-tamil-edge-joined-tenon-and-sewn-hull-mechanics"
        ]
    },
    {
        "id": "SHP-03",
        "category": "Transoceanic Hulls",
        "query": "Marakkalam and vangam multi decked transoceanic wooden cargo hulls deep sea voyages 500 tons",
        "expected_slugs": [
            "technology-marakkalam-and-vangam-multi-decked-transoceanic-wooden-cargo-hulls"
        ]
    },
    {
        "id": "SHP-04",
        "category": "Marine Pitch Caulking",
        "query": "Kungiliyam and ennai boiled dammar tree resin and fish oil marine waterproof caulking shell lime",
        "expected_slugs": [
            "artifact-kungiliyam-and-ennai-boiled-dammar-resin-and-fish-oil-marine-caulking"
        ]
    },
    {
        "id": "SHP-05",
        "category": "Steering & Rigging",
        "query": "Sukkaan and paai maram axial quarter rudders balance keels and woven pandanus mat sails helmsman",
        "expected_slugs": [
            "technology-sukkaan-and-paai-maram-axial-quarter-rudders-and-woven-mat-rigging"
        ]
    },
    {
        "id": "SHP-06",
        "category": "Shipwright Corporations",
        "query": "Marakkar kappal thatchar corporation hereditary guild of naval shipwrights and dockyard charters",
        "expected_slugs": [
            "institution-marakkar-kappal-thatchar-corporation-guild-of-naval-shipwrights"
        ]
    },
    {
        "id": "SHP-07",
        "category": "Marine Fasteners",
        "query": "Irumbu aani and maravani forged copper clenches and shipboard corrosion resistant fastenings treenails",
        "expected_slugs": [
            "artifact-irumbu-aani-and-maravani-corrosion-resistant-bronze-and-copper-sheathing-clenches"
        ]
    },
    {
        "id": "SHP-08",
        "category": "Shipyard Topography",
        "query": "Adirampattinam ancient marakkalam shipwright and caulking haven Palk Bay maritime yard",
        "expected_slugs": [
            "place-adirampattinam-ancient-marakkalam-shipwright-and-caulking-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Shipwright Hull Joinery, Tenon Planking & Caulking Resins")
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
