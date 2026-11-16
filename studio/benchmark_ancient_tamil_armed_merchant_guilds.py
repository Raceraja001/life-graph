#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Armed Merchant Guilds, Fortified Trade Towns & Mercenary Charters Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "GLD-01",
        "query": "What are the pan-Asian trading prerogatives asserted in the Ayyavole 500 mercantile prasasti across 18 countries, 32 ports, and 64 corporate towns?",
        "expected_slugs": ["insc-ayyavole-500-mercantile-prasasti", "concept-samaya-dharma-guild-jurisprudence"],
        "description": "Ayyavole 500 Pan-Asian Mercantile Prasasti"
    },
    {
        "id": "GLD-02",
        "query": "How did the Kattur inscription charter the settlement as an Erivirappattinam protected by armed merchant warriors with tax immunities?",
        "expected_slugs": ["insc-kattur-erivirappattinam-charter", "concept-erivirappattinam-fortified-trade-cities"],
        "description": "Kattur Erivirappattinam Fortified Merchant Charter"
    },
    {
        "id": "GLD-03",
        "query": "What are the death-binding suicide oaths taken by the Belaikara warrior retinues to defend temple treasuries and merchant bullion caravans?",
        "expected_slugs": ["insc-tiruvalangadu-belaikara-swamidrohi-charter", "concept-munrukai-mahasenai-mercenary-corps"],
        "description": "Belaikara & Munrukai-Mahasenai Suicide-Guards Oaths"
    },
    {
        "id": "GLD-04",
        "query": "How were fortified merchant cities (Erivirappattinam) engineered with moats, defensive ramparts, and sovereign extraterritorial armories?",
        "expected_slugs": ["concept-erivirappattinam-fortified-trade-cities", "place-kattur-fortified-merchant-station"],
        "description": "Erivirappattinam Fortified Merchant Urban Architecture"
    },
    {
        "id": "GLD-05",
        "query": "How was the tripartite mercenary army Munrukai-Mahasenai organized to protect long-distance trade caravans against forest highwaymen?",
        "expected_slugs": ["concept-munrukai-mahasenai-mercenary-corps", "char-erivira-mercenary-commander"],
        "description": "Munrukai-Mahasenai Tripartite Mercenary Escort Forces"
    },
    {
        "id": "GLD-06",
        "query": "What was the corporate legal system of Samaya-Dharma governing toll deductions (Magamai) and merchant dispute arbitration?",
        "expected_slugs": ["concept-samaya-dharma-guild-jurisprudence", "char-pattana-swami-ayyavole-guild-leader"],
        "description": "Samaya-Dharma Transnational Guild Law & Magamai Levies"
    },
    {
        "id": "GLD-07",
        "query": "What epigraphical evidence in Sumatra (Barus) and Thailand (Takuapa) proves the overseas maritime dominance of the Valanjiyar and Nanadesi merchant networks?",
        "expected_slugs": ["concept-valanjiyar-and-nanadesi-networks"],
        "description": "Valanjiyar & Nanadesi Southeast Asian Maritime Expeditions"
    },
    {
        "id": "GLD-08",
        "query": "Where was the fortified merchant station and corporate asylum city of Kattur located under Chola imperial authority?",
        "expected_slugs": ["place-kattur-fortified-merchant-station", "insc-kattur-erivirappattinam-charter"],
        "description": "Kattur Medieval Fortified Trade Citadel & Asylum Site"
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
    print("⚔️ ANCIENT TAMIL ARMED MERCHANT GUILDS RAG BENCHMARK")
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
