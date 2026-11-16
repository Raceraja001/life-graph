#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Sangam Ceramic Engineering, Black-and-Red Ware & Updraft Pyrotechnics Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "CER-01",
        "query": "How does classical Sangam poetry in Narrinai and Ainkurunuru depict the master potter (Kalam-chey-kove) rotating the flywheel and burnishing red slips?",
        "expected_slugs": ["text-narrinai-kalam-chey-koyil-pottery-hymns", "char-keezhadi-master-ceramic-pyrotechnologist"],
        "description": "Sangam Ceramic Poetry & Fast Flywheel Kalam-Chey-Kove Hymns"
    },
    {
        "id": "CER-02",
        "query": "What are the early Tamil-Brahmi personal name inscriptions incised post-firing into Black-and-Red Ware ceramics excavated at Keezhadi?",
        "expected_slugs": ["insc-keezhadi-black-and-red-ware-graffiti-sherds", "char-keezhadi-master-ceramic-pyrotechnologist"],
        "description": "Keezhadi Inscribed Black-and-Red Ware Sherds & Mass Literacy Graffiti"
    },
    {
        "id": "CER-03",
        "query": "What are the imported Roman wine amphorae, terra sigillata, and Rouletted Ware sherds discovered at the port of Alagankulam?",
        "expected_slugs": ["insc-alagarankulam-rouletted-ware-graffiti-charters", "char-alagankulam-imported-ceramic-trader"],
        "description": "Alagankulam Rouletted Ware & Mediterranean Roman Amphorae Epigraphs"
    },
    {
        "id": "CER-04",
        "query": "How did the inverted kiln firing technique create the distinctive dual-color Black-and-Red Ware with carbonized black interiors and oxidized red exteriors?",
        "expected_slugs": ["concept-black-and-red-ware-inverted-firing", "concept-black-and-red-ware-inverted-firing-pyrotechnics", "concept-double-chamber-updraft-ceramic-kiln-engineering"],
        "description": "Black-and-Red Ware Inverted Kiln Firing & Reduction-Oxidation Pyrotechnics"
    },
    {
        "id": "CER-05",
        "query": "What was the mechanical forming sequence of Sangam ceramics using fast flywheels, clay levigation, and stone anvil-paddle body thinning?",
        "expected_slugs": ["concept-high-speed-flywheel-and-paddle-beating-pottery", "text-narrinai-kalam-chey-koyil-pottery-hymns"],
        "description": "High-Speed Flywheel Dynamics & Stone Anvil-Paddle Body Beating"
    },
    {
        "id": "CER-06",
        "query": "How was colloidal hematite slip applied and burnished with agate pebbles to produce mirror-like metallic lusters on ancient Tamil pottery?",
        "expected_slugs": ["concept-hematite-red-ochre-slip-and-cord-burnishing", "concept-black-and-red-ware-inverted-firing-pyrotechnics"],
        "description": "Hematite Red Ochre Slip & Agate Pebble Burnishing Chemistry"
    },
    {
        "id": "CER-07",
        "query": "How were double-chamber updraft pottery kilns engineered with sunken fireboxes and perforated flue grate floors to achieve 1,000°C temperatures?",
        "expected_slugs": ["concept-double-chamber-updraft-ceramic-kiln-engineering", "place-tirukkampuliyur-kaveri-ceramic-center"],
        "description": "Double-Chamber Updraft Ceramic Kiln Mechanics & Perforated Flues"
    },
    {
        "id": "CER-08",
        "query": "Where was the historic Kaveri basin ceramic center of Tirukkampuliyur located where stratified Black-and-Red Ware kilns were excavated?",
        "expected_slugs": ["place-tirukkampuliyur-kaveri-ceramic-center", "concept-double-chamber-updraft-ceramic-kiln-engineering"],
        "description": "Tirukkampuliyur Historic Kaveri Ceramic Kiln & Stratified Stratum Center"
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
    print("🏺 SANGAM CERAMIC ENGINEERING, BLACK-AND-RED WARE & KILNS RAG BENCHMARK")
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
