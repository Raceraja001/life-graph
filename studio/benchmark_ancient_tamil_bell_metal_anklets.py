#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "BEL-01",
        "query": "Silappathikaram verses on Kannagi ruby filled hollow anklet and resonant bell metal gongs",
        "expected_slugs": [
            "text-silappathikaram-resonant-pearl-filled-anklet-and-gong-poetry"
        ],
        "category": "Literature & Epics"
    },
    {
        "id": "BEL-02",
        "query": "Seventy eight twenty two high tin bell bronze metallurgy and martensitic oil quenching",
        "expected_slugs": [
            "concept-seventy-eight-twenty-two-high-tin-bell-bronze-metallurgy"
        ],
        "category": "Alloy Metallurgy"
    },
    {
        "id": "BEL-03",
        "query": "Lost wax crotal bell casting Salangai with internal rattling sphere core breakout",
        "expected_slugs": [
            "concept-lost-wax-crotal-bell-casting-and-internal-rattling-sphere-cores"
        ],
        "category": "Crotal Bell Casting"
    },
    {
        "id": "BEL-04",
        "query": "Acoustic resonance and harmonic overtones in cast temple gongs Semakkalam turning",
        "expected_slugs": [
            "concept-acoustic-resonance-and-harmonic-overtones-in-cast-temple-gongs"
        ],
        "category": "Gong Acoustics"
    },
    {
        "id": "BEL-05",
        "query": "Hollow chased gold anklet Silambu gem insertion and blowpipe hard soldering",
        "expected_slugs": [
            "concept-hollow-chased-anklet-silambu-gem-insertion-and-soldering"
        ],
        "category": "Anklet Goldsmithing"
    },
    {
        "id": "BEL-06",
        "query": "Nachiarkoil Chola bell metal foundry guild charters and tin ingot quotas",
        "expected_slugs": [
            "insc-nachiarkoil-chola-bell-metal-foundry-guild-charters"
        ],
        "category": "Foundry Epigraphy"
    },
    {
        "id": "BEL-07",
        "query": "Master bell founder Mani Kollan tuning high-tin bronze gongs at Nachiarkoil",
        "expected_slugs": [
            "char-nachiarkoil-master-bell-founder-mani-kollan"
        ],
        "category": "Master Founders"
    },
    {
        "id": "BEL-08",
        "query": "Nachiarkoil ancient resonant bell metal lamp and alluvial clay foundry haven",
        "expected_slugs": [
            "place-nachiarkoil-ancient-resonant-bell-metal-haven"
        ],
        "category": "Foundry Haven Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Bell Metal & Anklet Metallurgy")
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
