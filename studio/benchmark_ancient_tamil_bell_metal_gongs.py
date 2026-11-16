#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "BEL-01",
        "category": "Sangam Epic Acoustics",
        "query": "Silappadikaram classical verses on temple bronze gongs and bell metal chimes Ilango Adigal",
        "expected_slugs": [
            "text-silappadikaram-temple-bronze-gongs-and-bell-metal-chimes-poetry"
        ]
    },
    {
        "id": "BEL-02",
        "category": "Bell-Metal Metallurgy",
        "query": "High tin bell metal alloy metallurgy and beta phase acoustic quenching venkalam kansa 78 copper",
        "expected_slugs": [
            "concept-high-tin-bell-metal-alloy-metallurgy-and-beta-phase-quenching-venkalam"
        ]
    },
    {
        "id": "BEL-03",
        "category": "Resonant Gongs",
        "query": "Acoustically tuned temple resonance gongs chegandi and sekkandi concentric scraping pranavakara",
        "expected_slugs": [
            "concept-acoustically-tuned-temple-resonance-gongs-chegandi-and-sekkandi"
        ]
    },
    {
        "id": "BEL-04",
        "category": "Lost-Wax Bronze Art",
        "query": "Lost wax cire perdue solid bronze iconography madhuchishta vidhana Cauvery alluvial clay Nataraja",
        "expected_slugs": [
            "concept-lost-wax-cire-perdue-solid-bronze-iconography-madhuchishta-vidhana"
        ]
    },
    {
        "id": "BEL-05",
        "category": "Charcoal Acid Burnishing",
        "query": "Abrasive tamarind acid and fine charcoal mirror finishing venkala palupu tartaric acid burnishing",
        "expected_slugs": [
            "concept-abrasive-tamarind-and-charcoal-mirror-polishing-venkala-palupu"
        ]
    },
    {
        "id": "BEL-06",
        "category": "Foundry Epigraphy",
        "query": "Nachiyarkoil Chola epigraphs on bell metal artisan guild and brazen lamp charters kammaranjeri",
        "expected_slugs": [
            "insc-nachiyarkoil-chola-bell-metal-artisan-guild-and-lamp-endowments"
        ]
    },
    {
        "id": "BEL-07",
        "category": "Gong Dedication Inscriptions",
        "query": "Kumbakonam epigraphs on brazen gong consecration and liturgical acoustics chegandi endowments",
        "expected_slugs": [
            "insc-kumbakonam-brazen-gong-and-temple-chime-consecration-epigraphs"
        ]
    },
    {
        "id": "BEL-08",
        "category": "Metallurgy Topography",
        "query": "Nachiyarkoil ancient Chola bell metal and resonant gong metallurgy haven Thanjavur",
        "expected_slugs": [
            "place-nachiyarkoil-ancient-chola-bell-metal-and-brass-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Bell-Metal Metallurgy & Resonant Gongs")
    print(f"Model: {EMBED_MODEL} | Dimension: 1024 | Total Queries: {len(TEST_CASES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    t0 = time.time()

    for tc in TEST_CASES:
        emb = get_bge_embedding(tc["query"])
        emb_str = "[" + ",".join(str(x) for x in emb) + "]"

        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
        """, (emb_str, emb_str))
        results = cur.fetchall()

        top_slug = results[0][0]
        top_sim = results[0][1]
        is_hit = top_slug in tc["expected_slugs"]
        status = "PASS" if is_hit else "FAIL"
        if is_hit:
            passed += 1

        print(f"[{status}] {tc['id']} ({tc['category']})")
        print(f"  Query:    '{tc['query']}'")
        print(f"  Expected: {tc['expected_slugs']}")
        print(f"  Top-1:    {top_slug} (Sim: {top_sim:.4f})")
        if not is_hit:
            print("  Top-5:")
            for rank, (r_slug, r_sim) in enumerate(results, 1):
                print(f"    {rank}. {r_slug} ({r_sim:.4f})")
        print("-" * 80)

    elapsed = time.time() - t0
    accuracy = (passed / len(TEST_CASES)) * 100
    print(f"RESULTS: {passed}/{len(TEST_CASES)} passed ({accuracy:.1f}%) in {elapsed:.2f}s")
    print("=" * 80)

    cur.close()
    conn.close()
    if passed != len(TEST_CASES):
        exit(1)

if __name__ == "__main__":
    main()
