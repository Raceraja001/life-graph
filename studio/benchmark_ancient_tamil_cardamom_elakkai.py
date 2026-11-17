#!/usr/bin/env python3
"""
Benchmark: Batch 56 - Ancient Tamil Cardamom (Elakkai) & Western Ghats Hill Spicery
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
    "id": "ELK-01",
    "title": "Cardamom kiln curing and bamboo drying racks technology",
    "query": "How did ancient Tamil Western Ghats cultivators harvest three-quarter mature green cardamom and cure it on bamboo drying racks in wood-smoke kilns to preserve chlorophyll?",
    "expected_slugs": [
      "technology-elakkai-understory-agroforestry-hand-harvesting-and-curing-kiln-technology"
    ]
  },
  {
    "id": "ELK-02",
    "title": "Alpha-terpinyl acetate and 1,8-cineole terpene chemistry",
    "query": "What is the biochemical role of alpha-terpinyl acetate and 1,8-cineole monoterpenes in green cardamom essential oil for gastric mucin secretion and carminative action?",
    "expected_slugs": [
      "concept-alpha-terpinyl-acetate-and-1-8-cineole-ester-terpene-aroma-chemistry-and-carminative-bioactivity"
    ]
  },
  {
    "id": "ELK-03",
    "title": "Siddha Elathi Chooranam hydrodistillation compounding",
    "query": "What are the compounding techniques in Siddha medicine for decorticating cardamom seeds without friction heat and distilling essential oil for Elathi Chooranam carminatives?",
    "expected_slugs": [
      "technology-elakkai-cardamom-essential-oil-hydrodistillation-and-siddha-carminative-compounding-technology"
    ]
  },
  {
    "id": "ELK-04",
    "title": "Green cardamom capsules and glazed storage bharani",
    "query": "What are the material features of oval green cardamom capsules, woven bamboo paranai slats, and airtight ceramic bharani jars sealed with beeswaxed linen?",
    "expected_slugs": [
      "artifact-green-cardamom-seed-capsules-woven-bamboo-drying-racks-and-earthen-storage-bharani"
    ]
  },
  {
    "id": "ELK-05",
    "title": "Bodinayakkanur Cardamom City spicery haven",
    "query": "Where was the ancient Western Ghats mountain haven of Bodinayakkanur located that commanded spice passes, cardamom drying warehouses, and export auctions?",
    "expected_slugs": [
      "place-bodinayakkanur-ancient-western-ghats-elakkai-cardamom-spicery-haven"
    ]
  },
  {
    "id": "ELK-06",
    "title": "Sangam Kurinji Cardamom Hills ecology and tribal tenure",
    "query": "How did Sangam Kurinji mountain chieftains and tribal clans maintain gathering tenure in the Cardamom Hills (Elamalai) and barter spices for lowland coastal salt?",
    "expected_slugs": [
      "concept-sangam-high-altitude-kurinji-spicery-cardamom-hills-ecology-and-forest-gathering-tenure"
    ]
  },
  {
    "id": "ELK-07",
    "title": "Siddha cooling tridosha equilibrium and oral hygiene",
    "query": "Why does Siddha medicine classify cardamom as a cooling seetha veeryam spice that pacifies Pitta heat, stimulates digestion without acidity, and eliminates oral bacteria?",
    "expected_slugs": [
      "concept-siddha-elathi-sooranam-cooling-digestive-tridosha-equilibrium-and-oral-microbiome-hygiene"
    ]
  },
  {
    "id": "ELK-08",
    "title": "Sangam Pathitruppathu and moral classic Elathi texts",
    "query": "Which classical Tamil literature documents Chera mountain cardamom tributes in Pathitruppathu and names the post-Sangam moral text Elathi after the six-spice remedy?",
    "expected_slugs": [
      "text-sangam-anthologies-and-siddha-elathi-classics-on-fragrant-cardamom-tributes"
    ]
  }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Batch 56 - Ancient Tamil Cardamom (Elakkai) & Western Ghats Hill Spicery")
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
