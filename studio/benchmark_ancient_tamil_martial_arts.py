#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Martial Arts, Weaponry & Fortification Architecture Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "WAR-01",
        "query": "How does Purapporul Venbamalai classify ancient Tamil warfare into 12 Puram thinais and what are the siege tactics of Uzhignai and Nochchi?",
        "expected_slugs": ["text-purapporul-venbamalai-military-code", "char-aiyanarithanar-military-theorist", "concept-aran-ancient-fortification"],
        "description": "Purapporul Venbamalai 12 Thinais & Siege Tactics"
    },
    {
        "id": "WAR-02",
        "query": "What is the heroic martial code of Sangam matriarchs in Purananuru 279 as depicted by poetess Okkur Masathiyar?",
        "expected_slugs": ["char-okkur-masathiyar-martial-poetess", "text-purananuru-martial-ethos"],
        "description": "Okkur Masathiyar & Purananuru Matriarchal Valor"
    },
    {
        "id": "WAR-03",
        "query": "How were battlefield wounds sutured with needle and tendon threads in Purananuru 284 field surgical medicine?",
        "expected_slugs": ["text-purananuru-martial-ethos"],
        "description": "Purananuru 284 Battlefield Surgical Triage & Suturing"
    },
    {
        "id": "WAR-04",
        "query": "What historical border skirmishes, cattle raids (Tholuk-kollai), and Eri-patti land grants are recorded on the Chengam Vatteluttu hero-stones?",
        "expected_slugs": ["insc-nadukal-hero-stones-chengam", "concept-nadukal-hero-stone-cult"],
        "description": "Chengam Vatteluttu Hero-Stones & Cattle Raids"
    },
    {
        "id": "WAR-05",
        "query": "What military weapons, iron arrowheads, and daggers were excavated at the Vembakottai archaeological site along the Vaippar river?",
        "expected_slugs": ["arch-vembakottai-weapons-arsenal", "place-vembakottai-archaeological-site"],
        "description": "Vembakottai Excavated Weapons Arsenal & Iron Points"
    },
    {
        "id": "WAR-06",
        "query": "What are the footwork patterns (Kaaladi) and weapon techniques of Silambam bamboo stick fencing and flexible sword (Surul-vaal)?",
        "expected_slugs": ["concept-silambam-stick-fencing", "concept-adimurai-varma-kalai"],
        "description": "Silambam Bamboo Fencing & Surul-Vaal Weaponry"
    },
    {
        "id": "WAR-07",
        "query": "What is the aerodynamic flight mechanism, gyroscopic rotation, and lethal range of the Tamil Valari throwing weapon?",
        "expected_slugs": ["concept-valari-throwing-boomerang"],
        "description": "Valari Aerodynamic Throwing Weapon & Gyroscopic Lift"
    },
    {
        "id": "WAR-08",
        "query": "What are the four classical fortress barriers (Neer-aran, Nilam-aran, Malai-aran, Kaattu-aran) codified in Tirukkural 742 and exemplified at Thirumayam?",
        "expected_slugs": ["concept-aran-ancient-fortification", "place-thirumayam-rock-fortress"],
        "description": "Fourfold Fortress Architecture & Thirumayam Moated Citadel"
    }
]

def get_embedding(query: str) -> list[float]:
    payload = json.dumps({"model": "bge-m3:latest", "prompt": query}).encode("utf-8")
    req = urllib.request.Request(OLLAMA_EMBED_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]

def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_CASES)

    print("=" * 75)
    print("⚔️ ANCIENT TAMIL MARTIAL ARTS, WEAPONRY & FORTIFICATION RAG BENCHMARK")
    print("=" * 75)

    for case in BENCHMARK_CASES:
        vec = get_embedding(case["query"])
        vec_literal = "[" + ",".join(str(x) for x in vec) + "]"

        # Retrieve top 5 closest chunks
        cur.execute("""
            SELECT 
                rc.id,
                rc.node_slug,
                rc.language,
                1 - (rc.embedding <=> %s::vector) AS similarity,
                LEFT(rc.content, 120) AS preview
            FROM rag_chunks rc
            ORDER BY rc.embedding <=> %s::vector ASC
            LIMIT 5;
        """, (vec_literal, vec_literal))

        rows = cur.fetchall()
        top1 = rows[0] if rows else None
        top1_source = top1[1] if top1 else None
        top1_sim = float(top1[3]) if top1 else 0.0

        is_match = top1_source in case["expected_slugs"]
        if is_match:
            passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"\n[{case['id']}] {case['description']}")
        print(f"  Query: \"{case['query']}\"")
        print(f"  Expected: {case['expected_slugs']}")
        print(f"  Top-1: {top1_source} (Cosine Sim: {top1_sim:.4f}) -> {status}")
        if not is_match and rows:
            print("  Top 3 Returned:")
            for i, r in enumerate(rows[:3]):
                print(f"    {i+1}. {r[1]} ({float(r[3]):.4f}) - {r[4].strip()}...")

    conn.close()
    acc = (passed / total) * 100
    print("\n" + "=" * 75)
    print(f"🎯 BENCHMARK RESULTS: {passed}/{total} Passed ({acc:.1f}% Top-1 Accuracy)")
    print("=" * 75)

if __name__ == "__main__":
    main()
