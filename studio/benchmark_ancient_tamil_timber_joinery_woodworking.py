#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Teak & Rosewood Joinery, Mortise-Tenon Woodworking & Royal Palaces
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "TIM-01",
        "name": "Sangam Timber Verse",
        "query": "Nedunalvadai classical Sangam verses on mortised palace rafters sandalwood pillars and Nakkirar",
        "expected": [
            "text-nedunalvadai-verses-on-sandalwood-pillars-and-mortised-palace-rafters"
        ]
    },
    {
        "id": "TIM-02",
        "name": "Mortise-Tenon Engineering",
        "query": "Poruthu thatchu mortise and tenon interlocking timber joinery engineering wedged tenons",
        "expected": [
            "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering"
        ]
    },
    {
        "id": "TIM-03",
        "name": "Cantilever Wooden Brackets",
        "query": "Kodi madangai cantilevered carved wooden brackets and overhanging eaves support kodungai",
        "expected": [
            "technology-kodi-madangai-cantilevered-carved-wooden-brackets-and-eaves-support"
        ]
    },
    {
        "id": "TIM-04",
        "name": "Traditional Framing Tools",
        "query": "Koor uli and vaali traditional heavy mortise chisels hewing adzes and scribers wootz",
        "expected": [
            "artifact-ulakkai-and-koor-vaali-hardwood-framing-tools-mortise-chisels-and-adzes"
        ]
    },
    {
        "id": "TIM-05",
        "name": "Teak Wood Chemistry",
        "query": "Thekku and eetti teak and rosewood heartwood chemistry and termite resistance tectoquinone",
        "expected": [
            "concept-thekku-and-eetti-teak-and-rosewood-sapwood-curing-and-termite-resisting-resins"
        ]
    },
    {
        "id": "TIM-06",
        "name": "Master Carpenters Guild",
        "query": "Thatchar rathakara guild corporation of master woodcrafters royal architects thatcha kaani",
        "expected": [
            "institution-thatchar-rathakara-corporation-of-master-woodcrafters-and-palace-architects"
        ]
    },
    {
        "id": "TIM-07",
        "name": "Lattice Windows & Louvers",
        "query": "Charupadi and jalakavathayan perforated timber lattice windows and microclimatic ventilation",
        "expected": [
            "technology-charupadi-perforated-timber-lattice-windows-and-microclimatic-draft-channels"
        ]
    },
    {
        "id": "TIM-08",
        "name": "Wooden Palace Citadel",
        "query": "Padmanabhapuram ancient Chera Venad monumental wooden palace haven Veli hills teak",
        "expected": [
            "place-padmanabhapuram-ancient-wooden-palace-haven"
        ]
    }
]

def get_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Ollama embedding error: {res.text}")
    return res.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Teak & Rosewood Joinery, Mortise-Tenon Woodworking & Royal Palaces")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        vec = get_embedding(tc["query"])
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
        print("-" * 80)

    elapsed = time.time() - t0
    acc = (passed / len(TEST_CASES)) * 100
    print(f"RESULTS: {passed}/{len(TEST_CASES)} passed ({acc:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    if passed < len(TEST_CASES):
        sys.exit(1)

if __name__ == "__main__":
    main()
