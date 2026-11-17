#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Bullock Cart Wheelwright Engineering, Shrink-Fit Iron Tyre Pyrotechnics, Axle Joinery & Peru-Vazhi Logistics
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
        "id": "CRT-01",
        "title": "Tirukkural on Saagadam Overload, Achaani & Umanar Carts",
        "query": "Tirukkural Peelipei Saagadamum Achirum Urulperuntherkku Achaani linchpin Perumpanarruppadai Umanar salt merchant cart",
        "expected_slugs": [
            "text-tirukkural-and-sangam-accounts-of-saagadam-achaani-and-umanar-salt-carts"
        ]
    },
    {
        "id": "CRT-02",
        "title": "Large-Diameter Wheel Terramechanics & Dished Spokes",
        "query": "Kattai vandi chakkaram large diameter wheel Bekker terramechanics sinkage rolling resistance dished spokes karuvelam vengai",
        "expected_slugs": [
            "concept-large-diameter-spoked-wheel-rolling-resistance-and-dished-spoke-mechanics"
        ]
    },
    {
        "id": "CRT-03",
        "title": "Thermal Shrink-Fit Iron Tyre & Hoop Stress Physics",
        "query": "Irumbu pattai wrought iron tyre thermal expansion interference shrink fit circumferential hoop tension radial spoke compression",
        "expected_slugs": [
            "concept-thermal-shrink-fit-iron-tyre-hoop-stress-and-radial-pre-compression"
        ]
    },
    {
        "id": "CRT-04",
        "title": "Single-Axle Load Balance (Eruthu-Kattu) & Yoke Ergonomics",
        "query": "Two wheeled bullock cart center of gravity eruthu kattu forward torque nukathadi neck yoke zebu hump thimilu throat choking",
        "expected_slugs": [
            "concept-two-wheeled-cart-center-of-gravity-balance-and-nukathadi-yoke-biomechanics"
        ]
    },
    {
        "id": "CRT-05",
        "title": "Kudam Hub Lathe-Turning & Vattai Felloe Joinery",
        "query": "Thatchar wheelwright rope lathe turned karuvelam kudam hub twelve staggered mortises aarakkaal spokes curved vattai felloes",
        "expected_slugs": [
            "technology-kudam-hub-turning-twelve-spoke-mortising-and-vattai-felloe-doweling"
        ]
    },
    {
        "id": "CRT-06",
        "title": "Pattai-Kuzhi Trench Firing & Alavu-Chakkaram Gauging",
        "query": "Alavu chakkaram iron traveller wheel circumference pattai kuzhi circular cow dung trench furnace red hot tyre water quenching",
        "expected_slugs": [
            "technology-pattai-kuzhi-circular-fire-trench-tyre-heating-and-rapid-water-quenching"
        ]
    },
    {
        "id": "CRT-07",
        "title": "Achu Axles, Kandennai Grease Pots & Thaangi-Kattai Props",
        "query": "Forged square iron achu axle achaani linchpin kandennai kinnam coconut shell castor tar grease pot thaangi kattai drop prop",
        "expected_slugs": [
            "artifact-achu-axle-achaani-linchpin-kandennai-grease-pot-and-mutti-katta-brake-props"
        ]
    },
    {
        "id": "CRT-08",
        "title": "Virudhunagar Pandya Peru-Vazhi Cart & Wheelwright Haven",
        "query": "Virudhunagar Virudupatti Pandya Peru Vazhi mullai karisal Vandi Pettai caravan depot karuvelam wheelwright pattarai haven",
        "expected_slugs": [
            "place-virudhunagar-ancient-pandya-peru-vazhi-bullock-cart-and-wheelwright-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Bullock Cart Wheelwright Engineering, Shrink-Fit Iron Tyre Pyrotechnics, Axle Joinery & Peru-Vazhi Logistics")
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
