#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Cooperage, Wooden Lathe Turning & Grain Measuring Metrology
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [
  {
    "id": "MET-01",
    "title": "Kanakkathikaram Agrarian Measures & Volumetric Hierarchy",
    "query": "How does the mathematical treatise Kanakkathikaram detail the hierarchical capacity measures from Sevidu and Nazhi up to the multi-ton Kalam?",
    "expected_slugs": [
      "text-kanakkathikaram-agrarian-grain-measures-and-cooperage-poetry",
      "concept-sexagesimal-grain-metrology-sevidu-alakku-uri-nazhi-marakkal"
    ]
  },
  {
    "id": "MET-02",
    "title": "Ennayiram Chola Temple Grain Treasury Charters & Student Rations",
    "query": "What do the inscriptions of Rajendra Chola I at Ennayiram record regarding daily grain rations in Nazhi and Kuruni for 350 university scholars?",
    "expected_slugs": [
      "insc-ennayiram-chola-temple-grain-treasury-and-marakkal-charters",
      "place-ennayiram-ancient-grain-treasury-haven"
    ]
  },
  {
    "id": "MET-03",
    "title": "Thiruvidaimarudur Royal Rajarajan-Marakkal Standard Charters",
    "query": "What do the royal inscriptions at Thiruvidaimarudur decree regarding the establishment of the Rajarajan-Marakkal as the mandatory uniform grain measure?",
    "expected_slugs": [
      "insc-thiruvidaimarudur-royal-rajarajan-marakkal-standard-charters",
      "concept-brass-rimmed-measuring-vessel-calibration-and-state-stamping"
    ]
  },
  {
    "id": "MET-04",
    "title": "Hardwood Grain Measure Lathe Turning & Volumetric Boring",
    "query": "How were seasoned teak and vengai timbers turned on bow-lathes and precision-bored to create non-warping cylindrical grain measuring vessels?",
    "expected_slugs": [
      "concept-hardwood-grain-measure-lathe-turning-and-cooperage-mechanics",
      "char-ennayiram-master-grain-cooper-marakkal-alavalar"
    ]
  },
  {
    "id": "MET-05",
    "title": "Brass-Rimmed Measuring Vessel Calibration & State Tiger Branding",
    "query": "How were wooden grain measures reinforced with riveted brass rim bands to prevent lip wear and branded with the royal tiger seal?",
    "expected_slugs": [
      "concept-brass-rimmed-measuring-vessel-calibration-and-state-stamping",
      "char-thanjavur-royal-metrology-inspector-kole-alavu-kankani"
    ]
  },
  {
    "id": "MET-06",
    "title": "Struck Measure (Thalambu-Alavu) vs. Heaped Calibration",
    "query": "What was the operational difference between struck measure using a scraper bar for tax equity and heaped measure in ancient Tamil grain markets?",
    "expected_slugs": [
      "concept-sexagesimal-grain-metrology-sevidu-alakku-uri-nazhi-marakkal",
      "text-kanakkathikaram-agrarian-grain-measures-and-cooperage-poetry"
    ]
  },
  {
    "id": "MET-07",
    "title": "Granary Moisture Protection, Nel-Kuthir Silos & Sluice Gates",
    "query": "How did elevated clay-straw Nel-Kuthir silos raised on stone piers protect stored paddy against rodents, moisture, and pests with gravity discharge gates?",
    "expected_slugs": [
      "concept-granary-moisture-protection-nel-kuthir-and-timber-sluice-gates",
      "place-ennayiram-ancient-grain-treasury-haven"
    ]
  },
  {
    "id": "MET-08",
    "title": "Ennayiram Ancient Grain Treasury Haven & Granary Complex",
    "query": "Where was the imperial Chola grain repository and educational sanctuary of Ennayiram situated in northern Tamil Nadu?",
    "expected_slugs": [
      "place-ennayiram-ancient-grain-treasury-haven",
      "insc-ennayiram-chola-temple-grain-treasury-and-marakkal-charters"
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
    print("🎯 ANCIENT TAMIL COOPERAGE, WOODEN LATHE TURNING & GRAIN MEASURING METROLOGY RAG BENCHMARK")
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
