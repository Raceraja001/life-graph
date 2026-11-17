#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Cane Sugar Milling, Jaggery Crystallization & Alambadi Boiling Hydraulics
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
        "id": "SGR-01",
        "title": "Sangam Sugar Milling Verses",
        "query": "Perumpanarruppadai Purananuru sugarcane crushers karumbu aalai boiling syrup verses",
        "expected_slugs": [
            "text-perumpanarruppadai-and-purananuru-on-sugarcane-milling-mills"
        ]
    },
    {
        "id": "SGR-02",
        "title": "Sugarcane Sucrose Physiology",
        "query": "Saccharum officinarum sucrose osmosis phloem accumulation stalk ripening Brix metrics",
        "expected_slugs": [
            "concept-saccharum-officinarum-sucrose-osmosis-and-phloem-ripening"
        ]
    },
    {
        "id": "SGR-03",
        "title": "Three Roller Cane Crusher",
        "query": "Animal driven three roller vertical hardwood sugarcane crusher milling tamarind wood gearing",
        "expected_slugs": [
            "technology-animal-driven-three-roller-vertical-crusher-milling"
        ]
    },
    {
        "id": "SGR-04",
        "title": "Boiling Cauldrons Artifact",
        "query": "Kopparai wrought iron boiling pans bagasse rakes terracotta conical jaggery molds",
        "expected_slugs": [
            "artifact-kopparai-iron-boiling-pans-bagasse-rakes-and-jaggery-molds"
        ]
    },
    {
        "id": "SGR-05",
        "title": "Sucrose Crystallization Chemistry",
        "query": "Sucrose supersaturation crystallization kinetics slaked lime clarification mucilage skimming",
        "expected_slugs": [
            "concept-sucrose-supersaturation-crystallization-kinetics-and-lime-clarification"
        ]
    },
    {
        "id": "SGR-06",
        "title": "Sugar Planters Guild",
        "query": "Karumbu uzhavar vellam vaanigar corporation sugar planters jaggery merchants guild",
        "expected_slugs": [
            "institution-karumbu-uzhavar-and-vellam-vaanigar-sugar-planters-corporation"
        ]
    },
    {
        "id": "SGR-07",
        "title": "Bagasse Furnace Pyrotechnics",
        "query": "Multi stage open pan evaporation bagasse flue furnaces self sustaining pyrotechnics",
        "expected_slugs": [
            "technology-multi-stage-open-pan-evaporation-and-bagasse-flue-furnaces"
        ]
    },
    {
        "id": "SGR-08",
        "title": "Amur Sugar Milling Haven",
        "query": "Amur ancient Chola sugarcane milling haven Kaveri riparian sugar basin citadel",
        "expected_slugs": [
            "place-amur-ancient-chola-sugarcane-milling-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Cane Sugar Milling, Jaggery Crystallization & Alambadi Boiling Hydraulics")
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
