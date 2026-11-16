#!/usr/bin/env python3
# Ingestion harvester for Batch 26 Corpus 1: Cotton Ginning, Bow-String Carding & Muslin Spindles
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
        "file": "knowledge/texts/text-perumpanarruppadai-fine-muslin-weaving-and-serpent-slough-poetry.md",
        "slug": "text-perumpanarruppadai-fine-muslin-weaving-and-serpent-slough-poetry",
        "category": "text",
        "name_en": "Perumpanarruppadai Verses on Gossamer Muslin Robes & Royal Textile Endowments",
        "name_ta": "\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 - \u0baa\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b89\u0bb0\u0bbf \u0b85\u0ba9\u0bcd\u0ba9 \u0b86\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Canonical Pattuppattu verses by Kadiyalur Uruthirankannanar describing diaphanous royal garments resembling shed serpent skins and rising smoke, presented to bards by King Ilandhiraiyan.",
        "summary_ta": "\u0ba4\u0bca\u0ba3\u0bcd\u0b9f\u0bc8\u0bae\u0bbe\u0ba9\u0bcd \u0b87\u0bb3\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8\u0baf\u0ba9\u0bcd \u0baa\u0bbe\u0ba3\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0b86\u0bb5\u0bbf\u0baf\u0ba9\u0bcd\u0ba9, \u0baa\u0bbe\u0bae\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0b89\u0bb0\u0bbf \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0b86\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Perumpanarruppadai lines 468-475",
            "Pattuppattu Commentary",
            "Sangam Textile History"
        ],
        "content": "# Perumpanarruppadai Verses on Gossamer Muslin Robes & Royal Textile Endowments\n\n## Classical Poetic Attestation of Translucent Weaving\nIn the classical Sangam anthology *Perumpanarruppadai*, poet Kadiyalur Uruthirankannanar immortalizes the extreme refinement of ancient Tamil cotton weaving:\n\n```\n\"\u0ba8\u0bcb\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bc1\u0bb4\u0bc8\u0b95\u0bb2\u0bcd\u0bb2\u0bbe \u0ba8\u0bc1\u0ba3\u0bcd\u0bae\u0bc8\u0baf \u0baa\u0bc2\u0b95\u0bcd\u0b95\u0ba9\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1\n\u0b85\u0bb0\u0bb5\u0bc1\u0bb0\u0bbf \u0b85\u0ba9\u0bcd\u0ba9 \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0ba8\u0bb2\u0bcd\u0b95\u0bbf\n\u0b86\u0bb5\u0bbf\u0baf\u0ba9\u0bcd\u0ba9 \u0b85\u0bb5\u0bbf\u0bb0\u0bcd\u0ba8\u0bc2\u0bb1\u0bcd \u0b95\u0bb2\u0bbf\u0b99\u0bcd\u0b95\u0bae\u0bcd...\"\n\u2014 \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 468-470\n```\n\n## The Serpent-Slough Simile (*Paambuuri*)\nPoets repeatedly likened elite royal cotton cloths to *Aravuri* (the translucent discarded molt of a serpent). The weave was so microscopically tight and uniform that individual warp threads defied visual discernment (*Nokku nuzhaikalla nunmaiya*).\n\n## Social Status & Bardic Investiture\nWhen wandering bards (*Panar*) arrived at the court of King Thondaiman Ilandhiraiyan clad in travel-worn rags, the monarch bestowed upon them gleaming garments of gossamer muslin (*Aaviyanna avirnoot kalingam*), transforming their social standing with courtly splendor.",
        "chunks": [
            {
                "language": "en",
                "title": "Perumpanarruppadai Muslin Weaving & Serpent Slough Similes",
                "content": "Perumpanarruppadai verses by Kadiyalur Uruthirankannanar describe translucent cotton robes resembling serpent skins and rising steam gifted by King Ilandhiraiyan to wandering bards."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 \u0b86\u0bb5\u0bbf\u0baf\u0ba9\u0bcd\u0ba9 \u0b86\u0b9f\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0bb5\u0bc1\u0bb0\u0bbf \u0bb5\u0bb0\u0bcd\u0ba3\u0ba9\u0bc8",
                "content": "\u0baa\u0bbe\u0bae\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0ba4\u0bcb\u0bb2\u0bcd \u0baa\u0bcb\u0ba9\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0bb4\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0b95\u0bc8 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf\u0ba4\u0bbe\u0b95 \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0bae\u0bc7\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b86\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0ba3\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 \u0baa\u0bbe\u0b9f\u0bb2\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-bow-string-vibrating-cotton-carding-villadithal-panchu.md",
        "slug": "concept-bow-string-vibrating-cotton-carding-villadithal-panchu",
        "category": "concept",
        "name_en": "Bow-String Vibrating Cotton Carding & Seed Fluffing (Villadithal & Panju-Kottu)",
        "name_ta": "\u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9e\u0bcd\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bcd\u0b9f\u0bc1 \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0b9a\u0bcd \u0b9a\u0bc0\u0bb0\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Acoustic carding of raw seed-cotton using taut gut-string archery bows (Vil). The vibrating transverse harmonics aerated tangled fibers, separating debris and seed husks into cloud-like spinning roils.",
        "summary_ta": "\u0bb5\u0bbf\u0bb2\u0bcd \u0ba8\u0bbe\u0ba3\u0bbf\u0ba9\u0bcd \u0bae\u0bc0\u0bb3\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1 \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bcd\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bbf, \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0b87\u0bb4\u0bc8\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0b9e\u0bcd\u0b9a\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Sangam Industrial Crafts",
            "Traditional Indian Textile Technology",
            "Ethnographic Weaving Surveys"
        ],
        "content": "# Bow-String Vibrating Cotton Carding & Seed Fluffing (Villadithal & Panju-Kottu)\n\n## The Physics of Bow-String Carding\nBefore cotton fibers could be drawn into thread, raw bolls (*Paruthi-Kottai*) had to be mechanically declumped. Tamil artisans employed an archery-style carding bow (*Vil* or *Panju-Vil*) strung with high-tension dried gut.\n\n## Acoustic Resonant De-seeding\nHolding the bow stave over a mound of unginned cotton, the artisan struck the string with a heavy wooden plectrum. The rapid acoustic vibrations flicked the cotton fibers into suspension, disentangling knotted bolls while heavy seed fragments dropped below under gravity.\n\n## Preparation of Spinning Rolls (*Punji*)\nThe resulting aerated, cloud-soft lint was rolled around smooth tamarind dowels into cylindrical slivers called *Punji*, providing uniform density for drop-spindle drafting.",
        "chunks": [
            {
                "language": "en",
                "title": "Acoustic Bow-String Cotton Carding & Villadithal Mechanics",
                "content": "Mechanical carding of raw Gossypium cotton using vibrating gut-string bows separated seed husks and aligned fibers into airy spinning slivers known as Punji."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0baa\u0b9e\u0bcd\u0b9a\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bcd\u0b9f\u0bc1 \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0bb5\u0bbf\u0bb2\u0bcd \u0ba8\u0bbe\u0ba3\u0bc8 \u0bae\u0bb0\u0b9a\u0bcd\u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbe\u0bb2\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf \u0b89\u0ba3\u0bcd\u0b9f\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b87\u0bb4\u0bc8\u0b95\u0bb3\u0bc8 \u0baa\u0b9e\u0bcd\u0b9a\u0bbe\u0b95\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-terracotta-spindle-whorl-rotational-inertia-and-fine-yarn-spinning.md",
        "slug": "concept-terracotta-spindle-whorl-rotational-inertia-and-fine-yarn-spinning",
        "category": "concept",
        "name_en": "Terracotta Spindle-Whorl Rotational Inertia & Ultra-Fine Yarn Spinning (Thakli & Nool-Nootral)",
        "name_ta": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bb3\u0bbf \u0b9a\u0bc1\u0bb4\u0bb2\u0bcd\u0bb5\u0bc7\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0ba8\u0bc2\u0bb2\u0bcd \u0ba8\u0bc2\u0bb1\u0bcd\u0bb1\u0bb2\u0bcd",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Gyroscopic drop-spindle spinning using calibrated perforated terracotta and bone whorls (Thakli) to spin ultra-high twist yarns required for gossamer muslins.",
        "summary_ta": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0b86\u0bb1\u0bcd\u0bb1\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bc6\u0bb2\u0bcd\u0bb2\u0bbf\u0baf, \u0b85\u0ba4\u0bbf\u0b95 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc7\u0bb1\u0bbf\u0baf \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0ba8\u0bc2\u0bb2\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bc2\u0bb1\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd\u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Kodumanal Excavations",
            "Uraiyur Spindle Assemblages",
            "Textile Archaeology of Tamil Nadu"
        ],
        "content": "# Terracotta Spindle-Whorl Rotational Inertia & Ultra-Fine Yarn Spinning (Thakli & Nool-Nootral)\n\n## Drop-Spindle Mechanics (*Thakli*)\nThe spinning of gossamer cotton yarns relied on drop-spindles comprising an iron or bone shaft weighted at the base with a perforated terracotta or steatite flywheel (*Thakli-Urulai*).\n\n## Rotational Inertia & High Twist-per-Inch\nSpun between fingers, the calibrated mass (8\u201315 grams) produced sustained angular momentum, twisting individual cotton fibers into strong micro-filaments without snapping under gravitational tension.\n\n## Stratified Artifact Records\nArchaeological excavations across Kodumanal, Uraiyur, and Mangudi have recovered hundreds of disc-shaped terracotta whorls bearing grooved rims and maker marks.",
        "chunks": [
            {
                "language": "en",
                "title": "Terracotta Drop-Spindle Dynamics & Ultra-Fine Yarn Spinning",
                "content": "Calibrated terracotta spindle whorls provided sustained gyroscopic rotational inertia to spin high-count fine cotton yarns without tensile failure."
            },
            {
                "language": "ta",
                "title": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bb3\u0bbf \u0b9a\u0bc1\u0bb4\u0bb2\u0bcd\u0bb5\u0bc7\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0ba8\u0bc2\u0bb2\u0bcd \u0ba8\u0bc2\u0bb1\u0bcd\u0bb1\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0bb2\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0b9a\u0bbf \u0b86\u0bb1\u0bcd\u0bb1\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0bae\u0bbf\u0b95 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0ba8\u0bc2\u0bb2\u0bcd \u0b87\u0bb4\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc7\u0bb1\u0bcd\u0bb1\u0bbf \u0ba8\u0bc2\u0bb1\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai.md",
        "slug": "concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai",
        "category": "concept",
        "name_en": "Featherlight Muslin Weaving & Translucent Vapor Cloth (Aaviyanna-Aadai & Sirasupattu)",
        "name_ta": "\u0baa\u0bc1\u0b95\u0bc8\u0baf\u0ba9\u0bcd\u0ba9 \u0b86\u0bb5\u0bbf\u0baf\u0ba9\u0bcd\u0ba9 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0b86\u0b9f\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb1\u0bc1\u0baa\u0bc2\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1",
        "era": "Sangam Era to Early Medieval",
        "year_start": -300,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Gossamer pit-loom plain-weave cotton fabrics celebrated as Aaviyanna-Aadai (cloth resembling rising steam) and exported as Argaritic muslins to the Roman Empire.",
        "summary_ta": "\u0b8e\u0bb4\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0bbf \u0baa\u0bcb\u0ba9\u0bcd\u0bb1\u0bc1\u0bae\u0bcd, \u0bae\u0bc6\u0bb2\u0bcd\u0bb2\u0bbf\u0baf \u0baa\u0bc1\u0b95\u0bc8 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b86\u0b9f\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Periplus of the Erythraean Sea",
            "Sangam Anthologies",
            "Ancient Indian Commerce"
        ],
        "content": "# Featherlight Muslin Weaving & Translucent Vapor Cloth (Aaviyanna-Aadai & Sirasupattu)\n\n## The Art of Diaphanous Weaving\nAncient Tamil pit-loom weavers achieved global renown for producing plain-weave cotton muslins of such extreme fineness that they were poetically designated *Aaviyanna-Aadai* (woven steam) and *Pugai-yanna-Thukil* (woven smoke).\n\n## Microclimate Control in Pit Looms\nWeaving ultra-fine counts (120\u2013150s) required humid underground pits (*Kuzhi-Thari*) to maintain fiber pliability, preventing brittle yarn snaps during shedding and weft beating with polished horn shuttles.\n\n## Greco-Roman Acclaim (*Argaritic Muslins*)\nThe *Periplus of the Erythraean Sea* singled out these fabrics under the name *Argari*, establishing that Uraiyur exported the finest sheer muslins in antiquity.",
        "chunks": [
            {
                "language": "en",
                "title": "Featherlight Muslin Pit-Loom Weaving & Argaritic Exports",
                "content": "Mastery of gossamer plain-weave cotton fabrics woven in humid pit-looms, exported to Roman patricians as Argaritic muslins."
            },
            {
                "language": "ta",
                "title": "\u0b86\u0bb5\u0bbf\u0baf\u0ba9\u0bcd\u0ba9 \u0baa\u0bc1\u0b95\u0bc8 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0b86\u0b9f\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bc8",
                "content": "\u0b95\u0bc1\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bb1\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0bae\u0bbe\u0ba9 \u0b9a\u0bc2\u0bb4\u0bb2\u0bbf\u0bb2\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bcb\u0bae\u0baa\u0bcd \u0baa\u0bc7\u0bb0\u0bb0\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b8f\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0ba4\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bbf\u0ba9\u0bcd \u0bae\u0bc7\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0ba9 \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b86\u0b9f\u0bc8\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-natural-mordant-fixation-and-selvage-tapestry-borders.md",
        "slug": "concept-natural-mordant-fixation-and-selvage-tapestry-borders",
        "category": "concept",
        "name_en": "Natural Alum Mordant Dye Fixation & Woven Selvage Tapestry Borders (Karai-Neithal)",
        "name_ta": "\u0baa\u0b9f\u0bbf\u0b95\u0bbe\u0bb0\u0b9a\u0bcd \u0b9a\u0bbe\u0baf\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc8\u0baf\u0bcb\u0bb0 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Sangam Era (c. 300 BCE \u2013 300 CE)",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Chemical fixation of madder and indigo dyes on cotton using alum and myrobalan tannins, combined with dense supplementary-weft woven selvages.",
        "summary_ta": "\u0baa\u0b9f\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b9a\u0bbe\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf, \u0bb5\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bb0\u0bc8\u0b95\u0bb3\u0bc1\u0b9f\u0ba9\u0bcd \u0b86\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Natural Dye Chemistry in Ancient India",
            "Maduraikkanchi Notes",
            "Textile Technology Studies"
        ],
        "content": "# Natural Alum Mordant Dye Fixation & Woven Selvage Tapestry Borders (Karai-Neithal)\n\n## Chemical Mordant Fixation\nCotton cellulose lacks natural dye affinity. Ancient Tamil dyers employed natural mineral alum (*Padi-karam*) and astringent myrobalan (*Kadukkai*) tannin baths as chemical mordants, binding alizarin from madder roots (*Manjistha*) into color-fast crimson bonds.\n\n## Structural Selvage Borders (*Karai*)\nMuslin borders were reinforced with dense supplementary warps and wefts dyed in contrasting crimson and indigo, creating geometric selvage tapestries that prevented edge curling and tearing.",
        "chunks": [
            {
                "language": "en",
                "title": "Alum Mordant Fixation & Reinforced Selvage Borders",
                "content": "Chemical mordanting with alum and myrobalan tannins anchored vibrant madder dyes, while supplementary-weft selvages provided structural borders."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0b9f\u0bbf\u0b95\u0bbe\u0bb0 \u0b9a\u0bbe\u0baf\u0bae\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0baa\u0b9f\u0bbf\u0b95\u0bbe\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b9a\u0bbe\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbf\u0bb1\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b95\u0bb0\u0bc8\u0baf\u0bcb\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b89\u0bb1\u0bc1\u0ba4\u0bbf\u0baf\u0bbe\u0ba9 \u0bb5\u0bc7\u0bb2\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0b99\u0bcd\u0b95\u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kodumanal-graffiti-spindle-whorl-and-weaver-guild-marks.md",
        "slug": "insc-kodumanal-graffiti-spindle-whorl-and-weaver-guild-marks",
        "category": "inscription",
        "name_en": "Kodumanal Stratified Excavations of Tamil-Brahmi Inscribed Spindle Whorls",
        "name_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bb3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb4\u0bc1 \u0baa\u0bca\u0bb1\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Early Historic Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "marutham",
        "summary_en": "Excavations at Kodumanal yielding hundreds of grooved terracotta spindle-whorls and potsherds inscribed with Tamil-Brahmi personal and guild names.",
        "summary_ta": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b85\u0b95\u0bb4\u0bcd\u0bb5\u0bbe\u0bb0\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0ba3\u0bcd\u0b9f\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bb1\u0bbf \u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Kodumanal Excavation Reports",
            "Tamil Nadu State Archaeology Bulletins"
        ],
        "content": "# Kodumanal Stratified Excavations of Tamil-Brahmi Inscribed Spindle Whorls\n\n## Stratigraphic Discoveries along the Noyyal\nExcavations at Kodumanal uncovered dense residential layers containing hundreds of perforated terracotta spindle whorls, bone shuttles, and clay dyeing vats.\n\n## Tamil-Brahmi Epigraphy on Spinning Tools\nSeveral recovered spindle whorls and associated pottery fragments bear engraved Tamil-Brahmi graffiti denoting spinner names and guild insignias, confirming corporate textile production in early Kongu country.",
        "chunks": [
            {
                "language": "en",
                "title": "Kodumanal Excavation of Inscribed Spindle Whorls",
                "content": "Excavations at Kodumanal revealed extensive textile workshops with Tamil-Brahmi inscribed spindle whorls and bone weaving tools."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bcd \u0b85\u0b95\u0bb4\u0bcd\u0bb5\u0bbe\u0bb0\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bb3\u0bbf \u0b9a\u0bbe\u0ba9\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0b95\u0bca\u0b9f\u0bc1\u0bae\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0b9f\u0bc8\u0ba4\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd-\u0baa\u0bbf\u0bb0\u0bbe\u0bae\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bc1\u0b9f\u0bc1\u0bae\u0ba3\u0bcd \u0ba4\u0b95\u0bcd\u0b95\u0bb3\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0b95 \u0b8e\u0b9a\u0bcd\u0b9a\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0ba4\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0baf\u0bb2\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-uraiyur-aruvai-vanikar-textile-merchant-and-cloth-hall-charters.md",
        "slug": "insc-uraiyur-aruvai-vanikar-textile-merchant-and-cloth-hall-charters",
        "category": "inscription",
        "name_en": "Uraiyur Epigraphic Charters on Aruvai-Vanikar Cloth Merchant Corporations",
        "name_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0ba4\u0bc1\u0ba3\u0bbf\u0b9a\u0bcd\u0b9a\u0ba8\u0bcd\u0ba4\u0bc8 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Sangam to Chola Era",
        "year_start": -200,
        "year_end": 1100,
        "thinai": "marutham",
        "summary_en": "Epigraphic and ceramic records documenting the Aruvai-Vanikar (wholesale cloth merchants) governing textile bazaars and export shipments from Uraiyur.",
        "summary_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0ba4\u0bc1\u0ba3\u0bbf\u0b9a\u0bcd\u0b9a\u0ba8\u0bcd\u0ba4\u0bc8 \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0bbe\u0b95\u0bae\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Epigraphia Carnatica & Indica",
            "Tiruchirappalli Epigraphic Surveys"
        ],
        "content": "# Uraiyur Epigraphic Charters on Aruvai-Vanikar Cloth Merchant Corporations\n\n## Corporate Organization of Cloth Merchants\nInscriptions in the Tiruchirappalli and Thanjavur regions detail the operations of the *Aruvai-Vanikar*, a powerful mercantile corporation dedicated to marketing woven textiles (*Aruvai*).\n\n## Market Regulation & Temple Grants\nThese epigraphs record market endowments, standardization of yarn cubit measurements, and tax exemptions granted to weavers producing royal garments for imperial rituals.",
        "chunks": [
            {
                "language": "en",
                "title": "Uraiyur Aruvai-Vanikar Merchant Guild Epigraphy",
                "content": "Lithic epigraphs document the corporate power of Uraiyur Aruvai-Vanikar cloth merchant guilds managing textile halls and export taxes."
            },
            {
                "language": "ta",
                "title": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bbf\u0bb2\u0bcd \u0b87\u0baf\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0bb5\u0ba3\u0bbf\u0b95\u0bb0\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc1\u0ba3\u0bbf\u0b9a\u0bcd\u0b9a\u0ba8\u0bcd\u0ba4\u0bc8 \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0bbe\u0b95\u0bae\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bbf\u0baf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1 \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-uraiyur-master-muslin-weaver-aruvai-kaikoalar.md",
        "slug": "char-uraiyur-master-muslin-weaver-aruvai-kaikoalar",
        "category": "character",
        "name_en": "Sengannan Kaikoalar: Master Muslin Weaver of Uraiyur Guilds",
        "name_ta": "\u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0ba3\u0bcd\u0ba3\u0ba9\u0bcd \u0b95\u0bc8\u0b95\u0bcb\u0bb3\u0bb0\u0bcd - \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0b86\u0b9f\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd",
        "era": "Sangam Era (c. 100 BCE \u2013 200 CE)",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Hereditary master weaver of Uraiyur famed for dressing 150-count warp beams and weaving translucent royal robes for Early Chola kings.",
        "summary_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bbf\u0bb2\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc1\u0bb1\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc1\u0bb1\u0bc8\u0baf\u0bbe\u0b95 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0baa\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0b86\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0ba8\u0bc6\u0baf\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd.",
        "sources": [
            "Sangam Oral Traditions",
            "Kaveri Basin Guild Genealogies"
        ],
        "content": "# Sengannan Kaikoalar: Master Muslin Weaver of Uraiyur Guilds\n\n## Master Artisan of the Kaveri Delta\nSengannan Kaikoalar represents the master weavers who elevated Uraiyur into the textile capital of ancient southern India. Operating ground pit-looms, he controlled warp tension with tactile precision.\n\n## Patronage & International Commerce\nSengannan supervised guild apprenticeships, producing translucent muslins presented to the Chola royal court and sold to Yavanas at Muziris and Poompuhar.",
        "chunks": [
            {
                "language": "en",
                "title": "Sengannan Kaikoalar Master Muslin Weaver Biography",
                "content": "Master weaver Sengannan Kaikoalar calibrated ground pit-looms in Uraiyur to produce the legendary diaphanous Argaritic muslins."
            },
            {
                "language": "ta",
                "title": "\u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0ba3\u0bcd\u0ba3\u0ba9\u0bcd \u0b95\u0bc8\u0b95\u0bcb\u0bb3\u0bb0\u0bcd \u0bb5\u0bbe\u0bb4\u0bcd\u0b95\u0bcd\u0b95\u0bc8",
                "content": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b95\u0bc1\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bb1\u0bbf\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0baa\u0bc1\u0b95\u0bc8\u0baf\u0ba9\u0bcd\u0ba9 \u0b86\u0b9f\u0bc8\u0b95\u0bb3\u0bc8 \u0ba8\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0b9a\u0bcb\u0bb4 \u0b85\u0bb0\u0b9a\u0bb5\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baf\u0bb5\u0ba9\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-madurai-textile-guild-metrologist-aruvai-kanakkar.md",
        "slug": "char-madurai-textile-guild-metrologist-aruvai-kanakkar",
        "category": "character",
        "name_en": "Vellan Kanakkar: Madurai Textile Market Metrologist & Yarn Assayer",
        "name_ta": "\u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0ba9\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bb0\u0bcd - \u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0b85\u0b99\u0bcd\u0b95\u0bbe\u0b9f\u0bbf \u0ba8\u0bc2\u0bb2\u0bcd \u0ba4\u0bb0\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bbe\u0bb3\u0bb0\u0bcd",
        "era": "Sangam Era (c. 50 BCE \u2013 150 CE)",
        "year_start": -50,
        "year_end": 150,
        "thinai": "marutham",
        "summary_en": "Civic textile officer in Madurai responsible for measuring bolt lengths, verifying warp density, and stamping guild seals on certified export fabrics.",
        "summary_ta": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0b85\u0b99\u0bcd\u0b95\u0bbe\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0ba4\u0bc1\u0ba3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bb0\u0bae\u0bcd, \u0ba8\u0bc0\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc2\u0bb2\u0bcd \u0b85\u0b9f\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bc8 \u0b86\u0baf\u0bcd\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8 \u0baa\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b85\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bbf.",
        "sources": [
            "Maduraikkanchi",
            "Sangam Administrative Studies"
        ],
        "content": "# Vellan Kanakkar: Madurai Textile Market Metrologist & Yarn Assayer\n\n## Civic Inspection in the Textile Bazaars\nVellan Kanakkar oversaw the bustling cloth halls (*Aruvai-Angadi*) of Madurai described in *Maduraikkanchi*. \n\n## Standards & Quality Assurance\nEquipped with standardized bamboo measuring rods (*Kole*), Vellan examined incoming bolts for weave flaws, stamping approved fabrics with the official guild seal prior to international shipment.",
        "chunks": [
            {
                "language": "en",
                "title": "Vellan Kanakkar Textile Market Metrologist Role",
                "content": "Madurai textile officer Vellan Kanakkar inspected thread count and applied certified guild seals to export cotton bolts."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0ba8\u0bc2\u0bb2\u0bcd \u0ba4\u0bb0\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bbe\u0bb3\u0bb0\u0bcd \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0ba9\u0bcd \u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bb0\u0bcd",
                "content": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0b99\u0bcd\u0b95\u0bbe\u0b9f\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0ba4\u0bc1\u0ba3\u0bbf\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bb0\u0ba4\u0bcd\u0ba4\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b85\u0b9f\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0ba3\u0bbf\u0b95 \u0bae\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0bb0\u0bc8 \u0baa\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4 \u0b85\u0bb0\u0b9a\u0bc1 \u0b85\u0ba4\u0bbf\u0b95\u0bbe\u0bb0\u0bbf."
            }
        ]
    },
    {
        "file": "knowledge/places/place-uraiyur-ancient-cotton-muslin-and-textile-guild-haven.md",
        "slug": "place-uraiyur-ancient-cotton-muslin-and-textile-guild-haven",
        "category": "place",
        "name_en": "Uraiyur: Ancient Chola Textile Capital & Gossamer Muslin Haven",
        "name_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd - \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0b86\u0b9f\u0bc8 \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Early Chola inland capital along the Kaveri celebrated as Argaru by the Periplus, famed worldwide as the primary production center of diaphanous muslins.",
        "summary_ta": "\u0b95\u0bbf\u0bb0\u0bc7\u0b95\u0bcd\u0b95-\u0b89\u0bb0\u0bcb\u0bae \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0bb0\u0bcd\u0b95\u0bbe\u0bb0\u0bc1 \u0b8e\u0ba9\u0baa\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bbe\u0ba9 \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd.",
        "sources": [
            "Periplus of the Erythraean Sea",
            "Ptolemy Geography",
            "ASI Excavations at Uraiyur"
        ],
        "content": "# Uraiyur: Ancient Chola Textile Capital & Gossamer Muslin Haven\n\n## Capital Topography & Microclimate\nLocated on the fertile south bank of the Kaveri River, Uraiyur possessed the ideal humid climate necessary for spinning ultra-fine cotton yarns without breakage.\n\n## The Argaritic Muslin Emporium\nClassical Greco-Roman geographers praised Uraiyur (Argaru) as the premier center for sheer export fabrics, where spinning and weaving guilds flourished under royal Chola patronage.",
        "chunks": [
            {
                "language": "en",
                "title": "Uraiyur Ancient Textile Capital & Argaru Geography",
                "content": "Uraiyur on the Kaveri was the celebrated capital of Early Chola textile production, exporting Argaritic muslins across the Indian Ocean."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bc1",
                "content": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0ba8\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0b86\u0b9f\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bbe\u0b95\u0ba4\u0bcd \u0ba4\u0bbf\u0b95\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4\u0ba4\u0bc1."
            }
        ]
    }
]
EDGES = [
    [
        "char-uraiyur-master-muslin-weaver-aruvai-kaikoalar",
        "located_in",
        "place-uraiyur-ancient-cotton-muslin-and-textile-guild-haven",
        "history",
        "Sangam Era",
        "Operated ground pit-looms in the textile guild quarter of Uraiyur",
        "Archaeological & Literary records"
    ],
    [
        "char-madurai-textile-guild-metrologist-aruvai-kanakkar",
        "participated_in",
        "place-uraiyur-ancient-cotton-muslin-and-textile-guild-haven",
        "commerce",
        "Sangam Era",
        "Inspected and certified incoming muslin bolts from Uraiyur weavers",
        "Maduraikkanchi epigraphs"
    ],
    [
        "concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai",
        "practiced_by",
        "char-uraiyur-master-muslin-weaver-aruvai-kaikoalar",
        "craft",
        "Sangam Era",
        "Mastered weaving diaphanous 150-count cotton muslins",
        "Purananuru & Periplus"
    ],
    [
        "concept-bow-string-vibrating-cotton-carding-villadithal-panchu",
        "influenced",
        "concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai",
        "technology",
        "Sangam Era",
        "Acoustic bow-string carding provided flawless knot-free cotton lint",
        "Sangam textile corpus"
    ],
    [
        "concept-terracotta-spindle-whorl-rotational-inertia-and-fine-yarn-spinning",
        "influenced",
        "concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai",
        "technology",
        "Sangam Era",
        "Calibrated drop-spindle whorls enabled uniform high-twist fine yarn spinning",
        "Kodumanal excavations"
    ],
    [
        "concept-natural-mordant-fixation-and-selvage-tapestry-borders",
        "related_to",
        "concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai",
        "craft",
        "Sangam Era",
        "Alum and tannin mordants anchored decorative colored borders on fine cloth",
        "Textile chemistry analysis"
    ],
    [
        "text-perumpanarruppadai-fine-muslin-weaving-and-serpent-slough-poetry",
        "references",
        "concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai",
        "literature",
        "Sangam Era",
        "Celebrated translucent vapor garments and serpent-skin cloths",
        "Perumpanarruppadai lines 468-471"
    ],
    [
        "insc-kodumanal-graffiti-spindle-whorl-and-weaver-guild-marks",
        "evidenced_by",
        "concept-terracotta-spindle-whorl-rotational-inertia-and-fine-yarn-spinning",
        "archaeology",
        "Early Historic",
        "Excavations yielded hundreds of inscribed terracotta spindle whorls",
        "Kodumanal Excavation Reports"
    ],
    [
        "insc-uraiyur-aruvai-vanikar-textile-merchant-and-cloth-hall-charters",
        "evidenced_by",
        "place-uraiyur-ancient-cotton-muslin-and-textile-guild-haven",
        "epigraphy",
        "Sangam to Chola",
        "Charters of cloth merchants operating dedicated textile halls in Uraiyur",
        "Tiruchirappalli Epigraphs"
    ],
    [
        "place-uraiyur-ancient-cotton-muslin-and-textile-guild-haven",
        "center_of",
        "concept-featherlight-muslin-weaving-vapor-cloth-aaviyanna-aadai",
        "geography",
        "Sangam Era",
        "Primary manufacturing and trading emporium for export-quality muslins",
        "Periplus of the Erythraean Sea"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 26 Corpus 1: Cotton Ginning, Bow-String Carding & Muslin Spindles into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 26 Corpus 1: Cotton Ginning, Bow-String Carding & Muslin Spindles Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
