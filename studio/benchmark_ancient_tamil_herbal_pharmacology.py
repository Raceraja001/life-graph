#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "MED-01",
        "query": "Agasthiyar Gunavagadam verses on Siddha pharmacology and sesame oil Thailam extraction stages",
        "expected_slugs": [
            "text-agasthiyar-gunavagadam-pharmacology-and-thailam-poetry"
        ],
        "category": "Literature & Pharmacology"
    },
    {
        "id": "MED-02",
        "query": "Herbal decoction reduction Kashayam and sesame oil Thailam triple phase extraction chemistry",
        "expected_slugs": [
            "concept-herbal-decoction-reduction-and-sesame-oil-thailam-extraction"
        ],
        "category": "Extraction Chemistry"
    },
    {
        "id": "MED-03",
        "query": "Subterranean herbal steam inhalation Viyarpani and Nochi leaves sweat therapy mechanics",
        "expected_slugs": [
            "concept-subterranean-herbal-steam-inhalation-and-sweat-therapy-viyarpani"
        ],
        "category": "Sudation Therapeutics"
    },
    {
        "id": "MED-04",
        "query": "Calcined metal ash Parpam synthesis in cow dung kilns and Marma trauma leaf poultices",
        "expected_slugs": [
            "concept-calcined-metal-ash-bhasma-and-herbal-marmam-poultices"
        ],
        "category": "Alchemical Parpams"
    },
    {
        "id": "MED-05",
        "query": "Botanical confections Lehiyam and high osmotic palmyra jaggery preservative matrices",
        "expected_slugs": [
            "concept-botanical-confections-lehiyam-and-palm-jaggery-preservatives"
        ],
        "category": "Confectionary Preservation"
    },
    {
        "id": "MED-06",
        "query": "Kollimalai rock epigraphs on medicinal flora protection charters and herbal gathering rights",
        "expected_slugs": [
            "insc-kollimalai-siddha-herbal-sanctuary-and-medicinal-flora-charters"
        ],
        "category": "Sanctuary Epigraphy"
    },
    {
        "id": "MED-07",
        "query": "Master Siddha pharmacologist Maruthuva Sithar practicing Ney Kuri urine diagnostics at Kollimalai",
        "expected_slugs": [
            "char-kollimalai-master-siddha-pharmacologist-maruthuva-sithar"
        ],
        "category": "Master Physicians"
    },
    {
        "id": "MED-08",
        "query": "Kollimalai ancient medicinal flora montane sanctuary and Thailam haven of Valvil Ori",
        "expected_slugs": [
            "place-kollimalai-ancient-medicinal-flora-and-thailam-haven"
        ],
        "category": "Montane Sanctuary Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Herbal Pharmacology & Thailam")
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
