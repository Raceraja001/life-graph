#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Stone Masonry Dressing, Hydraulic Sluice Engineering & Anicuts
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [
  {
    "id": "HYD-01",
    "title": "Karikala Chola Kallanai Chronicles & Porunararruppadai River Taming",
    "query": "How does classical Sangam literature in Porunararruppadai describe King Karikala Chola taming the Kaveri floods to irrigate the delta?",
    "expected_slugs": [
      "text-karikala-chola-kallanai-hydraulic-chronicles-and-sangam-odes",
      "concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations"
    ]
  },
  {
    "id": "HYD-02",
    "title": "Thiruvanaikoil Chola Grand Anicut Maintenance Charters & Stone Mason Guilds",
    "query": "What do the Chola inscriptions at Thiruvanaikoil record regarding Kallanai-puram land grants and tax exemptions for stone masons maintaining the Grand Anicut?",
    "expected_slugs": [
      "insc-thiruvanaikoil-chola-grand-anicut-maintenance-charters",
      "place-thiruvanaikoil-ancient-hydraulic-haven"
    ]
  },
  {
    "id": "HYD-03",
    "title": "Veeranam Parantaka Chola Reservoir Sluice Endowments & Vadavaru Feeder Canal",
    "query": "What do the imperial Chola inscriptions at Veeranam document regarding the excavation of the Vadavaru feeder canal and dressed granite sluice headworks?",
    "expected_slugs": [
      "insc-veeranam-parantaka-chola-reservoir-sluice-endowments",
      "concept-silt-scouring-sluices-and-kumizhi-thumbu-headworks"
    ]
  },
  {
    "id": "HYD-04",
    "title": "Cyclopean Granite Dressing, Sinking Foundation Mechanics & Clay Bedding",
    "query": "How did un-mortared cyclopean granite boulders sink through shifting river sand until resting securely on underlying clay at the Grand Anicut?",
    "expected_slugs": [
      "concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations",
      "char-kallanai-master-hydraulic-architect-neerarru-sirpan"
    ]
  },
  {
    "id": "HYD-05",
    "title": "Curved Weir Geometry, Downstream Talus Aprons & Energy Dissipation",
    "query": "How did the 329-meter serpentine curved masonry weir and sloping downstream boulder talus aprons dissipate the erosive kinetic energy of Kaveri floods?",
    "expected_slugs": [
      "concept-curved-weir-geometry-and-hydraulic-energy-dissipation-aprons",
      "concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations"
    ]
  },
  {
    "id": "HYD-06",
    "title": "Silt-Scouring Sluices, Kumizhi-Thumbu Vortex Headworks & Flushing",
    "query": "How did bottom-perforated conical stone sluices (Kumizhi-Thumbu) create vortices to flush heavy riverbed silt downstream onto paddy fields?",
    "expected_slugs": [
      "concept-silt-scouring-sluices-and-kumizhi-thumbu-headworks",
      "insc-veeranam-parantaka-chola-reservoir-sluice-endowments"
    ]
  },
  {
    "id": "HYD-07",
    "title": "Chola River Embankments (Kaveri Karai) & Delta Canal Bifurcation",
    "query": "How were stone-reinforced earthen levees (Kaveri-Karai) and diversion channels engineered by the Cholas to prevent flooding and distribute water across the delta?",
    "expected_slugs": [
      "concept-chola-river-embankment-and-flood-diversion-canal-networks",
      "concept-curved-weir-geometry-and-hydraulic-energy-dissipation-aprons"
    ]
  },
  {
    "id": "HYD-08",
    "title": "Thiruvanaikoil Ancient Hydraulic Haven & Kaveri-Kollidam Bifurcation",
    "query": "Where was the ancient hydraulic center of Thiruvanaikoil located at the Kaveri and Kollidam river split that directed delta water governance?",
    "expected_slugs": [
      "place-thiruvanaikoil-ancient-hydraulic-haven",
      "insc-thiruvanaikoil-chola-grand-anicut-maintenance-charters"
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
    print("🎯 ANCIENT TAMIL STONE MASONRY DRESSING, HYDRAULIC SLUICE ENGINEERING & ANICUTS RAG BENCHMARK")
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
