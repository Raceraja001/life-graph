#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "AST-01",
        "query": "Tholkappiyam protocols on hero stone erection kaatchi kaal-kole and celestial orientation",
        "expected_slugs": [
            "text-tholkappiyam-nadukal-astronomical-erection-and-hero-stone-protocols"
        ],
        "category": "Canonical Protocol"
    },
    {
        "id": "AST-02",
        "query": "Megalithic cup and ring petroglyph star maps charting Pleiades and Ursa Major on dolmens",
        "expected_slugs": [
            "concept-megalithic-cup-and-ring-petroglyph-astronomical-charting-kalthittai"
        ],
        "category": "Star Petroglyphs"
    },
    {
        "id": "AST-03",
        "query": "Menhir solar gnomon solstice and equinox shadow alignments nedungal astronomy",
        "expected_slugs": [
            "concept-solstice-and-equinox-shadow-alignment-of-monumental-menhirs"
        ],
        "category": "Solar Menhirs"
    },
    {
        "id": "AST-04",
        "query": "Pleiades Karttikai lunar mansion heliacal rising stone circle and dolmen porthole azimuth",
        "expected_slugs": [
            "concept-pleiades-karttikai-lunar-mansion-stone-circle-orientations"
        ],
        "category": "Pleiades Alignment"
    },
    {
        "id": "AST-05",
        "query": "Granitic orthostat thermal wedge quarrying and earthen ramp capstone levering kalthittai",
        "expected_slugs": [
            "concept-granitic-orthostat-quarrying-and-levered-capstone-engineering"
        ],
        "category": "Megalithic Engineering"
    },
    {
        "id": "AST-06",
        "query": "Kodumanal excavations astronomical stone circles aligned to celestial North and star graffiti",
        "expected_slugs": [
            "insc-kodumanal-astronomical-stone-circle-and-graffiti-charters"
        ],
        "category": "Cardinal Circles"
    },
    {
        "id": "AST-07",
        "query": "Mallachandram dolmenoid cists white kaolin celestial rock art sunbursts and constellations",
        "expected_slugs": [
            "insc-mallachandram-dolmenoid-cist-and-celestial-petroglyph-epigraphs"
        ],
        "category": "Rock Art Inscriptions"
    },
    {
        "id": "AST-08",
        "query": "Mallachandram ancient megalithic dolmen necropolis and archaeoastronomical haven",
        "expected_slugs": [
            "place-mallachandram-ancient-megalithic-dolmen-and-astronomical-haven"
        ],
        "category": "Archaeoastronomy Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Megalithic Petroglyphs & Archaeoastronomy")
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
