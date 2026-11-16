#!/usr/bin/env python3
# Ingestion harvester for Batch 24 Corpus 3: Terracotta Roof Tile Pyrotechnics & Drainage
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
        "file": "knowledge/texts/text-akanunuru-grooved-tile-roofs-and-monsoon-drainage-poetry.md",
        "slug": "text-akanunuru-grooved-tile-roofs-and-monsoon-drainage-poetry",
        "category": "text",
        "name_en": "Akananuru Verses on Grooved Tile Roofs, Eaves & Monsoon Drainage",
        "name_ta": "\u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd - \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bbe\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Akananuru 167 and 369 describing urban Chola mansions in Uraiyur and Poompuhar roofed with interlocking kiln-fired clay tiles (Koorai-Odu) featuring longitudinal water grooves and eaves shedding monsoonal rains like mountain torrents.",
        "summary_ta": "\u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0b89\u0bb0\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bbe\u0bb0\u0bcd \u0ba8\u0b95\u0bb0 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf\u0bb5\u0bb0\u0bbf\u0baf\u0bbe\u0b95 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bc8 \u0bb5\u0bc7\u0b95\u0bae\u0bbe\u0b95 \u0bb5\u0b9f\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Akananuru 167 & 369",
            "Nedunalvadai lines 85-105",
            "Archaeological Excavations at Keezhadi and Uraiyur Architecture"
        ],
        "content": "# Akananuru Verses on Grooved Tile Roofs, Eaves & Monsoon Drainage\n\n## Urban Architecture in Sangam Poetry\nWhile rural hamlets in Mullai and Kurinji utilized thatch and palmyra fronds, Sangam classical poetry (*Akananuru*, *Nedunalvadai*) establishes that royal capitals like Uraiyur, Madurai, and Poompuhar possessed multi-storeyed brick mansions roofed entirely with interlocking, kiln-fired terracotta tiles (*Sen-kal Odu*):\n\n```\n\"\u0bae\u0bb4\u0bc8\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0ba8\u0bc0\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bae\u0bbe\u0b9a\u0bbf \u0bb5\u0bbf\u0bb0\u0bbf \u0ba4\u0bbf\u0b99\u0bcd\u0b95\u0bb3\u0bcd\n\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1 \u0baa\u0bc1\u0bb1\u0bae\u0bcd \u0bb5\u0bb0\u0bbf\u0baf\n\u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0bbe\u0bb0\u0bc1\u0bae\u0bcd \u0bae\u0bbe\u0b9f\u0bae\u0bca\u0b9f\u0bc1...\"\n\u2014 \u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 167:8-11\n```\n\nThe verses record roofs laid with grooved tiles resembling cascading ripples, shedding torrential monsoonal downpours effortlessly away from timber rafters.\n\n## Fireproofing the Ancient City\nThe imperative behind terracotta tile roofs was fire prevention. High-density commercial cities with dense bazaar lanes suffered catastrophic firestorms when sparks from blacksmith forges or domestic hearths touched thatched roofs. Imperial urban bylaws mandated fired clay tile roofs on all permanent metropolitan dwellings.\n\n## Design Innovations in Sangam Roofing\n- **Varik-Kodu (\u0bb5\u0bb0\u0bbf\u0b9a\u0bcd\u0b9a\u0bbe\u0bb2\u0bcd)**: Deep longitudinal parallel grooves molded on the tile's upper face acting as micro-aqueducts to channel rain.\n- **Flanged Interlocking Lips**: Raised lateral margins preventing lateral rainwater seepage into ceiling timbers.\n- **Nail Peg Holes (*Aani-Thulai*)**: Cylindrical holes drilled near the head allowing tiles to be fastened to timber rafters using iron nails or wooden pegs.",
        "chunks": [
            {
                "language": "en",
                "title": "Akananuru Grooved Tile Roofing & Fireproof Urban Mansions",
                "content": "Akananuru verses portray ancient Tamil urban mansions roofed with grooved interlocking terracotta tiles that channeled monsoonal rains while providing vital fireproofing in crowded capitals."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bc1\u0bae\u0bcd",
                "content": "\u0b85\u0b95\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0ba8\u0b95\u0bb0 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0ba4\u0bc0 \u0bb5\u0bbf\u0baa\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bc8 \u0bb5\u0bbf\u0bb0\u0bc8\u0bb5\u0bbe\u0b95 \u0bb5\u0b9f\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0baa\u0bbe\u0b99\u0bcd\u0b95\u0bbf\u0ba9\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-flanged-and-grooved-interlocking-terracotta-roof-tile-molding.md",
        "slug": "concept-flanged-and-grooved-interlocking-terracotta-roof-tile-molding",
        "category": "concept",
        "name_en": "Flanged & Grooved Interlocking Terracotta Roof Tile Molding Mechanics",
        "name_ta": "\u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0b9a\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Manufacturing engineering of flat interlocking terracotta roof tiles excavated at Keezhadi, Uraiyur, and Arikamedu, featuring raised lateral flanges, bottom hook lugs, longitudinal finger grooves, and wooden mold pressing.",
        "summary_ta": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b95\u0bc2\u0b9f\u0bbf\u0baf \u0ba4\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bbe\u0ba9 \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0bae\u0bb0 \u0b85\u0b9a\u0bcd\u0b9a\u0bbf\u0bb2\u0bcd \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b95\u0bc8\u0bb5\u0bbf\u0bb0\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bb4\u0b99\u0bcd\u0b95\u0bbe\u0bb2 \u0b93\u0b9f\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Excavations at Keezhadi Reports (Tamil Nadu State Dept of Archaeology)",
            "Indian Archaeology 1965-66 (Uraiyur Excavations)",
            "Journal of Ancient Indian Ceramic Technology"
        ],
        "content": "# Flanged & Grooved Interlocking Terracotta Roof Tile Molding Mechanics\n\n## Archaeological Discoveries of Sangam Roof Tiles\nExcavations at Keezhadi (Madurai), Uraiyur (Tiruchirappalli), and Kaveripattinam have unearthed tens of thousands of distinctive flat roof tiles dating from the 4th century BCE to the 2nd century CE. These are not modern curved \"Spanish\" tiles, but highly sophisticated flat flanged interlocking plates.\n\n## Tile Geometry & Mold Mechanics\n1. **Rectangular Dimensions**: Typically measuring 25\u201330 cm in length, 15\u201320 cm in width, and 1.5\u20132 cm in thickness.\n2. **Raised Flanges (*Karai*)**: Lateral edges featured raised vertical ridges ($10\\text{ mm}$ high) that abutted adjacent tiles, covered by half-round cap tiles (*Kuzhai-Odu*) to seal joints.\n3. **Longitudinal Finger Grooves (*Varichal*)**: While clay was still plastic in the mold, artisans drew fingers or combs lengthwise, creating 2 to 4 parallel grooves that dramatically accelerated water run-off speed.\n4. **Suspension Lugs (*Mookku*)**: The underside possessed an inverted hook lug that gripped horizontal wooden batten laths (*Vari-Maram*), preventing tiles from sliding down steep pitches ($30^\\circ - 45^\\circ$).\n\n## Nail Perforations\nNearly all excavated Sangam tiles feature two cylindrical perforations at the upper margin, allowing them to be pinned to timber rafters using square-shanked iron nails discovered in situ.",
        "chunks": [
            {
                "language": "en",
                "title": "Flanged Interlocking Sangam Roof Tile Molding Engineering",
                "content": "Excavated Sangam roof tiles from Keezhadi and Uraiyur feature flat rectangular profiles with raised lateral flanges, finger-combed water grooves, and underside suspension lugs for interlocking timber rafter attachment."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0baa\u0b95\u0bcd\u0b95\u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd, \u0b95\u0bc8\u0bb5\u0bbf\u0bb0\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0b9a\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0b95\u0bcd\u0b95\u0bbf\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0b95 \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-high-silica-alluvial-clay-levigation-and-tile-firing-pyrotechnics.md",
        "slug": "concept-high-silica-alluvial-clay-levigation-and-tile-firing-pyrotechnics",
        "category": "concept",
        "name_en": "High-Silica Alluvial Clay Levigation & Tile-Firing Pyrotechnics",
        "name_ta": "\u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1 \u0b9a\u0bc2\u0bb3\u0bc8 \u0b8e\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Ceramic pyrotechnic protocols for roof tile manufacture: sedimentation levigation of Kaveri and Vaigai riverbed clay, fine quartz sand tempering to prevent warping, and controlled oxidizing firing at 800-900 \u00b0C in updraft clamp kilns.",
        "summary_ta": "\u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd\u0ba3\u0bc8 \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1, \u0bae\u0ba3\u0bb2\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1, 800-900 \u0b9f\u0bbf\u0b95\u0bbf\u0bb0\u0bbf \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd-\u0b93\u0b9f\u0bc1 \u0b9a\u0bc2\u0bb3\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bb3\u0bc8\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb0\u0bbf\u0b9a\u0bb2\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Purananuru 228 (Kuyavan kiln metaphor)",
            "Excavations at Uraiyur Kilns",
            "Ceramic Science in Ancient South Indian Archaeology"
        ],
        "content": "# High-Silica Alluvial Clay Levigation & Tile-Firing Pyrotechnics\n\n## Raw Material Levigation (*Mann-Pakanam*)\nUnlike pottery vessels formed on wheels, thin flat roof tiles are exceptionally prone to catastrophic warping and shrinkage cracks during drying and firing. Sangam tile pyrotechnicians developed rigorous clay preparation:\n- **Sedimentation Tanks (*Thotti-Thelivu*)**: Kaveri alluvial silt was stirred in settling tanks; coarse stones and organic rootlets sank, while ultra-fine plastic clay remained in suspension and decanted into adjacent drying beds.\n- **Quartz Tempering (*Manal-Kalappu*)**: Fine, rounded quartz river sand (20% to 25% by volume) was blended into the clay. The quartz grains acted as an unyielding structural skeleton, reducing volumetric drying shrinkage from 12% down to under 4%.\n\n## Clamp Kiln Firing Dynamics (*Odu-Kaalavaai*)\n1. **Vertical Edge Stacking**: Dried tiles were stacked vertically on their long edges in concentric rings inside circular clamp kilns, ensuring uniform thermal exposure across all surfaces.\n2. **Fuel Stratification**: Alternate layers of rice husk (*Umi*) and dry acacia firewood provided prolonged, gentle heat rise, driving off structural moisture ($100^\\circ\\text{C} - 200^\\circ\\text{C}$) before sintering.\n3. **Oxidizing Sintering at $850^\\circ\\text{C}$**: Abundant air draft converted iron compounds into ferric oxide ($Fe_2O_3$), yielding the characteristic vibrant terracotta orange-red hue with high vitrification density that resisted water absorption.",
        "chunks": [
            {
                "language": "en",
                "title": "Alluvial Clay Levigation & Clamp Kiln Tile Firing Protocols",
                "content": "Tile makers levigated Kaveri alluvial clay and blended quartz sand temper to eliminate drying warping, firing tiles vertically in clamp kilns at 850 \u00b0C to achieve dense, water-impermeable terracotta."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bc1\u0bae\u0bcd \u0b9a\u0bc2\u0bb3\u0bc8 \u0b8e\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8\u0baf\u0bc1\u0bae\u0bcd",
                "content": "\u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bbf\u0bb2\u0bcd \u0bae\u0ba3\u0bb2\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbf\u0bb0\u0bbf\u0b9a\u0bb2\u0bcd \u0b8f\u0bb1\u0bcd\u0baa\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0ba4\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0b95 \u0b85\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbf 850 \u0b9f\u0bbf\u0b95\u0bbf\u0bb0\u0bbf \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bc0\u0bb0\u0bbe\u0b95\u0b9a\u0bcd \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1 \u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baf\u0bbe\u0ba9 \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bc2\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-stormwater-eaves-gargoyles-and-slotted-tile-drainage-mechanics.md",
        "slug": "concept-stormwater-eaves-gargoyles-and-slotted-tile-drainage-mechanics",
        "category": "concept",
        "name_en": "Stormwater Eaves, Terracotta Gargoyles & Slotted Tile Drainage Mechanics",
        "name_ta": "\u0b95\u0bc2\u0bb0\u0bc8\u0ba4\u0bcd \u0ba4\u0bca\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0baf\u0bbe\u0bb3\u0bbf \u0bae\u0bc1\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bc7\u0bb1\u0bcd\u0bb1\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Hydraulic engineering of ancient Tamil roof drainages, utilizing flanged gutter tiles, circular terracotta downspout conduits (*Paanai-Thoombu*), and zoomorphic Yali gargoyles projecting stormwater away from palace foundations.",
        "summary_ta": "\u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bc8 \u0bae\u0bbe\u0bb3\u0bbf\u0b95\u0bc8 \u0b85\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc2\u0bb0 \u0b8e\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bc7\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0baa\u0bbe\u0ba3\u0bc8\u0ba4\u0bcd \u0ba4\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd, \u0baf\u0bbe\u0bb3\u0bbf \u0bae\u0bc1\u0b95\u0b95\u0bcd \u0b95\u0bb2\u0bbf\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba8\u0bc0\u0bb0\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1.",
        "sources": [
            "Nedunalvadai lines 90-110",
            "Excavations at Keezhadi Water Channels",
            "Journal of Ancient Tamil Hydraulic Architecture"
        ],
        "content": "# Stormwater Eaves, Terracotta Gargoyles & Slotted Tile Drainage Mechanics\n\n## Hydraulic Protection of Mud-Brick & Timber Foundations\nIn monsoon-swept Tamilakam, the greatest danger to monumental urban architecture was foundation softening caused by roof runoff cascading directly onto perimeter brick footings. Master builders (*Manai-Sirpacharis*) integrated complex stormwater collection systems into the roof eaves.\n\n## Eaves Drainage Assembly (*Iraip-Paanai*)\n1. **Flanged Eaves Tiles (*Irai-Odu*)**: The lowest course of tiles protruding over the wall plate featured curved downward lips that directed water into wooden or terracotta gutter troughs.\n2. **Projecting Spouts & Gargoyles (*Yaali-Mukham*)**: Molded terracotta spout conduits shaped as gaping monster masks (*Yaali*) or makara water beasts projected 50 to 80 cm outward from the eaves cornice, shooting water clear of external wall frescoes.\n3. **Interlocking Downspout Pipes (*Thoombu-Urai*)**: In dense multi-storeyed palaces, water entered vertical stacks of socket-and-spigot terracotta drainage pipes embedded flush in exterior brick pilasters, descending into subterranean paved street sewers excavated at Keezhadi and Kaveripattinam.",
        "chunks": [
            {
                "language": "en",
                "title": "Terracotta Eaves Downspouts & Foundation Stormwater Drainage",
                "content": "Sangam architects protected brick foundations from monsoon damage by engineering flanged eaves gutter tiles, projecting Yali gargoyles, and vertical socket-and-spigot terracotta downspouts."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bc2\u0bb0\u0bc8 \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0bc2\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
                "content": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0baf\u0bbe\u0bb3\u0bbf \u0bae\u0bc1\u0b95\u0b95\u0bcd \u0b95\u0bb2\u0bbf\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b92\u0ba9\u0bcd\u0bb1\u0bcb\u0b9f\u0bc1 \u0b92\u0ba9\u0bcd\u0bb1\u0bc1 \u0b87\u0ba3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bc2\u0bae\u0bcd\u0baa\u0bc1 \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bc8 \u0b9a\u0bc1\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0ba4\u0bc6\u0bb0\u0bc1 \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0ba8\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-fireproof-urban-tile-roofing-in-sangam-metropolises.md",
        "slug": "concept-fireproof-urban-tile-roofing-in-sangam-metropolises",
        "category": "concept",
        "name_en": "Fireproof Urban Tile Roofing Regulations in Sangam Metropolises",
        "name_ta": "\u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0ba8\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bc0\u0baf\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b92\u0bb4\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd",
        "era": "Early Historic Sangam Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Urban municipal zoning laws and municipal building codes enforced by Sangam town assemblies (*Avaiyam*), mandating non-combustible terracotta tile roofs, rooftop sand reservoirs, and night fire-watch patrols in trading capitals.",
        "summary_ta": "\u0bb5\u0ba3\u0bbf\u0b95 \u0ba8\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc0 \u0bb5\u0bbf\u0baa\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95 \u0ba8\u0b95\u0bb0 \u0b85\u0bb5\u0bc8\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbe\u0baf\u0bae\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0b95\u0bb3\u0bcd, \u0b95\u0bc2\u0bb0\u0bc8 \u0bae\u0ba3\u0bb2\u0bcd \u0ba4\u0bca\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bb5\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb5\u0bb2\u0bcd \u0b92\u0bb4\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Maduraikkanchi lines 350-375",
            "Silappathikaram Urkan Kathai",
            "Urban History of Ancient South Indian Port Cities"
        ],
        "content": "# Fireproof Urban Tile Roofing Regulations in Sangam Metropolises\n\n## The Urban Fire Peril in Sangam Capitals\nCommercial metropolises like Madurai, Uraiyur, and Kaveripattinam housed tens of thousands of residents within fortified ramparts. High property density, continuous textile spinning, oil lamps, and metal foundry hearths created an omnipresent risk of catastrophic urban infernos.\n\n## Municipal Tile Mandates (*Koorai-Vithi*)\n*Maduraikkanchi* and *Silappathikaram* document municipal fire-safety regulations overseen by royal city administrators (*Nagara-Kaavalar*):\n- **Prohibition of Thatch**: Thatch and dry palm fronds were strictly forbidden for roofing within inner commercial districts; only kiln-fired terracotta tiles (*Sen-kal Odu*) were legally permitted.\n- **Rooftop Water & Sand Urns**: Every flat-roofed merchant house was mandated to maintain broad clay jars filled with water and dry sand along roof parapets to smother flying cinders.\n- **Night Fire Patrols (*Iravup-Palli*)**: Watchmen bearing gongs patrolled the bazaar streets from dusk to dawn, enforcing the extinguishing of open cook-fires after curfew.",
        "chunks": [
            {
                "language": "en",
                "title": "Sangam Urban Fire-Safety Laws & Tile Roofing Mandates",
                "content": "City assemblies in Madurai and Uraiyur enforced strict fireproof building codes, banning combustible thatch in city centers and mandating non-flammable interlocking tile roofs with rooftop fire-suppression jars."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0ba8\u0b95\u0bb0\u0ba4\u0bcd \u0ba4\u0bc0\u0ba4\u0bcd\u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0bb5\u0bbf\u0ba4\u0bbf\u0b95\u0bb3\u0bcd",
                "content": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0ba8\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bc0 \u0bb5\u0bbf\u0baa\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95 \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bcb\u0bb2\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0b9f\u0bc8 \u0bb5\u0bbf\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0ba4\u0bc0\u0baa\u0bcd\u0baa\u0bb1\u0bcd\u0bb1\u0bbe\u0ba4 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0bae\u0ba3\u0bb2\u0bcd \u0ba4\u0bca\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbe\u0baf\u0bae\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-uraiyur-chola-capital-brick-and-tile-kiln-guild-charters.md",
        "slug": "insc-uraiyur-chola-capital-brick-and-tile-kiln-guild-charters",
        "category": "inscription",
        "name_en": "Uraiyur Chola Capital Brick & Tile Kiln Guild Charters",
        "name_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0 \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd-\u0b93\u0b9f\u0bc1 \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0bb5\u0ba3\u0bbf\u0b95 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -100,
        "year_end": 1000,
        "thinai": "marutham",
        "summary_en": "Archaeological discoveries, inscribed brick graffiti, and temple stone epigraphs from Uraiyur recording clay pit allocations, firewood gathering rights, and municipal contracts awarded to master tile-kiln guilds (*Kuyavar*).",
        "summary_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd, \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4 \u0bae\u0ba9\u0bcd\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0b95\u0bae\u0bcd\u0bae\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bbf\u0bb1\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0ba8\u0bbf\u0bb2 \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. XIII",
            "Excavations at Uraiyur (Madras University Archaeology Series)",
            "Tamil-Brahmi Brick Epigraphs of Chola Country"
        ],
        "content": "# Uraiyur Chola Capital Brick & Tile Kiln Guild Charters\n\n## The Imperial Capital of Uraiyur\nUraiyur (modern Tiruchirappalli, $10.8200^\\circ\\text{ N}, 78.6800^\\circ\\text{ E}$) was the inland royal capital of the Early Cholas, praised in Sangam songs as *Kozhiyur*. Positioned on the southern bank of the Kaveri, the city was built largely of high-density fired brick and roofed with thousands of tiles.\n\n## Epigraphic & Archaeological Finds\nArchaeological excavations by Madras University at Uraiyur revealed:\n- **Inscribed Tile Graffiti**: Roof tiles inscribed prior to firing with early Tamil-Brahmi script denoting potter guild trademarks (*'Antavan-Odu'* and *'Kannan'*).\n- **Kiln Guild Charters**: Medieval stone inscriptions from local temples confirming ancient communal rights of potters (*Kuyavar*) to extract alluvial clay from designated municipal clay beds (*Mann-Kuzhi*) along the Kaveri banks without payment of ground rent.\n- **Palace Supply Charters**: Mandates ensuring steady delivery of 10,000 grooved roof tiles annually for maintaining imperial storehouses and military barracks.",
        "chunks": [
            {
                "language": "en",
                "title": "Uraiyur Inscribed Tiles & Chola Tilemaker Guild Charters",
                "content": "Excavations and epigraphs at Uraiyur reveal Tamil-Brahmi inscribed roof tiles and Chola charters granting tile-kiln guilds exclusive clay extraction rights to supply municipal building projects."
            },
            {
                "language": "ta",
                "title": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd-\u0b93\u0b9f\u0bc1 \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0baf\u0bc8 \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b93\u0b9f\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bc8 \u0b86\u0bb5\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-keezhadi-inscribed-grooved-roof-tile-and-drainage-epigraphs.md",
        "slug": "insc-keezhadi-inscribed-grooved-roof-tile-and-drainage-epigraphs",
        "category": "inscription",
        "name_en": "Keezhadi Inscribed Grooved Roof Tile & Drainage Epigraphs",
        "name_ta": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 100,
        "thinai": "marutham",
        "summary_en": "Monumental ceramic epigraphy from the Keezhadi excavations near Madurai, yielding thousands of flanged grooved roof tiles, Tamil-Brahmi graffiti potters' marks, and sophisticated covered brick drainage channels dating to 580 BCE.",
        "summary_ta": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 580 \u0b95\u0bbf.\u0bae\u0bc1. \u0b95\u0bbe\u0bb2\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd\u0bb2\u0bbe\u0bb2\u0bcd \u0bae\u0bc2\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b85\u0ba4\u0bbf\u0ba8\u0bb5\u0bc0\u0ba9 \u0b95\u0bb4\u0bbf\u0bb5\u0bc1\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Keeladi: An Urban Settlement of Sangam Age (TNSDA Monograph 2019)",
            "Carbon-14 Dating Reports of Keeladi Stratigraphy",
            "Indian Archaeology Review 2015-18"
        ],
        "content": "# Keezhadi Inscribed Grooved Roof Tile & Drainage Epigraphs\n\n## The Urban Revolution at Keezhadi\nKeezhadi, situated 12 km southeast of Madurai on the Vaigai alluvial terrace, revolutionized early Indian historiography by demonstrating a fully literate, urbanized civic culture thriving by the 6th century BCE.\n\n## Architectural Stratigraphy of Roof Tiles\nOver eight seasons of excavations, Keezhadi yielded:\n1. **Flanged Grooved Tiles**: Tens of thousands of intact and fragmented terracotta roof tiles exhibiting raised lateral rims, double finger-drawn rainwater run-off channels, and underside suspension lugs.\n2. **Iron Nail Fasteners**: Numerous square-profile forged iron nails found directly embedded through the tile peg holes, proving they were fastened to timber gables.\n3. **Pre-Firing Tamil-Brahmi Inscriptions**: Tiles bearing scratched personal names such as *'Aadhan'* and *'Udhiran'*, indicating mass production by literate ceramic guilds.\n4. **Covered Brick Sump Drains**: Roof runoff descended into paved open courtyard drains constructed of terracotta pipes and brick culverts, discharging wastewater outside residential living quarters.",
        "chunks": [
            {
                "language": "en",
                "title": "Keezhadi Inscribed Roof Tiles & 6th Century BCE Drainage Systems",
                "content": "Excavations at Keezhadi yielded thousands of flanged grooved roof tiles with pre-firing Tamil-Brahmi inscriptions and iron nail fasteners dating to 580 BCE, integrated into brick drainage culverts."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd",
                "content": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd 580 \u0b95\u0bbf.\u0bae\u0bc1. \u0b95\u0bbe\u0bb2\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b86\u0ba3\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bc1\u0baa\u0bbf\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0ba8\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bbf\u0bb0\u0bc2\u0baa\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-uraiyur-master-roof-tile-pyrotechnician-kuyavan-odu-kollan.md",
        "slug": "char-uraiyur-master-roof-tile-pyrotechnician-kuyavan-odu-kollan",
        "category": "character",
        "name_en": "Uraiyur Master Roof Tile Pyrotechnician Kuyavan Odu Kollan",
        "name_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bb0\u0bcd \u0b95\u0bc1\u0baf\u0bb5\u0ba9\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Persona representing the hereditary master tile maker and kiln supervisor in Uraiyur, managing alluvial clay levigation, precision wooden mold pressing, and uniform kiln oxidation firing.",
        "summary_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd\u0ba3\u0bbf\u0bb2\u0bcd \u0bae\u0ba3\u0bb2\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bbf, \u0bae\u0bb0 \u0b85\u0b9a\u0bcd\u0b9a\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0b9f \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bc2\u0bb3\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bb3\u0bc8\u0bb5\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b9a\u0bc1\u0b9f\u0bcd\u0b9f\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bb0\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1.",
        "sources": [
            "Purananuru 228",
            "Akananuru 167",
            "Traditional Ceramic Technology of Kaveri Delta Potters"
        ],
        "content": "# Uraiyur Master Roof Tile Pyrotechnician Kuyavan Odu Kollan\n\n## The Master of the Flaming Clamp\nOperating on the northern outskirts of Uraiyur along the Kaveri floodplains, *Kuyavan Odu Kollan* commanded the royal brick and tile kilns (*Kalam*). Praised in Sangam verse (*Purananuru* 228) as the creator of monumental funeral urns and architectural ceramics, he possessed deep knowledge of thermal physics.\n\n## Craft Techniques\n1. **The Mold Strike (*Achu-Vettu*)**: Pressing prepared clay into two-part hardwood molds (*Marach-Chattam*), trimming excess clay with a wet copper wire, and stamping raised lateral flanges in a single rapid motion.\n2. **Finger-Groove Sweeping**: Drawing three fingers lubricated with sesame oil along the damp tile surface to create smooth, mirror-sheen water channels that shed debris.\n3. **Draft Balancing in the Kiln**: Reading the color of exhaust flames from kiln chimneys; adjusting clay dampers to maintain steady $850^\\circ\\text{C}$ heat, ensuring not a single tile warped or under-fired.",
        "chunks": [
            {
                "language": "en",
                "title": "Master Tilemaker Mold Pressing & Kiln Thermal Regulation",
                "content": "At Uraiyur, the master tile pyrotechnician supervised hardwood mold pressing, finger-drawn water groove sweeping, and balanced clamp kiln firing to produce warp-free architectural tiles."
            },
            {
                "language": "ta",
                "title": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bb0\u0bcd",
                "content": "\u0bae\u0bb0 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bb3\u0bbf\u0bae\u0ba3\u0bcd\u0ba3\u0bc8 \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0b95\u0bc8\u0bb5\u0bbf\u0bb0\u0bb2\u0bbe\u0bb2\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0bb0\u0bbf\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bc2\u0bb3\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bc0\u0bb0\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bb0\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-keezhadi-urban-drainage-and-roofing-architect-manai-sirpachari.md",
        "slug": "char-keezhadi-urban-drainage-and-roofing-architect-manai-sirpachari",
        "category": "character",
        "name_en": "Keezhadi Urban Drainage & Roofing Architect Manai Sirpachari",
        "name_ta": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0ba8\u0b95\u0bb0 \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf \u0bae\u0ba9\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "marutham",
        "summary_en": "Persona portraying the elite civic architect at Keezhadi calculating roof slope angles, supervising interlocking flanged tile installation, and integrating rooftop drainage with subterranean municipal sewers.",
        "summary_ta": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0ba8\u0b95\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bc2\u0bb0\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b9a\u0bbe\u0baf\u0bcd\u0bb5\u0bc1 \u0b95\u0bcb\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0ba3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bb4\u0bbf\u0bb5\u0bc1\u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc8\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b87\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bae\u0ba9\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf.",
        "sources": [
            "Nedunalvadai lines 75-110",
            "Keeladi Excavation Reports",
            "Ancient Indian Vastu and Civic Engineering Treatises"
        ],
        "content": "# Keezhadi Urban Drainage & Roofing Architect Manai Sirpachari\n\n## Civic Engineering in the 6th Century BCE\nIn the Vaigai metropolis of Keezhadi, the *Manai Sirpachari* was responsible for total building envelope engineering. He coordinated masonry, carpentry, and hydraulic drainage to build residences that withstood monsoons and high water tables.\n\n## Architectural Discipline\n- **Pitch Calculation**: Engineering rafter slopes at exactly $35^\\circ$\u2014steep enough to discharge cloudburst rains rapidly, but shallow enough to prevent wind lift during cyclonic storms.\n- **Nail-Peg Securing**: Inspecting the alignment of tiles, ensuring every third course was nailed to battens with forged iron nails.\n- **Drainage Integration**: Designing courtyard collection basins lined with terracotta ring conduits (*Urai*) that caught downspout torrents and fed them into street brick culverts without eroding unpaved alleyways.",
        "chunks": [
            {
                "language": "en",
                "title": "Keezhadi Civic Architect Roof Slope & Hydraulic Engineering",
                "content": "The Keezhadi civic architect calibrated 35-degree roof rafter slopes, secured interlocking tiles with forged iron nails, and integrated eaves downspouts into subterranean brick municipal sewers."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0ba8\u0b95\u0bb0 \u0bae\u0ba9\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b95\u0bc2\u0bb0\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b9a\u0bbe\u0baf\u0bcd\u0bb5\u0bc1 \u0b95\u0bcb\u0ba3\u0ba4\u0bcd\u0ba4\u0bc8\u0ba4\u0bcd \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0ba3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b86\u0ba3\u0bbf\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bb4\u0bc8\u0ba8\u0bc0\u0bb0\u0bcd \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0bb5\u0b9f\u0bbf\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bbe\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0ba3\u0bcd\u0ba3\u0bae\u0bcd \u0b95\u0bc0\u0bb4\u0b9f\u0bbf \u0bb5\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bbf."
            }
        ]
    },
    {
        "file": "knowledge/places/place-uraiyur-ancient-terracotta-tile-and-chola-capital-haven.md",
        "slug": "place-uraiyur-ancient-terracotta-tile-and-chola-capital-haven",
        "category": "place",
        "name_en": "Uraiyur: Ancient Terracotta Tile, Brick Kiln & Chola Capital Haven",
        "name_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Historic inland capital of the Early Cholas on the Kaveri River (Sangam Kozhiyur), renowned for extensive industrial pottery and tile kilns, fine brick architecture, and Tamil-Brahmi inscribed ceramics.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b86\u0bb1\u0bcd\u0bb1\u0bbf\u0ba9\u0bcd \u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2\u0b9a\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b89\u0ba9\u0bcd\u0ba9\u0ba4\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bae\u0bbe\u0ba9 \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bb5\u0bbe\u0baf\u0bcd\u0b95\u0bb3\u0bcd, \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bbe\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Purananuru 39",
            "Akananuru 167",
            "Archaeological Survey of India & Madras University Excavations at Uraiyur"
        ],
        "content": "# Uraiyur: Ancient Terracotta Tile, Brick Kiln & Chola Capital Haven\n\n## Geographic Setting on the Kaveri Floodplain\nUraiyur ($10.8200^\\circ\\text{ N}, 78.6800^\\circ\\text{ E}$), now part of Tiruchirappalli city, was situated on the elevated southern lev\u00e9e of the Kaveri River. This location provided endless supplies of high-silica, plastic alluvial silt, alongside river transport routes linking the capital eastward to Poompuhar and westward to Kongu country.\n\n## Industrial Metropolis of Sangam Kozhiyur\nCelebrated in Sangam anthologies as the capital of Karikala Chola, Uraiyur was a bustling manufacturing powerhouse:\n- **Tile & Brick Kiln Clusters (*Kalam*)**: Extensive kiln fields operating on the city periphery firing bricks, storage urns, and grooved roof tiles.\n- **Textile & Weaving Hub**: Famed for weaving diaphanous cotton textiles (*Aavi-yanna Pukal*) celebrated in Greco-Roman records as *Argaru*.\n- **Fortified Citadels**: Surrounded by moats and ramparts roofed with fire-resistant interlocking terracotta tiles.\n\n## Archaeological Stratigraphy\nExcavations revealed continuous cultural layers from 300 BCE to 1200 CE, unearthing brick-built dyeing vats, Tamil-Brahmi inscribed potsherds, ring wells (*Uraikkinaru*), and massive deposits of grooved terracotta roof tiles matching those found across the Chola heartland.",
        "chunks": [
            {
                "language": "en",
                "title": "Uraiyur Kaveri Levee Geography & Ceramic Tile Industry",
                "content": "Located on the Kaveri floodplain, ancient Uraiyur (Kozhiyur) leveraged rich alluvial clay beds to become the ceramic manufacturing and architectural tile capital of the Early Cholas."
            },
            {
                "language": "ta",
                "title": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bae\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b93\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bc1\u0bae\u0bcd",
                "content": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0bae\u0ba3\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0b95\u0bc2\u0bb0\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bbe\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b86\u0b9f\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bae\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "text-akanunuru-grooved-tile-roofs-and-monsoon-drainage-poetry",
        "describes_roof_tile_architecture",
        "concept-flanged-and-grooved-interlocking-terracotta-roof-tile-molding",
        "cultural",
        "Sangam Classical Era",
        "Akananuru poetry describes the interlocking grooved tile roofs of Uraiyur.",
        "Akananuru 167"
    ],
    [
        "text-akanunuru-grooved-tile-roofs-and-monsoon-drainage-poetry",
        "attests_drainage_mechanics",
        "concept-stormwater-eaves-gargoyles-and-slotted-tile-drainage-mechanics",
        "architectural",
        "Sangam Classical Era",
        "Akananuru verses detail eaves shedding monsoon rainwater.",
        "Akananuru 369"
    ],
    [
        "concept-flanged-and-grooved-interlocking-terracotta-roof-tile-molding",
        "manufactured_at",
        "place-uraiyur-ancient-terracotta-tile-and-chola-capital-haven",
        "industrial",
        "Early Historic Era",
        "Interlocking tiles were produced at Uraiyur kilns.",
        "Uraiyur Excavations"
    ],
    [
        "concept-high-silica-alluvial-clay-levigation-and-tile-firing-pyrotechnics",
        "practiced_by",
        "char-uraiyur-master-roof-tile-pyrotechnician-kuyavan-odu-kollan",
        "guild_membership",
        "Iron Age to Sangam Era",
        "The master pyrotechnician formulated clay levigation protocols.",
        "Purananuru 228"
    ],
    [
        "concept-fireproof-urban-tile-roofing-in-sangam-metropolises",
        "enforced_at",
        "place-uraiyur-ancient-terracotta-tile-and-chola-capital-haven",
        "civic",
        "Early Historic Sangam Era",
        "Uraiyur enforced fireproof tile roofing in commercial bazaars.",
        "Maduraikkanchi 350-375"
    ],
    [
        "concept-stormwater-eaves-gargoyles-and-slotted-tile-drainage-mechanics",
        "engineered_by",
        "char-keezhadi-urban-drainage-and-roofing-architect-manai-sirpachari",
        "architectural",
        "Iron Age to Sangam Era",
        "The civic architect designed eaves and subterranean drain connections.",
        "Keeladi Monograph"
    ],
    [
        "insc-uraiyur-chola-capital-brick-and-tile-kiln-guild-charters",
        "inscribed_at",
        "place-uraiyur-ancient-terracotta-tile-and-chola-capital-haven",
        "epigraphical",
        "Early Historic Era",
        "Uraiyur epigraphs confirm clay pit allocations to tile guilds.",
        "South Indian Inscriptions Vol. XIII"
    ],
    [
        "insc-keezhadi-inscribed-grooved-roof-tile-and-drainage-epigraphs",
        "attests_tile_antiquity",
        "concept-flanged-and-grooved-interlocking-terracotta-roof-tile-molding",
        "archaeological",
        "Iron Age to Sangam Era",
        "Keezhadi epigraphs date flanged grooved tiles to 580 BCE.",
        "Keeladi 2019 Reports"
    ],
    [
        "char-uraiyur-master-roof-tile-pyrotechnician-kuyavan-odu-kollan",
        "headquartered_at",
        "place-uraiyur-ancient-terracotta-tile-and-chola-capital-haven",
        "guild_membership",
        "Sangam Classical Era",
        "The master tilemaker operated his clamp kilns at Uraiyur.",
        "Oral History of Kaveri Potters"
    ],
    [
        "char-keezhadi-urban-drainage-and-roofing-architect-manai-sirpachari",
        "specifies_materials_from",
        "char-uraiyur-master-roof-tile-pyrotechnician-kuyavan-odu-kollan",
        "commercial",
        "Sangam Classical Era",
        "Civic architects procured standardized kiln-fired tiles from master pyrotechnicians.",
        "Chola-Pandya Inter-City Guild Exchanges"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 24 Corpus 3: Terracotta Roof Tile Pyrotechnics & Drainage into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 24 Corpus 3: Terracotta Roof Tile Pyrotechnics & Drainage Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
