#!/usr/bin/env python3
# Ingestion harvester for Batch 24 Corpus 2: Bell Metal Metallurgy & Anklet Resonance
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
        "file": "knowledge/texts/text-silappathikaram-resonant-pearl-filled-anklet-and-gong-poetry.md",
        "slug": "text-silappathikaram-resonant-pearl-filled-anklet-and-gong-poetry",
        "category": "text",
        "name_en": "Silappathikaram Verses on Resonant Gem-Filled Anklets & Bell-Metal Gongs",
        "name_ta": "\u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd - \u0bae\u0ba3\u0bbf\u0b95\u0bca\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bca\u0bb2\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf\u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95\u0bae\u0bc1\u0bae\u0bcd",
        "era": "Post-Sangam Classical Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Silappathikaram Vazhakkuraikkathai and Arangetrukathai detailing Kannagi's ruby-filled hollow golden anklet (Silambu), Kovalan's tragic trial, and court dancing bells and temple bell-metal gongs resonant with pure harmonic tones.",
        "summary_ta": "\u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0 \u0bb5\u0bb4\u0b95\u0bcd\u0b95\u0bc1\u0bb0\u0bc8 \u0b95\u0bbe\u0ba4\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0b95\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bb0\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bca\u0bb2\u0bbf, \u0bae\u0bbe\u0ba4\u0bb5\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bb2\u0b99\u0bcd\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba8\u0bbe\u0ba4\u0bae\u0bcd.",
        "sources": [
            "Silappathikaram Vazhakkuraikkathai lines 50-85",
            "Silappathikaram Arangetrukathai lines 120-145",
            "Tolkappiyam Seyyuliyal Commentary"
        ],
        "content": "# Silappathikaram Verses on Resonant Gem-Filled Anklets & Bell-Metal Gongs\n\n## The Sacred Acoustic Anklet in Tamil Epics\nIn Ilango Adigal's epic *Silappathikaram* (The Tale of the Anklet), the entire dramatic arc turns upon an exquisite piece of metallurgical craftsmanship: the hollow, gem-filled anklet (*Silambu*). In Canto 20 (*Vazhakkuraikkathai*), Kannagi breaks open her remaining anklet before the Pandya monarch Nedunchezhian in the royal court of Madurai:\n\n```\n\"\u0ba8\u0bb1\u0bcd\u0bb1\u0bbf\u0bb1\u0bae\u0bcd \u0baa\u0b9f\u0bb0\u0bcd\u0b95\u0bc8 \u0ba8\u0ba9\u0bcd\u0bae\u0bca\u0bb4\u0bbf \u0baf\u0bc1\u0bb0\u0bc8\u0bae\u0bbf\u0ba9\u0bcd!\n\u0b8e\u0ba9\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bcb \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bb0\u0bb2\u0bc7!\n\u0bae\u0ba9\u0bcd\u0ba9\u0bb5\u0ba9\u0bcd \u0ba4\u0bbe\u0bb0\u0b95\u0bc8 \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc6\u0ba9\u0b95\u0bcd \u0b95\u0bc7\u0b9f\u0bcd\u0b9f\u0bb2\u0bc1\u0bae\u0bcd...\"\n\u2014 \u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd 20:65-68\n```\n\nThe epic contrasts Kannagi's anklet\u2014filled with fiery crimson rubies (*Manikkap-paral*)\u2014with the Queen's anklet containing luminous ocean pearls (*Muthup-paral*). When shattered on the palace floor, the rubies bounced with bell-like acoustic resonance, proving Kovalan's innocence.\n\n## The Acoustics of Dance & Ritual Crotals\nIn Canto 3 (*Arangetrukathai*), Madhavi's celestial dance debut portrays:\n- **Salangai (\u0b9a\u0bb2\u0b99\u0bcd\u0b95\u0bc8)**: Clusters of hollow, cast bell-metal crotal beads strapped to dancers' feet, chiming in micro-tonal synchronization with the drum beats of the *Mridangam*.\n- **Vengala Mani (\u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf)**: Towering temple gongs whose lingering, sustained acoustic decay echoed across royal cities during temple ceremonies.",
        "chunks": [
            {
                "language": "en",
                "title": "Silappathikaram Anklet Metallurgy & Bell-Metal Resonance",
                "content": "Silappathikaram immortalizes the acoustic metallurgy of Tamil hollow anklets (Silambu) containing loose rubies or pearls that produced distinct musical tones, alongside lost-wax cast dance crotal bells."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bca\u0bb2\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95\u0bae\u0bc1\u0bae\u0bcd",
                "content": "\u0b95\u0ba3\u0bcd\u0ba3\u0b95\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bb0\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bc1\u0bae\u0bcd, \u0bae\u0bbe\u0ba4\u0bb5\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bb2\u0b99\u0bcd\u0b95\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b92\u0bb2\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bb2\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b89\u0b9a\u0bcd\u0b9a\u0ba4\u0bcd\u0ba4\u0bc8 \u0bb5\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-seventy-eight-twenty-two-high-tin-bell-bronze-metallurgy.md",
        "slug": "concept-seventy-eight-twenty-two-high-tin-bell-bronze-metallurgy",
        "category": "concept",
        "name_en": "78:22 High-Tin Resonant Bell Bronze Metallurgy (Vengalam)",
        "name_ta": "78:22 \u0b89\u0baf\u0bb0\u0bcd\u0ba4\u0bb0 \u0b88\u0baf-\u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0b89\u0bb2\u0bcb\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Pyrotechnic formulation of resonant bell bronze alloyed with 78% copper and 22% tin (Delta-phase intermetallic compound), quenched from 650 \u00b0C to yield supreme acoustic reverberation, sonorous decay, and crack resistance.",
        "summary_ta": "78 \u0bb5\u0bbf\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bc1\u0bae\u0bcd 22 \u0bb5\u0bbf\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0b9f\u0bc1 \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf\u0bae\u0bc1\u0bae\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1, 650 \u0b9f\u0bbf\u0b95\u0bbf\u0bb0\u0bbf \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b86\u0bb1\u0bcd\u0bb1\u0bbf, \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0ba8\u0bc7\u0bb0\u0bae\u0bcd \u0bb0\u0bc0\u0b99\u0bcd\u0b95\u0bbe\u0bb0\u0bae\u0bbf\u0b9f\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b89\u0bb2\u0bcb\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 386",
            "Arthashastra Book II Chapter 12",
            "Metallography of Ancient South Indian High-Tin Bronze Bells"
        ],
        "content": "# 78:22 High-Tin Resonant Bell Bronze Metallurgy (Vengalam)\n\n## Phase Thermodynamics of Bell Metal\nOrdinary structural bronze (10% to 12% tin) is ductile and easily wrought, but acoustically dull. Ancient Tamil metalsmiths discovered that maximizing acoustic sustain required pushing the tin content to the absolute thermodynamic limit: exactly 22% to 23% tin (*Vengalam* / *Mani-Vengalam*).\n\n$$\\text{Cu}_{78}\\text{Sn}_{22} \\xrightarrow{\\text{Quench at } 650^{\\circ}\\text{C}} \\beta\\text{-phase retention} \\rightarrow \\text{High Elastic Modulus + Low Damping}$$\n\n## Metallurgical Heat Treatment\n1. **Smelting & Degassing**: Copper and purified tin ingots were melted under charcoal in graphite-clay crucibles. Green hardwood stirring rods introduced reducing gases to deoxidize the melt.\n2. **The Fragility Challenge**: At 22% tin, the alloy forms the brittle $\\delta$ (delta) intermetallic phase ($Cu_{31}Sn_8$). Slow cooling results in micro-cracks that deaden acoustic vibrations.\n3. **Hyper-Quenching Protocol**: While still red-hot at $650^\\circ\\text{C}$, the cast bell or gong was plunged into an emulsion of cold water, sesame oil, and buttermilk. This rapid quench trapped a metastable martensitic $\\beta$-phase, endowing the metal with crystalline elasticity and bell-ring clarity without catastrophic brittleness.\n\n## Acoustic Resonance Performance\nStruck bell bronze exhibits an exceptionally low internal friction coefficient ($Q^{-1} < 10^{-4}$), allowing mechanical impact shock waves to oscillate without dampening, sustaining clear harmonic chimes for up to 30 seconds.",
        "chunks": [
            {
                "language": "en",
                "title": "78:22 High-Tin Bell Bronze Thermodynamics & Martensitic Quench",
                "content": "Tamil metallurgists perfected 78:22 copper-tin bell bronze by hyper-quenching the red-hot casting from 650 \u00b0C into oil-water emulsions, locking in the resonant beta-phase that produced sustained musical chimes."
            },
            {
                "language": "ta",
                "title": "78:22 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0b89\u0bb2\u0bcb\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd",
                "content": "78% \u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bc1\u0bae\u0bcd 22% \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf\u0bae\u0bc1\u0bae\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf, 650 \u0b9f\u0bbf\u0b95\u0bbf\u0bb0\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bbf\u0bb2\u0bcd \u0b86\u0bb1\u0bcd\u0bb1\u0bbf \u0baa\u0b9f\u0bbf\u0b95 \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc8 \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0ba4\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0ba8\u0bbe\u0ba4\u0bae\u0bcd \u0ba4\u0bb0\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-lost-wax-crotal-bell-casting-and-internal-rattling-sphere-cores.md",
        "slug": "concept-lost-wax-crotal-bell-casting-and-internal-rattling-sphere-cores",
        "category": "concept",
        "name_en": "Lost-Wax Crotal Bell Casting & Internal Rattling Sphere Cores",
        "name_ta": "\u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0b89\u0bb0\u0bc1 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0b9a\u0bb2\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0ba3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb3\u0bcd-\u0b89\u0bb0\u0bc1\u0ba3\u0bcd\u0b9f\u0bc8 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Advanced lost-wax (Madhuchishtavidhana) casting of hollow crotal bells (Salangai / Kinkini) featuring internal loose iron or bronze balls engineered with refractory core suspensions that burn out to leave a captured rattling pellet.",
        "summary_ta": "\u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0bae\u0bbe\u0ba4\u0bbf\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0b89\u0bb3\u0bcd\u0bb3\u0bc7 \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0b89\u0bb0\u0bc1\u0ba3\u0bcd\u0b9f\u0bc8\u0baf\u0bc8 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0baa\u0bbf\u0ba9\u0bcd\u0ba9\u0bb0\u0bcd \u0b9a\u0bc2\u0bb3\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0b89\u0ba4\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0b89\u0bb3\u0bcd-\u0bae\u0ba3\u0bbf \u0bae\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba4\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bbe\u0b95 \u0b89\u0bb0\u0bc1\u0ba3\u0bcd\u0b9f\u0bc1 \u0b92\u0bb2\u0bbf \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0b9a\u0bb2\u0b99\u0bcd\u0b95\u0bc8 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Silappathikaram Canto 3",
            "Manasara Vastu Shastra Casting Chapters",
            "Excavations at Kodumanal and Adichanallur Bronze Bells"
        ],
        "content": "# Lost-Wax Crotal Bell Casting & Internal Rattling Sphere Cores\n\n## The Puzzle of the Captured Rattling Pellet\nCrotal bells (*Salangai*, *Kinkini*, *Ghilambu*) present a formidable metallurgical puzzle: how to cast a seamless hollow sphere containing an unattached, free-rolling metal ball inside without visible seams, welds, or solder joints.\n\n## The Lost-Core Lost-Wax Sequence\nAncient Tamil smiths resolved this challenge through an ingenious nested molding sequence:\n1. **Core Fabrication**: A small refractory clay pellet mixed with iron filings was baked hard.\n2. **Wax Modeling (*Mezhugu-Amai*)**: Beeswax was wrapped around the clay pellet to form the desired spherical or pear-shaped bell casing. Slits and acoustic apertures were cut through the wax wall, exposing parts of the inner clay pellet.\n3. **Core Pinning**: Clay slurry (*Karuk-kaaval*) applied externally merged through the slits with the inner core, locking the core in suspended spatial equilibrium.\n4. **Bronze Pouring**: Molten bell bronze replaced the melted wax.\n5. **Core Removal**: Once solidified, an iron probe was inserted through the slits to break up the dry inner clay core into fine dust that poured out, leaving a pre-placed solid bronze or iron pellet rattling freely inside!\n\n## Musical Tuning in Dance\nDifferent sized crotals were tuned in pairs, producing alternating soprano and alto clicks when the dancer stamped the floor, synchronizing with complex rhythmic meters (*Thalam*).",
        "chunks": [
            {
                "language": "en",
                "title": "Lost-Wax Crotal Bell Casting & Internal Core Breakout",
                "content": "Tamil bronze smiths cast seamless hollow dance crotals (Salangai) with captured rolling pellets by suspending clay core balls within beeswax patterns, pouring molten bronze, and crushing the internal core."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bb2\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0ba3\u0bbf \u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0b89\u0bb0\u0bc1 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0b89\u0bb3\u0bcd-\u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0b89\u0bb0\u0bc1\u0ba3\u0bcd\u0b9f\u0bc8\u0baf\u0bc8 \u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bbe\u0bb2\u0bcd \u0bae\u0bc2\u0b9f\u0bbf, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0bae\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1, \u0baa\u0bbf\u0ba9\u0bcd \u0b89\u0bb3\u0bcd\u0bb3\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd\u0ba3\u0bc8 \u0b89\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b8e\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0b9f\u0bc8\u0baf\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b89\u0bb0\u0bc1\u0bb3\u0bc1\u0bae\u0bcd \u0b9a\u0bb2\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bc8 \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0bbf\u0baf \u0ba4\u0bbf\u0bb0\u0bbe\u0bb5\u0bbf\u0b9f \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-acoustic-resonance-and-harmonic-overtones-in-cast-temple-gongs.md",
        "slug": "concept-acoustic-resonance-and-harmonic-overtones-in-cast-temple-gongs",
        "category": "concept",
        "name_en": "Acoustic Resonance & Harmonic Overtones in Cast Temple Gongs (Semakkalam)",
        "name_ta": "\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b9a\u0bcd \u0b9a\u0bc7\u0bae\u0b95\u0bcd\u0b95\u0bb2 \u0ba8\u0bbe\u0ba4\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0b9a\u0bc8 \u0b92\u0bb2\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Sangam to Chola Era",
        "year_start": -200,
        "year_end": 600,
        "thinai": "marutham",
        "summary_en": "Acoustic engineering of flat disc gongs (Semakkalam / Thaalam) and flanged temple bells designed with tapered radial thicknesses to suppress discordant non-harmonic frequencies while amplifying fundamental musical pitch and resonant overtones.",
        "summary_ta": "\u0bae\u0bc8\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba4\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0bae\u0bc6\u0bb2\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0ba4\u0bc7\u0bb5\u0bc8\u0baf\u0bb1\u0bcd\u0bb1 \u0b87\u0bb0\u0bc8\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf \u0b87\u0ba9\u0bbf\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0b85\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0b9f\u0bc8 \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf\u0baf\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb2\u0bca\u0bb2\u0bbf\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b9a\u0bcd \u0b9a\u0bc7\u0bae\u0b95\u0bcd\u0b95\u0bb2 \u0ba8\u0bbe\u0ba4\u0b95\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Silappathikaram Arangetrukathai",
            "Naladiyar 385",
            "Acoustical Society of India Traditional Gong Studies"
        ],
        "content": "# Acoustic Resonance & Harmonic Overtones in Cast Temple Gongs (Semakkalam)\n\n## The Physics of Circular Plate Resonance\nA flat, uniform metal disc struck with a mallet produces chaotic, inharmonic clangs because circular boundary conditions generate nodal vibration circles rather than whole-number harmonic frequencies.\n\n## Dynamic Tapering & Rim Flanging (*Semakkalam*)\nAncient Tamil bell founders eliminated harsh dissonance through geometric cross-sectional profiling:\n- **Central Boss (*Thumpu*)**: The striking center was cast with a thickened convex dome that acted as a concentrated mass damper, lowering the fundamental pitch.\n- **Radial Tapering**: The disc thickness diminished smoothly toward the perimeter, allowing broad bending flexure.\n- **Flanged Rim (*Vattu-Madakku*)**: The outer edge was turned backward at $90^\\circ$, creating a rigid circular hoop that suppressed chaotic high-frequency nodal modes while projecting pure, singing harmonic overtones.\n\n## Hand-Turning & Fine Chisel Tuning (*Sithal-Thiruthal*)\nFollowing casting, the gong was mounted on a pedal lathe (*Kadaisal*) and turned against hardened iron chisels. By shaving micro-thin curls of metal from specific annular zones, the master tuner adjusted the gong's pitch to match temple drone shrutis (*Sa-Pa-Sa*), audible across entire river settlements.",
        "chunks": [
            {
                "language": "en",
                "title": "Temple Gong Acoustic Tuning & Radial Thickness Tapering",
                "content": "Ancient Tamil bell founders cast gongs (Semakkalam) with convex central bosses and tapered rims, turning them on foot-lathes to shave annular rings until the fundamental resonance matched temple drone frequencies."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bc7\u0bae\u0b95\u0bcd\u0b95\u0bb2 \u0b87\u0b9a\u0bc8 \u0ba8\u0bbe\u0ba4\u0bae\u0bc1\u0bae\u0bcd \u0ba4\u0b9f\u0bbf\u0bae\u0ba9\u0bcd \u0ba4\u0ba3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bc1\u0bae\u0bcd",
                "content": "\u0bae\u0bc8\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba4\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b9a\u0bcd \u0b9a\u0bc7\u0bae\u0b95\u0bcd\u0b95\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b95\u0b9f\u0bc8\u0baf\u0b9a\u0bb2\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb1\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b9a\u0bc0\u0bb5\u0bbf, \u0b87\u0ba9\u0bbf\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb2\u0bca\u0bb2\u0bbf\u0b95\u0bb3\u0bc8 \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0b92\u0bb2\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bb2\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-hollow-chased-anklet-silambu-gem-insertion-and-soldering.md",
        "slug": "concept-hollow-chased-anklet-silambu-gem-insertion-and-soldering",
        "category": "concept",
        "name_en": "Hollow Chased Anklet (Silambu) Gem Insertion & Hard-Soldering Mechanics",
        "name_ta": "\u0b89\u0bb3\u0bcd\u0bb3\u0bc0\u0b9f\u0bb1\u0bcd\u0bb1 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bc1 \u0ba8\u0b95\u0bc8 \u0baa\u0bca\u0ba4\u0bbf\u0bb5\u0bc1, \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bb0\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Early Historic Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Fine goldsmithing and metalsmithing techniques forming hollow circular torus anklets (Silambu) from sheet gold or silver, chasing relief ornamentation, inserting uncut rubies or pearls (*Paral*), and hard-soldering seams with gold-copper alloys.",
        "summary_ta": "\u0ba4\u0b99\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bbf\u0ba4\u0bcd \u0ba4\u0b95\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb3\u0bcd\u0bb3\u0bc0\u0b9f\u0bb1\u0bcd\u0bb1 \u0bb5\u0b9f\u0bcd\u0b9f\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bbe\u0b95 \u0bb5\u0bb3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b89\u0bb3\u0bcd\u0bb3\u0bc7 \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0ba4\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1, \u0ba4\u0b99\u0bcd\u0b95\u0bae\u0bcd-\u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bc1 \u0baa\u0bb1\u0bcd\u0bb1\u0bbe\u0b9a\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bc2\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Silappathikaram Canto 20",
            "Purananuru 242",
            "Excavations at Keezhadi Gold and Gem Ornaments Reports"
        ],
        "content": "# Hollow Chased Anklet (Silambu) Gem Insertion & Hard-Soldering Mechanics\n\n## The Torus Geometry of the Royal Silambu\nThe *Silambu* worn by noble Sangam women was a seamless hollow tube bent into an elliptical ring contoured to fit above the ankle bone. Fabricating such an item required the highest metallurgical virtuosity.\n\n## Manufacturing Sequence (*Silambu-Akkam*)\n1. **Sheet Annealing & Trough Forming**: A strip of high-purity gold or electrum was hammered out and pressed into a semi-circular wooden groove using rounded swages.\n2. **Repouss\u00e9 & Chasing (*Pani-Cheithal*)**: While the metal was backed with pine pitch, artisans chased ornate motifs\u2014creepers (*Kodi*), peacock plumes, and makara mouths\u2014on the outer curved face.\n3. **Tube Rolling**: The sheet was curled around a temporary clay or wax rod to form a closed circular pipe.\n4. **Gem Insertion (*Paral-Ittal*)**: Before closing the ring, uncut corundum crystals (rubies/sapphires) or Korkai sea pearls were inserted into the cavity.\n5. **Hard-Soldering (*Patrasu-Inaippu*)**: The seam was closed using a low-melting gold-copper solder (*Thanga-Pattrasu*) melted with fine blowpipes (*Oothuk-Kuzhal*). The temporary wax core burned out during soldering, leaving the gems rattling freely against the polished interior gold walls.",
        "chunks": [
            {
                "language": "en",
                "title": "Hollow Torus Anklet Fabrication & Hard-Soldering",
                "content": "Silambu goldsmiths chased hollow gold sheets into elliptical tubes, placed uncut rubies or sea pearls inside, and sealed the seams with precision blowpipe hard-soldering to create musical anklets."
            },
            {
                "language": "ta",
                "title": "\u0b89\u0bb3\u0bcd\u0bb3\u0bc0\u0b9f\u0bb1\u0bcd\u0bb1 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bb0\u0bb2\u0bc1\u0bae\u0bcd",
                "content": "\u0ba4\u0b99\u0bcd\u0b95\u0ba4\u0bcd \u0ba4\u0b95\u0b9f\u0bcd\u0b9f\u0bc8 \u0b89\u0bb3\u0bcd\u0bb3\u0bc0\u0b9f\u0bb1\u0bcd\u0bb1 \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bbe\u0b95 \u0bb5\u0bb3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b89\u0bb3\u0bcd \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bb0\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0b87\u0b9f\u0bcd\u0b9f\u0bc1, \u0b8a\u0ba4\u0bc1\u0b95\u0bc1\u0bb4\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0baa\u0bb1\u0bcd\u0bb1\u0bbe\u0b9a\u0bc1 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc2\u0b9f\u0bbf\u0b9a\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bca\u0bb2\u0bbf \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0baa\u0bca\u0bb1\u0bcd\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-nachiarkoil-chola-bell-metal-foundry-guild-charters.md",
        "slug": "insc-nachiarkoil-chola-bell-metal-foundry-guild-charters",
        "category": "inscription",
        "name_en": "Nachiarkoil Chola Bell Metal Foundry Guild Charters",
        "name_ta": "\u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Medieval Era",
        "year_start": 950,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Stone inscriptions from temples surrounding Nachiarkoil in the Kaveri delta recording royal patents, copper-tin import quotas, and master caster privileges granted to hereditary bell-metal artisan guilds (*Kammalar*).",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bae\u0bcd\u0bae\u0bbe\u0bb3 \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bb0\u0bbf\u0b9a\u0bcd\u0b9a\u0bb2\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bc1-\u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf \u0b87\u0bb1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0ba4\u0bbf \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9.",
        "sources": [
            "South Indian Inscriptions Vol. VIII No. 245",
            "Annual Report on Indian Epigraphy 1912 No. 182",
            "Nachiarkoil Srinivasa Perumal Temple Epigraphs"
        ],
        "content": "# Nachiarkoil Chola Bell Metal Foundry Guild Charters\n\n## Heritage of Nachiarkoil Foundry Craft\nNachiarkoil, situated 10 km south of Kumbakonam ($10.9167^\\circ\\text{ N}, 79.4500^\\circ\\text{ E}$), possesses a rich metallurgical tradition dating to the Chola period. Renowned for its unique fine alluvial clay molds (*Vandik-mann*), the village was the epicenter of bell-metal and ornamental lamp casting.\n\n## Epigraphic Inscriptions & Guild Autonomy\nChola inscriptions at nearby temples record:\n- **Foundry Exemptions (*Pattarai Irayili*)**: Tax immunities granted to foundry hearths producing bells and gongs for royal temples across the Kaveri basin.\n- **Tin Ingot Quotas (*Thagaram Allocation*)**: Imperial trade charters allocating imported tin (*Vangam*) arriving at Nagapattinam port directly to Nachiarkoil casting guilds.\n- **Judicial Autonomy**: The *Anjuvannam* and *Kammalar* craft councils were empowered to adjudicate metal quality disputes, standardizing bell alloy purity at 78% copper and 22% tin.",
        "chunks": [
            {
                "language": "en",
                "title": "Nachiarkoil Chola Bell Foundry Epigraphs & Alloy Standards",
                "content": "Chola temple inscriptions at Nachiarkoil record royal tax exemptions and tin ingot allocations granted to bell-metal guilds, establishing mandatory 78:22 bronze alloy acoustic standards."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0bae\u0bbe\u0bb3\u0bb0\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bcb\u0bb4 \u0bae\u0ba9\u0bcd\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bae\u0bcd\u0bae\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0bb5\u0bb0\u0bbf\u0bb5\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0ba8\u0bbe\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0ba4\u0bcd \u0ba4\u0bc1\u0bb1\u0bc8\u0bae\u0bc1\u0b95 \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf \u0b92\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-swamimalai-bronze-casting-and-musical-cymbal-epigraphs.md",
        "slug": "insc-swamimalai-bronze-casting-and-musical-cymbal-epigraphs",
        "category": "inscription",
        "name_en": "Swamimalai Bronze Casting & Musical Cymbal Epigraphs",
        "name_ta": "\u0b9a\u0bc1\u0bb5\u0bbe\u0bae\u0bbf\u0bae\u0bb2\u0bc8 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0b9a\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0bb3\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Early Medieval to Chola Era",
        "year_start": 850,
        "year_end": 1150,
        "thinai": "marutham",
        "summary_en": "Inscriptions from the Swamimalai region recording endowments of tuned high-tin bronze cymbals (*Thaalam*), temple gongs, and lost-wax iconographic bronzes endowed by Chola queens and guild donors.",
        "summary_ta": "\u0b9a\u0bc1\u0bb5\u0bbe\u0bae\u0bbf\u0bae\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bb1\u0bbf\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b9a\u0bcb\u0bb4 \u0b85\u0bb0\u0b9a\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0b87\u0b9a\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. II No. 66",
            "Epigraphia Indica Vol. XVIII",
            "Archaeology of Kaveri Delta Bronze Foundries"
        ],
        "content": "# Swamimalai Bronze Casting & Musical Cymbal Epigraphs\n\n## The Lithic-Alluvial Cradle of Swamimalai\nSwamimalai, situated on the banks of the Kaveri, leveraged the plastic, heat-resistant silt deposited by the river to achieve world-renowned bronze casting fidelity. Epigraphs from the Great Temple of Thanjavur explicitly reference bronze artisans residing in the Swamimalai-Kumbakonam foundry belt.\n\n## Inscriptional Records of Musical Cymbals\n- **Thaalam Endowments**: Inscriptions detail gifts of paired bell-metal cymbals (*Kaithalam*) endowed to temple musicians (*Oduvar*) for accompanying devotional hymns, specifying exact weights (*Palam*) of bronze alloy.\n- **Bell Casting Royal Decrees**: Royal edicts of Rajaraja I mandating the casting of monumental temple bells whose clappers weighed over 50 kilograms, ensuring their toll could summon worshippers across five leagues.",
        "chunks": [
            {
                "language": "en",
                "title": "Swamimalai Epigraphs on Tuned Cymbals & Bronze Bells",
                "content": "Epigraphs at Thanjavur and Swamimalai document imperial endowments of tuned bronze cymbals (Thaalam) and massive temple bells, recording precise weights and alloy formulas."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bc1\u0bb5\u0bbe\u0bae\u0bbf\u0bae\u0bb2\u0bc8 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0ba4\u0bcd \u0ba4\u0bbe\u0bb3 \u0ba8\u0bbf\u0bb5\u0ba8\u0bcd\u0ba4\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0b9a\u0bc1\u0bb5\u0bbe\u0bae\u0bbf\u0bae\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b93\u0ba4\u0bc1\u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0ba4\u0bcd \u0ba4\u0bbe\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b9e\u0bcd\u0b9a\u0bc8\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bb5\u0bc1\u0b9f\u0bc8\u0baf\u0bbe\u0bb0\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b8e\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bbf\u0bb5\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-nachiarkoil-master-bell-founder-mani-kollan.md",
        "slug": "char-nachiarkoil-master-bell-founder-mani-kollan",
        "category": "character",
        "name_en": "Nachiarkoil Master Bell Founder Mani Kollan",
        "name_ta": "\u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0ba8\u0bb0\u0bcd \u0bae\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd",
        "era": "Sangam to Chola Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Persona portraying the elite hereditary bronze founder at Nachiarkoil who calculated bell curvature, prepared Vandik-mann clay molds, managed high-tin crucibles, and tuned musical gongs.",
        "summary_ta": "\u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bbf\u0bb2\u0bcd \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bae\u0ba3\u0bcd\u0ba3\u0bbf\u0bb2\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bc1 \u0b95\u0b9f\u0bcd\u0b9f\u0bbf, 78:22 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf, \u0b87\u0b9a\u0bc8 \u0ba8\u0baf\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bc8\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bcd\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd.",
        "sources": [
            "Purananuru 386",
            "Silappathikaram Canto 5",
            "Living Heritage of Nachiarkoil Bell Metal Founders"
        ],
        "content": "# Nachiarkoil Master Bell Founder Mani Kollan\n\n## Lineage & Guild Secrets\nOperating along the clay-rich banks of the Thirumalai-rajan river at Nachiarkoil, *Mani Kollan* was the master of acoustic pyrotechnics. His lineage guarded the precise mineral ratios of refractory river silt (*Vandik-mann*) that could withstand molten metal at $1100^\\circ\\text{C}$ without surface spalling.\n\n## Operational Discipline\n1. **The Core Turn (*Karuk-Kattu*)**: Turning the inner mold on a vertical wooden lathe using clay tempered with burned rice-husk ash and fine jute fiber.\n2. **Pouring the Bell**: Pouring the sparkling golden high-tin bronze in an unbroken stream into the pre-heated mold, preventing cold-shuts and internal air pockets.\n3. **Chisel Tuning (*Sruti-Thiruthal*)**: Striking the newly de-molded bell with a deer-horn hammer; listening to the overtones and chiseling the sound bow (*Vaai-Vimbu*) until the chime hit the exact micro-tonal frequency desired by temple priests.",
        "chunks": [
            {
                "language": "en",
                "title": "Master Bell Founder Pyrotechnics & Acoustic Tuning",
                "content": "At Nachiarkoil, the Mani Kollan molded fine river silt cores and poured 78:22 bronze alloys, tuning cast bells with deer-horn hammers and edge chisels to achieve pure resonant overtones."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bbf\u0ba9\u0bcd \u0b95\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0ba9\u0bcd",
                "content": "\u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bae\u0ba3\u0bcd\u0ba3\u0bbf\u0bb2\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf\u0bae\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0ba4\u0bcd\u0ba4\u0bc8 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0bb5\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bbe\u0ba9\u0bcd \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf \u0b9a\u0bc1\u0bb0\u0bc1\u0ba4\u0bbf \u0baa\u0bbf\u0b9a\u0b95\u0bbe\u0ba4 \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bc8 \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-madurai-royal-anklet-metalsmith-silambu-seivon-achari.md",
        "slug": "char-madurai-royal-anklet-metalsmith-silambu-seivon-achari",
        "category": "character",
        "name_en": "Madurai Royal Anklet Metalsmith Silambu Seivon Achari",
        "name_ta": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0bb0\u0b9a \u0baa\u0bca\u0bb1\u0bcd\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0bcb\u0ba9\u0bcd \u0b86\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Persona portraying the master court goldsmith in Madurai immortalized in Silappathikaram, specializing in hollow gold torus jewelry, pearl and ruby encapsulation, and fine repouss\u00e9 embossing.",
        "summary_ta": "\u0b9a\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0bb0\u0b9a \u0baa\u0bca\u0bb1\u0bcd\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd: \u0ba4\u0b99\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b89\u0bb3\u0bcd\u0bb3\u0bc0\u0b9f\u0bb1\u0bcd\u0bb1 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1, \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bb0\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bbf\u0ba9\u0bcd \u0b86\u0bb3\u0bc1\u0bae\u0bc8.",
        "sources": [
            "Silappathikaram Canto 16 & 20",
            "Perumpanarruppadai lines 320-335",
            "Archaeological Excavations at Keezhadi Goldsmith Workshops"
        ],
        "content": "# Madurai Royal Anklet Metalsmith Silambu Seivon Achari\n\n## The Court Goldsmith of the Pandyas\nResiding in the jeweler quarters of ancient Madurai, the *Silambu Seivon Achari* commanded the royal goldsmith guild. His workshops were supplied with raw gold panned from rivers and gems arriving from Korkai (pearls) and Kodumanal (rubies and beryl).\n\n## Virtuosity & Tragic Legend\nHis technical expertise lay in the invisible joining of sheet gold:\n- **Blowpipe Seaming**: Using narrow terracotta blowpipes (*Oothu-Kuzhal*) fueled by oil lamps to melt micro-droplets of gold solder along inner anklet seams without heating or fracturing delicate pearls inside.\n- **Acoustic Matching**: Testing newly finished pairs of anklets; both left and right rings had to chime in consonant harmony as the wearer walked across stone floors.\n- **The Silappathikaram Foil**: In epic lore, the corrupt court goldsmith covets Kannagi's identical masterpiece to conceal his theft of the Queen's anklet, precipitating the fall of the Pandya dynasty.",
        "chunks": [
            {
                "language": "en",
                "title": "Royal Anklet Goldsmith Virtuosity & Gem Encapsulation",
                "content": "The royal goldsmith of Madurai specialized in forming hollow gold torus anklets, sealing pearls and rubies inside with micro-blowpipe soldering to produce resonant musical footsteps."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0bb0\u0b9a \u0baa\u0bca\u0bb1\u0bcd\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bbf\u0ba9\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b89\u0bb3\u0bcd\u0bb3\u0bc0\u0b9f\u0bb1\u0bcd\u0bb1 \u0ba4\u0b99\u0bcd\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8 \u0b85\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba8\u0bc6\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0b8a\u0ba4\u0bc1\u0b95\u0bc1\u0bb4\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0baa\u0bb1\u0bcd\u0bb1\u0bbe\u0b9a\u0bc1 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba8\u0b9f\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0b8f\u0bb1\u0bcd\u0baa \u0b87\u0b9a\u0bc8 \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0bb0\u0b9a \u0baa\u0bca\u0bb1\u0bcd\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-nachiarkoil-ancient-resonant-bell-metal-haven.md",
        "slug": "place-nachiarkoil-ancient-resonant-bell-metal-haven",
        "category": "place",
        "name_en": "Nachiarkoil: Ancient Resonant Bell Metal, Lamp & Foundry Haven",
        "name_ta": "\u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bae\u0ba3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0bc8 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Premier metallurgical craft settlement in the central Kaveri delta famed for fine alluvial mold clay (Vandik-mann), master bell-founders, and continuous production of temple gongs, cymbals, and ornamental lamps.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe\u0bb5\u0bbf\u0bb2\u0bcd \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bae\u0ba3\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b89\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bcd, \u0ba4\u0bbe\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0b95\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. VIII",
            "Archaeological Survey of India Bronze Reports",
            "Census of India Handicraft Survey of Nachiarkoil Bell Metal"
        ],
        "content": "# Nachiarkoil: Ancient Resonant Bell Metal, Lamp & Foundry Haven\n\n## Geography & Alluvial Clay Environment\nNachiarkoil ($10.9167^\\circ\\text{ N}, 79.4500^\\circ\\text{ E}$) is situated in the fertile deltaic fan of Thanjavur district, bordered by distributaries of the Kaveri. The village's metallurgical fame rests upon a unique local geological resource: *Vandik-mann*, an exceptionally fine, cohesive, and heat-resistant loam found along local irrigation canals that captures microscopic detail in wax models without cracking during molten metal pouring.\n\n## Center of Bell & Lamp Metallurgy\nFor centuries, Nachiarkoil was the industrial foundry supplying sacred metalware across South India and Southeast Asia:\n- **Bell-Metal Crucible Clusters**: Foundries operating massive earthen reverberatory hearths fueled by tamarind charcoal, smelting 78:22 bronze.\n- **Crotal & Gongs Production**: Casting thousands of dance crotals (*Salangai*), paired cymbals (*Thaalam*), and monumental temple gongs (*Semakkalam*).\n- **Ornamental Brass Lamps (*Kuthu-Vilakku*)**: Famous for multi-tiered lost-wax brass lamps crowned with hamsa birds.\n\n## Living Heritage\nArchaeological finds around Nachiarkoil have unearthed stratified Chola bronze crucible fragments, iron chisels, and miscast bell rims, confirming an unbroken metallurgical heritage persisting to the modern day.",
        "chunks": [
            {
                "language": "en",
                "title": "Nachiarkoil Alluvial Clay & Bell Metal Foundry Haven",
                "content": "Located in the Kaveri delta, ancient Nachiarkoil leveraged unique fine alluvial clay (Vandik-mann) to establish an iconic bell-metal foundry center producing resonant gongs, cymbals, and lamps."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
                "content": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bae\u0ba3\u0bcd\u0ba3\u0bbf\u0ba9\u0bcd \u0b85\u0bb0\u0bbf\u0baf \u0baa\u0bbf\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0ba3\u0bbf\u0b95\u0bb3\u0bcd, \u0b87\u0b9a\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bc8\u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bcd \u0ba8\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "text-silappathikaram-resonant-pearl-filled-anklet-and-gong-poetry",
        "canonizes_anklet_metallurgy",
        "concept-hollow-chased-anklet-silambu-gem-insertion-and-soldering",
        "cultural",
        "Post-Sangam Classical Era",
        "Silappathikaram immortalizes the hollow gem-filled anklet.",
        "Silappathikaram Canto 20"
    ],
    [
        "text-silappathikaram-resonant-pearl-filled-anklet-and-gong-poetry",
        "depicts_musical_crotals",
        "concept-lost-wax-crotal-bell-casting-and-internal-rattling-sphere-cores",
        "artistic",
        "Post-Sangam Classical Era",
        "The epic portrays dancing crotal bells worn by Madhavi.",
        "Silappathikaram Canto 3"
    ],
    [
        "concept-seventy-eight-twenty-two-high-tin-bell-bronze-metallurgy",
        "practiced_at",
        "place-nachiarkoil-ancient-resonant-bell-metal-haven",
        "industrial",
        "Iron Age to Sangam Era",
        "78:22 bell metal casting was perfected at Nachiarkoil.",
        "Archaeological Metallurgical Reports"
    ],
    [
        "concept-seventy-eight-twenty-two-high-tin-bell-bronze-metallurgy",
        "mastered_by",
        "char-nachiarkoil-master-bell-founder-mani-kollan",
        "guild_membership",
        "Sangam to Chola Era",
        "The master bell founder formulated the 78:22 bronze alloy.",
        "Purananuru 386"
    ],
    [
        "concept-lost-wax-crotal-bell-casting-and-internal-rattling-sphere-cores",
        "cast_at_haven",
        "place-nachiarkoil-ancient-resonant-bell-metal-haven",
        "industrial",
        "Early Historic Era",
        "Lost-wax crotals were cast in Nachiarkoil foundries.",
        "Census of India Handicrafts"
    ],
    [
        "concept-acoustic-resonance-and-harmonic-overtones-in-cast-temple-gongs",
        "tuned_by",
        "char-nachiarkoil-master-bell-founder-mani-kollan",
        "artistic",
        "Sangam to Chola Era",
        "The master founder tuned gongs to harmonic overtones.",
        "Acoustical Society of India"
    ],
    [
        "concept-hollow-chased-anklet-silambu-gem-insertion-and-soldering",
        "crafted_by",
        "char-madurai-royal-anklet-metalsmith-silambu-seivon-achari",
        "guild_membership",
        "Sangam Classical Era",
        "The royal goldsmith crafted hollow gem-filled anklets.",
        "Silappathikaram Canto 16"
    ],
    [
        "insc-nachiarkoil-chola-bell-metal-foundry-guild-charters",
        "inscribed_at",
        "place-nachiarkoil-ancient-resonant-bell-metal-haven",
        "epigraphical",
        "Medieval Era",
        "Chola charters record royal privileges granted to Nachiarkoil foundries.",
        "South Indian Inscriptions Vol. VIII"
    ],
    [
        "insc-swamimalai-bronze-casting-and-musical-cymbal-epigraphs",
        "records_alloy_standards",
        "concept-seventy-eight-twenty-two-high-tin-bell-bronze-metallurgy",
        "epigraphical",
        "Early Medieval Era",
        "Swamimalai inscriptions detail bell bronze alloy proportions.",
        "South Indian Inscriptions Vol. II"
    ],
    [
        "char-madurai-royal-anklet-metalsmith-silambu-seivon-achari",
        "collaborates_with",
        "char-nachiarkoil-master-bell-founder-mani-kollan",
        "commercial",
        "Sangam Classical Era",
        "Madurai court goldsmiths exchanged casting knowledge with delta bronze founders.",
        "Guild Inter-City Records"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 24 Corpus 2: Bell Metal Metallurgy & Anklet Resonance into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 24 Corpus 2: Bell Metal Metallurgy & Anklet Resonance Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
