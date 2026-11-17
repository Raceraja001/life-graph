#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Stick-Lac & Shellac Resin Harvesting, Kerria Lacca Host Ecology, Wax-Sealing & Turned Wood Lacquerware
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
        "id": "LAC-01",
        "title": "Silappadikaram, Kalittokai & Chola Lac Accounts",
        "query": "Silappadikaram Kalittokai cevv arakku alathagam sempanju crimson foot dye Chola arakku muddirai royal seal",
        "expected_slugs": [
            "text-silappadikaram-kalittokai-and-chola-charters-on-cevv-arakku-lac-and-seals"
        ]
    },
    {
        "id": "LAC-02",
        "title": "Kerria lacca Entomology & Polyester Resin Chemistry",
        "query": "Kerria lacca scale insect Schleichera oleosa puvam Butea monosperma aleuritic acid shellolic acid laccaic acid",
        "expected_slugs": [
            "concept-kerria-lacca-entomology-puvam-host-ecology-and-aleuritic-shellolic-polyester-chemistry"
        ]
    },
    {
        "id": "LAC-03",
        "title": "Stone-Vat Dye Washing & Cloth-Tube Shellac Melting",
        "query": "Kombarakku stone vat treading arakku neer crimson dye extraction mani arakku seedlac twisted cotton sausage bag shellac melting",
        "expected_slugs": [
            "technology-kombarakku-twig-scraping-stone-vat-laccaic-dye-washing-and-cloth-bag-shellac-melting"
        ]
    },
    {
        "id": "LAC-04",
        "title": "Kadaisal-Arakku Friction Melting & Veppalai Tribology",
        "query": "Kadaisal arakku dry friction heat flash melting 85 degrees Wrightia tinctoria veppalai wood taazhai screw pine leaf burnishing",
        "expected_slugs": [
            "concept-kadaisal-arakku-friction-heat-plastification-and-veppalai-wood-turnery-tribology"
        ]
    },
    {
        "id": "LAC-05",
        "title": "Mineral Pigmented Arakku-Kuchi & Multi-Layer Sgraffito",
        "query": "Kneading pigmented arakku kuchi sticks saadhilingam vermilion aritharam orpiment bow lathe multi layer sgraffito",
        "expected_slugs": [
            "technology-bow-lathe-veppalai-turning-mineral-pigmented-lac-stick-application-and-taazhai-buffing"
        ]
    },
    {
        "id": "LAC-06",
        "title": "Arakku-Mettuthal Goldsmith Pitch & Kemp Gem-Setting",
        "query": "Arakku mettuthal pattarai arakku goldsmith chasing pitch shellac brick dust hollow gold thali repousse Kemp cabochon setting",
        "expected_slugs": [
            "concept-arakku-mettuthal-goldsmith-chasing-pitch-and-royal-arakku-muddirai-sigillography"
        ]
    },
    {
        "id": "LAC-07",
        "title": "Lacquered Anjaraipetti Spice Towers & Choppu-Samaan Toys",
        "query": "Lacquered veppalai wood tiered maravai anjaraipetti spice box bridal kumkumam chimizh choppu samaan miniature kitchen toys",
        "expected_slugs": [
            "artifact-lacquered-veppalai-anjaraipetti-spice-boxes-marapachi-wooden-toys-and-choppu-ware"
        ]
    },
    {
        "id": "LAC-08",
        "title": "Cumbum Suruli Forest Kombarakku Lac & Turnery Haven",
        "query": "Cumbum Kambam Suruli Vannathiparai forest Theni Schleichera oleosa kumbadiri kombarakku lac turnery haven 9.7360 77.2840",
        "expected_slugs": [
            "place-cumbum-ancient-suruli-forest-kombarakku-lac-and-turnery-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Stick-Lac & Shellac Resin Harvesting, Kerria Lacca Host Ecology, Wax-Sealing & Turned Wood Lacquerware")
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
