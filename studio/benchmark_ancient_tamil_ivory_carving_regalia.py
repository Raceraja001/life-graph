#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Ivory Carving, Bone Artifacts & Royal Regalia
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'IVR-01', 'title': 'Nedunalvadai Royal Bedstead Ivory Carvings & Sangam Palace Hymns', 'query': 'How does classical poetry in Nedunalvadai describe the Pandya royal bedstead crafted from seasoned war elephant tusks with lathe-turned legs?', 'expected_slugs': ['text-nedunalvadai-palace-ivory-carving-poetry', 'concept-royal-ivory-throne-marquetry-and-palanquin-inlay']}, {'id': 'IVR-02', 'title': 'Porunthal Excavation 500 BCE Ivory Gaming Dice with Concentric Pips', 'query': 'What archaeological evidence at Porunthal near Palani revealed perfectly preserved ivory gaming dice with etched concentric circular pips dated to 500 BCE?', 'expected_slugs': ['insc-porunthal-ivory-dice-and-brahmi-epigraphs', 'place-porunthal-ancient-ivory-and-gem-lapidary-complex']}, {'id': 'IVR-03', 'title': 'Kodumanal Royal Ivory Combs, Sword Hilts & Artisan Charters', 'query': 'What do the Kodumanal excavation charters and Tamil-Brahmi artisan signatures reveal about double-sided fine-toothed ivory combs and sword handles?', 'expected_slugs': ['insc-kodumanal-ivory-comb-and-regalia-charters', 'concept-intricate-bas-relief-ivory-carving-and-staining']}, {'id': 'IVR-04', 'title': 'Elephant Tusk Seasoning, Oil Soaking & Reciprocal Bow-Lathe Turning', 'query': 'How were elephant tusks seasoned in water and sesame oil before being turned on reciprocal bow-lathes to shape cylindrical gaming pieces?', 'expected_slugs': ['concept-ivory-tusk-seasoning-cutting-and-lathe-turning', 'char-porunthal-master-ivory-turner-thandakkaran']}, {'id': 'IVR-05', 'title': 'Micro-Chiseling Bas-Relief Ivory Carvings, Vegetable Staining & Luster', 'query': 'How were intricate bas-relief and openwork pictorial carvings executed on ivory plaques using micro-chisels and stained with madder and turmeric?', 'expected_slugs': ['concept-intricate-bas-relief-ivory-carving-and-staining', 'char-madurai-royal-palace-ivory-inlay-artisan-silpa-asiriyan']}, {'id': 'IVR-06', 'title': 'Animal Bone Styli, Hardened Arrowpoints & Antler Kohl Rods', 'query': 'How were seasoned animal bones and deer antlers boiled in lye and carved into sharpened palm-leaf writing styluses, arrowpoints, and kohl rods?', 'expected_slugs': ['concept-bone-stylus-arrowpoint-and-cosmetic-rod-craft', 'insc-porunthal-ivory-dice-and-brahmi-epigraphs']}, {'id': 'IVR-07', 'title': 'Royal Ivory Throne Marquetry, Palanquin Veneers & Dynastic Heraldry', 'query': 'How were thin ivory veneers and dynastic heraldic emblems inlaid into royal hardwood thrones and palanquins using mortise-tenon joinery and hide glue?', 'expected_slugs': ['concept-royal-ivory-throne-marquetry-and-palanquin-inlay', 'text-nedunalvadai-palace-ivory-carving-poetry']}, {'id': 'IVR-08', 'title': 'Porunthal Ancient Ivory & Gem Lapidary Complex in Palani Foothills', 'query': 'Where is the ancient archaeological site of Porunthal situated along the Palani foothills that revealed 500 BCE ivory dice, glass beads, and grave urns?', 'expected_slugs': ['place-porunthal-ancient-ivory-and-gem-lapidary-complex', 'insc-porunthal-ivory-dice-and-brahmi-epigraphs']}]

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
    print("🎯 ANCIENT TAMIL IVORY CARVING, BONE ARTIFACTS & ROYAL REGALIA RAG BENCHMARK")
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
