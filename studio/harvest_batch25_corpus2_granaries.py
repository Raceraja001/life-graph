#!/usr/bin/env python3
# Ingestion harvester for Batch 25 Corpus 2: Granary Engineering & Post-Harvest Aeration
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
        "file": "knowledge/texts/text-purananuru-towering-granaries-and-grain-security-poetry.md",
        "slug": "text-purananuru-towering-granaries-and-grain-security-poetry",
        "category": "text",
        "name_en": "Purananuru Verses on Towering Granaries, Agrarian Abundance & Grain Security",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd - \u0bb5\u0bbf\u0ba3\u0bcd\u0baa\u0bca\u0bb0\u0bc1 \u0ba8\u0bc6\u0b9f\u0bc1\u0bb5\u0bb0\u0bc8 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Purananuru 120 and 230 describing royal and village granaries (*Kalanjiyam* and *Kuthir*) towering like mountain peaks, filled with golden paddy that sustained kingdom populations through multi-year droughts and sieges.",
        "summary_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 120 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd 230-\u0b86\u0bae\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd: \u0bae\u0bb2\u0bc8 \u0baa\u0bcb\u0bb2\u0bcd \u0b89\u0baf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba8\u0bbf\u0ba9\u0bcd\u0bb1 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0baa\u0b9e\u0bcd\u0b9a\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0bae\u0b95\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b89\u0ba3\u0bb5\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb5\u0bbf\u0ba4\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Purananuru 120 (by Kapilar on Pari)",
            "Purananuru 230",
            "Perumpanarruppadai lines 240-255"
        ],
        "content": "# Purananuru Verses on Towering Granaries, Agrarian Abundance & Grain Security\n\n## The Granary as the Measure of Royal Power\nIn the agrarian civilizations of the Kaveri and Vaigai river valleys, true sovereignty was measured not in coins, but in overflowing granaries. Sangam bards across *Purananuru* celebrated the monumental granary towers (*Kalanjiyam*) that guaranteed civilizational continuity:\n\n```\n\"\u0bb5\u0bbf\u0ba3\u0bcd\u0baa\u0bca\u0bb0\u0bc1 \u0ba8\u0bc6\u0b9f\u0bc1\u0bb5\u0bb0\u0bc8 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bc1\n\u0b8e\u0ba3\u0bcd\u0ba4\u0bbf\u0b9a\u0bc8 \u0bae\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0ba9\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bbf\u0bb4\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bc1\n\u0bae\u0bb4\u0bc8\u0bb5\u0bb3\u0bae\u0bcd \u0baa\u0bbf\u0bb4\u0bc8\u0ba4\u0bcd\u0ba4 \u0b95\u0bbe\u0bb2\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd\n\u0b95\u0bc1\u0bb1\u0bc8\u0bb5\u0bbf\u0bb2\u0bbe \u0ba8\u0bb2\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0b9f\u0bc8...\"\n\u2014 \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 120:5-8\n```\n\nKapilar's verses describe granaries resembling sky-piercing mountains, capable of disgorging grain to feed the citizenry even when the seasonal monsoon rains failed completely.\n\n## The Triad of Grain Storage Systems\nSangam literature distinguishes three tiers of post-harvest grain architecture:\n1. **Perum-Kalanjiyam (\u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bae\u0bcd)**: Massive multi-bay timber and brick granary compounds managed by state and temple authorities.\n2. **Pathayam (\u0baa\u0ba4\u0bbe\u0baf\u0bae\u0bcd)**: Subterranean masonry or clay-sealed pits excavated in dry marl soils, keeping seeds dormant for decades.\n3. **Nel-Kuthir (\u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd)**: Immense vertical earthenware or woven bamboo cylinders standing in courtyard verandas for domestic subsistence.",
        "chunks": [
            {
                "language": "en",
                "title": "Purananuru Granary Architecture & State Grain Security",
                "content": "Purananuru verses celebrate monumental granaries (Kalanjiyam) towering like mountains in Chola and Pandya capitals, designed to store golden paddy to safeguard kingdoms through extended drought cycles."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0bb5\u0bbe\u0ba9\u0bc1\u0baf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd",
                "content": "\u0bb5\u0bbf\u0ba3\u0bcd\u0baa\u0bca\u0bb0\u0bc1 \u0ba8\u0bc6\u0b9f\u0bc1\u0bb5\u0bb0\u0bc8 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0b9e\u0bcd\u0b9a\u0bae\u0bcd \u0bb5\u0ba8\u0bcd\u0ba4 \u0b95\u0bbe\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0baa\u0bb2\u0bcd\u0bb2\u0bbe\u0baf\u0bbf\u0bb0\u0b95\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0bae\u0b95\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b89\u0ba3\u0bb5\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0bb0\u0b9a \u0bb5\u0bb2\u0bbf\u0bae\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b85\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf\u0ba4\u0bc8 \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 \u0baa\u0bbe\u0b9f\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-subterranean-clay-lined-grain-storage-silos-pathayam-and-kuzhi.md",
        "slug": "concept-subterranean-clay-lined-grain-storage-silos-pathayam-and-kuzhi",
        "category": "concept",
        "name_en": "Subterranean Clay-Lined Grain Storage Silos (Pathayam & Kuzhi)",
        "name_ta": "\u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0baa\u0bc2\u0b9a\u0bbf\u0baf \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0ba4\u0bbe\u0b95\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Underground airtight grain storage pit engineering (*Pathayam* / *Nel-Kuzhi*), featuring straw-insulated red clay linings, fire-sterilized pit walls, and hermetic mud seals that deplete oxygen to eliminate grain weevils and maintain seed germination viability.",
        "summary_ta": "\u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b9a\u0bc1\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1, \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bcb\u0bb2\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bbe \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0bae\u0bc2\u0b9f\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b86\u0b95\u0bcd\u0bb8\u0bbf\u0b9c\u0ba9\u0bc8 \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf \u0bb5\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0baa\u0bb2 \u0b86\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0ba4\u0bbe\u0b95\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Excavations at Tirukkampuliyur and Alagarai Granary Layers",
            "Akananuru 37",
            "Traditional Hermetic Grain Storage in South Asia"
        ],
        "content": "# Subterranean Clay-Lined Grain Storage Silos (Pathayam & Kuzhi)\n\n## The Physics of Hermetic Underground Storage\nTo safeguard grain against predatory rodents, bird flocks, moisture rot, and fungal molds, ancient Tamil farmers excavated bottle-shaped subterranean pits known as *Nel-Kuzhi* or *Pathayam*:\n\n$$\\text{Living Grain + Insects} \\xrightarrow{\\text{Sealed Pit}} \\text{Consume Remaining } O_2 \\rightarrow \\text{High } CO_2 \\rightarrow \\text{Anoxia (Pest Asphyxiation)}$$\n\n## Construction Sequence of the Ancient Pathayam\n1. **Site Selection**: Excavating into hard, impervious laterite or dry clay subsoils elevated above seasonal groundwater tables.\n2. **Thermal Sterilization**: Filling the freshly dug pit with dry brushwood and burning it for 24 hours to bake the interior earth walls brick-hard, exterminating subterranean termites and fungal spores.\n3. **Straw & Chaff Insulation (*Vaikkol-Kaaval*)**: Lining the floor and perimeter walls with a 10 cm layer of sun-dried paddy straw (*Vaikkol*) and roasted rice husks (*Umi*) that absorbed residual soil humidity.\n4. **Hermetic Sealing**: Once filled to the brim with clean grain, the narrow neck was sealed with flat stone slabs (*Kal-Thattu*) luted with moist red clay and cow-dung plaster, locking the chamber in airtight isolation for up to five years.",
        "chunks": [
            {
                "language": "en",
                "title": "Hermetic Subterranean Pathayam Silo Engineering & Anoxia Pest Control",
                "content": "Tamil farmers engineered subterranean bottle-shaped pits (Pathayam) lined with fire-baked clay and paddy straw, hermetically sealing grain so that natural respiration depleted oxygen and asphyxiated weevils."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0ba4\u0bbe\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0b95\u0bcd\u0bb8\u0bbf\u0b9c\u0ba9\u0bcd \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0b9a\u0bc1\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bcb\u0bb2\u0bcd \u0baa\u0bb0\u0baa\u0bcd\u0baa\u0bbf \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb0\u0baa\u0bcd\u0baa\u0bbf \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0bae\u0bc2\u0b9f\u0bc1\u0bb5\u0ba4\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd, \u0ba4\u0bbe\u0ba9\u0bbf\u0baf \u0bb5\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8\u0baf\u0bbe\u0b95 \u0b85\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0baa\u0ba4\u0bbe\u0b95\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-elevated-timber-slatted-aerated-granary-architecture-kalanjiyam.md",
        "slug": "concept-elevated-timber-slatted-aerated-granary-architecture-kalanjiyam",
        "category": "concept",
        "name_en": "Elevated Timber-Slatted Aerated Granary Architecture (Kalanjiyam)",
        "name_ta": "\u0bae\u0bc7\u0b9f\u0bc8 \u0b89\u0baf\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0bae\u0bb0\u0b9a\u0bcd\u0b9a\u0b9f\u0bcd\u0b9f \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bcb\u0b9f\u0bcd\u0b9f \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd\u0b95\u0bb2\u0bc8",
        "era": "Early Historic to Chola Era",
        "year_start": -300,
        "year_end": 600,
        "thinai": "marutham",
        "summary_en": "Architectural engineering of monumental above-ground granary buildings (*Kalanjiyam*) erected on stone stilts with slatted teak or vengai planking, cross-ventilation louvers, and rat-guard stone discs to preserve paddy stocks against dampness.",
        "summary_ta": "\u0ba4\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0b95\u0bb2\u0bcd \u0ba4\u0bc2\u0ba3\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0b89\u0baf\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0b8e\u0bb2\u0bbf\u0b95\u0bb3\u0bcd \u0b8f\u0bb1\u0bbe\u0ba4 \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bcb\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Purananuru 230",
            "Mayamata Chapter 29 (Grain Warehouses)",
            "Structural Surveys of Chola Temple Granaries at Thiruvanaikoil"
        ],
        "content": "# Elevated Timber-Slatted Aerated Granary Architecture (Kalanjiyam)\n\n## The Microclimate Challenge of Tropical Humidity\nIn the humid river valleys of the Kaveri delta, moisture accumulation in bulk-stored grain causes \"sweating,\" spontaneous combustion from microbial heat, and Aspergillus mold blooms. Monumental grain architecture demanded passive thermodynamic aeration.\n\n## Architectural Elements of the Classical Kalanjiyam\n1. **Basal Elevation (*Kal-Thoon*)**: The entire granary floor was raised 1 to 1.5 meters above ground on monolithic stone pillars, isolating timber floors from groundwater capillary draw.\n2. **Rodent Baffles (*Eli-Thadukku*)**: Inverted conical stone collars fitted around the top of each pillar, creating an impassable physical barrier to climbing rats.\n3. **Slatted Hardwood Floorboards**: Floor planks of seasoned *Vengai* or *Teak* were laid with 3 mm inter-plank gaps, permitting upward ambient airflow while supporting hundreds of tons of grain.\n4. **Cross-Draft Gable Louvers**: High triangular gables featured louvered timber grilles angled to block driving monsoon rains while drawing rising warm air outward through thermal chimney convection.",
        "chunks": [
            {
                "language": "en",
                "title": "Elevated Aerated Kalanjiyam Architecture & Rodent Baffles",
                "content": "Monumental Tamil granaries (Kalanjiyam) stood elevated on stone pillars equipped with inverted rodent-guard discs, featuring slatted hardwood floors and louvered gables that induced passive convection currents."
            },
            {
                "language": "ta",
                "title": "\u0b89\u0baf\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0bae\u0bc7\u0b9f\u0bc8 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bae\u0bc1\u0bae\u0bcd \u0b8e\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb2\u0bc1\u0bae\u0bcd",
                "content": "\u0b95\u0bb2\u0bcd \u0ba4\u0bc2\u0ba3\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0b8e\u0bb2\u0bbf \u0b8f\u0bb1\u0bbe\u0ba4 \u0bb5\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb2\u0b95\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bc8\u0b95\u0bcd \u0b95\u0bc6\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-neem-leaf-turmeric-and-wood-ash-entomological-pest-repellents.md",
        "slug": "concept-neem-leaf-turmeric-and-wood-ash-entomological-pest-repellents",
        "category": "concept",
        "name_en": "Neem Leaf, Turmeric & Wood Ash Entomological Pest-Repellent Systems",
        "name_ta": "\u0bb5\u0bc7\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bc8, \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b9a\u0bcd\u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bb2\u0bcd \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf\u0bb5\u0bbf\u0bb0\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Indigenous botanical and mineral post-harvest preservation practices interstratifying sun-dried neem leaves (Azadirachta indica / Veppilai), wild turmeric rhizome dust, and sieved alkaline wood ash into stored grain to disrupt insect cuticle lipids.",
        "summary_ta": "\u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b9a\u0bc7\u0bae\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0ba4\u0bc1 \u0bb5\u0bc7\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bc8, \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0baa\u0bca\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b9a\u0bcd\u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bb2\u0bc8 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bbe\u0b95 \u0b87\u0b9f\u0bcd\u0b9f\u0bc1, \u0bb5\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb1\u0bbf\u0b9e\u0bcd\u0b9a\u0bbf \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf\u0b95\u0bb3\u0bc8 \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8\u0baf\u0bbe\u0b95 \u0bb5\u0bbf\u0bb0\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb0\u0bbe\u0bb5\u0bbf\u0b9f \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Sirupanarruppadai lines 140-150",
            "Tolkappiyam Porulatikaram 648",
            "Journal of Stored Products Research & Traditional Botanicals"
        ],
        "content": "# Neem Leaf, Turmeric & Wood Ash Entomological Pest-Repellent Systems\n\n## Botanical-Mineral Interstratification\nAncient Tamil agriculturists practiced chemical-free entomological control based on deep empirical observation of pest ecology (*Poochi-Kadamai*):\n\n- **Azadirachtin Action of Neem (*Veppilai*)**: Sun-dried bitter neem leaves were layered every 30 cm through the grain column. Volatile azadirachtins and meliantriol compounds acted as powerful antifeedants and insect growth regulators, sterilizing female grain borers (*Rhyzopertha dominica*).\n- **Curcumin Antifungal Barrier**: Pulverized wild turmeric (*Kasturi Manjal*) dusted over grain grains created a protective curcuminoid envelope that prevented spore germination of storage fungi (*Aspergillus* and *Penicillium*).\n- **Mechanical Desiccation by Wood Ash (*Saambal-Kaval*)**: Sifted alkaline hardwood ash was mixed directly into the top layer of grain. Fine silica crystals in the ash scratched the epicuticular wax layer of insect exoskeletons, causing moisture loss and fatal desiccation within 48 hours.",
        "chunks": [
            {
                "language": "en",
                "title": "Neem, Turmeric & Wood Ash Botanical Grain Preservation",
                "content": "Ancient Tamil granary keepers layered sun-dried neem leaves, turmeric dust, and alkaline wood ash between grain strata, combining azadirachtin insect repellency with desiccant ash to eliminate storage pests."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bc7\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b9a\u0bcd\u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bb2\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc7\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0baa\u0bca\u0b9f\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bb2\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0bb5\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0ba4\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf\u0b95\u0bb3\u0bcd \u0b85\u0ba3\u0bc1\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-monsoon-humidity-barrier-and-woven-bamboo-silo-linings.md",
        "slug": "concept-monsoon-humidity-barrier-and-woven-bamboo-silo-linings",
        "category": "concept",
        "name_en": "Monsoon Humidity Barrier & Woven Bamboo Silo Linings (Kuthir)",
        "name_ta": "\u0baa\u0bb0\u0bc1\u0bb5\u0bae\u0bb4\u0bc8 \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Early Historic Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Composite material engineering of household and communal grain bins (*Nel-Kuthir*), utilizing woven bamboo lattice cylinders plastered internally with cow dung, red clay, and rice husk chaff to create a breathing, moisture-buffering envelope.",
        "summary_ta": "\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bc0\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0baa\u0bbf\u0ba9\u0bcd\u0ba9\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bbf\u0bb5\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0b9a\u0bc6\u0bae\u0bcd\u0bae\u0ba3\u0bcd, \u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0ba3\u0bae\u0bcd, \u0b89\u0bae\u0bbf \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bc2\u0b9a\u0bbf, \u0baa\u0bb0\u0bc1\u0bb5\u0bae\u0bb4\u0bc8 \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb3\u0bcd\u0bb3\u0bc7 \u0bb5\u0bbf\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bbf\u0baf \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Nedunalvadai lines 120-135",
            "Excavations at Tirukkampuliyur Ceramic Layers",
            "Ethnoarchaeology of Vernacular Storage Structures in Tamil Nadu"
        ],
        "content": "# Monsoon Humidity Barrier & Woven Bamboo Silo Linings (Kuthir)\n\n## The Domestic Composite Silo (*Nel-Kuthir*)\nIn vernacular Tamil domestic architecture, the *Nel-Kuthir* (\u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd) was the central pantry fixture standing proudly on the inner veranda (*Thinnai*). These cylinders, ranging from 1 to 3 meters in height, represented a masterpiece of composite material engineering.\n\n## Composite Wall Stratigraphy\n1. **Tensile Framework**: A woven open-mesh basketry cylinder woven from green river bamboo (*Moongil-Keezhru*), providing hoop strength to resist outward hydrostatic grain pressure.\n2. **Plaster Formulation (*Mann-Kootu*)**: The lattice was plastered inside and out with a bio-composite mortar consisting of:\n   - High-plasticity red loam (*Semmann*) providing structural mass.\n   - Fresh cow dung (*Pasum-Saanam*) delivering microscopic cellulose fibers and anaerobic bacterial enzymes that inhibited fungal growth.\n   - Roasted paddy husk (*Umi-chambal*) acting as a lightweight thermal insulator.\n3. **Breathing Moisture Equilibrium**: The clay-dung membrane absorbed ambient humidity during wet nights and desorbed it during sunny afternoons, maintaining a dry, stable core microclimate ($< 13\\%\\text{ grain moisture}$).",
        "chunks": [
            {
                "language": "en",
                "title": "Woven Bamboo Nel-Kuthir Composite Plaster Engineering",
                "content": "Vernacular Tamil Nel-Kuthir storage silos combined woven bamboo lattices with red clay, cow dung, and rice husk chaff plasters, creating a dynamic moisture-buffering membrane that protected paddy during monsoon humidity."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0bc1\u0bb5\u0bae\u0bb4\u0bc8 \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0b9a\u0bbe\u0ba3\u0bae\u0bcd, \u0b9a\u0bc6\u0bae\u0bcd\u0bae\u0ba3\u0bcd, \u0b89\u0bae\u0bbf \u0b95\u0bb2\u0ba8\u0bcd\u0ba4 \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf\u0ba9\u0bc8 \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0b95\u0bb3\u0bcd, \u0baa\u0bb0\u0bc1\u0bb5\u0bae\u0bb4\u0bc8\u0b95\u0bcd\u0b95\u0bbe\u0bb2 \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb3\u0bcd\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb2\u0bb0\u0bcd\u0bb5\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0bbe\u0ba4\u0bcd\u0ba4\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-tirukkampuliyur-kaveri-delta-royal-granary-endowments.md",
        "slug": "insc-tirukkampuliyur-kaveri-delta-royal-granary-endowments",
        "category": "inscription",
        "name_en": "Tirukkampuliyur Kaveri Delta Royal Granary Endowments",
        "name_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd \u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe \u0b85\u0bb0\u0b9a \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -100,
        "year_end": 1000,
        "thinai": "marutham",
        "summary_en": "Archaeological excavations and temple epigraphs from Tirukkampuliyur on the Kaveri banks, unearthing Sangam-era circular granary brick foundations, grain storage jars, and imperial inscriptions documenting paddy endowment reserves (*Nel-Mudhal*).",
        "summary_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bb1\u0bbf\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0bb5\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bbf\u0bb5 \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf \u0b85\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0ba9\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf \u0b87\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Excavations at Tirukkampuliyur by Madras University 1962",
            "South Indian Inscriptions Vol. XVII",
            "Archaeological Survey of India Memoir No. 78"
        ],
        "content": "# Tirukkampuliyur Kaveri Delta Royal Granary Endowments\n\n## Archaeological Discovery on the Kaveri Banks\nTirukkampuliyur, situated on the southern bank of the Kaveri in Karur/Tiruchirappalli district ($10.9500^\\circ\\text{ N}, 78.4100^\\circ\\text{ E}$), was a major Early Historic agrarian emporium. Pioneering excavations by the University of Madras revealed continuous habitation spanning from the Megalithic period through the imperial Chola era.\n\n## Granary Architecture Unearthed\nExcavation trenches in Period II (Sangam-Early Historic) exposed:\n- **Circular Brick Silo Foundations**: Circular platforms of kiln-fired bricks ($40\\times20\\times7\\text{ cm}$) laid in concentric courses, interpreted as the bases of monumental public granaries (*Kalanjiyam*).\n- **Carbonized Grain Deposits**: Substantial deposits of carbonized paddy (*Oryza sativa*), pearl millet (*Kambu*), and green gram (*Pasi-payaru*) discovered inside subterranean storage pits.\n- **Inscribed Stone Epigraphs**: Chola inscriptions recording royal allocations of thousands of *kalams* of paddy stored as permanent disaster insurance reserves (*Aabathuk-Kaalam Nel-Mudhal*).",
        "chunks": [
            {
                "language": "en",
                "title": "Tirukkampuliyur Excavated Brick Granary Foundations & Carbonized Grain",
                "content": "Excavations at Tirukkampuliyur on the Kaveri revealed Sangam-era circular brick granary foundations and carbonized paddy pits alongside Chola epigraphs establishing royal grain reserves for famine relief."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bc1 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0bb5\u0b9f\u0bcd\u0b9f \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf \u0b85\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc1\u0b95\u0bbf\u0baf \u0ba8\u0bc6\u0bb2\u0bcd\u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8 \u0bae\u0bc6\u0baf\u0bcd\u0baa\u0bcd\u0baa\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-alagarai-chola-paddy-reserve-and-flood-relief-charters.md",
        "slug": "insc-alagarai-chola-paddy-reserve-and-flood-relief-charters",
        "category": "inscription",
        "name_en": "Alagarai Chola Paddy Reserve & Flood Relief Charters",
        "name_ta": "\u0b85\u0bb4\u0b95\u0bb0\u0bc8 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf \u0b87\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3 \u0ba8\u0bbf\u0bb5\u0bbe\u0bb0\u0ba3 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Medieval Era",
        "year_start": 850,
        "year_end": 1150,
        "thinai": "marutham",
        "summary_en": "Stone inscriptions from Alagarai on the northern bank of the Kaveri documenting state granary management, grain lending systems (*Nel-Kadan*) with controlled interest, and emergency paddy disbursement during monsoonal flood breaches.",
        "summary_ta": "\u0b85\u0bb4\u0b95\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd \u0baa\u0bcb\u0ba4\u0bc1 \u0b85\u0bb0\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bca\u0ba4\u0bc1\u0bae\u0b95\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bbf\u0bb5\u0bbe\u0bb0\u0ba3 \u0ba8\u0bc6\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0bb5\u0b9f\u0bcd\u0b9f\u0bbf \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0b9f\u0ba9\u0bcd \u0ba8\u0bc6\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9.",
        "sources": [
            "South Indian Inscriptions Vol. XIX",
            "Annual Report on Indian Epigraphy 1963-64 No. 278",
            "Excavations at Alagarai Site Report"
        ],
        "content": "# Alagarai Chola Paddy Reserve & Flood Relief Charters\n\n## The Agrarian Bastion of Alagarai\nDirectly opposite Tirukkampuliyur across the Kaveri River lies Alagarai, an ancient riverport and granary stronghold. The site yielded Megalithic Black-and-Red ware and extensive Chola architectural remains.\n\n## Epigraphic Inscriptions on Granary Administration\nStone charters from the Alagarai temples document:\n- **State Famine Reserves (*Pancha-Kaala Nel-Vaippu*)**: Mandatory quotas requiring every agricultural township (*Brahmadeya* and *Ur*) to deposit 5% of gross harvest into communal granaries managed under seal.\n- **Flood Relief Protocols**: Decrees mandating the opening of royal granaries during Kaveri embankment breaches (*Aatrup-Perukku*), distributing seed grain (*Vithai-Nel*) to displaced cultivators.\n- **Grain Metrology Audits**: Strict punishment for custodians using false wooden measures (*Kallak-Kuruni*), standardizing official royal measures (*Rajarajan-Marakkal*).",
        "chunks": [
            {
                "language": "en",
                "title": "Alagarai Chola Granary Inscriptions & Famine Relief Protocols",
                "content": "Chola temple inscriptions at Alagarai document state granary reserves, emergency flood disbursements of seed paddy, and mandatory audits of official volumetric grain measures."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb4\u0b95\u0bb0\u0bc8 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3 \u0ba8\u0bbf\u0bb5\u0bbe\u0bb0\u0ba3 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0b85\u0bb4\u0b95\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd \u0baa\u0bcb\u0ba4\u0bc1 \u0bb5\u0bbf\u0bb5\u0b9a\u0bbe\u0baf\u0bbf\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bbf\u0ba4\u0bc8\u0ba8\u0bc6\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0baa\u0bcd\u0baa\u0bc2\u0bb0\u0bcd\u0bb5 \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0b85\u0bb3\u0bb5\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc6\u0bb1\u0bbf\u0b95\u0bb3\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-tirukkampuliyur-master-granary-architect-kalanchiya-sirpachari.md",
        "slug": "char-tirukkampuliyur-master-granary-architect-kalanchiya-sirpachari",
        "category": "character",
        "name_en": "Tirukkampuliyur Master Granary Architect Kalanchiya Sirpachari",
        "name_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Persona representing the hereditary master architect specializing in agrarian warehouse engineering, calculating granary load capacities, damp-proof foundations, and rodent-guard masonry in the Kaveri delta.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf\u0baa\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b86\u0baf\u0bbf\u0bb0\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b95\u0bb2\u0bae\u0bcd \u0ba8\u0bc6\u0bb2\u0bcd\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0bae\u0bcd \u0baa\u0bc1\u0b95\u0bbe \u0bae\u0bc7\u0b9f\u0bc8 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0b8e\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0ba9\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf.",
        "sources": [
            "Purananuru 230",
            "Mayamata Vastu Shastra Chapters 28-30",
            "Excavations at Tirukkampuliyur Architecture"
        ],
        "content": "# Tirukkampuliyur Master Granary Architect Kalanchiya Sirpachari\n\n## Guild Lineage & Agrarian Engineering\nOperating along the fertile agricultural corridor between Karur and Uraiyur, the *Kalanchiya Sirpachari* commanded the building guilds dedicated to state food security. His authority governed timber selection, subterranean pit physics, and thermal ventilation.\n\n## Architectural Mastery\n1. **Soil Resonance Testing**: Striking iron crowbars into subsoil to detect subterranean moisture veins, ensuring grain pits were never sunk in water-seeping strata.\n2. **Stone Pillar Geometry**: Carving monolithic granite pillars with polished cylindrical necks that prevented rodent claws from gaining traction.\n3. **Timber Framing Precision**: Mortising Vengai and Teak beams to support floor loads exceeding 500 tons of bulk grain without sagging or cracking lateral brick walls.",
        "chunks": [
            {
                "language": "en",
                "title": "Master Granary Architect Engineering & Load Calculations",
                "content": "The Tirukkampuliyur master granary architect engineered high-capacity timber warehouses with polished stone rodent baffles and subterranean moisture testing to safeguard bulk grain stocks."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf",
                "content": "\u0bae\u0ba3\u0bcd\u0ba3\u0bbf\u0ba9\u0bcd \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0bae\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0ba4\u0bbe\u0b95\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b8e\u0bb2\u0bbf \u0b8f\u0bb1\u0bbe\u0ba4 \u0bb5\u0bb4\u0bc1\u0bb5\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bcd \u0ba4\u0bc2\u0ba3\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-kaveri-delta-grain-custodian-and-metrologist-kanakka-nayagam.md",
        "slug": "char-kaveri-delta-grain-custodian-and-metrologist-kanakka-nayagam",
        "category": "character",
        "name_en": "Kaveri Delta Grain Custodian & Metrologist Kanakka Nayagam",
        "name_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95 \u0ba8\u0bbe\u0baf\u0b95\u0bae\u0bcd",
        "era": "Sangam to Chola Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Persona portraying the elite royal grain accountant and metrological auditor supervising official paddy measures (Marakkal / Kalam), managing warehouse ledgers on palm leaves, and verifying grain moisture before storage.",
        "summary_ta": "\u0b85\u0bb0\u0b9a \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0baa\u0bcd\u0baa\u0bc2\u0bb0\u0bcd\u0bb5 \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bc8 \u0b85\u0bb3\u0ba8\u0bcd\u0ba4\u0bc1, \u0b93\u0bb2\u0bc8\u0b9a\u0bcd\u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bb5\u0bc1-\u0b9a\u0bc6\u0bb2\u0bb5\u0bc1 \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bc6\u0bb4\u0bc1\u0ba4\u0bbf, \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0baa\u0bcd \u0baa\u0bb0\u0bbf\u0b9a\u0bcb\u0ba4\u0ba9\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bb0\u0bcd.",
        "sources": [
            "Purananuru 386",
            "Tolkappiyam Porulatikaram Purathinaiyiyal",
            "Chola Inscriptions on Nel-Kanakku"
        ],
        "content": "# Kaveri Delta Grain Custodian & Metrologist Kanakka Nayagam\n\n## The Integrity of the Royal Grain Measure\nThe *Kanakka Nayagam* was the royal officer responsible for the physical and mathematical integrity of imperial grain reserves. Operating out of the great granary complexes along the Kaveri, he was the final arbiter of quality and volume.\n\n## Daily Operations & Quality Audits\n- **Bite & Snap Moisture Test (*Kadithu-Paarthal*)**: Biting raw paddy grains; if the kernel snapped cleanly with a sharp acoustic crack without flaking, grain moisture was verified below 13% for safe long-term silo storage.\n- **Volumetric Standardization**: Certifying the official bronze-banded wooden *Marakkal* and *Kalam* measures bearing the royal tiger or fish emblem, ensuring fair assessment of agricultural taxes.\n- **Pest Inspection**: Inspecting storage silos weekly, monitoring the aroma of ventilation flues; the faintest vinegar scent of souring grain triggered immediate re-aeration and sun-drying.",
        "chunks": [
            {
                "language": "en",
                "title": "Royal Grain Custodian Metrological Audits & Moisture Testing",
                "content": "The Kaveri grain custodian conducted acoustic bite tests to verify seed moisture below 13%, enforced standardized bronze-banded volumetric measures, and monitored silo ventilation against souring."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95 \u0ba8\u0bbe\u0baf\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0baa\u0ba3\u0bbf\u0b95\u0bb3\u0bcd",
                "content": "\u0ba8\u0bc6\u0bb2\u0bcd\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1, \u0b85\u0bb0\u0b9a \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b85\u0bb3\u0ba8\u0bcd\u0ba4\u0bc1, \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf \u0b87\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc8 \u0b93\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b86\u0bb5\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-tirukkampuliyur-ancient-granary-and-agrarian-haven.md",
        "slug": "place-tirukkampuliyur-ancient-granary-and-agrarian-haven",
        "category": "place",
        "name_en": "Tirukkampuliyur: Ancient Granary, Brick Silo & Agrarian Haven",
        "name_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0b95\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Iron Age to Medieval Era",
        "year_start": -400,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Major Early Historic agrarian riverport settlement on the southern bank of the Kaveri, famed for circular brick granary foundations, deep subterranean grain pits, and continuous role in regional grain reserves.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b86\u0bb1\u0bcd\u0bb1\u0bbf\u0ba9\u0bcd \u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1\u0bb1\u0bc8 \u0ba4\u0bb3\u0bae\u0bcd, \u0bb5\u0b9f\u0bcd\u0b9f \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0b86\u0bb4\u0bae\u0bbe\u0ba9 \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0ba4\u0bbe\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc8\u0baf\u0bae\u0bcd.",
        "sources": [
            "Excavations at Tirukkampuliyur Monograph",
            "Purananuru 230",
            "Archaeological Survey of India River Valley Surveys"
        ],
        "content": "# Tirukkampuliyur: Ancient Granary, Brick Silo & Agrarian Haven\n\n## Riverine Topography on the Central Kaveri\nTirukkampuliyur ($10.9500^\\circ\\text{ N}, 78.4100^\\circ\\text{ E}$) occupies a broad, naturally elevated silt terrace directly on the Kaveri River. This position allowed barge transport of bulk grains downriver to Uraiyur and Poompuhar, while natural river drainage kept the terrace dry during monsoon floods.\n\n## Archaeological Stratigraphy of the Granary Haven\nExcavations revealed three successive cultural periods spanning 1,500 years:\n- **Megalithic Black-and-Red Ware Layer**: Deep underground grain storage pits containing carbonized millets and rice husks.\n- **Sangam Brick Granaries**: Substantial circular platforms constructed of heavy fired bricks ($40\\times20\\times7\\text{ cm}$), complete with central wooden post-holes for supporting conical thatch roofs.\n- **Chola Warehouses**: Paved rectangular brick warehouse foundations with surrounding storm-drain gutters and iron key sets from grain padlocks.\n\n## Civilizational Role\nTirukkampuliyur stood as the agrarian granary anchor of the central Kaveri delta, accumulating surplus harvests from surrounding wetland *Nanjai* fields and disbursing grain to sustain armies, craftsmen, and temple academies.",
        "chunks": [
            {
                "language": "en",
                "title": "Tirukkampuliyur Central Kaveri Granary Haven Topography",
                "content": "Situated on an elevated silt terrace of the Kaveri, ancient Tirukkampuliyur served as the primary bulk grain collection and storage center for the central Chola kingdom, evidenced by stratified circular brick silos."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
                "content": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf\u0b95\u0bcd \u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0bae\u0bc7\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bcd\u0baa\u0bc1\u0bb2\u0bbf\u0baf\u0bc2\u0bb0\u0bcd, \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba9\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0ba4\u0bbe\u0b95\u0bc8\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b9a\u0bcb\u0bb4 \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0ba8\u0bc6\u0bb1\u0bcd\u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf \u0bae\u0bc8\u0baf\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb2\u0bae\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "text-purananuru-towering-granaries-and-grain-security-poetry",
        "describes_granary_architecture",
        "concept-elevated-timber-slatted-aerated-granary-architecture-kalanjiyam",
        "cultural",
        "Sangam Classical Era",
        "Purananuru poetry celebrates the towering mountain-like Kalanjiyam granaries.",
        "Purananuru 120"
    ],
    [
        "text-purananuru-towering-granaries-and-grain-security-poetry",
        "attests_subterranean_storage",
        "concept-subterranean-clay-lined-grain-storage-silos-pathayam-and-kuzhi",
        "agricultural",
        "Sangam Classical Era",
        "Verses detail deep underground grain silos holding harvests through multi-year droughts.",
        "Purananuru 230"
    ],
    [
        "concept-subterranean-clay-lined-grain-storage-silos-pathayam-and-kuzhi",
        "excavated_at_haven",
        "place-tirukkampuliyur-ancient-granary-and-agrarian-haven",
        "archaeological",
        "Iron Age to Sangam Era",
        "Excavations at Tirukkampuliyur revealed subterranean grain storage pits.",
        "Excavations at Tirukkampuliyur Reports"
    ],
    [
        "concept-elevated-timber-slatted-aerated-granary-architecture-kalanjiyam",
        "designed_by",
        "char-tirukkampuliyur-master-granary-architect-kalanchiya-sirpachari",
        "architectural",
        "Early Historic Era",
        "Master granary architects engineered the elevated timber-slatted granaries.",
        "Mayamata Chapter 29"
    ],
    [
        "concept-neem-leaf-turmeric-and-wood-ash-entomological-pest-repellents",
        "applied_in_storage",
        "concept-monsoon-humidity-barrier-and-woven-bamboo-silo-linings",
        "agricultural",
        "Iron Age to Sangam Era",
        "Neem and wood ash were dusted inside woven bamboo Kuthir silos.",
        "Sirupanarruppadai lines 140-150"
    ],
    [
        "concept-monsoon-humidity-barrier-and-woven-bamboo-silo-linings",
        "monitored_by_custodian",
        "char-kaveri-delta-grain-custodian-and-metrologist-kanakka-nayagam",
        "administrative",
        "Sangam Classical Era",
        "Grain custodians audited the moisture levels inside domestic Kuthir silos.",
        "Nedunalvadai lines 120-135"
    ],
    [
        "insc-tirukkampuliyur-kaveri-delta-royal-granary-endowments",
        "inscribed_at",
        "place-tirukkampuliyur-ancient-granary-and-agrarian-haven",
        "epigraphical",
        "Early Historic Era",
        "Epigraphs at Tirukkampuliyur record royal paddy storage reserves.",
        "South Indian Inscriptions Vol. XVII"
    ],
    [
        "insc-alagarai-chola-paddy-reserve-and-flood-relief-charters",
        "documents_famine_relief",
        "place-tirukkampuliyur-ancient-granary-and-agrarian-haven",
        "epigraphical",
        "Early Medieval Era",
        "Alagarai charters detail cross-river flood relief granary operations.",
        "South Indian Inscriptions Vol. XIX"
    ],
    [
        "char-tirukkampuliyur-master-granary-architect-kalanchiya-sirpachari",
        "headquartered_at",
        "place-tirukkampuliyur-ancient-granary-and-agrarian-haven",
        "guild_membership",
        "Sangam Classical Era",
        "The master granary architect operated his building guilds at Tirukkampuliyur.",
        "Architectural Inscription Records"
    ],
    [
        "char-kaveri-delta-grain-custodian-and-metrologist-kanakka-nayagam",
        "collaborates_with",
        "char-tirukkampuliyur-master-granary-architect-kalanchiya-sirpachari",
        "administrative",
        "Sangam Classical Era",
        "Grain accountants collaborated with architects to verify volumetric capacities.",
        "Chola Administrative Registers"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 25 Corpus 2: Granary Engineering & Post-Harvest Aeration into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 25 Corpus 2: Granary Engineering & Post-Harvest Aeration Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
