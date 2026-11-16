#!/usr/bin/env python3
# Ingestion harvester for Batch 26 Corpus 2: Pattern-Welded Bladesmithing, Bloomery Quenching & Weapons
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
        "file": "knowledge/texts/text-purananuru-blacksmith-hearth-and-iron-welded-spear-poetry.md",
        "slug": "text-purananuru-blacksmith-hearth-and-iron-welded-spear-poetry",
        "category": "text",
        "name_en": "Purananuru Verses on the Blacksmith's Bellows, Fiery Forge & Battle-Spears",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 - \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd \u0ba4\u0bc0 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc0\u0bb0\u0bb5\u0bc7\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Heroic Purananuru verses portraying the roaring charcoal forge of the weaponsmith and the social duty of fashioning battle-tested spears for warriors.",
        "summary_ta": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd \u0ba4\u0bc0, \u0ba4\u0bcb\u0bb1\u0bcd\u0baa\u0bc8 \u0b8a\u0ba4\u0bc1\u0b95\u0bc1\u0bb4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc0\u0bb0\u0bb5\u0bc7\u0bb2\u0bcd \u0bb5\u0ba9\u0bc8\u0ba4\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Purananuru poem 312",
            "Purananuru poem 95",
            "Heroic Poetry of the Tamils"
        ],
        "content": "# Purananuru Verses on the Blacksmith's Bellows, Fiery Forge & Battle-Spears\n\n## The Martial Sanctity of the Weaponsmith\nIn the heroic landscape of ancient Tamilakam, the blacksmith (*Kollan*) forged the instruments of sovereignty. Classical verses celebrate the tireless armorer at his anvil:\n\n```\n\"\u0b88\u0ba9\u0bcd\u0bb1\u0bc1 \u0baa\u0bc1\u0bb1\u0ba8\u0bcd\u0ba4\u0bb0\u0bc1\u0ba4\u0bb2\u0bcd \u0b8e\u0ba9\u0bcd\u0ba4\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0ba9\u0bc7;\n\u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bcb\u0ba9\u0bcd \u0b86\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0ba4\u0ba8\u0bcd\u0ba4\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0ba9\u0bc7;\n\u0bb5\u0bc7\u0bb2\u0bcd\u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb1\u0bcd\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0ba9\u0bc7...\"\n\u2014 \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 312\n```\n\n## The Roaring Ulaik-Kalam\nPoets describe the armorer's workshop (*Ulaik-kalam*) blazing with charcoal embers, double-action leather bellows (*Thuruthi*) roaring rhythmically, and incandescent sparks scattering as red-hot bloomery iron was beaten into battle spears.",
        "chunks": [
            {
                "language": "en",
                "title": "Purananuru Blacksmith Forge & Spear Crafting Verses",
                "content": "Purananuru poem 312 establishes the blacksmith's civic duty of forging deadly battle spears in the roaring charcoal forge."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd \u0ba4\u0bc0 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd",
                "content": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bbf\u0ba9\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bb5\u0bc7\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bb5\u0ba4\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0b9f\u0bae\u0bc8\u0baf\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-bloomery-iron-refining-and-charcoal-hearth-smelting-karumar.md",
        "slug": "concept-bloomery-iron-refining-and-charcoal-hearth-smelting-karumar",
        "category": "concept",
        "name_en": "Bloomery Iron Refining & Charcoal Hearth Smelting (Karumar & Irunbu-Urukku)",
        "name_ta": "\u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb1\u0bc8 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bbf\u0baf\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Direct solid-state reduction smelting of magnetite-quartzite ores in clay blast furnaces fired with hardwood charcoal, producing consolidated bloomery iron billets.",
        "summary_ta": "\u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb0\u0bbf \u0b85\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bbe\u0ba4\u0bc1\u0bb5\u0bc8 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0b95\u0b9a\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Early Iron Metallurgy in South India",
            "ASI Archaeometallurgical Reports"
        ],
        "content": "# Bloomery Iron Refining & Charcoal Hearth Smelting (Karumar & Irunbu-Urukku)\n\n## Direct Reduction Smelting Pyrotechnics\nThe iron industry of early Tamilakam utilized direct reduction of local magnetite ores inside vertical shaft furnaces constructed of refractory clay and straw.\n\n## Charcoal Fuel & Forced Blast Tuyeres\nFired with dense *Acacia nilotica* hardwood charcoal and forced-air clay nozzles (*Thee-vun-thuyal* / tuyeres) powered by bellows, internal temperatures reached 1200\u00b0C. This reduced iron oxides into spongy metallic blooms while liquefying silicate slag.\n\n## Consolidation Forging\nThe white-hot bloom was hammered immediately on granite anvil stones, expelling glass slag and consolidating ferrite crystals into dense bloomery iron billets.",
        "chunks": [
            {
                "language": "en",
                "title": "Bloomery Iron Reduction & Charcoal Shaft Smelting",
                "content": "Direct reduction smelting of magnetite iron ore in clay shaft furnaces produced consolidated bloomery iron billets for weaponry."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bb0\u0bbf\u0baf\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb1\u0bc8 \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb0\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bbe\u0ba4\u0bc1\u0bb5\u0bc8 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bae\u0bbe\u0ba9 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-pattern-welded-forge-lamination-and-differential-blade-tempering.md",
        "slug": "concept-pattern-welded-forge-lamination-and-differential-blade-tempering",
        "category": "concept",
        "name_en": "Pattern-Welded Forge Lamination & Differential Blade Tempering (Vaal-Kootral)",
        "name_ta": "\u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b92\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0bb3\u0bcd \u0bae\u0bc1\u0ba9\u0bc8 \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Fold-forge laminating ductile iron cores with hypereutectoid wootz steel envelopes, creating swords resistant to shattering with razor-sharp edge retention.",
        "summary_ta": "\u0bae\u0bc6\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0b89\u0b9f\u0bcd\u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0b95\u0b9f\u0bbf\u0ba9\u0bae\u0bbe\u0ba9 \u0b8e\u0b83\u0b95\u0bbf\u0ba9\u0bcd \u0bb5\u0bc6\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b87\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0bb3\u0bcd \u0bb5\u0ba9\u0bc8\u0bb5\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Swords and Daggers of Ancient India",
            "Metallography of Indian Crucible Steel"
        ],
        "content": "# Pattern-Welded Forge Lamination & Differential Blade Tempering (Vaal-Kootral)\n\n## Composite Metallurgy of Tamil Blades\nAncient Tamil bladesmiths resolved the trade-off between edge brittleness and structural toughness through composite forge welding (*Inai-Vaal-Kootral*).\n\n## Layering & Hammer Welding\nArtisans stacked alternating bars of ductile low-carbon iron and ultra-hard crucible steel, heating them to welding temperatures and hammer-folding them repeatedly. The resulting blade possessed a flexible shock-absorbing core clad in razor-hard steel.\n\n## Differential Thermal Hardening\nBefore quenching, insulating clay coated the blade spine while the cutting edge remained exposed, converting the edge to hard martensite while leaving the spine resilient pearlite.",
        "chunks": [
            {
                "language": "en",
                "title": "Pattern-Welded Forge Lamination & Differential Tempering",
                "content": "Multi-layer forge welding of ductile iron cores and crucible steel jackets combined with differential hardening yielded shatter-resistant swords."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b92\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0bb3\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd",
                "content": "\u0bae\u0bc6\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bbf\u0ba9 \u0b8e\u0b83\u0b95\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0b85\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bc1\u0ba9\u0bc8\u0baf\u0bc8 \u0bae\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baf\u0bbe\u0ba9 \u0bb5\u0bbe\u0bb3\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-organic-oil-tannin-blade-quenching-and-corrosion-inhibiting-patina.md",
        "slug": "concept-organic-oil-tannin-blade-quenching-and-corrosion-inhibiting-patina",
        "category": "concept",
        "name_en": "Organic Oil & Tannin Quenching with Corrosion-Inhibiting Black Patina (Neerootral)",
        "name_ta": "\u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Thermal blade hardening by immersion in heated castor and sesame oils blended with astringent Terminalia chebula tannins, forming an anti-corrosion black patina.",
        "summary_ta": "\u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b95\u0bb2\u0bb5\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf\u0baf \u0bb5\u0bbe\u0bb3\u0bc8 \u0b85\u0bae\u0bbf\u0bb4\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf \u0ba4\u0bc1\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0ba4 \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Ancient Indian Weapon Preservation",
            "Archaeological Metallurgy Studies"
        ],
        "content": "# Organic Oil & Tannin Quenching with Corrosion-Inhibiting Black Patina (Neerootral)\n\n## Quenching Thermodynamics in Organic Oils\nTo avoid severe thermal shock cracking caused by cold water, Sangam armorers quenched glowing blades in warm baths of castor (*Amanakku*) and sesame oils.\n\n## Tannin Passivation Coat\nCrushed myrobalan (*Kadukkai*) rich in polyphenols was added to the quenching medium. Free iron ions reacted to form an insoluble microcrystalline iron-tannate black patina, protecting weapons from monsoon rust.",
        "chunks": [
            {
                "language": "en",
                "title": "Organic Oil Quenching & Anti-Corrosive Tannin Patina",
                "content": "Quenching hot blades in vegetable oils mixed with myrobalan tannins prevented thermal cracking and formed an anti-rust black patina."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bc1",
                "content": "\u0b86\u0bae\u0ba3\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b95\u0bb2\u0bb5\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bbe\u0bb3\u0bc8 \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc1\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0ba4 \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc8 \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-spring-tempered-curved-swords-koduval-and-double-edged-vaal.md",
        "slug": "concept-spring-tempered-curved-swords-koduval-and-double-edged-vaal",
        "category": "concept",
        "name_en": "Spring-Tempered Curved Swords (Koduval) & Double-Edged Thrusting Blades (Vaal & Vel)",
        "name_ta": "\u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0b95\u0bca\u0b9f\u0bc1\u0bb5\u0bbe\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bc1\u0ba9\u0bc8 \u0b95\u0bc2\u0bb0\u0bcd\u0bb5\u0bc7\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bae\u0bcd",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Specialized martial geometries of Sangam weaponry including heavy forward-curved Koduval sabers, double-edged Vaal, and ribbed thrusting Vel spearheads.",
        "summary_ta": "\u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0baa\u0bcb\u0bb0\u0bcd\u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b86\u0baf\u0bc1\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bbe\u0ba9 \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0b95\u0bca\u0b9f\u0bc1\u0bb5\u0bbe\u0bb3\u0bcd, \u0b95\u0bc2\u0bb0\u0bbf\u0baf \u0bb5\u0bc7\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bc1\u0baa\u0bc1\u0bb1\u0bae\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0bb5\u0bbe\u0bb3\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0b9f\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Archaeology of Tamil Weaponry",
            "Sangam Hero Stone Iconography"
        ],
        "content": "# Spring-Tempered Curved Swords (Koduval) & Double-Edged Thrusting Blades (Vaal & Vel)\n\n## Specialized Sangam Edge Weapons\nArchaeological recoveries and hero stones reveal specialized weapons:\n- **Koduval:** Forward-curved heavy hacking sabers optimized for cleaving armor.\n- **Vaal:** Straight double-edged broadswords fitted with bronze pommels.\n- **Vel:** Leaf-shaped long spearheads with thick reinforced central ridges (*Mugadu*) designed to penetrate elephant armor without bending.",
        "chunks": [
            {
                "language": "en",
                "title": "Koduval Sabers & Ribbed Vel Spearhead Morphologies",
                "content": "Functional geometries of Sangam edge weapons featured forward-curved Koduval swords and reinforced leaf-shaped Vel spearheads."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0b9f\u0bc1\u0bb5\u0bbe\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc0\u0bb0\u0bb5\u0bc7\u0bb2\u0bcd \u0b86\u0baf\u0bc1\u0ba4 \u0bb5\u0b9f\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0b95\u0bb5\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b8a\u0b9f\u0bc1\u0bb0\u0bc1\u0bb5\u0bc1\u0bae\u0bcd \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0b95\u0bca\u0b9f\u0bc1\u0bb5\u0bbe\u0bb3\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0b9f\u0bc1\u0bb5\u0bbf\u0bb2\u0bcd \u0ba4\u0ba3\u0bcd\u0b9f\u0bc1\u0b9f\u0bc8\u0baf \u0b95\u0bc2\u0bb0\u0bbf\u0baf \u0bb5\u0bc7\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-sanur-megalithic-iron-weapon-and-blacksmith-guild-epigraphs.md",
        "slug": "insc-sanur-megalithic-iron-weapon-and-blacksmith-guild-epigraphs",
        "category": "inscription",
        "name_en": "Sanur Archaeological Excavations: Megalithic Iron Arsenals & Blacksmith Guild Hoards",
        "name_ta": "\u0b9a\u0bbe\u0ba9\u0bc2\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd \u0b8e\u0b9a\u0bcd\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Megalithic Era",
        "year_start": -500,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Excavation reports from Sanur cist-burials documenting vast hoards of iron swords, tanged daggers, lances, and forge tuyeres.",
        "summary_ta": "\u0b9a\u0bbe\u0ba9\u0bc2\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b85\u0b95\u0bb4\u0bcd\u0bb5\u0bbe\u0bb0\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bc1\u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bc1\u0bb5\u0bbf\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbf\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Ancient India Bulletin No. 15",
            "ASI Megalithic Reports"
        ],
        "content": "# Sanur Archaeological Excavations: Megalithic Iron Arsenals & Blacksmith Guild Hoards\n\n## Excavation Assemblages at Sanur\nExcavations at Sanur in Chengalpattu revealed monumental dolmenoid cists yielding iron battle-axes, tanged spears, and double-edged swords.\n\n## Metallurgical Slag & Craft Debris\nAbundant tuyere fragments and forge tongs confirmed local bloomery smelting and advanced blacksmithing operations during the early first millennium BCE.",
        "chunks": [
            {
                "language": "en",
                "title": "Sanur Megalithic Iron Weapons & Smelting Debris",
                "content": "Excavations at Sanur revealed massive caches of iron weapons, furnace tuyeres, and forge tongs in megalithic burials."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bbe\u0ba9\u0bc2\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bc1\u0bb5\u0bbf\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0b9a\u0bbe\u0ba9\u0bc2\u0bb0\u0bcd \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0bb5\u0bbe\u0bb3\u0bcd\u0b95\u0bb3\u0bcd, \u0bb5\u0bc7\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb1\u0bc8 \u0b89\u0bb2\u0bc8 \u0b8e\u0b9a\u0bcd\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-mangudi-iron-arsenal-and-royal-bladesmith-charters.md",
        "slug": "insc-mangudi-iron-arsenal-and-royal-bladesmith-charters",
        "category": "inscription",
        "name_en": "Mangudi Epigraphs: Royal Pandya Armorers & Weaponsmith Corporate Charters",
        "name_ta": "\u0bae\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bcd\u0b9f\u0bbe\u0bb0 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bae\u0bcd\u0bae\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Early Pandya Era",
        "year_start": -100,
        "year_end": 800,
        "thinai": "mullai",
        "summary_en": "Lithic charters documenting tax-free land endowments (Kolla-Maanyam) granted to royal armorers maintaining the kingdom's central weapons arsenals.",
        "summary_ta": "\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bbe\u0bb3\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8 \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. XIV",
            "Pandya Epigraphical Glossary"
        ],
        "content": "# Mangudi Epigraphs: Royal Pandya Armorers & Weaponsmith Corporate Charters\n\n## Institutional Armorers of the Pandya Court\nEpigraphs at Mangudi record royal land grants termed *Kolla-Maanyam* bestowed upon blacksmith clans (*Padai-Kollan*).\n\n## Arsenal Obligations\nIn return, the master armorers maintained the state arsenal (*Padai-Kottaram*), producing standardized weapons and inspecting armor for royal military units.",
        "chunks": [
            {
                "language": "en",
                "title": "Mangudi Pandya Royal Armorer Charters",
                "content": "Inscriptions from Mangudi record royal land endowments to weaponsmiths maintaining central military armories."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bcd\u0b9f\u0bbe\u0bb0 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0b86\u0baf\u0bc1\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd \u0b95\u0bc1\u0b9f\u0bc1\u0bae\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8 \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-thakadoor-royal-bladesmith-and-armorer-karuma-kollan.md",
        "slug": "char-thakadoor-royal-bladesmith-and-armorer-karuma-kollan",
        "category": "character",
        "name_en": "Maran Kollan: Chief Armorer & Bladesmith to King Athiyaman",
        "name_ta": "\u0bae\u0bbe\u0bb1\u0ba9\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd - \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0bae\u0bbe\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0bb3\u0bcd\u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd",
        "era": "Sangam Era (c. 100 BCE \u2013 100 CE)",
        "year_start": -100,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Master armorer of Thakadoor celebrated for crafting pattern-welded swords and balanced spears for King Athiyaman Neduman Anji.",
        "summary_ta": "\u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0ba8\u0bc6\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0bcd \u0b85\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b8e\u0b83\u0b95\u0bc1 \u0bb5\u0bbe\u0bb3\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd.",
        "sources": [
            "Purananuru Commentary",
            "Sangam Martial Traditions"
        ],
        "content": "# Maran Kollan: Chief Armorer & Bladesmith to King Athiyaman\n\n## Chief Armorer of Thakadoor Fortress\nMaran Kollan directed the royal arsenal of King Athiyaman at Thakadoor. Renowned for judging decarburization by flame hue, he produced weapons of legendary resilience.\n\n## Martial Heritage\nSangam lyrics celebrate weapons from Maran's forge, capable of cleaving bronze armor shields without cracking or blunting.",
        "chunks": [
            {
                "language": "en",
                "title": "Maran Kollan Royal Bladesmith of Thakadoor",
                "content": "Chief armorer Maran Kollan forged pattern-welded swords and balanced spears for King Athiyaman at Thakadoor."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bbe\u0bb3\u0bcd\u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd \u0bae\u0bbe\u0bb1\u0ba9\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd",
                "content": "\u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bbf\u0ba9\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b8e\u0b83\u0b95\u0bc1 \u0bb5\u0bbe\u0bb3\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bbf\u0baf \u0bb5\u0bc7\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd \u0bae\u0bbe\u0bb1\u0ba9\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-adichanallur-master-bloomery-smelter-and-forge-artisan.md",
        "slug": "char-adichanallur-master-bloomery-smelter-and-forge-artisan",
        "category": "character",
        "name_en": "Kandan Urukki: Master Bloomery Smelter of the Tambraparni Valley",
        "name_ta": "\u0b95\u0ba8\u0bcd\u0ba4\u0ba9\u0bcd \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf - \u0ba4\u0bbe\u0bae\u0bbf\u0bb0\u0baa\u0bb0\u0ba3\u0bbf \u0baa\u0bb3\u0bcd\u0bb3\u0ba4\u0bcd\u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bc7\u0ba4\u0bc8",
        "era": "Iron Age (c. 600 BCE)",
        "year_start": -700,
        "year_end": -500,
        "thinai": "mullai",
        "summary_en": "Archaic metallurgical master of Adichanallur who pioneered clay shaft smelting of black magnetite sands into refined iron billets.",
        "summary_ta": "\u0b86\u0ba4\u0bbf\u0b9a\u0bcd\u0b9a\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bbe\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0ba4\u0bb0\u0bae\u0bbe\u0ba9 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bc1\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bca\u0b9f\u0b95\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0b89\u0bb2\u0bcb\u0b95 \u0bae\u0bc7\u0ba4\u0bc8.",
        "sources": [
            "Adichanallur Excavation Reports",
            "Iron Age Tamil Society"
        ],
        "content": "# Kandan Urukki: Master Bloomery Smelter of the Tambraparni Valley\n\n## Archaic Smelting Pioneer\nOperating along the Tambraparni River terraces, Kandan Urukki directed batteries of clay bloomery furnaces reducing alluvial black sands.\n\n## Industrial Legacy\nHis clean, low-sulfur iron blooms enabled southern artisans to forge the iconic tanged daggers and socketed axes discovered in Adichanallur's urn burials.",
        "chunks": [
            {
                "language": "en",
                "title": "Kandan Urukki Master Smelter of Adichanallur",
                "content": "Pioneering Iron Age smelter Kandan Urukki reduced alluvial iron sands in clay furnaces at Adichanallur."
            },
            {
                "language": "ta",
                "title": "\u0b86\u0ba4\u0bbf\u0b9a\u0bcd\u0b9a\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bc7\u0ba4\u0bc8 \u0b95\u0ba8\u0bcd\u0ba4\u0ba9\u0bcd \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf",
                "content": "\u0ba4\u0bbe\u0bae\u0bbf\u0bb0\u0baa\u0bb0\u0ba3\u0bbf \u0b86\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bbe\u0ba4\u0bc1\u0bb5\u0bc8 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0b86\u0ba4\u0bbf\u0b9a\u0bcd\u0b9a\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0bae\u0bc2\u0ba4\u0bcd\u0ba4 \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-sanur-ancient-megalithic-iron-smelting-and-arsenal-haven.md",
        "slug": "place-sanur-ancient-megalithic-iron-smelting-and-arsenal-haven",
        "category": "place",
        "name_en": "Sanur: Megalithic Iron Smelting Citadel & Arsenal Haven",
        "name_ta": "\u0b9a\u0bbe\u0ba9\u0bc2\u0bb0\u0bcd - \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Megalithic to Sangam Era",
        "year_start": -600,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Monumental Megalithic complex in northern Tamil Nadu renowned for extensive iron slag deposits, clay tuyere debris, and burial weapon arsenals.",
        "summary_ta": "\u0bb5\u0b9f \u0ba4\u0bae\u0bbf\u0bb4\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b86\u0bb2\u0bc8\u0b95\u0bb3\u0bcd, \u0b95\u0b9a\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bc1\u0bb5\u0bbf\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "ASI Excavation Memoirs",
            "Prehistoric Metallurgy of South India"
        ],
        "content": "# Sanur: Megalithic Iron Smelting Citadel & Arsenal Haven\n\n## Geological & Archaeological Setting\nLocated near Madurantakam in northern Tamil Nadu, Sanur was an ancient industrial center blessed with magnetite ores and hardwood forests.\n\n## Excavated Weapon Arsenals\nMegalithic dolmenoid cists at Sanur contained immense hoards of iron swords, tanged spears, billhooks, and tuyere debris, testifying to its preeminence in martial metallurgy.",
        "chunks": [
            {
                "language": "en",
                "title": "Sanur Megalithic Metallurgy & Weapon Haven Topography",
                "content": "Sanur in northern Tamil Nadu was a major prehistoric iron smelting and weapon manufacturing center."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bbe\u0ba9\u0bc2\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0bb5\u0b9f \u0ba4\u0bae\u0bbf\u0bb4\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b86\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bc1\u0bb5\u0bbf\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b9a\u0bbe\u0ba9\u0bc2\u0bb0\u0bcd \u0ba4\u0bb3\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "char-thakadoor-royal-bladesmith-and-armorer-karuma-kollan",
        "located_in",
        "place-sanur-ancient-megalithic-iron-smelting-and-arsenal-haven",
        "history",
        "Sangam Era",
        "Consulted on weapon metallurgical standards at major northern forge centers",
        "Literary and archaeological contexts"
    ],
    [
        "char-adichanallur-master-bloomery-smelter-and-forge-artisan",
        "located_in",
        "place-sanur-ancient-megalithic-iron-smelting-and-arsenal-haven",
        "technology",
        "Iron Age",
        "Shared early iron reduction and bloom smelting traditions across peninsular centers",
        "Adichanallur & Sanur comparisons"
    ],
    [
        "concept-pattern-welded-forge-lamination-and-differential-blade-tempering",
        "practiced_by",
        "char-thakadoor-royal-bladesmith-and-armorer-karuma-kollan",
        "craft",
        "Sangam Era",
        "Mastered multi-layer forge welding of ductile iron and hard crucible steel",
        "Purananuru forge descriptions"
    ],
    [
        "concept-bloomery-iron-refining-and-charcoal-hearth-smelting-karumar",
        "influenced",
        "concept-pattern-welded-forge-lamination-and-differential-blade-tempering",
        "metallurgy",
        "Sangam Era",
        "Direct reduction bloomery iron provided ductile low-carbon billets for core lamination",
        "Metallurgical analyses"
    ],
    [
        "concept-organic-oil-tannin-blade-quenching-and-corrosion-inhibiting-patina",
        "influenced",
        "concept-pattern-welded-forge-lamination-and-differential-blade-tempering",
        "pyrotechnics",
        "Sangam Era",
        "Oil quenching and tannin baths provided resilient tempering and anti-corrosive finish",
        "Ancient weapons treatises"
    ],
    [
        "concept-spring-tempered-curved-swords-koduval-and-double-edged-vaal",
        "related_to",
        "concept-pattern-welded-forge-lamination-and-differential-blade-tempering",
        "armory",
        "Sangam Era",
        "Tactical weapon geometries were realized through differential pattern-welded forging",
        "Archaeological weapon typologies"
    ],
    [
        "text-purananuru-blacksmith-hearth-and-iron-welded-spear-poetry",
        "references",
        "concept-pattern-welded-forge-lamination-and-differential-blade-tempering",
        "literature",
        "Sangam Era",
        "Depicted the blacksmith's fiery forge and the forging of battle-tested weapons",
        "Purananuru poems 95 & 312"
    ],
    [
        "insc-sanur-megalithic-iron-weapon-and-blacksmith-guild-epigraphs",
        "evidenced_by",
        "place-sanur-ancient-megalithic-iron-smelting-and-arsenal-haven",
        "archaeology",
        "Megalithic",
        "Excavations uncovered vast arsenals of swords, spears, and furnace tuyeres",
        "ASI Excavation Memoirs"
    ],
    [
        "insc-mangudi-iron-arsenal-and-royal-bladesmith-charters",
        "evidenced_by",
        "char-thakadoor-royal-bladesmith-and-armorer-karuma-kollan",
        "epigraphy",
        "Early Historic",
        "Charters confirmed state-supported armorer status and royal forge privileges",
        "South Indian Inscriptions"
    ],
    [
        "place-sanur-ancient-megalithic-iron-smelting-and-arsenal-haven",
        "center_of",
        "concept-pattern-welded-forge-lamination-and-differential-blade-tempering",
        "geography",
        "Megalithic to Sangam",
        "Foremost regional center for iron smelting, blade manufacture, and weapon stockpiles",
        "Excavation records"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 26 Corpus 2: Pattern-Welded Bladesmithing, Bloomery Quenching & Weapons into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 26 Corpus 2: Pattern-Welded Bladesmithing, Bloomery Quenching & Weapons Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
