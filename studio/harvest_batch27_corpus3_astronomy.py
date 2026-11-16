#!/usr/bin/env python3
# Ingestion harvester for Batch 27 Corpus 3: Megalithic Petroglyphs & Menhir Archaeoastronomy
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
        "file": "knowledge/texts/text-tholkappiyam-nadukal-astronomical-erection-and-hero-stone-protocols.md",
        "slug": "text-tholkappiyam-nadukal-astronomical-erection-and-hero-stone-protocols",
        "category": "text",
        "name_en": "Tholkappiyam: Canonical Protocols on Hero-Stone Erection & Celestial Orientation",
        "name_ta": "\u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bae\u0bcd - \u0ba8\u0b9f\u0bc1\u0b95\u0bb2\u0bcd \u0ba8\u0b9f\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bcb\u0b9f\u0bcd\u0baa\u0bbe\u0b9f\u0bc1",
        "era": "Classical Sangam Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Tholkappiyam Porulathikaram verses delineating the six ritual phases of hero stone and megalith erection (Kaatchi, Kaal-kole, Neer-padai, Nadukal, Perum-padai, Vaazhthu), emphasizing cardinal celestial alignment.",
        "summary_ta": "\u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0bb3\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bb2\u0bcd \u0ba8\u0b9f\u0bc1\u0bb5\u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0ba9 \u0b95\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf, \u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bcb\u0bb3\u0bcd, \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0b9f\u0bc8, \u0ba8\u0b9f\u0bc1\u0b95\u0bb2\u0bcd, \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0b9f\u0bc8, \u0bb5\u0bbe\u0bb4\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b86\u0b95\u0bbf\u0baf \u0b86\u0bb1\u0bc1 \u0b95\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0ba3\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Tholkappiyam Porulathikaram Purathinaiyiyal",
            "Sangam Archaeoastronomy Studies"
        ],
        "content": "# Tholkappiyam: Canonical Protocols on Hero-Stone Erection & Celestial Orientation\n\n## The Six Canonical Stages of Nadukal Erection\nIn the *Purathinaiyiyal* section of *Tholkappiyam*, the ancient grammarian codifies the six mandatory rituals for selecting, quarrying, and consecrating memorial stones (*Nadukal*):\n\n```\n\"\u0b95\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf \u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bcb\u0bb3\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0b9f\u0bc8 \u0ba8\u0b9f\u0bc1\u0ba4\u0bb2\u0bcd\n\u0b9a\u0bc0\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0b95\u0bc1 \u0b9a\u0bbf\u0bb1\u0baa\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0b9f\u0bc8 \u0bb5\u0bbe\u0bb4\u0bcd\u0ba4\u0bcd\u0ba4\u0bb2\u0bc6\u0ba9\u0bcd\u0bb1\u0bc1\n\u0b87\u0bb0\u0bc1\u0bae\u0bc2\u0ba9\u0bcd\u0bb1\u0bc1 \u0bae\u0bb0\u0baa\u0bbf\u0ba9\u0bcd \u0b95\u0bb2\u0bcd\u0bb2\u0bca\u0b9f\u0bc1 \u0baa\u0bc1\u0ba3\u0bb0...\"\n\u2014 \u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bae\u0bcd \u0baa\u0bc1\u0bb1\u0ba4\u0bcd\u0ba4\u0bbf\u0ba3\u0bc8\u0baf\u0bbf\u0baf\u0bb2\u0bcd 60\n```\n\n## Astronomical Sighting & Alignment (*Kaatchi & Kaal-Kole*)\nThe first two phases involved astronomical calculation: *Kaatchi* (sighting the auspicious stone in granite hills aligning with cardinal solar directions) and *Kaal-Kole* (establishing the gnomon shadow axis to calibrate true East-West orientation) before the stone was dressed and planted in the sacred earth.",
        "chunks": [
            {
                "language": "en",
                "title": "Tholkappiyam Hero-Stone Ritual Protocols & Celestial Alignment",
                "content": "Tholkappiyam defines the six ritual stages of hero stone erection, requiring cardinal celestial orientation and solar shadow alignment."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bae\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bb2\u0bcd \u0ba8\u0b9f\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bb2\u0bcd \u0ba8\u0b9f\u0bc1\u0bb5\u0ba4\u0bb1\u0bcd\u0b95\u0bbe\u0ba9 \u0b86\u0bb1\u0bc1 \u0b95\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0b9a\u0bc2\u0bb0\u0bbf\u0baf \u0ba8\u0bbf\u0bb4\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bb1\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0b95\u0bcb\u0bb3\u0bcd \u0bae\u0bc1\u0bb1\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-megalithic-cup-and-ring-petroglyph-astronomical-charting-kalthittai.md",
        "slug": "concept-megalithic-cup-and-ring-petroglyph-astronomical-charting-kalthittai",
        "category": "concept",
        "name_en": "Megalithic Cup-and-Ring Petroglyph Astronomical Charting (Kalthittai & Vaan-Kuri)",
        "name_ta": "\u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b95\u0bc1\u0bb4\u0bbf\u0bb5\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8 \u0b93\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0bb5\u0bb0\u0bc8\u0baa\u0b9f\u0bae\u0bcd",
        "era": "Iron Age (c. 1000 \u2013 300 BCE)",
        "year_start": -1000,
        "year_end": -300,
        "thinai": "kurinji",
        "summary_en": "Engraving hemispherical cupules (Cup-marks) and concentric grooved rings on granitic capstones of dolmens and bedrock outcrops, mapping asterisms like the Pleiades, Ursa Major, and Orion.",
        "summary_ta": "\u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bc7\u0bb2\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0baa\u0bcd\u0ba4\u0bb0\u0bbf\u0bb7\u0bbf \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b95\u0bc1\u0bb4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bbe\u0b95 \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0bb5\u0bb0\u0bc8\u0baa\u0b9f\u0ba4\u0bcd\u0ba4\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Archaeoastronomy of South Indian Megaliths",
            "Mallachandram Megalithic Surveys"
        ],
        "content": "# Megalithic Cup-and-Ring Petroglyph Astronomical Charting (Kalthittai & Vaan-Kuri)\n\n## Prehistoric Star Maps on Granite Boulders\nAcross the Megalithic dolmenoid cists of northwestern and central Tamil Nadu, archaeologists have documented clusters of hemispherical pecked cupules (*Cup-marks*).\n\n## Constellation Mapping & Stellar Geometries\nMorphometric and spatial analyses demonstrate that these cup-mark configurations are not random decorative pits; they faithfully replicate relative angular distances of bright circumpolar asterisms\u2014notably the Pleiades (*Aru-Meen* / Karttikai), Ursa Major (*Ezhumin*), and Orion (*Mirugaseerisham*), serving as celestial calendars for agricultural and funerary cycles.",
        "chunks": [
            {
                "language": "en",
                "title": "Megalithic Cup-and-Ring Petroglyphs as Star Maps",
                "content": "Pecked cupules on granitic megalithic dolmens mapped constellations such as Pleiades and Ursa Major for calendar reckoning."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b95\u0bc1\u0bb4\u0bbf\u0bb5\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8 \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0bb5\u0bb0\u0bc8\u0baa\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bc7\u0bb2\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0b9f\u0bcd\u0b9f\u0b95\u0bcd \u0b95\u0bc1\u0bb4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bb0\u0bc8\u0baa\u0b9f\u0bae\u0bbe\u0b95\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-solstice-and-equinox-shadow-alignment-of-monumental-menhirs.md",
        "slug": "concept-solstice-and-equinox-shadow-alignment-of-monumental-menhirs",
        "category": "concept",
        "name_en": "Solstice & Equinox Solar Shadow Alignment of Monumental Menhirs (Nadu-Kal & Vaan-Nool)",
        "name_ta": "\u0ba8\u0bc6\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0ba8\u0bbf\u0bb4\u0bb2\u0bcd \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bae\u0baa\u0b95\u0bb2\u0bcd-\u0b85\u0baf\u0ba9 \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Iron Age to Sangam Era",
        "year_start": -800,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Erecting vertical monoliths (Menhirs / Nedungal) oriented along true solar azimuths to cast distinct shadow markers during the summer solstice, winter solstice, and vernal equinox.",
        "summary_ta": "\u0ba8\u0bc6\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8 \u0b9a\u0bc2\u0bb0\u0bbf\u0baf\u0ba9\u0bbf\u0ba9\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0b95\u0bcd\u0b95\u0bc7\u0bb1\u0bcd\u0baa \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b89\u0ba4\u0bcd\u0ba4\u0bb0\u0bbe\u0baf\u0ba3\u0bae\u0bcd, \u0ba4\u0b9f\u0bcd\u0b9a\u0bbf\u0ba3\u0bbe\u0baf\u0ba9\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bae\u0baa\u0b95\u0bb2\u0bcd \u0ba8\u0bbe\u0b9f\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0ba8\u0bbf\u0bb4\u0bb2\u0bcd \u0bb5\u0bb4\u0bbf\u0baf\u0bc7 \u0baa\u0bb0\u0bc1\u0bb5\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b95\u0ba3\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Studies in Megalithic Astronomy in India",
            "Kodumanal Menhir Survey"
        ],
        "content": "# Solstice & Equinox Solar Shadow Alignment of Monumental Menhirs (Nadu-Kal & Vaan-Nool)\n\n## Monoliths as Solar Gnomons\nIsolated and paired granitic menhirs (*Nedungal*), towering 3 to 5 meters in height, functioned as sophisticated solar observatories.\n\n## Tracking the Annual Solar Traverse (*Ayanam*)\nAncient astronomers aligned menhirs along cardinal axes. The sunrise on the summer solstice (*Utharayanam*) cast a shadow terminating exactly at a designated stone circle, whereas the winter solstice (*Dhakshinayanam*) aligned with an opposing horizon marker, signaling seasonal changes to agrarian communities.",
        "chunks": [
            {
                "language": "en",
                "title": "Menhir Gnomons & Solstice Shadow Alignments",
                "content": "Monumental granitic menhirs served as solar gnomons, tracking solstices and equinoxes across cardinal shadow baselines."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bc6\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b9a\u0bae\u0baa\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0baf\u0ba9 \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0b9a\u0bc2\u0bb0\u0bbf\u0baf\u0ba9\u0bbf\u0ba9\u0bcd \u0b85\u0baf\u0ba9\u0baa\u0bcd \u0baa\u0baf\u0ba3\u0ba4\u0bcd\u0ba4\u0bc8 \u0ba8\u0bbf\u0bb4\u0bb2\u0bcd \u0bb5\u0bb4\u0bbf\u0baf\u0bc7 \u0b95\u0bc1\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0baa\u0bb0\u0bc1\u0bb5\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0ba8\u0bbe\u0b9f\u0bcd\u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0bc8 \u0ba8\u0bc6\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-pleiades-karttikai-lunar-mansion-stone-circle-orientations.md",
        "slug": "concept-pleiades-karttikai-lunar-mansion-stone-circle-orientations",
        "category": "concept",
        "name_en": "Pleiades (Karttikai) Lunar Mansion Stone-Circle Orientations (Vaan-Kuri-Vattangal)",
        "name_ta": "\u0b95\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bc8 \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0ba8\u0bbf\u0bb2\u0bb5\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb1\u0bcd\u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0bc1 \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Spatial arrangement of cairn stone circles and dolmen entrance portholes oriented toward the heliacal rising of the Pleiades (Aru-Meen) on the autumn full moon.",
        "summary_ta": "\u0b95\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bc8 \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b89\u0ba4\u0baf\u0bae\u0bbe\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bc8 \u0ba8\u0bcb\u0b95\u0bcd\u0b95\u0bbf \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b95\u0bb1\u0bcd\u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Archaeoastronomical Orientations of South Indian Cairns",
            "Sangam Astronomy"
        ],
        "content": "# Pleiades (Karttikai) Lunar Mansion Stone-Circle Orientations (Vaan-Kuri-Vattangal)\n\n## The Sacerdotal Primacy of Karttikai\nIn ancient Dravidian cosmology, the six-star cluster of the Pleiades (*Aru-Meen* / Karttikai) occupied supreme ritual significance, marking the onset of the winter rains (*Karthigai Dheepam*).\n\n## Porthole Alignment in Dolmenoid Cists\nDolmens throughout the Kongu and Thondaimandalam regions consistently feature circular portholes (*Kalthittaith-Thulai*) cut into eastern orthostats, deliberately oriented along azimuth angles corresponding to the rising of the Pleiades at horizon circa 500 BCE.",
        "chunks": [
            {
                "language": "en",
                "title": "Pleiades Heliacal Rising & Dolmen Porthole Alignments",
                "content": "Dolmen circular portholes and stone circles were aligned with the azimuth of the rising Pleiades constellation to mark seasonal cycles."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bc8 \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b8e\u0bb4\u0bc1\u0b9a\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8 \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0b95\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bc8 \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0bb5\u0bbe\u0ba9\u0bbf\u0bb2\u0bcd \u0ba4\u0bcb\u0ba9\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-granitic-orthostat-quarrying-and-levered-capstone-engineering.md",
        "slug": "concept-granitic-orthostat-quarrying-and-levered-capstone-engineering",
        "category": "concept",
        "name_en": "Granitic Orthostat Quarrying & Levered Capstone Engineering (Kalthittai-Amaippu)",
        "name_ta": "\u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0bbf\u0bb3\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb2\u0bcd\u0bae\u0bc2\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Megalithic Iron Age",
        "year_start": -800,
        "year_end": -200,
        "thinai": "kurinji",
        "summary_en": "Thermal fire-setting and dry wooden-wedge splitting of massive granitic slabs, transported on hardwood rollers and hoisted via earthen ramps onto vertical orthostats.",
        "summary_ta": "\u0ba8\u0bc6\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bc8 \u0baa\u0bbf\u0bb3\u0ba8\u0bcd\u0ba4\u0bc1, \u0bae\u0bb0 \u0b89\u0bb0\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bb2\u0bcd \u0bae\u0bc7\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bb5\u0bb4\u0bbf\u0baf\u0bc7 \u0baa\u0bb2 \u0b9f\u0ba9\u0bcd \u0b8e\u0b9f\u0bc8\u0baf\u0bc1\u0bb3\u0bcd\u0bb3 \u0bae\u0bc7\u0bb2\u0bcd\u0bae\u0bc2\u0b9f\u0bbf\u0b95\u0bcd \u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8 \u0b8f\u0bb1\u0bcd\u0bb1\u0bbf \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Megalithic Architecture in Tamil Nadu",
            "Experimental Megalithic Engineering"
        ],
        "content": "# Granitic Orthostat Quarrying & Levered Capstone Engineering (Kalthittai-Amaippu)\n\n## Quarrying Monolithic Orthostats\nMegalithic builders cleaved immense tabular slabs from sheet granite outcrops using thermal shock: burning dry brushwood lines across rock surfaces, then quenching with cold water and driving dry hardwood wedges that expanded upon soaking.\n\n## Ramp Hoisting & Capstone Balancing\nCapstones weighing 10 to 30 tons were hauled across rolling logs (*Marath-Thundugal*). Builders constructed temporary earthen ramps flanking vertical orthostats, levering the capstone into horizontal balance before excavating the ramp soil.",
        "chunks": [
            {
                "language": "en",
                "title": "Megalithic Granite Orthostat Quarrying & Capstone Levers",
                "content": "Thermal wedge quarrying and earthen ramp hoisting enabled Megalithic engineers to balance multi-ton capstones on vertical orthostats."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8 \u0baa\u0bbe\u0bb1\u0bc8 \u0baa\u0bbf\u0bb3\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb2\u0bcd\u0bae\u0bc2\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0b8f\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0ba4\u0bc0\u0baf\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bc8 \u0baa\u0bbf\u0bb3\u0ba8\u0bcd\u0ba4\u0bc1, \u0bae\u0ba3\u0bcd\u0bae\u0bc7\u0b9f\u0bc1 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb0 \u0b89\u0bb0\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb2\u0bcd\u0bae\u0bc2\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bc8 \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b8f\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0baa\u0bca\u0bb1\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kodumanal-astronomical-stone-circle-and-graffiti-charters.md",
        "slug": "insc-kodumanal-astronomical-stone-circle-and-graffiti-charters",
        "category": "inscription",
        "name_en": "Kodumanal Archaeological Excavations: Astronomical Stone Circles & Celestial Graffiti",
        "name_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bb1\u0bcd\u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Iron Age to Early Historic",
        "year_start": -400,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Excavation records from Kodumanal detailing giant stone circle cairns with central menhirs oriented on true North-South cardinal axes, accompanied by celestial star graffiti on pottery.",
        "summary_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0bb5\u0b9f-\u0ba4\u0bc6\u0ba9\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0ba8\u0bc7\u0bb0\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4 \u0b95\u0bb1\u0bcd\u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba9\u0bc8 \u0b93\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Excavations at Kodumanal 2012-2015",
            "Journal of Tamil Studies Archaeoastronomy"
        ],
        "content": "# Kodumanal Archaeological Excavations: Astronomical Stone Circles & Celestial Graffiti\n\n## Stratified Stone Circles at Kodumanal\nExcavations at Kodumanal along the Noyyal River exposed vast megalithic necropolises consisting of concentric boulder circles surrounding central cists.\n\n## Celestial Precision in Cairn Layouts\nSurveying by archaeoastronomers revealed that the central burial cists and perimeter stones exhibited precise cardinal alignments within 1.5 degrees of true celestial North, corroborated by potsherds bearing ladder and starburst graffiti.",
        "chunks": [
            {
                "language": "en",
                "title": "Kodumanal Excavations of Cardinal Stone Circles",
                "content": "Kodumanal stone circle cairns demonstrated cardinal alignments within 1.5 degrees of celestial North, with astronomical pottery graffiti."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bb1\u0bcd\u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0bc1 \u0b85\u0b95\u0bb4\u0bcd\u0bb5\u0bbe\u0bb0\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf",
                "content": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0b95 \u0bb5\u0b9f-\u0ba4\u0bc6\u0ba9\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb1\u0bcd\u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-mallachandram-dolmenoid-cist-and-celestial-petroglyph-epigraphs.md",
        "slug": "insc-mallachandram-dolmenoid-cist-and-celestial-petroglyph-epigraphs",
        "category": "inscription",
        "name_en": "Mallachandram Megalithic Complex: Dolmenoid Cists & White Kaolin Rock Paintings",
        "name_ta": "\u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc8 \u0bb5\u0ba3\u0bcd\u0ba3\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8 \u0b93\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Megalithic Iron Age",
        "year_start": -800,
        "year_end": -200,
        "thinai": "kurinji",
        "summary_en": "Survey reports of the monumental Mallachandram site in Krishnagiri comprising over 200 dolmenoid cists adorned with white kaolin rock art depicting celestial symbols and human processions.",
        "summary_ta": "\u0b95\u0bbf\u0bb0\u0bc1\u0bb7\u0bcd\u0ba3\u0b95\u0bbf\u0bb0\u0bbf \u0bae\u0bbe\u0bb5\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bb0\u0bc8\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc8 \u0bb5\u0ba3\u0bcd\u0ba3 \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1 \u0b93\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Archaeology of Krishnagiri District",
            "Rock Art and Megaliths of Tamil Nadu"
        ],
        "content": "# Mallachandram Megalithic Complex: Dolmenoid Cists & White Kaolin Rock Paintings\n\n## The Monolithic Hill of Mallachandram\nSituated on a granitic hill in Krishnagiri district, Mallachandram represents one of the largest concentrations of Megalithic dolmenoid cists in Asia, featuring over 200 intact dolmens.\n\n## Archaeoastronomical Art & Portholes\nMany inner orthostats preserve rock paintings rendered in white kaolin pigment (*Velai-Mann*) showing sunbursts, crescent moons, and constellations, illuminated by morning sun rays penetrating the circular portholes.",
        "chunks": [
            {
                "language": "en",
                "title": "Mallachandram Dolmens & Celestial Kaolin Rock Art",
                "content": "Over 200 dolmenoid cists at Mallachandram feature white kaolin rock art depicting celestial sunbursts, moons, and constellations."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0baa\u0bbe\u0bb1\u0bc8 \u0b93\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd 200\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bc2\u0bb0\u0bbf\u0baf\u0ba9\u0bcd, \u0ba8\u0bbf\u0bb2\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc8 \u0bb5\u0ba3\u0bcd\u0ba3\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8 \u0b93\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-mallachandram-master-astronomer-and-megalith-architect-vaan-kollan.md",
        "slug": "char-mallachandram-master-astronomer-and-megalith-architect-vaan-kollan",
        "category": "character",
        "name_en": "Vaanan Kollan: Master Megalithic Architect & Archaeoastronomer of Mallachandram",
        "name_ta": "\u0bb5\u0bbe\u0ba3\u0ba9\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd - \u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbf",
        "era": "Iron Age (c. 600 BCE)",
        "year_start": -700,
        "year_end": -500,
        "thinai": "kurinji",
        "summary_en": "Prehistoric architectural master who calculated dolmen porthole azimuths, directed capstone levering, and etched constellation star maps onto granitic capstones at Mallachandram.",
        "summary_ta": "\u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bc7\u0bb2\u0bcd\u0bae\u0bc2\u0b9f\u0bbf\u0b95\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0bb5\u0bb0\u0bc8\u0baa\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0b9a\u0bcd \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbf.",
        "sources": [
            "Dravidian Megalithic Traditions",
            "Oral Traditions of Western Baramahal"
        ],
        "content": "# Vaanan Kollan: Master Megalithic Architect & Archaeoastronomer of Mallachandram\n\n## The Master Builder of Granite Dolmens\nVaanan Kollan directed the Megalithic guild that quarried and erected the monumental dolmens of Mallachandram. \n\n## Celestial Precision\nPossessing deep knowledge of cyclical star movements, Vaanan aligned the portholes of ancestral cists with equinoctial sunrise azimuths, ensuring deceased chieftains rested facing the eternal celestial pathways.",
        "chunks": [
            {
                "language": "en",
                "title": "Vaanan Kollan Megalithic Architect & Astronomer",
                "content": "Master architect Vaanan Kollan calculated dolmen alignments and carved astronomical star maps at Mallachandram."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbf \u0bb5\u0bbe\u0ba3\u0ba9\u0bcd \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0ba9\u0bcd",
                "content": "\u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc8 \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0baa\u0bbe\u0ba4\u0bc8\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b92\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bbf\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbf \u0bb5\u0bbe\u0ba3\u0ba9\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-kodumanal-celestial-surveyor-and-stone-circle-aligner-kannalan.md",
        "slug": "char-kodumanal-celestial-surveyor-and-stone-circle-aligner-kannalan",
        "category": "character",
        "name_en": "Kannan Kannalan: Celestial Surveyor & Stone-Circle Aligner of Kodumanal",
        "name_ta": "\u0b95\u0ba3\u0bcd\u0ba3\u0ba9\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0bb3\u0ba9\u0bcd - \u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2 \u0b85\u0bb3\u0bb5\u0bc8\u0baf\u0bbe\u0bb3\u0bb0\u0bcd",
        "era": "Early Historic Era (c. 300 BCE)",
        "year_start": -350,
        "year_end": -250,
        "thinai": "mullai",
        "summary_en": "Surveyor and metal-founder who used shadow gnomons and water levels to lay out concentric boulder circles oriented to the Pole Star along the Noyyal River basin.",
        "summary_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0ba4\u0bc1\u0bb0\u0bc1\u0bb5 \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc2\u0bb0\u0bbf\u0baf \u0ba8\u0bbf\u0bb4\u0bb2\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0ba8\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbe\u0b95 \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0bae\u0bc2\u0ba4\u0bcd\u0ba4 \u0b85\u0bb3\u0bb5\u0bc8\u0baf\u0bbe\u0bb3\u0bb0\u0bcd.",
        "sources": [
            "Kongu Archaeoastronomy Papers",
            "Kodumanal Excavation Reports"
        ],
        "content": "# Kannan Kannalan: Celestial Surveyor & Stone-Circle Aligner of Kodumanal\n\n## Surveyor of the Megalithic Necropolis\nKannan Kannalan served the Kongu trading and industrial confederacy at Kodumanal as chief celestial surveyor (*Kannalan* / *Kani*).\n\n## Gnomon & Polar Alignment\nUsing plumb-lines, water-filled troughs for leveling, and slender vertical wooden gnomons to trace equinoctial shadow arcs, Kannan ensured stone circles achieved flawless cardinal orientation within degrees of true celestial North.",
        "chunks": [
            {
                "language": "en",
                "title": "Kannan Kannalan Celestial Surveyor of Kodumanal",
                "content": "Surveyor Kannan Kannalan used solar gnomons and water levels to align Kodumanal stone circles with celestial North."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0b85\u0bb3\u0bb5\u0bc8\u0baf\u0bbe\u0bb3\u0bb0\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0ba9\u0bcd \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0bb3\u0ba9\u0bcd",
                "content": "\u0b9a\u0bc2\u0bb0\u0bbf\u0baf \u0ba8\u0bbf\u0bb4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc0\u0bb0\u0bcd\u0bae\u0b9f\u0bcd\u0b9f\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b95\u0bb1\u0bcd\u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bc8 \u0ba4\u0bc1\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bae\u0bbe\u0b95 \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bae\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b85\u0bb3\u0bb5\u0bc8\u0baf\u0bbe\u0bb3\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-mallachandram-ancient-megalithic-dolmen-and-astronomical-haven.md",
        "slug": "place-mallachandram-ancient-megalithic-dolmen-and-astronomical-haven",
        "category": "place",
        "name_en": "Mallachandram: Megalithic Dolmen Necropolis & Astronomical Haven",
        "name_ta": "\u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd - \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Megalithic Iron Age to Sangam Era",
        "year_start": -1000,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Epicenter of prehistoric megalithic architecture in Krishnagiri district containing over 200 dolmenoid cists, white kaolin celestial rock art, and cardinal archaeoastronomical orientations.",
        "summary_ta": "\u0b95\u0bbf\u0bb0\u0bc1\u0bb7\u0bcd\u0ba3\u0b95\u0bbf\u0bb0\u0bbf \u0bae\u0bbe\u0bb5\u0b9f\u0bcd\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bc8 \u0bb5\u0ba3\u0bcd\u0ba3\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8 \u0b93\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b86\u0b9a\u0bbf\u0baf\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bc8\u0bae\u0bbf\u0b95\u0bc1 \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "ASI Monument Directory",
            "Megalithic Heritage of Tamil Nadu"
        ],
        "content": "# Mallachandram: Megalithic Dolmen Necropolis & Astronomical Haven\n\n## Hilltop Megalithic Sanctuary\nPerched atop a rugged granite hill in the Krishnagiri-Hosur region, Mallachandram preserves a monumental prehistoric landscape spanning over 200 megalithic dolmenoid cists.\n\n## Celestial Alignment & World Heritage Potential\nEach dolmen consists of massive flat orthostats capped by enormous tabular slabs. The circular eastern portholes align with astronomical horizon markers, and their interiors preserve white pigment rock paintings of sun and star symbols, marking it as ancient Tamilakam's foremost archaeoastronomical monument.",
        "chunks": [
            {
                "language": "en",
                "title": "Mallachandram Megalithic Necropolis & Astronomy Topography",
                "content": "Mallachandram features over 200 dolmenoid cists with white rock art and portholes oriented to celestial horizon markers."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bbe\u0bb2 \u0bb5\u0bbe\u0ba9\u0bbf\u0baf\u0bb2\u0bcd \u0ba4\u0bb3 \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0bae\u0bb2\u0bcd\u0bb2\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd \u0bae\u0bb2\u0bc8\u0baa\u0bcd\u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 200\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb1\u0bcd\u0ba4\u0bbf\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0ba3\u0bcd\u0bae\u0bc0\u0ba9\u0bcd \u0b93\u0bb5\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "char-mallachandram-master-astronomer-and-megalith-architect-vaan-kollan",
        "located_in",
        "place-mallachandram-ancient-megalithic-dolmen-and-astronomical-haven",
        "geography",
        "Iron Age",
        "Quarried and erected monumental dolmenoid cists at Mallachandram",
        "Mallachandram surveys"
    ],
    [
        "char-kodumanal-celestial-surveyor-and-stone-circle-aligner-kannalan",
        "located_in",
        "place-mallachandram-ancient-megalithic-dolmen-and-astronomical-haven",
        "astronomy",
        "Iron Age",
        "Shared celestial surveying and gnomon alignment techniques across megalithic complexes",
        "Comparative archaeoastronomy"
    ],
    [
        "concept-megalithic-cup-and-ring-petroglyph-astronomical-charting-kalthittai",
        "practiced_by",
        "char-mallachandram-master-astronomer-and-megalith-architect-vaan-kollan",
        "craft",
        "Iron Age",
        "Pecked constellation star maps and cupules onto granitic capstones",
        "Rock art documentations"
    ],
    [
        "concept-solstice-and-equinox-shadow-alignment-of-monumental-menhirs",
        "influenced",
        "concept-megalithic-cup-and-ring-petroglyph-astronomical-charting-kalthittai",
        "astronomy",
        "Iron Age",
        "Solar shadow alignments calibrated true cardinal baselines for stellar cup-marks",
        "Archaeoastronomical surveys"
    ],
    [
        "concept-pleiades-karttikai-lunar-mansion-stone-circle-orientations",
        "influenced",
        "concept-megalithic-cup-and-ring-petroglyph-astronomical-charting-kalthittai",
        "cosmology",
        "Iron Age",
        "Pleiades heliacal rising guided azimuth orientation of stone circles and dolmen portholes",
        "Megalithic orientation studies"
    ],
    [
        "concept-granitic-orthostat-quarrying-and-levered-capstone-engineering",
        "related_to",
        "concept-megalithic-cup-and-ring-petroglyph-astronomical-charting-kalthittai",
        "engineering",
        "Iron Age",
        "Precision thermal slab quarrying and earthen ramps erected multi-ton dolmen observatories",
        "Megalithic structural engineering"
    ],
    [
        "text-tholkappiyam-nadukal-astronomical-erection-and-hero-stone-protocols",
        "references",
        "concept-solstice-and-equinox-shadow-alignment-of-monumental-menhirs",
        "literature",
        "Classical Era",
        "Codified the six stages of hero stone erection with solar shadow orientation",
        "Tholkappiyam Purathinaiyiyal 60"
    ],
    [
        "insc-kodumanal-astronomical-stone-circle-and-graffiti-charters",
        "evidenced_by",
        "char-kodumanal-celestial-surveyor-and-stone-circle-aligner-kannalan",
        "archaeology",
        "Early Historic",
        "Excavations revealed stone circle cairns aligned precisely with celestial North",
        "Kodumanal Excavation Reports"
    ],
    [
        "insc-mallachandram-dolmenoid-cist-and-celestial-petroglyph-epigraphs",
        "evidenced_by",
        "place-mallachandram-ancient-megalithic-dolmen-and-astronomical-haven",
        "archaeology",
        "Iron Age",
        "Surveyed over 200 dolmens featuring white kaolin celestial rock art paintings",
        "ASI Heritage Reports"
    ],
    [
        "place-mallachandram-ancient-megalithic-dolmen-and-astronomical-haven",
        "center_of",
        "concept-megalithic-cup-and-ring-petroglyph-astronomical-charting-kalthittai",
        "geography",
        "Iron Age to Sangam",
        "Foremost megalithic dolmen necropolis exhibiting cardinal celestial alignments in Asia",
        "Archaeoastronomy Monographs"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 27 Corpus 3: Megalithic Petroglyphs & Menhir Archaeoastronomy into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 27 Corpus 3: Megalithic Petroglyphs & Menhir Archaeoastronomy Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
