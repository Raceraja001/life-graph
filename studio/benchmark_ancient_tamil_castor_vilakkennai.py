#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Amanakku Castor & Vilakkennai
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
        "id": "AMN-01",
        "title": "Mansatti Roasting & Boiling-Water Float Skimming of Castor Oil",
        "query": "Which household technique roasted castor seeds in an unglazed mansatti over cow-dung cakes, pounded them in a granite ural, then boiled the mash in water so the oil floated by Stokes' law and was skimmed with a coconut-shell ladle?",
        "expected_slugs": [
            "technology-amanakku-seed-dehulling-earthen-pot-roasting-and-hot-water-float-rendering"
        ]
    },
    {
        "id": "AMN-02",
        "title": "Ther Journal Lubrication in the Boundary Regime & Castor Purge",
        "query": "How did ther carpenters jack the temple chariot and pour warm castor oil onto the hardwood axle journal and hub bore for the slow therottam procession, and how was a measured vilakkennai purge given with ginger or milk?",
        "expected_slugs": [
            "technology-temple-chariot-wooden-axle-vilakkennai-lubrication-and-pediatric-purgative-dosing"
        ]
    },
    {
        "id": "AMN-03",
        "title": "Nazhi-Uzhakku-Aazhakku Measures & Palmyra Leaf Cone Funnels",
        "query": "What objects included graduated terracotta and brass aazhakku, uzhakku and nazhi oil measures, long-necked ennai kudam pots, and folded palmyra-leaf cone funnels for pouring lamp oil into agal wells, along with the string test for oil grade?",
        "expected_slugs": [
            "artifact-cold-drawn-and-rendered-vilakkennai-terracotta-oil-measures-and-palmyra-funnels"
        ]
    },
    {
        "id": "AMN-04",
        "title": "Ricin-Bearing Pinnakku Manure & Hardwood Hub Greasing Paddle",
        "query": "Which castor press cake is forbidden as cattle feed because of ricin yet composted into betel-vine kodikkal gardens as a nematicidal nitrogen manure, and what spoon-bladed hardwood paddle packed grease into chariot hub bores?",
        "expected_slugs": [
            "artifact-castor-seed-pinnakku-fertilizer-and-massive-temple-axle-greasing-paddles"
        ]
    },
    {
        "id": "AMN-05",
        "title": "12-Hydroxy C18 Chain Hydrogen Bonding & Stribeck Curve",
        "query": "Explain how the C12 hydroxyl group of 12-hydroxy-cis-9-octadecenoic acid creates hydrogen bonding, a hydroxyl value near 165 mg KOH/g, viscosity near 900 mPa.s, and boundary-film adsorption on the Stribeck curve and Sommerfeld number.",
        "expected_slugs": [
            "concept-ricinoleic-acid-monounsaturated-hydroxy-fatty-acid-viscosity-and-lubrication-mechanics"
        ]
    },
    {
        "id": "AMN-06",
        "title": "EP3 Knockout Mice, Gαi Signalling & Lipoid Pneumonia Risk",
        "query": "Which concept covers Tunaru 2012 showing EP3 knockout mice resist castor oil diarrhoea, Gαi-coupled prostaglandin E2 receptor signalling in intestinal and uterine myometrium, and lipoid pneumonia aspiration risk in infants?",
        "expected_slugs": [
            "concept-smooth-muscle-ep3-prostanoid-receptor-activation-and-pediatric-laxative-safety"
        ]
    },
    {
        "id": "AMN-07",
        "title": "Lucas-Washburn Wick Capillarity, Incandescent Soot & Kulirchi Eyelid Oil",
        "query": "Why does lamp oil with a 229 C flash point wick slowly by Lucas-Washburn capillarity through cotton thiri, burn with little escaping soot thanks to its oxygen content, and soothe tired eyes as a cooling kulirchi eyelid application?",
        "expected_slugs": [
            "concept-vilakkennai-low-smoke-high-flashpoint-wick-luminescence-and-eye-cooling-physiology"
        ]
    },
    {
        "id": "AMN-08",
        "title": "Tagadur Capital of Adhiyaman Neduman Anji & Red-Soil Castor Uplands",
        "query": "Which place, the ancient Tagadur capital of Adhiyaman Neduman Anji praised by Avvaiyar for the gooseberry gift, lies on semi-arid granite red-soil uplands that grow rainfed castor with Krishnagiri and Salem?",
        "expected_slugs": [
            "place-dharmapuri-ancient-adhigaman-amanakku-castor-and-vilakkennai-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Amanakku Castor & Vilakkennai")
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
        rows = cur.fetchall()

        matched = False
        top_match = rows[0][0] if rows else "NONE"
        top_sim = rows[0][1] if rows else 0.0

        for rank, (r_slug, r_sim) in enumerate(rows):
            if r_slug in expected:
                matched = True
                status = "PASS" if rank == 0 else f"RANK-{rank+1}"
                print(f"[{qid}] {status} | Top: {top_match} ({top_sim:.4f}) | Expected: {expected}")
                if rank == 0:
                    passed += 1
                break
        if not matched:
            print(f"[{qid}] FAIL | Top: {top_match} ({top_sim:.4f}) | Expected: {expected}")

    print("=" * 80)
    acc = (passed / total) * 100
    print(f"Results: {passed}/{total} passed Top-1 ({acc:.1f}%)")
    print("=" * 80)
    if acc < 100.0:
        sys.exit(1)

if __name__ == "__main__":
    main()
