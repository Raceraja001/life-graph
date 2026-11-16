#!/usr/bin/env python3
import requests
import psycopg2
import time

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"

TEST_CASES = [
    {
        "id": "LTH-01",
        "category": "Sangam Martial Verse",
        "query": "Purananuru warrior leather bucklers arrow quivers and blacksmith forge bellows poetry",
        "expected_slugs": [
            "text-purananuru-warrior-leather-bucklers-and-bellows-poetry"
        ]
    },
    {
        "id": "LTH-02",
        "category": "Vegetal Tanning Chemistry",
        "query": "Avaram bark and kadukkai gallnut vegetal tanning protocols thol padaniduthal catechins",
        "expected_slugs": [
            "concept-avaram-bark-and-kadukkai-vegetal-tanning-protocols-thol-padaniduthal"
        ]
    },
    {
        "id": "LTH-03",
        "category": "War Buckler Metallurgy",
        "query": "Multi layered water buffalo hide war bucklers arrow deflecting shields parichai ballistics",
        "expected_slugs": [
            "concept-multi-layered-water-buffalo-hide-war-bucklers-parichai"
        ]
    },
    {
        "id": "LTH-04",
        "category": "Leather Utilitarian Gear",
        "query": "Water resistant animal skins travel flasks and iron furnace bellows engineering thuruthi",
        "expected_slugs": [
            "concept-water-resistant-leather-water-skins-and-smithing-bellows-thuruthi"
        ]
    },
    {
        "id": "LTH-05",
        "category": "Boiled Leather Armor",
        "query": "War elephant trappings chariot traces and body armor cuirasses mey maravadi vandi kattal",
        "expected_slugs": [
            "concept-chariot-harnessry-and-war-elephant-leather-cuirasses-mey-maravadi"
        ]
    },
    {
        "id": "LTH-06",
        "category": "Riverine Epigraphy",
        "query": "Palar basin epigraphs riverine leather guilds tannery vats and temple war drum endowments",
        "expected_slugs": [
            "insc-ranipet-palar-basin-leather-guild-and-tannery-endowments"
        ]
    },
    {
        "id": "LTH-07",
        "category": "Armory Inscriptions",
        "query": "Uraiyur Imperial Chola royal armory charters leather shield and harness guilds velaikaarar",
        "expected_slugs": [
            "insc-uraiyur-chola-military-leather-shield-armory-charters"
        ]
    },
    {
        "id": "LTH-08",
        "category": "Tannery Topography",
        "query": "Ranipet ancient Palar basin leather tannery and guild craft haven North Arcot",
        "expected_slugs": [
            "place-ranipet-ancient-palar-basin-leather-tannery-haven"
        ]
    }
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Leatherworking & War Shields")
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
