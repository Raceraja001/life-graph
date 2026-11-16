#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Legal Systems, Village Assemblies & Judiciary Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "LAW-01",
        "query": "How does Thirukkural Porutpal define Sengonmai (Righteous Scepter / Rule of Law) and the judicial duty of impartial equity without fear or favor?",
        "expected_slugs": ["text-thirukkural-porutpal-jurisprudence", "concept-sengol-sovereign-rule-of-law"],
        "description": "Thirukkural Sengonmai Jurisprudence & Judicial Impartiality"
    },
    {
        "id": "LAW-02",
        "query": "What are the judicial procedures, manslaughter trials, and restitution sentences (endowing temple lamps) recorded in Chola Dharmasana court inscriptions?",
        "expected_slugs": ["insc-chola-penal-justice-dharmasana", "place-thanjavur-dharmasana-court"],
        "description": "Chola Inscriptional Judiciary, Dharmasana Tribunals & Restitution"
    },
    {
        "id": "LAW-03",
        "query": "What are the constitutional audit and judicial arbitration functions of the Panchavara-Variyam recorded in the Brahmadesam inscription?",
        "expected_slugs": ["insc-brahmadesam-chola-panchavara-variyam", "concept-variyam-standing-committee-governance"],
        "description": "Brahmadesam Inscription & Panchavara-Variyam Executive Governance"
    },
    {
        "id": "LAW-04",
        "query": "How did the Kudavolai pot-ticket electoral system function with palm-leaf ballots drawn by an innocent boy to select ward committee leaders?",
        "expected_slugs": ["concept-kudavolai-pot-ticket-electoral-system", "insc-uttiramerur-kudavolai"],
        "description": "Kudavolai Secret-Ballot Democratic Ward Election System"
    },
    {
        "id": "LAW-05",
        "query": "How was the specialized standing committee system (Variyam) organized into Samvatsara, Eri, Thotta, and Pon committees to govern village republics?",
        "expected_slugs": ["concept-variyam-standing-committee-governance", "concept-ur-and-sabhai-village-republics"],
        "description": "Variyam Standing Committee System (Eri, Thotta, Samvatsara)"
    },
    {
        "id": "LAW-06",
        "query": "What is the symbolic meaning of the Sengol (Straight Scepter) in Tamil statecraft representing unbending justice contrasted with the tyrannical Kodunkol?",
        "expected_slugs": ["concept-sengol-sovereign-rule-of-law", "text-thirukkural-porutpal-jurisprudence"],
        "description": "Sengol Sovereignty & Rule of Law Jurisprudence"
    },
    {
        "id": "LAW-07",
        "query": "What are the structural distinctions between the Ur, the Sabhai (Mahasabha), and the Nagaram in ancient Tamil local village governance?",
        "expected_slugs": ["concept-ur-and-sabhai-village-republics"],
        "description": "Ur, Sabhai, and Nagaram Three-Tier Local Assemblies"
    },
    {
        "id": "LAW-08",
        "query": "Where was the ancient Pandyan democratic assembly township of Manur situated and what property qualifications were required to join the Mahasabha?",
        "expected_slugs": ["place-manur-pandyan-assembly-site", "insc-manur-sabha-rules", "char-manur-sabhai-nyayathipathi"],
        "description": "Manur Pandyan Assembly Township & 800 CE Democratic Qualifications"
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
    print("⚖️ ANCIENT TAMIL LEGAL SYSTEMS & VILLAGE ASSEMBLIES RAG BENCHMARK")
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
