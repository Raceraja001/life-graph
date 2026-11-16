#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Indo-Pacific Glassmaking, Drawn Micro-Beads & Marine Emporia Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "GLS-01",
        "query": "How do the Periplus Maris Erythraei and Sangam poetic lexica document maritime trade in drawn glass beads (Lithina Hualos) from Poduke?",
        "expected_slugs": ["text-periplus-maris-erythraei-glass-bead-cargoes", "char-mutisalah-maritime-bead-merchant"],
        "description": "Periplus Lithina Hualos & Kol-Mani Maritime Cargoes"
    },
    {
        "id": "GLS-02",
        "query": "What are the Tamil-Brahmi inscribed potsherds and glass guild graffiti excavated from the beadmaking workshops of Arikamedu?",
        "expected_slugs": ["insc-arikamedu-pottery-and-glass-guild-graffiti", "char-poduke-master-glass-furnace-blower"],
        "description": "Arikamedu Tamil-Brahmi Glass Guild Graffiti & Poduke Workshop Marks"
    },
    {
        "id": "GLS-03",
        "query": "What are the medieval glass furnace epigraphs and beadmaker guild charters recorded at Kudikadu near Cuddalore?",
        "expected_slugs": ["insc-kudikadu-glass-bead-furnace-charters", "place-kudikadu-coastal-glass-bead-furnaces"],
        "description": "Kudikadu Glass Furnace Epigraphs & Beadmaker Guild Charters"
    },
    {
        "id": "GLS-04",
        "query": "How was the Indo-Pacific drawn glass bead pyrotechnic technique executed using Lada mandrels, long hollow tubes, and ash tumbling?",
        "expected_slugs": ["concept-indo-pacific-drawn-glass-bead-pyrotechnics", "char-poduke-master-glass-furnace-blower"],
        "description": "Indo-Pacific Drawn Glass Tube Mechanics & Lada Pyrotechnics"
    },
    {
        "id": "GLS-05",
        "query": "Why were Arikamedu opaque red Mutisalah micro-beads used as a universal maritime trade currency across Africa, Southeast Asia, and Japan?",
        "expected_slugs": ["concept-arikamedu-red-mutisalah-bead-trade-network", "char-mutisalah-maritime-bead-merchant"],
        "description": "Red Mutisalah Micro-Beads & Global Indian Ocean Currency Network"
    },
    {
        "id": "GLS-06",
        "query": "What is the distinctive mineral soda-alumina (m-Na-Al) geochemical recipe of ancient Tamil glass colored with cobalt, copper, and manganese?",
        "expected_slugs": ["concept-mineral-soda-alumina-glass-chemical-recipes", "concept-indo-pacific-drawn-glass-bead-pyrotechnics"],
        "description": "Mineral Soda-Alumina (m-Na-Al) Chemical Recipes & Geochemical Fingerprints"
    },
    {
        "id": "GLS-07",
        "query": "What was the function of multi-grooved granite slabs, bow-drills, and abrasive slurries in mass-polishing and stringing glass micro-beads?",
        "expected_slugs": ["concept-grooved-stone-bead-polishing-and-stringing", "concept-indo-pacific-drawn-glass-bead-pyrotechnics"],
        "description": "Grooved Stone Bead Polishing Slabs & Bow-Drill Perforations"
    },
    {
        "id": "GLS-08",
        "query": "Where was the historic Coromandel coastal glass furnace site of Kudikadu located that sustained Indo-Pacific beadmaking after Arikamedu?",
        "expected_slugs": ["place-kudikadu-coastal-glass-bead-furnaces", "insc-kudikadu-glass-bead-furnace-charters"],
        "description": "Kudikadu Historic Coastal Glass Bead Manufacturing Emporium"
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
    print("🔮 INDO-PACIFIC GLASSMAKING & MUTISALAH BEADS RAG BENCHMARK")
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
