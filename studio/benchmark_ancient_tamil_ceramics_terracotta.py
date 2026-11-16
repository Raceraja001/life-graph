#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Ceramic Technology, Terracotta Kilns & Urban Engineering Corpus
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
        "query": "How do Sangam poems in Narrinai and Purananuru describe the hereditary potter (Kuyavan) spinning wet alluvium on the rotating wheel (Thigiri) and crafting burial urns?",
        "expected_slugs": ["text-narrinai-kuyavan-potter-metaphors", "concept-kuyavan-potter-guild-tradition"],
        "description": "Sangam Potter Metaphors & Rotating Wheel (Thigiri) Technology"
    },
    {
        "id": "CER-02",
        "query": "What archaeological evidence of thin-walled Black-and-Red ware potsherds inscribed with Tamil-Brahmi personal names was excavated at Keeladi?",
        "expected_slugs": ["arch-keeladi-black-and-red-ware-pottery", "char-keeladi-master-ceramic-artisan"],
        "description": "Keeladi Black-and-Red Ware & Tamil-Brahmi Potsherds"
    },
    {
        "id": "CER-03",
        "query": "What two-piece ceramic moulds, hollow terracotta figurines, and roof-tile kilns were discovered during excavations at Perur on the Noyyal River?",
        "expected_slugs": ["arch-perur-terracotta-figurine-and-moulds", "place-perur-terracotta-craft-quarter"],
        "description": "Perur Terracotta Moulds & Votive Craft Excavations"
    },
    {
        "id": "CER-04",
        "query": "How does the inverted firing technique in reducing pyrotechnic atmospheres produce Black-and-Red Ware (BRW) with black interiors and red exteriors?",
        "expected_slugs": ["concept-black-and-red-ware-inverted-firing", "arch-keeladi-black-and-red-ware-pottery"],
        "description": "Black-and-Red Ware Inverted Firing Pyrotechnology"
    },
    {
        "id": "CER-05",
        "query": "What is the engineering mechanism of stacking interlocking terracotta rings in sandy floodplains to build ancient Tamil ring-wells (Urai-kinaru)?",
        "expected_slugs": ["concept-urai-kinaru-terracotta-ring-wells"],
        "description": "Urai-Kinaru Terracotta Ring-Well Urban Engineering"
    },
    {
        "id": "CER-06",
        "query": "How were ancient Tamil ceramic updraft kilns designed with subterranean fireboxes and perforated clay hearth grates to achieve 1000°C temperatures?",
        "expected_slugs": ["concept-ancient-tamil-ceramic-kiln-engineering", "concept-kuyavan-potter-guild-tradition"],
        "description": "Ancient Ceramic Updraft Kiln Thermodynamics"
    },
    {
        "id": "CER-07",
        "query": "What were the specialized hereditary responsibilities of the Kuyavan-Velar artisan guild in producing burial urns, domestic vessels, and votive horses?",
        "expected_slugs": ["concept-kuyavan-potter-guild-tradition", "text-narrinai-kuyavan-potter-metaphors"],
        "description": "Kuyavan-Velar Potter Guild Hereditary Responsibilities"
    },
    {
        "id": "CER-08",
        "query": "Where was the ancient Kongu industrial ceramic and terracotta figurine manufacturing quarter located along the Noyyal River basin?",
        "expected_slugs": ["place-perur-terracotta-craft-quarter", "char-perur-terracotta-sculptor"],
        "description": "Perur Industrial Ceramic Quarter on the Noyyal River"
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
    print("🏺 ANCIENT TAMIL CERAMICS & TERRACOTTA RAG BENCHMARK")
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
