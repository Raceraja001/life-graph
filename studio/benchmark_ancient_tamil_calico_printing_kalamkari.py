#!/usr/bin/env python3
"""
RAG Benchmark Suite: Ancient Tamil Calico Block Printing, Resist-Wax Dyeing & Kalamkari Archetypes
Tests retrieval accuracy against Ollama bge-m3 dense vector embeddings in PostgreSQL.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

TEST_CASES = [{'id': 'PRT-01', 'title': 'Pattinappalai Painted Cotton Cloth (Chithira-Aadai) & Export Textile Hymns', 'query': 'How does classical poetry in Pattinappalai and Silappadikaram describe fine painted cotton garments (Chithira-Aadai) and resist-printed export muslins?', 'expected_slugs': ['text-pattinappalai-painted-cotton-cloth-chithira-aadai-poetry', 'char-kodali-karuppur-master-block-printer-chithira-achariyan']}, {'id': 'PRT-02', 'title': 'Kodali Karuppur Imperial Chola Resist-Wax Textile Guild & Temple Canopies', 'query': 'What do the Chola inscriptions at Kodali Karuppur near Kumbakonam record regarding royal patronage for resist-wax dyed temple canopies and court textiles?', 'expected_slugs': ['insc-kodali-karuppur-chola-textile-printer-charters', 'place-kodali-karuppur-ancient-textile-printing-haven']}, {'id': 'PRT-03', 'title': 'Kanchipuram Kalamkari Artisan Guilds, Alum Charters & Export Tax Epigraphs', 'query': 'What municipal charters and alum mordant regulations for textile dyers and kalam draughtsmen along the Vegavathi River are recorded at Kanchipuram?', 'expected_slugs': ['insc-kanchipuram-kalamkari-dyer-and-printer-guild-charters', 'char-kanchipuram-master-mordant-dyer-kalam-evar']}, {'id': 'PRT-04', 'title': 'Carved Hardwood Printing Blocks (Achchu-maram) & Registration Geometry', 'query': 'How were seasoned teak and rosewood printing blocks (Achchu-maram) carved with deep relief gouging, air release channels, and registration markers?', 'expected_slugs': ['concept-carved-teakwood-printing-blocks-and-relief-geometry', 'concept-molten-beeswax-resist-application-and-crackling-textures']}, {'id': 'PRT-05', 'title': 'Molten Beeswax Resist Application, Freehand Kalam Pens & Crackling Texture', 'query': 'How was compounded molten beeswax and dammar resin applied using wooden blocks and bamboo kalam pens to create crackled wax-resist dyed patterns?', 'expected_slugs': ['concept-molten-beeswax-resist-application-and-crackling-textures', 'char-kodali-karuppur-master-block-printer-chithira-achariyan']}, {'id': 'PRT-06', 'title': 'Fermented Iron Acetate (Kasi-k-kattu), Jaggery Rust Chemistry & Ferric Gallate', 'query': 'How was fermented iron acetate (Kasi-k-kattu) synthesized from rusted scrap iron, jaggery, and toddy to create permanent black ferric gallate ink?', 'expected_slugs': ['concept-iron-acetate-fermented-rust-black-dye-kasik-kattu', 'char-kanchipuram-master-mordant-dyer-kalam-evar']}, {'id': 'PRT-07', 'title': 'Riverine Continuous Flow Washing, Sheep Dung Bleaching & Sun-Curing Fixation', 'query': 'How did continuous riverine washing in the Kaveri, sheep dung enzymatic bleaching, and sun-curing fix mordants onto cotton fabrics?', 'expected_slugs': ['concept-riverine-running-water-washing-and-sun-bleaching-science', 'place-kodali-karuppur-ancient-textile-printing-haven']}, {'id': 'PRT-08', 'title': 'Kodali Karuppur Ancient Textile Printing Haven & Kaveri Sandbars', 'query': 'Where was the ancient Chola textile printing enclave of Kodali Karuppur located along the Kollidam River that created hybrid gold-brocaded printed sarees?', 'expected_slugs': ['place-kodali-karuppur-ancient-textile-printing-haven', 'insc-kodali-karuppur-chola-textile-printer-charters']}]

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
    print("🎯 ANCIENT TAMIL CALICO BLOCK PRINTING, RESIST-WAX DYEING & KALAMKARI ARCHETYPES RAG BENCHMARK")
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
