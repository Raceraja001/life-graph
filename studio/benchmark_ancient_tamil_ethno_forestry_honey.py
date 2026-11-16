#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Ethno-Forestry, Honey Harvesting & Mountain Biospheres Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "FOR-01",
        "query": "How does Kurunjippattu describe high-cliff wild honey harvesting (Malai-then) where climbers descend vertical precipices at night using rope ladders?",
        "expected_slugs": ["text-kurunjippattu-honey-harvest-and-hill-flora", "concept-malai-then-cliff-honey-harvesting-mechanics"],
        "description": "Kurunjippattu Cliff Wild Honey Harvesting Poetry"
    },
    {
        "id": "FOR-02",
        "query": "What mountain aromatics, seasoned aloeswood (Akil), and sandalwood are documented in Sirupanarruppadai as harvested from high-elevation forests?",
        "expected_slugs": ["text-sirupanarruppadai-forest-fragrances", "concept-akil-chandanam-aromatic-silviculture"],
        "description": "Sirupanarruppadai Montane Aromatics & Hardwood Silviculture"
    },
    {
        "id": "FOR-03",
        "query": "What are the rock epigraphs in the Western Ghats recording treaties between plains kings and hill forest chieftains over honey, ivory, and spice tributes?",
        "expected_slugs": ["insc-anaimalai-forest-chieftain-charters"],
        "description": "Anaimalai Hill Chieftain Charters & Forest Treaties"
    },
    {
        "id": "FOR-04",
        "query": "How did indigenous honey gatherers engineer flexible high-tensile rope ladders (Aani-kodi) to harvest honey from giant rock bees (Apis dorsata)?",
        "expected_slugs": ["concept-malai-then-cliff-honey-harvesting-mechanics", "char-kani-mountain-honey-master"],
        "description": "Malai-Then Cliff-Drop Rope Ladder Engineering & Apiculture"
    },
    {
        "id": "FOR-05",
        "query": "What was the water-curing and marsh-burial process used to season dense, fragrant aloeswood (Akil) and sandalwood for overseas export?",
        "expected_slugs": ["concept-akil-chandanam-aromatic-silviculture", "text-sirupanarruppadai-forest-fragrances"],
        "description": "Aromatic Hardwood Silviculture & Water Curing Mechanics"
    },
    {
        "id": "FOR-06",
        "query": "Why were defensive thorn forests (Kaval-kadu or Milai) cultivated around ancient Tamil fortresses as anti-cavalry military barriers?",
        "expected_slugs": ["concept-kaval-kadu-defensive-border-forests", "char-kaval-kadu-border-guardian"],
        "description": "Kaval-Kadu (Milai) Defensive Border Thorn Forests"
    },
    {
        "id": "FOR-07",
        "query": "What traditional ethnobotanical knowledge did Western Ghats tribes (Kanikkar) preserve regarding wild tubers (Valli-kizhangu) and snakebite antidotes?",
        "expected_slugs": ["concept-kani-tribal-ethnobotany-and-medicines"],
        "description": "Kani Ethnobotany, Wild Tubers & Anti-Venom Medicine"
    },
    {
        "id": "FOR-08",
        "query": "Where is the famous mountain plateau ruled by Sangam chieftain Valvil Ori celebrated for dense medicinal flora, wild honey, and sacred groves?",
        "expected_slugs": ["place-kollimalai-aromatic-and-medicinal-biosphere"],
        "description": "Kolli Hills (Kollimalai) Montane Flora & Wild Honey Biosphere"
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
    print("🌲 ANCIENT TAMIL ETHNO-FORESTRY & MOUNTAIN BIOSPHERES RAG BENCHMARK")
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
