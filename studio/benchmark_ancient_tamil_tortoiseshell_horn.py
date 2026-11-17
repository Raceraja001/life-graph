#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Tortoiseshell, Horn & Mother-of-Pearl Inlay Craft, Comb Sawing & Coastal Lapidary
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
        "id": "TRT-01",
        "title": "Periplus & Sangam Tortoiseshell & Comb Accounts",
        "query": "Periplus Maris Erythraei chelone Akananuru Kalittokai Porunararruppadai aamai odu seeppu eervali combs",
        "expected_slugs": [
            "text-periplus-and-sangam-corpus-on-aamai-odu-tortoiseshell-and-seeppu-combs"
        ]
    },
    {
        "id": "TRT-02",
        "title": "Thermoplastic Keratin Softening & Glue-Free Thermal Welding",
        "query": "Thermoplastic keratin polymer disulfide bonds softening 110 to 130 degrees Celsius autogenous glue free thermal welding",
        "expected_slugs": [
            "concept-thermoplastic-keratin-polymer-softening-and-autogenous-thermal-scute-welding"
        ]
    },
    {
        "id": "TRT-03",
        "title": "Anti-Static Keratin Tribology & Eervali Nit-Comb Biomechanics",
        "query": "Anti static keratin triboelectric potential scalp sebum distribution eervali sub millimetre nit lice comb biomechanics",
        "expected_slugs": [
            "concept-anti-static-keratin-hair-tribology-and-eervali-fine-tooth-comb-biomechanics"
        ]
    },
    {
        "id": "TRT-04",
        "title": "Horn Slitting, Sesame-Oil Roasting & Wedge-Press Flattening",
        "query": "Hollow buffalo horn longitudinal slitting sesame oil charcoal roasting hardwood wedge press maram achu flattening",
        "expected_slugs": [
            "technology-horn-and-scute-steam-flattening-iron-clamp-pressing-and-thermal-lamination"
        ]
    },
    {
        "id": "TRT-05",
        "title": "Karukku-Vaal Comb Tooth Sawing & Kudirai Foot-Vice",
        "query": "Kudirai wooden foot vice stiff backed karukku vaal steel pull saw 40 teeth per inch eervali sawing",
        "expected_slugs": [
            "technology-eervali-double-edged-comb-tooth-sawing-and-muthu-chippi-fretwork-inlay"
        ]
    },
    {
        "id": "TRT-06",
        "title": "Eervali Combs, Podimattai Snuff-Boxes & Mai-Kudam Vials",
        "query": "Double edged eervali pallari comb bow lathe turned airtight podimattai horn snuff box mai kudam collyrium pot",
        "expected_slugs": [
            "artifact-eervali-pallari-keratin-grooming-combs-podimattai-snuff-boxes-and-mai-kudam"
        ]
    },
    {
        "id": "TRT-07",
        "title": "Pinctada Nacre Iridescence & Ethical Buffalo-Horn Substitution",
        "query": "Pinctada fucata aragonite platelets thin film iridescence ethical substitution marine turtle scutes buffalo horn coconut shell",
        "expected_slugs": [
            "concept-pinctada-nacre-aragonite-iridescence-and-ethical-buffalo-horn-substitution"
        ]
    },
    {
        "id": "TRT-08",
        "title": "Kilakarai Gulf of Mannar Shell & Horn Craft Haven",
        "query": "Kilakarai Ramanathapuram Gulf of Mannar 21 coral islands Appa Tivu mother of pearl horn comb haven 9.2320 78.7840",
        "expected_slugs": [
            "place-kilakarai-ancient-gulf-of-mannar-tortoiseshell-and-horn-craft-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Tortoiseshell, Horn & Mother-of-Pearl Inlay Craft, Comb Sawing & Coastal Lapidary")
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
