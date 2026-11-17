#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Pearl Fishery Oyster Bed Apnea Diving, Marine Benthic Ecology & Parathavar Guild
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "PRL-01",
        "name": "Sangam Pearl Divers Verse",
        "query": "Maduraikanchi Periplus Korkai Pandyan pearl fishery divers flotillas Sangam era",
        "expected": [
            "text-maduraikanchi-and-periplus-on-korkai-pandya-pearl-fishery-flotillas"
        ]
    },
    {
        "id": "PRL-02",
        "name": "Pearl Oyster Biology",
        "query": "Pinctada radiata pearl oyster nacre secretion aragonite platelets Gulf of Mannar paru reef",
        "expected": [
            "concept-pinctada-radiata-pearl-oyster-biology-and-gulf-of-mannar-shoal-ecology"
        ]
    },
    {
        "id": "PRL-03",
        "name": "Apnea Diving Technology",
        "query": "Apnea breath hold diving amarkkal granite sinker stones valaikoodu rapid descent",
        "expected": [
            "technology-apnea-breath-hold-diving-amarkkal-sinker-stones-and-valaikoodu-bags"
        ]
    },
    {
        "id": "PRL-04",
        "name": "Sinker Stones Artifact",
        "query": "Amarkkal pierced granite sinker stones tortoiseshell nose clips braided dive ropes",
        "expected": [
            "artifact-amarkkal-granite-sinker-stones-tortoiseshell-nose-clips-and-dive-ropes"
        ]
    },
    {
        "id": "PRL-05",
        "name": "Pearl Grading Metrology",
        "query": "Ancient Tamil pearl grading ani thool pazham brass sieves lustre physics manjadi kalanju",
        "expected": [
            "concept-pearl-grading-ani-thool-and-pazham-sieve-metrics-and-lustre-physics"
        ]
    },
    {
        "id": "PRL-06",
        "name": "Shark Binders Guild",
        "query": "Kadal katti shark binders Parathavar pearl diving guild royal Pandyan monopoly",
        "expected": [
            "institution-kadal-katti-shark-binders-and-parathavar-pearl-diving-guild"
        ]
    },
    {
        "id": "PRL-07",
        "name": "Oyster Rotting Technology",
        "query": "Oyster flesh rotting kottu sand trenches enzymatic hydrolysis hydraulic pearl washing",
        "expected": [
            "technology-oyster-flesh-rotting-putrefaction-vats-and-pearl-washing-kinetics"
        ]
    },
    {
        "id": "PRL-08",
        "name": "Pearl Fishery Haven",
        "query": "Kayalpatnam ancient Pandyan pearl fishery haven diver harbor Arab trade emporium",
        "expected": [
            "place-kayalpatnam-ancient-pandya-pearl-fishery-haven"
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
    print("BENCHMARK: Ancient Tamil Pearl Fishery Oyster Bed Apnea Diving, Marine Benthic Ecology & Parathavar Guild")
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
