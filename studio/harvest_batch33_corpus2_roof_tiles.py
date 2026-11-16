#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Terracotta Roof Tiling, Interlocking Pantiles & Kiln Pyrotechnics
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
        "file": "knowledge/texts/text-pattinappalai-verses-on-tiled-mansions-and-fireproof-urban-roofs.md",
        "slug": "text-pattinappalai-verses-on-tiled-mansions-and-fireproof-urban-roofs",
        "category": "text",
        "name_en": "Pattinappalai: Classical Sangam Verses on Tiled Mansions & Fireproof Urban Roofs",
        "name_ta": "\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bc8 - \u0b93\u0b9f\u0bc1 \u0bb5\u0bc7\u0baf\u0bcd\u0ba8\u0bcd\u0ba4 \u0bae\u0bbe\u0b9f \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc0\u0baa\u0bcd\u0baa\u0bb1\u0bcd\u0bb1\u0bbe \u0ba8\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bb5\u0bbf\u0ba4\u0bc8\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Classical Sangam verses by Kadiyalur Uruthirankannanar describing the glittering tile-roofed multi-story mansions (maadam) of Kaveripoompattinam engineered to resist urban thatch fires.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bc7\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0baa\u0bb2 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bbe\u0b9f \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0ba4\u0bc0 \u0bb5\u0bbf\u0baa\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0baa\u0bcd\u0baa \u0b9a\u0bc6\u0bae\u0bcd\u0baa\u0bca\u0ba9\u0bcd \u0bb5\u0ba3\u0bcd\u0ba3 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0bb5\u0bc7\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0ba4\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bc8.",
        "sources": [
            "Pattinappalai 142-158",
            "Silappadikaram 5.10",
            "Nedunalvadai 100"
        ],
        "content": "# Pattinappalai: Classical Sangam Verses on Tiled Mansions\n\nIn Pattinappalai, composed by the Sangam poet Kadiyalur Uruthirankannanar, ancient Tamil literature documents the sophisticated ceramic urban architecture of the great Chola port city Kaveripoompattinam (Puhar).\n\nThe poet depicts multi-storied urban merchant residences (maadam and ezhunilaimadam) rising majestically along broad paved avenues. Unlike rural huts thatched with perishable palmyra leaves or straw, these metropolitan structures were clad in fireproof baked terracotta tiles (oodu).\n\nThe gleaming reddish roofs protected immense stocks of overseas goods against catastrophic city fires and torrential monsoon downpours, reflecting the mastery of architectural ceramic design in Early Historic Tamil urban centers."
    },
    {
        "file": "knowledge/concepts/concept-oodu-veythal-interlocking-clay-pantile-roofing-and-water-runoff-geometry.md",
        "slug": "concept-oodu-veythal-interlocking-clay-pantile-roofing-and-water-runoff-geometry",
        "category": "concept",
        "name_en": "Oodu-Veythal: Interlocking Clay Pantile Roofing & Water-Runoff Slope Geometry",
        "name_ta": "\u0b93\u0b9f\u0bc1 \u0bb5\u0bc7\u0baf\u0bcd\u0ba4\u0bb2\u0bcd - \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b87\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Ceramic roofing mechanics utilizing overlapping concave water-channel tiles (kaal-oodu) and convex cover tiles (kavizh-oodu) on pitch-sloped timber trusses to channel torrential monsoon rain.",
        "summary_ta": "\u0b85\u0b95\u0bb4\u0bbf \u0b93\u0b9f\u0bc1 (\u0b95\u0bbe\u0bb2\u0bcd \u0b93\u0b9f\u0bc1) \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb5\u0bbf\u0bb4\u0bcd \u0b93\u0b9f\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b92\u0ba9\u0bcd\u0bb1\u0ba9\u0bcd\u0bae\u0bc0\u0ba4\u0bc1 \u0b92\u0ba9\u0bcd\u0bb1\u0bc1 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf, \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bc0\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bbf\u0b9a\u0bc8\u0baf\u0bbe\u0bb2\u0bcd \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bc8 \u0bb5\u0b9f\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0b9a\u0bbf\u0bb5\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Pattinappalai 145",
            "Keezhadi Archaeological Tile Reports",
            "Tamil Architectural Engineering Studies"
        ],
        "content": "# Oodu-Veythal: Interlocking Clay Pantile Roofing Mechanics\n\nOodu-Veythal represents the traditional Tamil engineering science of ceramic tile roofing designed to withstand the intense thermal cycles and torrential cyclonic rains of South India.\n\nThe system utilized an ingenious pairing of curved terracotta tiles: concave under-tiles (kaal-oodu or aazh-oodu) laid with grooves facing upward along the roof pitch to act as high-velocity rainwater gutters, alternated with convex over-tiles (kavizh-oodu) overlapping the seam junctions like semi-cylindrical caps.\n\nCrafted with subtle tapered draft angles, the tiles locked together under their own weight on timber purlins without mortar or nails, allowing for thermal expansion and contraction during tropical heatwaves while providing instantaneous gravitational runoff during cloudbursts."
    },
    {
        "file": "knowledge/technologies/technology-soozhai-subterranean-downdraft-tile-firing-kiln-pyrotechnics.md",
        "slug": "technology-soozhai-subterranean-downdraft-tile-firing-kiln-pyrotechnics",
        "category": "technology",
        "name_en": "Soozhai: Subterranean Downdraft Tile-Firing Kiln Pyrotechnics & Thermal Insulation",
        "name_ta": "\u0b9a\u0bc2\u0bb3\u0bc8 - \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bc0\u0bb4\u0bcd\u0ba8\u0bcb\u0b95\u0bcd\u0b95\u0bc1 \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc2\u0bb3\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bae\u0bbf \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0b8e\u0bb0\u0bbf\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Subterranean ceramic firing kilns (soozhai) utilizing controlled downdraft flue circulation, slow cooling, and packed rice husk (umi) thermal insulation to vitrify terracotta tiles at 850-950\u00b0C.",
        "summary_ta": "\u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bc0\u0bb4\u0bcd\u0ba8\u0bcb\u0b95\u0bcd\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0bc2\u0bb3\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0ba8\u0bc6\u0bb2\u0bcd \u0b89\u0bae\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb1\u0b95\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 900\u00b0C \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba8\u0bbf\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1, \u0bb5\u0bbf\u0bb0\u0bbf\u0b9a\u0bb2\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b8e\u0bb0\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Keezhadi Industrial Kiln Excavations",
            "Sivaganga Pottery Survey",
            "Traditional Pyrotechnics Monograph"
        ],
        "content": "# Soozhai: Subterranean Downdraft Tile-Firing Kilns\n\nThe durability and water impermeability of Tamil terracotta roof tiles depended upon precise kiln pyrotechnics in subterranean furnaces known as soozhai.\n\nExcavated into the dry clay subsoil, the kiln featured a sunken combustion firebox, perforated brick floor grates, and curved downdraft flues that forced flames and superheated air down through stacked rows of green tiles before exiting perimeter chimneys. This draft geometry distributed uniform temperature throughout the chamber, eliminating cold spots.\n\nTiles were stacked on edge with intervening layers of fine rice husk (umi) that burned slowly without flame, generating steady incandescent radiant heat (850-950\u00b0C). The slow firing sintered the clay minerals into hard ceramic terracotta, followed by three days of sealed, oxygen-deprived cooling that prevented thermal shock cracking."
    },
    {
        "file": "knowledge/artifacts/artifact-kaal-oodu-and-muthugu-oodu-grooved-drainage-tiles-and-ridge-cap-seals.md",
        "slug": "artifact-kaal-oodu-and-muthugu-oodu-grooved-drainage-tiles-and-ridge-cap-seals",
        "category": "artifact",
        "name_en": "Kaal-Oodu & Muthugu-Oodu: Flanged Drainage Tiles, Locking Nibs & Ridge Cap Seals",
        "name_ta": "\u0b95\u0bbe\u0bb2\u0bcd \u0b93\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0ba4\u0bc1\u0b95\u0bc1 \u0b93\u0b9f\u0bc1 - \u0baa\u0bb3\u0bcd\u0bb3 \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0b93\u0b9f\u0bc1, \u0baa\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0bae\u0bc1\u0b95\u0b9f\u0bc1 \u0bae\u0bc2\u0b9f\u0bbf",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Standardized ceramic roof elements: flat flanged water-drainage tiles (kaal-oodu) with rear hanging nibs and parabolic ridge cap tiles (muthugu-oodu) sealing roof peaks.",
        "summary_ta": "\u0b95\u0bc2\u0bb0\u0bc8\u0b9a\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0ba9 \u0baa\u0bbf\u0ba9\u0bcd\u0baa\u0b95\u0bcd\u0b95 \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b89\u0b9a\u0bcd\u0b9a\u0bbf \u0bae\u0bc1\u0b95\u0b9f\u0bcd\u0b9f\u0bc8 \u0bae\u0bc2\u0b9f\u0bc1\u0bae\u0bcd \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0bae\u0bc1\u0ba4\u0bc1\u0b95\u0bc1 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Arikamedu Excavation Reports",
            "Keezhadi Archaeological Artifacts",
            "Indian Historical Ceramics Journal"
        ],
        "content": "# Kaal-Oodu & Muthugu-Oodu: Drainage Tiles & Ridge Caps\n\nArchaeological excavations across ancient Tamil sites (including Keezhadi, Arikamedu, and Kaveripoompattinam) have uncovered thousands of remarkably standardized architectural tile components.\n\nThe foundation unit was the kaal-oodu, a rectangular or flat S-shaped ceramic tile pressed with dual longitudinal drainage troughs and raised lateral flanges that interlocked snugly with adjacent tiles. The reverse face carried an integral clay lug or hanging nib that hooked over wooden roof battens without requiring metal fasteners.\n\nAt the roof peak, where sloping roof faces met, craftsmen installed muthugu-oodu (ridge cap tiles)\u2014large parabolic semi-cylindrical tiles bedded in lime mortar, creating an impermeable barrier against wind-driven rain while allowing hot attic air to vent safely from the ridge."
    },
    {
        "file": "knowledge/concepts/concept-man-padham-vaigai-alluvial-clay-aging-levigation-and-grog-tempering.md",
        "slug": "concept-man-padham-vaigai-alluvial-clay-aging-levigation-and-grog-tempering",
        "category": "concept",
        "name_en": "Man-Padham: Alluvial Clay Aging, Levigation & Quartz-Grog Tempering Science",
        "name_ta": "\u0bae\u0ba3\u0bcd \u0baa\u0ba4\u0bae\u0bcd - \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd, \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b85\u0bb2\u0b9a\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bb2\u0bcd \u0b95\u0bc1\u0bb4\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Geological clay processing methodology: harvesting riverbed plastic clays, weathering through wet-season levigation, and blending with pulverized ceramic grog to prevent drying shrinkage.",
        "summary_ta": "\u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b86\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd\u0ba3\u0bc8 \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf, \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b85\u0bb2\u0b9a\u0bbf \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0ba4\u0bcd \u0ba4\u0bc2\u0bb3\u0bcd (\u0b95\u0bc1\u0bb0\u0bbe\u0b95\u0bcd) \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbf\u0bb0\u0bbf\u0b9a\u0bb2\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf\u0baa\u0bcd \u0baa\u0bbf\u0b9a\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Manamadurai Pottery Ethnography",
            "Agastya Soil Sciences",
            "Keezhadi Ceramic Petrography"
        ],
        "content": "# Man-Padham: Alluvial Clay Levigation & Tempering\n\nProducing thin, warp-free terracotta roof tiles required sophisticated geotechnical clay preparation known as man-padham, developed over centuries along fertile riverbanks like the Vaigai and Kaveri.\n\nPotters harvested rich alluvial plastic clays (kazhimann) during summer months from dry river floodplains. The clay was slaked in large water tanks, allowing heavy grit and unweathered stones to settle, while the fine colloidal clay suspension was decanted into drying basins (levigation).\n\nTo control the high natural drying shrinkage of pure clay, craftsmen blended precise proportions of tempering agents: fine river quartz sand, sifted wood ash, and grog (pulverized baked terracotta pottery shards). The tempered clay was kneaded under bare feet for hours, aligning platelets to achieve optimum plasticity and green strength."
    },
    {
        "file": "knowledge/institutions/institution-kuyavar-chakri-guild-hereditary-corporation-of-master-tile-makers.md",
        "slug": "institution-kuyavar-chakri-guild-hereditary-corporation-of-master-tile-makers",
        "category": "institution",
        "name_en": "Kuyavar & Chakri Guild: Hereditary Corporation of Master Tile-Makers & Potters",
        "name_ta": "\u0b95\u0bc1\u0baf\u0bb5\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bbf\u0bb0\u0bbf \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1 - \u0baa\u0bbe\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bbf\u0baf \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bae\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Autonomous collegiate artisan guild of ceramic masters (Kuyavar, Velar, Chakri) holding municipal charters, clay-pit concessions, and state royal building contracts across Tamilakam.",
        "summary_ta": "\u0bae\u0ba3\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb5\u0bbe\u0bb0\u0bbf \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0b95\u0bb3\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bc1 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0ba4\u0bcd \u0ba4\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd/\u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8 \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0b95\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bc1\u0baf\u0bb5\u0bb0\u0bcd \u0ba4\u0ba9\u0bcd\u0ba9\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb1\u0bcd\u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1.",
        "sources": [
            "Manamadurai Epigraphs",
            "Chola Inscriptions on Kusavan-Kani",
            "South Indian Epigraphy Vol II"
        ],
        "content": "# Kuyavar & Chakri Guild: Master Tile-Makers Corporation\n\nArchitectural terracotta production was organized under the hereditary guild system of the Kuyavar or Velar corporations, documented in early Sangam poems and medieval Chola-Pandya epigraphy.\n\nGuild assemblies enjoyed recognized corporate rights: exclusive royal concessions to extract clay from designated lakebeds and river commons, tax-exempt residential quarters (kuyavan-theru), and kiln tax remissions (soozhai-vari). Master potters (chakrins) oversaw specialized divisions: mold-pressers, kiln tenders, and roof-laying artisans.\n\nThe guild guaranteed rigorous quality standards: testing fired tiles for ringing resonance and water absorption, and supplying millions of tiles for royal palaces, temple superstructures, granaries, and urban settlements across South India."
    },
    {
        "file": "knowledge/technologies/technology-achchu-palagai-hardwood-tile-molding-presses-and-wire-cutters.md",
        "slug": "technology-achchu-palagai-hardwood-tile-molding-presses-and-wire-cutters",
        "category": "technology",
        "name_en": "Achchu-Palagai: Hardwood Tile-Molding Presses, Wire Cutters & Drying Racks",
        "name_ta": "\u0b85\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bb2\u0b95\u0bc8 - \u0b95\u0b9f\u0bbf\u0ba9 \u0bae\u0bb0 \u0b93\u0b9f\u0bcd\u0b9f\u0bc1 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bbf \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Manual mass-production tooling: precision-machined hardwood open-face mold frames (achchu-palagai), bow-strung brass wire slab cutters, and shaded wicker drying racks.",
        "summary_ta": "\u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bb2\u0b95\u0bc8, \u0baa\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bbf \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb4\u0bb2\u0bbf\u0bb2\u0bcd \u0b9a\u0bc0\u0bb0\u0bbe\u0b95 \u0b89\u0bb2\u0bb0 \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Archaeological Excavation Toolsets",
            "Traditional Ceramic Technology Handbooks",
            "Madras Craft Survey"
        ],
        "content": "# Achchu-Palagai: Tile-Molding Presses & Tooling\n\nMass-producing thousands of identical interlocking tiles for large architectural projects required specialized hand tooling and forming jigs centered around the achchu-palagai.\n\nThe mold was an open-topped rectangular frame carved from seasoned Teak or Rosewood, internally lined with smooth brass plate to facilitate clean clay release. The mold bottom was profiled with reverse negative contours that imprinted drainage grooves and rear locking lugs into the wet clay slab.\n\nA lump of tempered clay was slapped vigorously into the frame, compacted with wooden mallets to eliminate air pockets, and planed flush with a bow-strung brass wire cutter (kambi-vetti). The formed tile was demolded onto a curved wooden form (palagai) to impart its drainage camber, then transferred to shaded wicker racks for slow, crack-free air curing before firing."
    },
    {
        "file": "knowledge/artifacts/artifact-chinnak-kol-curved-bamboo-slat-roof-truss-battens-and-tile-laths.md",
        "slug": "artifact-chinnak-kol-curved-bamboo-slat-roof-truss-battens-and-tile-laths",
        "category": "artifact",
        "name_en": "Chinnak-Kol: Seasoned Bamboo Slat Battens, Coir Lashing & Timber Roof Laths",
        "name_ta": "\u0b9a\u0bbf\u0ba9\u0bcd\u0ba9\u0b95\u0bcd \u0b95\u0bcb\u0bb2\u0bcd - \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd, \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b95\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0b9a\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Structural roof sub-framing: split seasoned bamboo battens (chinnak-kol / varichal) lashed with coconut coir twine across hardwood rafters to support interlocking tiles without nails.",
        "summary_ta": "\u0b95\u0b9f\u0bbf\u0ba9 \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0b9a\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b99\u0bcd\u0b95\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bbe\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd; \u0b86\u0ba3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b95\u0bbf\u0bb4\u0bcd\u0bb5\u0bbe\u0ba9 \u0bae\u0bb0\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0bae\u0bcd.",
        "sources": [
            "Silappadikaram Uraiperukathai",
            "Traditional Carpentry Manuals",
            "Madras Vernacular Architecture Studies"
        ],
        "content": "# Chinnak-Kol: Bamboo Battens & Roof Laths\n\nThe ceramic tile roof depended upon a flexible, resilient timber and bamboo sub-structure capable of supporting tons of heavy terracotta without sagging or warping.\n\nAbove the primary heavy hardwood rafters (kazhuthukol), carpenters laid closely spaced horizontal battens or laths known as chinnak-kol or varichal. These were split from mature, water-cured male bamboo (kallu-moongil) or seasoned palmyra slats, celebrated for their exceptional flexural tensile strength and resistance to dry rot.\n\nThe battens were lashed firmly to the rafters using tarred coconut coir cordage (thengai-kayiru) rather than iron nails, allowing the flexible sub-frame to absorb cyclonic winds and slight masonry settlement without displacing the interlocked tile courses resting above."
    },
    {
        "file": "knowledge/concepts/concept-tiled-thermal-insulation-and-passive-monsoon-ventilation-physics.md",
        "slug": "concept-tiled-thermal-insulation-and-passive-monsoon-ventilation-physics",
        "category": "concept",
        "name_en": "Passive Thermal Insulation & Micro-Climatic Ventilation in Terracotta Tile Roofs",
        "name_ta": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0bb2\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Thermodynamic physics of terracotta roofs: porous clay tiles dissipating solar radiation, creating buoyant hot-air attic currents that draw cool breezes through interior living quarters.",
        "summary_ta": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0ba8\u0bc1\u0ba3\u0bcd\u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bcd \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b95\u0bc2\u0bb0\u0bc8\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b9a\u0bc2\u0b9f\u0bbe\u0ba9 \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8 \u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bc7\u0bb1\u0bcd\u0bb1\u0bbf \u0bb5\u0bc0\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bc1\u0bb3\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4 \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8 \u0b88\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0baa\u0bcd\u0baa \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Nedunalvadai 85-95",
            "Traditional Climatological Architecture Studies",
            "Indian Building Science"
        ],
        "content": "# Passive Thermal Insulation in Terracotta Roofs\n\nBeyond rain protection and fireproofing, the Tamil terracotta tile roof was a masterpiece of passive thermodynamic environmental control engineered for hot, humid tropical climates.\n\nFired terracotta has high thermal mass and low thermal conductivity, retarding solar heat gain during scorching noon hours. Furthermore, the micro-porous structure of unglazed baked clay absorbed overnight dew and morning condensation; as daytime temperatures rose, this stored moisture evaporated (evaporative cooling), dissipating solar energy before it could radiate into the living spaces.\n\nThe layered, mortarless arrangement of overlapping tiles permitted micro-ventilation between every tile joint. Rising hot air in the attic space exhausted continuously through the high roof ridges, creating a passive thermosiphon stack effect that drew cool, shaded ambient breezes through ground-floor courtyards."
    },
    {
        "file": "knowledge/places/place-manamadurai-ancient-terracotta-tile-and-kiln-haven.md",
        "slug": "place-manamadurai-ancient-terracotta-tile-and-kiln-haven",
        "category": "place",
        "name_en": "Manamadurai: Ancient Terracotta Tile, Pottery Pyrotechnics & Vaigai Ceramic Haven",
        "name_ta": "\u0bae\u0bbe\u0ba9\u0bbe\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1, \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0b9a\u0bcd \u0b9a\u0bc2\u0bb3\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc8\u0b95\u0bc8 \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bcd",
        "era": "Early Historic to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "World-famous ceramic settlement on the banks of the Vaigai river in Sivaganga district, celebrated for over two millennia for its prized potting clay, acoustic ghatams, and heritage tile kilns.",
        "summary_ta": "\u0bb5\u0bc8\u0b95\u0bc8 \u0ba8\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b95\u0bb2\u0bc8 \u0ba8\u0b95\u0bb0\u0bae\u0bcd; \u0baa\u0bbf\u0bb0\u0ba4\u0bcd\u0baf\u0bc7\u0b95 \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0bb5\u0bb3\u0bae\u0bcd, \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b95\u0b9f\u0bae\u0bcd \u0b87\u0b9a\u0bc8\u0b95\u0bcd\u0b95\u0bb0\u0bc1\u0bb5\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0baa\u0ba3\u0bcd\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Manamadurai Pottery Inscriptions",
            "Sivaganga District Gazetteers",
            "GI Tag Documentation Manamadurai"
        ],
        "content": "# Manamadurai: Ancient Ceramic & Tile Haven\n\nManamadurai, situated along the tranquil sands of the sacred Vaigai river in southern Tamil Nadu, stands as the premier historic sanctuary of Tamil ceramic craftsmanship and terracotta pyrotechnics.\n\nThe unique geological character of the Vaigai alluvial clay\u2014rich in plastic colloidal silicates, iron oxides, and natural mica flakes\u2014endowed Manamadurai pottery and tiles with extraordinary acoustic resonance, strength, and thermal shock resistance. For generations, master potter lineages maintained massive downdraft kilns along the river meadows.\n\nManamadurai's interlocking terracotta roof tiles, water storage vessels, and celebrated clay musical instruments (ghatam) were transported throughout Tamilakam and exported through coastal ports, maintaining an unbroken tradition of ceramic pyrotechnic mastery from Sangam antiquity to the modern era."
    }
]
EDGES = [
    [
        "concept-oodu-veythal-interlocking-clay-pantile-roofing-and-water-runoff-geometry",
        "UTILIZES",
        "artifact-kaal-oodu-and-muthugu-oodu-grooved-drainage-tiles-and-ridge-cap-seals",
        "core",
        "Prehistoric to Modern Era",
        "Interlocking pantile roofing systems utilize grooved drainage under-tiles and curved ridge caps.",
        "Keezhadi Archaeological Reports"
    ],
    [
        "technology-soozhai-subterranean-downdraft-tile-firing-kiln-pyrotechnics",
        "FIRES",
        "concept-oodu-veythal-interlocking-clay-pantile-roofing-and-water-runoff-geometry",
        "core",
        "Prehistoric to Modern Era",
        "Subterranean downdraft kilns fire green molded clay tiles into vitreous weather-resistant terracotta.",
        "Keezhadi Industrial Kilns"
    ],
    [
        "concept-man-padham-vaigai-alluvial-clay-aging-levigation-and-grog-tempering",
        "SUPPLIES",
        "technology-achchu-palagai-hardwood-tile-molding-presses-and-wire-cutters",
        "core",
        "Prehistoric to Modern Era",
        "Aged and grog-tempered alluvial clay provides the raw workable paste for hardwood tile molds.",
        "Manamadurai Pottery Ethnography"
    ],
    [
        "technology-achchu-palagai-hardwood-tile-molding-presses-and-wire-cutters",
        "FORMS",
        "artifact-kaal-oodu-and-muthugu-oodu-grooved-drainage-tiles-and-ridge-cap-seals",
        "core",
        "Prehistoric to Modern Era",
        "Precision hardwood molding frames and wire cutters shape the standardized flanged tile geometry.",
        "Traditional Ceramic Handbooks"
    ],
    [
        "text-pattinappalai-verses-on-tiled-mansions-and-fireproof-urban-roofs",
        "CELEBRATES",
        "concept-oodu-veythal-interlocking-clay-pantile-roofing-and-water-runoff-geometry",
        "core",
        "Sangam Era",
        "Pattinappalai verses celebrate the glittering fireproof tile roofs of urban port city mansions.",
        "Pattinappalai 142-158"
    ],
    [
        "institution-kuyavar-chakri-guild-hereditary-corporation-of-master-tile-makers",
        "PRESERVES",
        "technology-soozhai-subterranean-downdraft-tile-firing-kiln-pyrotechnics",
        "core",
        "Early Historic to Medieval Era",
        "The hereditary potters and tile-makers guild preserved secretive downdraft kiln firing methods.",
        "Manamadurai Epigraphs"
    ],
    [
        "artifact-chinnak-kol-curved-bamboo-slat-roof-truss-battens-and-tile-laths",
        "SUPPORTS",
        "concept-oodu-veythal-interlocking-clay-pantile-roofing-and-water-runoff-geometry",
        "core",
        "Prehistoric to Modern Era",
        "Split seasoned bamboo battens provide the flexible, unnailed roof framing that supports tile courses.",
        "Traditional Carpentry Manuals"
    ],
    [
        "concept-oodu-veythal-interlocking-clay-pantile-roofing-and-water-runoff-geometry",
        "PRODUCES",
        "concept-tiled-thermal-insulation-and-passive-monsoon-ventilation-physics",
        "core",
        "Prehistoric to Modern Era",
        "Overlapping mortarless tile construction creates passive thermosiphon ventilation and evaporative cooling.",
        "Nedunalvadai 85-95"
    ],
    [
        "technology-soozhai-subterranean-downdraft-tile-firing-kiln-pyrotechnics",
        "OPERATED_AT",
        "place-manamadurai-ancient-terracotta-tile-and-kiln-haven",
        "core",
        "Early Historic to Modern Era",
        "Centuries of subterranean downdraft tile and pottery kilns operated along the Vaigai at Manamadurai.",
        "Sivaganga District Gazetteers"
    ],
    [
        "institution-kuyavar-chakri-guild-hereditary-corporation-of-master-tile-makers",
        "HEADQUARTERED_AT",
        "place-manamadurai-ancient-terracotta-tile-and-kiln-haven",
        "core",
        "Early Historic to Medieval Era",
        "Sovereign master potter and tile artisan guilds maintained primary headquarters at Manamadurai.",
        "South Indian Epigraphy Vol II"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Terracotta Roof Tiling, Interlocking Pantiles & Kiln Pyrotechnics into Moolam Chronicles & Life Graph...")

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
                properties = EXCLUDED.properties;
        """, (
            str(uuid.uuid4()), slug, d["category"], d["name_en"], d["name_ta"],
            d["era"], d["year_start"], d["year_end"], d["thinai"],
            d["summary_en"], d["summary_ta"], d["sources"], "core", props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} nodes upserted.")

    # Phase 3: PostgreSQL Lore Edges Insertion
    print("\n[Phase 3] Inserting 10 Lore Graph Relationships...")
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

    print(f"\n🎉 Ancient Tamil Terracotta Roof Tiling, Interlocking Pantiles & Kiln Pyrotechnics Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
