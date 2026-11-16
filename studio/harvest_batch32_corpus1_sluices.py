#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Megalithic Rock Sluice Hydraulic Engineering & Tank Cascades
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
        "file": "knowledge/texts/text-purananuru-18-nedunchezhian-verses-on-valley-damming-and-reservoir-hydraulics.md",
        "slug": "text-purananuru-18-nedunchezhian-verses-on-valley-damming-and-reservoir-hydraulics",
        "category": "text",
        "name_en": "Purananuru 18: Kudapulaviyanar Verses on Valley Damming & Reservoir Cascades",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 18 - \u0b95\u0bc1\u0b9f\u0baa\u0bc1\u0bb2\u0bb5\u0bbf\u0baf\u0ba9\u0bbe\u0bb0\u0bcd \u0baa\u0bbe\u0b9f\u0bbf\u0baf \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1\u0bb4\u0bbf\u0bb5\u0bc1 \u0b85\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0ba8\u0bbf\u0bb2\u0bc8 \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bc8",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Classical Sangam verses by Kudapulaviyanar instructing the Pandyan king Nedunchezhian that enduring sovereignty rests on damming low-lying valleys to accumulate rainwater reservoirs.",
        "summary_ta": "\u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1\u0bb4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bc8 \u0b85\u0ba3\u0bc8\u0b95\u0b9f\u0bcd\u0b9f\u0bbf \u0ba8\u0bc0\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bbe\u0b95 \u0bae\u0bbe\u0bb1\u0bcd\u0bb1\u0bbf \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd\u0bae\u0bc8\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb5\u0bcb\u0bb0\u0bc7 \u0b87\u0bb5\u0bcd\u0bb5\u0bc1\u0bb2\u0b95\u0bbf\u0bb2\u0bcd \u0b85\u0bb4\u0bbf\u0baf\u0bbe\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd \u0baa\u0bc6\u0bb1\u0bc1\u0bb5\u0bb0\u0bcd \u0b8e\u0ba9\u0bcd\u0bb1\u0bc1 \u0ba8\u0bc6\u0b9f\u0bc1\u0b9e\u0bcd\u0b9a\u0bc6\u0bb4\u0bbf\u0baf\u0ba9\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0bc1\u0b9f\u0baa\u0bc1\u0bb2\u0bb5\u0bbf\u0baf\u0ba9\u0bbe\u0bb0\u0bcd \u0b85\u0bb1\u0bbf\u0bb5\u0bc1\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 18",
            "Pathittruppathu 27",
            "Maduraikanchi 235"
        ],
        "content": "# Purananuru 18: Kudapulaviyanar on Valley Damming & Reservoir Cascades\n\nPurananuru poem 18, composed by the venerable Sangam bard Kudapulaviyanar in counsel to the Pandyan monarch Thalaiyalanganathu Seruvendra Nedunchezhian, provides foundational civilizational philosophy regarding hydraulic engineering in ancient Tamilakam.\n\nThe bard forcefully asserts that whoever binds the waters of rain by raising earthen embankments across valleys creates food, life, and enduring royal fame: 'Those who bound water where land was hollow have established their enduring bodies and names in this world.'\n\nThis seminal verse reflects an ancient agrarian realization that Tamil agriculture depended not merely on perennial rivers, but on capturing every droplet of monsoon runoff through vast chains of interconnected artificial reservoirs (eri) engineered across natural undulating topography."
    },
    {
        "file": "knowledge/concepts/concept-eri-ayam-interconnected-tank-cascade-catchment-hydrology.md",
        "slug": "concept-eri-ayam-interconnected-tank-cascade-catchment-hydrology",
        "category": "concept",
        "name_en": "Eri-Ayam: Interconnected Tank Cascade Catchment Hydrology & Valley Sequences",
        "name_ta": "\u0b8f\u0bb0\u0bbf \u0b86\u0baf\u0bae\u0bcd - \u0ba4\u0bca\u0b9f\u0bb0\u0bcd \u0b8f\u0bb0\u0bbf \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bbf\u0ba8\u0bbf\u0bb2 \u0bae\u0bc7\u0bb2\u0bbe\u0ba3\u0bcd\u0bae\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Indigenous meso-watershed hydrology linking chains of 20 to 50 reservoirs down river valleys, where surplus water from higher tanks fills lower tanks without wasteful oceanic runoff.",
        "summary_ta": "\u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0b9f\u0bbf\u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd 20 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd 50 \u0b8f\u0bb0\u0bbf\u0b95\u0bb3\u0bc8 \u0b92\u0ba9\u0bcd\u0bb1\u0ba9\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0b92\u0ba9\u0bcd\u0bb1\u0bbe\u0b95 \u0b87\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bc7\u0bb2\u0bcd\u0ba4\u0b9f\u0bcd\u0b9f\u0bc1 \u0b8f\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0b89\u0baa\u0bb0\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0b95\u0bc0\u0bb4\u0bcd\u0ba4\u0bcd\u0ba4\u0b9f\u0bcd\u0b9f\u0bc1 \u0b8f\u0bb0\u0bbf\u0baf\u0bc8 \u0b85\u0b9f\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bbf \u0ba8\u0bc0\u0bb0\u0bcd \u0bae\u0bc7\u0bb2\u0bbe\u0ba3\u0bcd\u0bae\u0bc8 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Purananuru 18",
            "Uttiramerur Epigraphs",
            "Madurantakam Tank Survey Records"
        ],
        "content": "# Eri-Ayam: Interconnected Tank Cascade Catchment Hydrology\n\nThe eri-ayam or tank cascade system constitutes the crowning achievement of ancient Tamil civil engineering in semi-arid and rain-fed agrarian basins (such as the Palar, Cheyyar, and Vaigai catchments).\n\nRather than constructing isolated giant dams, Tamil hydraulic engineers designed cascading chains of interconnected reservoirs spanning entire micro-watersheds. Higher reservoirs (thalai-eri) in the upper foothills captured torrential monsoon runoff, moderated flash floods, and allowed silt to settle.\n\nWhen upper tanks reached capacity, their masonry surplus weirs (kalingu) safely discharged excess water down designated feeder channels into intermediate tanks (naduvil-eri) and finally into lower terminal lakes (kadai-eri). This closed-loop cascade recharged groundwater tables, prevented topsoil erosion, and ensured continuous multi-crop irrigation even during low-rainfall years."
    },
    {
        "file": "knowledge/technologies/technology-kumizhi-thumbu-subaquatic-silt-clearing-piston-sluice-mechanics.md",
        "slug": "technology-kumizhi-thumbu-subaquatic-silt-clearing-piston-sluice-mechanics",
        "category": "technology",
        "name_en": "Kumizhi-Thumbu: Subaquatic Silt-Clearing Dual-Aperture Piston Sluice Mechanics",
        "name_ta": "\u0b95\u0bc1\u0bae\u0bbf\u0bb4\u0bbf\u0ba4\u0bcd \u0ba4\u0bc2\u0bae\u0bcd\u0baa\u0bc1 - \u0b95\u0b9f\u0bb2\u0b9f\u0bbf \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bc7\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8 \u0b95\u0bb2\u0bcd \u0ba4\u0bc2\u0bae\u0bcd\u0baa\u0bc1 \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Subaqueous granite piston sluice (kumizhi-thumbu) featuring dual hydrodynamic intake apertures that simultaneously discharge clear surface water for irrigation and scour heavy benthic silt.",
        "summary_ta": "\u0bae\u0bc7\u0bb2\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8 \u0bb5\u0bb4\u0bbf\u0baf\u0bc7 \u0ba4\u0bc6\u0bb3\u0bbf\u0ba8\u0bcd\u0ba4 \u0ba8\u0bc0\u0bb0\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0bcd\u0b95\u0bc1\u0bae\u0bcd, \u0b95\u0bc0\u0bb4\u0bcd\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8 \u0bb5\u0bb4\u0bbf\u0baf\u0bc7 \u0b85\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0ba4\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b9a\u0bc7\u0bb1\u0bcd\u0bb1\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b92\u0bb0\u0bc7 \u0ba8\u0bc7\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bc7\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bbe\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bb0\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Bahour Inscriptions",
            "Madurantakam Sluice Inscriptions",
            "Memoirs of Irrigation in South India"
        ],
        "content": "# Kumizhi-Thumbu: Subaquatic Silt-Clearing Sluice Mechanics\n\nThe kumizhi-thumbu is a uniquely indigenous Tamil hydraulic invention designed to solve the fatal problem that plagues all artificial reservoirs: sediment accumulation and siltation of the bed.\n\nSubmerged deep within the bed of the reservoir near the earthen bund, the sluice consists of a massive monolithic granite chamber or barrel. It features two distinct intake apertures: an upper vertical chimney orifice that draws clear surface water, and horizontal submerged bottom apertures level with the lake bed.\n\nWhen the conical wooden plug (thumbu-kambu) is raised, hydrostatic head pressure creates a powerful underwater vortex (kumizhi). This suction dredges the heavy benthic silt through the lower aperture while simultaneously channeling irrigation water through subterranean granite conduit pipes (madhavai) into agricultural canals, automatically fertilizing paddy fields with nutrient-rich silt and extending reservoir operational lifespan by centuries."
    },
    {
        "file": "knowledge/technologies/technology-kalingu-dressed-granite-curved-crest-surplus-escape-weirs.md",
        "slug": "technology-kalingu-dressed-granite-curved-crest-surplus-escape-weirs",
        "category": "technology",
        "name_en": "Kalingu: Dressed-Granite Curved-Crest Surplus Escape Weirs & Flood Spillways",
        "name_ta": "\u0b95\u0bb2\u0bbf\u0b99\u0bcd\u0b95\u0bc1 - \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bb5\u0bb3\u0bc8\u0bb5\u0bc1 \u0b89\u0baa\u0bb0\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0b85\u0ba3\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -300,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Monolithic dressed-granite surplus escape weirs (kalingu) with vertical slotted stone pillars enabling temporary timber flash-board installation to store maximum monsoon capacity.",
        "summary_ta": "\u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0ba4\u0bc2\u0ba3\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bb2\u0b95\u0bc8 \u0b9a\u0bc6\u0bb0\u0bc1\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b89\u0baa\u0bb0\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf (\u0b95\u0bb2\u0bbf\u0b99\u0bcd\u0b95\u0bc1); \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0ba4\u0bcd\u0ba4\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bbf \u0b8f\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bc8 \u0b89\u0b9f\u0bc8\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Kaveripakkam Inscriptions",
            "Uttiramerur Epigraphs",
            "Madurantakam Inscriptions"
        ],
        "content": "# Kalingu: Dressed-Granite Surplus Escape Weirs\n\nThe kalingu is the critical safety and regulation spillway of Tamil reservoir architecture. Positioned at one or both flanks of the earthen bund where solid bedrock could be excavated, the kalingu prevented cataclysmic dam breaches during extreme monsoon cloudbursts.\n\nConstructed from closely fitted, mortise-jointed ashlar granite blocks without mortar, the weir featured a broad curved crest that maximized hydraulic discharge efficiency. Heavy vertical stone monoliths were erected at precise intervals along the weir crest, carved with vertical side grooves.\n\nDuring dry months, village water masters inserted horizontal wooden stop-logs or woven brushwood hurdles into these stone grooves, temporarily raising water retention by two to three feet. When severe cyclonic inflows threatened to overtop the main earthen bund, the stop-logs were swiftly removed, allowing surplus water to discharge safely over the stone apron into downstream escape rivers."
    },
    {
        "file": "knowledge/technologies/technology-madhavai-and-sirai-subterranean-dressed-stone-gravity-conduits.md",
        "slug": "technology-madhavai-and-sirai-subterranean-dressed-stone-gravity-conduits",
        "category": "technology",
        "name_en": "Madhavai & Sirai: Subterranean Dressed-Stone Gravity Conduits & Flumes",
        "name_ta": "\u0bae\u0b9f\u0bb5\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb1\u0bc8 - \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bc2\u0b9f\u0bc1 \u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b88\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bbf\u0b9a\u0bc8 \u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0b95\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Underground masonry barrel conduits (madhavai) tunneled beneath massive earthen bunds to convey high-pressure water safely from reservoir beds into distributary canal networks.",
        "summary_ta": "\u0b8f\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b85\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0bae\u0bc2\u0b9f\u0bc1 \u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd (\u0bae\u0b9f\u0bb5\u0bc8); \u0b95\u0bb0\u0bc8 \u0b9a\u0bb0\u0bbf\u0baf\u0bbe\u0bae\u0bb2\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0b95\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc0\u0bb0\u0bc8 \u0b8e\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bc6\u0bb2\u0bcd\u0bb2\u0bc1\u0bae\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1.",
        "sources": [
            "Madurantakam Temple Charters",
            "Chola Epigraphy Vol III",
            "Ancient Hydraulic Architecture of Tamil Nadu"
        ],
        "content": "# Madhavai & Sirai: Subterranean Granite Gravity Conduits\n\nConveying water from a 20-foot-deep reservoir bed through a massive 50-foot-wide earthen embankment without destabilizing the soil required exceptional civil engineering. This was achieved through subterranean dressed-stone conduits termed madhavai or thumbu-kuzhal.\n\nThe conduit consisted of a rectangular or arched tunnel built from monolithic granite slabs: heavy foundation flags at the bottom, dressed vertical side orthostats, and colossal capstone lintels spanning the roof. The exterior seams were sealed with impervious puddling clay to prevent seepage piping along the conduit walls.\n\nOperating purely under gravity head, the madhavai discharged into an open masonry stilling basin (sirai) on the downstream side, dissipating kinetic energy and distributing calm, laminar flow into radiating irrigation channels (vaaykkal)."
    },
    {
        "file": "knowledge/institutions/institution-eri-variyam-chola-village-republic-irrigation-supervision-committee.md",
        "slug": "institution-eri-variyam-chola-village-republic-irrigation-supervision-committee",
        "category": "institution",
        "name_en": "Eri-Variyam: Imperial Chola Village Republic Irrigation Supervision Committee",
        "name_ta": "\u0b8f\u0bb0\u0bbf \u0bb5\u0bbe\u0bb0\u0bbf\u0baf\u0bae\u0bcd - \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbf\u0bb0\u0bbe\u0bae\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0baf\u0bb0\u0b9a\u0bc1 \u0b8f\u0bb0\u0bbf \u0bae\u0bc7\u0bb2\u0bbe\u0ba3\u0bcd\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1",
        "era": "Medieval Chola Era",
        "year_start": 800,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Democratic village assembly committee (Eri-Variyam) elected by pot-ticket ballot (kudavolai), legally empowered to maintain bunds, desilt tanks, enforce water shares, and collect tank cess.",
        "summary_ta": "\u0b95\u0bc1\u0b9f\u0bb5\u0bcb\u0bb2\u0bc8 \u0bae\u0bc1\u0bb1\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0b8f\u0bb0\u0bbf \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1, \u0ba4\u0bc2\u0bb0\u0bcd\u0bb5\u0bbe\u0bb0\u0bc1\u0ba4\u0bb2\u0bcd, \u0bb5\u0bb0\u0bbf \u0bb5\u0b9a\u0bc2\u0bb2\u0bcd (\u0b8f\u0bb0\u0bbf \u0b86\u0baf\u0bae\u0bcd) \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bae\u0ba8\u0bbf\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0ba4\u0bcd\u0ba4\u0bc8 \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0b95\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0ba9\u0bcd\u0ba9\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf \u0b95\u0bbf\u0bb0\u0bbe\u0bae\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bc1.",
        "sources": [
            "Uttiramerur Inscriptions of Parantaka I",
            "Madurantakam Epigraphs",
            "Chola Village Republic Studies"
        ],
        "content": "# Eri-Variyam: Chola Village Irrigation Committee\n\nThe enduring longevity of Tamil irrigation systems was secured by institutional governance rather than mere masonry. Under the imperial Cholas, local self-governing village assemblies (sabha and ur) maintained a dedicated executive body known as the Eri-Variyam (Tank Supervision Committee).\n\nAs recorded in the famed 10th-century Uttiramerur epigraphs of Parantaka I, committee members were elected annually by secret pot-ticket ballot (kudavolai) from among learned, property-owning agrarian citizens of upright character. The Eri-Variyam was entrusted with complete autonomous jurisdiction over all water bodies within the village boundary.\n\nThe committee supervised the seasonal desilting of reservoirs, deployed community corv\u00e9e labor and boats, maintained bund integrity, collected earmarked irrigation cess (eri-ayam and eri-patti), and resolved water distribution disputes among cultivating lineages."
    },
    {
        "file": "knowledge/concepts/concept-mann-karai-clay-core-earthen-bund-compaction-and-stone-revetment.md",
        "slug": "concept-mann-karai-clay-core-earthen-bund-compaction-and-stone-revetment",
        "category": "concept",
        "name_en": "Mann-Karai: Clay-Core Earthen Bund Compaction & Rip-Rap Stone Revetment",
        "name_ta": "\u0bae\u0ba3\u0bcd\u0b95\u0bb0\u0bc8 - \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0bae\u0bc8\u0baf \u0b8f\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0b9a\u0bc1\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb2\u0bc8\u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1 \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Earthen dam structural engineering utilizing puddled impervious clay cores (mann-karai) flanked by compacted gravel shoulders and dry-stone boulder rip-rap revetments to resist wave wash.",
        "summary_ta": "\u0b8f\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0ba8\u0b9f\u0bc1\u0bb5\u0bc7 \u0b95\u0b9a\u0bbf\u0bb5\u0bc1 \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0bae\u0bc8\u0baf\u0bae\u0bcd, \u0b87\u0bb0\u0bc1\u0baa\u0bc1\u0bb1\u0bae\u0bc1\u0bae\u0bcd \u0b9a\u0bb0\u0bb3\u0bc8 \u0bae\u0ba3\u0bcd \u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb2\u0bc8 \u0bae\u0bcb\u0ba4\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0ba9\u0bcd\u0baa\u0bc1\u0bb1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bcd (\u0bb0\u0bbf\u0baa\u0bcd-\u0bb0\u0bbe\u0baa\u0bcd).",
        "sources": [
            "Purananuru 18",
            "Tiruvallam Inscriptions",
            "Traditional Soil Mechanics Treatises"
        ],
        "content": "# Mann-Karai: Earthen Bund Compaction & Revetment\n\nThe construction of mammoth reservoir embankments spanning several kilometers in length and up to 30 feet in height demanded deep intuitive mastery of soil mechanics and geotechnical engineering.\n\nTamil bundwrights employed a zoned earthfill structure. At the heart of the bund was a core of plastic, highly impervious puddled black clay (karisalpann) tamped down by herds of water buffalo to prevent subterranean water seepage and piping failures. This clay core was supported on both sides by compacted gravelly loam shoulders (saralai-mann) sloping at stable 2:1 or 3:1 gradients.\n\nTo protect the waterside face of the earthen dam against erosion from monsoon wind-driven waves, the entire upstream slope was paved with interlocked dry-stone boulder pitching or granite revetment (alai-thadukku / rip-rap), stabilizing the embankment for centuries."
    },
    {
        "file": "knowledge/artifacts/artifact-thumbu-kal-perforated-granite-intake-plugs-and-wooden-pistons.md",
        "slug": "artifact-thumbu-kal-perforated-granite-intake-plugs-and-wooden-pistons",
        "category": "artifact",
        "name_en": "Thumbu-Kal: Perforated Granite Intake Plugs & Floating Wooden Pistons",
        "name_ta": "\u0ba4\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bcd - \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0ba4\u0bc2\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0b95\u0bcd\u0b95 \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0bae\u0bbf\u0bb4\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Granite intake collar stones (thumbu-kal) fitted with tapered wooden plug rods (kumizhi-kambu) operated from an elevated stone causeway to open or close sluice discharge.",
        "summary_ta": "\u0b8f\u0bb0\u0bbf \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0bae\u0bc2\u0bb4\u0bcd\u0b95\u0bbf\u0baf\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0ba4\u0bc2\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0b9f\u0bc8\u0baf\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0b87\u0bb2\u0bc1\u0baa\u0bcd\u0baa\u0bc8 \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0bae\u0bbf\u0bb4\u0bcd \u0b95\u0bc1\u0b9a\u0bcd\u0b9a\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Palar Basin Archaeological Artifacts",
            "Madurantakam Excavations",
            "Epigraphia Indica"
        ],
        "content": "# Thumbu-Kal: Perforated Granite Sluice Plugs\n\nThe mechanical valve controlling water discharge through ancient Tamil sluices was the thumbu-kal assembly. Positioned at the inlet of the underwater conduit, the thumbu-kal was a monolithic dressed granite block carved with one or more precision-ground circular or conical apertures.\n\nFitting tightly into this granite seat was a long, tapered wooden piston plug made from rot-resistant Iluppai or Teak heartwood, known as the kumizhi-kambu. The upper end of the rod was affixed to a long vertical wooden stem that extended above the water level, connected to a raised granite operating footbridge (nadai-paalam).\n\nBy turning or lifting the stem using a cross-lever bar, the sluice master (neer-paachi) calibrated the aperture opening with precision, controlling outflow velocity without needing to dive into the deep water."
    },
    {
        "file": "knowledge/concepts/concept-neer-paasanam-rotational-sluice-discharge-and-madai-allotment.md",
        "slug": "concept-neer-paasanam-rotational-sluice-discharge-and-madai-allotment",
        "category": "concept",
        "name_en": "Neer-Paasanam: Rotational Warabandi Water Allocation & Madai Sluice Turns",
        "name_ta": "\u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0bae\u0bcd - \u0bae\u0bc1\u0bb1\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0b9a\u0ba9\u0baa\u0bcd \u0baa\u0b99\u0bcd\u0b95\u0bc0\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0b9f\u0bc8 \u0ba8\u0bc0\u0bb0\u0bcd \u0ba4\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc6\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -300,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Equitable rotational water allocation system (neer-paasanam) dividing canal water among agrarian ayacut fields by timed turns (naazhigai) and field acreage under community oversight.",
        "summary_ta": "\u0ba8\u0bbf\u0bb2\u0baa\u0bcd \u0baa\u0bb0\u0baa\u0bcd\u0baa\u0bb3\u0bb5\u0bbf\u0bb1\u0bcd\u0b95\u0bc1 \u0b8f\u0bb1\u0bcd\u0baa \u0ba8\u0bbe\u0bb4\u0bbf\u0b95\u0bc8 \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bae\u0b9f\u0bc8 \u0ba8\u0bc0\u0bb0\u0bc8 \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bc1\u0bb1\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0bae\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0b99\u0bcd\u0b95\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Thanjavur Epigraphs",
            "Uttiramerur Charters",
            "Madurantakam Inscriptions"
        ],
        "content": "# Neer-Paasanam: Rotational Sluice Discharge & Water Allocation\n\nEquitable water management in ancient Tamil agrarian society was guided by strict legal and communal protocols termed neer-paasanam. Water from the reservoir was considered the common wealth of the entire settlement (ayacut).\n\nIrrigation water was allocated through a sophisticated rotational scheduling system (ancestral to the warabandi model). Sluice gates were opened only at predetermined hours, and discharge into primary distributary canals was monitored by specialized water distributors (madai-kaappalar or neer-katti).\n\nEach agricultural block received water in proportional duration measured by traditional water-clocks (naazhigai-vattil) based on crop type and soil permeability. Upstream farmers were legally prohibited from monopolizing flows before downstream tail-end farmers received their statutory allotment, maintaining social equilibrium across agrarian settlements."
    },
    {
        "file": "knowledge/places/place-madurantakam-ancient-chola-reservoir-cascade-and-kalingu-haven.md",
        "slug": "place-madurantakam-ancient-chola-reservoir-cascade-and-kalingu-haven",
        "category": "place",
        "name_en": "Madurantakam: Ancient Chola Reservoir Cascade & Monumental Kalingu Haven",
        "name_ta": "\u0bae\u0ba4\u0bc1\u0bb0\u0bbe\u0ba8\u0bcd\u0ba4\u0b95\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0b8f\u0bb0\u0bbf, \u0b95\u0bb2\u0bbf\u0b99\u0bcd\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Historic Chola irrigation capital in Chengalpattu district founded by Uttama Chola (Madurantaka), home to one of Tamil Nadu's largest ancient cascade lakes with monumental granite kalingu weirs.",
        "summary_ta": "\u0b89\u0ba4\u0bcd\u0ba4\u0bae \u0b9a\u0bcb\u0bb4\u0bb0\u0bbe\u0bb2\u0bcd (\u0bae\u0ba4\u0bc1\u0bb0\u0bbe\u0ba8\u0bcd\u0ba4\u0b95\u0ba9\u0bcd) \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0bae\u0ba4\u0bc1\u0bb0\u0bbe\u0ba8\u0bcd\u0ba4\u0b95\u0bae\u0bcd \u0b8f\u0bb0\u0bbf; \u0b86\u0b9a\u0bbf\u0baf\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0bae\u0bbe\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bbf\u0b99\u0bcd\u0b95\u0bc1 \u0bae\u0ba4\u0b95\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b9a\u0ba9 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bbf\u0ba9\u0bcd \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Madurantakam Temple Inscriptions",
            "Parantaka I Epigraphs",
            "Madras District Gazetteers"
        ],
        "content": "# Madurantakam: Monumental Reservoir & Kalingu Haven\n\nMadurantakam, situated in the fertile Palar-Cheyyar basin of northern Tamil Nadu, stands as one of the most celebrated civil engineering monuments of the Chola empire.\n\nFounded during the 10th century by the Chola monarch Uttama Chola (who bore the royal title Madurantaka), the township was engineered around the monumental Madurantakam Lake (Madurantaka Tatakam). Covering an immense water spread of thousands of acres with a multi-kilometer earthen embankment, the lake impounds seasonal river flows to irrigate dozens of downstream agrarian villages.\n\nThe site is world-renowned for its colossal dressed-granite surplus weirs (kalingu) and ancient silt-clearing piston sluices. Epigraphical records at the Eri-Kaatha-Ramar temple document unbroken centuries of water governance, communal desilting endowments, and hydraulic maintenance overseen by dedicated royal and village assemblies."
    }
]
EDGES = [
    [
        "concept-eri-ayam-interconnected-tank-cascade-catchment-hydrology",
        "GOVERNS",
        "technology-kumizhi-thumbu-subaquatic-silt-clearing-piston-sluice-mechanics",
        "core",
        "Prehistoric to Modern Era",
        "Catchment cascade hydrology principles dictate the placement and sizing of silt-clearing piston sluices.",
        "Bahour Inscriptions"
    ],
    [
        "technology-kumizhi-thumbu-subaquatic-silt-clearing-piston-sluice-mechanics",
        "INTEGRATES_WITH",
        "technology-madhavai-and-sirai-subterranean-dressed-stone-gravity-conduits",
        "core",
        "Prehistoric to Modern Era",
        "The subaquatic piston sluice connects directly into underground granite conduit tunnels beneath the bund.",
        "Madurantakam Sluice Inscriptions"
    ],
    [
        "technology-kalingu-dressed-granite-curved-crest-surplus-escape-weirs",
        "REGULATES",
        "concept-eri-ayam-interconnected-tank-cascade-catchment-hydrology",
        "core",
        "Prehistoric to Modern Era",
        "Dressed-granite surplus escape weirs safely discharge excess floodwaters to lower cascade reservoirs.",
        "Kaveripakkam Inscriptions"
    ],
    [
        "institution-eri-variyam-chola-village-republic-irrigation-supervision-committee",
        "SUPERVISES",
        "technology-kumizhi-thumbu-subaquatic-silt-clearing-piston-sluice-mechanics",
        "core",
        "Medieval Chola Era",
        "The democratic village tank committee exercised legal oversight over sluice operations and desilting maintenance.",
        "Uttiramerur Epigraphs"
    ],
    [
        "text-purananuru-18-nedunchezhian-verses-on-valley-damming-and-reservoir-hydraulics",
        "DOCUMENTS",
        "concept-eri-ayam-interconnected-tank-cascade-catchment-hydrology",
        "core",
        "Sangam Era",
        "Purananuru 18 provides early classical textual testimony of the civilizational imperative of valley damming.",
        "Purananuru 18"
    ],
    [
        "concept-mann-karai-clay-core-earthen-bund-compaction-and-stone-revetment",
        "REINFORCES",
        "technology-kalingu-dressed-granite-curved-crest-surplus-escape-weirs",
        "core",
        "Prehistoric to Modern Era",
        "Puddled clay cores and compacted embankments tie directly into stone abutments of surplus weirs.",
        "Traditional Soil Mechanics"
    ],
    [
        "artifact-thumbu-kal-perforated-granite-intake-plugs-and-wooden-pistons",
        "OPERATES",
        "technology-kumizhi-thumbu-subaquatic-silt-clearing-piston-sluice-mechanics",
        "core",
        "Prehistoric to Modern Era",
        "Perforated granite collar stones and tapered wooden pistons form the active valve mechanics of the sluice.",
        "Palar Basin Artifacts"
    ],
    [
        "concept-neer-paasanam-rotational-sluice-discharge-and-madai-allotment",
        "DIRECTED_BY",
        "institution-eri-variyam-chola-village-republic-irrigation-supervision-committee",
        "core",
        "Medieval Chola Era",
        "Equitable rotational water allocation was adjudicated and scheduled by the village tank assembly.",
        "Chola Epigraphy Vol III"
    ],
    [
        "technology-kalingu-dressed-granite-curved-crest-surplus-escape-weirs",
        "CONSTRUCTED_AT",
        "place-madurantakam-ancient-chola-reservoir-cascade-and-kalingu-haven",
        "core",
        "Early Medieval to Modern Era",
        "Monumental dressed-granite surplus escape weirs were erected at the flanks of Madurantakam Lake.",
        "Madurantakam Temple Charters"
    ],
    [
        "institution-eri-variyam-chola-village-republic-irrigation-supervision-committee",
        "CONVENED_AT",
        "place-madurantakam-ancient-chola-reservoir-cascade-and-kalingu-haven",
        "core",
        "Medieval Chola Era",
        "Sovereign village water assemblies met at the lakeside temple pavilions of Madurantakam.",
        "Parantaka I Epigraphs"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Megalithic Rock Sluice Hydraulic Engineering & Tank Cascades into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Megalithic Rock Sluice Hydraulic Engineering & Tank Cascades Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
