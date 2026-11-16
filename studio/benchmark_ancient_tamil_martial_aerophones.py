#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "AER-01",
        "query": "Curved sheet brass horn kombu conical bore acoustics and lip-reed resonance",
        "expected_slugs": [
            "concept-curved-brass-kombu-acoustic-horn-conical-bore-dynamics"
        ],
        "category": "Horn Acoustics"
    },
    {
        "id": "AER-02",
        "query": "Long straight brass trumpet thaarai high frequency directional overtone beaming",
        "expected_slugs": [
            "concept-straight-thaarai-herald-trumpet-high-register-overtone-physics"
        ],
        "category": "Trumpet Physics"
    },
    {
        "id": "AER-03",
        "query": "Right spiraled valampuri conch shell logarithmic chamber standing wave resonance",
        "expected_slugs": [
            "concept-valampuri-sangu-spiral-conch-shell-resonance-acoustics"
        ],
        "category": "Conch Bio-Acoustics"
    },
    {
        "id": "AER-04",
        "query": "Murasu kattil royal war drum coordination with aerophone tactical signaling codes",
        "expected_slugs": [
            "concept-murasu-kattil-war-drum-and-aerophone-battle-orchestration"
        ],
        "category": "Battle Orchestration"
    },
    {
        "id": "AER-05",
        "query": "Vellore Pallava hero-stone inscriptions granting land to martial war-horn casters",
        "expected_slugs": [
            "insc-vellore-pallava-war-horn-and-herald-charters"
        ],
        "category": "Military Epigraphy"
    },
    {
        "id": "AER-06",
        "query": "Kombu kollan master metalsmith brazing sheet-brass war horns in the Palar valley",
        "expected_slugs": [
            "char-vellore-master-horn-caster-kombu-kollan"
        ],
        "category": "Master Horn Casters"
    },
    {
        "id": "AER-07",
        "query": "Pandya royal herald trumpeter blowing high register thaarai signals from elephant back",
        "expected_slugs": [
            "char-madurai-royal-herald-trumpeter-thaarai-ooruvon"
        ],
        "category": "Royal Heralds"
    },
    {
        "id": "AER-08",
        "query": "Vellore ancient Palar valley martial brass horn foundry and military redoubt",
        "expected_slugs": [
            "place-vellore-ancient-martial-aerophone-haven"
        ],
        "category": "Foundry Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Martial Aerophones, Kombu & Thaarai Horns")
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
