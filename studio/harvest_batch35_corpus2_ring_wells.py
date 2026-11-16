#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Terracotta Well-Ring Hydraulics, Groundwater Filtration & Subterranean Pot-Wells
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
        "file": "knowledge/texts/text-purananuru-305-verses-on-terracotta-ring-wells-and-clear-potable-water.md",
        "slug": "text-purananuru-305-verses-on-terracotta-ring-wells-and-clear-potable-water",
        "category": "text",
        "name_en": "Purananuru 305: Classical Sangam Verses on Stacked Terracotta Well-Rings & Sweet Water",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 305 - \u0b89\u0bb1\u0bc8 \u0b95\u0bbf\u0ba3\u0bb1\u0bcd\u0bb1\u0bc1 \u0b8a\u0bb1\u0bcd\u0bb1\u0bc1 \u0ba8\u0bc0\u0bb0\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0bb3\u0bc8\u0baf\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb5\u0bbf\u0ba4\u0bc8",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Classical Sangam verses depicting deep well excavations in alluvial river plains using interlocking terracotta circular rings to draw sweet, filtered subterranean drinking water.",
        "summary_ta": "\u0bae\u0ba3\u0bb2\u0bcd \u0b9a\u0bb0\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbf\u0bb4\u0bbe\u0bae\u0bb2\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b89\u0bb1\u0bc8\u0b95\u0bb3\u0bc8 \u0b92\u0ba9\u0bcd\u0bb1\u0ba9\u0bcd \u0bae\u0bc7\u0bb2\u0bcd \u0b92\u0ba9\u0bcd\u0bb1\u0bbe\u0b95 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf, \u0bae\u0ba3\u0bb1\u0bcd\u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc2\u0baf \u0b8a\u0bb1\u0bcd\u0bb1\u0bc1 \u0ba8\u0bc0\u0bb0\u0bc8 \u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0bb1\u0bc8 \u0b95\u0bbf\u0ba3\u0bb1\u0bcd\u0bb1\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 305",
            "Pattinappalai 245-255",
            "Nedunalvadai 80"
        ],
        "content": "# Purananuru 305: Classical Verses on Terracotta Ring-Wells\n\nIn the ancient martial and social anthology *Purananuru* (poem 305), the poet draws an evocative technical metaphor comparing steady moral fortitude to the unfailing water yield of a terracotta ring-well (*urai-kinaru*).\n\nThe verse details how communities living along riverine floodplains and urban centers excavated vertical water shafts deep into sandy aquifers. To prevent treacherous sand collapse, potters crafted massive circular earthenware rings (*urai*), slipping them down the excavation chamber one by one.\n\nAs each terracotta cylinder settled into the water table, sand filtered through porous seams, yielding cool, sparkling, sand-free potable water (*theen-neer*) even during scorching summer droughts."
    },
    {
        "file": "knowledge/concepts/concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization.md",
        "slug": "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "category": "concept",
        "name_en": "Urai-Kinaru: Terracotta Ring Mechanics, Caisson Sinking & Hydrostatic Sand Stabilization",
        "name_ta": "\u0b89\u0bb1\u0bc8 \u0b95\u0bbf\u0ba3\u0bb1\u0bc1 - \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0bb3\u0bc8\u0baf \u0bb9\u0bc8\u0b9f\u0bcd\u0bb0\u0bbe\u0bb2\u0bbf\u0b95\u0bcd\u0bb8\u0bcd, \u0b9a\u0bb0\u0bbf\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Civil engineering principles of open caisson sinking where heavy, grooved earthenware circular rings descend under gravity as interior sand is excavated, stabilizing loose alluvial soils.",
        "summary_ta": "\u0bae\u0ba3\u0bb1\u0bcd\u0baa\u0bbe\u0b99\u0bcd\u0b95\u0bbe\u0ba9 \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0ba3\u0bb1\u0bc1 \u0ba4\u0bcb\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd\u0baa\u0bcb\u0ba4\u0bc1 \u0bae\u0ba3\u0bcd \u0b9a\u0bb0\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bc2\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0bb3\u0bc8\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b92\u0ba9\u0bcd\u0bb1\u0ba9\u0bcd \u0b95\u0bc0\u0bb4\u0bcd \u0b92\u0ba9\u0bcd\u0bb1\u0bbe\u0b95 \u0b87\u0bb1\u0b95\u0bcd\u0b95\u0bbf \u0ba8\u0bc0\u0bb0\u0bc2\u0bb1\u0bcd\u0bb1\u0bc8 \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Archaeological Excavation Reports of Keezhadi",
            "Arikamedu Excavation Memoirs",
            "Indian Journal of Geo-Engineering History"
        ],
        "content": "# Urai-Kinaru: Caisson Sinking & Sand Stabilization\n\nDigging wells in deltaic floodplains presents an acute geotechnical hazard: unconsolidated sand saturated with high-pressure groundwater collapses inwards as soon as a pit exceeds two meters depth.\n\nAncient Tamil hydraulic engineers solved this with the open-caisson method:\n- **Grooved Interlocking Collars**: Each circular terracotta ring (*urai*) was wheel-thrown or coil-molded with a stepped female rim at the top and a male rabbet at the bottom, locking concentric cylinders against lateral soil pressure.\n- **Self-Sinking Gravity Caisson**: The initial ring with a sharpened lower cutting edge (*kuthirai-padam*) was placed on the surface. As diggers scooped sand out from the interior, the stack sank smoothly by its own deadweight. Successive rings were added at ground level until reaching the perennial water table, sometimes twenty rings deep (6 to 8 meters).\n- **Hydrostatic Equilibrium**: The cylindrical geometry converted uniform lateral active earth pressure ($K_a \\cdot \\gamma \\cdot z$) into pure circumferential hoop compression, preventing tensile wall blowout."
    },
    {
        "file": "knowledge/technologies/technology-potter-wheel-ring-molding-and-open-air-bonfire-pyrotechnics.md",
        "slug": "technology-potter-wheel-ring-molding-and-open-air-bonfire-pyrotechnics",
        "category": "technology",
        "name_en": "Urai-Vanaithal: Heavy Wheel-Throwing, Segmented Coiling & Low-Temperature Kiln Firing",
        "name_ta": "\u0b89\u0bb1\u0bc8 \u0bb5\u0ba9\u0bc8\u0ba4\u0bb2\u0bcd - \u0b95\u0ba9\u0bb0\u0b95\u0b9a\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bae\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bb5\u0bb3\u0bc8\u0baf \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb1\u0ba8\u0bcd\u0ba4\u0bb5\u0bc6\u0bb3\u0bbf\u0b9a\u0bcd \u0b9a\u0bc2\u0bb3\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Ceramic manufacturing technology for giant 1-meter diameter terracotta well rings utilizing coarse quartz-tempered clay, specialized turntable throwing, and slow oxidising bonfire firings.",
        "summary_ta": "\u0b92\u0bb0\u0bc1 \u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bb0\u0bcd \u0bb5\u0bbf\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b89\u0bb1\u0bc8\u0b95\u0bb3\u0bc8 \u0b89\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb5\u0bbf\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0bb5\u0ba9\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1, \u0b89\u0bae\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bcb\u0bb2\u0bcd \u0baa\u0bb0\u0baa\u0bcd\u0baa\u0bbf\u0baf \u0b9a\u0bc2\u0bb3\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Keezhadi Ceramic Analysis Bulletins",
            "Ethnoarchaeology of Tamil Pottery",
            "Maduraikkanchi 400"
        ],
        "content": "# Urai-Vanaithal: Heavy Ring Molding & Kiln Firing\n\nFabricating a single terracotta well ring weighing upwards of 40 to 60 kilograms demanded exceptional mastery over clay rheology and firing thermodynamics:\n\n- **Quartz & Husk Tempering**: Pure alluvial clay shrinks dramatically during drying, causing massive circular cylinders to crack. Potters blended 30% coarse river sand, crushed quartz grog, and finely chopped rice husk (*thavidu*) into the paste, imparting high green strength and thermal shock resistance.\n- **Composite Throwing & Coiling**: The base ring was thrown on a heavy balanced stone turntable (*chakram*), while upper walls were built up using dense coils of clay, beaten flush with wooden mallets (*thattal-palagai*) supported by interior clay anvils (*kundhanni*).\n- **Oxidizing Clamp Kiln (*Soozhai*)**: Rings were stacked vertically inside earth-banked kilns, insulated with layers of dried cowdung cakes and rice straw, and fired at 750\u00b0C to 850\u00b0C. The porous, terracotta red matrix allowed groundwater to seep through micro-pores while blocking sand grains."
    },
    {
        "file": "knowledge/artifacts/artifact-chengal-kinaru-interlocking-wedge-shaped-curved-brick-masonry-wells.md",
        "slug": "artifact-chengal-kinaru-interlocking-wedge-shaped-curved-brick-masonry-wells",
        "category": "artifact",
        "name_en": "Chengal-Kinaru: Radial Wedge Bricks & Interlocking Architectural Well-Shafts",
        "name_ta": "\u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bbf\u0ba3\u0bb1\u0bc1 - \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0b86\u0baa\u0bcd\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd, \u0bb5\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bbf\u0bb5\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd \u0b95\u0bbf\u0ba3\u0bb1\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0bae\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Heavy civil well structures constructed with specially molded trapezoidal curved bricks whose interlocking radial geometry withstands seismic tremors and massive hydrostatic lateral forces.",
        "summary_ta": "\u0bb5\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bbf\u0bb5\u0b95\u0bcd \u0b95\u0bbf\u0ba3\u0bb1\u0bc1\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc6\u0ba9\u0bcd\u0bb1\u0bc7 \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bbe\u0b95 \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b86\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0b9f\u0bbf\u0bb5 \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0baa\u0bbe\u0b9a\u0ba9\u0b95\u0bcd \u0b95\u0bbf\u0ba3\u0bb1\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Archaeological Survey of Kaveripoompattinam",
            "Keezhadi Brick Architecture Monographs",
            "Pattinappalai 140-150"
        ],
        "content": "# Chengal-Kinaru: Radial Wedge-Brick Well Architecture\n\nIn large metropolitan settlements and temple complexes where water demand exceeded the capacity of narrow pot-wells, engineers erected monumental brick masonry wells (*chengal-kinaru*):\n\n- **Trapezoidal Radial Bricks**: Unlike rectangular wall bricks, well bricks were cast in tapered wooden molds with curved convex outer faces and concave inner faces. When arranged in a ring, the radial taper caused adjacent bricks to lock tightly under inward external pressure, functioning as a continuous vertical compression arch.\n- **Mortarless Friction or Lime-Pozzolana Bond**: Lower tiers submerged in the aquifer were laid dry without mortar, allowing water to infiltrate easily between joints. Upper structural tiers were bound with hydraulic lime mortar (*surki*) mixed with jaggery and egg-white extracts.\n- **Centuries of Service**: Structural brick wells unearthed at Keezhadi, Arikamedu, and Uraiyur demonstrate that these masonry shafts remained fully functional across centuries of changing groundwater levels."
    },
    {
        "file": "knowledge/concepts/concept-nilathadi-neer-natural-alluvial-aquifer-filtration-and-sand-matrix-purification.md",
        "slug": "concept-nilathadi-neer-natural-alluvial-aquifer-filtration-and-sand-matrix-purification",
        "category": "concept",
        "name_en": "Nilathadi-Neer: Natural Sand Bed Slow Filtration, Microbial Clarification & Potable Springs",
        "name_ta": "\u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0ba8\u0bc0\u0bb0\u0bcd - \u0bae\u0ba3\u0bb1\u0bcd\u0baa\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc8 \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0bb5\u0b9f\u0bbf\u0b95\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd, \u0b95\u0bbf\u0bb0\u0bc1\u0bae\u0bbf \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc2\u0baf \u0ba8\u0bc0\u0bb0\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1 \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Hydrogeological understanding of layered sand, gravel, and charcoal bottom beds acting as a multi-stage bio-sand water filter, removing pathogenic turbidity and salinity.",
        "summary_ta": "\u0b95\u0bbf\u0ba3\u0bb1\u0bcd\u0bb1\u0bbf\u0ba9\u0bcd \u0b85\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bae\u0ba3\u0bb2\u0bcd, \u0b95\u0bc2\u0bb4\u0bbe\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b95\u0bcd\u0b95\u0bb0\u0bbf \u0baa\u0bb0\u0baa\u0bcd\u0baa\u0bbf, \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0ba8\u0bc0\u0bb0\u0bc8 \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8\u0baf\u0bbe\u0b95\u0bb5\u0bc7 \u0bb5\u0b9f\u0bbf\u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0bc2\u0baf\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0ba8\u0bc0\u0bb0\u0bcd \u0bae\u0bc7\u0bb2\u0bbe\u0ba3\u0bcd\u0bae\u0bc8 \u0b85\u0bb1\u0bbf\u0bb5\u0bc1.",
        "sources": [
            "Charaka Samhita Water Chapters",
            "Sirupanattruppadai 150-165",
            "Groundwater Hydrology Historical Reviews"
        ],
        "content": "# Nilathadi-Neer: Sand Bed Filtration & Water Purification\n\nAncient Tamil urbanists demonstrated profound empirical understanding of hydrology, locating ring-wells within alluvial terraces where fine quartz sand functioned as a natural biological filter:\n\n- **Slow Sand Filtration**: Surface runoff contaminated with monsoon mud and organic matter filtered through meters of dense subterranean alluvial sands, shedding suspended colloidal particles, bacteria, and turbidity before entering the well sump.\n- **Charcoal Bottom Packing (*Kari-Padukkai*)**: Scribes and medical texts record that before commissioning a new ring-well, potters layered the bottom with coarse river pebbles, followed by a thick bed of fresh wood charcoal (*marakkari*). The active microporous carbon adsorbed organic odors and residual tannins.\n- **Thermal Invariance**: Subterranean water drawn from deep ring-wells remained at a constant, refreshing 24\u00b0C year-round, delightfully cool in oppressive summer months and soothingly warm in monsoon dawns."
    },
    {
        "file": "knowledge/institutions/institution-neer-thattar-and-kuyavar-guild-well-sinkers-and-ceramic-engineers.md",
        "slug": "institution-neer-thattar-and-kuyavar-guild-well-sinkers-and-ceramic-engineers",
        "category": "institution",
        "name_en": "Neer-Thattar & Kuyavar Guild: Corporation of Well-Sinkers & Hydraulic Ceramists",
        "name_ta": "\u0ba8\u0bc0\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbe\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0baf\u0bb5\u0bb0\u0bcd \u0b9a\u0baa\u0bc8 - \u0b95\u0bbf\u0ba3\u0bb1\u0bc1 \u0ba4\u0bcb\u0ba3\u0bcd\u0b9f\u0bc1\u0bb5\u0bcb\u0bb0\u0bcd, \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0ba8\u0bc0\u0bb0\u0bcd \u0b86\u0baf\u0bcd\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb1\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0bcb\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bb4\u0bc1",
        "era": "Classical Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Specialized vocational consortium combining traditional dowsers (water diviners), master trench diggers, and potters dedicated to urban water security and municipal well networks.",
        "summary_ta": "\u0ba8\u0bc0\u0bb0\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1 \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b87\u0b9f\u0ba4\u0bcd\u0ba4\u0bc8 \u0ba8\u0bbf\u0bb2\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1, \u0b95\u0bbf\u0ba3\u0bb1\u0bc1 \u0ba4\u0bcb\u0ba3\u0bcd\u0b9f\u0bbf, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b89\u0bb1\u0bc8\u0b95\u0bb3\u0bc8 \u0b87\u0bb1\u0b95\u0bcd\u0b95\u0bbf \u0ba8\u0bc0\u0bb0\u0bcd \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1\u0ba4\u0bcd \u0ba4\u0bb0\u0bc1\u0bae\u0bcd \u0bb5\u0bb2\u0bcd\u0bb2\u0bc1\u0ba8\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bae\u0bcd.",
        "sources": [
            "Keezhadi Inscriptional Evidence",
            "Brahat Samhita Dakargalam Chapter",
            "Pallava Municipal Water Charters"
        ],
        "content": "# Neer-Thattar & Kuyavar Guild: Hydraulic Ceramists\n\nThe installation of public and domestic water supplies in ancient cities like Madurai, Kaveripoompattinam, and Palayarai was orchestrated by specialized vocational guilds:\n\n- **Dakargalam (Water Dowsing Experts)**: Specialists known as *Neer-Nokkalar* surveyed soil textures, termite mound alignments (*karayan-putru*), and the proximity of specific water-loving trees (such as *maruthu* and *aththi*) to predict the exact depth and salinity of subterranean aquifers.\n- **The Sinking Crew (*Kuzhi-Vettuvar*)**: Skilled excavation divers worked within cramped 1-meter shafts, baling out slurry and water using leather buckets while ensuring the descending terracotta stack remained strictly vertical without tilting.\n- **Municipal Water Charters**: Village assemblies (*Ur* and *Sabha*) allocated communal funds (*kinatru-vari*) to hire the guild for periodic silt desoiling and ring replacement, ensuring continuous freshwater access for public squares and travelers' rest houses (*chathiram*)."
    },
    {
        "file": "knowledge/technologies/technology-urai-kinaru-drainage-soak-pits-and-urban-sanitation-networks.md",
        "slug": "technology-urai-kinaru-drainage-soak-pits-and-urban-sanitation-networks",
        "category": "technology",
        "name_en": "Soak-Pit Hydraulics: Terracotta Ring Drainage Pits & Urban Liquid Waste Dispersion",
        "name_ta": "\u0b95\u0bb4\u0bbf\u0bb5\u0bc1\u0ba8\u0bc0\u0bb0\u0bcd \u0b89\u0bb1\u0bc8 \u0b95\u0bbf\u0ba3\u0bb1\u0bc1 - \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b89\u0bb1\u0bbf\u0b9e\u0bcd\u0b9a\u0bc1 \u0b95\u0bc1\u0bb4\u0bbf\u0b95\u0bb3\u0bcd, \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0ba8\u0b95\u0bb0 \u0b9a\u0bc1\u0b95\u0bbe\u0ba4\u0bbe\u0bb0 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -500,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Sanitary engineering dual-use where identical stacked terracotta rings were sunk as wastewater soakaways and vertical percolation pits, absorbing domestic runoff without pooling.",
        "summary_ta": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bae\u0bc7\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd \u0b85\u0b95\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f, \u0bb5\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bae\u0bc8\u0baf\u0bb2\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb3\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bb4\u0bbf\u0bb5\u0bc1\u0ba8\u0bc0\u0bb0\u0bc8 \u0bae\u0ba3\u0bcd\u0ba3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bcd \u0b89\u0bb1\u0bbf\u0b9e\u0bcd\u0b9a\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b95\u0bbe\u0ba4\u0bbe\u0bb0 \u0b89\u0bb1\u0bc8 \u0b95\u0bbf\u0ba3\u0bb1\u0bcd\u0bb1\u0bc1 \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1.",
        "sources": [
            "Keezhadi Excavation Report (ASI / TNSDA 2019)",
            "Arikamedu Drainage Trench Surveys",
            "Urban Planning in Sangam Age"
        ],
        "content": "# Soak-Pit Hydraulics: Terracotta Ring Drainage Networks\n\nA crowning achievement of Sangam urban planning revealed in recent excavations at Keezhadi and Arikamedu is the dual application of terracotta ring structures for liquid waste management:\n\n- **Percolation Soak-Pits (*Kazhivu-Neer Urai*)**: Adjacent to kitchen quarters and textile dyeing vats, ancient engineers sunk stacks of four to six perforated terracotta rings. Domestic graywater flowed into these pits through covered brick sluices and clay pipes.\n- **Gravel-Lined Infiltration**: The bottom and perimeter of the soakaway were packed with coarse charcoal, broken potsherds (*odu-thundu*), and gravel. Water percolated rapidly into deep soil horizons while solid suspended matter was filtered out, preventing mosquito breeding and open stagnant puddles.\n- **Urban Density Support**: This subterranean soakaway system allowed dense urban settlements to thrive along riverbanks without polluting surface streets or shallow domestic drinking wells."
    },
    {
        "file": "knowledge/artifacts/artifact-thondi-and-saal-earthenware-well-buckets-and-counterpoise-bailing-levers.md",
        "slug": "artifact-thondi-and-saal-earthenware-well-buckets-and-counterpoise-bailing-levers",
        "category": "artifact",
        "name_en": "Thondi & Saal: Heavy Earthenware Bailers, Bull-Hide Well Buckets & Pulley Assemblies",
        "name_ta": "\u0ba4\u0bca\u0ba3\u0bcd\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0bb2\u0bcd - \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f \u0b95\u0bbf\u0ba3\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0bbe\u0bb3\u0bbf\u0b95\u0bb3\u0bcd, \u0ba4\u0bcb\u0bb2\u0bcd \u0b9a\u0bbe\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0baa\u0bbf\u0bb2\u0bc8 \u0baa\u0bbe\u0b9a\u0ba9\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Manual and draft-animal water-lifting hardware comprising wide-mouthed flared ceramic buckets, bull-hide water sacks, and friction-free hardwood pulley sheaves.",
        "summary_ta": "\u0b89\u0bb1\u0bc8 \u0b95\u0bbf\u0ba3\u0bb1\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba8\u0bc0\u0bb0\u0bc8 \u0bb5\u0bbf\u0bb0\u0bc8\u0bb5\u0bbe\u0b95 \u0bae\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bc7\u0bb2\u0bc7\u0bb1\u0bcd\u0bb1\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0bca\u0ba3\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bcd, \u0ba4\u0bcb\u0bb2\u0bcd \u0b9a\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0 \u0b89\u0bb0\u0bc1\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0baa\u0bbf\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0ba9\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbf\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Perumpanattruppadai 100-115",
            "Ainkurunuru 205",
            "Traditional Water Lifting Technology of India"
        ],
        "content": "# Thondi & Saal: Water-Lifting Bailers & Well Hardware\n\nDrawing water from deep ring-wells required robust bailing mechanisms suited to the structural parameters of narrow cylindrical shafts:\n\n- **Ceramic Well-Bailers (*Thondi*)**: Heavy, thick-rimmed flared earthenware pots thrown with a rounded reinforced base and an indented neck collar. Coir cords were secured tightly around the neck, allowing the pot to tip underwater and fill instantly.\n- **Picottah Leverage (*Ettram*)**: To lift large volumes for domestic garden irrigation, a counterbalanced wooden lever arm pivoted upon an upright bifurcated teak post (*kazhuthukol*). A stone counterweight eased the physical effort of hoisting heavy buckets from eight meters depth.\n- **Bullock Leather Sacks (*Saal*)**: In agricultural wells, massive stitched bull-hide bags (*kavalai*) fitted with long discharging leather trunks were pulled up inclined ramps by pairs of oxen, discharging hundreds of liters per stroke into distribution channels."
    },
    {
        "file": "knowledge/concepts/concept-alluvial-delta-stratigraphy-and-artesian-spring-dynamics.md",
        "slug": "concept-alluvial-delta-stratigraphy-and-artesian-spring-dynamics",
        "category": "concept",
        "name_en": "Delta Stratigraphy: Hydrogeological Layering, Impermeable Clays & Artesian Springs",
        "name_ta": "\u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bae\u0ba3\u0bcd \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1 - \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd, \u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0bc1\u0b95\u0bbe \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0b8a\u0bb1\u0bcd\u0bb1\u0bc1 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Geological mechanics of alternating clay aquitards and coarse sand aquifers across the Kaveri and Vaigai deltas that generate pressurized, self-filling perennial well springs.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc8\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bb2\u0bcd \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b87\u0b9f\u0bc8\u0baf\u0bc7 \u0b8f\u0bb1\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0ba4\u0bcd\u0ba4\u0bbe\u0bb2\u0bcd \u0b95\u0bbf\u0ba3\u0bb1\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd \u0ba4\u0bbe\u0ba9\u0bbe\u0b95 \u0b8a\u0bb1\u0bbf \u0ba8\u0bbf\u0bb1\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Geological Survey of India River Basin Bulletins",
            "Purananuru 399",
            "Hydrology of Ancient South Indian Deltas"
        ],
        "content": "# Delta Stratigraphy & Artesian Spring Dynamics\n\nThe remarkable productivity of ancient Tamil ring-wells was directly rooted in the stratigraphy of peninsular river deltas:\n\n- **Alternating Clay-Sand Cyclothems**: Flood events over millennia deposited alternating strata: fine impermeable clay lenses (*kazhimann*) followed by coarse, highly permeable quartz sands (*perum-manal*).\n- **Confined Aquifer Recharge**: Rain falling upon the distant Western Ghats and intermediate plateaus percolates into permeable strata, flowing downhill beneath confining clay layers. When a ring-well punctures the overlying clay aquitard, artesian hydraulic pressure drives pure groundwater upwards into the cylinder shaft.\n- **Continuous Sump Regeneration**: Because the earthenware bottom remains submerged in pressurized sand, a ring-well can be bailed dry and will recharge completely within thirty minutes, providing an inexhaustible municipal water supply."
    },
    {
        "file": "knowledge/places/place-palayarai-ancient-chola-metropolitan-reservoir-haven.md",
        "slug": "place-palayarai-ancient-chola-metropolitan-reservoir-haven",
        "category": "place",
        "name_en": "Palayarai: Ancient Chola Metropolitan Citadel & Ring-Well Hydraulic Haven",
        "name_ta": "\u0baa\u0bb4\u0bc8\u0baf\u0bb1\u0bc8 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bcd, \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0b89\u0bb1\u0bc8 \u0b95\u0bbf\u0ba3\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Historic early and imperial Chola secondary capital near Kumbakonam, celebrated for its sprawling network of residential ring-wells, temple moats, and sophisticated urban sanitation.",
        "summary_ta": "\u0b95\u0bc1\u0bae\u0bcd\u0baa\u0b95\u0bcb\u0ba3\u0bae\u0bcd \u0b85\u0bb0\u0bc1\u0b95\u0bc7 \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4, \u0b9a\u0bcb\u0bb4\u0baa\u0bcd \u0baa\u0bc7\u0bb0\u0bb0\u0b9a\u0bbf\u0ba9\u0bcd \u0b85\u0bb0\u0ba3\u0bcd\u0bae\u0ba9\u0bc8\u0b95\u0bb3\u0bcd, \u0baa\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0bb1\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b89\u0bb1\u0bc8 \u0b95\u0bbf\u0ba3\u0bb1\u0bc1\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0ba4\u0bbf\u0b95\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Palayarai Epigraphical Surveys",
            "Chola Metropolitan Archaeological Reports",
            "Periyapuranam Sambandar Saritham"
        ],
        "content": "# Palayarai: Ancient Chola Hydraulic Citadel\n\nSpread across a lush deltaic expanse just south of Kumbakonam in Thanjavur district, Palayarai flourished for over five centuries as the favored residential capital and military bastion of the Imperial Cholas.\n\n- **Vast Urban Population**: Housing the imperial palace (*Kandarathitham*), royal garrisons, and hundreds of monastic quarters (*padai-veedu*), Palayarai supported tens of thousands of inhabitants far from direct riverbanks, relying upon extensive subterranean ring-well grids.\n- **Subterranean Sanitation**: Archaeological excavations across the Palayarai complex revealed extensive dual-shaft ring systems: freshwater extraction wells situated uphill from household courtyards, and deep soakaway pits downstream absorbing municipal runoff.\n- **Monumental Water Moats**: The citadel was enveloped by concentric defensive moats fed by the Arasalar and Mudikondan rivers, replenishing the shallow groundwater table and ensuring that domestic ring-wells never dried up even during prolonged military sieges."
    }
]

EDGES = [
    [
        "text-purananuru-305-verses-on-terracotta-ring-wells-and-clear-potable-water",
        "DESCRIBES",
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "core",
        "Sangam Era",
        "Purananuru 305 verses depict deep ring-wells yielding sweet groundwater in sandy alluvium.",
        "Purananuru 305"
    ],
    [
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "MANUFACTURED_BY",
        "technology-potter-wheel-ring-molding-and-open-air-bonfire-pyrotechnics",
        "core",
        "Iron Age to Modern Era",
        "Potters threw and coiled heavy quartz-tempered clay rings fired in clamp kilns.",
        "Keezhadi Ceramic Analysis Bulletins"
    ],
    [
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "EVOLVED_INTO",
        "artifact-chengal-kinaru-interlocking-wedge-shaped-curved-brick-masonry-wells",
        "core",
        "Early Historic to Medieval Era",
        "Narrow terracotta pot-wells evolved into monumental curved radial wedge-brick well shafts.",
        "Archaeological Survey of Kaveripoompattinam"
    ],
    [
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "FILTERS_VIA",
        "concept-nilathadi-neer-natural-alluvial-aquifer-filtration-and-sand-matrix-purification",
        "core",
        "Prehistoric to Modern Era",
        "Ring-well shafts drew water naturally filtered through alluvial quartz sands and charcoal beds.",
        "Charaka Samhita Water Chapters"
    ],
    [
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "INSTALLED_BY",
        "institution-neer-thattar-and-kuyavar-guild-well-sinkers-and-ceramic-engineers",
        "core",
        "Classical Sangam to Medieval Era",
        "Guilds of water dowsers, trench diggers, and potters engineered urban well networks.",
        "Pallava Municipal Water Charters"
    ],
    [
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "ADAPTED_FOR",
        "technology-urai-kinaru-drainage-soak-pits-and-urban-sanitation-networks",
        "core",
        "Early Historic to Medieval Era",
        "Identical stacked terracotta rings served as urban sanitary soakaways absorbing domestic runoff.",
        "Keezhadi Excavation Report"
    ],
    [
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "ACCESSED_VIA",
        "artifact-thondi-and-saal-earthenware-well-buckets-and-counterpoise-bailing-levers",
        "core",
        "Iron Age to Modern Era",
        "Water was hoisted from ring-wells using earthenware thondi buckets and counterpoise picottahs.",
        "Perumpanattruppadai 100-115"
    ],
    [
        "concept-alluvial-delta-stratigraphy-and-artesian-spring-dynamics",
        "SUPPLIES_GROUNDWATER_TO",
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "core",
        "Prehistoric to Modern Era",
        "Confined alluvial aquifers in delta sediments supplied pressurized recharge to ring-wells.",
        "Hydrology of Ancient South Indian Deltas"
    ],
    [
        "concept-urai-kinaru-terracotta-well-ring-hydraulics-and-sand-collapse-stabilization",
        "PRESERVED_AT",
        "place-palayarai-ancient-chola-metropolitan-reservoir-haven",
        "core",
        "Early Medieval to Modern Era",
        "Palayarai citadel preserves extensive residential ring-well and soak-pit networks.",
        "Chola Metropolitan Archaeological Reports"
    ],
    [
        "institution-neer-thattar-and-kuyavar-guild-well-sinkers-and-ceramic-engineers",
        "OPERATED_AT",
        "place-palayarai-ancient-chola-metropolitan-reservoir-haven",
        "core",
        "Early Medieval to Modern Era",
        "Hydraulic guilds managed the domestic well and moat infrastructure of Palayarai capital.",
        "Palayarai Epigraphical Surveys"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 35: Ancient Tamil Terracotta Well-Ring Hydraulics, Groundwater Filtration & Subterranean Pot-Wells...")
    
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
