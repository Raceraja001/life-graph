#!/usr/bin/env python3
# Ingestion harvester for Batch 23 Corpus 1: Shell Lime Calcination & Calcareous Stucco
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
        "file": "knowledge/texts/text-manimekalai-white-stuccoed-palaces-and-lime-mortar-poetry.md",
        "slug": "text-manimekalai-white-stuccoed-palaces-and-lime-mortar-poetry",
        "category": "text",
        "name_en": "Manimekalai Verses on White Stuccoed Palaces, Lime Mortar & Sculptured Viharas",
        "name_ta": "\u0bae\u0ba3\u0bbf\u0bae\u0bc7\u0b95\u0bb2\u0bc8 \u0bb5\u0bc6\u0ba3\u0bcd\u0b9a\u0bc1\u0ba4\u0bc8 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bcd, \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bbe\u0bb0\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Post-Sangam Classical Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Manimekalai Canto 19 and 28 describing Poompuhar and Kanchipuram's radiant white Buddhist viharas, multi-storeyed palaces gleaming like silver mountains coated with burnished oyster-shell lime plaster (Sudai), and skilled plasterers executing lifelike relief sculptures.",
        "summary_ta": "\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf\u0baa\u0bc1\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bbf \u0bae\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0baa\u0bcb\u0bb2\u0bcd \u0b92\u0bb3\u0bbf\u0bb5\u0bc0\u0b9a\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd \u0b9a\u0bc1\u0ba4\u0bc8 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bcd, \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bbe\u0bb0\u0bc8\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bbe\u0ba9 \u0b9a\u0bc1\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0ba3\u0bbf\u0bae\u0bc7\u0b95\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Manimekalai Canto 19:105-118",
            "Manimekalai Canto 28:35-52",
            "Archaeological Survey of India Kaveripattinam Excavation Reports"
        ],
        "content": "# Manimekalai Verses on White Stuccoed Palaces, Lime Mortar & Sculptured Viharas\n\n## Overview & Canonical Context\nIn classical Tamil literature, the epic *Manimekalai* composed by Kulavanikan Seethalai Sathanar presents an architectural landscape dominated by brilliant, mirror-finish white lime stucco known as *Sudai* (\u0b9a\u0bc1\u0ba4\u0bc8) or *Vensuthai* (\u0bb5\u0bc6\u0ba3\u0bcd\u0b9a\u0bc1\u0ba4\u0bc8). Cantos 19 and 28 provide vivid accounts of the port metropolis of Kaveripattinam (Poompuhar) and the royal capital of Kanchipuram, where seven-storeyed Buddhist viharas and royal mansions gleamed like moonlit cumulus clouds.\n\n```\n\"\u0bb5\u0bc6\u0ba3\u0bcd\u0b9a\u0bc1\u0ba4\u0bc8 \u0baa\u0bc2\u0b9a\u0bbf\u0baf \u0bb5\u0bc6\u0ba3\u0bcd\u0ba4\u0bcb\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bbe\u0b9f\u0ba4\u0bcd\u0ba4\u0bc1\n\u0b85\u0ba3\u0b99\u0bcd\u0b95\u0bc1\u0b9f\u0bc8 \u0b85\u0bb0\u0bc8\u0baf\u0bb0\u0bcd \u0b85\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bb5\u0bae\u0bcd \u0baa\u0bc1\u0bb0\u0bbf\u0ba8\u0bcd\u0ba4\n\u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bc1 \u0b92\u0bb3\u0bbf \u0bb5\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd...\"\n\u2014 \u0bae\u0ba3\u0bbf\u0bae\u0bc7\u0b95\u0bb2\u0bc8 28:38-40\n```\n\n## Material Pyrotechnics & Architectural Application\nThe radiant whiteness celebrated in *Manimekalai* was not simple whitewash, but a dense, hydraulic calcareous matrix produced by calcining littoral oyster and cockle shells (*Chippi sunnambu*) mixed with fine river quartz sand, fermented jaggery liquor (*karupatti thanneer*), and astringent *Kadukkai* (Terminalia chebula) decoctions. \n\nPlasterers (*Sudhai-kootu Sirpacharis*) burnished the drying stucco with smooth agate pebbles and sap of the sacred fig (*Arasu*), creating a waterproof, diamond-hard, porcelain-like veneer capable of withstanding the aggressive, salt-laden marine monsoons of the Coromandel coast.\n\n## Epigraphic & Archaeological Corroboration\nExcavations conducted by the Archaeological Survey of India at Kaveripattinam (Pallavanesvaram and Melaiyur sites) unearthed monumental brick vihara walls dating to the 3rd\u20135th centuries CE retaining thick layers of burnished shell-lime stucco with polychrome pigment remnants, matching Sathanar's poetic descriptions.",
        "chunks": [
            {
                "language": "en",
                "title": "Manimekalai White Stucco Architecture & Shell-Lime Pyrotechnics",
                "content": "Manimekalai verses record the monumental stucco architecture of Poompuhar and Kanchipuram, where multi-storeyed viharas were coated with burnished oyster-shell lime mortar (Sudai) mixed with jaggery water and Kadukkai tannins to produce weather-resistant white facades."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba3\u0bbf\u0bae\u0bc7\u0b95\u0bb2\u0bc8 \u0bb5\u0bc6\u0ba3\u0bcd\u0b9a\u0bc1\u0ba4\u0bc8 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bbe\u0bb0\u0bc8\u0baf\u0bc1\u0bae\u0bcd",
                "content": "\u0bae\u0ba3\u0bbf\u0bae\u0bc7\u0b95\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf \u0bb5\u0bc6\u0ba3\u0bcd\u0b9a\u0bc1\u0ba4\u0bc8 \u0bae\u0bbe\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1, \u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0ba3\u0bcd\u0ba3\u0bc0\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b95\u0bb7\u0bbe\u0baf\u0bae\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0b95\u0ba4\u0bcd \u0ba4\u0bc0\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bbf\u0bb0\u0bbe\u0bb5\u0bbf\u0b9f\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-marine-mollusc-and-oyster-shell-calcination-kiln-pyrotechnics.md",
        "slug": "concept-marine-mollusc-and-oyster-shell-calcination-kiln-pyrotechnics",
        "category": "concept",
        "name_en": "Marine Mollusc & Oyster Shell Calcination Kiln Pyrotechnics",
        "name_ta": "\u0b95\u0b9f\u0bb2\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbf\u0bb3\u0bbf\u0b9e\u0bcd\u0b9a\u0bb2\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0b8e\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic to Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Traditional littoral calcination kilns converting calcium carbonate (CaCO3) from oyster reefs and shell middens into high-purity calcium oxide (quicklime / sunnambu) using palmyra frond fuel and forced draft updraft chambers reaching 900-1000 \u00b0C.",
        "summary_ta": "\u0b95\u0b9f\u0bb1\u0bcd\u0b95\u0bb0\u0bc8 \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbf\u0bb3\u0bbf\u0b9e\u0bcd\u0b9a\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 900-1000 \u0b9f\u0bbf\u0b95\u0bbf\u0bb0\u0bbf \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0ba9\u0bc8\u0bae\u0bb0 \u0bb5\u0bbf\u0bb1\u0b95\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba4\u0bc2\u0baf \u0b95\u0bbe\u0bb2\u0bcd\u0b9a\u0bbf\u0baf\u0bae\u0bcd \u0b86\u0b95\u0bcd\u0b9a\u0bc8\u0b9f\u0bc1 (\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1) \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0b8e\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Akananuru 210",
            "Periplus Maris Erythraei Section 59",
            "Archaeological Excavations at Marakkanam Littoral Shell Middens"
        ],
        "content": "# Marine Mollusc & Oyster Shell Calcination Kiln Pyrotechnics\n\n## Pyrochemical Transformation of Shell Carbonate\nAncient coastal Tamil communities in the Neithal landscape exploited vast littoral shell middens (*Chippi medugal*) and oyster reefs to generate exceptionally pure calcium oxide. Unlike inland sedimentary kankar limestone, marine mollusc shells (predominantly *Crassostrea madrasensis* and *Meretrix casta*) consist of dense aragonite and calcite matrices virtually free of clay, magnesium, and iron impurities.\n\n$$\\text{CaCO}_3 \\xrightarrow{850^{\\circ}\\text{C} - 950^{\\circ}\\text{C}} \\text{CaO} + \\text{CO}_2 \\uparrow$$\n\n## Updraft Kiln Architecture (*Sunnambu Kaalavaai*)\nThe ancient lime kiln was an open-topped cylindrical or inverted-cone stone and clay pit constructed in sand dunes:\n1. **Alternate Charge Stratification**: Sun-dried oyster shells were washed to remove ocean salt and stacked in alternating layers with dense charcoal and dry palmyra wood split logs (*panam kattai*).\n2. **Ventilation Flues**: Radial air intake conduits carved at ground level caught diurnal sea breezes, sustaining constant combustion without manual bellows.\n3. **Decarbonation Cycle**: Over 36 to 48 hours, temperatures reached 900 \u00b0C, driving off carbon dioxide and yielding soft, chalk-white lumps of quicklime (*Veval sunnambu*).\n\n## Superiority of Shell Lime\nQuicklime derived from marine shells possessed an ultrafine crystalline micro-structure. Upon hydration, it produced colloidal calcium hydroxide slurries with unmatched plasticity, workability, and luminosity compared to terrestrial quarried rock lime.",
        "chunks": [
            {
                "language": "en",
                "title": "Marine Mollusc Shell Calcination Thermodynamics & Kiln Design",
                "content": "Coastal Tamil shell-lime kilns subjected washed oyster shells to 900 \u00b0C thermal decarbonation in sea-breeze-driven updraft kilns, producing high-purity quicklime with ultrafine colloidal micro-structure for premium mortar and stucco."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0b9f\u0bb2\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3 \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0b95\u0b9f\u0bb1\u0bcd\u0b95\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b95\u0bb3\u0bcd \u0baa\u0ba9\u0bc8 \u0bae\u0bb0 \u0bb5\u0bbf\u0bb1\u0b95\u0bc1\u0b9f\u0ba9\u0bcd \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 900 \u0b9f\u0bbf\u0b95\u0bbf\u0bb0\u0bbf \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bc1\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0baf\u0bb0\u0bcd\u0ba4\u0bb0 \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bbe\u0b95 (\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1) \u0bae\u0bbe\u0bb1\u0bcd\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-jaggery-water-and-kadukkai-myrobalan-slaked-lime-mortar-chemistry.md",
        "slug": "concept-jaggery-water-and-kadukkai-myrobalan-slaked-lime-mortar-chemistry",
        "category": "concept",
        "name_en": "Jaggery Water & Kadukkai Myrobalan Slaked Lime Mortar Chemistry",
        "name_ta": "\u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0ba3\u0bcd\u0ba3\u0bc0\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4 \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 600,
        "thinai": "marutham",
        "summary_en": "Indigenous bio-mineral lime mortar formulated by slaking quicklime with fermented palmyra jaggery solution and chebulic myrobalan (Kadukkai) tannin decoctions, inducing sugar-chelate carbonation retarding, micro-pore filling, and tensile fracture toughness.",
        "summary_ta": "\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0b9f\u0ba9\u0bcd \u0baa\u0ba9\u0bc8 \u0bb5\u0bc6\u0bb2\u0bcd\u0bb2\u0b95\u0bcd \u0b95\u0bb0\u0bc8\u0b9a\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b8a\u0bb1\u0bb2\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bbf\u0b9a\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1, \u0ba8\u0bc1\u0ba3\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bbe\u0bb1\u0bc8 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baf\u0bc8\u0ba4\u0bcd \u0ba4\u0bb0\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bbf\u0bb0\u0bbe\u0bb5\u0bbf\u0b9f\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Mayamata Vastu Shastra Chapter 18",
            "Tolkappiyam Porulatikaram 648 Commentary",
            "Journal of Traditional Building Materials & Bio-mineral Mortars"
        ],
        "content": "# Jaggery Water & Kadukkai Myrobalan Slaked Lime Mortar Chemistry\n\n## Bio-Chemical Formulation Matrix\nAncient Tamil builders perfected an organic-inorganic composite mortar (*Vensuthai Kootu*) that remains structurally sound across millennia. Rather than hydrating quicklime with plain water, master masons (*Sunnambu Karaiyalar*) utilized an organic fermentation broth:\n1. **Fermented Palmyra Jaggery (*Karupatti Thanneer*)**: Sucrose and reducing sugars act as natural setting retarders, preventing flash desiccation under tropical sun while forming calcium-saccharate complexes.\n2. **Kadukkai Extract (*Terminalia chebula*)**: Tannic acid, chebulic acid, and ellagitannins react with calcium hydroxide to form insoluble calcium tannate gels, filling interstitial capillary pores.\n3. **Curd & Veldt Grape (*Pirandai*) Mucilage**: Natural polysaccharides enhance workability, elasticity, and adhesion to hard granite and kiln-fired terracotta brick.\n\n## Mortar Grinding & Maturation\nThe slaked mixture was ground inside circular stone trench mills (*Aattuk-kal thotti*) propelled by pairs of bullocks for several days. This prolonged mechanical shear shattered calcium hydroxide crystals into sub-micron colloidal platelets. The finished mortar was then sealed in pits under wet jute sacks to mature for up to 30 days before masonry application.\n\n## Carbonation & Durability Mechanics\n$$\\text{Ca(OH)}_2 + \\text{CO}_2 \\xrightarrow{\\text{tannin-sugar matrix}} \\text{CaCO}_3 \\text{ (calcite)} + \\text{H}_2\\text{O}$$\nThe organic additives slow down carbonation, allowing dense, interlocking rhombohedral calcite crystals to grow without micro-cracking, creating tensile elasticity that withstands seismic tremors and thermal expansion.",
        "chunks": [
            {
                "language": "en",
                "title": "Bio-Mineral Slaked Lime Mortar Organic Additives & Chelation",
                "content": "Tamil lime mortar achieved legendary strength by slaking shell quicklime in fermented palmyra jaggery and Kadukkai myrobalan tannins, forming calcium saccharate and tannate gels that retard carbonation and eliminate micro-porosity."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bbe\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0b9f\u0ba9\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bc1\u0bae\u0bcd \u0baa\u0ba9\u0b99\u0bcd\u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc6\u0b95\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0baa\u0bb2 \u0ba8\u0bbe\u0b9f\u0bcd\u0b95\u0bb3\u0bcd \u0b85\u0bb0\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8 \u0b86\u0baf\u0bbf\u0bb0\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b86\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baf\u0bc1\u0b9f\u0ba9\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-hydraulic-calcination-and-kankar-nodule-quicklime-hydration.md",
        "slug": "concept-hydraulic-calcination-and-kankar-nodule-quicklime-hydration",
        "category": "concept",
        "name_en": "Hydraulic Calcination & Kankar Nodule Quicklime Hydration",
        "name_ta": "\u0b95\u0bb0\u0bbf\u0b9a\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0b95\u0bcd \u0b95\u0b99\u0bcd\u0b95\u0bb0\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3 \u0bae\u0bc1\u0b9f\u0bbf\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Exploitation of subterranean nodular kankar limestone (Silicate-argillaceous limestone) found in black cotton soils to produce hydraulic lime capable of curing underwater in sluices, tank dams, and foundation retaining walls.",
        "summary_ta": "\u0b95\u0bb0\u0bbf\u0b9a\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0b99\u0bcd\u0b95\u0bb0\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1, \u0ba8\u0bc0\u0bb0\u0bbf\u0ba9\u0bcd \u0b85\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b87\u0bb1\u0bc1\u0b95\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0baf\u0bbe\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bbe\u0bb0\u0bc8 (Hydraulic lime) \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Purananuru 299",
            "Sirupanarruppadai lines 150-165",
            "Excavations at Vallam and Kodumanal Hydraulic Works"
        ],
        "content": "# Hydraulic Calcination & Kankar Nodule Quicklime Hydration\n\n## The Geology of Inland Kankar Limestone\nWhile coastal settlements relied on oyster shells, interior Kongu and Chola plateau engineers exploited nodular calcium carbonate concretions known as *Kankar* (\u0b95\u0b99\u0bcd\u0b95\u0bb0\u0bcd) embedded in sub-surface clay soils of Mullai and Marutham tracts. Unlike pure shell lime, kankar nodules contain natural inclusions of reactive silica ($SiO_2$) and alumina ($Al_2O_3$) ranging from 10% to 20%.\n\n## Formation of Hydraulic Silicates During Calcination\nWhen kankar nodules were calcined at temperatures above 950 \u00b0C, the calcium oxide chemically combined with clay minerals to form belite (dicalcium silicate, $2\\text{CaO}\\cdot\\text{SiO}_2$):\n\n$$2\\text{CaO} + \\text{SiO}_2 \\rightarrow 2\\text{CaO}\\cdot\\text{SiO}_2$$\n\nThis mineral composition endowed the slaked mortar with hydraulic properties\u2014the capacity to set and harden through hydration even when completely submerged in water, without relying on atmospheric carbon dioxide.\n\n## Waterwork Engineering Applications\nAncient Tamil civil engineers utilized kankar hydraulic lime mortar for:\n- **Anicut Spillways & Sluice Gates**: Lining granite blocks in river diversion weirs across the Kaveri and Vaigai.\n- **Deep Well Linings (*Uraikkinaru*)**: Mortaring terracotta rings in high groundwater water tables.\n- **Moat Retaining Walls**: Constructing impervious military revetments surrounding fortress citadels.",
        "chunks": [
            {
                "language": "en",
                "title": "Hydraulic Kankar Lime Calcination & Underwater Mortar Curing",
                "content": "Inland Tamil builders calcined silica-rich nodular kankar limestone to synthesize dicalcium silicates, producing hydraulic mortar capable of setting underwater in anicut dams, sluices, and moat revetments."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0b99\u0bcd\u0b95\u0bb0\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3 \u0bae\u0bc1\u0b9f\u0bbf\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0bae\u0ba3\u0bcd\u0ba3\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0b99\u0bcd\u0b95\u0bb0\u0bcd \u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1, \u0ba8\u0bc0\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b87\u0bb1\u0bc1\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0ba4\u0bbe\u0bb2\u0bcd \u0b85\u0ba3\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba4\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-polished-arasu-maram-chunam-rendering-and-burnished-stucco-finish.md",
        "slug": "concept-polished-arasu-maram-chunam-rendering-and-burnished-stucco-finish",
        "category": "concept",
        "name_en": "Polished Arasu Maram Chunam Rendering & Burnished Stucco Finish",
        "name_ta": "\u0b85\u0bb0\u0b9a\u0bc1 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb3\u0baa\u0bb3 \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3 \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Sangam to Chola Era",
        "year_start": -100,
        "year_end": 800,
        "thinai": "marutham",
        "summary_en": "Fine architectural multi-coat finishing technique applying aged micro-filtered slaked lime paste blended with sacred fig (Ficus religiosa / Arasu) latex, soapstone powder, and agate stone rubbing to yield a glassy, moisture-impermeable fresco substrate.",
        "summary_ta": "\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0b9f\u0ba9\u0bcd \u0b85\u0bb0\u0b9a\u0bc1 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bcd, \u0bae\u0bbe\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0bca\u0b9f\u0bbf \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0b85\u0b95\u0bc7\u0b9f\u0bcd \u0b95\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba4\u0bc7\u0baf\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bc1\u0b95\u0bbe\u0ba4\u0bcd \u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b9a\u0bc1\u0ba4\u0bc8\u0baa\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1.",
        "sources": [
            "Silappathikaram Kadaladukathai lines 110-125",
            "Chitrasutra of Vishnudharmottara Chapter 40",
            "Sittannavasal Cave Temple Plaster Stratigraphy"
        ],
        "content": "# Polished Arasu Maram Chunam Rendering & Burnished Stucco Finish\n\n## Multi-Layer Plaster Stratigraphy\nThe lustrous, marble-like finish on ancient Tamil palace and cave sanctuary walls was achieved through a multi-tiered plastering process known in guild tradition as *Palam-Sunnambu*:\n1. **Base Rendering (*Kattu-Kaarai*)**: A 15\u201320 mm coarse coat of shell lime, sharp quartz river sand, and chopped jute fiber applied over brick or granite substrates.\n2. **Intermediate Float (*Vannak-Kaarai*)**: A 5 mm medium coat incorporating finely ground marble or limestone dust slaked with *Kadukkai* tannin broth.\n3. **Intonaco Polish (*Neeru-Kaarai*)**: A sub-millimeter skim coat composed of triple-filtered lime cream aged for six months in water, blended with milky latex of the *Arasu* tree (*Ficus religiosa*) and pulverized soapstone (*Maakkal*).\n\n## Agate Pebble Burnishing (*Kalluru-Theippu*)\nWhile the final intonaco coat remained moist, artisans rubbed the surface in tight circular motions using ultra-smooth riverbed agate, chert, or carnelian pebbles (*Theippuk-kallu*). The friction compressed surface pore capillaries and forced lime latex emulsion to bleed upward, where reaction with atmospheric carbon dioxide formed an amorphous, glass-hard calcium carbonate skin.\n\n## Durability & Fresco Foundation\nThis mirror-burnished surface was non-porous, highly reflective, and resistant to tropical mildew. It served as the foundation for royal mural frescoes at Sittannavasal and Thanjavur Brihadisvara, locking mineral earth pigments (ochre, lapis, lampblack) into the crystal lattice of the curing lime.",
        "chunks": [
            {
                "language": "en",
                "title": "Burnished Chunam Stucco Technique & Agate Polishing",
                "content": "Ancient Tamil plasterers achieved a porcelain-like marble finish by applying multi-layer lime stucco enriched with Ficus latex and soapstone dust, burnishing it with agate pebbles to seal microscopic pores against tropical moisture."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb0\u0b9a\u0bc1 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0ba4\u0bcd \u0ba4\u0bc7\u0baf\u0bcd\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1",
                "content": "\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8\u0baf\u0bc1\u0b9f\u0ba9\u0bcd \u0b85\u0bb0\u0b9a\u0bc1 \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0b95\u0bc7\u0b9f\u0bcd \u0b95\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bb5\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bbf\u0bb5\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0baf\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0ba9 \u0baa\u0bb3\u0bbf\u0b99\u0bcd\u0b95\u0bc1 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bc1\u0b95\u0bbe \u0b9a\u0bc1\u0ba4\u0bc8\u0baa\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0b95\u0bc8 \u0b93\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-marakkanam-chola-oyster-shell-lime-kiln-endowment-charters.md",
        "slug": "insc-marakkanam-chola-oyster-shell-lime-kiln-endowment-charters",
        "category": "inscription",
        "name_en": "Marakkanam Oyster Shell Lime Kiln Guild Endowment Charters",
        "name_ta": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0bb5\u0ba3\u0bbf\u0b95 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Medieval Era",
        "year_start": 850,
        "year_end": 1150,
        "thinai": "neithal",
        "summary_en": "Epigraphical records from Marakkanam (Eyirpattinam) detailing royal licenses, tax exemptions (*Irayili*), and fuel gathering rights granted to coastal oyster-shell calcination guilds providing mortar for imperial temple constructions.",
        "summary_ta": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bc8 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0bb0 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b9a\u0bcb\u0bb4 \u0b85\u0bb0\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bb0\u0bbf\u0bb5\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb1\u0b95\u0bc1 \u0b9a\u0bc7\u0b95\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bbf\u0bae\u0bc8 \u0b95\u0bc1\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. VII No. 392",
            "Annual Report on Epigraphy 1919 No. 42",
            "Marakkanam Bhumisvara Temple Inscriptions"
        ],
        "content": "# Marakkanam Oyster Shell Lime Kiln Guild Endowment Charters\n\n## Epigraphic Discovery & Provenance\nThe coastal village of Marakkanam in Viluppuram district, identified with ancient Sangam *Eyirpattinam* mentioned in *Sirupanarruppadai*, possesses stone epigraphs at the Bhumisvara temple dating to the reigns of Parantaka I and Rajaraja Chola I. These inscriptions record imperial oversight of littoral lime calcination guilds (*Sunnambu Samayathar*).\n\n## Kiln Guild Stipulations & Shell Harvesting Rights\nThe epigraphs document:\n- **Demarcation of Shell Middens (*Chippi Thurai*)**: Exclusive territorial rights granted to lime-burners to collect dead oyster and bivalve shells along the brackish Yedayanthittu backwaters without interference from salt-pan operators (*Umanar*).\n- **Tax Levies & Exemptions (*Sunnambu Irayili*)**: Exemption from standard commercial transit tolls in exchange for an annual tribute of 500 measures (*kalam*) of triple-sifted white shell lime for white-washing temple enclosures and plastering vimanas.\n- **Fuel Entitlement (*Kaalavaai Kattu-Viraqu*)**: Royal authorization to harvest dry palmyra trunks and dead scrub timber from state-managed forest fringes for kiln firing.\n\n## Socio-Economic Status of Lime Burners\nThe charters indicate that lime calcination was a specialized, highly respected industrial craft. Guild leaders (*Sunnambu Chettiyar*) held seats on local port mercantile councils and coordinated logistics with master temple stone masons across Tondaimandalam and the Kaveri delta.",
        "chunks": [
            {
                "language": "en",
                "title": "Marakkanam Shell Lime Guild Imperial Charters & Inscriptions",
                "content": "Chola epigraphs at Marakkanam document royal grants and tax exemptions given to coastal lime-burning guilds operating oyster-shell kilns in exchange for fixed annual deliveries of pure white mortar for monumental temples."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd \u0baa\u0bc2\u0bae\u0bc0\u0bb8\u0bcd\u0bb5\u0bb0\u0bb0\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b9a\u0bc7\u0b95\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1, \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0bb5\u0bbf\u0bb1\u0b95\u0bc1 \u0b89\u0bb0\u0bbf\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0bb0 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b9a\u0bcb\u0bb4 \u0bae\u0ba9\u0bcd\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0bb5\u0bb0\u0bbf\u0b9a\u0bcd\u0b9a\u0bb2\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-pudukkottai-rock-cut-cave-temple-lime-plaster-epigraphs.md",
        "slug": "insc-pudukkottai-rock-cut-cave-temple-lime-plaster-epigraphs",
        "category": "inscription",
        "name_en": "Pudukkottai Rock-Cut Cave Temple Lime Plaster Epigraphs",
        "name_ta": "\u0baa\u0bc1\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0bb5\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8\u0baa\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Pallava to Early Pandya Era",
        "year_start": 600,
        "year_end": 850,
        "thinai": "mullai",
        "summary_en": "Cave inscriptions and donor graffiti from Thirumayam, Kudumiyanmalai, and Sittannavasal documenting endowments for rejuvenating weathered lime stucco (Sudai-Poochu) and preserving polychrome mural fresco surfaces.",
        "summary_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0bae\u0baf\u0bae\u0bcd, \u0b95\u0bc1\u0b9f\u0bc1\u0bae\u0bbf\u0baf\u0bbe\u0ba9\u0bcd\u0bae\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0ba9\u0bb5\u0bbe\u0b9a\u0bb2\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0bb5\u0bb0\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b9a\u0bcd \u0b9a\u0bc1\u0ba4\u0bc8\u0baa\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0baa\u0bc1\u0ba4\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0bb0\u0bcb\u0bb5\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bbf\u0bb5\u0ba8\u0bcd\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Inscriptions of the Pudukkottai State Part I No. 12 & 38",
            "Epigraphia Indica Vol. XXI",
            "Archaeological Survey of India Cave Temple Reports"
        ],
        "content": "# Pudukkottai Rock-Cut Cave Temple Lime Plaster Epigraphs\n\n## Archaeological & Conservation Epigraphy\nIn the granite hillocks of Pudukkottai district, rock-cut caverns from the 7th to 9th centuries CE contain rare donor epigraphs explicitly detailing structural plaster maintenance. Unlike free-standing stone masonry, granite cave sanctuaries suffered from humidity condensation and mineral salt leaching, requiring cyclical applications of protective lime stucco.\n\n## Inscriptional Records of Plaster Rejuvenation\nAt the Satyagirisvara cave temple in Thirumayam and the Sittannavasal cavern:\n- **Sudhai-Pani Endowments**: Inscriptions record perpetual gold endowments (*Kasu*) placed in trust with temple assemblies, the interest of which funded periodic re-plastering of cavern ceilings and monolithic bas-relief sculptures.\n- **Mortar Ingredients Enumeration**: Epigraphs reference donations of refined ghee (*Ney*), sweet jaggery (*Sarkarai*), and gum mastic (*Pasai*) purchased to prepare ceremonial plaster formulations for idol gilding and wall burnishing.\n\n## Preservation of Monolithic Art\nThese epigraphical records confirm that classical Tamil monolithic cave temples were never left as raw, unpolished granite. Every cave interior, cornice drip-line, and carved relief figure was coated with a micro-thin, porcelain-smooth skin of shell-lime plaster painted with mineral frescoes.",
        "chunks": [
            {
                "language": "en",
                "title": "Pudukkottai Cave Inscriptions on Lime Plaster Renovation",
                "content": "Epigraphs at Thirumayam and Sittannavasal record gold endowments dedicated to cyclical lime-plaster re-coating and fresco conservation using organic lime mortars enriched with jaggery and plant gums."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc1\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0bb5\u0bb0\u0bc8 \u0b9a\u0bc1\u0ba4\u0bc8\u0baa\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0ba8\u0bbf\u0bb5\u0ba8\u0bcd\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0ba4\u0bbf\u0bb0\u0bc1\u0bae\u0baf\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0ba9\u0bb5\u0bbe\u0b9a\u0bb2\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0bb5\u0bb0\u0bc8\u0b95\u0bb3\u0bc8 \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0b95\u0bbe\u0b95\u0bcd\u0b95 \u0b9a\u0bc1\u0ba4\u0bc8\u0baa\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1 \u0baa\u0bc1\u0ba4\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0b95\u0bcd\u0b95 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b85\u0bb1\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0baa\u0bcd\u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-marakkanam-master-shell-lime-calciner-sunnambu-kallan.md",
        "slug": "char-marakkanam-master-shell-lime-calciner-sunnambu-kallan",
        "category": "character",
        "name_en": "Marakkanam Master Shell Lime Calciner Sunnambu Kallan",
        "name_ta": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bb0\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bcd\u0b95\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Persona representing the hereditary master pyrotechnician supervising estuarine oyster bed dredging, shell washing, fuel stacking, and updraft kiln temperature regulation to produce premium quicklime along the Coromandel coast.",
        "summary_ta": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0ba3\u0bcd\u0b9f\u0bbf, \u0b89\u0bb5\u0bb0\u0bcd \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf, \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bc0\u0bb0\u0bbe\u0ba9 \u0ba4\u0bc0\u0baf\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bc6\u0ba3\u0bcd\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bc8\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bb0\u0bbf\u0ba9\u0bcd \u0b86\u0bb3\u0bc1\u0bae\u0bc8 \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bcd.",
        "sources": [
            "Sirupanarruppadai lines 145-160",
            "Akananuru 320",
            "Oral History of Coromandel Traditional Lime Calcination Families"
        ],
        "content": "# Marakkanam Master Shell Lime Calciner Sunnambu Kallan\n\n## Archetype & Social Role\nIn ancient Marakkanam (*Eyirpattinam*), the master shell-lime calciner\u2014known colloquially as *Sunnambu Kallan*\u2014occupied a vital industrial nexus connecting coastal extraction with imperial urban construction. Stationed where saltwater estuaries met coastal sand dunes, he commanded crews of dredge laborers, wood-cutters, and kiln tenders.\n\n## Technical Expertise & Daily Operations\n1. **Shell Selection & Desalination**: Inspecting harvested oyster and clam mounds, rejecting shells contaminated with mud or mangrove roots, and orchestrating freshwater leaching to remove marine sodium chlorides that cause efflorescence.\n2. **Draft Control by Wind Sight**: Observing coastal wind currents, opening or sealing lower air intake nozzles (*Kaalavaai Vaasal*) to maintain an optimal 900 \u00b0C orange-white incandescent heat without melting kiln clay walls into glass slag.\n3. **Slaking Diagnostics**: Testing quicklime reactivity by sprinkling water droplets; a vigorous, boiling effervescence releasing pure white steam confirmed complete calcination.\n\n## Trade Integration\nSunnambu Kallan's stamped lime bags made of woven palm leaves were loaded onto ox-drawn freight carts (*Podi-vandigal*) and river barges headed for royal building yards at Kanchipuram and Poompuhar.",
        "chunks": [
            {
                "language": "en",
                "title": "Master Shell Lime Calciner Operations & Pyrotechnic Diagnostics",
                "content": "The master shell calciner at Marakkanam managed oyster reef dredging, fresh-water desalination, and sea-breeze draft regulation in coastal updraft kilns to manufacture premium quicklime for metropolitan architecture."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bb0\u0bcd",
                "content": "\u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b95\u0bb3\u0bc8 \u0b89\u0bb5\u0bb0\u0bcd \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf, \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0b9f\u0bb2\u0bcd \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8 \u0b92\u0bb4\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0bb5\u0bc8\u0baf\u0bbe\u0ba9 \u0ba4\u0bc2\u0baf \u0bb5\u0bc6\u0ba3\u0bcd\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc8 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bb0\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-kaveripattinam-royal-stucco-mason-sudhai-kootu-sirpachari.md",
        "slug": "char-kaveripattinam-royal-stucco-mason-sudhai-kootu-sirpachari",
        "category": "character",
        "name_en": "Kaveripattinam Royal Stucco Mason Sudhai Kootu Sirpachari",
        "name_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0b9a\u0bc1\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Persona portraying the elite architectural artisan specializing in formulating aged organic lime plasters, modeling monumental Buddhist and Chola relief sculptures, and burnishing palace facades to mirror brilliance.",
        "summary_ta": "\u0baa\u0bb4\u0bc8\u0baf \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8\u0baf\u0bc1\u0b9f\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc2\u0bb4\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bbf\u0b9a\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1, \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0b95\u0bbe\u0bb0\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0bb1\u0bcd\u0baa\u0bc1\u0ba4 \u0b9a\u0bc1\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0b95\u0ba4\u0bcd \u0ba4\u0bc0\u0b9f\u0bcd\u0b9f\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bc1\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf.",
        "sources": [
            "Manimekalai Canto 28",
            "Silappathikaram Indira Vizhavedutha Kathai",
            "Vastu Vidya Shastra Stucco Sculpting Protocols"
        ],
        "content": "# Kaveripattinam Royal Stucco Mason Sudhai Kootu Sirpachari\n\n## Guild Lineage & Royal Patronage\nServing in the cosmopolitan capital of the Early Cholas at Poompuhar, the *Sudhai Kootu Sirpachari* was an artist-engineer trained in both lithic geometry and organic chemical plaster compounding. Holding court appointments, he directed the embellishment of palaces, triumphal archways (*Torana*), and multi-terraced viharas.\n\n## Art of Stucco Modeling (*Sudhai Uruvam*)\nUnlike carving which is a subtractive craft, stucco sculpture was an additive and modeling discipline:\n- **Armature Creation (*Koodu-Kattu*)**: Fashioning internal skeleton frameworks from seasoned bamboo splints, copper wires, and terracotta armatures.\n- **Coarse Plastic Massing**: Applying fiber-reinforced coarse lime mortar to establish muscle volume, anatomical proportions, and dramatic drapery folds.\n- **Fine Facial Rendering**: Layering ultra-smooth Arasu-latex lime paste to model serene Buddhist facial expressions, jewelry, and ornate headdresses.\n\n## Mastery of Pebble Burnishing\nHis signature mastery lay in the hand-burnishing of drying stucco using polished river agates dipped in warm milk emulsion, creating luminous statues that resisted torrential monsoons without peeling, cracking, or discoloration.",
        "chunks": [
            {
                "language": "en",
                "title": "Royal Stucco Sculptor Technique & Organic Armatures",
                "content": "The royal stucco mason at Kaveripattinam combined bamboo and terracotta armatures with aged organic lime pastes to sculpt monumental bas-reliefs and architectural friezes polished to a weather-resistant sheen."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9 \u0b85\u0bb0\u0b9a \u0b9a\u0bc1\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf",
                "content": "\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd, \u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf \u0b95\u0bb2\u0ba8\u0bcd\u0ba4 \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8\u0baf\u0bc8 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf, \u0baa\u0bc1\u0ba4\u0bcd\u0ba4 \u0bb5\u0bbf\u0b95\u0bbe\u0bb0\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b85\u0bb4\u0bbf\u0baf\u0bbe\u0ba4 \u0b9a\u0bc1\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-marakkanam-ancient-oyster-shell-lime-calcination-haven.md",
        "slug": "place-marakkanam-ancient-oyster-shell-lime-calcination-haven",
        "category": "place",
        "name_en": "Marakkanam: Ancient Oyster-Shell Lime Calcination & Port Industrial Haven",
        "name_ta": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "neithal",
        "summary_en": "Historic port town on the Coromandel coast (Sangam Eyirpattinam) surrounded by expansive hypersaline lagoons, fossilized shell mounds, and traditional lime kilns providing calcined mortar across Tamilakam.",
        "summary_ta": "\u0b9a\u0b99\u0bcd\u0b95 \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b8e\u0baf\u0bbf\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0b8e\u0ba9\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd, \u0b89\u0baa\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bcd, \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0baa\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95 \u0bae\u0bc8\u0baf\u0bae\u0bcd.",
        "sources": [
            "Sirupanarruppadai lines 115-130",
            "Periplus of the Erythraean Sea Section 60",
            "Archaeological Survey of India Excavations at Marakkanam"
        ],
        "content": "# Marakkanam: Ancient Oyster-Shell Lime Calcination & Port Industrial Haven\n\n## Geographical Setting & Littoral Resources\nMarakkanam is located on the Coromandel coast between Puducherry and Mamallapuram ($12.2000^\\circ\\text{ N}, 79.9500^\\circ\\text{ E}$). The site is uniquely situated on the Yedayanthittu backwater estuary, where calm brackish waters nurtured massive natural beds of edible oysters, cockles, and marine gastropods. Over centuries, continuous mollusc harvesting created monumental shell middens (*Chippi medugal*) along the shoreline.\n\n## Industrial Hub of Sangam Eyirpattinam\nCelebrated in *Sirupanarruppadai* under the ancient name *Eyirpattinam*, the port combined three inter-dependent maritime industries:\n1. **Salt Manufacture (*Uppalam*)**: Extensive salt pans worked by Umanar merchants producing high-grade sea salt.\n2. **Lime Calcination (*Sunnambu Thurai*)**: Clusters of cylindrical updraft kilns operating day and night, powered by steady oceanic winds.\n3. **Coastal Shipping**: Fleet roadsteads transporting bagged quicklime, salt, and dried fish northward to the Palar valley and southward to the Kaveri delta.\n\n## Archaeological Heritage\nArchaeological surveys around Marakkanam have recorded stratified shell middens over 3 meters deep containing Sangam-era Black-and-Red Ware, amphorae fragments, and circular burnt-brick kiln foundations, confirming its status as the premier lime-calcination industrial haven of ancient Tamilakam.",
        "chunks": [
            {
                "language": "en",
                "title": "Marakkanam Estuarine Topography & Shell Lime Kilns",
                "content": "Located on the Yedayanthittu backwaters, ancient Marakkanam (Eyirpattinam) leveraged vast oyster middens and marine wind updrafts to operate an extensive lime-calcination industrial complex supplying mortar across coastal South India."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
                "content": "\u0b87\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb4\u0bbf\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0b8e\u0baf\u0bbf\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bbe\u0ba9 \u0bae\u0bb0\u0b95\u0bbe\u0ba9\u0bae\u0bcd, \u0b89\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf, \u0ba4\u0bae\u0bbf\u0bb4\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0baa\u0bb2 \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0bb0\u0bc8 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0bae\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
  [
    "text-manimekalai-white-stuccoed-palaces-and-lime-mortar-poetry",
    "cites_pyrotechnic_source",
    "concept-marine-mollusc-and-oyster-shell-calcination-kiln-pyrotechnics",
    "cultural",
    "Post-Sangam Classical Era",
    "Manimekalai verses celebrating moon-white shell-lime stucco on seven-storeyed viharas",
    "Manimekalai Canto 28:38-40"
  ],
  [
    "text-manimekalai-white-stuccoed-palaces-and-lime-mortar-poetry",
    "describes_mortar_composition",
    "concept-jaggery-water-and-kadukkai-myrobalan-slaked-lime-mortar-chemistry",
    "cultural",
    "Post-Sangam Classical Era",
    "Epic descriptions of jaggery liquor and Kadukkai decoction slaked lime renderings",
    "Manimekalai Canto 19:105-118"
  ],
  [
    "concept-marine-mollusc-and-oyster-shell-calcination-kiln-pyrotechnics",
    "excavated_at",
    "place-marakkanam-ancient-oyster-shell-lime-calcination-haven",
    "archaeological",
    "Early Historic to Sangam Era",
    "Stratified shell middens and circular burnt-brick updraft kiln foundations",
    "Archaeological Excavations at Marakkanam Littoral Shell Middens"
  ],
  [
    "concept-jaggery-water-and-kadukkai-myrobalan-slaked-lime-mortar-chemistry",
    "practiced_by",
    "char-kaveripattinam-royal-stucco-mason-sudhai-kootu-sirpachari",
    "guild_membership",
    "Sangam to Medieval Era",
    "Royal stucco masons compounding organic-inorganic Vensuthai Kootu mortar",
    "Mayamata Vastu Shastra Chapter 18"
  ],
  [
    "concept-hydraulic-calcination-and-kankar-nodule-quicklime-hydration",
    "utilized_in_fortifications",
    "place-vallam-ancient-chariot-wheelwright-and-bronze-fitting-haven",
    "military_tech",
    "Early Historic Era",
    "Kankar hydraulic lime mortar lining moat revetments and sluice spillways",
    "Excavations at Vallam and Kodumanal Hydraulic Works"
  ],
  [
    "concept-polished-arasu-maram-chunam-rendering-and-burnished-stucco-finish",
    "burnished_by",
    "char-kaveripattinam-royal-stucco-mason-sudhai-kootu-sirpachari",
    "artistic",
    "Sangam to Chola Era",
    "Agate pebble burnishing of moist intonaco into glass-hard calcite skin",
    "Silappathikaram Kadaladukathai lines 110-125"
  ],
  [
    "insc-marakkanam-chola-oyster-shell-lime-kiln-endowment-charters",
    "inscribed_at",
    "place-marakkanam-ancient-oyster-shell-lime-calcination-haven",
    "epigraphical",
    "Early Medieval Era",
    "Bhumisvara temple epigraphs recording lime-burner guild shell-midden rights",
    "South Indian Inscriptions Vol. VII No. 392"
  ],
  [
    "insc-pudukkottai-rock-cut-cave-temple-lime-plaster-epigraphs",
    "documents_plaster_maintenance",
    "concept-polished-arasu-maram-chunam-rendering-and-burnished-stucco-finish",
    "epigraphical",
    "Pallava to Early Pandya Era",
    "Perpetual gold endowments funding cyclical re-plastering of cavern sanctuaries",
    "Inscriptions of the Pudukkottai State Part I No. 12 & 38"
  ],
  [
    "char-marakkanam-master-shell-lime-calciner-sunnambu-kallan",
    "operates_at",
    "place-marakkanam-ancient-oyster-shell-lime-calcination-haven",
    "industrial",
    "Sangam Classical Era",
    "Master calciner commanding kiln crews on the Yedayanthittu estuary dunes",
    "Sirupanarruppadai lines 145-160"
  ],
  [
    "char-kaveripattinam-royal-stucco-mason-sudhai-kootu-sirpachari",
    "canonized_in",
    "text-manimekalai-white-stuccoed-palaces-and-lime-mortar-poetry",
    "cultural",
    "Sangam Classical Era",
    "Stucco modelling artisans immortalized in Sathanar's palace descriptions",
    "Manimekalai Canto 28"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 23 Corpus 1: Shell Lime Calcination & Calcareous Stucco into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 23 Corpus 1: Shell Lime Calcination & Calcareous Stucco Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
