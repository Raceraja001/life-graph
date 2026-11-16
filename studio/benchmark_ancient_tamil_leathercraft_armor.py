#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Leathercraft, Armor Guilds & Footwear Metallurgy Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'LTH-01', 'query': 'How does classical Sangam poetry in Purananuru depict multi-layered buffalo leather shields, archer thumb tabs, and warrior combat sandals?', 'expected_slugs': ['text-purananuru-warrior-shield-and-leather-poetry', 'concept-cuir-bouilli-boiled-leather-armor-and-shield-reinforcement'], 'description': 'Purananuru Warrior Shield & Buffalo Hide Armor Poetry'}, {'id': 'LTH-02', 'query': 'What do the imperial Chola inscriptions at Gangaikondacholapuram record regarding royal leather armorers (Thol-kollan), cavalry saddles, and arsenals?', 'expected_slugs': ['insc-gangaikondacholapuram-armorers-and-leather-guild-charters', 'char-gangaikondacholapuram-master-armorer-thol-kollan'], 'description': 'Gangaikondacholapuram Cavalry Harness & Armorer Guild Charters'}, {'id': 'LTH-03', 'query': 'What are the medieval stone inscriptions from Tiruchirappalli and Uraiyur mandating municipal tannery zoning outside city walls and Avaram bark tithes?', 'expected_slugs': ['insc-tiruchirappalli-tannery-and-leather-tax-charters', 'concept-vegetable-tanning-avaram-bark-and-buffing-chemistry'], 'description': 'Tiruchirappalli Tannery Concessions & Bark Tithe Charters'}, {'id': 'LTH-04', 'query': 'How was vegetable tanning chemistry conducted in ancient Tamilakam using Senna auriculata (Avaram) bark tannins, lime dehairing, and oil currying?', 'expected_slugs': ['concept-vegetable-tanning-avaram-bark-and-buffing-chemistry', 'char-palani-foothills-master-tanner-thol-padaniduvor'], 'description': 'Vegetable Tanning Chemistry & Avaram Polyphenol Immersion'}, {'id': 'LTH-05', 'query': 'How was hardened boiled leather armor (Cuir-Bouilli) engineered using hot wax-resin impregnation and reinforced with bronze central shield bosses?', 'expected_slugs': ['concept-cuir-bouilli-boiled-leather-armor-and-shield-reinforcement', 'char-gangaikondacholapuram-master-armorer-thol-kollan'], 'description': 'Hardened Boiled Leather Armor Cuir-Bouilli & Shield Boss Metallurgy'}, {'id': 'LTH-06', 'query': 'What were the archery leather accessories used in Sangam warfare including molded lizard-skin bracers (Kaimurai), watertight quivers, and braided sinew strings?', 'expected_slugs': ['concept-archers-bracer-leather-quivers-and-sinew-bowstrings', 'text-purananuru-warrior-shield-and-leather-poetry'], 'description': 'Archer Leather Bracers, Quiver Moisture Seals & Sinew Stringcraft'}, {'id': 'LTH-07', 'query': 'How were ancient Tamil warrior combat sandals (Thod-seruppu) constructed with iron hobnails (Laada-aani) and multi-ply rawhide outsoles for mountain traction?', 'expected_slugs': ['concept-warrior-sandals-iron-cleated-caligae-and-leather-metrology', 'place-dindigul-ancient-leather-tanning-valley'], 'description': 'Warrior Combat Sandals Thod-Seruppu & Iron Hobnail Cleats'}, {'id': 'LTH-08', 'query': 'Where was the historic leather tanning and saddle-making valley of Dindigul located in the Kodaganar basin surrounded by wild Avaram scrub forests?', 'expected_slugs': ['place-dindigul-ancient-leather-tanning-valley', 'concept-vegetable-tanning-avaram-bark-and-buffing-chemistry'], 'description': 'Dindigul Ancient Leather Tanning Valley & Kodaganar Basin'}]

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
    print("🎯 ANCIENT TAMIL LEATHERCRAFT & WARRIOR ARMOR RAG BENCHMARK")
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
