#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Paleography, Epigraphical Scripts & Palm-Leaf Scriptoria Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "PAL-01",
        "query": "How does Tolkappiyam Ezhuthathikaram formulate the grammatical rule of the dot (Pulli) diacritic to suppress inherent vowel resonance on consonants?",
        "expected_slugs": ["text-tolkappiyam-ezhuthathikaram-phonology", "concept-tamil-brahmi-tamili-paleography"],
        "description": "Tolkappiyam Ezhuthathikaram Pulli Diacritic Rule"
    },
    {
        "id": "PAL-02",
        "query": "What is the historical significance of the 5th-century Pulankurichi rock inscription as a transitional bridge between Tamil-Brahmi and early Vatteluttu?",
        "expected_slugs": ["insc-pulankurichi-transition-epigraph", "concept-vatteluttu-evolution-and-syntax"],
        "description": "Pulankurichi Rock Epigraph Paleographical Transition"
    },
    {
        "id": "PAL-03",
        "query": "What are the earliest Tamil-Brahmi cave epigraphs and drip-ledge Jain ascetic bed charters discovered at Arittapatti near Madurai?",
        "expected_slugs": ["insc-arittapatti-chithar-malai-epigraph", "concept-tamil-brahmi-tamili-paleography"],
        "description": "Arittapatti Chithar-Malai Tamil-Brahmi Cave Charters"
    },
    {
        "id": "PAL-04",
        "query": "How did Tamil-Brahmi (Tamili) develop unique alphabetic graphemes for distinctive Dravidian phonemes like zha, la, rra, and na?",
        "expected_slugs": ["concept-tamil-brahmi-tamili-paleography", "text-tolkappiyam-ezhuthathikaram-phonology"],
        "description": "Tamil-Brahmi Orthography & Unique Dravidian Graphemes"
    },
    {
        "id": "PAL-05",
        "query": "Why did Vatteluttu become the dominant cursive administrative script across the Pandyan and Chera realms for cattle-raid hero stones (Nadukal)?",
        "expected_slugs": ["concept-vatteluttu-evolution-and-syntax", "insc-pulankurichi-transition-epigraph"],
        "description": "Vatteluttu Cursive Evolution & Hero Stone Epigraphy"
    },
    {
        "id": "PAL-06",
        "query": "How was the Grantha script developed by the Pallavas and Cholas to transcribe Sanskrit liturgical mantras and royal genealogies in copper plates?",
        "expected_slugs": ["concept-grantha-epigraphical-script"],
        "description": "Grantha Script Development & Sanskrit Prasasti Epigraphy"
    },
    {
        "id": "PAL-07",
        "query": "What was the traditional scribal method of boiling Palmyra palm leaves, incising them with an iron stylus (Ezhuthani), and applying lampblack oil?",
        "expected_slugs": ["concept-ezhuthani-stylus-palm-leaf-technology"],
        "description": "Ezhuthani Stylus Mechanics & Palmyra Manuscript Scribing"
    },
    {
        "id": "PAL-08",
        "query": "Where was the monumental 15-line Chendan-Kootran legal charter incised on a granite hillock displaying the earliest Vatteluttu land grants?",
        "expected_slugs": ["place-pulankurichi-rock-cut-scriptorium", "char-pulankurichi-royal-scribe"],
        "description": "Pulankurichi Granite Hill Scriptorium & Chendan-Kootran Charter"
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
    print("📜 ANCIENT TAMIL PALEOGRAPHY & SCRIPTS RAG BENCHMARK")
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
