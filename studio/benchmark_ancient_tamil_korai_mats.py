#!/usr/bin/env python3
"""
Benchmark: Tamil Korai Sedge Mat Weaving, Pattamadai Silk-Grass Mats and Riverine Reed Craft
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
        "id": "KOR-01",
        "title": "Sangam Mat and Reed Bedding Verses",
        "query": "Classical Tamil guide-poems where a bard is given a mat spread on the floor and soft reed bedding for the night",
        "expected_slugs": [
            "text-sangam-paai-and-nanal-reed-mat-bedding-references"
        ]
    },
    {
        "id": "KOR-02",
        "title": "Korai Sedge Cultivation Ecology",
        "query": "Marsh sedge with a solid three-angled stem cultivated from rhizomes under shallow standing water on river margin plots",
        "expected_slugs": [
            "concept-cyperus-pangorei-korai-sedge-ecology-on-thamirabarani-banks"
        ]
    },
    {
        "id": "KOR-03",
        "title": "Softening and Dyeing Strands",
        "query": "Splitting green stalks into thin ribbons, boiling them to soften the pith, then steeping and dyeing with indigo turmeric and root reds",
        "expected_slugs": [
            "concept-korai-stalk-splitting-boiling-and-natural-dye-absorption"
        ]
    },
    {
        "id": "KOR-04",
        "title": "Why Sedge Sleeps Cool",
        "query": "Why a grass floor covering feels cool in humid heat: air filled aerenchyma voids, cellulose adsorbing sweat vapour, reduced skin contact",
        "expected_slugs": [
            "concept-hygroscopic-sedge-aerenchyma-and-thermal-comfort-of-floor-mats"
        ]
    },
    {
        "id": "KOR-05",
        "title": "Mat Loom: Cotton Warp, Sedge Weft",
        "query": "Mat woven as a true cloth of two materials: counted cotton paavu threads lengthwise and single damp sedge oodai strands entered from alternate sides so butt ends even out, no fly shuttle or treadle, output measured in weeks per mat",
        "expected_slugs": [
            "technology-cotton-warp-korai-weft-frame-loom-paai-weaving"
        ]
    },
    {
        "id": "KOR-06",
        "title": "Superfine Mat Grading",
        "query": "Pattu paai grading by strand density per unit length, silk-like handle soft enough to fold and post, Geographical Indication for a Tirunelveli mat",
        "expected_slugs": [
            "technology-pattamadai-pattu-paai-superfine-strand-count-grading"
        ]
    },
    {
        "id": "KOR-07",
        "title": "Bridal Gift Mat Object",
        "query": "Wedding gift sleeping mat with red green and black borders and the couple's names worked into the field, folded in cloth and stored with neem leaves against borers",
        "expected_slugs": [
            "artifact-pattamadai-pattu-paai-bridal-mat-and-storage-rolls"
        ]
    },
    {
        "id": "KOR-08",
        "title": "Pattamadai Village Setting",
        "query": "Village near Ambasamudram on the Porunai river in Tirunelveli district whose name became the brand for fine sleeping mats",
        "expected_slugs": [
            "place-pattamadai-ancient-thamirabarani-korai-mat-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Tamil Korai Sedge Mat Weaving, Pattamadai Silk-Grass Mats and Riverine Reed Craft")
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
        results = cur.fetchall()

        top1_slug, top1_sim = results[0]
        if top1_slug in expected:
            passed += 1
            print(f"[PASS] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for s, sim in results:
                print(f"    - {s} ({sim:.4f})")

    cur.close()
    conn.close()

    print("=" * 80)
    print(f"SUMMARY: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print("=" * 80)
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
