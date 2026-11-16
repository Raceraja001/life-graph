#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Beekeeping, Forest Honey Harvesting & Wax Casting Guilds Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'HON-01', 'query': 'How does classical Sangam poetry in Kurunthokai and Akananuru depict Kurinji honey hunters scaling sheer mountain cliffs using suspended bamboo ladders?', 'expected_slugs': ['text-kurunthokai-cliff-honey-harvesting-poetry', 'char-jawadhu-hills-master-honey-hunter-theyn-karan'], 'description': 'Kurunthokai & Akananuru Cliffside Honey Hunting Hymns'}, {'id': 'HON-02', 'query': 'What do the Pandya stone inscriptions at Alagar Kovil record regarding forest honey tithes (Theyn-kadamai), hill harvesting rights, and temple lamp wax?', 'expected_slugs': ['insc-alagar-kovil-forest-honey-and-wax-endowments', 'concept-forest-honey-barter-and-hill-produce-caravans'], 'description': 'Alagar Kovil Pandya Forest Honey Tithes & Temple Lamp Wax Charters'}, {'id': 'HON-03', 'query': 'What are the medieval Chola epigraphs at Tiruvannamalai formalizing wild honey harvesting covenants with Jawadhu hill tribes and beeswax delivery quotas?', 'expected_slugs': ['insc-tiruvannamalai-hill-tribe-forest-honey-charters', 'place-jawadhu-hills-honey-cliff-escarpments'], 'description': 'Tiruvannamalai Jawadhu Hills Honey Harvester Covenants & Wax Charters'}, {'id': 'HON-04', 'query': 'How was nocturnal cliffside wild honeycomb harvesting conducted on sheer rock faces using braided cane ladders (Kani-maram) and herbal smoke torches?', 'expected_slugs': ['concept-cliffside-wild-honeycomb-harvesting-and-smoke-torches', 'char-jawadhu-hills-master-honey-hunter-theyn-karan'], 'description': 'Cliffside Wild Honeycomb Harvesting, Smoke Torches & Suspended Ladders'}, {'id': 'HON-05', 'query': 'How were Indian honeybees (Apis cerana indica) domesticated in ancient Tamil farmsteads using hollowed palmyra log hives and inverted terracotta pots?', 'expected_slugs': ['concept-hollow-log-and-clay-pot-apiary-domestication', 'text-kurunthokai-cliff-honey-harvesting-poetry'], 'description': 'Indigenous Apiary Domestication, Hollow Log Hives & Clay Pot Systems'}, {'id': 'HON-06', 'query': 'How was crude honeycomb wax purified through boiling water separation, cloth filtration, and compounded with dammar resin for bronze casting?', 'expected_slugs': ['concept-beeswax-rendering-refinement-and-cire-perdue-preparation', 'char-madurai-wax-refiner-and-guild-merchant-mezhugu-vanikan'], 'description': 'Beeswax Solar Rendering, Cloth Filtration & Cire-Perdue Preparation'}, {'id': 'HON-07', 'query': 'How did ancient forest honey harvesters barter mountain honey in bamboo tubes for sea salt and forged iron, and how was honey graded in Siddha medicine?', 'expected_slugs': ['concept-forest-honey-barter-and-hill-produce-caravans', 'text-kurunthokai-cliff-honey-harvesting-poetry'], 'description': 'Forest Honey Barter, Hill Produce Caravans & Siddha Medicinal Grading'}, {'id': 'HON-08', 'query': 'Where were the ancient honey-cliff escarpments of the Jawadhu Hills located that were celebrated in Malaipadukadam for abundant wild rock honey?', 'expected_slugs': ['place-jawadhu-hills-honey-cliff-escarpments', 'insc-tiruvannamalai-hill-tribe-forest-honey-charters'], 'description': 'Jawadhu Hills Ancient Honey Cliff Escarpments & Forest Ranges'}]

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
    print("🎯 ANCIENT TAMIL BEEKEEPING, HONEY & WAX GUILDS RAG BENCHMARK")
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
