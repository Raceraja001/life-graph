#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Vaagai Wood & Stone Rotary Oil Pressing, Nallennai Cold-Press Extraction & Ennai-Vaanigar Trade Guild
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "OIL-01",
        "name": "Sangam Oil Merchant Verse",
        "query": "Purananuru Natrinai sesame oil lamps palace streets ennai vaanigar merchants Sangam era",
        "expected": [
            "text-purananuru-and-natrinai-verses-on-sesame-oil-lamps-and-ennai-vaanigar"
        ]
    },
    {
        "id": "OIL-02",
        "name": "Sesamin Antioxidant Chemistry",
        "query": "Sesame oil cold press sesamin sesamolin lignan antioxidant shelf life oleic linoleic fatty acid",
        "expected": [
            "concept-til-oleic-fatty-acid-cold-press-extraction-and-sesamin-antioxidant-chemistry"
        ]
    },
    {
        "id": "OIL-03",
        "name": "Bull-Driven Rotary Press",
        "query": "Marachekku wooden bull driven rotary stone pestle oil press yoke arm granite mortar",
        "expected": [
            "technology-marachekku-wooden-bull-driven-rotary-stone-oil-press"
        ]
    },
    {
        "id": "OIL-04",
        "name": "Seed Pre-Treatment",
        "query": "Chekku seed steaming roasting wet milling pre-treatment maximum cold press oil yield",
        "expected": [
            "technology-chekku-seed-steaming-roasting-and-wet-milling-pre-treatment"
        ]
    },
    {
        "id": "OIL-05",
        "name": "Granite Mortar Artifact",
        "query": "Chekku kallu grooved granite mortar vat stone pestle roller terracotta oil settling jar",
        "expected": [
            "artifact-chekku-kallu-grooved-granite-mortar-and-pestle-roller"
        ]
    },
    {
        "id": "OIL-06",
        "name": "Eccentric Rotation Tribology",
        "query": "Oil press eccentric rotation torque Hertzian contact stress seed cell rupture tribology",
        "expected": [
            "concept-oil-press-torque-eccentric-rotation-and-tribological-seed-crush-physics"
        ]
    },
    {
        "id": "OIL-07",
        "name": "Oil Merchants Guild",
        "query": "Ennai vaanigar guild sesame oil pressers wholesale merchant temple lamp donation caravan",
        "expected": [
            "institution-ennai-vaanigar-guild-of-oil-pressers-wholesalers-and-lamp-oil-caravaners"
        ]
    },
    {
        "id": "OIL-08",
        "name": "Kangayam Oil Press Haven",
        "query": "Kangayam Kongu Nadu sesame groundnut marachekku oil press haven Kangayam cattle breed",
        "expected": [
            "place-kangayam-ancient-kongu-rotary-oil-press-haven"
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
    print("BENCHMARK: Ancient Tamil Vaagai Wood & Stone Rotary Oil Pressing, Nallennai Cold-Press Extraction & Ennai-Vaanigar Trade Guild")
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
