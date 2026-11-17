#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Screwpine Frond Braiding & Keora Attar
Generated automatically.
"""

import sys
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"

BENCHMARK_QUERIES = [
    {
        "id": "THZ-01",
        "title": "Mullu-Vangi De-Thorning & Sun-Dew Frond Bleaching",
        "query": "Which ancient Tamil technology harvested coastal Pandanus odorifer fronds using crescent sickles, stripped needle margins with the mullu-vangi knife, and bleached ribbons on sandbars with sea dew and sunlight?",
        "expected_slugs": [
            "technology-pandanus-odorifer-frond-thorny-margin-paring-splitting-and-sun-bleaching"
        ]
    },
    {
        "id": "THZ-02",
        "title": "24-Plait Twill Mat Weaving & Deg-Bhapka Keora Hydrodistillation",
        "query": "How did classical Neithal artisans plait 24-strand diagonal herringbone twill sleeping mats and conduct steam hydrodistillation in copper deg stills using bamboo chonga conduits into sandalwood oil bhapka receivers?",
        "expected_slugs": [
            "technology-thazham-paai-24-plait-twill-weaving-and-deg-bhapka-keora-attar-hydrodistillation"
        ]
    },
    {
        "id": "THZ-03",
        "title": "Fragrant Bridal Thazham-Paai & Vetrilai Chella-Paai Pouches",
        "query": "What traditional material artifacts included ivory-burnished bridal sleeping mats retaining natural Keora perfume, madder-lined vetrilai-chella-paai betel pouches, and hexagonal woven caskets?",
        "expected_slugs": [
            "artifact-thazham-paai-perfumed-sleeping-mats-betel-pouches-and-woven-baskets"
        ]
    },
    {
        "id": "THZ-04",
        "title": "Copper Deg, Insulated Chonga & Sandalwood Receiver Bhapka",
        "query": "What apparatus comprised hand-hammered copper deg cauldrons, coir-insulated bamboo chonga delivery canes, and cold-submerged copper bhapka receivers containing sandalwood oil for attar capture?",
        "expected_slugs": [
            "artifact-copper-deg-receiver-bhapka-coir-insulation-and-sandalwood-keora-attar-flasks"
        ]
    },
    {
        "id": "THZ-05",
        "title": "2-Phenylethyl Methyl Ether Volatile Chemistry & Sedative Dynamics",
        "query": "What biochemical concept explains the intense diffusion of male Pandanus odorifer spathes containing 65-80 percent 2-phenylethyl methyl ether, terpinen-4-ol, and sedative neuro-olfactory effects?",
        "expected_slugs": [
            "concept-pandanus-odorifer-spathe-phenylethyl-alcohol-methyl-ether-volatile-chemistry"
        ]
    },
    {
        "id": "THZ-06",
        "title": "Sclerenchyma Microfibril Angle & Tensile Flexibility",
        "query": "What biomechanical concept explains why Thazhai leaf fibers possess 450-650 MPa tensile strength, low 10-14 percent lignin, and helical microfibril winding allowing 180-degree folding without brittle rupture?",
        "expected_slugs": [
            "concept-thazhai-vascular-bundle-lignocellulose-pliancy-and-tensile-microstructure"
        ]
    },
    {
        "id": "THZ-07",
        "title": "Neithal Parathavar Foragers, Mat Women & Gandhika Perfume Guilds",
        "query": "What institution organized dawn estuarine flower-gathering Parathavar, household women plaiting 24-strand mats, and Gandhika merchant guilds financing copper distillation apparatus?",
        "expected_slugs": [
            "institution-neithal-parathavar-flower-gatherers-attar-merchants-and-weaving-cottage-guilds"
        ]
    },
    {
        "id": "THZ-08",
        "title": "Pichavaram Mangrove Estuary & Wild Pandanus Screwpine Groves",
        "query": "What ancient Neithal coastal haven situated between the Vellar and Coleroon rivers hosted vast wild screwpine sand dune thickets, dawn flower foraging, and Chidambaram temple attar supplies?",
        "expected_slugs": [
            "place-pichavaram-ancient-neithal-thazhai-screwpine-and-keora-attar-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Screwpine Frond Braiding & Keora Attar")
    print(f"Model: {MODEL_NAME} | Dimension: 1024 | Total Queries: {len(BENCHMARK_QUERIES)}")
    print("=" * 80)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_QUERIES)

    for item in BENCHMARK_QUERIES:
        qid = item["id"]
        qtitle = item["title"]
        query = item["query"]
        expected = item["expected_slugs"]

        q_emb = get_embedding(query)
        cur.execute("""
            SELECT node_slug, 1 - (embedding <=> %s::vector) AS sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT 5;
        """, (q_emb, q_emb))
        rows = cur.fetchall()

        matched = False
        top_match = rows[0][0] if rows else "NONE"
        top_sim = rows[0][1] if rows else 0.0

        for rank, (r_slug, r_sim) in enumerate(rows):
            if r_slug in expected:
                matched = True
                status = "PASS" if rank == 0 else f"RANK-{rank+1}"
                print(f"[{qid}] {status} | Top: {top_match} ({top_sim:.4f}) | Expected: {expected}")
                if rank == 0:
                    passed += 1
                break
        if not matched:
            print(f"[{qid}] FAIL | Top: {top_match} ({top_sim:.4f}) | Expected: {expected}")

    print("=" * 80)
    acc = (passed / total) * 100
    print(f"Results: {passed}/{total} passed Top-1 ({acc:.1f}%)")
    print("=" * 80)
    if acc < 100.0:
        sys.exit(1)

if __name__ == "__main__":
    main()
