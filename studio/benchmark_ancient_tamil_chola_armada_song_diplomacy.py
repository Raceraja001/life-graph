#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Overseas Maritime Expeditions, Kadaram (Kedah) & Song Dynasty Diplomacy Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "NAV-01",
        "query": "What are the records in China's Song Shi annals describing imperial Chola embassies in 1015 and 1077 CE bringing frankincense and pearls?",
        "expected_slugs": ["text-song-shi-chola-diplomatic-annals", "char-chola-ambassador-to-song-court"],
        "description": "Song Shi Annals & Imperial Chola Embassies to Kaifeng"
    },
    {
        "id": "NAV-02",
        "query": "What does the triumphant Meykkirthi of Rajendra Chola I record regarding the 1025 CE trans-oceanic armada assault on Srivijaya and Kadaram?",
        "expected_slugs": ["insc-tiruvalangadu-kadaram-conquest-charters", "concept-chola-armada-trans-oceanic-naval-tactics"],
        "description": "Rajendra Chola 1025 CE Maritime Meykkirthi & Kadaram Assault"
    },
    {
        "id": "NAV-03",
        "query": "What are the diplomatic endowments granted in the Leiden copper plates for the Buddhist Chudamani Vihara built at Nagapattinam by Srivijaya?",
        "expected_slugs": ["insc-nagapattinam-chudamani-vihara-charters", "concept-chudamani-vihara-buddhist-diplomatic-complex"],
        "description": "Nagapattinam Chudamani Vihara Charters & Anaimangalam Grant"
    },
    {
        "id": "NAV-04",
        "query": "What were the naval tactics of Rajendra I's battlefleet using southwest monsoon navigation and dual-pincer attacks through the Malacca and Sunda straits?",
        "expected_slugs": ["concept-chola-armada-trans-oceanic-naval-tactics", "char-chola-maritime-admiral-samudradhipati"],
        "description": "Chola Armada Naval Tactics & Dual-Pincer Malacca-Sunda Envelopment"
    },
    {
        "id": "NAV-05",
        "query": "What geopolitical transit toll bottleneck in the Malacca Strait maintained by Srivijaya led to Rajendra Chola's 1025 CE maritime assault?",
        "expected_slugs": ["concept-srivijaya-maritime-chokepoint-toll-geopolitics", "insc-tiruvalangadu-kadaram-conquest-charters"],
        "description": "Srivijayan Malacca Strait Toll Geopolitics & Geopolitical Conflict"
    },
    {
        "id": "NAV-06",
        "query": "How did Chola-Song tribute diplomacy facilitate bulk exchange of pearls and aromatics for Chinese copper coins and silver bullion ingots?",
        "expected_slugs": ["concept-chola-song-tribute-diplomacy-and-bullion-flow", "text-song-shi-chola-diplomatic-annals"],
        "description": "Chola-Song Macro-Economic Tribute Trade & Bullion Flows"
    },
    {
        "id": "NAV-07",
        "query": "What was the extraterritorial diplomatic and monastic function of the multi-story Chudamani Vihara (China Pagoda) at Nagapattinam?",
        "expected_slugs": ["concept-chudamani-vihara-buddhist-diplomatic-complex", "insc-nagapattinam-chudamani-vihara-charters"],
        "description": "Chudamani Vihara Diplomatic Enclave & China Pagoda Beacon"
    },
    {
        "id": "NAV-08",
        "query": "Where was the fortified Sumatran riverine citadel of Malaiyur on the Batang Hari river that was conquered by the Chola armada in 1025 CE?",
        "expected_slugs": ["place-malaiyur-jambi-sumatra-anchorage", "insc-tiruvalangadu-kadaram-conquest-charters"],
        "description": "Malaiyur (Jambi, Sumatra) Historic Naval Anchorage & Citadel"
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
    print("🚢 CHOLA ARMADA, KADARAM & SONG DYNASTY DIPLOMACY RAG BENCHMARK")
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
