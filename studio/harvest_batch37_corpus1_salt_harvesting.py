#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Tidal Salt Harvesting, Solar Evaporation Pan Hydraulics & Brine Chemistry
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
        "file": "knowledge/texts/text-perumpanattruppadai-verses-on-white-salt-mounds-and-eyilpattinam-pan-workers.md",
        "slug": "text-perumpanattruppadai-verses-on-white-salt-mounds-and-eyilpattinam-pan-workers",
        "category": "text",
        "name_en": "Perumpanattruppadai: Classical Verses on Glistening Salt Mounds & Eyilpattinam Salterns",
        "name_ta": "பெரும்பாணாற்றுப்படை - எயிற்பட்டினம் உப்பளங்கள், வெண்மழை போன்ற உப்புக் குவியல்கள் மற்றும் உமணர் இலக்கியப் பாடல்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Kadiyalur Uruthirankannanar's classical Sangam verses in Perumpanattruppadai describing coastal tidal salt pans (alalam) at Eyilpattinam (Marakkanam) with blinding white mounds of solar salt.",
        "summary_ta": "கடியலூர் உருத்திரங்கண்ணனார் பாடிய பெரும்பாணாற்றுப்படையில், எயிற்பட்டினத்து (மரகானம்) உப்பளங்களில் வெண் மேகக் குன்றுகள் போலக் குவிக்கப்பட்ட சூரிய உப்பின் காட்சிகளை விவரிக்கும் சங்கப் பாடல்.",
        "sources": [
            "Perumpanattruppadai 315-330",
            "Natrinai 311",
            "Akananuru 140"
        ],
        "content": "# Perumpanattruppadai: White Salt Mounds & Eyilpattinam Salterns\n\nIn *Perumpanattruppadai* (lines 315–330), the Sangam bard Kadiyalur Uruthirankannanar paints an unforgettable portrait of the maritime emporium of *Eyilpattinam* (modern Marakkanam):\n\n> \"Along the wide coastal estuaries where tidal surges fill shallow earthen pans (*alalam*), the searing summer sun crystallizes the brine into sparkling grains... Staked high like glistening peaks of white summer clouds (*ven-mazhai*), the purified salt is guarded day and night by bow-wielding guards against roaming birds and wild boars, awaiting the heavy bullock wains of the roaming *Umanar* traders.\"\n\nThis ancient poem attests that solar salt evaporation was an organized industrial enterprise producing immense surplus commodities for trans-peninsular and maritime commerce."
    },
    {
        "file": "knowledge/concepts/concept-uppalam-tidal-solar-evaporation-and-brine-crystallization-thermodynamics.md",
        "slug": "concept-uppalam-tidal-solar-evaporation-and-brine-crystallization-thermodynamics",
        "category": "concept",
        "name_en": "Uppalam: Tidal Saltern Thermodynamics, Fractional Evaporation & Halite Precipitation",
        "name_ta": "உப்பளம் - கடல் அலைமடை நீரியல், தொடர் சூரிய ஆவியாதல் மற்றும் சோடியம் குளோரைடு படிகமாதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Hydrodynamic and physical chemical mechanics of multi-stage solar salterns, progressively precipitating calcium carbonate and gypsum before crystallizing pure sodium chloride (halite) at 25-28° Baumé.",
        "summary_ta": "கடல் நீரைத் தொடர்ச்சியான மட்டப்படுக்கைகளில் பாய்ச்சி, சுண்ணாம்பு, ஜிப்சம் போன்றவற்றை முன்கூட்டியே படியவைத்து, 25-28 டிகிரி போமே அடர்த்தியில் தூய உப்பைப் பிரித்தெடுக்கும் இயற்பியல் வேதியியல்.",
        "sources": [
            "Industrial Saltern Engineering in South India",
            "Journal of Marine Technology and Chemical Sciences",
            "Sangam Salt Metallurgy Commentaries"
        ],
        "content": "# Uppalam: Tidal Saltern Thermodynamics & Crystallization\n\nAncient Tamil salterns (*uppalam*) operated on sophisticated principles of fractional precipitation:\n\n- **Reservoir Stage (*Thaangal*)**: High spring tides filled deep estuarine catchment ponds, trapping seawater at normal oceanic salinity (approx. 3.5° Baumé / 35 ppt).\n- **Evaporator Condensers (*Kallam*)**: Water was gravity-fed into shallow clay-lined earthen pans where solar insolation increased brine concentration. At 15° Baumé, calcium carbonate and iron oxides dropped out of solution.\n- **Crystallizer Pans (*Paathi*)**: Dense saturated mother liquor (*alalam*) was channeled into impeccably leveled pans at 25° Baumé. Here, cubic crystals of sodium chloride ($NaCl$) precipitated en masse, while bitter magnesium chloride and sulfate salts remained dissolved in the residual bitterns (*kadi-neer*), which were drained away before final scraping."
    },
    {
        "file": "knowledge/technologies/technology-alalam-and-paathi-clay-bund-pan-engineering-and-saline-sluicing.md",
        "slug": "technology-alalam-and-paathi-clay-bund-pan-engineering-and-saline-sluicing",
        "category": "technology",
        "name_en": "Alalam & Paathi: Puddled Clay Saltern Engineering, Bund Construction & Tidal Sluice Gates",
        "name_ta": "அளலம் மற்றும் பாத்தி - களிமண் தரை பதப்படுத்துதல், வரப்பு அமைத்தல் மற்றும் அலைமடை மதகு நீரியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Civil and hydraulic engineering of coastal saltern pans using marine alluvial clays compacted with wooden rammers to form impermeable pan floors, retaining bunds, and sluice regulators.",
        "summary_ta": "கடலோரக் களிமண்ணை மரத்தடிகளால் அடித்து கெட்டிப்படுத்தி, நீர் கசியாத உப்பளத் தரைகளையும், அலை நீரை முறைப்படுத்தும் பலகை மதகுகளையும் அமைக்கும் கட்டமைப்பு நுட்பம்.",
        "sources": [
            "Natrinai 254",
            "Archaeological Surveys of Coromandel Salterns",
            "Traditional Salt Manufacture in Coastal Tamil Nadu"
        ],
        "content": "# Alalam & Paathi: Saltern Pan Engineering & Sluicing\n\nConstructing high-efficiency salterns on porous coastal backwaters demanded rigorous earthworks engineering:\n\n- **Clay Bed Compaction (*Tharai-Mithi*)**: Artisans dug out sandy topsoil and refilled pans with impermeable dark alluvial clay (*kali-man*). Pan bottoms were repeatedly flooded with brine and trampled by teams of workers and beaten with flat wooden tampers until forming an impermeable, glass-smooth floor preventing brine seepage.\n- **Graded Bund Walls (*Paathi-Varappu*)**: Compacted earth bunds (0.5m high) separated adjacent pans, engineered with a gentle slope of 1:500 to enable effortless gravity transfer of evaporating brine from one basin to the next.\n- **Wooden Sluice Gates (*Madagu*)**: Estuarine channels featured teak or palmyra wood drop-boards that opened during high tide surges to admit seawater and shut during ebb tide to trap the volume."
    },
    {
        "file": "knowledge/artifacts/artifact-uppu-thadavai-and-marakkal-wooden-scraping-boards-and-salt-measures.md",
        "slug": "artifact-uppu-thadavai-and-marakkal-wooden-scraping-boards-and-salt-measures",
        "category": "artifact",
        "name_en": "Uppu-Thadavai & Marakkal: Hardwood Brine Scrapers, Drainage Rakes & Certified Volumetric Measures",
        "name_ta": "உப்புத் தடவை மற்றும் மரக்கால் - தேக்கு மர உப்பு வழிப்பான், வடிப்பு வாரல் மற்றும் முத்திரை மரக்கால்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Specialized wooden harvesting implements including broad curved scraping boards (thadavai) to gather delicate salt crystals without gouging clay floors, and royal stamped marakkal dry-measures.",
        "summary_ta": "களிமண் தரை சேதமடையாமல் உப்பை வாரியெடுக்கும் தேக்கு மர வழிப்பான் பலகை மற்றும் வர்த்தகத்தில் பயன்பட்ட அரச முத்திரையிட்ட மரக்கால் அளவைகள்.",
        "sources": [
            "Akananuru 390",
            "Korkai Archaeological Artifact Catalogs",
            "Inscriptions of Pandya Sadaiyan Maran"
        ],
        "content": "# Uppu-Thadavai & Marakkal: Harvesting Implements & Dry Measures\n\nExtracting pristine, sand-free salt crystals from fragile clay pan floors required specialized tools:\n\n- **The Scraping Board (*Uppu-Thadavai*)**: A wide, bevel-edged board fashioned from durable teak or neem wood, fitted with a long bamboo handle. Workers pulled the scraper gently across the water-salt interface, gathering crystallized salt ridges without disturbing the underlying compacted clay seal.\n- **Perforated Wooden Rakes (*Vadi-Vaali*)**: Slotted paddles allowed residual acidic mother liquor (*bitterns*) to drain back into disposal ditches, leaving dry white sodium chloride grains.\n- **Standardized Salt Dry-Measures (*Marakkal*)**: The barter of salt for paddy required strictly calibrated wooden dry measures bearing royal fish or tiger insignias, ensuring zero volumetric fraud during caravan exchanges."
    },
    {
        "file": "knowledge/concepts/concept-alalam-saline-microbiology-and-halophilic-crystal-purification.md",
        "slug": "concept-alalam-saline-microbiology-and-halophilic-crystal-purification",
        "category": "concept",
        "name_en": "Alalam-Biota: Halophilic Archaea, Solar Energy Absorption & Natural Crystal Bleaching",
        "name_ta": "அளலம் உயிரியல் - உவர்நீர் நுண்ணுயிரிகள், சூரிய வெப்ப ஈர்ப்பு மற்றும் இயற்கை படிக வெண்மை நுட்பம்",
        "era": "Prehistoric to Modern Era",
        "year_start": -1000,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Microbiological and solar interactions in high-salinity pans where red carotenoid-producing halophilic archaea (Dunaliella salina / Halobacterium) absorb sunlight to accelerate evaporation and yield sparkling white crystals.",
        "summary_ta": "அதி-உவர்நீர் நிலைகளில் வாழும் சிவப்பு நுண்-ஆல்காக்கள் சூரிய ஒளியை ஈர்த்து ஆவியாதலை விரைவுபடுத்துவதோடு, வெயில் மூலம் உப்புப் படிகங்களை வெண்மையாக்கும் சூழலியல் நுட்பம்.",
        "sources": [
            "Applied and Environmental Microbiology on Marine Solar Salterns",
            "Traditional Ecological Knowledge of Coastal Tamil Nadu",
            "Sangam Environmental Lexicon"
        ],
        "content": "# Alalam-Biota: Halophilic Ecology & Solar Evaporation\n\nThe pristine quality of ancient Coromandel salt was enhanced by natural biogeochemical cycles in hypersaline pans:\n\n- **The Halophilic Color Shift**: As brine crossed 20° Baumé, green micro-algae gave way to bloom populations of red halophilic micro-organisms (*Dunaliella salina* and extreme *Haloarchaea*).\n- **Accelerated Solar Absorption**: The red carotenoid pigments (bacteriorhodopsin) synthesized by these halophiles absorbed green and yellow light wavelengths, heating the brine layer 2–4°C above ambient air temperature and dramatically accelerating evaporation rates.\n- **Natural Solar Bleaching**: As pure sodium chloride crystals floated to the surface as pyramidal hopper crystals (*angel-wing salt* / *uppu-poo*), UV exposure photochemically bleached organic impurities, yielding the dazzling white color celebrated in Sangam literature."
    },
    {
        "file": "knowledge/institutions/institution-umanar-and-uppu-vanigar-guild-of-salt-merchants-and-bullock-caravaners.md",
        "slug": "institution-umanar-and-uppu-vanigar-guild-of-salt-merchants-and-bullock-caravaners",
        "category": "institution",
        "name_en": "Umanar: Trans-Peninsular Salt Caravans, Bullock Transport Guilds & Barter Economies",
        "name_ta": "உமணர் மற்றும் உப்பு வணிகர் - மாட்டு வண்டி உமணச் சாத்து, உப்பு-நெல் பண்டமாற்று மற்றும் பெருவழி வர்த்தக சங்கம்",
        "era": "Iron Age to Medieval Era",
        "year_start": -600,
        "year_end": 1400,
        "thinai": "neithal",
        "summary_en": "Nomadic merchant community (Umanar) organizing massive multi-wagon caravans (saathu) equipped with armed guards to transport coastal salt inland, bartering volume-for-volume for highland paddy and hill spices.",
        "summary_ta": "நூற்றுக்கணக்கான மாட்டு வண்டிகளில் உப்பை ஏற்றிக்கொண்டு, உள்நாட்டு நகரங்கள் மற்றும் மலைநாடுகளுக்குச் சென்று சம எடை நெல்லுக்கு உப்பு பண்டமாற்று செய்த உமணச் சாத்து வணிகக் கூட்டமைப்பு.",
        "sources": [
            "Akananuru 140",
            "Natrinai 311",
            "Silappadikaram 5:15-35",
            "Epigraphia Indica on Merchant Highways"
        ],
        "content": "# Umanar: Salt Merchant Guilds & Bullock Caravans\n\nThe *Umanar* formed one of the most vital distributive commercial networks of ancient South India:\n\n- **The Salt-Paddy Barter Equivalence**: Sangam texts celebrate the universal exchange rate: *\"Equal volume of white salt for unhusked golden paddy\"* (*nellum uppum nere oori*). Salt served as literal commodity currency across landlocked agricultural zones.\n- **The Caravan Guild (*Umana-Saathu*)**: To cross bandits-infested dry tracts (*palai*), merchants travelled in convoys of hundreds of high-wheeled bullock carts (*vandi*), accompanied by families, hunting dogs, and spear-bearing mercenaries (*maravar*).\n- **Inland Arterial Highways**: The *Umanar* carved long-distance trade trails linking coastal salterns at Marakkanam, Korkai, and Nagapattinam directly to inland capitals (Madurai, Karur, Uraiyur) and high mountain passes (Chera Kongu corridor)."
    },
    {
        "file": "knowledge/technologies/technology-uppu-kuval-thatched-palm-mat-stacking-and-monsoon-drainage-mounds.md",
        "slug": "technology-uppu-kuval-thatched-palm-mat-stacking-and-monsoon-drainage-mounds",
        "category": "technology",
        "name_en": "Uppu-Kuval: Conical Palm-Thatch Storage Mounds, Moisture Sump Wells & Monsoon Protection",
        "name_ta": "உப்புக் கூவல் - கூம்பு வடிவ உப்புக் குவியல், பனை ஓலை வேய்தல் மற்றும் பருவமழைக் காப்புப் பொறியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Post-harvest preservation engineering stacking tens of tons of harvested salt into conical mounds (kuval), thatched with water-repellent palmyra leaves and trench-drained to resist torrential monsoon rains.",
        "summary_ta": "மழைக்காலங்களில் உப்பு கரைந்து போகாமல் இருக்க, கூம்பு வடிவில் குவித்து பனை ஓலைகளால் வேய்ந்து, சுற்றிலும் வடிகால் அமைத்து பாதுகாக்கும் பண்டைய களஞ்சியப் பொறியியல்.",
        "sources": [
            "Perumpanattruppadai 325",
            "Traditional Warehouse Engineering in Coastal Ports",
            "Madras District Manual on Salt Depots"
        ],
        "content": "# Uppu-Kuval: Monsoon Salt Storage Engineering\n\nPreserving hundreds of tons of hygroscopic sodium chloride through the torrential northeast monsoon storms required ingenious bulk storage methods:\n\n- **Conical Angle of Repose (*Kuval*)**: Harvested salt was piled on elevated clay platforms into steep conical pyramids, naturally shedding rainwater down their 45-degree angle of repose.\n- **Palmyra Leaf Thatching (*Olai-Kattu*)**: The mounds were thatched with braided palmyra fronds (*panai-olai*) overlapping like fish scales and tied with thick coir cords weighted down with clay tiles. Rain ran off the hydrophobic leaf cuticle without penetrating the dense crystalline core.\n- **Surface Sintering**: A light shower dissolved just enough outer crystals to fuse them into a rock-hard impermeable outer crust (*uppu-koodu*), which protected the millions of dry interior crystals for over a year."
    },
    {
        "file": "knowledge/artifacts/artifact-kodi-valai-and-saltern-baskets-coir-woven-brine-strainers-and-salt-panniers.md",
        "slug": "artifact-kodi-valai-and-saltern-baskets-coir-woven-brine-strainers-and-salt-panniers",
        "category": "artifact",
        "name_en": "Kodi-Valai & Koodai: Coir-Woven Brine Strainers, Palmyra Panniers & Salt Slings",
        "name_ta": "கொடி வலை மற்றும் உப்புக் கூடை - தென்னை நார்க் கசிவு வலை, பனை ஓலைக் கூடை மற்றும் உப்புச் சுமைக் கருவிகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Porous woven wickerwork panniers and coir-mesh sling baskets designed to lift wet salt from crystallizers, allowing bitter mother liquor to rapidly drip drain during transport.",
        "summary_ta": "உப்பளத்திலிருந்து உப்பை அள்ளி எடுக்கும்போது, கார நீர் வடிந்து உப்பு மட்டும் தேங்கும் வண்ணம் பனை நாராலும் தென்னங்கயிற்றாலும் பின்னப்பட்ட வடி கூடை.",
        "sources": [
            "Natrinai 311",
            "Traditional Basketry and Saltern Tools of Tamil Nadu",
            "Adichanallur Ethno-Material Catalog"
        ],
        "content": "# Kodi-Valai & Koodai: Saltern Strainers & Baskets\n\nHandling corrosive hypersaline slush required completely non-metallic, rot-resistant containers:\n\n- **Free-Draining Palmyra Baskets (*Uppuk-Koodai*)**: Woven from tough outer splints of palmyra leaf ribs (*panai-eerkku*), these cone-shaped baskets featured calibrated drainage pores along the base. When lifted from the pan, bittern liquid drained out instantly within seconds.\n- **Shoulder Carrying Slings (*Kavu-Thadi*)**: Harvesters balanced two full baskets slung from resilient bamboo carrying poles (*kaavadi*), transferring salt swiftly from pan to storage heap.\n- **Salt-Resistant Cordage (*Kodi-Valai*)**: Nets crafted from wild creeper vines (*kodi*) and coir fiber withstood continuous exposure to hypersaline brine without fiber rot or tensile degradation."
    },
    {
        "file": "knowledge/concepts/concept-coromandel-solar-insolation-and-intertidal-estuarine-hydrology.md",
        "slug": "concept-coromandel-solar-insolation-and-intertidal-estuarine-hydrology",
        "category": "concept",
        "name_en": "Coromandel Insolation: Solar Radiant Flux, Offshore Wind Shear & Hypersaline Estuaries",
        "name_ta": "சோழமண்டல சூரியக் கதிர்வீச்சு - வெப்பப் பெருக்கம், தரைக்காற்று வீச்சு மற்றும் காயல் நீர்மவியல்",
        "era": "Prehistoric to Modern Era",
        "year_start": -1000,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Unique geographical, climatological, and oceanographic convergence along the Coromandel coast providing 300+ days of intense solar radiation and steady dry land winds ideal for massive solar salt production.",
        "summary_ta": "ஆண்டுக்கு 300 நாட்களுக்கு மேல் சுட்டெரிக்கும் வெயில், வங்கக்கடல் அலைமடை காயல்கள் மற்றும் உலர்ந்த நிலக்காற்றின் கூட்டுச்சேர்க்கையால் அமைந்த உப்பளச் சூழலியல்.",
        "sources": [
            "Climatological Atlas of Coastal Tamil Nadu",
            "National Institute of Oceanography Estuarine Studies",
            "Sangam Meteorology Commentaries"
        ],
        "content": "# Coromandel Insolation & Estuarine Hydrology\n\nThe Coromandel coastal plain between Chennai and Point Calimere boasts one of the world's most productive macro-environments for solar salt manufacture:\n\n- **Semi-Arid Rain-Shadow Dynamics**: While the Western Ghats capture the southwest monsoon (June–September), the east coast experiences extreme heat, clear skies, and blistering dry offshore westerly winds (*kachan-kaathu*).\n- **High Evaporative Deficit**: Daily potential evapotranspiration rates exceed 8–10 mm per day, causing brine to concentrate rapidly within 3–5 days per pan cycle.\n- **Backwater Estuary Networks**: Vast lagoon systems—including the Marakkanam backwaters, Buckingham Canal corridor, and Vedaranyam salt swamps—provide endless sheltered marine tidal inlets protected from ocean storm swells."
    },
    {
        "file": "knowledge/places/place-marakkanam-ancient-eyilpattinam-salt-pan-haven.md",
        "slug": "place-marakkanam-ancient-eyilpattinam-salt-pan-haven",
        "category": "place",
        "name_en": "Marakkanam: Ancient Eyilpattinam Saltern Haven, Ostracite Lagoons & Salt Guild Citadel",
        "name_ta": "மரகானம் - பண்டைய எயிற்பட்டினம் உப்பளத் துறைமுகம், உமணர் குடியிருப்பு மற்றும் உப்பு வர்த்தகத் தளம்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "The celebrated ancient seaport of Eyilpattinam in Villupuram district, documented in the Periplus and Sangam literature as South India's premier tidal solar salt production and caravan distribution emporium.",
        "summary_ta": "பெரிப்ளஸ் நூல் கூறும் சோபட்மா, சங்க இலக்கியம் போற்றும் எயிற்பட்டினம், பல நூறு ஏக்கர் பரப்பளவில் அமைந்த வரலாற்றுச் சிறப்புமிக்க மரகானம் உப்பளத் தளம்.",
        "sources": [
            "Periplus of the Erythraean Sea (Sopatma)",
            "Perumpanattruppadai 315-340",
            "ASI Excavation Reports at Marakkanam"
        ],
        "content": "# Marakkanam: Ancient Eyilpattinam Saltern Haven\n\nIdentified in Greco-Roman records as *Sopatma* (meaning \"coastal fortress\" / *Eyilpattinam*), Marakkanam in modern Villupuram district is South India's grandest historic salt haven:\n\n- **Continuous Millennial Production**: For over two thousand years, the expansive, brackish mudflats connecting the Yedayanthittu estuary to the Bay of Bengal have been worked by hereditary salt-making lineages (*Alalar*).\n- **The Great Umanar Hub**: Classical epigraphs and Sangam poems record Eyilpattinam as the northern terminal where thousands of bullock carts gathered each dry season to haul sacks of crystalline white salt into the Pallava and Chola interiors.\n- **Archaeological Heritage**: Excavations by the Tamil Nadu State Department of Archaeology have revealed ancient pottery shards, brick saltern sluice walls, and Roman amphora fragments, confirming Marakkanam's pivotal stature in global maritime commerce."
    }
]

EDGES = [
    [
        "text-perumpanattruppadai-verses-on-white-salt-mounds-and-eyilpattinam-pan-workers",
        "DESCRIBES",
        "place-marakkanam-ancient-eyilpattinam-salt-pan-haven",
        "core",
        "Sangam Era",
        "Perumpanattruppadai verses describe the vast white salt mounds of Eyilpattinam.",
        "Perumpanattruppadai 315-330"
    ],
    [
        "place-marakkanam-ancient-eyilpattinam-salt-pan-haven",
        "UTILIZES",
        "concept-uppalam-tidal-solar-evaporation-and-brine-crystallization-thermodynamics",
        "core",
        "Iron Age to Modern Era",
        "Marakkanam salterns operate on fractional brine condensation and solar crystallization.",
        "Industrial Saltern Engineering in South India"
    ],
    [
        "concept-uppalam-tidal-solar-evaporation-and-brine-crystallization-thermodynamics",
        "ENGINEERED_VIA",
        "technology-alalam-and-paathi-clay-bund-pan-engineering-and-saline-sluicing",
        "core",
        "Iron Age to Modern Era",
        "Compacted clay floors and wooden sluices enabled progressive brine concentration.",
        "Archaeological Surveys of Coromandel Salterns"
    ],
    [
        "technology-alalam-and-paathi-clay-bund-pan-engineering-and-saline-sluicing",
        "HARVESTED_WITH",
        "artifact-uppu-thadavai-and-marakkal-wooden-scraping-boards-and-salt-measures",
        "core",
        "Iron Age to Modern Era",
        "Teakwood scrapers gathered salt crystals without damaging clay floor seals.",
        "Akananuru 390"
    ],
    [
        "concept-uppalam-tidal-solar-evaporation-and-brine-crystallization-thermodynamics",
        "ENHANCED_BY",
        "concept-alalam-saline-microbiology-and-halophilic-crystal-purification",
        "core",
        "Prehistoric to Modern Era",
        "Halophilic archaea increased solar heat absorption and accelerated salt yields.",
        "Applied and Environmental Microbiology on Marine Solar Salterns"
    ],
    [
        "place-marakkanam-ancient-eyilpattinam-salt-pan-haven",
        "DISTRIBUTED_BY",
        "institution-umanar-and-uppu-vanigar-guild-of-salt-merchants-and-bullock-caravaners",
        "core",
        "Iron Age to Medieval Era",
        "Umanar merchant caravans hauled Eyilpattinam salt inland on bullock carts.",
        "Silappadikaram 5:15-35"
    ],
    [
        "concept-uppalam-tidal-solar-evaporation-and-brine-crystallization-thermodynamics",
        "STORED_VIA",
        "technology-uppu-kuval-thatched-palm-mat-stacking-and-monsoon-drainage-mounds",
        "core",
        "Iron Age to Modern Era",
        "Conical thatched mounds protected bulk salt through torrential monsoon seasons.",
        "Perumpanattruppadai 325"
    ],
    [
        "artifact-kodi-valai-and-saltern-baskets-coir-woven-brine-strainers-and-salt-panniers",
        "USED_IN",
        "technology-alalam-and-paathi-clay-bund-pan-engineering-and-saline-sluicing",
        "core",
        "Iron Age to Modern Era",
        "Porous palmyra baskets drained corrosive bitterns during salt gathering.",
        "Natrinai 311"
    ],
    [
        "concept-uppalam-tidal-solar-evaporation-and-brine-crystallization-thermodynamics",
        "DRIVEN_BY",
        "concept-coromandel-solar-insolation-and-intertidal-estuarine-hydrology",
        "core",
        "Prehistoric to Modern Era",
        "Coromandel solar radiant flux and dry offshore winds powered rapid evaporation.",
        "Climatological Atlas of Coastal Tamil Nadu"
    ],
    [
        "institution-umanar-and-uppu-vanigar-guild-of-salt-merchants-and-bullock-caravaners",
        "BASED_AT",
        "place-marakkanam-ancient-eyilpattinam-salt-pan-haven",
        "core",
        "Iron Age to Medieval Era",
        "Marakkanam was the supreme coastal guild station for trans-peninsular Umanar.",
        "Periplus of the Erythraean Sea (Sopatma)"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 37: Ancient Tamil Tidal Salt Harvesting, Solar Evaporation Pan Hydraulics & Brine Chemistry...")
    
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

    print(f"Ingestion Complete for Batch 37 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
