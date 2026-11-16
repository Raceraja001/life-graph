#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "APN-01",
        "category": "Sangam Apnea Verse",
        "query": "Maduraikanchi classical Sangam verses on subaquatic pearl harvesters and chank divers Mankudi Maruthanar",
        "expected_slugs": [
            "text-maduraikanchi-verses-on-gulf-of-mannar-subaquatic-pearl-harvesters"
        ]
    },
    {
        "id": "APN-02",
        "category": "Breath-Hold Conditioning",
        "query": "Moochu adakkal ancient Tamil breath holding lung expansion conditioning hypercapnia tolerance glossopharyngeal",
        "expected_slugs": [
            "concept-moochu-adakkal-ancient-tamil-apnea-and-lung-expansion-conditioning"
        ]
    },
    {
        "id": "APN-03",
        "category": "Sinker Ballasts",
        "query": "Thoorvai kal teardrop granite sinker diving stones rapid descent coir retrieval rope thozhan",
        "expected_slugs": [
            "technology-thoorvai-kal-granite-diving-sinker-stones-and-rope-retrieval"
        ]
    },
    {
        "id": "APN-04",
        "category": "Dive Reflex Physiology",
        "query": "Subaquatic bradycardia conditioning and mammalian dive reflex in Tamil pearl divers splenic contraction",
        "expected_slugs": [
            "concept-mammalian-dive-reflex-and-subaquatic-bradycardia-conditioning"
        ]
    },
    {
        "id": "APN-05",
        "category": "Nose Clips",
        "query": "Mookku channai tortoiseshell buffalo horn spring diving nose clips beeswax lining compression",
        "expected_slugs": [
            "artifact-mookku-channai-tortoiseshell-and-horn-diving-nose-clips"
        ]
    },
    {
        "id": "APN-06",
        "category": "Tympanic Equalization",
        "query": "Sevi theerthal tympanic membrane equalization Eustachian middle ear pressure clearance barotrauma",
        "expected_slugs": [
            "concept-sevi-theerthal-tympanic-equalization-and-eustachian-clearing"
        ]
    },
    {
        "id": "APN-07",
        "category": "Diver Guilds",
        "query": "Muthu kuli sangam Parathavar pearl diver guild and sacred chank extraction corporations Pandyan",
        "expected_slugs": [
            "institution-muthu-kuli-sangam-parathavar-diver-guild-and-chank-guilds"
        ]
    },
    {
        "id": "APN-08",
        "category": "Apnea Topography",
        "query": "Kulasekharapatnam ancient Pandya pearl diving apnea fleet and maritime haven Gulf of Mannar",
        "expected_slugs": [
            "place-kulasekharapatnam-ancient-pearl-diver-and-apnea-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Pearl Diver Breath-Control & Subaquatic Physiology")
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
