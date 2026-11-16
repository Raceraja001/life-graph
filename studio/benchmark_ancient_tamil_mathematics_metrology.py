#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Mathematics, Metrology, Fractions & Land Surveying Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "MTH-01",
        "query": "How does Kari Nayanar's Kanakkathikaram explain practical Tamil arithmetic, field geometry calculations, and fractional division?",
        "expected_slugs": ["text-kanakkathikaram-kari-nayanar", "char-kari-nayanar-mathematician"],
        "description": "Kanakkathikaram Practical Arithmetic & Field Geometry"
    },
    {
        "id": "MTH-02",
        "query": "What are the traditional pedagogical mathematical tables preserved in En-Suvadi palm leaves for trade arithmetic and volume measures?",
        "expected_slugs": ["text-aathisudi-kondrai-vendan-metrology"],
        "description": "En-Suvadi Pedagogical Tables & Trade Arithmetic"
    },
    {
        "id": "MTH-03",
        "query": "What are the micro-fractional units of land measurement recorded on the Thanjavur Brihadisvara plinth accurate to fractions of a Veli?",
        "expected_slugs": ["insc-thanjavur-land-survey-metrology", "concept-chola-land-survey-standardization"],
        "description": "Thanjavur Temple Cadastral Land Survey Epigraphs"
    },
    {
        "id": "MTH-04",
        "query": "What is the ancient Tamil micro-fractional taxonomy including Mundri (1/320), Kaani (1/80), Maa (1/20), and Immi (1/2,150,400)?",
        "expected_slugs": ["concept-tamil-micro-fractional-mathematics", "text-kanakkathikaram-kari-nayanar"],
        "description": "Tamil Micro-Fractional Metrology & Vigesimal Subdivisions"
    },
    {
        "id": "MTH-05",
        "query": "How did the Imperial Chola cadastral survey standardize the 16-span measuring rod (Ulagalandan-kol) and classify soils into productivity grades (Tharam)?",
        "expected_slugs": ["concept-chola-land-survey-standardization", "char-rajaraja-nilam-alandha-senapathi"],
        "description": "Chola Cadastral Land Survey & Ulagalandan-Kol Standard"
    },
    {
        "id": "MTH-06",
        "query": "What is the traditional hierarchical volumetric system for grain and liquid measurement from Sevidu and Aazhakku up to Marakkal and Kalam?",
        "expected_slugs": ["concept-ancient-tamil-grain-and-cubic-measures"],
        "description": "Grain & Liquid Volumetric Metrology (Aazhakku, Padi, Marakkal, Kalam)"
    },
    {
        "id": "MTH-07",
        "query": "How were botanical seed standards like Kunrimani and Manjadi used to measure gold weight and verify fineness (Maatru) on touchstones?",
        "expected_slugs": ["concept-pon-weight-and-touchstone-metrology"],
        "description": "Botanical Seed Standards for Gold Weight & Touchstone Metrology"
    },
    {
        "id": "MTH-08",
        "query": "Where were the royal cadastral land revenue registers (Vari-p-poththagam) and survey maps maintained in the Chola capital of Thanjavur?",
        "expected_slugs": ["place-thanjavur-royal-survey-archives", "concept-chola-land-survey-standardization"],
        "description": "Thanjavur Imperial Cadastral Land Survey Archives"
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
    print("📐 ANCIENT TAMIL MATHEMATICS & METROLOGY RAG BENCHMARK")
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
