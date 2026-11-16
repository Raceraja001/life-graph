#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Teak & Rosewood Joinery, Mortise-Tenon Woodworking & Royal Palaces
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
        "file": "knowledge/texts/text-nedunalvadai-verses-on-sandalwood-pillars-and-mortised-palace-rafters.md",
        "slug": "text-nedunalvadai-verses-on-sandalwood-pillars-and-mortised-palace-rafters",
        "category": "text",
        "name_en": "Nedunalvadai: Classical Sangam Verses on Mortised Palace Rafters & Sandalwood Pillars",
        "name_ta": "\u0ba8\u0bc6\u0b9f\u0bc1\u0ba8\u0bb2\u0bcd\u0bb5\u0bbe\u0b9f\u0bc8 - \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc8\u0bae\u0bcd\u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0ba4\u0bcd \u0ba4\u0bc2\u0ba3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Classical Sangam verses by Nakkirar detailing the architectural splendor of Pandyan palaces with precisely mortised hardwood rafters, sculpted sandalwood pillars, and interlocking eaves.",
        "summary_ta": "\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0bae\u0ba9\u0bcd\u0ba9\u0ba9\u0bbf\u0ba9\u0bcd \u0b85\u0ba8\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0bc1\u0bb0 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0ba8\u0b95\u0bcd\u0b95\u0bc0\u0bb0\u0bb0\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0ba9 \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0bc8\u0bae\u0bcd\u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9 \u0bae\u0bb0\u0ba4\u0bcd \u0ba4\u0bc2\u0ba3\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0b95\u0bca\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Nedunalvadai 75-115",
            "Mullaippattu 40-55",
            "Silappadikaram Adaikkalakkathai"
        ],
        "content": "# Nedunalvadai: Verses on Mortised Palace Rafters & Sandalwood Pillars\n\nIn *Nedunalvadai* (lines 75\u2013115), the Sangam poet Nakkirar provides an extraordinarily detailed technical description of classical Pandyan palace architecture (*koyil* or *armanai*).\n\nThe poet depicts master carpenters (*thatchar*) employing sophisticated joinery systems to assemble multi-tiered royal pavilions without a single ferrous nail. Heavy rafters (*kaimmaram*) crafted from seasoned teak (*thekku*) and rosewood (*eetti*) were cut with precision mortise-and-tenon joints (*poruthu*) and secured with dense hardwood dowels (*ani*).\n\nMassive cylindrical pillars turned from fragrant sandalwood (*chandanam*) and terminalia (*marutham*) supported cantilevered projecting eaves (*kodungai*) sculpted with mythic crests. These timber systems accommodated thermal expansion during intense tropical heat while remaining rigidly watertight during the torrential north-east monsoons."
    },
    {
        "file": "knowledge/concepts/concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering.md",
        "slug": "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering",
        "category": "concept",
        "name_en": "Poruthu-Thatchu: Mortise-and-Tenon Interlocking Timber Joinery Engineering",
        "name_ta": "\u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1 - \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bc1, \u0b95\u0bc1\u0b9f\u0bc1\u0bae\u0bbf-\u0bae\u0b9f\u0bbf\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Indigenous Tamil joinery engineering utilizing mortise-tenon, lap, and bridle interlocking timber connections reinforced with dry hardwood trenails rather than iron fasteners.",
        "summary_ta": "\u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbf\u0b95\u0bb3\u0bcd \u0b87\u0ba9\u0bcd\u0bb1\u0bbf \u0b89\u0bb2\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0b95\u0b9f\u0bbf\u0ba9 \u0bae\u0bb0 \u0b86\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baf\u0bbe\u0b95 \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0b9f\u0bbf\u0bb5\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0b9f\u0bc1\u0bae\u0bbf\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Manasara Vastu Shastra (Tamil recensions)",
            "Mayamata Architecture Manuals",
            "Padmanabhapuram Palace Records"
        ],
        "content": "# Poruthu-Thatchu: Interlocking Timber Joinery Engineering\n\nTamil traditional architecture rejected ferrous iron spikes in monumental timber frames, recognizing that rust expands and fractures fibrous hardwood when exposed to coastal humidity.\n\nInstead, master joiners developed *poruthu-thatchu*\u2014a comprehensive taxonomy of self-locking mortise-and-tenon joints:\n1. *Kudumi-poruthu* (through-tenon): Where a sculpted rectangular tongue penetrates fully through the receiving timber.\n2. *Madivu-poruthu* (lap and bridle joint): Used at corners and roof ties to distribute tensile shearing loads.\n3. *Aappu-pinithal* (wedged tenon): Driven with tapered rosewood wedges to create permanent friction-locked joints.\n\nThese interlocking assemblies allowed massive timber frames to flex microscopically under cyclonic gusts without joint failure, maintaining structural equilibrium for centuries."
    },
    {
        "file": "knowledge/technologies/technology-kodi-madangai-cantilevered-carved-wooden-brackets-and-eaves-support.md",
        "slug": "technology-kodi-madangai-cantilevered-carved-wooden-brackets-and-eaves-support",
        "category": "technology",
        "name_en": "Kodi-Madangai: Cantilevered Sculpted Timber Brackets & Overhanging Eaves Support",
        "name_ta": "\u0b95\u0bca\u0b9f\u0bbf \u0bae\u0b9f\u0b99\u0bcd\u0b95\u0bc8 - \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bc8 \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Early Historic to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Curved cantilevered wooden brackets projecting outward from wall-plates to support deep multi-tiered verandas and shield mud-plaster and timber walls from heavy tropical downpours.",
        "summary_ta": "\u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0b9a\u0bc1\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bc8 \u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0bb3\u0bbf\u0ba8\u0bc0\u0b9f\u0bcd\u0b9f\u0bbf \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bc8\u0ba8\u0baf\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0ba4\u0bbf\u0b95\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bbf \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Padmanabhapuram Architectural Surveys",
            "Silappadikaram Chapter 5",
            "Vernacular Architecture of South India"
        ],
        "content": "# Kodi-Madangai: Cantilevered Sculpted Timber Brackets\n\nIn South Indian vernacular and royal architecture, eaves overhangs extended up to two meters beyond exterior walls to prevent torrential tropical rains from splashing against timber paneling and lime plaster.\n\nTo bear the tremendous weight of multi-layered terracotta tile roofs without intermediate ground columns, craftsmen engineered *kodi-madangai* (or *kodungai* brackets):\n- **Cantilever Geometry**: Stepped corbel brackets projecting upward and outward at 45-degree angles from the top wall-plate (*uttaram*).\n- **Artistic Sculpture**: Hand-carved from dense jackwood (*palaa*) or rosewood into motifs of mythic crocodiles (*makara*), rampant lions (*yali*), and unfurling floral foliage (*kodi-karukku*).\n- **Load Redistribution**: The downwards moment of the tiled roof is transmitted smoothly back into vertical load-bearing columns, ensuring wind-resistant stability."
    },
    {
        "file": "knowledge/artifacts/artifact-ulakkai-and-koor-vaali-hardwood-framing-tools-mortise-chisels-and-adzes.md",
        "slug": "artifact-ulakkai-and-koor-vaali-hardwood-framing-tools-mortise-chisels-and-adzes",
        "category": "artifact",
        "name_en": "Koor-Uli & Vaali: Traditional Heavy Mortise Chisels, Adzes & Scribing Gauges",
        "name_ta": "\u0b95\u0bc2\u0bb0\u0bcd \u0b89\u0bb3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0bb3\u0bbf - \u0b95\u0ba9\u0bb0\u0b95\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb3\u0bbf \u0b89\u0bb3\u0bbf\u0b95\u0bb3\u0bcd, \u0bb5\u0bc0\u0b9a\u0bcd\u0b9a\u0bc1 \u0bb5\u0bbe\u0bb3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0b9f\u0bcd\u0b9f\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbf\u0b95\u0bb3\u0bcd",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Specialized wootz-steel edged woodcarving toolkits comprising heavy socketed mortise chisels, adzes for surface dressing, bow-drills, and charcoal string line scribers.",
        "summary_ta": "\u0b95\u0b9f\u0bbf\u0ba9\u0bae\u0bbe\u0ba9 \u0b88\u0b9f\u0bcd\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b87\u0bb4\u0bc8\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bb5\u0bc1\u0bae\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b89\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0b83\u0b95\u0bc1 \u0baa\u0bca\u0bb3\u0bbf \u0b89\u0bb3\u0bbf\u0b95\u0bb3\u0bcd, \u0b95\u0bc8\u0bb5\u0bbe\u0bb3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1 \u0ba8\u0bc2\u0bb2\u0bcd\u0b95\u0bb0\u0bc1\u0bb5\u0bbf\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Archaeological Woodworking Implements of Tamil Nadu",
            "Purananuru 206",
            "Traditional Craft Tool Lexicon"
        ],
        "content": "# Koor-Uli & Vaali: Traditional Woodworking Toolkits\n\nThe mastery of ancient Tamil carpenters (*thatchar*) was inextricably linked to metallurgical advancements in wootz carbon crucible steel.\n\nKey tools in the traditional royal carpenter's chest (*thatchuk-koodai*) included:\n1. *Poli-Uli* (Heavy Mortise Chisel): A thick, trapezoidal wootz blade forged with a substantial socket, struck with heavy tamarind-wood mallets (*marach-chuttikkal*) to gouge deep, clean tenon slots.\n2. *Vaali* (Curved Hewing Adze): A razor-sharp arched transverse blade swung rhythmically between the artisan's feet to plane rough logs into perfectly squared beams without sawmarks.\n3. *Koodu-Koor* (Scribing Compass) and *Kari-Nool* (Charcoal Snap-Line): High-precision layout tools enabling millimeter-accurate alignment across ten-meter rafters."
    },
    {
        "file": "knowledge/concepts/concept-thekku-and-eetti-teak-and-rosewood-sapwood-curing-and-termite-resisting-resins.md",
        "slug": "concept-thekku-and-eetti-teak-and-rosewood-sapwood-curing-and-termite-resisting-resins",
        "category": "concept",
        "name_en": "Thekku & Eetti: Teak and Rosewood Heartwood Chemistry & Natural Termite Resistance",
        "name_ta": "\u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b88\u0b9f\u0bcd\u0b9f\u0bbf - \u0bb5\u0bc8\u0bb0\u0baa\u0bcd\u0baa\u0bbe\u0baf\u0bcd\u0ba8\u0bcd\u0ba4 \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd, \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc8\u0baf\u0bbe\u0ba9\u0bcd \u0b8e\u0ba4\u0bbf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Botanical and chemical selection of mature Anamalai and Western Ghats teak and rosewood heartwood rich in tectoquinone and natural polyphenols that resist subterranean termites and rot.",
        "summary_ta": "\u0bae\u0bc7\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0bae\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0ba4\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b88\u0b9f\u0bcd\u0b9f\u0bbf \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0bc8\u0bb0\u0baa\u0bcd\u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9f\u0bc6\u0b95\u0bcd\u0b9f\u0bcb\u0b95\u0bc1\u0baf\u0bbf\u0ba9\u0bcb\u0ba9\u0bcd \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b95\u0bb0\u0bc8\u0baf\u0bbe\u0ba9\u0bcd \u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Akananuru 282",
            "Tamil Silviculture Epigraphs",
            "Indian Forester Historical Studies"
        ],
        "content": "# Thekku & Eetti: Teak and Rosewood Silvicultural Selection\n\nAncient Tamil architectural guilds (*rathakaras* and *kammalar*) followed strict silvicultural doctrines regarding tree selection, felling calendars, and seasoning.\n\nTimber was harvested exclusively from the Western Ghats (*Sahyadri*) during the waning moon when sap flow was minimal:\n- **Tectona grandis (*Thekku*)**: Valued for its dense natural oils and secondary metabolites (notably tectoquinone), rendering it inherently impervious to subterranean termites (*karayan*) and fungal dry rot.\n- **Dalbergia latifolia (*Eetti* / Rosewood)**: Exceptionally high density and compressive strength (exceeding 85 MPa), used for high-stress kingpins, lintels, and palace thrones.\n- **Water Curing (*Neer-Padham*)**: Felled trunks were submerged in flowing river backwaters for up to six months to leach out fermentable starches and water-soluble sugars, eliminating the food source for wood-boring beetles."
    },
    {
        "file": "knowledge/institutions/institution-thatchar-rathakara-corporation-of-master-woodcrafters-and-palace-architects.md",
        "slug": "institution-thatchar-rathakara-corporation-of-master-woodcrafters-and-palace-architects",
        "category": "institution",
        "name_en": "Thatchar Rathakara Guild: Hereditary Corporation of Master Woodcrafters & Royal Architects",
        "name_ta": "\u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd-\u0bb0\u0ba4\u0b95\u0bbe\u0bb0\u0bb0\u0bcd \u0b9a\u0baa\u0bc8 - \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bcd, \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bb4\u0bc1",
        "era": "Classical Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Autonomous artisan guild corporately recognized in royal inscriptions with exclusive rights over civic timber design, palace engineering, temple chariot fabrication, and apprenticeship charters.",
        "summary_ta": "\u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd \u0b95\u0bbe\u0ba3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb0\u0ba4\u0b95\u0bbe\u0bb0 \u0b85\u0ba8\u0bcd\u0ba4\u0bb8\u0bcd\u0ba4\u0bc1 \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8, \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0ba9\u0bcd\u0ba9\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1.",
        "sources": [
            "Uttiramerur Inscriptions",
            "Chola Rathakara Charters (1118 CE)",
            "Manur Village Council Records"
        ],
        "content": "# Thatchar Rathakara Guild: Royal Carpenters' Corporation\n\nThe woodcrafting community in ancient Tamilakam operated under a structured guild hierarchy governed by canonized mathematical treatises and royal land charters (*thatcha-kaani*).\n\nThe guild comprised four distinct grades of mastery:\n1. *Sthapati* (Chief Architectural Master): Planned cosmological alignments, ground plans, and proportional formulas (*aadi-pramana*).\n2. *Sutragrahin* (Chief Surveyor): Measured horizontal and vertical axes using the sacred bamboo rod (*kole*).\n3. *Takshaka* (*Thatchar* / Master Joiner): Cut, sculpted, and erected load-bearing timber members.\n4. *Vardhakin* (Finishing Joiner): Polished panels, fitted lattice screens, and applied natural beeswax finishes.\n\nInscriptions from the reign of Kulottunga Chola I explicitly confirm that the Rathakara-Thatchar corporations maintained their own courts, arbitrated trade disputes, collected taxes on timber imports, and maintained exclusive hereditary apprenticeship traditions."
    },
    {
        "file": "knowledge/technologies/technology-charupadi-perforated-timber-lattice-windows-and-microclimatic-draft-channels.md",
        "slug": "technology-charupadi-perforated-timber-lattice-windows-and-microclimatic-draft-channels",
        "category": "technology",
        "name_en": "Charupadi & Jalakavathayan: Perforated Timber Lattice Windows & Micro-Ventilation Screens",
        "name_ta": "\u0b9a\u0bbe\u0bb0\u0bc1\u0baa\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0bb3\u0bb0\u0b95\u0bcd \u0b95\u0bbf\u0bb3\u0bbf\u0b95\u0bcd\u0b95\u0bc2\u0ba3\u0bcd\u0b9f\u0bc1 - \u0ba4\u0bc1\u0bb3\u0bc8\u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bb2\u0b95\u0ba3\u0bbf, \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb4\u0bb2\u0bcd \u0ba4\u0bbf\u0bb0\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 300,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Ergonomically inclined timber window benches and geometrically carved rosewood lattice screens providing privacy, solar shading, and continuous Venturi-effect passive cross-ventilation.",
        "summary_ta": "\u0ba8\u0bc7\u0bb0\u0b9f\u0bbf \u0bb5\u0bc6\u0baf\u0bbf\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0bb5\u0bc6\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0bb0\u0bcd\u0bb5\u0bc8\u0baf\u0bc8 \u0bae\u0bb1\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bc0\u0bb0\u0bbe\u0ba9 \u0ba4\u0bc6\u0ba9\u0bcd\u0bb1\u0bb2\u0bcd \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8 \u0b87\u0bb2\u0bcd\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bcd \u0b88\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b9a\u0bcd \u0b9a\u0bbe\u0bb3\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0bb0\u0bc1\u0baa\u0b9f\u0bbf \u0b9a\u0bbe\u0baf\u0bcd\u0bb5\u0bc1 \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc8 \u0bae\u0bb0 \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Padmanabhapuram Palace Architecture",
            "Manasara Windows Chapter",
            "Vernacular Climatic Design Studies"
        ],
        "content": "# Charupadi & Jalakavathayan: Micro-Climatic Timber Windows\n\nTropical palace architecture demanded effective thermal mitigation without mechanical aids. The *charupadi* and *jalakavathayan* (lattice windows) represented an apex of ergonomic and climatic timber engineering.\n\n- **Venturi Airflow**: Intricate fretwork screens cut with geometric rhombuses and perforations constricted incoming humid sea breezes, accelerating air velocity and causing a noticeable evaporative cooling drop across interior halls.\n- **Solar Shading & Glare Reduction**: Slanted timber louvers blocked direct midday solar radiation while scattering soft ambient light across polished clay and lime floors.\n- **Integrated Reclining Seating**: The *charupadi* functioned simultaneously as an inclined, ergonomically sculpted banquette bench lining the perimeter of verandas, where courtiers relaxed while remaining shielded behind outer timber grilles."
    },
    {
        "file": "knowledge/artifacts/artifact-mukappu-carved-teak-gable-fascias-and-ornate-lintel-friezes.md",
        "slug": "artifact-mukappu-carved-teak-gable-fascias-and-ornate-lintel-friezes",
        "category": "artifact",
        "name_en": "Mukappu & Kudamuttu: Sculpted Teak Gable Fascias, Lintel Friezes & Pendant Finials",
        "name_ta": "\u0bae\u0bc1\u0b95\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0b9f\u0bae\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1 - \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0 \u0bae\u0bc1\u0b95\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0b95\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0ba8\u0bbf\u0bb2\u0bc8 \u0b89\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0bae\u0ba3\u0bbf \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb2\u0bc8",
        "era": "Early Historic to Modern Era",
        "year_start": -200,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Monolithic teak triangular gable fascias, ornate entrance lintels, and hanging lotus bud pendants displaying intricate dynastic heraldry and mythic iconography.",
        "summary_ta": "\u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8 \u0bae\u0bc1\u0b95\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0baf\u0bbf\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc0\u0bb0\u0bae\u0bbe\u0b95 \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0bbe\u0bae\u0bb0\u0bc8 \u0b85\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0b99\u0bcd\u0b95\u0bb2\u0bcd\u0b95\u0bb3\u0bcd, \u0b9a\u0bbf\u0bae\u0bcd\u0bae \u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9c\u0bb2\u0b9f\u0bcd\u0b9a\u0bc1\u0bae\u0bbf \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b85\u0b9f\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bae\u0bb0 \u0bae\u0bc1\u0b95\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Padmanabhapuram Palace Woodcarvings",
            "Silappadikaram Book of Madurai",
            "South Indian Temple Carvings Survey"
        ],
        "content": "# Mukappu & Kudamuttu: Sculpted Teak Gable Fascias\n\nThe primary exterior expression of status in ancient Tamil residences and royal compounds was concentrated in the *mukappu*\u2014the triangular pediment and entrance gable framing the main portico (*thinnai*).\n\nCrafted from massive, straight-grained teak billets:\n- **Intricate Bas-Relief**: Master woodcarvers incised elaborate narrative scenes from the epics, flanked by heraldic motifs such as twin jumping carps (*kayal* for Pandyas), leaping tigers (*puli* for Cholas), or upright bows (*vil* for Cheras).\n- **Kudamuttu (Pendant Drops)**: From the apex of the gable hung intricately turned drops styled like stylized lotus buds (*kamala-muttu*) or inverted ceremonial bells, carved from single solid wood cylinders.\n- **Interlocking Splines**: Gable components were held together with concealed internal hardwood splines, allowing moisture movement without cracking the carved surface relief."
    },
    {
        "file": "knowledge/concepts/concept-kadamba-and-maruthu-structural-beam-timber-deflection-and-load-distribution.md",
        "slug": "concept-kadamba-and-maruthu-structural-beam-timber-deflection-and-load-distribution",
        "category": "concept",
        "name_en": "Kadamba & Maruthu: Structural Timber Beam Mechanics, Modulus of Rupture & Load Bearing",
        "name_ta": "\u0b95\u0b9f\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bc1\u0ba4\u0bc1 - \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0b89\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0 \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0bae\u0bc8\u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb1\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bbf\u0bb5\u0bc1 \u0b8e\u0ba4\u0bbf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Structural mechanics of native Tamil broadleaf timbers (Terminalia and Neolamarckia) utilized for heavy roof spans, evaluating modulus of rupture, bending resistance, and fiber elasticity.",
        "summary_ta": "\u0b85\u0b95\u0ba9\u0bcd\u0bb1 \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8 \u0bae\u0ba3\u0bcd\u0b9f\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bb5\u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0b95 \u0bae\u0bb0\u0bc1\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bae\u0bcd\u0baa \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba8\u0bbe\u0bb0\u0bcd \u0ba8\u0bc6\u0b95\u0bbf\u0bb4\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0bb0\u0bae\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb1\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Perumpanattruppadai 345-360",
            "Mayamata Chapter 15",
            "Engineering Properties of Indian Timbers"
        ],
        "content": "# Kadamba & Maruthu: Structural Timber Beam Mechanics\n\nWhile rosewood and teak were prized for surface finish, monumental halls spanning upwards of eight to ten meters without intermediate columns demanded timbers with exceptional flexural strength and resistance to shear deflection.\n\nMaster builders utilized two regional riparian hard timber species:\n1. *Maruthu* (*Terminalia arjuna*): Harvested from riverbank alluvium, maruthu possesses an interwoven grain structure with an outstanding modulus of elasticity (MOE > 12,000 MPa). It was designated for primary tie-beams (*per-uttaram*) capable of resisting sagging under dynamic roof loads.\n2. *Kadamba* (*Neolamarckia cadamba*): Known for its uniform fiber density and superior shock-absorbing characteristics, chosen for central transverse joists and floor decks above subterranean cellars.\n\nProportional sizing formulas mandated that beam depth (*kandham*) be proportional to span length squared, preventing noticeable center deflection over centuries of service."
    },
    {
        "file": "knowledge/places/place-padmanabhapuram-ancient-wooden-palace-haven.md",
        "slug": "place-padmanabhapuram-ancient-wooden-palace-haven",
        "category": "place",
        "name_en": "Padmanabhapuram: Ancient Chera-Venad Monumental Wooden Palace Haven",
        "name_ta": "\u0baa\u0ba4\u0bcd\u0bae\u0ba8\u0bbe\u0baa\u0baa\u0bc1\u0bb0\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bc7\u0bb0-\u0bb5\u0bc7\u0ba3\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 300,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Monumental wooden palace citadel at the foot of the Veli Hills in Kanyakumari district, standing as Asia's largest surviving timber architectural complex with master mortise joinery.",
        "summary_ta": "\u0b95\u0ba9\u0bcd\u0ba9\u0bbf\u0baf\u0bbe\u0b95\u0bc1\u0bae\u0bb0\u0bbf \u0bae\u0bbe\u0bb5\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0bb5\u0bc7\u0bb3\u0bbf\u0bae\u0bb2\u0bc8 \u0b85\u0b9f\u0bbf\u0bb5\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3, \u0b86\u0b9a\u0bbf\u0baf\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0bae\u0bbf\u0b95\u0baa\u0bcd\u0baa\u0bc6\u0bb0\u0bbf\u0baf \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd \u0b95\u0bb2\u0bc8 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bbf\u0ba9\u0bcd \u0b89\u0b9a\u0bcd\u0b9a\u0bae\u0bc1\u0bae\u0bbe\u0ba9 \u0bae\u0bb0 \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Travancore Archaeological Series",
            "Padmanabhapuram Palace Monograph",
            "Paditruppattu 88"
        ],
        "content": "# Padmanabhapuram: Ancient Wooden Palace Haven\n\nNestled beneath the granite ramparts of the Veli Hills in modern Kanyakumari district (historically part of ancient Venad and the southern Chera realm), Padmanabhapuram represents the most complete surviving masterpiece of classical South Indian timber architecture.\n\nCovering a fortified compound enclosed by massive granite bastions, the palace complex is constructed almost entirely of hand-hewn seasoned teak, rosewood, and jackwood:\n- **King's Council Chamber (*Manthrasala*)**: Features 300-year-old louvered timber slats and continuous *charupadi* seating, illuminated through mica and seashell window panels.\n- **Uppirikka Malika**: A towering four-tiered timber pagoda whose uppermost chamber houses the sacred medicinal wooden cot (*marundhu-kattil*) carved from 64 distinct herbal timbers.\n- **Acoustic and Thermal Performance**: Deep overhanging eaves, interlocking floor joists, and open-plan clerestories maintain interior temperatures up to 6\u00b0C cooler than the ambient outdoor heat without mechanical airflow."
    }
]

EDGES = [
    [
        "text-nedunalvadai-verses-on-sandalwood-pillars-and-mortised-palace-rafters",
        "DESCRIBES",
        "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering",
        "core",
        "Sangam Era",
        "Nedunalvadai verses depict precision mortised palace rafters assembled without iron nails.",
        "Nedunalvadai 75-115"
    ],
    [
        "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering",
        "EMPLOYS_TOOL",
        "artifact-ulakkai-and-koor-vaali-hardwood-framing-tools-mortise-chisels-and-adzes",
        "core",
        "Iron Age to Modern Era",
        "Mortise-and-tenon joints were gouged and planed using heavy socketed chisels and wootz adzes.",
        "Archaeological Woodworking Implements"
    ],
    [
        "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering",
        "UTILIZES_RESOURCE",
        "concept-thekku-and-eetti-teak-and-rosewood-sapwood-curing-and-termite-resisting-resins",
        "core",
        "Prehistoric to Modern Era",
        "Joiners selected mature teak and rosewood heartwood rich in insect-repelling tectoquinone.",
        "Akananuru 282"
    ],
    [
        "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering",
        "GOVERNED_BY",
        "institution-thatchar-rathakara-corporation-of-master-woodcrafters-and-palace-architects",
        "core",
        "Classical Sangam to Medieval Era",
        "Woodworking corporations standardized proportional timber formulas and joinery training.",
        "Chola Rathakara Charters"
    ],
    [
        "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering",
        "CONSTRUCTS",
        "technology-kodi-madangai-cantilevered-carved-wooden-brackets-and-eaves-support",
        "core",
        "Early Historic to Modern Era",
        "Precision joints anchored cantilevered corbel brackets supporting massive tile roof eaves.",
        "Padmanabhapuram Architectural Surveys"
    ],
    [
        "technology-kodi-madangai-cantilevered-carved-wooden-brackets-and-eaves-support",
        "INTEGRATES_WITH",
        "artifact-mukappu-carved-teak-gable-fascias-and-ornate-lintel-friezes",
        "core",
        "Early Historic to Modern Era",
        "Overhanging eaves brackets terminated at elaborate entrance gable fascias and lotus finials.",
        "Padmanabhapuram Palace Woodcarvings"
    ],
    [
        "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering",
        "ENABLES",
        "technology-charupadi-perforated-timber-lattice-windows-and-microclimatic-draft-channels",
        "core",
        "Early Medieval to Modern Era",
        "Timber framing accommodated fretwork lattice windows and inclined perimeter bench seating.",
        "Manasara Windows Chapter"
    ],
    [
        "concept-kadamba-and-maruthu-structural-beam-timber-deflection-and-load-distribution",
        "PROVIDES_STRENGTH_FOR",
        "technology-kodi-madangai-cantilevered-carved-wooden-brackets-and-eaves-support",
        "core",
        "Prehistoric to Modern Era",
        "High-elasticity Terminalia beams distributed massive roof loads to corbel brackets.",
        "Perumpanattruppadai 345-360"
    ],
    [
        "concept-poruthu-thatchu-mortise-tenon-joinery-and-interlocking-timber-engineering",
        "PRESERVED_AT",
        "place-padmanabhapuram-ancient-wooden-palace-haven",
        "core",
        "Early Medieval to Modern Era",
        "Padmanabhapuram represents the paramount surviving architectural haven of Tamil timber joinery.",
        "Padmanabhapuram Palace Monograph"
    ],
    [
        "institution-thatchar-rathakara-corporation-of-master-woodcrafters-and-palace-architects",
        "OPERATED_AT",
        "place-padmanabhapuram-ancient-wooden-palace-haven",
        "core",
        "Early Medieval to Modern Era",
        "Master carpentry guilds planned and executed the monumental timber pavilions of Padmanabhapuram.",
        "Travancore Archaeological Series"
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
