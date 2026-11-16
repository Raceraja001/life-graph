#!/usr/bin/env python3
# Retrieval benchmark for Ancient Tamil Betel Vine Horticulture, Arecanut Hydraulics & Hospitality Rituals
import sys
import time
import requests
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"

TEST_CASES = [
    {
        "id": "BTL-01",
        "name": "Sangam Betel Verse",
        "query": "Silappadikaram verses on spiced betel leaves areca nuts and royal banquets Ilango Adigal",
        "expected": [
            "text-silappadikaram-verses-on-spiced-betel-leaves-areca-nuts-and-royal-banquets"
        ]
    },
    {
        "id": "BTL-02",
        "name": "Piper Betle Physiology",
        "query": "Piper betle horticulture dioecious vine climbers microclimatic humidity and leaf phenolics",
        "expected": [
            "concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology"
        ]
    },
    {
        "id": "BTL-03",
        "name": "Kodi-Kaal Agroforestry",
        "query": "Kodi kaal live agathi hedgerows ridge and furrow hydraulics micro sprinkle irrigation",
        "expected": [
            "technology-kodi-kaal-live-support-agroforestry-agathi-hedgerows-and-ridge-furrow-hydraulics"
        ]
    },
    {
        "id": "BTL-04",
        "name": "Ceremonial Betel Platters",
        "query": "Thaamboola thattil and adappam chased brass betel platters leather pouches and royal bearers",
        "expected": [
            "artifact-thaamboola-thattil-and-adappam-chased-brass-betel-platters-and-areca-nut-shears"
        ]
    },
    {
        "id": "BTL-05",
        "name": "Thaamboolam Pharmacology",
        "query": "Thaamboolam pharmacology arecoline chavicol synergy alkaline salivation and digestive mechanics",
        "expected": [
            "concept-thaamboolam-alkaloid-synergy-arecoline-hydroxychavicol-and-digestive-physiology"
        ]
    },
    {
        "id": "BTL-06",
        "name": "Betel Merchants Guild",
        "query": "Vetrillai vanigar guild of master betel cultivators wholesale consignment merchants and toll epigraphs",
        "expected": [
            "institution-vetrillai-vanigar-and-kodi-kaalar-guild-of-betel-cultivators-and-merchants"
        ]
    },
    {
        "id": "BTL-07",
        "name": "Plantain Sheath Packaging",
        "query": "Ilai kattu moist plantain sheath packaging micro perforated ventilation and dark curing",
        "expected": [
            "technology-ilai-kattu-perforated-moist-plantain-sheath-packaging-and-post-harvest-curing"
        ]
    },
    {
        "id": "BTL-08",
        "name": "Betel Haven Authoor",
        "query": "Authoor ancient Thamirabarani delta betel vine haven kodi kaal groves and GI sanctuary",
        "expected": [
            "place-authoor-ancient-thamirabarani-betel-vine-haven"
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
    print("BENCHMARK: Ancient Tamil Betel Vine Horticulture, Arecanut Hydraulics & Hospitality Rituals")
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
