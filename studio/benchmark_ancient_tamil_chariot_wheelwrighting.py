#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Chariot Wheelwrighting, Spoke-Felloe Dynamics & Processional Vehicles
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "CHR-01",
        "name": "Sangam Wheelwright Verse",
        "query": "Purananuru 87 classical Sangam verses on royal wheelwrights hardwood felloes and war chariots Avvaiyar",
        "expected": [
            "text-purananuru-87-verses-on-master-wheelwrights-and-monumental-war-chariots"
        ]
    },
    {
        "id": "CHR-02",
        "name": "Wheel Kinematics",
        "query": "Azhi kaal wheel kinematics segmental felloe joinery and radial spoke pre stressing",
        "expected": [
            "concept-azhi-kaal-composite-timber-wheel-felloe-spoke-and-hub-kinematics"
        ]
    },
    {
        "id": "CHR-03",
        "name": "Chariot Cable Rigging",
        "query": "Thaer vada kattu monumental coir towing hawsers lever steering and turning physics",
        "expected": [
            "technology-thaer-vada-kattu-massive-coir-towing-cable-rigging-and-steering-pivots"
        ]
    },
    {
        "id": "CHR-04",
        "name": "Iron Wheel Tires",
        "query": "Irumbu pattarai and kadam shrink fitted iron wheel tires hardened linchpins and axle sleeves",
        "expected": [
            "artifact-irumbu-pattarai-and-kadam-wrought-iron-wheel-tires-and-axle-linchpins"
        ]
    },
    {
        "id": "CHR-05",
        "name": "Timber Vibration Damping",
        "query": "Rathakara mechanics structural timber damping harmonic resonance and deflection elasticity",
        "expected": [
            "concept-rathakara-structural-timber-damping-and-shock-absorption-physics"
        ]
    },
    {
        "id": "CHR-06",
        "name": "Chariot Builders Guild",
        "query": "Rathakara and thatchar royal corporation of chariot architects guild charters and epigraphs",
        "expected": [
            "institution-rathakara-and-thaer-thatchar-corporation-of-temple-chariot-architects"
        ]
    },
    {
        "id": "CHR-07",
        "name": "Pyramidal Vimana Spire",
        "query": "Chithira thaer multi tiered pyramidal vimana superstructure and modular timber framing",
        "expected": [
            "technology-chithira-thaer-multi-tiered-pyramidal-vimana-superstructure-engineering"
        ]
    },
    {
        "id": "CHR-08",
        "name": "Chariot Haven Thiruvarur",
        "query": "Thiruvarur ancient Azhi Ther chariot haven Kamalalayam tank and processional capital",
        "expected": [
            "place-thiruvarur-ancient-azhi-ther-chariot-haven"
        ]
    }
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Ollama embedding error: {res.text}")
    return res.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Chariot Wheelwrighting, Spoke-Felloe Dynamics & Processional Vehicles")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        vec = get_bge_embedding(tc["query"])
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector ASC
            LIMIT 5;
        """, (vec, vec))
        rows = cur.fetchall()
        top1 = rows[0][0] if rows else None
        top1_sim = rows[0][1] if rows else 0.0

        if top1 in tc["expected"]:
            passed += 1
            print(f"[PASS] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for r in rows:
                print(f"    - {r[0]} (Sim: {r[1]:.4f})")

    elapsed = time.time() - t0
    acc = (passed / len(TEST_CASES)) * 100
    print("=" * 80)
    print(f"SUMMARY: {passed}/{len(TEST_CASES)} passed ({acc:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    cur.close()
    conn.close()

    if passed < len(TEST_CASES):
        sys.exit(1)

if __name__ == "__main__":
    main()
