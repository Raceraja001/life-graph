#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Bowyer Craft, Bamboo-Sinew Archery Mechanics, Arrowsmithing & Valvil Ori Kurinji Tradition
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
        "id": "ARC-01",
        "title": "Purananuru 152 on Valvil Ori's Five-Beast Arrow",
        "query": "Purananuru 152 Vanparanar Sirupanarruppadai Valvil Ori single pagazhi arrow elephant tiger deer boar monitor lizard Chera Vil Kodi",
        "expected_slugs": [
            "text-purananuru-and-sirupanarruppadai-on-valvil-ori-and-chera-vil-kodi-archery"
        ]
    },
    {
        "id": "ARC-02",
        "title": "Kal-Moongil Bamboo Flexural Strain-Energy & Tillering",
        "query": "Dendrocalamus strictus kal moongil vengai kodun cil bow stave outer silica tensile belly compression parabolic limb tillering",
        "expected_slugs": [
            "concept-kal-moongil-bamboo-flexural-strain-energy-and-kodun-cil-stave-mechanics"
        ]
    },
    {
        "id": "ARC-03",
        "title": "Pagazhi Dynamic Spine & Helical Eagle Fletching",
        "query": "Pagazhi kanai arrow dynamic flexural spine archer paradox front of center balance three vane helical eagle feather oozhi spin",
        "expected_slugs": [
            "concept-pagazhi-arrow-spine-paradox-and-helical-feather-fletching-aerodynamics"
        ]
    },
    {
        "id": "ARC-04",
        "title": "Thumb-Draw Kinematics & Sabda-Vedhi Acoustic Ranging",
        "query": "Full draw earlobe anchor dorsal back tension release oasai arithal sabda vedhi binaural acoustic target ranging forest canopy",
        "expected_slugs": [
            "concept-sabda-vedhi-acoustic-target-ranging-and-thumb-draw-release-kinematics"
        ]
    },
    {
        "id": "ARC-05",
        "title": "Smoke-Seasoned Staves & Marul Hemp-Sinew Bowstrings",
        "query": "Smoke loft seasoned bamboo castor oil charcoal heat tempering Sansevieria roxburghiana marul hemp deer sinew vil naan bowstring",
        "expected_slugs": [
            "technology-bamboo-stave-heat-tillering-and-marul-hemp-sinew-bowstring-twisting"
        ]
    },
    {
        "id": "ARC-06",
        "title": "Wootz Arrowhead Forging & Steatite Shaft Straightening",
        "query": "Kollan azhal mugam forged Wootz steel arrowhead ardhachandra crescent bodkin grooved steatite nanal reed straightening arakku lac",
        "expected_slugs": [
            "technology-wootz-arrowhead-forging-charcoal-shaft-straightening-and-fletching"
        ]
    },
    {
        "id": "ARC-07",
        "title": "Kurinji Unda-Vil Double-Stringed Pellet-Bows",
        "query": "Unda vil undai vil double stringed bamboo pellet bow wooden spacer block baked clay balls mann undai thinai punam millet parrots",
        "expected_slugs": [
            "artifact-kurinji-unda-vil-double-stringed-pellet-bows-and-clay-sling-bullets"
        ]
    },
    {
        "id": "ARC-08",
        "title": "Kolli Hills (Kollimalai) Valvil Ori Archery Haven",
        "query": "Kolli Hills Kollimalai Namakkal Eastern Ghats Agaya Gangai Arapaleeswarar Valvil Ori kurinji bamboo bowyer archery haven",
        "expected_slugs": [
            "place-kolli-hills-valvil-ori-ancient-kurinji-archery-and-bowyer-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Bowyer Craft, Bamboo-Sinew Archery Mechanics, Arrowsmithing & Valvil Ori Kurinji Tradition")
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
