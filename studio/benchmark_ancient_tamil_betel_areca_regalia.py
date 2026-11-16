#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Betel & Areca Cultivation, Paan Culture & Bronze Regalia
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'BTL-01', 'title': 'Silappadikaram Betel Leaf, Areca Nut & Sangam Hospitality Hymns', 'query': 'How does classical poetry in Silappadikaram describe the bustling Madurai betel markets and the compounding of fragrant paan rolls with cloves and cardamom?', 'expected_slugs': ['text-silappadikaram-betel-paan-and-hospitality-poetry', 'char-madurai-court-paan-master-tamboola-nayagan']}, {'id': 'BTL-02', 'title': 'Thiruvaduthurai Chola Betel Garden Tithes & Temple Paan Charters', 'query': 'What do the Chola inscriptions at Thiruvaduthurai record regarding royal land grants for temple betel gardens (Vetrilaik-kodik-kal) and daily leaf quotas for deities?', 'expected_slugs': ['insc-thiruvaduthurai-chola-betel-garden-endowments', 'concept-betel-vine-trellis-cultivation-and-microclimate-hydrology']}, {'id': 'BTL-03', 'title': 'Authoor Tambraparni Delta Betel Leaf Concessions & Riverine Trade', 'query': 'What do the Pandya epigraphs and historical travel chronicles record regarding Authoor betel leaf cultivation along the Tambraparni and riverine trade?', 'expected_slugs': ['insc-authoor-pandya-vetrillai-tax-and-trade-charters', 'place-authoor-ancient-betel-vine-groves']}, {'id': 'BTL-04', 'title': 'Betel Vine Trellis Agronomy (Vetrilaik-kodi), Agathi Symbiosis & Ditch Inundation', 'query': 'How was the microclimate agronomy of ancient Tamil betel trellis cultivation (Kodik-kal) maintained using Agathi support trees and flooded trenches?', 'expected_slugs': ['concept-betel-vine-trellis-cultivation-and-microclimate-hydrology', 'char-authoor-master-betel-cultivator-vetrilai-kodi-kavalan']}, {'id': 'BTL-05', 'title': 'Areca Palm Cultivation (Kamugu), Boiling Curing in Kalli & Nut Grading', 'query': 'How were areca nut palms cultivated, de-husked, and boiled in concentrated tannin broth (Kalli) to cure them for commercial grading?', 'expected_slugs': ['concept-areca-palm-harvesting-curing-and-nut-grading-metrology', 'concept-betel-vine-trellis-cultivation-and-microclimate-hydrology']}, {'id': 'BTL-06', 'title': 'Chunam Marine Shell Calcination, Catechu Resins & Paan Chemistry', 'query': 'How was pure calcium hydroxide (Chunam) calcined from marine bivalve shells and pearl-chank fragments along the Gulf of Mannar for paan chemistry?', 'expected_slugs': ['concept-chunam-marine-shell-calcination-and-paan-alchemy', 'text-silappadikaram-betel-paan-and-hospitality-poetry']}, {'id': 'BTL-07', 'title': 'Lost-Wax Cast Bronze Betel Caskets (Pakkuk-kudai) & Zoomorphic Cutters', 'query': 'What lost-wax bronze caskets (Pakkuk-kudai) and articulated steel areca nut cutters (Pakku-vetti) were engineered for royal Tamil courtly regalia?', 'expected_slugs': ['concept-lost-wax-bronze-betel-boxes-and-royal-regalia-caskets', 'char-madurai-court-paan-master-tamboola-nayagan']}, {'id': 'BTL-08', 'title': 'Authoor Ancient Betel Vine Groves & Tambraparni Canal Basin', 'query': 'Where were the ancient betel vine groves of Authoor located along the Tambraparni River that produced the world-famous pungent Authoor betel leaves?', 'expected_slugs': ['place-authoor-ancient-betel-vine-groves', 'insc-authoor-pandya-vetrillai-tax-and-trade-charters']}]

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
    print("🎯 ANCIENT TAMIL BETEL & ARECA CULTIVATION, PAAN CULTURE & BRONZE REGALIA RAG BENCHMARK")
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
