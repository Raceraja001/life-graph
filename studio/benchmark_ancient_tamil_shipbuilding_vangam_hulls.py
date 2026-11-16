#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Shipbuilding, Sewn-Plank Masula Boats & Ocean-Going Vangam Hulls
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [
  {
    "id": "SHP-01",
    "title": "Pattinappalai Ocean-Going Vessels & Kaveripoompattinam Harbor Masts",
    "query": "How does classical Sangam poetry in Pattinappalai depict the towering masts, fluttering flags, and ocean-going Vangam ships at Kaveripoompattinam?",
    "expected_slugs": [
      "text-pattinappalai-shipbuilding-and-ocean-navigators-poetry",
      "concept-trans-oceanic-vangam-and-kalam-hull-framing-mechanics"
    ]
  },
  {
    "id": "SHP-02",
    "title": "Chettiyarpattinam Chola Shipyard Charters & Estuarine Drydock Epigraphs",
    "query": "What do the Chola inscriptions along the Coromandel coast record regarding state-sponsored shipyards, timber concessions, and drydocks at Chettiyarpattinam?",
    "expected_slugs": [
      "insc-chettiyarpattinam-chola-shipyard-and-drydock-charters",
      "place-chettiyarpattinam-ancient-shipyard-haven"
    ]
  },
  {
    "id": "SHP-03",
    "title": "Marakkanam Pallava Harbor Epigraphs & Riverine Timber Flotillas",
    "query": "How did Pallava charters at Sopatma Marakkanam regulate timber flotillas floating down the Palar river basin and harbor lighter tolls?",
    "expected_slugs": [
      "insc-marakkanam-pallava-harbor-and-timber-supply-charters",
      "concept-sewn-plank-masula-boat-architecture-and-coir-stitching"
    ]
  },
  {
    "id": "SHP-04",
    "title": "Sewn-Plank Masula Boat Architecture & Elastic Surf Breaker Hydrodynamics",
    "query": "How did the indigenous sewn-plank Masula boat absorb high-energy surf shocks without rigid iron ribs or nails using coir lacing?",
    "expected_slugs": [
      "concept-sewn-plank-masula-boat-architecture-and-coir-stitching",
      "concept-coconut-coir-lashing-vegetable-pitch-and-dammar-caulking"
    ]
  },
  {
    "id": "SHP-05",
    "title": "Trans-Oceanic Vangam and Kalam Keel Architecture & Transverse Ribs",
    "query": "How were trans-oceanic Tamil Vangam and Kalam vessels framed with single-tree teak keels, curved ribs, and carvel planking?",
    "expected_slugs": [
      "concept-trans-oceanic-vangam-and-kalam-hull-framing-mechanics",
      "char-chettiyarpattinam-master-shipwright-marakkal-thatchan"
    ]
  },
  {
    "id": "SHP-06",
    "title": "Coconut Coir Lashing, Vegetable Dammar Pitch & Anti-Fouling",
    "query": "How did ancient Tamil shipwrights formulate hydrophobic dammar resin, fish oil, and saltwater-retted coconut coir to resist shipworm teredo navalis?",
    "expected_slugs": [
      "concept-coconut-coir-lashing-vegetable-pitch-and-dammar-caulking",
      "concept-sewn-plank-masula-boat-architecture-and-coir-stitching"
    ]
  },
  {
    "id": "SHP-07",
    "title": "Monsoon Wind Meteorology, Star Azimuths & Dual Quarter-Rudders",
    "query": "How did ancient Tamil navigators utilize southwest and northeast monsoon winds, stellar constellations, and dual quarter-rudders to cross the ocean?",
    "expected_slugs": [
      "concept-monsoon-wind-meteorology-and-dual-quarter-rudder-navigation",
      "char-nagapattinam-ocean-navigator-kalam-selvan-nayagan"
    ]
  },
  {
    "id": "SHP-08",
    "title": "Chettiyarpattinam Ancient Shipyard Haven & Estuarine Basin",
    "query": "Where was the ancient and medieval Chola shipyard haven of Chettiyarpattinam situated along the Coromandel coast for refitting naval armadas?",
    "expected_slugs": [
      "place-chettiyarpattinam-ancient-shipyard-haven",
      "insc-chettiyarpattinam-chola-shipyard-and-drydock-charters"
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
    print("🎯 ANCIENT TAMIL SHIPBUILDING, SEWN-PLANK MASULA BOATS & VANGAM HULLS RAG BENCHMARK")
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
