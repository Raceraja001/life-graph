#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "COT-01",
        "query": "Acoustic bow-string cotton carding and villadithal panju de-seeding harmonics",
        "expected_slugs": [
            "concept-bow-string-vibrating-cotton-carding-villadithal-panchu"
        ],
        "category": "Cotton Carding"
    },
    {
        "id": "COT-02",
        "query": "Terracotta spindle whorl rotational inertia thakli high twist spinning at Kodumanal",
        "expected_slugs": [
            "concept-terracotta-spindle-whorl-rotational-inertia-and-fine-yarn-spinning"
        ],
        "category": "Drop-Spindle Dynamics"
    },
    {
        "id": "COT-03",
        "query": "Featherlight muslin weaving aaviyanna aadai vapor cloth and serpent slough Argaritic textiles",
        "expected_slugs": [
            "concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai"
        ],
        "category": "Gossamer Weaving"
    },
    {
        "id": "COT-04",
        "query": "Alum mordant dye fixation myrobalan tannins and karai woven selvage tapestry borders",
        "expected_slugs": [
            "concept-natural-mordant-fixation-and-selvage-tapestry-borders"
        ],
        "category": "Mordant Dyeing"
    },
    {
        "id": "COT-05",
        "query": "Perumpanarruppadai verses on serpent slough muslin robes gifted by King Ilandhiraiyan",
        "expected_slugs": [
            "text-perumpanarruppadai-fine-muslin-weaving-and-serpent-slough-poetry"
        ],
        "category": "Sangam Literature"
    },
    {
        "id": "COT-06",
        "query": "Kodumanal excavations inscribed terracotta spindle whorls and Tamil-Brahmi weaver guild marks",
        "expected_slugs": [
            "insc-kodumanal-graffiti-spindle-whorl-and-weaver-guild-marks"
        ],
        "category": "Stratified Archaeology"
    },
    {
        "id": "COT-07",
        "query": "Master muslin weaver Sengannan Kaikoalar calibrating ground pit-looms at Uraiyur",
        "expected_slugs": [
            "char-uraiyur-master-muslin-weaver-aruvai-kaikoalar"
        ],
        "category": "Master Artisans"
    },
    {
        "id": "COT-08",
        "query": "Uraiyur ancient Chola textile capital and Argaritic muslin export haven on Kaveri",
        "expected_slugs": [
            "place-uraiyur-ancient-cotton-muslin-and-textile-guild-haven"
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
    print("BENCHMARK: Ancient Tamil Cotton Ginning & Muslin Weaving")
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
