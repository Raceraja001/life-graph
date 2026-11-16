#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Coastal Ports, Lighthouses & Maritime Customs Administration Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "CUS-01",
        "query": "How does Pattinappalai describe the customs clearance process, warehouse storage, and stamping of goods with the royal Chola tiger seal (Puli-p-pori) at Puhar port?",
        "expected_slugs": ["text-pattinappalai-customs-administration", "text-pattinappalai-textile-emporium", "concept-puli-p-pori-chola-customs-tiger-seal"],
        "description": "Pattinappalai Customs House & Puli-p-pori Royal Stamping"
    },
    {
        "id": "CUS-02",
        "query": "What is the structural description in Perumpanarruppadai of the towering brick lighthouse (Kalamkarai-vilakkam) guiding overseas ships at night to port?",
        "expected_slugs": ["text-perumpanarruppadai-kalamkarai-lighthouse", "concept-kalamkarai-vilakkam-beacon-architecture"],
        "description": "Perumpanarruppadai Kalamkarai-vilakkam Lighthouse Architecture"
    },
    {
        "id": "CUS-03",
        "query": "What archaeological artifacts including Roman amphorae, terra sigillata, intaglio gems, and brick warehouses were excavated at Arikamedu (Poduke)?",
        "expected_slugs": ["arch-arikamedu-indo-roman-emporium-excavation", "place-arikamedu-indo-roman-customs-wharf"],
        "description": "Arikamedu Indo-Roman Emporium & Wharf Excavation Artifacts"
    },
    {
        "id": "CUS-04",
        "query": "How did Chola customs officers apply the Puli-p-pori tiger seal on imported and exported merchandise before collecting import duties?",
        "expected_slugs": ["concept-puli-p-pori-chola-customs-tiger-seal", "char-puhar-sunga-adhikari"],
        "description": "Puli-p-pori Tiger-Seal Verification & Clearance Mechanics"
    },
    {
        "id": "CUS-05",
        "query": "How were ancient Tamil lighthouses (Kalamkarai-vilakkam) engineered with high brick watchtowers and oil fire beacons along the Coromandel coast?",
        "expected_slugs": ["concept-kalamkarai-vilakkam-beacon-architecture", "text-perumpanarruppadai-kalamkarai-lighthouse"],
        "description": "Kalamkarai-vilakkam Beacon Engineering & Coastal Warning Systems"
    },
    {
        "id": "CUS-06",
        "query": "How were foreign Mediterranean and Arab merchants accommodated in autonomous cosmopolitan quarters called Yavana-cheri near Tamil ports?",
        "expected_slugs": ["concept-yavana-cheri-foreign-merchant-quarters", "char-arikamedu-yavana-potter-merchant"],
        "description": "Yavana-cheri Foreign Enclaves & Extraterritorial Quarters"
    },
    {
        "id": "CUS-07",
        "query": "What were the administrative rates and collection procedures for transit customs tolls and maritime trade duties known as Thol-urimai or Sunkam?",
        "expected_slugs": ["concept-thol-urimai-customs-and-transit-duties", "char-puhar-sunga-adhikari"],
        "description": "Thol-urimai Customs Tolls, Sunkam Rates & Fiscal Duties"
    },
    {
        "id": "CUS-08",
        "query": "What archaeological evidence of Greco-Roman trade, rouletted pottery, and Vaigai river oceanic wharves was discovered at the Pandyan port of Alagankulam?",
        "expected_slugs": ["place-alagankulam-pandyan-oceanic-port"],
        "description": "Alagankulam Pandyan Port & Vaigai Estuary Oceanic Wharves"
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
    print("⚓ ANCIENT TAMIL COASTAL PORTS & MARITIME CUSTOMS RAG BENCHMARK")
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
