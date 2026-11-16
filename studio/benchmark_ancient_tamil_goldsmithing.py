#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Goldsmithing, Granulation & Filigree Regalia
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "GLD-01",
        "name": "Sangam Goldsmith Verse",
        "query": "Silappadikaram verses on Madurai jewellers street pon sei seri and gold smelting furnaces",
        "expected": [
            "text-silappadikaram-14-verses-on-madurai-jewellers-street-and-gold-refining"
        ]
    },
    {
        "id": "GLD-02",
        "name": "Kundrumani Weight Metrology",
        "query": "Kundrumani Abrus precatorius seed standard gravimetric metrology and manjadi gold units",
        "expected": [
            "concept-kundrumani-abrus-precatorius-standard-seed-gravimetric-metrology"
        ]
    },
    {
        "id": "GLD-03",
        "name": "Blowpipe Cupellation Assay",
        "query": "Thattar kodu and oothu kuzhal clay blowpipe cupellation bone ash hearth gold assaying",
        "expected": [
            "technology-thattar-kodu-and-oothu-kuzhal-blowpipe-cupellation-and-gold-assaying"
        ]
    },
    {
        "id": "GLD-04",
        "name": "Makara Gold Earrings",
        "query": "Makara kundalam mythical sea monster gold filigree earrings and granulated pendants",
        "expected": [
            "artifact-makara-kundalam-gold-filigree-earrings-and-granulated-pendants"
        ]
    },
    {
        "id": "GLD-05",
        "name": "Mercury Fire Gilding",
        "query": "Pon akkam mercury fire gilding depletion gilding and 24 karat surface enrichment",
        "expected": [
            "concept-pon-akkam-gold-mercury-fire-gilding-and-surface-enrichment"
        ]
    },
    {
        "id": "GLD-06",
        "name": "Royal Mint Masters",
        "query": "Akkar and Thattar corporation of royal goldsmiths mint masters and bullion assayers",
        "expected": [
            "institution-akkar-and-thattar-corporation-of-royal-goldsmiths-and-mint-masters"
        ]
    },
    {
        "id": "GLD-07",
        "name": "Gold Granulation Droplets",
        "query": "Kadal mani and micro droplet gold granulation colloidal hard soldering on repousse sheet",
        "expected": [
            "technology-kadal-mani-and-pon-granulation-micro-droplet-gold-soldering"
        ]
    },
    {
        "id": "GLD-08",
        "name": "Madurai Jewellery Haven",
        "query": "Madurai ancient Pandya royal goldsmiths and mint atelier haven Akka Saalai Vaigai",
        "expected": [
            "place-madurai-ancient-pandya-jewellers-guild-haven"
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
    print("BENCHMARK: Ancient Tamil Goldsmithing, Granulation & Filigree Regalia")
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
