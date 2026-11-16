#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Perfumery, Sandalwood Maceration & Aromatic Hydro-Distillation
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [
  {
    "id": "PRF-01",
    "title": "Maduraikkanchi Aromatic Bazaars & Incense Fumes (Narum-Pukai)",
    "query": "How does classical Sangam poetry in Maduraikkanchi describe the fragrant night bazaars of Madurai, burning incense braziers, and sandalwood pastes?",
    "expected_slugs": [
      "text-maduraikkanchi-aromatic-bazaar-and-incense-poetry",
      "concept-compound-incense-formulation-narum-pukai-and-resin-burners"
    ]
  },
  {
    "id": "PRF-02",
    "title": "Kallidaikurichi Royal Sandalwood Tribute Charters & Podhigai Hills",
    "query": "What do the Pandya inscriptions at Kallidaikurichi record regarding state monopolies on fragrant sandalwood logs harvested from the Podhigai mountains?",
    "expected_slugs": [
      "insc-kallidaikurichi-royal-sandalwood-tribute-charters",
      "concept-sandalwood-heartwood-maceration-and-stone-grinding-mechanics"
    ]
  },
  {
    "id": "PRF-03",
    "title": "Thirumeyyam Temple Aromatic Endowments & Sumatra Camphor Imports",
    "query": "What do the rock-cut inscriptions at Thirumeyyam document regarding merchant guild endowments of Barus camphor, civet musk, and agarwood for deity unguents?",
    "expected_slugs": [
      "insc-thirumeyyam-temple-aromatic-ointment-and-camphor-endowments",
      "concept-civet-musk-and-attar-cold-enfleurage-fragrance-preservation"
    ]
  },
  {
    "id": "PRF-04",
    "title": "Clay Hydro-Distillation Retorts & Akil Agarwood Essential Oil",
    "query": "How did ancient Tamil perfumers construct earthenware hydro-distillation stills (Deg and Bhapka) to extract concentrated essential oil from resinous agarwood?",
    "expected_slugs": [
      "concept-clay-hydro-distillation-and-akil-agarwood-essential-oils",
      "char-marungurpattinam-master-incense-distiller-narum-pukai-seyvor"
    ]
  },
  {
    "id": "PRF-05",
    "title": "Sandalwood Heartwood Maceration, Circular Lithic Grinding & Santalols",
    "query": "How was mature oily sandalwood rubbed in circular friction on granite slabs with rosewater to produce cooling santalol-rich cosmetic pastes?",
    "expected_slugs": [
      "concept-sandalwood-heartwood-maceration-and-stone-grinding-mechanics",
      "insc-kallidaikurichi-royal-sandalwood-tribute-charters"
    ]
  },
  {
    "id": "PRF-06",
    "title": "Compound Incense Formulation (Kootu-Dhoopam) & Perforated Censers",
    "query": "How did ancient perfumers compound benzoin gum, dammar resin, agarwood dust, and vetiver into incense pellets burned inside aerated bronze censers?",
    "expected_slugs": [
      "concept-compound-incense-formulation-narum-pukai-and-resin-burners",
      "text-maduraikkanchi-aromatic-bazaar-and-incense-poetry"
    ]
  },
  {
    "id": "PRF-07",
    "title": "Civet Musk (Punuhu), Cold Enfleurage & Animal Attar Fixatives",
    "query": "How was waxy perineal civet secretion purified and used in cold enfleurage fat beds to fix fragile nocturnal jasmine and screwpine floral fragrances?",
    "expected_slugs": [
      "concept-civet-musk-and-attar-cold-enfleurage-fragrance-preservation",
      "insc-thirumeyyam-temple-aromatic-ointment-and-camphor-endowments"
    ]
  },
  {
    "id": "PRF-08",
    "title": "Marungurpattinam Ancient Aromatic Haven & Coromandel Incense Port",
    "query": "Where was the ancient maritime incense port of Marungurpattinam situated along the Coromandel coast for exporting agarwood and perfumes?",
    "expected_slugs": [
      "place-marungurpattinam-ancient-aromatic-haven",
      "char-marungurpattinam-master-incense-distiller-narum-pukai-seyvor"
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
    print("🎯 ANCIENT TAMIL PERFUMERY, SANDALWOOD MACERATION & AROMATIC HYDRO-DISTILLATION RAG BENCHMARK")
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
