#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Bell-Metal Metallurgy, High-Tin Bronzes & Specular Mirrors
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'BEL-01', 'title': 'Perumpanarruppadai High-Tin Bronze Cymbals (Kaithalam) & Mirrors', 'query': 'How does classical poetry in Perumpanarruppadai and Silappadikaram describe resonant high-tin bronze cymbals (Kaithalam) and polished specular metal mirrors?', 'expected_slugs': ['text-perumpanarruppadai-bell-metal-cymbals-and-mirror-poetry', 'concept-sacred-bronze-gongs-cymbals-and-percussion-metallurgy']}, {'id': 'BEL-02', 'title': 'Thiruvidaimarudur Chola Bronze Temple Bell Endowments & Metrology', 'query': 'What do the imperial Chola inscriptions at Thiruvidaimarudur record regarding royal gifts of massive cast bell-metal temple bells and exact weight metrology?', 'expected_slugs': ['insc-thiruvidaimarudur-chola-temple-bell-endowments', 'concept-acoustic-temple-bell-geometry-and-sound-resonance-casting']}, {'id': 'BEL-03', 'title': 'Vagaikulam Pandya Bell-Metal Guild Charters & Furnace Remissions', 'query': 'What royal privileges and furnace tax remissions were granted to the hereditary bell-metal founders of Vagaikulam along the Tambraparni River?', 'expected_slugs': ['insc-vagaikulam-pandya-bell-metal-artisan-charters', 'place-vagaikulam-ancient-bell-metal-casting-haven']}, {'id': 'BEL-04', 'title': 'High-Tin Bronze Metallurgy (Vengalam), Beta Phase (78:22) & Quenching', 'query': 'How did ancient Tamil metallurgists hot-forge high-tin bronze (78:22 copper-tin ratio) in the ductile beta-phase (650°C-750°C) and water-quench it to prevent brittleness?', 'expected_slugs': ['concept-high-tin-bronze-alloy-mechanics-and-phase-diagram-vengalam', 'concept-acoustic-temple-bell-geometry-and-sound-resonance-casting']}, {'id': 'BEL-05', 'title': 'Acoustic Temple Bell Geometry, Swept Core & Sound Bow Harmonics', 'query': 'How was swept clay core molding used to cast parabolic sound bows and tune wall thickness gradients for long acoustic chime decay in temple bells?', 'expected_slugs': ['concept-acoustic-temple-bell-geometry-and-sound-resonance-casting', 'char-vagaikulam-master-bell-metal-founder-vengala-kollan']}, {'id': 'BEL-06', 'title': 'Specular Metal Mirror Metallurgy (67:33 Speculum) & Velvet Lapping', 'query': 'What metallurgical formulation (67:33 copper-tin ratio) and progressive abrasive velvet lapping were used to cast distortion-free specular metal mirrors?', 'expected_slugs': ['concept-specular-metal-mirror-polishing-and-speculum-metallurgy', 'char-swamimalai-master-speculum-mirror-polisher-kannadi-achari']}, {'id': 'BEL-07', 'title': 'Sacred Bronze Gongs (Semakkalam), Tala Cymbals & Strain Hardening', 'query': 'How were sacred flat disc gongs (Semakkalam) and heavy tala cymbals (Kaithalam) forged and strain-hardened to cut through temple percussion ensembles?', 'expected_slugs': ['concept-sacred-bronze-gongs-cymbals-and-percussion-metallurgy', 'char-vagaikulam-master-bell-metal-founder-vengala-kollan']}, {'id': 'BEL-08', 'title': 'Vagaikulam Ancient Bell-Metal Casting Haven on the Tambraparni', 'query': 'Where was the historic non-ferrous foundry haven of Vagaikulam situated along the Tambraparni River that specialized in high-tin bell-metal casting?', 'expected_slugs': ['place-vagaikulam-ancient-bell-metal-casting-haven', 'insc-vagaikulam-pandya-bell-metal-artisan-charters']}]

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
    print("🎯 ANCIENT TAMIL BELL-METAL METALLURGY, HIGH-TIN BRONZES & SPECULAR MIRRORS RAG BENCHMARK")
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
