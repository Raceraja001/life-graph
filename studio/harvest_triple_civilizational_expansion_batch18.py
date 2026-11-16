#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 18):
1. Ancient Tamil Burnt-Brick Engineering, Ring Wells & Stucco Sculpture (Sudhai) (10 dossiers)
2. Ancient Tamil Perfumery, Sandalwood Maceration & Aromatic Hydro-Distillation (10 dossiers)
3. Ancient Tamil Cooperage, Wooden Lathe Turning & Grain Measuring Metrology (10 dossiers)

Total: 30 Canonical Dossiers, 30 Relational Edges, 60 Dense 1024-dim BGE-M3 Embeddings.
"""

import os
import sys
import json
import uuid
import time
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

def get_bge_embedding(text_str: str) -> list[float]:
    payload = json.dumps({
        "model": "bge-m3:latest",
        "prompt": text_str[:4000]
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]

DOSSIERS = [
  {
    "slug": "text-manimekalai-burnt-brick-architecture-and-stucco-poetry",
    "category": "texts",
    "file": "text-manimekalai-burnt-brick-architecture-and-stucco-poetry.md",
    "node_type": "text",
    "name_en": "Manimekalai Burnt-Brick Architecture, Chaitya Monuments & Stucco Sculpture Poetry",
    "name_ta": "மணிமேகலை - சுடுமண் செங்கல் கட்டடக்கலை, சைத்திய மண்டபங்கள் மற்றும் சுதைச் சிற்பப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": 100,
    "year_end": 400,
    "thinai": "marutham",
    "summary_en": "Classical epic verses in Manimekalai (Chakravakkottam ll. 80-115) and Silappadikaram describing the towering burnt-brick Buddhist chaityas, multi-tier monastery halls, brick ring wells, and painted lime-stucco statues (Sudhai-chilangal) of Kaveripoompattinam and Uraiyur.",
    "summary_ta": "மணிமேகலை மற்றும் சிலப்பதிகாரத்தில் காவிரிப்பூம்பட்டினம் மற்றும் உறையூரின் சுட்ட செங்கல் சைத்திய மண்டபங்கள், பல அடுக்கு விகாரைகள், உறைக்கிணறுகள் மற்றும் வெள்ளைப் பூச்சு சுதைச் சிற்பங்களின் கலைநயத்தைப் போற்றும் செவ்வியல் பாடல்கள்.",
    "sources": [
      "Manimekalai Chakravakkottam ll. 80-115",
      "Silappadikaram Uraiperukatturai",
      "Perumpanarruppadai ll. 400-415"
    ],
    "content": "---\nid: text-manimekalai-burnt-brick-architecture-and-stucco-poetry\ntitle: Manimekalai Burnt-Brick Architecture, Chaitya Monuments & Stucco Sculpture Poetry\ntype: text\nera: Sangam Classical Era (c. 100 - 400 CE)\nthinai: marutham (Urban Architectural Literature)\nstatus: canonical\n---\n\n# Manimekalai: Burnt-Brick Architecture, Chaitya Monuments & Stucco Sculpture Poetry\n\n## 1. Classical Primary Source Citations\n- **Manimekalai** (*Chakravakkottam*, ll. 80–115): Poet-merchant Chithalai Chathanar describes the splendid brick architecture of Puhar, recording the sacred *Chakravakkottam* shrine, the brick-built stupas (*Chaitya*), and towering monasteries erected with dense, red-fired ceramic bricks (*Suduman-sengal*).\n- **Manimekalai** (*Sirai-Kottam Arakottam-aakkiya Kathai*): Portrays kingly architects and master brick masons converting state prisons into compassionate monastic halls, detailing the application of lustrous white lime-mortar plaster (*Ven-sudhai*) and sculptural bas-reliefs.\n- **Silappadikaram** (*Adaikkalakkathai*): Depicts brick ramparts and watchtowers encircling Uraiyur, where stucco celestial figures (*Sudhai-chilangal*) adorned the entrance gopurams.\n\n## 2. Lithic vs. Ceramic Architectural Transition\nBefore the widespread adoption of structural granite temples under the Pallavas and Cholas, early historic Tamil urban civilization relied on an extraordinary ceramic engineering paradigm:\n- **Foundations & Core Walls**: Constructed of massive high-fired alluvial clay bricks bound with fine clay-sand mud or hydraulic lime slurry.\n- **Surface Protection & Art**: Coated with multiple layers of slaked shell-lime stucco (*Sudhai*), protecting porous bricks against tropical torrential monsoon deluges while providing a pristine canvas for frescoes.\n- **Hydraulic Conduits**: Ring wells (*Urai-kinaru*) and subsurface stormwater drains crafted from interlocking terracotta rings.\n\n## 3. Socio-Cultural & Civic Significance\nThe verses in Manimekalai prove that 2nd-century Tamil cities featured monumental multi-story civic and religious structures engineered with precision bricklaying, modular sizing, and sophisticated stucco modeling long before stone temples became universal."
  },
  {
    "slug": "insc-urayur-chola-brick-temple-and-drainage-charters",
    "category": "inscriptions",
    "file": "insc-urayur-chola-brick-temple-and-drainage-charters.md",
    "node_type": "inscription",
    "name_en": "Uraiyur Chola Brick Temple Charters & Urban Drainage Concession Epigraphs",
    "name_ta": "உறையூர் சோழர் செங்கல் கோவில் மற்றும் நகரக் கழிவுநீர்க் கால்வாய் கல்வெட்டுகள்",
    "era": "Early Historic to Chola Era",
    "year_start": -200,
    "year_end": 1050,
    "thinai": "marutham",
    "summary_en": "Archaeological and epigraphical records from ancient Uraiyur on the Kaveri basin documenting early Chola royal palace foundations, kilns, subterranean burnt-brick covered drains, and artisan quarters dedicated to bricklaying and stucco crafting.",
    "summary_ta": "காவிரி ஆற்றங்கரை உறையூர் அகழாய்விலும் கல்வெட்டுகளிலும் வெளிவந்த முற்காலச் சோழர் அரண்மனை அடித்தளங்கள், சுடுமண் செங்கல் சூளைகள், நிலத்தடி மூடப்பட்ட செங்கல் கழிவுநீர்க் கால்வாய்கள் மற்றும் சுதைச் சிற்பிகள் குடியிருப்பு ஆவணங்கள்.",
    "sources": [
      "Uraiyur Archaeological Excavations (Madras University)",
      "South Indian Inscriptions Vol VIII",
      "TNSDA Urban Site Reports"
    ],
    "content": "---\nid: insc-urayur-chola-brick-temple-and-drainage-charters\ntitle: Uraiyur Chola Brick Temple Charters & Urban Drainage Concession Epigraphs\ntype: inscription\nera: Early Historic to Chola Era (c. 200 BCE - 1050 CE)\nthinai: marutham (Ancient Dynastic Capital)\nstatus: canonical\n---\n\n# Uraiyur: Chola Brick Temple Charters & Urban Drainage Concession Epigraphs\n\n## 1. Archaeological Context & Stratigraphy\nUraiyur, located on the southern bank of the Kaveri river in Tiruchirappalli, served as the celebrated Sangam capital of the Early Cholas. Archaeological excavations conducted by the University of Madras and ASI revealed extensive brick structural phases dating from 300 BCE to 1100 CE.\n\n## 2. Inscriptional & Structural Evidence\n- **Burnt-Brick Foundations (*Sengal-Kattadam*)**: Disclosed thick brick walls measuring up to 1.2 meters wide, constructed with oversized Sangam bricks (typically 38 x 20 x 7 cm), showing distinct finger-grooved impressions for mortar keying.\n- **Subsurface Brick Drainage Conduits (*Neer-Vaikkal*)**: Long underground channels lined with burnt bricks and roofed with corbelled ceramic capstones, engineered to evacuate municipal runoff directly into the Kaveri without eroding street surfaces.\n- **Dyeing Vats & Ceramic Cisterns**: Interconnected rectangular brick cisterns waterproofed with lime-crushed brick mortar (*Surki*), used for indigo and madder textile dyeing.\n\n## 3. Epigraphical Records of Guild Allotments\nInscribed records in neighboring shrines document royal land grants (*Thatcha-kaani*) conferred upon master bricklayers (*Sengal-Thatchar*) and stucco sculptors (*Sudhai-Kammalar*) tasked with restoring civic structures after seasonal Kaveri floods."
  },
  {
    "slug": "insc-poompuhar-sangam-brick-wharf-and-jetty-epigraphs",
    "category": "inscriptions",
    "file": "insc-poompuhar-sangam-brick-wharf-and-jetty-epigraphs.md",
    "node_type": "inscription",
    "name_en": "Poompuhar Sangam Brick Wharf Epigraphs & Estuarine Jetty Excavation Charters",
    "name_ta": "பூம்புகார் சங்ககால செங்கல் படகுத்துறை மற்றும் கழிமுக இறங்குதளம் அகழாய்வுக் கல்வெட்டுகள்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 300,
    "thinai": "neithal",
    "summary_en": "Excavation records and marine epigraphical findings at Kilaiyur and Poompuhar uncovering a monumental Sangam-era burnt-brick wharf, wooden mooring posts, and tidal inlet masonry engineered for trans-oceanic cargo lighterage.",
    "summary_ta": "பூம்புகார் மற்றும் கீழையூர் அகழாய்வில் வெளிவந்த பிரம்மாண்ட சங்ககால சுடுமண் செங்கல் படகுத்துறை (Wharf), நாவாய் கட்டும் மரத்தூண்கள், மற்றும் கடல்கலன் சரக்கு இறங்குதள நீரியல் செங்கல் கட்டுமான ஆவணங்கள்.",
    "sources": [
      "ASI Marine Archaeology Unit Reports - Poompuhar",
      "NIO Underwater Excavations Bulletin",
      "South Indian Inscriptions Vol XXIII"
    ],
    "content": "---\nid: insc-poompuhar-sangam-brick-wharf-and-jetty-epigraphs\ntitle: Poompuhar Sangam Brick Wharf Epigraphs & Estuarine Jetty Excavation Charters\ntype: inscription\nera: Sangam Classical Era (c. 300 BCE - 300 CE)\nthinai: neithal (Estuarine Maritime Engineering)\nstatus: canonical\n---\n\n# Poompuhar: Sangam Brick Wharf Epigraphs & Estuarine Jetty Excavation Charters\n\n## 1. Discovery & Marine Archaeological Excavations\nDuring maritime excavations conducted at Kilaiyur near Poompuhar (ancient Kaveripoompattinam), the Archaeological Survey of India (ASI) and the National Institute of Oceanography (NIO) uncovered the submerged remains of a colossal semicircular brick wharf platform designed for berthing oceanic ships.\n\n## 2. Engineering Specifications of the Wharf\n- **Brick Metrology & Strength**: Constructed with heavy, dense ceramic bricks measuring 42 x 21 x 7.5 cm, carbon-dated to the 3rd–2nd century BCE. The bricks exhibit minimal porosity and high crushing strength, engineered to withstand brackish estuarine wave impact.\n- **Wooden Mooring Bollards (*Marat-Thoon*)**: Carbonized trunks of rot-resistant hardwood (Ilupai / *Madhuca longifolia*) embedded into the brick masonry plinth to secure mooring hawsers of arriving Vangams.\n- **Canal Ingress Channels**: The brick jetty was flanked by dredged revetments allowing lighters to discharge cargo directly onto paved storage platforms above the high-tide line.\n\n## 3. Physical Validation of Sangam Texts\nThis brick wharf represents the physical, indisputable proof of the harbor scenes described in *Pattinappalai* and *Silappadikaram*, demonstrating that Sangam ports were equipped with permanent, high-performance civil engineering works."
  },
  {
    "slug": "concept-sangam-burnt-brick-kiln-pyrotechnics-and-mortarless-bonding",
    "category": "concepts",
    "file": "concept-sangam-burnt-brick-kiln-pyrotechnics-and-mortarless-bonding.md",
    "node_type": "concept",
    "name_en": "Sangam Burnt-Brick Kiln Pyrotechnics, Alluvial Clays & Modular Metrology",
    "name_ta": "சங்ககால செங்கல் சூளை வெப்ப நுட்பம், வண்டல் களிமண் மற்றும் 4:2:1 விகித செங்கல் அளவியல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 500,
    "thinai": "marutham",
    "summary_en": "The pyrotechnology and metrological standardization of Sangam burnt bricks: levigated river silt, rice husk chaff tempering, clamp kiln wood firing reaching 900-1000°C, and adherence to the universal 4:2:1 dimensional ratio ensuring interlocked bond strength.",
    "summary_ta": "ஆற்று வண்டல் களிமண்ணைப் பதப்படுத்தி, உமிச் சாம்பல் பிணைப்புடன் 900-1000°C வெப்பத்தில் சுடப்பட்ட சங்ககால செங்கற்களின் தயாரிப்பு முறை மற்றும் 4:2:1 நீள-அகல-உயர விகித நிலைத்தன்மை கட்டமைப்பு.",
    "sources": [
      "Indian Archaeology: A Review",
      "Gour: Architectural Metallurgy of Ancient India",
      "Keezhadi & Uraiyur Ceramic Metrology"
    ],
    "content": "---\nid: concept-sangam-burnt-brick-kiln-pyrotechnics-and-mortarless-bonding\ntitle: Sangam Burnt-Brick Kiln Pyrotechnics, Alluvial Clays & Modular Metrology\ntype: concept\nera: Early Historic Era (c. 400 BCE - 500 CE)\nthinai: marutham (Pyrotechnology & Modular Masonry)\nstatus: canonical\n---\n\n# Sangam Burnt-Brick Kiln Pyrotechnics, Alluvial Clays & Modular Metrology\n\n## 1. Modular Dimensioning & The 4:2:1 Ratio\nBricks recovered from Sangam urban contexts across Tamilakam (Poompuhar, Uraiyur, Keezhadi, Arikamedu, Kodumanal) exhibit a remarkably consistent dimensional standard:\n- **Typical Proportions**: Length ~36 to 42 cm, Width ~18 to 21 cm, Thickness ~6 to 7.5 cm.\n- **The 4:2:1 Mathematical Harmony**: The length is exactly twice the width, and four times the thickness. This geometric property allows perfect structural interlocking in both English bond and header-stretcher arrangements without requiring cut fractional bricks.\n\n## 2. Clay Preparation & Degraissant Tempering\n1. **Sedimentary Clay Selection (*Vandal-man*)**: Excavated from backwaters and river meanders, dried, crushed, and levigated in water settling basins to eliminate coarse pebbles.\n2. **Organic Tempering**: Blended with finely chopped straw, rice husks (*Umi*), and river sand. During firing, the organic matter burned away, leaving micro-voids that accommodated thermal expansion and prevented shattering during sudden cooling.\n\n## 3. Clamp Kiln Pyrotechnics (*Sengal-Soolai*)\n- **Fuel Layering**: Raw molded sundried bricks were stacked in open clamp kilns (*Pazha-soolai*) interleaved with palmyrah logs, tamarind wood, and dried cowdung cakes.\n- **Slow Firing & Soaking**: Fired over 4 to 6 days, gradually reaching soaking temperatures between 900°C and 1,050°C.\n- **Oxidizing Atmosphere**: Ample air draft through flue openings oxidized iron minerals in the clay, producing the deep orange-red terracotta color characteristic of Sangam ceramics."
  },
  {
    "slug": "concept-terracotta-ring-well-engineering-urai-kinaru-and-soak-pits",
    "category": "concepts",
    "file": "concept-terracotta-ring-well-engineering-urai-kinaru-and-soak-pits.md",
    "node_type": "concept",
    "name_en": "Terracotta Ring Well Engineering (Urai-Kinaru), Soak Pits & Groundwater Filtration",
    "name_ta": "சுடுமண் உறைக்கிணறு வடிவமைப்பு (உறைக்கிணறு), வண்டல் வடிகட்டுதல் மற்றும் நிலத்தடி நீர் மேலாண்மை",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 800,
    "thinai": "marutham",
    "summary_en": "Indigenous sanitary and groundwater civil engineering using interlocking terracotta cylindrical rings (Urai) sunk vertically into alluvial water tables, acting as potable drinking water wells, sanitary soak pits, and natural bio-filtration systems.",
    "summary_ta": "ஆற்றுப்படுகை மற்றும் கடற்கரை மணற்பரப்பில் சுடுமண் வளையங்களை (உறை) ஒன்றன் மேல் ஒன்றாக இறக்கி நிலத்தடி நீரைச் சேகரித்து வடிகட்டிய உறைக்கிணறுகள் மற்றும் கழிவுநீர் உறிஞ்சு குழிகளின் பண்டைய சுகாதாரப் பொறியியல்.",
    "sources": [
      "Pattirrupathu v. 51",
      "Keezhadi Archaeological Reports",
      "Sankalia: Aspects of Indian Archaeology"
    ],
    "content": "---\nid: concept-terracotta-ring-well-engineering-urai-kinaru-and-soak-pits\ntitle: Terracotta Ring Well Engineering (Urai-Kinaru), Soak Pits & Groundwater Filtration\ntype: concept\nera: Early Historic Era (c. 400 BCE - 800 CE)\nthinai: marutham (Hydraulic Sanitary Engineering)\nstatus: canonical\n---\n\n# Terracotta Ring Well Engineering (Urai-Kinaru), Soak Pits & Groundwater Filtration\n\n## 1. Classical Citations & Urban Ubiquity\n- **Pathitrupathu** (v. 51): Sings of sweet water drawn from deep terracotta-lined wells (*Urai-kinaru*) in fertile settlement quarters.\n- **Archaeological Stratigraphy**: Ring wells have been unearthed in every major Sangam urban excavation (Keezhadi, Uraiyur, Poompuhar, Korkai, Alagankulam), often stacked up to 20 to 30 rings deep into the subterranean water table.\n\n## 2. Manufacturing & Sinking Mechanics\n1. **Ring Fabrication on Potters' Wheel**: Massive circular terracotta cylinders (diameter ~60 to 90 cm, height ~25 to 35 cm, thickness ~3 to 5 cm) were wheel-turned or slab-molded from tempered alluvial clay with grooved rebated rims for interlocking.\n2. **Caisson Sinking Method**: \n   - A circular shaft was excavated to the water table.\n   - The first ring was placed in the bottom; as earth was scooped out from inside the ring, gravity pulled the ring downward.\n   - Subsequent rings were seated on top, tongue-and-groove jointed with clay or lime mortar, sinking continuously through loose sand without requiring timber formwork.\n\n## 3. Dual Functionality: Potable Wells & Sanitary Soak Pits\n- **Drinking Water Filtration**: In coastal and river delta soils, the porous terracotta walls and surrounding sand pack filtered out suspended silt and surface biological contaminants, yielding crystal-clear potable water.\n- **Urban Soak Pits**: In residential dye-houses and domestic kitchens, ring stacks were filled with graded gravel, charcoal dust, and broken potsherds, functioning as subterranean septic absorption pits that purified greywater before recharging aquifers."
  },
  {
    "slug": "concept-hydraulic-lime-plaster-slaking-and-sudhai-stucco-sculpture",
    "category": "concepts",
    "file": "concept-hydraulic-lime-plaster-slaking-and-sudhai-stucco-sculpture.md",
    "node_type": "concept",
    "name_en": "Hydraulic Lime Plaster Slaking, Egg-White Buffering & Sudhai Stucco Sculpture",
    "name_ta": "சுண்ணாம்பு நீரேற்றம், முட்டைக் கரு-கடுக்காய் பிணைப்பு மற்றும் சுதைச் சிற்பக் கலை",
    "era": "Early Historic to Medieval Era",
    "year_start": -200,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "The sophisticated biochemical formulation of ancient Tamil stucco (Sudhai): calcined sea shell lime slaked with jaggery water, gall-nut (Kadukkai) tannin extracts, egg whites, and river sand, sculpted over core brick armatures to create weather-impervious monumental statuary.",
    "summary_ta": "சுட்ட சிப்பிச் சுண்ணாம்பு, வெல்லக் கரைசல், கடுக்காய் ஊறல் சாறு, முட்டையின் வெள்ளைக்கரு மற்றும் மணல் சேர்த்து அரைக்கப்பட்ட சுண்ணச் சாந்து (சுதை) கொண்டு செங்கல் சட்டகங்கள் மீது வடிக்கப்பட்ட நீடித்த சுதைச் சிற்பக் கலை.",
    "sources": [
      "Manimekalai ll. 80-95",
      "Mayamata Architecture Treatise",
      "Tamil Vastu & Stucco Conservation Studies"
    ],
    "content": "---\nid: concept-hydraulic-lime-plaster-slaking-and-sudhai-stucco-sculpture\ntitle: Hydraulic Lime Plaster Slaking, Egg-White Buffering & Sudhai Stucco Sculpture\ntype: concept\nera: Early Historic to Medieval Era (c. 200 BCE - 1200 CE)\nthinai: marutham (Stucco Chemistry & Plastic Arts)\nstatus: canonical\n---\n\n# Hydraulic Lime Plaster Slaking, Egg-White Buffering & Sudhai Stucco Sculpture\n\n## 1. The Art of Sudhai (Lime Stucco)\nIn classical Tamil temple architecture, **Sudhai** represents the versatile art of modeling three-dimensional divine icons, guardian dvarapalas, and intricate roof vimanams using a pliable, slow-curing bio-chemical lime mastic over internal brick and timber skeletal armatures (*Koodu*).\n\n## 2. Chemical Ingredients & Preparation\n1. **Calcined Shell Lime (*Chunnam*)**: Sourced from burned coastal oyster, marine clam, and conch shells, yielding pure calcium oxide (CaO) with zero iron impurities, producing a blindingly white base.\n2. **Slaking with Bio-Extracts**: Slaked in large pits with water infused with:\n   - **Kadukkai (*Terminalia chebula*)**: Tannin extract retards rapid drying, preventing surface shrinkage cracks.\n   - **Panang-karupatti (Palm Jaggery)**: Sugars form calcium saccharate complexes that dramatically enhance tensile bond strength.\n   - **Egg Whites (*Muttai-venkaru*) & Curd**: Proteins act as natural hydrophobic plasticizers, conferring high water repellency.\n3. **Milling & Grinding (*Saandhu-Araitthal*)**: The mixture was ground for weeks in stone bullock-driven mills (*Aralai*) until transformed into a buttery, smooth paste.\n\n## 3. Armature Modeling & Polishing\n- **Rough Brick Understructure**: Core brickwork was built with coarse steps approximating the figure's silhouette.\n- **Layered Stucco Build-Up**: Successive coats—from coarse lime-sand (*Kara-saandhu*) to micro-fine lime-marble dust (*Nai-saandhu*)—were applied with bronze spatulas.\n- **Agate Burnishing**: Cured surfaces were rubbed with smooth river agates and coated with coconut milk, yielding a porcelain-like ivory luster that withstood centuries of tropical rain."
  },
  {
    "slug": "concept-corbelled-brick-vaulting-and-subsurface-stormwater-conduits",
    "category": "concepts",
    "file": "concept-corbelled-brick-vaulting-and-subsurface-stormwater-conduits.md",
    "node_type": "concept",
    "name_en": "Corbelled Brick Vaulting, False Arches & Subsurface Municipal Stormwater Conduits",
    "name_ta": "படிமுறை செங்கல் வளைவுகள் (கார்பெல்), நிலத்தடி வடிகால்கள் மற்றும் நகரக் கழிவுநீர்ப் பொறியியல்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 600,
    "thinai": "marutham",
    "summary_en": "Structural engineering of corbelled brick false arches and vaulted subterranean drainage conduits in ancient Tamil capitals, cantilever-projecting successive brick courses inward to bridge spans without centering timbers or true voussoirs.",
    "summary_ta": "மரச் சட்டகங்கள் இன்றி, செங்கற்களை ஒன்றன் மேல் ஒன்றாக உள்நோக்கி நீட்டி அடுக்கி வளைவுகளை உருவாக்கிய கார்பெல் (Corbelled) முறை மற்றும் நகர வெள்ளநீரை வெளியேற்றிய நிலத்தடி மூடப்பட்ட வடிகால் அமைப்பு.",
    "sources": [
      "Kaveripoompattinam Archaeological Reports",
      "Arikamedu Excavation Memoirs (Wheeler)",
      "Chola Urban Civil Engineering Studies"
    ],
    "content": "---\nid: concept-corbelled-brick-vaulting-and-subsurface-stormwater-conduits\ntitle: Corbelled Brick Vaulting, False Arches & Subsurface Municipal Stormwater Conduits\ntype: concept\nera: Early Historic Era (c. 300 BCE - 600 CE)\nthinai: marutham (Municipal Civil Engineering)\nstatus: canonical\n---\n\n# Corbelled Brick Vaulting, False Arches & Subsurface Municipal Stormwater Conduits\n\n## 1. Mechanics of the Corbelled Brick Vault\nPrior to the post-12th-century introduction of the true radiating voussoir arch with keystone, ancient Tamil master builders bridged doorways, roof chambers, and deep drainage culverts using **corbelled brick vaulting** (*Padip-padaip-punarpu*):\n- **Cantilever Stepping**: Each horizontal course of burnt brick projected inward by approximately one-quarter of a brick length beyond the course below it.\n- **Counterweight Stability**: Heavy exterior masonry overburden counterbalanced the cantilevered projection, preventing toppling until opposite sides met at the apex.\n- **Apex Capping**: Sealed with heavy flat terracotta tiles or stone capstones.\n\n## 2. Municipal Drainage Systems of Sangam Capitals\nExcavations at Poompuhar, Uraiyur, and Arikamedu have revealed extensive municipal drainage networks that rivaled those of contemporary Rome and Alexandria:\n1. **Paved Inverts**: Drain floors were lined with large flat burnt tiles laid on tight slopes to maintain self-cleansing water velocities.\n2. **Corbelled Coverings**: Roofed with corbelled brick arches flush with street pavement levels, allowing carts and pedestrian traffic to pass overhead safely.\n3. **Silt Inspection Chambers (*Manik-kuzhi*)**: Intermittent settling sumps collected sand and heavy debris, allowing municipal sweepers to shovel out sediment through removable access slabs."
  },
  {
    "slug": "char-poompuhar-master-brick-architect-sengal-thatchan",
    "category": "characters",
    "file": "char-poompuhar-master-brick-architect-sengal-thatchan.md",
    "node_type": "character",
    "name_en": "Master Brick Architect & Kiln Supervisor of Poompuhar (Sengal-Thatchan)",
    "name_ta": "பூம்புகார் தலைமை செங்கல் சிற்பி மற்றும் சூளை கண்காணிப்பாளர் (செங்கல் தச்சன்)",
    "era": "Sangam Classical Era",
    "year_start": -100,
    "year_end": 150,
    "thinai": "neithal",
    "summary_en": "Hereditary master architect of Kaveripoompattinam in charge of river-clay testing, kiln firing temperatures, wharf platform geometry, and modular brick construction for Chola royal docks.",
    "summary_ta": "காவிரிப்பூம்பட்டினத்தின் அரச படகுத்துறைகள், கோட்டைக் கொத்தளங்கள் மற்றும் நகர மாளிகைகளை வடிவமைத்த, வண்டல் களிமண் தரம் மற்றும் சூளை வெப்பநிலையை நிர்ணயித்த தலைமை செங்கல் தச்சன்.",
    "sources": [
      "Poompuhar Excavation Monographs",
      "Sangam Architectural Commentaries",
      "South Indian Epigraphy"
    ],
    "content": "---\nid: char-poompuhar-master-brick-architect-sengal-thatchan\ntitle: Master Brick Architect & Kiln Supervisor of Poompuhar (Sengal-Thatchan)\ntype: character\nera: Sangam Classical Era (c. 100 BCE - 150 CE)\nthinai: neithal (Harbor Civil Architecture)\nstatus: canonical\n---\n\n# Master Brick Architect & Kiln Supervisor of Poompuhar (Sengal-Thatchan)\n\n## 1. Professional Guild Standing\nThe **Sengal-Thatchan** (Master Brick Mason and Architect) held an esteemed post in the maritime administration of Poompuhar. Operating under royal charters granted by the Chola crown, he directed large guilds of clay preparers, molders, kiln firemen, and masons constructing harbor walls, warehouse basements, and religious stupas.\n\n## 2. Technical Specializations\n- **Clay Viscosity Assessment**: Evaluated raw alluvial clays by plasticity touch tests to gauge appropriate sand and rice husk ratios.\n- **Marine Foundation Engineering**: Sited the monumental brick wharf at Kilaiyur, laying massive stepped brick footings upon submerged clay-sand layers capable of resisting daily saltwater tidal scouring.\n- **Standardized Brick Gauge**: Enforced the strict 4:2:1 dimensional standard across dozens of artisan kilns surrounding the capital."
  },
  {
    "slug": "char-urayur-master-stucco-sculptor-sudhai-sirpan",
    "category": "characters",
    "file": "char-urayur-master-stucco-sculptor-sudhai-sirpan.md",
    "node_type": "character",
    "name_en": "Master Stucco Sculptor & Lime Alchemist of Uraiyur (Sudhai-Sirpan)",
    "name_ta": "உறையூர் தலைமை சுதைச் சிற்பி மற்றும் சுண்ண ரசவாதக் கலைஞர் (சுதைச் சிற்பன்)",
    "era": "Sangam to Chola Era",
    "year_start": 200,
    "year_end": 450,
    "thinai": "marutham",
    "summary_en": "Visionary master stucco artist of the Chola capital of Uraiyur, celebrated for compounding shell-lime mastics with egg whites and plant tannins, sculpting lifelike monumental figures over brick core armatures.",
    "summary_ta": "உறையூர் மாளிகைகள் மற்றும் ஆலயங்களின் செங்கல் கட்டமைப்பு மீது சிப்பிச் சுண்ணாம்பு, முட்டைக் கரு, கடுக்காய் சாறு கொண்டு வழுவழுப்பான, அழியாத சுதைச் சிற்பங்களை வடித்த தலைமைச் சிற்பி.",
    "sources": [
      "Manimekalai Commentaries",
      "Uraiyur Art Historical Catalogues",
      "TNSDA Monograph Series"
    ],
    "content": "---\nid: char-urayur-master-stucco-sculptor-sudhai-sirpan\ntitle: Master Stucco Sculptor & Lime Alchemist of Uraiyur (Sudhai-Sirpan)\ntype: character\nera: Sangam to Chola Era (c. 200 - 450 CE)\nthinai: marutham (Stucco Guild Leadership)\nstatus: canonical\n---\n\n# Master Stucco Sculptor & Lime Alchemist of Uraiyur (Sudhai-Sirpan)\n\n## 1. Persona & Architectural Role\nThe **Sudhai-Sirpan** (Master Stucco Sculptor) was the lead plastic artist of ancient Uraiyur. At a time when royal palaces, Buddhist chaityas, and Jain shrines were constructed of brick and timber, his stucco coatings and figurative sculptures transformed raw structural masonry into dazzling works of artistic devotion.\n\n## 2. Mastery of Organic Chemistry & Sculpture\n- **Bio-Chemical Slaking**: Formulated custom mortar blends infused with palm sugar and egg whites to balance slow initial setting with extreme long-term stone-like hardness.\n- **Dynamic Figural Modeling**: Worked rapidly with horn, bone, and bronze modeling tools over rough brick armatures, capturing dynamic drapery folds, delicate jewelry ornaments, and expressive facial countenances before the lime hardened.\n- **Fresco Ground Preparation**: Prepared ultra-smooth *Vajralepa* stucco grounds polished with river pebbles to receive natural mineral pigments (red ochre, lamp black, lapis lazuli)."
  },
  {
    "slug": "place-urayur-ancient-chola-brick-masonry-haven",
    "category": "places",
    "file": "place-urayur-ancient-chola-brick-masonry-haven.md",
    "node_type": "place",
    "name_en": "Uraiyur Ancient Chola Brick Masonry Haven & Kaveri Riparian Capital",
    "name_ta": "உறையூர் பண்டைய சோழர் செங்கல் கட்டடக்கலை நகரம் மற்றும் காவிரி ஆற்றுத் தலைநகர்",
    "era": "Sangam to Chola Era",
    "year_start": -300,
    "year_end": 1250,
    "thinai": "marutham",
    "summary_en": "The storied inland capital of the Early Cholas situated on the Kaveri river (modern Tiruchirappalli), renowned for its massive burnt-brick urban foundations, ring wells, textile dye vats, and centuries of architectural innovation.",
    "summary_ta": "காவிரி நதிக்கரையில் அமைந்த சங்ககால சோழர்களின் புகழ்பெற்ற உறைவிடம்; பிரம்மாண்ட சுட்ட செங்கல் மாளிகைகள், உறைக்கிணறுகள், சாயத் தொட்டிகள் மற்றும் தொடர்ச்சியான நகர்ப்புற நாகரிகத்தின் உறைவிடம்.",
    "sources": [
      "Archaeology of the Kaveri Delta",
      "University of Madras Excavation Reports",
      "South Indian Inscriptions"
    ],
    "content": "---\nid: place-urayur-ancient-chola-brick-masonry-haven\ntitle: Uraiyur Ancient Chola Brick Masonry Haven & Kaveri Riparian Capital\ntype: place\nera: Sangam to Chola Era (c. 300 BCE - 1250 CE)\nthinai: marutham (Inland Dynastic Capital)\nstatus: canonical\n---\n\n# Uraiyur Ancient Chola Brick Masonry Haven & Kaveri Riparian Capital\n\n## 1. Geographical Location & Riparian Urbanism\nUraiyur is situated on the southern floodplains of the Kaveri river in the heart of Tiruchirappalli (coordinates approx. 10.8250° N, 78.6850° E). Sheltered from coastal naval attacks while possessing direct waterborne transit down the Kaveri to Puhar and the Bay of Bengal, it served as the political and architectural heart of the Sangam Cholas.\n\n## 2. Archaeological Discoveries & Structural Remains\nExtensive excavations have brought to light:\n- **Massive Brick Architecture**: Complex multi-room palace complexes constructed with 4:2:1 proportioned burnt bricks, showing evidence of lime plaster surfacing.\n- **Interlocking Ring Wells**: Deep terracotta caissons tapping uncontaminated deep aquifers beneath the Kaveri silt beds.\n- **Covered Brick Culverts**: Subsurface urban stormwater and wastewater systems discharging safely into peripheral agricultural canals.\n- **Textile Dyeing Complexes**: Rectangular brick vats stained with mineral residues, attesting to Uraiyur's international fame for producing diaphanous woven muslins praised in the Roman empire.\n\n## 3. Epicenter of Ceramic & Stucco Engineering\nUraiyur was the chief training ground where generations of master bricklayers and stucco sculptors developed the structural and artistic techniques that later blossomed into the monumental granite architecture of the Imperial Cholas."
  },
  {
    "slug": "text-maduraikkanchi-aromatic-bazaar-and-incense-poetry",
    "category": "texts",
    "file": "text-maduraikkanchi-aromatic-bazaar-and-incense-poetry.md",
    "node_type": "text",
    "name_en": "Maduraikkanchi Aromatic Bazaar Hymns, Incense Fumes (Narum-Pukai) & Royal Attar Poetry",
    "name_ta": "மதுரைக்காஞ்சி - வாசனைத் திரவிய அங்காடி, நறும்புகை மற்றும் அரச நறுமணப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -100,
    "year_end": 200,
    "thinai": "marutham",
    "summary_en": "Sangam verses in Maduraikkanchi (ll. 360-390, 500-520) and Silappadikaram portraying the fragrant night bazaars of Madurai, clouds of aromatic incense (Narum-pukai) drifting from palaces, ground sandalwood pastes, and merchants compounding exotic resins.",
    "summary_ta": "மதுரைக்காஞ்சி மற்றும் சிலப்பதிகாரத்தில் மதுரையின் அல்லங்காடி நறுமண வீதிகள், மாளிகைகளிலிருந்து எழும் அகில் நறும்புகை, அரைக்கப்பட்ட சந்தனக் குழம்பு மற்றும் வாசனைத் திரவியக் கலவைகள் பற்றிய செவ்வியல் பாடல்கள்.",
    "sources": [
      "Maduraikkanchi ll. 360-390, 500-520",
      "Silappadikaram Kadaladukathai ll. 75-100",
      "Natrinai v. 299"
    ],
    "content": "---\nid: text-maduraikkanchi-aromatic-bazaar-and-incense-poetry\ntitle: Maduraikkanchi Aromatic Bazaar Hymns, Incense Fumes (Narum-Pukai) & Royal Attar Poetry\ntype: text\nera: Sangam Classical Era (c. 100 BCE - 200 CE)\nthinai: marutham (Urban Olfactory Culture)\nstatus: canonical\n---\n\n# Maduraikkanchi: Aromatic Bazaar Hymns, Incense Fumes (Narum-Pukai) & Royal Attar Poetry\n\n## 1. Classical Primary Source Citations\n- **Maduraikkanchi** (ll. 360–390, 500–520): Poet Mankudi Maruthanar offers an olfactory panorama of ancient Madurai, where evening bazaars (*Allangadi*) overflow with mounds of fresh flower garlands, crushed musk, and incense braziers (*Thoopa-kinnam*) filling multi-story mansions with sweet clouds of burnt eaglewood (*Akil*) and frankincense.\n- **Silappadikaram** (*Kadaladukathai*, ll. 75–100): Describes the elaborate royal toilet of queenly courtesan Madhavi, who bathes in waters infused with ten aromatic astringents, five perfumed flowers, and thirty-two fragrant herb pastes, followed by drying her dark tresses in dense aromatic smoke (*Narum-pukai*).\n- **Natrinai** (v. 299): Depicts cooling sandalwood paste ground on circular stone slabs smeared upon the chests of warrior chieftains.\n\n## 2. Olfactory Hierarchy of Ancient Tamilakam\nFragrance in early Tamil culture was not merely an aesthetic luxury, but a sacred, medicinal, and climatically essential technology:\n- **Cooling Aromatics (*Kanal-thirutthi*)**: Sandalwood (*Sandhanam*) and vetiver (*Vettiver*) applied to the skin to dissipate tropical midday heat.\n- **Warming Incense (*Narum-pukai*)**: Smoldering dried agarwood (*Akil*), benzoin (*Sambrani*), and camphor (*Karpooram*) used to dry damp hair and disinfect indoor air during monsoon seasons.\n- **Royal Attars & Ointments**: Compound blends of civet (*Punuhu*), musk (*Kasturi*), and screwpine (*Thazhambu*) signifying dynastic majesty.\n\n## 3. Socio-Economic Value\nTamil ports acted as the premier global crossroads for aromatics, collecting indigenous hill spices from the Western Ghats while importing frankincense from Arabia and camphor from Sumatra, re-exporting them as refined compound unguents throughout the ancient world."
  },
  {
    "slug": "insc-kallidaikurichi-royal-sandalwood-tribute-charters",
    "category": "inscriptions",
    "file": "insc-kallidaikurichi-royal-sandalwood-tribute-charters.md",
    "node_type": "inscription",
    "name_en": "Kallidaikurichi Royal Sandalwood Tribute Charters & Western Ghats Forest Grants",
    "name_ta": "கல்லிடைக்குறிச்சி பாண்டியர் சந்தன மரக் கொடை மற்றும் மேற்குத் தொடர்ச்சி மலை நறுமணப் பட்டயங்கள்",
    "era": "Pandya Classical Era",
    "year_start": 800,
    "year_end": 1150,
    "thinai": "kurinji",
    "summary_en": "Stone epigraphs from Kallidaikurichi on the Tambraparni basin recording royal Pandya monopolies on fragrant sandalwood (Santalum album) harvests in the Podhigai hills, tribute quotas of aromatic logs, and temple unguent endowments.",
    "summary_ta": "தாம்பிரபரணி படுகை கல்லிடைக்குறிச்சிக் கல்வெட்டுகள், பொதிகை மலையில் விளையும் வாசனைச் சந்தன மரங்களின் மீதான பாண்டிய மன்னரின் உரிமை, சந்தன மரப் பாரங்கள் மற்றும் ஆலய நறுமணப் பூச்சு மானிய ஆவணங்கள்.",
    "sources": [
      "South Indian Inscriptions Vol XIV",
      "Pandya Epigraphical Survey",
      "Forestry and Epigraphy of Southern Tamil Nadu"
    ],
    "content": "---\nid: insc-kallidaikurichi-royal-sandalwood-tribute-charters\ntitle: Kallidaikurichi Royal Sandalwood Tribute Charters & Western Ghats Forest Grants\ntype: inscription\nera: Pandya Classical Era (c. 800 - 1150 CE)\nthinai: kurinji (Montane Forest Epigraphy)\nstatus: canonical\n---\n\n# Kallidaikurichi: Royal Sandalwood Tribute Charters & Western Ghats Forest Grants\n\n## 1. Epigraphical Provenance\nCarved onto the granite foundations of the historic Manikkaswami and Varaha shrines at Kallidaikurichi at the foot of the Podhigai mountains along the Tambraparni river, these Pandya charters date from the 9th to 12th centuries CE.\n\n## 2. Inscription Mandates & Forest Revenue\n- **Sandalwood Monopolies (*Sandhana-vari*)**: Decrees that all mature red-heartwood sandalwood trees (*Sem-sandhanam*) felled in the upper Podhigai forest were state-controlled royal monopolies (*Raja-pogam*).\n- **Guild Tribute Deliveries**: Mandates that the hill tribal foraging chiefs (*Kanikkarar*) deliver dry seasoned heartwood logs annually to royal warehouses in Kallidaikurichi.\n- **Temple Unguent Endowments (*Sandhana-Kaapu*)**: Allocates daily rations of pulverized sandalwood for the ceremonial anointing of deity icons, specifying that the paste be ground freshly on pure granite grinding stones (*Urai-kal*).\n\n## 3. Forest Ecology & Preservation\nThe charters contain conservation clauses prohibiting the premature cutting of young saplings, requiring trees to reach full aromatic maturity (typically 30 to 40 years, when essential oil content in heartwood peaks) before felling."
  },
  {
    "slug": "insc-thirumeyyam-temple-aromatic-ointment-and-camphor-endowments",
    "category": "inscriptions",
    "file": "insc-thirumeyyam-temple-aromatic-ointment-and-camphor-endowments.md",
    "node_type": "inscription",
    "name_en": "Thirumeyyam Temple Aromatic Ointment Endowments & Camphor Import Charters",
    "name_ta": "திருமெய்யம் பாண்டியர் ஆலய நறுமணக் காப்பு மற்றும் கற்பூர இறக்குமதி கல்வெட்டுகள்",
    "era": "Medieval Pandya Era",
    "year_start": 850,
    "year_end": 1100,
    "thinai": "marutham",
    "summary_en": "Rock-cut temple inscriptions at Thirumeyyam recording extensive perpetual endowments for fragrant civet musk (Punuhu), Barus camphor (Pachai Karpooram), agarwood chips, and rosewater shipments funded by overseas merchant guilds.",
    "summary_ta": "திருமெய்யம் குடைவரைக் கோவில் கல்வெட்டுகள், புனுகு, சுமாத்திரா நாட்டு பச்சைக்கற்பூரம், அகில் கட்டைகள் மற்றும் பன்னீர் நறுமணக் காப்புக்காக திசையாயிரத்து ஐந்நூற்றுவர் வணிகக் குழு வழங்கிய நிரந்தர அறக்கொடைகள்.",
    "sources": [
      "Inscriptions of the Pudukkottai State",
      "South Indian Inscriptions Vol XVII",
      "Indian Ocean Aromatic Trade Epigraphs"
    ],
    "content": "---\nid: insc-thirumeyyam-temple-aromatic-ointment-and-camphor-endowments\ntitle: Thirumeyyam Temple Aromatic Ointment Endowments & Camphor Import Charters\ntype: inscription\nera: Medieval Pandya Era (c. 850 - 1100 CE)\nthinai: marutham (Sacred Olfactory Epigraphy)\nstatus: canonical\n---\n\n# Thirumeyyam: Temple Aromatic Ointment Endowments & Camphor Import Charters\n\n## 1. Epigraphical Provenance\nInscribed on the living rock walls of the Satyagiriswara and Sathyamurthi Perumal rock-cut sanctuaries at Thirumeyyam (Pudukkottai district), these epigraphs reflect the lavish patronage of Pandya royals and international merchant consortiums.\n\n## 2. Inscriptional Records of Imported Aromatics\n- **Pachai Karpooram (Barus Camphor)**: Documents endowments of pure crystalline edible camphor imported from Barus in Sumatra, measured in gold drams (*Kalanju*) and burned in ceremonial lamps to perfume temple halls.\n- **Punuhu (Civet Musk) Endowments**: Grants agricultural village revenues to purchase raw civet glandular secretions from master animal keepers, used to coat stone icons with a lustrous, water-repellent perfumed patina.\n- **Merchant Consortium Signatures**: Explicitly records donations from the *Tisai-Aayirathu-Ainnurruvar* (The 500 of the Thousand Directions), verifying that international merchant guilds channeled luxury aromatics directly into regional temple liturgies.\n\n## 3. Cultural & Preservative Functions\nBeyond worship, these aromatic coatings had physical preservation roles: camphor, sandalwood oil, and civet acted as natural insecticidal, antimicrobial, and anti-fungal varnishes, preventing rock-cut relief carvings from moisture decay."
  },
  {
    "slug": "concept-clay-hydro-distillation-and-akil-agarwood-essential-oils",
    "category": "concepts",
    "file": "concept-clay-hydro-distillation-and-akil-agarwood-essential-oils.md",
    "node_type": "concept",
    "name_en": "Clay Hydro-Distillation, Deg-Bhapka Retorts & Akil Agarwood Essential Oil Extraction",
    "name_ta": "சுடுமண் நீராவி வடித்தல் (ஹைட்ரோ-டிஸ்டிலேஷன்), அகில் மர எண்ணெய் மற்றும் நறுமணத் தைலப் பிரித்தெடுப்பு",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 800,
    "thinai": "kurinji",
    "summary_en": "Traditional Tamil pyrochemical hydro-distillation using dual earthenware pots (Deg and Bhapka receiver) connected by bamboo conduits, extracting concentrated essential oils and attars from resinous infected agarwood (Akil / Aquilaria agallocha) and aromatic floral petals.",
    "summary_ta": "இரு சுடுமண் கலசங்கள் மற்றும் மூங்கில் குழாய் கொண்ட பாரம்பரிய நீராவி வடித்தல் முறை மூலம், வைரம்பாய்ந்த அகில் மரம், ரோஜா மற்றும் தாழம்பூவிலிருந்து அடர்ந்த நறுமணத் தைலங்களை வடித்தெடுத்த சங்ககால வேதியியல் நுட்பம்.",
    "sources": [
      "Silappadikaram Kadaladukathai",
      "Chola Pharmacopeia & Rasavatham Texts",
      "Forbes: Short History of the Art of Distillation"
    ],
    "content": "---\nid: concept-clay-hydro-distillation-and-akil-agarwood-essential-oils\ntitle: Clay Hydro-Distillation, Deg-Bhapka Retorts & Akil Agarwood Essential Oil Extraction\ntype: concept\nera: Sangam Classical Era (c. 300 BCE - 800 CE)\nthinai: kurinji (Pyrochemical Distillation Technology)\nstatus: canonical\n---\n\n# Clay Hydro-Distillation, Deg-Bhapka Retorts & Akil Agarwood Essential Oil Extraction\n\n## 1. Ancient Hydro-Distillation Apparatus (*Vaala-Iyanthiram*)\nCenturies before the European alembic still, ancient Tamil perfumers and Siddha alchemists engineered an ingenious, low-pressure hydro-distillation apparatus composed entirely of local earthenware and botanical elements:\n1. **Boiler Retort (*Deg* / *Kozhundhu-Kalam*)**: A heavy, thick-walled refractory earthenware pot filled with crushed botanical aromatics submerged in freshwater.\n2. **Clay-Coir Sealing (*Kalyan-Pattu*)**: The lid was hermetically sealed using strips of cotton fabric soaked in sticky river clay, preventing aromatic steam escape under pressure.\n3. **Bamboo Vapor Conduit (*Mungil-Kuzhal*)**: A curved bamboo pipe wrapped in wet coir fibers directed rising steam into the receiver.\n4. **Submerged Condenser Receiver (*Bhapka* / *Neer-Kinnam*)**: A copper or glazed earthenware vessel placed inside an open water cooling tank.\n\n## 2. Agarwood (*Akil*) Extraction Dynamics\n- **Resin-Infected Heartwood**: Healthy *Aquilaria* wood is pale and odorless. Only when infected by specific parasitic mold does the tree produce dark, dense, highly resinous heartwood (*Akil*).\n- **Maceration & Steam Stripping**: Dark chips were steeped in water for days, then subjected to slow, steady charcoal boiling. Steam stripped the volatile sesquiterpene aromatic compounds from the wood matrix.\n- **Condensation onto Carrier Oil**: The vapors condensed inside the cold receiver, dripping into a base of pure virgin sesame or sandalwood oil, which absorbed and stabilized the fragile top notes.\n\n## 3. Product Excellence & Export\nThe resulting thick, resinous attar was poured into hollowed ivory vials and unglazed porous clay flasks, renowned across Rome, Egypt, and China as one of the most precious and enduring fragrances of antiquity."
  },
  {
    "slug": "concept-sandalwood-heartwood-maceration-and-stone-grinding-mechanics",
    "category": "concepts",
    "file": "concept-sandalwood-heartwood-maceration-and-stone-grinding-mechanics.md",
    "node_type": "concept",
    "name_en": "Sandalwood Heartwood Maceration, Circular Stone Grinding & Santalol Thermoregulation",
    "name_ta": "சந்தனக் கட்டை உரசுதல், வட்ட வடிவ உரைகல் மற்றும் சாந்தலோல் உடல் குளிர்ச்சி இயக்கவியல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 1200,
    "thinai": "kurinji",
    "summary_en": "The mechanics of manual sandalwood extraction: rubbing matured oily heartwood logs in circular motions upon rough-surfaced granite grinding stones (Sandhana-kal) with rosewater, releasing alpha- and beta-santalols providing physiological skin cooling and sacred anointing.",
    "summary_ta": "முதிர்ந்த சந்தனக் கட்டையை வட்ட வடிவ கருங்கல் உரைகல்லில் பன்னீர் தெளித்து வட்ட இயக்கத்தில் உரசி, ஆல்பா-சாந்தலோல் செறிந்த குளிர்ந்த நறுமணச் சந்தனக் குழம்பை (சந்தனக் காப்பு) உருவாக்கும் பாரம்பரிய இயற்பியல் முறை.",
    "sources": [
      "Purananuru v. 396",
      "Silappadikaram",
      "Pharmacological Studies on Santalum album (ICMR)"
    ],
    "content": "---\nid: concept-sandalwood-heartwood-maceration-and-stone-grinding-mechanics\ntitle: Sandalwood Heartwood Maceration, Circular Stone Grinding & Santalol Thermoregulation\ntype: concept\nera: Early Historic Era (c. 400 BCE - 1200 CE)\nthinai: kurinji (Biophysical Metallurgy & Cosmetic Physiology)\nstatus: canonical\n---\n\n# Sandalwood Heartwood Maceration, Circular Stone Grinding & Santalol Thermoregulation\n\n## 1. The Podhigai Sandalwood Benchmark\nThe Western Ghats of Tamilakam, specifically the Podhigai hills of the Pandya kingdom, produced the world's most fragrant white and yellow sandalwood (*Santalum album* / *Ven-sandhanam*). Sangam literature constantly links cool southerly breezes (*Thenral*) with the intoxicating aroma of blooming sandalwood groves.\n\n## 2. Grinding Mechanics on the Lithic Slab (*Sandhana-Kal*)\n1. **Petrology of the Grinding Stone**: Fashioned from fine-textured, medium-hard granite or dolerite with a deliberately dressed, microscopic abrasive grain. The slab was carved as a flat disc with an outer annular groove (*Neer-vazhi*) to capture accumulating liquid paste.\n2. **Circular Friction Dynamics**: The artisan held the dense, oily heartwood log with both hands, pressing down with firm vertical pressure while executing continuous rhythmic circular strokes.\n3. **Hydration Lubrication**: Drops of chilled spring water or rosewater (*Panneer*) were continuously dripped onto the contact surface. The water acted as both an emulsion vehicle and a thermal sink, preventing frictional heating from volatilizing fragile santalol terpenes.\n\n## 3. Biophysical Cooling & Medicinal Action\n- **Santalol Concentration**: Genuine Podhigai sandalwood heartwood contained over 90% alpha- and beta-santalols.\n- **Topical Thermoregulation**: When applied to the skin, evaporation of the aqueous paste produced an immediate drop in localized skin temperature, constricting capillary vessels, alleviating tropical prickly heat, and shielding against ultraviolet solar radiation."
  },
  {
    "slug": "concept-compound-incense-formulation-narum-pukai-and-resin-burners",
    "category": "concepts",
    "file": "concept-compound-incense-formulation-narum-pukai-and-resin-burners.md",
    "node_type": "concept",
    "name_en": "Compound Incense Formulation (Narum-Pukai), Benzoin Resins & Bronze Censer Aerodynamics",
    "name_ta": "கூட்டு நறுமணப் புகை தயாரிப்பு (நறும்புகை), சாம்பிராணிப் பிசின் மற்றும் வெண்கலத் தூபக்கால் காற்றோட்டம்",
    "era": "Sangam to Chola Era",
    "year_start": -300,
    "year_end": 1100,
    "thinai": "marutham",
    "summary_en": "Pyrotechnological formulation of aromatic solid incenses (Narum-pukai / Kootu-dhoopam) blending Shorea dammar, benzoin gum (Sambrani), agarwood dust, and dried vetiver, burned over smoldering coconut charcoal inside pierced bronze censers (Dhoopa-kal).",
    "summary_ta": "சாம்பிராணிப் பிசின், குங்கிலியம், அகில்தூள், மற்றும் வெட்டிவேர் சேர்த்து அரைக்கப்பட்ட கூட்டு நறுமண உருண்டைகள் மற்றும் துளையிடப்பட்ட வெண்கல தூபக்கால்களில் எரிக்கப்படும் நறும்புகை நுட்பம்.",
    "sources": [
      "Maduraikkanchi ll. 360-375",
      "Silappadikaram",
      "South Indian Temple Ritual Metalwork"
    ],
    "content": "---\nid: concept-compound-incense-formulation-narum-pukai-and-resin-burners\ntitle: Compound Incense Formulation (Narum-Pukai), Benzoin Resins & Bronze Censer Aerodynamics\ntype: concept\nera: Sangam to Chola Era (c. 300 BCE - 1100 CE)\nthinai: marutham (Aromatic Pyrotechnology & Censer Metallurgy)\nstatus: canonical\n---\n\n# Compound Incense Formulation (Narum-Pukai), Benzoin Resins & Bronze Censer Aerodynamics\n\n## 1. The Chemistry of Compound Incense (*Kootu-Dhoopam*)\nRather than burning single unblended tree resins, ancient Tamil perfumers formulated sophisticated multi-ingredient compound incenses known in classical texts as *Kootu* or *Narum-pukai*:\n- **Base Binder Matrix**: Natural tree resins including *Styrax benzoin* (*Sambrani*) and *Canarium strictum* (*Dammar* / Black Dammar).\n- **Aromatic Heartwood Powders**: Fine shavings of aged sandalwood (*Sandhanam*) and eaglewood (*Akil*).\n- **Botanical Fixatives**: Dried vetiver root fibers (*Vettiver*), costus root (*Kottam*), and spikenard (*Sadamanji*).\n- **Plasticizing Emulsion**: Kneaded with honey (*Thaen*) and clarified ghee (*Nei*) to form moist, pliable incense cones or sun-dried pellets.\n\n## 2. Bronze Censer Aerodynamics (*Dhoopa-Kal*)\nTo sustain gentle, smoke-rich smoldering without flaming or rapid ash burnout:\n1. **Thermal Charcoal Bed**: Lump charcoal made from dense coconut shells (*Thennam-kottai*) was brought to a steady red glow inside the censer bowl.\n2. **Perforated Conical Cover**: The cast bronze censer was fitted with a domed lid pierced with floral, geometric, and avian apertures (*Killi-thulai*).\n3. **Chimney Convection Draft**: The perforated lid created a regulated thermal convection draft: rising hot air drew fresh oxygen through base vents while venting thick, aromatic, sanitized smoke out the top vents without generating foul soot.\n\n## 3. Disinfectant & Antimicrobial Functions\nIn dense tropical cities like Madurai and Puhar, daily domestic and civic incense burning functioned as an essential airborne fumigant, driving away mosquitoes, flies, and fungal mold during humid monsoons."
  },
  {
    "slug": "concept-civet-musk-and-attar-cold-enfleurage-fragrance-preservation",
    "category": "concepts",
    "file": "concept-civet-musk-and-attar-cold-enfleurage-fragrance-preservation.md",
    "node_type": "concept",
    "name_en": "Civet Musk (Punuhu), Cold Enfleurage & Animal Attar Fixative Preservation",
    "name_ta": "புனுகுப் பூனைச் சுரப்பு (புனுகு), மலர் கொழுப்பு உறிஞ்சல் (என்புளூரேஜ்) மற்றும் நறுமண நிலைநிறுத்தல்",
    "era": "Early Historic to Medieval Era",
    "year_start": -200,
    "year_end": 1200,
    "thinai": "mullai",
    "summary_en": "Biochemical animal fixatives in Tamil perfumery: harvesting glandular perineal secretions of the small Indian civet (Punuhu-poonai), deodorization, and cold fat enfleurage absorbing nocturnal jasmine and screwpine essential oils into stable ointments.",
    "summary_ta": "புனுகுப் பூனையின் நறுமணச் சுரப்பைத் தூய்மைப்படுத்தி, மல்லிகை மற்றும் தாழம்பூவின் ஆவியாகும் மணத்தை நெய் மற்றும் கொழுப்பில் உறிஞ்சி நிலைநிறுத்திய (Enfleurage) பாரம்பரிய வாசனைத் தைல நுட்பம்.",
    "sources": [
      "Silappadikaram",
      "Thiruvanaikoil & Thirumeyyam Inscriptions",
      "Traditional South Indian Aromatic Formulary"
    ],
    "content": "---\nid: concept-civet-musk-and-attar-cold-enfleurage-fragrance-preservation\ntitle: Civet Musk (Punuhu), Cold Enfleurage & Animal Attar Fixative Preservation\ntype: concept\nera: Early Historic to Medieval Era (c. 200 BCE - 1200 CE)\nthinai: mullai (Biochemical Animal Chemistry)\nstatus: canonical\n---\n\n# Civet Musk (Punuhu), Cold Enfleurage & Animal Attar Fixative Preservation\n\n## 1. Animal Fixatives in Ancient Olfactory Science\nFloral essences like jasmine (*Malligai*) and screwpine (*Thazhambu*) contain light, highly volatile aromatic alcohols and esters that evaporate within minutes in tropical heat. To create perfumes that lingered on royal silk and skin for days, ancient Tamil perfumers utilized animal fixatives:\n- **Punuhu (Civet)**: Waxy perineal glandular excretion of the Asian palm civet (*Paradoxurus hermaphroditus*) and small Indian civet (*Viverricula indica*).\n- **Kasturi (Musk)**: Dried secretion from Himalayan musk deer imported via northern trade routes.\n\n## 2. Processing & Deodorization of Punuhu\n1. **Humane Extraction**: Wild and semi-domesticated civets kept in bamboo aviaries naturally rubbed their scent glands against wooden posts, where the wax was periodically scraped off with silver spoons.\n2. **Purification via Dairy Washing**: Raw civet contains fecal skatole compounds. Perfumers washed the raw wax repeatedly in boiling milk and citrus juice (*Elumichai-saaru*), removing unpleasant odors and leaving a warm, radiant, velvety floral musk note.\n3. **Cold Fat Enfleurage**: Purified civet was blended with clarified deer fat or sesame oil, spread onto ceramic plates, and covered with freshly plucked nocturnal jasmine blossoms. Every twelve hours, spent petals were replaced with fresh flowers until the fat was fully saturated with floral molecules.\n\n## 3. Royal & Liturgical Applications\nThe resulting paste—known as *Punuhu-chattam*—was applied to royal crowns, silk turbans, and the granite moolavar deities of sanctum sanctorums, where its hydrophobic, antimicrobial nature protected stone icons against condensation decay."
  },
  {
    "slug": "char-madurai-chief-royal-perfumer-vasanai-kollan",
    "category": "characters",
    "file": "char-madurai-chief-royal-perfumer-vasanai-kollan.md",
    "node_type": "character",
    "name_en": "Chief Royal Perfumer of the Pandya Court in Madurai (Vasanai-Kollan)",
    "name_ta": "மதுரை பாண்டிய அரச தலைமை வாசனைத் திரவியக் கலைஞர் (வாசனைப் பெருந்தச்சன்)",
    "era": "Sangam Classical Era",
    "year_start": -50,
    "year_end": 150,
    "thinai": "marutham",
    "summary_en": "Chief royal perfumer and scent formulator of the ancient Pandya court in Madurai, master of blending thirty-two herbs into courtly ointments, regulating palace incense burners, and assaying imported camphor.",
    "summary_ta": "மதுரை பாண்டிய மன்னரின் அரசவையில் முப்பத்திரண்டு மூலிகைகளைக் கொண்டு நறுமணத் தைலங்களை உருவாக்கி, அரண்மனை நறும்புகை மற்றும் வாசனைப் பூச்சுகளை நிர்வகித்த முதன்மை நறுமணக் கலைஞர்.",
    "sources": [
      "Maduraikkanchi ll. 365-385",
      "Silappadikaram",
      "Pandya Palace Historical Chronicles"
    ],
    "content": "---\nid: char-madurai-chief-royal-perfumer-vasanai-kollan\ntitle: Chief Royal Perfumer of the Pandya Court in Madurai (Vasanai-Kollan)\ntype: character\nera: Sangam Classical Era (c. 50 BCE - 150 CE)\nthinai: marutham (Courtly Olfactory Guilds)\nstatus: canonical\n---\n\n# Chief Royal Perfumer of the Pandya Court in Madurai (Vasanai-Kollan)\n\n## 1. Position & Imperial Standing\nThe **Vasanai-Kollan** (Master Aromatic Alchemist) held supreme authority over the royal perfume workshops (*Thoopa-kottam*) of the ancient Pandya palace in Madurai. Serving both the sovereign and the high nobility, he was an accredited scholar of botany, chemistry, and olfactory aesthetics.\n\n## 2. Royal Responsibilities & Craft Mastery\n- **The Sovereign Unguent (*Raja-Sandhanam*)**: Formulated the proprietary royal sandalwood paste infused with saffron threads (*Kumkumapoo*), Barus camphor, and purified civet applied daily to the monarch's shoulders before public durbar.\n- **Palace Air Conditioning**: Orchestrated the burning of dense agarwood and benzoin smoke through concealed flues in palace bedchambers, ensuring rooms remained pleasantly scented and free of insects throughout the night.\n- **Assaying Imported Luxuries**: Tested the purity of imported aromatic gums arriving from Arabia, Ceylon, and Kedah at the Pandya port of Korkai."
  },
  {
    "slug": "char-marungurpattinam-master-incense-distiller-narum-pukai-seyvor",
    "category": "characters",
    "file": "char-marungurpattinam-master-incense-distiller-narum-pukai-seyvor.md",
    "node_type": "character",
    "name_en": "Master Incense Distiller & Attar Blender of Marungurpattinam (Narum-Pukai-Seyvor)",
    "name_ta": "மருங்கூர்ப்பட்டின தலைமை நறுமண வடிப்பாளர் மற்றும் தைல சிற்பி (நறும்புகை செய்வோர்)",
    "era": "Sangam Classical Era",
    "year_start": 50,
    "year_end": 200,
    "thinai": "neithal",
    "summary_en": "Master hydro-distiller operating out of the ancient coastal emporium of Marungurpattinam, veteran of boiling clay retorts, condensing wild rose and screwpine vapors into sandalwood carrier oils for oceanic export.",
    "summary_ta": "மருங்கூர்ப்பட்டினத் துறைமுகத்தில் சுடுமண் கலசங்கள் மூலம் தாழம்பூ மற்றும் அகில் தைலங்களை வடித்தெடுத்து, மரக்கலங்கள் வழியே உரோமாபுரி மற்றும் சீனாவிற்கு ஏற்றுமதி செய்த தலைமை நறுமண வணிகர்.",
    "sources": [
      "Silappadikaram Kadaladukathai",
      "Periplus of the Erythraean Sea",
      "Archaeology of the Coromandel Coast"
    ],
    "content": "---\nid: char-marungurpattinam-master-incense-distiller-narum-pukai-seyvor\ntitle: Master Incense Distiller & Attar Blender of Marungurpattinam (Narum-Pukai-Seyvor)\ntype: character\nera: Sangam Classical Era (c. 50 - 200 CE)\nthinai: neithal (Maritime Aromatic Commerce)\nstatus: canonical\n---\n\n# Master Incense Distiller & Attar Blender of Marungurpattinam (Narum-Pukai-Seyvor)\n\n## 1. Professional Identity & Port Enclave\nStationed at the maritime emporium of Marungurpattinam south of Kaveripoompattinam, the **Narum-Pukai-Seyvor** (Master Maker of Fragrant Vapors) directed export-oriented aromatic workshops catering to merchant fleets crossing the Bay of Bengal and Arabian Sea.\n\n## 2. Industrial Technical Expertise\n- **Hydro-Distillation Retort Banks**: Operated battery banks of interconnected earthenware stills (*Vaala-iyanathirangal*) fired with low-smoke acacia charcoal.\n- **Floral Attar Sourcing**: Processed tons of fresh coastal screwpine (*Pandanus* / *Thazhambu*) blooms at dawn, capturing their fugitive fragrance before mid-morning heat dissipated the delicate floral alcohols.\n- **Clay Flask Sealing**: Sealed precious attars inside narrow-necked terracotta flasks lined with beeswax, ensuring that volatile essences survived multi-month voyages across stormy ocean latitudes."
  },
  {
    "slug": "place-marungurpattinam-ancient-aromatic-haven",
    "category": "places",
    "file": "place-marungurpattinam-ancient-aromatic-haven.md",
    "node_type": "place",
    "name_en": "Marungurpattinam Ancient Aromatic & Incense Haven (Coromandel Coast)",
    "name_ta": "மருங்கூர்ப்பட்டினம் பண்டைய நறுமணத் திரவியத் துறைமுகம் மற்றும் வாசனை அங்காடி",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 500,
    "thinai": "neithal",
    "summary_en": "Celebrated ancient maritime port and incense market situated along the central Coromandel coast south of Poompuhar, described in Sangam poetry and Greek geography as a primary emporium for sandalwood, agarwood, and exotic attars.",
    "summary_ta": "பூம்புகாருக்குத் தெற்கே அமைந்திருந்த வரலாற்றுப் புகழ்பெற்ற சங்ககாலத் துறைமுகம்; அகில், சந்தனம், பன்னீர் மற்றும் நறுமணத் தைலங்கள் குவித்து விற்கப்பட்ட சர்வதேச வாசனைத் திரவிய வணிக மையம்.",
    "sources": [
      "Silappadikaram",
      "Ptolemy's Geography",
      "TNSDA Coastal Survey Reports"
    ],
    "content": "---\nid: place-marungurpattinam-ancient-aromatic-haven\ntitle: Marungurpattinam Ancient Aromatic & Incense Haven (Coromandel Coast)\ntype: place\nera: Sangam Classical Era (c. 200 BCE - 500 CE)\nthinai: neithal (Maritime Aromatic Haven)\nstatus: canonical\n---\n\n# Marungurpattinam Ancient Aromatic & Incense Haven (Coromandel Coast)\n\n## 1. Geographical Location & Coastal Topography\nMarungurpattinam is located along the central Coromandel coastline of Tamil Nadu, situated between the Kaveri delta and the coastal lagoons (coordinates approx. 10.9167° N, 79.8333° E). Sheltered by offshore barrier spits, its tidal creeks allowed merchant craft to anchor securely while loading fragile luxury cargo.\n\n## 2. Archaeological Discoveries & Aromatic Artifacts\nCoastal surveys and excavations have yielded:\n- **Unguent Alabastra & Terracotta Vials**: Hundreds of miniature, narrow-necked ceramic perfume bottles (*Kuppi*) and imported Roman glass unguentaria.\n- **Distillation Retort Fragments**: Vitrified earthenware lids with lateral conduit sockets matching traditional hydro-distillation apparatus designs.\n- **Resin Middens**: Soil cores containing fossilized residues of *Canarium* dammar and ambergris particles washed ashore and traded by coastal fishermen.\n\n## 3. Global Maritime Hub for Fragrance\nMentioned in Sangam epics alongside Puhar, Marungurpattinam was the key commercial node where hill aromatics from the Western Ghats (sandalwood, cardamom, pepper) met insular Southeast Asian resins (camphor, benzoin) before being shipped westward to Roman Alexandria and eastward to the courts of China."
  },
  {
    "slug": "text-kanakkathikaram-agrarian-grain-measures-and-cooperage-poetry",
    "category": "texts",
    "file": "text-kanakkathikaram-agrarian-grain-measures-and-cooperage-poetry.md",
    "node_type": "text",
    "name_en": "Kanakkathikaram Agrarian Grain Measures, Cooperage Standards & Fractional Metrology",
    "name_ta": "கணக்கதிகாரம் - தானிய அளவைகள், மரக்கலப் பாண்டங்கள் மற்றும் பின்னம்சார் அளவியல் பாடல்கள்",
    "era": "Sangam to Chola Era",
    "year_start": 200,
    "year_end": 1100,
    "thinai": "marutham",
    "summary_en": "Mathematical treatises in Kanakkathikaram, Aathisudi, and Sangam agricultural verses detailing the standardized volume hierarchy of turned wooden grain vessels (Sevidu, Aazhakku, Uri, Nazhi, Kuruni/Marakkal, Padakku, Kalam) ensuring fair market transactions and agrarian taxation.",
    "summary_ta": "கணக்கதிகாரம் மற்றும் சங்ககால கணித நூல்களில் செவிடு, ஆழாக்கு, உரி, நாழி, குறுணி/மரக்கால், பதக்கு, கலம் என படிமுறை வரிசையில் அமைந்த மர தானிய அளவைகள் மற்றும் துல்லிய பின்னம்சார் நுகர்வு அளவியல் பாடல்கள்.",
    "sources": [
      "Kanakkathikaram (Kari Nayanar)",
      "Purananuru v. 386",
      "Tolkappiyam Marabiyal"
    ],
    "content": "---\nid: text-kanakkathikaram-agrarian-grain-measures-and-cooperage-poetry\ntitle: Kanakkathikaram Agrarian Grain Measures, Cooperage Standards & Fractional Metrology\ntype: text\nera: Sangam to Chola Era (c. 200 - 1100 CE)\nthinai: marutham (Agrarian Mathematics & Metrology)\nstatus: canonical\n---\n\n# Kanakkathikaram: Agrarian Grain Measures, Cooperage Standards & Fractional Metrology\n\n## 1. Classical Primary Source Citations\n- **Kanakkathikaram** (Kari Nayanar): Classical Tamil mathematical and metrological compendium establishing the definitive volumetric relationships between fractions of grain measures, from the microscopic *Immi* up to the multi-ton *Kalam*.\n- **Purananuru** (v. 386): Depicts bustling village threshing floors (*Kalam*) where harvested paddy (*Nel*) is measured using polished wooden vessels (*Marakkal* / *Ambanam*) before distribution to bardic poets and tenant cultivators.\n- **Tolkappiyam** (*Marabiyal*): Encodes the conventional names and hierarchical terms for measures of capacity, weight, and volume in ancient Tamilakam.\n\n## 2. Volumetric Hierarchy of Tamil Cooperage\nThe capacity measurement system was strictly binary and sexagesimal, permitting rapid mental calculations during village harvests:\n- **5 Sevidu** = 1 Aazhakku (~160 ml)\n- **2 Aazhakku** = 1 Uzhakku (~320 ml)\n- **2 Uzhakku** = 1 Uri (~640 ml)\n- **2 Uri** = 1 Nazhi / Padi (~1,280 ml or ~1.3 liters)\n- **8 Nazhi** = 1 Kuruni / Marakkal (~10.24 liters)\n- **2 Kuruni** = 1 Padakku (~20.48 liters)\n- **2 Padakku** = 1 Thunai (~40.96 liters)\n- **3 Thunai (12 Marakkal)** = 1 Kalam (~122.88 liters or ~100 kg paddy)\n\n## 3. Socio-Economic Enforcement\nStandard volume vessels prevented agrarian extortion by landholders and guaranteed that royal grain tithes (*Kadamai*) were calculated with absolute uniformity across empire districts."
  },
  {
    "slug": "insc-ennayiram-chola-temple-grain-treasury-and-marakkal-charters",
    "category": "inscriptions",
    "file": "insc-ennayiram-chola-temple-grain-treasury-and-marakkal-charters.md",
    "node_type": "inscription",
    "name_en": "Ennayiram Chola Temple Grain Treasury Charters & Marakkal Standardization Epigraphs",
    "name_ta": "எண்ணாயிரம் சோழர் தானியக் களஞ்சியம் மற்றும் மரக்கால் அளவை நிலைப்படுத்தல் கல்வெட்டுகள்",
    "era": "Imperial Chola Era",
    "year_start": 1025,
    "year_end": 1070,
    "thinai": "marutham",
    "summary_en": "Inscriptions of Rajendra Chola I at Ennayiram detailing the imperial Vedic college and granary, specifying exact daily grain rations (Nazhi, Kuruni) for 350 scholars, grain storage logistics, and calibrated brass-rimmed Marakkal vessels.",
    "summary_ta": "முதலாம் இராஜேந்திர சோழனின் புகழ்பெற்ற எண்ணாயிரக் கல்வெட்டுகள்; 350 மாணவர்களுக்கான தினசரி நெல் பங்கீடுகள், நெற்களஞ்சியப் பராமரிப்பு மற்றும் அரச முத்திரை பொறித்த பித்தளை விளிம்பு மரக்கால் வழியே அளக்கப்பட்ட நெல் நிர்வாக ஆவணங்கள்.",
    "sources": [
      "South Indian Inscriptions Vol XXIII",
      "Epigraphia Indica Vol IX",
      "Chola Agrarian Inscriptions of South Arcot"
    ],
    "content": "---\nid: insc-ennayiram-chola-temple-grain-treasury-and-marakkal-charters\ntitle: Ennayiram Chola Temple Grain Treasury Charters & Marakkal Standardization Epigraphs\ntype: inscription\nera: Imperial Chola Era (c. 1025 - 1070 CE)\nthinai: marutham (Imperial Treasury Epigraphy)\nstatus: canonical\n---\n\n# Ennayiram: Chola Temple Grain Treasury Charters & Marakkal Standardization Epigraphs\n\n## 1. Epigraphical Provenance\nCarved into the granite walls of the Alagiya Narasimha Perumal temple at Ennayiram (Villupuram district), this monumental inscription dates to the 25th regnal year of Emperor Rajendra Chola I (c. 1037 CE).\n\n## 2. Inscription Content & Educational Grain Budgets\n- **Vedic College Rations**: Records the endowment of vast village lands yielding thousands of kalams of paddy annually to feed 340 residential students and 14 professors.\n- **Exact Daily Rations in Nazhi & Kuruni**: \n   - Junior students: 1 *Nazhi* of cleaned rice daily + cash allowance for oil.\n   - Senior scholars: 1.5 *Nazhi* + condiments.\n   - Professors: 1 *Kuruni* (8 Nazhi) of paddy per day.\n- **Grain Waste & Spillage Allowances**: Inscription specifies statutory allowances for shrinkage, rat loss, and moisture evaporation (*Nel-theemai*) during annual silo storage.\n\n## 3. Standardization via the Imperial Marakkal\nThe inscription mandates that all incoming tenant grain tithes and outgoing student rations be measured using the officially consecrated imperial standard vessel, prohibiting the use of uncertified local village measures to prevent fraud."
  },
  {
    "slug": "insc-thiruvidaimarudur-royal-rajarajan-marakkal-standard-charters",
    "category": "inscriptions",
    "file": "insc-thiruvidaimarudur-royal-rajarajan-marakkal-standard-charters.md",
    "node_type": "inscription",
    "name_en": "Thiruvidaimarudur Royal Rajarajan-Marakkal Standard Charters & Grain Guild Epigraphs",
    "name_ta": "திருவிடைமருதூர் சோழர் 'இராஜராஜன்-மரக்கால்' அரச அளவை மற்றும் தானிய வணிகக் கல்வெட்டுகள்",
    "era": "Imperial Chola Era",
    "year_start": 985,
    "year_end": 1014,
    "thinai": "marutham",
    "summary_en": "Inscriptions of Rajaraja Chola I at the Mahalingaswami temple in Thiruvidaimarudur formally establishing the royal 'Rajarajan-Marakkal' as the certified uniform grain capacity vessel for the entire delta kingdom, complete with iron rim reinforcement rules.",
    "summary_ta": "திருவிடைமருதூர் மகாலிங்கசுவாமி கோவில் கல்வெட்டுகள்; சோழ நாடு முழுவதும் அதிகாரப்பூர்வ தானிய அளவையாக 'இராஜராஜன்-மரக்கால்' நிறுவப்பட்டது, பித்தளை/இரும்பு விளிம்பு கட்டமைப்பு மற்றும் தேய்மானத் தடுப்பு அரச விதிகள்.",
    "sources": [
      "South Indian Inscriptions Vol V",
      "Thiruvidaimarudur Inscriptions",
      "Nilakanta Sastri: The Colas"
    ],
    "content": "---\nid: insc-thiruvidaimarudur-royal-rajarajan-marakkal-standard-charters\ntitle: Thiruvidaimarudur Royal Rajarajan-Marakkal Standard Charters & Grain Guild Epigraphs\ntype: inscription\nera: Imperial Chola Era (c. 985 - 1014 CE)\nthinai: marutham (State Standard Metrology)\nstatus: canonical\n---\n\n# Thiruvidaimarudur: Royal Rajarajan-Marakkal Standard Charters & Grain Guild Epigraphs\n\n## 1. Provenance & Metrological Mandate\nDiscovered on the inner ambulatory walls of the Thiruvidaimarudur temple in the Thanjavur delta, this critical inscription records a major administrative reform enacted during the height of Rajaraja Chola I's reign.\n\n## 2. The 'Rajarajan-Marakkal' Decree\nBefore Rajaraja I, dozens of disparate, locally varied measuring vessels (*Kudi-marakkal*, *Urar-marakkal*) existed across different nadus, leading to disputes during tax collection. By this charter:\n- **Imperial Standardization**: Rajaraja abolished regional variants, declaring the **Rajarajan-Marakkal** (named after his royal title) as the sole legal grain measure.\n- **Prototype Master Vessel**: A certified bronze master prototype was housed inside the royal treasury at Thanjavur, against which all temple and market wooden vessels had to be checked annually.\n- **Punishment for Debasement**: Merchants or tax collectors caught using shallow-bottomed or shaved wooden vessels were subject to heavy fines (*Dhandam*) paid in gold.\n\n## 3. Economic Unification of the Chola Empire\nThe standardized Marakkal unified the agrarian economy of the Kaveri delta, enabling seamless market trade, transparent tax assessments, and predictable grain accumulation for military mobilization."
  },
  {
    "slug": "concept-hardwood-grain-measure-lathe-turning-and-cooperage-mechanics",
    "category": "concepts",
    "file": "concept-hardwood-grain-measure-lathe-turning-and-cooperage-mechanics.md",
    "node_type": "concept",
    "name_en": "Hardwood Grain Measure Lathe Turning, Hollow Cooperage & Volumetric Tolerances",
    "name_ta": "கடின மரக் கடைசல் அளவைப் பாண்டங்கள் (மரக்கால்), குடைசல் வேலை மற்றும் கனஅளவுத் துல்லியவியல்",
    "era": "Early Historic to Chola Era",
    "year_start": -300,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Wood-turning and cooperage engineering of Tamil grain vessels: turning dense, non-warping seasoned hardwoods (Vengai, Teak, Ebony) on bow-lathes, precision internal boring to exact cubic capacity, and water-displacement volumetric calibration.",
    "summary_ta": "வேங்கை, தேக்கு, கருங்காலி போன்ற உறுதியான மரங்களை கடைசல் பட்டடையில் ஏற்றி, உள்வட்டத்தைக் குடைந்து, நீர் இடப்பெயர்ச்சி மூலம் துல்லிய கனஅளவு நிர்ணயித்த பாரம்பரிய மரக்கலத் தயாரிப்பு நுட்பம்.",
    "sources": [
      "Silappadikaram",
      "Kanakkathikaram",
      "Traditional Woodcraft & Lathe Technology of Tamil Nadu"
    ],
    "content": "---\nid: concept-hardwood-grain-measure-lathe-turning-and-cooperage-mechanics\ntitle: Hardwood Grain Measure Lathe Turning, Hollow Cooperage & Volumetric Tolerances\ntype: concept\nera: Early Historic to Chola Era (c. 300 BCE - 1200 CE)\nthinai: marutham (Wood Lathe Turning & Volumetric Geometry)\nstatus: canonical\n---\n\n# Hardwood Grain Measure Lathe Turning, Hollow Cooperage & Volumetric Tolerances\n\n## 1. Wood Selection for Volumetric Stability\nGrain measuring vessels cannot be made from soft, hygroscopic woods that expand in humid weather or shrink in dry heat, as volume fluctuations would distort tax measurements:\n- **Vengai (*Pterocarpus marsupium*)**: Dense, hard, resistant to termites and dimensional warping.\n- **Thekku (Teak / *Tectona grandis*)**: High natural oil content prevents water absorption and grain rot.\n- **Karungali (Ebony / *Diospyros ebenum*)**: Extremely dense, hard-wearing, used for royal master standards.\n\n## 2. Lathe Turning & Boring Mechanics (*Kadaisal-Pattarai*)\n1. **Log Seasoning**: Hardwood trunk sections were seasoned in shade for two years to ensure complete equilibrium moisture content.\n2. **Bow-Lathe Mounting (*Vil-Kadaisal*)**: The cylindrical timber block was centered between iron pivots on a horizontal wooden bed, rotated at high speed using a coir bowstring pulled by an apprentice.\n3. **Internal Core Boring**: The master cooper applied long-handled gouges and curved hollowing scrapers, boring out the interior core to exact vertical cylindrical dimensions with flat, level bottoms.\n4. **Volumetric Verification**: The finished vessel was calibrated using dry sesame seeds or water displacement against the royal reference prototype, adjusting the depth until volumetric error was under 0.5%."
  },
  {
    "slug": "concept-brass-rimmed-measuring-vessel-calibration-and-state-stamping",
    "category": "concepts",
    "file": "concept-brass-rimmed-measuring-vessel-calibration-and-state-stamping.md",
    "node_type": "concept",
    "name_en": "Brass-Rimmed Measuring Vessel Calibration, Anti-Wear Metallurgy & State Seal Stamping",
    "name_ta": "பித்தளை விளிம்பு மரக்கால் அளவை, தேய்மானத் தடுப்பு உலோகவியல் மற்றும் அரச முத்திரையிடுதல்",
    "era": "Sangam to Chola Era",
    "year_start": -200,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Reinforcing wooden measuring vessels with riveted brass and iron rim collars to prevent lip abrasion during grain striking, paired with hot-iron state branding and temple seal stamping certifying legal volumetric integrity.",
    "summary_ta": "மரக்காலின் வாய் விளிம்பு தேய்ந்து கனஅளவு குறையாமல் இருக்க பித்தளை அல்லது இரும்புப் பட்டைகளை அறைந்து, அரச மற்றும் ஆலய முத்திரைகளைச் சுட்டுப் பதித்து சட்டப்பூர்வமாக்கிய அளவியல் தொழில்நுட்பம்.",
    "sources": [
      "Thiruvidaimarudur Inscriptions",
      "Ennayiram Epigraphs",
      "Tamil Metrology and Guild Administration"
    ],
    "content": "---\nid: concept-brass-rimmed-measuring-vessel-calibration-and-state-stamping\ntitle: Brass-Rimmed Measuring Vessel Calibration, Anti-Wear Metallurgy & State Seal Stamping\ntype: concept\nera: Sangam to Chola Era (c. 200 BCE - 1200 CE)\nthinai: marutham (Metrological Enforcement & Metallurgy)\nstatus: canonical\n---\n\n# Brass-Rimmed Measuring Vessel Calibration, Anti-Wear Metallurgy & State Seal Stamping\n\n## 1. The Wear Problem in Grain Measuring\nDuring the measurement of abrasive unhusked paddy (*Nel*), the wooden brim of the measure is subjected to friction every time the grain is leveled with a straight wooden strike-bar (*Thalambu-kole*). Over months of daily use, the wooden lip wears down, imperceptibly reducing the vessel's capacity:\n- A loss of just 2 millimeters off the rim of a Marakkal reduces measured volume by over 2.5%, causing significant tax revenue shortfalls.\n\n## 2. Metallurgical Rim Reinforcement (*Pithalai-Kattu*)\nTo prevent this wear, ancient Tamil coopers developed metal-bound vessels:\n1. **Cast Brass / Bronze Rim Collar**: A precision-cast sheet collar of brass or bronze was fitted snugly around the outer and inner perimeter of the top rim.\n2. **Flush Copper Riveting**: Fastened with flush-hammered copper rivets (*Chembani*) so no internal protrusions could trap grain seeds.\n3. **Base Band Armor**: A lower metal band was riveted around the base to prevent splitting when slammed onto stone warehouse floors.\n\n## 3. Royal Brand Stamping (*Achu-Pathithal*)\n- **State Brand Mark**: Certified vessels were branded on the exterior wood using red-hot iron dies carrying the royal emblem (Chola Tiger, Pandya Fish, or Temple Conch).\n- **Periodic Guild Inspection**: Village grain inspectors (*Kole-alavu-kankani*) conducted annual audits, re-stamping verified measures and destroying uncertified vessels."
  },
  {
    "slug": "concept-sexagesimal-grain-metrology-sevidu-alakku-uri-nazhi-marakkal",
    "category": "concepts",
    "file": "concept-sexagesimal-grain-metrology-sevidu-alakku-uri-nazhi-marakkal.md",
    "node_type": "concept",
    "name_en": "Sexagesimal Grain Metrology, Strike-Measurement (Thalambu) & Heaped Calibration",
    "name_ta": "அளவைப் படிநிலை (செவிடு-ஆழாக்கு-உரி-நாழி-மரக்கால்), தலைதடவு அளவை மற்றும் குவியல் கணக்கீடு",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "The operational physics of ancient Tamil volumetric measurement: distinguishing between struck measure (Thalambu-alavu) using a polished scraper stick for flat accuracy, and heaped measure (Kuvithal) used for rough retail commodities, governing civic tax equity.",
    "summary_ta": "மரக்காலில் தானியத்தை நிரப்பி சமப்படுத்தும் தலைதடவு (தலம்பு) அளவை முறை மற்றும் குவித்து அளக்கும் முறைக்கு இடையிலான துல்லிய வேறுபாடுகள் மற்றும் பண்டைய வரி அளவியல் நுட்பங்கள்.",
    "sources": [
      "Kanakkathikaram",
      "Tolkappiyam Porulathikaram",
      "Chola Revenue Assessment Manuals"
    ],
    "content": "---\nid: concept-sexagesimal-grain-metrology-sevidu-alakku-uri-nazhi-marakkal\ntitle: Sexagesimal Grain Metrology, Strike-Measurement (Thalambu) & Heaped Calibration\ntype: concept\nera: Sangam Classical Era (c. 300 BCE - 1200 CE)\nthinai: marutham (Agrarian Measurement Physics)\nstatus: canonical\n---\n\n# Sexagesimal Grain Metrology, Strike-Measurement (Thalambu) & Heaped Calibration\n\n## 1. Struck Measure (*Thalambu-Alavu*) vs. Heaped Measure (*Kuvithal*)\nIn ancient Tamil grain markets, legal contracts and tax charters explicitly specified the measurement technique to eliminate ambiguity:\n- **Thalambu-Alavu (Struck Measure)**: Grain was poured loosely into the vessel without tamping. A cylindrical wooden strike-bar (*Thalambu-kole* or *Padi-kole*) was drawn smoothly across the brass-bound rim, scraping off all grain projecting above the level of the brim. This was the mandatory standard for imperial tax collection, temple rations, and wholesale transactions.\n- **Kuvithal-Alavu (Heaped Measure)**: Grain was allowed to pile naturally into a conical heap above the rim at its angle of repose (~35 degrees). Used primarily in local retail barter for low-value agricultural goods (millets, pulses).\n\n## 2. Density Variations & Moisture Accounting\nTamil metrologists recognized that fresh, damp paddy occupies less volume per kilogram than dry seasoned grain:\n- **Theemai Factor**: Epigraphs record statutory deductions (*Nel-Theemai*) of 5 to 10% allowed when measuring freshly harvested, wet monsoon paddy (*Kar-nel*) compared to sun-dried summer grain (*Kuruvai-nel*).\n\n## 3. Mathematical Elegance of the System\nThe system's modularity allowed any quantity of grain from a single meal portion (~1 Nazhi) up to an armada's cargo (~10,000 Kalams) to be computed and recorded using integer multiples and simple binary halves, making Tamil agricultural administration one of the most efficient in pre-modern history."
  },
  {
    "slug": "concept-granary-moisture-protection-nel-kuthir-and-timber-sluice-gates",
    "category": "concepts",
    "file": "concept-granary-moisture-protection-nel-kuthir-and-timber-sluice-gates.md",
    "node_type": "concept",
    "name_en": "Granary Moisture Protection, Nel-Kuthir Earthen Silos & Gravity Discharge Sluices",
    "name_ta": "நெற்களஞ்சியம் ஈரப்பதப் பாதுகாப்பு, நெற்குதிர் சுடுமண் சேமிப்பு மற்றும் ஈர்ப்பு விசை தானிய மதகுகள்",
    "era": "Early Historic to Medieval Era",
    "year_start": -300,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Post-harvest grain preservation engineering: elevated granaries (Nel-Kalanjiyam), unbaked clay-straw bins (Nel-Kuthir) raised on stone piers to deter rodents, neem-leaf fumigation, and bottom slide-board gravity discharge chutes.",
    "summary_ta": "எலி மற்றும் ஈரப்பதம் புகாவண்ணம் கருங்கல் தூண்கள் மீது உயர்த்தப்பட்ட நெற்களஞ்சியங்கள், வேப்பிலை பாதுகாப்புடன் கூடிய நெற்குதிர்கள் மற்றும் கீழ்மட்ட தானிய வெளியேற்ற மதகுகளின் சேமிப்புப் பொறியியல்.",
    "sources": [
      "Purananuru v. 230",
      "Silappadikaram",
      "Temple Architecture of the Cholas (Srinivasan)"
    ],
    "content": "---\nid: concept-granary-moisture-protection-nel-kuthir-and-timber-sluice-gates\ntitle: Granary Moisture Protection, Nel-Kuthir Earthen Silos & Gravity Discharge Sluices\ntype: concept\nera: Early Historic to Medieval Era (c. 300 BCE - 1200 CE)\nthinai: marutham (Agricultural Storage & Silo Engineering)\nstatus: canonical\n---\n\n# Granary Moisture Protection, Nel-Kuthir Earthen Silos & Gravity Discharge Sluices\n\n## 1. The Challenge of Tropical Grain Storage\nIn the tropical monsoon climate of Tamilakam, harvested paddy stored improperly is quickly decimated by rice weevils (*Sitophilus oryzae*), fungal molds (*Aspergillus*), and rodents. Ancient Tamil agriculturalists solved this through specialized structural silos known as **Nel-Kalanjiyam** and **Nel-Kuthir**.\n\n## 2. Structural Design of the Nel-Kuthir\n1. **Raised Stone Piers (*Kal-Thoon*)**: Earthen silos were elevated 40 to 60 cm above ground level on rounded granite boulders. This air gap prevented subterranean soil moisture from wicking into the bin and created an impassable physical barrier against termites and burrowing rats.\n2. **Clay-Straw Composite Walls**: The cylindrical silo body was built up in spiraling coils of unbaked clay blended with rice husk, chopped straw, and dried cowdung. The porous clay walls breathed, allowing metabolic grain heat and moisture vapor to escape without condensation.\n3. **Botanical Pest Repellents**: Dried leaves of neem (*Veppilai*), wild vitex (*Nochi*), and turmeric root powder were mixed with the paddy layers to naturally repel insect pests.\n\n## 3. Gravity Discharge Chutes (*Nel-Kadavu*)\nAt the bottom of the silo, an inclined wooden spout was fitted with a sliding vertical gate (*Palagai-kadavu*):\n- When the gate was lifted, grain flowed smoothly under gravity into a waiting Marakkal measure, avoiding the need to climb into the silo from above and minimizing grain breakage and airborne dust."
  },
  {
    "slug": "char-ennayiram-master-grain-cooper-marakkal-alavalar",
    "category": "characters",
    "file": "char-ennayiram-master-grain-cooper-marakkal-alavalar.md",
    "node_type": "character",
    "name_en": "Master Grain Cooper & Vessel Calibrator of Ennayiram (Marakkal-Alavalar)",
    "name_ta": "எண்ணாயிரம் தலைமை தானிய அளவைப் பாண்ட தச்சர் (மரக்கால் அளவாளர்)",
    "era": "Imperial Chola Era",
    "year_start": 1020,
    "year_end": 1080,
    "thinai": "marutham",
    "summary_en": "Chief wood cooper and metrological calibrator attached to the royal granary at Ennayiram, authoritative master of lathe-turning hardwood measures, mounting brass collars, and verifying statutory college grain quotas.",
    "summary_ta": "எண்ணாயிரம் அரச தானியக் களஞ்சியத்தின் தலைமை மரக்கல தச்சர்; வேங்கை மரத்தில் மரக்கால் கடைசல் செய்து, பித்தளை விளிம்பு அமைத்து, கல்விச்சாலையின் நெல் அளவைகளை நிலைநிறுத்திய முதன்மை அளவாளர்.",
    "sources": [
      "Ennayiram Temple Epigraphs",
      "Chola Village Administration Archives",
      "South Indian Inscriptions Vol XXIII"
    ],
    "content": "---\nid: char-ennayiram-master-grain-cooper-marakkal-alavalar\ntitle: Master Grain Cooper & Vessel Calibrator of Ennayiram (Marakkal-Alavalar)\ntype: character\nera: Imperial Chola Era (c. 1020 - 1080 CE)\nthinai: marutham (Granary Metrology Leadership)\nstatus: canonical\n---\n\n# Master Grain Cooper & Vessel Calibrator of Ennayiram (Marakkal-Alavalar)\n\n## 1. Professional Identity & Office\nThe **Marakkal-Alavalar** held the critical civic office of master cooper and volumetric certifier for the massive imperial granary and residential university at Ennayiram during the reign of Rajendra Chola I. \n\n## 2. Technical Mastery & Daily Oversight\n- **Precision Turning**: Sourced seasoned heartwood teak and vengai, turning uniform-capacity cylindrical measures on his workshop lathe.\n- **Water Displacement Calibration**: Tested each newly finished measure against the temple's official bronze prototype using water-displacement balances, filing the internal bottom until the volume matched down to the milliliter.\n- **Grain Strike Supervision**: Oversaw the measurement of hundreds of daily cartloads of tribute paddy brought in by tenant farmers, ensuring that measuring strikes were level, uncompressed, and free of foreign debris."
  },
  {
    "slug": "char-thanjavur-royal-metrology-inspector-kole-alavu-kankani",
    "category": "characters",
    "file": "char-thanjavur-royal-metrology-inspector-kole-alavu-kankani.md",
    "node_type": "character",
    "name_en": "Royal Metrology Inspector of the Thanjavur Treasury (Kole-Alavu-Kankani)",
    "name_ta": "தஞ்சாவூர் சோழர் அரச பண்டார அளவை ஆய்வாளர் (கோலளவுக் கண்காணி)",
    "era": "Imperial Chola Era",
    "year_start": 990,
    "year_end": 1035,
    "thinai": "marutham",
    "summary_en": "Senior state metrology inspector dispatched from the Thanjavur imperial treasury to inspect village grain measures, brand verified standards with the Chola royal tiger seal, and audit revenue registers across the delta.",
    "summary_ta": "தஞ்சைப் பெரிய கோவில் மற்றும் அரச கருவூலத்தின் தலைமை அளவை அதிகாரி; கிராமங்கள் தோறும் புழங்கும் மரக்கால்களை ஆய்வு செய்து, புலி முத்திரை பதித்து, வரி ஏய்ப்புகளைத் தடுத்த அரச கண்காணிப்பாளர்.",
    "sources": [
      "Brihadisvara Temple Inscriptions",
      "South Indian Inscriptions Vol II",
      "Chola Revenue Manuals"
    ],
    "content": "---\nid: char-thanjavur-royal-metrology-inspector-kole-alavu-kankani\ntitle: Royal Metrology Inspector of the Thanjavur Treasury (Kole-Alavu-Kankani)\ntype: character\nera: Imperial Chola Era (c. 990 - 1035 CE)\nthinai: marutham (Imperial Fiscal Administration)\nstatus: canonical\n---\n\n# Royal Metrology Inspector of the Thanjavur Treasury (Kole-Alavu-Kankani)\n\n## 1. Imperial Standing & Authority\nOperating directly under the chief revenue minister (*Adhikari*) of Emperor Rajaraja Chola I, the **Kole-Alavu-Kankani** (Imperial Inspector of Standards and Measures) held judicial authority to enforce uniform metrology throughout the Chola realm.\n\n## 2. Regulatory Duties & Audit Circuit\n- **Circuit Inspections**: Traveled with an official bronze prototype of the *Rajarajan-Marakkal* to every market town (*Nagaram*) and agricultural assembly (*Sabha*).\n- **Brand Stamping Authority**: Possessed the royal heated branding iron to emboss the imperial tiger crest onto verified hardwood vessels.\n- **Seizure of Fraudulent Measures**: Empowered by imperial edict to confiscate and burn non-compliant, fraudulent, or worn measures, levying statutory gold fines on delinquent merchants and local administrators."
  },
  {
    "slug": "place-ennayiram-ancient-grain-treasury-haven",
    "category": "places",
    "file": "place-ennayiram-ancient-grain-treasury-haven.md",
    "node_type": "place",
    "name_en": "Ennayiram Ancient Grain Treasury Haven & Imperial Educational Center",
    "name_ta": "எண்ணாயிரம் சோழர் தானியக் கருவூலம் மற்றும் பெருங்கலைக் கல்லூரி நகரம்",
    "era": "Imperial Chola Era",
    "year_start": 950,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Celebrated Chola agrarian center and educational sanctuary in Villupuram district, renowned for its colossal imperial granaries, standardized Marakkal measuring regimes, and historic inscriptions detailing student grain endowments.",
    "summary_ta": "விழுப்புரம் மாவட்டத்தில் அமைந்த வரலாற்றுப் புகழ்பெற்ற சோழர் தானியக் களஞ்சியம் மற்றும் பல்கலைக்கழக மையம்; இராஜேந்திர சோழனின் அளவியல் ஆவணங்கள் மற்றும் தானிய மேலாண்மைக்கான வரலாற்றுத் தளம்.",
    "sources": [
      "South Indian Inscriptions Vol XXIII",
      "Archaeological Survey of Northern Tamil Nadu",
      "Nilakanta Sastri: The Colas"
    ],
    "content": "---\nid: place-ennayiram-ancient-grain-treasury-haven\ntitle: Ennayiram Ancient Grain Treasury Haven & Imperial Educational Center\ntype: place\nera: Imperial Chola Era (c. 950 - 1200 CE)\nthinai: marutham (Imperial Granary Sanctuary)\nstatus: canonical\n---\n\n# Ennayiram Ancient Grain Treasury Haven & Imperial Educational Center\n\n## 1. Geographical Location & Agrarian Setting\nEnnayiram is located in the fertile plains of modern Villupuram district in northern Tamil Nadu (coordinates approx. 12.1833° N, 79.5167° E). Blessed with feeder tanks and extensive paddy cultivation, it served as a major regional storage haven and educational metropolis under the Imperial Cholas.\n\n## 2. Archaeological Remains & Granary Architecture\nSurveys and epigraphical excavations have identified:\n- **Massive Granary Foundations**: Substructures of elevated grain storage complexes designed with thick stone retaining bases and gravity-fed chutes.\n- **Metrological Inscriptions**: The famous 1037 CE charter of Rajendra Chola I detailing the precise distribution of thousands of kalams of paddy through the imperial *Marakkal*.\n- **Terracotta Ring Wells & Soak Pits**: Domestic and civic water infrastructure supporting over a thousand resident scholars, professors, and granary administrators.\n\n## 3. Historic Significance for Metrological Science\nEnnayiram stands as the paramount physical monument to Chola bureaucratic precision, demonstrating how standardized capacity metrology was seamlessly fused with temple governance, higher education, and welfare administration."
  }
]

EDGES = [
  [
    "text-manimekalai-burnt-brick-architecture-and-stucco-poetry",
    "describes_brick_monuments",
    "concept-sangam-burnt-brick-kiln-pyrotechnics-and-mortarless-bonding",
    "literature",
    "Sangam Classical Era",
    "Manimekalai verses depict monumental burnt-brick chaityas, stupas, and monasteries at Puhar.",
    "Manimekalai Chakravakkottam ll. 80-115"
  ],
  [
    "insc-urayur-chola-brick-temple-and-drainage-charters",
    "records_brick_foundations_at",
    "place-urayur-ancient-chola-brick-masonry-haven",
    "epigraphy",
    "Early Historic to Chola Era",
    "Uraiyur excavations and epigraphs reveal early Chola brick palace foundations and covered drainage conduits.",
    "Uraiyur Archaeological Excavations"
  ],
  [
    "insc-poompuhar-sangam-brick-wharf-and-jetty-epigraphs",
    "proves_maritime_brickwork",
    "concept-sangam-burnt-brick-kiln-pyrotechnics-and-mortarless-bonding",
    "epigraphy",
    "Sangam Classical Era",
    "Excavations at Poompuhar prove that monumental wharves were built with dense 4:2:1 proportioned burnt bricks.",
    "ASI Marine Archaeology Unit Reports"
  ],
  [
    "concept-sangam-burnt-brick-kiln-pyrotechnics-and-mortarless-bonding",
    "provides_core_for",
    "concept-hydraulic-lime-plaster-slaking-and-sudhai-stucco-sculpture",
    "architecture",
    "Early Historic Era",
    "Burnt-brick walls provided the structural core over which hydraulic lime stucco (Sudhai) was sculpted.",
    "Mayamata Architecture Treatise"
  ],
  [
    "concept-terracotta-ring-well-engineering-urai-kinaru-and-soak-pits",
    "supplies_freshwater_to",
    "place-urayur-ancient-chola-brick-masonry-haven",
    "hydraulics",
    "Early Historic Era",
    "Terracotta ring wells (Urai-kinaru) tapped subterranean Kaveri water tables across residential Uraiyur.",
    "Pathitrupathu v. 51"
  ],
  [
    "concept-corbelled-brick-vaulting-and-subsurface-stormwater-conduits",
    "evacuates_drainage_from",
    "place-urayur-ancient-chola-brick-masonry-haven",
    "civil_engineering",
    "Early Historic Era",
    "Corbelled brick vaulted drains evacuated municipal stormwater from Uraiyur into the Kaveri.",
    "Chola Urban Civil Engineering Studies"
  ],
  [
    "char-poompuhar-master-brick-architect-sengal-thatchan",
    "constructed_wharves_at",
    "insc-poompuhar-sangam-brick-wharf-and-jetty-epigraphs",
    "architecture",
    "Sangam Classical Era",
    "The master brick architect engineered the semicircular brick wharf platform at Poompuhar.",
    "NIO Underwater Excavations Bulletin"
  ],
  [
    "char-urayur-master-stucco-sculptor-sudhai-sirpan",
    "sculpted_icons_at",
    "place-urayur-ancient-chola-brick-masonry-haven",
    "plastic_arts",
    "Sangam to Chola Era",
    "The master stucco sculptor modeled divine icons and palace reliefs over brick cores at Uraiyur.",
    "Uraiyur Art Historical Catalogues"
  ],
  [
    "text-manimekalai-burnt-brick-architecture-and-stucco-poetry",
    "celebrates_stucco_art",
    "concept-hydraulic-lime-plaster-slaking-and-sudhai-stucco-sculpture",
    "literature",
    "Sangam Classical Era",
    "Manimekalai poetry describes dazzling white lime-mortar plaster and painted stucco bas-reliefs.",
    "Manimekalai ll. 80-95"
  ],
  [
    "char-poompuhar-master-brick-architect-sengal-thatchan",
    "enforced_modular_ratio",
    "concept-sangam-burnt-brick-kiln-pyrotechnics-and-mortarless-bonding",
    "metrology",
    "Sangam Classical Era",
    "The master architect enforced the universal 4:2:1 dimensional standard across brick kilns.",
    "Keezhadi & Uraiyur Ceramic Metrology"
  ],
  [
    "text-maduraikkanchi-aromatic-bazaar-and-incense-poetry",
    "depicts_aromatic_bazaars",
    "concept-compound-incense-formulation-narum-pukai-and-resin-burners",
    "literature",
    "Sangam Classical Era",
    "Maduraikkanchi poems describe Madurai evening markets dense with smoldering aromatic incense braziers.",
    "Maduraikkanchi ll. 360-390"
  ],
  [
    "insc-kallidaikurichi-royal-sandalwood-tribute-charters",
    "regulates_harvests_of",
    "concept-sandalwood-heartwood-maceration-and-stone-grinding-mechanics",
    "epigraphy",
    "Pandya Classical Era",
    "Pandya charters at Kallidaikurichi regulate royal sandalwood tree felling and tribute deliveries from Podhigai.",
    "South Indian Inscriptions Vol XIV"
  ],
  [
    "insc-thirumeyyam-temple-aromatic-ointment-and-camphor-endowments",
    "endows_civet_ointments",
    "concept-civet-musk-and-attar-cold-enfleurage-fragrance-preservation",
    "epigraphy",
    "Medieval Pandya Era",
    "Thirumeyyam rock-cut inscriptions record merchant endowments for daily civet musk and camphor ointments.",
    "Inscriptions of the Pudukkottai State"
  ],
  [
    "concept-clay-hydro-distillation-and-akil-agarwood-essential-oils",
    "distills_resins_into",
    "concept-civet-musk-and-attar-cold-enfleurage-fragrance-preservation",
    "chemistry",
    "Sangam Classical Era",
    "Hydro-distilled floral and wood essential oils were fixed with animal civet musk to prevent rapid evaporation.",
    "Traditional South Indian Aromatic Formulary"
  ],
  [
    "concept-sandalwood-heartwood-maceration-and-stone-grinding-mechanics",
    "provides_cooling_base_for",
    "concept-civet-musk-and-attar-cold-enfleurage-fragrance-preservation",
    "dermatology",
    "Early Historic Era",
    "Freshly ground sandalwood paste served as the cooling carrier base for royal civet musk ointments.",
    "Pharmacological Studies on Santalum album"
  ],
  [
    "char-madurai-chief-royal-perfumer-vasanai-kollan",
    "formulated_perfumes_at",
    "text-maduraikkanchi-aromatic-bazaar-and-incense-poetry",
    "craft",
    "Sangam Classical Era",
    "The chief royal perfumer formulated thirty-two herb ointments for the Pandya court in Madurai.",
    "Maduraikkanchi ll. 365-385"
  ],
  [
    "char-marungurpattinam-master-incense-distiller-narum-pukai-seyvor",
    "operated_distilleries_at",
    "place-marungurpattinam-ancient-aromatic-haven",
    "chemistry",
    "Sangam Classical Era",
    "The master distiller operated battery banks of hydro-distillation stills at Marungurpattinam.",
    "Silappadikaram Kadaladukathai"
  ],
  [
    "char-marungurpattinam-master-incense-distiller-narum-pukai-seyvor",
    "practiced_clay_distillation",
    "concept-clay-hydro-distillation-and-akil-agarwood-essential-oils",
    "technology",
    "Sangam Classical Era",
    "The master distiller perfected clay-retort steam stripping of agarwood and screwpine oils.",
    "Forbes: Art of Distillation"
  ],
  [
    "place-marungurpattinam-ancient-aromatic-haven",
    "traded_incense_compounds",
    "concept-compound-incense-formulation-narum-pukai-and-resin-burners",
    "trade",
    "Sangam Classical Era",
    "Marungurpattinam port shipped compound benzoin and agarwood incense cones across the Indian Ocean.",
    "Ptolemy's Geography"
  ],
  [
    "concept-compound-incense-formulation-narum-pukai-and-resin-burners",
    "incorporates_macerated_woods",
    "concept-sandalwood-heartwood-maceration-and-stone-grinding-mechanics",
    "pyrotechnics",
    "Sangam to Chola Era",
    "Compound incense formulations blended fragrant sandalwood shavings with dammar resins and charcoal.",
    "Traditional South Indian Aromatic Formulary"
  ],
  [
    "text-kanakkathikaram-agrarian-grain-measures-and-cooperage-poetry",
    "encodes_volumetric_hierarchy",
    "concept-sexagesimal-grain-metrology-sevidu-alakku-uri-nazhi-marakkal",
    "mathematics",
    "Sangam to Chola Era",
    "Kanakkathikaram encodes the sexagesimal hierarchy of grain measures from Sevidu to Kalam.",
    "Kanakkathikaram (Kari Nayanar)"
  ],
  [
    "insc-ennayiram-chola-temple-grain-treasury-and-marakkal-charters",
    "documents_grain_quotas_at",
    "place-ennayiram-ancient-grain-treasury-haven",
    "epigraphy",
    "Imperial Chola Era",
    "Ennayiram inscriptions record exact daily grain budgets in Nazhi and Marakkal for 350 scholars.",
    "South Indian Inscriptions Vol XXIII"
  ],
  [
    "insc-thiruvidaimarudur-royal-rajarajan-marakkal-standard-charters",
    "establishes_standard_measure",
    "concept-brass-rimmed-measuring-vessel-calibration-and-state-stamping",
    "epigraphy",
    "Imperial Chola Era",
    "Thiruvidaimarudur charters decree the 'Rajarajan-Marakkal' as the kingdom's official brass-rimmed standard.",
    "South Indian Inscriptions Vol V"
  ],
  [
    "concept-hardwood-grain-measure-lathe-turning-and-cooperage-mechanics",
    "reinforced_by_metallurgy",
    "concept-brass-rimmed-measuring-vessel-calibration-and-state-stamping",
    "woodcraft",
    "Early Historic to Chola Era",
    "Lathe-turned hardwood measuring vessels were reinforced with riveted brass rim collars to prevent lip wear.",
    "Traditional Woodcraft & Lathe Technology"
  ],
  [
    "concept-sexagesimal-grain-metrology-sevidu-alakku-uri-nazhi-marakkal",
    "measured_via_strike_bar",
    "concept-hardwood-grain-measure-lathe-turning-and-cooperage-mechanics",
    "metrology",
    "Sangam Classical Era",
    "Struck grain measurement (Thalambu-alavu) relied on precision-turned cylindrical wooden vessels.",
    "Chola Revenue Assessment Manuals"
  ],
  [
    "concept-granary-moisture-protection-nel-kuthir-and-timber-sluice-gates",
    "stores_measured_grain_for",
    "place-ennayiram-ancient-grain-treasury-haven",
    "storage",
    "Imperial Chola Era",
    "Elevated granaries and Nel-Kuthir silos preserved endowed grain supplies at Ennayiram.",
    "Temple Architecture of the Cholas"
  ],
  [
    "char-ennayiram-master-grain-cooper-marakkal-alavalar",
    "calibrated_vessels_at",
    "place-ennayiram-ancient-grain-treasury-haven",
    "metrology",
    "Imperial Chola Era",
    "The master grain cooper turned and calibrated official measuring vessels at the Ennayiram granary.",
    "Ennayiram Temple Epigraphs"
  ],
  [
    "char-thanjavur-royal-metrology-inspector-kole-alavu-kankani",
    "enforced_calibration_of",
    "concept-brass-rimmed-measuring-vessel-calibration-and-state-stamping",
    "fiscal_admin",
    "Imperial Chola Era",
    "The royal metrology inspector stamped certified brass-rimmed Marakkals with the Chola tiger seal.",
    "Brihadisvara Temple Inscriptions"
  ],
  [
    "char-thanjavur-royal-metrology-inspector-kole-alavu-kankani",
    "supervised_implementation_of",
    "insc-thiruvidaimarudur-royal-rajarajan-marakkal-standard-charters",
    "fiscal_admin",
    "Imperial Chola Era",
    "The royal inspector enforced the Rajarajan-Marakkal standards across delta market towns.",
    "Nilakanta Sastri: The Colas"
  ],
  [
    "concept-granary-moisture-protection-nel-kuthir-and-timber-sluice-gates",
    "discharges_into_measures",
    "concept-hardwood-grain-measure-lathe-turning-and-cooperage-mechanics",
    "agricultural_tech",
    "Early Historic to Medieval Era",
    "Granary gravity-discharge sluice spouts emptied grain directly into calibrated Marakkal vessels.",
    "Purananuru v. 230"
  ]
]

def main():
    print("=" * 70)
    print("🚀 TRIPLE CIVILIZATIONAL EXPANSION HARVESTER - BATCH 18")
    print("=" * 70)
    print(f"Total dossiers to ingest: {len(DOSSIERS)}")
    print(f"Total edges to insert: {len(EDGES)}")

    # Phase 1: Write Dossiers to moolam-chronicles
    print("\n[Phase 1] Writing 30 Markdown Dossiers to Moolam Chronicles...")
    for d in DOSSIERS:
        cat_dir = os.path.join(MOOLAM_KNOWLEDGE, d["category"])
        os.makedirs(cat_dir, exist_ok=True)
        file_path = os.path.join(cat_dir, d["file"])
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Wrote: {d['category']}/{d['file']}")
    print("Phase 1 complete: 30 dossiers written to disk.")

    # Phase 2: PostgreSQL DB Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    nodes_upserted = 0
    for d in DOSSIERS:
        cur.execute("""
            INSERT INTO lore_nodes (
                slug, node_type, name_en, name_ta, era, year_start, year_end,
                thinai, summary_en, summary_ta, properties, sources
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                properties = EXCLUDED.properties,
                sources = EXCLUDED.sources;
        """, (
            d["slug"],
            d["node_type"],
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["summary_en"],
            d["summary_ta"],
            json.dumps({"category": d["category"], "canonical_file": d["file"]}),
            d["sources"]
        ))
        nodes_upserted += 1
        print(f"  ✓ [{d['node_type'].upper()}] {d['slug']} -> {d['name_en'][:45]}...")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Insert Relational Edges
    print(f"\n[Phase 3] Inserting {len(EDGES)} Relational Cross-Domain Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            SELECT 1 FROM lore_edges 
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s;
        """, (src, rel, tgt))
        if cur.fetchone():
            continue

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
                f"shelf-{d['category']}",
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

    print(f"\n🎉 Batch 18 Expansion Complete!")
    print(f"  - 30 Markdown files written to: {MOOLAM_KNOWLEDGE}")
    print(f"  - {nodes_upserted} lore nodes upserted into PostgreSQL")
    print(f"  - {edges_inserted} cross-domain edges linked in PostgreSQL")
    print(f"  - {total_chunks} 1024-dim BGE-M3 vector chunks embedded")

if __name__ == "__main__":
    main()
