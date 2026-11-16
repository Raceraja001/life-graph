#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Theater, Drama & Epigraphical Performing Arts Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "THE-01",
        "query": "How does Silappadikaram Kadaladukadai describe the 11 classical dance forms (Pathinondru Aadal) performed by Madhavi and the theatrical curtain mechanics?",
        "expected_slugs": ["text-silappadikaram-kadaladukadai-drama", "char-madhavi-natya-acharya"],
        "description": "Silappadikaram Kadaladukadai 11 Classical Dances & Curtains"
    },
    {
        "id": "THE-02",
        "query": "What are the lost Tamil dramatic treatise traditions like Seyithriyam, Muruval, and Sayantham cited by commentator Adiyarkkunallar?",
        "expected_slugs": ["text-arapatthan-arangan-nataka-treatise"],
        "description": "Ancient Tamil Nataka Manuals & Adiyarkkunallar Citations"
    },
    {
        "id": "THE-03",
        "query": "What are the inscriptional endowments for staging the annual Rajarajeswara Natakam play and the 400 Thalicheri dancers recorded at Thanjavur Brihadisvara?",
        "expected_slugs": ["insc-thanjavur-rajarajeswara-nataka-charter", "char-rajarajeswara-nataka-asiriyar"],
        "description": "Thanjavur Brihadisvara Rajarajeswara Natakam & Thalicheri Charters"
    },
    {
        "id": "THE-04",
        "query": "What are the eleven divine dances (Pathinondru Aadal) dividing into standing dances (Nindradal) and folk dances (Puzhithiyadal) in Tamil tradition?",
        "expected_slugs": ["concept-pathinondru-aadal-eleven-dances", "text-silappadikaram-kadaladukadai-drama"],
        "description": "Pathinondru Aadal Classical Dance Typology"
    },
    {
        "id": "THE-05",
        "query": "What is the symbolic meaning and royal honor of the Talaikol scepter awarded to the prima danseuse during her graduation performance (Arangetram)?",
        "expected_slugs": ["concept-talaikol-danseuse-sovereign-rod"],
        "description": "Talaikol Sovereign Dance Scepter & Arangetram Initiation"
    },
    {
        "id": "THE-06",
        "query": "How were the 400 Thalicheri temple dancers endowed with individual residential houses and annual paddy shares (Pangu) in Chola Thanjavur?",
        "expected_slugs": ["concept-thalicheri-temple-artist-guilds", "insc-thanjavur-rajarajeswara-nataka-charter"],
        "description": "Thalicheri Pendugal Endowed Houses & Pangu Land Shares"
    },
    {
        "id": "THE-07",
        "query": "What are the standard proscenium dimensions (8 by 7 by 1 koles) and curtain systems (Oru-muga and Iru-muga Ezhini) in ancient Tamil stagecraft (Aranga Amaithi)?",
        "expected_slugs": ["concept-aranga-amaithi-classical-stagecraft"],
        "description": "Aranga Amaithi Classical Stage Engineering & Curtain Mechanics"
    },
    {
        "id": "THE-08",
        "query": "Where was the grand open-air theatrical pavilion (Nataka Salai) situated in Thanjavur for enacting classical dance-dramas before the royal court?",
        "expected_slugs": ["place-thanjavur-rajarajeswara-nataka-arangan", "char-rajarajeswara-nataka-asiriyar"],
        "description": "Thanjavur Brihadisvara Theatrical Pavilion & Nataka Salai"
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
    print("🎭 ANCIENT TAMIL THEATER & PERFORMING ARTS RAG BENCHMARK")
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
