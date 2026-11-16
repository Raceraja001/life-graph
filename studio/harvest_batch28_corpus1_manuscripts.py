#!/usr/bin/env python3
# Ingestion harvester for Batch 28 Corpus 1: Palm-Leaf Manuscripts, Stylus Calligraphy & Cartography
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
        "file": "knowledge/texts/text-tholkappiyam-scribal-orthography-and-manuscript-preservation-protocols.md",
        "slug": "text-tholkappiyam-scribal-orthography-and-manuscript-preservation-protocols",
        "category": "text",
        "name_en": "Tholkappiyam: Canonical Verses on Graphemic Orthography & Scribal Phonology",
        "name_ta": "\u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bae\u0bcd - \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0bb5\u0bb0\u0bbf\u0bb5\u0b9f\u0bbf\u0bb5 \u0bb5\u0bbf\u0ba4\u0bbf\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd",
        "era": "Classical Sangam Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "marutham",
        "summary_en": "Foundational grammatical sutras in Tholkappiyam Ezhuthathikaram regulating phonemic character drafting, dotting of consonants (Pulli), vowel elongation, and scribal incising conventions on palm-leaf surfaces.",
        "summary_ta": "\u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bc2\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb3\u0bcd\u0bb3\u0bbf \u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8, \u0bae\u0bc6\u0baf\u0bcd\u0baf\u0bc6\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b89\u0baf\u0bbf\u0bb0\u0bc6\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0ba9\u0bc8\u0baf\u0bcb\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bc1\u0bae\u0bcd \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0ba3 \u0bb5\u0bbf\u0ba4\u0bbf\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Tholkappiyam Ezhuthathikaram",
            "Nannool Scribal Commentary",
            "History of Tamil Epigraphy"
        ],
        "content": "# Tholkappiyam: Canonical Verses on Graphemic Orthography & Scribal Phonology\n\n## The Orthography of Incised Letters\nIn the *Ezhuthathikaram* of *Tholkappiyam*, ancient Tamil scribal phonology and letter drafting protocols are codified with mathematical precision:\n\n```\n\"\u0bae\u0bc6\u0baf\u0bcd\u0baf\u0bbf\u0ba9\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0baa\u0bc1\u0bb3\u0bcd\u0bb3\u0bbf\u0baf\u0bca\u0b9f\u0bc1 \u0ba8\u0bbf\u0bb2\u0bc8\u0baf\u0bb2\u0bcd;\n\u0b8e\u0b95\u0bb0 \u0b92\u0b95\u0bb0\u0ba4\u0bcd\u0ba4\u0bc1 \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b85\u0bb1\u0bcd\u0bb1\u0bc7...\"\n\u2014 \u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd 15-16\n```\n\n## The Structural Challenge of Palm-Leaf Scribing\nWriting with a sharp iron stylus (*Ezhuthani*) across the fibrous, parallel grain of seasoned palmyrah palm leaves (*Olai*) presented severe physical constraints. Placing a punctate dot (*Pulli*) or sharp horizontal line would pierce and split the leaf along its vein. Scribes developed cursive, circular graphemes and omitted the superscript dot in rapid hand-copying to preserve leaf structural integrity.",
        "chunks": [
            {
                "language": "en",
                "title": "Tholkappiyam Scribal Orthography & Pulli Dot Conventions",
                "content": "Tholkappiyam Ezhuthathikaram codifies Tamil phonemic orthography and the specialized adaptation of circular letterforms to prevent splitting palm-leaf grain."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b93\u0bb2\u0bc8\u0b9a\u0bcd\u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0ba3\u0bae\u0bcd",
                "content": "\u0baa\u0ba9\u0bc8\u0baf\u0bcb\u0bb2\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0ba8\u0bb0\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd \u0b95\u0bbf\u0bb4\u0bbf\u0baf\u0bbe\u0bae\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0b95\u0bcd\u0b95 \u0bb5\u0b9f\u0bcd\u0b9f\u0bc6\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0b9f\u0bbf\u0bb5\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0baa\u0bc1\u0bb3\u0bcd\u0bb3\u0bbf \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bca\u0bb2\u0bcd\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0ba3\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-palmyrah-leaf-seasoning-turmeric-boiling-and-guillotine-sizing.md",
        "slug": "concept-palmyrah-leaf-seasoning-turmeric-boiling-and-guillotine-sizing",
        "category": "concept",
        "name_en": "Palmyrah Leaf Seasoning, Turmeric Boiling & Guillotine Sizing (Olai-Padhanidhal)",
        "name_ta": "\u0baa\u0ba9\u0bc8\u0baf\u0bcb\u0bb2\u0bc8 \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bb2\u0bcd, \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0b85\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0ba4\u0bcd\u0ba4\u0bbf \u0ba8\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Curing juvenile Borassus flabellifer fronds through shade drying, boiling in turmeric (Manjal) and lime water to deter silverfish and wood-borers, followed by guillotine edge-trimming (Olai-Vettukathi) into uniform rectangular manuscript folios.",
        "summary_ta": "\u0b87\u0bb3\u0bae\u0bcd\u0baa\u0ba9\u0bc8 \u0b93\u0bb2\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf, \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b85\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf\u0b95\u0bb3\u0bcd \u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b9a\u0bae\u0b85\u0bb3\u0bb5\u0bbe\u0b95 \u0ba8\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Manuscriptology of South India",
            "Traditional Palm Leaf Conservation",
            "Saraswathi Mahal Preservation Records"
        ],
        "content": "# Palmyrah Leaf Seasoning, Turmeric Boiling & Guillotine Sizing (Olai-Padhanidhal)\n\n## Frond Harvesting & Material Selection\nOnly young, tender fronds of the palmyrah palm (*Borassus flabellifer*, specifically the sweet-sap *Thaali-Panai* variety) possessed the supple, non-brittle epidermis required for lasting manuscripts. Harvesters cut blemish-free leaves before their spines hardened.\n\n## Turmeric Decoction & Anti-Fungal Boiling\nThe harvested fronds were dried in shaded breezes, then immersed in boiling copper cauldrons containing water infused with fresh turmeric rhizomes (*Manjal*), neem leaves, and shell lime (*Sunnambu*). Curcumin penetrated the cellulose matrix, imparting a golden luster while acting as an irreversible natural fungicide and insect repellent against silverfish.\n\n## Sizing & Perforation\nOnce conditioned, folios were smoothed by drawing them over polished wooden cylinders and trimmed to exact lengths using a pivoted curved guillotine knife (*Olai-Vettukathi*). Twin stringing holes (*Kuzhi*) were burned through the leaf using heated needle irons.",
        "chunks": [
            {
                "language": "en",
                "title": "Palmyrah Leaf Seasoning & Anti-Insect Turmeric Boiling",
                "content": "Boiling young palmyrah fronds in turmeric decoctions and trimming with guillotine knives produced insect-resistant folios for manuscript scribes."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0ba9\u0bc8\u0baf\u0bcb\u0bb2\u0bc8 \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0b85\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0baa\u0b9a\u0bcd\u0b9a\u0bc8 \u0b93\u0bb2\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b85\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf \u0b85\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bae \u0b85\u0bb3\u0bb5\u0bc1 \u0baa\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bbe\u0b95 \u0ba8\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bbe\u0b95 \u0bae\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening.md",
        "slug": "concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening",
        "category": "concept",
        "name_en": "Incised Iron Stylus Calligraphy & Lampblack Carbon Inking (Ezhuthani & Mai-Poosal)",
        "name_ta": "\u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf \u0bb5\u0bb0\u0bbf\u0bb5\u0b9f\u0bbf\u0bb5\u0b95\u0bcd \u0b95\u0bc0\u0bb1\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc8 \u0baa\u0bc2\u0b9a\u0bbf \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc1\u0bb2\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bcd",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Rapid micro-incising of cursive Tamil script using needle-sharp hardened bloomery steel styluses (Ezhuthani), followed by smearing charred coconut-shell lampblack (Mai) mixed with aromatic resin oil into incisions to render text permanently legible.",
        "summary_ta": "\u0b8e\u0b83\u0b95\u0bc1 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf\u0baf\u0bbe\u0bb2\u0bcd \u0b93\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bc0\u0bb1\u0bbf, \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd \u0b9a\u0bbf\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8 \u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0baa\u0bc2\u0b9a\u0bbf \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bc1\u0bb2\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bc8.",
        "sources": [
            "Tamil Scribes and Styluses",
            "Epigraphia Indica",
            "Ancient Writing Instruments"
        ],
        "content": "# Incised Iron Stylus Calligraphy & Lampblack Carbon Inking (Ezhuthani & Mai-Poosal)\n\n## The Iron Stylus (*Ezhuthani*)\nThe principal scribal instrument was the *Ezhuthani*, a composite steel tool featuring a hardened micro-chisel or needle point at the lower tip, a weighted brass or bone central grip for inertia, and a flat knife-blade at the crest for trimming fronds.\n\n## Tactile Scribing Dynamics\nThe scribe rested the conditioned leaf across the left thumb and manipulated the stylus with the right thumb and forefinger, etching cursive graphemes with controlled pressure to penetrate only the waxy cuticle layer without severing the structural vascular bundles.\n\n## Carbon Inking & Blackening (*Mai-Poosal*)\nFreshly scratched incisions were invisible against the yellow frond. The scribe wiped a viscous black paste (*Mai*) made from charred coconut shells, castor oil, and the juice of *Karisalanganni* (Eclipta prostrata) across the leaf. The carbon granules lodged permanently within the grooves, while excess ink was wiped away, revealing jet-black, indelible calligraphy.",
        "chunks": [
            {
                "language": "en",
                "title": "Incised Iron Stylus Scribing & Lampblack Inking Dynamics",
                "content": "Scribes used needle-sharp steel styluses to etch cursive characters into palm leaves, rubbing lampblack carbon paste into grooves for permanent contrast."
            },
            {
                "language": "ta",
                "title": "\u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf \u0b95\u0bc0\u0bb1\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc8 \u0baa\u0bc2\u0b9a\u0bc1\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf\u0baf\u0bbe\u0bb2\u0bcd \u0b93\u0bb2\u0bc8\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bc0\u0bb1\u0bbf, \u0ba4\u0bc7\u0b99\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b9a\u0bbf\u0bb0\u0b9f\u0bcd\u0b9f\u0bc8 \u0bae\u0bc8 \u0baa\u0bc2\u0b9a\u0bbf \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb0\u0ba8\u0bcd\u0ba4\u0bb0\u0bae\u0bbe\u0b95 \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0baa\u0bb4\u0b99\u0bcd\u0b95\u0bbe\u0bb2 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-perforated-cord-binding-and-teak-wood-protective-boards-chuvadi.md",
        "slug": "concept-perforated-cord-binding-and-teak-wood-protective-boards-chuvadi",
        "category": "concept",
        "name_en": "Perforated Cord Binding & Teak-Wood Protective Boards (Chuvadi-Kattu)",
        "name_ta": "\u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0ba8\u0bc2\u0bb2\u0bcd \u0b95\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0 \u0baa\u0bb2\u0b95\u0bc8 \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Mechanical binding of hundreds of incised palm leaves threaded through dual punctured alignment holes with spun cotton cord (Kattu-Nool), clamped between carved teak or rosewood protective covers (Kamba-Palgai).",
        "summary_ta": "\u0ba8\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b8f\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bb0\u0bbf\u0b9a\u0bc8\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0ba4\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bcd \u0bb5\u0bb4\u0bbf\u0baf\u0bc7 \u0ba8\u0bc2\u0bb2\u0bcd \u0b95\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bb3\u0bc8 \u0b87\u0bb0\u0bc1\u0baa\u0bc1\u0bb1\u0bae\u0bc1\u0bae\u0bcd \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b87\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Manuscript Curation Protocols",
            "Saraswathi Mahal Library Catalogues"
        ],
        "content": "# Perforced Cord Binding & Teak-Wood Protective Boards (Chuvadi-Kattu)\n\n## The Mechanics of Manuscript Assembly\nA complete classical text comprised dozens or hundreds of leaves. To maintain strict serial ordering, twin circular holes were burned equidistant from the lateral edges.\n\n## Cord Threading & Retention Knots\nA heavy, multi-ply cotton cord (*Chuvadi-Nool*) was threaded through one hole, looped around, and knotted with a polished bone or lead stop-peg (*Kili-Thatu*). Readers uncoiled the cord and flipped leaves vertically like Venetian blinds without detaching the sequence.\n\n## Hardwood Clamping Covers (*Kamba-Palgai*)\nThe stack was sandwiched between two slightly larger protective boards of seasoned teak, ebony, or sandalwood. Tied under firm tension with an outer cord wrap, the rigid boards prevented warping under fluctuating monsoon humidity.",
        "chunks": [
            {
                "language": "en",
                "title": "Palm-Leaf Manuscript Cord Threading & Hardwood Covers",
                "content": "Threading folios through alignment holes and securing them between carved teak protective boards preserved manuscripts for centuries."
            },
            {
                "language": "ta",
                "title": "\u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b95\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bcd\u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1",
                "content": "\u0b8f\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bb0\u0bbf\u0b9a\u0bc8\u0baf\u0bbe\u0b95 \u0ba8\u0bc2\u0bb2\u0bcd \u0b95\u0bcb\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0baa\u0bcd \u0baa\u0bb2\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b87\u0b9f\u0bc8\u0baf\u0bc7 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0bc6\u0bae\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-epistolary-scroll-couriers-and-cloth-wrapped-land-deeds-pattayam.md",
        "slug": "concept-epistolary-scroll-couriers-and-cloth-wrapped-land-deeds-pattayam",
        "category": "concept",
        "name_en": "Epistolary Scroll Couriers & Cloth-Wrapped Land Deeds (Olai-Pattayam & Thoodhu)",
        "name_ta": "\u0b85\u0bb0\u0b9a\u0bc1 \u0b93\u0bb2\u0bc8 \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0ba4\u0baa\u0bbe\u0bb2\u0bcd \u0ba4\u0bc2\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0baf\u0bae\u0bcd",
        "era": "Sangam to Chola Era",
        "year_start": -200,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Official state administration using rolled palm-leaf missives (Surul-Olai) sealed with royal clay bullae, dispatched via swift foot-couriers (Thoodhuvar) and archived in red wax-treated textile pouches.",
        "summary_ta": "\u0b85\u0bb0\u0b9a \u0b86\u0ba3\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb0\u0bc1\u0bb3\u0bcb\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bbf \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8 \u0baa\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba4\u0bc2\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bb5\u0bb4\u0bbf\u0baf\u0bc7 \u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0baf \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0bbe\u0b95 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Chola Revenue Administration",
            "Epigraphic Registers of Land Grants"
        ],
        "content": "# Epistolary Scroll Couriers & Cloth-Wrapped Land Deeds (Olai-Pattayam & Thoodhu)\n\n## Bureaucracy of the Palm Leaf\nIn imperial Chola and Pandya realms, everyday civil and judicial administration functioned entirely on palm-leaf rolls (*Surul-Olai*). Imperial scribes (*Olai-Nayagam*) inscribed land surveys, tax remissions, and sovereign orders.\n\n## Royal Seal Authentication & Dispatch\nThe finished scroll was rolled tightly, tied with silk or bark cord, and enveloped in molten beeswax stamped with the monarch's dynastic seal (Tiger for Cholas, Double Fish for Pandyas). Royal relay couriers (*Vira-Thoodhuvar*) ran along military highways, carrying missives in oilskin pouches across provinces.",
        "chunks": [
            {
                "language": "en",
                "title": "Palm-Leaf Royal Missives & Epistolary Couriers",
                "content": "Rolled palm-leaf scrolls sealed with wax dynastic crests served as administrative decrees dispatched by royal relay couriers."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb0\u0b9a \u0b9a\u0bc1\u0bb0\u0bc1\u0bb3\u0bcb\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc2\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0bbe\u0b95 \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0b85\u0bb0\u0b9a \u0b86\u0ba3\u0bc8\u0b95\u0bb3\u0bc8 \u0b9a\u0bc1\u0bb0\u0bc1\u0bb3\u0bcb\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bbf \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8 \u0baa\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbf\u0bb0\u0bc8\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bc2\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b85\u0ba9\u0bc1\u0baa\u0bcd\u0baa\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0bbe\u0b95\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-thanjavur-saraswathi-mahal-scribal-guild-and-manuscript-endowments.md",
        "slug": "insc-thanjavur-saraswathi-mahal-scribal-guild-and-manuscript-endowments",
        "category": "inscription",
        "name_en": "Thanjavur Epigraphs: Royal Scriptoria, Scribe Guilds & Chuvadi Endowments",
        "name_ta": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bbe\u0bb5\u0bc2\u0bb0\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0ba8\u0bc2\u0bb2\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0bb3\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Imperial Chola to Nayaka Era",
        "year_start": 985,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Temple and palace lithic records at Thanjavur documenting royal scriptorium offices (Saraswathi Bhandaram), land grants to copyist scribes, and endowments for oil and lemongrass leaf preservation.",
        "summary_ta": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bc8 \u0baa\u0bc6\u0bb0\u0bbf\u0baf\u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb0\u0b9a\u0bc1\u0bb5\u0ba4\u0bbf \u0bae\u0b95\u0bbe\u0bb2\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0b9f\u0bbf\u0baf\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95 \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. II",
            "Thanjavur Saraswathi Mahal Epigraphic Registers"
        ],
        "content": "# Thanjavur Epigraphs: Royal Scriptoria, Scribe Guilds & Chuvadi Endowments\n\n## Royal Libraries (*Saraswathi Bhandaram*)\nInscriptions in the Thanjavur region record the foundation and maintenance of institutional manuscript libraries termed *Saraswathi Bhandaram*.\n\n## Scribe Endowments & Maintenance\nChola inscriptions detail grants of tax-free land (*Pangu*) awarded to master scribes (*Ezhuthalar*) tasked with transcribing aging palm-leaf texts onto fresh seasoned folios, alongside provisions of lemongrass oil (*Thailam*) to preserve leaf flexibility.",
        "chunks": [
            {
                "language": "en",
                "title": "Thanjavur Scriptorium Libraries & Scribe Endowments",
                "content": "Lithic records at Thanjavur document institutional Saraswathi Bhandaram scriptoria, copyist land grants, and preservation oils."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0b9e\u0bcd\u0b9a\u0bbe\u0bb5\u0bc2\u0bb0\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0ba8\u0bc2\u0bb2\u0b95\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0baa\u0bb4\u0bc8\u0baf \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0b9f\u0bbf\u0baf\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b9a\u0bcb\u0bb4 \u0bae\u0ba9\u0bcd\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8 \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1 \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kanchipuram-ghatika-manuscript-library-and-scriptorium-charters.md",
        "slug": "insc-kanchipuram-ghatika-manuscript-library-and-scriptorium-charters",
        "category": "inscription",
        "name_en": "Kanchipuram Ghatika Epigraphs: Ancient Collegiate Manuscript Archives",
        "name_ta": "\u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf\u0baa\u0bc1\u0bb0\u0bae\u0bcd \u0b95\u0b9f\u0bbf\u0b95\u0bc8 \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0ba8\u0bc2\u0bb2\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bbf\u0b9a\u0bcd\u0b9a\u0bbe\u0bb2\u0bc8 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Pallava Era (c. 600 \u2013 850 CE)",
        "year_start": 600,
        "year_end": 850,
        "thinai": "marutham",
        "summary_en": "Pallava lithic charters at Kanchipuram detailing the grand collegiate Ghatika, its massive multilingual palm-leaf manuscript vaults, and endowments for resident scholar-scribes.",
        "summary_ta": "\u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf\u0baa\u0bc1\u0bb0\u0bae\u0bcd \u0b95\u0b9f\u0bbf\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b87\u0baf\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0b95\u0bbe\u0baa\u0bcd\u0baa\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0b85\u0bb1\u0bbf\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Pallava Charters of Kanchipuram",
            "Epigraphia Indica Vol. XVIII"
        ],
        "content": "# Kanchipuram Ghatika Epigraphs: Ancient Collegiate Manuscript Archives\n\n## The Premier University of Ancient South India\nThe *Ghatika* of Kanchipuram was an internationally renowned center of higher education, attracting scholars from across Asia.\n\n## Manuscript Scriptorium Charters\nPallava inscriptions on granite temple basements describe endowments supporting hundreds of copyist students and scribal masters maintaining astronomical tables, grammatical canons, and legal treatises on durable seasoned palm leaves.",
        "chunks": [
            {
                "language": "en",
                "title": "Kanchipuram Ghatika Manuscript Archives & Scriptorium",
                "content": "Pallava epigraphs at Kanchipuram record the collegiate Ghatika scriptorium and its endowed vaults of palm-leaf manuscripts."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf\u0baa\u0bc1\u0bb0\u0bae\u0bcd \u0b95\u0b9f\u0bbf\u0b95\u0bc8 \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0baa\u0bb2\u0bcd\u0bb2\u0bb5\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf \u0b95\u0b9f\u0bbf\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0bb2\u0bcd\u0bb2\u0bbe\u0baf\u0bbf\u0bb0\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0b9f\u0bbf\u0baf\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0b95\u0bb2\u0bcd\u0bb5\u0bbf\u0b9a\u0bcd\u0b9a\u0bbe\u0bb2\u0bc8 \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-madurai-master-manuscript-scribe-ezhuthanip-paavalar.md",
        "slug": "char-madurai-master-manuscript-scribe-ezhuthanip-paavalar",
        "category": "character",
        "name_en": "Maran Paavalar: Master Calligrapher & Chief Scribe of the Madurai Academy",
        "name_ta": "\u0bae\u0bbe\u0bb1\u0ba9\u0bcd \u0baa\u0bbe\u0bb5\u0bb2\u0bb0\u0bcd - \u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b9a\u0b99\u0bcd\u0b95 \u0b85\u0bb5\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0bb3\u0bb0\u0bcd",
        "era": "Sangam Era (c. 100 BCE \u2013 100 CE)",
        "year_start": -100,
        "year_end": 100,
        "thinai": "marutham",
        "summary_en": "Hereditary master calligrapher attached to the royal Pandya court in Madurai, celebrated for his rapid, unblemished stylus calligraphy and supervision of the imperial archives.",
        "summary_ta": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bbf\u0bb4\u0bc8\u0baf\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b8f\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd.",
        "sources": [
            "Madurai Sangam Biographies",
            "Pandya Literary Traditions"
        ],
        "content": "# Maran Paavalar: Master Calligrapher & Chief Scribe of the Madurai Academy\n\n## Scribe to the Sangam Poets\nMaran Paavalar directed the royal copying atelier of Madurai under the early Pandya kings. Renowned for writing 500 verses a day without a single leaf tear, he trained dozens of apprentice scribes.\n\n## The Keeper of the Canons\nMaran oversaw the transcription of oral bardic anthologies into permanent bound palm-leaf codices (*Chuvadi*), ensuring poems like *Netunalvaatai* and *Kuruntokai* survived for future generations.",
        "chunks": [
            {
                "language": "en",
                "title": "Maran Paavalar Master Manuscript Calligrapher Biography",
                "content": "Master calligrapher Maran Paavalar directed the Pandya scribal atelier in Madurai, inscribing oral bardic poems into permanent codices."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0bb3\u0bb0\u0bcd \u0bae\u0bbe\u0bb1\u0ba9\u0bcd \u0baa\u0bbe\u0bb5\u0bb2\u0bb0\u0bcd",
                "content": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b9a\u0b99\u0bcd\u0b95 \u0b85\u0bb5\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b93\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bbf\u0bb4\u0bc8\u0baf\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b95\u0bb5\u0bbf\u0ba4\u0bc8\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b8e\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bbe\u0ba3\u0bbf \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-kanchipuram-ghatika-textual-archivist-chuvadi-kaavalan.md",
        "slug": "char-kanchipuram-ghatika-textual-archivist-chuvadi-kaavalan",
        "category": "character",
        "name_en": "Dharmakeerthi Kaavalan: Chief Textual Archivist of the Kanchipuram Ghatika",
        "name_ta": "\u0ba4\u0bb0\u0bc1\u0bae\u0b95\u0bc0\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf \u0b95\u0bbe\u0bb5\u0bb2\u0ba9\u0bcd - \u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf \u0b95\u0b9f\u0bbf\u0b95\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0bb5\u0bb2\u0bb0\u0bcd",
        "era": "Classical Pallava Era (c. 650 CE)",
        "year_start": 620,
        "year_end": 680,
        "thinai": "marutham",
        "summary_en": "Venerated librarian and archivist at Kanchipuram who systematized thematic shelf cataloging, pest-resistant oil fumigation, and copying rotas across thousands of manuscripts.",
        "summary_ta": "\u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf \u0b95\u0b9f\u0bbf\u0b95\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b86\u0baf\u0bbf\u0bb0\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0bb5\u0b95\u0bc8\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0baa\u0bc2\u0b9a\u0bcd\u0b9a\u0bbf\u0b95\u0bb3\u0bcd \u0b85\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bc2\u0bb2\u0b95\u0bb0\u0bcd.",
        "sources": [
            "Ghatika Records of Kanchipuram",
            "Pallava Intellectual History"
        ],
        "content": "# Dharmakeerthi Kaavalan: Chief Textual Archivist of the Kanchipuram Ghatika\n\n## Guardian of the Manuscript Vaults\nDharmakeerthi Kaavalan administered the subterranean stone archives of the Kanchipuram Ghatika. \n\n## Preservation Innovations\nDharmakeerthi instituted biannual oil treatments: wiping folios with a blend of lemongrass (*Vasanap-Pullu*) and camphor oil, repelling pests and preserving the supple flexibility of priceless leaves across decades.",
        "chunks": [
            {
                "language": "en",
                "title": "Dharmakeerthi Kaavalan Chief Archivist of Kanchipuram",
                "content": "Chief archivist Dharmakeerthi Kaavalan systematized cataloging and lemongrass oil preservation in the Kanchipuram Ghatika library."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf \u0b95\u0b9f\u0bbf\u0b95\u0bc8 \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0bb5\u0bb2\u0bb0\u0bcd \u0ba4\u0bb0\u0bc1\u0bae\u0b95\u0bc0\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf",
                "content": "\u0b95\u0bbe\u0b9e\u0bcd\u0b9a\u0bbf \u0b95\u0b9f\u0bbf\u0b95\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0baa\u0bb2\u0bcd\u0bb2\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd \u0b8f\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bbe\u0b9a\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0bc1\u0bb2\u0bcd \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0baa\u0bc2\u0b9a\u0bbf \u0ba4\u0bb2\u0bc8\u0bae\u0bc1\u0bb1\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc1\u0bb1\u0bc8\u0baf\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bc2\u0bb2\u0b95\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-madurai-ancient-sangam-scribal-academy-and-scriptorium-haven.md",
        "slug": "place-madurai-ancient-sangam-scribal-academy-and-scriptorium-haven",
        "category": "place",
        "name_en": "Madurai: Ancient Sangam Scribal Academy & Scriptorium Haven",
        "name_ta": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0ba4\u0bae\u0bbf\u0bb4\u0bcd\u0b9a\u0bcd \u0b9a\u0b99\u0bcd\u0b95 \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0b85\u0bb5\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0ba3\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Venerable capital of the Pandyas on the Vaigai River, celebrated as the historic seat of the Tamil Sangam academies, royal archival treasuries, and master manuscript scribal guilds.",
        "summary_ta": "\u0bb5\u0bc8\u0b95\u0bc8 \u0ba8\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bae\u0bc1\u0bae\u0bcd, \u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bcd \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0ba9 \u0b9a\u0b99\u0bcd\u0b95\u0baa\u0bcd \u0baa\u0bb2\u0b95\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bc1\u0bae\u0bbe\u0ba9 \u0bae\u0ba4\u0bc1\u0bb0\u0bc8.",
        "sources": [
            "Maduraikkanchi",
            "Silappathikaram",
            "Archaeological Surveys of Madurai"
        ],
        "content": "# Madurai: Ancient Sangam Scribal Academy & Scriptorium Haven\n\n## Capital of Literary Immortalization\nSituated on the fertile plains of the Vaigai River, Madurai flourished as the intellectual and administrative capital of classical Tamil civilization. \n\n## The Scriptorium of the Sangam\nWithin the royal palace precincts and temple complexes, master scribes converted oral bardic verse into permanent palm-leaf manuscripts. The city housed dedicated archives (*Aavana-Kalam*) where land deeds, court judgments, and literary corpora were cataloged under royal protection.",
        "chunks": [
            {
                "language": "en",
                "title": "Madurai Ancient Scribal Academy & Scriptorium Topography",
                "content": "Madurai on the Vaigai River was the premier center for classical Tamil manuscript scribing and royal archival treasuries."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b9a\u0b99\u0bcd\u0b95 \u0b8f\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc1\u0bb5\u0b9f\u0bbf \u0b85\u0bb5\u0bc8\u0b95\u0bcd \u0b95\u0bb3\u0bae\u0bcd",
                "content": "\u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bbe\u0ba9 \u0bae\u0ba4\u0bc1\u0bb0\u0bc8, \u0b9a\u0b99\u0bcd\u0b95 \u0b87\u0bb2\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b93\u0bb2\u0bc8\u0b9a\u0bcd\u0b9a\u0bc1\u0bb5\u0b9f\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0b85\u0bb1\u0bbf\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf\u0ba4\u0bc1."
            }
        ]
    }
]
EDGES = [
    [
        "char-madurai-master-manuscript-scribe-ezhuthanip-paavalar",
        "located_in",
        "place-madurai-ancient-sangam-scribal-academy-and-scriptorium-haven",
        "history",
        "Sangam Era",
        "Operated royal scribal atelier in the Sangam academy of Madurai",
        "Maduraikkanchi & literary records"
    ],
    [
        "char-kanchipuram-ghatika-textual-archivist-chuvadi-kaavalan",
        "participated_in",
        "place-madurai-ancient-sangam-scribal-academy-and-scriptorium-haven",
        "scholarship",
        "Classical Era",
        "Exchanged certified palm-leaf copies of grammatical canons with Madurai scriptoria",
        "Pallava-Pandya intellectual annals"
    ],
    [
        "concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening",
        "practiced_by",
        "char-madurai-master-manuscript-scribe-ezhuthanip-paavalar",
        "craft",
        "Sangam Era",
        "Mastered micro-incising of circular graphemes and lampblack contrasting",
        "Traditional scribal genealogies"
    ],
    [
        "concept-palmyrah-leaf-seasoning-turmeric-boiling-and-guillotine-sizing",
        "influenced",
        "concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening",
        "technology",
        "Sangam Era",
        "Conditioned boiled fronds provided durable unblemished surfaces for stylus scribing",
        "Manuscriptology treatises"
    ],
    [
        "concept-perforated-cord-binding-and-teak-wood-protective-boards-chuvadi",
        "related_to",
        "concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening",
        "binding",
        "Sangam Era",
        "Threaded cord assembly and hardwood boards protected incised folios from damage",
        "Saraswathi Mahal protocols"
    ],
    [
        "concept-epistolary-scroll-couriers-and-cloth-wrapped-land-deeds-pattayam",
        "related_to",
        "concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening",
        "administration",
        "Sangam to Chola",
        "State administrative missives utilized incised palm-leaf scrolls sealed with dynastic crests",
        "Inscriptional administrative studies"
    ],
    [
        "text-tholkappiyam-scribal-orthography-and-manuscript-preservation-protocols",
        "references",
        "concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening",
        "grammar",
        "Classical Era",
        "Codified orthographic rules adapted to palm-leaf grain physical constraints",
        "Tholkappiyam Ezhuthathikaram"
    ],
    [
        "insc-thanjavur-saraswathi-mahal-scribal-guild-and-manuscript-endowments",
        "evidenced_by",
        "char-kanchipuram-ghatika-textual-archivist-chuvadi-kaavalan",
        "epigraphy",
        "Chola to Nayaka",
        "Charters confirmed institutional scriptoria endowments and copyist rations",
        "South Indian Inscriptions"
    ],
    [
        "insc-kanchipuram-ghatika-manuscript-library-and-scriptorium-charters",
        "evidenced_by",
        "place-madurai-ancient-sangam-scribal-academy-and-scriptorium-haven",
        "epigraphy",
        "Pallava Era",
        "Documented inter-collegiate manuscript transfers and scriptorium maintenance",
        "Pallava Charters"
    ],
    [
        "place-madurai-ancient-sangam-scribal-academy-and-scriptorium-haven",
        "center_of",
        "concept-incised-iron-stylus-calligraphy-ezhuthani-and-lampblack-blackening",
        "geography",
        "Sangam Era",
        "Foremost royal academy and production center for canonical Tamil literature",
        "Maduraikkanchi topographical notes"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 28 Corpus 1: Palm-Leaf Manuscripts, Stylus Calligraphy & Cartography into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 28 Corpus 1: Palm-Leaf Manuscripts, Stylus Calligraphy & Cartography Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
