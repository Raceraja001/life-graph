#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "ZYM-01",
        "query": "Malaipadukadam verses on aged bamboo tube aromatic liquor Theral and mountain hospitality",
        "expected_slugs": [
            "text-malaipadukadam-aged-bamboo-tube-liquor-and-aromatic-theral-poetry"
        ],
        "category": "Literature & Zymurgy"
    },
    {
        "id": "ZYM-02",
        "query": "Double pot clay retort hydro distillation and cold water vapor condensation mechanics",
        "expected_slugs": [
            "concept-double-pot-clay-retort-hydro-distillation-and-vapor-condensation"
        ],
        "category": "Distillation Retorts"
    },
    {
        "id": "ZYM-03",
        "query": "Madhuca longifolia Iluppai flower sugar fermentation and wild cliff honey mead",
        "expected_slugs": [
            "concept-madhuca-longifolia-iluppai-flower-and-wild-honey-fermentation-zymurgy"
        ],
        "category": "Floral Mead Fermentation"
    },
    {
        "id": "ZYM-04",
        "query": "Siddha herbal arishtam decoction with Woodfordia flowers and terracotta tannin maturation",
        "expected_slugs": [
            "concept-herbal-arishtam-decoction-and-bark-tannin-maturation-in-terracotta"
        ],
        "category": "Medicinal Arishtams"
    },
    {
        "id": "ZYM-05",
        "query": "Subterranean amphora cellar aging and wax sealed bamboo internode storage without oxidation",
        "expected_slugs": [
            "concept-subterranean-amphora-cellar-aging-and-bamboo-internode-storage"
        ],
        "category": "Cellar Aging & Preservation"
    },
    {
        "id": "ZYM-06",
        "query": "Alagankulam Mediterranean wine amphora graffiti and terracotta distillation retort epigraphs",
        "expected_slugs": [
            "insc-alagankulam-mediterranean-amphora-and-distillation-retort-epigraphs"
        ],
        "category": "Port Epigraphy & Retorts"
    },
    {
        "id": "ZYM-07",
        "query": "Master aromatic distiller Mattu Sey Thalaivan operating ceramic stills at Alagankulam",
        "expected_slugs": [
            "char-alagankulam-master-aromatic-distiller-mattu-sey-thalaivan"
        ],
        "category": "Master Distillers"
    },
    {
        "id": "ZYM-08",
        "query": "Alagankulam ancient aromatic distillation amphora and maritime haven at Vaigai estuary",
        "expected_slugs": [
            "place-alagankulam-ancient-aromatic-distillation-and-amphora-haven"
        ],
        "category": "Estuarine Port Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Clay Retort Distillation & Zymurgy")
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
