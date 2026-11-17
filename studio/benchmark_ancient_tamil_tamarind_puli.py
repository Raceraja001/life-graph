#!/usr/bin/env python3
"""
Benchmark: Batch 56 - Ancient Tamil Tamarind (Puli) Agroforestry & Tartaric Acid Technology
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
    "id": "PLI-01",
    "title": "Tamarind pod harvesting and salted mattai-puli curing",
    "query": "How did traditional Tamil cultivators harvest ripe tamarind pods with hooked bamboo poles, de-seed the pulp, and compact it with rock salt into mattai-puli blocks?",
    "expected_slugs": [
      "technology-puli-pod-harvesting-deseeding-rock-salt-compacting-and-mattai-puli-maturation-technology"
    ]
  },
  {
    "id": "PLI-02",
    "title": "Tartaric acid chelation and puli-ittu-vilakki metal cleaning",
    "query": "What is the chemical mechanism of L(+)-tartaric acid in tamarind pulp chelating copper oxides to clean tarnished brass and bronze vessels in the puli-ittu-vilakki practice?",
    "expected_slugs": [
      "technology-puli-ittu-vilakki-tartaric-acid-chelation-brass-bronze-cleaning-and-culinary-acid-stewing-technology"
    ]
  },
  {
    "id": "PLI-03",
    "title": "Molecular chemistry of tartaric acid and food preservation",
    "query": "What are the molecular properties of L(+)-tartaric acid as a bidentate ligand, its thermal stability up to 175°C, and its bacterial lysis mechanism in tamarind pulp?",
    "expected_slugs": [
      "concept-tartaric-acid-isomer-chelation-chemistry-copper-oxide-dissolution-and-food-preservation"
    ]
  },
  {
    "id": "PLI-04",
    "title": "Glazed bharani jars and salted mattai-puli artifacts",
    "query": "What are the material artifacts of Tamil tamarind storage: compressed salted mattai-puli cakes wrapped in palm leaf sheaths and glazed earthenware bharani jars?",
    "expected_slugs": [
      "artifact-salted-mattai-puli-earthenware-bharani-wooden-pod-mallets-and-bronze-kinnam-pots"
    ]
  },
  {
    "id": "PLI-05",
    "title": "Tamarind-wood pestles and puli-kuzhambu clay manchatti",
    "query": "How were interlocked tamarind heartwood pestles (ulakkai), slow-burning charcoal embers, and clay manchatti pots utilized in traditional kitchens?",
    "expected_slugs": [
      "artifact-tamarind-wood-mortar-pestles-charcoal-braziers-and-puli-kuzhambu-clay-chatti-cookware"
    ]
  },
  {
    "id": "PLI-06",
    "title": "Sangam puli-kari gastronomy and Purananuru meat feasts",
    "query": "How does Sangam classical poetry in Purananuru and Malaipadukadam describe sour tamarind meat stews (puli-kari) balancing red meat digestion and warrior stamina?",
    "expected_slugs": [
      "concept-sangam-puli-kari-gastronomy-purananuru-sour-meat-stews-and-digestive-homeostasis"
    ]
  },
  {
    "id": "PLI-07",
    "title": "Tindivanam ancient tamarind agroforestry haven",
    "query": "Where was the ancient Thondaimandalam haven of Tindivanam (Thinthirini-vanam) located, renowned for vast tamarind groves, highway avenues, and bulk spice mandis?",
    "expected_slugs": [
      "place-tindivanam-ancient-thondaimandalam-puli-tamarind-agroforestry-haven"
    ]
  },
  {
    "id": "PLI-08",
    "title": "Chola epigraphs on puli taxation and temple endowments",
    "query": "Which historical inscriptions document Chola taxes on tamarind groves (puli-kadamai) and perpetual temple endowments of Puli-Ogarai tamarind rice at Srirangam?",
    "expected_slugs": [
      "text-purananuru-and-chola-epigraphs-on-puliya-maram-groves-tamarind-taxation-and-feasting"
    ]
  }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Batch 56 - Ancient Tamil Tamarind (Puli) Agroforestry & Tartaric Acid Technology")
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
