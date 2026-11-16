#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Sculpture, Iconography & Lost-Wax Bronze Casting Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "SCU-01",
        "query": "What are the canonical iconometric proportions, Tala measurements, and body flexion postures (Bhanga) codified in the Sirpa Chennool?",
        "expected_slugs": ["text-sirpa-chennool-sculpture-canon", "concept-talamana-iconometric-proportions"],
        "description": "Sirpa Chennool Iconometry, Tala & Bhanga Postures"
    },
    {
        "id": "SCU-02",
        "query": "How did Dravidian Vastu Shastra texts like Mayamata govern stone basement foundations (Upapitha and Adhishthana) and granite interlocking joints in temple architecture?",
        "expected_slugs": ["text-mayamata-dravidian-vastu-canon", "char-kunjara-mallan-rajaraja-perunthachan"],
        "description": "Mayamata Dravidian Vastu Shastra & Granite Foundations"
    },
    {
        "id": "SCU-03",
        "query": "What details of 66 solid copper icons, metallic weights, and master sculptor honors are recorded in the Thanjavur Brihadisvara inscriptions of Rajaraja Chola I?",
        "expected_slugs": ["insc-thanjavur-rajaraja-bronze-endowments", "concept-madhuchehishtavidhana-lost-wax-casting"],
        "description": "Thanjavur Temple 1010 CE Bronze Endowments & Sculptor Honors"
    },
    {
        "id": "SCU-04",
        "query": "What is the solid cire-perdue (Madhuchehishtavidhana) lost-wax casting technique and Panchaloha alloy composition perfected by Chola bronzecasters?",
        "expected_slugs": ["concept-madhuchehishtavidhana-lost-wax-casting", "char-swamimalai-master-stapathi", "place-swamimalai-bronze-artisan-quarter"],
        "description": "Madhuchehishtavidhana Lost-Wax Bronze Casting & Panchaloha"
    },
    {
        "id": "SCU-05",
        "query": "What are the mathematical ratios of the Talamana system, including Uttama Dasa-Tala (124 Angulas) and Ashta-Tala in sacred sculpting?",
        "expected_slugs": ["concept-talamana-iconometric-proportions", "text-sirpa-chennool-sculpture-canon"],
        "description": "Talamana Sacred Geometry & Uttama Dasa-Tala Metrics"
    },
    {
        "id": "SCU-06",
        "query": "What is the cosmic symbolism of the Ananda Tandava Nataraja bronze icon with the drum, fire, Abhaya mudra, and crushing of Apasmara?",
        "expected_slugs": ["concept-chola-bronze-ananda-tandava-iconography"],
        "description": "Ananda Tandava Nataraja Cosmic Iconography & Prabha Aureole"
    },
    {
        "id": "SCU-07",
        "query": "How were the five-fold artisan guilds of the Kammalar organized, and how did master sculptors transmit craft secrets through guru-shishya lineages?",
        "expected_slugs": ["concept-kammalar-stapathi-guild-guilds", "char-swamimalai-master-stapathi"],
        "description": "Kammalar Five-Fold Artisan Guilds & Stapathi Lineages"
    },
    {
        "id": "SCU-08",
        "query": "How did Chief Architect Kunjara Mallan Rajaraja Perunthachan engineer the 216-foot soaring vimana and 80-ton granite dome of the Thanjavur Brihadisvara Temple?",
        "expected_slugs": ["char-kunjara-mallan-rajaraja-perunthachan", "text-mayamata-dravidian-vastu-canon"],
        "description": "Kunjara Mallan Perunthachan & Thanjavur Hollow Vimana Engineering"
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
    print("🗿 ANCIENT TAMIL SCULPTURE & BRONZE CASTING RAG BENCHMARK")
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
