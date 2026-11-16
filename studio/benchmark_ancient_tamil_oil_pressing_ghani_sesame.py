#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Oil Pressing, Rotary Ghani Mills & Sesame Chemistry
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'OIL-01', 'title': 'Purananuru Sesame Harvest, Cold-Pressed Oil & Sacred Lamp Hymns', 'query': 'How does Sangam literature in Purananuru praise the black sesame harvest, rotary crushing mills, fragrant cold-pressed Nal-ennai, and sacred lamps?', 'expected_slugs': ['text-purananuru-fragrant-sesame-oil-and-ghani-poetry', 'concept-cold-pressed-sesame-and-castor-oil-chemistry']}, {'id': 'OIL-02', 'title': 'Tiruvannamalai Chola Sekku-Irai Oil Press Taxes & Nandavilakku Exemptions', 'query': 'What do the medieval Chola inscriptions at Tiruvannamalai record regarding municipal Sekku-irai oil press taxes and tax exemptions for Nandavilakku lamps?', 'expected_slugs': ['insc-tiruvannamalai-chola-oil-press-tax-charters', 'concept-rotary-granite-ghani-mortar-and-pestle-mechanics']}, {'id': 'OIL-03', 'title': 'Ennayiram Imperial Chola College Sesame Oil Rations & Student Charters', 'query': 'What details does the monumental Ennayiram inscription of Rajendra Chola I preserve regarding daily sesame oil rations for Vedic students and sacred lamps?', 'expected_slugs': ['insc-ennayiram-brahmadeya-oil-ration-and-mill-charters', 'concept-nandavilakku-perpetual-temple-lamps-and-sesame-oil-tithes']}, {'id': 'OIL-04', 'title': 'Rotary Granite Ghani Mills (Chekku), Oxen Draft Sweeps & Mortar Physics', 'query': 'How did the mechanical physics of the rotary granite ghani (Chekku) with an angled hardwood pestle and oxen sweep crush sesame seeds without heat buildup?', 'expected_slugs': ['concept-rotary-granite-ghani-mortar-and-pestle-mechanics', 'char-vaniyambadi-master-oil-miller-chekku-karan']}, {'id': 'OIL-05', 'title': 'Cold-Pressed Sesame (Nal-ennai) & Castor Oil Chemistry and Antioxidants', 'query': 'What is the biochemical profile of cold-pressed sesame oil (Nal-ennai) containing sesamol antioxidants and high-viscosity castor oil in ancient Tamil medicine?', 'expected_slugs': ['concept-cold-pressed-sesame-and-castor-oil-chemistry', 'text-purananuru-fragrant-sesame-oil-and-ghani-poetry']}, {'id': 'OIL-06', 'title': 'Oil Merchant Guilds (Sankarappadi-nattar & Vaniyar) & Market Assemblies', 'query': 'How were the influential oil merchant guilds (Sankarappadi-nattar and Vaniyar) organized to manage urban oil production monopolies and temple endowments?', 'expected_slugs': ['concept-oil-merchant-guilds-sankarappadi-and-vaniya-corporations', 'char-thanjavur-temple-oil-guild-chief-vaniya-thalaivan']}, {'id': 'OIL-07', 'title': 'Nandavilakku Perpetual Temple Lamps, Sesame Oil Tithes & Cast Bronze', 'query': 'How did the liturgical institution of Nandavilakku operate in Tamil temples through endowments of cows and oil presses ensuring daily measures of sesame oil?', 'expected_slugs': ['concept-nandavilakku-perpetual-temple-lamps-and-sesame-oil-tithes', 'insc-ennayiram-brahmadeya-oil-ration-and-mill-charters']}, {'id': 'OIL-08', 'title': 'Vaniyambadi Ancient Oil Millers Quarter & Palar River Mills', 'query': 'Where was the ancient oil-milling settlement of Vaniyambadi located along the Palar River where master millers operated batteries of granite presses?', 'expected_slugs': ['place-vaniyambadi-ancient-oil-millers-quarter', 'char-vaniyambadi-master-oil-miller-chekku-karan']}]

def get_bge_embedding(text_str: str) -> list[float]:
    payload = json.dumps({
        "model": "bge-m3:latest",
        "prompt": text_str[:4000]
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
    print("🎯 ANCIENT TAMIL OIL PRESSING, ROTARY GHANI MILLS & SESAME CHEMISTRY RAG BENCHMARK")
    print("=" * 75)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(TEST_CASES)

    for case in TEST_CASES:
        qid = case["id"]
        qtitle = case["title"]
        query = case["query"]
        expected = case["expected_slugs"]

        q_emb = get_bge_embedding(query)
        q_emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"

        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) as similarity
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 1;
        """, (q_emb_str, q_emb_str))

        top_match = cur.fetchone()
        if not top_match:
            print(f"[{qid}] {qtitle}\n  Query: \"{query}\"\n  ❌ FAIL: No results returned")
            continue

        top_slug, score = top_match
        is_hit = top_slug in expected

        if is_hit:
            passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"\n[{qid}] {qtitle}")
        print(f"  Query: \"{query}\"")
        print(f"  Expected: {expected}")
        print(f"  Top-1: {top_slug} (Cosine Sim: {score:.4f}) -> {status}")

    acc = (passed / total) * 100.0
    print("\n" + "=" * 75)
    print(f"🎯 BENCHMARK RESULTS: {passed}/{total} Passed ({acc:.1f}% Top-1 Accuracy)")
    print("=" * 75 + "\n")

    cur.close()
    conn.close()

    if passed != total:
        sys.exit(1)

if __name__ == "__main__":
    import sys
    main()
