#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Goldsmithing, Granulation Beads & Royal Filigree Metallurgy
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [
  {
    "id": "GLD-01",
    "title": "Silappadikaram Gold Bazaar (Pon-Angadi) & Fourfold Gold Classification",
    "query": "How does classical poetry in Silappadikaram describe the gold bazaar of Kaveripoompattinam and the four classical classifications of gold?",
    "expected_slugs": [
      "text-silappadikaram-gold-bazaar-and-goldsmith-guild-poetry",
      "concept-urai-kal-touchstone-assaying-and-gold-purity-metrology"
    ]
  },
  {
    "id": "GLD-02",
    "title": "Keezhadi Early Pandya Gold Assay Epigraphs & Touchstones",
    "query": "What do the 6th-century BCE archaeological excavations at Keezhadi on the Vaigai reveal regarding touchstones, crucibles, and goldsmith workshops?",
    "expected_slugs": [
      "insc-keezhadi-early-pandya-gold-assay-and-artisan-charters",
      "char-keezhadi-master-goldsmith-pon-kollan"
    ]
  },
  {
    "id": "GLD-03",
    "title": "Kodumanal Chera Goldsmith Guild Charters & Wire-Drawing Drawplates",
    "query": "What do the inscribed Tamil-Brahmi sherds and perforated drawplates at Kodumanal document about Chera filigree jewelry workshops?",
    "expected_slugs": [
      "insc-kodumanal-cheran-filigree-goldsmith-guild-charters",
      "concept-royal-filigree-wire-drawing-and-repousse-leafwork"
    ]
  },
  {
    "id": "GLD-04",
    "title": "Micro-Granulation Gold Bead Fabrication & Eutectic Colloidal Soldering",
    "query": "How did ancient Tamil jewelers create microscopic spherical gold beads via surface tension and bond them through copper salt eutectic reactions?",
    "expected_slugs": [
      "concept-micro-granulation-gold-bead-fabrication-and-eutectic-bonding",
      "char-keezhadi-master-goldsmith-pon-kollan"
    ]
  },
  {
    "id": "GLD-05",
    "title": "Royal Filigree Wire Drawing, Pitch-Bed Repoussé & Chasing",
    "query": "How was annealed gold drawn through graduated drawplates into fine filigree wires and hammered from behind on warm pitch beds for repoussé relief?",
    "expected_slugs": [
      "concept-royal-filigree-wire-drawing-and-repousse-leafwork",
      "char-pattanam-royal-filigree-jeweler-chempon-achari"
    ]
  },
  {
    "id": "GLD-06",
    "title": "Urai-Kal Touchstone Assaying & Botanical Seed Carat Weights",
    "query": "How did goldsmiths in ancient Tamilakam utilize velvety black jasper touchstones (Urai-kal) and botanical seed weights (Kundrimani, Manjadi) to assay gold purity?",
    "expected_slugs": [
      "concept-urai-kal-touchstone-assaying-and-gold-purity-metrology",
      "text-silappadikaram-gold-bazaar-and-goldsmith-guild-poetry"
    ]
  },
  {
    "id": "GLD-07",
    "title": "Die-Struck Gold Coin Minting & Dynastic Emblems",
    "query": "How were gold coins hot-struck between engraved iron anvil dies to emboss the Chera Bow, Chola Tiger, and Pandya Double Carp?",
    "expected_slugs": [
      "concept-die-struck-gold-coin-minting-and-punch-marked-symbolism",
      "concept-urai-kal-touchstone-assaying-and-gold-purity-metrology"
    ]
  },
  {
    "id": "GLD-08",
    "title": "Pattanam Ancient Gold & Gem Lapidary Haven (Muziris)",
    "query": "Where was the ancient Chera maritime port of Pattanam Muziris situated, where thousands of micro-granulated gold beads and Roman coins were excavated?",
    "expected_slugs": [
      "place-pattanam-ancient-gold-lapidary-haven",
      "char-pattanam-royal-filigree-jeweler-chempon-achari"
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
    print("🎯 ANCIENT TAMIL GOLDSMITHING, GRANULATION BEADS & ROYAL FILIGREE METALLURGY RAG BENCHMARK")
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
