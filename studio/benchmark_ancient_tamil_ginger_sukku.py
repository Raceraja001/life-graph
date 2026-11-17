#!/usr/bin/env python3
"""
Benchmark: Ancient Tamil Ginger, Sukku & Thirikadugu
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
        "id": "SKK-01",
        "title": "Bamboo-Splinter Peeling, Chunnambu Lime-Water Steeping & Sun-Curing",
        "query": "Which ancient Tamil technology scraped fresh ginger periderm with bamboo splinters, steeped the peeled rhizomes in 2 percent calcium hydroxide chunnambu lime-water, and sun-cured them on palm-leaf platforms until they rang hollow when tapped?",
        "expected_slugs": [
            "technology-inji-rhizome-peeling-lime-water-steeping-and-sukku-sun-curing"
        ]
    },
    {
        "id": "SKK-02",
        "title": "Vasthirakayam Churnam & Inji Lehyam Paagu Stage",
        "query": "How did Siddha pharmacists dry-roast Sukku, Milagu and Thippili in an iron vanali, pound them in a stone ural, sieve through muslin by vasthirakayam, and boil ginger juice with jaggery and ghee to the thread-forming paagu stage for lehyam?",
        "expected_slugs": [
            "technology-thirikadugu-tri-pungent-pulverization-and-inji-lehyam-decoction"
        ]
    },
    {
        "id": "SKK-03",
        "title": "Cow-Dung Sealed Sukku Kudam & Brass Kalvam",
        "query": "What artifacts included chalk-white lime-bloomed dry ginger hands, earthenware kudam jars sealed with cow dung and clay and layered with neem leaves against cigarette beetles, and heavy cast-brass kalvam mortars with pestles?",
        "expected_slugs": [
            "artifact-sun-cured-chalky-sukku-roots-clay-coated-storage-pots-and-brass-pestles"
        ]
    },
    {
        "id": "SKK-04",
        "title": "Candied Inji Murabba & Sukku-Malli Kaapi Brewing Pots",
        "query": "What household objects included candied ginger murabba in palm-sugar syrup stored in glazed jaadi jars, earthen mann-satti pots for brewing dry ginger and coriander seed coffee with karupatti, and blunt wooden ginger scrapers?",
        "expected_slugs": [
            "artifact-inji-murabba-confections-sukku-malli-kaapi-pots-and-wooden-peeling-knives"
        ]
    },
    {
        "id": "SKK-05",
        "title": "Beta-Hydroxy Ketone to Alpha-Beta Enone Dehydration Kinetics",
        "query": "What chemical concept explains the acid-catalysed first-order dehydration of the beta-hydroxy ketone [6]-gingerol into the alpha,beta-unsaturated enone [6]-shogaol above 60 degrees C, its TRPV1 and TRPA1 pungency, and retro-aldol cleavage to zingerone?",
        "expected_slugs": [
            "concept-gingerol-dehydration-to-shogaol-thermal-kinetics-and-pungency-amplification"
        ]
    },
    {
        "id": "SKK-06",
        "title": "Piperine CYP3A4, P-Glycoprotein & Glucuronidation Bioenhancer",
        "query": "What pharmacological concept describes piperine inhibiting CYP3A4, P-glycoprotein efflux and UDP-glucuronosyltransferase to raise curcumin bioavailability by 2000 percent, acting as a yogavahi bioenhancer alongside ginger shogaol?",
        "expected_slugs": [
            "concept-thirikadugu-synergistic-bioavailability-enhancement-and-piperine-shogaol-mechanics"
        ]
    },
    {
        "id": "SKK-07",
        "title": "Kadar, Muthuvan & Paliyar Foragers and Naattu Marundhu Kadai Merchants",
        "query": "What institution linked Anamalai hill tribes such as the Kadar, Muthuvan and Paliyar foraging wild kaattu inji in punam clearings with naattu marundhu kadai raw-drug merchants, Nanadesi trade guilds and the Tirumukkudal temple athular salai hospital?",
        "expected_slugs": [
            "institution-western-ghats-rhizome-foraging-guilds-and-ayurvedic-siddha-marundhu-merchants"
        ]
    },
    {
        "id": "SKK-08",
        "title": "Palghat Gap Winds, Aliyar Valley & Kongu Roman Coin Hoards",
        "query": "Which Kongu Nadu market town at the foot of the Anamalai hills, with dry Palghat Gap winds, Aliyar and Palar valley red soils, a weekly santhai shandy and Roman denarii hoards, served as a ginger and dry-ginger curing haven?",
        "expected_slugs": [
            "place-pollachi-ancient-kongu-inji-ginger-and-sukku-curing-haven"
        ]
    }
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=" * 80)
    print("BENCHMARK: Ancient Tamil Ginger, Sukku & Thirikadugu")
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
