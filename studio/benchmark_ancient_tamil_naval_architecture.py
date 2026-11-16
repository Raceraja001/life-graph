#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Maritime Ship Architecture & Naval Warfare Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "NAV-01",
        "query": "How does the Kappal Sattiram classify ancient Tamil vessels into Kattumaram, Vangam, and Navai, and what timber selection rules are codified for shipwrights?",
        "expected_slugs": ["text-kappal-sattiram-naval-architecture", "concept-kappal-anatomy-and-rigging"],
        "description": "Kappal Sattiram Ship Typology & Timber Selection Rules"
    },
    {
        "id": "NAV-02",
        "query": "What is the indigenous stitched-hull construction (Koorai-kappal) technique using coconut coir cordage and dammar resin caulking without iron nails?",
        "expected_slugs": ["concept-kappal-anatomy-and-rigging", "text-kappal-sattiram-naval-architecture"],
        "description": "Stitched-Hull Construction (Koorai) & Coir Caulking"
    },
    {
        "id": "NAV-03",
        "query": "How does Maduraikkanchi describe mountain-like ocean ships (Navai) with cloud-sails anchored offshore and guided by harbor beacon lighthouses (Kalamkarai-vilakkam)?",
        "expected_slugs": ["text-maduraikkanchi-oceanic-navai", "concept-kappal-anatomy-and-rigging"],
        "description": "Maduraikkanchi Mountain-Masted Navai & Harbor Beacons"
    },
    {
        "id": "NAV-04",
        "query": "What details of the 1025 CE Srivijaya maritime campaign across the Straits of Malacca and Kadaram are inscribed on the Thanjavur temple plinth by Rajendra Chola I?",
        "expected_slugs": ["insc-thanjavur-rajendra-naval-expedition", "char-rajendra-chola-naval-emperor", "concept-chola-naval-armada-1025"],
        "description": "Thanjavur Plinth 1025 CE Srivijaya Naval Inscription"
    },
    {
        "id": "NAV-05",
        "query": "What are the hydrodynamic principles of twin-hull stability, wave-piercing log geometry, and unsinkable buoyancy in indigenous Tamil Kattumaram craft?",
        "expected_slugs": ["concept-kattumaram-and-twin-hull-hydrodynamics"],
        "description": "Kattumaram Hydrodynamics & Metacentric Stability"
    },
    {
        "id": "NAV-06",
        "query": "What naval warfare tactics did Tamil fleets employ, including the ramming prow (Amparam), incendiary fire jars (Thee-panai), and marine shock troops (Kadal-maravar)?",
        "expected_slugs": ["concept-naval-warfare-and-tactics", "char-chola-kadal-padai-thalapathi"],
        "description": "Naval Warfare Tactics, Ramming Prow & Marine Shock Troops"
    },
    {
        "id": "NAV-07",
        "query": "How were the Imperial Chola naval dockyards organized at Nagapattinam with tidal slipways, brackish timber seasoning basins, and ship repair facilities?",
        "expected_slugs": ["concept-nagapattinam-chola-naval-dockyards", "place-nagapattinam-naval-dockyard"],
        "description": "Nagapattinam Naval Dockyards, Tidal Slipways & Seasoning Yards"
    },
    {
        "id": "NAV-08",
        "query": "How does Purananuru celebrate Chola King Kulamutrathu Killivalavan for commanding an offensive naval armada across the wave-tossed ocean?",
        "expected_slugs": ["text-purananuru-kulamutrathu-killivalavan-navy", "char-kulamutrathu-killivalavan"],
        "description": "Purananuru Killivalavan Early Chola Naval Armada"
    }
]

def get_embedding(query: str) -> list[float]:
    payload = json.dumps({"model": "bge-m3:latest", "prompt": query}).encode("utf-8")
    req = urllib.request.Request(OLLAMA_EMBED_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]

def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_CASES)

    print("=" * 75)
    print("⚓ ANCIENT TAMIL MARITIME SHIP ARCHITECTURE & NAVAL WARFARE RAG BENCHMARK")
    print("=" * 75)

    for case in BENCHMARK_CASES:
        vec = get_embedding(case["query"])
        vec_literal = "[" + ",".join(str(x) for x in vec) + "]"

        # Retrieve top 5 closest chunks
        cur.execute("""
            SELECT 
                rc.id,
                rc.node_slug,
                rc.language,
                1 - (rc.embedding <=> %s::vector) AS similarity,
                LEFT(rc.content, 120) AS preview
            FROM rag_chunks rc
            ORDER BY rc.embedding <=> %s::vector ASC
            LIMIT 5;
        """, (vec_literal, vec_literal))

        rows = cur.fetchall()
        top1 = rows[0] if rows else None
        top1_source = top1[1] if top1 else None
        top1_sim = float(top1[3]) if top1 else 0.0

        is_match = top1_source in case["expected_slugs"]
        if is_match:
            passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"\n[{case['id']}] {case['description']}")
        print(f"  Query: \"{case['query']}\"")
        print(f"  Expected: {case['expected_slugs']}")
        print(f"  Top-1: {top1_source} (Cosine Sim: {top1_sim:.4f}) -> {status}")
        if not is_match and rows:
            print("  Top 3 Returned:")
            for i, r in enumerate(rows[:3]):
                print(f"    {i+1}. {r[1]} ({float(r[3]):.4f}) - {r[4].strip()}...")

    conn.close()
    acc = (passed / total) * 100
    print("\n" + "=" * 75)
    print(f"🎯 BENCHMARK RESULTS: {passed}/{total} Passed ({acc:.1f}% Top-1 Accuracy)")
    print("=" * 75)

if __name__ == "__main__":
    main()
