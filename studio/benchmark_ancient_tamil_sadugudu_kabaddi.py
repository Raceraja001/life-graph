#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Sadugudu Breath-Hold Tag-Wrestling, Paadi-Kodu Arena Kinematics & Rural Martial Conditioning
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
        "id": "SDG-01",
        "title": "Sangam Malyutham & Sadugudu-Paattu Folk Ballads",
        "query": "Sangam Kalithogai Purananuru mallar malyutham Devaneya Pavanar Sadugudu Paattu oral folk couplets Paadi Aattam",
        "expected_slugs": [
            "text-sangam-malyutham-and-tamil-folk-ballads-on-sadugudu-and-paadi-aattam"
        ]
    },
    {
        "id": "SDG-02",
        "title": "Paaduthal Single-Breath Canting & Apnea Physiology",
        "query": "Paaduthal continuous single breath vocal canting expiratory apnea acoustic bio verification hypercapnic anaerobic raid",
        "expected_slugs": [
            "concept-paaduthal-single-breath-vocal-canting-and-anaerobic-apnea-physiology"
        ]
    },
    {
        "id": "SDG-03",
        "title": "Seven-Defender Chain Arc & Nulle-Kodu Kinematics",
        "query": "Seven defender kai korthal linked wrist chain arc moolai corner nadu kattu thavalai paaychal nulle kodu midline lunge",
        "expected_slugs": [
            "concept-seven-defender-chain-geometry-and-nulle-kodu-midline-kinematics"
        ]
    },
    {
        "id": "SDG-04",
        "title": "Sanjeevani Resurrection & Gaminee Rule Systems",
        "query": "Sanjeevani sequential player revival resurrection uyir peruthal Gaminee total elimination Lona All Out Sadugudu rules",
        "expected_slugs": [
            "concept-sanjeevani-and-goongi-traditional-tamil-sadugudu-revival-and-capture-rules"
        ]
    },
    {
        "id": "SDG-05",
        "title": "Sadugudu-Kalam Sieved Red Earth, Paddy Ash & Neem Pit",
        "query": "Sadugudu kalam triple sieved semman red earth umi saambal paddy husk ash veppam punnakku neem oil cake cushioned pit",
        "expected_slugs": [
            "technology-sadugudu-kalam-cushioned-red-earth-paddy-ash-and-neem-court-preparation"
        ]
    },
    {
        "id": "SDG-06",
        "title": "Kaal-Pidi Ankle-Picks & Muthalai-Pidi Crocodile-Rolls",
        "query": "Kaal pidi low corner ankle pick heel lift muthalai pidi crocodile barrel roll sangili pidi chain tackle grappling",
        "expected_slugs": [
            "technology-kaal-pidi-ankle-picks-muthalai-pidi-crocodile-rolls-and-chain-tackling"
        ]
    },
    {
        "id": "SDG-07",
        "title": "Kida-Parisu Prize Rams & Thookku-Kal Grip-Stones",
        "query": "Kida parisu vettri kida garlanded tournament prize ram thookku kal spherical granite grip lifting stones karlakattai",
        "expected_slugs": [
            "artifact-kida-parisu-champion-fighting-rams-and-kal-eluthu-stone-conditioning-weights"
        ]
    },
    {
        "id": "SDG-08",
        "title": "Peravurani Chola-Coast Sadugudu Arena Haven",
        "query": "Peravurani Pattukkottai Pudukkottai Agniyar marutham red soil coconut coir cushioned Sadugudu Kabaddi arena haven",
        "expected_slugs": [
            "place-peravurani-ancient-chola-sadugudu-arena-and-martial-athletics-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Sadugudu Breath-Hold Tag-Wrestling, Paadi-Kodu Arena Kinematics & Rural Martial Conditioning")
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
