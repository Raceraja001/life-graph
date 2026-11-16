#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Iron Age Megalithic Burial Architecture & Urn Necropolises Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "MEG-01",
        "query": "How does Purananuru poetry address the potter (Kalam-chey-kove) moulding colossal burial urns (Mudumakkal Thaazhi) for departed chieftains?",
        "expected_slugs": ["text-purananuru-mudumakkal-thaazhi-funerary-poetry", "char-adichanallur-funerary-potter-and-urn-sculptor"],
        "description": "Purananuru Mudumakkal Thaazhi & Kalam-Chey-Kove Mortuary Poetry"
    },
    {
        "id": "MEG-02",
        "query": "What are the early Tamil-Brahmi inscribed rims, floral decorations, and mother goddess effigies excavated from Adichanallur burial urns?",
        "expected_slugs": ["insc-adichanallur-tamil-brahmi-urn-excavation-records", "concept-mudumakkal-thaazhi-pyriform-urn-engineering"],
        "description": "Adichanallur Urn Epigraphy & Terracotta Goddess Figurines"
    },
    {
        "id": "MEG-03",
        "query": "What are the Tamil-Brahmi inscribed potsherds and chieftain grave offerings recovered from the transepted cist tombs of Kodumanal?",
        "expected_slugs": ["insc-kodumanal-megalithic-cist-tomb-inscriptions", "concept-megalithic-cist-and-dolmen-stone-circle-architecture"],
        "description": "Kodumanal Megalithic Cist Tomb Inscriptions & Chieftain Grave Goods"
    },
    {
        "id": "MEG-04",
        "query": "How were giant pyriform terracotta burial urns (Mudumakkal Thaazhi) engineered to resist subterranean soil pressure over millennia?",
        "expected_slugs": ["concept-mudumakkal-thaazhi-pyriform-urn-engineering", "char-adichanallur-funerary-potter-and-urn-sculptor"],
        "description": "Mudumakkal Thaazhi Pyriform Ceramic Engineering & Hydrostatic Durability"
    },
    {
        "id": "MEG-05",
        "query": "What was the megalithic architecture of dolmenoid cists using interlocking orthostatic granite slabs, port-holes, and cairn circles?",
        "expected_slugs": ["concept-megalithic-cist-and-dolmen-stone-circle-architecture", "place-mallachandram-megalithic-dolmens"],
        "description": "Megalithic Cists & Dolmens: Orthostats, Port-Holes & Lithic Circles"
    },
    {
        "id": "MEG-06",
        "query": "What metallurgical grave goods were buried with Iron Age nobility: gold filigree diadems, iron broadswords, and bronze animal effigies?",
        "expected_slugs": ["concept-iron-age-funerary-iron-weapons-and-bronze-diadems", "char-porunai-megalithic-chieftain"],
        "description": "Gold Filigree Diadems, Forged Iron Weapons & Cast Bronze Figurines"
    },
    {
        "id": "MEG-07",
        "query": "How did the Porunai river valley metallurgical culture combine high-tin bronze casting, Black-and-Red Ware, and wet-rice farming dated to 1155 BCE?",
        "expected_slugs": ["concept-porunai-river-basin-megalithic-metallurgical-ecology", "insc-adichanallur-tamil-brahmi-urn-excavation-records"],
        "description": "Porunai River Basin Metallurgical Ecology & 1155 BCE Antiquity"
    },
    {
        "id": "MEG-08",
        "query": "Where is the largest concentration of over 200 megalithic dolmens and white rock paintings located on the Moraiyar Hill in Krishnagiri?",
        "expected_slugs": ["place-mallachandram-megalithic-dolmens", "concept-megalithic-cist-and-dolmen-stone-circle-architecture"],
        "description": "Mallachandram Moraiyar Hill Megalithic Dolmen Complex"
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
    print("🏺 IRON AGE MEGALITHIC BURIAL ARCHITECTURE & URNS RAG BENCHMARK")
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
