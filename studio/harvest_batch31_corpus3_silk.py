#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Silk Sericulture, Mulberry Cultivation & Gold Zari Brocading
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
        "file": "knowledge/texts/text-porunarattruppadai-verses-on-gossamer-silk-and-serpent-slough-robes.md",
        "slug": "text-porunarattruppadai-verses-on-gossamer-silk-and-serpent-slough-robes",
        "category": "text",
        "name_en": "Porunarattruppadai: Classical Sangam Verses on Gossamer Silk & Serpent-Slough Robes",
        "name_ta": "\u0baa\u0bca\u0bb0\u0bc1\u0ba8\u0bb0\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8 - \u0b86\u0bb5\u0bbf \u0baa\u0bcb\u0ba9\u0bcd\u0bb1 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd\u0b9a\u0bc7\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0bae\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0bc8 \u0b86\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bb5\u0bbf\u0ba4\u0bc8\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Sangam verses of Porunarattruppadai describing royal silk garments so diaphanous and exquisitely fine that their woven threads resembled the slough of a serpent or rising vapors.",
        "summary_ta": "\u0baa\u0bbe\u0bae\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0b9a\u0b9f\u0bcd\u0b9f\u0bc8 \u0baa\u0bcb\u0bb2\u0bb5\u0bc1\u0bae\u0bcd, \u0baa\u0bc1\u0b95\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b86\u0bb5\u0bbf \u0baa\u0bcb\u0bb2\u0bb5\u0bc1\u0bae\u0bcd \u0b95\u0ba3\u0bcd\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0ba4\u0bcd \u0ba4\u0bc6\u0bb0\u0bbf\u0baf\u0bbe\u0ba4 \u0bae\u0bbf\u0b95 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0ba8\u0bc2\u0bb2\u0bcd\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b85\u0bb0\u0b9a \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b86\u0b9f\u0bc8\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bcb\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0bca\u0bb0\u0bc1\u0ba8\u0bb0\u0bbe\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd\u0baa\u0b9f\u0bc8.",
        "sources": [
            "Porunarattruppadai 82-96",
            "Perumpanattruppadai 469",
            "Silappadikaram 14"
        ],
        "content": "# Porunarattruppadai: Classical Sangam Verses on Gossamer Silk\n\nIn the ancient Sangam poem Porunarattruppadai, composed by Mudathama Kanniyar in praise of the great Chola king Karikala Peruvalathan, classical Tamil literature offers breathtaking testimony to the peerless mastery of Tamil silk weaving.\n\nThe poet describes how King Karikala honored visiting bards with gifts of luminous silk garments (pattaadai). The fabric was so gossamer and delicately woven that its individual warp and weft intersections were invisible to the naked eye, resembling 'the delicate, translucent slough shed by a serpent' (aravuriyan) or the faint, ethereal wisp of rising vapor (pukaimukizh annavay).\n\nThese ancient literary descriptions establish that the Tamil country had achieved world-class luxury silk filament processing, spinning, and ultra-fine handloom weaving centuries before European acquaintance with the silk trade."
    },
    {
        "file": "knowledge/concepts/concept-pattu-nool-thozhil-ancient-tamil-mulberry-sericulture-and-filament-reeling.md",
        "slug": "concept-pattu-nool-thozhil-ancient-tamil-mulberry-sericulture-and-filament-reeling",
        "category": "concept",
        "name_en": "Pattu-Nool-Thozhil: Ancient Mulberry Sericulture, Silkworm Rearing & Cocoon Reeling",
        "name_ta": "\u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc2\u0bb2\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0bae\u0bb2\u0bcd\u0baa\u0bc6\u0bb0\u0bbf \u0bae\u0ba3\u0bcd\u0baa\u0bc1\u0bb4\u0bc1 \u0bb5\u0bb3\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1, \u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc2\u0bb2\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Indigenous sericultural agro-science: high-nutrient mulberry cultivation (mulbari), rearing of Bombyx mori worms, and sensitive warm-water cocoon reeling yielding continuous silk filaments.",
        "summary_ta": "\u0b8a\u0b9f\u0bcd\u0b9f\u0b9a\u0bcd\u0b9a\u0ba4\u0bcd\u0ba4\u0bc1 \u0ba8\u0bbf\u0bb1\u0bc8\u0ba8\u0bcd\u0ba4 \u0bae\u0bb2\u0bcd\u0baa\u0bc6\u0bb0\u0bbf\u0b9a\u0bcd \u0b9a\u0bc6\u0b9f\u0bbf \u0bb5\u0bb3\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1, \u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0bb4\u0bc1 \u0bae\u0bc7\u0bb2\u0bbe\u0ba3\u0bcd\u0bae\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0ba8\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0b9f\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0ba4\u0bca\u0b9f\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf\u0baf\u0bbe\u0ba9 \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b87\u0bb4\u0bc8\u0b95\u0bb3\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0ba4\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bca\u0bb4\u0bbf\u0bb2\u0bcd.",
        "sources": [
            "Perumpanattruppadai 465-470",
            "Chola Inscriptions",
            "Madras Handloom Records"
        ],
        "content": "# Pattu-Nool-Thozhil: Ancient Mulberry Sericulture & Reeling\n\nThe production of high-grade silk in Tamil Nadu was founded on the agricultural and biological discipline of pattu-nool-thozhil\u2014the cultivation of mulberry trees and the scientific management of silkworms.\n\nSericultural farmers along the river valleys cultivated rich plots of mulberry (mulbari), pruning bushes systematically to stimulate tender, nutrient-dense foliage. Silkworms (kamblipoochi / Bombyx mori) were nurtured in ventilated circular bamboo trays (thattukal), maintained under controlled ambient humidity and protected from predatory ants and wasps.\n\nOnce the silkworms spun dense fibrous protective cocoons (pattu-koodu), they were harvested and transferred to hot-water degumming vats. Expert filament reelers extracted the microscopically fine continuous bave filaments from multiple cocoons simultaneously, twisting them onto rotating wooden reels into smooth, lustrous silk yarn (pattu-nool)."
    },
    {
        "file": "knowledge/technologies/technology-kuzhi-thari-and-adai-ground-pit-loom-and-jacquard-harness-mechanics.md",
        "slug": "technology-kuzhi-thari-and-adai-ground-pit-loom-and-jacquard-harness-mechanics",
        "category": "technology",
        "name_en": "Kuzhi-Thari & Adai: Earthen Pit-Loom Mechanics, Shedding Treaddles & Adai Pattern Harness",
        "name_ta": "\u0b95\u0bc1\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bb1\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b9f\u0bc8 - \u0ba4\u0bb0\u0bc8\u0bae\u0b9f\u0bcd\u0b9f \u0b95\u0bc1\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bb1\u0bbf \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0b9a\u0bcd\u0b9a\u0bc1 \u0b85\u0b9f\u0bc8 \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Ergonomic earthen pit-looms (kuzhi-thari) preserving moisture-tension in silk filaments, operated with foot treadles and complex string-harness pattern cards (adai) preceding Jacquards.",
        "summary_ta": "\u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0b9f\u0bbf \u0b88\u0bb0\u0baa\u0bcd\u0baa\u0ba4\u0ba4\u0bcd\u0ba4\u0bc8\u0baa\u0bcd \u0baa\u0baf\u0ba9\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bbf \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b87\u0bb4\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baf\u0bc8\u0b95\u0bcd \u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b95\u0bc1\u0bb4\u0bbf\u0ba4\u0bcd\u0ba4\u0bb1\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0b95\u0bcd\u0b95\u0bb2\u0bbe\u0ba9 \u0b89\u0bb0\u0bc1\u0bb5\u0b99\u0bcd\u0b95\u0bb3\u0bc8 \u0ba8\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0bae\u0bb0\u0baa\u0bc1 \u0b85\u0b9f\u0bc8 \u0b95\u0baf\u0bbf\u0bb1\u0bc1 \u0b85\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bbf\u0ba9\u0bcd \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bb5\u0bbf\u0baf\u0bb2\u0bcd.",
        "sources": [
            "Silappadikaram Uraiperukathai",
            "Tirubhuvanam Weavers Guild Records",
            "Census of Handicrafts 1961"
        ],
        "content": "# Kuzhi-Thari & Adai: Ground Pit-Loom & Pattern Harness Mechanics\n\nThe quintessential handloom of traditional Tamil silk weaving is the kuzhi-thari, or sunken pit-loom. The weaver sits on a wooden bench at ground level with legs positioned inside an earthen trench dug into the floor, operating the shedding pedals (mithi) directly beneath the warp.\n\nThis sunken earthen environment was engineered for precise physical thermodynamics: the cool, humid ground moisture stabilized natural moisture content in delicate silk warp threads, drastically reducing yarn brittleness and warp breakage during intensive beating.\n\nFor intricate figured brocades, the loom was integrated with the adai\u2014an indigenous multi-harness thread-programming mechanism. Resembling a complex vertical web of cords hanging above the weaver, the adai encoded warp-lifting sequences for floral borders and mythological motifs, functioning as an ancestral mechanical precursor to the modern Jacquard attachment."
    },
    {
        "file": "knowledge/technologies/technology-korvai-interlocked-weft-temple-border-weaving-craftsmanship.md",
        "slug": "technology-korvai-interlocked-weft-temple-border-weaving-craftsmanship",
        "category": "technology",
        "name_en": "Korvai: Interlocked-Weft Contrast Border Weaving & Temple Spire (Mokku) Mechanics",
        "name_ta": "\u0b95\u0bcb\u0bb0\u0bcd\u0bb5\u0bc8 - \u0bae\u0bc2\u0ba9\u0bcd\u0bb1\u0bc1 \u0ba8\u0bbe\u0b9f\u0bbe \u0b87\u0ba3\u0bc8\u0ba4\u0bcd\u0ba4\u0bc2\u0b9f\u0bc1 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1, \u0baa\u0b9f\u0bcd\u0b9f\u0bc8 \u0b95\u0bb0\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0baa\u0bc1\u0bb0\u0bae\u0bcd/\u0bae\u0bca\u0b95\u0bcd\u0b95\u0bc1 \u0bb5\u0b9f\u0bbf\u0bb5\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Peerless Tamil triple-shuttle interlocked-weft technique (korvai) enabling solid-color contrasting borders with sharp temple-spire saw-tooth motifs (reku / mottu) of immense structural integrity.",
        "summary_ta": "\u0b87\u0bb0\u0bc1 \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0b87\u0ba3\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1 \u0bae\u0bc2\u0ba9\u0bcd\u0bb1\u0bc1 \u0ba8\u0bbe\u0b9f\u0bbe\u0b95\u0bcd\u0b95\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb0\u0ba3\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0bb5\u0ba3\u0bcd\u0ba3\u0b95\u0bcd \u0b95\u0bb0\u0bc8\u0b95\u0bb3\u0bc8 \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bbf\u0bb0\u0b9a\u0bbf\u0ba4\u0bcd\u0ba4\u0bbf \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b95\u0bcb\u0bb0\u0bcd\u0bb5\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bcb\u0baf\u0bbf\u0bb2\u0bcd \u0b95\u0bcb\u0baa\u0bc1\u0bb0 (\u0bae\u0bca\u0b95\u0bcd\u0b95\u0bc1) \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Chola Temple Silk Endowments",
            "Tirubhuvanam GI Documentation",
            "Textiles and Ornaments of India"
        ],
        "content": "# Korvai: Interlocked-Weft Contrast Border Weaving\n\nKorvai represents the hallmark technical innovation of Tamil heritage silk weaving. In standard weaving, a single weft yarn travels across the entire fabric width. In korvai, the body of the saree and its two heavy borders are woven with completely different colored yarns and separate shuttles.\n\nThe process typically requires two weavers working in synchronized rhythm at the pit-loom. As the primary weaver throws the body shuttle, the assistant weaver simultaneously throws border shuttles from both selvages. At the border junction, the weft threads are looped and interlocked around each other before beating the reed.\n\nThis interlocking creates the iconic saw-tooth or triangular temple spire designs known as reku, thazhampoo-reku, or mottu. Korvai demands flawless tension control, yielding a solid, heavy-contrast border that never separates or frays across a century of wear."
    },
    {
        "file": "knowledge/artifacts/artifact-thanga-zari-beaten-gold-wrapped-pure-silk-brocade-threads.md",
        "slug": "artifact-thanga-zari-beaten-gold-wrapped-pure-silk-brocade-threads",
        "category": "artifact",
        "name_en": "Thanga-Zari: Flattened Pure Silver-Gold Wire Wound on Mulberry Silk Brocade Core",
        "name_ta": "\u0ba4\u0b99\u0bcd\u0b95 \u0b9c\u0bb0\u0bbf - \u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0b99\u0bcd\u0b95\u0bae\u0bcd \u0b89\u0bb0\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc8\u0baf \u0b87\u0bb4\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9c\u0bb0\u0bbf\u0b95\u0bc8 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Micro-metallurgy of genuine Tamil zari: silver ingots drawn through diamond dies into gossamer micro-wires, flattened into badla ribbons, and spun around a core of dyed mulberry silk.",
        "summary_ta": "\u0bb5\u0bc6\u0bb3\u0bcd\u0bb3\u0bbf \u0b95\u0bae\u0bcd\u0baa\u0bbf\u0baf\u0bc8 \u0bb5\u0bc8\u0bb0\u0ba4\u0bcd \u0ba4\u0bc1\u0bb3\u0bc8\u0baf\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc1\u0ba3\u0bcd\u0ba3\u0bbf\u0baf \u0b87\u0bb4\u0bc8\u0baf\u0bbe\u0b95 \u0b87\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0ba4\u0b9f\u0bcd\u0b9f\u0bc8\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bbf, \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc2\u0bb2\u0bbf\u0ba9\u0bcd \u0bae\u0bc0\u0ba4\u0bc1 \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0bb1\u0bbf\u0ba4\u0bcd \u0ba4\u0b99\u0bcd\u0b95\u0bae\u0bcd \u0baa\u0bc2\u0b9a\u0bbf \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba4\u0bcd\u0ba4\u0bae\u0bbe\u0ba9 \u0ba4\u0b99\u0bcd\u0b95 \u0b9c\u0bb0\u0bbf\u0b95\u0bc8.",
        "sources": [
            "Kanchipuram & Tirubhuvanam Inscriptions",
            "South Indian Epigraphy Vol IV",
            "Indian Textile Technology Journal"
        ],
        "content": "# Thanga-Zari: Silver-Gold Wrapped Silk Brocade Threads\n\nGenuine gold zari (thanga-zari) is a masterpiece of precision micro-metallurgy and composite textile chemistry developed to embellish royal robes and temple draperies.\n\nThe manufacturing process began with metallurgical alloying: high-purity silver (98.5%) was cast into solid rods, mechanically hammered, and cold-drawn through a graduating series of pierced sapphire and diamond dies until reduced to a micro-wire finer than a human hair.\n\nThis circular wire was then flattened between mirror-polished chilled steel rollers into a paper-thin micro-ribbon known as badla. The badla ribbon was precision-wound in a tight spiral around a central core yarn of yellow-dyed pure mulberry silk (pattu-nool). Finally, the silver-wound thread was electroplated or gilded in a molten gold bath, producing a luminous, non-tarnishing gold zari filament capable of withstanding the abrasion of weaving shuttles."
    },
    {
        "file": "knowledge/concepts/concept-iyarkai-vanna-nool-natural-botanical-mordanting-and-silk-yarn-dyeing.md",
        "slug": "concept-iyarkai-vanna-nool-natural-botanical-mordanting-and-silk-yarn-dyeing",
        "category": "concept",
        "name_en": "Iyarkai-Vanna-Nool: Botanical Silk Dyeing, Alum Mordanting & Fermented Herbal Vats",
        "name_ta": "\u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0bb5\u0ba3\u0bcd\u0ba3 \u0ba8\u0bc2\u0bb2\u0bcd - \u0bae\u0bc2\u0bb2\u0bbf\u0b95\u0bc8\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd\u0b9a\u0bbe\u0baf\u0bae\u0bbf\u0b9f\u0bc1\u0ba4\u0bb2\u0bcd, \u0baa\u0b9f\u0bbf\u0b95\u0bbe\u0bb0\u0baa\u0bcd \u0baa\u0bbf\u0b9f\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0ba3\u0bcd\u0ba3\u0b9a\u0bcd \u0b9a\u0bc6\u0bb4\u0bc1\u0bae\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Indigenous botanical dyestuff formulations for protein silk fibers: madder (chayaver) crimsons, fermented indigo (avuri) blues, and turmeric golds fixed with potash alum and myrobalan.",
        "summary_ta": "\u0b9a\u0bbe\u0baf\u0bb5\u0bc7\u0bb0\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b9a\u0bbf\u0bb5\u0baa\u0bcd\u0baa\u0bc1, \u0b85\u0bb5\u0bc1\u0bb0\u0bbf \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0ba8\u0bc0\u0bb2\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0b9e\u0bcd\u0b9a\u0bb3\u0bcd-\u0b95\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1 \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b87\u0bb4\u0bc8\u0b95\u0bb3\u0bc1\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0bc8\u0baf\u0bbe\u0ba9 \u0b87\u0baf\u0bb1\u0bcd\u0b95\u0bc8 \u0bb5\u0ba3\u0bcd\u0ba3\u0bae\u0bc7\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bbf\u0b95\u0bbe\u0bb0\u0b9a\u0bcd \u0b9a\u0bbe\u0baf \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Porunarattruppadai 90-95",
            "Siddha Toxicology & Alchemy Treatises",
            "Traditional Dyers Guild Codex"
        ],
        "content": "# Iyarkai-Vanna-Nool: Botanical Silk Dyeing & Mordanting\n\nAncient Tamil dyers mastered the complex biochemistry of bonding organic plant polyphenols and flavonoids to protein-based silk fibroin filaments, producing vibrant, light-fast colors that retained their brilliance for centuries.\n\nRaw degummed silk skeins were first treated in a mordant bath of dissolved potash alum (padikaram) combined with tannic acid extracted from dried myrobalan fruits (kadukkai). This mordanting created chemical coordination complexes on the fiber surface, locking incoming dye molecules into the molecular matrix.\n\nDyers utilized an extensive pharmacopeia of botanical extracts: the root of Chay-root (Oldenlandia umbellata / chayaver) and madder (manjistha) yielded the iconic fiery scarlet and deep crimson (arukku); anaerobic fermentation vats of wild indigo leaves (avuri) yielded deep lapis blues; and infusions of turmeric (manjal), sappanwood, and pomegranate rind produced glorious temple golds."
    },
    {
        "file": "knowledge/institutions/institution-kaikkolar-pattu-saliya-guild-imperial-silk-weavers-guild.md",
        "slug": "institution-kaikkolar-pattu-saliya-guild-imperial-silk-weavers-guild",
        "category": "institution",
        "name_en": "Kaikkolar & Pattu-Saliya Guild: Imperial Chola Royal Silk Weaving Guilds & Tax Charters",
        "name_ta": "\u0b95\u0bc8\u0b95\u0bcd\u0b95\u0bcb\u0bb3\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0bb2\u0bbf\u0baf\u0bb0\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1 - \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b85\u0bb0\u0b9a \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd \u0b95\u0bc1\u0bb4\u0bc1\u0bae\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bbf\u0b9a\u0bcd \u0b9a\u0bb2\u0bc1\u0b95\u0bc8\u0b95\u0bb3\u0bcd",
        "era": "Medieval Chola Era",
        "year_start": 800,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Sovereign merchant-artisan guilds of royal silk weavers (Kaikkolar, Pattu-Saliyar) granted exclusive tax charters, residential quarters, and loom privileges by imperial Chola monarchs.",
        "summary_ta": "\u0b9a\u0bcb\u0bb4\u0baa\u0bcd \u0baa\u0bc7\u0bb0\u0bb0\u0b9a\u0bb0\u0bcd\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0baa\u0bbf\u0bb0\u0ba4\u0bcd\u0baf\u0bc7\u0b95 \u0ba4\u0bb1\u0bbf \u0bb5\u0bb0\u0bbf\u0bb5\u0bbf\u0bb2\u0b95\u0bcd\u0b95\u0bc1\u0b95\u0bb3\u0bcd (\u0ba4\u0bb1\u0bbf \u0b87\u0bb1\u0bc8), \u0b85\u0bb0\u0b9a \u0b86\u0ba4\u0bb0\u0bb5\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0ba9\u0bbf \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd \u0bb5\u0bc0\u0ba4\u0bbf\u0b95\u0bb3\u0bcd \u0baa\u0bc6\u0bb1\u0bcd\u0bb1\u0bc1 \u0b87\u0baf\u0b99\u0bcd\u0b95\u0bbf\u0baf \u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0bb2\u0bbf\u0baf\u0bb0\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bc8\u0b95\u0bcd\u0b95\u0bcb\u0bb3\u0bb0\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1.",
        "sources": [
            "Thanjavur Big Temple Inscriptions",
            "Tirubhuvanam Epigraphs",
            "Kanchipuram Temple Charters"
        ],
        "content": "# Kaikkolar & Pattu-Saliya Guild: Imperial Silk Weavers\n\nDuring the imperial Chola epoch, luxury textile production was organized under powerful collegiate artisan guilds, predominantly the Kaikkolar (Sengunthar) and Pattu-Saliyar corporations.\n\nTemple inscriptions across Thanjavur, Kanchipuram, and Tirubhuvanam document the high social and economic standing of these weaving guilds. Monarchs such as Rajaraja I and Kulothunga III granted the guilds royal charters guaranteeing specific tax exemptions on looms (thari-irai) and dye houses (chaya-vari).\n\nIn exchange, the guilds were bound by sacred covenant to supply the royal palace with fine brocades and furnish temple deities with ceremonial silk canopies, vastrams, and festival banners. Guild assemblies adjudicated internal craft disputes, maintained rigid quality standards for zari purity, and safeguarded trade secrets."
    },
    {
        "file": "knowledge/artifacts/artifact-pattu-koodu-silkworm-cocoon-degumming-and-sericin-dissolution.md",
        "slug": "artifact-pattu-koodu-silkworm-cocoon-degumming-and-sericin-dissolution",
        "category": "artifact",
        "name_en": "Pattu-Koodu: Silkworm Cocoon Degumming, Alkaline Sericin Dissolution & Filament Extraction",
        "name_ta": "\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0bc1 - \u0bb5\u0bc6\u0ba8\u0bcd\u0ba8\u0bc0\u0bb0\u0bcd \u0baa\u0bc1\u0bb4\u0bc1\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0bc1 \u0baa\u0ba4\u0baa\u0bcd\u0baa\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd, \u0b9a\u0bc6\u0bb0\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc2\u0bb2\u0bcd \u0baa\u0bbf\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Biochemical process of softening whole pupal cocoons in boiling soapnut or wood-ash alkaline solutions to dissolve sticky sericin gum, freeing lustrous twin fibroin filaments.",
        "summary_ta": "\u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc2\u0b9f\u0bcd\u0b9f\u0bbf\u0ba9\u0bcd \u0bae\u0bc0\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0b9a\u0bc6\u0bb0\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bc8 \u0ba8\u0bc0\u0b95\u0bcd\u0b95, \u0baa\u0bc2\u0bb5\u0ba8\u0bcd\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0bbe\u0baf\u0bcd \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0b9a\u0bbe\u0bae\u0bcd\u0baa\u0bb2\u0bcd \u0b95\u0bb2\u0ba8\u0bcd\u0ba4 \u0bb5\u0bc6\u0ba8\u0bcd\u0ba8\u0bc0\u0bb0\u0bbf\u0bb2\u0bcd \u0b8a\u0bb1\u0bb5\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1 \u0bae\u0bbf\u0bb0\u0bc1\u0ba4\u0bc1\u0bb5\u0bbe\u0ba9 \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b87\u0bb4\u0bc8\u0b95\u0bb3\u0bc8 \u0bb5\u0bbf\u0b9f\u0bc1\u0bb5\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0b9a\u0bc6\u0baf\u0bb2\u0bcd\u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Siddha Natural Dye & Fiber Texts",
            "Chola Agro-Processing Records",
            "South Indian Silk Monograph 1899"
        ],
        "content": "# Pattu-Koodu: Silkworm Cocoon Degumming & Extraction\n\nThe raw silkworm cocoon (pattu-koodu) consists of two parallel filaments of the structural protein fibroin, bound together by a water-soluble gummy coating of the globular protein sericin. Without removing this gum, the fibers cannot be separated or wound smoothly.\n\nTraditional Tamil sericulturists developed a delicate alkaline bath process: whole cocoons were submerged in earthen copper cauldrons filled with water heated to precisely 80\u201390 degrees Celsius, conditioned with natural plant ashes or wild soapnut (poovanthikottai) extract.\n\nThe mild alkaline environment hydrolyzed and dissolved the gummy sericin without degrading the crystalline fibroin core. Expert artisans stirred the cauldron with a brush of fine twigs, catching the loosened microscopic filament ends and drawing them upward in smooth, continuous, glimmering baves."
    },
    {
        "file": "knowledge/concepts/concept-petni-and-mukkani-structural-warp-densities-in-heavyweight-silks.md",
        "slug": "concept-petni-and-mukkani-structural-warp-densities-in-heavyweight-silks",
        "category": "concept",
        "name_en": "Petni & Mukkani: Structural Warp Densities, Reed Counts & Heavy Drape Physics",
        "name_ta": "\u0baa\u0bc7\u0b9f\u0bcd\u0ba9\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bbe\u0ba3\u0bbf - \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b85\u0b9f\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbe\u0ba9 \u0baa\u0bbe\u0bb5\u0bc1 \u0b87\u0bb4\u0bc8\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0b95\u0ba9\u0baa\u0bb0\u0bbf\u0bae\u0bbe\u0ba3\u0bae\u0bcd",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Warp-joining methodology (petni) and high-density reed counts (mukkani / 100+ ends/inch) producing heavy-drape, crease-resistant Chola silks weighing upwards of 900 grams.",
        "summary_ta": "\u0baa\u0bb4\u0bc8\u0baf \u0baa\u0bbe\u0bb5\u0bc1 \u0ba8\u0bc2\u0bb2\u0bc1\u0b9f\u0ba9\u0bcd \u0baa\u0bc1\u0ba4\u0bbf\u0baf \u0baa\u0bbe\u0bb5\u0bc1 \u0ba8\u0bc2\u0bb2\u0bc8 \u0bae\u0bc1\u0bb1\u0bc1\u0b95\u0bcd\u0b95\u0bbf \u0b87\u0ba3\u0bc8\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bc7\u0b9f\u0bcd\u0ba9\u0bbf \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd 100-\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bb1\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b87\u0bb4\u0bc8\u0baf\u0b9f\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bbf \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b95\u0ba9\u0bae\u0bbe\u0ba9 \u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd\u0b9a\u0bc7\u0bb2\u0bc8 \u0b95\u0b9f\u0bcd\u0b9f\u0bae\u0bc8\u0baa\u0bcd\u0baa\u0bc1.",
        "sources": [
            "Tirubhuvanam Silk Handloom Manuals",
            "Madras Craft Survey 1954",
            "Tamil Lexicon"
        ],
        "content": "# Petni & Mukkani: Structural Warp Densities & Heavy Drape\n\nTraditional Tamil silk sarees from centers like Tirubhuvanam and Kanchipuram are renowned for their extraordinary weight, firm body, and rich drape\u2014distinguishing them from lighter northern or eastern Indian silks.\n\nThis structural density was achieved through the petni technique and high reed count calculations. Petni is the meticulous process of twisting and splicing each individual strand of a new warp to the remaining ends of the previous warp on the loom, a labor-intensive operation involving over 4,000 to 6,000 individual filament splices.\n\nCombined with heavy multi-ply twisted yarns (double-warp and three-ply weft) and tight reed counts exceeding 100 to 120 ends per inch (mukkani densities), the resulting textile possessed remarkable dimensional stability, refusing to crease or wrinkle, and creating a fabric with substantial tactile substance weighing between 800 and 1,000 grams."
    },
    {
        "file": "knowledge/places/place-tirubhuvanam-ancient-silk-weaving-and-zari-brocade-haven.md",
        "slug": "place-tirubhuvanam-ancient-silk-weaving-and-zari-brocade-haven",
        "category": "place",
        "name_en": "Tirubhuvanam: Ancient Chola Silk Weaving, Pure Zari Brocade & Textile Haven",
        "name_ta": "\u0ba4\u0bbf\u0bb0\u0bc1\u0baa\u0bc1\u0bb5\u0ba9\u0bae\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1, \u0ba4\u0b99\u0bcd\u0b95 \u0b9c\u0bb0\u0bbf\u0b95\u0bc8 \u0bb5\u0bc7\u0bb2\u0bc8\u0baa\u0bcd\u0baa\u0bbe\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd \u0ba8\u0b95\u0bb0\u0bcd",
        "era": "Medieval Chola to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Renowned Chola silk-weaving enclave on the Kaveri near Kumbakonam, famous for GI-tagged heavyweight pure silk sarees, intricate golden zari pallus, and seamless petni borders.",
        "summary_ta": "\u0b95\u0bc1\u0bae\u0bcd\u0baa\u0b95\u0bcb\u0ba3\u0bae\u0bcd \u0b85\u0bb0\u0bc1\u0b95\u0bc7 \u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0b95\u0bbe\u0bb2\u0baa\u0bcd \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0ba8\u0bc6\u0b9a\u0bb5\u0bc1 \u0ba8\u0b95\u0bb0\u0bcd; \u0baa\u0bc1\u0bb5\u0bbf\u0b9a\u0bbe\u0bb0\u0bcd \u0b95\u0bc1\u0bb1\u0bbf\u0baf\u0bc0\u0b9f\u0bc1 \u0baa\u0bc6\u0bb1\u0bcd\u0bb1 \u0b95\u0ba9\u0bae\u0bbe\u0ba9 \u0baa\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bc7\u0bb2\u0bc8\u0b95\u0bb3\u0bcd, \u0ba4\u0b99\u0bcd\u0b95 \u0b9c\u0bb0\u0bbf\u0b95\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba8\u0bc6\u0b9a\u0bb5\u0bbe\u0bb3\u0bb0\u0bcd \u0baa\u0ba3\u0bcd\u0baa\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0ba4\u0bcd \u0ba4\u0bb3\u0bae\u0bcd.",
        "sources": [
            "Kampahareswara Temple Inscriptions",
            "Chola Epigraphy",
            "Tirubhuvanam Silk Cooperative Archives"
        ],
        "content": "# Tirubhuvanam: Ancient Silk Weaving Haven\n\nTirubhuvanam, situated on the lush alluvial banks of the Kaveri river adjacent to Kumbakonam, has flourished for over eight centuries as the premier sanctum of imperial Chola silk craftsmanship.\n\nFounded during the reign of Kulothunga Chola III (who consecrated the magnificent Kampahareswara temple), the township was established with dedicated weavers' colonies (saliya-theru). Here, hereditary weaver lineages developed a unique style of heavyweight pure silk weaving characterized by solid contrast korvai borders, radiant 24-karat gold zari threadwork, and distinctive folded diamond pleats.\n\nRecognized with a prestigious Geographical Indication (GI) tag, Tirubhuvanam remains an active, vibrant center where centuries-old pit-looms continue to produce handwoven silks embodying the technical genius, aesthetic beauty, and cultural majesty of ancient Tamil civilization."
    }
]
EDGES = [
    [
        "concept-pattu-nool-thozhil-ancient-tamil-mulberry-sericulture-and-filament-reeling",
        "PRODUCES",
        "artifact-pattu-koodu-silkworm-cocoon-degumming-and-sericin-dissolution",
        "core",
        "Prehistoric to Modern Era",
        "Mulberry sericulture husbandry culminates in the harvest and boiling extraction of whole cocoons.",
        "Chola Agro-Processing Records"
    ],
    [
        "technology-kuzhi-thari-and-adai-ground-pit-loom-and-jacquard-harness-mechanics",
        "EXECUTES",
        "technology-korvai-interlocked-weft-temple-border-weaving-craftsmanship",
        "core",
        "Prehistoric to Modern Era",
        "The earthen pit-loom with dual weaver stations executes the intricate triple-shuttle korvai technique.",
        "Tirubhuvanam Weavers Guild Records"
    ],
    [
        "artifact-thanga-zari-beaten-gold-wrapped-pure-silk-brocade-threads",
        "EMBELLISHES",
        "technology-kuzhi-thari-and-adai-ground-pit-loom-and-jacquard-harness-mechanics",
        "core",
        "Early Medieval to Modern Era",
        "Genuine silver-gold zari filament is woven into rich brocade pallus and temple spires on the pit loom.",
        "South Indian Epigraphy Vol IV"
    ],
    [
        "concept-iyarkai-vanna-nool-natural-botanical-mordanting-and-silk-yarn-dyeing",
        "ENRICHES",
        "concept-pattu-nool-thozhil-ancient-tamil-mulberry-sericulture-and-filament-reeling",
        "core",
        "Prehistoric to Modern Era",
        "Botanical mordanted dyes impart permanent luminous crimsons, blues, and golds to reeled silk filaments.",
        "Porunarattruppadai 90-95"
    ],
    [
        "text-porunarattruppadai-verses-on-gossamer-silk-and-serpent-slough-robes",
        "DOCUMENTS",
        "concept-pattu-nool-thozhil-ancient-tamil-mulberry-sericulture-and-filament-reeling",
        "core",
        "Sangam Era",
        "Porunarattruppadai provides early classical evidence of gossamer-fine Tamil silk filament weaving.",
        "Porunarattruppadai 82-96"
    ],
    [
        "institution-kaikkolar-pattu-saliya-guild-imperial-silk-weavers-guild",
        "GOVERNS",
        "technology-kuzhi-thari-and-adai-ground-pit-loom-and-jacquard-harness-mechanics",
        "core",
        "Medieval Chola Era",
        "The royal silk weavers guild regulated loom standards, quality certifications, and guild apprentice training.",
        "Thanjavur Big Temple Inscriptions"
    ],
    [
        "concept-petni-and-mukkani-structural-warp-densities-in-heavyweight-silks",
        "GOVERNS",
        "technology-korvai-interlocked-weft-temple-border-weaving-craftsmanship",
        "core",
        "Medieval to Modern Era",
        "Warp splicing and ultra-dense reed counts provide the robust structural foundation for solid korvai borders.",
        "Tirubhuvanam Silk Handloom Manuals"
    ],
    [
        "artifact-pattu-koodu-silkworm-cocoon-degumming-and-sericin-dissolution",
        "PROCESSED_INTO",
        "concept-pattu-nool-thozhil-ancient-tamil-mulberry-sericulture-and-filament-reeling",
        "core",
        "Prehistoric to Modern Era",
        "Degummed silk cocoons are reeled into high-tensile, lustrous mulberry silk yarn.",
        "South Indian Silk Monograph 1899"
    ],
    [
        "technology-korvai-interlocked-weft-temple-border-weaving-craftsmanship",
        "MASTERED_AT",
        "place-tirubhuvanam-ancient-silk-weaving-and-zari-brocade-haven",
        "core",
        "Early Medieval to Modern Era",
        "The delicate art of contrast korvai temple border weaving is historically mastered at Tirubhuvanam.",
        "Tirubhuvanam GI Documentation"
    ],
    [
        "institution-kaikkolar-pattu-saliya-guild-imperial-silk-weavers-guild",
        "HEADQUARTERED_AT",
        "place-tirubhuvanam-ancient-silk-weaving-and-zari-brocade-haven",
        "core",
        "Medieval Chola Era",
        "Prominent Chola royal silk weaver guilds maintained major guild assemblies and dye works at Tirubhuvanam.",
        "Kampahareswara Temple Inscriptions"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Silk Sericulture, Mulberry Cultivation & Gold Zari Brocading into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Silk Sericulture, Mulberry Cultivation & Gold Zari Brocading Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
