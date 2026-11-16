#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Composite Bow Ballistics, Horn-Wood-Sinew Lamination & Sangam Archery Warfare
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
        "file": "knowledge/texts/text-purananuru-150-verses-on-valvil-ori-and-lethal-composite-archery.md",
        "slug": "text-purananuru-150-verses-on-valvil-ori-and-lethal-composite-archery",
        "category": "text",
        "name_en": "Purananuru 150: Classical Sangam Verses on Valvil Ori & Penetrative Composite Archery",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 150 - \u0bb5\u0bb2\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b93\u0bb0\u0bbf, \u0bae\u0bbe\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bb2\u0bcd, \u0b85\u0bae\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0b9f\u0bcd\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Classical Sangam verses by Vanparanar immortalizing King Valvil Ori's legendary feat of shooting a single high-velocity arrow through an elephant, tiger, deer, and boar.",
        "summary_ta": "\u0b92\u0bb0\u0bc7 \u0b85\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bcd \u0baf\u0bbe\u0ba9\u0bc8, \u0baa\u0bc1\u0bb2\u0bbf, \u0bae\u0bbe\u0ba9\u0bcd, \u0baa\u0ba9\u0bcd\u0bb1\u0bbf \u0b86\u0b95\u0bbf\u0baf\u0bb5\u0bb1\u0bcd\u0bb1\u0bc8\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1\u0b9a\u0bcd \u0b9a\u0bc6\u0ba9\u0bcd\u0bb1 \u0bb5\u0bb2\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b93\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0bbf\u0baf\u0b95\u0bcd\u0b95\u0ba4\u0bcd\u0ba4\u0b95\u0bcd\u0b95 \u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0ba9\u0bcd\u0baa\u0bb0\u0ba3\u0bb0\u0bcd \u0baa\u0bbe\u0b9f\u0bbf\u0baf \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 150",
            "Purananuru 152",
            "Akananuru 209"
        ],
        "content": "# Purananuru 150: Verses on Valvil Ori & Penetrative Archery\n\nIn *Purananuru* 150, the Sangam bard Vanparanar recounts the most celebrated feat of marksmanship in ancient Tamil martial lore, performed by King Valvil Ori of the mountainous Kollimalai ranges.\n\nThe poet witnesses Ori releasing a single heavy arrow (*kodu-veng-kana*) from his massive reflex composite bow (*val-vil*). The projectile carried such extraordinary kinetic momentum that it pierced cleanly through a charging bull elephant, slew an adjacent tiger, felled an axis deer, penetrated a wild boar, and embedded itself deep into the back of an iguana in its burrow.\n\nWhile heroic hyperbole elevates the verse, the poem records critical technical realities of ancient Tamil archery: the immense draw weights of laminated mountain reflex bows, the balance of heavy bamboo arrow shafts, and the penetrative lethality of wootz-steel broadhead points."
    },
    {
        "file": "knowledge/concepts/concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics.md",
        "slug": "concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics",
        "category": "concept",
        "name_en": "Composite Bow Dynamics: Horn, Hardwood Core & Animal Sinew Lamination Physics",
        "name_ta": "\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bbf\u0bb2\u0bcd \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd - \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1, \u0b95\u0b9f\u0bbf\u0ba9 \u0bae\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b9a\u0bc8\u0ba8\u0bbe\u0bb0\u0bcd \u0b92\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Biomechanical engineering of laminated composite bows combining compressible wild water buffalo horn on the belly, seasoned bamboo or hardwood in the core, and elastic animal back sinew.",
        "summary_ta": "\u0bb5\u0bbf\u0bb1\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0ba9 \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0b8e\u0bb0\u0bc1\u0bae\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1, \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0ba8\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0b95\u0bc1\u0ba4\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0bb5\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bc1 \u0ba4\u0b9a\u0bc8\u0ba8\u0bbe\u0bb0\u0bcd\u0b95\u0bb3\u0bc8 \u0bae\u0bc0\u0ba9\u0bcd \u0baa\u0b9a\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b92\u0b9f\u0bcd\u0b9f\u0bbf\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bbf\u0bb2\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Dhanurveda Traditional Archery Treatises",
            "Journal of Archery Research",
            "Archaeological Weapons of Tamilakam"
        ],
        "content": "# Composite Bow Dynamics: Lamination Physics\n\nThe traditional South Indian reflex composite bow (*kodu-vil*) achieved stored energy and cast velocity far surpassing simple wooden self-bows:\n\n- **Belly Compression (Horn)**: The inner face facing the archer was laminated with strips of wild water buffalo (*kadum-ma*) horn. Horn possesses an extraordinary compressive yield strength (over 130 MPa), absorbing severe compression without taking a permanent bend.\n- **Core Structural Spline**: Seasoned split bamboo (*kal-moongil*) or red sanders wood formed the neutral axis, providing lightweight structural shear stability.\n- **Backing Tensile Layer (Sinew)**: The outer face was lined with pounded dried leg tendons and neck sinew (*narambu*) of deer or cattle. Animal sinew boasts a tensile breaking strength exceeding 200 MPa and can stretch up to 10% elastically, snapping back with ferocious whip-action.\n- **Fish-Bladder Gelatin Glue (*Meen-Pisaatha*)**: The laminates were bound under high pressure with boiled sturgeon or carp swim-bladder collagen glue, forming a unified flexural composite unaffected by tropical vibrations."
    },
    {
        "file": "knowledge/technologies/technology-wootz-steel-arrowhead-metallurgy-and-ballistic-penetration.md",
        "slug": "technology-wootz-steel-arrowhead-metallurgy-and-ballistic-penetration",
        "category": "technology",
        "name_en": "Wootz Arrowheads: High-Carbon Steel Metallurgy, Socketing & Ballistic Penetration",
        "name_ta": "\u0b89\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0b83\u0b95\u0bc1 \u0b85\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0ba9\u0bc8\u0b95\u0bb3\u0bcd - \u0b95\u0bc2\u0bb0\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0bb5\u0b9f\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd, \u0b86\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb5\u0b9a\u0bae\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Forging of high-carbon wootz crucible steel into specialized ballistic arrowheads: needle-pointed bodkins for piercing iron armor and razor-edged broadheads for infantry trauma.",
        "summary_ta": "\u0b95\u0bb5\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b8a\u0b9f\u0bc1\u0bb0\u0bc1\u0bb5\u0bbf\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b8a\u0b9a\u0bbf\u0bae\u0bc1\u0ba9\u0bc8 \u0b85\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0baa\u0bcd \u0baa\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb2\u0bc8\u0b95\u0bc1\u0bb2\u0bc8\u0baf\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bb3\u0bc8\u0ba8\u0bcd\u0ba4 \u0b89\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0b83\u0b95\u0bc1 \u0b85\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b89\u0bb2\u0bcb\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Kodumanal Excavations Metallurgy Reports",
            "Purananuru 77",
            "Indian Iron and Steel Archaeological Metallurgy"
        ],
        "content": "# Wootz Arrowheads: Ballistic Metallurgy & Penetration\n\nExcavations across Tamil Iron Age and Sangam sites (Kodumanal, Porunthal, and Alagankulam) have yielded thousands of precision-forged steel arrowheads (*ambu-koor*):\n\n- **Wootz Crucible Steel**: Arrowheads were hand-forged from high-carbon crucible steel (1.2% to 1.6% C). Quenched in herbal oils and tempered to Rockwell C 58, the tips maintained razor sharpness upon impacting bronze cuirasses and hardened leather war shields (*thol-kedagam*).\n- **Specialized Tip Typology**:\n  1. *Koor-Ambu* (Bodkin Point): Narrow, four-sided square pyramidal tips engineered with a small cross-sectional area to concentrate kinetic energy ($KE = \frac{1}{2}mv^2$) and breach plate armor.\n  2. *Nari-Mugam* (Broadhead / Fox-Muzzle): Broad triangular barbed blades designed to slice deep vascular arteries and prevent removal without severe tissue laceration.\n  3. *Thee-Ambu* (Incendiary Arrow): Hollow-pierced iron sockets wrapped with pitch and sulfur-soaked cotton to torch siege towers and thatched roofs."
    },
    {
        "file": "knowledge/artifacts/artifact-kodu-veng-kana-hardened-reed-arrow-shafts-and-hawk-feather-fletching.md",
        "slug": "artifact-kodu-veng-kana-hardened-reed-arrow-shafts-and-hawk-feather-fletching",
        "category": "artifact",
        "name_en": "Kodu-Veng-Kana: Fire-Hardened Reed Shafts & Falcon-Feather Ballistic Fletching",
        "name_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bb5\u0bc6\u0b99\u0bcd\u0b95\u0ba3\u0bc8 - \u0ba4\u0bc0\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0baf \u0ba8\u0bbe\u0ba3\u0bb2\u0bcd \u0b85\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0ba3\u0bcd\u0b9f\u0bc1, \u0baa\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0bb4\u0bc1\u0b95\u0bc1 \u0b87\u0bb1\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bcd \u0b95\u0bb2\u0bc8",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "High-velocity ballistic projectiles fabricated from seasoned wild river reeds or arrow-bamboo, straightened over hot embers and stabilized with spiral-trimmed eagle and vulture primary feathers.",
        "summary_ta": "\u0ba8\u0bc7\u0bb0\u0bbe\u0b95\u0baa\u0bcd \u0baa\u0bb1\u0ba8\u0bcd\u0ba4\u0bc1 \u0b9a\u0bc6\u0ba9\u0bcd\u0bb1\u0bc1 \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95 \u0b95\u0bb4\u0bc1\u0b95\u0bc1, \u0baa\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0b87\u0bb1\u0b95\u0bc1\u0b95\u0bb3\u0bcd \u0baa\u0bbf\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f, \u0ba4\u0bc0\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbe\u0ba3\u0bb2\u0bcd \u0b85\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Purananuru 95",
            "Akananuru 272",
            "Ethno-Ballistics of Indigenous Archery"
        ],
        "content": "# Kodu-Veng-Kana: Reed Shafts & Falcon Fletching\n\nAn arrow's flight accuracy is entirely governed by dynamic spine (stiffness) and aerodynamic drag stabilization:\n\n- **Arrow-Reed (*Ambu-Naanal*)**: Shafts were harvested from dense wild mountain reeds (*Saccharum arundinaceum*) or solid male bamboo (*kal-moongil*). Cut into uniform lengths of 28 to 32 inches, the raw culms were straightened by rolling them while warm through grooved hardwood heating jigs (*kanal-palagai*).\n- **Aerodynamic Fletching (*Parunthu-Iraagu*)**: Scribes noted that feathers from birds of prey\u2014specifically white-bellied sea eagles, falcons, and vultures\u2014were selected for their rigid barbs and water-repellent preen oil. Three feathers were split, trimmed into low-drag parabolic profiles, and lashed to the nock with fine silk thread sealed in shellac.\n- **Helical Spin**: Feathers were affixed at a slight 2-degree spiral offset, imparting a rifle-like gyroscopic spin of 3,000 RPM in flight, suppressing yaw and ensuring laser-straight trajectory over 150 meters."
    },
    {
        "file": "knowledge/concepts/concept-archer-thumb-ring-release-and-mongolian-draw-kinematics.md",
        "slug": "concept-archer-thumb-ring-release-and-mongolian-draw-kinematics",
        "category": "concept",
        "name_en": "Thumb-Ring Release: Horn & Agate Archer Rings & Biomechanical Draw Kinematics",
        "name_ta": "\u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bbe\u0bb3\u0bbf \u0bb5\u0bbf\u0bb0\u0bb2\u0bcd \u0bae\u0bcb\u0ba4\u0bbf\u0bb0\u0bae\u0bcd - \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1, \u0b85\u0b95\u0bc7\u0b9f\u0bcd \u0bae\u0bcb\u0ba4\u0bbf\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bb5\u0bbf\u0bb0\u0bb2\u0bcd \u0ba8\u0bbe\u0ba3\u0bcd \u0b87\u0bb4\u0bc1 \u0bb5\u0bbf\u0b9a\u0bc8 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1500,
        "thinai": "mullai",
        "summary_en": "Biomechanical draw technique utilizing grooved bovine horn, bone, or agate thumb rings (viralkaap) enabling archers to hold and cleanly release heavy 80-pound bowstrings without nerve damage.",
        "summary_ta": "\u0b95\u0b9f\u0bc1\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bb5\u0bbf\u0bb0\u0bb2\u0bbe\u0bb2\u0bcd \u0b87\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd\u0baa\u0bcb\u0ba4\u0bc1 \u0ba8\u0bb0\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0baa\u0bbe\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b8e\u0bb0\u0bc1\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bbe\u0ba3\u0bbf\u0b95\u0bcd\u0b95 \u0bb5\u0bbf\u0bb0\u0bb2\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bcb\u0ba4\u0bbf\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Purananuru 89",
            "Tamil Epigraphical Records of Martial Guilds",
            "Biomechanics of Asian Archery Releases"
        ],
        "content": "# Thumb-Ring Release & Draw Kinematics\n\nHeavy war bows with draw weights exceeding 70 to 90 pounds cannot be drawn with western three-finger Mediterranean draws without pinching the arrow and damaging finger nerves:\n\n- **The Asian Thumb Lock**: Ancient Tamil warriors (*maravar* and *mazhavar*) utilized the thumb lock: the bowstring was locked behind the inner joint of the right thumb, with the index finger curled securely over the thumb nail to reinforce the grip.\n- **Viralkaap (Archery Thumb Ring)**: To protect the thumb tendon and create an instantaneous, frictionless release, archers wore cylindrical or lip-lipped thumb rings (*viralkaap*) carved from polished water buffalo horn, sambar deer antler, or banded agate.\n- **Archer's Paradox Elimination**: Because the arrow rested on the right side of the bow stave during a thumb draw, the natural deflection of the releasing string aligned the arrow directly down the sightline, minimizing the horizontal paradox oscillation."
    },
    {
        "file": "knowledge/institutions/institution-mazhavar-and-villaligal-corporation-of-royal-archers-and-marksmen.md",
        "slug": "institution-mazhavar-and-villaligal-corporation-of-royal-archers-and-marksmen",
        "category": "institution",
        "name_en": "Villaligal & Mazhavar Guild: Corporation of Royal Bowmen, Scouts & Archery Regiments",
        "name_ta": "\u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bbe\u0bb3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb4\u0bb5\u0bb0\u0bcd \u0baa\u0b9f\u0bc8 - \u0b85\u0bb0\u0b9a \u0bb5\u0bbf\u0bb2\u0bcd\u0bb5\u0bc0\u0bb0\u0bb0\u0bcd \u0b95\u0bb4\u0b95\u0bae\u0bcd, \u0ba4\u0ba9\u0bc1\u0bb0\u0bcd\u0bb5\u0bc7\u0ba4\u0baa\u0bcd \u0baa\u0baf\u0bbf\u0bb1\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb2\u0bcd \u0baa\u0b9f\u0bc8\u0baa\u0bcd\u0baa\u0bbf\u0bb0\u0bbf\u0bb5\u0bc1",
        "era": "Classical Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "palai",
        "summary_en": "Professional military corporations of elite bowmen organized into standardized regiments (Villigal), maintained through royal land endowments, specialized archery ranges, and martial academies.",
        "summary_ta": "\u0b9a\u0bcb\u0bb4, \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc7\u0bb0 \u0bb5\u0bc7\u0ba8\u0bcd\u0ba4\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0b99\u0bcd\u0b95\u0bc1 \u0bb5\u0b95\u0bbf\u0ba4\u0bcd\u0ba4, \u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0b9f\u0bbf \u0b95\u0bbe\u0ba3\u0bbf \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bbf\u0bb2\u0bcd\u0bb5\u0bc0\u0bb0\u0bb0\u0bcd \u0baa\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Thanjavur Brihadisvara Inscriptions (Perundanam Villigal)",
            "Purananuru 88-104",
            "Chola Military Organization Studies"
        ],
        "content": "# Villaligal & Mazhavar: Corporation of Royal Bowmen\n\nArchers constituted the primary ranged shock force of Sangam and imperial Tamil armies, recognized in epigraphs as distinct elite martial bodies:\n\n- **Sangam Mazhavar**: Ferocious tribal and pastoral highland bowmen renowned for their peerless woodland skirmishing, lightning ambushes, and unwavering loyalty to chieftains like Adigaman of Thagadur.\n- **Chola Imperial Regiments**: Great temple inscriptions at Thanjavur document professional permanent archery brigades including the *Perundanam Villigal* (Senior Royal Bowmen) and *Sirudanam Villigal* (Junior Bowmen), housed in fortified barracks (*padai-veedu*).\n- **Archery Training Academies (*Vil-Kottai*)**: Young cadets trained in *Dhanur-Vithai* (the science of the bow), drilling in five classical shooting positions, rapid-fire volley shooting from moving chariots, and night target acquisition guided solely by sound."
    },
    {
        "file": "knowledge/technologies/technology-bowstring-twisting-wild-hemp-deer-sinew-and-silk-binding.md",
        "slug": "technology-bowstring-twisting-wild-hemp-deer-sinew-and-silk-binding",
        "category": "technology",
        "name_en": "Bowstring Twisting: Wild Sann-Hemp, Rawhide & Raw Silk Multi-Ply Cordage",
        "name_ta": "\u0ba8\u0bbe\u0ba3\u0bcd \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd - \u0b9a\u0ba3\u0bb2\u0bcd, \u0bae\u0bbe\u0ba9\u0bcd \u0ba8\u0bb0\u0bae\u0bcd\u0baa\u0bc1, \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc2\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0ba9\u0bcd\u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0ba4\u0b9f\u0bb5\u0bbf\u0baf \u0bb5\u0bbf\u0bb2\u0bcd\u0ba8\u0bbe\u0ba3\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "High-tensile bowstring engineering spinning long-line Sann-hemp fibers, braided animal sinew, and raw mulberry silk saturated in beeswax to withstand violent dynamic launch shock.",
        "summary_ta": "\u0b85\u0bae\u0bcd\u0baa\u0bc8 \u0b85\u0ba4\u0bbf\u0bb5\u0bc7\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bc6\u0bb2\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0baa\u0bcb\u0ba4\u0bc1 \u0b85\u0bb1\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bcb\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95, \u0b9a\u0ba3\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc2\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0ba4\u0b9f\u0bb5\u0bbf \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb2\u0bcd\u0ba8\u0bbe\u0ba3\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Dhanurveda Bowstring Formulations",
            "Purananuru 100",
            "Traditional Rope and Twine Technology"
        ],
        "content": "# Bowstring Twisting & Dynamic String Shock\n\nThe bowstring (*vil-naan* or *kodi*) is the critical energetic link transforming potential energy stored in drawn bow limbs into kinetic projectile velocity:\n\n- **Material Selection**: Cheap vegetable fibers snap under the violent shock of dry releases. Master bowyers spun bowstrings from long-line water-retted Sann-hemp (*Crotalaria juncea*), mountain agave (*marul-naar*), or continuous raw silk yarns (*pattu-nool*).\n- **Beeswax & Pine Resin Impregnation**: As individual strands were twisted under high tension, they were burnished vigorously with a heated cake of pure beeswax and pine dammar resin. This consolidated the strands into a moisture-proof solid cord, preventing rain water absorption from slackening string tension during humid monsoons.\n- **Center Serving (*Nock-Kattu*)**: The center section struck by the arrow nock was tightly served with fine silk whipping thread to prevent abrasive wear from the sharp iron-incised nock."
    },
    {
        "file": "knowledge/artifacts/artifact-ambura-koodu-embossed-leather-quivers-and-quick-draw-baldrics.md",
        "slug": "artifact-ambura-koodu-embossed-leather-quivers-and-quick-draw-baldrics",
        "category": "artifact",
        "name_en": "Ambura-Koodu: Embossed Water-Buffalo Hide Quivers & Cross-Chest Baldrics",
        "name_ta": "\u0b85\u0bae\u0bcd\u0baa\u0bc1\u0bb0\u0bbe\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0bc1 - \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0bcb\u0bb2\u0bcd \u0b85\u0bae\u0bcd\u0baa\u0bb1\u0bbe\u0ba4\u0bcd\u0ba4\u0bc2\u0ba3\u0bbf, \u0ba4\u0bcb\u0bb3\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb0\u0bc8\u0bb5\u0bc1 \u0b85\u0bae\u0bcd\u0baa\u0bc1 \u0b8e\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1500,
        "thinai": "mullai",
        "summary_en": "Cylindrical back and hip quivers crafted from stiff vegetable-tanned buffalo leather, fitted with rain hoods, internal felt noise dampers, and multi-point balance straps.",
        "summary_ta": "\u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0ba8\u0ba9\u0bc8\u0baf\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd, \u0b9a\u0ba4\u0bcd\u0ba4\u0bae\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0bb5\u0bbf\u0bb0\u0bc8\u0bb5\u0bbe\u0b95 \u0b85\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbf \u0b8e\u0baf\u0bcd\u0baf\u0bb5\u0bc1\u0bae\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b8e\u0bb0\u0bc1\u0bae\u0bc8\u0ba4\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0b85\u0bae\u0bcd\u0baa\u0bb1\u0bbe\u0ba4\u0bcd\u0ba4\u0bc2\u0ba3\u0bbf.",
        "sources": [
            "Purananuru 98",
            "Thanjavur Palace Armory Relics",
            "Ancient Tamil Military Regalia Surveys"
        ],
        "content": "# Ambura-Koodu: Leather Quivers & Tactical Baldrics\n\nAn archer in sustained battle required instant, unhindered access to three dozen arrows without looking away from oncoming cavalry charges:\n\n- **Tanned Leather Construction**: Fabricated from vegetable-tanned thick water-buffalo hide (*erumaith-thol*), boiled in wax (*cuir bouilli*) to form a rigid, crush-proof cylinder that shielded fragile arrow shafts from enemy sword blows.\n- **Internal Acoustic Damping**: The base of the quiver was packed with dense sheep's wool felt (*kambali*) soaked in oil, preventing iron arrowheads from clattering loudly against each other during stealthy nighttime woodland maneuvers.\n- **Adjustable Baldric (*Kachai*)**: Wide cross-chest shoulder baldrics with forged bronze buckles maintained the quiver at a calibrated 45-degree angle over the right shoulder, enabling split-second blind arrow extraction (*nodiyil-eeythal*)."
    },
    {
        "file": "knowledge/concepts/concept-ballistic-trajectory-arrow-weight-and-kinetic-impact-physics.md",
        "slug": "concept-ballistic-trajectory-arrow-weight-and-kinetic-impact-physics",
        "category": "concept",
        "name_en": "Ballistic Trajectory: Arrow Grain Weight, Flight Drag & Kinetic Impact Physics",
        "name_ta": "\u0b8e\u0bb1\u0bbf\u0baa\u0bca\u0bb0\u0bc1\u0bb3\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd - \u0b85\u0bae\u0bcd\u0baa\u0bc1 \u0b8e\u0b9f\u0bc8, \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0b89\u0bb0\u0bbe\u0baf\u0bcd\u0bb5\u0bc1, \u0bb5\u0bbf\u0b9a\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb5\u0b9a\u0bae\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0ba8\u0bcd\u0ba4 \u0b86\u0bb1\u0bcd\u0bb1\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Physical calculations balancing arrow mass against initial launch velocity ($F=ma$, $p=mv$) to optimize penetrating momentum against armored war elephants and heavy infantry.",
        "summary_ta": "\u0b85\u0bae\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0b8e\u0b9f\u0bc8, \u0b95\u0bbe\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0baa\u0bb1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0b9a\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0ba4\u0bbf\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0b95\u0bb5\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0b95\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0ba8\u0bcd\u0ba4 \u0b86\u0bb1\u0bcd\u0bb1\u0bb2\u0bbf\u0ba9\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd \u0b9a\u0bae\u0ba9\u0bcd\u0baa\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0bbe\u0b9f\u0bc1.",
        "sources": [
            "Akananuru 318",
            "Fundamentals of External Ballistics",
            "Military Engineering in Ancient Tamil Literature"
        ],
        "content": "# Ballistic Trajectory & Kinetic Impact Physics\n\nSangam military theorists recognized that defeating armored war elephants (*pattathu-yaanai*) demanded optimizing projectile momentum ($p = mv$) rather than simply maximizing muzzle velocity:\n\n- **Heavy vs Light Arrows**: Light reed arrows (300 grains / 20 grams) launched at high velocity (65 m/s) shed velocity rapidly due to aerodynamic atmospheric drag, proving ineffective against heavy hide armor at long ranges.\n- **Heavy War Darts (*Perum-Kana*)**: For siege warfare and elephant defense, bowyers crafted massive 800-grain (52 gram) arrows tipped with dense steel bodkins. While initial launch speed was lower (45 m/s), their immense momentum carried through armor plate and bone tissue without deflecting.\n- **Parabolic Arc Calculation**: Experienced archers adjusted their elevation angles (*koni-nokku*) instinctively, dropping heavy volleys into enemy formations from 200 meters using high-angle plunging fire."
    },
    {
        "file": "knowledge/places/place-thagadur-ancient-adigaman-archery-and-fortress-haven.md",
        "slug": "place-thagadur-ancient-adigaman-archery-and-fortress-haven",
        "category": "place",
        "name_en": "Thagadur: Ancient Adigaman Citadel & Mazhavar Archery Arsenal Haven",
        "name_ta": "\u0ba4\u0b95\u0b9f\u0bc2\u0bb0\u0bcd - \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0ba8\u0bc6\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0bcd \u0b85\u0b9e\u0bcd\u0b9a\u0bbf \u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8, \u0bae\u0bb4\u0bb5\u0bb0\u0bcd \u0bb5\u0bbf\u0bb2\u0bcd \u0baa\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bbf\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1300,
        "thinai": "mullai",
        "summary_en": "Historic fortress citadel of King Adigaman Neduman Anji in Dharmapuri district, celebrated in Sangam literature as the capital of elite Mazhavar composite archers and monumental arsenals.",
        "summary_ta": "\u0b85\u0bb5\u0bcd\u0bb5\u0bc8\u0baf\u0bbe\u0bb0\u0bbe\u0bb2\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b85\u0ba4\u0bbf\u0baf\u0bae\u0bbe\u0ba9\u0bcd \u0ba8\u0bc6\u0b9f\u0bc1\u0bae\u0bbe\u0ba9\u0bcd \u0b85\u0b9e\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0ba4\u0bb2\u0bc8\u0b9a\u0bbf\u0bb1\u0ba8\u0bcd\u0ba4 \u0bb5\u0bbf\u0bb2\u0bcd\u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bcd, \u0b86\u0baf\u0bc1\u0ba4\u0b95\u0bcd \u0b95\u0bbf\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Purananuru 88-104 (Avvaiyar Verses)",
            "Thagadur Yattirai Epic",
            "Dharmapuri Archaeological Excavations"
        ],
        "content": "# Thagadur: Ancient Adigaman Archery Haven\n\nPerched strategically along the frontier between the Kongu highlands and the Tondaimandalam plains in modern Dharmapuri district, ancient Thagadur served as the impregnable fortress citadel of the famous Sangam patron-king Adigaman Neduman Anji.\n\n- **The Mazhavar Bowmen Garrison**: Immortalized across dozens of poems by the venerated poetess Avvaiyar, Thagadur was defended by the legendary Mazhavar bowmen whose composite archery dominated peninsular warfare.\n- **The Royal Arsenal (*Kalam-Poli-Kottam*)**: In *Purananuru* 95, Avvaiyar famously contrasts the glittering, pristine weapons in the rival king's court with the chipped, blood-stained, repair-worn arrows and bows filling Adigaman's working blacksmith forges and armories in Thagadur.\n- **The Siege of Thagadur (*Thagadur Yattirai*)**: The protracted military campaign waged against Thagadur by the Chera monarch Perumcheral Irumporai is commemorated in the classical military epic *Thagadur Yattirai*, providing the most exhaustive tactical account of archery barrages, siege escalades, and composite bow warfare in classical Tamil history."
    }
]

EDGES = [
    [
        "text-purananuru-150-verses-on-valvil-ori-and-lethal-composite-archery",
        "DESCRIBES",
        "concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics",
        "core",
        "Sangam Era",
        "Purananuru 150 verses celebrate the tremendous penetrative velocity of laminated composite bows.",
        "Purananuru 150"
    ],
    [
        "concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics",
        "PROPELS",
        "technology-wootz-steel-arrowhead-metallurgy-and-ballistic-penetration",
        "core",
        "Iron Age to Modern Era",
        "Laminated reflex bows drove wootz-steel bodkins through heavy armor shields.",
        "Dhanurveda Traditional Archery Treatises"
    ],
    [
        "technology-wootz-steel-arrowhead-metallurgy-and-ballistic-penetration",
        "MOUNTED_ON",
        "artifact-kodu-veng-kana-hardened-reed-arrow-shafts-and-hawk-feather-fletching",
        "core",
        "Iron Age to Modern Era",
        "Forged wootz points were socketed onto fire-hardened reed shafts with falcon fletching.",
        "Kodumanal Excavations Metallurgy Reports"
    ],
    [
        "concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics",
        "DRAWN_WITH",
        "concept-archer-thumb-ring-release-and-mongolian-draw-kinematics",
        "core",
        "Iron Age to Medieval Era",
        "High-draw-weight composite bows utilized horn thumb rings for rapid, painless releases.",
        "Purananuru 89"
    ],
    [
        "concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics",
        "FITTED_WITH",
        "technology-bowstring-twisting-wild-hemp-deer-sinew-and-silk-binding",
        "core",
        "Prehistoric to Modern Era",
        "Composite limbs were braced with multi-ply beeswax-coated hemp and sinew bowstrings.",
        "Dhanurveda Bowstring Formulations"
    ],
    [
        "artifact-kodu-veng-kana-hardened-reed-arrow-shafts-and-hawk-feather-fletching",
        "STORED_IN",
        "artifact-ambura-koodu-embossed-leather-quivers-and-quick-draw-baldrics",
        "core",
        "Iron Age to Medieval Era",
        "Tactical reed arrows were carried in embossed water-buffalo hide quivers with rain hoods.",
        "Purananuru 98"
    ],
    [
        "concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics",
        "GOVERNED_BY",
        "concept-ballistic-trajectory-arrow-weight-and-kinetic-impact-physics",
        "core",
        "Prehistoric to Modern Era",
        "Arrow grain weight and launch velocity determined kinetic impact momentum.",
        "Fundamentals of External Ballistics"
    ],
    [
        "concept-composite-bow-dynamics-horn-wood-and-animal-sinew-lamination-physics",
        "WIELDED_BY",
        "institution-mazhavar-and-villaligal-corporation-of-royal-archers-and-marksmen",
        "core",
        "Classical Sangam to Medieval Era",
        "Elite Mazhavar corporations and Chola Villaligal regiments manned imperial archery forces.",
        "Thanjavur Brihadisvara Inscriptions"
    ],
    [
        "institution-mazhavar-and-villaligal-corporation-of-royal-archers-and-marksmen",
        "GARRISONED_AT",
        "place-thagadur-ancient-adigaman-archery-and-fortress-haven",
        "core",
        "Iron Age to Medieval Era",
        "Thagadur fortress was the premier Sangam stronghold of elite Mazhavar archery regiments.",
        "Purananuru 88-104"
    ],
    [
        "artifact-kodu-veng-kana-hardened-reed-arrow-shafts-and-hawk-feather-fletching",
        "STORED_AT",
        "place-thagadur-ancient-adigaman-archery-and-fortress-haven",
        "core",
        "Iron Age to Medieval Era",
        "King Adigaman maintained vast working arrow arsenals in Thagadur during sieges.",
        "Thagadur Yattirai Epic"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 35: Ancient Tamil Composite Bow Ballistics, Horn-Wood-Sinew Lamination & Sangam Archery Warfare...")
    
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

    print(f"Ingestion Complete for Batch 35 Corpus 3 (Composite Bow Ballistics)! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
