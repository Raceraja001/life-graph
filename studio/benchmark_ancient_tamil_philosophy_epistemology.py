#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Philosophy, Epistemology & Dialectics Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "PHI-01",
        "query": "How does Manimekalai present the Samaya Kanakkar Thanthiram debate between rival philosophical schools and establish Buddhist Pramana-Vada?",
        "expected_slugs": ["text-manimekalai-samaya-kanakkar-epistemology", "char-seethalai-sathanar-philosopher-poet"],
        "description": "Manimekalai Samaya Kanakkar Inter-School Philosophical Debates"
    },
    {
        "id": "PHI-02",
        "query": "What are the Jain logical refutations of Buddhist and Lokayata materialism presented by Nilakesi using Anekantavada multi-faceted logic?",
        "expected_slugs": ["text-nilakesi-jain-epistemological-polemics"],
        "description": "Nilakesi Jain Epistemological Polemics & Anekantavada"
    },
    {
        "id": "PHI-03",
        "query": "How does Meikandar's Sivajnana Bodham formulate the 12 epistemological sutras proving the existence of the Pathi-Pasu-Paasa triad?",
        "expected_slugs": ["text-sivajnana-bodham-saiva-metaphysics", "char-meikandar-epistemological-reformer", "concept-pathi-pasu-paasa-triad"],
        "description": "Sivajnana Bodham 12 Epistemological Sutras & Tripartite Ontology"
    },
    {
        "id": "PHI-04",
        "query": "How does Tolkappiyam Meyppattiyal analyze the eight somatic emotional states (Nagai, Azhugai, Ilivaral, Marutkai, Acham, Perumitham, Vekuli, Uvakai)?",
        "expected_slugs": ["text-tolkappiyam-meyppattiyal-aesthetics", "concept-meyppadu-eightfold-aesthetic-emotions"],
        "description": "Tolkappiyam Meyppattiyal Eightfold Somatic Aesthetic Psychology"
    },
    {
        "id": "PHI-05",
        "query": "What are the three valid means of knowledge in Tamil Pramana-Vada: direct perception (Katchi), inference (Karuthu), and verbal testimony (Urai)?",
        "expected_slugs": ["concept-pramana-vada-tamil-epistemology", "text-manimekalai-samaya-kanakkar-epistemology"],
        "description": "Pramana-Vada Instruments of Valid Knowledge (Katchi, Karuthu, Urai)"
    },
    {
        "id": "PHI-06",
        "query": "What is the 12-link causal chain of Dependent Origination (Pratityasamutpada / Bhavachakra) taught by Aravana Adigal in Manimekalai?",
        "expected_slugs": ["concept-anatta-and-pratityasamutpada-manimekalai", "char-aravanavadigal-buddhist-preceptor"],
        "description": "Dependent Origination (Pratityasamutpada) & Bhavachakra in Manimekalai"
    },
    {
        "id": "PHI-07",
        "query": "What are the three cosmic fetters of Paasa (Anavam, Kanmam, and Maayai) that bind the embodied soul (Pasu) in Saiva Siddhanta?",
        "expected_slugs": ["concept-pathi-pasu-paasa-triad", "text-sivajnana-bodham-saiva-metaphysics"],
        "description": "The Pathi-Pasu-Paasa Tripartite Metaphysical Ontology"
    },
    {
        "id": "PHI-08",
        "query": "Where was the ancient Buddhist monastic university of logic and dialectics located in Kanchipuram where Dignaga and Aravana Adigal taught?",
        "expected_slugs": ["place-kanchipuram-buddhist-dialectical-vihara", "char-aravanavadigal-buddhist-preceptor"],
        "description": "Kanchipuram Raja Vihara Monastic Center of Buddhist Dialectics"
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
    print("📜 ANCIENT TAMIL PHILOSOPHY, EPISTEMOLOGY & DIALECTICS RAG BENCHMARK")
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
