#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Palm-Wine (Toddy) Tapping, Palmyrah Architecture & Tree-of-Life Engineering
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'PAL-01', 'title': 'Purananuru Sweet Toddy, Palmyrah Groves & Chieftain Feasting', 'query': 'How does classical Sangam poetry in Purananuru describe tall palmyrah groves, sweet morning padhaneer, and foaming vessels of aged toddy?', 'expected_slugs': ['text-purananuru-toddy-tapping-and-palmyrah-poetry', 'char-udangudi-master-palm-climber-panai-eri-thalaivan']}, {'id': 'PAL-02', 'title': 'Sayalgudi Pandya Panai-Irai Tree Taxes & Tapper Guild Charters', 'query': 'What do the Pandya inscriptions around Sayalgudi record regarding the Panai-irai tree tax levied on sap-yielding palmyrah groves and tapper licenses?', 'expected_slugs': ['insc-sayalgudi-pandya-palmyrah-grove-tax-charters', 'concept-palmyrah-tree-of-life-botanical-engineering-panai']}, {'id': 'PAL-03', 'title': 'Udangudi Chola Palm Jaggery Tithes & Temple Kitchen Shipments', 'query': 'What do the imperial Chola records at Udangudi document regarding regular shipments of unrefined palm jaggery (Karupatti) to royal temple kitchens?', 'expected_slugs': ['insc-udangudi-chola-palm-jaggery-tithe-charters', 'place-udangudi-ancient-palmyrah-and-jaggery-haven']}, {'id': 'PAL-04', 'title': 'Palmyrah Tree-of-Life Agronomy (Panai) & Teri Dune Stabilization', 'query': 'How did the botanical engineering of the Asian palmyrah palm stabilize arid red Teri sand dunes and irrigation tank bunds across Tamilakam?', 'expected_slugs': ['concept-palmyrah-tree-of-life-botanical-engineering-panai', 'concept-palmyrah-timber-structural-rafters-and-leaf-thatch-architecture']}, {'id': 'PAL-05', 'title': 'Toddy Tapping Mechanics, Spadix Bruising & Lime Slaked Neera', 'query': 'How were flowering palmyrah spadices bruised and sliced, and how did slaked lime coatings prevent fermentation into alcoholic toddy?', 'expected_slugs': ['concept-toddy-tapping-mechanics-inflorescence-bruising-and-slaked-lime', 'char-udangudi-master-palm-climber-panai-eri-thalaivan']}, {'id': 'PAL-06', 'title': 'Open-Pan Palm Sap Boiling, Clarification & Karupatti Crystallization', 'query': 'How was sweet neera sap boiled down and clarified in open copper cauldrons over palm-frond fires before casting into coconut shell jaggery molds?', 'expected_slugs': ['concept-open-pan-palm-sap-boiling-and-karupatti-crystallization', 'char-sayalgudi-master-palm-jaggery-boiler-karupatti-seyvor']}, {'id': 'PAL-07', 'title': 'Palmyrah Heartwood Rafters (Panang-kazhi), Thatch & Fiber Cordage', 'query': 'How were termite-resistant outer heartwood palmyrah rafters (Panang-kazhi), braided leaf thatch panels, and palm-fiber cordage utilized in Tamil vernacular architecture?', 'expected_slugs': ['concept-palmyrah-timber-structural-rafters-and-leaf-thatch-architecture', 'concept-palmyrah-tree-of-life-botanical-engineering-panai']}, {'id': 'PAL-08', 'title': 'Udangudi Ancient Palmyrah & Jaggery Haven in the Teri Dune Basin', 'query': 'Where was the historic palmyrah agro-forestry center of Udangudi situated in the Teri red dune basin that produced prized palm jaggery?', 'expected_slugs': ['place-udangudi-ancient-palmyrah-and-jaggery-haven', 'insc-udangudi-chola-palm-jaggery-tithe-charters']}]

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
    print("🎯 ANCIENT TAMIL PALM-WINE (TODDY) TAPPING, PALMYRAH ARCHITECTURE & TREE-OF-LIFE ENGINEERING RAG BENCHMARK")
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
