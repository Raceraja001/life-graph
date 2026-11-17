#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Ceremonial Fans, Palmyra Folding Visiri, Vetiver Evaporative Cooling & Temple Alavattam Regalia
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
        "id": "FAN-01",
        "title": "Silappadikaram & Chola Inscriptions on Ceremonial Fans",
        "query": "Silappadikaram Perumpanarruppadai Thanjavur Chola inscriptions ven chamarai yak tail whisk alavattam visiri",
        "expected_slugs": [
            "text-silappadikaram-and-chola-inscriptions-on-ven-chamarai-alavattam-and-visiri"
        ]
    },
    {
        "id": "FAN-02",
        "title": "Vetiver Evaporative Cooling & Sesquiterpene Volatiles",
        "query": "Chrysopogon zizanioides vettiver root fan evaporative latent heat wet bulb cooling khusimol alpha beta vetivone sesquiterpene",
        "expected_slugs": [
            "concept-vetiver-root-evaporative-thermodynamics-and-sesquiterpene-volatiles"
        ]
    },
    {
        "id": "FAN-03",
        "title": "Palmyra Accordion-Pleat Stiffness & Petiole Hinge",
        "query": "Borassus flabellifer panai olai corrugated accordion pleat second moment of area bending stiffness mattai kambu petiole hastula",
        "expected_slugs": [
            "concept-borassus-flabellifer-petiole-hinge-mechanics-and-accordion-pleat-stiffness"
        ]
    },
    {
        "id": "FAN-04",
        "title": "Shodasa-Upachara Aeration & Ashta-Mangala Regalia",
        "query": "Kamikagama Shodasa Upachara vyajana chamara seva Ashta Mangala royal sovereignty Surya Chandra sun moon fan symbolism",
        "expected_slugs": [
            "concept-shodasa-upachara-ritual-aeration-and-royal-ashta-mangala-insignia"
        ]
    },
    {
        "id": "FAN-05",
        "title": "Kurutholai Steaming & Collapsible Surul-Visiri Weaving",
        "query": "Kurutholai palmyra frond turmeric boiling Surul Visiri Madakku Visiri 360 degree collapsible folding pocket fan pivot spindle",
        "expected_slugs": [
            "technology-panai-olai-steaming-radial-slitting-and-surul-visiri-pivot-weaving"
        ]
    },
    {
        "id": "FAN-06",
        "title": "Vettiver Twined Braiding & Thanjavur Appliqué Alavattam",
        "query": "Twined vettiver root braiding thazhampoo Pandanus Thanjavur Thayyal Kaarar banath woollen felt velvet applique alavattam hoop",
        "expected_slugs": [
            "technology-vettiver-root-mat-braiding-and-thanjavur-appliqued-alavattam-embroidery"
        ]
    },
    {
        "id": "FAN-07",
        "title": "Mayil-Peeli Peacock-Feather & Bridal Vettiver Fans",
        "query": "Mayil peeli visiri Pavo cristatus peacock eye feather quill lattice Murugan kavadi Siddha mantra veesuthal bridal sabha fan",
        "expected_slugs": [
            "artifact-mayil-peeli-visiri-peacock-feather-fans-and-medicinal-vettiver-hand-fans"
        ]
    },
    {
        "id": "FAN-08",
        "title": "Vallam–Thanjavur Palmyra Visiri & Alavattam Haven",
        "query": "Vallam Thanjavur tableland Kaveri Vennar marutham palmyra surul visiri vettiver fan temple alavattam craft haven",
        "expected_slugs": [
            "place-vallam-ancient-thanjavur-palmyra-visiri-and-vetiver-fan-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Ceremonial Fans, Palmyra Folding Visiri, Vetiver Evaporative Cooling & Temple Alavattam Regalia")
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
