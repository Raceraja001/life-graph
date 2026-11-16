#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Saltpans, Salt Merchant Guilds & Umanar Caravans Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'SLT-01', 'query': 'How does classical Sangam poetry in Sirupanarruppadai depict coastal solar saltpans, Umanar bullock carts, and salt-for-grain barter?', 'expected_slugs': ['text-sirupanarruppadai-saltpan-and-umanar-poetry', 'concept-umanar-bullock-cart-caravans-and-salt-barter-economics'], 'description': 'Sirupanarruppadai Saltpan Ecology & Umanar Merchant Cart Hymns'}, {'id': 'SLT-02', 'query': 'What do the Pallava and Chola inscriptions at Marakkanam record regarding royal saltpan boundaries, brine sluice rights, and temple salt tithes?', 'expected_slugs': ['insc-marakkanam-saltpan-royal-charters', 'char-marakkanam-saltpan-master-alam-kavalar'], 'description': 'Marakkanam Eyilpattinam Royal Saltpan Concessions & Sluice Charters'}, {'id': 'SLT-03', 'query': 'What are the Pandyan stone inscriptions from Kayalpattinam and the Tambraparni delta assessing salt revenue, dry measures, and merchant guild tolls?', 'expected_slugs': ['insc-kayalpattinam-salt-revenue-and-measure-charters', 'concept-salt-measuring-metrology-and-coastal-customs-tolls'], 'description': 'Kayalpattinam & Tambraparni Salt Revenue & Standard Brass Measure Charters'}, {'id': 'SLT-04', 'query': 'How were multi-stage solar evaporation saltpans engineered using intake reservoirs, intermediate condensers, and compacted clay beds to fractionate pure salt?', 'expected_slugs': ['concept-solar-evaporation-pans-and-brine-fractionation', 'char-marakkanam-saltpan-master-alam-kavalar'], 'description': 'Solar Evaporation Basin Architecture & Hydraulic Brine Fractionation'}, {'id': 'SLT-05', 'query': 'How did Umanar merchant clans organize covered bullock cart convoys, pack-bullocks, and barter equal volumes of sea salt for mountain paddy?', 'expected_slugs': ['concept-umanar-bullock-cart-caravans-and-salt-barter-economics', 'char-umanar-caravan-chief-karum-ser-thalaivan'], 'description': 'Umanar Cart Caravan Logistics & Uppe-Nel-Maari Parity Barter'}, {'id': 'SLT-06', 'query': 'How were thousands of kalams of crystalline salt stored and protected from monsoonal humidity using elevated earthen platforms and thatched palmyra cones?', 'expected_slugs': ['concept-clay-lined-salt-storage-silos-and-moisture-protection', 'place-thoothukudi-ancient-solar-saltpans'], 'description': 'Elevated Clay-Lined Salt Storage Silos & Thatched Pyramid Insulation'}, {'id': 'SLT-07', 'query': 'What were the dry volumetric units of measurement used for salt in ancient Tamilakam and how did royal customs posts (Ulgu) assess transit duties?', 'expected_slugs': ['concept-salt-measuring-metrology-and-coastal-customs-tolls', 'insc-kayalpattinam-salt-revenue-and-measure-charters'], 'description': 'Volumetric Marakkal Salt Metrology & Ulgu Customs Checkpoints'}, {'id': 'SLT-08', 'query': 'Where was the historic solar salt haven of Thoothukudi located where low monsoonal rainfall and dry winds supported continuous crystal salt extraction?', 'expected_slugs': ['place-thoothukudi-ancient-solar-saltpans', 'concept-solar-evaporation-pans-and-brine-fractionation'], 'description': 'Thoothukudi Ancient Solar Salt Haven & Gulf of Mannar Brines'}]

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
    print("🎯 ANCIENT TAMIL SALTPANS & UMANAR CARAVANS RAG BENCHMARK")
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
