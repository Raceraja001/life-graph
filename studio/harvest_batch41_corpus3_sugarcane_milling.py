#!/usr/bin/env python3
"""
Harvester: Batch 41 - Ancient Tamil Cane Sugar Milling, Jaggery Crystallization & Alambadi Boiling Hydraulics
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

# The knowledge tree uses real English plurals ("technologies", not "technologys").
CATEGORY_DIRS = {
    "technology": "technologies",
    "archaeology": "archaeology",
    "history": "history",
    "science": "science",
}


def category_dir(category: str) -> str:
    return CATEGORY_DIRS.get(category, category + "s")


DOSSIERS = [
    {
        "slug": "text-perumpanarruppadai-and-purananuru-on-sugarcane-milling-mills",
        "category": "text",
        "file": "text-perumpanarruppadai-and-purananuru-on-sugarcane-milling-mills.md",
        "name_en": "Perumpanarruppadai & Purananuru Verses on Sugarcane Crushers and Boiling Furnaces",
        "name_ta": "பெரும்பாணாற்றுப்படை மற்றும் புறநானூற்று கரும்பாலை, சாறு பிழிதல் மற்றும் வெல்லப் பாகு பாடல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Sangam poems describing roaring sugarcane crushers ('Karumbu-Aalai') sounding like trumpet calls of rutting war elephants, crushing thick black cane, and boiling sweet juice in massive open iron vats over bagasse flames.",
        "summary_ta": "போர்க்கள யானைகளின் முழக்கம் போல ஒலிக்கும் கரும்பாலைகள், கரும்புச் சாறு பிழிதல் மற்றும் பெரும் கொப்பரைகளில் பாகு காய்ச்சுதல் பற்றிய பெரும்பாணாற்றுப்படை மற்றும் புறநானூற்றுப் பாடல்கள்.",
        "sources": [
            "Perumpanarruppadai 260-264",
            "Purananuru 322",
            "Ainkurunuru 54",
            "Pattinappalai 10-15"
        ],
        "content": "# Perumpanarruppadai & Purananuru on Sugarcane Milling\n\nSangam literature provides vivid descriptions of hydraulic and animal-driven sugarcane milling across fertile river valleys:\n\n**Literary Testimonies:**\n- **Perumpanarruppadai (lines 260-264)**: Portrays the agrarian Marutham landscape where sugarcane press machines (*Karumbu-Aalai*) groan under the turning of heavy ox-driven timbers, echoing like trumpeting elephants (*kai-punai yanaiyin muzhangum*). Sweet juice flows in frothing rivulets toward bubbling iron boiling cauldrons.\n- **Purananuru (Verse 322)**: Describes the thick sweet scent of boiling cane juice (*paagu*) spreading through the hamlet, drawing bees and passing travelers.\n- **Pattinappalai (lines 10-15)**: Mentions vast coastal and riparian estates where sugar cane was crushed alongside paddy threshing grounds."
    },
    {
        "slug": "concept-saccharum-officinarum-sucrose-osmosis-and-phloem-ripening",
        "category": "concept",
        "file": "concept-saccharum-officinarum-sucrose-osmosis-and-phloem-ripening.md",
        "name_en": "Saccharum Officinarum Sucrose Osmosis, Phloem Accumulation & Stalk Ripening",
        "name_ta": "கரும்பு தாவர உடலியல், புளோயம் சாறு சுக்ரோஸ் திரட்சி மற்றும் தண்டு முதிர்ச்சி இயக்கவியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Botanical and biochemical physiology of South Indian noble sugarcane (Saccharum officinarum): sucrose translocation across stalk parenchyma vacuoles, invertase enzyme downregulation during dry ripening, and Brix concentration metrics.",
        "summary_ta": "இந்திய பாரம்பரியக் கரும்பின் உடலியல் மற்றும் சர்க்கரைத் திரட்சி: தண்டின் பாரன்கைமா செல்களில் சுக்ரோஸ் சேமிப்பு, இன்வெர்டேஸ் என்சைம் கட்டுப்பாடு மற்றும் பிரிக்ஸ் அடர்த்தி.",
        "sources": [
            "Sugarcane Breeding Institute Coimbatore Monographs",
            "Plant Physiology & Biochemistry Journal",
            "Agricultural Botany Studies"
        ],
        "content": "# Saccharum Officinarum Sucrose Physiology & Stalk Ripening\n\nIndigenous sugarcane (*Karumbu*, *Saccharum officinarum*) was cultivated in alluvial silt terraces of Tamil rivers for millennia:\n\n**Biochemical Maturation:**\n- **Sucrose Storage**: Synthesized in photosynthetic leaves, sucrose is translocated via phloem sieve tubes and stored in large central vacuoles of stalk parenchyma cells, reaching concentrations of 18–22% by fresh weight.\n- **Dry Ripening Phase**: Ripening occurs during the cooler, rain-free post-monsoon months (December–March). Acid invertase enzymes downregulate, suppressing hydrolysis of sucrose into reducing hexoses (glucose and fructose).\n- **Quality Indicators**: Harvesters tested stalks by fracture brittleness and metallic resonance when tapped, ensuring a Brix reading >20° before feeding stalks into the crushers."
    },
    {
        "slug": "technology-animal-driven-three-roller-vertical-crusher-milling",
        "category": "technology",
        "file": "technology-animal-driven-three-roller-vertical-crusher-milling.md",
        "name_en": "Animal-Driven Three-Roller Vertical Hardwood Sugarcane Crusher Milling",
        "name_ta": "மாட்டு இழுவை கொண்ட மூன்று மர உருளை செங்குத்து கரும்பாலை பிழிதல் தொழில்நுட்பம்",
        "era": "Early Historic to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Mechanical engineering of traditional Tamil sugarcane mills: vertical geared cylindrical hardwood rollers (tamarind or vaagai), mortise-tenon wooden gearing, bullock sweep draft, and channeled juice collection troughs.",
        "summary_ta": "பண்டைய கரும்பாலையின் இயந்திரக் கட்டமைப்பு: புளியமரம் அல்லது வாகை மரத்திலான மூன்று செங்குத்து பற்சக்கர உருளைகள், எருது இழுவை மற்றும் சாறு வழிந்தோடும் கால்வாய் அமைப்பு.",
        "sources": [
            "Indian Journal of History of Science",
            "Ancient Sugar Machinery in Tamil Nadu",
            "Tamil Agricultural Technology Memoirs"
        ],
        "content": "# Three-Roller Vertical Sugarcane Crusher Milling\n\nThe extraction of sweet juice from fibrous sugarcane stalks required robust mechanical advantages achieved through animal-powered timber mills:\n\n**Crusher Architecture:**\n1. **Vertical Geared Rollers**: Three cylindrical rollers carved from ultra-dense seasoned tamarind (*Tamarindus indica*) or ironwood (*Vaagai*) were mounted vertically in a rigid hardwood frame.\n2. **Meshed Wooden Gearing**: Spiral or peg-and-socket teeth carved into roller crowns transferred torque from a central drive roller to adjacent follower rollers.\n3. **Bullock Sweep Sweep**: A long horizontal beam (sweep) extending 4–6 meters was hitched to a pair of Kangayam draught bullocks walking in a continuous circular track.\n4. **Compression Mechanism**: Stalks were manually guided through narrow gaps between rotating rollers twice, squeezing out 60–65% of available juice, which drained into terracotta cisterns."
    },
    {
        "slug": "artifact-kopparai-iron-boiling-pans-bagasse-rakes-and-jaggery-molds",
        "category": "artifact",
        "file": "artifact-kopparai-iron-boiling-pans-bagasse-rakes-and-jaggery-molds.md",
        "name_en": "Kopparai Shallow Wrought-Iron Boiling Pans, Bagasse Rakes & Terracotta Molds",
        "name_ta": "இரும்புக் கொப்பரைகள், சக்கை தள்ளும் வாரிகள் மற்றும் அச்சு வெல்ல சுடுமண் தட்டுகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The tool suite of ancient Tamil sugar manufacture: massive shallow wrought-iron cauldrons (kopparai), perforated skimming ladles, long-handled bagasse fuel rakes, wooden cooling troughs, and inverted conical jaggery molds.",
        "summary_ta": "கரும்பு வெல்லம் தயாரிக்கும் பாரம்பரிய உபகரணங்கள்: அகன்ற வார்ப்பிரும்பு கொப்பரைகள், நுரை நீக்கும் கரண்டிகள், சக்கை வாரிகள், மரக் குளிரூட்டும் தொட்டிகள் மற்றும் அச்சு வெல்ல தட்டுகள்.",
        "sources": [
            "Madras Government Museum Industrial Arts Catalog",
            "Thanjavur Agrarian Implement Collections",
            "Tamil Traditional Metallurgy Reports"
        ],
        "content": "# Kopparai Boiling Pans & Jaggery Processing Tools\n\nProcessing raw cane juice into stable solid jaggery required an ensemble of specialized heavy-duty implements:\n\n**Equipment Inventory:**\n- **Kopparai Boiling Vats**: Shallow, open-pan cauldrons forged from wrought iron or riveted copper plates, spanning 1.5 to 2.5 meters in diameter with flanged rims, optimizing surface evaporation.\n- **Skimming Ladles (*Kottu-Karandi*)**: Broad brass or perforated iron discs fitted to long bamboo poles, used to skim coagulated impurities and proteins from the boiling surface.\n- **Cooling Troughs (*Doni*)**: Long rectangular hollowed jackfruit-wood troughs where supersaturated syrup was aerated with wooden paddles to initiate seed crystallization.\n- **Conical Molds (*Achu*)**: Terracotta or turned wooden molds where warm syrup solidified into uniform golden-brown cone or block jaggery (*Achu Vellam*)."
    },
    {
        "slug": "concept-sucrose-supersaturation-crystallization-kinetics-and-lime-clarification",
        "category": "concept",
        "file": "concept-sucrose-supersaturation-crystallization-kinetics-and-lime-clarification.md",
        "name_en": "Sucrose Supersaturation Kinetics, Slaked Lime Clarification & Mucilage Scum Skimming",
        "name_ta": "சுக்ரோஸ் மிகைசெறிவுப் படிகமாக்கல், சுண்ணாம்புத் தெளிவு மற்றும் வெண்டைக்காய் பசை நுரைநீக்கம்",
        "era": "Iron Age to Modern Era",
        "year_start": -800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The chemical physics of traditional sugar boiling: open-pan heat concentration to 118°C-120°C, slaked lime (Ca(OH)2) addition to neutralize organic acids, herbal mucilage (wild okra / Abelmoschus) flocculation, and sucrose nucleation.",
        "summary_ta": "வெல்லப் பாகு காய்ச்சும் வேதியியல்: 118°C-120°C வரை வெப்பமூட்டுதல், அமில சமநிலைக்கு சுண்ணநீர் சேர்த்தல், காட்டு வெண்டை பசை கொண்டு கசடு நீக்குதல் மற்றும் படிகமாதல்.",
        "sources": [
            "Sugar Technology International",
            "Indian Chemical Society Transactions",
            "Journal of Food Science and Technology"
        ],
        "content": "# Sucrose Supersaturation Kinetics & Lime Clarification\n\nTransforming perishable cane juice into shelf-stable, crystalline jaggery (*Vellam*) involves meticulous chemical thermodynamics:\n\n**Chemical Transformations:**\n1. **Neutralization & Clarification**: Fresh cane juice has an acidic pH of 5.0–5.4. Master boilers introduced controlled aliquots of slaked lime ($\\\\text{Ca}(\\\\text{OH})_2$) milk to raise pH to 6.2–6.5, arresting sucrose inversion into non-crystallizing glucose.\n2. **Herbal Flocculation**: Macerated mucilaginous extract of wild okra (*Vendai / Abelmoschus esculentus*) was stirred into the simmering pan. The natural plant proteins act as colloidal coagulants, binding suspended pectins, gums, and cellular debris into a buoyant scum that rises to the rim for easy skimming.\n3. **Thermal Supersaturation**: As water evaporated, the syrup reached the critical striking point ($118^\\\\circ\\\\text{C}-120^\\\\circ\\\\text{C}$, 82–84% solids). When a drop cooled in water formed a soft pliable ball (*Pagu-Urundai*), the vat was immediately discharged to induce crystallization."
    },
    {
        "slug": "institution-karumbu-uzhavar-and-vellam-vaanigar-sugar-planters-corporation",
        "category": "institution",
        "file": "institution-karumbu-uzhavar-and-vellam-vaanigar-sugar-planters-corporation.md",
        "name_en": "Karumbu-Uzhavar & Vellam-Vaanigar Corporation: Sugarcane Planters & Jaggery Merchants Guild",
        "name_ta": "கரும்பு உழவர் மற்றும் வெல்ல வணிகர் சபை: கரும்பு விவசாயிகள் மற்றும் சர்க்கரை வர்த்தகக் கூட்டமைப்பு",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "The agrarian and mercantile guild network controlling sugarcane estate management, collective mill operation, seasonal labor mobilization, and trans-regional transport of crystalline sugar and jaggery blocks.",
        "summary_ta": "கரும்பு சாகுபடி, ஆலை இயக்கம் மற்றும் வெல்ல வர்த்தகத்தை ஒருங்கிணைத்த பண்டைய வணிகர் மற்றும் உழவர் பெருமன்றம்: காவேரி மற்றும் பாலாற்றுப் படுகைகளின் வர்த்தக நெட்வொர்க்.",
        "sources": [
            "South Indian Inscriptions: Kaveri Delta Sugar Endowments",
            "Imperial Chola Agrarian Epigraphy",
            "Sangam Economic History"
        ],
        "content": "# Karumbu-Uzhavar & Vellam-Vaanigar Guild\n\nThe capital-intensive nature of sugarcane milling necessitated cooperative guild structures among riverine landowners and merchants:\n\n**Guild Functions:**\n- **Collective Mill Infrastructure**: Shared capital investment in seasoned hardwood rollers, draught oxen, and expensive iron boiling pans (*Kopparai*), rotating crushing schedules among farming lineages.\n- **Temple Confectionery Endowments**: Supplied standardized jaggery (*Achu Vellam*) and refined crystallized sugar (*Sarkkarai / Karkandu*) for temple *naivedyam* (sweet pongal, payasam) mandated in Chola royal inscriptions.\n- **Caravan Distribution**: Packed jaggery in woven palm-leaf sacks loaded onto pack bullocks for inland distribution to Chera hill countries and coastal ports."
    },
    {
        "slug": "technology-multi-stage-open-pan-evaporation-and-bagasse-flue-furnaces",
        "category": "technology",
        "file": "technology-multi-stage-open-pan-evaporation-and-bagasse-flue-furnaces.md",
        "name_en": "Multi-Stage Open Pan Evaporation & Self-Sustaining Bagasse Flue Furnaces",
        "name_ta": "பலபடி திறந்த கொப்பரை ஆவியாதல் மற்றும் கரும்புச் சக்கை எரிவாயுக் காற்றுச் சூளை",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Energy-efficient thermal pyrotechnics of ancient Tamil sugar camps: semi-underground brick furnaces fueled entirely by sun-dried crushed cane residue (bagasse), with channeled flues directing heat under multi-stage boiling pans.",
        "summary_ta": "கரும்பு சக்கையை மட்டுமே எரிபொருளாகப் பயன்படுத்திய சுயசார்பு சூளை அமைப்பு: நிலத்தடி காற்றுப் பாதைகள் மூலம் வெப்பத்தை வரிசையான கொப்பரைகளுக்குப் பகிர்ந்தளிக்கும் முறை.",
        "sources": [
            "Tamil Agricultural Engineering Studies",
            "Journal of Rural Technology",
            "Ethno-Technology of Indian Sugar"
        ],
        "content": "# Multi-Stage Open Pan Evaporation & Bagasse Flue Furnaces\n\nThe boiling of thousands of liters of watery cane juice required tremendous thermal energy, resolved through self-sustaining pyrotechnic furnace engineering:\n\n**Furnace Architecture:**\n- **Zero-Waste Combustion**: Crushed sugarcane stalks (*bagasse*) were spread on field bunds to sun-dry, providing 100% of the combustible fuel required for the entire boiling season.\n- **Channeled Flue Design**: An excavated sunken hearth (*aduppu*) drew fresh air through an inclined subterranean draft channel. Hot flue gases passed horizontally under a series of two or three staggered pans (settling, boiling, and striking pans).\n- **Thermal Efficiency**: Incoming raw juice was pre-heated in the tail pan by exhaust gases before transfer to the roaring primary fire pan, cutting fuel expenditure by 40%."
    },
    {
        "slug": "place-amur-ancient-chola-sugarcane-milling-haven",
        "category": "place",
        "file": "place-amur-ancient-chola-sugarcane-milling-haven.md",
        "name_en": "Amur: Ancient Chola Sugarcane Milling Haven, Kaveri Riparian Sugar Basin & Milling Citadel",
        "name_ta": "ஆமூர் - பண்டைய சோழர் கரும்பாலைத் தளம், காவேரி ஆற்றுப் படுகை சர்க்கரை உற்பத்தி மையம்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic agrarian sugar manufacturing citadel on the Kaveri River basin in Tiruchirappalli district, celebrated in Sangam poems and Chola epigraphs as an expansive sugar basin of perpetual sugarcane crushers, sweet syrup vats, and jaggery markets.",
        "summary_ta": "திருச்சிராப்பள்ளி மாவட்டத்தில் காவேரி ஆற்றுப் படுகையில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க கரும்பு உற்பத்தி மையம்: சங்கப் பாடல்களிலும் சோழர் கல்வெட்டுகளிலும் புகழ்பெற்ற கரும்பாலைகள் மற்றும் வெல்ல சந்தைகளின் தாயகம்.",
        "sources": [
            "Tiruchirappalli District Gazetteer",
            "South Indian Inscriptions Vol. VIII",
            "Sangam Geography of the Kaveri Delta"
        ],
        "content": "# Amur: Ancient Chola Sugarcane Milling Haven\n\nAmur, situated along the fertile alluvial banks of the Kaveri near Musiri, has stood for over two millennia as the preeminent heartland of Tamil sugarcane culture:\n\n**Historical Significance:**\n- **Sangam Celebrations**: Celebrated in *Purananuru* and *Ahananuru* as a wealthy riparian haven where the air perpetually carried the caramel aroma of boiling cane juice and the mechanical rumbling of sugarcane mills.\n- **Chola Inscriptional Records**: Epigraphs from the reign of Rajaraja I and Rajendra I document mandatory tax payments and temple donations paid directly in *katti-vellam* (block jaggery) processed in Amur's communal mills.\n- **Hydraulic Endowment**: Ancient river channels diverted from the Kaveri provided perennial irrigation to dense sugarcane cane plantations, maintaining year-round sugar milling."
    },
    {
        "slug": "concept-amorphous-jaggery-block-solidification-and-hygroscopic-storage",
        "category": "concept",
        "file": "concept-amorphous-jaggery-block-solidification-and-hygroscopic-storage.md",
        "name_en": "Amorphous Jaggery Block Solidification, Moisture Equilibrium & Palm-Leaf Storage",
        "name_ta": "வெல்லக் கட்டி திடமாதல் இயற்பியல், ஈரப்பத சமநிலை மற்றும் பனை ஓலைப் பெட்டி சேமிப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The physical chemistry of jaggery cooling, micro-crystalline matrix solidification, equilibrium relative humidity, and traditional storage techniques using desiccating lime dust and breathable woven palm-leaf containers (kottan).",
        "summary_ta": "வெல்லப் பாகு ஆறி கெட்டிப்படும் இயற்பியல் மாற்றங்கள், ஈரப்பதக் கட்டுப்பாடு மற்றும் கெடாமல் பாதுகாக்க பனை ஓலைப் பெட்டிகளில் சேமிக்கும் பாரம்பரிய முறை.",
        "sources": [
            "Food Packaging and Shelf Life Journal",
            "Indian Sugar Technology Transactions",
            "Traditional Food Preservation Systems"
        ],
        "content": "# Amorphous Jaggery Solidification & Storage Physics\n\nSolidified jaggery (*Vellam*) is a complex food matrix consisting of microcrystalline sucrose enveloped in a film of amorphous molasses, invert sugars, and mineral salts:\n\n**Storage Physics & Degradation Prevention:**\n- **Hygroscopic Sensitivity**: Due to the presence of reducing sugars (glucose and fructose) and mineral salts (potassium and calcium), jaggery absorbs moisture from the atmosphere when ambient relative humidity exceeds 65%, triggering microbial souring and liquefaction.\n- **Crystalline Setting**: Thorough aeration during cooling forms millions of micro-crystals of sucrose, yielding a fine, crumble-resistant grain structure.\n- **Breathable Palm Leaf Storage (*Kottan*)**: Traditional producers packed hardened jaggery cakes in multilayered woven palmyra leaf baskets lined with dry paddy straw and dusting powder of quicklime, allowing moisture vapor to escape while blocking liquid condensation."
    },
    {
        "slug": "artifact-palmyra-jaggery-leaves-measuring-scales-and-sugar-caravans",
        "category": "artifact",
        "file": "artifact-palmyra-jaggery-leaves-measuring-scales-and-sugar-caravans.md",
        "name_en": "Palmyra Jaggery Packing Baskets, Bronze Balance Beams & Sugar Sacks",
        "name_ta": "பனை ஓலை வெல்லப் பெட்டிகள், வெண்கலத் துலாக்கோல் மற்றும் சர்க்கரை பொதி மூட்டைகள்",
        "era": "Sangam to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Trade equipment and packaging artifacts of the ancient Tamil sugar trade: woven palmyra containers (kottan), calibrated bronze balance beams (thula-kool), stone standard weights, and bullock pack-saddles.",
        "summary_ta": "பண்டைய சர்க்கரை வர்த்தகப் பொருட்கள்: பனை ஓலைப் பெட்டிகள், துல்லியமான வெண்கலத் தராசுகள், நிறுத்தல் கற்கள் மற்றும் மாட்டு வண்டிப் பொதி சாதனங்கள்.",
        "sources": [
            "Kaveripoompattinam Commercial Artifact Catalog",
            "Madras Museum Metrology Collection",
            "South Indian Mercantile Epigraphy"
        ],
        "content": "# Jaggery Packing Baskets, Scales & Caravan Artifacts\n\nThe commercialization of sugar produced a specialized trade artifact assemblage across Tamil Nadu:\n\n**Artifact Typology:**\n- **Woven Kottan Baskets**: Platted from split palmyra leaflets, these standardized cylindrical containers held between 5 and 20 *palam* of block jaggery, protected against mechanical damage during transport.\n- **Bronze Steelyards & Scales (*Thula-Kool*)**: Calibrated bronze balance beams inscribed with royal Chola seal stamps, used at toll-stations (*sungachavadi*) to tax sugar consignments.\n- **Sugar Pack-Saddles (*Goni-Pothi*)**: Coarse jute and hemp sacks slung in pairs across bullock backs, transported in armed merchant caravans guarded by *Valanjiyar* warrior escorts."
    }
]

EDGES = [
    [
        "text-perumpanarruppadai-and-purananuru-on-sugarcane-milling-mills",
        "describes",
        "technology-animal-driven-three-roller-vertical-crusher-milling",
        "material_culture",
        "Sangam Era",
        "Sangam poems describe roaring ox-driven sugarcane crushers echoing across riverine villages.",
        "Perumpanarruppadai 260-264"
    ],
    [
        "concept-saccharum-officinarum-sucrose-osmosis-and-phloem-ripening",
        "supplies",
        "technology-animal-driven-three-roller-vertical-crusher-milling",
        "material_culture",
        "Iron Age to Modern Era",
        "Ripened high-Brix cane stalks are crushed to extract sucrose-rich juice.",
        "Sugarcane Breeding Institute"
    ],
    [
        "technology-animal-driven-three-roller-vertical-crusher-milling",
        "feeds",
        "artifact-kopparai-iron-boiling-pans-bagasse-rakes-and-jaggery-molds",
        "material_culture",
        "Early Historic to Medieval Era",
        "Cane mills extract juice that flows directly into shallow iron boiling cauldrons.",
        "Ancient Sugar Machinery"
    ],
    [
        "concept-sucrose-supersaturation-crystallization-kinetics-and-lime-clarification",
        "governs",
        "technology-multi-stage-open-pan-evaporation-and-bagasse-flue-furnaces",
        "material_culture",
        "Iron Age to Modern Era",
        "Lime neutralization, mucilage skimming, and thermal evaporation dictate furnace operation.",
        "Sugar Technology International"
    ],
    [
        "technology-multi-stage-open-pan-evaporation-and-bagasse-flue-furnaces",
        "heats",
        "artifact-kopparai-iron-boiling-pans-bagasse-rakes-and-jaggery-molds",
        "material_culture",
        "Sangam to Medieval Era",
        "Sunken bagasse furnaces heat multi-pan iron cauldrons to boil syrup to striking point.",
        "Tamil Agricultural Studies"
    ],
    [
        "institution-karumbu-uzhavar-and-vellam-vaanigar-sugar-planters-corporation",
        "manages",
        "place-amur-ancient-chola-sugarcane-milling-haven",
        "material_culture",
        "Sangam to Chola Era",
        "Sugar planter and merchant guilds operated communal mills and jaggery markets in Amur.",
        "South Indian Inscriptions"
    ],
    [
        "place-amur-ancient-chola-sugarcane-milling-haven",
        "hosts",
        "technology-animal-driven-three-roller-vertical-crusher-milling",
        "material_culture",
        "Iron Age to Modern Era",
        "Amur served as an expansive sugarcane milling haven in the Kaveri Delta.",
        "Tiruchirappalli Gazetteer"
    ],
    [
        "concept-amorphous-jaggery-block-solidification-and-hygroscopic-storage",
        "preserves",
        "artifact-palmyra-jaggery-leaves-measuring-scales-and-sugar-caravans",
        "material_culture",
        "Iron Age to Modern Era",
        "Moisture equilibrium physics dictates packing in breathable woven palm-leaf kottan containers.",
        "Food Packaging Journal"
    ],
    [
        "institution-karumbu-uzhavar-and-vellam-vaanigar-sugar-planters-corporation",
        "trades",
        "artifact-palmyra-jaggery-leaves-measuring-scales-and-sugar-caravans",
        "material_culture",
        "Sangam to Chola Era",
        "Guild merchants weighed jaggery with bronze scales and transported it in pack-bullock caravans.",
        "Kaveripoompattinam Catalog"
    ],
    [
        "text-perumpanarruppadai-and-purananuru-on-sugarcane-milling-mills",
        "celebrates",
        "place-amur-ancient-chola-sugarcane-milling-haven",
        "material_culture",
        "Sangam Era",
        "Sangam literature celebrates the sweet scent and bustling sugar economy of Kaveri basin citadels like Amur.",
        "Purananuru 322"
    ]
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=== Phase 1: Markdown Dossiers ===")
    for d in DOSSIERS:
        cat_dir = os.path.join(DOSSIER_DIR, category_dir(d["category"]))
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
        title = d["name_en"]
        slug = d["slug"]
        text_en = d["summary_en"] + " " + d["content"][:800]
        emb_en = get_embedding(text_en)
        cur.execute("""
            INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (slug, d["category"], "en", title + " (Overview)", text_en, d["sources"][0] if d["sources"] else "Oral Tradition", emb_en))

        text_ta = d["summary_ta"] + " " + d["name_ta"]
        emb_ta = get_embedding(text_ta)
        cur.execute("""
            INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (slug, d["category"], "ta", d["name_ta"] + " (கண்ணோட்டம்)", text_ta, d["sources"][0] if d["sources"] else "Oral Tradition", emb_ta))
        print(f"Embedded 2 chunks for: {slug}")
    conn.commit()

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
