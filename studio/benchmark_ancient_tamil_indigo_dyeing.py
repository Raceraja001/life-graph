#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "IND-01",
        "query": "Indigofera tinctoria leaf fermentation microbial hydrolysis indican cleavage to indoxyl",
        "expected_slugs": [
            "concept-indigofera-tinctoria-leaf-fermentation-and-hydrolysis-neeli"
        ],
        "category": "Fermentation Chemistry"
    },
    {
        "id": "IND-02",
        "query": "Alkaline wood-ash lye slaked lime reducing indigotin to soluble leuco-indigo white indigo",
        "expected_slugs": [
            "concept-alkaline-ash-and-slaked-lime-vat-reduction-chemistry"
        ],
        "category": "Vat Reduction"
    },
    {
        "id": "IND-03",
        "query": "Atmospheric aerobic oxidation turning green dipped cloth into permanent deep blue indigotin",
        "expected_slugs": [
            "concept-leuco-indigo-aerobic-oxidation-and-cotton-fiber-binding"
        ],
        "category": "Atmospheric Oxidation"
    },
    {
        "id": "IND-04",
        "query": "Mud-resist dhabu clay and molten beeswax block printing with alum mordant cross-dyeing",
        "expected_slugs": [
            "concept-mud-resist-wax-and-alum-mordant-calico-printing-kalamkari"
        ],
        "category": "Resist Printing"
    },
    {
        "id": "IND-05",
        "query": "Karur Chera textile dyers guild Tamil-Brahmi pot graffiti atan vannan",
        "expected_slugs": [
            "insc-karur-chera-textile-dyers-guild-epigraphs"
        ],
        "category": "Dyers Epigraphy"
    },
    {
        "id": "IND-06",
        "query": "Uraiyur Early Chola excavated burnt brick indigo dyeing cisterns and drainage tanks",
        "expected_slugs": [
            "insc-uraiyur-early-chola-indigo-vat-charters"
        ],
        "category": "Excavated Vats"
    },
    {
        "id": "IND-07",
        "query": "Neeli vannan master indigo dyer judging vat fermentation by coppery surface sheen",
        "expected_slugs": [
            "char-karur-master-indigo-vat-dyer-neeli-vannan"
        ],
        "category": "Master Dyers"
    },
    {
        "id": "IND-08",
        "query": "Karur ancient inland Chera capital textile emporium and indigo dyeing haven",
        "expected_slugs": [
            "place-karur-ancient-indigo-and-textile-haven"
        ],
        "category": "Textile Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Indigo Fermentation, Vat Dyeing & Calico Printing")
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
