#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Palm-Leaf Manuscript Scribing, Iron Stylus Metallurgy & Herbal Preservatives
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
        "file": "knowledge/texts/text-tholkappiyam-payiram-verses-on-engraved-palm-scrolls-and-academic-conclaves.md",
        "slug": "text-tholkappiyam-payiram-verses-on-engraved-palm-scrolls-and-academic-conclaves",
        "category": "text",
        "name_en": "Tholkappiyam Payiram: Classical Verses on Engraved Palm Scrolls & Scholarly Conclaves",
        "name_ta": "\u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd - \u0baa\u0ba9\u0bc8\u0baf\u0bc7\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bcd, \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b99\u0bcd\u0b95\u0bc7\u0bb1\u0bcd\u0bb1 \u0bae\u0bb0\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -500,
        "year_end": 100,
        "thinai": "marutham",
        "summary_en": "Foundational verses by Panamparanar documenting the codification, incised palm-leaf preservation, and rigorous academic defense of Tholkappiyam in the Pandyan royal court.",
        "summary_ta": "\u0ba8\u0bbf\u0bb2\u0ba8\u0bcd\u0ba4\u0bb0\u0bc1 \u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0bbf\u0bb1\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0ba9\u0bcd \u0b85\u0bb5\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0ba4\u0b99\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bbe\u0b9a\u0bbe\u0ba9\u0bcd \u0bae\u0bc1\u0ba9\u0bcd\u0ba9\u0bbf\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bae\u0bcd \u0b85\u0bb0\u0b99\u0bcd\u0b95\u0bc7\u0bb1\u0bcd\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0baa\u0ba9\u0bc8\u0baf\u0bc7\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0baf\u0bbf\u0bb0\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Tholkappiyam Cirappuppayiram",
            "Iraiyanar Akapporul Urai",
            "Silappadikaram Uraippayiram"
        ],
        "content": "# Tholkappiyam Payiram: Engraved Palm Scrolls & Academic Conclaves\n\nThe preface (*Payiram*) to the oldest extant Tamil grammatical treatise, *Tholkappiyam*, authored by Panamparanar, provides primary textual verification for the antiquity of written palm-leaf codicology in Tamilakam.\n\nThe poem recounts how Tholkappiyanar inscribed his monumental linguistic treatise onto cured palmyra leaf scrolls (*olaichuvadi*). In the royal court of the Pandyan king Nilantharu Thiruvin Pandyan, the text was presented and defended chapter by chapter before the eminent polymath Athankottu Asan.\n\nThis record demonstrates that long before paper was known in India, ancient Tamil society had institutionalized palm-leaf manuscript production, employing incised metal styli (*ezhuthani*) to record grammar, literature, law, and agrarian revenue accounts."
    },
    {
        "file": "knowledge/concepts/concept-thalai-patham-borassus-flabellifer-palm-leaf-boiling-curing-and-rib-removal.md",
        "slug": "concept-thalai-patham-borassus-flabellifer-palm-leaf-boiling-curing-and-rib-removal",
        "category": "concept",
        "name_en": "Thalai-Padham: Palmyra Leaf Boiling, Herb Steaming & Midrib Sizing Technology",
        "name_ta": "\u0b93\u0bb2\u0bc8 \u0baa\u0ba4\u0bae\u0bcd - \u0baa\u0ba9\u0bc8 \u0b93\u0bb2\u0bc8 \u0ba4\u0bc7\u0bb0\u0bcd\u0bb5\u0bc1, \u0bb5\u0bc7\u0b95\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd, \u0b88\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Careful horticultural curing of young tender fronds of Borassus flabellifer through turmeric-lime steaming, dew rehydration, and surface burnishing to produce durable manuscript leaves.",
        "summary_ta": "\u0b87\u0bb3\u0b99\u0bcd\u0b95\u0bc1\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0ba9\u0bc8 \u0b93\u0bb2\u0bc8\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd-\u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0bb5\u0bc7\u0b95\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0baa\u0ba9\u0bbf\u0bb5\u0bc6\u0baf\u0bbf\u0bb2\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0b8e\u0bb4\u0bc1\u0ba4\u0ba4\u0bcd \u0ba4\u0b95\u0bc1\u0ba8\u0bcd\u0ba4 \u0b8f\u0b9f\u0bc1\u0b95\u0bb3\u0bbe\u0b95 \u0bae\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Traditional Palm-Leaf Manuscript Conservation Manuals",
            "Saraswathi Mahal Library Monographs",
            "Ainkurunuru 310"
        ],
        "content": "# Thalai-Padham: Palmyra Leaf Curing Technology\n\nUntreated fresh palmyra leaves (*panai-olai*) dry brittle and crack within weeks. Transforming the foliage of *Borassus flabellifer* into flexible, centuries-lasting manuscript leaves (*edu*) involved a precise multi-stage procedure:\n\n1. **Frond Selection (*Kuruthu-Thedal*)**: Only tender young apical fronds (*manja-kuruthu*) harvested at dawn were selected, prized for their supple, dense cell structure and absence of surface blemishes.\n2. **Midrib Removal (*Eerkku-Neekkal*)**: The stiff central structural rib was slit away using a sharp curved brass knife, yielding two uniform flat folios.\n3. **Steam Curing (*Avi-Padham*)**: Leaves were steeped in copper vats filled with water infused with raw turmeric (*manjal*\u2014a natural antifungal agent) and slaked lime (*sunnambu*). Steaming broke down acidic plant saps and gelatinized cellular starch.\n4. **Shade Dew-Conditioning**: Folios were dried under indirect shade by day and exposed to night dew (*pani*), followed by polishing with smooth cowrie shells (*sozhi*) to create frictionless scribing surfaces."
    },
    {
        "file": "knowledge/technologies/technology-ezhuthani-varkkam-hardened-steel-stylus-geometry-and-incision-mechanics.md",
        "slug": "technology-ezhuthani-varkkam-hardened-steel-stylus-geometry-and-incision-mechanics",
        "category": "technology",
        "name_en": "Ezhuthani-Varkkam: Hardened Steel Stylus Metallurgy, Bevel Geometry & Incision Mechanics",
        "name_ta": "\u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf \u0bb5\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bae\u0bcd - \u0b89\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0b83\u0b95\u0bc1 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf, \u0bae\u0bc1\u0ba9\u0bc8 \u0bb5\u0b9f\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0ba9\u0bc8\u0baf\u0bc7\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bc0\u0bb1\u0bb2\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "High-carbon wootz-steel engraving instruments with razor-sharp micro-beveled needle tips engineered to incise leaf epidermis without puncturing underlying vascular bundles.",
        "summary_ta": "\u0baa\u0ba9\u0bc8 \u0b93\u0bb2\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0ba8\u0bb0\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bbf\u0bb4\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd, \u0b85\u0ba4\u0ba9\u0bcd \u0bae\u0bc7\u0bb2\u0bcd \u0ba4\u0bcb\u0bb2\u0bbf\u0bb2\u0bcd \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0ba9 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bc0\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0b95\u0bcd\u0b95\u0bc1 \u0b8e\u0b83\u0b95\u0bbe\u0bb2\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bc2\u0bb0\u0bcd\u0bae\u0bc1\u0ba9\u0bc8 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Epigraphia Indica Vol. XVII",
            "Archaeological Metallurgy of Tamil Styli",
            "Periyapuranam Kannappa Nayanar Puranam"
        ],
        "content": "# Ezhuthani-Varkkam: Steel Stylus Incision Mechanics\n\nWriting upon palm leaves did not involve surface ink painting, but rather microscopic surgical engraving into the leaf epidermis:\n\n- **Wootz Crucible Tip**: The scribing point (*ezhuthani-koor*) was forged from hyper-eutectoid wootz crucible steel, heat-treated to Rockwell C 62 hardness to maintain a needle point through hundreds of folio inscriptions.\n- **Micro-Bevel Geometry**: The tip was ground with an obtuse diamond or hemispherical bevel. A sharp dagger point would snag and tear parallel vascular bundles (*naar*), whereas a calibrated micro-radius smoothly compressed and displaced surface cellulose fibers without fracturing the leaf.\n- **Incision Posture**: The scribe held the stylus strictly perpendicular between thumb and index finger, guiding the shaft with the left thumb's grooved nail (*noraik-kuri*), achieving writing speeds of up to 40 characters per minute."
    },
    {
        "file": "knowledge/artifacts/artifact-koodaram-and-gandham-chisel-pointed-and-needle-pointed-iron-calligraphy-styli.md",
        "slug": "artifact-koodaram-and-gandham-chisel-pointed-and-needle-pointed-iron-calligraphy-styli",
        "category": "artifact",
        "name_en": "Koodaram & Gandham: Dual-Purpose Styli with Scribing Needles & Leaf-Cutting Blades",
        "name_ta": "\u0b95\u0bc2\u0b9f\u0bbe\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bae\u0bcd - \u0b87\u0bb0\u0bc1\u0baa\u0b95\u0bcd\u0b95 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf, \u0b8f\u0b9f\u0bc1 \u0ba8\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0ba4\u0bcd\u0ba4\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0ba3\u0bcd\u0b9f\u0bc2\u0b9a\u0bbf",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Artistic ceremonial and daily iron styli featuring a scribing needle at one pole, an ornate weighted brass balance finial, and a folding or integral leaf-trimming utility blade.",
        "summary_ta": "\u0b93\u0bb2\u0bc8\u0baf\u0bc8 \u0ba8\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bc2\u0bb0\u0bbf\u0baf \u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bc1\u0bae\u0bcd, \u0ba8\u0b9f\u0bc1\u0bb5\u0bbf\u0bb2\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0bae\u0bbe\u0ba9\u0bae\u0bc1\u0bae\u0bcd, \u0bae\u0bc1\u0ba9\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bc2\u0bb0\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0b8e\u0bb4\u0bc1\u0ba4\u0bc1 \u0bae\u0bc1\u0bb3\u0bcd\u0bb3\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bb2\u0ba8\u0bcb\u0b95\u0bcd\u0b95\u0bc1 \u0b87\u0bb0\u0bc1\u0baa\u0b95\u0bcd\u0b95\u0ba4\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbf\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Government Oriental Manuscripts Library Catalogue",
            "Tanjore Museum Metal Artifacts",
            "Naladiyar 395"
        ],
        "content": "# Koodaram & Gandham: Dual-Purpose Writing Instruments\n\nMaster scribes (*ezhuthalar*) wielded multifunctional composite tools designed to streamline complete folio fabrication:\n\n1. *Koodara-Ezhuthani*: The terminal end opposite the stylus point broadened into a flat, razor-sharp curved chisel blade (*koodaram* or *vaali*). This enabled the scribe to trim folios to uniform dimensions and slice ragged leaf margins instantly without switching tools.\n2. *Gandham* (Piercing Bodkin): A sharp conical awl located on the stylus shoulder used to punch identical binding cord holes (*eduth-thulai*) through stacks of forty folios simultaneously.\n3. *Balance Finials*: Elaborately chased in brass, bronze, or silver with motifs of parrots (*kili*), peacocks, or sacred fish, serving as counterweights that stabilized the stylus during prolonged multi-hour scribing sessions."
    },
    {
        "file": "knowledge/concepts/concept-mai-thadaval-lampblack-and-herbal-oil-infusion-for-high-contrast-incised-glyphs.md",
        "slug": "concept-mai-thadaval-lampblack-and-herbal-oil-infusion-for-high-contrast-incised-glyphs",
        "category": "concept",
        "name_en": "Mai-Thadaval: Lampblack, Herbal Extract & Essential Oil Inking for High-Contrast Glyphs",
        "name_ta": "\u0bae\u0bc8 \u0ba4\u0b9f\u0bb5\u0bb2\u0bcd - \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0bae\u0bc8, \u0bb5\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0bb0\u0bbf, \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb0\u0bc1 \u0bb5\u0bc6\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Contrast-rendering process rubbing a suspension of soot from sesame oil lamps and aromatic herbal resins across incised folios, permanently embedding black carbon into carved grooves.",
        "summary_ta": "\u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf\u0baf\u0bbe\u0bb2\u0bcd \u0b95\u0bc0\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0ba9\u0bc8\u0baf\u0bc7\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd \u0b8e\u0bb3\u0bcd\u0bb3\u0bc6\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0bb5\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bcd \u0b95\u0bb0\u0bbf, \u0bb5\u0b9a\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb1\u0bcd\u0bb1\u0bbe\u0bb4\u0bc8\u0b9a\u0bcd \u0b9a\u0bbe\u0bb1\u0bc1 \u0ba4\u0b9f\u0bb5\u0bbf \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bb3\u0bc0\u0bb0\u0bc6\u0ba9 \u0bb5\u0bc6\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc8 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Tamil Palm Leaf Conservation Treatise",
            "Saraswathi Mahal Preservation Archives",
            "Manimekalai 19"
        ],
        "content": "# Mai-Thadaval: Contrast-Rendering Inking Chemistry\n\nFreshly incised incisions on a palm leaf are translucent and nearly invisible to the reader. The text was made permanent and vibrantly legible through *mai-thadaval* (inking and wiping):\n\n- **Sub-Micron Carbon Pigment**: Scribes collected ultrafine amorphous carbon (lampblack / *vilakku-mai*) deposited on earthenware lids placed over oil lamps burning pure sesame (*nallennai*) or castor oil.\n- **Herbal Binder Suspension**: The lampblack was pulverized and suspended in a liquid emulsion comprising juice of *Eclipta prostrata* (*karisalankanni*\u2014providing deep blue-black lustrous depth) and gum acacia resin (*karuvelam-pisiri*).\n- **Application & Wiping**: The black paste was rubbed vigorously into the inscribed grooves using clean cotton swabs. Scribes then rubbed the leaf surface with dry rice bran (*thavidu*), wiping clean the glossy un-incised leaf face while leaving the carved glyphs intensely dark and razor-sharp."
    },
    {
        "file": "knowledge/institutions/institution-kanakkar-and-ezhuthalar-guild-of-royal-scribes-and-scriptorium-librarians.md",
        "slug": "institution-kanakkar-and-ezhuthalar-guild-of-royal-scribes-and-scriptorium-librarians",
        "category": "institution",
        "name_en": "Kanakkar & Ezhuthalar Guild: Corporation of Royal Scribes, Epigraphers & Librarians",
        "name_ta": "\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bb0\u0bcd-\u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0bb3\u0bb0\u0bcd \u0b9a\u0baa\u0bc8 - \u0b85\u0bb0\u0b9a \u0b86\u0bb5\u0ba3\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bcd, \u0b93\u0bb2\u0bc8 \u0ba8\u0bbe\u0baf\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bb4\u0bc1",
        "era": "Classical Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "State-sponsored bureaucratic corporation holding hereditary responsibilities for recording land grants, composing royal edicts, auditing temple wealth, and archiving temple libraries.",
        "summary_ta": "\u0b85\u0bb0\u0b9a\u0bb0\u0bbf\u0ba9\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0b93\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd, \u0ba8\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0baf\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bc1\u0ba4\u0bb2\u0bcd, \u0bb5\u0bb0\u0bbf \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb0\u0b9a\u0bc1\u0bb5\u0ba4\u0bbf \u0bae\u0b95\u0bbe\u0bb2\u0bcd \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0ba8\u0bc2\u0bb2\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0b85\u0bb0\u0b9a\u0bc1\u0baa\u0bcd \u0baa\u0ba3\u0bbf\u0b95\u0bcd \u0b95\u0bb4\u0b95\u0bae\u0bcd.",
        "sources": [
            "Tirumukkudal Inscription of Virarajendra",
            "Thanjavur Brihadisvara Royal Library Charters",
            "Silappadikaram Uraiperukatturai"
        ],
        "content": "# Kanakkar & Ezhuthalar Guild: Royal Scribes & Archivists\n\nAncient and medieval Tamil governance relied upon an extensive, highly literate administrative class organized into professional scriptorium corporations (*Ezhuthuppalli* and *Karanattar*):\n\n- **Olai-Nayagam (Chief Imperial Secretary)**: The highest bureaucratic officer in the Chola and Pandya empires, who sat alongside the king to record verbal royal orders (*thiruvaimozhi*) onto palm leaves.\n- **Thandal-Kanakkar (Revenue Accountants)**: Village and district scribes maintaining cadastral land surveys (*nilavazhi*), irrigation sluice water allocations, and tax rolls inscribed on palm rolls.\n- **Saraswathi-Bhandara (Temple Scriptorium Librarians)**: Attached to monumental institutions like Ennayiram, Tirumukkudal, and Thanjavur, where teams of copyists systematically duplicated deteriorating palm leaves every sixty years to ensure textual immortality."
    },
    {
        "file": "knowledge/technologies/technology-kattuthadi-and-sutharam-teak-binding-boards-and-corded-spine-retention.md",
        "slug": "technology-kattuthadi-and-sutharam-teak-binding-boards-and-corded-spine-retention",
        "category": "technology",
        "name_en": "Kattuthadi & Sutharam: Hardwood Binding Boards, Corded Spines & Folio Security",
        "name_ta": "\u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd - \u0bae\u0bb0\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bb3\u0bcd, \u0ba8\u0bc2\u0bb2\u0bcd\u0b95\u0bcb\u0bb5\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Bookbinding engineering utilizing bevel-edged teak or ebony protection boards, braided silk or coir cords, and bone pins to compress folios into compact, pest-resistant bundles.",
        "summary_ta": "\u0ba8\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0baa\u0ba9\u0bc8\u0baf\u0bc7\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bb0\u0bbf\u0b9a\u0bc8 \u0b95\u0bc1\u0bb2\u0bc8\u0baf\u0bbe\u0bae\u0bb2\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95 \u0b87\u0bb0\u0bc1\u0baa\u0bc1\u0bb1\u0bae\u0bc1\u0bae\u0bcd \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bb3\u0bcd, \u0ba8\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bbf\u0ba3\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "U. V. Swaminatha Iyer Manuscript Collection Records",
            "Catalogus Catalogorum Studies",
            "Naladiyar 312"
        ],
        "content": "# Kattuthadi & Sutharam: Palm-Leaf Bookbinding Mechanics\n\nA loose stack of fragile palm leaves was vulnerable to insect entry, warping, and folio transposition. Scribes engineered the *kattuthadi* binding system:\n\n- **Protective End-Boards (*Kattuthadi*)**: Two precisely planed, beveled hardwood slats (teak, ebony, or rosewood) sandwiching the manuscript stack. The outer faces were often hand-lacquered or carved with floral motifs.\n- **Suthara-Nool (Spine Retaining Cord)**: A braided silk or wax-coated cotton cord threaded through either a single central hole (*oru-thulai*) or dual symmetric holes (*iru-thulai*).\n- **Tension Clamping**: The cord was wrapped spirally around the compressed wooden boards and secured with a carved bone or copper locking pin (*kili*), creating an airtight wooden seal preventing moisture absorption and silverfish infiltration."
    },
    {
        "file": "knowledge/artifacts/artifact-vasambu-thailam-acorus-calamus-and-lemongrass-anti-insect-preservative-resin.md",
        "slug": "artifact-vasambu-thailam-acorus-calamus-and-lemongrass-anti-insect-preservative-resin",
        "category": "artifact",
        "name_en": "Vasambu-Thailam: Sweet Flag, Lemongrass & Citronella Botanical Insecticide Resins",
        "name_ta": "\u0bb5\u0b9a\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bc8\u0bb2\u0bae\u0bcd - \u0baa\u0ba9\u0bc8 \u0b93\u0bb2\u0bc8 \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0ba4\u0bcd \u0ba4\u0bc8\u0bb2\u0bae\u0bcd, \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf \u0ba4\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Specialized volatile herbal oil distillation containing Acorus calamus and Cymbopogon extracts smeared onto folios to prevent attacks by silverfish, booklice, and mold spores.",
        "summary_ta": "\u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bbf\u0baa\u0bcd\u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf, \u0baa\u0bc1\u0ba4\u0bcd\u0ba4\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc2\u0b9e\u0bcd\u0b9a\u0bc8 \u0b8f\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95 \u0bb5\u0b9a\u0bae\u0bcd\u0baa\u0bc1, \u0baa\u0bc1\u0bb2\u0bcd \u0ba4\u0bc8\u0bb2\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0baa\u0bcd\u0baa\u0bc6\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bc2\u0b9a\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc6\u0bb1\u0bbf.",
        "sources": [
            "Saraswathi Mahal Conservation Manual",
            "Ayurvedic Materia Medica of South India",
            "National Mission for Manuscripts Bulletin"
        ],
        "content": "# Vasambu-Thailam: Botanical Manuscript Preservative Oils\n\nThe preservation of centuries-old Tamil palm leaf manuscripts across hot, humid monsoonal climates was made possible by advanced natural pharmacology (*maruthuva-thailam*):\n\n- **Acorus calamus (*Vasambu* / Sweet Flag)**: The dried rhizome contains potent active phenylpropanoids (notably $\\alpha$-asarone and $\\beta$-asarone), which act as powerful neurotoxins and feeding deterrents against silverfish (*Lepisma saccharina*), booklice, and termites.\n- **Citronella & Lemongrass (*Vasanai-Pull*)**: Volatile terpenes in lemongrass essential oil provide broad-spectrum antifungal action, preventing humid mold blooms (*poonam*) during the rainy seasons.\n- **Application Cycle**: Manuscript curators brushed folios every three to five years with a light film of *vasambu-thailam* emulsified with camphor (*karpooram*), keeping the leaf parchment supple while repelling bio-deteriorating pests."
    },
    {
        "file": "knowledge/concepts/concept-granthalipi-and-vatteluttu-epigraphic-stroke-dynamics-on-fibrous-substrates.md",
        "slug": "concept-granthalipi-and-vatteluttu-epigraphic-stroke-dynamics-on-fibrous-substrates",
        "category": "concept",
        "name_en": "Vatteluttu & Grantha Stroke Dynamics: Circular Calligraphy Conditioned by Leaf Fibers",
        "name_ta": "\u0bb5\u0b9f\u0bcd\u0b9f\u0bc6\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbf\u0bb0\u0ba8\u0bcd\u0ba4 \u0bb5\u0bb0\u0bbf\u0bb5\u0b9f\u0bbf\u0bb5 \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd - \u0baa\u0ba9\u0bc8 \u0ba8\u0bbe\u0bb0\u0bbe\u0bb2\u0bcd \u0b89\u0ba8\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bbf\u0bb5\u0b95\u0bcd \u0b95\u0bc8\u0baf\u0bc6\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bc8",
        "era": "Classical Antiquity to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Paleographic evolution explaining how horizontal straight strokes were eliminated in Tamil and Vatteluttu scripts to prevent tearing parallel leaf fibers, giving rise to circular glyphs.",
        "summary_ta": "\u0baa\u0ba9\u0bc8 \u0b93\u0bb2\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0bae\u0b9f\u0bcd\u0b9f \u0ba8\u0bb0\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0b95\u0bbf\u0bb4\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1\u0bb5\u0bbf\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0b95 \u0ba8\u0bc7\u0bb0\u0bcd\u0b95\u0bcb\u0b9f\u0bc1\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bb5\u0bbf\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1, \u0bb5\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bbf\u0bb5 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bbe\u0b95 \u0bae\u0bbe\u0bb1\u0bbf\u0baf \u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bcd\u0b9f\u0bc6\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bb0\u0bbf\u0bb5\u0b9f\u0bbf\u0bb5 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1.",
        "sources": [
            "Mahadevan: Early Tamil Epigraphy",
            "B\u00fchler: Indian Paleography",
            "South Indian Epigraphical Studies"
        ],
        "content": "# Vatteluttu Stroke Dynamics & Fibrous Substrates\n\nOne of the most profound instances of material constraints directing linguistic aesthetics is observed in the paleographic evolution of South Indian scripts:\n\n- **The Rupture Risk of Straight Lines**: A palm leaf consists of thousands of parallel longitudinal cellulose fibers (*naar*) running along its length. If an iron stylus engraves a long horizontal straight line ($\u2014$), it severs multiple adjacent vascular bundles along the grain, causing the leaf to instantly split and split apart under tension.\n- **The Physics of the Arc**: To preserve leaf structural integrity, scribes systematically transformed angular Brahmi strokes into continuous curving loops, sweeping circles, and undulating curves (*vattu* or *vatteluttu*).\n- **Continuous Fluidity**: Curved strokes distributed incision pressure across multiple diagonal fibers, dispersing shear forces and enabling miniature, ultra-dense script layouts containing over fifty characters per ten-inch folio."
    },
    {
        "file": "knowledge/places/place-suriyanarkoil-ancient-chola-manuscript-and-scriptorium-haven.md",
        "slug": "place-suriyanarkoil-ancient-chola-manuscript-and-scriptorium-haven",
        "category": "place",
        "name_en": "Suriyanarkoil: Ancient Chola Manuscript Scriptorium & Astrological Library Haven",
        "name_ta": "\u0b9a\u0bc2\u0bb0\u0bbf\u0baf\u0ba9\u0bbe\u0bb0\u0bcd\u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0b9a\u0bb1\u0bc8, \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0ba8\u0bc2\u0bb2\u0b95\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 900,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Historic Chola religious and academic scriptorium sanctuary in Thanjavur district, celebrated for monumental palm-leaf libraries housing classical epics, medical treatises, and celestial charts.",
        "summary_ta": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bbe\u0bb5\u0bc2\u0bb0\u0bcd \u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf\u0baa\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb2\u0bcb\u0ba4\u0bcd\u0ba4\u0bc1\u0b99\u0bcd\u0b95 \u0b9a\u0bcb\u0bb4\u0ba9\u0bbe\u0bb2\u0bcd \u0b86\u0ba4\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f, \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5, \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bca\u0b95\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Kulottunga Chola I Inscriptions",
            "South Indian Temple Inscriptions Series",
            "Saraswathi Mahal Archive Studies"
        ],
        "content": "# Suriyanarkoil: Ancient Chola Manuscript Haven\n\nSituated near Thiruvidaimarudur in the fertile Kaveri delta of Thanjavur district, Suriyanarkoil (consecrated during the reign of Kulottunga Chola I in the early 11th century CE) operated as a preeminent scriptorium (*Saraswathi-Bhandara*) and celestial observatory.\n\n- **Sacred Manuscript Archive**: Attached to the monumental temple of the Sun God (*Bhaskara*), the complex housed comprehensive repositories of palm-leaf treatises on mathematics (*kanidham*), astronomy and planetary ephemerides (*jyotisha*), Siddha pharmacology (*maruthuvam*), and temple architectural manuals (*shilpa shastra*).\n- **Hereditary Copyists**: Endowment inscriptions record permanent tax-free land assignments (*bhattavritti*) to support scholarly copyists (*ezhuthalar*) whose daily duty was copying, verifying, and oil-treating ancient manuscripts.\n- **Architectural Preservation Vaults**: Scriptorium chambers featured thick double-granite walls, high clerestory ventilation, and subterranean dry storage cellars specifically engineered to isolate vulnerable palm-leaf scrolls from river delta moisture and damp mold."
    }
]

EDGES = [
    [
        "text-tholkappiyam-payiram-verses-on-engraved-palm-scrolls-and-academic-conclaves",
        "DESCRIBES",
        "concept-thalai-patham-borassus-flabellifer-palm-leaf-boiling-curing-and-rib-removal",
        "core",
        "Sangam Era",
        "Tholkappiyam payiram validates ancient academic codification upon cured palm leaf folios.",
        "Tholkappiyam Cirappuppayiram"
    ],
    [
        "concept-thalai-patham-borassus-flabellifer-palm-leaf-boiling-curing-and-rib-removal",
        "PREPARES_SUBSTRATE_FOR",
        "technology-ezhuthani-varkkam-hardened-steel-stylus-geometry-and-incision-mechanics",
        "core",
        "Iron Age to Modern Era",
        "Cured and steamed palm leaves provided flat, smooth surfaces for steel stylus incision.",
        "Traditional Palm-Leaf Manuscript Conservation"
    ],
    [
        "technology-ezhuthani-varkkam-hardened-steel-stylus-geometry-and-incision-mechanics",
        "INFLUENCES",
        "concept-granthalipi-and-vatteluttu-epigraphic-stroke-dynamics-on-fibrous-substrates",
        "core",
        "Classical Antiquity to Medieval Era",
        "Needle incision mechanics on fibrous leaves gave rise to circular Vatteluttu glyphs.",
        "Mahadevan: Early Tamil Epigraphy"
    ],
    [
        "technology-ezhuthani-varkkam-hardened-steel-stylus-geometry-and-incision-mechanics",
        "USES_TOOL",
        "artifact-koodaram-and-gandham-chisel-pointed-and-needle-pointed-iron-calligraphy-styli",
        "core",
        "Iron Age to Modern Era",
        "Dual-ended styli combined incising needles with leaf-trimming chisel blades.",
        "Archaeological Metallurgy of Tamil Styli"
    ],
    [
        "technology-ezhuthani-varkkam-hardened-steel-stylus-geometry-and-incision-mechanics",
        "REQUIRES_CONTRAST",
        "concept-mai-thadaval-lampblack-and-herbal-oil-infusion-for-high-contrast-incised-glyphs",
        "core",
        "Prehistoric to Modern Era",
        "Incised grooves were infused with lampblack and Eclipta juice to render glyphs black.",
        "Tamil Palm Leaf Conservation Treatise"
    ],
    [
        "concept-thalai-patham-borassus-flabellifer-palm-leaf-boiling-curing-and-rib-removal",
        "PRESERVED_BY",
        "artifact-vasambu-thailam-acorus-calamus-and-lemongrass-anti-insect-preservative-resin",
        "core",
        "Prehistoric to Modern Era",
        "Cured leaves were coated with sweet flag and citronella oil to deter silverfish and mold.",
        "Saraswathi Mahal Conservation Manual"
    ],
    [
        "concept-thalai-patham-borassus-flabellifer-palm-leaf-boiling-curing-and-rib-removal",
        "BOUND_BY",
        "technology-kattuthadi-and-sutharam-teak-binding-boards-and-corded-spine-retention",
        "core",
        "Classical Antiquity to Modern Era",
        "Inscribed folios were compressed between teak boards and secured with silk cords.",
        "Catalogus Catalogorum Studies"
    ],
    [
        "technology-ezhuthani-varkkam-hardened-steel-stylus-geometry-and-incision-mechanics",
        "PRACTICED_BY",
        "institution-kanakkar-and-ezhuthalar-guild-of-royal-scribes-and-scriptorium-librarians",
        "core",
        "Classical Sangam to Medieval Era",
        "Scribes and epigraphers maintained imperial archives and temple libraries with styli.",
        "Tirumukkudal Inscription of Virarajendra"
    ],
    [
        "institution-kanakkar-and-ezhuthalar-guild-of-royal-scribes-and-scriptorium-librarians",
        "OPERATED_AT",
        "place-suriyanarkoil-ancient-chola-manuscript-and-scriptorium-haven",
        "core",
        "Early Medieval to Modern Era",
        "Scribes and copyists preserved astronomical and literary treatises at Suriyanarkoil.",
        "Kulottunga Chola I Inscriptions"
    ],
    [
        "artifact-vasambu-thailam-acorus-calamus-and-lemongrass-anti-insect-preservative-resin",
        "APPLIED_AT",
        "place-suriyanarkoil-ancient-chola-manuscript-and-scriptorium-haven",
        "core",
        "Early Medieval to Modern Era",
        "Suriyanarkoil librarians applied herbal oils to maintain palm leaves across monsoons.",
        "Saraswathi Mahal Archive Studies"
    ]
]

TITLE = "Ancient Tamil Palm-Leaf Manuscript Scribing, Iron Stylus Metallurgy & Herbal Preservatives"


def get_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=120)
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]


def main():
    print(f"Ingesting {TITLE} into Moolam Chronicles & Life Graph...")

    # Phase 1: Write Markdown Files
    print("\n[Phase 1] Writing 10 Markdown Knowledge Dossiers...")
    files_written = 0
    for d in DOSSIERS:
        fpath = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        files_written += 1
        print(f"  [Dossier Written] {d['file']}")
    print(f"Phase 1 complete: {files_written} markdown dossiers written.")

    # Phase 2: PostgreSQL Lore Nodes Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    nodes_upserted = 0
    for d in DOSSIERS:
        props = json.dumps({
            "category": d["category"],
            "canonical_file": d["file"],
            "harvester": "batch34_corpus3",
            "domain": TITLE,
        })
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
            str(uuid.uuid4()), d["slug"], d["category"], d["name_en"], d["name_ta"],
            d["era"], d["year_start"], d["year_end"], d.get("thinai", ""),
            d["summary_en"], d["summary_ta"], d["sources"], "core", props
        ))
        nodes_upserted += 1
        print(f"  [Node Upserted] {d['slug']}")
    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} nodes upserted.")

    # Phase 3: PostgreSQL Lore Edges Insertion
    print("\n[Phase 3] Inserting 10 Lore Graph Relationships...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, ev = edge
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
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, ev
        ))
        edges_inserted += 1
        print(f"  [Edge Linked] {src} --({rel})-> {tgt}")
    conn.commit()
    print(f"Phase 3 complete: {edges_inserted} edges processed.")

    # Phase 4: Vector Embeddings
    print(f"\n[Phase 4] Generating 1024-dim {EMBED_MODEL} Embeddings via Ollama...")
    total_chunks = 0
    for d in DOSSIERS:
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s;", (d["slug"],))

        chunks = [
            {
                "language": "en",
                "title": d["name_en"],
                "content": (
                    f"{d['name_en']}\n\nSummary:\n{d['summary_en']}\n\n"
                    f"Key Concepts:\n{d['content'][:1500]}"
                ),
            },
            {
                "language": "ta",
                "title": d["name_ta"],
                "content": (
                    f"{d['name_ta']}\n\nசுருக்கம்:\n{d['summary_ta']}\n\n"
                    f"முக்கிய நுட்பங்கள்:\n{d['content'][:1500]}"
                ),
            },
        ]

        for ch in chunks:
            emb = get_embedding(ch["content"])
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            cur.execute("""
                INSERT INTO rag_chunks (
                    id, node_slug, shelf, language, title, content,
                    source_ref, embedding, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                );
            """, (
                str(uuid.uuid4()), d["slug"], f"shelf-{d['category']}s",
                ch["language"], ch["title"], ch["content"], d["file"], emb_str
            ))
            total_chunks += 1
        print(f"  [Embedded Chunks] {d['slug']} (en + ta)")
    conn.commit()
    cur.close()
    conn.close()

    print(
        f"\nIngestion Complete for {TITLE}! "
        f"({files_written} files, {nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)"
    )


if __name__ == "__main__":
    main()
