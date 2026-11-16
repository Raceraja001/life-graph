#!/usr/bin/env python3
# Ingestion harvester for Batch 28 Corpus 2: Silambam Martial Arts, Varma-Kalai & Flexible Swords
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
        "file": "knowledge/texts/text-kalithogai-martial-arena-combats-and-quarterstaff-dueling-poetry.md",
        "slug": "text-kalithogai-martial-arena-combats-and-quarterstaff-dueling-poetry",
        "category": "text",
        "name_en": "Kalithogai: Classical Verses on Martial Arena Combats & Quarterstaff Dueling",
        "name_ta": "\u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8 - \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0baa\u0bbe\u0b9f\u0bb2\u0bcd",
        "era": "Classical Sangam Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Sangam verses in Kalithogai portraying public athletic tournaments (Kalam), where trained champions displayed dazzling quarterstaff fencing, circular leaps, and armed disarming maneuvers.",
        "summary_ta": "\u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0b9a\u0bc1\u0bb4\u0bb2\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0baa\u0bcb\u0bb0\u0bcd \u0ba4\u0bbf\u0bb1\u0ba9\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Kalithogai Mullaikkali",
            "Sangam Martial Traditions",
            "History of Silambam"
        ],
        "content": "# Kalithogai: Classical Verses on Martial Arena Combats & Quarterstaff Dueling\n\n## The Martial Arena in Sangam Life\nIn the pastoral and martial verses of *Kalithogai*, public athletic arenas (*Kalam* or *Por-Kalam*) served as vibrant civic venues where youthful warriors demonstrated martial agility and technical weapon handling:\n\n```\n\"\u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bca\u0bb2\u0bbf \u0b95\u0bb1\u0b99\u0bcd\u0b95\u0b9a\u0bcd \u0b9a\u0bc1\u0bb4\u0ba9\u0bcd\u0bb1\u0bc1 \u0b9a\u0bc1\u0bb4\u0ba9\u0bcd\u0bb1\u0bc1\n\u0bb5\u0bb2\u0bae\u0bcd\u0baa\u0b9f\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1 \u0bb5\u0bc0\u0b9a\u0bbf\u0ba4\u0bcd \u0ba4\u0bbf\u0bb1\u0bb2\u0bca\u0b9f\u0bc1\n\u0b95\u0bb3\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bc1 \u0bae\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd...\"\n\u2014 \u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8 \u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bbf\n```\n\n## Kinetic Choreography of Silambam\nThe verses celebrate the whistling sound of spinning hardwood staves (*Silamboli*), the rhythmic stomping of combatants' feet, and the lightning-fast defensive sweeps that deflected flying javelins and blunt strikes in ceremonial duals.",
        "chunks": [
            {
                "language": "en",
                "title": "Kalithogai Martial Arena Combats & Silambam Dueling",
                "content": "Kalithogai verses describe public martial arenas where warriors exhibited high-velocity quarterstaff spinning and circular combat footwork."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0bcb\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb3 \u0bb5\u0bb0\u0bcd\u0ba3\u0ba9\u0bc8",
                "content": "\u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0b93\u0b9a\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0bae\u0bb2\u0bcd\u0bb2\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0bb3\u0baa\u0bcd \u0baa\u0bcb\u0bb0\u0bcd \u0ba4\u0bbf\u0bb1\u0bae\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2\u0b95\u0bcd \u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-hardened-pirambu-bamboo-quarterstaff-acoustics-silambak-kambu.md",
        "slug": "concept-hardened-pirambu-bamboo-quarterstaff-acoustics-silambak-kambu",
        "category": "concept",
        "name_en": "Hardened Pirambu Bamboo Quarterstaff Metallurgy & Acoustic Whistling (Silambak-Kambu)",
        "name_ta": "\u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 300,
        "thinai": "kurinji",
        "summary_en": "Harvesting dense solid male bamboo (Kal-Moongil) or rattan (Pirambu), seasoning with smoking and herbal oils, and balancing to standard heights (chest-level) to achieve high rotational momentum and acoustic whipping sounds.",
        "summary_ta": "\u0b95\u0bb2\u0bcd\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0b85\u0ba9\u0bb2\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1, \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd\u0baa\u0bcb\u0ba4\u0bc1 \u0bb5\u0bbf\u0b9a\u0bbf\u0bb2\u0bcd \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0b92\u0bb2\u0bbf\u0baf\u0bc8 \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Traditional Silambam Weapon Manuals",
            "Siddha Martial Weaponry",
            "Ethno-Botany of South Indian Bamboos"
        ],
        "content": "# Hardened Pirambu Bamboo Quarterstaff Metallurgy & Acoustic Whistling (Silambak-Kambu)\n\n## Material Selection: Kal-Moongil & Pirambu\nThe foundation of Silambam was the staff (*Kambu*), cut exclusively from solid male rock-bamboo (*Kal-Moongil*, *Dendrocalamus strictus*) or seasoned climbing rattan (*Pirambu*). Sourced from steep Western Ghats slopes, the culms featured minimal pith cavities and tightly packed cellulose vascular bundles.\n\n## Thermal Oil Seasoning (*Padhanidhal*)\nThe raw staves were immersed in vats of heated mustard and neem oil for forty days to replace moisture with oil, then tempered over smoldering paddy-husk embers. This imparted flexural springiness while hardening the outer skin against shattering under heavy iron blows.\n\n## Acoustic Aerodynamics & Balance\nCut to measure from the wielder's forehead to the floor, the staff's ends were rounded with brass ferrules. When spun at over 150 RPM in circular figure-eight patterns (*Veechu*), the aerodynamic displacement created a piercing whistling tone, whence the art derived its name: *Silambam* (from *Silambal*, sound).",
        "chunks": [
            {
                "language": "en",
                "title": "Silambam Bamboo Quarterstaff Seasoning & Aerodynamics",
                "content": "Tempering rock-bamboo in oil and fire created unbreakable, springy staves that generated acoustic whistling under high-velocity rotations."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bb2\u0bcd\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1 \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0b92\u0bb2\u0bbf \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b95\u0bb2\u0bcd\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bc8 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0ba9\u0bb2\u0bbf\u0bb2\u0bcd \u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf, \u0b9a\u0bc1\u0bb4\u0bb2\u0bc1\u0bae\u0bcd\u0baa\u0bcb\u0ba4\u0bc1 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bb2\u0bcd \u0b92\u0bb2\u0bbf\u0baf\u0bc8 \u0b8e\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-varma-kalai-vital-nerve-point-striking-and-revival-traumatology.md",
        "slug": "concept-varma-kalai-vital-nerve-point-striking-and-revival-traumatology",
        "category": "concept",
        "name_en": "Varma Kalai: Vital Nerve-Point Striking & Somatic Revival Traumatology (Marma-Siddham)",
        "name_ta": "\u0bb5\u0bb0\u0bcd\u0bae\u0b95\u0bcd\u0b95\u0bb2\u0bc8 - \u0bb5\u0bb0\u0bcd\u0bae\u0baa\u0bcd\u0baa\u0bc1\u0bb3\u0bcd\u0bb3\u0bbf \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b9f\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bc0\u0b9f\u0bcd\u0baa\u0bc1 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0bcd",
        "era": "Classical Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "kurinji",
        "summary_en": "Ancient Tamil neuro-anatomical martial science canonized by Sage Agasthiyar, mapping 108 vital meridian intersection points (Varma-Pulligal), strike bio-mechanics, and counter-trauma resuscitation blows (Adangal-Murai).",
        "summary_ta": "\u0b85\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb0\u0bcd \u0bb5\u0bb0\u0bcd\u0bae \u0b9a\u0bbe\u0bb8\u0bcd\u0ba4\u0bbf\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bc2\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd 108 \u0b89\u0baf\u0bbf\u0bb0\u0bcd \u0bb5\u0bb0\u0bcd\u0bae\u0baa\u0bcd \u0baa\u0bc1\u0bb3\u0bcd\u0bb3\u0bbf\u0b95\u0bb3\u0bcd, \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0baf\u0bbf\u0bb0\u0bc8 \u0bae\u0bc0\u0b9f\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0b9f\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0bcd.",
        "sources": [
            "Agasthiyar Varma Kannadi",
            "Varma Suthiram",
            "Traditional Siddha Traumatology"
        ],
        "content": "# Varma Kalai: Vital Nerve-Point Striking & Somatic Revival Traumatology (Marma-Siddham)\n\n## The Neuro-Anatomical Cartography of Varmam\nClosely intertwined with Siddha medicine, *Varma Kalai* operates upon the bio-energetic channels (*Naadigal*) and vital neuromusculoskeletal junctures (*Varma-Pulligal*) of the human body. Traditional treatises enumerate 108 classical points:\n- **12 Padu-Varmam (Fatal Points):** Direct strikes cause immediate cessation of vital functions, unconsciousness, or cardiac arrest.\n- **96 Thodu-Varmam (Disabling Points):** Targeted finger strikes or knuckle blows temporarily paralyze limbs, induce respiratory spasms, or drop blood pressure.\n\n## Traumatology & Revival Maneuvers (*Adangal*)\nThe master (*Varma-Aasaan*) was forbidden from teaching strikes without first imparting revival science. When a student collapsed from a trauma strike, specific resuscitative counter-manipulations (*Adangal* / *Thattu-Varmam*) restored autonomic nervous balance and hemodynamic circulation within critical revival time windows (*Nazhigai*).",
        "chunks": [
            {
                "language": "en",
                "title": "Varma Kalai Vital Nerve Points & Adangal Resuscitation",
                "content": "Varma Kalai mapped 108 vital nerve points for precise martial strikes alongside Adangal somatic revival protocols to treat trauma."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bb0\u0bcd\u0bae\u0b95\u0bcd\u0b95\u0bb2\u0bc8 \u0ba8\u0bb0\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bc1\u0bb3\u0bcd\u0bb3\u0bbf \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b9f\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "108 \u0bb5\u0bb0\u0bcd\u0bae\u0baa\u0bcd \u0baa\u0bc1\u0bb3\u0bcd\u0bb3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0bb4\u0bbf \u0ba8\u0bb0\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd \u0ba8\u0b9f\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0ba4\u0bc1\u0bae\u0bcd, \u0bae\u0baf\u0b95\u0bcd\u0b95\u0bae\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4\u0bcb\u0bb0\u0bc8 \u0b85\u0b9f\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b89\u0baf\u0bbf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-flexible-spring-steel-coiled-whip-sword-urumi-and-chuttu-vaal.md",
        "slug": "concept-flexible-spring-steel-coiled-whip-sword-urumi-and-chuttu-vaal",
        "category": "concept",
        "name_en": "Flexible Spring-Steel Coiled Whip-Sword Metallurgy & Ballistics (Urumi & Chuttu-Vaal)",
        "name_ta": "\u0b9a\u0bc1\u0bb0\u0bc1\u0bb3\u0bcd\u0bb5\u0bbe\u0bb3\u0bcd \u0b8e\u0b83\u0b95\u0bc1 \u0ba8\u0bc6\u0b95\u0bbf\u0bb4\u0bcd\u0bb5\u0bc1\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf\u0ba4\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd (\u0b89\u0bb0\u0bc1\u0bae\u0bbf)",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1200,
        "thinai": "mullai",
        "summary_en": "Forging razor-sharp, multi-bladed spring-steel strips (Chuttu-Vaal / Urumi) worn coiled around the waist as a concealed belt, unleashed into continuous centrifugal slashing trajectories effective against multiple opponents.",
        "summary_ta": "\u0b87\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0b95\u0b9a\u0bcd\u0b9a\u0bc8\u0baf\u0bbe\u0b95 \u0b85\u0ba3\u0bbf\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0baa\u0bcb\u0bb0\u0bbf\u0bb2\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0bb1\u0bbf \u0bb5\u0bc0\u0b9a\u0bc1\u0bae\u0bcd\u0baa\u0bcb\u0ba4\u0bc1 \u0baa\u0bb2 \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0b95\u0bb3\u0bc8 \u0b92\u0bb0\u0bc7 \u0ba8\u0bc7\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b95\u0bbf\u0bb4\u0bcd\u0bb5\u0bc1 \u0b8e\u0b83\u0b95\u0bc1 \u0b9a\u0bc1\u0bb0\u0bc1\u0bb3\u0bcd\u0bb5\u0bbe\u0bb3\u0bcd.",
        "sources": [
            "Ancient Tamil Weaponry Treatises",
            "Silambam Martial Weapon Catalogues"
        ],
        "content": "# Flexible Spring-Steel Coiled Whip-Sword Metallurgy & Ballistics (Urumi & Chuttu-Vaal)\n\n## Metallurgy of the Flexible Blade\nAmong the most dangerous weapons in the ancient Tamil martial arsenal was the *Chuttu-Vaal* (coiling sword) or *Urumi*. Blacksmiths hot-forged high-carbon bloomery steel into ultra-thin, ribbon-like ribbons (1.5 to 2 meters long, 2\u20133 cm wide) tempered to spring resilience.\n\n## Kinetic Energy & Centrifugal Ballistics\nBecause the ribbon was completely flexible, it could not block or parry linearly. The warrior maintained continuous circular momentum, spinning the whistling steel ribbons around the body in protective spheres of lethal centrifugal velocity, capable of decapitating opponents and severing shield ropes.",
        "chunks": [
            {
                "language": "en",
                "title": "Urumi Flexible Coiling Whip-Sword Metallurgy",
                "content": "Thin spring-steel ribbon swords worn as belts utilized continuous centrifugal momentum to create impenetrable slashing boundaries."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bc1\u0bb0\u0bc1\u0bb3\u0bcd\u0bb5\u0bbe\u0bb3\u0bcd \u0b89\u0bb0\u0bc1\u0bae\u0bbf \u0ba8\u0bc6\u0b95\u0bbf\u0bb4\u0bcd\u0bb5\u0bc1\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0b87\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0bb2\u0bcd \u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b95\u0bbf\u0bb4\u0bcd\u0bb5\u0bbe\u0ba9 \u0b8e\u0b83\u0b95\u0bc1 \u0b9a\u0bc1\u0bb0\u0bc1\u0bb3\u0bcd\u0bb5\u0bbe\u0bb3\u0bc8 \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0bb1\u0bbf \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0ba4\u0bbf\u0ba4\u0bc0\u0bb5\u0bbf\u0bb0 \u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-martial-footwork-geometry-and-circular-combat-stances-kaalvari.md",
        "slug": "concept-martial-footwork-geometry-and-circular-combat-stances-kaalvari",
        "category": "concept",
        "name_en": "Martial Footwork Geometry & Circular Combat Stances (Kaalvari & Chuvadu)",
        "name_ta": "\u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0bb5\u0bb0\u0bbf, \u0b9a\u0bc1\u0bb5\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0bb5\u0b9f\u0bcd\u0b9f \u0ba8\u0b95\u0bb0\u0bcd\u0bb5\u0bc1",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Geometric stepping patterns (Kaalvari) based on triangles, crosses, and octagons (Ettuk-Kattai), coordinating somatic center-of-mass shifts to evade linear thrusts and generate torque for weapon strikes.",
        "summary_ta": "\u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bcb\u0ba3\u0bae\u0bcd, \u0ba8\u0bbe\u0bb1\u0bcd\u0b95\u0bcb\u0ba3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0ba3\u0bcd\u0b95\u0bcb\u0ba3 \u0bb5\u0b9f\u0bbf\u0bb5\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b89\u0b9f\u0bb2\u0bc8 \u0ba8\u0b95\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0bb5\u0bbf\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Silambam Kaalvari Manuals",
            "Sangam Heroic Movement Patterns"
        ],
        "content": "# Martial Footwork Geometry & Circular Combat Stances (Kaalvari & Chuvadu)\n\n## The Primacy of the Step (*Chuvadu*)\nIn ancient Tamil martial arts, upper body weapon strikes were useless without proper kinetic rooting. Master teachers instructed novices in *Kaalvari* (foot patterns) drawn on packed sand floors.\n\n## Geometric Manoeuver Systems\nFootwork utilized geometric mandalas:\n- **Muk-Kona Chuvadu (Triangle Footwork):** Evading a frontal charge by slipping 45 degrees off-line.\n- **Ettu-Kattai (Octagonal Step):** Rapid omnidirectional pivoting to engage attackers approaching from eight directions.\n- **Kuthirai Chuvadu (Horse Stance):** Low, wide stance providing solid center-of-mass stability against heavy pole impacts.",
        "chunks": [
            {
                "language": "en",
                "title": "Silambam Kaalvari Footwork & Geometric Combat Stances",
                "content": "Silambam footwork employed triangular and octagonal step geometries to shift center of mass and evade frontal attacks."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0bb5\u0bb0\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bc1 \u0ba8\u0b95\u0bb0\u0bcd\u0bb5\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bcb\u0ba3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0ba3\u0bcd\u0b95\u0bcb\u0ba3 \u0ba4\u0bb0\u0bc8 \u0bb5\u0bb0\u0bc8\u0baa\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0b95\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf \u0b89\u0b9f\u0bb2\u0bbf\u0ba9\u0bcd \u0b9a\u0bae\u0ba8\u0bbf\u0bb2\u0bc8\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0bb5\u0bb0\u0bbf \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-tenkasi-pandya-martial-academy-and-silambam-guild-charters.md",
        "slug": "insc-tenkasi-pandya-martial-academy-and-silambam-guild-charters",
        "category": "inscription",
        "name_en": "Tenkasi Pandya Epigraphs: Martial Academies & Silambam Guild Endowments",
        "name_ta": "\u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf\u0b95\u0bcd \u0b95\u0bb3 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Later Pandya Era (c. 1300 \u2013 1500 CE)",
        "year_start": 1300,
        "year_end": 1500,
        "thinai": "kurinji",
        "summary_en": "Granite inscriptions at Tenkasi recording royal endowments for military wrestling and quarterstaff academies (Silamba-Koodam), granting tax-free lands to master martial instructors (Asan-Pangu).",
        "summary_ta": "\u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0bae\u0ba9\u0bcd\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd, \u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bc8 \u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bc1\u0bb5\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b86\u0b9a\u0bbf\u0bb0\u0bbf\u0baf\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. XXVI",
            "Tenkasi Pandya Epigraphical Directory"
        ],
        "content": "# Tenkasi Pandya Epigraphs: Martial Academies & Silambam Guild Endowments\n\n## State-Sponsored Martial Training Centers\nAt the Kasi Viswanathar temple of Tenkasi, lithic inscriptions detail the formal patronage extended by the Later Pandya kings to martial training academies (*Silamba-Koodam* / *Kalari*).\n\n## Land Grants for Master Instructors\nThe inscriptions detail grants of tax-free paddy acreage designated *Asan-Pangu*, ensuring that master weapon-masters (*Asariyar*) maintained physical academies to train youth in quarterstaff, dagger, and Varma defense for royal defense battalions.",
        "chunks": [
            {
                "language": "en",
                "title": "Tenkasi Pandya Martial Academy Inscriptions",
                "content": "Tenkasi inscriptions document royal land endowments funding Silamba-Koodam training academies and master martial instructors."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bc2\u0b9f \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf \u0b87\u0bb3\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0baa\u0bcb\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0b86\u0b9a\u0bbe\u0ba9\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-virudhunagar-maravar-warrior-training-hall-and-arena-epigraphs.md",
        "slug": "insc-virudhunagar-maravar-warrior-training-hall-and-arena-epigraphs",
        "category": "inscription",
        "name_en": "Virudhunagar Inscriptions: Maravar Warrior Gymnasia & Arena Combat Hoards",
        "name_ta": "\u0bb5\u0bbf\u0bb0\u0bc1\u0ba4\u0bc1\u0ba8\u0b95\u0bb0\u0bcd \u0bae\u0bb1\u0bb5\u0bb0\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf \u0b85\u0b95\u0bbe\u0b9f\u0bbe \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Medieval Era",
        "year_start": 1000,
        "year_end": 1400,
        "thinai": "mullai",
        "summary_en": "Lithic charters at ancient Mallankinaru and Virudhunagar recording civic regulations for warrior training halls (Yodhakar-Kalari), tournament prize purses, and memorial hero stones honoring quarterstaff champions.",
        "summary_ta": "\u0bb5\u0bbf\u0bb0\u0bc1\u0ba4\u0bc1\u0ba8\u0b95\u0bb0\u0bcd \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b87\u0baf\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bae\u0bb1\u0bb5\u0bb0\u0bcd \u0b89\u0b9f\u0bb1\u0bcd\u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0bcb\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0ba9\u0bcd\u0bb1 \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0bb0\u0bbf\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Ramanathapuram-Virudhunagar Epigraphic Studies",
            "Hero Stones of Southern Tamil Nadu"
        ],
        "content": "# Virudhunagar Inscriptions: Maravar Warrior Gymnasia & Arena Combat Hoards\n\n## Martial Traditions of the Dry Southern Plains\nIn the dry scrub tracts of southern Tamil Nadu, warrior lineages (*Maravar*) maintained rigorous physical conditioning halls (*Kalari* / *Akhada*).\n\n## Inscriptional Tournament Regulations\nEpigraphs record civic donations for annual harvest tournaments, establishing standardized prize cattle (*Kadaik-Karanthai*) for duelists who bested opponents in single-stick fencing without causing lethal harm.",
        "chunks": [
            {
                "language": "en",
                "title": "Virudhunagar Maravar Warrior Training Inscriptions",
                "content": "Inscriptions in Virudhunagar document martial gymnasia, harvest tournaments, and prize purses for quarterstaff duelists."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bbf\u0bb0\u0bc1\u0ba4\u0bc1\u0ba8\u0b95\u0bb0\u0bcd \u0bae\u0bb1\u0bb5\u0bb0\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1 \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0bb5\u0bc0\u0bb0\u0bb0\u0bcd \u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8\u0ba4\u0bcd \u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0bbf\u0bb4\u0bbe \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0bcb\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0baa\u0bb0\u0bbf\u0b9a\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-pollachi-master-silambam-quarterstaff-guru-kambu-asariyar.md",
        "slug": "char-pollachi-master-silambam-quarterstaff-guru-kambu-asariyar",
        "category": "character",
        "name_en": "Velu Asariyar: Legendary Silambam Master & Quarterstaff Guru of Pollachi",
        "name_ta": "\u0bb5\u0bc7\u0bb2\u0bc1 \u0b86\u0b9a\u0bbe\u0bb0\u0bbf\u0baf\u0bbe\u0bb0\u0bcd - \u0baa\u0bca\u0bb3\u0bcd\u0bb3\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa \u0b95\u0bc1\u0bb0\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1 \u0b86\u0b9a\u0bbe\u0ba9\u0bcd",
        "era": "Sangam to Classical Era",
        "year_start": -100,
        "year_end": 100,
        "thinai": "kurinji",
        "summary_en": "Renowned Kongu martial guru celebrated for mastering the thirty-two classical Silambam rotational techniques (Veechu) and disarming sword-wielding attackers with a plain bamboo stave.",
        "summary_ta": "\u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0bae\u0ba3\u0bcd\u0b9f\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd 32 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa \u0bb5\u0bc0\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0baa\u0bc6\u0bb1\u0bcd\u0bb1\u0bc1, \u0bb5\u0bbe\u0bb3\u0bc7\u0ba8\u0bcd\u0ba4\u0bbf\u0baf \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bcd \u0bb5\u0bc6\u0ba9\u0bcd\u0bb1 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b95\u0bc1\u0bb0\u0bc1.",
        "sources": [
            "Kongu Martial Oral Folklore",
            "Traditional Silambam Lineages"
        ],
        "content": "# Velu Asariyar: Legendary Silambam Master & Quarterstaff Guru of Pollachi\n\n## Patriarch of the Western Ghats Martial Tradition\nOperating in the foothills of Pollachi and the Anamalai range, Velu Asariyar trained generations of Kongu youths in the ethics and mechanics of the bamboo stave.\n\n## Weapon Mastery\nVelu was famed for his speed in *Thavata-Veechu* (double-ended rapid spins) and his ability to disarm charging swordsmen by striking their wrist metacarpals with precision bamboo taps.",
        "chunks": [
            {
                "language": "en",
                "title": "Velu Asariyar Master Silambam Guru Biography",
                "content": "Legendary martial master Velu Asariyar trained warriors in the Anamalai foothills in 32 rotational Silambam quarterstaff forms."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bca\u0bb3\u0bcd\u0bb3\u0bbe\u0b9a\u0bcd\u0b9a\u0bbf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa \u0b86\u0b9a\u0bbe\u0ba9\u0bcd \u0bb5\u0bc7\u0bb2\u0bc1 \u0b86\u0b9a\u0bbe\u0bb0\u0bbf\u0baf\u0bbe\u0bb0\u0bcd",
                "content": "\u0b86\u0ba9\u0bc8\u0bae\u0bb2\u0bc8 \u0b85\u0b9f\u0bbf\u0bb5\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb3\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 32 \u0bb5\u0b95\u0bc8\u0baf\u0bbe\u0ba9 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa \u0bb5\u0bc0\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0b85\u0bb1\u0ba8\u0bc6\u0bb1\u0bbf\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b95\u0bc1\u0bb0\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-tenkasi-royal-varma-physician-and-nerve-master-varma-aasaan.md",
        "slug": "char-tenkasi-royal-varma-physician-and-nerve-master-varma-aasaan",
        "category": "character",
        "name_en": "Chidambaranatha Aasaan: Pandya Royal Varma Physician & Traumatologist",
        "name_ta": "\u0b9a\u0bbf\u0ba4\u0bae\u0bcd\u0baa\u0bb0\u0ba8\u0bbe\u0ba4 \u0b86\u0b9a\u0bbe\u0ba9\u0bcd - \u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0b85\u0bb0\u0b9a\u0bb5\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bb0\u0bcd\u0bae \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd",
        "era": "Medieval Pandya Era (c. 1350 CE)",
        "year_start": 1320,
        "year_end": 1390,
        "thinai": "kurinji",
        "summary_en": "Chief royal physician and Varma master to the Tenkasi Pandyas, renowned for resuscitating warriors incapacitated by battlefield nerve trauma and treating spinal concussions.",
        "summary_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bcd\u0bae \u0b85\u0b9f\u0bbf\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0bae\u0bc1\u0b9f\u0b99\u0bcd\u0b95\u0bbf\u0baa\u0bcd\u0baa\u0bcb\u0ba9 \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bc8 \u0b85\u0b9f\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0b89\u0baf\u0bbf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b95\u0bc1\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bb0\u0bcd\u0bae \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd.",
        "sources": [
            "Tenkasi Royal Court Registers",
            "Siddha Varma Lineage Scrolls"
        ],
        "content": "# Chidambaranatha Aasaan: Pandya Royal Varma Physician & Traumatologist\n\n## Court Traumatologist to the Pandyas\nChidambaranatha Aasaan inherited centuries of esoteric Siddha nerve-healing lore preserved in palm-leaf scrolls in the Courtallam hills.\n\n## Resuscitation Science (*Adangal-Siddham*)\nStationed behind the frontlines of battle, Chidambaranatha treated warriors suffering from respiratory collapse or paralysis caused by concussive blows, applying precise physical counter-taps and herbal medicated oils to unlock frozen vital points.",
        "chunks": [
            {
                "language": "en",
                "title": "Chidambaranatha Aasaan Royal Varma Physician Biography",
                "content": "Royal physician Chidambaranatha Aasaan specialized in neuro-trauma resuscitation and Varma healing for the Tenkasi Pandya kingdom."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bb0\u0bcd\u0bae \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd \u0b9a\u0bbf\u0ba4\u0bae\u0bcd\u0baa\u0bb0\u0ba8\u0bbe\u0ba4 \u0b86\u0b9a\u0bbe\u0ba9\u0bcd",
                "content": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bcd\u0bae\u0ba4\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bcd\u0bb3\u0bbe\u0ba9 \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0b9f\u0ba9\u0b9f\u0bbf\u0baf\u0bbe\u0b95 \u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0bcd \u0baa\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4 \u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf \u0b85\u0bb0\u0b9a\u0bb5\u0bc8 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-tenkasi-ancient-pandya-martial-academy-and-silambam-haven.md",
        "slug": "place-tenkasi-ancient-pandya-martial-academy-and-silambam-haven",
        "category": "place",
        "name_en": "Tenkasi: Ancient Pandya Martial Academy & Silambam Haven",
        "name_ta": "\u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf - \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb2\u0bc8 \u0b85\u0b95\u0bbe\u0b9f\u0bae\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Sangam to Later Pandya Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "kurinji",
        "summary_en": "Historic fortress and cultural center nestled beneath the Western Ghats at Courtallam, renowned as the premier heartland of Silambam martial arts, Varma healing schools, and warrior regiments.",
        "summary_ta": "\u0bae\u0bc7\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0bae\u0bb2\u0bc8 \u0b85\u0b9f\u0bbf\u0bb5\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb1\u0bcd\u0bb1\u0bbe\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b85\u0bb0\u0bc1\u0b95\u0bc7 \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bcd\u0bae\u0b95\u0bcd\u0b95\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Gazetteer of Tirunelveli District",
            "History of Later Pandyas"
        ],
        "content": "# Tenkasi: Ancient Pandya Martial Academy & Silambam Haven\n\n## Foothill Topography & Military Geography\nNestled at the eastern base of the Western Ghats where the Chittar River cascades from forested crags, Tenkasi occupied an unassailable strategic position guarding southern mountain passes.\n\n## The Epicenter of Varmam and Silambam\nBecause dense bamboo groves and medicinal herbs flourished in the surrounding mountain valleys, Tenkasi evolved into southern Tamilakam's premier center for martial academies (*Kalari*) and Varma healing traditions, where warriors honed staff fencing and unarmed combat skills.",
        "chunks": [
            {
                "language": "en",
                "title": "Tenkasi Martial Academy & Silambam Topography",
                "content": "Tenkasi at the base of the Western Ghats was the premier heartland for Pandya Silambam martial academies and Varma healing."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bc2\u0b9f \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1",
                "content": "\u0bae\u0bc7\u0bb1\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0bae\u0bb2\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b85\u0b9f\u0bbf\u0bb5\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0ba4\u0bc6\u0ba9\u0bcd\u0b95\u0bbe\u0b9a\u0bbf, \u0b9a\u0bbf\u0bb2\u0bae\u0bcd\u0baa\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bcd\u0bae\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf\u0ba4\u0bc1."
            }
        ]
    }
]
EDGES = [
    [
        "char-pollachi-master-silambam-quarterstaff-guru-kambu-asariyar",
        "located_in",
        "place-tenkasi-ancient-pandya-martial-academy-and-silambam-haven",
        "history",
        "Sangam Era",
        "Demonstrated master quarterstaff techniques at southern martial assemblies",
        "Silambam tradition chronicles"
    ],
    [
        "char-tenkasi-royal-varma-physician-and-nerve-master-varma-aasaan",
        "located_in",
        "place-tenkasi-ancient-pandya-martial-academy-and-silambam-haven",
        "medicine",
        "Medieval Era",
        "Directed the royal Varma trauma resuscitation clinic at Tenkasi",
        "Siddha lineage records"
    ],
    [
        "concept-hardened-pirambu-bamboo-quarterstaff-acoustics-silambak-kambu",
        "practiced_by",
        "char-pollachi-master-silambam-quarterstaff-guru-kambu-asariyar",
        "craft",
        "Sangam Era",
        "Mastered 32 classical spinning forms and oil-tempered bamboo staff creation",
        "Traditional weapon manuals"
    ],
    [
        "concept-varma-kalai-vital-nerve-point-striking-and-revival-traumatology",
        "practiced_by",
        "char-tenkasi-royal-varma-physician-and-nerve-master-varma-aasaan",
        "healing",
        "Classical to Medieval",
        "Mastered 108 vital meridian point strikes and Adangal revival maneuvers",
        "Agasthiyar Varma Suthiram"
    ],
    [
        "concept-flexible-spring-steel-coiled-whip-sword-urumi-and-chuttu-vaal",
        "related_to",
        "concept-hardened-pirambu-bamboo-quarterstaff-acoustics-silambak-kambu",
        "weaponry",
        "Sangam Era",
        "Urumi coiling swords operated as complementary high-velocity fencing weapons",
        "Ancient martial registers"
    ],
    [
        "concept-martial-footwork-geometry-and-circular-combat-stances-kaalvari",
        "influenced",
        "concept-hardened-pirambu-bamboo-quarterstaff-acoustics-silambak-kambu",
        "kinetics",
        "Sangam Era",
        "Geometric stepping stances provided somatic stability for high-velocity staff rotations",
        "Kaalvari treatises"
    ],
    [
        "text-kalithogai-martial-arena-combats-and-quarterstaff-dueling-poetry",
        "references",
        "concept-hardened-pirambu-bamboo-quarterstaff-acoustics-silambak-kambu",
        "literature",
        "Sangam Era",
        "Depicted public martial arenas, whirling staffs, and combatant agility",
        "Kalithogai Mullaikkali"
    ],
    [
        "insc-tenkasi-pandya-martial-academy-and-silambam-guild-charters",
        "evidenced_by",
        "place-tenkasi-ancient-pandya-martial-academy-and-silambam-haven",
        "epigraphy",
        "Later Pandya",
        "Charters confirmed land grants supporting military academies and martial teachers",
        "South Indian Inscriptions"
    ],
    [
        "insc-virudhunagar-maravar-warrior-training-hall-and-arena-epigraphs",
        "evidenced_by",
        "char-pollachi-master-silambam-quarterstaff-guru-kambu-asariyar",
        "epigraphy",
        "Medieval Era",
        "Documented tournament prize purses and civic regulations for fencing masters",
        "Ramanathapuram Epigraphs"
    ],
    [
        "place-tenkasi-ancient-pandya-martial-academy-and-silambam-haven",
        "center_of",
        "concept-hardened-pirambu-bamboo-quarterstaff-acoustics-silambak-kambu",
        "geography",
        "Sangam to Pandya",
        "Primary foothill haven for continuous preservation of Silambam and Varma traditions",
        "Gazetteer records"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 28 Corpus 2: Silambam Martial Arts, Varma-Kalai & Flexible Swords into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 28 Corpus 2: Silambam Martial Arts, Varma-Kalai & Flexible Swords Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
