#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Agriculture, Agronomy & Heritage Paddy Varieties Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "AGR-01",
        "query": "How does Porunararruppadai describe the incredible agricultural fertility of the Kaveri delta yielding a thousand kalams of paddy per veli?",
        "expected_slugs": ["text-porunararruppadai-velanmai-agronomy", "concept-sennel-and-heritage-paddy-cultivation"],
        "description": "Porunararruppadai Kaveri Wetland Agronomy & High Yields"
    },
    {
        "id": "AGR-02",
        "query": "What is the depiction in Malaipadukadam of mountain slope dryland agriculture, millet swiddens (Tinai), and bird scaring watchtowers?",
        "expected_slugs": ["text-malaipadukadam-siru-tinai-millet-farming", "concept-punsei-tinai-dryland-millet-polyculture"],
        "description": "Malaipadukadam Mountain Millet Agronomy & Swiddens"
    },
    {
        "id": "AGR-03",
        "query": "What are the imperial land survey inscriptions at Thanjavur Brihadisvara assessing revenue in standard Red Paddy (Sennel) measured by the Aadavallan marakkal?",
        "expected_slugs": ["insc-thanjavur-sennel-land-survey-charters", "char-kaveri-delta-paddy-surveyor"],
        "description": "Thanjavur Brihadisvara Sennel Cadastral Survey Charters"
    },
    {
        "id": "AGR-04",
        "query": "What were the primary indigenous heirloom rice varieties (Sennel, Vennel, Siru-sennel, Kadal-kazhuthu) cultivated in ancient Tamil wetlands?",
        "expected_slugs": ["concept-sennel-and-heritage-paddy-cultivation", "text-porunararruppadai-velanmai-agronomy"],
        "description": "Indigenous Heirloom Rice Biodiversity & Landrace Varieties"
    },
    {
        "id": "AGR-05",
        "query": "How did ancient Tamil dryland farmers practice rainfed polyculture by intercropping millets with symbiotic nitrogen-fixing legumes (Payaru)?",
        "expected_slugs": ["concept-punsei-tinai-dryland-millet-polyculture"],
        "description": "Punsei Dryland Millet Polyculture & Legume Nitrogen Fixation"
    },
    {
        "id": "AGR-06",
        "query": "What were the mechanics of Tamil wetland puddling using heavy timber ard-plows (Nanchi) with forged iron shares and green leaf manuring?",
        "expected_slugs": ["concept-uzhavu-plowing-and-marutham-pedology", "char-uzhava-perumakan-master-farmer"],
        "description": "Uzhavu Plowing Technology & Wetland Soil Puddling Mechanics"
    },
    {
        "id": "AGR-07",
        "query": "How was post-harvest grain processed on circular threshing floors (Kalam) by bullock trampling and preserved in moisture-proof straw silos (Kuthir)?",
        "expected_slugs": ["concept-kalam-threshing-and-agrarian-metrology"],
        "description": "Kalam Threshing Engineering & Straw Silo (Kuthir) Storage"
    },
    {
        "id": "AGR-08",
        "query": "Where was the fertile heartland of the Kaveri delta located where five alluvial river branches converged for intensive double-crop rice paddies?",
        "expected_slugs": ["place-thiruvaiyaru-kaveri-paddy-basin", "text-porunararruppadai-velanmai-agronomy"],
        "description": "Thiruvaiyaru Five-River Deltaic Rice Heartland"
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
    print("🌾 ANCIENT TAMIL AGRICULTURE & HERITAGE PADDY RAG BENCHMARK")
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
