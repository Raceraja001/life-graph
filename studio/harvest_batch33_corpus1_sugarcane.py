#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Sugarcane Milling, Rotary Crushing & Boiling House Granulation
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
        "file": "knowledge/texts/text-purananuru-392-verses-on-creaking-sugarcane-presses-and-steaming-vats.md",
        "slug": "text-purananuru-392-verses-on-creaking-sugarcane-presses-and-steaming-vats",
        "category": "text",
        "name_en": "Purananuru 392: Classical Sangam Verses on Creaking Sugarcane Presses & Steaming Vats",
        "name_ta": "\u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bc1 392 - \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bc8 \u0b87\u0b9f\u0bbf\u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95 \u0b93\u0ba4\u0bc8, \u0bb5\u0bc6\u0bb2\u0bcd\u0bb2\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8 \u0ba8\u0bb1\u0bc1\u0bae\u0ba3\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd\u0b95\u0bb3\u0bcd",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Classical Sangam verses by Kovan Puthur Thevanar depicting the deafening creak of oxen-driven rotary cane mills and the billowing sweet aroma of boiling jaggery syrup across Kaveri fields.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0bae\u0bb0\u0bc1\u0ba4 \u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1\u0b95\u0bb3\u0bcd \u0b9a\u0bc1\u0bb4\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bc8\u0baf\u0bbf\u0ba9\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0bae\u0bcd \u0bae\u0bc1\u0bb4\u0b95\u0bcd\u0b95 \u0b93\u0b9a\u0bc8\u0baf\u0bc8\u0baf\u0bc1\u0bae\u0bcd, \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bc1\u0bae\u0bcd \u0b87\u0ba9\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bc8\u0baf\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bbf\u0bb5\u0bb0\u0bbf\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bc1\u0bb1\u0ba8\u0bbe\u0ba9\u0bc2\u0bb1\u0bcd\u0bb1\u0bc1\u0baa\u0bcd \u0baa\u0bbe\u0b9f\u0bb2\u0bcd.",
        "sources": [
            "Purananuru 392",
            "Ainkurunuru 65",
            "Perumpanattruppadai 260"
        ],
        "content": "# Purananuru 392: Classical Sangam Verses on Sugarcane Presses\n\nIn Purananuru 392, the Sangam poet Kovan Puthur Thevanar presents an evocative sensory tableau of the agrarian technology and economic prosperity of ancient Tamilakam's riverine heartlands.\n\nThe verse describes how pastoral Marutham villages echoed day and night with the thunderous, rhythmic creaking of rotary sugarcane presses (karumbu-aalai). Heavy bullocks turned the massive stone and wooden grinding mortars, expressing streams of foaming pale-green sucrose juice from thick stalks of cultivated cane (karumbu).\n\nAdjacent to the mills, multi-furnace boiling sheds billowed sweet, fragrant steam as boiling masters (aalai-thatchar) ladled boiling cane syrup across stepping pans, crystalizing golden raw jaggery (achuvellam) that was packed into palm-leaf baskets for inland and trans-oceanic trade."
    },
    {
        "file": "knowledge/concepts/concept-karumbu-aalai-rotary-granite-mortar-and-wooden-pestle-cane-crushers.md",
        "slug": "concept-karumbu-aalai-rotary-granite-mortar-and-wooden-pestle-cane-crushers",
        "category": "concept",
        "name_en": "Karumbu-Aalai: Rotary Granite Mortar & Hardwood Pestle Cane-Crushing Mechanics",
        "name_ta": "\u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bc8 - \u0b89\u0bb0\u0bc1\u0bb3\u0bc8\u0b95\u0bcd \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b86\u0bb2\u0bc8, \u0bae\u0bb0 \u0b89\u0bb0\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1 \u0b9a\u0bc1\u0bb4\u0bb2\u0bcd \u0baa\u0bbf\u0bb4\u0bbf \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Oxen-driven rotary granite mortar and hardwood pestle crushers (karumbu-aalai) exerting immense compressive shear to crush woody cane stalks and express up to 60% juice by weight.",
        "summary_ta": "\u0baa\u0bbf\u0bb0\u0bae\u0bcd\u0bae\u0bbe\u0ba3\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bb2\u0bcd \u0b89\u0bb0\u0bb2\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb2\u0bc1\u0baa\u0bcd\u0baa\u0bc8 \u0bae\u0bb0 \u0b89\u0bb2\u0b95\u0bcd\u0b95\u0bc8 \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1, \u0b8e\u0bb0\u0bc1\u0ba4\u0bc1\u0b95\u0bb3\u0bbf\u0ba9\u0bcd \u0b87\u0bb4\u0bc1\u0bb5\u0bbf\u0b9a\u0bc8\u0baf\u0bbe\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc8 \u0ba8\u0b9a\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0b9a\u0bcd \u0b9a\u0bbe\u0bb1\u0bc1 \u0baa\u0bbf\u0bb4\u0bbf\u0baf\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bbf\u0baf \u0ba4\u0bae\u0bbf\u0bb4\u0bb0\u0bcd \u0b85\u0bb0\u0bc8\u0bb5\u0bc8 \u0b86\u0bb2\u0bc8.",
        "sources": [
            "Purananuru 392",
            "Perumpanattruppadai 262",
            "Tamil Agro-Engineering Monograph 1922"
        ],
        "content": "# Karumbu-Aalai: Rotary Granite Mortar & Pestle Mechanics\n\nThe technological cornerstone of ancient Tamil sugar production was the oxen-powered rotary mortar-and-pestle cane crusher, termed the karumbu-aalai or karumbu-pidzhi-pori.\n\nThe installation centered on a massive cylindrical basin carved from dense granite, sunk into the earth for structural rigidity. Inside rotated an inclined, conical pestle sculpted from heavy, seasoned Iluppai (Madhuca longifolia) or Tamarind heartwood, connected to an extended horizontal wooden sweep arm (kole-maram).\n\nA team of hump-backed bulls or water buffalo hitched to the sweep arm walked in continuous circular tracks. Bundles of stripped sugarcane stalks were hand-fed into the annular gap between the revolving wooden pestle and the stationary granite mortar bowl. The combined rotary rubbing and extreme compressive shear crushed the fibrous cellulose rind, expelling rich juice through a sloped bottom spout into subterranean clay sedimentation jars."
    },
    {
        "file": "knowledge/technologies/technology-aduppu-kottagai-multi-pan-gravity-stepped-juice-clarification-furnaces.md",
        "slug": "technology-aduppu-kottagai-multi-pan-gravity-stepped-juice-clarification-furnaces",
        "category": "technology",
        "name_en": "Aduppu-Kottagai: Multi-Pan Gravity-Stepped Juice Clarification Batteries & Furnaces",
        "name_ta": "\u0b85\u0b9f\u0bc1\u0baa\u0bcd\u0baa\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bcd\u0b9f\u0b95\u0bc8 - \u0baa\u0bb2 \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8 \u0baa\u0b9f\u0bbf\u0ba8\u0bbf\u0bb2\u0bc8 \u0b9a\u0bbe\u0bb1\u0bc1 \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bc1\u0bae\u0bcd \u0b89\u0bb2\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0baa\u0bcd \u0baa\u0b95\u0bbf\u0bb0\u0bcd\u0bb5\u0bc1",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Thermal engineering of multi-tier open furnace batteries (aduppu-kottagai) fueled by dried cane bagasse (chakkai), boiling juice across sequential pans of increasing brix density.",
        "summary_ta": "\u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0b95\u0bcd\u0b95\u0bc8\u0baf\u0bc8 (\u0b9a\u0b95\u0bcd\u0b95\u0bc8) \u0b8e\u0bb0\u0bbf\u0baa\u0bca\u0bb0\u0bc1\u0bb3\u0bbe\u0b95\u0b95\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f\u0bc1, \u0bae\u0bc2\u0ba9\u0bcd\u0bb1\u0bc1 \u0bae\u0bc1\u0ba4\u0bb2\u0bcd \u0ba8\u0bbe\u0ba9\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0bb2\u0bc8 \u0bb5\u0bc6\u0ba3\u0bcd\u0b95\u0bb2/\u0ba4\u0bbe\u0bae\u0bbf\u0bb0\u0b95\u0bcd \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8\u0b95\u0bb3\u0bbf\u0bb2\u0bcd \u0bb5\u0bc6\u0baa\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bc8\u0baa\u0bcd \u0baa\u0b95\u0bbf\u0bb0\u0bcd\u0ba8\u0bcd\u0ba4\u0bc1 \u0b9a\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8 \u0b85\u0b9f\u0bb0\u0bcd \u0baa\u0bbe\u0b95\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b89\u0bb2\u0bc8 \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd.",
        "sources": [
            "Ainkurunuru 65",
            "Chola Village Epigraphs",
            "Traditional Jaggery Technology Studies"
        ],
        "content": "# Aduppu-Kottagai: Multi-Pan Juice Clarification Furnaces\n\nConverting perishable raw cane juice into stable solid sugar required high-efficiency thermal evaporation and crystallization facilities known as the aduppu-kottagai.\n\nTamil boiling masters constructed elongate, subterranean trench hearths spanned by three to four cascading, shallow, hand-hammered copper or bell-metal boiling cauldrons (kopari or thula-kopparai). The furnace draft was engineered so that hot flue gases from a single combustion chamber flowed beneath all pans in sequence before exiting a tall clay chimney stack.\n\nThe furnace achieved complete circular energy autonomy: sun-dried fibrous crushed cane pulp (bagasse or karumbu-chakkai) was burned as the primary fuel, eliminating deforestation. Raw juice entered the highest, cooler pan for initial warming and scum separation, before being ladled down to successively hotter pans, boiling down into thick viscous golden mass (paagu)."
    },
    {
        "file": "knowledge/artifacts/artifact-achuvellam-and-kopari-solid-jaggery-molds-and-cast-copper-evaporation-pans.md",
        "slug": "artifact-achuvellam-and-kopari-solid-jaggery-molds-and-cast-copper-evaporation-pans",
        "category": "artifact",
        "name_en": "Achuvellam & Kopari: Solid Jaggery Casting Molds & Hammered Copper Evaporation Pans",
        "name_ta": "\u0b85\u0b9a\u0bcd\u0b9a\u0bc1\u0bb5\u0bc6\u0bb2\u0bcd\u0bb2\u0bae\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8 - \u0bb5\u0bc6\u0bb2\u0bcd\u0bb2 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb0 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0ba4\u0bbe\u0bae\u0bbf\u0bb0\u0b95\u0bcd \u0b95\u0bbe\u0baf\u0bcd\u0b9a\u0bcd\u0b9a\u0bc1 \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Deep hand-hammered copper evaporation pans (kopari) and carved teak block casting molds (achuvellam-achchu) that formed hardened, shelf-stable pyramidal blocks of jaggery.",
        "summary_ta": "\u0b85\u0b95\u0ba9\u0bcd\u0bb1 \u0ba4\u0bbe\u0bae\u0bbf\u0bb0\u0b95\u0bcd \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bb5\u0bc6\u0bb2\u0bcd\u0bb2\u0baa\u0bcd \u0baa\u0bbe\u0b95\u0bc8 \u0b8a\u0bb1\u0bcd\u0bb1\u0bbf \u0ba4\u0bbf\u0b9f\u0bae\u0bbe\u0ba9 \u0b95\u0bc2\u0bae\u0bcd\u0baa\u0bc1/\u0b95\u0b9f\u0bcd\u0b9f\u0bbf\u0b95\u0bb3\u0bbe\u0b95 \u0bb5\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba4\u0bc7\u0b95\u0bcd\u0b95\u0bc1 \u0bae\u0bb0 \u0b85\u0b9a\u0bcd\u0b9a\u0bc1 \u0bb5\u0bbe\u0bb0\u0bcd\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Kongu Nadu Epigraphs",
            "Porunarattruppadai 195",
            "South Indian Agricultural Implements"
        ],
        "content": "# Achuvellam & Kopari: Jaggery Molds & Evaporation Pans\n\nThe physical crystallization and commercial packaging of Tamil jaggery relied upon specialized metallurgical and woodworking artifacts: the kopari pan and the achuvellam-achchu.\n\nThe kopari was a wide, shallow, heavy-gauge copper cauldron measuring up to five feet in diameter, beaten from high-purity sheet copper by brazier guilds. Copper provided rapid, uniform thermal conductivity, preventing localized burning and caramelization of delicate sucrose sugars during the final critical boiling stages.\n\nWhen the syrup reached the strike-point (118-120\u00b0C, tested by dropping a pellet of syrup into cold water until it formed a firm, malleable ball), it was scooped into wooden cooling troughs and vigorously aerated with wooden paddles. The cooling mass was swiftly poured into oiled wooden matrix blocks carved with hundreds of conical or cubical cavities (achuvellam), solidifying into dense, golden-amber crystalline jaggery bricks impervious to spoilage during long maritime transport."
    },
    {
        "file": "knowledge/concepts/concept-vendai-mucilage-and-lime-natural-cane-juice-defecation-chemistry.md",
        "slug": "concept-vendai-mucilage-and-lime-natural-cane-juice-defecation-chemistry",
        "category": "concept",
        "name_en": "Vendai-Mucilage & Lime: Natural Cane-Juice Defecation & Clarification Chemistry",
        "name_ta": "\u0bb5\u0bc6\u0ba3\u0bcd\u0b9f\u0bc8 \u0baa\u0bbf\u0b9a\u0bbf\u0ba9\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 - \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0bb1\u0bc1 \u0b87\u0baf\u0bb2\u0bcd\u0baa\u0bc1\u0ba8\u0bbf\u0bb2\u0bc8 \u0ba4\u0bc2\u0baf\u0bcd\u0bae\u0bc8\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bb2\u0bcd \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Organic bio-chemical clarification using wild okra mucilage (vendai-kolapazham) and slaked oyster shell lime to flocculate suspended colloidal proteins, gums, and coloring polyphenols.",
        "summary_ta": "\u0bb5\u0bc6\u0ba3\u0bcd\u0b9f\u0bc8\u0b95\u0bcd \u0b95\u0bc2\u0bb4\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bbf\u0baa\u0bcd\u0baa\u0bbf\u0b9a\u0bcd \u0b9a\u0bc1\u0ba3\u0bcd\u0ba3\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0bc1 \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0b9a\u0bcd \u0b9a\u0bbe\u0bb1\u0bcd\u0bb1\u0bbf\u0ba9\u0bcd \u0b85\u0bae\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0ba9\u0bcd\u0bae\u0bc8\u0baf\u0bc8 \u0ba8\u0b9f\u0bc1\u0ba8\u0bbf\u0bb2\u0bc8\u0baf\u0bbe\u0b95\u0bcd\u0b95\u0bbf, \u0bae\u0bbe\u0b9a\u0bc1\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0bb0\u0bc8\u0b95\u0bb3\u0bc8\u0baf\u0bc1\u0bae\u0bcd \u0ba4\u0bbf\u0bb0\u0b9f\u0bcd\u0b9f\u0bbf \u0ba8\u0bc0\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0bbe\u0bb0\u0bae\u0bcd\u0baa\u0bb0\u0bbf\u0baf \u0bb5\u0bc7\u0ba4\u0bbf\u0baf\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Agastya Siddha Chemistry Treatises",
            "Traditional Jaggery Making Guild Lore",
            "Purananuru 392"
        ],
        "content": "# Vendai-Mucilage & Lime: Natural Juice Clarification Chemistry\n\nRaw sugarcane juice contains colloidal impurities, acidic proteins, waxes, chlorophyll, and dark tannins that would yield bitter, gummy, dark-black jaggery if boiled unpurified. Ancient Tamil boiling masters perfected a natural chemical defecation process without synthetic additives.\n\nAs the raw juice reached 80\u00b0C in the first boiling pan, small amounts of slaked marine shell lime (sunnambu / calcium hydroxide) were stirred into the vat. This neutralized natural organic acids, preventing sucrose inversion into non-crystallizing reducing sugars.\n\nConcurrently, an aqueous extract of crushed wild okra stems and bark (vendai-kolapazham or Hibiscus ficulneus mucilage) was introduced. The long-chain natural polysaccharides formed an electro-chemical net that coagulated and bound suspended colloidal impurities into a buoyant, spongy blanket of scum (azhukku). The boiler master swept this foam from the surface with perforated bamboo skimmers, leaving crystalline, light-amber clarified syrup."
    },
    {
        "file": "knowledge/institutions/institution-karumbu-velan-kudi-guild-of-sugar-millers-and-boiling-house-masters.md",
        "slug": "institution-karumbu-velan-kudi-guild-of-sugar-millers-and-boiling-house-masters",
        "category": "institution",
        "name_en": "Karumbu-Velan-Kudi: Guild of Sugar Millers & Boiling House Corporations",
        "name_ta": "\u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0b95\u0bc1\u0b9f\u0bbf - \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bc8 \u0b89\u0bb0\u0bbf\u0bae\u0bc8\u0baf\u0bbe\u0bb3\u0bb0\u0bcd\u0b95\u0bb3\u0bcd \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0bb5\u0ba3\u0bbf\u0b95\u0baa\u0bcd \u0baa\u0bc6\u0bb0\u0bc1\u0b99\u0bcd\u0b95\u0bc1\u0bb4\u0bc1",
        "era": "Early Historic to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Sovereign agrarian artisan corporation governing sugarcane cultivation, communal rotary mill scheduling, fuel rights, and sugar tax charters (aalai-vari) in the Kaveri and Kongu basins.",
        "summary_ta": "\u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bc8\u0b95\u0bb3\u0bcd \u0b87\u0baf\u0b95\u0bcd\u0b95\u0bae\u0bcd, \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf\u0ba4\u0bcd \u0ba4\u0bb0\u0bae\u0bcd, \u0b95\u0bca\u0baa\u0bcd\u0baa\u0bb0\u0bc8 \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b85\u0bb0\u0b9a \u0b86\u0bb2\u0bc8 \u0bb5\u0bb0\u0bbf\u0b95\u0bb3\u0bc8 (\u0b86\u0bb2\u0bc8 \u0bb5\u0bb0\u0bbf) \u0ba8\u0bbf\u0bb0\u0bcd\u0bb5\u0b95\u0bbf\u0ba4\u0bcd\u0ba4 \u0b9a\u0bcb\u0bb4\u0bb0\u0bcd-\u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bbf\u0bb2\u0bcd\u0b9f\u0bc1.",
        "sources": [
            "Namakkal Inscriptions",
            "Thiruchengodu Epigraphs",
            "Chola Revenue Epigraphs"
        ],
        "content": "# Karumbu-Velan-Kudi: Sugar Millers Guild\n\nThe intensive capital investment, coordinated labor, and specialized seasonal timing required for sugarcane harvesting and milling led to the emergence of the Karumbu-Velan-Kudi corporations across the Kaveri and Amaravathi river basins.\n\nTemple inscriptions from Namakkal, Mohanur, and Tiruchengode record extensive state charters granted to these sugar masters. Because cut sugarcane rapidly ferments within 24 hours of cutting, the guild operated a centralized rotational milling calendar: coordinating teams of harvesters, draft bullock supply, bagasse drying fields, and boiling furnace shifts around the clock.\n\nThe guild negotiated collective export contracts with international maritime merchant bodies like the Ayyavole-500 and Manigramam, and paid royal milling excises (aalai-ayam and aalai-vari) in exchange for exclusive milling monopolies across designated river nadus."
    },
    {
        "file": "knowledge/concepts/concept-panang-kalkandu-and-sarkkarai-fine-sucrose-crystallization-mechanics.md",
        "slug": "concept-panang-kalkandu-and-sarkkarai-fine-sucrose-crystallization-mechanics",
        "category": "concept",
        "name_en": "Panang-Kalkandu & Sarkkarai: Fine Sucrose Crystallization & Sugar Candy Lapidary",
        "name_ta": "\u0baa\u0ba9\u0b99\u0bcd\u0b95\u0bb1\u0bcd\u0b95\u0ba3\u0bcd\u0b9f\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 - \u0baa\u0b9f\u0bbf\u0b95 \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0bb5\u0bb3\u0bb0\u0bcd\u0b9a\u0bcd\u0b9a\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bb1\u0bcd\u0b95\u0ba3\u0bcd\u0b9f\u0bc1 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0ba8\u0bc1\u0b9f\u0bcd\u0baa\u0bae\u0bcd",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Secondary crystallization science creating translucent sugar rock crystals (kalkandu / sarkkarai) by slow evaporative cooling of super-saturated syrup seeded with cotton threads in clay jars.",
        "summary_ta": "\u0b85\u0ba4\u0bbf\u0b9a\u0bc6\u0bb1\u0bbf\u0bb5\u0bc2\u0b9f\u0bcd\u0b9f\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0baa\u0ba9\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0b95\u0bbf\u0bb2\u0bcd \u0ba8\u0bc2\u0bb2\u0bcd\u0b95\u0bb3\u0bc8\u0ba4\u0bcd \u0ba4\u0bca\u0b99\u0bcd\u0b95\u0bb5\u0bbf\u0b9f\u0bcd\u0b9f\u0bc1, \u0bae\u0bc6\u0ba4\u0bc1\u0bb5\u0bbe\u0ba9 \u0b95\u0bc1\u0bb3\u0bbf\u0bb0\u0bcd\u0bb5\u0bbf\u0ba4\u0bcd\u0ba4\u0bb2\u0bcd \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0b92\u0bb3\u0bbf\u0baa\u0bc1\u0b95\u0bc1\u0bae\u0bcd \u0baa\u0b9f\u0bbf\u0b95\u0b95\u0bcd \u0b95\u0bb1\u0bcd\u0b95\u0ba3\u0bcd\u0b9f\u0bc1\u0b95\u0bb3\u0bc8 \u0b89\u0bb0\u0bc1\u0bb5\u0bbe\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0b87\u0baf\u0bb1\u0bcd\u0baa\u0bbf\u0baf\u0bb2\u0bcd \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Agastya Siddha Gunavagadam",
            "Silappadikaram 5.30",
            "Sanskrit-Tamil Medical Glosses"
        ],
        "content": "# Panang-Kalkandu & Sarkkarai: Fine Sucrose Crystallization\n\nBeyond raw solid jaggery, ancient Tamil culinary and Siddha pharmacology mastered the refined art of high-purity sucrose crystallization, producing crystal candy (kalkandu) and loose sugar (sarkkarai).\n\nTo initiate crystallization, clarified cane or palmyra syrup was concentrated past normal jaggery strike temperature and poured into unglazed porous terracotta amphorae (kalkandu-paanai). Clean cotton threads or bamboo slivers were suspended vertically inside the pots to serve as crystalline nucleation seeds.\n\nThe sealed jars were buried in insulated grain chaff or cool subterranean chambers for 40 to 60 days. Slow, undisturbed cooling induced pure sucrose molecules to precipitate out of the mother liquor and assemble into large, faceted, translucent quartz-like sugar crystals clinging to the strings. The remaining molasses was drained off, yielding medicinal-grade rock candy celebrated in classical Siddha therapeutics."
    },
    {
        "file": "knowledge/artifacts/artifact-karumbu-pidzhi-pori-gear-driven-iron-and-hardwood-roller-crushers.md",
        "slug": "artifact-karumbu-pidzhi-pori-gear-driven-iron-and-hardwood-roller-crushers",
        "category": "artifact",
        "name_en": "Karumbu-Pidhi-Pori: Intermeshed Two-Roller and Three-Roller Hardwood Milling Gear",
        "name_ta": "\u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0baa\u0bbf\u0bb4\u0bbf \u0baa\u0bca\u0bb1\u0bbf - \u0baa\u0bb1\u0bcd\u0b9a\u0b95\u0bcd\u0b95\u0bb0 \u0bae\u0bb0 \u0b89\u0bb0\u0bc1\u0bb3\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b87\u0bb0\u0bc1\u0bae\u0bc1\u0ba9\u0bc8 \u0b85\u0bb4\u0bc1\u0ba4\u0bcd\u0ba4 \u0b85\u0bb0\u0bc8\u0bb5\u0bc8 \u0b8e\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0bae\u0bcd",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Vertical intermeshed twin and triple-roller wooden gear mills (karumbu-pidzhi-pori) utilizing helical hardwood gear teeth carved directly into Iluppai rollers to continuously draw in cane.",
        "summary_ta": "\u0b87\u0ba3\u0bc8\u0ba8\u0bcd\u0ba4 \u0baa\u0bb1\u0bcd\u0b9a\u0b95\u0bcd\u0b95\u0bb0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b95\u0bca\u0ba3\u0bcd\u0b9f \u0b87\u0bb0\u0ba3\u0bcd\u0b9f\u0bc1 \u0b85\u0bb2\u0bcd\u0bb2\u0ba4\u0bc1 \u0bae\u0bc2\u0ba9\u0bcd\u0bb1\u0bc1 \u0bae\u0bb0 \u0b89\u0bb0\u0bc1\u0bb3\u0bc8\u0b95\u0bb3\u0bcd \u0b9a\u0bc1\u0bb4\u0ba9\u0bcd\u0bb1\u0bc1, \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc8 \u0b89\u0bb3\u0bcd\u0bb5\u0bbe\u0b99\u0bcd\u0b95\u0bbf \u0b92\u0bb0\u0bc7 \u0b9a\u0bc1\u0bb1\u0bcd\u0bb1\u0bbf\u0bb2\u0bcd \u0b9a\u0bbe\u0bb1\u0bcd\u0bb1\u0bc8\u0baa\u0bcd \u0baa\u0bbf\u0bb4\u0bbf\u0ba8\u0bcd\u0ba4\u0bc6\u0b9f\u0bc1\u0b95\u0bcd\u0b95\u0bc1\u0bae\u0bcd \u0bae\u0bc7\u0bae\u0bcd\u0baa\u0b9f\u0bcd\u0b9f \u0b8e\u0ba8\u0bcd\u0ba4\u0bbf\u0bb0\u0baa\u0bcd \u0baa\u0bca\u0bb1\u0bbf\u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Chola Mechanical Artifacts",
            "Epigraphia Carnatica Vol IX",
            "Indian Journal of History of Science"
        ],
        "content": "# Karumbu-Pidhi-Pori: Intermeshed Roller Milling Gear\n\nDuring the medieval Chola epoch, Tamil mechanical engineering advanced from simple mortar-and-pestle crushers to dual and triple vertical roller mills, known as the karumbu-pidzhi-pori.\n\nThe machine consisted of two or three upright cylindrical rollers turned from rock-hard, fine-grained Iluppai or Rosewood, mounted in a rigid timber frame. At the top of each roller, master carpenters carved integrated wooden spur gears or helical intermeshing teeth.\n\nWhen oxen revolved the main drive shaft, the interlocked teeth synchronized the counter-rotation of adjacent rollers at high torque. A cane feeder pressed whole bundles of stalks between the rollers, which gripped and flattened the cane through a calibrated pinch clearance. This continuous-feed roller geometry nearly doubled juice throughput per bullock-hour and drastically reduced operator labor."
    },
    {
        "file": "knowledge/concepts/concept-kaveri-alluvial-cane-husbandry-and-trench-ratooning-methods.md",
        "slug": "concept-kaveri-alluvial-cane-husbandry-and-trench-ratooning-methods",
        "category": "concept",
        "name_en": "Kaveri Alluvial Cane Husbandry: Deep-Trench Planting, Ratooning & Propping Agronomy",
        "name_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0bb5\u0ba3\u0bcd\u0b9f\u0bb2\u0bcd \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd\u0bae\u0bc8 - \u0b86\u0bb4\u0bcd\u0b95\u0bcd\u0b95\u0bbe\u0bb2\u0bcd \u0ba8\u0b9f\u0bb5\u0bc1, \u0bae\u0bb1\u0bc1\u0ba4\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0bae\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0b9f\u0bcd\u0b9f\u0bc1 \u0bae\u0bc1\u0bb1\u0bc8",
        "era": "Prehistoric to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Ancient agrarian agronomy of sugarcane: deep-furrow silt planting (aazh-kaal), bamboo-pole propping against cyclone winds, and multi-year rootstock ratooning (maruthaambu).",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0bb5\u0b9f\u0bbf\u0ba8\u0bbf\u0bb2\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b86\u0bb4\u0bae\u0bbe\u0ba9 \u0baa\u0bbe\u0ba4\u0bcd\u0ba4\u0bbf\u0b95\u0bb3\u0bcd \u0b85\u0bae\u0bc8\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bc2\u0b99\u0bcd\u0b95\u0bbf\u0bb2\u0bcd \u0b95\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bb3\u0bbe\u0bb2\u0bcd \u0bae\u0bc1\u0b9f\u0bcd\u0b9f\u0bc1\u0b95\u0bcd \u0b95\u0bca\u0b9f\u0bc1\u0ba4\u0bcd\u0ba4\u0bc1, \u0bae\u0bb1\u0bc1\u0ba4\u0bbe\u0bae\u0bcd\u0baa\u0bc1 \u0bae\u0bc2\u0bb2\u0bae\u0bcd \u0baa\u0bb2 \u0baa\u0bb0\u0bc1\u0bb5\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0ba4\u0bca\u0b9f\u0bb0\u0bcd \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1 \u0b85\u0bb1\u0bc1\u0bb5\u0b9f\u0bc8 \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0bc1\u0bae\u0bcd \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd\u0bae\u0bc8 \u0bae\u0bc1\u0bb1\u0bc8.",
        "sources": [
            "Ainkurunuru 65",
            "Tirumandiram Agro Verses",
            "Kaveri Delta Agricultural Folklore"
        ],
        "content": "# Kaveri Alluvial Cane Husbandry & Ratooning\n\nAncient Tamil agricultural treatises recognized sugarcane (Saccharum officinarum) as a soil-exhausting crop demanding exceptional soil fertility, copious irrigation, and advanced crop management.\n\nIn the rich silts of the Kaveri and Amaravathi riverbanks, farmers excavated deep parallel trenches (aazh-kaal). Mature cane setts with two to three viable buds were planted horizontally in the trenches and buried under composted cattle manure and river silt.\n\nAs stalks grew to heights of 10 to 14 feet, farmers bundled adjacent stalks together and lashed them to long bamboo poles (karumbu-kattu / propping) to prevent storm lodging during the north-east monsoon. After harvest, the root crowns were carefully tended in the soil to sprout second and third-year ratoon crops (maruthaambu), maintaining sustained sugar production across multi-year cycles."
    },
    {
        "file": "knowledge/places/place-mohanur-ancient-kaveri-sugarcane-milling-haven.md",
        "slug": "place-mohanur-ancient-kaveri-sugarcane-milling-haven",
        "category": "place",
        "name_en": "Mohanur: Ancient Kaveri Sugarcane Milling, Jaggery Granulation & Kongu Haven",
        "name_ta": "\u0bae\u0bcb\u0b95\u0ba9\u0bc2\u0bb0\u0bcd - \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bc8, \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1 \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0ba8\u0b95\u0bb0\u0bcd",
        "era": "Early Historic to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Celebrated riparian agro-industrial settlement on the northern bank of the Kaveri in Namakkal district, famed across Tamil history as the premier heartland of sugarcane plantations and boiling houses.",
        "summary_ta": "\u0b95\u0bbe\u0bb5\u0bbf\u0bb0\u0bbf \u0ba8\u0ba4\u0bbf\u0b95\u0bcd\u0b95\u0bb0\u0bc8\u0baf\u0bbf\u0bb2\u0bcd \u0b85\u0bae\u0bc8\u0ba8\u0bcd\u0ba4\u0bc1\u0bb3\u0bcd\u0bb3 \u0baa\u0ba3\u0bcd\u0b9f\u0bc8\u0baf \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bbe\u0bb2\u0bc8 \u0ba8\u0b95\u0bb0\u0bae\u0bcd; \u0bb5\u0bb3\u0bae\u0bbe\u0ba9 \u0b95\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0ba4\u0bcd \u0ba4\u0bcb\u0b9f\u0bcd\u0b9f\u0b99\u0bcd\u0b95\u0bb3\u0bcd, \u0ba8\u0bbe\u0b9f\u0bcd\u0b9f\u0bc1\u0b9a\u0bcd \u0b9a\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0bb0\u0bc8 \u0b89\u0bb1\u0bcd\u0baa\u0ba4\u0bcd\u0ba4\u0bbf \u0bae\u0bb1\u0bcd\u0bb1\u0bc1\u0bae\u0bcd \u0b95\u0bca\u0b99\u0bcd\u0b95\u0bc1-\u0b9a\u0bcb\u0bb4\u0bb0\u0bcd \u0bb5\u0bc7\u0bb3\u0bbe\u0ba3\u0bcd \u0bb5\u0ba3\u0bbf\u0b95\u0baa\u0bcd \u0baa\u0bc1\u0b95\u0bb2\u0bbf\u0b9f\u0bae\u0bcd.",
        "sources": [
            "Mohanur Temple Inscriptions",
            "Namakkal Taluk Epigraphs",
            "Madras District Gazetteers"
        ],
        "content": "# Mohanur: Ancient Sugarcane Milling Haven\n\nMohanur, situated on the sacred southern curve of the Kaveri river in the historic Kongu country (present-day Namakkal district), has flourished for over two millennia as the capital of Tamil sugarcane milling and jaggery production.\n\nFed by the perennial, silt-laden waters of the Kaveri and extensive network of anicuts, the alluvial floodplains surrounding Mohanur provided ideal conditions for cultivating prized sweet sugarcane varieties. Historical records and archaeological remnants attest to hundreds of rotary stone crushers and brick boiling batteries lining the riverbank.\n\nMohanur's golden jaggery blocks and rock crystal candies were transported down the Kaveri on coracles (parisal) and ox carts to the coastal emporia of Kaveripoompattinam and Nagapattinam, cementing its reputation as the sweet granary of Tamil civilization."
    }
]
EDGES = [
    [
        "concept-karumbu-aalai-rotary-granite-mortar-and-wooden-pestle-cane-crushers",
        "EXTRACTS",
        "concept-kaveri-alluvial-cane-husbandry-and-trench-ratooning-methods",
        "core",
        "Prehistoric to Modern Era",
        "Oxen-driven rotary granite crushers extract sucrose juice from Kaveri alluvial sugarcane stalks.",
        "Purananuru 392"
    ],
    [
        "concept-karumbu-aalai-rotary-granite-mortar-and-wooden-pestle-cane-crushers",
        "SUPPLIES",
        "technology-aduppu-kottagai-multi-pan-gravity-stepped-juice-clarification-furnaces",
        "core",
        "Prehistoric to Modern Era",
        "Freshly expressed cane juice is piped or channeled into the multi-pan boiling house batteries.",
        "Ainkurunuru 65"
    ],
    [
        "technology-aduppu-kottagai-multi-pan-gravity-stepped-juice-clarification-furnaces",
        "UTILIZES",
        "artifact-achuvellam-and-kopari-solid-jaggery-molds-and-cast-copper-evaporation-pans",
        "core",
        "Prehistoric to Modern Era",
        "Multi-pan boiling furnaces utilize deep copper evaporation pans and wooden matrix molds.",
        "Traditional Jaggery Technology"
    ],
    [
        "concept-vendai-mucilage-and-lime-natural-cane-juice-defecation-chemistry",
        "PURIFIES",
        "technology-aduppu-kottagai-multi-pan-gravity-stepped-juice-clarification-furnaces",
        "core",
        "Prehistoric to Modern Era",
        "Natural okra mucilage and lime clarify boiling cane syrup by coagulating colloidal impurities.",
        "Agastya Siddha Chemistry"
    ],
    [
        "text-purananuru-392-verses-on-creaking-sugarcane-presses-and-steaming-vats",
        "DOCUMENTS",
        "concept-karumbu-aalai-rotary-granite-mortar-and-wooden-pestle-cane-crushers",
        "core",
        "Sangam Era",
        "Purananuru 392 provides classical literary documentation of creaking rotary sugarcane presses.",
        "Purananuru 392"
    ],
    [
        "institution-karumbu-velan-kudi-guild-of-sugar-millers-and-boiling-house-masters",
        "GOVERNS",
        "technology-aduppu-kottagai-multi-pan-gravity-stepped-juice-clarification-furnaces",
        "core",
        "Early Historic to Medieval Era",
        "The sugar millers guild regulated boiling house operations, seasonal schedules, and product quality.",
        "Namakkal Inscriptions"
    ],
    [
        "concept-panang-kalkandu-and-sarkkarai-fine-sucrose-crystallization-mechanics",
        "REFINES",
        "artifact-achuvellam-and-kopari-solid-jaggery-molds-and-cast-copper-evaporation-pans",
        "core",
        "Prehistoric to Modern Era",
        "Slow secondary evaporative crystallization refines concentrated boiling syrup into rock sugar crystals.",
        "Silappadikaram 5.30"
    ],
    [
        "artifact-karumbu-pidzhi-pori-gear-driven-iron-and-hardwood-roller-crushers",
        "ENHANCES",
        "concept-karumbu-aalai-rotary-granite-mortar-and-wooden-pestle-cane-crushers",
        "core",
        "Early Medieval to Modern Era",
        "Intermeshed gear-driven wooden roller mills enhanced extraction throughput over single mortar crushers.",
        "Chola Mechanical Artifacts"
    ],
    [
        "technology-aduppu-kottagai-multi-pan-gravity-stepped-juice-clarification-furnaces",
        "OPERATED_AT",
        "place-mohanur-ancient-kaveri-sugarcane-milling-haven",
        "core",
        "Early Historic to Modern Era",
        "Multi-pan boiling batteries and evaporation furnaces lined the riverbanks of Mohanur.",
        "Mohanur Temple Inscriptions"
    ],
    [
        "institution-karumbu-velan-kudi-guild-of-sugar-millers-and-boiling-house-masters",
        "ANCHORED_AT",
        "place-mohanur-ancient-kaveri-sugarcane-milling-haven",
        "core",
        "Early Historic to Medieval Era",
        "The collegiate guild of master sugarcane millers maintained major assemblies and granaries at Mohanur.",
        "Kongu Nadu Epigraphs"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Sugarcane Milling, Rotary Crushing & Boiling House Granulation into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Sugarcane Milling, Rotary Crushing & Boiling House Granulation Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
