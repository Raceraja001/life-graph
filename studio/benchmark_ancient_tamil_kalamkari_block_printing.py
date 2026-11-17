#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Natural Dye Block Printing, Wax-Resist Kalamkari Hand-Painting & Sithira-Aadai Textile Traditions
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "KLM-01",
        "name": "Sangam Painted Garment Verse",
        "query": "Silappadikaram Manimekalai sithira aadai painted garments padumanar dye market Kaveripattinam",
        "expected": [
            "text-silappadikaram-and-manimekalai-on-sithira-aadai-painted-garments-and-bazaar-dyers"
        ]
    },
    {
        "id": "KLM-02",
        "name": "Indigo Mordant Dye Chemistry",
        "query": "Indigo vat reduction madder alizarin mordanting turmeric curcumin myrobalan tannin cotton dye chemistry",
        "expected": [
            "concept-indigo-madder-turmeric-and-myrobalan-mordant-dye-chemistry-on-cotton"
        ]
    },
    {
        "id": "KLM-03",
        "name": "Kalamkari Wax Resist Technology",
        "query": "Kalamkari wax resist batik canting pen khari mordant bamboo pen block printing teak hardwood",
        "expected": [
            "technology-kalamkari-wax-resist-chari-pen-and-block-painting"
        ]
    },
    {
        "id": "KLM-04",
        "name": "Teak Printing Block Artifact",
        "query": "Tharisai kaliru carved teak rosewood block printing natural dye paste tray alignment pins",
        "expected": [
            "artifact-tharisai-carved-teak-printing-block-and-natural-dye-paste-tray"
        ]
    },
    {
        "id": "KLM-05",
        "name": "Wax Resist Capillary Physics",
        "query": "Wax resist capillary penetration cotton fiber crackling halo dye gradient transition zone batik",
        "expected": [
            "concept-wax-resist-capillary-penetration-and-crackling-dye-halos"
        ]
    },
    {
        "id": "KLM-06",
        "name": "Cotton Mordant Pre-Treatment",
        "query": "Cotton myrobalan tannin alum double mordanting ferrous sulfate iron black pre-treatment sequence",
        "expected": [
            "technology-cotton-myrobalan-alum-pre-mordant-treatment-sequence"
        ]
    },
    {
        "id": "KLM-07",
        "name": "Padumanar Dyer Guild",
        "query": "Sikkanayakanpettai kalamkari padumanar guild master dyers Chintamani Brihadeeswara temple textiles",
        "expected": [
            "institution-sikkanayakanpettai-kalamkari-padumanar-guild-of-master-dyers-and-block-printers"
        ]
    },
    {
        "id": "KLM-08",
        "name": "Kalamkari Haven Place",
        "query": "Sikkanayakanpettai ancient Tamil kalamkari haven natural dye block print Thanjavur Kumbakonam",
        "expected": [
            "place-sikkanayakanpettai-ancient-kalamkari-haven"
        ]
    }
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Ollama embedding error: {res.text}")
    return res.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Natural Dye Block Printing, Wax-Resist Kalamkari Hand-Painting & Sithira-Aadai Textile Traditions")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        vec = get_bge_embedding(tc["query"])
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector ASC
            LIMIT 5;
        """, (vec, vec))
        rows = cur.fetchall()
        top1 = rows[0][0] if rows else None
        top1_sim = rows[0][1] if rows else 0.0

        if top1 in tc["expected"]:
            passed += 1
            print(f"[PASS] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {tc['id']} ({tc['name']})")
            print(f"  Query:    '{tc['query']}'")
            print(f"  Expected: {tc['expected']}")
            print(f"  Top-1:    {top1} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for r in rows:
                print(f"    - {r[0]} (Sim: {r[1]:.4f})")

    elapsed = time.time() - t0
    acc = (passed / len(TEST_CASES)) * 100
    print("=" * 80)
    print(f"SUMMARY: {passed}/{len(TEST_CASES)} passed ({acc:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    cur.close()
    conn.close()

    if passed < len(TEST_CASES):
        sys.exit(1)

if __name__ == "__main__":
    main()
