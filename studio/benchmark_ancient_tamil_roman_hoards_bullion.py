#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Roman Currency Hoards, Bullion Demonetization & Trade Balances Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "ROM-01",
        "query": "What archaeological evidence of Augustan and Tiberian gold aurei caches was excavated in the Pollachi corridor near the Palakkad Gap?",
        "expected_slugs": ["arch-pollachi-roman-aurei-hoards", "concept-kongu-palakkad-gap-bullion-highway"],
        "description": "Pollachi Roman Aurei Hoards in the Palakkad Gap"
    },
    {
        "id": "ROM-02",
        "query": "What was discovered at Vellalur on the Noyyal River including over 500 Roman silver denarii and engraved carnelian intaglio rings?",
        "expected_slugs": ["arch-vellalur-denarii-and-jewelry-hoards", "char-vellalur-roman-bullion-dealer"],
        "description": "Vellalur Roman Silver Denarii Hoards & Jewelry Depots"
    },
    {
        "id": "ROM-03",
        "query": "What numismatic discoveries from the Amaravathi riverbed at Karur yielded Roman aurei alongside Sangam Chera portrait coins?",
        "expected_slugs": ["arch-karur-amaravathi-riverbed-bullion-finds"],
        "description": "Karur Amaravathi Riverbed Numismatic Discoveries"
    },
    {
        "id": "ROM-04",
        "query": "Why did ancient Tamil merchants cut deep chisel-slits across the faces of Roman emperors on imported gold aurei and silver denarii?",
        "expected_slugs": ["concept-roman-bullion-counter-marking"],
        "description": "Roman Bullion Chisel-Slit Counter-Marking & Demonetization"
    },
    {
        "id": "ROM-05",
        "query": "How does Pliny the Elder in Naturalis Historia record the astronomical Roman trade deficit of 50 million sesterces draining to India for spices and pearls?",
        "expected_slugs": ["concept-mediterranean-trade-deficit-and-pliny-lament", "char-pliny-the-elder-trade-historian"],
        "description": "Pliny's Naturalis Historia on the Indian Ocean Bullion Drain"
    },
    {
        "id": "ROM-06",
        "query": "What were the locally molded baked terracotta Roman coin bullae excavated at urban centers like Uraiyur and worn as elite amulets?",
        "expected_slugs": ["concept-terracotta-roman-coin-bullae"],
        "description": "Terracotta Roman Coin Bullae & Clay Prestige Amulets"
    },
    {
        "id": "ROM-07",
        "query": "How did the 30-kilometer Palakkad Gap mountain pass function as the trans-peninsular bullion arterial channeling Roman gold from Muziris to Coromandel?",
        "expected_slugs": ["concept-kongu-palakkad-gap-bullion-highway", "arch-pollachi-roman-aurei-hoards"],
        "description": "The Palakkad Gap Trans-Peninsular Bullion Highway"
    },
    {
        "id": "ROM-08",
        "query": "Where was the historic inland bullion melting and minting center located on the Thamirabarani River in Tirunelveli district?",
        "expected_slugs": ["place-kallidaikurichi-porunai-mint-quarter"],
        "description": "Kallidaikurichi Thamirabarani Industrial Minting Center"
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
    print("🏛️ ROMAN CURRENCY HOARDS & MEDITERRANEAN BULLION RAG BENCHMARK")
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
