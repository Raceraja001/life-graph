#!/usr/bin/env python3
# Ingestion harvester for Batch 28 Corpus 3: Bovine Husbandry, War Bull Breeding & Bull Wrestling
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
        "file": "knowledge/texts/text-kalithogai-mullai-pastoral-bull-wrestling-and-bravery-poetry.md",
        "slug": "text-kalithogai-mullai-pastoral-bull-wrestling-and-bravery-poetry",
        "category": "text",
        "name_en": "Kalithogai: Classical Verses on Mullai Pastoral Bull-Embracing & Valour",
        "name_ta": "\u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8 - \u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bbf \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0baf\u0bb0\u0bcd \u0bb5\u0bc0\u0bb0\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd",
        "era": "Classical Sangam Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "The definitive classical anthology of Sangam bull-wrestling (Yeru-Thazhuvuthal) in Mullaikkali, describing fearsome humped bulls charging into dust-swept arenas and brave Ayar youths locking arms around their humps to win maidens' hands.",
        "summary_ta": "\u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8 \u0ba8\u0bbf\u0bb2 \u0b86\u0baf\u0bb0\u0bcd \u0b87\u0bb3\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0b9a\u0bc0\u0bb1\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0b85\u0b9e\u0bcd\u0b9a\u0bbe\u0bae\u0bb2\u0bcd \u0ba4\u0bb4\u0bc1\u0bb5\u0bbf \u0b85\u0b9f\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0b95\u0bbe\u0b9f\u0bcd\u0b9a\u0bbf\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8.",
        "sources": [
            "Kalithogai Mullaikkali poems 101-107",
            "Sangam Pastoral Literature",
            "History of Jallikattu"
        ],
        "content": "# Kalithogai: Classical Verses on Mullai Pastoral Bull-Embracing & Valour\n\n## The Ancient Tradition of Yeru-Thazhuvuthal\nIn the classical poetry of *Kalithogai* (specifically the seven poems of *Mullaikkali*), the indigenous Tamil sport of bull-embracing (*Yeru-Thazhuvuthal*, the ancestral root of modern Jallikattu) is immortalized with vivid realism:\n\n```\n\"\u0b95\u0bca\u0bb2\u0bcd\u0bb2\u0bc7\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd \u0b95\u0bcb\u0b9f\u0b9e\u0bcd\u0b9a\u0bc1\u0bb5\u0bbe\u0ba9\u0bc8 \u0bae\u0bb1\u0bc1\u0bae\u0bc8\u0baf\u0bc1\u0bae\u0bcd\n\u0baa\u0bc1\u0bb2\u0bcd\u0bb2\u0bbe\u0bb3\u0bc7 \u0b86\u0baf \u0bae\u0b95\u0bb3\u0bcd;\n\u0b85\u0b9e\u0bcd\u0b9a\u0bbe\u0bb0\u0bcd \u0b95\u0bca\u0bb2\u0bc8\u0b8f\u0bb1\u0bc1 \u0b95\u0bca\u0bb3\u0bcd\u0baa\u0bb5\u0bb0\u0bcd...\"\n\u2014 \u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8 \u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8\u0b95\u0bcd\u0b95\u0bb2\u0bbf 103\n```\n\n## The Arena of Chivalry & Testing\nThe poems portray decorated stockades (*Thozhu*) where massive black, red, and spotted bulls with sharpened horns were unleashed amidst beating drums. Fearless Ayar (pastoral) youths leaped not to overpower the bull through cruelty, but to embrace its muscular hump (*Thimil*) with bare arms, riding its bucking fury across the ring to prove martial worth before prospective brides.",
        "chunks": [
            {
                "language": "en",
                "title": "Kalithogai Mullai Bull-Embracing & Pastoral Bravery",
                "content": "Kalithogai Mullaikkali details fearless pastoral youths embracing charging war bulls by the hump to prove valor and win brides."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8 \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0baf\u0bb0\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bcd",
                "content": "\u0b9a\u0bc0\u0bb1\u0bbf\u0baa\u0bcd\u0baa\u0bbe\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bbf\u0bae\u0bbf\u0bb2\u0bc8 \u0b85\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0b9f\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8 \u0ba8\u0bbf\u0bb2 \u0b86\u0baf\u0bb0\u0bcd \u0b87\u0bb3\u0bc8\u0b9e\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bc0\u0bb0\u0ba4\u0bcd\u0ba4\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bbf\u0ba4\u0bcd\u0ba4\u0bca\u0b95\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-selective-breeding-of-humped-war-bulls-pulikulam-and-kangayam.md",
        "slug": "concept-selective-breeding-of-humped-war-bulls-pulikulam-and-kangayam",
        "category": "concept",
        "name_en": "Selective Breeding of Indigenous Humped War Bulls (Pulikulam & Kangayam)",
        "name_ta": "\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb2\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd-\u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bc8 \u0bb5\u0bb3\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Indigenous pastoral genetics selecting resilient Bos indicus zebu breeds: the muscular, aggressive Pulikulam (Jallikattu Kaalai) and heat-tolerant, heavy-draft Kangayam cattle, reared for battlefield transport, agricultural power, and arena combat.",
        "summary_ta": "\u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0ba9 \u0b95\u0b9f\u0bbf\u0ba9 \u0b89\u0bb4\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb0\u0bcd\u0b95\u0bcd\u0b95 \u0b95\u0bc1\u0ba3\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bc1\u0bb2\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bb0\u0baa\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc7\u0ba9\u0bcd\u0bae\u0bc8.",
        "sources": [
            "Indigenous Cattle Breeds of Tamil Nadu",
            "Zooarchaeological Surveys of Keezhadi",
            "Pastoral History of South India"
        ],
        "content": "# Selective Breeding of Indigenous Humped War Bulls (Pulikulam & Kangayam)\n\n## Indigenous Zebu Genetics (*Bos indicus*)\nAncient Tamil pastoralists (*Aayar* and *Idaiyar*) developed two distinct purebred cattle strains:\n- **Pulikulam:** Compact, agile, fiercely territorial bulls with backward-sweeping lyre horns, bred along the Vaigai basin specifically for arena agility and predator defense.\n- **Kangayam:** Massive, steel-grey draft bulls developed in the dry Kongu plateau, possessing exceptional bone density, upright horns, and prominent humps (*Thimil*).\n\n## Pastoral Herd Management (*Patti*)\nHerds were maintained in open thorn enclosures (*Patti* / *Thozhu*). Sires were chosen through strict physical selection: deep chests, broad forehead plates, and aggressive fighting temperaments.",
        "chunks": [
            {
                "language": "en",
                "title": "Selective Breeding of Pulikulam & Kangayam Zebu Bulls",
                "content": "Indigenous pastoralists selectively bred aggressive Pulikulam and heavy-draft Kangayam cattle for battlefield hauling and arena trials."
            },
            {
                "language": "ta",
                "title": "\u0baa\u0bc1\u0bb2\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bb0\u0baa\u0bc1 \u0bb5\u0bb3\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8 \u0ba8\u0bbf\u0bb2 \u0b86\u0baf\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0ba4\u0bbf\u0bae\u0bbf\u0bb2\u0bc1\u0bae\u0bcd, \u0b95\u0bc2\u0bb0\u0bbf\u0baf \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0baa\u0bc1\u0bb2\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bb0\u0baa\u0bc1\u0bb5\u0bb4\u0bbf\u0baf\u0bbe\u0b95 \u0ba4\u0bc7\u0bb0\u0bcd\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0bb5\u0bb3\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4 \u0bae\u0bc1\u0bb1\u0bc8."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-pastoral-cattle-raids-aanirai-kavarral-and-heroic-recovery-karanthai.md",
        "slug": "concept-pastoral-cattle-raids-aanirai-kavarral-and-heroic-recovery-karanthai",
        "category": "concept",
        "name_en": "Pastoral Cattle Raids & Heroic Herd Recovery Protocols (Vetchi & Karanthai)",
        "name_ta": "\u0b86\u0ba8\u0bbf\u0bb0\u0bc8 \u0b95\u0bb5\u0bb0\u0bcd\u0ba4\u0bb2\u0bcd (\u0bb5\u0bc6\u0b9f\u0bcd\u0b9a\u0bbf) \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0ba8\u0bbf\u0bb0\u0bc8 \u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd (\u0b95\u0bb0\u0ba8\u0bcd\u0ba4\u0bc8) \u0baa\u0bcb\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bcb\u0b9f\u0bcd\u0baa\u0bbe\u0b9f\u0bc1",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 200,
        "thinai": "mullai",
        "summary_en": "Canonical Sangam warfare doctrine initiating inter-kingdom hostilities through nocturnal cattle-raids (Vetchi), countered by immediate pursuit and armed herd recovery (Karanthai), commemorating fallen warrior-herders with inscribed hero stones.",
        "summary_ta": "\u0baa\u0b95\u0bc8 \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0b86\u0ba8\u0bbf\u0bb0\u0bc8\u0b95\u0bb3\u0bc8 \u0b95\u0bb5\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bcb\u0bb0\u0bcd \u0ba4\u0bca\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0ba4\u0bb2\u0bc1\u0bae\u0bcd, \u0ba4\u0bae\u0ba4\u0bc1 \u0baa\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bc0\u0b9f\u0bcd\u0b95 \u0b89\u0baf\u0bbf\u0bb0\u0bcd\u0b95\u0bca\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0baa\u0bcb\u0bb0\u0bbf\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0ba8\u0bcd\u0ba4\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb0\u0bcd \u0bae\u0bb0\u0baa\u0bc1.",
        "sources": [
            "Tholkappiyam Purathinaiyiyal",
            "Purananuru Cattle Raid Poems",
            "Hero Stone Epigraphy of Dharmapuri"
        ],
        "content": "# Pastoral Cattle Raids & Heroic Herd Recovery Protocols (Vetchi & Karanthai)\n\n## Cattle as the Ultimate Sovereign Wealth\nIn early Tamil society, cattle (*Aanirai* / *Madu*, literally 'wealth') represented mobile capital. Inter-state warfare formally commenced with cattle raiding (*Vetchi*): warriors crowned with scarlet scarlet ixora flowers seized the enemy's herds to protect livestock from impending siege devastation.\n\n## The Heroic Defense (*Karanthai*)\nThe invaded clan countered immediately under the sign of the purple basil (*Karanthai*). Herdsmen armed with bows and spears pursued the raiders across rugged defiles. Warriors who fell defending their community's cattle were venerated on inscribed hero stones (*Nadukal*) depicting the hero holding a bow beside his rescued bull.",
        "chunks": [
            {
                "language": "en",
                "title": "Vetchi Cattle Raiding & Karanthai Recovery Warfare",
                "content": "Sangam military doctrine began conflicts with Vetchi cattle seizures and Karanthai herd recovery, immortalizing fallen defenders on hero stones."
            },
            {
                "language": "ta",
                "title": "\u0bb5\u0bc6\u0b9f\u0bcd\u0b9a\u0bbf \u0b86\u0ba8\u0bbf\u0bb0\u0bc8 \u0b95\u0bb5\u0bb0\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0ba8\u0bcd\u0ba4\u0bc8 \u0bae\u0bc0\u0b9f\u0bcd\u0b9f\u0bb2\u0bcd \u0baa\u0bcb\u0bb0\u0bcd\u0bae\u0bc1\u0bb1\u0bc8",
                "content": "\u0b95\u0bbe\u0bb2\u0bcd\u0ba8\u0b9f\u0bc8\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bb5\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0baa\u0bcb\u0bb0\u0bc8\u0ba4\u0bcd \u0ba4\u0bca\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0bb5\u0ba4\u0bc1\u0bae\u0bcd, \u0b89\u0baf\u0bbf\u0bb0\u0bc8 \u0ba4\u0bc1\u0b9a\u0bcd\u0b9a\u0bae\u0bbe\u0b95 \u0bae\u0ba4\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b86\u0ba8\u0bbf\u0bb0\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bc0\u0b9f\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0ba8\u0bcd\u0ba4\u0bc8 \u0bae\u0bb1\u0bb5\u0bb0\u0bcd \u0bae\u0bb0\u0baa\u0bc1\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-bare-handed-war-bull-embracing-arena-combats-yeru-thazhuvuthal.md",
        "slug": "concept-bare-handed-war-bull-embracing-arena-combats-yeru-thazhuvuthal",
        "category": "concept",
        "name_en": "Bare-Handed War Bull-Embracing Arena Combats (Yeru-Thazhuvuthal & Manju-Virattu)",
        "name_ta": "\u0bb5\u0bc6\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bc8 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0b9e\u0bcd\u0b9a\u0bc1\u0bb5\u0bbf\u0bb0\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bc0\u0bb0 \u0bb5\u0bbf\u0bb3\u0bc8\u0baf\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1",
        "era": "Sangam to Modern Era",
        "year_start": -400,
        "year_end": 1500,
        "thinai": "mullai",
        "summary_en": "Non-violent ritualized arena combat where unarmed athletes sprinted alongside charging stud bulls, grappling the dorsal thoracic hump (Thimil) and maintaining hold over a prescribed distance without injuring or restraining the animal.",
        "summary_ta": "\u0b86\u0baf\u0bc1\u0ba4\u0b99\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd\u0bb1\u0bbf \u0b93\u0b9f\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0ba4\u0bbf\u0bae\u0bbf\u0bb2\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0ba4\u0bcd\u0ba4\u0bc1 \u0b95\u0bc1\u0bb1\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9f\u0bcd\u0b9f \u0ba4\u0bca\u0bb2\u0bc8\u0bb5\u0bc1 \u0bb5\u0bb0\u0bc8 \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0b9a\u0bc6\u0ba9\u0bcd\u0bb1\u0bc1 \u0bb5\u0bc0\u0bb0\u0ba4\u0bcd\u0ba4\u0bc8 \u0ba8\u0bbf\u0bb2\u0bc8\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd.",
        "sources": [
            "Kalithogai Commentary",
            "Keezhadi Inscribed Potsherd with Bull Motif",
            "Jallikattu Historical Antiquity"
        ],
        "content": "# Bare-Handed War Bull-Embracing Arena Combats (Yeru-Thazhuvuthal & Manju-Virattu)\n\n## The Ethos of Mutual Respect\nUnlike Western bullfighting that aims to execute the animal, ancient Tamil *Yeru-Thazhuvuthal* was fundamentally an act of intimate heroic embrace (*Thazhuvuthal*). The bull was venerated as family and deity; the contest was an exhibition of somatic balance, courage, and athletic grace.\n\n## Biomechanics of the Hump Hold\nThe contestant leaped onto the right flank of the galloping bull, wrapping the left arm around the muscular hump (*Thimil*) while holding the tail or horn with the right hand. Surviving three bucking cycles or riding the bull across the arena boundary (*Ellai*) established victory, winning gold ornaments tied between the bull's horns (*Kasu-Kattal*).",
        "chunks": [
            {
                "language": "en",
                "title": "Yeru-Thazhuvuthal Non-Violent Bull Embracing Biomechanics",
                "content": "Unarmed youths grappled the humps of galloping bulls over fixed distances in the ancient non-violent martial sport of Yeru-Thazhuvuthal."
            },
            {
                "language": "ta",
                "title": "\u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bb5\u0bbf\u0bb3\u0bc8\u0baf\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bae\u0bbf\u0bb2\u0bcd \u0baa\u0bbf\u0b9f\u0bbf \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
                "content": "\u0b95\u0bbe\u0bb3\u0bc8\u0baf\u0bc8\u0ba4\u0bcd \u0ba4\u0bbe\u0b95\u0bcd\u0b95\u0bbe\u0bae\u0bb2\u0bcd \u0b85\u0ba4\u0ba9\u0bcd \u0ba4\u0bbf\u0bae\u0bbf\u0bb2\u0bc8 \u0b85\u0ba9\u0bcd\u0baa\u0bcb\u0b9f\u0bc1\u0bae\u0bcd \u0bb5\u0bc0\u0bb0\u0ba4\u0bcd\u0ba4\u0bcb\u0b9f\u0bc1\u0bae\u0bcd \u0ba4\u0bb4\u0bc1\u0bb5\u0bbf \u0b85\u0b9f\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bca\u0ba9\u0bcd\u0bae\u0bc8 \u0bb5\u0bbe\u0baf\u0bcd\u0ba8\u0bcd\u0ba4 \u0ba4\u0bae\u0bbf\u0bb4\u0bb0\u0bcd\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bb5\u0bc0\u0bb0 \u0bb5\u0bbf\u0bb3\u0bc8\u0baf\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1."
            }
        ]
    },
    {
        "file": "knowledge/concepts/concept-bovine-herbal-drenches-horn-cautery-and-pastoral-veterinary-care.md",
        "slug": "concept-bovine-herbal-drenches-horn-cautery-and-pastoral-veterinary-care",
        "category": "concept",
        "name_en": "Bovine Herbal Drenches, Horn Cautery & Pastoral Veterinary Care (Maattu-Maruthuvam)",
        "name_ta": "\u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0bcd, \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1 \u0b9a\u0bc1\u0b9f\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0ba8\u0b9f\u0bc8\u0baa\u0bcd \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Iron Age to Sangam Era",
        "year_start": -400,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Traditional veterinary medicine utilizing oral botanical drenches (Kashayam of ginger, black pepper, and garlic), horn cauterization with heated brass irons to relieve sinus pressure, and herbal poultices for arena puncture wounds.",
        "summary_ta": "\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bc1, \u0bae\u0bbf\u0bb3\u0b95\u0bc1, \u0baa\u0bc2\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb1\u0bcd\u0bb1\u0bbe\u0bb4\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0b95\u0bbe\u0bb2\u0bcd\u0ba8\u0b9f\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bc1\u0bae\u0bcd, \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1 \u0b9a\u0bc1\u0b9f\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba8\u0bcb\u0baf\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bc1\u0ba3\u0bae\u0bbe\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Traditional Siddha Veterinary Texts",
            "Madu-Vaidhya Sastram",
            "Rural Tamil Pastoral Knowledge"
        ],
        "content": "# Bovine Herbal Drenches, Horn Cautery & Pastoral Veterinary Care (Maattu-Maruthuvam)\n\n## Holistic Veterinary Science (*Maattu-Vaidhyam*)\nAncient pastoralists possessed sophisticated diagnostic understanding of ruminant physiology. They formulated botanical drenches administered via hollow bamboo pipes (*Kuzhal*).\n\n## Therapeutics & Trauma Surgery\n- **Digestive Drenches:** Decoctions of dried ginger (*Sukku*), asafoetida (*Perungayam*), and sour buttermilk restored rumen flora during monsoon bloating.\n- **Horn Cauterization (*Kombu-Sudhal*):** Applying heated curved iron bars to horn bases stimulated cranial circulation and cured horn rot and sinusitis.\n- **Wound Poultices:** Deep lacerations suffered in arena contests were dressed with turmeric, aloe vera (*Sothu-Kattralai*), and neem oil, accelerating aseptic tissue regeneration without toxic scarring.",
        "chunks": [
            {
                "language": "en",
                "title": "Bovine Herbal Drenches & Horn Cautery Veterinary Care",
                "content": "Traditional Siddha veterinary medicine used botanical drenches, horn cauterization, and aloe poultices to treat pastoral herds."
            },
            {
                "language": "ta",
                "title": "\u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
                "content": "\u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bc1\u0bb4\u0bb2\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0bae\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0b95\u0bca\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd, \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1 \u0b9a\u0bc1\u0b9f\u0bc1\u0ba4\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0ba3\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd-\u0b95\u0bb1\u0bcd\u0bb1\u0bbe\u0bb4\u0bc8 \u0baa\u0bc2\u0b9a\u0bbf \u0b95\u0bc1\u0ba3\u0bae\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-alanganallur-hero-stone-bull-wrestler-and-arena-endowments.md",
        "slug": "insc-alanganallur-hero-stone-bull-wrestler-and-arena-endowments",
        "category": "inscription",
        "name_en": "Alanganallur & Madurai Epigraphs: Bull-Wrestling Arenas & Hero Stone Charters",
        "name_ta": "\u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb3\u0bae\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Early Historic to Medieval Era",
        "year_start": -200,
        "year_end": 1400,
        "thinai": "mullai",
        "summary_en": "Epigraphic and hero stone records in the Madurai region documenting royal arena allocations (Manju-Virattu Kalam), prize distributions, and memorial stones commemorating fearless youths who fell in the arena.",
        "summary_ta": "\u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bbf\u0bb2\u0bcd \u0bb5\u0bc0\u0bb0\u0bae\u0bb0\u0ba3\u0bae\u0bcd \u0b85\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0bae\u0bc8\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0bb5\u0ba3\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "Tamil Nadu State Department of Archaeology Bulletins",
            "Madurai District Inscriptions"
        ],
        "content": "# Alanganallur & Madurai Epigraphs: Bull-Wrestling Arenas & Hero Stone Charters\n\n## Epigraphic Antiquity of the Arena\nInscriptions across the Vaigai basin document the deep institutional roots of bull-embracing tournaments. Hero stones (*Nadukal*) depict athletic youths grappling the humps of leaping bulls.\n\n## Memorial Hero Stones\nA famous memorial stone in the region honors a fallen youth, depicting him with hand locked in the bull's hump while retaining his warrior dagger, testifying to the extreme martial valor associated with the arena.",
        "chunks": [
            {
                "language": "en",
                "title": "Alanganallur Bull-Wrestling Hero Stones & Arena Charters",
                "content": "Hero stones and inscriptions around Madurai commemorate brave youths grappling charging bulls and record arena land grants."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0b95\u0bbe\u0bb3\u0bc8\u0baf\u0bc8 \u0b85\u0b9f\u0b95\u0bcd\u0b95\u0bbf \u0bb5\u0bc0\u0bb0\u0bae\u0bb0\u0ba3\u0bae\u0bcd \u0b85\u0b9f\u0bc8\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0b95 \u0ba8\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0ba8\u0b9f\u0bc1\u0b95\u0bb1\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0b9e\u0bcd\u0b9a\u0bc1\u0bb5\u0bbf\u0bb0\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc8\u0ba4\u0bbe\u0ba9 \u0b86\u0bb5\u0ba3\u0b99\u0bcd\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/inscriptions/insc-kangayam-chola-cattle-pasture-and-breeding-herd-charters.md",
        "slug": "insc-kangayam-chola-cattle-pasture-and-breeding-herd-charters",
        "category": "inscription",
        "name_en": "Kangayam Chola Epigraphs: Royal Pasture Rights & Cattle Breeding Charters",
        "name_ta": "\u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0bae\u0bc7\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2 \u0b89\u0bb0\u0bbf\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b86\u0ba8\u0bbf\u0bb0\u0bc8\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
        "era": "Imperial Chola Era (c. 1000 \u2013 1200 CE)",
        "year_start": 1000,
        "year_end": 1200,
        "thinai": "mullai",
        "summary_en": "Lithic charters in the Noyyal-Amaravathi corridor recording communal pasture boundaries (Pulla-Kani), breeding bull maintenance funds, and cattle theft punitive codes.",
        "summary_ta": "\u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0bae\u0bcd \u0baa\u0b95\u0bc1\u0ba4\u0bbf\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bbe\u0bb2\u0bcd\u0ba8\u0b9f\u0bc8 \u0bae\u0bc7\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0baa\u0bca\u0bb2\u0bbf \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1 \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0ba4\u0bcd\u0ba4 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd.",
        "sources": [
            "South Indian Inscriptions Vol. V",
            "Kongu Chola Inscriptions"
        ],
        "content": "# Kangayam Chola Epigraphs: Royal Pasture Rights & Cattle Breeding Charters\n\n## Pastoral Foundations of the Kongu Realm\nInscriptions in Kangayam and Dharapuram detail the careful agrarian and pastoral regulation maintained by Imperial Chola administrators.\n\n## Breeding Herd Endowments\nThe records establish perpetual endowments (*Kadaik-Koodai*) funding stud breeding bulls (*Poli-Erudhu*) and delineating extensive grazing reserves (*Meichal-Nilam*) to ensure the vigor of agricultural and war oxen.",
        "chunks": [
            {
                "language": "en",
                "title": "Kangayam Chola Pasture Charters & Breeding Bull Funds",
                "content": "Chola inscriptions at Kangayam detail communal pasture endowments and funding for stud breeding bulls to sustain cattle vigor."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0bae\u0bcd \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0bae\u0bc7\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0b95\u0bcd \u0b95\u0bb2\u0bcd\u0bb5\u0bc6\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bcd",
                "content": "\u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf \u0bae\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0baa\u0bca\u0bb2\u0bbf \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd, \u0bae\u0bc7\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bb2\u0bcd \u0ba8\u0bbf\u0bb2\u0b99\u0bcd\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0ba4\u0bc1\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd \u0b9a\u0bcb\u0bb4 \u0b85\u0bb0\u0b9a\u0bc1 \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0ba8\u0bbf\u0bb2\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc8\u0b95\u0bb3\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-alanganallur-champion-bull-wrestler-kaalai-adakki-veeran.md",
        "slug": "char-alanganallur-champion-bull-wrestler-kaalai-adakki-veeran",
        "category": "character",
        "name_en": "Kothan Maran: Champion Bull-Wrestler & Ayar Chieftain of Alanganallur",
        "name_ta": "\u0b95\u0bcb\u0ba4\u0ba9\u0bcd \u0bae\u0bbe\u0bb1\u0ba9\u0bcd - \u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bb5\u0bc0\u0bb0\u0bb0\u0bcd",
        "era": "Sangam Era (c. 100 BCE \u2013 100 CE)",
        "year_start": -100,
        "year_end": 100,
        "thinai": "mullai",
        "summary_en": "Fabled pastoral athlete celebrated in Sangam lyrics for leaping onto the fiercest black stud bulls, clasping their humps across dusty arenas, and winning the golden floral garland.",
        "summary_ta": "\u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0bc6\u0bb1\u0bcd\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bc8\u0baf\u0bbe\u0bb2\u0bcd \u0b85\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0b85\u0b9f\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2 \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0b86\u0baf\u0bb0\u0bcd \u0bb5\u0bc0\u0bb0\u0ba9\u0bcd.",
        "sources": [
            "Mullaikkali Commentaries",
            "Madurai Pastoral Folklore"
        ],
        "content": "# Kothan Maran: Champion Bull-Wrestler & Ayar Chieftain of Alanganallur\n\n## Champion of the Pastoral Arena\nKothan Maran led the Ayar youth of the northern Madurai foothills. Renowned for supreme agility, he possessed the rare intuition to predict a bull's lateral head hook.\n\n## Feats of Chivalric Bravery\nIn seven successive harvest festivals, Kothan embraced the untamed temple stud bull, surviving horn thrusts to guide the animal to rest, earning him the hand of the chieftain's daughter and royal honors.",
        "chunks": [
            {
                "language": "en",
                "title": "Kothan Maran Champion Bull-Wrestler Biography",
                "content": "Pastoral champion Kothan Maran mastered bare-handed hump grappling on untamed stud bulls in the ancient arenas of Alanganallur."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bb5\u0bc0\u0bb0\u0ba9\u0bcd \u0b95\u0bcb\u0ba4\u0ba9\u0bcd \u0bae\u0bbe\u0bb1\u0ba9\u0bcd",
                "content": "\u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0b95\u0bb3\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b95\u0bca\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0b85\u0b9e\u0bcd\u0b9a\u0bbe\u0bae\u0bb2\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0ba4\u0bbf\u0bae\u0bbf\u0bb2\u0bc8 \u0b85\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc6\u0ba9\u0bcd\u0bb1 \u0b9a\u0b99\u0bcd\u0b95\u0b95\u0bbe\u0bb2\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0bae\u0bc8 \u0bb5\u0bc0\u0bb0\u0ba9\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/characters/char-kangayam-master-bovine-breeder-and-herdsman-aanirai-kaavalan.md",
        "slug": "char-kangayam-master-bovine-breeder-and-herdsman-aanirai-kaavalan",
        "category": "character",
        "name_en": "Periyan Kaavalan: Master Bovine Geneticist & Kongu Herdsman",
        "name_ta": "\u0baa\u0bc6\u0bb0\u0bbf\u0baf\u0ba9\u0bcd \u0b95\u0bbe\u0bb5\u0bb2\u0ba9\u0bcd - \u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf \u0bae\u0bbe\u0b9f\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0bae\u0bc2\u0ba4\u0bcd\u0ba4 \u0bb5\u0bb3\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd",
        "era": "Sangam Era (c. 50 BCE \u2013 150 CE)",
        "year_start": -50,
        "year_end": 150,
        "thinai": "mullai",
        "summary_en": "Veteran cattle breeder who selected purebred Kangayam sires, managed thousands of grazing cattle across the dry Noyyal savanna, and formulated herbal herd medicines.",
        "summary_ta": "\u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b86\u0baf\u0bbf\u0bb0\u0b95\u0bcd\u0b95\u0ba3\u0b95\u0bcd\u0b95\u0bbe\u0ba9 \u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf\u0b95\u0bcd \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bc8 \u0bae\u0bc7\u0baf\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1, \u0b9a\u0bbf\u0bb1\u0ba8\u0bcd\u0ba4 \u0baa\u0bca\u0bb2\u0bbf \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bc7\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1 \u0bb5\u0bb3\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4 \u0bae\u0bc2\u0ba4\u0bcd\u0ba4 \u0b86\u0baf\u0bb0\u0bcd \u0ba4\u0bb2\u0bc8\u0bb5\u0bb0\u0bcd.",
        "sources": [
            "Kongu Pastoral Ethno-History",
            "Ancient Animal Husbandry Records"
        ],
        "content": "# Periyan Kaavalan: Master Bovine Geneticist & Kongu Herdsman\n\n## Guardian of the Kongu Draft Breeds\nPeriyan Kaavalan directed the communal herds of the Noyyal valley. He selected sires with massive humps, tight dewlaps, and flint-hard black hooves capable of traveling forty miles without shoeing.\n\n## Veterinary Master\nPeriyan treated entire herds against seasonal cattle plagues using herbal drenches of ginger and wild basil, ensuring the military draft oxen of Tamil kings remained in peak physical condition.",
        "chunks": [
            {
                "language": "en",
                "title": "Periyan Kaavalan Master Cattle Breeder Biography",
                "content": "Kongu herdsman Periyan Kaavalan selected prime Kangayam breeding sires and administered botanical veterinary medicine to regional herds."
            },
            {
                "language": "ta",
                "title": "\u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bb5\u0bb3\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bbe\u0bb3\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bbf\u0baf\u0ba9\u0bcd \u0b95\u0bbe\u0bb5\u0bb2\u0ba9\u0bcd",
                "content": "\u0b95\u0bbe\u0b99\u0bcd\u0b95\u0bc7\u0baf \u0b95\u0bbe\u0bb3\u0bc8\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0ba4\u0bc2\u0baf \u0bae\u0bb0\u0baa\u0bc8 \u0bb5\u0bb3\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0b95\u0bbe\u0bb2\u0bcd\u0ba8\u0b9f\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8 \u0bae\u0bb0\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1\u0bb5\u0bae\u0bcd \u0b85\u0bb3\u0bbf\u0ba4\u0bcd\u0ba4 \u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc2\u0ba4\u0bcd\u0ba4 \u0b86\u0baf\u0bb0\u0bcd."
            }
        ]
    },
    {
        "file": "knowledge/places/place-alanganallur-ancient-mullai-bull-wrestling-and-pastoral-haven.md",
        "slug": "place-alanganallur-ancient-mullai-bull-wrestling-and-pastoral-haven",
        "category": "place",
        "name_en": "Alanganallur: Ancient Mullai Bull-Wrestling Arena & Pastoral Haven",
        "name_ta": "\u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0b85\u0bb0\u0b99\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1500,
        "thinai": "mullai",
        "summary_en": "Historic pastoral settlement north of Madurai, celebrated worldwide as the premier ceremonial ground and ancestral arena for Tamil bull-embracing tournaments (Yeru-Thazhuvuthal).",
        "summary_ta": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0bb5\u0b9f\u0b95\u0bcd\u0b95\u0bc7 \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0b89\u0bb2\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb4\u0bcd\u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd (\u0b9c\u0bb2\u0bcd\u0bb2\u0bbf\u0b95\u0bcd\u0b95\u0b9f\u0bcd\u0b9f\u0bc1) \u0ba4\u0bbf\u0bb0\u0bc1\u0bb5\u0bbf\u0bb4\u0bbe \u0b85\u0bb0\u0b99\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb2\u0bcd\u0bb2\u0bc8 \u0ba8\u0bbf\u0bb2 \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Gazetteer of Madurai District",
            "Archaeological Surveys of the Vaigai Basin"
        ],
        "content": "# Alanganallur: Ancient Mullai Bull-Wrestling Arena & Pastoral Haven\n\n## Pastoral Geography of the Vaigai Basin\nSituated in the scrubland and forested foothill buffer north of Madurai, Alanganallur evolved as the natural meeting ground between pastoral Mullai cattle-herders and urban Marutham merchants.\n\n## The World Capital of Bull Embracing\nFor over two millennia, Alanganallur has hosted the foremost annual harvest gathering where elite stud bulls from surrounding villages are tested in open arena contests. Hero stones and folk traditions confirm continuous celebration of brave unarmed bull-embracing from the Sangam era into the 21st century.",
        "chunks": [
            {
                "language": "en",
                "title": "Alanganallur Pastoral Bull-Wrestling Topography",
                "content": "Alanganallur north of Madurai is the world-renowned historic epicenter of Tamil bull-embracing (Yeru-Thazhuvuthal) tournaments."
            },
            {
                "language": "ta",
                "title": "\u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bb5\u0bb0\u0bb2\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1 \u0baa\u0bc1\u0bb5\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
                "content": "\u0bae\u0ba4\u0bc1\u0bb0\u0bc8 \u0b85\u0bb0\u0bc1\u0b95\u0bc7 \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0b85\u0bb2\u0b99\u0bcd\u0b95\u0bbe\u0ba8\u0bb2\u0bcd\u0bb2\u0bc2\u0bb0\u0bcd, \u0b87\u0bb0\u0ba3\u0bcd\u0b9f\u0bbe\u0baf\u0bbf\u0bb0\u0bae\u0bcd \u0b86\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb2\u0bbe\u0b95 \u0b8f\u0bb1\u0bc1 \u0ba4\u0bb4\u0bc1\u0bb5\u0bc1\u0ba4\u0bb2\u0bcd \u0bb5\u0bc0\u0bb0 \u0bb5\u0bbf\u0bb3\u0bc8\u0baf\u0bbe\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0b89\u0bb2\u0b95\u0ba4\u0bcd \u0ba4\u0bb2\u0bc8\u0ba8\u0b95\u0bb0\u0bae\u0bbe\u0b95 \u0bb5\u0bbf\u0bb3\u0b99\u0bcd\u0b95\u0bc1\u0b95\u0bbf\u0bb1\u0ba4\u0bc1."
            }
        ]
    }
]
EDGES = [
    [
        "char-alanganallur-champion-bull-wrestler-kaalai-adakki-veeran",
        "located_in",
        "place-alanganallur-ancient-mullai-bull-wrestling-and-pastoral-haven",
        "geography",
        "Sangam Era",
        "Contested and embraced prize stud bulls in the historic arena of Alanganallur",
        "Kalithogai commentaries"
    ],
    [
        "char-kangayam-master-bovine-breeder-and-herdsman-aanirai-kaavalan",
        "participated_in",
        "place-alanganallur-ancient-mullai-bull-wrestling-and-pastoral-haven",
        "commerce",
        "Sangam Era",
        "Supplied prize Kangayam breeding bulls to the annual harvest tournaments",
        "Kongu pastoral records"
    ],
    [
        "concept-bare-handed-war-bull-embracing-arena-combats-yeru-thazhuvuthal",
        "practiced_by",
        "char-alanganallur-champion-bull-wrestler-kaalai-adakki-veeran",
        "chivalry",
        "Sangam Era",
        "Mastered bare-handed hump grappling on untamed galloping bulls",
        "Mullaikkali verses"
    ],
    [
        "concept-selective-breeding-of-humped-war-bulls-pulikulam-and-kangayam",
        "influenced",
        "concept-bare-handed-war-bull-embracing-arena-combats-yeru-thazhuvuthal",
        "genetics",
        "Sangam Era",
        "Selective breeding produced agile, muscular bulls suited for martial arena tests",
        "Pastoral breeding surveys"
    ],
    [
        "concept-pastoral-cattle-raids-aanirai-kavarral-and-heroic-recovery-karanthai",
        "related_to",
        "concept-bare-handed-war-bull-embracing-arena-combats-yeru-thazhuvuthal",
        "warfare",
        "Sangam Era",
        "Arena agility directly prepared warrior-herders for armed cattle defense and recovery",
        "Tholkappiyam Purathinaiyiyal"
    ],
    [
        "concept-bovine-herbal-drenches-horn-cautery-and-pastoral-veterinary-care",
        "influenced",
        "concept-selective-breeding-of-humped-war-bulls-pulikulam-and-kangayam",
        "veterinary",
        "Sangam Era",
        "Herbal drenches and horn cautery preserved the physical longevity of elite breeding herds",
        "Traditional veterinary texts"
    ],
    [
        "text-kalithogai-mullai-pastoral-bull-wrestling-and-bravery-poetry",
        "references",
        "concept-bare-handed-war-bull-embracing-arena-combats-yeru-thazhuvuthal",
        "literature",
        "Sangam Era",
        "Celebrated youthful heroes grappling charging bulls by the hump across stockades",
        "Kalithogai poems 101-107"
    ],
    [
        "insc-alanganallur-hero-stone-bull-wrestler-and-arena-endowments",
        "evidenced_by",
        "place-alanganallur-ancient-mullai-bull-wrestling-and-pastoral-haven",
        "epigraphy",
        "Early Historic",
        "Inscriptions and hero stones recorded arena land grants and celebrated fallen duelists",
        "Madurai Archaeological Memoirs"
    ],
    [
        "insc-kangayam-chola-cattle-pasture-and-breeding-herd-charters",
        "evidenced_by",
        "char-kangayam-master-bovine-breeder-and-herdsman-aanirai-kaavalan",
        "epigraphy",
        "Imperial Chola",
        "Charters confirmed perpetual endowments for breeding bulls and communal pastures",
        "South Indian Inscriptions"
    ],
    [
        "place-alanganallur-ancient-mullai-bull-wrestling-and-pastoral-haven",
        "center_of",
        "concept-bare-handed-war-bull-embracing-arena-combats-yeru-thazhuvuthal",
        "geography",
        "Sangam to Modern",
        "Unbroken historic sanctuary and global epicenter for Tamil bull-embracing tournaments",
        "Gazetteer records"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 28 Corpus 3: Bovine Husbandry, War Bull Breeding & Bull Wrestling into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 28 Corpus 3: Bovine Husbandry, War Bull Breeding & Bull Wrestling Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
