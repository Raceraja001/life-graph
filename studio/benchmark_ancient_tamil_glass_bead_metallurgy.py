#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Glass Bead Metallurgy & Vitreous Enamels
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'GLS-01', 'title': 'Perumpanarruppadai & Pattinappalai Sangam Glass Bead & Bangle Poetry', 'query': 'How does classical Sangam poetry in Perumpanarruppadai and Pattinappalai describe coastal glassmakers melting silica batches and turning vitreous bangles?', 'expected_slugs': ['text-perumpanarruppadai-glass-bead-and-bangle-poetry', 'concept-glass-bangle-grooved-mandrel-turning-metrology']}, {'id': 'GLS-02', 'title': 'Arikamedu Indo-Roman Glass Furnace Charters & Mutisalah Export', 'query': 'What archaeological evidence and Tamil-Brahmi pot-sherds from Arikamedu confirm subterranean circular brick glass furnaces and global export of mutisalah beads?', 'expected_slugs': ['insc-arikamedu-indo-roman-glass-manufactory-charters', 'char-arikamedu-master-glass-blower-kannadi-kollan']}, {'id': 'GLS-03', 'title': 'Karaikadu Sangam Coastal Glass Bead Guild & Slag Mounds', 'query': 'What do the excavation epigraphs and material strata at Karaikadu reveal regarding specialized coastal glass bead artisan guilds and drawing debitage?', 'expected_slugs': ['insc-karaikadu-glass-bead-guild-charters', 'place-karaikadu-ancient-glass-bead-industrial-haven']}, {'id': 'GLS-04', 'title': 'Glass Cane Drawing Mechanics, Dump-and-Pull Pyrotechnics & Capillaries', 'query': 'How was the indigenous Tamil dump-and-pull glass cane drawing process executed across earthen corridors to produce hollow capillaries?', 'expected_slugs': ['concept-glass-cane-drawing-dump-and-pull-mechanics', 'char-karaikadu-bead-drawing-technician-mani-seyvor']}, {'id': 'GLS-05', 'title': 'Monochrome Indo-Pacific Glass Beads, Mineral Oxides & Nanoparticles', 'query': 'What chemical formulations of mineral oxides including copper nanoparticles, cobalt, and iron were used to create opaque red and sapphire monochrome Indo-Pacific glass beads?', 'expected_slugs': ['concept-monochrome-indo-pacific-glass-bead-pyrotechnics', 'concept-glass-cane-drawing-dump-and-pull-mechanics']}, {'id': 'GLS-06', 'title': 'Vitreous Enamel Glazing, Terracotta Bead Coating & High-Fire Frits', 'query': 'How did ancient Tamil artisans fuse low-melting-point vitreous glass frits onto terracotta beads and votive passport tokens in sealed saggars?', 'expected_slugs': ['concept-vitreous-enamel-glazing-and-terracotta-fusion', 'char-arikamedu-master-glass-blower-kannadi-kollan']}, {'id': 'GLS-07', 'title': 'Glass Bangle Fabrication on Grooved Mandrels & Annular Metrology', 'query': 'How were annular glass bangles manufactured on grooved rotating clay mandrels and flame-polished to standard wrist dimensions?', 'expected_slugs': ['concept-glass-bangle-grooved-mandrel-turning-metrology', 'text-perumpanarruppadai-glass-bead-and-bangle-poetry']}, {'id': 'GLS-08', 'title': 'Karaikadu Ancient Glass Bead Industrial Haven & Coromandel Slag Mounds', 'query': 'Where was the ancient coastal industrial haven of Karaikadu located along the Coromandel coast that produced tons of glass beads and furnace slag?', 'expected_slugs': ['place-karaikadu-ancient-glass-bead-industrial-haven', 'insc-karaikadu-glass-bead-guild-charters']}]

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
    print("🎯 ANCIENT TAMIL GLASS BEAD METALLURGY & VITREOUS ENAMELS RAG BENCHMARK")
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
