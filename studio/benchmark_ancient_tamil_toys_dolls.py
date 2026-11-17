#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Terracotta & Wooden Toys, Thalaiyatti Counterweight Dolls & Childhood Pedagogy
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
        "id": "TOY-01",
        "title": "Sangam & Bhakti Literary References to Siru-Ther Toy Carts",
        "query": "Kalittokai Akananuru Periazhwar Tirumozhi siru-ther miniature toy chariots puthalvar uruttum vandal-pavai literary references",
        "expected_slugs": [
            "text-sangam-and-bhakti-literature-on-siru-ther-toy-carts-and-childhood-playthings"
        ]
    },
    {
        "id": "TOY-02",
        "title": "Thalaiyatti Bommai Roly-Poly Center-of-Mass Physics",
        "query": "Thanjavur Thalaiyatti Bommai weighted hemispherical base center of mass restoring gravitational torque gimbal wire nodding dancer doll",
        "expected_slugs": [
            "concept-thalaiyatti-bommai-weighted-hemisphere-center-of-mass-and-gimbal-oscillation"
        ]
    },
    {
        "id": "TOY-03",
        "title": "Sen-Chandana Marappachi Red Sandalwood Teething Dolls",
        "query": "Pterocarpus santalinus red sandalwood sen-chandana Marappachi wedding dolls infant teething santalin gum relief Navaratri Golu tiers",
        "expected_slugs": [
            "concept-sen-chandana-marappachi-medicinal-teething-dolls-and-navaratri-golu-pedagogy"
        ]
    },
    {
        "id": "TOY-04",
        "title": "Pillai-Tamizh Developmental Stages & Toy Pedagogy",
        "query": "Pillai-Tamizh ten paruvam developmental milestones sensorimotor childhood toy pedagogy binaural tracking bipedal gait nada-vandi",
        "expected_slugs": [
            "concept-pillai-tamizh-developmental-stages-and-kinesthetic-childhood-toy-pedagogy"
        ]
    },
    {
        "id": "TOY-05",
        "title": "Gadilam Clay Press-Molding & Tapioca Paper-Mache Shells",
        "query": "Two-piece bivalve terracotta plaster molds achu-bommai tapioca flour javvarisi fenugreek paste paper-mache shell casting",
        "expected_slugs": [
            "technology-gadilam-alluvial-clay-press-molding-and-tapioca-paper-mache-shell-casting"
        ]
    },
    {
        "id": "TOY-06",
        "title": "Palmyra Olai-Kilukiluppai Braiding & Nada-Vandi Joinery",
        "query": "Borassus flabellifer kurutholai palmyra leaf polyhedral braiding olai-kilukiluppai rattle bow-lathe kadaisal arakku lacquer nada-vandi",
        "expected_slugs": [
            "technology-palmyra-leaf-olai-kilukiluppai-braiding-and-wooden-nada-vandi-joinery"
        ]
    },
    {
        "id": "TOY-07",
        "title": "Excavated Sangam Terracotta Wheels & Pull-Toys",
        "query": "Keeladi Korkai Uraiyur excavated perforated terracotta wheels painted spokes zoomorphic ram bull pull-toys avian whistles",
        "expected_slugs": [
            "artifact-siru-ther-miniature-wheeled-carts-and-sanga-kalam-terracotta-figurines"
        ]
    },
    {
        "id": "TOY-08",
        "title": "Panruti Gadilam River Alluvial Clay Toy Haven",
        "query": "Panruti Cuddalore district Gadilam river alluvial clay doll terracotta toy haven 11.7740 79.5530 Thiruvathigai Vandipalayam",
        "expected_slugs": [
            "place-panruti-ancient-gadilam-clay-doll-and-terracotta-toy-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Terracotta & Wooden Toys, Thalaiyatti Counterweight Dolls & Childhood Pedagogy")
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
