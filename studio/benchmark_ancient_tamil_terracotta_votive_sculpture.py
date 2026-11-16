#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Terracotta Votive Sculpture, Urn Burial Figurines & Ayyanar Shrines
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'TER-01', 'title': 'Manimekalai Potter Guild (Kuyavar), Votive Terracottas & Funerary Urn Hymns', 'query': 'How does the classical epic Manimekalai depict skilled potters modeling clay effigies, guardian sculptures, and giant funerary urns?', 'expected_slugs': ['text-manimekalai-potter-guild-and-terracotta-effigy-poetry', 'char-adichanallur-funerary-urn-potter-thaazhi-kuyavan']}, {'id': 'TER-02', 'title': 'Keezhadi Anthropomorphic Terracotta Figurines & 6th Century BCE Coiffures', 'query': 'What anthropomorphic terracotta female heads and elaborate hair coiffures dated to the 6th century BCE were unearthed during Keezhadi excavations?', 'expected_slugs': ['insc-keezhadi-terracotta-figurine-and-brahmi-epigraphs', 'concept-anthropomorphic-terracotta-figurines-and-hair-bun-stylistics']}, {'id': 'TER-03', 'title': 'Sendamangalam Potter Guild Tax Remissions & Monumental Ayyanar Steeds', 'query': 'What do the Kadava inscriptions at Sendamangalam reveal regarding tax remissions for potter guilds in exchange for sculpting colossal Ayyanar war horses?', 'expected_slugs': ['insc-sendamangalam-potter-charters-and-ayyanar-endowments', 'concept-hollow-coil-construction-monumental-terracotta-horses']}, {'id': 'TER-04', 'title': 'Colossal Hollow-Coil Ayyanar Horses, Internal Arches & Granular Physics', 'query': 'How was the structural engineering of colossal hollow-coil Ayyanar terracotta horses achieved using grog temper, internal diaphragms, and steam vents?', 'expected_slugs': ['concept-hollow-coil-construction-monumental-terracotta-horses', 'char-vilangudi-master-terracotta-sculptor-kuyap-perun-thatchan']}, {'id': 'TER-05', 'title': 'Megalithic Funerary Urns (Mudhumakkal-thaazhi) & Inverted Reduction Firing', 'query': 'How were giant megalithic burial urns (Mudhumakkal-thaazhi) thrown, paddle-thinned, and fired under inverted reduction conditions to create Black-and-Red Ware?', 'expected_slugs': ['concept-megalithic-burial-urn-pyrotechnics-and-black-and-red-reduction', 'char-adichanallur-funerary-urn-potter-thaazhi-kuyavan']}, {'id': 'TER-06', 'title': 'Anthropomorphic Terracotta Modeling, Pinch Sculpting & Aimpaal Coiffures', 'query': 'What plastic techniques combining molded facial masks and hand-pinched bodies were used to depict classical Sangam coiffures on terracotta figurines?', 'expected_slugs': ['concept-anthropomorphic-terracotta-figurines-and-hair-bun-stylistics', 'insc-keezhadi-terracotta-figurine-and-brahmi-epigraphs']}, {'id': 'TER-07', 'title': 'Open Clamp Bonfire Kilns (Soolai), Rice-Husk Smothering & Smoke Blackening', 'query': 'How were modular rural clamp bonfires (Soolai) constructed using rice husks, dung cakes, and damp mud plastering for controlled reduction firing?', 'expected_slugs': ['concept-open-clamp-bonfire-kilns-and-rice-husk-reduction', 'concept-megalithic-burial-urn-pyrotechnics-and-black-and-red-reduction']}, {'id': 'TER-08', 'title': 'Vilangudi Ancient Terracotta Votive Haven & Vaigai Potter Quarter', 'query': 'Where was the historic ceramic and terracotta sculptural center of Vilangudi situated along the Vaigai River near Madurai that crafted Ayyanar steeds?', 'expected_slugs': ['place-vilangudi-ancient-terracotta-votive-haven', 'char-vilangudi-master-terracotta-sculptor-kuyap-perun-thatchan']}]

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
    print("🎯 ANCIENT TAMIL TERRACOTTA VOTIVE SCULPTURE, URN BURIAL FIGURINES & AYYANAR SHRINES RAG BENCHMARK")
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
