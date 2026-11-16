#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Granite Quarrying, Wedge-Splitting & Monolithic Sculpting
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
        "file": "knowledge/texts/text-chulavamsa-and-epigraphs-on-pandya-monolithic-sculptors-and-granite-caves.md",
        "slug": "text-chulavamsa-and-epigraphs-on-pandya-monolithic-sculptors-and-granite-caves",
        "category": "text",
        "name_en": "Epigraphical Charters & Inscriptions on Early Pandya Monolithic Rock-Cut Sculptors",
        "name_ta": "\u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0b99\u0bcd\u0b95\u0bb3\u0bcd - \u0bae\u0bc1\u0bb1\u0bcd\u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0bb5\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bbe\u0bb0\u0bbf\u0baf\u0bb0\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Early Medieval Pandya Era",
        "year_start": 700,
        "year_end": 900,
        "thinai": "mullai",
        "summary_en": "Epigraphical inscriptions recording early Pandya master sculptors (perun-thatchar) who hewed monolithic shrines, rock-cut cave temples, and exquisite relief friezes out of living granite.",
        "summary_ta": "\u0bb5\u0bbe\u0bb4\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0b92\u0bb1\u0bcd\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd (\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bbe\u0ba9\u0bcd \u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd), \u0baa\u0bc1\u0b9f\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4 \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b9a\u0bbe\u0b9a\u0ba9\u0baa\u0bcd \u0baa\u0ba4\u0bbf\u0bb5\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Kalugumalai Inscriptions",
            "Anamalai Inscriptions",
            "Tirupparankunram Epigraphs"
        ],
        "content": "# Epigraphical Charters on Early Pandya Monolithic Rock-Cut Sculptors\n\nThe 8th-century epigraphical records of the early Pandya kingdom (contemporary with King Maran Chadayan / Nedunjadayan) preserve remarkable historical documentation of rock-cut monolithic sculpture in southern Tamil Nadu.\n\nInscriptions carved into the living rock faces of Kalugumalai, Anamalai, and Tirupparankunram record the royal commissions and guild genealogies of master stone sculptors (perun-thatchar). These records reveal that royal patrons granted hereditary honors, gold bracelets (thadambu), and tax-free lands to artists capable of conceiving and executing monumental monolithic shrines from living granite cliffs.\n\nThe epigraphs praise the mathematical precision, geometric alignment, and spiritual iconography embodied in these works, establishing stone sculpting as one of the preeminent fine arts of ancient Tamil civilization."
    },
    {
        "file": "knowledge/technologies/technology-aappu-vettuthal-dry-wooden-wedge-water-swelling-and-fire-quench-quarrying.md",
        "slug": "technology-aappu-vettuthal-dry-wooden-wedge-water-swelling-and-fire-quench-quarrying",
        "category": "technology",
        "name_en": "Aappu-Vettuthal: Dry Wooden Wedge Water-Swelling & Thermal Quench Granite Quarrying",
        "name_ta": "\u0b86\u0baa\u0bcd\u0baa\u0bc1 \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bb2\u0bcd - \u0b89\u0bb2\u0bb0\u0bcd \u0bae\u0bb0 \u0b86\u0baa\u0bcd\u0baa\u0bc1 \u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0baa\u0bcd\u0baa \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1 \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -800,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Megalithic granite quarrying science: chiseling linear series of wedge mortises, inserting bone-dry hardwood wedges, and soaking with water to generate tremendous expansional cleavage.",
        "summary_ta": "\u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b92\u0bb0\u0bc7 \u0ba8\u0bc7\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1, \u0b95\u0bbe\u0baf\u0bcd\u0ba8\u0bcd\u0ba4 \u0baa\u0bc1\u0bb3\u0bbf\u0baf\u0bae\u0bb0 \u0b86\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc8 \u0b85\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba8\u0bc0\u0bb0\u0bcd \u0b8a\u0bb1\u0bcd\u0bb1\u0bbf \u0b89\u0baa\u0bcd\u0baa\u0b9a\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0bb5\u0ba4\u0ba9\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0baf\u0bc8 \u0ba8\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbe\u0b95\u0baa\u0bcd \u0baa\u0bbf\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd.",
        "sources": [
            "Megalithic Quarry Studies",
            "Silpa Sastra Treatises",
            "Archaeological Survey of India Reports"
        ],
        "content": "# Aappu-Vettuthal: Dry Wooden Wedge Granite Quarrying\n\nAncient Tamil quarry masters developed an ingenious non-explosive rock fragmentation method known as aappu-vettuthal, enabling them to split massive, unblemished granite monoliths weighing dozens of tons with surgical precision.\n\nAlong the natural cleavage strike or desired cutline of a granite outcrop, quarrymen used hardened wootz steel chisels and heavy sledgehammers to cut a linear series of rectangular mortise sockets (aappu-kuzhi) spaced four to six inches apart. Into each socket, they tightly drove wedges of bone-dry tamarind or acacia hardwood.\n\nOnce secured, warm water was poured continuously over the wooden wedges. As the dry cellular fibers absorbed moisture, the wood swelled with colossal hydraulic expansion force (exceeding 200 kilograms per square centimeter). The cumulative lateral pressure induced instantaneous micro-fractures between the sockets, cleanly splitting the granite block along the intended fault line without internal micro-cracking."
    },
    {
        "file": "knowledge/technologies/technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering.md",
        "slug": "technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering",
        "category": "technology",
        "name_en": "Vettuvan-Koil: Top-Down Monolithic Trench Rock-Cutting Engineering & Sinking Pit Mechanics",
        "name_ta": "\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bbe\u0ba9\u0bcd \u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd - \u0bae\u0bc7\u0bb2\u0bcd-\u0b95\u0bc0\u0bb4\u0bcd \u0b92\u0bb1\u0bcd\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0b85\u0b95\u0bb4\u0bbf \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0b9f\u0bc8\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd\u0b95\u0bb2\u0bc8",
        "era": "Early Medieval Pandya Era",
        "year_start": 750,
        "year_end": 850,
        "thinai": "mullai",
        "summary_en": "Architectural genius of top-down monolithic rock excavation at Kalugumalai: excavating a deep rectangular perimeter trench 30 feet into bedrock to sculpt a complete temple from the apex downward.",
        "summary_ta": "\u0b95\u0bb4\u0bc1\u0b95\u0bc1\u0bae\u0bb2\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0bae\u0bb2\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b89\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 30 \u0b85\u0b9f\u0bbf \u0b86\u0bb4\u0ba4\u0bcd\u0ba4\u0bbf\u0bb1\u0bcd\u0b95\u0bc1\u0b9a\u0bcd \u0b9a\u0bc6\u0bb5\u0bcd\u0bb5\u0b95 \u0b85\u0b95\u0bb4\u0bbf \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bbf, \u0bae\u0bc8\u0baf\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0baf\u0bc8 \u0b89\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbf\u0bb2\u0bbf\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0b95\u0bc0\u0bb4\u0bcd\u0ba8\u0bcb\u0b95\u0bcd\u0b95\u0bbf\u0b9a\u0bcd \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0b92\u0bb1\u0bcd\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bbe\u0ba9\u0bcd \u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0b95\u0bcd\u0b95\u0bb2\u0bc8.",
        "sources": [
            "Kalugumalai Archaeological Monograph",
            "K.V. Soundara Rajan Cave Temples",
            "Epigraphia Indica"
        ],
        "content": "# Vettuvan-Koil: Top-Down Monolithic Rock-Cutting Engineering\n\nThe 8th-century Vettuvan Koil at Kalugumalai represents the absolute zenith of monolithic stone architecture under the early Pandya dynasty, earned the title 'The Ellora of the South'.\n\nUnlike structural temples built by assembling pre-cut stone blocks from the foundation upward, the Vettuvan Koil was carved entirely out of a single living granite hill using top-down trench excavation. Sculptors first quarried a rectangular perimeter trench 7.5 meters deep and several meters wide into the summit of the hill, isolating a massive central rectangular core of virgin stone.\n\nWorking from the soaring finial (stupi) and octagonal domical roof (shikhara) downward to the sanctum walls, master craftsmen carved ornate tiers of celestial deities, crouching lions, and flying ganas. Because an error in cutting away stone could never be replaced, the top-down methodology required flawless geometric foresight, perfect depth control, and complete mastery of volumetric space."
    },
    {
        "file": "knowledge/artifacts/artifact-wootz-karunkal-uli-tempered-hypereutectoid-steel-stone-carving-chisels.md",
        "slug": "artifact-wootz-karunkal-uli-tempered-hypereutectoid-steel-stone-carving-chisels",
        "category": "artifact",
        "name_en": "Wootz Karunkal-Uli: Tempered Hypereutectoid Crucible Steel Stone-Carving Chisels",
        "name_ta": "\u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b89\u0bb3\u0bbf - \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0bc2\u0b9f\u0bcd\u0bb8\u0bcd \u0b8e\u0b83\u0b95\u0bc1 \u0b95\u0bb2\u0bcd\u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0bb3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc8\u0bb5\u0bbf\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "High-carbon crucible wootz steel chisels (karunkal-uli) differentially oil-quenched to achieve razor-hard cutting tips (62 HRC) backed by ductile shock-absorbing shanks for granite sculpting.",
        "summary_ta": "\u0b85\u0ba4\u0bbf\u0b89\u0baf\u0bb0\u0bcd \u0b95\u0bbe\u0bb0\u0bcd\u0baa\u0ba9\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0bb5\u0bc2\u0b9f\u0bcd\u0bb8\u0bcd \u0b8e\u0b83\u0b95\u0bbf\u0ba9\u0bbe\u0bb2\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0bc1, \u0b8e\u0ba3\u0bcd\u0ba3\u0bc6\u0baf\u0bcd \u0baa\u0ba4\u0ba9\u0bbf\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bc2\u0bb0\u0bbf\u0baf \u0ba8\u0bc1\u0ba9\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa \u0b89\u0bb3\u0bbf (\u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b89\u0bb3\u0bbf).",
        "sources": [
            "Kodumanal Steel Metallurgical Analysis",
            "Silpa Treatises",
            "Traditional Sthapati Handbooks"
        ],
        "content": "# Wootz Karunkal-Uli: Crucible Steel Stone Chisels\n\nCarving dense, abrasive quartz-rich granite required cutting edges far harder and tougher than ordinary wrought iron. Tamil stone sculptors relied on specialized chisels forged from indigenous crucible wootz steel (karunkal-uli).\n\nProduced in clay crucibles heated to 1400\u00b0C in southern metallurgical centers, the steel possessed a hypereutectoid carbon content of 1.4% to 1.8%, forming hard iron carbide (cementite) micro-crystals embedded in a tough pearlite matrix. Blacksmiths hand-forged diverse chisel geometries: pointed punches (koor-uli) for rapid stone spalling, flat-edged chisels (vettu-uli) for leveling plane surfaces, and claw-toothed chisels (pal-uli) for smoothing contour ridges.\n\nThe cutting tip was differentially heated and quenched in herbal sesame oil infusions to achieve extreme hardness (62-64 HRC), while the striking shank was left tempered and ductile to withstand relentless blow after blow from heavy iron or hardwood mallets without shattering."
    },
    {
        "file": "knowledge/concepts/concept-talamana-proportional-iconometric-grid-and-measurement-canons.md",
        "slug": "concept-talamana-proportional-iconometric-grid-and-measurement-canons",
        "category": "concept",
        "name_en": "Talamana: Proportional Iconometric Grid & Canonical Sculptural Measurement Codes",
        "name_ta": "\u0ba4\u0bbe\u0bb3\u0bae\u0bbe\u0ba9\u0bae\u0bcd - \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0ba3\u0bbf\u0ba4 \u0bb5\u0bbf\u0b95\u0bbf\u0ba4\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb3\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0bb5\u0bbf\u0ba4\u0bbf\u0b95\u0bb3\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Canonical Silpa measurement science (talamana) using modular units (angula and tala) based on human facial lengths to map harmonious proportions onto stone blocks before carving.",
        "summary_ta": "\u0bae\u0bc1\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0ba8\u0bc0\u0bb3\u0ba4\u0bcd\u0ba4\u0bc8 \u0b92\u0bb0\u0bc1 \u0ba4\u0bbe\u0bb3\u0bae\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1, \u0b85\u0b99\u0bcd\u0b95\u0bc1\u0bb2\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baf\u0bb5\u0bc8 \u0b85\u0bb2\u0b95\u0bc1\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0baa\u0bbe\u0bb1\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b89\u0bb0\u0bc1\u0bb5\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0bb5\u0bb0\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa \u0b9a\u0bbe\u0bb8\u0bcd\u0ba4\u0bbf\u0bb0\u0b95\u0bcd \u0b95\u0ba3\u0bbf\u0ba4 \u0bb5\u0bbf\u0b95\u0bbf\u0ba4\u0bbe\u0b9a\u0bcd\u0b9a\u0bbe\u0bb0\u0bae\u0bcd.",
        "sources": [
            "Manasara Silpa Sastra Chapter 57",
            "Mayamata Chapter 22",
            "Kashyapa Silpa Sastra"
        ],
        "content": "# Talamana: Proportional Iconometric Grid System\n\nBefore a single chisel struck the stone, master sculptors (sirpacharyas) laid out the divine image using a rigorous system of canonical modular proportions known as talamana.\n\nThe basic unit of length was the tala (the length of the palm or face from hairline to chin), divided into twelve equal angulas, each containing eight yavas (barley grains). Different categories of beings were prescribed specific mathematical ratios: deities were mapped according to the majestic Dasa-Tala (ten-tala) or Uttama-Dasa-Tala (124 angulas) system, kings in Nava-Tala (nine-tala), and mortal humans in Ashta-Tala (eight-tala).\n\nSculptors drafted these proportions onto squared granite blocks using red ochre chalk lines and string grids, establishing vertical plumb axes (brahmasutra) and horizontal anatomical datums, ensuring absolute aesthetic harmony, balanced gravity, and divine majesty."
    },
    {
        "file": "knowledge/institutions/institution-perun-thatchar-silpi-guild-master-granite-sculptor-guilds.md",
        "slug": "institution-perun-thatchar-silpi-guild-master-granite-sculptor-guilds",
        "category": "institution",
        "name_en": "Perun-Thatchar Silpi Guild: Sovereign Corporations of Master Granite Sculptors",
        "name_ta": "\u0baa\u0bc6\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0b9a\u0bcd\u0b9a\u0bb0\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbf \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1 - \u0b85\u0bb0\u0b9a \u0b86\u0ba4\u0bb0\u0bb5\u0bc1 \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0ba4\u0bb2\u0bc8\u0b9a\u0bbf\u0bb1\u0ba8\u0bcd\u0ba4 \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbf\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0b9f\u0b95\u0bcd \u0b95\u0bb2\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0bae\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "mullai",
        "summary_en": "Collegiate corporations of master architects (sthapathis) and sculptors (perun-thatchar) governing architectural canons, quarry concessions, and royal monument contracts.",
        "summary_ta": "\u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bb2\u0bc8 \u0ba8\u0bc6\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8\u0b95\u0bb3\u0bcd, \u0baa\u0bbe\u0bb1\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0bb5\u0bbe\u0bb0\u0bbf \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0b9f\u0baa\u0bcd \u0baa\u0ba3\u0bbf\u0b95\u0bb3\u0bc8 \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0b95\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba4\u0ba9\u0bcd\u0ba9\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0bae\u0bc1\u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0bbe\u0b9a\u0bbe\u0bb0\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1.",
        "sources": [
            "Kalugumalai Epigraphs",
            "Pudukkottai Inscriptions",
            "South Indian Temple Inscriptions"
        ],
        "content": "# Perun-Thatchar Silpi Guild: Master Sculptor Corporations\n\nThe creation of monumental stone architecture across Tamil Nadu was orchestrated by highly organized, prestigious artisan corporations led by the Perun-Thatchar (Chief Master Sculptor or Sthapathi).\n\nDocumented in hundreds of rock inscriptions from the Pallava, Pandya, and Chola epochs, these guilds possessed complex internal hierarchies: the Sthapathi conceived the architectural vision and iconometric geometry; the Sutragrahin maintained plumb lines and horizontal alignments; the Takshaka cut and dressed structural blocks; and the Vardhakin carved intricate ornamentation and polished surfaces.\n\nGuilds enjoyed high civic standing: monarchs bestowed royal titles, tax-exempt agricultural villages (sirpa-kaani), and ceremonial privileges. The guilds rigorously regulated craft secrets, trained youth through lifelong apprenticeships, and adjudicated all standards of stone craftsmanship."
    },
    {
        "file": "knowledge/concepts/concept-kal-palupu-quartz-sand-abrasive-polishing-and-relief-burnishing.md",
        "slug": "concept-kal-palupu-quartz-sand-abrasive-polishing-and-relief-burnishing",
        "category": "concept",
        "name_en": "Kal-Palupu: Quartz Sand Abrasive Polishing, Agate Burnishing & Granite Finishing",
        "name_ta": "\u0b95\u0bb2\u0bcd \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bc1 - \u0b95\u0bc1\u0bb5\u0bbe\u0bb0\u0bcd\u0b9f\u0bcd\u0bb8\u0bcd \u0bae\u0ba3\u0bb2\u0bcd \u0b9a\u0bbf\u0bb0\u0bbe\u0baf\u0bcd\u0baa\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bc7\u0baf\u0bcd\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd, \u0b85\u0b95\u0bc7\u0b9f\u0bcd \u0baa\u0bbe\u0bb2\u0bbf\u0bb7\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0bb5\u0bb4\u0bb5\u0bb4\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Surface lapidary technology of polishing rough-chiseled granite surfaces into mirror-like, silky finishes using progressive grits of river quartz sand, emery powder, and agate burnishers.",
        "summary_ta": "\u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd\u0bb2\u0bbf\u0ba9\u0bcd \u0b95\u0bb0\u0b9f\u0bc1\u0bae\u0bc1\u0bb0\u0b9f\u0bbe\u0ba9 \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0bb0\u0baa\u0bcd\u0baa\u0bc8 \u0b86\u0bb1\u0bcd\u0bb1\u0bc1 \u0bae\u0ba3\u0bb2\u0bcd, \u0b95\u0bc1\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc6\u0bb4\u0bc1\u0b95\u0bc1 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0ba3\u0bcd\u0ba3\u0bbe\u0b9f\u0bbf \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0baa\u0bb3\u0baa\u0bb3\u0baa\u0bcd\u0baa\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1\u0b9a\u0bbe\u0bb0\u0bcd \u0ba4\u0bc7\u0baf\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Megalithic Sarcophagus Polishing Studies",
            "Kalugumalai Relief Studies",
            "Silpa Rathnam"
        ],
        "content": "# Kal-Palupu: Quartz Sand Polishing & Relief Finishing\n\nFollowing the raw chiseled sculpting of a monolithic relief, stone masters executed the refined surface treatment known as kal-palupu, transforming crystalline, abrasive granite into smooth, tactile surfaces.\n\nThe process utilized progressive mechanical abrasion. Artisans first rubbed the chiseled stone with flat blocks of hard quartzite sandstone lubricated with water and coarse river sand to eliminate chisel ridges. Next, finer grits of pulverized corundum (kuruntham / emery powder) and crushed quartz were applied with wet coir pads or wooden rubbing blocks.\n\nFor sanctum deity images and royal portrait reliefs, final lustrous burnishing was achieved using smooth pebbles of agate or carnelian rubbed under high manual pressure, followed by application of warm sesame oil and beeswax, sealing the stone pores and bringing forth the natural iridescent sheen of feldspar and hornblende crystals."
    },
    {
        "file": "knowledge/artifacts/artifact-thookku-kundu-and-nool-plumb-bobs-right-angles-and-triangulation-lines.md",
        "slug": "artifact-thookku-kundu-and-nool-plumb-bobs-right-angles-and-triangulation-lines",
        "category": "artifact",
        "name_en": "Thookku-Kundu & Nool: Cast-Bronze Plumb Bobs, Chalk Lines & Geometry Triangulation",
        "name_ta": "\u0ba4\u0bc2\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0bc1\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc2\u0bb2\u0bcd - \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0ba4\u0bcd \u0ba4\u0bc2\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0bc1\u0ba3\u0bcd\u0b9f\u0bc1, \u0ba8\u0bc2\u0bb2\u0bcd \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0ba3 \u0b85\u0bb3\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0bb5\u0bbf\u0b95\u0bb3\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Precision geometric sighting artifacts: cast bronze conical plumb bobs (thookku-kundu), red ochre marking cords (nool), and bamboo right-angle set squares (mattam) for architectural alignment.",
        "summary_ta": "\u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bbf\u0bb2\u0bc8\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bc8 \u0b85\u0bb3\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2\u0ba4\u0bcd \u0ba4\u0bc2\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0bc1\u0ba3\u0bcd\u0b9f\u0bc1, \u0ba8\u0bc7\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bcb\u0b9f\u0bc1 \u0baa\u0bcb\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0bc6\u0b99\u0bcd\u0b95\u0bbe\u0bb5\u0bbf \u0ba8\u0bc2\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bcb\u0ba3 \u0b85\u0bb3\u0bb5\u0bbf\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Mayamata Chapter 6",
            "Kashyapa Silpa Sastra",
            "Traditional Sthapathi Toolsets"
        ],
        "content": "# Thookku-Kundu & Nool: Plumb Bobs & Alignment Tools\n\nExcavating complex multi-tiered monolithic temples into living stone demanded rigorous optical and geometric verification tools to ensure absolute verticality and horizontal alignment.\n\nChief among these was the thookku-kundu, a conical plumb bob cast from heavy bell-metal bronze, suspended from a fine silk or twisted hemp thread. By checking the plumb bob against vertical rock faces, sculptors ensured that towering pillars and tiered vimana profiles did not deviate from true verticality.\n\nHorizontal datums were established using water-filled clay troughs or communicating tubes (jala-mattam). Ochre-soaked chalk lines (nool) were snapped against stone faces to create long, razor-straight cutlines, while triangular wooden set-squares (mattam) verified perfect 90-degree right angles across sanctum corners."
    },
    {
        "file": "knowledge/concepts/concept-granite-petrology-and-grain-cleavage-strike-analysis.md",
        "slug": "concept-granite-petrology-and-grain-cleavage-strike-analysis",
        "category": "concept",
        "name_en": "Kal-Niram & Izhai: Traditional Granite Petrology, Grain Cleavage & Acoustic Sounding",
        "name_ta": "\u0b95\u0bb2\u0bcd \u0ba8\u0bbf\u0bb1\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb4\u0bc8 - \u0baa\u0bbe\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bbf\u0baf \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0ba9\u0bbf\u0bae\u0bb5\u0bbf\u0baf\u0bb2\u0bcd, \u0b87\u0bb4\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b92\u0bb2\u0bbf \u0b85\u0ba4\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1 \u0ba4\u0bc7\u0bb0\u0bcd\u0bb5\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Indigenous petrological geology: identifying three functional stone genders (male, female, neuter) based on acoustic resonance, feldspar crystal strike, and grain direction for sculpting.",
        "summary_ta": "\u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0b9f\u0bcd\u0b9f\u0bbf\u0baa\u0bcd \u0baa\u0bbe\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b8e\u0bb4\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2 \u0b93\u0b9a\u0bc8\u0baf\u0bc8 \u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b86\u0ba3\u0bcd \u0b95\u0bb2\u0bcd, \u0baa\u0bc6\u0ba3\u0bcd \u0b95\u0bb2\u0bcd, \u0b85\u0bb2\u0bbf \u0b95\u0bb2\u0bcd \u0b8e\u0ba9\u0bcd\u0bb1\u0bc1 \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1, \u0b85\u0bb5\u0bb1\u0bcd\u0bb1\u0bbf\u0ba9\u0bcd \u0b87\u0bb4\u0bc8\u0ba4\u0bcd \u0ba4\u0bbf\u0b9a\u0bc8\u0baf\u0bc8 \u0b85\u0bb1\u0bbf\u0ba8\u0bcd\u0ba4\u0bc1 \u0b9a\u0bc6\u0ba4\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0bb1\u0bc8 \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Brihat Samhita Stone Chapters",
            "Silpa Rathnam Chapter 12",
            "Traditional Sthapathi Oral Science"
        ],
        "content": "# Kal-Niram & Izhai: Traditional Granite Petrology & Acoustic Selection\n\nTraditional Tamil stone architecture classified crystalline igneous rocks not by modern chemical assays, but through acute observation of mineral composition, grain strike (izhai), and acoustic resonant frequency.\n\nMaster stonemasons tapped candidate boulders with an iron rod, categorizing rocks into three distinct acoustic and metaphysical genders: 'Male stones' (Aan-kal) emitted a clear, ringing, metallic bell-like chime and were chosen for free-standing deity sculptures and load-bearing pillars; 'Female stones' (Penn-kal) resonated with a deeper, melodious chime and were carved into delicate bas-reliefs and pedestal plinths; 'Neuter stones' (Ali-kal) yielded a dull, muted thud and were relegated to subterranean foundation rubble.\n\nFurthermore, sculptors carefully studied the orientation of microscopic feldspar cleavage planes (the grain or izhai). Working along the natural cleavage strike minimized hammer effort and prevented sudden uncontrolled spalling."
    },
    {
        "file": "knowledge/places/place-kalugumalai-ancient-pandya-monolithic-granite-sculpture-haven.md",
        "slug": "place-kalugumalai-ancient-pandya-monolithic-granite-sculpture-haven",
        "category": "place",
        "name_en": "Kalugumalai: Ancient Pandya Monolithic Granite Sculpture Haven & Vettuvan Koil",
        "name_ta": "\u0b95\u0bb4\u0bc1\u0b95\u0bc1\u0bae\u0bb2\u0bc8 - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0b92\u0bb1\u0bcd\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b95\u0bcd \u0b95\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bbe\u0ba9\u0bcd \u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Early Medieval Pandya to Modern Era",
        "year_start": 700,
        "year_end": 1900,
        "thinai": "mullai",
        "summary_en": "Celebrated rocky hillock in Thoothukudi district, renowned throughout world art history as the home of the early Pandya monolithic Vettuvan Koil and pristine Jaina bas-relief sculptures.",
        "summary_ta": "\u0ba4\u0bc6\u0ba9\u0bcd\u0ba9\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0ba9\u0bcd \u0b8e\u0bb2\u0bcd\u0bb2\u0bcb\u0bb0\u0bbe \u0b8e\u0ba9\u0baa\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b92\u0bb1\u0bcd\u0bb1\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0bb5\u0bbe\u0ba9\u0bcd \u0b95\u0bcb\u0bb5\u0bbf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b9a\u0bae\u0ba3\u0bb0\u0bcd \u0baa\u0bc1\u0b9f\u0bc8\u0baa\u0bcd\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0bbf\u0bb1\u0bcd\u0baa\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0bae\u0bc1\u0bb1\u0bcd\u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0bbe\u0ba3\u0bcd\u0b9f\u0bbf\u0baf\u0bb0\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Kalugumalai Archaeological Reports",
            "Epigraphia Indica Vol III",
            "South Indian Temple Architecture"
        ],
        "content": "# Kalugumalai: Ancient Monolithic Sculpture Haven\n\nKalugumalai, a majestic rocky outcrop rising dramatically from the dry plains of Thoothukudi district, holds a sacred place in global art and architectural history as the preeminent sanctuary of early Pandya monolithic stone carving.\n\nFlourishing under the patronage of the early Pandya rulers during the 8th century CE, the hillock was transformed by master sculptor guilds into an open-air academy of stone craftsmanship. Its crowning architectural jewel is the Vettuvan Koil (the 'Sculptor's Haven'), an unfinished monolithic temple hewn from the living rock with breathtaking aesthetic mastery and intricate carvings of celestial dancers, musicians, and lions.\n\nAdjoining the temple are vertical cliff walls adorned with over a hundred polished bas-relief images of Jain Tirthankaras carved by diverse regional guilds, bearing donor inscriptions from across Tamilakam and standing as testament to the unparalleled stone sculpting genius of ancient Tamil civilization."
    }
]
EDGES = [
    [
        "technology-aappu-vettuthal-dry-wooden-wedge-water-swelling-and-fire-quench-quarrying",
        "QUARRIES",
        "concept-granite-petrology-and-grain-cleavage-strike-analysis",
        "core",
        "Prehistoric to Modern Era",
        "Wedge-splitting methods exploit natural mineral grain cleavage and acoustic strike lines in bedrock.",
        "Megalithic Quarry Studies"
    ],
    [
        "technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering",
        "UTILIZES",
        "technology-aappu-vettuthal-dry-wooden-wedge-water-swelling-and-fire-quench-quarrying",
        "core",
        "Early Medieval Pandya Era",
        "Quarrying deep perimeter trenches into living bedrock utilized precision wooden wedge splitting.",
        "Kalugumalai Archaeological Monograph"
    ],
    [
        "artifact-wootz-karunkal-uli-tempered-hypereutectoid-steel-stone-carving-chisels",
        "CARVES",
        "technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering",
        "core",
        "Early Medieval Pandya Era",
        "Differential oil-quenched wootz steel chisels carved the intricate tiers and friezes of the monolithic temple.",
        "Kodumanal Steel Metallurgical Analysis"
    ],
    [
        "concept-talamana-proportional-iconometric-grid-and-measurement-canons",
        "GOVERNS",
        "technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering",
        "core",
        "Prehistoric to Modern Era",
        "Canonical Silpa geometric grids dictated the proportions and visual harmony of carved deity figures.",
        "Manasara Silpa Sastra Chapter 57"
    ],
    [
        "text-chulavamsa-and-epigraphs-on-pandya-monolithic-sculptors-and-granite-caves",
        "DOCUMENTS",
        "institution-perun-thatchar-silpi-guild-master-granite-sculptor-guilds",
        "core",
        "Early Medieval Pandya Era",
        "Inscriptions in rock faces record royal honors, titles, and endowments granted to master sculptor guilds.",
        "Kalugumalai Inscriptions"
    ],
    [
        "institution-perun-thatchar-silpi-guild-master-granite-sculptor-guilds",
        "MASTERS",
        "technology-aappu-vettuthal-dry-wooden-wedge-water-swelling-and-fire-quench-quarrying",
        "core",
        "Early Historic to Medieval Era",
        "Collegiate guilds of master stonemasons mastered quarrying and wedge fracture technologies across generations.",
        "Pudukkottai Inscriptions"
    ],
    [
        "concept-kal-palupu-quartz-sand-abrasive-polishing-and-relief-burnishing",
        "POLISHES",
        "technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering",
        "core",
        "Early Medieval Pandya Era",
        "Progressive quartz sand grinding and corundum burnishing imparted silk-like luster to bas-relief figures.",
        "Silpa Rathnam Chapter 12"
    ],
    [
        "artifact-thookku-kundu-and-nool-plumb-bobs-right-angles-and-triangulation-lines",
        "ALIGNS",
        "technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering",
        "core",
        "Early Medieval Pandya Era",
        "Bronze plumb bobs and red ochre cords verified vertical plumb and geometric alignment during trench sinking.",
        "Mayamata Chapter 6"
    ],
    [
        "technology-vettuvan-koil-top-down-monolithic-trench-rock-cutting-engineering",
        "LOCATED_AT",
        "place-kalugumalai-ancient-pandya-monolithic-granite-sculpture-haven",
        "core",
        "Early Medieval Pandya to Modern Era",
        "The world-famous monolithic top-down Vettuvan Koil temple is situated at the rocky crest of Kalugumalai.",
        "K.V. Soundara Rajan Cave Temples"
    ],
    [
        "institution-perun-thatchar-silpi-guild-master-granite-sculptor-guilds",
        "FLOURISHED_AT",
        "place-kalugumalai-ancient-pandya-monolithic-granite-sculpture-haven",
        "core",
        "Early Medieval Pandya Era",
        "Master stone sculptor and carver corporations maintained active sculptural workshops at Kalugumalai.",
        "Epigraphia Indica Vol III"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Granite Quarrying, Wedge-Splitting & Monolithic Sculpting into Moolam Chronicles & Life Graph...")

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
                properties = EXCLUDED.properties;
        """, (
            str(uuid.uuid4()), slug, d["category"], d["name_en"], d["name_ta"],
            d["era"], d["year_start"], d["year_end"], d["thinai"],
            d["summary_en"], d["summary_ta"], d["sources"], "core", props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} nodes upserted.")

    # Phase 3: PostgreSQL Lore Edges Insertion
    print("\n[Phase 3] Inserting 10 Lore Graph Relationships...")
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

    print(f"\n🎉 Ancient Tamil Granite Quarrying, Wedge-Splitting & Monolithic Sculpting Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
