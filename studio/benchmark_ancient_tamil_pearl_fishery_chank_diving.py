#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Pearl Fishery, Chank Diving & Gulf of Mannar Shell Carving Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'PRL-01', 'query': 'How does classical Tamil poetry in Maduraikkanchi describe the deep-sea pearl fisheries of Korkai and the diving techniques of the Parathavar clan?', 'expected_slugs': ['text-maduraikkanchi-korkai-pearl-diving-canon', 'char-korkai-chief-pearl-diver-parathavar-headman'], 'description': 'Maduraikkanchi Korkai Pearl Fishery & Parathavar Free-Diving Poetry'}, {'id': 'PRL-02', 'query': 'What are the ancient Pandya royal inscriptions and archaeological records from Korkai documenting the royal pearl monopoly and diving fleet permits?', 'expected_slugs': ['insc-korkai-pandya-pearl-fishery-royal-monopoly-charters', 'concept-gulf-of-mannar-pearl-diving-guild-corporations'], 'description': 'Korkai Pandya Royal Pearl Monopolies & Fleet Licensing Epigraphs'}, {'id': 'PRL-03', 'query': 'What do the archaeological excavations and epigraphs at Periyapattinam reveal regarding sacred chank cutting workshops and trans-oceanic bangle trade?', 'expected_slugs': ['insc-periyapattinam-chank-cutting-and-export-charters', 'place-periyapattinam-chank-cutting-haven'], 'description': 'Periyapattinam Sacred Chank Shell Cutting Guild & Bangle Charters'}, {'id': 'PRL-04', 'query': 'How did ancient Tamil free-divers execute rapid descents using heavy stone sinkers (Irangukal) and manage breath-holding while harvesting oysters?', 'expected_slugs': ['concept-free-diving-stone-weight-and-breath-holding-mechanics', 'text-maduraikkanchi-korkai-pearl-diving-canon'], 'description': 'Stone Sinker Irangukal Descent Mechanics & Breath-Holding Physiology'}, {'id': 'PRL-05', 'query': 'What was the technical sequence for slicing Turbinella pyrum chank shells into bangles using crescent saws and inlaying them with colored lacquer?', 'expected_slugs': ['concept-sacred-turbinella-pyrum-chank-sawing-and-bangle-lapidary', 'char-periyapattinam-master-chank-carver'], 'description': 'Turbinella pyrum Conch Crescent Sawing & Red Lacquer Inlay'}, {'id': 'PRL-06', 'query': 'How were harvested pearls graded in ancient Tamilakam using pierced copper sieve plates (Thulai-thattu) and evaluated for luster and sphericity?', 'expected_slugs': ['concept-pearl-grading-metrology-and-sieve-fractionation', 'concept-gulf-of-mannar-pearl-diving-guild-corporations'], 'description': 'Pierced Copper Sieve Fractionation & Pearl Luster Grading Metrology'}, {'id': 'PRL-07', 'query': 'How did the Parathavar diving corporations organize seasonal pearl diving camps (Salapam) in the Gulf of Mannar and administer diver welfare covenants?', 'expected_slugs': ['concept-gulf-of-mannar-pearl-diving-guild-corporations', 'char-korkai-chief-pearl-diver-parathavar-headman'], 'description': 'Parathavar Salapam Seasonal Base Camps & Maritime Welfare Covenants'}, {'id': 'PRL-08', 'query': 'Where was the historic chank harvesting haven of Periyapattinam located where massive debitage mounds of sawed conch shells were excavated?', 'expected_slugs': ['place-periyapattinam-chank-cutting-haven', 'concept-sacred-turbinella-pyrum-chank-sawing-and-bangle-lapidary'], 'description': 'Periyapattinam Historic Chank Harvesting Haven & Shell Mound Debitage'}]

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
    print("🎯 GULF OF MANNAR PEARL FISHERY & CHANK DIVING RAG BENCHMARK")
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
