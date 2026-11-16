#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "LIT-01",
        "query": "Malaipadukadam mountain rock acoustics echoes and sonorous ringing stones in Naviram hills",
        "expected_slugs": [
            "text-malaipadukadam-resonant-mountain-rock-acoustics-poetry"
        ],
        "category": "Mountain Acoustics"
    },
    {
        "id": "LIT-02",
        "query": "Kudumiyanmalai rock-cut musical inscription of Mahendravarman parivadini lute swaras",
        "expected_slugs": [
            "insc-kudumiyanmalai-pallava-musical-epigraphs-and-acoustic-charters"
        ],
        "category": "Musical Inscriptions"
    },
    {
        "id": "LIT-03",
        "query": "Sonorous ringing rocks dolerite dykes natural granitic lithophones isai-kal cupules",
        "expected_slugs": [
            "concept-sonorous-granite-ringing-rocks-and-lithophone-percussion-isai-kal"
        ],
        "category": "Lithophone Physics"
    },
    {
        "id": "LIT-04",
        "query": "Prehistoric drilled avian bone flutes knuckle-span finger-holes animal lure whistles",
        "expected_slugs": [
            "concept-prehistoric-drilled-avian-bone-flutes-and-animal-whistles"
        ],
        "category": "Bone Aerophones"
    },
    {
        "id": "LIT-05",
        "query": "Rock-cut cavern acoustic modes helmholtz cavity resonance low frequency vocal chanting",
        "expected_slugs": [
            "concept-granite-cavern-acoustic-modes-and-helmholtz-resonance-kudaivarai"
        ],
        "category": "Cavern Helmholtz Resonance"
    },
    {
        "id": "LIT-06",
        "query": "Megalithic cairn circle circular soundscapes funerary mourning drumming and port-hole waveguides",
        "expected_slugs": [
            "concept-megalithic-cairn-circle-soundscapes-and-funerary-acoustics"
        ],
        "category": "Funerary Archaeoacoustics"
    },
    {
        "id": "LIT-07",
        "query": "Master stone sculptor tuning granite pillars to musical swara pitches at Kudumiyanmalai",
        "expected_slugs": [
            "char-kudumiyanmalai-master-lithophone-sculptor-isai-kal-thatchan"
        ],
        "category": "Musical Stone Sculptors"
    },
    {
        "id": "LIT-08",
        "query": "Narthamalai ancient granite hills resonant ringing rocks and cavern sanctuary haven",
        "expected_slugs": [
            "place-narthamalai-ancient-sonorous-rock-and-cavern-haven"
        ],
        "category": "Sonorous Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Lithophones, Ringing Rocks & Cavern Acoustics")
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
