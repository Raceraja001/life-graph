#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Classical Astronomy, Nakshatra Calendrics & Inscriptional Solar Eclipses Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "AST-01",
        "query": "How does the Kanakkan Parani and Tamil astronomical canon formulate Nakshatra asterisms, the 60-Nazhikai daily division, and solar transits?",
        "expected_slugs": ["text-kanakkan-parani-astronomical-nakshatra-canon", "concept-nakshatra-27-asterism-calendrical-metrology"],
        "description": "Kanakkan Parani Nakshatra Calendrics & 60-Nazhikai Division"
    },
    {
        "id": "AST-02",
        "query": "What are the inscriptional records on the Tiruvidaimarudur temple walls documenting exact solar eclipses (Surya-grahana) correlated with regnal years?",
        "expected_slugs": ["insc-tiruvidaimarudur-solar-eclipse-charters", "char-tiruvidaimarudur-eclipse-assayer"],
        "description": "Tiruvidaimarudur Solar Eclipse Charters & Astronomical Dating"
    },
    {
        "id": "AST-03",
        "query": "What are the planetary conjunctions and Panchanga five-limb astronomical ephemerides recorded in the Kudumiyamalai rock epigraphs?",
        "expected_slugs": ["insc-kudumiyamalai-astronomical-ephemeris-records", "concept-meykkirthi-astronomical-regnal-synchronization"],
        "description": "Kudumiyamalai Planetary Conjunctions & Panchanga Ephemerides"
    },
    {
        "id": "AST-04",
        "query": "How did ancient Tamil astronomers understand eclipse mechanics as orbital shadow syzygies of the Earth and Moon at Rahu-Ketu nodes?",
        "expected_slugs": ["concept-solar-and-lunar-eclipse-epigraphical-reckoning", "insc-tiruvidaimarudur-solar-eclipse-charters"],
        "description": "Rahu-Ketu Shadow Syzygy Mechanics & Scientific Eclipse Prediction"
    },
    {
        "id": "AST-05",
        "query": "How was the Tamil sidereal solar calendar structured into twelve solar months commencing at Sankranti transits across the 27 Nakshatras?",
        "expected_slugs": ["concept-nakshatra-27-asterism-calendrical-metrology", "text-kanakkan-parani-astronomical-nakshatra-canon"],
        "description": "Sidereal Solar-Lunar Calendar & 27 Lunar Asterisms"
    },
    {
        "id": "AST-06",
        "query": "How did royal Chola scribes use multi-variable astronomical date formulas (Meykkirthi) to create unalterable historical timestamps?",
        "expected_slugs": ["concept-meykkirthi-astronomical-regnal-synchronization", "char-kanakkathikari-astronomical-epigrapher"],
        "description": "Meykkirthi Multi-Variable Astronomical Redundancy Codes"
    },
    {
        "id": "AST-07",
        "query": "What were the physical timekeeping instruments used in ancient Tamilakam: the Sanku shadow gnomon and the Neer-Nazhikai water clepsydra?",
        "expected_slugs": ["concept-sanku-gnomon-and-neer-nazhikai-water-clocks", "char-kanakkathikari-astronomical-epigrapher"],
        "description": "Sanku Shadow Gnomons & Neer-Nazhikai Copper Clepsydras"
    },
    {
        "id": "AST-08",
        "query": "Where was the historic Kaveri astronomical sanctuary located where Chola solar eclipse inscriptions and solar observation audits took place?",
        "expected_slugs": ["place-tiruvidaimarudur-astronomical-epigraph-center", "insc-tiruvidaimarudur-solar-eclipse-charters"],
        "description": "Tiruvidaimarudur Historic Kaveri Solar Observatory Center"
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
    print("🔭 CLASSICAL TAMIL ASTRONOMY, NAKSHATRAS & ECLIPSES RAG BENCHMARK")
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
