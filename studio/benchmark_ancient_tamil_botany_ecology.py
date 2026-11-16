#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Sangam Botany, Ethnobotany & Ecological Landscape Architecture Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [
    {
        "id": "BOT-01",
        "query": "How does Kabilar's Kurinjippattu systematically catalog the 99 indigenous sacred flowers of Tamilakam with botanical precision?",
        "expected_slugs": ["text-kurinjippattu-99-sacred-flowers", "char-kabilar-nature-poet-botanist"],
        "description": "Kurinjippattu 99 Sacred Botanical Flora Catalog"
    },
    {
        "id": "BOT-02",
        "query": "What are the seasonal monsoon dynamics, pastoral flora, and scrub forest ecology documented in Nappoothanar's Mullaippattu?",
        "expected_slugs": ["text-mullaippattu-forest-ecology", "char-peyanar-mullai-pastoral-bard"],
        "description": "Mullaippattu Pastoral Forest Ecology & Monsoon Flora"
    },
    {
        "id": "BOT-03",
        "query": "How does Pathitrupathu describe the rainforest canopy, teak reserves, and tidal estuarine mangrove buffers (Kandal) of the Chera kingdom?",
        "expected_slugs": ["text-pathitrupathu-riverine-mangrove-ecology"],
        "description": "Pathitrupathu Western Ghats Canopy & Mangrove Buffers"
    },
    {
        "id": "BOT-04",
        "query": "What is the holistic Aintinai biogeographical zoning framework in Tolkappiyam connecting terrain, flora, fauna, and human microclimates?",
        "expected_slugs": ["concept-aintinai-biogeographical-zones"],
        "description": "Aintinai Five Biogeographical Zones & Tolkappiyam Ecology"
    },
    {
        "id": "BOT-05",
        "query": "How did traditional community sacred groves (Kavu) function as biodiversity refugia and water table protectors through religious taboos?",
        "expected_slugs": ["concept-sacred-groves-kavu-conservation"],
        "description": "Kavu Sacred Groves & Community Biodiversity Conservation"
    },
    {
        "id": "BOT-06",
        "query": "What medicinal and healing applications of wild flora like Vengai, Neem, and Thumbai are recorded in Sangam ethnobotany?",
        "expected_slugs": ["concept-sangam-ethnobotany-and-healing-flora"],
        "description": "Sangam Ethnobotany & Indigenous Medicinal Flora"
    },
    {
        "id": "BOT-07",
        "query": "What are the fragrant indigenous paddy cultivars (Sennel, Aivanam), lotus pond filtration, and wetland dynamics in the Marutham agro-ecosystem?",
        "expected_slugs": ["concept-marutham-wetland-agro-ecosystem", "char-avvaiyar-ecological-philosopher"],
        "description": "Marutham Wetland Agro-Ecosystem & Scented Paddy Cultivars"
    },
    {
        "id": "BOT-08",
        "query": "What is the ecological significance of the Kolli Hills (Kolli Malai) as a sacred montane medicinal plant sanctuary and Siddha haven?",
        "expected_slugs": ["place-kolli-malai-botanical-sanctuary", "concept-sangam-ethnobotany-and-healing-flora"],
        "description": "Kolli Malai Sacred Botanical Sanctuary & Medicinal Streams"
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
    print("🌺 SANGAM BOTANY, ETHNOBOTANY & ECOLOGICAL ARCHITECTURE RAG BENCHMARK")
    print("=" * 75)

    for case in BENCHMARK_CASES:
        vec = get_embedding(case["query"])
        vec_literal = "[" + ",".join(str(x) for x in vec) + "]"

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
