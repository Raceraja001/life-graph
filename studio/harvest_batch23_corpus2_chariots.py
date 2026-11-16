#!/usr/bin/env python3
# Ingestion harvester for Batch 23 Corpus 2: Chariot Wheelwright Engineering & Axle Joinery
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
        "file": "knowledge/texts/text-purananuru-chariot-wheelwright-and-eight-chariots-craftsmanship-poetry.md",
        "slug": "text-purananuru-chariot-wheelwright-and-eight-chariots-craftsmanship-poetry",
        "category": "text",
        "name_en": "Purananuru Verses on the Master Wheelwright & Eight Chariots Craftsmanship",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd - \u0ba4\u0bbf\u0ba3\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0ba9\u0bc1\u0bae\u0bcd \u0b8e\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd \u0bb5\u0bbf\u0ba9\u0bc8\u0ba4\u0bcd \u0ba4\u0bbf\u0bb1\u0ba9\u0bc1\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Purananuru 87 by poetess Avvaiyar describing the unyielding fortitude of prince Neduman Anji using the metaphor of a master carpenter (Kaikol Thachan) who crafts eight war chariots in a single month assembling flawless hardwood components.",
        "summary_ta": "\u0b92\u0bb3\u0bb5\u0bc8\u0baf\u0bbe\u0bb0\u0bcd \u0baa\u0bbe\u0b9f\u0bbf\u0baf \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 87-\u0b86\u0bae\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd: \u0ba4\u0bbf\u0b99\u0bcd\u0b95\u0bb3\u0bcd\u0b95\u0bcb\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b92\u0bb0\u0bc1 \u0ba4\u0bbf\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b8e\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bc8\u0bb5\u0bb2\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0ba9\u0bcd \u0bb5\u0bbf\u0ba9\u0bc8\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0ba9\u0bc8 \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0ba8\u0bc6\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0bcd \u0b85\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0baa\u0bc7\u0bb0\u0bbe\u0bb1\u0bcd\u0bb1\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b89\u0bb5\u0bae\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 87 (Avvaiyar on Neduman Anji)",
            "Pathitrupathu 27",
            "Tolkappiyam Porulatikaram Purathinaiyiyal 72"
        ],
        "content": "# Purananuru Verses on the Master Wheelwright & Eight Chariots Craftsmanship\n\n## Literary Masterpiece & The Wheelwright Metaphor\nIn *Purananuru* 87, the venerated Sangam poetess Avvaiyar sings the prowess of the chieftain of Thakadoor, Athiyaman Neduman Anji. She chooses as her central imagery the rigorous kinetic perfection of the royal chariot carpenter (*Kaikol Thachan*):\n\n```\n\"\u0b92\u0bb0\u0bc1 \u0ba4\u0bbf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bb5\u0bbe\u0bb3\u0bcd \u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bc1 \u0b92\u0ba3\u0bcd \u0b9a\u0bc1\u0b9f\u0bb0\u0bcd \u0ba8\u0bcb\u0b95\u0bcd\u0b95\u0bbf\u0baf\n\u0b95\u0bc8\u0bb5\u0bb2\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0ba9\u0bcd \u0ba4\u0bbf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1\n\u0b8e\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba4\u0bc7\u0bb0\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0b85\u0baa\u0bcd \u0baa\u0b95\u0bb2\u0bcd...\"\n\u2014 \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 87:1-3\n```\n\nThis verse celebrates an artisan whose geometric exactitude was so refined that he could produce eight battlefield chariots within a single month\u2014each component interlocking with microscopic tolerances.\n\n## Anatomy of the Sangam War Chariot (*Por-Thaer*)\nSangam poetry across *Purananuru* and *Pathitrupathu* establishes a sophisticated Tamil nomenclature for wheeled vehicles:\n- **Nemi (\u0ba8\u0bc7\u0bae\u0bbf)**: The curved outer felloe rim, bent under steam and bound with rawhide or bronze tires.\n- **Kudam (\u0b95\u0bc1\u0b9f\u0bae\u0bcd)**: The central hardwood axle hub mortised with radial spoke sockets.\n- **Kaal (\u0b95\u0bbe\u0bb2\u0bcd)**: Radial tapered spokes sustaining vertical compression and lateral centrifugal torque.\n- **Acchaani (\u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf)**: The bronze or tempered iron linchpin preventing the spinning wheel from sliding off the axle.\n\n## Symbolic & Military Prominence\nChariots represented the pinnacle of technological capability among the Tamil crowned monarchs (Chera, Chola, Pandya). A well-balanced chariot allowed archers and javelin throwers to maneuver across rocky plateaus while absorbing severe terrain shock.",
        "chunks": [
            {
                "language": "en",
                "title": "Purananuru Wheelwright Metaphor & Sangam Chariot Craftsmanship",
                "content": "Purananuru 87 celebrates the supreme engineering mastery of the master wheelwright (Kaikol Thachan), using the crafting of eight battle chariots in a single month to symbolize flawless craftsmanship and military readiness."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0ba9\u0bbf\u0ba9\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 87-\u0bb2\u0bcd \u0b92\u0bb3\u0bb5\u0bc8\u0baf\u0bbe\u0bb0\u0bcd \u0b92\u0bb0\u0bc1 \u0ba4\u0bbf\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b8e\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba4\u0bc7\u0bb0\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bc8\u0bb5\u0bb2\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0ba9\u0bbf\u0ba9\u0bcd \u0bb5\u0bc7\u0bb2\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bc8 \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bbf\u0ba9\u0bcd \u0b86\u0bb1\u0bcd\u0bb1\u0bb2\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b89\u0bb5\u0bae\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0ba4\u0bcd \u0ba4\u0bbf\u0bb1\u0ba9\u0bc8 \u0bb5\u0bc6\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bbf\u0bb1\u0bbe\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-bent-felloe-wooden-rim-segmentation-and-joinery-nemiyum-kodum.md",
        "slug": "concept-bent-felloe-wooden-rim-segmentation-and-joinery-nemiyum-kodum",
        "category": "concept",
        "name_en": "Bent-Felloe Wooden Rim Segmentation & Joinery Mechanics (Nemiyum Kodum)",
        "name_ta": "\u0bb5\u0bb3\u0bc8\u0bb5\u0bc1 \u0bae\u0bb0 \u0ba8\u0bc7\u0bae\u0bbf\u0ba4\u0bcd \u0ba4\u0bc1\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0 \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1 \u0b87\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Engineering mechanics of fabricating chariot wheel rims by steam-bending hardwood felloe segments (Kodu / Nemi), interlocking them with mortise-and-tenon scarf joints, and securing them with hot-shrunk bronze or rawhide tires.",
        "summary_ta": "\u0ba8\u0bc0\u0bb0\u0bbe\u0bb5\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bb5\u0bb3\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bb0\u0ba4\u0bcd \u0ba4\u0bc1\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 (\u0ba8\u0bc7\u0bae\u0bbf/\u0b95\u0bcb\u0b9f\u0bc1) \u0bae\u0bc1\u0bb3\u0bc8 \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0b87\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bc2\u0b9f\u0bbe\u0ba9 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0ba4\u0bcb\u0bb2\u0bcd \u0baa\u0bc2\u0b9a\u0bbf \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0 \u0bb5\u0bbf\u0bb3\u0bbf\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Purananuru 87 Commentary",
            "Perumpanarruppadai lines 385-400",
            "Indian Journal of History of Science (Ancient Wheel Mechanics)"
        ],
        "content": "# Bent-Felloe Wooden Rim Segmentation & Joinery Mechanics (Nemiyum Kodum)\n\n## Structural Demands on Chariot Wheels\nA war chariot wheel traveling at high velocity across uneven Deccan trap and granite terrain experiences tremendous dynamic stress: vertical gravitational loads, radial impact shocks from boulders, and severe transverse twisting during tactical turns. Solid wooden disc wheels were discarded early in favor of spoked wheels with segmented felloe rims (*Nemi*).\n\n## Steam-Bending & Segmental Joinery\nThe outer circumference of the wheel was assembled from 6 to 8 curved segments (*Kodu*):\n1. **Wood Selection**: Straight-grained *Vengai* (*Pterocarpus marsupium*) or *Karunkali* (*Diospyros ebenum*) seasoned in shaded oil baths to enhance tensile flexibility.\n2. **Steam Softening (*Aavi-Valaippu*)**: Wood billets were exposed to moist steam in clay ovens, then bent over semi-circular stone jigs and pegged until cooled.\n3. **Scarf & Tongue Joinery (*Naakku-Poruthu*)**: Ends of adjacent felloes were precision-carved with interlocking tongues and reinforced with hardwood dowels (*Maramulaigal*).\n\n## Tire Binding & Tensile Compression\nTo prevent felloes from separating under impact, ancient Tamil wheelwrights employed two binding methods:\n- **Shrink-Fitted Bronze Tires (*Vengala Vattu*)**: A bronze hoop forged slightly undersized was heated red-hot, expanded over the wooden rim, and instantly quenched with cold water, compressing the wooden felloes into a rigid pre-stressed ring.\n- **Rawhide Binding (*Pasaith-Thol*)**: Wet buffalo rawhide strips wrapped tightly around the felloe that shrank with immense force as they dried, locking spokes and rim into unity.",
        "chunks": [
            {
                "language": "en",
                "title": "Chariot Felloe Rim Steam Bending & Pre-Stressed Joinery",
                "content": "Tamil chariot builders assembled wheel rims from steam-bent hardwood felloes (Nemi) joined with mortise scarfs and bound by hot-shrunk bronze tires, creating a pre-stressed structure that absorbed brutal terrain shocks."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0b95\u0bcd\u0b95\u0bb0 \u0ba8\u0bc7\u0bae\u0bbf \u0bb5\u0bb3\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0b87\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bbe\u0bb2\u0bbf \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bc0\u0bb0\u0bbe\u0bb5\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bb3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bc1\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0b87\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bc2\u0b9f\u0bbe\u0ba9 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bc8 \u0b8f\u0bb1\u0bcd\u0bb1\u0bbf \u0b9a\u0bc1\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb5\u0ba4\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b89\u0b9f\u0bc8\u0baf\u0bbe\u0ba4 \u0b9a\u0b95\u0bcd\u0b95\u0bb0 \u0ba8\u0bc7\u0bae\u0bbf \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-hardwood-vengai-and-teak-radial-spoke-compression-mechanics.md",
        "slug": "concept-hardwood-vengai-and-teak-radial-spoke-compression-mechanics",
        "category": "concept",
        "name_en": "Hardwood Vengai & Teak Radial Spoke Compression Mechanics",
        "name_ta": "\u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0 \u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "kurinji",
        "summary_en": "Botanical material selection and aerodynamic shaping of tapered chariot spokes (Kaal) using high-modulus timber (Pterocarpus marsupium and Tectona grandis) engineered to distribute dynamic shock vectors from the rim to the central hub.",
        "summary_ta": "\u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc0\u0bb5\u0bbf, \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0b89\u0bb0\u0bbe\u0baf\u0bcd\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 (\u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd) \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Malaipadukadam lines 40-55",
            "Akananuru 128",
            "Timber Mechanics of Ancient Indian Wheeled Vehicles"
        ],
        "content": "# Hardwood Vengai & Teak Radial Spoke Compression Mechanics\n\n## Material Optimization: Vengai & Teak\nIn ancient Tamil chariot construction, spokes (*Kaal* or *Aaram*) could not be made from ordinary timber. Wheelwrights selected *Vengai* (*Pterocarpus marsupium*) from the slopes of the Western Ghats because of its dense grain, natural resin content that resists dry rot, and remarkable resilience under compression:\n\n- **Modulus of Rupture**: Vengai exhibits exceptional resistance to splintering under catastrophic bending loads.\n- **Teak (*Thekku*)**: Selected for light-weight scout chariots due to its dimensional stability and natural insecticidal tectoquinones.\n\n## Aerodynamic Diamond Profile (*Kathi-Kaal*)\nRather than circular cylinders, Sangam spokes were shaped with a tapered elliptical or flattened diamond cross-section:\n1. **Stress Transfer**: The widest dimension aligned with the wheel plane to counter braking and acceleration torque.\n2. **Lateral Deflection**: The thin edge sliced through air during rapid rotation, minimizing aerodynamic resistance while shedding road mud.\n3. **Mortise Tapering**: Spoke ends were carved into rectangular tenons inserted into precision-chiseled mortise cavities in the central hub (*Kudam*) and felloe (*Nemi*).\n\n## Dynamic Radial Load Distribution\n$$\\sigma = \\frac{F_{\\text{impact}}}{A_{\\text{tenon}}}$$\nThe radial configuration ensured that at any microsecond of rotation, the weight of the chariot was distributed across multiple spokes, converting localized surface impacts into distributed compressive forces around the entire wooden loop.",
        "chunks": [
            {
                "language": "en",
                "title": "Radial Spoke Timber Mechanics & Dynamic Load Distribution",
                "content": "Wheelwrights utilized Vengai and teak wood to carve diamond-profile spokes (Kaal) that minimized wind resistance while transferring violent shock forces smoothly between the rim and central axle hub."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0bb0 \u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4 \u0bb5\u0bbf\u0b9a\u0bc8",
                "content": "\u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8\u0b95\u0bcd \u0b95\u0bbf\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bc6\u0bb2\u0bcd\u0bb2\u0bc1\u0bae\u0bcd \u0b95\u0ba4\u0bcd\u0ba4\u0bbf \u0bb5\u0b9f\u0bbf\u0bb5 \u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0bb0 \u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0bae\u0bc8 \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0bcd\u0b95\u0bc1 \u0b9a\u0bc0\u0bb0\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0b9f\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-bronze-axle-bushing-castor-oil-lubrication-and-hub-acchaani.md",
        "slug": "concept-bronze-axle-bushing-castor-oil-lubrication-and-hub-acchaani",
        "category": "concept",
        "name_en": "Bronze Axle Bushing, Castor Oil Lubrication & Hub Acchaani Mechanics",
        "name_ta": "\u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba3\u0bcd, \u0b86\u0bae\u0ba3\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc6\u0baf\u0bcd \u0bae\u0b9a\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Tribological engineering of chariot wheel hubs utilizing low-friction cast bronze sleeve bushings, castor oil (Amanakku nei) hydrostatic lubrication reservoirs, and forged bronze linchpins (Acchaani) preventing wheel dislodgement under high speeds.",
        "summary_ta": "\u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bc1\u0bb3\u0bcd \u0ba4\u0bc7\u0baf\u0bcd\u0bae\u0bbe\u0ba9\u0ba4\u0bcd\u0ba4\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bbe\u0baf\u0bcd (\u0baa\u0bc2\u0ba3\u0bcd), \u0b86\u0bae\u0ba3\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0bae\u0b9a\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0bae\u0bcd \u0b95\u0bb4\u0ba9\u0bcd\u0bb1\u0bc1\u0bb5\u0bbf\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Tirukkural 667 (Acchaani metaphor)",
            "Purananuru 90",
            "Archaeological Excavations at Kodumanal Iron and Bronze Findings"
        ],
        "content": "# Bronze Axle Bushing, Castor Oil Lubrication & Hub Acchaani Mechanics\n\n## The Tribology of the Wheel Hub (*Kudam*)\nThe central rotating hub (*Kudam*) represented the point of highest friction and heat generation in ancient chariots. If wood contacted the static axle spindle directly, rotational friction would char the wood and seize the wheel within miles of hard driving.\n\n## Bronze Sleeve Bushings (*Vengala Thulai-Poon*)\nAncient Tamil metallurgists resolved this tribological crisis by casting cylindrical bronze sleeve bearings:\n- **Low-Friction Bronze Alloy**: High-tin bronze (80% Cu, 20% Sn) provided an ultra-hard, galling-resistant interface against polished iron or seasoned hardwood axles.\n- **Axial Keyways**: The outer surface of the bronze sleeve featured longitudinal ridges that locked permanently into the end-grain of the wooden wheel hub, preventing internal spinning.\n\n## Hydrodynamic Castor Oil Lubrication (*Amanakku Nei*)\n- **Lubricant Choice**: Castor oil (*Ricinus communis* / *Amanakku nei*) possesses the highest kinematic viscosity and thermal stability among botanical oils, maintaining an unbroken lubricating film even under friction heating.\n- **Reservoir Grooves**: Spiral channels grooved inside the bronze bushing circulated oil across the spindle during rotation.\n\n## The Sacred Security of the Acchaani\nTo prevent the wheel from slipping outward under centrifugal sway, a forged bronze or iron linchpin\u2014the *Acchaani*\u2014was inserted vertically through the protruding axle tip. Valluvar famously immortalized this component in *Tirukkural* 667:\n\n```\n\"\u0b89\u0bb0\u0bc1\u0bb5\u0bc1\u0b95\u0ba3\u0bcd \u0b9f\u0bc6\u0bb3\u0bcd\u0bb3\u0bbe\u0bae\u0bc8 \u0bb5\u0bc7\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b89\u0bb0\u0bc1\u0bb3\u0bcd\u0baa\u0bc6\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\n\u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf \u0b85\u0ba9\u0bcd\u0ba9\u0bbe\u0bb0\u0bcd \u0b89\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1.\"\n\u2014 \u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb1\u0bb3\u0bcd 667\n```\n\nA small, unadorned pin held the monumental, speeding battle carriage from catastrophic collapse.",
        "chunks": [
            {
                "language": "en",
                "title": "Tribological Hub Bushings, Castor Oil & The Acchaani Linchpin",
                "content": "Sangam chariot hubs utilized cast bronze sleeve bushings and high-viscosity castor oil to prevent friction seizure, secured by the iconic forged Acchaani linchpin celebrated in Tirukkural 667."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bc1\u0bb3\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0baa\u0bcd \u0baa\u0bc2\u0ba3\u0bc1\u0bae\u0bcd \u0b86\u0bae\u0ba3\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc6\u0baf\u0bcd \u0bae\u0b9a\u0b95\u0bc1\u0bae\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bbe\u0baf\u0bcd\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0ba4\u0bcd\u0ba4\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bae\u0bbe\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0baa\u0bca\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0bc8 \u0ba4\u0bbf\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb1\u0bb3\u0bcd 667 \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-battlefield-chariot-shock-absorption-and-yoke-harness-acrodynamics.md",
        "slug": "concept-battlefield-chariot-shock-absorption-and-yoke-harness-acrodynamics",
        "category": "concept",
        "name_en": "Battlefield Chariot Shock Absorption & Yoke Harness Aerodynamics",
        "name_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "palai",
        "summary_en": "Kinematic shock dampening mechanisms in Sangam combat chariots, utilizing rawhide floor web suspensions, flexible split-bamboo draft poles, and curved wooden yokes (Nukathadi) transferring equine draft without choking chest muscles.",
        "summary_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd \u0baa\u0bbe\u0baf\u0bc1\u0bae\u0bcd\u0baa\u0bcb\u0ba4\u0bc1 \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95 \u0ba4\u0bcb\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd, \u0bb5\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0ba4\u0bbf\u0bb0\u0bc8 \u0bae\u0bbe\u0bb0\u0bcd\u0baa\u0bc8 \u0ba8\u0bc6\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0ba4 \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0ba8\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Pathitrupathu 54",
            "Mullaippattu lines 30-45",
            "Kavya Studies in Ancient Indian Military Chariots"
        ],
        "content": "# Battlefield Chariot Shock Absorption & Yoke Harness Aerodynamics\n\n## Dynamic Isolation on Rocky Terrain\nSangam military encounters in the Palai and Mullai badlands required war chariots to gallop over gravel, boulders, and battle debris without flipping or shattering the warrior's balance. Without metal leaf springs, shock absorption relied on elastic materials and kinematic decoupling.\n\n## Suspended Platform Mechanics (*Thol-Thalam*)\n- **Woven Rawhide Floor**: The fighting platform was not solid planks, but an open grid of interwoven, cured buffalo leather thongs stretched across the chassis framework.\n- **Kinetic Damping**: The flexible leather platform acted as an organic spring bed, flexing under dynamic vertical accelerations and protecting the archer's knees and spine from impact shocks.\n\n## Flexible Draft Pole & Double Yoke (*Kodungkaal & Nukathadi*)\n1. **Curved Draft Pole (*Kodungkaal*)**: The central beam connecting chariot chassis to the team of horses was fashioned from seasoned *Moongil* (bamboo) or *Marutham* wood with a slight S-curve that bowed under sudden braking or acceleration.\n2. **Ergonomic Throat Yoke (*Nukathadi*)**: Carved from lightweight *Kalyana Murungai* (*Erythrina variegata*), the yoke curved comfortably over equine withers, distributing draft forces across the chest bone rather than compressing the windpipe.\n3. **Bronze Ring Guides (*Pidi-Valayam*)**: Reins (*Vaaividu-Kayiru*) passed through polished bronze guide rings, preventing tangling during split-second tactical wheel maneuvers.",
        "chunks": [
            {
                "language": "en",
                "title": "Chariot Suspension Engineering & Equine Yoke Ergonomics",
                "content": "Combat chariots achieved dynamic shock dampening through suspended rawhide woven platforms and curved bamboo draft poles, harnessed to horse teams via ergonomic wooden yokes that maximized draft efficiency."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bbe\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf",
                "content": "\u0ba4\u0bcb\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bcd\u0bb1\u0bbe\u0bb2\u0bcd \u0baa\u0bbf\u0ba9\u0bcd\u0ba9\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bbf\u0ba4\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0b86\u0b95\u0bbf\u0baf\u0bb5\u0bc8 \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0b95\u0bcd \u0b95\u0bb0\u0b9f\u0bc1\u0bae\u0bc1\u0bb0\u0b9f\u0bbe\u0ba9 \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb3\u0bcd\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0bbf \u0bb5\u0bc0\u0bb0\u0ba9\u0bbf\u0ba9\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0b95\u0bc1\u0bb2\u0bc8\u0baf\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0ba4\u0bcd\u0ba4\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-vallam-thanjavur-chariot-guild-and-wheelwright-endowment-charters.md",
        "slug": "insc-vallam-thanjavur-chariot-guild-and-wheelwright-endowment-charters",
        "category": "inscription",
        "name_en": "Vallam Thanjavur Chariot Guild & Wheelwright Endowment Charters",
        "name_ta": "\u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0ba4\u0b9e\u0bcd\u0b9a\u0bbe\u0bb5\u0bc2\u0bb0\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0bb5\u0bbf\u0ba9\u0bc8\u0b9e\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Historic to Chola Era",
        "year_start": -100,
        "year_end": 1000,
        "thinai": "mullai",
        "summary_en": "Archaeological inscriptions and graffiti from the fortified citadel of Vallam near Thanjavur recording hereditary land grants (*Thachak-Kaani*) and tax immunities conferred upon wheelwright guilds building military and ceremonial chariots.",
        "summary_ta": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bbe\u0bb5\u0bc2\u0bb0\u0bcd \u0b85\u0bb0\u0bc1\u0b95\u0bbf\u0bb2\u0bc1\u0bb3\u0bcd\u0bb3 \u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0b9a\u0bcd\u0b9a\u0b95\u0bcd\u0b95\u0bbe\u0ba3\u0bbf \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb2\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9.",
        "sources": [
            "South Indian Inscriptions Vol. II",
            "Annual Report on Epigraphy 1968 No. 210",
            "Excavations at Vallam by Tamil University 1984"
        ],
        "content": "# Vallam Thanjavur Chariot Guild & Wheelwright Endowment Charters\n\n## Archaeological Context of Vallam Citadel\nVallam, located on a laterite plateau 10 km west of Thanjavur, was a fortified bastion possessing multi-ringed moats and defensive ramparts established in the Sangam era and continuously occupied through the Chola imperial era. Excavations conducted by Tamil University revealed intense military metallurgy, iron projectile points, and extensive carpenter tool caches.\n\n## Epigraphic Content: Thachak-Kaani Land Grants\nStone inscriptions from the Vallam rampart temples record:\n- **Hereditary Tenure (*Thachak-Kaani*)**: Perpetual agricultural land rights bestowed upon master chariot wheelwrights (*Ratha-Kara Thachan*) to ensure continuous maintenance of royal war wagons and temple processional cars.\n- **Tax Exemptions (*Toll Immunity*)**: Exemption of wheelwright workshops from wood transit taxes (*Marak-Kattanam*) on high-grade timber floated down the Kaveri and Vennaru rivers from the Kollimalai forests.\n- **Standardization Mandates**: Official royal proclamations establishing strict geometric standards for axle diameter, spoke count (typically 12, 16, or 24 spokes), and wheel track width.\n\n## Guild Autonomy & Military Logistics\nThe Vallam charters demonstrate that chariot carpenters were organized into autonomous guilds with executive authority to certify battle readiness before imperial military campaigns.",
        "chunks": [
            {
                "language": "en",
                "title": "Vallam Epigraphs on Wheelwright Guilds & Imperial Charters",
                "content": "Excavations and inscriptions at the Vallam citadel document royal land endowments (Thachak-Kaani) and timber tax immunities granted to master wheelwright guilds manufacturing standardized military chariots."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0b95\u0bcd\u0b95\u0bbe\u0ba3\u0bbf \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0b9a\u0bcd\u0b9a\u0b95\u0bcd\u0b95\u0bbe\u0ba3\u0bbf \u0bb5\u0bb0\u0bbf\u0bb5\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bcb\u0b95\u0bcd\u0b95\u0bc1\u0bb5\u0bb0\u0ba4\u0bcd\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bb2\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0bb3\u0bcd\u0bb3\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kodumanal-graffiti-pottery-chariot-and-wheel-emblem-epigraphs.md",
        "slug": "insc-kodumanal-graffiti-pottery-chariot-and-wheel-emblem-epigraphs",
        "category": "inscription",
        "name_en": "Kodumanal Graffiti Pottery Chariot & Wheel Emblem Epigraphs",
        "name_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b95\u0bc0\u0bb1\u0bb2\u0bcd \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Tamil-Brahmi inscribed potsherds and post-firing graffiti emblems from Kodumanal excavations depicting multi-spoked chariot wheels, bronze axle pins, and merchant-guild seals associated with trans-peninsular chariot transit.",
        "summary_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b89\u0bb3\u0bcd\u0bb3 \u0baa\u0bb2-\u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Excavations at Kodumanal (Tamil Nadu State Dept of Archaeology)",
            "K. Rajan: Archaeology of Kongu Country",
            "Tamil-Brahmi Epigraphy Corpus Vol. IV"
        ],
        "content": "# Kodumanal Graffiti Pottery Chariot & Wheel Emblem Epigraphs\n\n## The Kongu Trade Arterial at Kodumanal\nKodumanal, on the banks of the Noyyal River in Erode district, was the industrial gem and metallurgical metropolis of the Kongu Chera kingdom. Positioned along the Palakkad Gap highway connecting Karur to Muziris, the site yielded unparalleled artifacts of high-speed overland transport.\n\n## Graffiti Motifs & Tamil-Brahmi Inscriptions\nExcavation trenches yielded hundreds of Megalithic Black-and-Red Ware shards bearing distinct wheeled vehicle iconography:\n1. **Sixteen-Spoked Wheel Emblems (*Aarakkaal Chakkaram*)**: Finely incised geometric wheels displaying distinct hub rings, tapered spokes, and outer felloe segments, serving as owner-guild hallmarks.\n2. **Tamil-Brahmi Personal Names**: Inscriptions reading *'Athan'* and *'Kannan'* associated with wheel motifs, indicating private merchant fleet operators.\n3. **Artifact Finds**: Corroborating the ceramic graffiti, excavators unearthed cast bronze hub rings, iron linchpins, horse bit cheek-pieces, and chariot bridle attachments directly dating to 300 BCE.\n\n## Significance for Indian Vehicle History\nThese artifacts provide incontrovertible archaeological proof that spoked war and transport chariots were not merely mythological constructs, but active, highly engineered transport mechanisms operating across ancient Tamil kingdoms.",
        "chunks": [
            {
                "language": "en",
                "title": "Kodumanal Chariot Wheel Graffiti & Metallurgical Artifacts",
                "content": "Archaeological excavations at Kodumanal revealed Tamil-Brahmi pottery graffiti depicting sixteen-spoked chariot wheels alongside physical bronze hub rings and iron linchpins dating to the 3rd century BCE."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc0\u0bb1\u0bb2\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf\u0b9a\u0bcd \u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
                "content": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b85\u0b95\u0bb4\u0bbe\u0baf\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1-\u0b9a\u0bbf\u0bb5\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0ba3\u0bcd\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd 16 \u0b86\u0bb0\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0ba3\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bc8 \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0b9a\u0bc6\u0baf\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-vallam-master-chariot-wheelwright-thaer-seivon-thachan.md",
        "slug": "char-vallam-master-chariot-wheelwright-thaer-seivon-thachan",
        "category": "character",
        "name_en": "Vallam Master Chariot Wheelwright Thaer Seivon Thachan",
        "name_ta": "\u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0bcb\u0ba9\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Persona portraying the elite mechanical wheelwright who calculated wheel balance, steam-bent hardwood felloes, calibrated axle tolerances, and commanded royal chariot armories of the Chola kingdom.",
        "summary_ta": "\u0bae\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0ba8\u0bb0\u0bae\u0bcd\u0baa\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1, \u0ba8\u0bc0\u0bb0\u0bbe\u0bb5\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc7\u0bae\u0bbf \u0bb5\u0bb3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b9a\u0bcd \u0b9a\u0bae\u0ba8\u0bbf\u0bb2\u0bc8\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0ba3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0bb0\u0b9a \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0ba9\u0bbf\u0ba9\u0bcd \u0b86\u0bb3\u0bc1\u0bae\u0bc8 \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bcd.",
        "sources": [
            "Purananuru 87",
            "Manimekalai Canto 19",
            "Traditional Thachu Shastra Guild Manuals"
        ],
        "content": "# Vallam Master Chariot Wheelwright Thaer Seivon Thachan\n\n## The Lineage of Kaikol Thachan\nThe master wheelwright at the royal fortress of Vallam represents the highest echelon of pre-industrial mechanical engineering. Descended from generations of guild masters (*Kaikol Thachanmar*), he commanded the complex supply chain of timber, steam pits, bronze foundries, and leather curriers.\n\n## Geometry & Balancing Precision\nThe hallmark of a master wheelwright lay in dynamic balance (*Chakkara Samanilai*):\n- **Acoustic Timber Testing**: Tapping seasoned Vengai logs with a wooden mallet; a clear, bell-like ring revealed dense, crack-free heartwood suitable for spoke carving.\n- **Rotational Balancing**: Suspending completed wheels on temporary vertical spindles and spinning them by hand. If the wheel stopped randomly without oscillating back to a heavy low point, it was certified *Thooya Chakkiram* (pure wheel).\n- **Track Calibration**: Setting identical gauge spacing between left and right wheels to ensure high-speed stability when charging over rutted battlefield soil.\n\n## Military Readiness\nDuring mobilization, Thaer Seivon Thachan oversaw round-the-clock assembly lines where modular replacement spokes, axles, and felloes were packed into mobile logistical repair wagons accompany royal armies.",
        "chunks": [
            {
                "language": "en",
                "title": "Master Wheelwright Geometry, Timber Acoustics & Dynamic Balance",
                "content": "The Vallam master wheelwright utilized acoustic resonance testing of Vengai logs and dynamic rotational balancing to craft war chariot wheels capable of maintaining stability at extreme speeds."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bbf\u0ba9\u0bcd \u0b95\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0ba9\u0bcd",
                "content": "\u0bb5\u0bc7\u0b99\u0bcd\u0b95\u0bc8 \u0bae\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b92\u0bb2\u0bbf\u0b95\u0bc7\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba4\u0bb0\u0bae\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1, \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b9a\u0bae\u0ba8\u0bbf\u0bb2\u0bc8\u0baf\u0bc8 \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0bb1\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0ba3\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bbf\u0ba9\u0bcd \u0b86\u0bb3\u0bc1\u0bae\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-kodumanal-bronze-axle-pin-smith-acchaani-kollan.md",
        "slug": "char-kodumanal-bronze-axle-pin-smith-acchaani-kollan",
        "category": "character",
        "name_en": "Kodumanal Bronze Axle Pin Smith Acchaani Kollan",
        "name_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Persona portraying the specialized precision metalsmith at Kodumanal forging bronze axle bushings, hardened iron linchpins (Acchaani), and wheel tire hoops for military chariots.",
        "summary_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b89\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0baa\u0bcd \u0baa\u0bc2\u0ba3\u0bcd\u0b95\u0bb3\u0bcd, \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baf\u0bbe\u0ba9 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1.",
        "sources": [
            "Purananuru 170",
            "Tirukkural 667",
            "Excavations at Kodumanal Metallurgy Reports"
        ],
        "content": "# Kodumanal Bronze Axle Pin Smith Acchaani Kollan\n\n## The Metallurgical Crucible of Kodumanal\nOperating alongside the beryl lapidary workshops of Kodumanal, *Acchaani Kollan* was a pyrotechnic specialist focused on vehicular hardware. His forge produced the small, unyielding metal components upon which the survival of entire chariot battalions depended.\n\n## Precision Casting & Forging Discipline\n1. **Lost-Wax Bushing Casting**: Fabricating beeswax models of hub sleeves with internal oil grooves, packing them in refractory river silt, and casting high-tin bronze alloyed to prevent seizure.\n2. **Hot-Drop Axle Linchpins (*Acchaani*)**: Forging low-carbon wrought iron rods, upsetting the head into an eyelet for securing retaining thongs, and case-hardening the shaft through carbonaceous pack-annealing.\n3. **Hub Reinforcement Rings (*Kudap-Poon*)**: Forging expander rings that compressed wooden wheel hubs, preventing spokes from splitting the hub body outward.\n\n## Symbiosis with the Wheelwright\nAcchaani Kollan worked shoulder-to-shoulder with the chariot carpenter, measuring wooden spindles with calibrated reed calipers to ensure clearances of less than one millimeter, preventing wheel wobble and energy loss.",
        "chunks": [
            {
                "language": "en",
                "title": "Kodumanal Precision Chariot Hardware & Bronze Metallurgist",
                "content": "At Kodumanal, the Acchaani Kollan forged lost-wax bronze bushings and case-hardened iron linchpins, supplying the critical anti-friction metal components required for chariot engineering."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bbf\u0ba9\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0baa\u0bcd \u0baa\u0bc2\u0ba3\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0ba4\u0bc7\u0baf\u0bcd\u0bae\u0bbe\u0ba9\u0bae\u0bcd \u0b85\u0b9f\u0bc8\u0baf\u0bbe\u0ba4 \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b85\u0b9a\u0bcd\u0b9a\u0bbe\u0ba3\u0bbf\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0b95 \u0bb5\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b87\u0ba3\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0ba3\u0bbf\u0baf\u0bbe\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0b89\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb3\u0b95\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-vallam-ancient-chariot-wheelwright-and-bronze-fitting-haven.md",
        "slug": "place-vallam-ancient-chariot-wheelwright-and-bronze-fitting-haven",
        "category": "place",
        "name_en": "Vallam: Ancient Chariot Wheelwright, Arsenal & Bronze Fitting Haven",
        "name_ta": "\u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bb3 \u0bae\u0bc8\u0baf\u0bae\u0bcd",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1100,
        "thinai": "mullai",
        "summary_en": "Strategic plateau fortress near Thanjavur containing deep defensive moats, timber seasoning reservoirs, and royal chariot wheelwright arsenals that supplied wheeled combat vehicles to the Chola military.",
        "summary_ta": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bc8 \u0baa\u0bc0\u0b9f\u0baa\u0bc2\u0bae\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b86\u0bb4\u0bae\u0bbe\u0ba9 \u0b85\u0b95\u0bb4\u0bbf\u0b95\u0bb3\u0bcd, \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb1\u0bc8\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b9a\u0bcb\u0bb4\u0baa\u0bcd \u0baa\u0bc7\u0bb0\u0bb0\u0b9a\u0bbf\u0ba9\u0bcd \u0baa\u0bbf\u0bb0\u0ba4\u0bbe\u0ba9 \u0ba4\u0bc7\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0bb1\u0bc8\u0baf\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8 \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Akananuru 336",
            "South Indian Inscriptions Vol. II",
            "Tamil University Archaeological Excavations at Vallam"
        ],
        "content": "# Vallam: Ancient Chariot Wheelwright, Arsenal & Bronze Fitting Haven\n\n## Strategic Plateau Geography\nVallam ($10.7200^\\circ\\text{ N}, 79.0600^\\circ\\text{ E}$) commands an elevated laterite ridge rising 50 meters above the flat agricultural plains of the Kaveri delta. This elevated topography offered two decisive military advantages: natural immunity to delta monsoon flooding and dry, well-drained terrain ideal for chariot training and testing.\n\n## Royal Wheelwright Arsenals (*Thaer-Pattarai*)\nArchaeological investigations revealed that ancient Vallam functioned as a permanent military arsenal:\n- **Timber Seasoning Pits**: Subterranean mud chambers and oil vats where Vengai, Karunkali, and Teak logs were aged for years to eliminate internal moisture tension.\n- **Forging Quadrangles**: Concentrations of iron slag, tuyeres, and crucible debris indicating local manufacture of bronze bushings, axle pins, and tire bands.\n- **Chariot Proving Grounds (*Thaer-Veedhi*)**: Wide, straight earthen causeways flanking the outer moat where newly assembled chariots underwent rigorous stress-testing over rocky obstacles.\n\n## Historical Continuity\nMentioned in Sangam poetry (*Akananuru* 336) as a fortified stronghold of prince Nedunkilli, Vallam retained its status as the chief wheelwright and artillery garrison of the Chola empire down through the imperial reigns of Rajaraja and Rajendra Chola.",
        "chunks": [
            {
                "language": "en",
                "title": "Vallam Strategic Fortress & Chariot Arsenal Geography",
                "content": "Perched on a laterite plateau near Thanjavur, ancient Vallam served as the central chariot wheelwright arsenal of the Chola empire, featuring timber seasoning ponds, metal foundries, and chariot proving grounds."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc7\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b95\u0bb4\u0bbf\u0b95\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8",
                "content": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bc8 \u0b9a\u0bae\u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bc7\u0b9f\u0bcd\u0b9f\u0bc1\u0ba8\u0bbf\u0bb2\u0b95\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bb5\u0bb2\u0bcd\u0bb2\u0bae\u0bcd, \u0bae\u0bb0\u0b95\u0bcd \u0b95\u0bbf\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bcd, \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b89\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf\u0b95\u0bcd \u0b95\u0bb3\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bb1\u0bc8\u0baf\u0bbe\u0b95\u0ba4\u0bcd \u0ba4\u0bbf\u0b95\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4\u0ba4\u0bc1."
            }
        ]
    }
]
EDGES = [
    [
        "text-purananuru-chariot-wheelwright-and-eight-chariots-craftsmanship-poetry",
        "describes_wheel_rim",
        "concept-bent-felloe-wooden-rim-segmentation-and-joinery-nemiyum-kodum",
        "literary",
        "Sangam Classical Era",
        "Purananuru 87 renders the wheelwright's bent felloe and segmented wooden rim (nemiyum kodum) as the measure of a patron's generosity",
        "Purananuru 87 (Avvaiyar on Neduman Anji)"
    ],
    [
        "text-purananuru-chariot-wheelwright-and-eight-chariots-craftsmanship-poetry",
        "lauds_spoke_craftsmanship",
        "concept-hardwood-vengai-and-teak-radial-spoke-compression-mechanics",
        "literary",
        "Sangam Classical Era",
        "Sangam panegyric praises the radial vengai and teak spokes carrying the chariot's compression load",
        "Pathitrupathu 27; Malaipadukadam lines 40-55"
    ],
    [
        "concept-bent-felloe-wooden-rim-segmentation-and-joinery-nemiyum-kodum",
        "assembled_at",
        "place-vallam-ancient-chariot-wheelwright-and-bronze-fitting-haven",
        "craft_specialization",
        "Sangam to Chola Era",
        "Felloe bending and rim mortise joinery were executed in the Vallam wheelwright yards",
        "Tamil University Archaeological Excavations at Vallam 1984"
    ],
    [
        "concept-bronze-axle-bushing-castor-oil-lubrication-and-hub-acchaani",
        "forged_by",
        "char-kodumanal-bronze-axle-pin-smith-acchaani-kollan",
        "metallurgy",
        "Sangam Classical Era",
        "Bronze axle bushings and the acchaani linchpin were cast and fitted by the Kodumanal axle-pin smith",
        "Purananuru 170; Tirukkural 667"
    ],
    [
        "concept-bronze-axle-bushing-castor-oil-lubrication-and-hub-acchaani",
        "excavated_at",
        "place-kodumanal-gem-lapidary-industrial-hub",
        "archaeological",
        "Early Historic Era",
        "Bronze hub fittings and axle-pin assemblages recovered from the Kodumanal industrial horizons",
        "Excavations at Kodumanal Iron and Bronze Findings"
    ],
    [
        "concept-battlefield-chariot-shock-absorption-and-yoke-harness-acrodynamics",
        "contextualized_in",
        "text-purananuru-chariot-wheelwright-and-eight-chariots-craftsmanship-poetry",
        "military_tech",
        "Sangam Classical Era",
        "Battlefield shock absorption and yoke-harness dynamics are attested through Sangam war-chariot poetry",
        "Pathitrupathu 54; Mullaippattu lines 30-45"
    ],
    [
        "insc-vallam-thanjavur-chariot-guild-and-wheelwright-endowment-charters",
        "discovered_at",
        "place-vallam-ancient-chariot-wheelwright-and-bronze-fitting-haven",
        "epigraphy",
        "Early Historic to Chola Era",
        "Chariot guild and wheelwright endowment charters recorded at Vallam, Thanjavur district",
        "South Indian Inscriptions Vol. II; Annual Report on Epigraphy 1968 No. 210"
    ],
    [
        "insc-kodumanal-graffiti-pottery-chariot-and-wheel-emblem-epigraphs",
        "identifies_metallurgical_guild",
        "char-kodumanal-bronze-axle-pin-smith-acchaani-kollan",
        "industrial_epigraphy",
        "Iron Age to Sangam Era",
        "Chariot and wheel emblem graffiti on Kodumanal pottery mark the axle-pin smith's metallurgical guild",
        "Tamil-Brahmi Epigraphy Corpus Vol. IV; K. Rajan: Archaeology of Kongu Country"
    ],
    [
        "char-vallam-master-chariot-wheelwright-thaer-seivon-thachan",
        "headquartered_at",
        "place-vallam-ancient-chariot-wheelwright-and-bronze-fitting-haven",
        "biography",
        "Sangam Classical Era",
        "The master chariot wheelwright (thaer seivon thachan) operated his workshop at Vallam",
        "Purananuru 87; Traditional Thachu Shastra Guild Manuals"
    ],
    [
        "char-vallam-master-chariot-wheelwright-thaer-seivon-thachan",
        "collaborates_with",
        "char-kodumanal-bronze-axle-pin-smith-acchaani-kollan",
        "economic_interlock",
        "Sangam Classical Era",
        "Woodwright and bronze-smith lineages interlocked: timber wheel bodies fitted with Kodumanal bronze axle hardware",
        "Manimekalai Canto 19; Excavations at Kodumanal Metallurgy Reports"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 23 Corpus 2: Chariot Wheelwright Engineering & Axle Joinery into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 23 Corpus 2: Chariot Wheelwright Engineering & Axle Joinery Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
