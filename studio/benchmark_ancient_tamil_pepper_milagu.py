#!/usr/bin/env python3
"""
Benchmark: Batch 56 - Ancient Tamil Black Pepper (Milagu) & Indo-Roman Spice Confederations
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
    "id": "MLG-01",
    "title": "Pepper vine standards and hot-water scalding curing",
    "query": "How did ancient Tamil cultivators harvest black pepper from living tree standards and use hot-water scalding to activate polyphenol oxidase for pitch-black sun curing?",
    "expected_slugs": [
      "technology-milagu-pepper-vine-standards-harvesting-hot-water-scalding-and-sun-curing-technology"
    ]
  },
  {
    "id": "MLG-02",
    "title": "Piperine alkaloid thermo-pungency and bioenhancement",
    "query": "How does the molecular alkaloid piperine bind to TRPV1 vanilloid thermo-receptors on sensory nerve endings to induce calcium influx and perspiration diaphoresis?",
    "expected_slugs": [
      "concept-piperine-alkaloid-thermo-pungency-vanilloid-receptor-activation-and-bioavailability-enhancement"
    ]
  },
  {
    "id": "MLG-03",
    "title": "Milagu Rasam and coarse crushing decoction technology",
    "query": "What are the pharmacological preparation techniques for coarse crushing of peppercorns to preserve terpenes and brewing medicinal Milagu Rasam with tamarind and cumin?",
    "expected_slugs": [
      "technology-milagu-kashayam-decoction-thirikadugu-blending-and-milagu-rasam-pharmacology-technology"
    ]
  },
  {
    "id": "MLG-04",
    "title": "Shriveled black pepper drupes and granite ammikkal",
    "query": "What are the material characteristics of shriveled corrugated black peppercorn drupes and flat granite ammikkal stones used for shearing spice pericarps?",
    "expected_slugs": [
      "artifact-shriveled-black-pepper-drupes-terracotta-steeping-pots-and-granite-ammikal-grinding-stones"
    ]
  },
  {
    "id": "MLG-05",
    "title": "Roman gold aurei hoards and Musiris spice balances",
    "query": "What archaeological evidence proves the massive Roman gold coin hoards in Coimbatore and burlap spice bales weighed at Musiris harbor docks?",
    "expected_slugs": [
      "artifact-roman-gold-aurei-hoards-burlap-spice-bales-and-musiris-dockyard-steelyard-balances"
    ]
  },
  {
    "id": "MLG-06",
    "title": "Indo-Roman pepper trade and Pliny bullion drain economics",
    "query": "How did Apicius Roman recipes and Alaric 3000 pounds pepper ransom reflect the macro-economics of Yavana maritime fleets sailing via Hippalus monsoon winds from Berenike?",
    "expected_slugs": [
      "concept-indo-roman-maritime-black-pepper-yavana-trade-and-gold-bullion-drain-economics"
    ]
  },
  {
    "id": "MLG-07",
    "title": "Kolli Hills ancient pepper haven and Valvil Ori",
    "query": "Where was the misty montane spice haven of Kolli Hills located, famed for King Valvil Ori and high-piperine heirloom black pepper agroforestry?",
    "expected_slugs": [
      "place-kolli-hills-ancient-milagu-black-pepper-and-spicery-haven"
    ]
  },
  {
    "id": "MLG-08",
    "title": "Akananuru 149 and Periplus records on pepper trade",
    "query": "Which historical and Sangam literary texts record Yavana ships exchanging gold for cargoes of black pepper (kari) in Akananuru 149 and the Periplus?",
    "expected_slugs": [
      "text-sangam-akanannuru-and-periplus-maris-erythraei-records-on-pepper-fleets-and-tribute"
    ]
  }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Batch 56 - Ancient Tamil Black Pepper (Milagu) & Indo-Roman Spice Confederations")
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
        rows = cur.fetchall()

        top_slug, top_sim = rows[0] if rows else (None, 0.0)
        is_hit = top_slug in expected
        status = "PASS" if is_hit else "FAIL"
        if is_hit:
            passed += 1

        print(f"Query [{qid}]: {qtitle}")
        print(f"  Top-1: {top_slug} (sim: {top_sim:.4f}) -> {status}")
        if not is_hit:
            print(f"  Expected: {expected}")
            print("  Top 5 returned:")
            for r in rows:
                print(f"    - {r[0]} (sim: {r[1]:.4f})")
        print("-" * 60)

    cur.close()
    conn.close()

    accuracy = (passed / total) * 100
    print(f"Benchmark Result: {passed}/{total} passed ({accuracy:.1f}% Top-1 Accuracy)")
    if passed == total:
        print("ALL PROBES PASSED!")
        sys.exit(0)
    else:
        print("FAILURES DETECTED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
