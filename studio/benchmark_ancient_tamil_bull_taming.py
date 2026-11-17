#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Bull-Taming Sports, Native Cattle Breeds and Mullai Pastoral Heritage
Generated automatically.
"""

import sys
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"

BENCHMARK_QUERIES = [
    {
        "id": "BUL-01",
        "title": "Mullaikkali Bridal Contest Poetics",
        "query": "How does the Mullaikkali section of Kalittokai stage marriage eligibility as a literary convention voiced by cowherd speakers in the kali metre?",
        "expected_slugs": [
            "text-mullaikkali-bridal-bull-contest-convention-and-ayar-cowherd-idiom"
        ]
    },
    {
        "id": "BUL-02",
        "title": "Indus Seal & Rock-Art Comparison",
        "query": "Why can the resemblance between Indus valley sealings, Minoan bull-leaping and South Indian rock paintings not be read as proven continuity?",
        "expected_slugs": [
            "concept-indus-seal-and-rock-art-bull-taming-scholarly-parallels"
        ]
    },
    {
        "id": "BUL-03",
        "title": "Delta & Hill-Forest Breed Morphology",
        "query": "Compare the short-legged hornless mottai madu of the Cauvery delta paddy fields with the brown and white trotting cattle of the Erode hill forests",
        "expected_slugs": [
            "concept-umblachery-and-bargur-native-breed-morphology-and-draught-aptitude"
        ]
    },
    {
        "id": "BUL-04",
        "title": "Korangadu Silvopasture Tenure",
        "query": "Enclosed dry pasture plots with Cenchrus grass sward, Acacia leucophloea shade and a living thorn hedge, let out seasonally for overnight penning manure",
        "expected_slugs": [
            "concept-korangadu-kaaval-grazing-commons-and-silvopasture-tenure"
        ]
    },
    {
        "id": "BUL-05",
        "title": "Release Chute & Ground Geometry",
        "query": "The narrow single-animal masonry gateway, holding pen, marked run, double barricading and exit lanes that shape flow through the arena ground",
        "expected_slugs": [
            "technology-vadivasal-arena-chute-and-kalam-enclosure-layout"
        ]
    },
    {
        "id": "BUL-06",
        "title": "Conditioning Regimen & Horn Dressing",
        "query": "Low impact stamina work by swimming a stud bull in village tanks, sand running, cottonseed and horse gram concentrate, sesame oil massage, hoof paring and filing the horns",
        "expected_slugs": [
            "technology-kaalai-conditioning-regimen-tank-swimming-and-horn-dressing"
        ]
    },
    {
        "id": "BUL-07",
        "title": "Cattle Gear: Ropes, Bells, Horn Caps",
        "query": "Fibre nose lines and tethers, cast bell metal neck bells for locating animals by ear in thorn pasture, brass horn caps and festival tassels",
        "expected_slugs": [
            "artifact-kayiru-halters-bell-metal-mani-collars-and-horn-brass-caps"
        ]
    },
    {
        "id": "BUL-08",
        "title": "Temple Bull & Herder Assembly",
        "query": "A bull dedicated to a shrine, never yoked or sold, serving as the village common breeding sire, and the pastoral community assembly that timed migrations and settled stray disputes",
        "expected_slugs": [
            "institution-kovil-kaalai-temple-bull-endowment-and-idaiyar-herder-assembly"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Bull-Taming Sports, Native Cattle Breeds and Mullai Pastoral Heritage")
    print(f"Model: {MODEL_NAME} | Dimension: 1024 | Total Queries: {len(BENCHMARK_QUERIES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_QUERIES)

    for item in BENCHMARK_QUERIES:
        qid = item["id"]
        qtitle = item["title"]
        query = item["query"]
        expected = item["expected_slugs"]

        q_emb = get_embedding(query)
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
        """, (q_emb, q_emb))
        results = cur.fetchall()

        top1_slug, top1_sim = results[0]
        if top1_slug in expected:
            passed += 1
            print(f"[PASS] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for s, sim in results:
                print(f"    - {s} ({sim:.4f})")

    cur.close()
    conn.close()

    print("=" * 80)
    print(f"SUMMARY: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print("=" * 80)
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
