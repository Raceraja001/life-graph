#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Sangam Fauna, War Elephants & Maritime Horse Imports Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "ELE-01",
        "query": "How does Purananuru describe the royal war elephant (Kaliru) equipped with iron tusk sheaths (Irumpu-k-kodu) battering enemy fort gates?",
        "expected_slugs": ["text-purananuru-kaliru-elephant-warfare", "concept-kaliru-war-elephant-siege-mechanics"],
        "description": "Purananuru Kaliru War Elephant Siege Poetry"
    },
    {
        "id": "ELE-02",
        "query": "What is the historical evidence in Pattinappalai of spirited Arabian and Persian war horses arriving by oceanic dhows at Poompuhar harbor?",
        "expected_slugs": ["text-pattinappalai-kudirai-maritime-imports", "concept-kudirai-k-kodu-arabian-horse-trade"],
        "description": "Pattinappalai Oceanic Horse Imports at Poompuhar"
    },
    {
        "id": "ELE-03",
        "query": "What are the inscriptional records in the Anamalai corridor documenting royal elephant sanctuaries, capture quotas, and mahout land shares?",
        "expected_slugs": ["insc-kurunji-anai-malai-elephant-charters", "place-anamalai-chera-elephant-capture-basin"],
        "description": "Anamalai Elephant Sanctuary Epigraphs & Mahout Grants"
    },
    {
        "id": "ELE-04",
        "query": "How were mature tuskers tactically deployed with armored caparisons, forehead plates, and iron-tipped tusks to breach fortress ramparts?",
        "expected_slugs": ["concept-kaliru-war-elephant-siege-mechanics", "text-purananuru-kaliru-elephant-warfare"],
        "description": "Kaliru Siege Tactics & Iron Tusk Battering Mechanics"
    },
    {
        "id": "ELE-05",
        "query": "How was the trans-oceanic Arabian horse trade organized by merchant guilds (Kudirai-c-cetti) importing steeds through Coromandel and Kayal ports?",
        "expected_slugs": ["concept-kudirai-k-kodu-arabian-horse-trade", "char-kudirai-c-cetti-arabian-horse-importer"],
        "description": "Kudirai-k-Kodu Arabian Horse Trade & Guild Importers"
    },
    {
        "id": "ELE-06",
        "query": "What does Sangam literature record regarding the hunting ethology of the royal tiger (Vengai) and bird divination omens?",
        "expected_slugs": ["concept-sangam-fauna-panthera-and-avian-omens"],
        "description": "Sangam Wildlife Ethology & Royal Tiger (Vengai) Symbolism"
    },
    {
        "id": "ELE-07",
        "query": "What were the traditional elephant-trapping methods using pit-traps (Kuli) and timber kraal stockades (Pandi) in the Western Ghats?",
        "expected_slugs": ["concept-elephant-capture-and-khedda-technology"],
        "description": "Indigenous Elephant Capture Technology (Kuli & Pandi)"
    },
    {
        "id": "ELE-08",
        "query": "Where was the premier Western Ghats rainforest elephant breeding habitat and capture reserve located in antiquity?",
        "expected_slugs": ["place-anamalai-chera-elephant-capture-basin", "char-chola-paka-maravan-chief-mahout"],
        "description": "Anamalai Montane Elephant Sanctuary & Capture Basin"
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
    print("🐘 SANGAM FAUNA, WAR ELEPHANTS & HORSE IMPORTS RAG BENCHMARK")
    print("=" * 75)

    for case in BENCHMARK_CASES:
        vec = get_embedding(case["query"])
        vec_literal = "[" + ",".join(str(x) for x in vec) + "]"

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
