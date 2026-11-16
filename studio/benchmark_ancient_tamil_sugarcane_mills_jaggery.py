#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Sugar Engineering, Sugarcane Mills & Jaggery Crystallization Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'SGR-01', 'query': 'How does classical Sangam poetry in Purananuru depict King Adigaman introducing sugarcane and Perumpanarruppadai describe night-running crushing mills?', 'expected_slugs': ['text-purananuru-adigaman-sugarcane-origin-poetry', 'char-tagadur-master-sugarcane-millwright-aalai-kollan'], 'description': 'Purananuru Adigaman Sugarcane Introduction & Sangam Mill Hymns'}, {'id': 'SGR-02', 'query': 'What do the medieval Chola and Hoysala inscriptions at Thiruvannamalai record regarding annual taxes on sugarcane mills (Aalai-kaanam) and molasses tithes?', 'expected_slugs': ['insc-thiruvannamalai-sugar-mill-and-jaggery-tithes', 'char-kaveri-basin-sugar-boiling-artisan-vellam-kaachuvor'], 'description': 'Thiruvannamalai Sugarcane Mill Taxes & Temple Jaggery Tithes'}, {'id': 'SGR-03', 'query': 'What are the ancient rock inscriptions from Tagadur commemorating Adigaman royal sugarcane plantations, irrigation weirs, and millwright guilds?', 'expected_slugs': ['insc-tagadur-adigaman-sugarcane-endowment-charters', 'place-dharmapuri-adigaman-sugarcane-valley'], 'description': 'Tagadur Adigaman Sugarcane Cultivation & Irrigation Weir Charters'}, {'id': 'SGR-04', 'query': 'How were dual-roller wooden and iron sugarcane crushing mills (Karumbu-Aalai) engineered and driven by oxen sweeps in ancient Tamil agriculture?', 'expected_slugs': ['concept-hydraulic-and-oxen-driven-roller-sugarcane-crushing-mills', 'char-tagadur-master-sugarcane-millwright-aalai-kollan'], 'description': 'Oxen-Driven Roller Sugarcane Crushing Mill Mechanical Architecture'}, {'id': 'SGR-05', 'query': 'How was raw sugarcane juice clarified using wild okra mucilage and slaked lime, boiled in stepped flue furnaces, and crystallized into solid jaggery?', 'expected_slugs': ['concept-open-pan-sugar-boiling-clarification-and-jaggery-crystallization', 'char-kaveri-basin-sugar-boiling-artisan-vellam-kaachuvor'], 'description': 'Open-Pan Sugar Boiling Furnaces & Clarification Pyrotechnics'}, {'id': 'SGR-06', 'query': 'How was crystallized rock sugar candy (Kalkandu) produced in unglazed earthenware pots and used as an organic preservative matrix in Siddha medicine?', 'expected_slugs': ['concept-crystallized-sugar-candy-kalkandu-and-confectionery-arts', 'concept-open-pan-sugar-boiling-clarification-and-jaggery-crystallization'], 'description': 'Kalkandu Rock Sugar Crystallization & Siddha Confectionery Arts'}, {'id': 'SGR-07', 'query': 'How did ancient sugar merchant guilds transport liquid cane molasses in lac-sealed terracotta jars along the Kaveri river to coastal trade emporia?', 'expected_slugs': ['concept-sugar-merchant-guilds-and-monsoon-syrup-transport', 'place-dharmapuri-adigaman-sugarcane-valley'], 'description': 'Sugar Merchant Guild Logistics & Lac-Sealed Syrup Amphorae Transport'}, {'id': 'SGR-08', 'query': 'Where was the historic sugarcane valley of Tagadur situated that was celebrated as the ancient cradle of sugarcane agriculture in Tamilakam?', 'expected_slugs': ['place-dharmapuri-adigaman-sugarcane-valley', 'insc-tagadur-adigaman-sugarcane-endowment-charters'], 'description': 'Dharmapuri Tagadur Adigaman Sugarcane Valley & Historic Mills'}]

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
    print("🎯 ANCIENT TAMIL SUGAR ENGINEERING & JAGGERY CRYSTALLIZATION RAG BENCHMARK")
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
