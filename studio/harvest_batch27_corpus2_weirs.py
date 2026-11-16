#!/usr/bin/env python3
# Ingestion harvester for Batch 27 Corpus 2: Tidal Estuarine Fish-Weirs & Stake-Nets
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
        "file": "knowledge/texts/text-perumpanarruppadai-lagoon-fish-weir-and-parathavar-trapping-poetry.md",
        "slug": "text-perumpanarruppadai-lagoon-fish-weir-and-parathavar-trapping-poetry",
        "category": "text",
        "name_en": "Perumpanarruppadai: Classical Poetry on Estuarine Fish-Weirs & Brackish Trapping",
        "name_ta": "\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 - \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc0\u0ba9\u0bcd \u0baa\u0bca\u0bb1\u0bbf \u0baa\u0bbe\u0b9f\u0bb2\u0bcd",
        "era": "Sangam Era (c. 200 BCE \u2013 200 CE)",
        "year_start": -200,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Sangam verses by Kadiyalur Uruthirankannanar depicting coastal lagoon settlements, bamboo stake-weirs erected across tidal creeks, and nocturnal torchlight trapping of mullet and tiger prawns.",
        "summary_ta": "\u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0b95\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf\u0b95\u0bb3\u0bcd, \u0b87\u0bb0\u0bb5\u0bbf\u0bb2\u0bcd \u0ba4\u0bc0\u0baa\u0bcd\u0baa\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc6\u0bb3\u0bbf\u0b9a\u0bcd\u0b9a\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bae\u0b9f\u0bb5\u0bc8 \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0bb5\u0bbe\u0bb4\u0bcd\u0bb5\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8.",
        "sources": [
            "Perumpanarruppadai lines 315-325",
            "Sangam Neithal Poetry Commentary"
        ],
        "content": "# Perumpanarruppadai: Classical Poetry on Estuarine Fish-Weirs & Brackish Trapping\n\n## Neithal Creek Engineering in Classical Verse\nThe classical anthology *Perumpanarruppadai* vividly describes the sophisticated tidal trapping systems constructed by coastal fishermen (*Parathavar*):\n\n```\n\"\u0b95\u0bb4\u0bbf\u0b9a\u0bc2\u0bb4\u0bcd \u0baa\u0b9f\u0baa\u0bcd\u0baa\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bbf\u0bae\u0ba9\u0bc8 \u0bb5\u0bbf\u0baf\u0bb2\u0bcd\u0ba8\u0b95\u0bb0\u0bcd\n\u0ba8\u0bc6\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0bae\u0bbe\u0b9f\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bbf\u0bb2\u0bb5\u0bc1\u0b95\u0bcd\u0b95\u0ba4\u0bbf\u0bb0\u0bcd \u0baa\u0bcb\u0bb2\n\u0bb5\u0bc7\u0baf\u0bcd\u0ba8\u0bcd\u0ba4 \u0ba8\u0bb1\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bcd \u0bb5\u0bc7\u0bb2\u0bbf \u0b85\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1\n\u0bae\u0b9f\u0bb5\u0bc8 \u0bae\u0bc0\u0ba9\u0bcd \u0b95\u0bb5\u0bb0\u0bc1\u0bae\u0bcd...\"\n\u2014 \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 315-318\n```\n\n## Nocturnal Tidal Trapping\nPoets capture the ingenious exploitation of ocean tides. During incoming high tides (*Perukku*), schools of brackish-water fish rushed into the mangrove estuaries. As the tide ebbed (*Vattram*), bamboo fences (*Vey-Velik-Kattu*) intercepted returning shoals, channeling them into funnel traps where fishermen speared leaping grey mullets (*Madavai*) under flare torches.",
        "chunks": [
            {
                "language": "en",
                "title": "Perumpanarruppadai Estuarine Fish-Weir Verses",
                "content": "Perumpanarruppadai verses describe woven bamboo fences and stake-nets capturing tidal shoals of mullet fish in coastal lagoons."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd \u0baa\u0bca\u0bb1\u0bbf \u0bb5\u0bb0\u0bcd\u0ba3\u0ba9\u0bc8",
                "content": "\u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bb5\u0bc7\u0bb2\u0bbf\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0b9f\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bc8\u0baa\u0bbf\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0bae\u0bc1\u0bb1\u0bc8\u0baf\u0bc8 \u0baa\u0bbe\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai.md",
        "slug": "concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai",
        "category": "concept",
        "name_en": "Bamboo-Slat Tidal Fish-Weir Engineering (Sirahu & Padugai-Valai)",
        "name_ta": "\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 (\u0b9a\u0bbf\u0bb1\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8)",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Construction of V-shaped leading fences (Sirahu) and heart-shaped terminal impoundments (Padugai) from split bamboo slats tied with coir twine across tidal estuarine channels, catching receding fish passively on ebb tides.",
        "summary_ta": "\u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0b93\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 V \u0bb5\u0b9f\u0bbf\u0bb5\u0bbf\u0bb2\u0bcd \u0ba8\u0b9f\u0bcd\u0b9f\u0bc1, \u0bb5\u0b9f\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bc1\u0bb3\u0bcd\u0bb3 \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95 \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0bbf\u0bb1\u0b95\u0bc1\u0bb5\u0bc7\u0bb2\u0bbf\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Traditional Estuarine Fishing Systems of Coromandel",
            "Marine Ethno-Archaeology of Tamil Nadu"
        ],
        "content": "# Bamboo-Slat Tidal Fish-Weir Engineering (Sirahu & Padugai-Valai)\n\n## Hydrodynamics of Tidal Fish-Weirs\nAlong the mangrove lagoons of Pulicat, Muttukadu, and Pichavaram, ancient fisherfolk mastered passive hydraulic trapping. They erected semi-permanent guiding fences called *Sirahu* (wings) angled diagonally against the tidal current.\n\n## Split Bamboo & Coir Matting Construction\nStout palmyrah posts were driven into muddy estuary beds. Between them, artisans tied flexible screens woven from split bamboo strips (*Moongil-Thatti*) lashed with rot-resistant palmyrah and coir cordage. The gaps allowed water to drain freely while blocking fish larger than fingerlings.\n\n## Terminal Heart-Trap Chambers (*Padugai*)\nThe converging wings guided schooling fish into a heart-shaped holding chamber (*Padugai*) equipped with non-return funnel valving. At low tide, fishermen waded in to scoop concentrated catches with hand dip-nets (*Koodai-Valai*).",
        "chunks": [
            {
                "language": "en",
                "title": "Bamboo-Slat Tidal Fish-Weir Hydrodynamics & Sirahu Wings",
                "content": "Angled bamboo fences and heart-shaped terminal chambers passively trapped schools of fish during estuarine tidal ebb cycles."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0b95\u0bc1\u0bb5\u0bc7\u0bb2\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd \u0baa\u0bca\u0bb1\u0bbf \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd V-\u0bb5\u0b9f\u0bbf\u0bb5 \u0b9a\u0bbf\u0bb1\u0b95\u0bc1\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0b9f\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bc8\u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-coir-staked-estuarine-pound-net-hydraulics-katti-valai.md",
        "slug": "concept-coir-staked-estuarine-pound-net-hydraulics-katti-valai",
        "category": "concept",
        "name_en": "Coir-Staked Estuarine Pound-Net Hydraulics (Katti-Valai & Thanduk-Kodi)",
        "name_ta": "\u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0ba8\u0bbf\u0bb2\u0bc8\u0baf\u0bbe\u0ba9 \u0bb5\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc1",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Deployment of fixed submerged barrier nets woven from heavy-gauge twisted coconut coir cordage, secured to mangrove-wood stakes (Kazhi) to capture large predatory estuarine species like barramundi and sea bass.",
        "summary_ta": "\u0b9a\u0ba4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0ba8\u0bbf\u0bb2\u0b95\u0bcd \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0bb2\u0bc8\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf, \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba8\u0bc1\u0bb4\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bbf\u0baf \u0b95\u0bbe\u0bb2\u0bbe \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0bb5\u0bbe \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Traditional Indian Ocean Fishing Gear",
            "Neithal Technology Studies"
        ],
        "content": "# Coir-Staked Estuarine Pound-Net Hydraulics (Katti-Valai & Thanduk-Kodi)\n\n## Fixed Pound-Net Architecture (*Katti-Valai*)\nUnlike drifting gillnets, the *Katti-Valai* was an anchored stationary trap. Fishermen drove dense lines of mangrove stakes (*Thandu*) across mouth bars where ocean tides met river discharge.\n\n## Salt-Resistant Coir Meshing\nNets were knotted from multi-ply twisted coconut coir (*Thennam-Kayiru*), treated with astringent mangrove bark decoctions (*Kandal-Pattai*) to prevent biofouling and marine wood-borer decay. Heavy terracotta sinkers held the bottom line flush against the silt bed, while dried gourd floats maintained net verticality against powerful tidal surges.",
        "chunks": [
            {
                "language": "en",
                "title": "Coir-Staked Estuarine Pound-Net Engineering",
                "content": "Fixed submerged nets knotted from coconut coir and secured to mangrove stakes intercepted predatory fish entering tidal estuaries."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd\u0baa\u0bbf\u0b9f\u0bbf \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bb5\u0bb2\u0bc8\u0b95\u0bb3\u0bc8 \u0b9a\u0ba4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0ba8\u0bbf\u0bb2 \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bc6\u0bb0\u0bbf\u0baf \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-lunar-cycle-nocturnal-brackish-lagoon-prawn-and-mullet-trapping.md",
        "slug": "concept-lunar-cycle-nocturnal-brackish-lagoon-prawn-and-mullet-trapping",
        "category": "concept",
        "name_en": "Lunar Cycle Nocturnal Brackish Lagoon Prawn & Mullet Trapping (Padu-Neri)",
        "name_ta": "\u0ba4\u0bbf\u0ba4\u0bbf \u0ba8\u0bbf\u0bb2\u0bb5\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bb5\u0bc1\u0ba8\u0bc7\u0bb0 \u0b87\u0bb1\u0bbe\u0bb2\u0bcd-\u0bae\u0b9f\u0bb5\u0bc8 \u0bae\u0bc0\u0ba9\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Synchronizing estuarine net-setting with lunar syzygy (Amavasai and Pournami spring tides), utilizing nocturnal flare torches (Theevatti) to attract phototactic tiger prawns and mullets into conical wicker traps.",
        "summary_ta": "\u0b85\u0bae\u0bbe\u0bb5\u0bbe\u0b9a\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bcc\u0bb0\u0bcd\u0ba3\u0bae\u0bbf \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0b8f\u0bb1\u0bcd\u0bb1\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0ba4\u0bc0\u0baa\u0bcd\u0baa\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc6\u0bb3\u0bbf\u0b9a\u0bcd\u0b9a\u0ba4\u0bcd\u0ba4\u0bbe\u0bb2\u0bcd \u0b87\u0bb1\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0baa\u0bca\u0bb1\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bcd \u0bb5\u0bb0\u0bb5\u0bb4\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Traditional Maritime Ecological Knowledge",
            "Sangam Neithal Ethno-Biology"
        ],
        "content": "# Lunar Cycle Nocturnal Brackish Lagoon Prawn & Mullet Trapping (Padu-Neri)\n\n## Lunar Tidal Calibration (*Padu-Neri*)\nAncient lagoon fishermen operated on an empirical lunar calendar. They recognized that during new moon (*Amavasai*) and full moon (*Pournami*) spring tides (*Perukku-Nal*), maximum water volumes forced immense migrations of juvenile tiger prawns (*Iraal*) and grey mullets (*Madavai*) into shallow lagoons.\n\n## Nocturnal Phototaxis Trapping\nFishermen mounted resinous torch baskets (*Theevatti*) at the entrances of woven conical bamboo traps (*Koodu*). Drawn by the luminous reflections on dark brackish waters, prawns and fish swam directly into narrow non-return chambers.",
        "chunks": [
            {
                "language": "en",
                "title": "Lunar Cycle Estuarine Prawn & Mullet Trapping",
                "content": "Synchronizing trap settings with lunar spring tides and torchlight phototaxis enabled massive harvests of estuarine prawns and mullets."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bbf\u0bb2\u0bb5\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bb5\u0bc1\u0ba8\u0bc7\u0bb0 \u0b87\u0bb1\u0bbe\u0bb2\u0bcd \u0baa\u0bca\u0bb1\u0bbf \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0ba4\u0bbf\u0ba4\u0bbf \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bb5\u0bc6\u0bb3\u0bcd\u0bb3 \u0b8f\u0bb1\u0bcd\u0bb1\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bc0\u0baa\u0bcd\u0baa\u0ba8\u0bcd\u0ba4 \u0b92\u0bb3\u0bbf\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b87\u0bb1\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-smoke-cured-estuarine-fish-preservation-and-salt-brine-maturation.md",
        "slug": "concept-smoke-cured-estuarine-fish-preservation-and-salt-brine-maturation",
        "category": "concept",
        "name_en": "Smoke-Cured Estuarine Fish Preservation & Salt-Brine Maturation (Karuvadu-Vaithal)",
        "name_ta": "\u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd \u0b89\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd\u0b95\u0ba3\u0bcd\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0b95\u0bc8 \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Post-harvest preservation of surplus estuarine catches using sea salt rubbing, brine vat soaking, and mangrove-wood smoke drying (Pugai-Ittal) to produce shelf-stable dried fish traded to inland agricultural zones.",
        "summary_ta": "\u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0baa\u0bcd\u0baa\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1, \u0b9a\u0ba4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0ba8\u0bbf\u0bb2 \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0b95\u0bbe\u0bb2\u0bae\u0bcd \u0b95\u0bc6\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Purananuru Salt & Fish Trade",
            "Traditional Fish Curing of Coromandel"
        ],
        "content": "# Smoke-Cured Estuarine Fish Preservation & Salt-Brine Maturation (Karuvadu-Vaithal)\n\n## Dealing with Seasonal Gluts\nThe immense catches harvested during spring tides exceeded immediate local consumption, necessitating long-term curing technologies.\n\n## Brining & Smoke Curing\nCatches were gutted, split longitudinally, and packed in subterranean clay jars layered with coarse sea salt from nearby saltpans (*Uppalam*). After drawing out moisture for three days, fish were hung on bamboo racks inside enclosed curing huts over smoldering mangrove roots (*Kandal-Kattai*), imparting antimycotic smoke coatings and savory flavor.",
        "chunks": [
            {
                "language": "en",
                "title": "Estuarine Fish Salt Brining & Mangrove Smoke Curing",
                "content": "Longitudinal gutting, salt brining, and smoking over mangrove roots cured seasonal surplus estuarine fish into durable Karuvadu."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bc0\u0ba9\u0bcd \u0b89\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd\u0b95\u0ba3\u0bcd\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0b95\u0bc8 \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b95\u0b9f\u0bb2\u0bcd \u0b89\u0baa\u0bcd\u0baa\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b95\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b89\u0bb2\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0b95\u0bbe\u0bb2\u0bae\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-pulicat-pazhaverkadu-lagoon-fishery-and-weir-tax-charters.md",
        "slug": "insc-pulicat-pazhaverkadu-lagoon-fishery-and-weir-tax-charters",
        "category": "inscription",
        "name_en": "Pazhaverkadu (Pulicat) Inscriptions: Lagoon Weir Charters & Royal Fish Tolls",
        "name_ta": "\u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b8f\u0bb0\u0bbf \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b9a\u0bc1\u0b99\u0bcd\u0b95 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Imperial Chola to Vijayanagara Era",
        "year_start": 950,
        "year_end": 1400,
        "thinai": "neithal",
        "summary_en": "Stone inscriptions at coastal temples along Pulicat Lake documenting fishing territories (Padu-Urimai), bamboo weir maintenance rights, and royal fish tithes (Meen-Pattam).",
        "summary_ta": "\u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b8f\u0bb0\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf\u0b95\u0bb3\u0bcd \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0baa\u0bbe\u0b9f\u0bc1 \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bb0\u0bbf \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. XXVI",
            "Tiruvallur District Epigraphy"
        ],
        "content": "# Pazhaverkadu (Pulicat) Inscriptions: Lagoon Weir Charters & Royal Fish Tolls\n\n## Epigraphic Geography of Pulicat Lake\nPulicat Lagoon (historic Pazhaverkadu) represents India's second largest brackish-water lagoon. Stone epigraphs preserve governance codes regulating estuarine fishing rights.\n\n## Traditional Padu Rights & Royal Revenue\nThe inscriptions codify ancestral fishing territory rotations (*Padu-Murai*), stipulating that specific villages held exclusive weekly rights to erect bamboo stake-weirs across named creeks in return for paying a tithe (*Meen-Pattam*) to the state treasury.",
        "chunks": [
            {
                "language": "en",
                "title": "Pazhaverkadu Lagoon Fishing Weir Charters",
                "content": "Inscriptions from Pulicat Lake codify rotational fishing rights and royal taxes on estuarine bamboo fish-weirs."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf \u0b9a\u0bc1\u0b99\u0bcd\u0b95\u0bb5\u0bb0\u0bbf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b8f\u0bb0\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0ba9 \u0baa\u0bbe\u0b9f\u0bc1 \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0bb5\u0bb0\u0bbf\u0bb5\u0bbf\u0ba4\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-muttukadu-coastal-estuarine-fish-weir-endowments.md",
        "slug": "insc-muttukadu-coastal-estuarine-fish-weir-endowments",
        "category": "inscription",
        "name_en": "Muttukadu Estuarine Charters: Tidal Weir Fish Tithes & Temple Endowments",
        "name_ta": "\u0bae\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf \u0b95\u0bca\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Pallava to Chola Era",
        "year_start": 700,
        "year_end": 1100,
        "thinai": "neithal",
        "summary_en": "Inscriptions along the Buckingham canal corridor recording fishermen guilds dedicating proceeds from seasonal weir catches to endow perpetual temple lamps.",
        "summary_ta": "\u0bae\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b92\u0bb0\u0bc1 \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bc8 \u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0bb0\u0bbf\u0b95\u0bcd\u0b95 \u0ba4\u0bbe\u0ba9\u0bae\u0bbe\u0b95 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Chengalpattu District Archaeological Epigraphs",
            "Pallava Lithic Records"
        ],
        "content": "# Muttukadu Estuarine Charters: Tidal Weir Fish Tithes & Temple Endowments\n\n## Estuarine Settlements south of Mamallapuram\nMuttukadu, where the Kovalam backwaters meet the Bay of Bengal, hosted thriving estuarine fishing hamlets under Pallava and Chola governance.\n\n## Fisherman Guild Endowments\nLithic records document fishing corporations donating shares of dried fish (*Unangal*) and fish oil derived from estuarine weirs to sustain perpetual oil lamps at coastal shrines.",
        "chunks": [
            {
                "language": "en",
                "title": "Muttukadu Tidal Fish-Weir Temple Endowments",
                "content": "Lithic charters at Muttukadu backwaters record fishermen donating dried fish and oil from tidal weirs to coastal temples."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bb5\u0bb0\u0bcd \u0b85\u0bb1\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1",
                "content": "\u0bae\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0bb5\u0bb0\u0bc1\u0bb5\u0bbe\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0ba8\u0bcd\u0ba4\u0bbe\u0bb5\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-pazhaverkadu-master-estuarine-weir-engineer-valai-parathavan.md",
        "slug": "char-pazhaverkadu-master-estuarine-weir-engineer-valai-parathavan",
        "category": "character",
        "name_en": "Maraban Parathavan: Master Estuarine Weir Architect of Pazhaverkadu",
        "name_ta": "\u0bae\u0bbe\u0bb1\u0baa\u0ba9\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0ba9\u0bcd - \u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd",
        "era": "Sangam Era (c. 100 BCE \u2013 100 CE)",
        "year_start": -100,
        "year_end": 100,
        "thinai": "neithal",
        "summary_en": "Veteran coastal artisan who engineered extensive bamboo-slat tidal traps, calibrated weir wing angles against monsoon surges, and resolved village lagoon fishing disputes.",
        "summary_ta": "\u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b8f\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0ba8\u0bc0\u0bb0\u0bcb\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd\u0ba4\u0bc8 \u0b95\u0ba3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0b95\u0bc1\u0bb5\u0bc7\u0bb2\u0bbf\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0bc0\u0ba9\u0bb5\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbe\u0bb3\u0bb0\u0bcd.",
        "sources": [
            "Pulicat Fisherfolk Oral Genealogies",
            "Coromandel Coastal Folklore"
        ],
        "content": "# Maraban Parathavan: Master Estuarine Weir Architect of Pazhaverkadu\n\n## Pioneer of Tidal Hydraulic Weirs\nMaraban Parathavan commanded the estuarine weir guilds of northern Tamilakam. He read the velocity of incoming ocean tides and drove palmyrah foundation pilings at critical hydraulic focal points.\n\n## Guild Leadership\nHis precision-angled bamboo wings directed migrating shoals into terminal holding pens without collapsing under monsoon torrents, ensuring bountiful fish yields for coastal communities.",
        "chunks": [
            {
                "language": "en",
                "title": "Maraban Parathavan Master Weir Architect Biography",
                "content": "Master weir architect Maraban Parathavan calibrated bamboo tidal fences and stake-nets across the Pulicat lagoon."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf \u0bae\u0bc7\u0ba4\u0bc8 \u0bae\u0bbe\u0bb1\u0baa\u0ba9\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0ba9\u0bcd",
                "content": "\u0ba8\u0bc0\u0bb0\u0bcb\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bb5\u0bc7\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0bcd\u0b95\u0bc7\u0bb1\u0bcd\u0baa \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bb3\u0ba4\u0bcd\u0ba4\u0bc8\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0bc0\u0ba9\u0bb5\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-kayalpatnam-brackish-lagoon-fish-merchant-kala-vanikan.md",
        "slug": "char-kayalpatnam-brackish-lagoon-fish-merchant-kala-vanikan",
        "category": "character",
        "name_en": "Kumanan Vanikan: Brackish Lagoon Fish Merchant & Caravaneer",
        "name_ta": "\u0b95\u0bc1\u0bae\u0ba3\u0ba9\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0ba9\u0bcd - \u0b95\u0bbe\u0baf\u0bb2\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0b89\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd",
        "era": "Sangam Era (c. 50 BCE \u2013 150 CE)",
        "year_start": -50,
        "year_end": 150,
        "thinai": "neithal",
        "summary_en": "Prominent coastal merchant who organized bullock-cart caravans transporting cured estuarine fish, dried prawns, and sea salt from Gulf of Mannar lagoons to inland Kongu and Madurai markets.",
        "summary_ta": "\u0b95\u0bbe\u0baf\u0bb2\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0bb5\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb3\u0bcd\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0ba3\u0bcd\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b9f\u0bb0\u0bbf\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1\u0b9a\u0bc6\u0ba9\u0bcd\u0bb1\u0bc1 \u0bb5\u0bbf\u0bb1\u0bcd\u0bb1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd.",
        "sources": [
            "Akananuru Salt Caravans",
            "Early Historic Maritime Trade"
        ],
        "content": "# Kumanan Vanikan: Brackish Lagoon Fish Merchant & Caravaneer\n\n## Linking the Littoral to Inland Agrarian Cities\nOperating from the southern lagoons of Kayalpatnam and Korkai, Kumanan Vanikan purchased seasonal catches of barramundi (*Kala*) and mullets straight from weir traps.\n\n## Bull-Cart Salt Caravans\nOrganizing caravans of pack-bullocks and covered wagons (*Pandi*), Kumanan transported cured dry-fish and rock salt across dry scrub terrain, exchanging marine protein for upland paddy and pulses.",
        "chunks": [
            {
                "language": "en",
                "title": "Kumanan Vanikan Estuarine Fish Merchant Role",
                "content": "Merchant Kumanan Vanikan organized overland bullock caravans transporting cured estuarine fish and salt to inland markets."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bbe\u0baf\u0bb2\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b95\u0bc1\u0bae\u0ba3\u0ba9\u0bcd",
                "content": "\u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0bae\u0bc0\u0ba9\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b89\u0baa\u0bcd\u0baa\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b89\u0bb4\u0bb5\u0bc1 \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1\u0b9a\u0bc6\u0ba9\u0bcd\u0bb1\u0bc1 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0baa\u0ba3\u0bcd\u0b9f\u0bae\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba8\u0baf\u0ba9\u0bcd\u0bae\u0bbf\u0b95\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-pazhaverkadu-ancient-estuarine-lagoon-and-fish-weir-haven.md",
        "slug": "place-pazhaverkadu-ancient-estuarine-lagoon-and-fish-weir-haven",
        "category": "place",
        "name_en": "Pazhaverkadu: Ancient Pulicat Lagoon Haven & Estuarine Fish-Weir Center",
        "name_ta": "\u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b8f\u0bb0\u0bbf \u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bbe\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1300,
        "thinai": "neithal",
        "summary_en": "Monumental coastal lagoon at the northern boundary of Tamilakam, celebrated since Sangam times for its labyrinthine mangrove creeks, tidal fish-weirs, and maritime trade harbors.",
        "summary_ta": "\u0bb5\u0b99\u0bcd\u0b95\u0b95\u0bcd \u0b95\u0b9f\u0bb2\u0bc1\u0bae\u0bcd \u0ba8\u0ba9\u0bcd\u0ba9\u0bc0\u0bb0\u0bc1\u0bae\u0bcd \u0b87\u0ba3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0b8f\u0bb0\u0bbf\u0baf\u0bc1\u0bae\u0bcd, \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bc1\u0bae\u0bbe\u0ba9 \u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1.",
        "sources": [
            "Periplus of the Erythraean Sea",
            "Archaeological Surveys of Pulicat Lagoon"
        ],
        "content": "# Pazhaverkadu: Ancient Pulicat Lagoon Haven & Estuarine Fish-Weir Center\n\n## Marine Geography of Pulicat Lake\nStraddling the Coromandel coast north of Chennai, Pazhaverkadu (Pulicat) forms an expansive estuarine lagoon separated from the open sea by a slender barrier spit.\n\n## The Epicenter of Estuarine Trapping\nTidal inlets create immense nutrient-rich nursery grounds for mullets, prawns, and sea bass. For millennia, indigenous Parathavar communities have maintained sophisticated systems of bamboo fences and stake-nets here, making it ancient Tamilakam's premier estuarine fishing hub.",
        "chunks": [
            {
                "language": "en",
                "title": "Pazhaverkadu Estuarine Lagoon & Fish-Weir Topography",
                "content": "Pazhaverkadu (Pulicat Lake) was ancient Tamilakam's premier estuarine lagoon for tidal bamboo fish-weir systems."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b95\u0bb4\u0bbf\u0bae\u0bc1\u0b95 \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1",
                "content": "\u0bb5\u0b99\u0bcd\u0b95\u0b95\u0bcd \u0b95\u0b9f\u0bb2\u0bbf\u0ba9\u0bcd \u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0baa\u0bb4\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b8f\u0bb0\u0bbf, \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2\u0bae\u0bcd \u0ba4\u0bca\u0b9f\u0bcd\u0b9f\u0bc7 \u0bae\u0bc0\u0ba9\u0bcd\u0bb5\u0bc7\u0bb2\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bae\u0bc8\u0baf\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf\u0ba4\u0bc1."
            }
        ]
    }
]
EDGES = [
    [
        "char-pazhaverkadu-master-estuarine-weir-engineer-valai-parathavan",
        "located_in",
        "place-pazhaverkadu-ancient-estuarine-lagoon-and-fish-weir-haven",
        "geography",
        "Sangam Era",
        "Engineered and maintained bamboo-slat tidal fish-weirs at Pazhaverkadu",
        "Pulicat archaeological surveys"
    ],
    [
        "char-kayalpatnam-brackish-lagoon-fish-merchant-kala-vanikan",
        "participated_in",
        "place-pazhaverkadu-ancient-estuarine-lagoon-and-fish-weir-haven",
        "commerce",
        "Sangam Era",
        "Traded cured estuarine fish from lagoon weirs to inland caravan routes",
        "Akananuru salt caravan verses"
    ],
    [
        "concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai",
        "practiced_by",
        "char-pazhaverkadu-master-estuarine-weir-engineer-valai-parathavan",
        "craft",
        "Sangam Era",
        "Mastered hydrodynamic design of V-shaped wings and non-return fish traps",
        "Estuarine ethno-technology"
    ],
    [
        "concept-coir-staked-estuarine-pound-net-hydraulics-katti-valai",
        "related_to",
        "concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai",
        "hydraulics",
        "Sangam Era",
        "Submerged coir nets operated synergistically with bamboo weir barriers",
        "Traditional fishing gear manuals"
    ],
    [
        "concept-lunar-cycle-nocturnal-brackish-lagoon-prawn-and-mullet-trapping",
        "influenced",
        "concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai",
        "ecology",
        "Sangam Era",
        "Lunar spring tides dictated the setting and opening of estuarine fish weirs",
        "Traditional ecological knowledge"
    ],
    [
        "concept-smoke-cured-estuarine-fish-preservation-and-salt-brine-maturation",
        "influenced",
        "concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai",
        "preservation",
        "Sangam Era",
        "Seasonal surpluses from tidal weirs were preserved via salt brining and smoke curing",
        "Coromandel curing studies"
    ],
    [
        "text-perumpanarruppadai-lagoon-fish-weir-and-parathavar-trapping-poetry",
        "references",
        "concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai",
        "literature",
        "Sangam Era",
        "Poetically described woven grass fences and nocturnal torchlight fish trapping",
        "Perumpanarruppadai lines 315-325"
    ],
    [
        "insc-pulicat-pazhaverkadu-lagoon-fishery-and-weir-tax-charters",
        "evidenced_by",
        "place-pazhaverkadu-ancient-estuarine-lagoon-and-fish-weir-haven",
        "epigraphy",
        "Imperial Chola",
        "Charters codified hereditary rotational fishing rights and royal fish tithes",
        "South Indian Inscriptions"
    ],
    [
        "insc-muttukadu-coastal-estuarine-fish-weir-endowments",
        "evidenced_by",
        "char-pazhaverkadu-master-estuarine-weir-engineer-valai-parathavan",
        "epigraphy",
        "Pallava to Chola",
        "Documented fishermen guild donations of dried weir fish to endow temple lamps",
        "Chengalpattu Epigraphs"
    ],
    [
        "place-pazhaverkadu-ancient-estuarine-lagoon-and-fish-weir-haven",
        "center_of",
        "concept-bamboo-slat-tidal-fish-weir-engineering-sirahu-and-padugai",
        "geography",
        "Sangam to Chola",
        "Foremost brackish-water lagoon complex for continuous tidal weir fishing",
        "Maritime archaeological records"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 27 Corpus 2: Tidal Estuarine Fish-Weirs & Stake-Nets into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 27 Corpus 2: Tidal Estuarine Fish-Weirs & Stake-Nets Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
