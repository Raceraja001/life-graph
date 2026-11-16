#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Temple Architecture, Stone Quarrying & Agamic Vastu Engineering Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "ARC-01",
        "query": "How do Mayamata and Agamic Silpa texts formulate sacred geometry, the 64- and 81-square Padavinyasa Vastu Mandalas, and vimana proportions?",
        "expected_slugs": ["text-mayamata-silparatna-tamil-agamic-vastu", "concept-agamic-vastu-mandala-temple-metrology"],
        "description": "Mayamata Agamic Vastu Mandalas & Proportional Metrology"
    },
    {
        "id": "ARC-02",
        "query": "What are the foundation epigraphs on the Thanjavur Brihadisvara basement commemorating chief architect Kunjaramallan Rajaraja Perunthatchan?",
        "expected_slugs": ["insc-thanjavur-peruvudaiyar-architect-charter", "char-kunjaramallan-rajaraja-perunthatchan-architect"],
        "description": "Brihadisvara Foundation Charters & Chief Architect Kunjaramallan"
    },
    {
        "id": "ARC-03",
        "query": "What are the engineering and structural innovations of the concave curvilinear octagonal vimana at Gangaikonda Cholapuram?",
        "expected_slugs": ["insc-gangaikonda-cholapuram-foundation-charters", "insc-thanjavur-peruvudaiyar-architect-charter"],
        "description": "Gangaikonda Cholapuram Curvilinear Vimana Architecture"
    },
    {
        "id": "ARC-04",
        "query": "How were multi-ton charnockite granite blocks cleaved using wooden swelling wedges and transported across the Kaveri on fluvial barges?",
        "expected_slugs": ["concept-granite-quarrying-and-kaveri-barge-transport", "char-ammangudi-granite-quarry-master"],
        "description": "Granite Quarrying, Wedge-Splitting & Kaveri Barge Logistics"
    },
    {
        "id": "ARC-05",
        "query": "What was the dry-stone masonry technique used in Chola temples using zero-mortar joints, mortise-and-tenon dowels, and corbelled vaulting?",
        "expected_slugs": ["concept-interlocking-dry-masonry-and-corbelled-vaulting", "insc-thanjavur-peruvudaiyar-architect-charter"],
        "description": "Zero-Mortar Dry Masonry & Corbelled Hollow-Core Vaulting"
    },
    {
        "id": "ARC-06",
        "query": "How did Agamic Vastu metrology determine astronomical true north using the Sanku gnomon shadow and allocate concentric temple padas?",
        "expected_slugs": ["concept-agamic-vastu-mandala-temple-metrology", "text-mayamata-silparatna-tamil-agamic-vastu"],
        "description": "Sanku Gnomon Orientation & Concentric Padavinyasa Grids"
    },
    {
        "id": "ARC-07",
        "query": "How was the 80-ton granite sikhara capstone hoisted to the 216-foot summit of Brihadisvara via a 6-kilometer earthen ramp?",
        "expected_slugs": ["concept-kudamuzha-and-sikhara-monolith-hoisting-ramps", "char-kunjaramallan-rajaraja-perunthatchan-architect"],
        "description": "Sikhara Monolith Hoisting & Sarappallam 6-Km Inclined Ramp"
    },
    {
        "id": "ARC-08",
        "query": "Where were the historic Chola imperial granite quarries and Kaveri barge loading basins located north of Kumbakonam?",
        "expected_slugs": ["place-ammangudi-chola-granite-quarries", "concept-granite-quarrying-and-kaveri-barge-transport"],
        "description": "Ammangudi Historic Chola Granite Quarries & Fluvial Basin"
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
    print("🏛️ TEMPLE ARCHITECTURE, QUARRYING & AGAMIC VASTU RAG BENCHMARK")
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
