#!/usr/bin/env python3
# Ingestion harvester for Batch 26 Corpus 3: Coral Reef Diving, Submarine Extraction & Marine Gemmology
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
        "file": "knowledge/texts/text-akanannuru-coral-reef-diving-and-fisherfolk-pearl-poetry.md",
        "slug": "text-akanannuru-coral-reef-diving-and-fisherfolk-pearl-poetry",
        "category": "text",
        "name_en": "Akananuru Verses on Neithal Coral Reef Diving & Fisherfolk Shore Encampments",
        "name_ta": "\u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 - \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0baa\u0bb5\u0bb4 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0bb5\u0bbe\u0bb4\u0bcd\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd",
        "era": "Sangam Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Evocative Akananuru maritime verses describing Parathavar fishermen returning with branching scarlet corals and pearls to coastal drying sands.",
        "summary_ta": "\u0bae\u0ba9\u0bcd\u0ba9\u0bbe\u0bb0\u0bcd \u0b95\u0b9f\u0bb1\u0bcd\u0b95\u0bb0\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0baa\u0bb5\u0bb4\u0bae\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0b95\u0b9f\u0bb1\u0bcd\u0b95\u0bb0\u0bc8 \u0bae\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb5\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bc1\u0bae\u0bcd \u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Akananuru poem 350",
            "Akananuru poem 70",
            "Tamil Littoral Poetry"
        ],
        "content": "# Akananuru Verses on Neithal Coral Reef Diving & Fisherfolk Shore Encampments\n\n## The Littoral Wealth of the Southern Sea\nThe maritime (*Neithal*) songs of *Akananuru* depict the vibrant coastal life along the Gulf of Mannar:\n\n```\n\"\u0bae\u0bc1\u0bb4\u0b99\u0bcd\u0b95\u0bc1 \u0ba4\u0bbf\u0bb0\u0bc8\u0baa\u0bcd \u0baa\u0bcc\u0bb5\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1\n\u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bb5\u0bb4\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bbf \u0b95\u0bca\u0ba3\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1\n\u0bb5\u0bc6\u0ba3\u0bcd\u0bae\u0ba3\u0bb1\u0bcd \u0baa\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb5\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd...\"\n\u2014 \u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bb2\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\n```\n\n## Coral Harvesting beside Pearl Fisheries\nFisherfolk fleets navigated barrier shoals, returning at sundown with red coral branches (*Sem-Pavazham*) entangled in dragnets and diver baskets, drying them alongside salt heaps on sunlit beaches.",
        "chunks": [
            {
                "language": "en",
                "title": "Akananuru Coral Harvesting & Littoral Life Verses",
                "content": "Akananuru maritime poems describe Parathavar divers harvesting scarlet coral branches and drying them along the sandy beaches."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 \u0baa\u0bb5\u0bb4 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0b95\u0b9f\u0bb2\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbf \u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bb5\u0bb4\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0b95\u0b9f\u0bb1\u0bcd\u0b95\u0bb0\u0bc8 \u0bae\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb5\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0bb0\u0bcd \u0bb5\u0bbe\u0bb4\u0bcd\u0bb5\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bb2\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-submarine-reef-coral-harvesting-and-bamboo-pole-prying.md",
        "slug": "concept-submarine-reef-coral-harvesting-and-bamboo-pole-prying",
        "category": "concept",
        "name_en": "Submarine Coral Reef Harvesting & Weighted Diver Extraction (Pavazham-Kulikkal)",
        "name_ta": "\u0b95\u0b9f\u0bb2\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bb5\u0bb4\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bc8 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb5\u0bb4\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bbf \u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Free-diving techniques by Parathavar divers in the Gulf of Mannar using stone sinkers and prying chisels to harvest Corallium rubrum colonies.",
        "summary_ta": "\u0bae\u0ba9\u0bcd\u0ba9\u0bbe\u0bb0\u0bcd \u0bb5\u0bb3\u0bc8\u0b95\u0bc1\u0b9f\u0bbe \u0baa\u0bb5\u0bb4\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b8e\u0b9f\u0bc8\u0baf\u0bc1\u0bb3\u0bcd\u0bb3 \u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbf, \u0baa\u0bb5\u0bb4\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bbf\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Marine Archaeology of Gulf of Mannar",
            "Traditional Pearl & Coral Fisheries"
        ],
        "content": "# Submarine Coral Reef Harvesting & Weighted Diver Extraction (Pavazham-Kulikkal)\n\n## Barrier Reef Ecology in the Gulf of Mannar\nShallow coral reefs in the Palk Bay and Gulf of Mannar sheltered branching red precious corals (*Pavazhak-kodi*).\n\n## Weighted Dive Mechanics\nFree-divers used heavy stone sinkers (*Kulikkal*) tied to their feet to descend rapidly to depths of 10\u201315 fathoms. Using bronze or bamboo prying chisels (*Vettu-Kole*), they cleanly detached mature coral stalks at the base without shattering the delicate branches.",
        "chunks": [
            {
                "language": "en",
                "title": "Submarine Coral Harvesting & Free-Diver Mechanics",
                "content": "Free-diving Parathavar used stone sinkers and notched prying tools to harvest branching red coral colonies from barrier reefs."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0b9f\u0bb2\u0b9f\u0bbf \u0baa\u0bb5\u0bb4 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8 \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0b8e\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf \u0b95\u0b9f\u0bb2\u0bbf\u0bb2\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbf \u0baa\u0bb5\u0bb4\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0b9a\u0bc7\u0ba4\u0bae\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf \u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-calcareous-coral-branch-seasoning-and-sandstone-abrasive-smoothing.md",
        "slug": "concept-calcareous-coral-branch-seasoning-and-sandstone-abrasive-smoothing",
        "category": "concept",
        "name_en": "Calcareous Coral Branch Seasoning & Sandstone Lapidary Abrasion (Pavazha-Sevithal)",
        "name_ta": "\u0baa\u0bb5\u0bb4\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bbf \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bb1\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0ba4\u0bc0\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Washing raw coral in sweet water lye to dissolve living tissue, followed by wet sandstone grinding to shape bead blanks and expose crimson luster.",
        "summary_ta": "\u0baa\u0bc1\u0ba4\u0bbf\u0ba4\u0bbe\u0b95 \u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0ba9\u0bcd\u0ba9\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0ba3\u0bb1\u0bcd\u0b95\u0bb2\u0bcd\u0bb2\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0baf\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0ba4\u0bc0\u0b9f\u0bcd\u0b9f\u0bbf \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Lapidary Crafts in Ancient Tamilakam",
            "Indian Ocean Gemmology Studies"
        ],
        "content": "# Calcareous Coral Branch Seasoning & Sandstone Lapidary Abrasion (Pavazha-Sevithal)\n\n## De-fleshing in Sweet Water Lye\nHarvested coral branches were steeped in tubs of well-water with wood-ash lye to dissolve organic coenosarc tissue without harming the calcium carbonate skeleton.\n\n## Sandstone Abrasion Wheels\nDried stems were sectioned into bead cylinders and smoothed on revolving sandstone wheels (*Aanai-Kal*) charged with wet quartz silt, developing a smooth, brilliant red polish.",
        "chunks": [
            {
                "language": "en",
                "title": "Coral Seasoning & Sandstone Wheel Grinding",
                "content": "Post-harvest lye washing and wet sandstone abrasive grinding shaped raw coral stalks into smooth crimson bead blanks."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bb5\u0bb4\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bbf \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0ba4\u0bc0\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd",
                "content": "\u0ba8\u0ba9\u0bcd\u0ba9\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0baa\u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0ba3\u0bb1\u0bcd\u0b95\u0bb2\u0bcd\u0bb2\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0baf\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0ba9 \u0baa\u0bb5\u0bb4 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bbe\u0b95 \u0bae\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-coral-bead-perforation-and-quartz-micro-drill-lapidary.md",
        "slug": "concept-coral-bead-perforation-and-quartz-micro-drill-lapidary",
        "category": "concept",
        "name_en": "Coral Bead Perforation & High-Speed Bow-Drill Lapidary (Pavazha-Mani-Thulaithal)",
        "name_ta": "\u0baa\u0bb5\u0bb4 \u0bae\u0ba3\u0bbf \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb2\u0bcd-\u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bcd\u0b95\u0bb0\u0bc1\u0bb5\u0bbf \u0bae\u0ba3\u0bbf\u0bb5\u0bbf\u0ba9\u0bc8",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Drilling concentric stringing bores through brittle coral beads using micro-flint bow drills and fine corundum abrasive slurry.",
        "summary_ta": "\u0b95\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0bbe\u0ba9 \u0baa\u0bb5\u0bb4 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba8\u0bc1\u0ba3\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0b87\u0b9f\u0bc1\u0bb5\u0ba4\u0bb1\u0bcd\u0b95\u0bc1 \u0bb5\u0bbf\u0bb2\u0bcd-\u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bcd\u0b95\u0bb0\u0bc1\u0bb5\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bb1\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0bb5\u0bc1\u0b9f\u0bb0\u0bc8\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Bead Lapidary at Korkai and Kodumanal",
            "Ancient Drilling Technologies"
        ],
        "content": "# Coral Bead Perforation & High-Speed Bow-Drill Lapidary (Pavazha-Mani-Thulaithal)\n\n## Micro-Drilling Brittle Aragonite\nBecause red coral has moderate hardness (Mohs 3.5\u20134) and brittle cleavages, high-speed micro-drills were required to prevent fracturing.\n\n## Double-Ended Bow-Drill Technique\nArtisans used iron drill points tipped with micro-flint, driven by high-velocity bow cords. By drilling halfway from each side with oil and corundum slurry, they formed clean, perfectly centered stringing bores.",
        "chunks": [
            {
                "language": "en",
                "title": "Bow-Drill Perforation of Brittle Coral Beads",
                "content": "Micro-lapidary bow-drilling with corundum slurry perforated delicate coral beads from both ends to avoid spalling."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bbf\u0bb2\u0bcd-\u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bcd\u0b95\u0bb0\u0bc1\u0bb5\u0bbf \u0baa\u0bb5\u0bb4 \u0bae\u0ba3\u0bbf \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0baa\u0bb5\u0bb4 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bcd \u0b89\u0b9f\u0bc8\u0baf\u0bbe\u0bae\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95 \u0b87\u0bb0\u0bc1\u0baa\u0bc1\u0bb1\u0bae\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0ba8\u0bc1\u0ba3\u0bcd-\u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bb2\u0bcd \u0b95\u0bb2\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-scarlet-coral-necklaces-pavazhamalai-and-chola-temple-donations.md",
        "slug": "concept-scarlet-coral-necklaces-pavazhamalai-and-chola-temple-donations",
        "category": "concept",
        "name_en": "Scarlet Coral Necklaces (Pavazhamalai) & Chola Temple Epigraphic Endowments",
        "name_ta": "\u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bb5\u0bb4 \u0bae\u0bbe\u0bb2\u0bc8 \u0b95\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0bc8",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "neithal",
        "summary_en": "Prestige jewelry stringing scarlet coral beads with pearls and gold spacers, cataloged in Thanjavur temple inscriptions as sacred royal endowments.",
        "summary_ta": "\u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b99\u0bcd\u0b95 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bbe\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Thanjavur Brihadisvara Inscriptions",
            "Chola Temple Jewellery Registers"
        ],
        "content": "# Scarlet Coral Necklaces (Pavazhamalai) & Chola Temple Epigraphic Endowments\n\n## Aesthetic Synthesis of Coral and Pearls\nIn classical Tamil adornment, red coral (*Pavazham*) was paired with white pearls (*Muthu*). Strung on gold wire with repouss\u00e9 filigree beads, these multi-strand necklaces adorned royals and temple deities.\n\n## Thanjavur Inscriptional Inventories\nRajaraja Chola I and his queens gifted numerous *Pavazhamalai* to the Thanjavur temple. Inscriptions record the exact weight (*Kalanju*), bead count, and gold clasp alloy specifications.",
        "chunks": [
            {
                "language": "en",
                "title": "Pavazhamalai Coral Necklaces & Chola Temple Gifts",
                "content": "Strands of scarlet coral and pearls formed elite Pavazhamalai necklaces recorded in royal temple endowments."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bb5\u0bb4 \u0bae\u0bbe\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b86\u0baa\u0bb0\u0ba3\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bcd",
                "content": "\u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0baa\u0bb5\u0bb4\u0bae\u0bc1\u0bae\u0bcd \u0b87\u0ba3\u0bc8\u0ba8\u0bcd\u0ba4 \u0bb5\u0bbf\u0bb2\u0bc8\u0bae\u0ba4\u0bbf\u0baa\u0bcd\u0baa\u0bb1\u0bcd\u0bb1 \u0b86\u0baa\u0bb0\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b9e\u0bcd\u0b9a\u0bc8 \u0baa\u0bc6\u0bb0\u0bbf\u0baf\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-manamelkudi-pandyar-coral-fishery-and-marine-revenue-charters.md",
        "slug": "insc-manamelkudi-pandyar-coral-fishery-and-marine-revenue-charters",
        "category": "inscription",
        "name_en": "Manamelkudi Epigraphs: Pandya Royal Charters on Marine Coral Tolls",
        "name_ta": "\u0bae\u0ba3\u0bae\u0bc7\u0bb2\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0baa\u0bb5\u0bb4\u0ba4\u0bcd\u0ba4\u0bc1\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0bb5\u0bb0\u0bbf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Medieval Pandya Era",
        "year_start": 800,
        "year_end": 1250,
        "thinai": "neithal",
        "summary_en": "Lithic charters at Manamelkudi recording Pandya customs duties and royal tithes levied on boatloads of harvested raw coral branches.",
        "summary_ta": "\u0bae\u0ba3\u0bae\u0bc7\u0bb2\u0bcd\u0b95\u0bc1\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0ba4\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b9a\u0bc1\u0b99\u0bcd\u0b95 \u0bb5\u0bb0\u0bbf\u0b95\u0bb3\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Pandya Inscriptions of Pudukkottai",
            "Maritime Epigraphy of Tamil Nadu"
        ],
        "content": "# Manamelkudi Epigraphs: Pandya Royal Charters on Marine Coral Tolls\n\n## Customs Charters in Palk Bay\nManamelkudi was a vital collection haven for marine commodities. Stone epigraphs detail royal Pandya tolls (*Kadamai*) on boatloads of harvested coral (*Pavazha-Thoni*).\n\n## Revenue Allocation\nA portion of the harvested coral revenue was remitted to the state treasury while dedicated shares maintained harbour infrastructure and coastal temples.",
        "chunks": [
            {
                "language": "en",
                "title": "Manamelkudi Inscriptions on Coral Marine Tolls",
                "content": "Lithic charters from Manamelkudi record royal Pandya revenue tithes on harvested marine coral boatloads."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba3\u0bae\u0bc7\u0bb2\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0baa\u0bb5\u0bb4\u0ba4\u0bcd\u0ba4\u0bc1\u0bb1\u0bc8 \u0b9a\u0bc1\u0b99\u0bcd\u0b95\u0bb5\u0bb0\u0bbf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0bae\u0ba3\u0bae\u0bc7\u0bb2\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bb5\u0bb4\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bbf\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bbf\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bb0\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b85\u0bb0\u0b9a\u0bc1 \u0b86\u0ba3\u0bc8\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-devipattinam-coastal-coral-merchant-and-amphora-epigraphs.md",
        "slug": "insc-devipattinam-coastal-coral-merchant-and-amphora-epigraphs",
        "category": "inscription",
        "name_en": "Devipattinam Maritime Records: Coral Merchant Guilds & Roman Amphorae",
        "name_ta": "\u0ba4\u0bc7\u0bb5\u0bbf\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0baa\u0bb5\u0bb4 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bcb\u0bae \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Sangam to Medieval Era",
        "year_start": -100,
        "year_end": 1100,
        "thinai": "neithal",
        "summary_en": "Epigraphic and archaeological records from Devipattinam documenting endowments by Pavazha-Chettiyar coral guilds and Mediterranean trade connections.",
        "summary_ta": "\u0ba4\u0bc7\u0bb5\u0bbf\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bc6\u0baf\u0bb2\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bb5\u0bb4\u0b9a\u0bcd \u0b9a\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0bbe\u0bb0\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bcb\u0bae \u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0b95\u0ba4\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Ramanathapuram Archaeological Studies",
            "Indo-Roman Coastal Trade"
        ],
        "content": "# Devipattinam Maritime Records: Coral Merchant Guilds & Roman Amphorae\n\n## Sheltered Lagoon Archaeology\nDevipattinam served as an ancient protected lagoon anchorage behind fringing coral reefs. Excavations recovered Mediterranean amphora shards.\n\n## Pavazha-Chettiyar Guild Endowments\nTemple inscriptions record corporate gifts of gold and coral bead strands made by the *Pavazha-Chettiyar* guild, confirming active gem merchant operations.",
        "chunks": [
            {
                "language": "en",
                "title": "Devipattinam Coral Merchant Guild Records",
                "content": "Epigraphs at Devipattinam document the Pavazha-Chettiyar coral jewelers guild alongside Roman trade artifacts."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bc7\u0bb5\u0bbf\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bae\u0bcd \u0baa\u0bb5\u0bb4 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0ba4\u0bc7\u0bb5\u0bbf\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0baf\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0bb5\u0bb4 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bcb\u0bae \u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0b95\u0ba4\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0ba4\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bb2\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-pamban-master-coral-diver-and-reef-navigator-pavazha-parathavar.md",
        "slug": "char-pamban-master-coral-diver-and-reef-navigator-pavazha-parathavar",
        "category": "character",
        "name_en": "Thathan Parathavan: Veteran Coral Diver & Shoal Pilot of Pamban Island",
        "name_ta": "\u0ba4\u0bbe\u0ba4\u0ba9\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0ba9\u0bcd - \u0baa\u0bbe\u0bae\u0bcd\u0baa\u0ba9\u0bcd \u0ba4\u0bc0\u0bb5\u0bc1 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0baa\u0bb5\u0bb4 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd",
        "era": "Sangam Era (c. 100 BCE \u2013 100 CE)",
        "year_start": -100,
        "year_end": 100,
        "thinai": "neithal",
        "summary_en": "Hereditary Parathavar seafaring navigator renowned for commanding coral diving fleets across the barrier shoals of Pamban passage.",
        "summary_ta": "\u0baa\u0bbe\u0bae\u0bcd\u0baa\u0ba9\u0bcd \u0b95\u0b9f\u0bb1\u0bcd\u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b86\u0baa\u0ba4\u0bcd\u0ba4\u0bbe\u0ba9 \u0baa\u0bb5\u0bb4\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbf \u0baa\u0bb5\u0bb4\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd.",
        "sources": [
            "Oral History of Pamban Fisherfolk",
            "Sangam Maritime Ethno-History"
        ],
        "content": "# Thathan Parathavan: Veteran Coral Diver & Shoal Pilot of Pamban Island\n\n## Navigational Genius of the Parathavar\nThathan Parathavan commanded the coral diving fleets of Pamban Island. Able to hold his breath at depth for two minutes, he located virgin underwater coral gardens.\n\n## Guild Leadership\nThathan regulated diving seasons, ensuring young divers harvested only mature branching colonies while protecting juvenile beds for future cycles.",
        "chunks": [
            {
                "language": "en",
                "title": "Thathan Parathavan Master Coral Diver Biography",
                "content": "Veteran diver Thathan Parathavan guided coral-diving catamarans across shallow reef channels around Pamban Island."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bbe\u0bae\u0bcd\u0baa\u0ba9\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd \u0ba4\u0bbe\u0ba4\u0ba9\u0bcd \u0baa\u0bb0\u0ba4\u0bb5\u0ba9\u0bcd",
                "content": "\u0baa\u0bbe\u0bae\u0bcd\u0baa\u0ba9\u0bcd \u0ba4\u0bc0\u0bb5\u0bbf\u0ba9\u0bcd \u0baa\u0bb5\u0bb4\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bb5\u0bb4\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0bbe\u0bb2\u0bc1\u0bae\u0bbf."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-korkai-royal-coral-gemmologist-and-stringer-pavazhak-kothon.md",
        "slug": "char-korkai-royal-coral-gemmologist-and-stringer-pavazhak-kothon",
        "category": "character",
        "name_en": "Silamban Kothon: Pandya Royal Coral Lapidary & Master Stringer",
        "name_ta": "\u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0ba9\u0bcd \u0b95\u0bcb\u0ba4\u0bcd\u0ba4\u0bcb\u0ba9\u0bcd - \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0b95\u0bcd \u0baa\u0bb5\u0bb4 \u0bae\u0ba3\u0bbf\u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd",
        "era": "Sangam Era (c. 50 BCE \u2013 150 CE)",
        "year_start": -50,
        "year_end": 150,
        "thinai": "neithal",
        "summary_en": "Pandya royal court lapidary in Korkai specialized in sizing, polishing, and stringing high-grade scarlet coral beads with pearls and gold wire.",
        "summary_ta": "\u0b95\u0bca\u0bb1\u0bcd\u0b95\u0bc8 \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b85\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1, \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b9f\u0ba9\u0bcd \u0b87\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0bb0\u0b9a \u0bae\u0bbe\u0bb2\u0bc8\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0ba8\u0b95\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd.",
        "sources": [
            "Korkai Excavation Memoirs",
            "Pandya Court Artisan Registers"
        ],
        "content": "# Silamban Kothon: Pandya Royal Coral Lapidary & Master Stringer\n\n## Royal Court Lapidary in Korkai\nOperating from the royal ateliers of Korkai, Silamban Kothon shaped freshly harvested coral branches into polished spherical and barrel beads.\n\n## Master Stringer (*Kothon*)\nSilamban assembled multi-strand ceremonial necklaces combining deep crimson corals with lustrous sea pearls for the crowns and deities of the Pandya kings.",
        "chunks": [
            {
                "language": "en",
                "title": "Silamban Kothon Royal Coral Lapidary of Korkai",
                "content": "Master gemmologist Silamban Kothon crafted exquisite coral and pearl jewelry in the Pandya royal court at Korkai."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0bb1\u0bcd\u0b95\u0bc8 \u0b85\u0bb0\u0b9a\u0bb5\u0bc8 \u0baa\u0bb5\u0bb4 \u0bae\u0ba3\u0bbf\u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0ba9\u0bcd",
                "content": "\u0b95\u0bca\u0bb1\u0bcd\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b85\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0b85\u0bb0\u0b9a \u0b85\u0ba3\u0bbf\u0b95\u0bb2\u0ba9\u0bcd\u0b95\u0bb3\u0bbe\u0b95 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0ba9\u0bcd \u0b95\u0bcb\u0ba4\u0bcd\u0ba4\u0bcb\u0ba9\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-pamban-ancient-coral-reef-haven-and-marine-gem-center.md",
        "slug": "place-pamban-ancient-coral-reef-haven-and-marine-gem-center",
        "category": "place",
        "name_en": "Pamban: Ancient Coral Reef Island Haven & Marine Gem Center",
        "name_ta": "\u0baa\u0bbe\u0bae\u0bcd\u0baa\u0ba9\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0baa\u0bb5\u0bb4\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bc8 \u0ba4\u0bc0\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0bae\u0ba3\u0bbf\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "neithal",
        "summary_en": "Strategic island reef passage between the Gulf of Mannar and Palk Bay famed for its vibrant shallow coral reefs and maritime gem commerce.",
        "summary_ta": "\u0bae\u0ba9\u0bcd\u0ba9\u0bbe\u0bb0\u0bcd \u0bb5\u0bb3\u0bc8\u0b95\u0bc1\u0b9f\u0bbe\u0bb5\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0ba9\u0bc8\u0baf\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0baa\u0bb5\u0bb4\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bc8\u0ba4\u0bcd \u0ba4\u0bc0\u0bb5\u0bc1.",
        "sources": [
            "Periplus of the Erythraean Sea",
            "Archaeology of the Pamban Passage"
        ],
        "content": "# Pamban: Ancient Coral Reef Island Haven & Marine Gem Center\n\n## Marine Topography & Strategic Passage\nPamban Island anchors the reef chain connecting southern India with Sri Lanka, sheltering prolific shallow coral beds in warm, nutrient-rich waters.\n\n## The Coral Fishery Haven\nProtected by outer shoals, Pamban provided a safe natural haven for coral diving fleets, serving as the commercial fulcrum where divers traded marine gems to visiting merchants.",
        "chunks": [
            {
                "language": "en",
                "title": "Pamban Island Coral Reef Haven Topography",
                "content": "Pamban Island was the central haven for coral divers and marine gem trade between the Gulf of Mannar and Palk Bay."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bbe\u0bae\u0bcd\u0baa\u0ba9\u0bcd \u0baa\u0bb5\u0bb4\u0baa\u0bcd\u0baa\u0bbe\u0bb1\u0bc8 \u0ba4\u0bc0\u0bb5\u0bc1 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0bae\u0ba9\u0bcd\u0ba9\u0bbe\u0bb0\u0bcd \u0bb5\u0bb3\u0bc8\u0b95\u0bc1\u0b9f\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0baa\u0bb5\u0bb4 \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bb2\u0bcd\u0b9a\u0bbe\u0bb0\u0bcd \u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bc0\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0bbe\u0bae\u0bcd\u0baa\u0ba9\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "char-pamban-master-coral-diver-and-reef-navigator-pavazha-parathavar",
        "located_in",
        "place-pamban-ancient-coral-reef-haven-and-marine-gem-center",
        "geography",
        "Sangam Era",
        "Navigated local reef passages and commanded diving crews at Pamban",
        "Akananuru littoral descriptions"
    ],
    [
        "char-korkai-royal-coral-gemmologist-and-stringer-pavazhak-kothon",
        "located_in",
        "place-pamban-ancient-coral-reef-haven-and-marine-gem-center",
        "commerce",
        "Sangam Era",
        "Procured freshly harvested coral branches from Pamban diving flotillas",
        "Korkai archaeological context"
    ],
    [
        "concept-coral-bead-perforation-and-quartz-micro-drill-lapidary",
        "practiced_by",
        "char-korkai-royal-coral-gemmologist-and-stringer-pavazhak-kothon",
        "craft",
        "Sangam Era",
        "Mastered micro-drilling of brittle coral beads using bow-drills and slurry",
        "Lapidary tool excavations"
    ],
    [
        "concept-submarine-reef-coral-harvesting-and-bamboo-pole-prying",
        "influenced",
        "concept-coral-bead-perforation-and-quartz-micro-drill-lapidary",
        "technology",
        "Sangam Era",
        "Supplied undamaged mature coral branches for micro-lapidary cutting",
        "Marine extraction records"
    ],
    [
        "concept-calcareous-coral-branch-seasoning-and-sandstone-abrasive-smoothing",
        "influenced",
        "concept-coral-bead-perforation-and-quartz-micro-drill-lapidary",
        "technology",
        "Sangam Era",
        "Sandstone grinding prepared smooth concentric bead blanks for drilling",
        "Lapidary analyses"
    ],
    [
        "concept-scarlet-coral-necklaces-pavazhamalai-and-chola-temple-donations",
        "related_to",
        "concept-coral-bead-perforation-and-quartz-micro-drill-lapidary",
        "adornment",
        "Sangam to Chola",
        "Perforated coral beads were strung into royal and temple necklaces",
        "Thanjavur Brihadisvara epigraphs"
    ],
    [
        "text-akanannuru-coral-reef-diving-and-fisherfolk-pearl-poetry",
        "references",
        "concept-submarine-reef-coral-harvesting-and-bamboo-pole-prying",
        "literature",
        "Sangam Era",
        "Poetically described Parathavar divers harvesting red coral on southern shores",
        "Akananuru littoral verses"
    ],
    [
        "insc-manamelkudi-pandyar-coral-fishery-and-marine-revenue-charters",
        "evidenced_by",
        "place-pamban-ancient-coral-reef-haven-and-marine-gem-center",
        "epigraphy",
        "Medieval Pandya",
        "Charters confirmed state tolls on boatloads of harvested marine coral",
        "Manamelkudi Epigraphs"
    ],
    [
        "insc-devipattinam-coastal-coral-merchant-and-amphora-epigraphs",
        "evidenced_by",
        "char-pamban-master-coral-diver-and-reef-navigator-pavazha-parathavar",
        "archaeology",
        "Early Historic",
        "Documented merchant guilds trading directly with coral diver flotillas",
        "Devipattinam excavation data"
    ],
    [
        "place-pamban-ancient-coral-reef-haven-and-marine-gem-center",
        "center_of",
        "concept-submarine-reef-coral-harvesting-and-bamboo-pole-prying",
        "geography",
        "Sangam Era",
        "Primary island launching center for diving fleets across Gulf of Mannar reefs",
        "Maritime geography records"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 26 Corpus 3: Coral Reef Diving, Submarine Extraction & Marine Gemmology into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 26 Corpus 3: Coral Reef Diving, Submarine Extraction & Marine Gemmology Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
