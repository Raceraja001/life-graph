#!/usr/bin/env python3
"""
Dedicated RAG Benchmark Evaluation Suite:
Ancient Stone Sculptural Engineering, Monolithic Rathas & Pallava Bas-Reliefs Corpus
Evaluates dense vector search (bge-m3:latest, cosine distance) across 8 domain queries.
"""

import json
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"

BENCHMARK_CASES = [{'id': 'SCP-01', 'query': 'How do classical Tamil literary hymns in Nalayira Divya Prabandham and Dandin Avantisundari Katha celebrate the monolithic granite shrines of Mamallapuram?', 'expected_slugs': ['text-mamallapuram-pallava-sculpture-and-vastu-hymns', 'char-mamallapuram-chief-sculptor-perun-thatchan'], 'description': 'Mamallapuram Pallava Sculptural Architecture & Classical Vastu Hymns'}, {'id': 'SCP-02', 'query': 'What are the archaic Pallava Grantha inscriptions on the Dharmaraja Ratha recording the royal titles (Birudas) of Narasimhavarman I Mamalla and master carvers?', 'expected_slugs': ['insc-mamallapuram-dharmaraja-ratha-biruda-epigraphs', 'char-mamallapuram-chief-sculptor-perun-thatchan'], 'description': 'Dharmaraja Ratha Royal Grantha Birudas & Master Sculptor Epigraphs'}, {'id': 'SCP-03', 'query': 'What do the bilingual Grantha and Nagari rock inscriptions on the Atiranachanda cave temple at Saluvankuppam reveal regarding rock excavation art?', 'expected_slugs': ['insc-saluvankuppam-atiranachanda-cave-temple-charters', 'place-saluvankuppam-tiger-cave-and-monolith-sanctuary'], 'description': 'Saluvankuppam Atiranachanda Cave Dual-Script Charters & Rock Engineering'}, {'id': 'SCP-04', 'query': 'How were free-standing granite monoliths excavated from the top down using water-swelled wooden wedges, carbon steel chisels, and terraced quarrying?', 'expected_slugs': ['concept-granite-monolith-scooping-and-quarry-wedge-splitting', 'char-mamallapuram-chief-sculptor-perun-thatchan'], 'description': 'Top-Down Granite Monolith Scooping & Hydrostatic Wedge Splitting'}, {'id': 'SCP-05', 'query': 'What were the mathematical canons of Talamana iconometry, Dasa-tala deity proportions, and plumb-line grids (Sutra) used in ancient Tamil sculpture?', 'expected_slugs': ['concept-talamana-iconometric-proportions-and-shilpa-sastra', 'char-mamallapuram-chief-sculptor-perun-thatchan'], 'description': 'Talamana Iconometric Proportions & Shilpa Plumb-Line Metrology'}, {'id': 'SCP-06', 'query': 'How did Pallava sculptors engineer the colossal Descent of the Ganga bas-relief, integrating a natural granite rock fissure into a celestial water cascade?', 'expected_slugs': ['concept-bas-relief-open-air-frieze-narrative-composition', 'text-mamallapuram-pallava-sculpture-and-vastu-hymns'], 'description': 'Descent of the Ganga Bas-Relief Frieze & Hydraulic Cleft Integration'}, {'id': 'SCP-07', 'query': 'How was the fourfold hierarchy of Sthapati, Sutragrahin, Takshaka, and Vardhaki organized within ancient Tamil stone architectural guilds?', 'expected_slugs': ['concept-sthapati-guild-organization-and-sculptor-titles', 'insc-mamallapuram-dharmaraja-ratha-biruda-epigraphs'], 'description': 'Sthapati Guild Hierarchies, Royal Mason Honors & Ayudha Consecration'}, {'id': 'SCP-08', 'query': 'Where is the seaside archaeological complex of Saluvankuppam located where the Tiger Cave Yali mandapa and submerged pre-Pallava brick shrines were found?', 'expected_slugs': ['place-saluvankuppam-tiger-cave-and-monolith-sanctuary', 'insc-saluvankuppam-atiranachanda-cave-temple-charters'], 'description': 'Saluvankuppam Tiger Cave & Monolithic Rock-Cut Sanctuary Site'}]

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
    print("🎯 PALLAVA STONE SCULPTURAL ENGINEERING & MONOLITHIC RATHAS RAG BENCHMARK")
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
