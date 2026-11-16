#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Textiles, Silk Weaving & Dyeing Chemistry Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "TEX-01",
        "query": "How does Porunararruppadai describe the viper-skin metric (Pambu urithanna madi) and invisible yarn count of Sangam muslins?",
        "expected_slugs": ["text-porunararruppadai-textile-weaving", "concept-uraiyur-madurai-muslin-weaving"],
        "description": "Porunararruppadai Viper-Skin Metric & Invisible Weave"
    },
    {
        "id": "TEX-02",
        "query": "What are the Argaritic muslins from Uraiyur documented in the 1st-century CE Periplus Maris Erythraei and their value in Rome?",
        "expected_slugs": ["text-periplus-muslin-exports", "concept-textile-trade-indo-roman-monopoly", "char-uriyur-mudukanan-sathanar"],
        "description": "Periplus Argaritic Muslins from Uraiyur & Roman Luxury Trade"
    },
    {
        "id": "TEX-03",
        "query": "How did Chola customs officers at Poompuhar stamp textile bales with the imperial Tiger Seal (Puli-p-pori) in Pattinappalai?",
        "expected_slugs": ["text-pattinappalai-textile-emporium", "concept-textile-trade-indo-roman-monopoly"],
        "description": "Pattinappalai Poompuhar Customs Tiger Seal on Textile Bales"
    },
    {
        "id": "TEX-04",
        "query": "What are the inscriptional privileges, loom taxes (Thari-irai), and guild regulations of the Saliyar and Kaikkolar in Kanchipuram?",
        "expected_slugs": ["insc-kanchipuram-saliga-guild-charter", "concept-kanchipuram-chola-silk-guilds", "char-perunkol-saligan-master-weaver"],
        "description": "Kanchipuram Saliyar & Kaikkolar Loom Charters (Thari-irai)"
    },
    {
        "id": "TEX-05",
        "query": "What is the biochemical mechanism of anaerobic vat fermentation of indigo (Avuri) and atmospheric oxidation in ancient Tamil dyeing?",
        "expected_slugs": ["concept-indigo-madder-vat-dyeing"],
        "description": "Indigo (Avuri) Vat Fermentation & Atmospheric Oxidation Chemistry"
    },
    {
        "id": "TEX-06",
        "query": "How did ancient weavers in Uraiyur and Madurai use pit looms (Kuzhi-t-thari) and spindle whorls to weave 120s count Karunganni cotton?",
        "expected_slugs": ["concept-uraiyur-madurai-muslin-weaving", "text-porunararruppadai-textile-weaving"],
        "description": "Uraiyur-Madurai Pit Looms (Kuzhi-t-thari) & Karunganni Cotton"
    },
    {
        "id": "TEX-07",
        "query": "What is the Korvai interlocking warp technique and three-shuttle weaving process in authentic Kanchipuram silk saris?",
        "expected_slugs": ["concept-kanchipuram-chola-silk-guilds", "char-perunkol-saligan-master-weaver"],
        "description": "Kanchipuram Korvai Interlocking Warp & Three-Shuttle Mechanics"
    },
    {
        "id": "TEX-08",
        "query": "Where was the famous Aruvai Veethi textile wholesale merchant avenue situated in the Pandyan capital of Madurai?",
        "expected_slugs": ["place-madurai-aruvai-veethi", "concept-uraiyur-madurai-muslin-weaving"],
        "description": "Madurai Aruvai Veethi Classical Textile Merchant Avenue"
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
    print("🧵 ANCIENT TAMIL TEXTILES, SILK WEAVING & DYEING CHEMISTRY RAG BENCHMARK")
    print("=" * 75)

    for case in BENCHMARK_CASES:
        vec = get_embedding(case["query"])
        vec_literal = "[" + ",".join(str(x) for x in vec) + "]"

        # Retrieve top 5 closest chunks
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
