#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Palm-Leaf Manuscript Scribing, Iron Stylus Metallurgy & Herbal Preservatives
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "PAL-01",
        "name": "Tholkappiyam Scroll Verse",
        "query": "Tholkappiyam Payiram classical verses on engraved palm scrolls academic conclaves Panamparanar",
        "expected": [
            "text-tholkappiyam-payiram-verses-on-engraved-palm-scrolls-and-academic-conclaves"
        ]
    },
    {
        "id": "PAL-02",
        "name": "Palm Leaf Curing Science",
        "query": "Thalai padham palmyra leaf boiling herb steaming and midrib sizing technology Borassus",
        "expected": [
            "concept-thalai-patham-borassus-flabellifer-palm-leaf-boiling-curing-and-rib-removal"
        ]
    },
    {
        "id": "PAL-03",
        "name": "Steel Stylus Metallurgy",
        "query": "Ezhuthani varkkam hardened steel stylus metallurgy bevel geometry and incision mechanics wootz",
        "expected": [
            "technology-ezhuthani-varkkam-hardened-steel-stylus-geometry-and-incision-mechanics"
        ]
    },
    {
        "id": "PAL-04",
        "name": "Dual Purpose Styli",
        "query": "Koodaram and gandham dual purpose styli with scribing needles and leaf cutting chisel blades",
        "expected": [
            "artifact-koodaram-and-gandham-chisel-pointed-and-needle-pointed-iron-calligraphy-styli"
        ]
    },
    {
        "id": "PAL-05",
        "name": "Inking Contrast Chemistry",
        "query": "Mai thadaval lampblack herbal extract and essential oil inking for high contrast incised glyphs",
        "expected": [
            "concept-mai-thadaval-lampblack-and-herbal-oil-infusion-for-high-contrast-incised-glyphs"
        ]
    },
    {
        "id": "PAL-06",
        "name": "Royal Scribes Guild",
        "query": "Kanakkar and ezhuthalar guild corporation of royal scribes epigraphers librarians olai nayagam",
        "expected": [
            "institution-kanakkar-and-ezhuthalar-guild-of-royal-scribes-and-scriptorium-librarians"
        ]
    },
    {
        "id": "PAL-07",
        "name": "Bookbinding Mechanics",
        "query": "Kattuthadi and sutharam hardwood binding boards corded spines and folio security teak",
        "expected": [
            "technology-kattuthadi-and-sutharam-teak-binding-boards-and-corded-spine-retention"
        ]
    },
    {
        "id": "PAL-08",
        "name": "Manuscript Scriptorium Haven",
        "query": "Suriyanarkoil ancient Chola manuscript scriptorium and astrological library haven delta",
        "expected": [
            "place-suriyanarkoil-ancient-chola-manuscript-and-scriptorium-haven"
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
    print("BENCHMARK: Ancient Tamil Palm-Leaf Manuscript Scribing, Iron Stylus Metallurgy & Herbal Preservatives")
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
