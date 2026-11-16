#!/usr/bin/env python3
# Ingestion harvester for Batch 25 Corpus 1: Herbal Pharmacology & Thailam Extraction
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
        "file": "knowledge/texts/text-agasthiyar-gunavagadam-pharmacology-and-thailam-poetry.md",
        "slug": "text-agasthiyar-gunavagadam-pharmacology-and-thailam-poetry",
        "category": "text",
        "name_en": "Agasthiyar Gunavagadam Verses on Siddha Pharmacology, Medicated Thailam & Decoction Protocols",
        "name_ta": "\u0b85\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bc1\u0ba3\u0bb5\u0bbe\u0b95\u0b9f\u0bae\u0bcd - \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bbf\u0baf\u0bb2\u0bcd, \u0ba4\u0bc8\u0bb2 \u0bae\u0bc1\u0bb1\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Classical to Early Medieval Era",
        "year_start": -100,
        "year_end": 700,
        "thinai": "kurinji",
        "summary_en": "Agasthiyar Gunavagadam and Theraiyar Yamaga Venba treatises detailing indigenous Siddha pharmacological principles: classification of 4448 human ailments, therapeutic extraction of medicated herbal oils (Thailam), and reduction of raw plant decoctions (Kashayam).",
        "summary_ta": "\u0b85\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bc1\u0ba3\u0bb5\u0bbe\u0b95\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0bb0\u0bc8\u0baf\u0bb0\u0bcd \u0ba8\u0bc2\u0bb2\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd 4448 \u0ba8\u0bcb\u0baf\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0b85\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0b9f\u0bc8\u0b95\u0bb3\u0bcd, \u0ba4\u0bc8\u0bb2\u0baa\u0bcd \u0baa\u0bbe\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0bb5\u0bb1\u0bcd\u0bb1\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Agasthiyar Gunavagadam Thailam Section",
            "Theraiyar Yamaga Venba",
            "Traditional Siddha Pharmacopoeia of Tamil Nadu"
        ],
        "content": "# Agasthiyar Gunavagadam Verses on Siddha Pharmacology, Medicated Thailam & Decoction Protocols\n\n## The Foundation of Dravidian Medicine\nSiddha medicine (*Siddha Maruthuvam*), deeply rooted in ancient Tamil culture and canonized in treatises attributed to Sage Agasthiyar and Theraiyar, operates upon the tridosha doctrine (*Mukkuttram*\u2014Vatham, Pitham, Kapham). Therapeutic healing aimed to restore bio-energetic equilibrium using botanical, mineral, and marine pharmaceuticals.\n\n```\n\"\u0b95\u0bbe\u0baf \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0bbf \u0ba4\u0bb0\u0bc1\u0bae\u0bcd \u0b95\u0ba9\u0b95 \u0ba4\u0bc8\u0bb2\u0bae\u0ba4\u0bc1\n\u0b86\u0baf \u0b95\u0bb2\u0bc8 \u0bb5\u0bb2\u0bcd\u0bb2\u0bcb\u0bb0\u0bcd \u0b85\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bbf\u0b9f\u0bc1\u0bb5\u0bbe\u0bb0\u0bcd \u2014 \u0ba4\u0bc2\u0baf\n\u0b85\u0ba4\u0bbf\u0bae\u0ba4\u0bc1\u0bb0\u0bae\u0bcd \u0b9a\u0ba8\u0bcd\u0ba4\u0ba9\u0bae\u0bcd \u0b86\u0b9f\u0bbe\u0ba4\u0bcb\u0b9f\u0bc8 \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bbf\n\u0baa\u0ba4\u0bae\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8...\"\n\u2014 \u0b85\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bc1\u0ba3\u0bb5\u0bbe\u0b95\u0b9f\u0bae\u0bcd \u0ba4\u0bc8\u0bb2\u0baa\u0bcd \u0baa\u0b9f\u0bb2\u0bae\u0bcd\n```\n\n## Pharmaceutical Phases of Thailam Extraction (*Pakam*)\nThe preparation of medicated external and internal oils (*Thailam*) followed strict thermal and viscosity stages:\n1. **Dravam (Liquid Base)**: Freshly pressed cold virgin sesame oil (*Nallennai*) or cow's milk enriched with herbal decoctions.\n2. **Kalkam (Paste)**: Finely ground therapeutic roots, barks, and seeds.\n3. **Paka Nilai (Critical Viscosity Endpoints)**:\n   - *Manal Pakam* (Sand Stage): Paste turns sandy; optimal for nasal drops (*Nasiyam*).\n   - *Mezhugu Pakam* (Wax Stage): Paste rolls smoothly like soft wax between fingers; ideal for ear drops and internal ingestion.\n   - *Kadugu Pakam* (Mustard Stage): Dark, aromatic cracking point; utilized for vigorous external neuromuscular rubs.\n\n## Trauma Surgery & Battlefield Hemostasis\nEarly Tamil surgeons (*Rana-Vaidhiyar*) carried portable wooden apothecary chests (*Maruthuva Petti*) containing cauterizing oils, styptic powders derived from *Kadal-Nurai* (cuttlefish bone), and astringent bark pastes to staunch arterial bleeding in battle.",
        "chunks": [
            {
                "language": "en",
                "title": "Agasthiyar Gunavagadam Pharmacology & Thailam Extraction Stages",
                "content": "Agasthiyar Gunavagadam verses systematize Siddha pharmacology, documenting precise thermal endpoints (Paka Nilai) for boiling sesame oil decoctions into therapeutic Thailam oils for internal and external healing."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bc1\u0ba3\u0bb5\u0bbe\u0b95\u0b9f \u0ba4\u0bc8\u0bb2\u0baa\u0bcd \u0baa\u0bbe\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bbf\u0baf\u0bb2\u0bcd \u0ba8\u0bc6\u0bb1\u0bbf\u0b95\u0bb3\u0bc1\u0bae\u0bcd",
                "content": "\u0b85\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bc1\u0ba3\u0bb5\u0bbe\u0b95\u0b9f\u0bae\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0ba3\u0bb2\u0bcd \u0baa\u0bbe\u0b95\u0bae\u0bcd, \u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0baa\u0bbe\u0b95\u0bae\u0bcd, \u0b95\u0b9f\u0bc1\u0b95\u0bc1 \u0baa\u0bbe\u0b95\u0bae\u0bcd \u0b86\u0b95\u0bbf\u0baf \u0ba4\u0bc8\u0bb2\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bbe\u0ba9 \u0bb5\u0bc6\u0baa\u0bcd\u0baa \u0b85\u0bb3\u0bb5\u0bc0\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc6\u0bb1\u0bbf\u0b95\u0bb3\u0bbe\u0b95\u0bc1\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-herbal-decoction-reduction-and-sesame-oil-thailam-extraction.md",
        "slug": "concept-herbal-decoction-reduction-and-sesame-oil-thailam-extraction",
        "category": "concept",
        "name_en": "Herbal Decoction Reduction & Sesame Oil Thailam Extraction Chemistry",
        "name_ta": "\u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bcd \u0b95\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bb2\u0bcd\u0bb2\u0bc6\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0ba4\u0bc8\u0bb2\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Early Historic to Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "kurinji",
        "summary_en": "Biochemical extraction technology transferring fat-soluble and water-soluble phytoconstituents into cold-pressed sesame oil (Sesamum indicum / Nallennai) through slow simmering of four-fold reduced aqueous bark and root decoctions.",
        "summary_ta": "\u0ba8\u0bbe\u0ba9\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b92\u0ba9\u0bcd\u0bb1\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bc8\u0baf\u0bc1\u0bae\u0bcd (\u0b95\u0bb7\u0bbe\u0baf\u0bae\u0bcd) \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0bb5\u0bbf\u0bb4\u0bc1\u0ba4\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba8\u0bb2\u0bcd\u0bb2\u0bc6\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bbf\u0bb2\u0bcd \u0b87\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc6\u0bb2\u0bcd\u0bb2\u0bbf\u0baf \u0ba4\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf, \u0b95\u0bca\u0bb4\u0bc1\u0baa\u0bcd\u0baa\u0bc1-\u0ba8\u0bc0\u0bb0\u0bcd\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Theraiyar Thaila Varkka Churukkam",
            "Charaka Samhita Chikitsa Sthana",
            "Biochemical Evaluation of Classical Siddha Medicated Oils"
        ],
        "content": "# Herbal Decoction Reduction & Sesame Oil Thailam Extraction Chemistry\n\n## Thermodynamics of Triple-Phase Lipid Infusion\nThe synthesis of medicated oil (*Thailam*) is an advanced thermodynamic extraction designed to transfer diverse chemical compounds\u2014lipophilic alkaloids, hydrophilic glycosides, and volatile essential oils\u2014into a stable lipid carrier:\n\n$$\\text{Plant Tissues} + \\text{Water} \\xrightarrow{\\text{Boil to } \\frac{1}{4}} \\text{Kashayam} \\xrightarrow{+ \\text{Kalkam} + \\text{Sesame Oil}} \\text{Evaporate } H_2O \\rightarrow \\text{Medicated Oil}$$\n\n## Role of Sesame Oil (*Nallennai*) as Bio-Enhancer\nSesame oil was revered as the supreme medicinal vehicle (*Taila* derives from *Tila* / sesame):\n- **High Penetration Depth**: Low molecular weight triglycerides rich in linoleic and oleic acids penetrate deep transdermal and mucosal barriers.\n- **Natural Antioxidants**: Endogenous lignans (sesamin, sesamol, and sesamolin) resist rancidity, ensuring long shelf-life without chemical preservatives.\n\n## Boiling Sequence & Emulsion Breakdown\nThe mixture of Kashayam (water extract), Kalkam (herbal paste), and sesame oil forms an emulsion. Heated over low charcoal embers (*Mandhagni*), the water gradually vaporizes. As the last trace of water boils off, the herbal paste crisps into spherical beads, signaling that all active botanical constituents have been transferred into the lipid phase without scorching the oil.",
        "chunks": [
            {
                "language": "en",
                "title": "Sesame Oil Thailam Triple-Phase Phytochemical Extraction",
                "content": "Siddha Thailam extraction utilizes reduced aqueous plant decoctions and sesame oil carriers, evaporating water under mild embers to infuse lipophilic and hydrophilic phytochemicals into stable, preservative-free oils."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bb2\u0bcd\u0bb2\u0bc6\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0ba4\u0bc8\u0bb2\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb4\u0bc1\u0ba4\u0bc1\u0bae\u0bcd \u0ba8\u0bb2\u0bcd\u0bb2\u0bc6\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bc1\u0b9f\u0ba9\u0bcd \u0bae\u0bc6\u0bb2\u0bcd\u0bb2\u0bbf\u0baf \u0ba4\u0ba3\u0bb2\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0ba8\u0bc0\u0bb0\u0bcd \u0bae\u0bc1\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0bbf\u0baf\u0bbe\u0ba9 \u0baa\u0bbf\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0b95\u0bb3\u0bcd \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b89\u0baf\u0bb0\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-subterranean-herbal-steam-inhalation-and-sweat-therapy-viyarpani.md",
        "slug": "concept-subterranean-herbal-steam-inhalation-and-sweat-therapy-viyarpani",
        "category": "concept",
        "name_en": "Subterranean Herbal Steam Inhalation & Sweat Therapy Mechanics (Viyarpani)",
        "name_ta": "\u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0b86\u0bb5\u0bbf \u0baa\u0bbf\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0baf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0ba3\u0bbf \u0bb5\u0bbf\u0baf\u0bb0\u0bcd\u0bb5\u0bc8 \u0b9a\u0bbf\u0b95\u0bbf\u0b9a\u0bcd\u0b9a\u0bc8",
        "era": "Early Historic Sangam Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Thermal sudation and detoxifying steam therapy (*Viyarpani* / *Vedhu*) using subterranean brick sweat-chambers heated with hot river boulders and drenched with boiling decoctions of Vitex negundo (Nochi) and Eucalyptus leaves.",
        "summary_ta": "\u0b9a\u0bc2\u0b9f\u0bc7\u0bb1\u0bcd\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0b89\u0bb0\u0bc1\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0ba8\u0bca\u0b9a\u0bcd\u0b9a\u0bbf, \u0baf\u0bc2\u0b95\u0bb2\u0bbf\u0baa\u0bcd\u0b9f\u0bb8\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bbf\u0ba8\u0bc0\u0bb0\u0bc8 \u0b8a\u0bb1\u0bcd\u0bb1\u0bbf \u0b8e\u0bb4\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3 \u0ba8\u0bc0\u0bb0\u0bbe\u0bb5\u0bbf\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0ba8\u0bcb\u0baf\u0bbe\u0bb3\u0bbf\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0baf\u0bb0\u0bcd\u0b95\u0bcd\u0b95 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0b9a\u0bcd\u0b9a\u0bc1\u0b95\u0bb3\u0bc8 \u0bb5\u0bc6\u0bb3\u0bbf\u0baf\u0bc7\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0baf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0ba3\u0bbf \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Agasthiyar Vaidya Rathina Churukkam",
            "Malaipadukadam lines 300-315",
            "Journal of Traditional Thermal Therapies in South India"
        ],
        "content": "# Subterranean Herbal Steam Inhalation & Sweat Therapy Mechanics (Viyarpani)\n\n## Classical Dravidian Sudation Therapy (*Vedhu / Viyarpani*)\nIn the monsoon-chilled tracts of Kurinji and Mullai, ancient Tamil healers developed *Viyarpani* (\u0bb5\u0bbf\u0baf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0ba3\u0bbf)\u2014induced diaphoretic therapy\u2014to treat chronic rheumatic paralysis (*Vatha noi*), respiratory fevers, and deep tissue stiffness.\n\n## Chamber Architecture & Steam Dynamics\n1. **Sudation Pit (*Vedhu Kottam*)**: A sunken brick-lined pit constructed beneath ground level to retain radiant heat.\n2. **Thermal Granite Mass (*Chudu-Kallu*)**: Dense granite river boulders heated red-hot in adjacent hardwood hearths were placed inside the central pit.\n3. **Herbal Drenching (*Kashaya-Thelippu*)**: Attendants poured steaming infusions of *Nochi* (*Vitex negundo*), *Adathodai* (*Justicia adhatoda*), and camphor leaves over the glowing stones.\n4. **Vapor Absorption**: The room filled instantaneously with supersaturated volatile terpene vapors. The patient, swaddled in rough woven wool or beaten bark-cloth, inhaled the medicated steam while transdermal pores dilated, triggering copious sweating that eliminated metabolic toxins.",
        "chunks": [
            {
                "language": "en",
                "title": "Subterranean Herbal Sudation Pits & Nochi Steam Therapy",
                "content": "Ancient Tamil healers practiced Viyarpani sudation by drenching red-hot river stones with Vitex negundo (Nochi) decoctions in subterranean brick chambers to treat respiratory ailments and neuromuscular stiffness."
            },
            {
                "language": "ta",
                "title": "\u0ba8\u0bbf\u0bb2\u0bb5\u0bb1\u0bc8 \u0bb5\u0bbf\u0baf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0ba3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bca\u0b9a\u0bcd\u0b9a\u0bbf \u0b86\u0bb5\u0bbf \u0b9a\u0bbf\u0b95\u0bbf\u0b9a\u0bcd\u0b9a\u0bc8",
                "content": "\u0b9a\u0bc2\u0b9f\u0bbe\u0ba9 \u0b86\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0ba8\u0bca\u0b9a\u0bcd\u0b9a\u0bbf, \u0b86\u0b9f\u0bbe\u0ba4\u0bcb\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb7\u0bbe\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b8a\u0bb1\u0bcd\u0bb1\u0bbf \u0b8e\u0bb4\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0ba8\u0bc0\u0bb0\u0bbe\u0bb5\u0bbf\u0baf\u0bbe\u0bb2\u0bcd \u0ba8\u0bcb\u0baf\u0bbe\u0bb3\u0bbf\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0baf\u0bb0\u0bcd\u0b95\u0bcd\u0b95 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bbe\u0ba4 \u0ba8\u0bcb\u0baf\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0ba3\u0bae\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bb5\u0bbf\u0baf\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0ba3\u0bbf \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-calcined-metal-ash-bhasma-and-herbal-marmam-poultices.md",
        "slug": "concept-calcined-metal-ash-bhasma-and-herbal-marmam-poultices",
        "category": "concept",
        "name_en": "Calcined Metal Ash (Bhasma / Parpam) & Herbal Marmam Poultices",
        "name_ta": "\u0baa\u0bc1\u0b9f\u0bae\u0bbf\u0b9f\u0bcd\u0b9f \u0b89\u0bb2\u0bcb\u0b95 \u0baa\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bcd\u0bae \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Early Historic to Medieval Era",
        "year_start": -200,
        "year_end": 500,
        "thinai": "kurinji",
        "summary_en": "Alchemical incineration (*Pudam*) of metals and minerals (iron, mica, conch shell) inside cow-dung clamp kilns to synthesize biocompatible sub-micron ashes (*Parpam* / *Chendooram*), blended with herbal leaf poultices to treat lethal trauma to vital Marma points.",
        "summary_ta": "\u0b87\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1, \u0ba4\u0bbe\u0bb3\u0b95\u0bae\u0bcd, \u0b9a\u0b99\u0bcd\u0b95\u0bc1 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1\u0bb5\u0bb1\u0bcd\u0bb1\u0bc8 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b9a\u0bcd \u0b9a\u0bbe\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0b85\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bc1\u0b9f\u0bae\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0bb1\u0bcd\u0baa-\u0b9a\u0bc6\u0ba8\u0bcd\u0ba4\u0bc2\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc1\u0bae\u0bcd, \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0bb5\u0bb0\u0bcd\u0bae\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bc1\u0bae\u0bcd.",
        "sources": [
            "Agasthiyar Muppu 50",
            "Bogar 7000 Saptakanda Treatises",
            "Siddha Alchemy & Mineral Pharmacology Studies"
        ],
        "content": "# Calcined Metal Ash (Bhasma / Parpam) & Herbal Marmam Poultices\n\n## The Alchemy of Nanoscale Biomineral Parpam\nLong before modern nanomedicine, Siddha alchemists (*Rasa-Vaithiyar*) transformed toxic elemental metals and minerals into non-toxic, cellularly assimilable medicinal ashes known as *Parpam* (white ashes) and *Chendooram* (ruby-red oxides).\n\n## The Calcination Sequence (*Puda-Vidhi*)\n1. **Shodhana (Purification)**: Heating metals red-hot and quenching them repeatedly in herbal juices (e.g., *Kattralai* / Aloe vera, *Sirukeerai* juice) to disrupt metal crystal bonds.\n2. **Kalkam Grinding**: Grinding the purified metal with herbal decoctions in granite pestle mortars (*Kalvam*) for hundreds of hours until the metallic luster vanished entirely.\n3. **Pudam Kiln Firing**: Sealing the dried medicinal cakes inside interlocking terracotta crucibles (*Agal*) luted with clay-smeared cloth. The sealed capsules were buried under 50 to 500 dried cow-dung cakes (*Varatti*) and fired, achieving thermal incineration at $600^\\circ\\text{C} - 800^\\circ\\text{C}$.\n\n## Marmam Vital Point Trauma Poultices\nIn martial arts (*Kalari* and *Varma Kalai*), warriors struck in vital neuro-vascular junctions (*Marma points*) were treated with warm poultices (*Kattu-Pattru*) blending *Pavazha Parpam* (coral ash), *Arakku* (lac), and crushed *Murungai* bark to arrest internal hemorrhaging and reset displaced joints.",
        "chunks": [
            {
                "language": "en",
                "title": "Siddha Pudam Metal Calcination & Marma Trauma Poultices",
                "content": "Siddha alchemists synthesized biocompatible mineral ashes (Parpam) through cyclic cow-dung clamp calcination (Pudam), combining them with botanical leaf poultices to treat traumatic strikes to vital Marma points."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc1\u0b9f\u0bae\u0bbf\u0b9f\u0bcd\u0b9f \u0baa\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bcd\u0bae \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bc1",
                "content": "\u0b89\u0bb2\u0bcb\u0b95\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b9a\u0bcd \u0b9a\u0bbe\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0b85\u0bb0\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0b95\u0bb2\u0bcd \u0baa\u0bc1\u0b9f\u0bae\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0baa\u0bb1\u0bcd\u0baa-\u0b9a\u0bc6\u0ba8\u0bcd\u0ba4\u0bc2\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0bb5\u0bb0\u0bcd\u0bae \u0b85\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0b86\u0bb1\u0bcd\u0bb1\u0bbf \u0b89\u0baf\u0bbf\u0bb0\u0bcd\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0baf\u0bb0\u0bcd \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1\u0b95\u0bb3\u0bbe\u0b95\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-botanical-confections-lehiyam-and-palm-jaggery-preservatives.md",
        "slug": "concept-botanical-confections-lehiyam-and-palm-jaggery-preservatives",
        "category": "concept",
        "name_en": "Botanical Confections (Lehiyam) & Palm Jaggery Preservative Matrices",
        "name_ta": "\u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0bb2\u0bc7\u0b95\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0ba9\u0b99\u0bcd\u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Sangam to Medieval Era",
        "year_start": -100,
        "year_end": 600,
        "thinai": "mullai",
        "summary_en": "Pharmaceutics of shelf-stable medicinal jams and confections (*Lehiyam* / *Ilakam*) prepared by reducing botanical extracts in clarified butter (Ney) and high-density palmyra jaggery syrup, creating high osmotic pressure barriers against fungal spoilage.",
        "summary_ta": "\u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0baa\u0ba9\u0b99\u0bcd\u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0b95\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc2\u0baf \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bbf\u0bb3\u0bb1\u0bbf, \u0b85\u0ba4\u0bbf\u0b95 \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0b85\u0b9f\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bc2\u0b9e\u0bcd\u0b9a\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0b95\u0bcd\u0b9f\u0bc0\u0bb0\u0bbf\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bc0\u0ba3\u0bcd\u0b9f \u0b95\u0bbe\u0bb2\u0bae\u0bcd \u0b95\u0bc6\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb2\u0bc7\u0b95\u0bbf\u0baf \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Agasthiyar Paripooranam 400",
            "Pathitrupathu 42",
            "Traditional Phytotherapy & Food-Medicine in Tamil Heritage"
        ],
        "content": "# Botanical Confections (Lehiyam) & Palm Jaggery Preservative Matrices\n\n## The Confectionary Pharmacology of Lehiyam\nTo ensure palatable ingestion of bitter roots and volatile spices by royal courtiers, pregnant women, and convalescents, ancient Tamil pharmacologists compounded semi-solid medicinal pastes termed *Lehiyam* (\u0bb2\u0bc7\u0b95\u0bbf\u0baf\u0bae\u0bcd) or *Ilakam*.\n\n## Pharmaceutical Compounding Protocol\n1. **Sugar Base (*Pagu-Nilai*)**: Palmyra jaggery (*Karupatti*) or pure honeycomb was boiled in water until it achieved the \"one-string\" consistency (*Oru-Izhai Paagu*).\n2. **Choornam Incorporation**: Superfine powders of dry ginger (*Chukku*), black pepper (*Milagu*), long pepper (*Thippili*), and ashwagandha (*Amukkuram*) were sifted into the boiling syrup.\n3. **Clarified Butter & Honey Seal**: Pure cow's ghee (*Pasum-Ney*) was folded into the simmering confection, followed by raw honey added after cooling below $40^\\circ\\text{C}$.\n\n## Osmotic Preservation Dynamics\n$$\\text{High Solute Concentration (Sucrose + Invert Sugars)} \\rightarrow \\text{High Osmotic Pressure} \\rightarrow \\text{Microbial Desiccation}$$\nThe high osmotic concentration bound all available free water ($a_w < 0.60$), rendering the confection naturally bacteriostatic and fungistatic for years inside glazed ceramic jars without artificial chemicals.",
        "chunks": [
            {
                "language": "en",
                "title": "Siddha Lehiyam Confections & High-Osmotic Jaggery Preservation",
                "content": "Tamil physicians formulated shelf-stable Lehiyam confections by folding pulverized herbs into boiled palmyra jaggery and ghee, utilizing high osmotic pressure to inhibit microbial growth for years."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0ba9\u0b99\u0bcd\u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf \u0bb2\u0bc7\u0b95\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0b95\u0bbf\u0baf\u0bb2\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0baa\u0bcd\u0baa\u0bc1\u0bae\u0bcd",
                "content": "\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bc1, \u0bae\u0bbf\u0bb3\u0b95\u0bc1 \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0b9f\u0bbf\u0b95\u0bb3\u0bc8 \u0baa\u0ba9\u0b99\u0bcd\u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0b95\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0bbf\u0bb2\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb0\u0b9f\u0bcd\u0b9f\u0bbf, \u0ba8\u0bc0\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b89\u0baf\u0bb0\u0bcd \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0ba4\u0bcd\u0ba4\u0bbe\u0bb2\u0bcd \u0baa\u0bb2\u0bcd\u0bb2\u0bbe\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0b95\u0bc6\u0b9f\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb2\u0bc7\u0b95\u0bbf\u0baf\u0ba4\u0bcd \u0ba4\u0baf\u0bbe\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kollimalai-siddha-herbal-sanctuary-and-medicinal-flora-charters.md",
        "slug": "insc-kollimalai-siddha-herbal-sanctuary-and-medicinal-flora-charters",
        "category": "inscription",
        "name_en": "Kollimalai Siddha Herbal Sanctuary & Medicinal Flora Charters",
        "name_ta": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8 \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0ba4\u0bcd \u0ba4\u0bbe\u0bb5\u0bb0 \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Sangam to Medieval Era",
        "year_start": -100,
        "year_end": 1100,
        "thinai": "kurinji",
        "summary_en": "Rock inscriptions from Arapaleeswarar temple and cavern shelters in the Kollimalai mountain range recording royal protection of rare botanical habitats (*Marunthu-Malai*), hermit physician endowments, and tax exemptions for herbal gatherers.",
        "summary_ta": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8 \u0b85\u0bb1\u0baa\u0bcd\u0baa\u0bb3\u0bc0\u0bb8\u0bcd\u0bb5\u0bb0\u0bb0\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b85\u0bb0\u0bbf\u0baf \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0bb5\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd, \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bcd \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0bbf \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0b9a\u0bc7\u0b95\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0bb1\u0bcd\u0b95\u0bc1 \u0bb5\u0bb0\u0bbf\u0bb5\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4\u0ba4\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b9a\u0bc6\u0baf\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9.",
        "sources": [
            "South Indian Inscriptions Vol. XXII",
            "Annual Report on Indian Epigraphy 1929 No. 142",
            "Ethnobotany & Epigraphy of the Kolli Hills"
        ],
        "content": "# Kollimalai Siddha Herbal Sanctuary & Medicinal Flora Charters\n\n## Mountain Sanctuary of Valvil Ori\nKollimalai ($11.2500^\\circ\\text{ N}, 78.3500^\\circ\\text{ E}$), a prominent mass of the Eastern Ghats in Namakkal district, was ruled in the Sangam era by the generous chieftain Valvil Ori. Celebrated in *Sirupanarruppadai* and *Purananuru*, its mist-draped granite cliffs nurtured the richest biodiversity of endemic medicinal plants in Tamilakam.\n\n## Inscriptional Evidence of Botanical Protection\nEpigraphs carved on boulders near the Arapaleeswarar sanctuary and Selur caverns record:\n- **Sanctuary Immunity (*Marunthu-Kani*)**: Royal decrees designating montane valleys as protected herbal repositories where tree felling, forest burning, and commercial charcoal making were capital crimes.\n- **Gathering Rights (*Thazhai-Kattanam Exemption*)**: Indigenous Malayali tribes and itinerant Siddha ascetics were granted untaxed access to gather medicinal barks, mycorrhizal tubers (*Boomechakkarak-kizhangu*), and therapeutic orchids.\n- **Endowments for Mountain Dispensaries**: Land grants funding stone hospice pavilions where traveling ascetics boiled seasonal Thailam preparations for free distribution to pilgrims.",
        "chunks": [
            {
                "language": "en",
                "title": "Kollimalai Royal Charters on Medicinal Plant Protection",
                "content": "Inscriptions in the Kolli Hills document ancient royal decrees protecting endemic medicinal valleys (Marunthu-Kani) from deforestation while exempting traditional herbalists from gathering taxes."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0b9a\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bb5\u0bb2\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b93\u0bb0\u0bbf\u0baf\u0bbf\u0ba9\u0bcd \u0bae\u0bb2\u0bc8\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0bb0\u0bbf\u0baf \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0ba4\u0bcd \u0ba4\u0bbe\u0bb5\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0b85\u0bb4\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd, \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0b9a\u0bc7\u0b95\u0bb0\u0bbf\u0b95\u0bcd\u0b95 \u0bae\u0bc1\u0bb4\u0bc1 \u0b89\u0bb0\u0bbf\u0bae\u0bc8 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4\u0ba4\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-maruthuvakkudi-chola-hospital-and-herbal-dispensary-epigraphs.md",
        "slug": "insc-maruthuvakkudi-chola-hospital-and-herbal-dispensary-epigraphs",
        "category": "inscription",
        "name_en": "Maruthuvakkudi Chola Hospital & Herbal Dispensary Epigraphs",
        "name_ta": "\u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0b86\u0ba4\u0bc1\u0bb0\u0b9a\u0bbe\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0b95\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Medieval Chola Era",
        "year_start": 900,
        "year_end": 1150,
        "thinai": "marutham",
        "summary_en": "Famous medical epigraphs from Maruthuvakkudi and Thirumukkoodal detailing imperial Chola hospital wards (*Aathurasalai*), stocks of 20 named medicinal oils and lehiyams, and salaries paid to physicians, surgeons, and apothecary nurses.",
        "summary_ta": "\u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb0\u0bc1\u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0bb2\u0bc2\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0b87\u0bb2\u0bb5\u0b9a \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0ba9\u0bc8\u0b95\u0bb3\u0bcd, \u0b85\u0b99\u0bcd\u0b95\u0bc1 \u0b9a\u0bc7\u0bae\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f 20 \u0bb5\u0b95\u0bc8\u0baf\u0bbe\u0ba9 \u0ba4\u0bc8\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0bb2\u0bc7\u0b95\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bcd, \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0b9a\u0bbf\u0b95\u0bbf\u0b9a\u0bcd\u0b9a\u0bc8 \u0ba8\u0bbf\u0baa\u0bc1\u0ba3\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0bb4\u0b99\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b8a\u0ba4\u0bbf\u0baf \u0bb5\u0bbf\u0bb5\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Epigraphia Indica Vol. XXI (Tirumukkudal Inscription of Virarajendra)",
            "South Indian Inscriptions Vol. VII",
            "K.A. Nilakanta Sastri: The Colas Medical Chapters"
        ],
        "content": "# Maruthuvakkudi Chola Hospital & Herbal Dispensary Epigraphs\n\n## The Institutionalization of Dravidian Healthcare\nDuring the Chola golden age, free hospital complexes (*Aathurasalai* or *Vaidyasala*) were established adjoining major temple universities and urban centers. The epigraphical records from Maruthuvakkudi (near Kumbakonam) and Thirumukkoodal represent the most detailed hospital records from pre-modern Asia.\n\n## Inventories of Pharmacological Stock\nThe inscriptions enumerate precise stocks of prepared Siddha and Ayurvedic remedies maintained under lock in temple dispensaries:\n- **Medicated Oils**: *Bala-Haritaki Thailam*, *Sukha-Sadhana Thailam*, and *Ghee-based infusions* stored in stone jars.\n- **Digestive Electuaries**: *Dasamoola Haritaki Lehiyam* and *Bilvadi Lehiyam* for treating dysentery and fever.\n- **Surgical Equipment & Staffing**: Salaries allocated for a resident Chief Physician (*Maruthuvan*), a wound surgeon (*Shalya-Karan*), two apothecary gatherers, two nurses (*Aathurar Sevagar*), and a washerman for surgical bandages.",
        "chunks": [
            {
                "language": "en",
                "title": "Chola Hospital Epigraphs & Standardized Medicine Inventories",
                "content": "Imperial Chola epigraphs at Maruthuvakkudi and Thirumukkoodal record state-funded hospital wards stocking over twenty varieties of standardized Thailams and Lehiyams under salaried medical specialists."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0b86\u0ba4\u0bc1\u0bb0\u0b9a\u0bbe\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bbf\u0baf\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
                "content": "\u0ba4\u0bbf\u0bb0\u0bc1\u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0bb2\u0bc2\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0bbf \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2 \u0b87\u0bb2\u0bb5\u0b9a \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0ba9\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b9a\u0bc7\u0bae\u0bbf\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b87\u0bb0\u0bc1\u0baa\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba4\u0bc8\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0bb2\u0bc7\u0b95\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0b9a\u0bbf\u0b95\u0bbf\u0b9a\u0bcd\u0b9a\u0bc8 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b8a\u0ba4\u0bbf\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bbf\u0ba9\u0bcd\u0bb1\u0ba9."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-kollimalai-master-siddha-pharmacologist-maruthuva-sithar.md",
        "slug": "char-kollimalai-master-siddha-pharmacologist-maruthuva-sithar",
        "category": "character",
        "name_en": "Kollimalai Master Siddha Pharmacologist Maruthuva Sithar",
        "name_ta": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bbf\u0baf\u0bb2\u0bcd \u0bb5\u0bb2\u0bcd\u0bb2\u0bc1\u0ba8\u0bb0\u0bcd \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0b9a\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0bb0\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Persona portraying the venerated ascetic physician residing in the cloud caverns of Kollimalai, possessing encyclopedic mastery of botanical taxonomy, lunar harvesting rhythms, and alchemical metal calcination.",
        "summary_ta": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bbe\u0bb4\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1, \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0bc1\u0ba3\u0bae\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1, \u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0 \u0ba8\u0bbf\u0bb2\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0baa\u0bc1\u0b9f\u0bae\u0bbf\u0b9f\u0bcd\u0b9f \u0baa\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0ba4\u0bcd \u0ba4\u0bc8\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0b86\u0bb3\u0bc1\u0bae\u0bc8.",
        "sources": [
            "Sirupanarruppadai lines 95-110",
            "Bogar 7000",
            "Oral Traditions of Kolli Hills Siddha Lineages"
        ],
        "content": "# Kollimalai Master Siddha Pharmacologist Maruthuva Sithar\n\n## The Healer of the Cloud Forests\nDwelling above the mist line in the granite rock shelters of Kollimalai, *Maruthuva Sithar* embodied the spiritual and practical pinnacles of Tamil healing science. Disdaining urban wealth, he was sought after by crowned monarchs and wounded warriors alike.\n\n## Rhythms of Botanical Gathering (*Mooligai-Parippu*)\n1. **Astrological & Circadian Calibration**: Gathering root medicines during the waxing moon (*Valarpirai*) when sap concentrated in aerial foliage; harvesting roots at dusk during the dark fortnight when therapeutic juices retreated subterraneanly.\n2. **The Test of the Oil Drop (*Ney-Kuri*)**: Diagnosing patient ailments by floating a drop of sesame oil on the surface of fresh morning urine; the spreading shape (circular for Vatham, ring-shaped for Pitham, pearl-like for Kapham) dictated the pharmacological formula.\n3. **Crucible Mastery**: Compounding metallic ashes in tiny clay crucibles fired with tamarind charcoal, producing medicines that cured with micro-gram doses.",
        "chunks": [
            {
                "language": "en",
                "title": "Master Siddha Pharmacologist Botanical Gathering & Ney-Kuri Diagnostics",
                "content": "The Kollimalai Siddha master gathered medicinal herbs according to circadian and lunar sap rhythms, employing urine oil-drop diagnostics (Ney-Kuri) to formulate customized Thailam cures."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0bb0\u0bbf\u0ba9\u0bcd \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0ba8\u0bc6\u0bb1\u0bbf",
                "content": "\u0b9a\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0 \u0ba8\u0bbf\u0bb2\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b8f\u0bb1\u0bcd\u0baa \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bb1\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bbf\u0bb1\u0bc1\u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0ba8\u0bb2\u0bcd\u0bb2\u0bc6\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0bb5\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bcb\u0baf\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 (\u0ba8\u0bc6\u0baf\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bb1\u0bbf), \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0b85\u0bb0\u0bbf\u0baf \u0ba4\u0bc8\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0bb0\u0bbf\u0ba9\u0bcd \u0bae\u0bb0\u0baa\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-urandhai-royal-wound-surgeon-ranavaidhiyar-kollan.md",
        "slug": "char-urandhai-royal-wound-surgeon-ranavaidhiyar-kollan",
        "category": "character",
        "name_en": "Urandhai Royal Wound Surgeon Ranavaidhiyar Kollan",
        "name_ta": "\u0b89\u0bb1\u0ba8\u0bcd\u0ba4\u0bc8 \u0b85\u0bb0\u0b9a \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3\u0b95\u0bcd \u0b95\u0bbe\u0baf \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd \u0b87\u0bb0\u0ba3\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb0\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Persona portraying the elite military trauma surgeon in the Chola capital of Uraiyur, wielding bronze lancets, silk sutures, cauterizing hot oils, and analgesic herbal decoctions to treat deep battle wounds.",
        "summary_ta": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0baa\u0bbe\u0b9a\u0bb1\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bb3\u0bcd, \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc2\u0bb2\u0bcd\u0b95\u0bb3\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0ba8\u0bc6\u0baf\u0bcd\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bcd\u0bae\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd \u0baa\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0bbe\u0baf\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0ba3\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf\u0baf \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b87\u0bb0\u0ba3 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bb0\u0bcd.",
        "sources": [
            "Purananuru 68 & 353",
            "Pathitrupathu 42",
            "Surgical Chapters of Ancient Tamil Medical Classics"
        ],
        "content": "# Urandhai Royal Wound Surgeon Ranavaidhiyar Kollan\n\n## The Trauma Surgeon of the Battle Citadel\nAttached to the imperial Chola armories at Uraiyur (*Urandhai*), *Ranavaidhiyar Kollan* was a veteran of border campaigns and siege warfare. He treated horrific flesh lacerations, severed tendons, and arrow wounds sustained against Pandya and Chera forces.\n\n## Battlefield Surgical Interventions\n- **Arrow Extraction (*Ambu-Vaangal*)**: Using specialized hollow bronze forceps to dislodge barbed iron arrowheads without tearing surrounding muscle tissue.\n- **Cauterization & Hemostasis**: Pouring boiling medicated sesame oil blended with *Veppilai* (neem) and turmeric directly into gaping wounds to instantly cauterize bleeding capillaries and prevent gangrene.\n- **Ant-Head Suture Technique**: Utilizing the formidable mandibles of giant black forest ants (*Katturumbu*) to clamp lacerated intestine walls together; once the ant bit both edges, its body was snapped off, leaving organic, dissolving chitin clips that healed without infection.",
        "chunks": [
            {
                "language": "en",
                "title": "Royal Battlefield Surgeon Trauma Interventions & Ant Suture Protocols",
                "content": "At Uraiyur, the royal trauma surgeon utilized hollow bronze forceps for arrow extraction, hot neem oil cauterization, and natural ant-mandible sutures to save wounded warriors from fatal battlefield trauma."
            },
            {
                "language": "ta",
                "title": "\u0b89\u0bb1\u0bc8\u0baf\u0bc2\u0bb0\u0bcd \u0b85\u0bb0\u0b9a \u0b87\u0bb0\u0ba3\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bb0\u0bbf\u0ba9\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb3 \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0b9a\u0bbf\u0b95\u0bbf\u0b9a\u0bcd\u0b9a\u0bc8",
                "content": "\u0b85\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0b95\u0bcd \u0b95\u0bc1\u0bb1\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0b9a\u0bc1\u0b9f\u0bc1\u0ba8\u0bc6\u0baf\u0bcd\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bae\u0bcd \u0b86\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0b8e\u0bb1\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bc1\u0b9f\u0bb2\u0bcd \u0b95\u0bbf\u0bb4\u0bbf\u0b9a\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0bbf\u0baf \u0b9a\u0b99\u0bcd\u0b95 \u0b95\u0bbe\u0bb2 \u0b85\u0bb1\u0bc1\u0bb5\u0bc8 \u0b9a\u0bbf\u0b95\u0bbf\u0b9a\u0bcd\u0b9a\u0bc8 \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/places/place-kollimalai-ancient-medicinal-flora-and-thailam-haven.md",
        "slug": "place-kollimalai-ancient-medicinal-flora-and-thailam-haven",
        "category": "place",
        "name_en": "Kollimalai: Ancient Medicinal Flora, Montane Sanctuary & Thailam Haven",
        "name_ta": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0ba4\u0bcd \u0ba4\u0bbe\u0bb5\u0bb0\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc8\u0bb2 \u0bae\u0bc8\u0baf\u0bae\u0bcd",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "kurinji",
        "summary_en": "Iconic mist-cloaked mountain plateau in the Eastern Ghats famed in Sangam anthologies as the domain of chieftain Valvil Ori, containing deep evergreen shola valleys, waterfalls, and the highest concentration of medicinal herbs in South India.",
        "summary_ta": "\u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bb2\u0bcd \u0bae\u0bbf\u0b95\u0bcd\u0b95 \u0bb5\u0bb2\u0bcd\u0bb5\u0bbf\u0bb2\u0bcd \u0b93\u0bb0\u0bbf \u0b86\u0b9f\u0bcd\u0b9a\u0bbf \u0b9a\u0bc6\u0baf\u0bcd\u0ba4 \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8, \u0b9a\u0bcb\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bcd, \u0ba8\u0bc0\u0bb0\u0bcd\u0bb5\u0bc0\u0bb4\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0bbf\u0ba8\u0bcd\u0ba4\u0bbf\u0baf\u0bbe\u0bb5\u0bbf\u0ba9\u0bcd \u0bae\u0bbf\u0b95 \u0b85\u0b9f\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbe\u0ba9 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Purananuru 158",
            "Sirupanarruppadai lines 110-125",
            "Botanical Survey of India Monograph on the Flora of Kolli Hills"
        ],
        "content": "# Kollimalai: Ancient Medicinal Flora, Montane Sanctuary & Thailam Haven\n\n## Montane Geography & Microclimates\nRising abruptly to an elevation of 1,300 meters above the dry plains of the Kaveri basin ($11.2500^\\circ\\text{ N}, 78.3500^\\circ\\text{ E}$), Kollimalai encompasses over 280 square kilometers of plateau dissected by precipitous ravines, perennial streams, and cascading cataracts like Agaya Gangai.\n\n## Botanical Epicenter of Siddha Heritage\nThe combination of montane mist, red lateritic soil enriched with decomposing humus, and stable high humidity created an ecological refuge where over 1,200 species of medicinal plants flourished:\n- **Shola Herbal Sanctuaries**: Valley forests sheltering rare therapeutic species including *Gloriosa superba* (*Sengandal*\u2014the national flower of Tamilakam), *Rauvolfia serpentina* (*Sarpagandhi*), and endemic wild gingers.\n- **Cavern Laboratories (*Sithar Gugai*)**: Over thirty natural granite caves where ancient ascetics ground mineral parpams, cured roots in honey, and boiled aromatic thailam oils.\n- **Arapaleeswarar Hermitage**: A sacred cultural center where pilgrims and village physicians converged during harvest festivals to trade dried barks, mountain honey, and seasoned medicinal tubers.",
        "chunks": [
            {
                "language": "en",
                "title": "Kollimalai Montane Microclimate & Herbal Biodiversity Haven",
                "content": "Elevated 1,300 meters above the Kaveri plains, the mist-cloaked Kolli Hills formed South India's premier medicinal botanical sanctuary, harboring over 1,200 therapeutic plant species within protected evergreen sholas."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "1300 \u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bb0\u0bcd \u0b89\u0baf\u0bb0\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b9a\u0bcb\u0bb2\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b86\u0b95\u0bbe\u0baf \u0b95\u0b99\u0bcd\u0b95\u0bc8 \u0b85\u0bb0\u0bc1\u0bb5\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bbf\u0bae\u0bb2\u0bc8, 1200-\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b85\u0bb0\u0bbf\u0baf \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0ba4\u0bcd \u0ba4\u0bbe\u0bb5\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0bb0\u0bcd \u0b95\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bcd\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd."
            }
        ]
    }
]
EDGES = [
    [
        "text-agasthiyar-gunavagadam-pharmacology-and-thailam-poetry",
        "canonizes_extraction_protocols",
        "concept-herbal-decoction-reduction-and-sesame-oil-thailam-extraction",
        "cultural",
        "Classical to Early Medieval Era",
        "Agasthiyar Gunavagadam records the boiling protocols for sesame oil Thailam.",
        "Agasthiyar Gunavagadam Thailam Section"
    ],
    [
        "text-agasthiyar-gunavagadam-pharmacology-and-thailam-poetry",
        "details_steam_therapy",
        "concept-subterranean-herbal-steam-inhalation-and-sweat-therapy-viyarpani",
        "medical",
        "Classical to Early Medieval Era",
        "The treatise details diaphoretic Viyarpani sudation therapy.",
        "Theraiyar Yamaga Venba"
    ],
    [
        "concept-herbal-decoction-reduction-and-sesame-oil-thailam-extraction",
        "sourced_from_haven",
        "place-kollimalai-ancient-medicinal-flora-and-thailam-haven",
        "botanical",
        "Early Historic Era",
        "Medicinal roots for Thailam were harvested from Kollimalai.",
        "Botanical Survey Reports"
    ],
    [
        "concept-calcined-metal-ash-bhasma-and-herbal-marmam-poultices",
        "utilized_by_surgeon",
        "char-urandhai-royal-wound-surgeon-ranavaidhiyar-kollan",
        "medical",
        "Early Historic Era",
        "Trauma surgeons applied mineral Parpams and poultices to battlefield wounds.",
        "Purananuru 68"
    ],
    [
        "concept-botanical-confections-lehiyam-and-palm-jaggery-preservatives",
        "formulated_by_pharmacologist",
        "char-kollimalai-master-siddha-pharmacologist-maruthuva-sithar",
        "pharmacological",
        "Sangam to Medieval Era",
        "The master pharmacologist compounded shelf-stable Lehiyams.",
        "Agasthiyar Paripooranam"
    ],
    [
        "concept-subterranean-herbal-steam-inhalation-and-sweat-therapy-viyarpani",
        "practiced_at_haven",
        "place-kollimalai-ancient-medicinal-flora-and-thailam-haven",
        "therapeutic",
        "Early Historic Sangam Era",
        "Subterranean sudation pits were operated in the Kolli Hills.",
        "Traditional Thermal Therapies"
    ],
    [
        "insc-kollimalai-siddha-herbal-sanctuary-and-medicinal-flora-charters",
        "inscribed_at",
        "place-kollimalai-ancient-medicinal-flora-and-thailam-haven",
        "epigraphical",
        "Sangam to Medieval Era",
        "Royal charters protected the medicinal flora of Kollimalai.",
        "South Indian Inscriptions Vol. XXII"
    ],
    [
        "insc-maruthuvakkudi-chola-hospital-and-herbal-dispensary-epigraphs",
        "stocks_pharmacological_remedies",
        "concept-botanical-confections-lehiyam-and-palm-jaggery-preservatives",
        "epigraphical",
        "Medieval Chola Era",
        "Hospital epigraphs inventory standardized Lehiyam and Thailam stocks.",
        "Tirumukkudal Inscription"
    ],
    [
        "char-kollimalai-master-siddha-pharmacologist-maruthuva-sithar",
        "headquartered_at",
        "place-kollimalai-ancient-medicinal-flora-and-thailam-haven",
        "guild_membership",
        "Sangam Classical Era",
        "The master Siddha physician operated in Kollimalai cloud caves.",
        "Sirupanarruppadai lines 95-110"
    ],
    [
        "char-urandhai-royal-wound-surgeon-ranavaidhiyar-kollan",
        "procures_herbal_oils_from",
        "char-kollimalai-master-siddha-pharmacologist-maruthuva-sithar",
        "commercial",
        "Sangam Classical Era",
        "Royal army surgeons sourced emergency trauma Thailams from Kolli mountain hermits.",
        "Purananuru 353"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 25 Corpus 1: Herbal Pharmacology & Thailam Extraction into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 25 Corpus 1: Herbal Pharmacology & Thailam Extraction Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
