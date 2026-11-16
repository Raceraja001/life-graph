#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Numismatics, Imperial Bullion & Royal Minting Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "NUM-01",
        "query": "How does Kanakkathikaram formulate mathematical rules for testing gold purity (Maatru) using touchstones and botanical seed weights (Manjadi, Kunrimani)?",
        "expected_slugs": ["text-kanakkathikaram-bullion-metrology", "concept-urai-kal-touchstone-gold-assaying"],
        "description": "Kanakkathikaram Gold Fineness & Touchstone Mathematical Rules"
    },
    {
        "id": "NUM-02",
        "query": "What are the imperial Brihadisvara inscriptional standards governing endowments in high-purity Madhurantakan-madai gold coins?",
        "expected_slugs": ["insc-thanjavur-madhurantakan-madai-charters", "concept-madhurantakan-madai-gold-standard"],
        "description": "Thanjavur Brihadisvara Madhurantakan-Madai Currency Standards"
    },
    {
        "id": "NUM-03",
        "query": "What are the state mint (Akkasalai) charters and royal minter accountability rules recorded in the rock epigraphs of Kudumiyamalai?",
        "expected_slugs": ["insc-kudumiyamalai-akkasalai-mint-charter", "place-kudumiyamalai-pandyan-minting-station"],
        "description": "Kudumiyamalai Epigraphs & State Akkasalai Mint Governance"
    },
    {
        "id": "NUM-04",
        "query": "What was the weight standard (1 Kalanju), gold fineness (9.5 to 10 Maatru), and exchange ratio of the imperial Chola Madhurantakan-madai coin?",
        "expected_slugs": ["concept-madhurantakan-madai-gold-standard", "insc-thanjavur-madhurantakan-madai-charters"],
        "description": "Madhurantakan-Madai Gold Standard & Metrological Precision"
    },
    {
        "id": "NUM-05",
        "query": "How were bronze coin dies (Kasa-achu), planchet blanking, and crucible melting engineered in the royal Akkasalai mints?",
        "expected_slugs": ["concept-akkasalai-state-mint-mechanics", "char-akkasalai-nayakan-master-minter"],
        "description": "Akkasalai Minting Pyrotechnics & Die-Striking Mechanics"
    },
    {
        "id": "NUM-06",
        "query": "What was the analytical streak method using black basanite touchstones (Urai-kal) and standard needles to detect debased gold alloys?",
        "expected_slugs": ["concept-urai-kal-touchstone-gold-assaying", "char-thanjavur-kasu-paritchakar-coin-assayer"],
        "description": "Urai-Kal Basanite Touchstone Assaying & Streak Analysis"
    },
    {
        "id": "NUM-07",
        "query": "How was the iconic Ceylon-man type standing king motif on the Rajaraja Kasu transmitted across South India and the Indian Ocean?",
        "expected_slugs": ["concept-ceylon-man-type-coinage-transmission"],
        "description": "Ceylon-Man Type Standing King Coinage Arc (Rajaraja Kasu)"
    },
    {
        "id": "NUM-08",
        "query": "Where was the historic rock-cut temple site in Pudukkottai located where Pandyan state coin dies and Akkasalai mint records are preserved?",
        "expected_slugs": ["place-kudumiyamalai-pandyan-minting-station", "insc-kudumiyamalai-akkasalai-mint-charter"],
        "description": "Kudumiyamalai Historic Pandyan Minting Hub & Sanctuary"
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
    print("🪙 ANCIENT TAMIL NUMISMATICS, BULLION & MINTING RAG BENCHMARK")
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
