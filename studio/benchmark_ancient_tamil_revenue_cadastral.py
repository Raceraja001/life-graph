#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Revenue Secretariat, Cadastral Auditing & Land Classification Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "REV-01",
        "query": "How does the Periyapuranam and Chola administrative canon describe the central revenue secretariat (Puravu-vari-thinaikalam) and palm-leaf accounting ledgers (Vari-pothagam)?",
        "expected_slugs": ["text-periyapuranam-vari-pothagam-chola-revenue", "concept-puravu-vari-thinaikalam-revenue-ministry"],
        "description": "Periyapuranam & Vari-Pothagam Revenue Administration Canon"
    },
    {
        "id": "REV-02",
        "query": "What was the monumental empire-wide cadastral land survey of 1001 CE initiated by Rajaraja I recorded on the Thanjavur temple walls?",
        "expected_slugs": ["insc-tanjavur-ulagalantan-cadastral-survey", "concept-ulagalantan-16-span-standard-survey-rod"],
        "description": "Thanjavur Ulagalantan Cadastral Survey Inscription"
    },
    {
        "id": "REV-03",
        "query": "What are the inscriptional tax reclassifications and flood remission decrees issued by the revenue ministry recorded at Tirukkandiyur?",
        "expected_slugs": ["insc-kandiyur-puravu-vari-revenue-charter", "place-tirukkandiyur-chola-revenue-secretariat"],
        "description": "Tirukkandiyur Revenue Charters & Sand-Inundation Tax Relief"
    },
    {
        "id": "REV-04",
        "query": "What was the bureaucratic hierarchy and administrative structure of the central Chola revenue ministry (Puravu-vari-thinaikalam)?",
        "expected_slugs": ["concept-puravu-vari-thinaikalam-revenue-ministry", "char-puravu-vari-thinaikkala-nayakan"],
        "description": "Puravu-Vari-Thinaikalam Central Revenue Bureaucracy"
    },
    {
        "id": "REV-05",
        "query": "How were district cadastral palm-leaf ledgers (Vari-pothagam) maintained, audited, and updated following land sales and transfers?",
        "expected_slugs": ["concept-vari-pothagam-cadastral-palm-leaf-ledgers", "text-periyapuranam-vari-pothagam-chola-revenue"],
        "description": "Vari-Pothagam Cadastral Ledgers & District Audit Security"
    },
    {
        "id": "REV-06",
        "query": "How did the Chola revenue administration classify agricultural soils into 12 Taram grades, distinguishing Nansey wetlands from Punsey drylands?",
        "expected_slugs": ["concept-chola-land-tax-classifications", "insc-tanjavur-ulagalantan-cadastral-survey"],
        "description": "Chola Land Tax Classifications & 12 Taram Soil Grading"
    },
    {
        "id": "REV-07",
        "query": "What was the imperial 16-span standard measuring rod (Ulagalantan-kol) used for cadastral land surveying and micro-acreage calculation?",
        "expected_slugs": ["concept-ulagalantan-16-span-standard-survey-rod", "char-ulagalantan-royal-land-surveyor"],
        "description": "Ulagalantan 16-Span Cadastral Survey Measuring Rod"
    },
    {
        "id": "REV-08",
        "query": "Where was the historic Chola revenue administrative center located on the Kaveri river where royal flood-remission charters are incised?",
        "expected_slugs": ["place-tirukkandiyur-chola-revenue-secretariat", "insc-kandiyur-puravu-vari-revenue-charter"],
        "description": "Tirukkandiyur Historic Administrative Center & Scriptorium"
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
    print("📜 CHOLA REVENUE SECRETARIAT & CADASTRAL AUDITING RAG BENCHMARK")
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
