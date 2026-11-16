#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Veterinary Medicine, Elephant Treatises & Cavalry Management Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'VET-01', 'query': 'How does classical Sangam poetry in Purananuru and Malaipadukadam depict wild elephant capture, acoustic mahout commands, and taming protocols?', 'expected_slugs': ['text-sangam-elephant-training-and-gaja-sastra-hymns', 'char-western-ghats-elephant-kheddah-master'], 'description': 'Sangam Elephant Literature, Mahout Commands & Conditioning Protocols'}, {'id': 'VET-02', 'query': 'What do the Brihadisvara Temple inscriptions at Thanjavur record regarding royal war elephant brigades, mahouts, and veterinary medical endowments?', 'expected_slugs': ['insc-tanjavur-royal-cavalry-and-war-elephant-stables-charters', 'char-thanjavur-royal-chief-veterinary-surgeon'], 'description': 'Thanjavur Brihadisvara Royal Elephant Stables & Anai-yatkal Brigades'}, {'id': 'VET-03', 'query': 'What are the Pandya royal charters from the Vaigai river basin endowing herbal gardens and land grants for horse physicians?', 'expected_slugs': ['insc-madurai-vaigai-cavalry-encampment-charters', 'concept-equine-pulse-diagnosis-and-herbal-veterinary-pharmacology'], 'description': 'Madurai Vaigai Cavalry Encampments & Equine Physician Charters'}, {'id': 'VET-04', 'query': 'How were wild elephants captured in ancient Tamilakam using pitfall trenches (Kuzhi) and timber funnel stockades (Varikoodam or Kheddah)?', 'expected_slugs': ['concept-elephant-capture-kheddah-and-stockade-taming-mechanics', 'place-mudumalai-elephant-forest-sanctuary'], 'description': 'Elephant Pit Trapping Kuzhi & Timber Funnel Stockade Mechanics'}, {'id': 'VET-05', 'query': 'How was protective iron and bronze forehead plating (Mukapadam/Odai) and steel tusk daggers engineered for ancient Tamil war elephants during fort sieges?', 'expected_slugs': ['concept-war-elephant-armor-tusk-swords-and-siege-mechanics', 'char-thanjavur-royal-chief-veterinary-surgeon'], 'description': 'War Elephant Metallic Mukapadam Forehead Plating & Tusk Daggers'}, {'id': 'VET-06', 'query': 'What was the traditional Tamil Siddha veterinary method of equine radial pulse examination (Asva-nadi) and herbal decoctions for horse colic and wound healing?', 'expected_slugs': ['concept-equine-pulse-diagnosis-and-herbal-veterinary-pharmacology', 'insc-madurai-vaigai-cavalry-encampment-charters'], 'description': 'Siddha Equine Pulse Examination Asva-Nadi & Herbal Pharmacology'}, {'id': 'VET-07', 'query': 'How were purebred Arabian and Persian war horses shipped across the Indian Ocean to Tamil ports and traded by Kudirai-chetti merchant guilds?', 'expected_slugs': ['concept-arabian-steed-import-trade-and-horse-guild-charters', 'insc-tanjavur-royal-cavalry-and-war-elephant-stables-charters'], 'description': 'Arabian War Steed Maritime Importation & Kudirai-Chetti Corporations'}, {'id': 'VET-08', 'query': 'Where was the historic elephant forest corridor of Mudumalai located where Sangam royal armies captured and habituated wild elephant herds?', 'expected_slugs': ['place-mudumalai-elephant-forest-sanctuary', 'concept-elephant-capture-kheddah-and-stockade-taming-mechanics'], 'description': 'Mudumalai Ancient Elephant Forest Corridor & Herd Encampments'}]

def get_query_embedding(query_str: str) -> list[float]:
    payload = json.dumps({
        "model": "bge-m3:latest",
        "prompt": query_str
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]

def main():
    print("=" * 75)
    print("🎯 ANCIENT TAMIL VETERINARY MEDICINE & ELEPHANT STABLES RAG BENCHMARK")
    print("=" * 75)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    passed = 0
    total = len(BENCHMARK_CASES)

    for case in BENCHMARK_CASES:
        qid = case["id"]
        query = case["query"]
        expected = case["expected_slugs"]
        desc = case["description"]

        print(f"\n[{qid}] {desc}")
        print(f"  Query: \"{query}\"")
        print(f"  Expected: {expected}")

        q_emb = get_query_embedding(query)
        emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"

        cur.execute("""
            SELECT 
                node_slug,
                title,
                content,
                1 - (embedding <=> %s::vector) as cosine_sim
            FROM rag_chunks
            ORDER BY embedding <=> %s::vector ASC
            LIMIT 3;
        """, (emb_str, emb_str))

        rows = cur.fetchall()
        if not rows:
            print("  ❌ No results returned!")
            continue

        top1_slug = rows[0][0]
        top1_sim = rows[0][3]

        if top1_slug in expected:
            passed += 1
            print(f"  Top-1: {top1_slug} (Cosine Sim: {top1_sim:.4f}) -> ✅ PASS")
        else:
            print(f"  Top-1: {top1_slug} (Cosine Sim: {top1_sim:.4f}) -> ❌ FAIL")
            print("  Top 3 Returned:")
            for i, r in enumerate(rows, 1):
                print(f"    {i}. {r[0]} ({r[3]:.4f}) - {r[1]}")

    accuracy = (passed / total) * 100
    print("\n" + "=" * 75)
    print(f"🎯 BENCHMARK RESULTS: {passed}/{total} Passed ({accuracy:.1f}% Top-1 Accuracy)")
    print("=" * 75 + "\n")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
