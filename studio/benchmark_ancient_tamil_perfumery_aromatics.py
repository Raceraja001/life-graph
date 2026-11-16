#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Perfumery, Sandalwood Distillation & Aromatic Cosmetology Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "PER-01",
        "query": "How does the Silappadikaram describe the sixty-four fragrant pastes, sandalwood grinding, and agarwood hair-smoking customs?",
        "expected_slugs": ["text-silappadikaram-aromatic-cosmetic-canon", "concept-agarwood-smoking-and-civet-musk-blending"],
        "description": "Silappadikaram Sixty-Four Aromatic Pastes & Akil Smoke Traditions"
    },
    {
        "id": "PER-02",
        "query": "What are the Pandyan epigraphs at Kallidaikurichi regulating sandalwood merchant guild concessions and temple unguent endowments?",
        "expected_slugs": ["insc-kallidaikurichi-sandalwood-guild-charters", "concept-aromatic-guild-networks-and-forest-concessions"],
        "description": "Kallidaikurichi Sandalwood Guild Charters & Transit Toll Remissions"
    },
    {
        "id": "PER-03",
        "query": "What are the Chola royal endowments at Thiruvaiyaru providing gold to purchase imported Barus camphor, saffron, and sandalwood?",
        "expected_slugs": ["insc-thiruvaiyaru-fragrance-endowment-charters", "concept-javvadu-and-attar-herbal-cosmetology"],
        "description": "Thiruvaiyaru Sacred Fragrance Charters & Barus Camphor Ablutions"
    },
    {
        "id": "PER-04",
        "query": "How were basalt grinding slabs (Santhana-kallu) and earthenware alembics used in ancient Tamil sandalwood maceration and hydro-distillation?",
        "expected_slugs": ["concept-sandalwood-grinding-and-clay-hydro-distillation", "char-madurai-master-perfumer-suvanta-karar"],
        "description": "Sandalwood Basalt Grinding & Earthenware Hydro-Distillation Retorts"
    },
    {
        "id": "PER-05",
        "query": "How was agarwood (Akil) smoked beneath wicker frames (Akil-koodu) and stabilized using civet (Punugu) and musk (Kasthuri) fixatives?",
        "expected_slugs": ["concept-agarwood-smoking-and-civet-musk-blending", "char-madurai-master-perfumer-suvanta-karar"],
        "description": "Agarwood Akil-Koodu Wicker Smoking & Animal Fixative Blending"
    },
    {
        "id": "PER-06",
        "query": "What was the cosmetic formulation of Javvadu powder made from sandalwood root flour, saffron, and floral attars?",
        "expected_slugs": ["concept-javvadu-and-attar-herbal-cosmetology", "insc-thiruvaiyaru-fragrance-endowment-charters"],
        "description": "Javvadu Formulation & Herbal Cosmetology Powder Matrices"
    },
    {
        "id": "PER-07",
        "query": "How did merchant corporations like Manigramam manage Western Ghats forest concessions and bulk export of sandalwood and spices?",
        "expected_slugs": ["concept-aromatic-guild-networks-and-forest-concessions", "char-western-ghats-agarwood-harvester"],
        "description": "Aromatic Guild Commercial Networks & Western Ghats Concessions"
    },
    {
        "id": "PER-08",
        "query": "Where was the historic Western Ghats aromatic and sandalwood sanctuary of Courtallam located with medicinal herb cascades?",
        "expected_slugs": ["place-courtallam-aromatic-hill-groves", "char-western-ghats-agarwood-harvester"],
        "description": "Courtallam Historic Aromatic Sanctuary & Medicinal Cascade Biosphere"
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
    print("🌸 ANCIENT PERFUMERY, SANDALWOOD & AROMATIC COSMETOLOGY RAG BENCHMARK")
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
