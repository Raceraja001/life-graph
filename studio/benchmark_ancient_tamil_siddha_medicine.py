#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Medicine, Siddha Pharmacology & Pulse Diagnosis Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "MED-01",
        "query": "How does Agathiyar Vaidya Kaviyam define the three humoral pathologies of Mukkutram (Vatham, Pittham, Kapham) and the 96 physiological tattvas?",
        "expected_slugs": ["text-agathiyar-vaidya-kaviyam-siddha", "char-agathiyar-siddha-father"],
        "description": "Agathiyar Vaidya Kaviyam Mukkutram & 96 Tattvas"
    },
    {
        "id": "MED-02",
        "query": "What are the circadian hygienic maxims, dietary rules, and Neikkuri urine oil-drop diagnostic tests formulated by Sage Theraiyar?",
        "expected_slugs": ["text-theraiyar-sekkiruvadukal-hygiene", "char-theraiyar-master-diagnostician"],
        "description": "Theraiyar Circadian Hygiene & Neikkuri Urine Test"
    },
    {
        "id": "MED-03",
        "query": "What is the three-finger radial pulse examination (Nadi Parikshai) and animal gait metaphors for Vatham, Pittham, and Kapham in Siddha diagnosis?",
        "expected_slugs": ["concept-nadi-parikshai-pulse-mechanics", "text-agathiyar-vaidya-kaviyam-siddha"],
        "description": "Nadi Parikshai Three-Finger Radial Pulse & Animal Gaits"
    },
    {
        "id": "MED-04",
        "query": "What is the esoteric Muppu tri-salt catalytic matrix and how does it enable calcination of metals into non-toxic Bhasma and Kaya Kalpa elixirs?",
        "expected_slugs": ["concept-muppu-universal-catalyst", "concept-siddha-herbo-mineral-pharmacology"],
        "description": "Muppu Catalytic Tri-Salt & Kaya Kalpa Longevity"
    },
    {
        "id": "MED-05",
        "query": "How did Siddhar Bogar synthesize the Navapashanam amalgam from nine mineral poisons for the immortal Murugan icon at Palani?",
        "expected_slugs": ["concept-navapashanam-amalgam", "text-bogar-7000-saptha-kandam", "concept-navapashanam-nine-poison-amalgam", "char-bogar-alchemist-sculptor", "place-palani-malai-navapashanam"],
        "description": "Bogar 7000 & Navapashanam Nine-Poison Synthesis"
    },
    {
        "id": "MED-06",
        "query": "What are the 15 inpatient hospital beds, medical staff salaries, and 20 stored medicines recorded in the 1067 CE Thirumukkudal inscription of Veera Rajendra Chola?",
        "expected_slugs": ["insc-thirumukkudal-veera-rajendra-hospital", "place-thirumukkudal-aathula-salai"],
        "description": "Thirumukkudal Inscription 1067 CE Chola Free Hospital"
    },
    {
        "id": "MED-07",
        "query": "What is the Pudam calcination process using sealed clay saucers (Agal) and cow-dung cakes to produce nanostructured Bhasmas and Chendoorams?",
        "expected_slugs": ["concept-siddha-herbo-mineral-pharmacology", "concept-muppu-universal-catalyst"],
        "description": "Pudam Calcination Metallurgy & Herbo-Mineral Pharmacology"
    },
    {
        "id": "MED-08",
        "query": "Where is the sacred Navapashanam Dhandayuthapani shrine and Bogar Siddhar samadhi cave situated in Tamilakam?",
        "expected_slugs": ["place-palani-malai-navapashanam", "char-bogar-alchemist-sculptor"],
        "description": "Palani Murugan Hill Navapashanam Shrine & Bogar Samadhi"
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
    print("🌿 ANCIENT TAMIL MEDICINE & SIDDHA PHARMACOLOGY RAG BENCHMARK")
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
