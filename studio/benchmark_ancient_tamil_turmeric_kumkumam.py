#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Turmeric Rhizome Agronomy, Alkaline-Lime Kumkumam Chemistry & Auspicious Antiseptic Culture
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
        "id": "MNJ-01",
        "title": "Sangam & Bhakti Literary References to Pasu-Manjal",
        "query": "Pattinappalai Malaipadukadam Nedunalvadai Akananuru Tiruppavai pasu-manjal backyard gardens manjal-chanthu threshold festoons",
        "expected_slugs": [
            "text-sangam-and-bhakti-literature-on-pasu-manjal-turmeric-pastes-and-festive-thresholds"
        ]
    },
    {
        "id": "MNJ-02",
        "title": "Curcuma longa Virali & Kilangu Botany & Curcuminoids",
        "query": "Curcuma longa virali-manjal lateral fingers kilangu-manjal mother bulbs Curcuma aromatica diferuloylmethane curcumin keto-enol ar-turmerone",
        "expected_slugs": [
            "concept-curcuma-longa-virali-and-kilangu-botany-curcuminoid-tautomerism-and-turmerone"
        ]
    },
    {
        "id": "MNJ-03",
        "title": "Alkaline-Lime & Borax Bathochromic Chemistry of Kungumam",
        "query": "Alkaline slaked lime Ca(OH)2 borax vengaram alum phenolic deprotonation bathochromic shift 420 nm yellow to 530 nm crimson Kungumam Aarathi",
        "expected_slugs": [
            "concept-alkaline-lime-borax-deprotonation-chemistry-of-crimson-kungumam-transformation"
        ]
    },
    {
        "id": "MNJ-04",
        "title": "Auspicious Manjal Antiseptic Hygiene & Manjal-Kayiru",
        "query": "Nilai-padi wooden threshold turmeric wash ant termite repellent 9-strand cotton manjal-kayiru thaali cord transdermal antiseptic",
        "expected_slugs": [
            "concept-auspicious-manjal-antiseptic-hygiene-mangalsutra-cord-dyeing-and-aarathi-prophylaxis"
        ]
    },
    {
        "id": "MNJ-05",
        "title": "Manjal-Kopparai Alkaline Boiling & Rotary Drum Polishing",
        "query": "Manjal-kopparai perforated trough alkaline boiling starch gelatinization 15-day sun drying metallic snap hexagonal rotary drum polishing",
        "expected_slugs": [
            "technology-manjal-kopparai-alkaline-boiling-starch-gelatinization-and-rotary-polishing"
        ]
    },
    {
        "id": "MNJ-06",
        "title": "Thaazhampoo Kungumam Vat Steeping & Oil Conditioning",
        "query": "Thaazhampoo Pandanus Kungumam lemon juice borax alum shell-lime supernatant 20-day solar steeping gingelly oil stabilization",
        "expected_slugs": [
            "technology-thaazhampoo-kungumam-vat-steeping-sun-evaporation-and-sesame-oil-stabilization"
        ]
    },
    {
        "id": "MNJ-07",
        "title": "Erode Manjal-Mundi Guilds & Underground Manjal-Kuzhi Pits",
        "query": "Erode Manjal-Mundi fracture grading flask-shaped underground storage pit manjal-kuzhi paddy straw vengai leaf hermetic lining",
        "expected_slugs": [
            "institution-erode-manjal-mundi-commission-guilds-and-underground-manjal-kuzhi-granaries"
        ]
    },
    {
        "id": "MNJ-08",
        "title": "Erode Kongu Kaveri-Bhavani GI Turmeric Haven",
        "query": "Erode Manjal Maanagaram 11.3410 77.7170 Kaveri Bhavani Kalingarayan Canal Chinnavedanpatti GI turmeric curing trade haven",
        "expected_slugs": [
            "place-erode-ancient-kongu-manjal-turmeric-curing-and-trade-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Turmeric Rhizome Agronomy, Alkaline-Lime Kumkumam Chemistry & Auspicious Antiseptic Culture")
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
