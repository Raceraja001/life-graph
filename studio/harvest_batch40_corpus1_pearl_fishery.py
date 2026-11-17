#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Pearl Fishery Oyster Bed Apnea Diving, Marine Benthic Ecology & Parathavar Guild
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
        "file": "knowledge/texts/text-maduraikanchi-and-periplus-on-korkai-pandya-pearl-fishery-flotillas.md",
        "slug": "text-maduraikanchi-and-periplus-on-korkai-pandya-pearl-fishery-flotillas",
        "category": "text",
        "name_en": "Maduraikanchi & Periplus: Sangam & Greco-Roman Accounts of Korkai Pearl Divers and Pandya Flotillas",
        "name_ta": "மதுரைக்காஞ்சி மற்றும் பெரிப்ளஸ் - கொற்கைப் பாண்டி நாட்டு முத்துக்குளிப்புத் துறைமுகக் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Classical Sangam accounts in Maduraikanchi and the Greco-Roman Periplus of the Erythraean Sea documenting the massive royal pearl-diving flotillas of the Pandyan kingdom at Korkai and the Gulf of Mannar, describing thousands of apnea divers, armed shark-binding priests, and global pearl auctions.",
        "summary_ta": "மதுரைக்காஞ்சி மற்றும் பெரிப்ளஸ் குறிப்புகளில் மன்னார் வளைகுடா மற்றும் கொற்கைத் துறைமுகத்தில் பாண்டிய மன்னரின் ஆயிரக்கணக்கான மூச்சு அடக்கு முத்துக்குளிப்பாளர்கள், கடல்கட்டி சுறா மந்திரக் காவலர்கள் மற்றும் சர்வதேச முத்து சந்தைகள்.",
        "sources": [
            "Maduraikanchi (Pattuppattu Anthology)",
            "Periplus of the Erythraean Sea",
            "Ptolemy's Geography",
            "Akananuru 27"
        ],
        "content": "# Maduraikanchi & Periplus: Korkai Pearl Flotillas\n\nBoth classical Tamil poetry and contemporary Greco-Roman maritime manuals document the extraordinary scale of the Pandyan pearl fisheries in the Gulf of Mannar:\n\n> *\"In Korkai where great white waves shatter upon the shore, divers leap into the roaring dark ocean, carrying stone sinkers, and bring up shining pearls from the deep beds to fill the royal treasuries of the victorious Chezhiyan king...\"* (Maduraikanchi 134–144)\n\nThe *Periplus of the Erythraean Sea* (1st century CE, §59) confirms:\n> *\"Beyond the port of Bakare lies the country of Pandion... Here are the fisheries for pearls, worked by condemned criminals and hereditary divers; Korkai (Colchoi) is the emporium for this trade, where the pearls are washed, pierced, and graded for the Roman Empire...\"*\n\nThe Pandyan monarchy derived immense prestige and customs revenues from this monopolistic fishery, financing continental armies and importing Mediterranean wine, Roman gold aurei, and Arabian thoroughbred horses."
    },
    {
        "file": "knowledge/concepts/concept-pinctada-radiata-pearl-oyster-biology-and-gulf-of-mannar-shoal-ecology.md",
        "slug": "concept-pinctada-radiata-pearl-oyster-biology-and-gulf-of-mannar-shoal-ecology",
        "category": "concept",
        "name_en": "Pinctada Radiata Oyster Biology: Nacre Secretion, Calcareous Bed Formations & Gulf of Mannar Ecology",
        "name_ta": "முத்துக் சிப்பி உடற்கூறியல் - முத்துச்சிப்பி கால்சியம் படிவு மற்றும் மன்னார் வளைகுடா பவளப்பாறைச் சூழலியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Marine biology and benthic ecology of the Persian-Gulf/Mannar pearl oyster (Pinctada radiata and Pinctada fucata): mantle epithelial nacre secretion forming aragonite platelets around micro-irritants, benthic calcareous shoal reef formations (paru), and the unique hydrodynamic upwelling of the Gulf of Mannar that fosters planktonic blooms.",
        "summary_ta": "மன்னார் வளைகுடா முத்துச்சிப்பியின் உயிரியல்: அரகோனைட் படிக அடுக்குகள் மூலம் சிப்பி இழை முத்து உருவாக்கம், பவளப்பாறை படுகை அமைப்புகள் மற்றும் ஆழ்கடல் நீரோட்டங்களால் பெருகும் நுண்ணுயிர் உணவுச் சூழலியல்.",
        "sources": [
            "Marine Fisheries Bureau: Gulf of Mannar Pearl Oyster Surveys",
            "Journal of Molluscan Studies",
            "Indian Ocean Coral Reef Ecology"
        ],
        "content": "# Pinctada Radiata & Gulf of Mannar Benthic Ecology\n\nThe Gulf of Mannar represents one of the most prolific natural pearl oyster habitats in world history due to precise geophysical and biological conditions:\n\n**Biomineralization Mechanics:**\n- **Nacre Secretion**: When a parasite larvae or grain of quartz breaches the shell margin, the oyster's outer mantle epithelium secretes concentric micro-layers of calcium carbonate (aragonite crystal tablets, 0.5 μm thick) bonded by an organic matrix of conchiolin protein.\n- **Structural Iridescence**: The alternating refractive indices of aragonite crystals ($n = 1.68$) and conchiolin ($n = 1.53$) create constructive thin-film light interference, producing the deep Orient lustre (*ani muthu*) prized across antiquity.\n\n**Benthic Reef Topology (*Paru*):**\nOysters anchor via byssus threads onto hard calcarenite sandstone ridges (*paru*) located 8 to 22 meters underwater, 10–20 km off the coast. The primary historic beds included *Melon-paru*, *Devi-paru*, and *Korkai-paru*.\n\n**Hydrodynamic Upwelling:**\nThe shallow bathymetry of the Palk Strait and Gulf of Mannar funnels nutrient-rich monsoon currents, generating massive diatom blooms that provide filter-feeding oysters with constant, high-energy nutrition."
    },
    {
        "file": "knowledge/technologies/technology-apnea-breath-hold-diving-amarkkal-sinker-stones-and-valaikoodu-bags.md",
        "slug": "technology-apnea-breath-hold-diving-amarkkal-sinker-stones-and-valaikoodu-bags",
        "category": "technology",
        "name_en": "Apnea Breath-Hold Diving: Amarkkal Granite Sinkers, Rapid Descent Dynamics and Coir Net Retrieval",
        "name_ta": "மூச்சு அடக்கு முத்துக்குளிப்பு: அமர்க்கல் எடைக் கருங்கல், விரைவு இறங்கு இயற்பியல் மற்றும் வலைக்கூடு",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "The physiological and mechanical technology of ancient Tamil apnea pearl diving: using 10-15 kg grooved granite sinker stones (amarkkal) to achieve rapid negative buoyancy descent to 15-20 meters depth in under 20 seconds, conserving oxygen for bottom gathering into woven coir waist nets (valaikoodu) during 60-90 second dives.",
        "summary_ta": "பண்டைய தமிழ் மூச்சு அடக்கு முத்துக்குளிப்பு தொழில்நுட்பம்: 10-15 கிலோ எடையுள்ள அமர்க்கல் கருங்கல்லைப் பயன்படுத்தி 20 வினாடிகளில் 15-20 மீட்டர் ஆழத்தை அடைந்து, ஆக்சிஜனை மிச்சப்படுத்தி 60-90 வினாடிகளில் இடுப்பு வலைக்கூட்டில் சிப்பிகளை சேகரிக்கும் முறை.",
        "sources": [
            "Hornell: The Indian Pearl Fisheries of the Gulf of Mannar",
            "Undersea & Hyperbaric Medicine: Free-Diving Physiology",
            "Tamil Naval History"
        ],
        "content": "# Apnea Pearl Diving Technology: Amarkkal & Descent Dynamics\n\nAncient Tamil pearl gatherers (*kulippalar*) attained extraordinary depths without compressed air, employing a streamlined mechanical descent system:\n\n**Descent Phase with Amarkkal:**\n1. The diver stood on the gunwale of the wooden boat (*thoni* or *vallam*), placing one foot in a rope stirrup attached to an *amarkkal*—a pyramidal or grooved granite stone weighing 10–15 kg suspended by a retrieval line held by the boat tender (*mandak*).\n2. Clamping a horn or tortoiseshell spring-clip over his nostrils to prevent water ingress, the diver inhaled deeply, hyperventilating slightly to expel residual CO2.\n3. Upon signal, the tender released the stone line. The diver descended feet-first at a velocity of 1.2 to 1.6 m/s, reaching the seabed (15–20 meters depth) in under 15 seconds without expending muscular metabolic energy.\n\n**Benthic Gathering Phase:**\nAt the reef bottom, the diver slipped his foot out of the stirrup, signaling the tender to haul the stone back up. Working horizontally along the *paru* reef for 45 to 70 seconds, the diver scraped clusters of byssus-anchored oysters using a short iron knife, packing them into an open-mouthed coir bag (*valaikoodu*) slung around his neck.\n\n**Ascent Phase:**\nWhen pulmonary carbon dioxide levels triggered diaphragmatic contractions, the diver jerked the safety line attached to his waist. The boat tender hauled the diver to the surface at ~1.5 m/s, completing a total submerged cycle of 80–110 seconds. Divers performed 30 to 45 such dives per day."
    },
    {
        "file": "knowledge/artifacts/artifact-amarkkal-granite-sinker-stones-tortoiseshell-nose-clips-and-dive-ropes.md",
        "slug": "artifact-amarkkal-granite-sinker-stones-tortoiseshell-nose-clips-and-dive-ropes",
        "category": "artifact",
        "name_en": "Amarkkal Pierced Granite Sinkers, Tortoiseshell Nose-Clips and Braided Cotton Signal Ropes",
        "name_ta": "அமர்க்கல் துளையிட்ட கருங்கற்கள், ஆமை ஓட்டு மூக்குக் கிளிப்புகள் மற்றும் சமிக்ஞைக் கயிறுகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "The physical diving kit recovered across Pandyan maritime sites: perforated granite or basalt sinker weights (amarkkal) shaped into tear-drops to minimize hydrodynamic drag, polished tortoiseshell or horn spring nose-clips (mookku-kattai), and multi-strand braided palmyra/cotton tether ropes.",
        "summary_ta": "பாண்டியர் துறைமுகங்களில் கண்டெடுக்கப்பட்ட முத்துக்குளிப்பு கருவிகள்: நீர் எதிர்ப்பு குறைந்த துளையிட்ட கூம்பு வடிவ அமர்க்கல் கற்கள், ஆமை ஓட்டிலான மூக்குக் கிளிப்புகள் மற்றும் சமிக்ஞைக் கயிறுகள்.",
        "sources": [
            "ASI Maritime Archaeology Excavation Reports: Korkai & Kayalpatnam",
            "Hornell Ethnographic Collections: Cambridge Museum",
            "South Indian Material Culture"
        ],
        "content": "# Amarkkal & Maritime Diving Kit\n\nArchaeological excavations at Korkai, Alagankulam, and Kayalpatnam have uncovered the specialized material culture of classical apnea divers:\n\n**1. Amarkkal (Granite Sinker Stone):**\nA dense plutonic charnockite or basalt boulder (10–14 kg) dressed into a hydrodynamic drop or pyramidal form. A transverse hole (2.5 cm diameter) drilled through the apex holds a coir grommet. Longitudinal surface grooves allow water to flow smoothly past the descending stone, reducing turbulence and maximizing terminal sinking velocity.\n\n**2. Mookku-Kattai (Nose-Clamp):**\nCarved from flexible hawksbill sea turtle carapace (*aamai-oodu*) or water buffalo horn. Heated in boiling sesame oil to impart plastic spring-tension, the U-shaped clip clamped firmly across the nostrils, maintaining an airtight seal against 2–3 atmospheres of hydrostatic pressure without requiring manual pressure equalization.\n\n**3. Valaikoodu (Coir Neck-Basket):**\nA wide-mouthed flexible bag woven from two-ply coconut-fiber (*senbu-kayiru*) cordage with a rigid circular rim made from bent split-cane. Sunk with lead sinkers around the rim, it remained open underwater to receive scraped oysters quickly.\n\n**4. Signal & Haul Ropes (*Kani-Kayiru*):**\nBraided from sun-cured palmyra fibers or wild sunn-hemp (*sanappu*), greased with fish oil to resist saltwater rot and waterlogging, capable of lifting 150 kg without snapping."
    },
    {
        "file": "knowledge/concepts/concept-pearl-grading-ani-thool-and-pazham-sieve-metrics-and-lustre-physics.md",
        "slug": "concept-pearl-grading-ani-thool-and-pazham-sieve-metrics-and-lustre-physics",
        "category": "concept",
        "name_en": "Ancient Tamil Pearl Classification: Ani, Thool & Pazham Sieve Metrics, Weight Ratios and Lustre Physics",
        "name_ta": "பண்டைய தமிழ் முத்து வகைப்பாடு: அணி, தூள், பழம் சல்லடை அளவுகள் மற்றும் முத்து ஒளிவிலகல் இயற்பியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "The rigorous metrological and optical classification system for pearls in Tamil epigraphy and literature: sorting into sixteen grades through nested brass sieves, separating perfect spherical gems (ani), button and baroque shapes (pazham), and seed pearls (thool), evaluated using traditional weight units (manjadi and kalanju).",
        "summary_ta": "தமிழ் கல்வெட்டுகள் மற்றும் இலக்கியங்களில் உள்ள முத்து தரப் பிரிப்பு முறை: பதினாறு துளை பித்தளை சல்லடைகள் வழியே உருண்டை முத்து (அணி), ஒழுங்கற்ற முத்து (பழம்) மற்றும் சிற்றளவிலான தூள் முத்துக்களை மஞ்சாடி, கழஞ்சு எடையில் மதிப்பிடும் முறை.",
        "sources": [
            "Thanjavur Brihadeeswara Temple Epigraphs on Pearl Jewels",
            "Silappadikaram Commentary by Adiyarkkunallar",
            "Kautilya's Arthashastra on Pandyan Pearls"
        ],
        "content": "# Ancient Tamil Pearl Metrology & Grading\n\nPandyan pearl grading, preserved in Chola temple inventories and Sangam commentaries, utilized an objective hierarchy combining geometry, weight, and optical clarity:\n\n**The Primary Morphological Classes:**\n1. **Ani (அணி)**: Flawless, perfectly spherical pearls with supreme mirror-lustre (*thejassu*). Reserved exclusively for crown jewels and deity crowns.\n2. **Vadivu / Vattam (வடிவு)**: Nearly spherical pearls with slight oval distortion; used in royal necklaces (*muthu-maala*).\n3. **Pazham (பழம்)**: Baroque, teardrop, or button-shaped pearls formed against the shell wall.\n4. **Thool / Kuru-muthu (தூள்)**: Microscopic seed pearls (< 2 mm), gathered in massive volumes for pearl embroidery, medicinal calcined bhasma (*muthu-parpam*), and export.\n\n**Concentric Sieve Calibration (*Muthu-Challadai*):**\nPearls were graded by passing through a nested tier of 10 to 16 perforated brass plates (*challadai*), each containing numbered holes of precise calibration:\n- *Siru-thulai* (highest sieve): 20 to 30 holes per square inch.\n- *Perun-thulai* (lowest sieve): 800 to 1,000 microscopic holes per square inch.\n\n**Weight Equivalents:**\nMeasured using scarlet *manjadi* (*Adenanthera pavonina*) seeds and gold *kalanju* weights:\n$$1\\text{ Kalanju} \\approx 20\\text{ Manjadi} \\approx 5.2\\text{ grams}$$\nPrices scaled exponentially based on diameter: doubling the pearl diameter increased valuation tenfold."
    },
    {
        "file": "knowledge/institutions/institution-kadal-katti-shark-binders-and-parathavar-pearl-diving-guild.md",
        "slug": "institution-kadal-katti-shark-binders-and-parathavar-pearl-diving-guild",
        "category": "institution",
        "name_en": "Kadal-Katti Shark Binders, Parathavar Maritime Guilds & Royal Pandyan Pearl Monopoly",
        "name_ta": "கடல்கட்டி சுறா மந்திரக் காவலர், பரதவர் முத்துக்குளிப்புக் கழகம் மற்றும் பாண்டியர் முத்து உரிமை",
        "era": "Iron Age to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "neithal",
        "summary_en": "The corporate and social organization of the Gulf of Mannar pearl fisheries: the Parathavar seafaring clan organized into specialized diving guilds, the state-commissioned Kadal-Katti ('sea-binders' or shark shamans) who performed ritual shark-deterrence rites, and the royal tax system allocating one-third of all harvested oysters to the Pandyan king.",
        "summary_ta": "மன்னார் வளைகுடா முத்துக்குளிப்பின் நிர்வாகக் கட்டமைப்பு: பரதவர் கடல்சார் தொழிற்கழகம், சுறா தாக்குதல்களைத் தடுக்கும் சடங்குகளைச் செய்த கடல்கட்டி பூசாரிகள், மற்றும் அரசருக்கு மூன்றில் ஒரு பங்கு சிப்பிகளை வழங்கும் பாண்டிய வரி முறை.",
        "sources": [
            "Marco Polo's Travels in the Coromandel",
            "Ibn Battuta on the Pearl Divers of Ma'bar",
            "Castes and Tribes of Southern India: Parathavar"
        ],
        "content": "# Kadal-Katti & The Parathavar Guild Structure\n\nThe pearl fishery was an intensely dangerous economic monopoly regulated by hereditary naval guilds and royal officials:\n\n**The Parathavar Seafaring Clans:**\nThe *Parathavar* held exclusive customary rights to dive the Gulf of Mannar reefs. Organized into territorial flotillas commanded by headmen (*Thalaivan* or *Adappan*), they maintained strict operational schedules governed by astronomical tides and monsoon winds (diving strictly between February and April when seas were glass-calm).\n\n**The Kadal-Katti (Shark-Binders):**\nVenetian traveler Marco Polo (1292 CE) and Arab chronicler Ibn Battuta (1344 CE) both noted the vital role of the *Kadal-Katti* (Brahmins or shamans of the sea):\n- Each flotilla paid 5% of their catch to the *Kadal-Katti*, who stood on the lead vessels reciting mantras, casting incantations into the water, and burning herbal resins to \"bind the mouths of the sharks\" (*sura-kattu*).\n- These rituals provided essential psychological stabilization for apnea divers operating in waters inhabited by tiger sharks and sawfish.\n\n**Royal Monopolistic Taxation:**\nThe Pandyan treasury stationed royal officers (*Kanakkar*) on the beach at Korkai and Kayal. As boats landed, total oyster bags were divided into three equal heaps:\n1. One-third was claimed directly by the Pandyan monarch as royal domain tax (*Kadamai*).\n2. One-third went to the divers (*kulippalar*).\n3. One-third was allocated to the boat owner, net menders, and shark-binders."
    },
    {
        "file": "knowledge/technologies/technology-oyster-flesh-rotting-putrefaction-vats-and-pearl-washing-kinetics.md",
        "slug": "technology-oyster-flesh-rotting-putrefaction-vats-and-pearl-washing-kinetics",
        "category": "technology",
        "name_en": "Oyster Flesh Putrefaction: Sand Trenches, Enzymatic Hydrolysis and Hydraulic Pearl Extraction",
        "name_ta": "சிப்பி அழுகல் முறை: மணல் குழிகள், என்சைம் சிதைவு மற்றும் நீரில் முத்து பிரித்தெடுக்கும் நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "Post-harvest biochemical processing of pearl oysters: controlled rotting in coastal sand pits and thatched enclosures (kottu), natural enzymatic and bacterial decomposition of muscular tissue over 7-10 days, followed by gentle hydraulic washing through tiered copper strainers to separate heavy pearls without scratching delicate nacre surfaces.",
        "summary_ta": "அறுவடைக்குப் பிந்தைய சிப்பி பதப்படுத்துதல்: கடற்கரை மணல் கொட்டில்களில் 7-10 நாட்கள் இயற்கையாக அழுக வைத்து, என்சைம் சிதைவுக்குப் பின் நீரினால் கழுவி பளபளப்பான முத்துக்களை பிரித்தெடுக்கும் தொழில்நுட்பம்.",
        "sources": [
            "Hornell: The Pearl Fishery of Tuticorin",
            "Journal of the Asiatic Society of Bengal",
            "Traditional Marine Technologies of Tamil Nadu"
        ],
        "content": "# Oyster Putrefaction & Hydraulic Extraction\n\nExtracting pearls by forcing open living oysters with knives risks gouging the nacre surface and destroying the jewel's commercial value. Instead, ancient Tamils mastered a controlled biochemical decomposition process:\n\n**1. Kottu Sand Enclosures:**\nMillions of harvested oysters were piled into vast rectangular enclosures (*kottu*) partitioned on the dry sand spits of Korkai or Kayal. The piles were covered with woven palmyra mats to shield them from predatory seabirds while admitting blistering solar heat.\n\n**2. Bacterial & Enzymatic Hydrolysis:**\nOver 7 to 10 days, endogenous autolytic enzymes and ubiquitous marine bacteria (*Vibrio* and *Pseudomonas* species) systematically hydrolyzed the oyster's adductor muscle and mantle connective tissues. The flesh decomposed into a liquefied, foul-smelling slurry, leaving the calcium carbonate shells and embedded pearls completely detached.\n\n**3. Hydraulic Washing (*Muthu-Kaluvudhal*):**\nThe putrefied slurry was transferred into seawater-filled wooden canoes (*kallu-thoni*) or copper vats. Workers agitated the liquid by hand, allowing the dense pearls (specific gravity $\\approx 2.71$) to sink rapidly to the bottom while light organic debris and empty shell valves floated or remained suspended.\n\n**4. Cleansing & Drying:**\nThe recovered pearl sediment was washed three times in fresh river water, scrubbed with coarse sea salt and rice husks (*thavidu*) to polish away residual mucus films, and dried on clean white calico cloth in shaded sea breezes."
    },
    {
        "file": "knowledge/places/place-kayalpatnam-ancient-pandya-pearl-fishery-haven.md",
        "slug": "place-kayalpatnam-ancient-pandya-pearl-fishery-haven",
        "category": "place",
        "name_en": "Kayalpatnam: Ancient Pandyan Pearl Fishery Haven, Apnea Diver Harbors & Arab Trade Emporium",
        "name_ta": "காயல்பட்டினம் - பண்டைய பாண்டியர் முத்துக்குளிப்புத் தளம், பரதவர் துறைமுகம் மற்றும் முத்து வர்த்தக மையம்",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Historic maritime harbor and pearl-diving emporium south of Korkai along the Gulf of Mannar in Thoothukudi district, celebrated across antiquity as a primary staging station for deep-sea pearl diving flotillas, apnea training lagoons, international Arab horse-for-pearl trade exchanges, and sacred chank fisheries.",
        "summary_ta": "தூத்துக்குடி மாவட்டத்தில் கொற்கைக்கு தெற்கே மன்னார் வளைகுடாவில் அமைந்த வரலாற்று சிறப்புமிக்க முத்துக்குளிப்புத் துறைமுகம்: மூச்சு அடக்கு வீரர்கள் பயிற்சித் தளம், சர்வதேச முத்து வணிக மையம் மற்றும் குதிரை வர்த்தக பரிமாற்ற நகரம்.",
        "sources": [
            "Marco Polo's Description of Cail",
            "Ibn Battuta's Rihla",
            "Thoothukudi District Gazetteer",
            "Epigraphia Indica"
        ],
        "content": "# Kayalpatnam: Pearl Fishery Haven\n\nSituated along the sheltered estuarine bight of the Thamirabarani River basin, Kayalpatnam (historic *Palayakayal* / *Cail*) succeeded Korkai as the primary deep-water pearl capital of the Pandyan kingdom:\n\n**Maritime Strategic Setting:**\nThe natural sandspits and offshore coral shoals shielded Kayalpatnam's inner roadstead from rough Indian Ocean swells, providing ideal mooring for hundreds of pearl-diving catamarans (*kattumaram*) and large Arabian *dhows*.\n\n**Global Gem Emporium:**\nIn the 13th century, Marco Polo described the port (*Cail*):\n> *\"It is a great and noble city... touching here all the ships that come from the West, from Hormuz, from Kis, from Aden, laden with horses and other merchandise, to trade for pearls of great price...\"*\n\nArab merchant prince Jamal-ud-din operated a massive horse-trading concession headquartered at Kayalpatnam, exchanging 1,400 Arabian stallions annually directly for prime Pandyan pearls.\n\n**Living Maritime Heritage:**\nTo this day, the coastline retains ancestral communities of deep-sea divers, traditional conch carvers, and salt-saltern workers whose cultural traditions trace back thousands of years to the classical Sangam age."
    },
    {
        "file": "knowledge/concepts/concept-gulf-of-mannar-upwelling-currents-salinity-and-benthic-calcium-carbonate.md",
        "slug": "concept-gulf-of-mannar-upwelling-currents-salinity-and-benthic-calcium-carbonate",
        "category": "concept",
        "name_en": "Gulf of Mannar Upwelling Currents, Hydrodynamics, Salinity Gradients & Benthic Biocalcification",
        "name_ta": "மன்னார் வளைகுடா ஆழ்கடல் நீரோட்டங்கள், உவர்ப்பு விகிதம் மற்றும் கால்சியம் படிமக் சூழலியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Oceanographic and chemical dynamics of the Gulf of Mannar: the intersection of Bay of Bengal and Arabian Sea current systems driving seasonal nutrient upwelling, stable high salinity (34-36 ppt), alkaline pH (8.1-8.3), and supersaturated calcium carbonate levels that enable rapid mollusc shell calcification.",
        "summary_ta": "மன்னார் வளைகுடாவின் கடல்சார் வேதியியல் இயற்பியல்: வங்கக் கடல் மற்றும் அரபிக்கடல் நீரோட்டங்களின் சங்கமம், ஊட்டச்சத்து நிறைந்த ஆழ்கடல் எழுச்சி, சீரான உவர்ப்பு மற்றும் கால்சியம் கார்பனேட் செறிவு.",
        "sources": [
            "National Institute of Oceanography: Gulf of Mannar Hydrodynamics",
            "Marine Chemistry Journal",
            "Ocean Science Studies"
        ],
        "content": "# Gulf of Mannar Oceanographic & Calcification Dynamics\n\nThe exceptional quality and density of oysters in the Gulf of Mannar are governed by unique marine physicochemical gradients:\n\n**Current Convergence & Seasonal Upwelling:**\nThe Gulf of Mannar forms a wedge-shaped oceanic cul-de-sac between southeastern India and Sri Lanka. During the Southwest Monsoon (May–September), clockwise equatorial currents force deep oceanic water into the Gulf, triggering cold, nutrient-rich upwelling along the Tamil coast. Phosphate and nitrate concentrations rise by 400%, feeding massive phytoplankton blooms.\n\n**Biocalcification Chemistry:**\n- **Salinity**: Remains remarkably stable between 34.5 and 36.2 parts per thousand (ppt), shielded from major river deltas except the seasonal Thamirabarani.\n- **Saturation State ($\\\\Omega$)**: Aragonite saturation ($\\\\Omega_{arag}$) consistently exceeds 3.8. In this supersaturated environment, oysters expend minimal metabolic energy precipitating $\\text{Ca}^{2+}$ and $\\text{CO}_3^{2-}$ ions from ambient seawater into hard shell nacre.\n- **Water Temperature**: Subsurface temperatures range between 26°C and 29°C year-round, maintaining maximum enzymatic activity of mantle carbonic anhydrase, the key catalyst in shell building."
    },
    {
        "file": "knowledge/artifacts/artifact-muthu-koodai-woven-dive-baskets-shark-tooth-talismans-and-sieves.md",
        "slug": "artifact-muthu-koodai-woven-dive-baskets-shark-tooth-talismans-and-sieves",
        "category": "artifact",
        "name_en": "Muthu Koodai Palmyra Dive Baskets, Shark-Tooth Amulets and Concentric Brass Grading Sieves",
        "name_ta": "முத்துக் கூடை பனை நார்ப்பைகள், சுறாப் பல் தாயத்துக்கள் மற்றும் பித்தளை முத்துச் சல்லடைகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "The material ensemble of pearl harvesting and merchant evaluation: woven palmyra-fiber diver gathering bags (muthu-koodai), fossilized shark-tooth talismans worn by divers to repel predators, and graduated brass nesting sieves used by pearl merchants in port bourses.",
        "summary_ta": "முத்து சேகரிப்பு மற்றும் வணிக ஆய்வுக் கருவிகள்: பனை நாரினால் பின்னப்பட்ட மூழ்கு பைகள், சுறா பற்களால் ஆன தாயத்துக்கள் மற்றும் துறைமுக சந்தைகளில் பயன்படுத்தப்பட்ட துளையிட்ட பித்தளைச் சல்லடைகள்.",
        "sources": [
            "Government Museum Chennai: Numismatic & Archaeological Catalogues",
            "Hornell Ethnographic Collections",
            "Maritime Antiquities of Southern India"
        ],
        "content": "# Muthu Koodai, Talismans & Merchant Sieves\n\nThe material assemblage of the pearl trade spans both deep-sea harvesting gear and precision bazaar evaluation instruments:\n\n**1. Muthu-Koodai (Palmyra Dive Bag):**\nA robust, flexible net-basket woven from split palmyra leaf fibers (*panai-naaru*) or coir cordage. Featuring a loop handle fitted around the diver's neck and an elastic cinching mouth, it allowed divers to quickly deposit scraped shells using one hand while steadying themselves against current surges with the other.\n\n**2. Sura-Pal Thali (Shark-Tooth Amulet):**\nRecovered from ancient coastal burials near Tuticorin, these amulets feature fossilized or fresh teeth of tiger sharks (*Galeocerdo cuvier*) perforated at the root and bound with gold or copper wire. Worn around the neck alongside consecrated coral beads, they served as ritual talismans conferring spiritual immunity against marine predators.\n\n**3. Concentric Grading Sieves (*Muthu-Challadai Tier*):**\nA stacked tower of shallow spun-brass bowls, each fitting snugly into the one below. The bottom of each bowl is pierced with a hexagonal matrix of circular holes machined to tolerances under 0.1 mm. When a bulk consignment of raw pearls was shaken through the stack, the gems self-sorted into standardized merchant categories in minutes."
    }
]

EDGES = [
    [
        "text-maduraikanchi-and-periplus-on-korkai-pandya-pearl-fishery-flotillas",
        "DOCUMENTS",
        "institution-kadal-katti-shark-binders-and-parathavar-pearl-diving-guild",
        "core",
        "Sangam Era",
        "Maduraikanchi documents the royal Pandyan pearl fleets and seafaring guilds",
        "Maduraikanchi 134-144"
    ],
    [
        "technology-apnea-breath-hold-diving-amarkkal-sinker-stones-and-valaikoodu-bags",
        "HARVESTS",
        "concept-pinctada-radiata-pearl-oyster-biology-and-gulf-of-mannar-shoal-ecology",
        "core",
        "Iron Age to Modern Era",
        "Apnea breath-hold divers harvested benthic Pinctada oysters from shallow reefs",
        "Hornell Indian Pearl Fisheries"
    ],
    [
        "artifact-amarkkal-granite-sinker-stones-tortoiseshell-nose-clips-and-dive-ropes",
        "IMPLEMENTS",
        "technology-apnea-breath-hold-diving-amarkkal-sinker-stones-and-valaikoodu-bags",
        "core",
        "Iron Age to Modern Era",
        "Pierced granite sinker stones and nose-clips formed the core physical apnea kit",
        "ASI Maritime Archaeology Korkai"
    ],
    [
        "technology-oyster-flesh-rotting-putrefaction-vats-and-pearl-washing-kinetics",
        "EXTRACTS_FROM",
        "concept-pinctada-radiata-pearl-oyster-biology-and-gulf-of-mannar-shoal-ecology",
        "core",
        "Iron Age to Modern Era",
        "Bacterial rotting in sand trenches released pearls without scratching nacre",
        "Journal of the Asiatic Society"
    ],
    [
        "concept-pearl-grading-ani-thool-and-pazham-sieve-metrics-and-lustre-physics",
        "CLASSIFIES",
        "artifact-muthu-koodai-woven-dive-baskets-shark-tooth-talismans-and-sieves",
        "core",
        "Iron Age to Modern Era",
        "Graduated brass sieves sorted pearls into ani, vadivu, and thool categories",
        "Thanjavur Temple Epigraphs"
    ],
    [
        "institution-kadal-katti-shark-binders-and-parathavar-pearl-diving-guild",
        "OPERATED_FROM",
        "place-kayalpatnam-ancient-pandya-pearl-fishery-haven",
        "core",
        "Iron Age to Medieval Era",
        "Parathavar divers and shark-binding priests were stationed at Kayalpatnam",
        "Marco Polo Travels"
    ],
    [
        "concept-gulf-of-mannar-upwelling-currents-salinity-and-benthic-calcium-carbonate",
        "SUSTAINS",
        "concept-pinctada-radiata-pearl-oyster-biology-and-gulf-of-mannar-shoal-ecology",
        "core",
        "Iron Age to Modern Era",
        "Nutrient-rich upwelling currents sustained massive pearl oyster colonies",
        "National Institute of Oceanography"
    ],
    [
        "place-kayalpatnam-ancient-pandya-pearl-fishery-haven",
        "TRADED",
        "concept-pearl-grading-ani-thool-and-pazham-sieve-metrics-and-lustre-physics",
        "core",
        "Iron Age to Modern Era",
        "Kayalpatnam served as the global bourse where graded pearls were exported",
        "Ibn Battuta Rihla"
    ],
    [
        "artifact-amarkkal-granite-sinker-stones-tortoiseshell-nose-clips-and-dive-ropes",
        "FOUND_AT",
        "place-kayalpatnam-ancient-pandya-pearl-fishery-haven",
        "core",
        "Iron Age to Modern Era",
        "Archaeological excavations at Kayalpatnam recovered ancient diving sinker stones",
        "ASI Maritime Survey Reports"
    ],
    [
        "text-maduraikanchi-and-periplus-on-korkai-pandya-pearl-fishery-flotillas",
        "ATTESTS",
        "technology-apnea-breath-hold-diving-amarkkal-sinker-stones-and-valaikoodu-bags",
        "core",
        "Sangam Era",
        "Classical texts explicitly describe divers leaping with stones into the ocean",
        "Periplus of the Erythraean Sea §59"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 40: Ancient Tamil Pearl Fishery Oyster Bed Apnea Diving, Marine Benthic Ecology & Parathavar Guild...")
    
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

    print(f"Ingestion Complete for Batch 40 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
