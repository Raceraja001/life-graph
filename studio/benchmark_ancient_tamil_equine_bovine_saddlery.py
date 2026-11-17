#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Equine & Bovine Saddlery, Mookkanangkayiru Nasal-Halter Biomechanics, Brass Salli-Mani Acoustics & Anthiyur Fair Craft
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
        "id": "SDL-01",
        "title": "Sangam Poems on Pallanam Saddles, Thalaiyattam & Kinkini",
        "query": "Nedunalvaadai Maduraikanchi Ahananuru pallanam horse saddle thalaiyattam crimson plume kadivalam kinkini mani bells",
        "expected_slugs": [
            "text-sangam-ahananuru-and-nedunalvaadai-on-pallanam-saddles-thalaiyattam-and-kinkini-bells"
        ]
    },
    {
        "id": "SDL-02",
        "title": "Mookkanangkayiru Nasal-Septum & Cranial Lever Biomechanics",
        "query": "Mookkanangkayiru bovine nasal septum trigeminal mechanoreceptor cranial moment arm leverage valaiyak kayiru Kangayam bull steering",
        "expected_slugs": [
            "concept-mookkanangkayiru-nasal-septum-mechanoreceptor-leverage-and-bovine-steering-biomechanics"
        ]
    },
    {
        "id": "SDL-03",
        "title": "Salli-Mani Globular Bronze Bell Acoustics & Herd Tracking",
        "query": "Salli mani globular bronze crotal rumble bell ul naakku loose iron pellet Helmholtz slit resonance kotta mani forest herd tracking",
        "expected_slugs": [
            "concept-salli-mani-globular-cattle-bell-helmholtz-resonance-and-forest-herd-localization"
        ]
    },
    {
        "id": "SDL-04",
        "title": "Equine Kadivalam Diastema Bit & Panju-Senam Biomechanics",
        "query": "Kadivalam jointed iron bit toothless mandibular diastema bar pressure panju metthai senam spine clearing kapok bolsters angavadi",
        "expected_slugs": [
            "concept-equine-kadivalam-jointed-bit-oral-bar-pressure-and-angavadi-stirrup-equilibrium"
        ]
    },
    {
        "id": "SDL-05",
        "title": "Mookku-Kuthuthal Septum Piercing & Kombu-Seevuthal",
        "query": "Mookku kuthuthal thulai oosi nasal piercing turmeric neem oil three strand mookkanangkayiru kombu seevuthal horn paring castor oil",
        "expected_slugs": [
            "technology-bovine-nasal-septum-piercing-horn-paring-and-three-strand-mookkanangkayiru-twisting"
        ]
    },
    {
        "id": "SDL-06",
        "title": "Enclosed-Pellet Salli-Mani Casting & Saddle Quilting",
        "query": "Core encapsulated iron clapper pellet sandy clay paddy husk core molten bell metal salli mani casting nada pattai girth weaving",
        "expected_slugs": [
            "technology-cire-perdue-salli-mani-bell-casting-and-panju-metthai-cotton-saddle-quilting"
        ]
    },
    {
        "id": "SDL-07",
        "title": "Kombu-Kuppi Brass Horn-Caps & Cowrie Netri-Pattam",
        "query": "Lathe turned brass kombu kuppi horn tip ferrule kuncham tassels cowrie shell sozhi netri pattam forehead band Mattu Pongal",
        "expected_slugs": [
            "artifact-kombu-kuppi-turned-brass-horn-ferrules-netri-pattam-cowrie-forehead-bands-and-salli-mani-collars"
        ]
    },
    {
        "id": "SDL-08",
        "title": "Anthiyur Gurunathaswamy Horse & Cattle Fair Haven",
        "query": "Anthiyur Erode Bargur foothills Gurunathaswamy Temple Aadi Horse and Cattle Fair Kongu mullai saddlery bell bazaar haven",
        "expected_slugs": [
            "place-anthiyur-ancient-kongu-gurunathaswamy-horse-and-cattle-fair-saddlery-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Equine & Bovine Saddlery, Mookkanangkayiru Nasal-Halter Biomechanics, Brass Salli-Mani Acoustics & Anthiyur Fair Craft")
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
        results = cur.fetchall()

        top1_slug, top1_sim = results[0]
        if top1_slug in expected:
            passed += 1
            print(f"[PASS] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
        else:
            print(f"[FAIL] {qid} ({qtitle})")
            print(f"  Query:    '{query}'")
            print(f"  Expected: {expected}")
            print(f"  Top-1:    {top1_slug} (Sim: {top1_sim:.4f})")
            print("  Top-5:")
            for s, sim in results:
                print(f"    - {s} ({sim:.4f})")

    cur.close()
    conn.close()

    print("=" * 80)
    print(f"SUMMARY: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print("=" * 80)
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
