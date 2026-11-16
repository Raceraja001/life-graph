#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Tamil Mining, Gemmology & Beryl Extraction Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'GEM-01', 'query': 'How does classical Sangam poetry in Akananuru and Purananuru depict the excavation of glowing crystals from mountain veins and lapidary wheels?', 'expected_slugs': ['text-akananuru-gem-mining-and-lapidary-poetry', 'char-kodumanal-master-gem-lapidary-artisan'], 'description': 'Akananuru Gem Mining Poetry & Rotary Lapidary Spindle Verses'}, {'id': 'GEM-02', 'query': 'What do the Tamil-Brahmi inscribed potsherds and quartz bead furnaces excavated at the industrial site of Kodumanal reveal about gem production?', 'expected_slugs': ['insc-kodumanal-beryl-and-quartz-industrial-charters', 'char-kodumanal-master-gem-lapidary-artisan'], 'description': 'Kodumanal Tamil-Brahmi Inscribed Gem Sherds & Quartz Bead Furnaces'}, {'id': 'GEM-03', 'query': 'What are the historical inscriptions and Roman coin hoards at Padiyur documenting imperial aquamarine beryl mines and export concessions?', 'expected_slugs': ['insc-padiyur-sapphire-and-aquamarine-mine-charters', 'place-padiyur-aquamarine-beryl-mines'], 'description': 'Padiyur Aquamarine Deep Shaft Inscriptions & Roman Denarii Hoards'}, {'id': 'GEM-04', 'query': 'How did ancient miners extract beryl from pegmatite veins using fire-setting thermal fracturing, vertical shafts, and timber shoring?', 'expected_slugs': ['concept-open-cast-and-shaft-beryl-pegmatite-mining-mechanics', 'place-padiyur-aquamarine-beryl-mines'], 'description': 'Thermal Fire-Setting Rock Fracturing & Pegmatite Shaft Mining Mechanics'}, {'id': 'GEM-05', 'query': 'What mechanical lapidary methods were used in ancient Tamilakam to facet gem beads using corundum slurry wheels and diamond micro-drills?', 'expected_slugs': ['concept-corundum-slurry-lapidary-wheels-and-gem-faceting', 'insc-kodumanal-beryl-and-quartz-industrial-charters'], 'description': 'Corundum Slurry Lapidary Wheels & Diamond-Tipped Micro-Drilling'}, {'id': 'GEM-06', 'query': 'How were beryl, sapphire, and quartz crystals scientifically classified and inspected for internal flaws in ancient Tamil Ratna-Pariksha gemmology?', 'expected_slugs': ['concept-beryl-classification-and-ratna-pariksha-gemmology', 'text-akananuru-gem-mining-and-lapidary-poetry'], 'description': 'Ratna-Pariksha Gemmological Classification & Cardinal Flaw Inspection'}, {'id': 'GEM-07', 'query': 'How did Indo-Roman trade syndicates transport Kongu beryls and polished beads across the Palakkad Gap to the western port of Musiris?', 'expected_slugs': ['concept-indo-roman-beryl-trade-syndicates-and-export-routes', 'insc-kodumanal-beryl-and-quartz-industrial-charters'], 'description': 'Indo-Roman Beryl Trade Syndicates & Palakkad Gap Caravan Logistics'}, {'id': 'GEM-08', 'query': 'Where were the ancient beryl and aquamarine pegmatite mines of Padiyur situated that supplied the Roman Empire with sea-green crystals?', 'expected_slugs': ['place-padiyur-aquamarine-beryl-mines', 'concept-open-cast-and-shaft-beryl-pegmatite-mining-mechanics'], 'description': 'Padiyur Ancient Pegmatite Aquamarine Mines & Giant Quartz Dykes'}]

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
    print("🎯 ANCIENT TAMIL GEM MINING & BERYL EXTRACTION RAG BENCHMARK")
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
