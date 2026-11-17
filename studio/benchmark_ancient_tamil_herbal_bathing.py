#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Herbal Saponin Cleansers, Ennai-Kuzhial Oil-Bath Thermoregulation & Temple Thirumanjanam Aromatics
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
        "id": "SNM-01",
        "title": "Paripadal, Silappadikaram & Tiruppavai Bathing Poetics",
        "query": "Paripadal Silappadikaram Tiruppavai Kurinjippattu Vaigai Kaveri neeradal aimpal-koonthal pathu-thuvar herbal hair washing verses",
        "expected_slugs": [
            "text-paripadal-silappadikaram-and-tiruppavai-on-aromatic-hair-washing-and-river-bathing"
        ]
    },
    {
        "id": "SNM-02",
        "title": "Seekakai, Arappu & Manipungan Triterpenoid Saponin Chemistry",
        "query": "Acacia concinna seekakai Albizia amara usilai arappu Sapindus emarginatus manipungan triterpenoid saponin micelles acidic pH 4.5 to 5.5",
        "expected_slugs": [
            "concept-seekakai-arappu-and-manipungan-triterpenoid-saponin-micelle-emulsification"
        ]
    },
    {
        "id": "SNM-03",
        "title": "Siddha Ennai-Kuzhial Oil-Bath Pitta Thermoregulation",
        "query": "Siddha Ennai-Kuzhial Wednesday Saturday head oil bath Sesamum indicum pitta thermoregulation cutaneous vasodilation sesamin sesamolin",
        "expected_slugs": [
            "concept-siddha-ennai-kuzhial-gingelly-oil-bath-pitta-thermoregulation-and-vagus-toning"
        ]
    },
    {
        "id": "SNM-04",
        "title": "Nalangu-Maa & Thirumanjana-Podi Rhizome Phytochemistry",
        "query": "Nalangu-maa Thirumanjana-podi Curcuma aromatica kasturi-manjal Curcuma zedoaria poolankizhangu germacrone green gram icon degreasing",
        "expected_slugs": [
            "concept-nalangu-maa-and-thirumanjana-podi-antimicrobial-phytochemistry-and-icon-de-greasing"
        ]
    },
    {
        "id": "SNM-05",
        "title": "Kaaychiya Ennai Mezhugu-Patham Boiling & 21-Herb Milling",
        "query": "Kaaychiya ennai pepper cumin garlic karisalanganni ponnanganni anhydrous mezhugu-patham boiling 21-ingredient seekakai stone milling",
        "expected_slugs": [
            "technology-kuzhambu-ennai-decoction-boiling-and-21-herb-seekakai-arappu-milling"
        ]
    },
    {
        "id": "SNM-06",
        "title": "Akil-Sambirani Wicker-Cone Hair Fumigation",
        "query": "Koonthal-pugaiyoothuthal inverted bamboo wicker cone pugai-koodai Aquilaria agallocha akil Styrax benzoin sambirani hair fumigation",
        "expected_slugs": [
            "technology-akil-sambirani-hair-fumigation-and-temple-thirumanjanam-abhishekam-compounding"
        ]
    },
    {
        "id": "SNM-07",
        "title": "Ennai-Kinnam Bowls, Manjal-Kallu & Vetiver Scrubbers",
        "query": "Bell-metal brass ennai-kinnam oil cup circular sandstone manjal-kallu rubbing stone vetiver peerkangai-naar loofah scrubbers",
        "expected_slugs": [
            "artifact-ennai-kinnam-oil-bowls-perforated-koonthal-pugai-koodai-and-vetiver-scrubbers"
        ]
    },
    {
        "id": "SNM-08",
        "title": "Srirangam Kaveri Island Thirumanjanam & Snana Haven",
        "query": "Srirangam Thiruvarangam Kaveri Kollidam island 10.8620 78.6900 Amma Mandapam elephant Thirumanjanam Jyeshtabhishekam thailakappu haven",
        "expected_slugs": [
            "place-srirangam-ancient-kaveri-thirumanjanam-aromatics-and-herbal-snana-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Herbal Saponin Cleansers, Ennai-Kuzhial Oil-Bath Thermoregulation & Temple Thirumanjanam Aromatics")
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
