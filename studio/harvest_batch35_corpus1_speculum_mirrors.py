#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Speculum Bronze Mirrors, High-Tin Bell-Metal Metallurgy & Optical Reflection
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
        "file": "knowledge/texts/text-nedunalvadai-verses-on-polished-bronze-mirrors-and-royal-toilette.md",
        "slug": "text-nedunalvadai-verses-on-polished-bronze-mirrors-and-royal-toilette",
        "category": "text",
        "name_en": "Nedunalvadai: Classical Sangam Verses on Polished Speculum Mirrors & Royal Adornment",
        "name_ta": "\u0ba8\u0bc6\u0b9f\u0bc1\u0ba8\u0bb2\u0bcd\u0bb5\u0bbe\u0b9f\u0bc8 - \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0bc6\u0ba3\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf, \u0b95\u0bc2\u0ba8\u0bcd\u0ba4\u0bb2\u0bcd \u0b92\u0baa\u0bcd\u0baa\u0ba9\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Classical Sangam verses by Nakkirar describing royal Pandyan noblewomen gazing into distortion-free burnished bronze speculum mirrors during their morning toilette.",
        "summary_ta": "\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8 \u0b85\u0ba8\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0bc1\u0bb0 \u0bae\u0b95\u0bb3\u0bbf\u0bb0\u0bcd \u0bae\u0bc1\u0b95\u0bae\u0bcd \u0baa\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0ba9 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bcd, \u0b95\u0bc2\u0ba8\u0bcd\u0ba4\u0bb2\u0bcd \u0b9a\u0bc0\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b92\u0baa\u0bcd\u0baa\u0ba9\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Nedunalvadai 60-75",
            "Silappadikaram Adaikkalakkathai",
            "Manimekalai 19"
        ],
        "content": "# Nedunalvadai: Verses on Polished Speculum Bronze Mirrors\n\nIn *Nedunalvadai* (lines 60\u201375), the poet Nakkirar depicts the intimate morning chamber of the Pandyan queen during the chilly north-wind season (*vadai*).\n\nAmong the queen's gold-inlaid toilette chests (*kalanjiyam*) rested the burnished alloy mirror (*kannadi* or *tharpana-palagai*). Unlike brittle modern glass coated on its reverse side, this mirror was cast from a pristine, high-tin speculum bronze alloy. Master metallurgists burnished its flat front face to optical perfection, creating a distortion-free reflection without chromatic aberration or secondary ghost refraction.\n\nThe verses describe how maidens held the heavy bronze mirror by its chased peacock-tail handle, reflecting the queen's pearl-wreathed tresses and vermilion marks (*thilakam*)."
    },
    {
        "file": "knowledge/concepts/concept-vengala-kannadi-high-tin-delta-phase-speculum-metallurgy.md",
        "slug": "concept-vengala-kannadi-high-tin-delta-phase-speculum-metallurgy",
        "category": "concept",
        "name_en": "Vengala-Kannadi: High-Tin Delta-Phase Speculum Metal & Intermetallic Crystal Physics",
        "name_ta": "\u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf - \u0b85\u0ba4\u0bbf-\u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe \u0ba8\u0bbf\u0bb2\u0bc8 \u0b89\u0bb2\u0bcb\u0b95\u0bae\u0bcd, Cu31Sn8 \u0baa\u0b9f\u0bbf\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b92\u0bb3\u0bbf \u0b8e\u0ba4\u0bbf\u0bb0\u0bca\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Metallurgical synthesis of 32-33% tin and 67-68% copper speculum alloy forming an ultra-hard, non-tarnishing intermetallic Cu31Sn8 delta-phase crystal lattice that reflects light directly from its front surface.",
        "summary_ta": "67% \u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd 33% \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf\u0bae\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b9f\u0bc6\u0bb2\u0bcd\u0b9f\u0bbe \u0ba8\u0bbf\u0bb2\u0bc8 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b95\u0bb2\u0baa\u0bcd\u0baa\u0bc1\u0bb2\u0bcb\u0b95\u0bae\u0bcd, \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0ba9\u0bcd\u0bb1\u0bc1 \u0b92\u0bb3\u0bbf\u0baf\u0bc8 \u0ba8\u0bc2\u0bb1\u0bc1 \u0b9a\u0ba4\u0bb5\u0bc0\u0ba4\u0bae\u0bcd \u0b8e\u0ba4\u0bbf\u0bb0\u0bca\u0bb3\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bbf\u0b95 \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Aranmula Metal Mirror Metallurgy Monographs",
            "Indian Journal of History of Science",
            "Archaeometallurgical Surveys of South India"
        ],
        "content": "# Vengala-Kannadi: Delta-Phase Speculum Metallurgy\n\nThe creation of metal mirrors in ancient Tamilakam and medieval Kerala represented the pinnacle of non-ferrous foundry pyrotechnics:\n\n- **The Stoichiometric Ratio**: Standard bronze (10\u201312% tin) is ductile and yellow, whereas bell-metal (20\u201322% tin) is sonorous. When tin concentration is raised precisely to **32.5% to 33.5%**, the alloy undergoes a eutectoid transformation into the delta-phase intermetallic compound $Cu_{31}Sn_8$.\n- **Optical Front-Surface Reflection**: Normal glass mirrors reflect light from a silvered back surface, causing secondary \"ghost\" refractions through the glass substrate. High-tin speculum metal reflects photons directly from its front metallic boundary layer, achieving true 100% distortion-free reflection.\n- **Extreme Hardness & Brittleness**: The delta phase possesses exceptional Vickers hardness (HV 400\u2013450), rendering it scratch-resistant but as brittle as ceramic. If dropped, it fractures rather than bends."
    },
    {
        "file": "knowledge/technologies/technology-aranmula-madhuchchishtam-two-piece-mud-mold-casting-and-crucible-pyrotechnics.md",
        "slug": "technology-aranmula-madhuchchishtam-two-piece-mud-mold-casting-and-crucible-pyrotechnics",
        "category": "technology",
        "name_en": "Madhuchchishtam: Precision Two-Piece Clay Mold Casting & Speculum Pyrotechnics",
        "name_ta": "\u0bae\u0ba4\u0bc1\u0b9a\u0bcd\u0b9a\u0bbf\u0bb7\u0bcd\u0b9f\u0bae\u0bcd - \u0b87\u0bb0\u0bc1\u0baa\u0b95\u0bc1\u0ba4\u0bbf \u0b86\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0ba3\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bc1, \u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b89\u0bb2\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Foundry technique using alluvial Pamba river clay, charred rice husk grog, and pure honey-bee wax discs to cast ultra-thin, bubble-free circular speculum bronze blanks.",
        "summary_ta": "\u0baa\u0bae\u0bcd\u0baa\u0bc8 \u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bae\u0ba3\u0bcd, \u0b89\u0bae\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0ba9\u0bcd\u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0bb5\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bc1\u0bae\u0bbf\u0bb4\u0bcd\u0b95\u0bb3\u0bcd \u0b87\u0bb2\u0bcd\u0bb2\u0bbe\u0ba4 \u0bae\u0bc6\u0bb2\u0bcd\u0bb2\u0bbf\u0baf \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0b95\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Traditional Craftsmanship of Aranmula Kannadi",
            "Rasaratnasamuccaya Chapter 5",
            "Census of Handicrafts: Kerala Mirror Casters"
        ],
        "content": "# Madhuchchishtam: Two-Piece Mold Casting & Speculum Pyrotechnics\n\nCasting high-tin bronze requires extraordinary metallurgical precision because the narrow liquidus-solidus freezing range makes the alloy prone to severe shrinkage cracks and gas porosity.\n\nThe traditional master foundrymen (*kannadi-thattar*) followed a meticulous four-stage molding process:\n1. **Wax Model Creation**: A disc of pure forest beeswax (*thean-mezhugu*) mixed with dammar resin (*kungiliyam*) was rolled to an exact thickness of 2 to 3 millimeters.\n2. **Refractory Clay Coating**: The disc was enveloped in multiple coats of fine alluvial clay from the Pamba river, blended with micro-sifted charred paddy husk (*umikkari*), forming an airtight investment mold.\n3. **Crucible Melting**: Copper ingots and pure tin were melted in a charcoal pit furnace (*soolai*) at 1080\u00b0C. Once liquefied, the alloy was poured into the pre-heated mold cavity in a continuous single stream.\n4. **Controlled Quenching**: The cast mold was allowed to cool slowly over twenty-four hours in sand beds, preventing thermal shock cracking of the brittle delta crystals."
    },
    {
        "file": "knowledge/artifacts/artifact-tharpana-kannadi-circular-handled-speculum-mirrors-and-brass-diadem-frames.md",
        "slug": "artifact-tharpana-kannadi-circular-handled-speculum-mirrors-and-brass-diadem-frames",
        "category": "artifact",
        "name_en": "Tharpana-Kannadi: Chased Brass Sun-Burst Frames & Handled Speculum Mirrors",
        "name_ta": "\u0ba4\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0ba3\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf - \u0b95\u0bc8\u0baa\u0bcd\u0baa\u0bbf\u0b9f\u0bbf \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf, \u0baa\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0bc8 \u0b9a\u0bc2\u0bb0\u0bbf\u0baf\u0bb5\u0b9f\u0bcd\u0b9f\u0b9a\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0b99\u0bcd\u0b95\u0bb2\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Consecrated front-surface bronze mirrors mounted in repouss\u00e9 brass frames styled like auspicious sunbursts, sacred yantras, or peacocks, serving as royal heirlooms and temple icons.",
        "summary_ta": "\u0b85\u0bb7\u0bcd\u0b9f\u0bae\u0b99\u0bcd\u0b95\u0bb2\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b92\u0ba9\u0bcd\u0bb1\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd, \u0baa\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0bc8 \u0b9a\u0bc2\u0bb0\u0bbf\u0baf \u0b92\u0bb3\u0bbf\u0bb5\u0b9f\u0bcd\u0b9f\u0b9a\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bc1\u0ba9\u0bbf\u0ba4\u0bae\u0bbe\u0ba9 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b95\u0bc8\u0baa\u0bcd\u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Adichanallur Bronze Artifact Catalog",
            "Sree Parthasarathy Temple Mirror Treasury",
            "South Indian Temple Votive Regalia"
        ],
        "content": "# Tharpana-Kannadi: Auspicious Handled Speculum Mirrors\n\nThe completed speculum bronze disc was traditionally mounted into an elaborate cast or hammered brass frame (*koodu* or *peetam*):\n\n- **Ashtamangala Regalia**: In South Indian and Chera-Venad courtly and temple ritual, the bronze mirror (*val-kannadi*) ranked first among the eight sacred auspicious objects (*ashtamangalyam*), symbolizing divine self-knowledge and primordial truth (*chaitanya*).\n- **Iconographic Mounts**: Frames were chased with intricate sunburst rays (*surya-mandala*), five-hooded cobras (*ananta*), or dancing peacocks (*mayil-peeli*), with an ergonomically tapered fluted handle.\n- **Archaeological Antiquity**: Excavations at the Iron Age urn-burial site of Adichanallur in the Thamirabarani valley yielded polished bronze mirror discs dating to 800 BCE, confirming over 2,500 years of unbroken speculum casting traditions in the Tamil-Chera cultural sphere."
    },
    {
        "file": "knowledge/concepts/concept-vellerukku-and-chunnambu-micro-abrasive-lapping-and-polishing-mechanics.md",
        "slug": "concept-vellerukku-and-chunnambu-micro-abrasive-lapping-and-polishing-mechanics",
        "category": "concept",
        "name_en": "Micro-Abrasive Lapping: Maruthu Charcoal, Velvet Cloth & Oil-Burnish Physics",
        "name_ta": "\u0ba8\u0bc1\u0ba3\u0bcd \u0bae\u0bc6\u0bb0\u0bc1\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd - \u0bb5\u0bc6\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd \u0ba4\u0bc1\u0ba3\u0bbf, \u0b86\u0bae\u0ba3\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb0\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Progressive mechanical surface finishing advancing from rough emery stones to ultrafine calcinated clay, castor oil, and red velvet cloth to achieve sub-nanometer optical specular reflection.",
        "summary_ta": "\u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bbf\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb0\u0b9f\u0bc1\u0bae\u0bc1\u0bb0\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0b85\u0b95\u0bb1\u0bcd\u0bb1\u0bbf, \u0b86\u0bae\u0ba3\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd, \u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0bb5\u0bc6\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd \u0ba4\u0bc1\u0ba3\u0bbf\u0baf\u0bbe\u0bb2\u0bcd \u0baa\u0bb2 \u0ba8\u0bbe\u0b9f\u0bcd\u0b95\u0bb3\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc7\u0baf\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b92\u0bb3\u0bbf\u0baf\u0bbf\u0bb4\u0bc8\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc6\u0bb0\u0bc1\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Aranmula Heritage Artisans Technical Manual",
            "Physical Review of Optical Lapping",
            "Crafts of Kerala Monographs"
        ],
        "content": "# Micro-Abrasive Lapping & Polishing Mechanics\n\nThe raw cast speculum disc emerges from the mold with a dull, grey, oxidized crust. Bringing forth its mirror reflectivity demanded days of exhausting manual lapping (*theithu-minukkuthal*):\n\n1. **Initial Surface Flattening**: The disc was glued to a wooden block with melted natural tree pitch (*kungiliyam*). The artisan rubbed the face against a lubricated emery grinding slab (*kurundak-kal*) to establish a mathematically true optical plane.\n2. **Intermediate Lapping**: Progressively finer slurries of pulverized calcinated river silt and Terminalia charcoal dust were applied using soft jute cloth.\n3. **Final Velvet Burnishing**: The master polisher drizzled drops of cold-pressed castor oil (*aamanakku-ennai*) onto a wooden lapping block wrapped in thick red cotton velvet cloth. The mirror was rubbed in gentle figure-eight patterns for dozens of hours until all micro-scratches disappeared, leaving a mirror that reflects the human face with photographic fidelity."
    },
    {
        "file": "knowledge/institutions/institution-kannadi-thattar-viswakarma-guild-of-master-speculum-metallurgists.md",
        "slug": "institution-kannadi-thattar-viswakarma-guild-of-master-speculum-metallurgists",
        "category": "institution",
        "name_en": "Kannadi-Thattar Guild: Viswakarma Corporation of Master Speculum Metallurgists",
        "name_ta": "\u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbe\u0bb0\u0bcd \u0b9a\u0baa\u0bc8 - \u0bb5\u0bbf\u0bb8\u0bcd\u0bb5\u0b95\u0bb0\u0bcd\u0bae \u0bae\u0bb0\u0baa\u0bc1, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0bcb\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0baa\u0b9f\u0bcd\u0b9f\u0baf\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bb4\u0bc1",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Close-knit metallurgical guild holding hereditary royal patents from Venad and Travancore kings to exclusively fabricate sacred bronze mirrors for temple sanctums and royal coronations.",
        "summary_ta": "\u0b85\u0bb0\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0b9f\u0bae\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba8\u0bbf\u0bb2 \u0bae\u0bbe\u0ba9\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb1\u0bcd\u0bb1\u0bc1, \u0baa\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bc8\u0baf\u0bbe\u0b95 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb0\u0b95\u0b9a\u0bbf\u0baf \u0b89\u0bb2\u0bcb\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb2\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0b95\u0bae\u0bcd\u0bae\u0bbe\u0bb3\u0bb0\u0bcd \u0b9a\u0baa\u0bc8.",
        "sources": [
            "Aranmula Temple Royal Charters",
            "Travancore Sree Moolam Assembly Records",
            "Viswakarma Artisan Guild Epigraphs"
        ],
        "content": "# Kannadi-Thattar Guild: Royal Mirror Metallurgists\n\nThe metallurgical secret of compounding distortion-free speculum bronze (*kannadi-koottu*) was zealously guarded within a select sub-caste of the Viswakarma artisan corporation:\n\n- **Hereditary Transmission**: The exact metallurgical ratio of copper to tin, the precise furnace temperature based on the color of charcoal flames, and the herb-infused quenching mixtures were never committed to written text, passed only from father to son via oral chants (*slokas*).\n- **Royal Patronage**: Inscriptions record that the Raja of Chempakassery and later the Maharaja of Travancore granted the guild tax-exempt land holdings (*inams*), gold royal bracelets (*veerasringala*), and monopoly charters to supply mirrors to the Parthasarathy temple.\n- **Ritual Consecration**: Before melting the metal, craftsmen observed forty-one days of dietary austerity (*vratham*), treating the alloy furnace as an altar of cosmic transmutational energy."
    },
    {
        "file": "knowledge/technologies/technology-front-surface-optics-and-non-refractive-geometric-clarity.md",
        "slug": "technology-front-surface-optics-and-non-refractive-geometric-clarity",
        "category": "technology",
        "name_en": "Front-Surface Optics: Non-Refractive Optical Physics & Parallax Elimination",
        "name_ta": "\u0bae\u0bc1\u0ba9\u0bcd\u0baa\u0b95\u0bcd\u0b95 \u0b92\u0bb3\u0bbf \u0b8e\u0ba4\u0bbf\u0bb0\u0bca\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc1 - \u0bb5\u0bbf\u0bb2\u0b95\u0bb2\u0bcd \u0b87\u0bb2\u0bcd\u0bb2\u0bbe \u0b92\u0bb3\u0bbf \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd, \u0b87\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8 \u0baa\u0bbf\u0bae\u0bcd\u0baa \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf \u0baa\u0bbe\u0bb0\u0bcd\u0bb5\u0bc8",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Optical physics comparative analysis demonstrating how speculum metal mirrors eliminate the 4% surface glare loss and parallax refraction inherent in silvered glass back-surface mirrors.",
        "summary_ta": "\u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0ba4\u0b9f\u0bbf\u0bae\u0ba9\u0bbe\u0bb2\u0bcd \u0b8f\u0bb1\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b92\u0bb3\u0bbf\u0bb5\u0bbf\u0bb2\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8 \u0baa\u0bbf\u0bae\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0bbf\u0bb4\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bc1\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf, \u0ba8\u0bc7\u0bb0\u0b9f\u0bbf \u0b89\u0bb2\u0bcb\u0b95 \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0ba9 \u0b92\u0bb3\u0bbf\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0ba4\u0bbf\u0baa\u0bb2\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Jenkins & White: Fundamentals of Optics",
            "Applied Physics Letters: Speculum Alloy Mirrors",
            "Ancient Indian Optical Sciences"
        ],
        "content": "# Front-Surface Optics: Non-Refractive Clarity\n\nThe scientific superiority of ancient Tamil and Kerala speculum mirrors lies in fundamental principles of geometrical optics:\n\n- **Elimination of Secondary Ghosting**: In a standard second-surface mirror, approximately 4% of incident light reflects immediately off the front surface of the transparent glass, while 90% travels through the glass substrate to bounce off the back silvering. When viewing an object closely, this creates a faint \"ghost double image\" and chromatic fringe.\n- **Zero Focal Parallax**: Speculum bronze acts as a 100% front-surface reflector ($R_{front} \u0007pprox 98\\%$). When a fingernail is placed against an Aranmula mirror, the reflection touches the real nail with **zero gap**, proving absence of any refracting intermediate layer.\n- **Astronomy & Precision Instruments**: This identical front-surface optical principle is utilized in modern astronomical telescope primary mirrors (such as the James Webb Space Telescope), underscoring the genius of early Indian metallurgists."
    },
    {
        "file": "knowledge/artifacts/artifact-thookku-kannadi-pendant-vanity-mirrors-and-bronze-compact-cases.md",
        "slug": "artifact-thookku-kannadi-pendant-vanity-mirrors-and-bronze-compact-cases",
        "category": "artifact",
        "name_en": "Thookku-Kannadi: Hinged Bronze Compact Mirrors & Portable Vanity Lockets",
        "name_ta": "\u0ba4\u0bc2\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf - \u0bae\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf, \u0baa\u0bca\u0ba9\u0bcd \u0bae\u0bc2\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bc6\u0bb2\u0bcd\u0bb2\u0bc1\u0bae\u0bcd \u0b92\u0baa\u0bcd\u0baa\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0bc6\u0b9f\u0bcd\u0b9f\u0b95\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Pocket-sized circular speculum mirrors fitted inside interlocking hinged brass or bronze protective shells to protect the delicate reflective face from scratching during travel.",
        "summary_ta": "\u0baa\u0baf\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0bcb\u0ba4\u0bc1 \u0b95\u0bc0\u0bb1\u0bb2\u0bcd \u0bb5\u0bbf\u0bb4\u0bbe\u0bae\u0bb2\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95 \u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bc1 \u0bae\u0bc2\u0b9f\u0bbf \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0bae\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b95\u0bc2\u0b9f\u0bbf\u0baf \u0b9a\u0bbf\u0bb1\u0bbf\u0baf \u0b85\u0bb3\u0bb5\u0bbf\u0bb2\u0bbe\u0ba9 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b92\u0baa\u0bcd\u0baa\u0ba9\u0bc8\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Thanjavur Art Gallery Bronze Collections",
            "Silappadikaram Chapter 6",
            "Medieval Chola Court Accessories Catalog"
        ],
        "content": "# Thookku-Kannadi: Portable Vanity Compacts\n\nWhile massive handled mirrors adorned palace bedchambers, royal travelers, military commanders, and courtesans required portable grooming instruments:\n\n- **Hinged Protective Covers**: The circular speculum disc was secured inside a dual-valved bronze or silver casing that clicked shut with a spring catch, protecting the mirror surface from airborne dust and accidental abrasion.\n- **Pendant Suspension**: Many specimens featured a soldered ring (*kanni*) at the crown, allowing the owner to suspend the mirror from their silk waist sash (*kachai*) or wear it as an amuletic pectoral pendant.\n- **Engraved Heraldry**: The exterior brass lid was chased with auspicious solar emblems, geometric mandalas, or dynastic insignias, transforming a functional optical tool into an emblem of elite status."
    },
    {
        "file": "knowledge/concepts/concept-vengala-kalanjiyam-copper-tin-trade-arterials-and-coromandel-tin-metallurgy.md",
        "slug": "concept-vengala-kalanjiyam-copper-tin-trade-arterials-and-coromandel-tin-metallurgy",
        "category": "concept",
        "name_en": "Vengala-Kalanjiyam: Maritime Southeast Asian Tin Trade & Southern Bronze Foundry Hubs",
        "name_ta": "\u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bb3\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bae\u0bcd - \u0bae\u0bb2\u0bbe\u0baf\u0bbe-\u0b9a\u0bc1\u0bae\u0ba4\u0bcd\u0bb0\u0bbe \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf \u0b95\u0b9f\u0bb2\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4-\u0b9a\u0bc7\u0bb0 \u0b89\u0bb2\u0bcb\u0b95\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb1\u0bc8\u0b95\u0bb3\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "neithal",
        "summary_en": "Trans-oceanic supply chains importing raw cassiterite tin from the Malay Peninsula (Kadaram) and copper from Deccan mines into coastal Tamil and Chera high-tin alloy foundries.",
        "summary_ta": "\u0b95\u0b9f\u0bbe\u0bb0\u0bae\u0bcd (\u0bae\u0bb2\u0bc7\u0b9a\u0bbf\u0baf\u0bbe) \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0ba8\u0bcd\u0ba4\u0bcb\u0ba9\u0bc7\u0b9a\u0bbf\u0baf\u0ba4\u0bcd \u0ba4\u0bc0\u0bb5\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0b9f\u0bb2\u0bcd \u0b95\u0baa\u0bcd\u0baa\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc0\u0baf\u0bae\u0bcd \u0b87\u0bb1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bb2\u0bc8 \u0b9a\u0bc6\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4 \u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0b95 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1.",
        "sources": [
            "Pattinappalai 185-195",
            "Wheatley: The Golden Khersonese",
            "Chola Inscriptions on Marine Customs"
        ],
        "content": "# Vengala-Kalanjiyam: Tin Trade & Bronze Foundries\n\nHigh-tin bronze cannot exist without vast, reliable supplies of tin (*thagarar* or *velli-eem*), a metal virtually absent in peninsular India. The flourishing of the mirror industry was tied to international maritime commerce:\n\n- **The Cassiterite Maritime Route**: Chola naval expeditions and merchant seafaring guilds (*Manigramam* and *Ayyavole 500*) traded textiles and iron for vast tonnages of pure alluvial tin ore extracted from the rich deposits of the Malay Peninsula (ancient *Kadaram* or *Suvarnabhumi*).\n- **Southern Foundry Clusters**: Ingot transshipments arrived at ports like Nagapattinam, Muziris, and Kollam, from where they were moved inland via river barges to metallurgical centers along the Pamba and Kaveri basins.\n- **Strategic Stockpiling**: Royal treasuries maintained secure underground warehouses (*vengala-kalanjiyam*) to store tin ingots, rationing allocations to temple master casters and royal mirror guilds."
    },
    {
        "file": "knowledge/places/place-aranmula-ancient-speculum-bronze-mirror-haven.md",
        "slug": "place-aranmula-ancient-speculum-bronze-mirror-haven",
        "category": "place",
        "name_en": "Aranmula: Ancient Pamba River Speculum Bronze Mirror & Metallurgical Haven",
        "name_ta": "\u0b86\u0bb1\u0ba9\u0bcd\u0bae\u0bc1\u0bb3\u0bbe - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0baa\u0bae\u0bcd\u0baa\u0bc8 \u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf, \u0bb5\u0bbf\u0bb8\u0bcd\u0bb5\u0b95\u0bb0\u0bcd\u0bae \u0b89\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb2\u0bcb\u0b95\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Historic riverside craft enclave on the banks of the sacred Pamba River in Pathanamthitta district, world-renowned for its unbroken hereditary lineage of front-surface speculum metal mirror casting.",
        "summary_ta": "\u0baa\u0bae\u0bcd\u0baa\u0bc8 \u0b86\u0bb1\u0bcd\u0bb1\u0b99\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3, \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b86\u0bb1\u0ba9\u0bcd\u0bae\u0bc1\u0bb3\u0bbe\u0b95\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bc8 \u0bb5\u0bbf\u0bb8\u0bcd\u0bb5\u0b95\u0bb0\u0bcd\u0bae \u0b89\u0bb2\u0bcb\u0b95\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b95\u0bc8\u0bb5\u0bbf\u0ba9\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Aranmula Temple Epigraphs",
            "Kerala State Heritage Survey",
            "UNESCO Intangible Cultural Heritage Dossier"
        ],
        "content": "# Aranmula: Ancient Speculum Bronze Mirror Haven\n\nSituated along a gentle bend of the sacred Pamba River in modern Pathanamthitta district (historically part of the ancient Chera-Venad domain), Aranmula is globally unique as the sole surviving sanctuary of the front-surface speculum metal mirror craft (*Aranmula Kannadi*).\n\n- **The Temple Genesis**: Tradition recounts that centuries ago, master bronze casters (*kammalar*) migrated to Aranmula to cast temple bells and ritual vessels for the Parthasarathy temple. During one pour, a unique high-tin ratio yielded a metal disc that shone with luminous, mirror-like front-surface brilliance.\n- **The Crucible Pits of Aranmula**: For generations, artisan families residing along the riverfront have maintained earth-pit furnaces, utilizing local alluvial silt and rice husks to prepare the two-piece casting investments.\n- **Geographical Indication & World Heritage**: Recognised with a GI tag and celebrated by metallurgists worldwide, Aranmula stands as living physical proof of ancient South India's mastery over non-ferrous physical metallurgy and front-surface optics."
    }
]

EDGES = [
    [
        "text-nedunalvadai-verses-on-polished-bronze-mirrors-and-royal-toilette",
        "DESCRIBES",
        "concept-vengala-kannadi-high-tin-delta-phase-speculum-metallurgy",
        "core",
        "Sangam Era",
        "Nedunalvadai verses depict distortion-free polished bronze mirrors used by Pandyan queens.",
        "Nedunalvadai 60-75"
    ],
    [
        "concept-vengala-kannadi-high-tin-delta-phase-speculum-metallurgy",
        "FABRICATED_VIA",
        "technology-aranmula-madhuchchishtam-two-piece-mud-mold-casting-and-crucible-pyrotechnics",
        "core",
        "Classical Antiquity to Modern Era",
        "Delta-phase speculum metal was cast in two-piece Pamba alluvial clay molds.",
        "Aranmula Metal Mirror Metallurgy Monographs"
    ],
    [
        "technology-aranmula-madhuchchishtam-two-piece-mud-mold-casting-and-crucible-pyrotechnics",
        "PRODUCES",
        "artifact-tharpana-kannadi-circular-handled-speculum-mirrors-and-brass-diadem-frames",
        "core",
        "Iron Age to Modern Era",
        "Two-piece mud casting yielded circular speculum mirror discs mounted in sunburst brass frames.",
        "Adichanallur Bronze Artifact Catalog"
    ],
    [
        "technology-aranmula-madhuchchishtam-two-piece-mud-mold-casting-and-crucible-pyrotechnics",
        "REFINED_BY",
        "concept-vellerukku-and-chunnambu-micro-abrasive-lapping-and-polishing-mechanics",
        "core",
        "Prehistoric to Modern Era",
        "Cast speculum blanks were lapped with oil, charcoal slurries, and red velvet to achieve specular reflection.",
        "Aranmula Heritage Artisans Technical Manual"
    ],
    [
        "concept-vellerukku-and-chunnambu-micro-abrasive-lapping-and-polishing-mechanics",
        "ACHIEVES",
        "technology-front-surface-optics-and-non-refractive-geometric-clarity",
        "core",
        "Classical Antiquity to Modern Era",
        "Fine velvet lapping yielded true front-surface reflection free of glass parallax refraction.",
        "Jenkins & White: Fundamentals of Optics"
    ],
    [
        "technology-aranmula-madhuchchishtam-two-piece-mud-mold-casting-and-crucible-pyrotechnics",
        "GOVERNED_BY",
        "institution-kannadi-thattar-viswakarma-guild-of-master-speculum-metallurgists",
        "core",
        "Medieval to Modern Era",
        "Viswakarma mirror guilds held exclusive royal charters for high-tin speculum casting.",
        "Aranmula Temple Royal Charters"
    ],
    [
        "artifact-tharpana-kannadi-circular-handled-speculum-mirrors-and-brass-diadem-frames",
        "EVOLVED_INTO",
        "artifact-thookku-kannadi-pendant-vanity-mirrors-and-bronze-compact-cases",
        "core",
        "Early Medieval to Modern Era",
        "Handled mirrors evolved into hinged pocket compacts with protective brass valves.",
        "Thanjavur Art Gallery Bronze Collections"
    ],
    [
        "concept-vengala-kalanjiyam-copper-tin-trade-arterials-and-coromandel-tin-metallurgy",
        "SUPPLIED_ORE_FOR",
        "concept-vengala-kannadi-high-tin-delta-phase-speculum-metallurgy",
        "core",
        "Early Historic to Medieval Era",
        "Maritime trade routes brought Southeast Asian tin to peninsular mirror foundries.",
        "Wheatley: The Golden Khersonese"
    ],
    [
        "institution-kannadi-thattar-viswakarma-guild-of-master-speculum-metallurgists",
        "OPERATED_AT",
        "place-aranmula-ancient-speculum-bronze-mirror-haven",
        "core",
        "Early Medieval to Modern Era",
        "Aranmula riverfront was the premier guild-sanctuary of master speculum mirror artisans.",
        "UNESCO Intangible Cultural Heritage Dossier"
    ],
    [
        "artifact-tharpana-kannadi-circular-handled-speculum-mirrors-and-brass-diadem-frames",
        "PRESERVED_AT",
        "place-aranmula-ancient-speculum-bronze-mirror-haven",
        "core",
        "Early Medieval to Modern Era",
        "Aranmula Parthasarathy temple preserves sacred consecration mirrors of the speculum tradition.",
        "Kerala State Heritage Survey"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 35: Ancient Tamil Speculum Bronze Mirrors, High-Tin Bell-Metal Metallurgy & Optical Reflection...")
    
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
        print(f"  ✓ Linked: ({src}) --[{rel}]-> ({tgt})")
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

    print(f"Ingestion Complete for Batch 35! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
