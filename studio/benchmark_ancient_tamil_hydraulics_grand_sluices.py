#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Hydraulic Sluices, Grand Anicut & Cascade Tanks Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "HYD-01",
        "query": "How does Porunararruppadai celebrate Karikala Cholan taming the Kaveri floods through massive stone embankment engineering?",
        "expected_slugs": ["text-porunararruppadai-kallanai-delta-engineering", "char-karikala-chola-hydraulic-visionary"],
        "description": "Porunararruppadai Grand Anicut Civil Engineering Praise"
    },
    {
        "id": "HYD-02",
        "query": "What are the inscriptional and copper plate traditions documenting Karikala Chola's boulder diversion structure at the Grand Anicut (Kallanai)?",
        "expected_slugs": ["insc-kallanai-karikala-stone-embankment-charters", "char-karikala-chola-hydraulic-visionary", "char-karikala-cholan-water-engineer", "concept-kallanai-hydraulic-dam-mechanics"],
        "description": "Kallanai Epigraphical Records & Granite Embankment Charters"
    },
    {
        "id": "HYD-03",
        "query": "What are the imperial Chola inscriptions recording the excavation and maintenance of the 16-kilometer Veeranam Lake fed by the Vadavaru channel?",
        "expected_slugs": ["insc-veeranam-tank-rajendra-excavation-charter", "place-veeranam-lake-reservoir"],
        "description": "Veeranam Lake Rajendra Chola Excavation Charters"
    },
    {
        "id": "HYD-04",
        "query": "What is the fluid dynamic principle of the curved axis (329 meters) of the Grand Anicut in scouring silt down the Kollidam while feeding Kaveri canals?",
        "expected_slugs": ["concept-kallanai-hydraulic-dam-mechanics", "text-porunararruppadai-kallanai-delta-engineering"],
        "description": "Kallanai Curved Axis Hydrodynamics & Silt Scouring Mechanics"
    },
    {
        "id": "HYD-05",
        "query": "How does the indigenous Tamil Kumuzhi Thumbu underwater piston sluice use hydrostatic pressure to flush dead bottom silt while discharging clean surface water?",
        "expected_slugs": ["concept-kumuzhi-thumbu-piston-sluice-hydraulics", "char-chola-neerkatti-hydraulic-engineer"],
        "description": "Kumuzhi Thumbu Piston Sluice Dual-Orifice Self-Scouring"
    },
    {
        "id": "HYD-06",
        "query": "How were cascade tank networks (Erigal) engineered across drought-prone micro-catchments so surplus overflow chained into downstream reservoirs?",
        "expected_slugs": ["concept-cascade-tank-network-hydrography"],
        "description": "Cascade Tank Hydrography & Interconnected Watershed Networks"
    },
    {
        "id": "HYD-07",
        "query": "What is the architectural engineering of stepped stone surplus spillways (Kalingu) utilizing curved cills and grooved pillars with wooden flashboards?",
        "expected_slugs": ["concept-kalingu-surplus-escape-weir-architecture"],
        "description": "Kalingu Surplus Weir Architecture & Energy Dissipation"
    },
    {
        "id": "HYD-08",
        "query": "Where was the monumental 16-kilometer artificial lake created by Rajendra Chola located in Cuddalore district?",
        "expected_slugs": ["place-veeranam-lake-reservoir", "insc-veeranam-tank-rajendra-excavation-charter"],
        "description": "Veeranam Lake Monumental Reservoir Location"
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
    print("🌊 ANCIENT TAMIL HYDRAULIC SLUICES & GRAND ANICUT RAG BENCHMARK")
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
