#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Copperplate Epigraphy, Cire-Perdue Bronze Casting & Scribe Seals Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'BRZ-01', 'query': 'How does classical Tamil literature in Silappadikaram describe coppersmith guilds (Sembu-seivor), bronze icon casters, and beeswax sculpture modeling?', 'expected_slugs': ['text-silappadikaram-bronze-casting-and-wax-modeling-canon', 'char-swamimalai-master-bronze-sthapati-silpa-achariyan'], 'description': 'Silappadikaram Bronze Metallurgy, Wax Modeling & Lost-Wax Canon'}, {'id': 'BRZ-02', 'query': 'What are the historic Velvikkudi copper plates of Pandya King Nedunjadaiyan documenting land grant restitution, scribal colophons, and twin-fish bronze ring seals?', 'expected_slugs': ['insc-velvikkudi-pandya-copperplate-grant-charters', 'char-madurai-royal-copperplate-scribe-sasana-karan'], 'description': 'Velvikkudi Early Pandya Imperial Copperplate Grant & Scribe Seals'}, {'id': 'BRZ-03', 'query': 'What are the giant Karandai copper plates of Rajendra Chola I weighing 107 kg and secured with a 10-kg bronze ring bearing the imperial tiger-fish seal?', 'expected_slugs': ['insc-karandai-chola-copperplate-charters', 'place-karandai-chola-scriptorium-haven'], 'description': 'Karandai Imperial Chola Giant Copperplate Set & Royal Ring-Seal Charters'}, {'id': 'BRZ-04', 'query': 'What was the complete metallurgical sequence of Cire-Perdue lost-wax bronze idol casting using multi-layer Kaveri clay molds and Panchaloha alloy pouring?', 'expected_slugs': ['concept-cire-perdue-lost-wax-bronze-idol-casting-mechanics', 'char-swamimalai-master-bronze-sthapati-silpa-achariyan'], 'description': 'Cire-Perdue Lost-Wax Bronze Casting Mechanics & Panchaloha Metallurgy'}, {'id': 'BRZ-05', 'query': 'How were royal copperplate sheets forged, annealed, leveled with raised rim margins, and incised with sharp steel styluses in ancient Tamil chanceries?', 'expected_slugs': ['concept-copperplate-rolling-beating-and-incising-metrology', 'insc-karandai-chola-copperplate-charters'], 'description': 'Copperplate Sheet Hammering, Surface Annealing & Stylus Engraving'}, {'id': 'BRZ-06', 'query': 'How were royal dynastic ring seals cast in bronze using lost-wax and hot-peened with tamper-evident rivets to prevent fraudulent plate insertions?', 'expected_slugs': ['concept-royal-dynastic-ring-seals-and-lost-wax-emblem-casting', 'insc-velvikkudi-pandya-copperplate-grant-charters'], 'description': 'Royal Dynastic Ring-Seals, Intaglio Signets & Anti-Forgery Rivet Metallurgy'}, {'id': 'BRZ-07', 'query': 'How were coppersmith and bronze artisan guilds (Kanchu-karar) organized in ancient Tamilakam and what were the honors of imperial court epigraphists?', 'expected_slugs': ['concept-coppersmith-and-engraver-guild-corporations', 'char-swamimalai-master-bronze-sthapati-silpa-achariyan'], 'description': 'Coppersmith Guild Corporations Kanchu-Karar & Scribe Titles'}, {'id': 'BRZ-08', 'query': 'Where was the royal Chola scriptorium and archive haven of Karandai located near Thanjavur where monumental copperplate sets were engineered and preserved?', 'expected_slugs': ['place-karandai-chola-scriptorium-haven', 'insc-karandai-chola-copperplate-charters'], 'description': 'Karandai Chola Royal Scriptorium & Copperplate Archive Haven'}]

def get_query_embedding(query_str: str) -> list[float]:
    payload = json.dumps({
        "model": "bge-m3:latest",
        "prompt": query_str
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]

def main():
    print("=" * 75)
    print("🎯 COPPERPLATE EPIGRAPHY & CIRE-PERDUE BRONZE CASTING RAG BENCHMARK")
    print("=" * 75)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_CASES)

    for case in BENCHMARK_CASES:
        qid = case["id"]
        query = case["query"]
        expected = case["expected_slugs"]
        desc = case["description"]

        print(f"\n[{qid}] {desc}")
        print(f"  Query: \"{query}\"")
        print(f"  Expected: {expected}")

        q_emb = get_query_embedding(query)
        emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"

        cur.execute("""
            SELECT 
                node_slug,
                title,
                content,
                1 - (embedding <=> %s::vector) as cosine_sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector ASC
            LIMIT 3;
        """, (emb_str, emb_str))

        rows = cur.fetchall()
        if not rows:
            print("  ❌ No results returned!")
            continue

        top1_slug = rows[0][0]
        top1_sim = rows[0][3]

        if top1_slug in expected:
            passed += 1
            print(f"  Top-1: {top1_slug} (Cosine Sim: {top1_sim:.4f}) -> ✅ PASS")
        else:
            print(f"  Top-1: {top1_slug} (Cosine Sim: {top1_sim:.4f}) -> ❌ FAIL")
            print("  Top 3 Returned:")
            for i, r in enumerate(rows, 1):
                print(f"    {i}. {r[0]} ({r[3]:.4f}) - {r[1]}")

    accuracy = (passed / total) * 100
    print("\n" + "=" * 75)
    print(f"🎯 BENCHMARK RESULTS: {passed}/{total} Passed ({accuracy:.1f}% Top-1 Accuracy)")
    print("=" * 75 + "\n")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
