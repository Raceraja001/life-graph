#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Mineralogy, Gemology & Pearl Diver Guilds Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "GEM-01",
        "query": "How does the Ratna Pariksha classify precious gemstones including diamond, ruby, sapphire, and beryl according to crystal luster and mineral flaws?",
        "expected_slugs": ["text-ratna-pariksha-tamil-gemology", "concept-navaratna-gemological-classification"],
        "description": "Ratna Pariksha Tamil Gemology & Navaratna Mineralogy"
    },
    {
        "id": "GEM-02",
        "query": "What archaeological evidence of semi-precious bead factories, diamond-tipped micro-drills, and quartz furnaces was discovered at Kodumanal?",
        "expected_slugs": ["arch-kodumanal-beryl-quartz-lapidary-factory", "place-kodumanal-gem-lapidary-industrial-hub"],
        "description": "Kodumanal Excavations of Quartz Furnaces & Micro-Drills"
    },
    {
        "id": "GEM-03",
        "query": "What are the Pandyan royal pearl fishery charters and harvest division contracts regulating the Parathavar divers in the Gulf of Mannar?",
        "expected_slugs": ["insc-korkai-parathavar-pearl-charter", "concept-muthu-kuli-pearl-fishery-mechanics"],
        "description": "Korkai Pearl Fishery Charters & Parathavar Diver Agreements"
    },
    {
        "id": "GEM-04",
        "query": "How did Kodumanal lapidary craftsmen engineer double-pointed diamond drill bits to pierce hard beryl and carnelian beads with 0.5 mm holes?",
        "expected_slugs": ["concept-kodumanal-diamond-tipped-micro-drilling", "concept-kodumanal-gemstone-lapidary", "arch-kodumanal-beryl-quartz-lapidary-factory"],
        "description": "Kodumanal Diamond-Tipped Micro-Drilling Technology"
    },
    {
        "id": "GEM-05",
        "query": "What was the deep-sea free diving process (Muthu-kuli) using sinking stones, coir nets, and shark-binding charms in the ancient pearl fisheries?",
        "expected_slugs": ["concept-muthu-kuli-pearl-fishery-mechanics", "insc-korkai-parathavar-pearl-charter"],
        "description": "Muthu-Kuli Free Diving Mechanics & Sinking Stone Technique"
    },
    {
        "id": "GEM-06",
        "query": "Where were the major mineral mining belts for beryl (Vaidhurya) and sapphires located in the Kongu region of ancient Tamilakam?",
        "expected_slugs": ["concept-navaratna-gemological-classification", "place-kodumanal-gem-lapidary-industrial-hub"],
        "description": "Navaratna Gemological Belts in Kongu Nadu (Beryl & Sapphire)"
    },
    {
        "id": "GEM-07",
        "query": "How was the Parathavar maritime guild organized to manage coastal pearl fisheries, salt manufacturing, and naval defense for the Pandyan kings?",
        "expected_slugs": ["concept-parathavar-marine-guild-organization", "char-korkai-muthu-kuli-thalavan"],
        "description": "Parathavar Maritime Guild Organization & Coastal Sovereignty"
    },
    {
        "id": "GEM-08",
        "query": "Why was the ancient city of Kodumanam (Kodumanal) on the Noyyal river celebrated in Pathitrupathu as the premier gem lapidary hub?",
        "expected_slugs": ["place-kodumanal-gem-lapidary-industrial-hub", "char-kodumanal-master-lapidary-artisan"],
        "description": "Kodumanal Industrial Gem Factory & Ancient Lapidary Metropolis"
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
    print("💎 ANCIENT TAMIL MINERALOGY, GEMOLOGY & PEARL DIVER GUILDS RAG BENCHMARK")
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
