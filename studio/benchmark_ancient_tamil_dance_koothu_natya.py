#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Classical Dance, Koothu Traditions & Natya Metrology Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "DAN-01",
        "query": "How does the Silappadikaram Arangetru Kadhai define the classical Tamil dance canon, the 11 sacred dances (Aadal), and stage debut protocols?",
        "expected_slugs": ["text-silappadikaram-arangetru-kadhai-dance-canon", "char-madhavi-classical-natya-virtuoso"],
        "description": "Silappadikaram Arangetru Kadhai & 11 Sacred Aadal Dances"
    },
    {
        "id": "DAN-02",
        "query": "What are the inscriptional records on the Brihadisvara north wall listing 400 temple dancers (Talicceri Pendir) and their individual land endowments?",
        "expected_slugs": ["insc-thanjavur-talicceri-pendir-dance-charter", "place-thanjavur-talicceri-peruntheru-quarters"],
        "description": "Thanjavur Talicceri Pendir Inscriptions & 400 Dancers Roll"
    },
    {
        "id": "DAN-03",
        "query": "What are the 108 Natya Karana sculptural bas-reliefs and accompanying inscribed label verses on the Chidambaram Nataraja gopurams?",
        "expected_slugs": ["insc-chidambaram-natya-karana-sculptural-epigraphs", "concept-adavu-and-karana-biomechanics-metrology"],
        "description": "Chidambaram 108 Natya Karana Sculptures & Inscribed Labels"
    },
    {
        "id": "DAN-04",
        "query": "What was the physical biomechanics of Tamil dance coordinating foot strikes (Tattu), hand hasthas, and the 108 Karana kinetic units?",
        "expected_slugs": ["concept-adavu-and-karana-biomechanics-metrology", "insc-chidambaram-natya-karana-sculptural-epigraphs"],
        "description": "Adavu & Karana Biomechanics & Kinetic Triad"
    },
    {
        "id": "DAN-05",
        "query": "How did Chola Tala metrology formulate rhythm through Solkattu syllables, Jati fractions, and Kudamuzha drum polyrhythms?",
        "expected_slugs": ["concept-chola-tala-metrology-and-solkattu-rhythms", "char-thanjavur-tala-asiriyar-rhythm-director"],
        "description": "Chola Tala Metrology, Solkattu & Fractional Jati Mathematics"
    },
    {
        "id": "DAN-06",
        "query": "What were the architectural dimensions, bamboo measuring staff (En-kol), and three mechanical silk curtain systems of the ancient Tamil Arangam stage?",
        "expected_slugs": ["concept-arangam-theatrical-stage-architecture", "text-silappadikaram-arangetru-kadhai-dance-canon"],
        "description": "Arangam En-Kol Stage Architecture & Triple Silk Curtains"
    },
    {
        "id": "DAN-07",
        "query": "How did the imperial Chola Talicceri residential quarter system endow artists with hereditary agrarian shares (Pangu) and guild autonomy?",
        "expected_slugs": ["concept-talicceri-dance-quarters-and-paddy-endowments", "insc-thanjavur-talicceri-pendir-dance-charter"],
        "description": "Talicceri Urban Patronage System & Hereditary Pangu Land Grants"
    },
    {
        "id": "DAN-08",
        "query": "Where was the historic Thanjavur Talicceri grand boulevard situated where 400 royal temple dancers and musicians resided?",
        "expected_slugs": ["place-thanjavur-talicceri-peruntheru-quarters", "insc-thanjavur-talicceri-pendir-dance-charter"],
        "description": "Thanjavur Talicceri Peruntheru Cultural Artist Boulevard"
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
    print("💃 CLASSICAL DANCE, KOOTHU TRADITIONS & NATYA METROLOGY RAG BENCHMARK")
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
