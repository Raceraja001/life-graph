#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Sesame Seed Agronomy, Ellu-Kai-Pidi Shatter-Proof Harvesting, Sesamin Antioxidant Chemistry & Pitru-Tharpanam Rituals
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
        "id": "ELL-01",
        "title": "Sangam Poems on Ellu Capsules & El+Nei Etymology",
        "query": "Malaipadukadam Purananuru Tolkappiyam el plus nei ennai etymology seven sesame pods ellu kaai Sangam dryland",
        "expected_slugs": [
            "text-sangam-purananuru-and-malaipadukadam-on-ellu-sesame-capsules-and-el-nei-etymology"
        ]
    },
    {
        "id": "ELL-02",
        "title": "Thai-Pattam Residual Moisture & Sand-Broadcast Sowing",
        "query": "Sesamum indicum Thai Pattam deep taproot residual subsoil moisture waterlogging sensitivity manal kalanthu vithaithal sand broadcast sowing",
        "expected_slugs": [
            "concept-sesamum-indicum-thai-pattam-residual-moisture-agronomy-and-sand-broadcast-sowing"
        ]
    },
    {
        "id": "ELL-03",
        "title": "Capsule Dehiscence Biomechanics & Acropetal Ripening",
        "query": "Ellu kaai four locule capsule loculicidal suture dehiscence bilayered pericarp shrinkage acropetal bottom to top ripening shatter",
        "expected_slugs": [
            "concept-loculicidal-capsule-dehiscence-biomechanics-and-indeterminate-acropetal-ripening"
        ]
    },
    {
        "id": "ELL-04",
        "title": "Sesamin-Sesamolin Lignan Chemistry & Oxalate Hull",
        "query": "Furofuran lignans sesamin sesamolin thermal conversion sesamol antioxidant rancidity resistance calcium oxalate black testa hull umi",
        "expected_slugs": [
            "concept-sesamin-sesamolin-lignan-antioxidant-chemistry-and-calcium-oxalate-hull-nutrition"
        ]
    },
    {
        "id": "ELL-05",
        "title": "Ellu-Por Conical Stook Curing & Inverted Tap-Threshing",
        "query": "Ellu por conical stook sweat curing koodaram inverted bundle cloth sheet bamboo rod ellu thattuthal three stage tap threshing",
        "expected_slugs": [
            "technology-ellu-por-conical-stook-curing-and-inverted-cloth-bamboo-tap-threshing"
        ]
    },
    {
        "id": "ELL-06",
        "title": "Wet-Friction Dehulling & Stone-Ural Ellurundai Pounding",
        "query": "Karuppu ellu warm water soaking wet friction rubbing umi neekkuthal white vellai ellu stone ural panai karuppatti ellurundai pounding",
        "expected_slugs": [
            "technology-karuppu-ellu-wet-friction-hulling-and-ural-pestle-ellurundai-pounding"
        ]
    },
    {
        "id": "ELL-07",
        "title": "Ellu-Kizhi Sani Lamps & Thila-Tharpanam Libations",
        "query": "Ellu kizhi black cotton cloth pouch wick Saneeswarar Saturday lamp darbha pavitram Pitru Theertham ellu thanneer thila tharpanam",
        "expected_slugs": [
            "artifact-ellu-kizhi-black-sesame-cloth-pouches-sani-deepam-lamps-and-darbha-tharpanam-rings"
        ]
    },
    {
        "id": "ELL-08",
        "title": "Vallioor Pandya Dryland Ellu Agronomy Haven",
        "query": "Vallioor Tirunelveli Nambiyar Western Ghats mullai post Pishanam Thai Pattam sem ellu karuppu ellu dryland oilseed haven",
        "expected_slugs": [
            "place-vallioor-ancient-pandya-ellu-sesame-agronomy-and-dryland-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Sesame Seed Agronomy, Ellu-Kai-Pidi Shatter-Proof Harvesting, Sesamin Antioxidant Chemistry & Pitru-Tharpanam Rituals")
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
