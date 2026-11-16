#!/usr/bin/env python3
# Ingestion harvester for Batch 24 Corpus 1: Coir Cordage & Marine Rigging
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
        "file": "knowledge/texts/text-pattinappalai-ship-rigging-and-coir-cordage-poetry.md",
        "slug": "text-pattinappalai-ship-rigging-and-coir-cordage-poetry",
        "category": "text",
        "name_en": "Pattinappalai Verses on Ocean Ships, Coir Rigging & Hawser Mooring",
        "name_ta": "\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bc8 \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd - \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc2\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 100,
        "thinai": "neithal",
        "summary_en": "Pattinappalai lines 25-40 and 175-185 describing the bustling port of Kaveripattinam: majestic oceanic ships (Vangam) rolling like mountain clouds in the harbor, held fast by immense triple-twisted coconut coir hawsers (Kavan-Kayiru) and taut rigging ropes.",
        "summary_ta": "\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0b95\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf\u0b95\u0bb3\u0bcd: \u0b85\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b86\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0ba9\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4 \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bbe\u0bb2\u0bcd (\u0b95\u0bb5\u0ba3\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1) \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0\u0bae\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Pattinappalai lines 25-40 & 175-185",
            "Akananuru 255",
            "Archaeological Survey of India Poompuhar Underwater Reports"
        ],
        "content": "# Pattinappalai Verses on Ocean Ships, Coir Rigging & Hawser Mooring\n\n## Coastal Port Landscape of Poompuhar\nIn the Sangam masterpiece *Pattinappalai*, the poet Kadiyalur Uruttirangannanar provides an eyewitness portrait of Kaveripattinam, the great maritime emporium of the Cholas. Among its most vivid technical depictions is the port roadstead, where towering sea-going vessels (*Vangam* and *Naavai*) were moored to wooden and stone bitts using massive natural fiber ropes:\n\n```\n\"\u0b95\u0bc2\u0bae\u0bcd\u0baa\u0bca\u0b9f\u0bc1 \u0bae\u0bc0\u0baa\u0bcd\u0baa\u0bbe\u0baf\u0bcd \u0b95\u0bb3\u0bc8\u0baf\u0bbe\u0ba4\u0bc1, \u0bae\u0bb1\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1\n\u0baa\u0bc2\u0b9f\u0bcd\u0b9f\u0bbf\u0baf \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bae\u0bcd \u0bae\u0bbe\u0b95\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0ba8\u0ba3\u0bcd\u0ba3\u0bbf...\"\n\u2014 \u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bc8 29-30\n```\n\nThe poet explicitly describes ships resting in the harbor with their masts erect (*Koompu*) and furled sails held taut by stay-lines and halliards (*Mar-kayiru*), braving the relentless ocean swell.\n\n## The Superiority of Coconut Coir in Saltwater\nWhile inland communities used hemp or grass fibers, oceanic navigation in ancient Tamilakam was utterly dependent on coconut coir (*Thengai naar* / *Kayiru*):\n- **Marine Salt Resistance**: Coir contains naturally high concentrations of lignin (over 40%), making it virtually immune to bacterial decomposition and rotting in tropical seawater.\n- **Dynamic Buoyancy & Elastic Elongation**: Coir ropes float on sea water and stretch up to 25% without snapping, absorbing the violent wave energy of rolling ships that would snap rigid hemp or chain cables.\n\n## Nautical Vocabulary in Sangam Epics\nSangam maritime poetry preserves an intricate terminology for nautical rigging:\n- **Paimara-Kayiru (\u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1)**: Rigging shrouds stabilizing vertical timber masts.\n- **Kavan-Kayiru (\u0b95\u0bb5\u0ba3\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1)**: Heavy mooring cables and anchor hawsers.\n- **Kodu-Kayiru (\u0b95\u0bca\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1)**: Steering sweep lashing and rudder control cords.",
        "chunks": [
            {
                "language": "en",
                "title": "Pattinappalai Ocean Rigging & Marine Coir Mechanics",
                "content": "Pattinappalai verses document the advanced coir rope rigging of ocean-going ships in ancient Kaveripattinam, where high-lignin coconut fiber cables (Mar-kayiru) provided saltwater-resistant elasticity and anchor mooring strength."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bc8 \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0\u0bae\u0bc1\u0bae\u0bcd",
                "content": "\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bb5\u0ba3\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b85\u0bb4\u0bc1\u0b95\u0bbe\u0ba4 \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bbf\u0ba9\u0bcd \u0b89\u0bb1\u0bc1\u0ba4\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc0\u0bb3\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bc8 \u0bb5\u0bc6\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0b95\u0b9f\u0bb2\u0bcb\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-brackish-estuarine-coconut-husk-retting-and-pectin-hydrolysis.md",
        "slug": "concept-brackish-estuarine-coconut-husk-retting-and-pectin-hydrolysis",
        "category": "concept",
        "name_en": "Brackish Estuarine Coconut Husk Retting & Pectin Hydrolysis",
        "name_ta": "\u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8 \u0b8a\u0bb1\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0b95\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0b9a\u0bbf\u0ba4\u0bc8\u0bb5\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Biochemical retting technology soaking fibrous coconut husks in tidal brackish estuarine lagoons for 6 to 10 months, where halophilic bacteria hydrolyze pectin and polyphenol binders to free pristine, golden coir fibers.",
        "summary_ta": "\u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bc1\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 6 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd 10 \u0bae\u0bbe\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bb5\u0bb0\u0bc8 \u0baa\u0bc1\u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0baa\u0bbe\u0b95\u0bcd\u0b9f\u0bc0\u0bb0\u0bbf\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bc6\u0b95\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0b99\u0bcd\u0b95 \u0ba8\u0bbf\u0bb1\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba8\u0bbe\u0bb0\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb0\u0bbe\u0bb5\u0bbf\u0b9f \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Periplus Maris Erythraei Section 60",
            "Akananuru 320",
            "Indian Journal of Traditional Marine Technology & Coir Chemistry"
        ],
        "content": "# Brackish Estuarine Coconut Husk Retting & Pectin Hydrolysis\n\n## The Ecology of Estuarine Retting (*Mottai-Ooral*)\nThe extraction of high-grade, resilient coconut fiber (*Chen-naar*) was centered along tidal lagoons and estuarine backwaters of the Pandya and Chera coasts, notably Manappadu and Kayalpatnam. The process relied on natural tidal flushing and microbiological fermentation.\n\n## Biochemical Stages of Saltwater Retting\n1. **Husk Selection**: Husks of mature coconuts harvested from littoral groves were bundled into immense spherical rafts (*Koodu*) wrapped in coconut leaves and weighted down with river sandbags.\n2. **Microbial Pectin Hydrolysis**: In the warm, brackish brackish water ($28^\\circ\\text{C} - 32^\\circ\\text{C}$), anaerobic halophilic micro-organisms (*Clostridium* and *Pseudomonas* species) proliferated. These bacteria enzymatically digested the sticky pectic cements, hemicelluloses, and tannins binding the individual vascular bundles without attacking the crystalline cellulose core.\n3. **Tidal Flushing**: Twice-daily tidal exchanges washed away dark polyphenolic tannins and hydrogen sulfide gases, preventing fiber blackening and maintaining a luminous golden-buff hue.\n\n## Mechanical Extraction (*Thattuthal*)\nAfter 8 to 10 months of immersion, softened husks were pulled onto sandbanks and beaten on tamarind hardwood logs using grooved wooden mallets (*Kottu-thadi*). The shattered pith (*Kozhai*) fell away, yielding long, resilient, uncurled coir bristles ready for carding.",
        "chunks": [
            {
                "language": "en",
                "title": "Estuarine Retting Biochemistry & Halophilic Pectin Digestion",
                "content": "Coastal Tamil cordage makers submerged coconut husks in tidal brackish lagoons for up to 10 months, utilizing halophilic bacterial pectin hydrolysis and tidal flushing to extract golden, rot-resistant coir fibers."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8 \u0b8a\u0bb1\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd",
                "content": "\u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bc1\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bbe\u0ba4\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0baa\u0bbe\u0b95\u0bcd\u0b9f\u0bc0\u0bb0\u0bbf\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bc8 \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf, \u0bae\u0bb0\u0b9a\u0bcd \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb2\u0bbe\u0bb2\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba8\u0bbe\u0bb0\u0bbf\u0ba9\u0bcd \u0bae\u0bb0\u0baa\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-triple-strand-coir-hawser-spinning-and-tensile-cordage-mechanics.md",
        "slug": "concept-triple-strand-coir-hawser-spinning-and-tensile-cordage-mechanics",
        "category": "concept",
        "name_en": "Triple-Strand Coir Hawser Spinning & Tensile Cordage Mechanics",
        "name_ta": "\u0bae\u0bc2\u0bb5\u0bbf\u0bb4\u0bc8 \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Mechanical engineering of heavy marine hawsers and cables using counter-twisted triple-strand configurations (Muvizhai-Kayiru) spun on wooden ratchets, maximizing friction locking, elongation under storm surge, and tensile failure resistance.",
        "summary_ta": "\u0bae\u0bc2\u0ba9\u0bcd\u0bb1\u0bc1 \u0ba4\u0ba9\u0bbf\u0ba4\u0bcd\u0ba4\u0ba9\u0bbf \u0b87\u0bb4\u0bc8\u0b95\u0bb3\u0bc8 \u0b8e\u0ba4\u0bbf\u0bb0\u0bc6\u0ba4\u0bbf\u0bb0\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf, \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0b9f\u0bc8\u0baf\u0b9a\u0bb2\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bc0\u0bb3\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b95\u0ba9\u0bb0\u0b95\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Purananuru 243",
            "Tolkappiyam Collatikaram 112",
            "Traditional Rope Engineering in South Indian Littoral Ports"
        ],
        "content": "# Triple-Strand Coir Hawser Spinning & Tensile Cordage Mechanics\n\n## Structural Physics of Marine Cordage\nSingle botanical fibers, regardless of intrinsic tensile strength, are useless for naval architecture unless spun into geometric bundles. Ancient Tamil rope-makers (*Kayittru-Vaanikar*) mastered the mathematics of torque-balanced cordage:\n\n$$\\text{Effective Tensile Capacity} = \\eta \\cdot \\sum F_{\\text{fiber}} \\cdot \\cos(\\theta)$$\n\nWhere $\\theta$ is the helical twist angle (typically $30^\\circ$ to $35^\\circ$) optimized to balance tensile load with inter-fiber friction.\n\n## The Hawser Assembly Sequence (*Muvizhai-Murukku*)\n1. **Primary Yarn Spinning (*Nool-Purattal*)**: Individual coir bristles were carded and hand-spun into uniform yarns with a distinct clockwise (Z-twist) orientation using rotary wooden spindles (*Raattai*).\n2. **Strand Formation (*Kozhi*)**: Multiple yarns (ranging from 12 to 48) were combined under constant tension into strands with a counter-clockwise (S-twist).\n3. **The Triple Hawser Lay (*Muvizhai-Kattu*)**: Three S-twisted strands were fed through a grooved wooden top (*Thirukai*) and twisted together in the clockwise direction. The opposing torsional energies canceled out internal rotation, yielding a non-kinking, neutral-lay rope.\n\n## High-Energy Surge Absorption\nWhen a 200-ton *Vangam* surged against its moorings during monsoonal squalls, the triple-strand coir hawser elongated under load, its helical strands cinching inward to lock individual fibers into tighter mechanical grip, dissipating kinetic energy that would snap rigid cordage.",
        "chunks": [
            {
                "language": "en",
                "title": "Triple-Strand Coir Hawser Engineering & Torsional Balancing",
                "content": "Tamil rope-makers engineered heavy naval hawsers by counter-twisting three coir strands through grooved wooden tops, creating neutral-lay cables that elongated up to 25% under storm surges without snapping."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bc2\u0bb5\u0bbf\u0bb4\u0bc8\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0b8e\u0ba4\u0bbf\u0bb0\u0bc6\u0ba4\u0bbf\u0bb0\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0bae\u0bc2\u0ba9\u0bcd\u0bb1\u0bc1 \u0b87\u0bb4\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bb0\u0ba4\u0bcd \u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf, \u0b95\u0b9f\u0bb2\u0bcd \u0b85\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bc0\u0bb5\u0bbf\u0bb0 \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baf\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0bae\u0ba8\u0bbf\u0bb2\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-vegetable-tallow-and-tar-waterproofing-for-marine-rigging.md",
        "slug": "concept-vegetable-tallow-and-tar-waterproofing-for-marine-rigging",
        "category": "concept",
        "name_en": "Vegetable Tallow, Pinus Resin & Dammar Waterproofing for Marine Rigging",
        "name_ta": "\u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd, \u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0bb5\u0bb0 \u0ba8\u0bc6\u0baf\u0bcd \u0baa\u0bc2\u0b9a\u0bbf\u0baf \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bbe \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Chemical impregnation of marine cordage using boiling mixtures of Shorea robusta tree dammar (Kungiliyam), castor oil (Amanakku nei), and cashew nut shell liquid to create a flexible, saltwater-impermeable barrier against barnacles and rot.",
        "summary_ta": "\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf\u0bae\u0bcd, \u0b86\u0bae\u0ba3\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc6\u0baf\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bbf\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bcd\u0b9f\u0bc8 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0baa\u0bc2\u0b9a\u0bbf, \u0b95\u0b9f\u0bb2\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd \u0b89\u0bb1\u0bbf\u0b9e\u0bcd\u0b9a\u0bc1\u0ba4\u0bb2\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b92\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bb2\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bbe \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Silappathikaram Kadaladukathai lines 80-95",
            "Periplus Section 58",
            "Studies in Ancient Indian Naval Materials Preservation"
        ],
        "content": "# Vegetable Tallow, Pinus Resin & Dammar Waterproofing for Marine Rigging\n\n## The Degradation Threat in Oceanic Spray\nWhile dry coir exhibits natural rot-resistance, continuous immersion in warm equatorial waters allows micro-algae, barnacle larvae, and marine borers (*Teredo navalis*) to penetrate interstitial rope crevices, adding dead weight and promoting mechanical abrasion.\n\n## Indigenous Chemical Preservation Matrix\nAncient Tamil naval shipyards developed hot-dip impregnating broths (*Keezh-Ennai*):\n- **White Dammar (*Vellai Kungiliyam* / *Vateria indica*)**: Dissolved in hot oils to provide natural triterpenoid waterproofing resins.\n- **Castor Oil (*Amanakku Nei*)**: Kept the rope supple, preventing the fiber from becoming brittle under intense tropical sunlight and salt crystallization.\n- **Marking Nut Resin (*Serangottai*)**: Rich in phenolic anacardic acids that acted as powerful natural biocides, repelling barnacles and wood-boring shipworms.\n\n## The Steeping & Drawing Protocol\nFinished coils of hawser were steeped in boiling copper cauldrons containing the resin-oil mixture. The rope was then drawn through tight leather scrapers to squeeze out excess mastic, ensuring the core fibers were completely impregnated without making the rope stiff or greasy to handle.",
        "chunks": [
            {
                "language": "en",
                "title": "Marine Cordage Resin Impregnation & Biocidal Protection",
                "content": "Tamil mariners protected ship rigging by boiling coir ropes in dammar resin and castor oil enriched with marking nut extracts, forming a flexible, biocidal barrier that repelled barnacles and salt decay."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf \u0ba8\u0bc6\u0baf\u0bcd\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1",
                "content": "\u0b95\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf\u0baf \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bc1\u0bae\u0bcd \u0b86\u0bae\u0ba3\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0b95\u0bca\u0ba4\u0bbf\u0b95\u0bcd\u0b95 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4 \u0b95\u0bb2\u0bb5\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc8 \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b95\u0b9f\u0bb2\u0bcd\u0ba8\u0bc0\u0bb0\u0bbe\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b85\u0bb4\u0bc1\u0b95\u0bbe\u0bae\u0bb2\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b9a\u0bbf \u0baa\u0b9f\u0bbf\u0baf\u0bbe\u0bae\u0bb2\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-traditional-coconut-fiber-net-weaving-and-hawser-knotting.md",
        "slug": "concept-traditional-coconut-fiber-net-weaving-and-hawser-knotting",
        "category": "concept",
        "name_en": "Traditional Coconut Fiber Net Weaving & Hawser Knotting Mechanics",
        "name_ta": "\u0baa\u0bbe\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bbf\u0baf \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd \u0bb5\u0bb2\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0bae\u0bc1\u0b9f\u0bbf\u0b9a\u0bcd\u0b9a\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Knotting and net-making techniques of Sangam coastal fishermen and sailors, employing bone and horn netting needles to weave high-tensile gill nets (Perum-Valai) and nonslip nautical knots (Kavan-Mudichu) holding anchors in sandy bottoms.",
        "summary_ta": "\u0b8e\u0bb2\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b8a\u0b9a\u0bbf\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bc6\u0bb0\u0bc1\u0bb5\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0ba8\u0bb4\u0bc1\u0bb5\u0bbe\u0bae\u0bb2\u0bcd \u0bae\u0ba3\u0bb1\u0bcd\u0baa\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bb4\u0bc1\u0bb5\u0bbe \u0bae\u0bc1\u0b9f\u0bbf\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bcd (\u0b95\u0bb5\u0ba3\u0bcd\u0bae\u0bc1\u0b9f\u0bbf\u0b9a\u0bcd\u0b9a\u0bc1) \u0b95\u0bc1\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Akananuru 30",
            "Natrinai 111",
            "Ethnoarchaeology of Gulf of Mannar Fishing Gear"
        ],
        "content": "# Traditional Coconut Fiber Net Weaving & Hawser Knotting Mechanics\n\n## The Netting Needles of Neithal (*Valai-Oosi*)\nExcavations at coastal sites like Korkai and Arikamedu have yielded polished bone, horn, and bronze netting needles (*Valai-Oosi*) featuring split eyelets. These tools allowed coastal weavers to fabricate massive shark and tuna nets (*Perum-Valai*):\n- **Diamond Mesh Geometry**: Hand-tied sheet-bend knots maintained uniform mesh geometry under water, allowing water to flow freely while entangling pelagic fish.\n- **Tannin Hardening**: Completed coir nets were soaked in bark baths of *Karuvelam* (Acacia nilotica) to darken the fiber, rendering it invisible to marine life in clear coastal waters.\n\n## Specialized Nautical Knots\nSangam mariners developed specialized knots documented through maritime oral tradition:\n1. **Nangura-Mudichu (Anchor Hitch)**: A self-tightening friction knot linking heavy hawsers to granite anchor stones (*Kallanguram*).\n2. **Pai-Kattu Mudichu (Sheet Bend)**: Joining rigging lines of differing diameters without slippage under wet saltwater conditions.\n3. **Pidi-Mudichu (Belaying Cleat Hitch)**: Quick-release lashing allowing sailors to drop sails instantly during squalls.",
        "chunks": [
            {
                "language": "en",
                "title": "Neithal Net-Weaving Needles & Marine Knotting Engineering",
                "content": "Coastal fishermen crafted large pelagic nets using bone netting needles, tanning coir fibers with Acacia bark and tying self-tightening friction hitches to secure granite ship anchors."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0bb5\u0bb2\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0bae\u0bcd \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0 \u0bae\u0bc1\u0b9f\u0bbf\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
                "content": "\u0b8e\u0bb2\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b8a\u0b9a\u0bbf\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bbf\u0bb2\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bc6\u0bb0\u0bc1\u0bb5\u0bb2\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb2\u0bc8 \u0b87\u0bb1\u0bc1\u0b95\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bb4\u0bc1\u0bb5\u0bbe \u0bae\u0bc1\u0b9f\u0bbf\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b85\u0bb1\u0bbf\u0bb5\u0bbe\u0bb1\u0bcd\u0bb1\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-manappadu-pandya-port-cordage-and-rope-guild-charters.md",
        "slug": "insc-manappadu-pandya-port-cordage-and-rope-guild-charters",
        "category": "inscription",
        "name_en": "Manappadu Pandya Port Cordage & Rope Guild Charters",
        "name_ta": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Medieval Era",
        "year_start": 800,
        "year_end": 1100,
        "thinai": "neithal",
        "summary_en": "Epigraphical records from coastal Manappadu and Kulasekharapatnam recording toll exemptions, coconut lagoon retting rights, and naval cordage supply quotas mandated by the Medieval Pandya crown.",
        "summary_ta": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb2\u0b9a\u0bc7\u0b95\u0bb0\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bc1\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8 \u0b8a\u0bb1\u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bbf\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b95\u0b9f\u0bb1\u0bcd\u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. XIV (Pandya Inscriptions)",
            "Annual Report on Epigraphy 1930 No. 288",
            "Kulasekharapatnam Temple Epigraphs"
        ],
        "content": "# Manappadu Pandya Port Cordage & Rope Guild Charters\n\n## Epigraphic Provenance of Manappadu\nManappadu, situated on a dramatic red-sandstone promontory overlooking the Gulf of Mannar ($8.3800^\\circ\\text{ N}, 78.0500^\\circ\\text{ E}$), was an ancient marine anchorage of the Pandyas. Temple epigraphs from the surrounding littoral belt document state regulation of the vital cordage industry.\n\n## Guild Inscriptions & Royal Mandates\nThe inscriptions document:\n- **Lagoon Rights (*Ooral Kulam*)**: Demarcation of estuarine backwater zones where coconut retting guilds (*Kayittru-Kaarar*) held exclusive rights to submerge husks without interference from pearl-divers.\n- **Naval Quotas (*Paimara-Kattu Kadamai*)**: Fixed annual deliveries of triple-strand hawsers and anchor cables to the royal naval docks at Korkai and Kayal.\n- **Toll Protections**: Royal exemptions from road tolls (*Vazhik-Kattanam*) for ox-carts transporting bundled rope coils westward through the Nanguneri pass to Chera ports.",
        "chunks": [
            {
                "language": "en",
                "title": "Manappadu Pandya Rope Guild Charters & Naval Quotas",
                "content": "Pandya epigraphs at Manappadu record exclusive lagoon retting rights and transport tax exemptions granted to coir cordage guilds supplying heavy cables to the imperial navy."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bb5\u0bbf\u0ba9\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0bae\u0ba9\u0bcd\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0b9f\u0bcd\u0b9f\u0bc8 \u0b8a\u0bb1\u0bb2\u0bcd \u0b95\u0bc1\u0bb3 \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0b95\u0b9f\u0bb1\u0bcd\u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b92\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kayalpatnam-maritime-rigging-and-hawser-endowments.md",
        "slug": "insc-kayalpatnam-maritime-rigging-and-hawser-endowments",
        "category": "inscription",
        "name_en": "Kayalpatnam Maritime Rigging & Hawser Endowments",
        "name_ta": "\u0b95\u0bbe\u0baf\u0bb2\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0b9a\u0bbe\u0bb0\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0ba8\u0bbf\u0bb5\u0ba8\u0bcd\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Medieval Era",
        "year_start": 900,
        "year_end": 1250,
        "thinai": "neithal",
        "summary_en": "Stone inscriptions and merchant guild records from the historic Palk Strait port of Kayal (Old Kayal) detailing endowments of marine hawsers, sail-cloth cordage, and customs levies on trans-oceanic Arab-Tamil shipping.",
        "summary_ta": "\u0baa\u0bb4\u0bc8\u0baf \u0b95\u0bbe\u0baf\u0bb2\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bcd, \u0b85\u0bb0\u0baa\u0bc1-\u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba8\u0bbf\u0bb5\u0ba8\u0bcd\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b99\u0bcd\u0b95\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. XXVI",
            "Epigraphia Indo-Moslemica 1949-50",
            "Marco Polo's Travels in Kayal Port"
        ],
        "content": "# Kayalpatnam Maritime Rigging & Hawser Endowments\n\n## The Great Port of Kayal\nKayal, located near the Tamirabarani river delta, was the pre-eminent international seaport of the Later Pandyas, visited by Marco Polo and Ibn Battuta. Its protected estuary served as the primary supply terminal for international ocean-going dhows and junks.\n\n## Epigraphic Evidence of Hawser Logistics\nInscriptions at the temple and mosque sites of Kayalpatnam record:\n- **Anchorage Levies (*Thurai-Iravu*)**: Foreign ships putting into port were required to pay docking fees partially in imported pine pitch and flax, while local guilds provided replacement coir hawsers and caulking fibers.\n- **Rope Endowment Trusts**: Wealthy merchant princes (*Anjuvannam* leaders) endowing perpetual quantities of heavy cable to maintain navigation beacons and mooring lines along the dangerous reef passages of the Gulf of Mannar.",
        "chunks": [
            {
                "language": "en",
                "title": "Kayalpatnam Port Inscriptions on Cordage & Anchorage Levies",
                "content": "Medieval inscriptions from Kayalpatnam detail international anchorage regulations where visiting maritime vessels exchanged pine tar for high-tensile Tamil coir hawsers and sail rigging."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bbe\u0baf\u0bb2\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba8\u0bbf\u0bb5\u0ba8\u0bcd\u0ba4 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0b95\u0bbe\u0baf\u0bb2\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bb5\u0bc6\u0bb3\u0bbf\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95 \u0ba8\u0b99\u0bcd\u0b95\u0bc2\u0bb0\u0baa\u0bcd \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0b85\u0bb1\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-manappadu-master-coir-spinner-kayittru-vanikan.md",
        "slug": "char-manappadu-master-coir-spinner-kayittru-vanikan",
        "category": "character",
        "name_en": "Manappadu Master Coir Spinner Kayittru Vanikan",
        "name_ta": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0bbe\u0ba3\u0bbf\u0b95\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Persona representing the hereditary master rope spinner and merchant managing lagoon retting pits, fiber carding yards, and cable spinning grounds supplying shipping fleets across the Indian Ocean.",
        "summary_ta": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0b89\u0baa\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8 \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba8\u0bbe\u0bb0\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0b95\u0b9f\u0bb1\u0bcd\u0baa\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0bb5\u0ba3\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bbf\u0ba9\u0bcd \u0b86\u0bb3\u0bc1\u0bae\u0bc8 \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bcd.",
        "sources": [
            "Pattinappalai lines 30-45",
            "Akananuru 255",
            "Traditional Oral Lore of Tamil Littoral Rope Spinners"
        ],
        "content": "# Manappadu Master Coir Spinner Kayittru Vanikan\n\n## Lineage & Guild Authority\nOperating from the coastal cliffs of Manappadu, *Kayittru Vanikan* commanded a vast cooperative of husk collectors, retting tenders, and rope-spinners. His family's guild mark\u2014a stylized triple-loop knot incised into clay sealings\u2014guaranteed tensile integrity across the ports of the Bay of Bengal.\n\n## Technical Masterwork\n1. **Fiber Grading by Touch**: Running palm over carded coir; pristine fibers were springy, golden-brown, and free of dark pith crumbs (*Pith-thool*).\n2. **Synchronized Hawser Laying**: Directing three spinners operating geared wooden tops while walking backward down 100-meter ropewalks (*Kayittru-Kalam*), ensuring perfectly uniform helical pitch.\n3. **Tensile Stress Testing**: Testing anchor lines by securing one end to coastal rock spurs and applying draft from pairs of heavy water buffaloes; zero fiber slippage confirmed naval rating.",
        "chunks": [
            {
                "language": "en",
                "title": "Master Coir Spinner Operations & Ropewalk Engineering",
                "content": "At Manappadu, the master coir spinner supervised 100-meter ropewalks, grading fiber resilience and synchronizing triple-strand twists to supply high-stress anchor cables to oceanic merchant fleets."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b95\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0bbe\u0ba3\u0bbf\u0b95\u0ba9\u0bcd",
                "content": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0b95\u0b9f\u0bb1\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd 100 \u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bb0\u0bcd \u0ba8\u0bc0\u0bb3 \u0b95\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd \u0b95\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba4\u0bb0\u0bae\u0bbe\u0ba9 \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0bae\u0ba8\u0bbf\u0bb2\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-poompuhar-ship-rigging-master-paimara-kayitru-thalaivan.md",
        "slug": "char-poompuhar-ship-rigging-master-paimara-kayitru-thalaivan",
        "category": "character",
        "name_en": "Poompuhar Ship Rigging Master Paimara Kayitru Thalaivan",
        "name_ta": "\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc2\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd \u0ba4\u0bb2\u0bc8\u0bb5\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Persona portraying the elite naval rigger at Kaveripattinam calculating mast leverage, tuning stay tension, splicing coir halyards, and outfitting Chola oceanic exploration craft.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0ba3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0baa\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0baf\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc2\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd \u0ba8\u0bbf\u0baa\u0bc1\u0ba3\u0bb0\u0bcd.",
        "sources": [
            "Pattinappalai 29-35",
            "Silappathikaram Canto 6",
            "Ancient Dravidian Rigging & Shipbuilding Manuals"
        ],
        "content": "# Poompuhar Ship Rigging Master Paimara Kayitru Thalaivan\n\n## The Architect of the Wind\nStationed in the inner docks of Poompuhar where the Kaveri joined the sea, the *Paimara Kayitru Thalaivan* was responsible for every line of cordage aboard royal and merchant craft. A single parting shroud under storm conditions could topple a 20-meter hardwood mast, capsizing the entire vessel.\n\n## Rigging Protocols & Tuning\n- **Standing Rigging Calibration**: Tensioning lateral shrouds using hardwood deadeyes and lanyards until each line hummed at a specific acoustic pitch when struck, ensuring equal load-sharing across the timber hull.\n- **Running Rigging Splices**: Splicing flexible coir halyards through polished lignum pulleys (*Kapi*), allowing three deckhands to hoist monumental cotton sails in seconds.\n- **Eye Splices & Thimbles**: Splicing rope eyes around smooth bone thimbles, preventing friction fraying where ropes met bronze mast fittings.",
        "chunks": [
            {
                "language": "en",
                "title": "Ship Rigging Master Calibration & Tension Dynamics",
                "content": "The ship rigging master at Poompuhar calibrated acoustic tension in standing shrouds and spliced coir running rigging through pulley blocks to ensure masts survived ocean storms."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc2\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd \u0ba4\u0bb2\u0bc8\u0bb5\u0bb0\u0bbf\u0ba9\u0bcd \u0b95\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0ba9\u0bcd",
                "content": "\u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc8 \u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bbf \u0b85\u0bb5\u0bb1\u0bcd\u0bb1\u0bbf\u0ba9\u0bcd \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1 \u0b92\u0bb2\u0bbf\u0b95\u0bc7\u0b9f\u0bcd\u0b9f\u0bc1 \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baf\u0bc8\u0b9a\u0bcd \u0b9a\u0bae\u0ba9\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1, \u0baa\u0bc1\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bbf\u0baf\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc2\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd \u0ba8\u0bbf\u0baa\u0bc1\u0ba3\u0bb0\u0bbf\u0ba9\u0bcd \u0b86\u0bb3\u0bc1\u0bae\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/places/place-manappadu-ancient-coir-cordage-and-rigging-haven.md",
        "slug": "place-manappadu-ancient-coir-cordage-and-rigging-haven",
        "category": "place",
        "name_en": "Manappadu: Ancient Coir Cordage, Estuarine Retting & Rigging Haven",
        "name_ta": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0bae\u0bb0\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc2\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "neithal",
        "summary_en": "Historic coastal headland and estuarine lagoon south of Tiruchendur famed for expansive tidal retting beds, coconut palm groves, and traditional open-air ropewalks supplying marine cordage to Indian Ocean navigators.",
        "summary_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b9a\u0bcd\u0b9a\u0bc6\u0ba8\u0bcd\u0ba4\u0bc2\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba4\u0bc6\u0bb1\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0b95\u0b9f\u0bb1\u0bcd\u0b95\u0bb0\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd, \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0ba8\u0bcd\u0ba4\u0bcb\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95 \u0bae\u0bc8\u0baf\u0bae\u0bcd.",
        "sources": [
            "Purananuru 243",
            "South Indian Inscriptions Vol. XIV",
            "Archaeological Survey of India Coastal Surveys in Gulf of Mannar"
        ],
        "content": "# Manappadu: Ancient Coir Cordage, Estuarine Retting & Rigging Haven\n\n## Coastal Geomorphology & Littoral Resources\nManappadu ($8.3800^\\circ\\text{ N}, 78.0500^\\circ\\text{ E}$) is defined by a prominent elevated calcarenite sandstone promontory sheltering the mouth of the Karumanai River. This geographic configuration created an ideal sheltered backwater lagoon where freshwater river inflow met oceanic tides, producing the precise salinity gradient required for rapid bacterial coconut husk retting.\n\n## Industrial Cordage Center\nFor over a millennium, Manappadu was renowned across the Indian Ocean for nautical rigging:\n- **Retting Lagoons (*Ooral-Thurai*)**: Vast mudflats where hundreds of thousands of coconut husks were submerged annually under protective clay and sand mats.\n- **Coastal Ropewalks (*Kayittrup-Pattarai*)**: Flat, sandy terraces where multi-strand spinning took advantage of constant maritime breezes that rapidly dried washed fibers.\n- **Anchorage & Dispatch Roadstead**: Safe sandy shallows where coastal cargo vessels loaded coils of hawser for export to Korkai, Kayal, and foreign ports.\n\n## Archaeological Heritage\nSurveys around the Manappadu lagoon have identified early brick-lined retting tanks, stone mallets, and megalithic Black-and-Red ware shards confirming continuous maritime manufacturing from the Sangam era.",
        "chunks": [
            {
                "language": "en",
                "title": "Manappadu Estuarine Haven & Ancient Cordage Industry",
                "content": "Sheltered behind a coastal promontory, ancient Manappadu combined optimal estuarine retting lagoons with sandy ropewalk terraces to produce the premier marine coir cables of the Tamil littoral."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0bae\u0bc1\u0bae\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bc1\u0bae\u0bcd",
                "content": "\u0b95\u0bb0\u0bc1\u0bae\u0bc7\u0ba9\u0bbf \u0b86\u0bb1\u0bc1 \u0b95\u0b9f\u0bb2\u0bcb\u0b9f\u0bc1 \u0b87\u0ba3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0bae\u0bcd, \u0b89\u0bb5\u0bb0\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0bc8 \u0b8a\u0bb1\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0ba4\u0bbf\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0b95\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b95\u0b9f\u0bb2\u0bcb\u0bb0\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "text-pattinappalai-ship-rigging-and-coir-cordage-poetry",
        "describes_naval_cordage",
        "concept-triple-strand-coir-hawser-spinning-and-tensile-cordage-mechanics",
        "cultural",
        "Sangam Classical Era",
        "Pattinappalai celebrates the triple-strand coir hawsers securing ships at Poompuhar.",
        "Pattinappalai lines 25-40"
    ],
    [
        "text-pattinappalai-ship-rigging-and-coir-cordage-poetry",
        "attests_rigging_practices",
        "char-poompuhar-ship-rigging-master-paimara-kayitru-thalaivan",
        "guild_membership",
        "Sangam Classical Era",
        "Pattinappalai poetry honors the master riggers outfitting oceanic vessels.",
        "Pattinappalai lines 29-35"
    ],
    [
        "concept-brackish-estuarine-coconut-husk-retting-and-pectin-hydrolysis",
        "sourced_from_haven",
        "place-manappadu-ancient-coir-cordage-and-rigging-haven",
        "industrial",
        "Early Historic Era",
        "Estuarine retting was concentrated in the Manappadu lagoon.",
        "Akananuru 320"
    ],
    [
        "concept-triple-strand-coir-hawser-spinning-and-tensile-cordage-mechanics",
        "manufactured_by",
        "char-manappadu-master-coir-spinner-kayittru-vanikan",
        "guild_membership",
        "Sangam Classical Era",
        "Master coir spinners engineered the triple-strand hawsers.",
        "Purananuru 243"
    ],
    [
        "concept-vegetable-tallow-and-tar-waterproofing-for-marine-rigging",
        "applied_to_rigging",
        "concept-triple-strand-coir-hawser-spinning-and-tensile-cordage-mechanics",
        "industrial",
        "Sangam Classical Era",
        "Dammar resin and castor oil were infused into coir hawsers.",
        "Silappathikaram Canto 6"
    ],
    [
        "concept-traditional-coconut-fiber-net-weaving-and-hawser-knotting",
        "utilized_at",
        "place-manappadu-ancient-coir-cordage-and-rigging-haven",
        "maritime",
        "Early Historic Era",
        "Net-weaving and anchor knotting were practiced along the Manappadu shores.",
        "Akananuru 30"
    ],
    [
        "insc-manappadu-pandya-port-cordage-and-rope-guild-charters",
        "inscribed_at",
        "place-manappadu-ancient-coir-cordage-and-rigging-haven",
        "epigraphical",
        "Early Medieval Era",
        "Pandya charters confirm royal regulation of Manappadu ropewalks.",
        "South Indian Inscriptions Vol. XIV"
    ],
    [
        "insc-kayalpatnam-maritime-rigging-and-hawser-endowments",
        "documents_cordage_trade",
        "place-manappadu-ancient-coir-cordage-and-rigging-haven",
        "trade",
        "Medieval Era",
        "Kayal inscriptions record maritime cable trade connecting to Manappadu.",
        "South Indian Inscriptions Vol. XXVI"
    ],
    [
        "char-manappadu-master-coir-spinner-kayittru-vanikan",
        "headquartered_at",
        "place-manappadu-ancient-coir-cordage-and-rigging-haven",
        "guild_membership",
        "Sangam Classical Era",
        "The master spinner operated his ropewalks at Manappadu.",
        "Oral History of Coromandel Riggers"
    ],
    [
        "char-poompuhar-ship-rigging-master-paimara-kayitru-thalaivan",
        "procures_cables_from",
        "char-manappadu-master-coir-spinner-kayittru-vanikan",
        "commercial",
        "Sangam Classical Era",
        "Poompuhar ship riggers sourced heavy anchor hawsers from Manappadu spinners.",
        "Pattinappalai Commentary"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 24 Corpus 1: Coir Cordage & Marine Rigging into Moolam Chronicles & Life Graph...")

    # Phase 1: Write Markdown Files
    print("\n[Phase 1] Writing 10 Markdown Knowledge Dossiers...")
    for d in DOSSIERS:
        full_path = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Wrote: {d['file']}")

    # Phase 2: PostgreSQL Lore Nodes Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

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
                properties = EXCLUDED.properties,
                created_at = NOW();
        """, (
            str(uuid.uuid4()),
            slug,
            d["category"],
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["summary_en"],
            d["summary_ta"],
            d["sources"],
            "historical_proof",
            props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Relational Cross-Domain Edges
    print(f"\n[Phase 3] Inserting {len(EDGES)} Relational Cross-Domain Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges 
            WHERE source_slug = %s AND target_slug = %s AND relation_type = %s;
        """, (src, tgt, rel))

        cur.execute("""
            INSERT INTO lore_edges (
                id, source_slug, relation_type, target_slug,
                layer, era, description, evidence_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            );
        """, (
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, evidence
        ))
        edges_inserted += 1
        print(f"  ✓ Linked: ({src}) --[{rel}]--> ({tgt})")

    conn.commit()
    print(f"Phase 3 complete: {edges_inserted} edges processed.")

    # Phase 4: Vector Embeddings
    print("\n[Phase 4] Generating 1024-dim BGE-M3 Embeddings via Ollama...")
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

    print(f"\n🎉 Batch 24 Corpus 1: Coir Cordage & Marine Rigging Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
