#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Coir Retting, Marine Cordage & Coconut Fiber Rigging
import os
import sys
import json
import uuid
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles"

DOSSIERS = [
    {
        "file": "knowledge/texts/text-akanananuru-verses-on-coconut-fiber-steeping-and-coastal-lagoon-retting.md",
        "slug": "text-akanananuru-verses-on-coconut-fiber-steeping-and-coastal-lagoon-retting",
        "category": "text",
        "name_en": "Akananuru: Classical Sangam Verses on Estuarine Husk Retting & Coir Spinning",
        "name_ta": "\u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 - \u0b95\u0bbe\u0baf\u0bb2\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0bae\u0bcd, \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8 \u0ba8\u0ba9\u0bc8\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Classical Sangam verses depicting coastal littoral communities steeping coconut husks in tidal backwater pits and twisting golden coir cords for fishing nets and oceancraft.",
        "summary_ta": "\u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2 \u0b89\u0baa\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcb\u0bb0\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba4\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Akananuru 240",
            "Natrinai 345",
            "Perumpanattruppadai 310-325"
        ],
        "content": "# Akananuru: Verses on Estuarine Husk Retting & Coir Cordage\n\nIn the coastal landscapes (*neithal*) documented across the Sangam anthology *Akananuru* (particularly poem 240), poets paint vivid scenes of early maritime industrial technology.\n\nLittoral communities inhabiting coastal estuaries (*kayal* and *kazhi*) excavated saline pits in intertidal sands. Green coconut husks (*thengai-mattai*) were bundled into wicker nets and submerged beneath tidally refreshed brackish water for months. \n\nOnce microbial anaerobic fermentation loosened the tough pectin glues, women and elder artisans beat the soaked husks with smooth hardwood clubs (*mungil-thadi*), extracting bundles of golden, lustrous coir fiber (*thumbu* or *naar*). The fibers were immediately spun into rot-proof cordage essential for marine fishing nets, outrigger lashings, and merchant shipping hawsers."
    },
    {
        "file": "knowledge/concepts/concept-naar-azhukkal-anaerobic-saline-husk-retting-and-pectin-decomposition-biochemistry.md",
        "slug": "concept-naar-azhukkal-anaerobic-saline-husk-retting-and-pectin-decomposition-biochemistry",
        "category": "concept",
        "name_en": "Naar-Azhukkal: Brackish Anaerobic Husk Retting & Microbial Pectin Decomposition",
        "name_ta": "\u0ba8\u0bbe\u0bb0\u0bcd \u0b85\u0bb4\u0bc1\u0b95\u0bb2\u0bcd - \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bb2\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8 \u0b8a\u0bb1\u0bb5\u0bc8\u0baa\u0bcd\u0baa\u0bc1, \u0baa\u0bbe\u0b95\u0bcd\u0b9f\u0bc0\u0bb0\u0bbf\u0baf\u0bbe \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0b95\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0b9a\u0bbf\u0ba4\u0bc8\u0bb5\u0bc1 \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Biochemical immersion process where halophilic and anaerobic bacteria in tidal estuarine lagoons break down polyphenols and pectins without damaging the cellulose coir fiber core.",
        "summary_ta": "\u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd 8 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd 10 \u0bae\u0bbe\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bc1\u0baf\u0bbf\u0bb0\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd \u0b9a\u0bbf\u0ba4\u0bc8\u0baf\u0bbe\u0bae\u0bb2\u0bcd \u0baa\u0b9a\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0b95\u0bb3\u0bc8 \u0bae\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0ba4\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Traditional Coir Technology of Kerala & Tamil Nadu",
            "Periplus of the Erythraean Sea",
            "Marine Biodeterioration Studies"
        ],
        "content": "# Naar-Azhukkal: Brackish Anaerobic Husk Retting Biochemistry\n\nThe production of high-tensile, pliable marine-grade coir required prolonged saline immersion (*azhukkal*):\n- **Tidal Water Flushing**: Retting in stagnant freshwater creates foul, dark, brittle fiber. In contrast, coastal estuaries subject to daily tidal ebb and flow provide optimal salinity (10\u201325 ppt) and continuous dissolved oxygen replenishment at the boundary layer.\n- **Microbial Enzymatic Action**: Anaerobic bacterial consortia (predominantly *Clostridium* and *Bacillus* strains) secrete pectinase enzymes that selectively hydrolyze the intercellular middle lamella (pectin and hemicellulose) binding individual fiber bundles.\n- **Tannin Extraction**: Saline flushing leaches out soluble astringent polyphenols and tannins, transforming dark, stiff husks into light, supple, golden-brown fibers resistant to embrittlement."
    },
    {
        "file": "knowledge/technologies/technology-kayiru-thirippu-spindle-twisting-and-multi-ply-marine-hawser-lay-braiding.md",
        "slug": "technology-kayiru-thirippu-spindle-twisting-and-multi-ply-marine-hawser-lay-braiding",
        "category": "technology",
        "name_en": "Kayiru-Thirippu: Spindle-Twisting & Multi-Ply Marine Hawser Lay-Braiding Technology",
        "name_ta": "\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 - \u0ba4\u0b95\u0bcd\u0b95\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0bb4\u0bb2\u0bcd, \u0b87\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8-\u0bae\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bb0\u0bbf \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcb\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Mechanical transformation of combed coir fiber into high-tensile yarn, ropes, and multi-ply anchor hawsers using fly-wheel spindles and synchronized hand-rolling.",
        "summary_ta": "\u0ba4\u0bc2\u0baf\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bc8\u0bb5\u0bbf\u0ba9\u0bc8\u0ba4\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb4\u0bb2\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bbe\u0b95 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0ba4\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0b9a\u0bbe\u0bb0\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Maduraikkanchi 315-325",
            "Traditional Indian Cordage Crafts",
            "Maritime Archaeology of South India"
        ],
        "content": "# Kayiru-Thirippu: Marine Hawser Lay-Braiding\n\nTransforming discontinuous coconut fiber whiskers (15\u201325 cm length) into kilometer-long mooring cables capable of securing thirty-meter merchant *vangams* required sophisticated twisting physics:\n\n1. **Fiber Opening & Carding**: Beaten husks were manually combed across iron-pin carding boards (*naar-seepu*) to remove pith dust (*kombu*) and align parallel fiber bundles.\n2. **Yarn Spinning (*Nool-Thirippu*)**: Two counter-rotating spindles (*thakki* or wooden flywheels) imparted clockwise ('Z'-twist) shear to draw out continuous single-ply yarns.\n3. **Hawser Laying (*Kayiru-Murukku*)**: Three or four 'Z'-twisted strands were combined under tension and twisted counter-clockwise ('S'-twist). The opposing rotational energies neutralized torque, producing balanced, non-kinking ropes with extraordinary shock-absorbing tensile elasticity."
    },
    {
        "file": "knowledge/artifacts/artifact-kattumaram-thamban-salt-resistant-coir-lashing-cables-and-anchor-hawsers.md",
        "slug": "artifact-kattumaram-thamban-salt-resistant-coir-lashing-cables-and-anchor-hawsers",
        "category": "artifact",
        "name_en": "Kattumaram Thamban: Heavy Salt-Resistant Coir Lashing Cables & Anchor Hawsers",
        "name_ta": "\u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bb0\u0ba4\u0bcd \u0ba4\u0bae\u0bcd\u0baa\u0bbe\u0ba9\u0bcd - \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd \u0b8e\u0ba4\u0bbf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1, \u0baa\u0b9f\u0b95\u0bc1 \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0 \u0bb5\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Massive 3-inch to 6-inch diameter coir cables utilized to lash together buoyant hydro-dynamically shaped logs into open-sea surf-riding catamarans and anchor deep-sea vessels.",
        "summary_ta": "\u0b85\u0bb2\u0bc8\u0bae\u0bcb\u0ba4\u0bc1\u0bae\u0bcd \u0b86\u0bb4\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bc8 \u0b92\u0ba9\u0bcd\u0bb1\u0bbe\u0b95\u0baa\u0bcd \u0baa\u0bbf\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd, \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0b9f\u0bb2\u0bbf\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bb5\u0bc1\u0bae\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bae\u0bcd\u0baa\u0bbe\u0ba9\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Purananuru 303",
            "Hornell: The Origins of the Catamaran (1920)",
            "Indian Ocean Maritime Material Culture"
        ],
        "content": "# Kattumaram Thamban: Salt-Resistant Coir Lashing Cables\n\nThe very name *kattumaram* (\"tied logs\" in Tamil) highlights the critical reliance of peninsular naval architecture on high-performance coir cordage (*thamban*).\n\n- **Dynamic Shock Absorption**: Unlike modern synthetic ropes that snap under sudden shock loads, natural coir fibers can stretch up to 30% of their length before breaking, absorbing the violent impact of rolling ocean breakers against surf-riding logs.\n- **Buoyancy**: Because coir possesses an internal cellular lumen filled with trapped air, thick coir anchor hawsers float on seawater, preventing them from dragging on jagged coral reefs and snagging rocky sea floors.\n- **Abrasion Resistance**: Submerged in salt water, coir fibers actually expand and tighten their surface weave, increasing grip and knot-holding security around wet hardwood beams."
    },
    {
        "file": "knowledge/concepts/concept-thengai-naar-tensile-elasticity-and-saltwater-immersion-rot-resistance.md",
        "slug": "concept-thengai-naar-tensile-elasticity-and-saltwater-immersion-rot-resistance",
        "category": "concept",
        "name_en": "Thengai-Naar: High Lignin Cellular Structure, Elasticity & Oceanic Rot Immunity",
        "name_ta": "\u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd - \u0b85\u0ba4\u0bbf\u0b95 \u0bb2\u0bbf\u0b95\u0bcd\u0ba9\u0bbf\u0ba9\u0bcd \u0b9a\u0bc6\u0bb2\u0bcd\u0bb2\u0bc1\u0bb2\u0bcb\u0bb8\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1, \u0bae\u0bc0\u0bb3\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0baa\u0bcd\u0baa\u0bc1\u0ba8\u0bc0\u0bb0\u0bcd \u0b85\u0bb4\u0bc1\u0b95\u0bbe\u0bae\u0bc8 \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Biomechanical analysis of coconut mesocarp fiber containing over 45% lignin, making it the most resilient natural plant fiber against saltwater biodeterioration.",
        "summary_ta": "\u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0ba4\u0bbe\u0bb5\u0bb0 \u0ba8\u0bbe\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bc7\u0baf\u0bc7 45 \u0b9a\u0ba4\u0bb5\u0bc0\u0ba4\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0ba4\u0bbf\u0b95\u0bae\u0bbe\u0ba9 \u0bb2\u0bbf\u0b95\u0bcd\u0ba9\u0bbf\u0ba9\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba4\u0bbe\u0bb2\u0bcd, \u0b95\u0b9f\u0bb2\u0bbf\u0bb2\u0bcd \u0baa\u0bb2 \u0b86\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbf\u0ba9\u0bbe\u0bb2\u0bc1\u0bae\u0bcd \u0b85\u0bb4\u0bc1\u0b95\u0bbe\u0ba4 \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bbf\u0ba9\u0bcd \u0ba8\u0bc1\u0ba3\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "ASTM Textile Fiber Standards",
            "Journal of Natural Fibers Historical Studies",
            "Silappadikaram Chapter 6"
        ],
        "content": "# Thengai-Naar: Lignin Cellular Structure & Oceanic Durability\n\nAmong all vegetable fibers utilized by ancient maritime civilizations (including flax, hemp, jute, and sisal), coconut coir (*thengai-naar*) stands unique in its chemical composition and mechanical longevity:\n\n- **Ultra-High Lignin Content**: Coir fiber comprises 41\u201345% lignin and 36\u201343% cellulose. Lignin is a complex aromatic polymer that is completely indigestible to most marine wood-boring and decomposing organisms, conferring near-total immunity to saltwater rot.\n- **Cellular Lumen & Microfibrillar Angle**: Individual coir cells feature a spiraling microfibril orientation angled at 45 degrees to the fiber axis. This helical spring-like architecture gives coir an elongation capacity of 25\u201340%, unmatched by any other natural bast fiber.\n- **Tensile Resilience**: A single dry coir hawser retains up to 90% of its initial breaking tenacity even after eighteen months of continuous immersion in tropical seawater."
    },
    {
        "file": "knowledge/institutions/institution-valayar-and-naar-thirippor-hereditary-guild-of-coir-spinners-and-rigging-masters.md",
        "slug": "institution-valayar-and-naar-thirippor-hereditary-guild-of-coir-spinners-and-rigging-masters",
        "category": "institution",
        "name_en": "Naar-Thirippor Guild: Hereditary Corporation of Coir Spinners & Naval Rigging Masters",
        "name_ta": "\u0ba8\u0bbe\u0bb0\u0bcd \u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bcb\u0bb0\u0bcd \u0b9a\u0baa\u0bc8 - \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0bcb\u0bb0\u0bcd, \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bb4\u0bc1",
        "era": "Classical Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "neithal",
        "summary_en": "Maritime coastal artisan corporation commanding intertidal retting lagoons, establishing cordage quality standards, and supplying bulk rigging to Chola and Pandya navies.",
        "summary_ta": "\u0b9a\u0bcb\u0bb4\u0bb0\u0bcd, \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0b9f\u0bb1\u0bcd\u0baa\u0b9f\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0bb3\u0bbf\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bb0\u0bae\u0bbe\u0ba9 \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0b89\u0baa\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb4\u0bbf \u0ba8\u0bbe\u0bb0\u0bcd \u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bcb\u0bb0\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bae\u0bcd.",
        "sources": [
            "Kollam Copper Plates (849 CE)",
            "Nagapattinam Port Inscriptions",
            "Ibn Battuta Travels in South India"
        ],
        "content": "# Naar-Thirippor Guild: Naval Rigging Masters\n\nThe immense demand for cordage across Indian Ocean maritime networks spurred the formation of powerful specialized artisan guilds known in epigraphs as *Naar-Thirippor* or *Kayitru-Kammalar*.\n\n- **Retting Rights (*Azhukkal-Kaani*)**: Royal decrees granted the guild legal jurisdiction over tidal estuaries, mudflats, and coconut grove perimeters, regulating the seasonal rotation of retting pits to maintain water quality.\n- **Standardized Cable Gauges**: The guild enforced strict specifications for naval cordage:\n  - *Makkattu-kayiru* (small lashing cord for planks and sails).\n  - *Vangak-kayiru* (medium rigging halyards).\n  - *Perum-thamban* (heavy anchor cables tested against standardized weight limits).\n- **International Commerce**: Medieval travelers including Ibn Battuta and Marco Polo marveled that Chinese junks and Arab dhows visited Kollam and Nagapattinam explicitly to purchase thousands of tons of Tamil coir cordage, celebrated as the world's finest marine binding medium."
    },
    {
        "file": "knowledge/technologies/technology-parambu-pinithal-flexible-coir-stitching-of-ocean-going-hull-planking.md",
        "slug": "technology-parambu-pinithal-flexible-coir-stitching-of-ocean-going-hull-planking",
        "category": "technology",
        "name_en": "Parambu-Pinithal: Sewn-Plank Naval Architecture & Coir-Stitched Hull Flexibility",
        "name_ta": "\u0baa\u0bb1\u0bae\u0bcd\u0baa\u0bc1 \u0baa\u0bbf\u0ba3\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd - \u0ba4\u0bc8\u0baf\u0bb2\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1, \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bbe\u0bb2\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0baa\u0bbf\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Prehistoric to Early Modern Era",
        "year_start": -500,
        "year_end": 1600,
        "thinai": "neithal",
        "summary_en": "Pre-eminent Indian Ocean naval joinery where hardwood hull planks are stitched flush using continuous oiled coir cordage threaded through drilled angled holes over coir wadding.",
        "summary_ta": "\u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b86\u0ba3\u0bbf\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb2\u0bbe\u0b95 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bb3\u0bc8 \u0b92\u0ba9\u0bcd\u0bb1\u0bcb\u0b9f\u0bc1 \u0b92\u0ba9\u0bcd\u0bb1\u0bc1 \u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bc8\u0baf\u0bb2\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Periplus of the Erythraean Sea \u00a760",
            "Silappadikaram Kadalaadukathai",
            "Indian Ocean Sewn Boat Tradition Reports"
        ],
        "content": "# Parambu-Pinithal: Sewn-Plank Naval Architecture\n\nWestern and Chinese observers consistently recorded that traditional Tamil ocean vessels (*vangam*, *padagu*, and *tondi*) were built entirely without iron fastenings, employing *parambu-pinithal* (sewn-plank assembly):\n\n- **Angled Blind Holes**: Hull planks of teak or aini were laid carvel-style (edge to edge). Artisans drilled rows of small angled holes along the inner seams, never piercing the outer face to maintain water-tight exterior surfaces.\n- **Oiled Coir Stitching**: Continuous three-ply coir twine, saturated in boiled fish oil and coconut resin, was stitched back and forth across the seam through the holes, binding the planks under immense manual torque.\n- **Compressive Wadding**: A thick roll of dry coconut husk fiber was laid along the interior seam beneath the stitches. When the boat entered water, the wadding swelled, creating an impenetrable hydraulic gasket.\n- **Wave Flexibility**: The sewn hull could flex and twist under violent monsoon waves without structural fracture, absorbing energies that would shear rigid iron bolts."
    },
    {
        "file": "knowledge/artifacts/artifact-kodi-maram-kayiru-coir-stay-ropes-and-woven-palmyra-mat-sail-rigging.md",
        "slug": "artifact-kodi-maram-kayiru-coir-stay-ropes-and-woven-palmyra-mat-sail-rigging",
        "category": "artifact",
        "name_en": "Kodi-Maram Kayiru: Coir Mast Stays, Shrouds & Woven Palmyra Mat Sail Rigging",
        "name_ta": "\u0b95\u0bca\u0b9f\u0bbf\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 - \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0baa\u0bcd \u0baa\u0b95\u0bcd\u0b95\u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd, \u0baa\u0bbe\u0baf\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bae\u0bcd",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Comprehensive standing and running rigging systems fabricated from tension-balanced coir ropes supporting hardwood masts, yards, and heavy woven palmyra sailcloth.",
        "summary_ta": "\u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0b95\u0bcd\u0b95\u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd \u0ba4\u0bc2\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bcb\u0bb2\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Pattinappalai 170-185",
            "Manimekalai Chapter 25",
            "Chola Maritime Fleet Manuals"
        ],
        "content": "# Kodi-Maram Kayiru: Coir Mast Rigging Systems\n\nThe propulsion of deep-sea Sangam and Chola merchant vessels relied upon towering single or double masts (*kodi-maram*) braced entirely by coir standing rigging:\n\n- **Forestays and Shrouds (*Kodi-Thamban*)**: Thick four-ply coir hawsers anchored the masthead to the gunwales, preventing mast buckling when catching high-velocity monsoon gales (*vadakadu* and *kondal*).\n- **Halyards & Sheets (*Painool-Kayiru*)**: Lighter two-ply ropes used to hoist the massive lateen and square sails woven from dried palmyra leaf matting (*panai-paai*).\n- **Tensile Resilience in Gales**: Unlike stiff hemp that snaps suddenly under cyclonic wind gusts, coir rigging acted as a dynamic shock-dampener, stretching momentarily during sudden squalls to protect the mast from snapping at the deck partners."
    },
    {
        "file": "knowledge/concepts/concept-brackish-estuarine-biotopes-and-sulfate-reducing-microbial-fiber-softening.md",
        "slug": "concept-brackish-estuarine-biotopes-and-sulfate-reducing-microbial-fiber-softening",
        "category": "concept",
        "name_en": "Brackish Estuarine Biotopes & Sulfate-Reducing Microbial Fiber Softening Ecology",
        "name_ta": "\u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0b9a\u0bcd \u0b9a\u0bc2\u0bb4\u0bb2\u0bbf\u0baf\u0bb2\u0bcd - \u0b9a\u0bb2\u0bcd\u0baa\u0bc7\u0b9f\u0bcd \u0b92\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b95\u0bcd\u0b9f\u0bc0\u0bb0\u0bbf\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd \u0bae\u0bc6\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0b9a\u0bc2\u0bb4\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Ecological symbiosis between mangrove backwaters, tidal salinity gradients, and hydrogen-sulfide generating anaerobic bacteria producing superior white coir fibers.",
        "summary_ta": "\u0b95\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcb\u0bb0 \u0b89\u0baa\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b87\u0ba3\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bc1\u0baf\u0bbf\u0bb0\u0bcd\u0b9a\u0bcd \u0b9a\u0bc2\u0bb4\u0bb2\u0bbf\u0bb2\u0bcd, \u0b9a\u0bb2\u0bcd\u0baa\u0bc7\u0b9f\u0bcd \u0baa\u0bbe\u0b95\u0bcd\u0b9f\u0bc0\u0bb0\u0bbf\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b89\u0baf\u0bb0\u0bcd\u0ba4\u0bb0 \u0bb5\u0bc6\u0ba3\u0bcd\u0ba8\u0bbe\u0bb0\u0bcd \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0bc2\u0bb4\u0bb2\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Estuarine and Coastal Marine Science Reports",
            "Purananuru 348",
            "Kerala Backwater Ecology Monographs"
        ],
        "content": "# Brackish Estuarine Biotopes & Microbial Fiber Softening\n\nThe geographical concentration of ancient coir manufacturing along the southwest and southeast coasts was directly determined by unique estuarine coastal ecology (*neithal-kazhi*):\n\n- **Mangrove & Lagoon Synergy**: Dense mangrove wetlands (*alaiyaathi-kaadugal*) filtered terrestrial silt, creating protected, shallow saltwater embayments with high organic sulfur content.\n- **Sulfate-Reducing Bacteria (*Desulfovibrio*)**: In the anaerobic benthic muds of these lagoons, specialized sulfur bacteria reduce seawater sulfates to hydrogen sulfide ($H_2S$), which effectively bleaches and softens the lignified coir fibers without hydrolyzing structural cellulose.\n- **White Coir (*Velli-Naar*)**: Husks retted in these dynamic estuarine biotopes yielded pristine, silky \"white coir,\" prized above all other grades for high-value maritime trade and royal palace furnishings."
    },
    {
        "file": "knowledge/places/place-kollam-ancient-venad-coir-cordage-haven.md",
        "slug": "place-kollam-ancient-venad-coir-cordage-haven",
        "category": "place",
        "name_en": "Kollam: Ancient Venad Maritime Coir Cordage & International Rigging Haven",
        "name_ta": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bb5\u0bc7\u0ba3\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1, \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0ba4\u0bae\u0bcd\u0baa\u0bbe\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Early Historic to Modern Era",
        "year_start": -200,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Premier maritime harbor on the Ashtamudi Lake backwaters, renowned across the Afro-Eurasian trade world as the global capital of marine coir hawser manufacture and naval outfitting.",
        "summary_ta": "\u0b85\u0bb7\u0bcd\u0b9f\u0bae\u0bc1\u0b9f\u0bbf \u0b8f\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bb2\u0bbf\u0ba9\u0bcd \u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4, \u0b9a\u0bb0\u0bcd\u0bb5\u0ba4\u0bc7\u0b9a \u0b85\u0bb3\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1, \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0 \u0bb5\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd \u0b8f\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bb5\u0bc7\u0ba3\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Kollam Syrian Copper Plates (849 CE)",
            "Ibn Battuta Rihla",
            "Marco Polo Travels",
            "Paditruppattu 55"
        ],
        "content": "# Kollam: Ancient Maritime Coir Cordage Haven\n\nSituated on the shores of Ashtamudi Lake where the Kallada River discharges into the Arabian Sea, Kollam (the *Nelcynda* or *Columbo* of ancient geographers, and capital of the southern Chera-Venad dynasty) flourished as the undisputed global capital of the marine coir industry.\n\n- **Vast Retting Estuaries**: The labyrinthine saltwater channels of Ashtamudi provided hundreds of square kilometers of ideal tidal retting beds, capable of processing tens of millions of coconut husks simultaneously.\n- **The Syrian Christian & Local Guild Charters**: The famed *Tarissapalli Copper Plates* (849 CE) granted royal merchant Mar Sapir Iso and indigenous artisan guilds hereditary monopolies over fiber carding, spinning wheel taxes (*naar-vari*), and export duties.\n- **Global Naval Export**: Arab merchant vessels (*markab*) sailing from Oman, Persian Gulf dhows, and Song Dynasty Chinese junks routinely drydocked at Kollam to restock their ships with miles of freshly twisted coir stays, anchor hawsers, and sewn-boat stitching twine."
    }
]

EDGES = [
    [
        "text-akanananuru-verses-on-coconut-fiber-steeping-and-coastal-lagoon-retting",
        "DESCRIBES",
        "concept-naar-azhukkal-anaerobic-saline-husk-retting-and-pectin-decomposition-biochemistry",
        "core",
        "Sangam Era",
        "Akananuru verses depict littoral backwater retting of coconut husks in tidal pits.",
        "Akananuru 240"
    ],
    [
        "concept-naar-azhukkal-anaerobic-saline-husk-retting-and-pectin-decomposition-biochemistry",
        "DEPENDS_ON",
        "concept-brackish-estuarine-biotopes-and-sulfate-reducing-microbial-fiber-softening",
        "core",
        "Prehistoric to Modern Era",
        "Anaerobic husk retting relies upon sulfate-reducing bacteria in tidal mangrove lagoons.",
        "Estuarine and Coastal Marine Science Reports"
    ],
    [
        "concept-naar-azhukkal-anaerobic-saline-husk-retting-and-pectin-decomposition-biochemistry",
        "YIELDS",
        "concept-thengai-naar-tensile-elasticity-and-saltwater-immersion-rot-resistance",
        "core",
        "Prehistoric to Modern Era",
        "Saline immersion leaches tannins and isolates rot-resistant, high-lignin coir fibers.",
        "ASTM Textile Fiber Standards"
    ],
    [
        "concept-thengai-naar-tensile-elasticity-and-saltwater-immersion-rot-resistance",
        "PROCESSED_BY",
        "technology-kayiru-thirippu-spindle-twisting-and-multi-ply-marine-hawser-lay-braiding",
        "core",
        "Iron Age to Modern Era",
        "High-elasticity coir whiskers were spun into balanced multi-ply marine ropes.",
        "Maduraikkanchi 315-325"
    ],
    [
        "technology-kayiru-thirippu-spindle-twisting-and-multi-ply-marine-hawser-lay-braiding",
        "PRODUCES",
        "artifact-kattumaram-thamban-salt-resistant-coir-lashing-cables-and-anchor-hawsers",
        "core",
        "Classical Antiquity to Modern Era",
        "Synchronized spindle twisting produced buoyant, shock-absorbing catamaran lashing cables.",
        "Hornell: The Origins of the Catamaran"
    ],
    [
        "technology-kayiru-thirippu-spindle-twisting-and-multi-ply-marine-hawser-lay-braiding",
        "CONSTRUCTS",
        "artifact-kodi-maram-kayiru-coir-stay-ropes-and-woven-palmyra-mat-sail-rigging",
        "core",
        "Classical Antiquity to Modern Era",
        "Counter-twisted coir hawsers served as flexible standing shrouds and sail halyards.",
        "Pattinappalai 170-185"
    ],
    [
        "technology-kayiru-thirippu-spindle-twisting-and-multi-ply-marine-hawser-lay-braiding",
        "ENABLES",
        "technology-parambu-pinithal-flexible-coir-stitching-of-ocean-going-hull-planking",
        "core",
        "Prehistoric to Early Modern Era",
        "High-tenacity oiled coir twine was stitched through carvel planks to assemble ocean vessels.",
        "Periplus of the Erythraean Sea \u00a760"
    ],
    [
        "technology-kayiru-thirippu-spindle-twisting-and-multi-ply-marine-hawser-lay-braiding",
        "ORGANIZED_BY",
        "institution-valayar-and-naar-thirippor-hereditary-guild-of-coir-spinners-and-rigging-masters",
        "core",
        "Classical Sangam to Medieval Era",
        "Hereditary artisan corporations controlled fiber retting lagoons and cordage standards.",
        "Kollam Copper Plates (849 CE)"
    ],
    [
        "institution-valayar-and-naar-thirippor-hereditary-guild-of-coir-spinners-and-rigging-masters",
        "HEADQUARTERED_AT",
        "place-kollam-ancient-venad-coir-cordage-haven",
        "core",
        "Early Historic to Modern Era",
        "Kollam Ashtamudi backwaters was the global capital of guild-managed naval coir cordage.",
        "Ibn Battuta Rihla"
    ],
    [
        "artifact-kattumaram-thamban-salt-resistant-coir-lashing-cables-and-anchor-hawsers",
        "USED_AT",
        "place-kollam-ancient-venad-coir-cordage-haven",
        "core",
        "Early Historic to Modern Era",
        "Arab dhows and regional fleets outrigged and re-cabled with Kollam coir hawsers.",
        "Marco Polo Travels"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 34...")
    
    # Phase 1: Write Dossiers
    print("Phase 1: Writing Markdown Dossiers...")
    for d in DOSSIERS:
        fpath = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Written: {d['file']}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Phase 2: Upsert Lore Nodes
    print("Phase 2: Upserting Lore Nodes...")
    nodes_upserted = 0
    for d in DOSSIERS:
        slug = d["slug"]
        props = json.dumps({"category": d["category"], "canonical_file": d["file"]})
        cur.execute("""
            INSERT INTO lore_nodes (
                id, slug, node_type, name_en, name_ta, era, year_start, year_end,
                thinai, summary_en, summary_ta, sources, layer, properties, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (slug) DO UPDATE SET
                node_type = EXCLUDED.node_type,
                name_en = EXCLUDED.name_en,
                name_ta = EXCLUDED.name_ta,
                era = EXCLUDED.era,
                year_start = EXCLUDED.year_start,
                year_end = EXCLUDED.year_end,
                thinai = EXCLUDED.thinai,
                summary_en = EXCLUDED.summary_en,
                summary_ta = EXCLUDED.summary_ta,
                sources = EXCLUDED.sources,
                layer = EXCLUDED.layer,
                properties = EXCLUDED.properties;
        """, (
            str(uuid.uuid4()), slug, d["category"], d["name_en"], d["name_ta"],
            d["era"], d["year_start"], d["year_end"], d.get("thinai"),
            d["summary_en"], d["summary_ta"], d["sources"], "core", props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")
    conn.commit()

    # Phase 3: Insert Lore Edges
    print("Phase 3: Inserting Lore Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s;
        """, (src, rel, tgt))
        cur.execute("""
            INSERT INTO lore_edges (
                id, source_slug, relation_type, target_slug, layer, era,
                description, evidence_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            );
        """, (
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, evidence
        ))
        edges_inserted += 1
        print(f"  ✓ Linked: ({src}) --[{rel}]--> ({tgt})")
    conn.commit()

    # Phase 4: Embed & Insert RAG Chunks
    print("Phase 4: Embedding RAG Chunks with bge-m3:latest...")
    total_chunks = 0
    for d in DOSSIERS:
        slug = d["slug"]
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s;", (slug,))
        chunks = [
            {
                "language": "en",
                "title": d["name_en"],
                "content": f"{d['name_en']}\n\nSummary:\n{d['summary_en']}\n\nKey Concepts:\n{d['content'][:1500]}"
            },
            {
                "language": "ta",
                "title": d["name_ta"],
                "content": f"{d['name_ta']}\n\nசுருக்கம்:\n{d['summary_ta']}\n\nமுக்கிய நுட்பங்கள்:\n{d['content'][:1500]}"
            }
        ]
        for ch in chunks:
            emb = get_bge_embedding(ch["content"])
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            cur.execute("""
                INSERT INTO rag_chunks (
                    id, node_slug, shelf, language, title, content,
                    source_ref, embedding, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                );
            """, (
                str(uuid.uuid4()),
                slug,
                f"shelf-{d['category']}s",
                ch["language"],
                ch["title"],
                ch["content"],
                d["file"],
                emb_str
            ))
            total_chunks += 1
        print(f"  ✓ Embedded 2 chunks for: {slug}")
    conn.commit()
    cur.close()
    conn.close()

    print(f"Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
