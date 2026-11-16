#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "SIL-01",
        "query": "Kalithogai verses on public martial arenas spinning quarterstaffs and combatant dueling",
        "expected_slugs": [
            "text-kalithogai-martial-arena-combats-and-quarterstaff-dueling-poetry"
        ],
        "category": "Sangam Martial Verse"
    },
    {
        "id": "SIL-02",
        "query": "Hardened rock bamboo quarterstaff thermal oil seasoning and acoustic whistling silambak kambu",
        "expected_slugs": [
            "concept-hardened-pirambu-bamboo-quarterstaff-acoustics-silambak-kambu"
        ],
        "category": "Staff Metallurgy"
    },
    {
        "id": "SIL-03",
        "query": "Varma Kalai 108 vital nerve points padu-varmam strikes and adangal revival resuscitation",
        "expected_slugs": [
            "concept-varma-kalai-vital-nerve-point-striking-and-revival-traumatology"
        ],
        "category": "Varma Neuro-Traumatology"
    },
    {
        "id": "SIL-04",
        "query": "Flexible spring steel coiled whip sword urumi and chuttu vaal centrifugal ballistics",
        "expected_slugs": [
            "concept-flexible-spring-steel-coiled-whip-sword-urumi-and-chuttu-vaal"
        ],
        "category": "Whip-Sword Metallurgy"
    },
    {
        "id": "SIL-05",
        "query": "Martial footwork geometry kaalvari triangular and octagonal combat stances chuvadu",
        "expected_slugs": [
            "concept-martial-footwork-geometry-and-circular-combat-stances-kaalvari"
        ],
        "category": "Combat Footwork"
    },
    {
        "id": "SIL-06",
        "query": "Tenkasi Pandya inscriptions royal endowments for silamba koodam martial academies and asan pangu",
        "expected_slugs": [
            "insc-tenkasi-pandya-martial-academy-and-silambam-guild-charters"
        ],
        "category": "Martial Epigraphy"
    },
    {
        "id": "SIL-07",
        "query": "Virudhunagar Maravar warrior training halls tournament prize purses and arena charters",
        "expected_slugs": [
            "insc-virudhunagar-maravar-warrior-training-hall-and-arena-epigraphs"
        ],
        "category": "Arena Charters"
    },
    {
        "id": "SIL-08",
        "query": "Tenkasi ancient Pandya martial academy and Silambam quarterstaff haven Western Ghats",
        "expected_slugs": [
            "place-tenkasi-ancient-pandya-martial-academy-and-silambam-haven"
        ],
        "category": "Martial Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Silambam Martial Arts & Varma-Kalai")
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
