#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Burnt-Brick Engineering, Ring Wells & Stucco Sculpture (Sudhai)
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [
  {
    "id": "BRK-01",
    "title": "Manimekalai Burnt-Brick Chaityas & Stucco Sculpture",
    "query": "How does classical epic poetry in Manimekalai describe the magnificent burnt-brick chaityas, stupas, and white stucco sculptures of Puhar?",
    "expected_slugs": [
      "text-manimekalai-burnt-brick-architecture-and-stucco-poetry",
      "concept-hydraulic-lime-plaster-slaking-and-sudhai-stucco-sculpture"
    ]
  },
  {
    "id": "BRK-02",
    "title": "Uraiyur Chola Brick Palace Foundations & Covered Drains",
    "query": "What do the archaeological excavations at ancient Uraiyur reveal regarding early Chola burnt-brick palace walls and subterranean drainage conduits?",
    "expected_slugs": [
      "insc-urayur-chola-brick-temple-and-drainage-charters",
      "place-urayur-ancient-chola-brick-masonry-haven"
    ]
  },
  {
    "id": "BRK-03",
    "title": "Poompuhar Sangam Brick Wharf & Kilaiyur Jetty Epigraphs",
    "query": "What do marine archaeological excavations at Kilaiyur Poompuhar prove regarding the monumental Sangam-era burnt-brick wharf and mooring posts?",
    "expected_slugs": [
      "insc-poompuhar-sangam-brick-wharf-and-jetty-epigraphs",
      "char-poompuhar-master-brick-architect-sengal-thatchan"
    ]
  },
  {
    "id": "BRK-04",
    "title": "Sangam Burnt-Brick Kiln Pyrotechnics & 4:2:1 Modular Metrology",
    "query": "How were Sangam burnt bricks tempered with rice husks, fired in clamp kilns at 1000°C, and standardized to the universal 4:2:1 dimensional ratio?",
    "expected_slugs": [
      "concept-sangam-burnt-brick-kiln-pyrotechnics-and-mortarless-bonding",
      "char-poompuhar-master-brick-architect-sengal-thatchan"
    ]
  },
  {
    "id": "BRK-05",
    "title": "Terracotta Ring Wells (Urai-Kinaru) & Groundwater Bio-Filtration",
    "query": "How did terracotta ring wells (Urai-Kinaru) packed with charcoal and gravel function as domestic soak pits and graywater filtration systems in Sangam cities?",
    "expected_slugs": [
      "concept-terracotta-ring-well-engineering-urai-kinaru-and-soak-pits",
      "concept-urai-kinaru-terracotta-ring-wells"
    ]
  },
  {
    "id": "BRK-06",
    "title": "Hydraulic Shell-Lime Plaster Slaking & Sudhai Stucco Modeling",
    "query": "How did Tamil artisans slake calcined sea shell lime with palm jaggery, kadukkai tannins, and egg whites to sculpt weather-proof Sudhai stucco icons?",
    "expected_slugs": [
      "concept-hydraulic-lime-plaster-slaking-and-sudhai-stucco-sculpture",
      "char-urayur-master-stucco-sculptor-sudhai-sirpan"
    ]
  },
  {
    "id": "BRK-07",
    "title": "Corbelled Brick Vaulting & Subsurface Municipal Stormwater Conduits",
    "query": "How did ancient Tamil builders construct corbelled brick false arches and vaulted subterranean drainage conduits without true keystones?",
    "expected_slugs": [
      "concept-corbelled-brick-vaulting-and-subsurface-stormwater-conduits",
      "insc-urayur-chola-brick-temple-and-drainage-charters"
    ]
  },
  {
    "id": "BRK-08",
    "title": "Uraiyur Ancient Chola Brick Masonry Haven & Kaveri Capital",
    "query": "Where was the inland dynastic capital of Uraiyur situated along the Kaveri river, renowned for its brick architecture and dye vats?",
    "expected_slugs": [
      "place-urayur-ancient-chola-brick-masonry-haven",
      "insc-urayur-chola-brick-temple-and-drainage-charters"
    ]
  }
]

def get_bge_embedding(text_str: str) -> list[float]:
    payload = json.dumps({
        "model": "bge-m3:latest",
        "prompt": text_str[:4000]
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]

def main():
    print("=" * 75)
    print("🎯 ANCIENT TAMIL BURNT-BRICK ENGINEERING, RING WELLS & STUCCO SCULPTURE RAG BENCHMARK")
    print("=" * 75)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(TEST_CASES)

    for case in TEST_CASES:
        qid = case["id"]
        qtitle = case["title"]
        query = case["query"]
        expected = case["expected_slugs"]

        q_emb = get_bge_embedding(query)
        q_emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"

        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) as similarity
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 1;
        """, (q_emb_str, q_emb_str))

        top_match = cur.fetchone()
        if not top_match:
            print(f"[{qid}] {qtitle}\n  Query: \"{query}\"\n  ❌ FAIL: No results returned")
            continue

        top_slug, score = top_match
        is_hit = top_slug in expected

        if is_hit:
            passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"\n[{qid}] {qtitle}")
        print(f"  Query: \"{query}\"")
        print(f"  Expected: {expected}")
        print(f"  Top-1: {top_slug} (Cosine Sim: {score:.4f}) -> {status}")

    acc = (passed / total) * 100.0
    print("\n" + "=" * 75)
    print(f"🎯 BENCHMARK RESULTS: {passed}/{total} Passed ({acc:.1f}% Top-1 Accuracy)")
    print("=" * 75 + "\n")

    cur.close()
    conn.close()

    if passed != total:
        sys.exit(1)

if __name__ == "__main__":
    import sys
    main()
