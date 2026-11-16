#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Village Irrigation Assemblies, Eri-Variyam & Water Jurisprudence Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "IRI-01",
        "query": "How does the Thirukkural articulate the ethical obligations of sovereigns regarding rainwater conservation, reservoir embankments, and irrigation governance?",
        "expected_slugs": ["text-thiruvalluvar-arasan-neer-management-ethics", "concept-eri-variyam-elected-tank-committee"],
        "description": "Thirukkural Arasan Neer Water Governance Ethics & Tank Ethos"
    },
    {
        "id": "IRI-02",
        "query": "What are the democratic electoral qualifications and disqualifications for the annual Tank Committee (Eri-variyam) in the 921 CE Uttiramerur inscription?",
        "expected_slugs": ["insc-uttiramerur-eri-variyam-tank-charter", "concept-eri-variyam-elected-tank-committee"],
        "description": "Uttiramerur 921 CE Kudavolai Eri-Variyam Charter"
    },
    {
        "id": "IRI-03",
        "query": "What are the permanent gold endowments and daily desilting bullock cart (Eri-vandi) requirements recorded in the Tribhuvani lake epigraphs?",
        "expected_slugs": ["insc-tribhuvani-lake-maintenance-endowment", "place-tribhuvani-chola-irrigation-hub"],
        "description": "Tribhuvani Lake Maintenance Endowments & Eri-Vandi Carts"
    },
    {
        "id": "IRI-04",
        "query": "What were the administrative powers, operational duties, and autonomy of the elected village Tank Committee (Eri-variyam)?",
        "expected_slugs": ["concept-eri-variyam-elected-tank-committee", "concept-eri-variyam-irrigation", "char-eri-variya-perumakan-tank-custodian"],
        "description": "Eri-Variyam Democratic Tank Committee & Water Management"
    },
    {
        "id": "IRI-05",
        "query": "How did Eri-patti land endowments and Eri-ayam grain cesses ring-fence sustainable funding exclusively for lake maintenance and sluice repair?",
        "expected_slugs": ["concept-eri-patti-and-eri-ayam-tank-endowments", "insc-tribhuvani-lake-maintenance-endowment"],
        "description": "Eri-Patti & Eri-Ayam Dedicated Irrigation Endowments"
    },
    {
        "id": "IRI-06",
        "query": "What was the customary legal principle of Murai rotational water rationing used during drought to protect tail-end agrarian fields?",
        "expected_slugs": ["concept-murai-rotational-irrigation-rationing", "concept-eri-variyam-elected-tank-committee"],
        "description": "Murai Rotational Irrigation Rationing & Customary Water Law"
    },
    {
        "id": "IRI-07",
        "query": "What was the civic tradition of Kuda-neer-vetti (Kudimaramathu) where village households contributed communal labor for channel desilting?",
        "expected_slugs": ["concept-kuda-neer-vetti-communal-canal-maintenance", "char-eri-variya-perumakan-tank-custodian"],
        "description": "Kuda-Neer-Vetti Mandatory Civic Canal Desilting Tradition"
    },
    {
        "id": "IRI-08",
        "query": "Where is the historic Chola irrigation center located near Puducherry that established year-round lake desilting cart endowments?",
        "expected_slugs": ["place-tribhuvani-chola-irrigation-hub", "insc-tribhuvani-lake-maintenance-endowment"],
        "description": "Tribhuvani Historic Chola Reservoir & Desilting Hub"
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
    print("💧 VILLAGE IRRIGATION ASSEMBLIES & ERI-VARIYAM RAG BENCHMARK")
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
