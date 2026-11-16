#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "DRU-01",
        "query": "Purananuru verses on sacred war drum couch Murasu Kattil and Mosikiranar royal reverence",
        "expected_slugs": [
            "text-purananuru-royal-war-drum-bed-and-murasu-reverence-poetry"
        ],
        "category": "Literature & Martial Reverence"
    },
    {
        "id": "DRU-02",
        "query": "Resonant jackfruit wood barrel hollowing and parabolic acoustic sound chamber mechanics",
        "expected_slugs": [
            "concept-resonant-jackfruit-wood-barrel-hollowing-and-acoustic-chambers"
        ],
        "category": "Woodworking Mechanics"
    },
    {
        "id": "DRU-03",
        "query": "Cured bullock hide tanning Acacia tannins and twisted leather thong tensioning mechanics",
        "expected_slugs": [
            "concept-cured-bullock-hide-tanning-and-twisted-leather-thong-tensioning"
        ],
        "category": "Membrane Tanning"
    },
    {
        "id": "DRU-04",
        "query": "Black mineral paste tuning slug Maru Karun Chanthu on drumhead for harmonic overtones",
        "expected_slugs": [
            "concept-black-mineral-paste-tuning-slug-acoustics-maru-on-drumhead"
        ],
        "category": "Acoustic Tuning Slugs"
    },
    {
        "id": "DRU-05",
        "query": "Military drum low frequency acoustic wave propagation and battlefield tactical signal codes",
        "expected_slugs": [
            "concept-military-drum-acoustic-wave-propagation-and-battlefield-signals"
        ],
        "category": "Battlefield Communications"
    },
    {
        "id": "DRU-06",
        "query": "Thakadoor Athiyaman royal war drum epigraphs hero stones and Murasu Kaani charters",
        "expected_slugs": [
            "insc-thakadoor-athiyaman-war-drum-and-arsenal-epigraphs"
        ],
        "category": "Arsenal Epigraphy"
    },
    {
        "id": "DRU-07",
        "query": "Master war drum artisan Murasu Seivon Kollan assembling thunderous drums at Thakadoor",
        "expected_slugs": [
            "char-thakadoor-master-war-drum-artisan-murasu-seivon-kollan"
        ],
        "category": "Master Artisans"
    },
    {
        "id": "DRU-08",
        "query": "Thakadoor ancient royal war drum arsenal and Athiyaman military citadel haven",
        "expected_slugs": [
            "place-thakadoor-ancient-royal-war-drum-and-arsenal-haven"
        ],
        "category": "Military Citadel Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil War Drum Membranophones & Acoustics")
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
