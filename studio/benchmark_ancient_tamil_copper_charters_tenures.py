#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Epigraphical Royal Charters, Brahmadeya-Devadana Tenures & Pidi-Nadanthu Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "TEN-01",
        "query": "What are the bilingual Sanskrit and Tamil contents of the Anbil copper plates granted by Sundara Chola to minister Aniruddha Brahmadhiraja?",
        "expected_slugs": ["text-anbil-copper-plates-chola-genealogy", "char-aniruddha-brahmadhiraja-chola-minister"],
        "description": "Anbil Copper Plates of Sundara Chola & Minister Aniruddha"
    },
    {
        "id": "TEN-02",
        "query": "How do the Velanjeri copper plates of Parantaka I document the creation of a Brahmadeya and the elephant boundary walking rite (Pidi-soozhnthu)?",
        "expected_slugs": ["insc-velanjeri-copper-plates-parantaka", "concept-pidi-soozhnthu-elephant-boundary-perambulation"],
        "description": "Velanjeri Copper Plates & Ritual Elephant Boundary Walking"
    },
    {
        "id": "TEN-03",
        "query": "What are the characteristics of the monumental 55-leaf Karandai Tamil Sangam copper plate charter issued by Rajendra Chola I?",
        "expected_slugs": ["insc-karandai-tamil-sangam-plates-rajendra", "concept-chola-royal-copper-plate-karanams"],
        "description": "Karandai Tamil Sangam 55-Leaf Copper Plate Charter"
    },
    {
        "id": "TEN-04",
        "query": "What were the socioeconomic and corporate governance structures of Brahmadeya and Devadana land tenures in medieval Tamilakam?",
        "expected_slugs": ["concept-brahmadeya-and-devadana-land-tenures", "concept-irayili-tax-exemption-and-kadamai"],
        "description": "Brahmadeya & Devadana Tenurial Autonomy & Sabhai Rule"
    },
    {
        "id": "TEN-05",
        "query": "What was the legal ritual protocol of Pidi-soozhnthu where a royal female elephant circumambulated village borders to fix permanent boundaries?",
        "expected_slugs": ["concept-pidi-soozhnthu-elephant-boundary-perambulation", "char-pidi-nadanthu-boundary-arbitrator"],
        "description": "Pidi-Soozhnthu Elephant Circumambulation Legal Protocol"
    },
    {
        "id": "TEN-06",
        "query": "What legal exemptions were granted under Irayili status to immunize temple and scholar lands from Kadamai and Kudimai dues?",
        "expected_slugs": ["concept-irayili-tax-exemption-and-kadamai", "concept-brahmadeya-and-devadana-land-tenures"],
        "description": "Irayili Tax Remission Charters & Kadamai Exemptions"
    },
    {
        "id": "TEN-07",
        "query": "How were Chola royal copper-plate charters (Sempetu) authenticated and sealed with lost-wax cast bronze tiger-seal rings?",
        "expected_slugs": ["concept-chola-royal-copper-plate-karanams", "insc-karandai-tamil-sangam-plates-rajendra"],
        "description": "Chola Royal Copper-Plate Karanams & Cast Bronze Ring Seals"
    },
    {
        "id": "TEN-08",
        "query": "Where is the historic Kollidam north bank Brahmadeya village located where Sundara Chola's Anbil copper plates were discovered?",
        "expected_slugs": ["place-anbil-chola-brahmadeya-settlement", "text-anbil-copper-plates-chola-genealogy"],
        "description": "Anbil Historic Brahmadeya Settlement & Kollidam Alluvial Hub"
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
    print("📜 EPIGRAPHICAL ROYAL CHARTERS & BRAHMADEYA TENURES RAG BENCHMARK")
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
