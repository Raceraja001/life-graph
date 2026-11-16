#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "DRM-01",
        "category": "Sangam Drum Verse",
        "query": "Purananuru 50 classical Sangam verses on consecrated royal war drums and sacred murasu couches Mosikeeranar",
        "expected_slugs": [
            "text-purananuru-50-verses-on-consecrated-war-drums-and-sacred-murasu-couches"
        ]
    },
    {
        "id": "DRM-02",
        "category": "War Drum Acoustics",
        "query": "Veera murasu martial acoustic warfare and low frequency resonant sonic projection 30 to 60 Hz",
        "expected_slugs": [
            "concept-veera-murasu-martial-acoustic-warfare-and-low-frequency-resonance"
        ]
    },
    {
        "id": "DRM-03",
        "category": "Leather Thong Bracing",
        "query": "Var pinithal twisted bull hide leather thong radial bracing and membrane tensioning mechanics 15 kN",
        "expected_slugs": [
            "technology-var-pinithal-twisted-leather-thong-radial-tensioning-mechanics"
        ]
    },
    {
        "id": "DRM-04",
        "category": "Acoustic Tuning Paste",
        "query": "Murasu marunthu iron oxide rice paste acoustic center loading and pitch tuning sorrow damping",
        "expected_slugs": [
            "artifact-murasu-marunthu-iron-oxide-and-cooked-rice-acoustic-tuning-paste"
        ]
    },
    {
        "id": "DRM-05",
        "category": "Infantry Signaling Drums",
        "query": "Thannumai and thudi infantry rhythm signaling and hourglass wooden battlefield drums Maravar",
        "expected_slugs": [
            "technology-thannumai-and-thudi-infantry-rhythm-signaling-and-hourglass-resonators"
        ]
    },
    {
        "id": "DRM-06",
        "category": "Military Drummer Guilds",
        "query": "Murasu kottuvar guild hereditary military drummers heralds and state temple honors murasu kaani",
        "expected_slugs": [
            "institution-murasu-kottuvar-guild-hereditary-military-drummers-and-heralds"
        ]
    },
    {
        "id": "DRM-07",
        "category": "Resonator Cauldron Shells",
        "query": "Murasu kattu hollowed Vengai heartwood cauldron resonator shells and acoustic acoustics 200 liters",
        "expected_slugs": [
            "artifact-murasu-kattu-hollowed-vengai-heartwood-cauldron-resonator-shells"
        ]
    },
    {
        "id": "DRM-08",
        "category": "Martial Drum Topography",
        "query": "Alangudi ancient Pudukkottai martial drum haven heroic memorials and percussion craftsmen",
        "expected_slugs": [
            "place-alangudi-ancient-pudukkottai-martial-drum-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Military Drum Acoustics, Membrane Tensioning & War Resonators")
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
