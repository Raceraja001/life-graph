#!/usr/bin/env python3
"""
Harvester: Batch 42 - Ancient Tamil Crucible Wootz Steel Smelting, Bloomery Pyrotechnics & Ultra-High Carbon Damascus Metallurgy
Generated automatically.
"""

import os
import json
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"
DOSSIER_DIR = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

DOSSIERS = [
    {
        "slug": "text-purananuru-and-patittruppathu-on-blacksmiths-bellows-and-steel-swords",
        "category": "text",
        "file": "text-purananuru-and-patittruppathu-on-blacksmiths-bellows-and-steel-swords.md",
        "name_en": "Purananuru & Patittruppathu Verses on Blacksmiths Bellows, Wootz Swords and Armory Furnaces",
        "name_ta": "புறநானூறு மற்றும் பதிற்றுப்பத்து கொல்லன் உலைக்களத் துருத்தி மற்றும் எஃகு வாள் பாடல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Sangam verses describing the roaring charcoal hearths of iron masters (Uruku-Kollan), skin bellows breathing flames like hissing serpents, forging razor-sharp Wootz steel swords (Karumpon / Ukku) capable of cleaving elephant tusks.",
        "summary_ta": "பாம்பு மூச்சு விடுவது போல துருத்தி ஊதி எரியும் கொல்லன் உலைக்களம், யானைக் கொம்புகளையும் வெட்டி வீழ்த்தும் கருங்கால் இரும்பு மற்றும் உக்கு எஃகு வாள்கள் பற்றிய புறநானூற்றுப் பாடல்கள்.",
        "sources": [
            "Purananuru 170",
            "Purananuru 312",
            "Patittruppathu 19",
            "Ahananuru 72"
        ],
        "content": "# Purananuru & Patittruppathu on Blacksmith Furnaces & Wootz Steel\n\nAncient Tamil literature provides celebrated eyewitness depictions of intense bloomery iron and crucible steel metallurgy:\n\n**Literary Testimonies:**\n- **Purananuru 170 & 312**: Describes the armory workshop of the *Uruku-Kollan* where deer-skin bellows (*thurutti*) blow rhythmic blasts of air into white-hot charcoal embers, forging curved steel battle-axes and double-edged swords.\n- **Patittruppathu 19**: Celebrates Chera warriors wielding *Karum-Pattayam* (dark watered steel blades) that glisten like midnight lightning, exhibiting the damask watering patterns characteristic of ultra-high carbon Wootz steel.\n- **Narrinai 125**: Depicts the red sparks showering across the village smithy as incandescent steel ingots (*irumbu-katti*) are beaten on heavy iron anvils."
    },
    {
        "slug": "concept-ultra-high-carbon-steel-metallurgy-cementite-spheroidization",
        "category": "concept",
        "file": "concept-ultra-high-carbon-steel-metallurgy-cementite-spheroidization.md",
        "name_en": "Ultra-High Carbon Steel Metallurgy, Iron-Carbon Phase Diagrams & Cementite Spheroidization",
        "name_ta": "மீவுயர் கார்பன் எஃகு உலோகவியல், இரும்பு-கார்பன் நிலை வரைபடம் மற்றும் சிமென்டைட் உருண்டையாதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Materials science and crystallography of South Indian Wootz steel: 1.2% to 1.6% hypereutectoid carbon concentration, slow crucible cooling yielding proeutectoid cementite networks, and thermal cycling creating the legendary Damascene water-mark swirl pattern.",
        "summary_ta": "தென்னிந்திய வூட்ஃஸ் உக்கு எஃகின் படிகவியல் மற்றும் வேதியியல்: 1.2% முதல் 1.6% வரையிலான கார்பன் அளவு, மெதுவான குளிரூட்டல் மூலம் உருவாகும் சிமென்டைட் கோடுகள் மற்றும் மங்கலான அலை வடிவக் கட்டமைப்பு.",
        "sources": [
            "Metallurgical Transactions: Wootz Steel Crystallography",
            "Verhoeven Damascus Steel Studies",
            "CSIR National Metallurgical Laboratory Reports"
        ],
        "content": "# Ultra-High Carbon Wootz Steel Metallurgy\n\nSouth Indian crucible steel (*Ukku*) revolutionized ancient world metallurgy by achieving hypereutectoid carbon concentrations unknown to the West:\n\n**Thermodynamic & Crystal Mechanics:**\n- **Carbon Saturation ($1.2-1.6\\\\%\\\\text{ C}$)**: Wrought iron bloom was sealed inside refractory clay crucibles with dried *Cassia auriculata* wood and carbonaceous foliage. At furnace temperatures exceeding $1250^\\\\circ\\\\text{C}$, iron absorbed gaseous carbon via diffusion, lowering its liquidus melting point.\n- **Slow Solidification**: Ingot cooling over several hours allowed coarse proeutectoid cementite ($\\text{Fe}_3\\text{C}$) to precipitate along austenite grain boundaries.\n- **Spheroidization Thermomechanics**: Repeated low-temperature forging ($650^\\\\circ\\\\text{C}-800^\\\\circ\\\\text{C}$) fragmented brittle cementite grain boundaries into rounded sub-micron carbide spheres aligned in wavy bands, imparting both supernatural razor sharpness and flexible shock resistance."
    },
    {
        "slug": "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers",
        "category": "technology",
        "file": "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers.md",
        "name_en": "Closed Refractory Crucible Pyrotechnics, Rice-Husk Clay Saggers & Natural Tuyeres",
        "name_ta": "மூடப்பட்ட தீச்செங்கல் மூசை சூளை எரிப்பு, உமி கலந்த களிமண் மூடிகள் மற்றும் காற்றுத் துருத்திக் குழல்கள்",
        "era": "Iron Age to Medieval Era",
        "year_start": -800,
        "year_end": 1400,
        "thinai": "mullai",
        "summary_en": "The pyrotechnological sequence of Tamil Wootz crucible steel: formulating aluminosilicate clay crucibles tempered with carbonaceous rice husks, hermetic clay sealing, packing in tiered beehive furnaces, and forced blast smelting.",
        "summary_ta": "தமிழ் உக்கு மூசைத் தயாரிப்பு முறை: உமி கலந்த காரத்தன்மை கொண்ட களிமண் கொண்டு மூசைகள் உருவாக்குதல், மூலப்பொருட்களை வைத்து மூடி சீலிடுதல் மற்றும் துருத்தி கொண்டு 1300°C வரை சுடுதல்.",
        "sources": [
            "Archaeometry of Indian Crucible Steel",
            "Excavations at Mel-Siruvalur (TNSDA)",
            "British Museum Wootz Ingot Analyses"
        ],
        "content": "# Closed Crucible Pyrotechnics & Refractory Saggers\n\nThe manufacturing of crucible steel required specialized ceramics that could withstand prolonged exposure to temperatures above $1300^\\circ\\text{C}$ without slumping:\n\n**Manufacturing Sequence:**\n1. **Refractory Clay Formulation**: High-alumina kaolinitic clay was heavily tempered with charred rice husks (*umikkari*). Upon firing, the rice husks pyrolyzed into graphite-like carbon networks, imparting extraordinary thermal shock resistance.\n2. **Charge Loading**: Solidified wrought iron blooms were chopped into uniform pellets, packed into cylindrical crucibles with dried twigs of *Avaram* (*Cassia auriculata*), bamboo charcoal, and green leaves, then sealed with a domed clay lid.\n3. **Furnace Operation**: Up to 30 crucibles were arrayed vertically in a sunken pit kiln. Multiple clay tuyeres directed forced air blasts from animal-skin bellows into the bed of acacia charcoal, holding the furnace at peak fusion for 6 to 8 hours until the iron melted completely into homogenous liquid steel."
    },
    {
        "slug": "artifact-ukku-steel-crucibles-button-ingots-and-damascus-blades",
        "category": "artifact",
        "file": "artifact-ukku-steel-crucibles-button-ingots-and-damascus-blades.md",
        "name_en": "Ukku Refractory Ceramic Crucibles, Conical Button Ingots & Damascus Blades",
        "name_ta": "உக்கு மூசை ஓடுகள், கூம்பு வடிவ எஃகு கட்டிகள் மற்றும் அலைவரிசை பட்டய வாள்கள்",
        "era": "Iron Age to Modern Era",
        "year_start": -800,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Material repertoire of South Indian Wootz steel craft: vitreous-slagged cylindrical crucibles, flat-bottomed conical steel cakes (button ingots / wootz cakes), slag-encrusted tuyeres, and etched water-patterned sword blades.",
        "summary_ta": "வூட்ஃஸ் உக்கு எஃகின் தொல்பொருட்கள்: கண்ணாடி போன்ற கசடு படிந்த சுடுமண் மூசைகள், அரை வட்ட எஃகு கட்டிகள், துளைக் குழாய்கள் மற்றும் நீர் அலைவரிசை எஃகு வாள்கள்.",
        "sources": [
            "Kodumanal Excavation Reports",
            "Mel-Siruvalur Excavation Memoirs",
            "Wallace Collection Damascus Steel Catalog"
        ],
        "content": "# Ukku Crucibles, Button Ingots & Damascus Blades\n\nExcavations across Tamil Nadu provide physical proof of large-scale crucible steel production for export to the Mediterranean, Arabia, and Persia:\n\n**Diagnostic Artifact Assemblages:**\n- **Vitrified Crucibles**: Cylindrical containers (15–20 cm length, 6–8 cm diameter) displaying dark green glassy iron-silicate slagging on outer surfaces and a smooth hemispherical inner base.\n- **Button Ingots (*Wootz Cakes*)**: Dense circular steel ingots weighing between 500 grams and 1.5 kilograms, showing radial dendritic contraction crystals on their convex top surfaces and flat bottoms.\n- **Damascene Watered Blades**: Finished weapons exhibiting intricate swirling bright and dark micro-bands of iron carbide particles set in a dark pearlite-martensite matrix."
    },
    {
        "slug": "concept-magnetite-iron-sand-reduction-bloomery-sponge-iron-chemistry",
        "category": "concept",
        "file": "concept-magnetite-iron-sand-reduction-bloomery-sponge-iron-chemistry.md",
        "name_en": "Magnetite Black Sand Placer Reduction, Carbon Monoxide Gas Dynamics & Sponge Iron Bloom",
        "name_ta": "காந்த இரும்பு மணல் தாது ஒடுக்கம், கார்பன் மோனாக்சைடு வாயு இயக்கவியல் மற்றும் பஞ்சு இரும்பு உற்பத்தி",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Chemical reduction thermodynamics of Tamil iron smelting: washing titaniferous magnetite placer sands from riverbeds and hill slopes, carbon monoxide reduction in low-shaft bloomery furnaces, and solid-state sponge iron agglomeration.",
        "summary_ta": "ஆற்றுப்படுகை காந்த இரும்பு மணல் தாதுவை பிரித்தெடுத்து, தாழ்நிலை சூளைகளில் கரியமில வாயு கொண்டு உருக்கி, கசடு நீக்கி பஞ்சு இரும்பு (ஸ்பாஞ்ச் இரும்பு) உருவாக்கும் வேதியியல்.",
        "sources": [
            "Journal of Materials Science: Ancient Indian Metallurgy",
            "Geological Survey of India Iron Ore Studies",
            "Indian Academy of Sciences Proceedings"
        ],
        "content": "# Magnetite Placer Sand Reduction & Sponge Iron Bloom\n\nBefore crucible steel smelting could occur, pristine low-phosphorus iron was produced from abundant placer sands:\n\n**Reduction Chemistry in Shaft Bloomery ($1100^\\circ\\text{C}-1200^\\circ\\text{C}$):**\n- **Placer Beneficiation**: Black titaniferous magnetite sands washed down from hill slopes (Salem, Dharmapuri) were gathered along stream beds and density-separated using water panning.\n- **Solid-State Reduction**: Ascending carbon monoxide gas ($\\text{CO}$) generated by burning wood charcoal reduced iron oxides without melting metallic iron:\n  $$\\\\text{Fe}_3\\\\text{O}_4 + 4\\\\text{CO} \\\\rightarrow 3\\\\text{Fe} + 4\\\\text{CO}_2$$\n- **Slag-Metal Separation**: Liquid fayalite slag ($2\\\\text{FeO}\\\\cdot\\\\text{SiO}_2$) melted at $1170^\\circ\\text{C}$ and was tapped out through base apertures, leaving behind a spongy porous mass of malleable low-carbon ferrite bloom."
    },
    {
        "slug": "institution-uruku-kollan-corporation-of-hereditary-steelmakers-and-armorers",
        "category": "institution",
        "file": "institution-uruku-kollan-corporation-of-hereditary-steelmakers-and-armorers.md",
        "name_en": "Uruku-Kollan Corporation: Hereditary Steelmakers, Bloomery Masters & Royal Armorers",
        "name_ta": "உருக்குக் கொல்லன் சபை: மரபுவழி எஃகு உருக்குவோர், சூளை தலைவர்கள் மற்றும் படைக்கலப் பெருமன்றம்",
        "era": "Iron Age to Vijayanagara Era",
        "year_start": -600,
        "year_end": 1600,
        "thinai": "mullai",
        "summary_en": "The corporate artisan guild of Tamil ironsmiths and crucible steelmasters: managing forest charcoal rights, maintaining blast furnace secret formulations, manufacturing royal ordnance, and trading ingots across oceanic ports.",
        "summary_ta": "பண்டைய தமிழ் எஃகு தயாரிப்பாளர்கள் மற்றும் ஆயுதக் கொல்லர்களின் சங்கம்: நிலக்கரி வெட்டும் உரிமை, எஃகு உருக்கும் ரகசிய உத்திகள், அரச படைக்கலப் பராமரிப்பு மற்றும் ஏற்றுமதி ஒழுங்குமுறை.",
        "sources": [
            "South Indian Inscriptions: Blacksmith Guild Charters",
            "Castes and Tribes of Southern India",
            "Sangam Institutional Studies"
        ],
        "content": "# Uruku-Kollan Corporation: Hereditary Steelmakers\n\nThe mastery of crucible pyrotechnology was guarded and perpetuated by specialized artisan lineages:\n\n**Guild Functions:**\n- **Forest Charcoal Commons**: Held royal patents (*ulaimanyam*) guaranteeing exclusive access to hard timbers (*Acacia*, *Hardwickia binata*) essential for generating sulfur-free, ultra-hot furnace coals.\n- **Standardized Ingot Weights**: Cast conical steel buttons (*Ukku-Katti*) to standardized weight units (*Palam* and *Kalanju*) recognized by international traders from Rome and Persia.\n- **Weapon Testing Standards**: Tested combat swords by their ability to shear silk handkerchiefs dropped on the blade and sever iron rods without chipping or bending."
    },
    {
        "slug": "technology-thermo-mechanical-forging-and-clay-quenching-heat-treatment",
        "category": "technology",
        "file": "technology-thermo-mechanical-forging-and-clay-quenching-heat-treatment.md",
        "name_en": "Thermo-Mechanical Forging, Differential Clay Quenching & Oil Tempering",
        "name_ta": "வெப்ப இயந்திரவியல் சம்மட்டி அடித்தல், வேறுபட்ட களிமண் குளிரூட்டல் மற்றும் எண்ணெய் பதப்படுத்தல்",
        "era": "Iron Age to Medieval Era",
        "year_start": -600,
        "year_end": 1400,
        "thinai": "mullai",
        "summary_en": "The delicate blacksmithing sequence for Wootz ingots: warm forging within a narrow cherry-red temperature window (650°C-800°C) to prevent hot-shortness cracking, differential clay slurry coating for hardened martensite edges, and vegetable oil quenching.",
        "summary_ta": "உக்கு எஃகை வாளாக உருவாக்கும் சம்மட்டி முறை: விரிசல் ஏற்படாமல் 700°C செவ்வெப்பத்தில் மட்டுமே அடித்தல், களிமண் பூசி கூர்முனைக்கு அதிகக் கடினத்தன்மையும் தண்டுக்கு நெகிழ்வும் தரும் குளிரூட்டல் முறை.",
        "sources": [
            "Journal of Cultural Heritage Metallurgy",
            "The Sword and the Crucible Studies",
            "Ancient Indian Steel Heat-Treatment Memoirs"
        ],
        "content": "# Thermo-Mechanical Forging & Quenching Heat Treatment\n\nWootz steel cannot be forged like ordinary wrought iron or low-carbon steel due to its extreme carbon content ($1.5\\\\%\\\\text{ C}$):\n\n**Blacksmithing Sequence:**\n1. **Narrow Temperature Window**: If heated above $850^\\circ\\text{C}$, the steel dissolves into austenite and shatters under hammer blows (hot-shortness). Master smiths forged Wootz strictly between $650^\\circ\\text{C}$ and $780^\\circ\\text{C}$ (cherry-red heat), striking hundreds of rapid, light hammer blows.\n2. **Differential Clay Coating**: A paste of refractory clay, iron filings, and salt was applied thickly along the spine and thinly along the cutting edge.\n3. **Quenching & Tempering**: Plunged into cold sesame oil or animal fats, the thin edge cooled rapidly to form glass-hard martensite ($>62\\text{ HRC}$), while the insulated spine cooled slowly into tough pearlite ($40\\text{ HRC}$), combining an unyielding edge with elastic shock resistance."
    },
    {
        "slug": "place-mel-siruvalur-ancient-crucible-steel-haven",
        "category": "place",
        "file": "place-mel-siruvalur-ancient-crucible-steel-haven.md",
        "name_en": "Mel-Siruvalur: Ancient Crucible Steel Haven, Thenpennai Iron Belt & Sagger Smelting Citadel",
        "name_ta": "மேல்சிறுவளூர் - பண்டைய உக்கு எஃகு உருக்குத் தளம், தென்பெண்ணை இரும்புப் படுகை மற்றும் மூசை சூளை பெருநகரம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 400,
        "thinai": "mullai",
        "summary_en": "Historic metallurgical archaeological site in Kallakurichi district along the Thenpennai river basin, famous for the unearthing of ancient crucible steel furnaces, dozens of vitrified clay crucibles, iron smelting slag mounds, and bloomery tuyeres.",
        "summary_ta": "கள்ளக்குறிச்சி மாவட்டத்தில் தென்பெண்ணை ஆற்றுப் படுகையில் அமைந்துள்ள பெருமைமிக்க உக்கு எஃகு அகழ்வாய்வுத் தளம்: பழங்கால எஃகு மூசைகள், கசடு மேடுகள் மற்றும் உலைக்களங்களின் வரலாற்று மையம்.",
        "sources": [
            "Mel-Siruvalur Excavation Reports (TNSDA)",
            "Archaeometallurgy in Tamil Nadu",
            "Thenpennai Basin Iron Age Surveys"
        ],
        "content": "# Mel-Siruvalur: Ancient Crucible Steel Haven\n\nMel-Siruvalur stands as one of Tamil Nadu's most decisive archaeological sites for early crucible steel production:\n\n**Archaeological Prominence:**\n- Excavations conducted by the Tamil Nadu State Department of Archaeology revealed a high concentration of specialized crucible furnaces associated with Iron Age and early historic ceramic layers.\n- The recovery of intact and fragmented cylindrical clay crucibles containing iron prills and high-carbon slag residue proves that local metallurgists mastered crucible fusion techniques as early as the mid-1st millennium BCE.\n- Proximity to the iron-ore rich hills of the Kalrayan range and the Thenpennai river channel provided optimal access to ore, charcoal, and transportation arteries."
    },
    {
        "slug": "concept-damascus-watered-silk-pattern-optical-crystallography",
        "category": "concept",
        "file": "concept-damascus-watered-silk-pattern-optical-crystallography.md",
        "name_en": "Damascus Watered-Silk Swirl Pattern, Acid Etching & Optical Contrast Physics",
        "name_ta": "அலைவரிசை எஃகு அலைவடிவ இயற்பியல், அமில அரிப்பு மற்றும் ஒளி எதிரொலிப்பு மாறுபாடுகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Optical and chemical principles of Damascus steel visual surface patterns (jauhar): light scattering differential between white, hard cementite particle bands and dark, etched pearlite matrices revealed via mild natural acid etching (tamarind / citrus juices).",
        "summary_ta": "அலைவரிசை எஃகு வாள்களின் மேற்பரப்பில் தோன்றும் அலை வடிவங்களின் (ஜவ்ஹர்) ஒளியியல் மற்றும் வேதியியல்: புளி மற்றும் எலுமிச்சை சாறு கொண்டு அரிக்கும் போது வெளிப்படும் ஒளி சிதறல்.",
        "sources": [
            "Journal of Applied Crystallography",
            "Smithsonian Damascus Steel Analyses",
            "Nature Materials Historical Metallurgy"
        ],
        "content": "# Damascus Watered-Silk Swirl Pattern & Acid Etching\n\nThe mesmerizing visual pattern (*Jauhar* / *Neer-Vaikkal*) of true Wootz Damascus blades is an intrinsic optical consequence of its micro-structure:\n\n**Micro-Optical Mechanics:**\n- **Carbide Banding**: Macro-segregation of trace elements (vanadium, titanium, molybdenum present in local iron sand ores) stabilizes planar arrays of spherical iron carbide particles during thermal cycling.\n- **Differential Chemical Etching**: Dipping the polished blade into an aqueous solution of mild organic acids (sour tamarind water or citrus juice) selectively attacks the softer, low-carbon ferritic-pearlitic matrix, darkening it through light-trapping micro-pitting.\n- **Optical Scattering**: The refractory cementite carbide spheres ($\\text{Fe}_3\\text{C}$) remain completely unetched and mirror-like, reflecting specular light that contrasts sharply against the dark background to produce undulating watered-silk ribbons."
    },
    {
        "slug": "artifact-iron-tuyeres-bellows-nozzles-and-blooming-furnace-slags",
        "category": "artifact",
        "file": "artifact-iron-tuyeres-bellows-nozzles-and-blooming-furnace-slags.md",
        "name_en": "Vitrified Terracotta Tuyeres, Bellows Nozzles & Heavy Fayalite Slag Cakes",
        "name_ta": "சுடுமண் காற்றுத் துளைக் குழாய்கள், துருத்தி முனைகள் மற்றும் கனத்த இரும்பு கசடு கட்டிகள்",
        "era": "Iron Age to Medieval Era",
        "year_start": -800,
        "year_end": 1400,
        "thinai": "mullai",
        "summary_en": "Diagnostic refractory industrial by-products found at ancient Tamil metallurgical sites: high-vitrified terracotta air pipe nozzles (tuyeres), tap slag flows, dense fayalite furnace bottom cakes, and charcoal sintering debris.",
        "summary_ta": "பண்டைய தமிழ் இரும்பு உலைக்களங்களின் அடையாளத் தொல்பொருட்கள்: கண்ணாடி போல உருகிய காற்று குழல்கள், சூளைக் கசடு கட்டிகள் மற்றும் நிலக்கரி எச்சங்கள்.",
        "sources": [
            "Keezhadi Archaeological Excavation Reports",
            "Guchipalayam Iron Furnace Excavations",
            "Archaeological Survey of India"
        ],
        "content": "# Vitrified Tuyeres, Bellows Nozzles & Fayalite Slags\n\nExcavated iron-smelting contexts throughout Tamil Nadu yield voluminous evidence of high-temperature furnace operations:\n\n**Artifact Characteristics:**\n- **Refractory Tuyeres (*Thoombu*)**: Tubular clay pipes with inner diameters of 25–40 mm, exhibiting extreme vitrification and bloomed green glass slag on their furnace-facing ends where temperatures reached $1300^\\circ\\text{C}$.\n- **Fayalite Furnace Bottoms**: Dense, porous disc-shaped cakes of iron-silicate slag ($2\\text{FeO}\\cdot\\text{SiO}_2$) that accumulated at the hearth base beneath the sponge iron bloom, featuring high density ($>3.8\\text{ g/cm}^3$).\n- **Slag Runnel Flows**: Frozen rope-like rivulets of tapped slag demonstrating continuous furnace operation during smelting runs."
    }
]

EDGES = [
    [
        "text-purananuru-and-patittruppathu-on-blacksmiths-bellows-and-steel-swords",
        "evidences",
        "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers",
        "material_culture",
        "Sangam Era",
        "Sangam poems describe roaring iron furnaces, skin bellows, and razor steel blades.",
        "Purananuru 170 & 312"
    ],
    [
        "concept-ultra-high-carbon-steel-metallurgy-cementite-spheroidization",
        "governs",
        "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers",
        "material_culture",
        "Iron Age to Modern Era",
        "Iron-carbon phase equilibrium and carbon diffusion dictate closed crucible smelting temperatures.",
        "CSIR Metallurgy Studies"
    ],
    [
        "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers",
        "produces",
        "artifact-ukku-steel-crucibles-button-ingots-and-damascus-blades",
        "material_culture",
        "Iron Age to Medieval Era",
        "Closed crucible smelting produces vitreous crucibles and conical Wootz button ingots.",
        "Archaeometry of Indian Steel"
    ],
    [
        "concept-magnetite-iron-sand-reduction-bloomery-sponge-iron-chemistry",
        "feeds",
        "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers",
        "material_culture",
        "Iron Age to Modern Era",
        "Low-carbon sponge iron blooms produced from placer sands serve as the base feed for steel crucibles.",
        "Journal of Materials Science"
    ],
    [
        "institution-uruku-kollan-corporation-of-hereditary-steelmakers-and-armorers",
        "manages",
        "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers",
        "material_culture",
        "Iron Age to Vijayanagara Era",
        "Steelmakers guilds maintained strict trade secrets for furnace construction and crucible ratios.",
        "Blacksmith Guild Charters"
    ],
    [
        "technology-thermo-mechanical-forging-and-clay-quenching-heat-treatment",
        "shapes",
        "artifact-ukku-steel-crucibles-button-ingots-and-damascus-blades",
        "material_culture",
        "Iron Age to Medieval Era",
        "Careful low-temperature forging and differential oil quenching transform raw ingots into Damascus swords.",
        "Sword and the Crucible"
    ],
    [
        "place-mel-siruvalur-ancient-crucible-steel-haven",
        "hosts",
        "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers",
        "material_culture",
        "Iron Age to Sangam Era",
        "Mel-Siruvalur in the Thenpennai basin housed major crucible steel melting installations.",
        "TNSDA Excavation Reports"
    ],
    [
        "concept-damascus-watered-silk-pattern-optical-crystallography",
        "reveals",
        "artifact-ukku-steel-crucibles-button-ingots-and-damascus-blades",
        "material_culture",
        "Iron Age to Modern Era",
        "Mild natural acid etching scatters specular light across spheroidized carbide bands.",
        "Smithsonian Studies"
    ],
    [
        "technology-closed-crucible-steel-pyrotechnics-and-refractory-clay-saggers",
        "discharges",
        "artifact-iron-tuyeres-bellows-nozzles-and-blooming-furnace-slags",
        "material_culture",
        "Iron Age to Medieval Era",
        "Crucible and bloomery operations generate slagged tuyeres and dense fayalite furnace bottoms.",
        "Keezhadi Reports"
    ],
    [
        "text-purananuru-and-patittruppathu-on-blacksmiths-bellows-and-steel-swords",
        "celebrates",
        "place-mel-siruvalur-ancient-crucible-steel-haven",
        "material_culture",
        "Sangam Era",
        "Sangam literature celebrates the glowing armory workshops and legendary swords of the Tamil steel centers.",
        "Patittruppathu 19"
    ]
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=== Phase 1: Markdown Dossiers ===")
    for d in DOSSIERS:
        cat_dir = os.path.join(DOSSIER_DIR, d["category"] + "s")
        os.makedirs(cat_dir, exist_ok=True)
        filepath = os.path.join(cat_dir, d["file"])
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"Wrote dossier: {filepath}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=== Phase 2: Lore Nodes Upsert ===")
    for d in DOSSIERS:
        props = json.dumps({"category": d["category"], "canonical_file": d["file"]})
        cur.execute("""
            INSERT INTO lore_nodes (slug, node_type, name_en, name_ta, era, year_start, year_end, thinai, summary_en, summary_ta, sources, layer, properties)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            d["slug"], d["category"], d["name_en"], d["name_ta"], d["era"],
            d["year_start"], d["year_end"], d["thinai"], d["summary_en"],
            d["summary_ta"], d["sources"], "material_culture", props
        ))
        print(f"Upserted node: {d['slug']}")
    conn.commit()

    print("=== Phase 3: Lore Edges Insert ===")
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, ev = edge
        cur.execute("""
            SELECT 1 FROM lore_edges
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s
        """, (src, rel, tgt))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO lore_edges (source_slug, relation_type, target_slug, layer, era, description, evidence_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (src, rel, tgt, layer, era, desc, ev))
            print(f"Inserted edge: {src} -> {tgt} ({rel})")
        else:
            print(f"Edge exists: {src} -> {tgt} ({rel})")
    conn.commit()

    print("=== Phase 4: RAG Chunks Embedding ===")
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
            emb = get_embedding(ch["content"])
            cur.execute("""
                INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                slug,
                f"shelf-{d['category']}s",
                ch["language"],
                ch["title"],
                ch["content"],
                d["sources"][0] if d["sources"] else "Oral Tradition",
                emb,
            ))
        print(f"Embedded 2 chunks for: {slug}")
    conn.commit()

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
