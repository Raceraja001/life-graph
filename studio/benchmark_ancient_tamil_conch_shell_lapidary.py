#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Conch (Chank) Shell Cutting, Sacred Bangles & Marine Lapidary
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'CHK-01', 'title': 'Kurunthokai Sacred Conch Bangles (Sangu-Valaiyal) & Diver Hymns', 'query': "How does classical Sangam poetry in Kurunthokai and Aingurunuru describe deep-sea shell divers and snow-white cut conch bangles slipping from lovers' wrists?", 'expected_slugs': ['text-kurunthokai-sacred-conch-bangle-and-diver-poetry', 'char-korkai-master-conch-shell-cutter-sangu-aruppor']}, {'id': 'CHK-02', 'title': 'Korkai Pandya Royal Chank Fishery Charters & Shell Slag Strata', 'query': 'What archaeological evidence and foreign geographical accounts confirm the royal Pandya monopoly on deep-sea chank beds and shell sawing mounds at Korkai?', 'expected_slugs': ['insc-korkai-pandya-chank-fishery-and-customs-charters', 'concept-deep-sea-chank-diving-mechanics-and-parathavar-harvesters']}, {'id': 'CHK-03', 'title': 'Keezhakkarai Gulf of Mannar Chank Diver Guild & Boat Levies', 'query': 'What marine diving concessions, boat levies (Thoni-kadamai), and reef boundaries are documented in epigraphs at the chank emporium of Keezhakkarai?', 'expected_slugs': ['insc-keezhakkarai-marine-chank-diver-guild-charters', 'place-keezhakkarai-ancient-chank-diving-haven']}, {'id': 'CHK-04', 'title': 'Deep-Sea Chank Diving Mechanics, 15-kg Sinking Stones & Physiology', 'query': 'How did Parathavar freedivers descend to 20-meter reef depths using 15-kg granite sinking stones and coir net bags to harvest Turbinella pyrum shells?', 'expected_slugs': ['concept-deep-sea-chank-diving-mechanics-and-parathavar-harvesters', 'char-keezhakkarai-master-chank-diver-salapa-thalaivan']}, {'id': 'CHK-05', 'title': 'Transverse Conch Cutting, Curved Leaf-Saws (Karuvadu) & Bangle Hoops', 'query': 'How did ancient shell lapidaries slice seamless annular bangle hoops from conch shells using curved crescent-shaped iron saws (Karuvadu) and sand slurry?', 'expected_slugs': ['concept-transverse-and-spiral-chank-cutting-with-curved-leaf-saws', 'char-korkai-master-conch-shell-cutter-sangu-aruppor']}, {'id': 'CHK-06', 'title': 'Sacred Valampuri Dextral Conch Rarity & Dynastic Coronation Alchemy', 'query': 'What biological rarity characterizes the dextral right-winding conch (Valampuri Sangu) and why was it revered for royal dynastic coronations?', 'expected_slugs': ['concept-sacred-valampuri-dextral-conch-auspicious-alchemy', 'char-korkai-master-conch-shell-cutter-sangu-aruppor']}, {'id': 'CHK-07', 'title': 'Chank Columella Core Drilling, Tubular Beads & Mosaic Inlays', 'query': 'How were the central columella spiral cores of sawn conch shells drilled and turned on bow-lathes into tubular beads, gaming dice, and furniture inlays?', 'expected_slugs': ['concept-conch-columella-bead-turning-and-chank-inlay-lapidary', 'concept-transverse-and-spiral-chank-cutting-with-curved-leaf-saws']}, {'id': 'CHK-08', 'title': 'Keezhakkarai Ancient Chank Diving Haven & Gulf of Mannar Reefs', 'query': 'Where was the ancient Gulf of Mannar chank diving haven of Keezhakkarai situated that supported fleets of diving dhonis and massive shell middens?', 'expected_slugs': ['place-keezhakkarai-ancient-chank-diving-haven', 'insc-keezhakkarai-marine-chank-diver-guild-charters']}]

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
    print("🎯 ANCIENT TAMIL CONCH (CHANK) SHELL CUTTING, SACRED BANGLES & MARINE LAPIDARY RAG BENCHMARK")
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
