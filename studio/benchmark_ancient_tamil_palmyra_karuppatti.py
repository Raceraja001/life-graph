#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Palmyra Karuppatti & Panang Kalkandu
Generated automatically.
"""

import sys
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"

BENCHMARK_QUERIES = [
    {
        "id": "KRP-01",
        "title": "Kilinjal Cockle-Shell Lime Dusting & Azhukku Nurai Scum Skimming",
        "query": "Which technology dusted palmyra muttai pots with burnt kilinjal cockle-shell lime, strained padaneer through palm-fibre sieves, and skimmed grey azhukku nurai scum with perforated coconut-shell ladles in an open iron koparai until kambi patham thread stage?",
        "expected_slugs": [
            "technology-padaneer-seashell-lime-inhibition-open-iron-pan-boiling-and-scum-skimming"
        ]
    },
    {
        "id": "KRP-02",
        "title": "Chirattai Half-Shell Molding & Threaded Clay-Pot Kalkandu Burial",
        "query": "How was beaten palm syrup poured into wetted chirattai coconut half-shell molds, while thinner syrup was sealed in unglazed pots strung with cotton threads and buried in paddy husk for 40 to 60 days to grow panang kalkandu?",
        "expected_slugs": [
            "technology-karuppatti-chirattai-molding-and-clay-pot-panang-kalkandu-slow-crystallization"
        ]
    },
    {
        "id": "KRP-03",
        "title": "Dome Karuppatti Blocks & Mudhal-Tharam Kalkandu Grading",
        "query": "What finished goods were hemispherical karuppatti domes with coconut-fibre ridges packed twenty to a kottan, and threaded panang kalkandu druses graded mudhal-tharam, irandam-tharam and thool?",
        "expected_slugs": [
            "artifact-udangudi-karuppatti-coconut-shell-blocks-and-crystalline-panang-kalkandu-clusters"
        ]
    },
    {
        "id": "KRP-04",
        "title": "Ring-Handled Cast-Iron Koparai, Tamarind Oars & Kudai Baskets",
        "query": "What boiling-shed toolkit comprised a 1.2 metre ring-handled cast-iron koparai on a clay-lined trench hearth, tamarind and palmyra-heartwood thuduppu stirring oars, and conical palm-leaf kudai sap baskets?",
        "expected_slugs": [
            "artifact-heavy-cast-iron-boiling-koparai-wooden-stirring-oars-and-palm-leaf-kudai-baskets"
        ]
    },
    {
        "id": "KRP-05",
        "title": "Invertase Suppression, Amadori Rearrangement & HMF Caramelization",
        "query": "What chemistry concept explains calcium hydroxide suppressing invertase beta-fructofuranosidase hydrolysis of sucrose while alkaline open-pan heating accelerates Amadori rearrangement, melanoidin formation and 5-hydroxymethylfurfural caramelization?",
        "expected_slugs": [
            "concept-sucrose-inversion-prevention-by-calcium-hydroxide-and-caramelization-kinetics"
        ]
    },
    {
        "id": "KRP-06",
        "title": "Non-Centrifugal Sugar DPPH/FRAP Antioxidants & Glycemic Index",
        "query": "What nutritional concept describes non-centrifugal karuppatti with gallic and ferulic acid polyphenols, DPPH and FRAP antioxidant capacity, high potassium and iron ash content, and a glycemic index of 35 to 45?",
        "expected_slugs": [
            "concept-polyphenolic-antioxidant-dense-mineral-matrix-and-low-glycemic-nutritional-biochemistry"
        ]
    },
    {
        "id": "KRP-07",
        "title": "Metastable Zone, Heterogeneous Thread Nucleation & Monoclinic Lattice",
        "query": "What crystallization concept contrasts labile-zone shock nucleation by sand-bed beating with metastable-zone growth on cotton thread heterogeneous nucleation sites and capillary dehydration through porous terracotta forming monoclinic sucrose crystals?",
        "expected_slugs": [
            "concept-supersaturated-pan-cooling-nucleation-and-crystal-lattice-growth-in-porous-earthenware"
        ]
    },
    {
        "id": "KRP-08",
        "title": "Nadar Pettai Brokers & the Mahimai Community Cess",
        "query": "What institution of Nadar palm climbers and pettai karuppatti brokers levied a voluntary mahimai cess on every bag of palm sugar to fund schools, wells and choultries while shipping cargoes from Kulasekarapattinam to Rangoon and Penang?",
        "expected_slugs": [
            "institution-teri-sand-dune-nadar-palm-tappers-guilds-and-coastal-karuppatti-mercantile-trusts"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Palmyra Karuppatti & Panang Kalkandu")
    print(f"Model: {MODEL_NAME} | Dimension: 1024 | Total Queries: {len(BENCHMARK_QUERIES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_QUERIES)

    for item in BENCHMARK_QUERIES:
        qid = item["id"]
        qtitle = item["title"]
        query = item["query"]
        expected = item["expected_slugs"]

        q_emb = get_embedding(query)
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
        """, (q_emb, q_emb))
        rows = cur.fetchall()

        matched = False
        top_match = rows[0][0] if rows else "NONE"
        top_sim = rows[0][1] if rows else 0.0

        for rank, (r_slug, r_sim) in enumerate(rows):
            if r_slug in expected:
                matched = True
                status = "PASS" if rank == 0 else f"RANK-{rank+1}"
                print(f"[{qid}] {status} | Top: {top_match} ({top_sim:.4f}) | Expected: {expected}")
                if rank == 0:
                    passed += 1
                break
        if not matched:
            print(f"[{qid}] FAIL | Top: {top_match} ({top_sim:.4f}) | Expected: {expected}")

    print("=" * 80)
    acc = (passed / total) * 100
    print(f"Results: {passed}/{total} passed Top-1 ({acc:.1f}%)")
    print("=" * 80)
    if acc < 100.0:
        sys.exit(1)

if __name__ == "__main__":
    main()
