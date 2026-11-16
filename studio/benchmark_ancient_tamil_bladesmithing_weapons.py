#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "BLA-01",
        "query": "Direct reduction bloomery iron refining and charcoal blast furnace smelting with clay tuyeres",
        "expected_slugs": [
            "concept-bloomery-iron-refining-and-charcoal-hearth-smelting-karumar"
        ],
        "category": "Bloomery Smelting"
    },
    {
        "id": "BLA-02",
        "query": "Pattern welded forge lamination ductile iron core and crucible steel jacket vaal kootral",
        "expected_slugs": [
            "concept-pattern-welded-forge-lamination-and-differential-blade-tempering"
        ],
        "category": "Bladesmithing Lamination"
    },
    {
        "id": "BLA-03",
        "query": "Organic vegetable oil quenching with myrobalan tannins and anti-rust black iron-tannate patina",
        "expected_slugs": [
            "concept-organic-oil-tannin-blade-quenching-and-corrosion-inhibiting-patina"
        ],
        "category": "Thermal Quenching"
    },
    {
        "id": "BLA-04",
        "query": "Spring tempered curved sword koduval and reinforced ribbed vel spearhead geometries",
        "expected_slugs": [
            "concept-spring-tempered-curved-swords-koduval-and-double-edged-vaal"
        ],
        "category": "Weapon Geometry"
    },
    {
        "id": "BLA-05",
        "query": "Purananuru poem 312 blacksmith forge roaring bellows and civic duty of forging spears",
        "expected_slugs": [
            "text-purananuru-blacksmith-hearth-and-iron-welded-spear-poetry"
        ],
        "category": "Martial Literature"
    },
    {
        "id": "BLA-06",
        "query": "Sanur megalithic excavations cist burials iron swords lances and furnace tuyeres",
        "expected_slugs": [
            "insc-sanur-megalithic-iron-weapon-and-blacksmith-guild-epigraphs"
        ],
        "category": "Excavation Inscriptions"
    },
    {
        "id": "BLA-07",
        "query": "Master armorer Maran Kollan forging pattern-welded swords for King Athiyaman at Thakadoor",
        "expected_slugs": [
            "char-thakadoor-royal-bladesmith-and-armorer-karuma-kollan"
        ],
        "category": "Royal Armorers"
    },
    {
        "id": "BLA-08",
        "query": "Sanur ancient megalithic iron smelting citadel and weapons arsenal haven",
        "expected_slugs": [
            "place-sanur-ancient-megalithic-iron-smelting-and-arsenal-haven"
        ],
        "category": "Arsenal Topography"
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Pattern-Welded Bladesmithing & Weapons")
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
