#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Maritime Lighthouse Architecture, Night Beacons & Coastal Piloting Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "LGT-01",
        "query": "How does the Perumpanarruppadai depict the towering Ilangu-Sudar masonry lighthouse propping up the heavens with nocturnal oil flares?",
        "expected_slugs": ["text-perumpanarruppadai-ilangu-sudar-lighthouse-poetry", "char-poompuhar-lighthouse-keeper-deepa-kavalar"],
        "description": "Perumpanarruppadai Ilangu-Sudar Lighthouse Poetry & Night Flares"
    },
    {
        "id": "LGT-02",
        "query": "What submerged semicircular brick platforms and beacon tower foundations were discovered in marine excavations at Poompuhar?",
        "expected_slugs": ["insc-poompuhar-maritime-beacon-foundations", "concept-deepa-stambham-masonry-lighthouse-engineering"],
        "description": "Poompuhar Submerged Brick Beacon Foundations & Underwater Archaeology"
    },
    {
        "id": "LGT-03",
        "query": "What are the harbor customs regulations, pilotage cesses, and beacon maintenance endowments recorded at Marakkanam (Sopatma)?",
        "expected_slugs": ["insc-marakkanam-eyil-pattinam-beacon-charters", "place-marakkanam-sopatma-historic-beacon-port"],
        "description": "Marakkanam Eyilpattinam Beacon Charters & Pilotage Cesses"
    },
    {
        "id": "LGT-04",
        "query": "How were ancient Tamil masonry lighthouses (Deepa-Stambham) engineered with open parapets, large oil reservoirs, and bronze reflector shields?",
        "expected_slugs": ["concept-deepa-stambham-masonry-lighthouse-engineering", "text-perumpanarruppadai-ilangu-sudar-lighthouse-poetry"],
        "description": "Deepa-Stambham Architectural Engineering & Oil Flare Mechanics"
    },
    {
        "id": "LGT-05",
        "query": "How were pairs of high and low coastal bonfire beacons used to triangulate harbor entrances and guide ships through dangerous shoals?",
        "expected_slugs": ["concept-coastal-bonfire-beacons-and-channel-piloting", "char-marakkanam-estuary-harbor-pilot"],
        "description": "Coastal Triangulation Bonfire Beacons & Harbor Entrance Piloting"
    },
    {
        "id": "LGT-06",
        "query": "What hydrographic instruments were deployed in ancient Tamil coastal waters: moored float buoys and tallow sounding leads?",
        "expected_slugs": ["concept-shoal-warning-buoys-and-estuary-sounding-leads", "char-marakkanam-estuary-harbor-pilot"],
        "description": "Shoal Warning Float Buoys & Tallow Sounding Lead Technologies"
    },
    {
        "id": "LGT-07",
        "query": "What were the pilotage protocols, statutory harbor dues, and legal liabilities of coastal pilot corporations (Kalam-oottuvor)?",
        "expected_slugs": ["concept-maritime-pilot-corporations-and-harbor-tolls", "char-marakkanam-estuary-harbor-pilot"],
        "description": "Maritime Pilot Guild Governance & Harbor Pilotage Liability"
    },
    {
        "id": "LGT-08",
        "query": "Where was the ancient Coromandel port of Marakkanam (Sopatma / Eyilpattinam) situated with its deep-sea beacon tower and salt pans?",
        "expected_slugs": ["place-marakkanam-sopatma-historic-beacon-port", "insc-marakkanam-eyil-pattinam-beacon-charters"],
        "description": "Marakkanam (Sopatma) Historic Coromandel Beacon Port & Roadstead"
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
    print("🗼 MARITIME LIGHTHOUSES, BEACONS & COASTAL PILOTING RAG BENCHMARK")
    print("=" * 75)

    for case in BENCHMARK_CASES:
        vec = get_embedding(case["query"])
        vec_literal = "[" + ",".join(str(x) for x in vec) + "]"

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
