#!/usr/bin/env python3
"""
Harvester: Batch 43 - Ancient Tamil Beryl & Quartz Lapidary, Micro-Diamond Drilling & Gemstone Slicing
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
        "slug": "text-patittruppathu-on-kodumanam-gem-city-and-beryl-bead-craft",
        "category": "text",
        "file": "text-patittruppathu-on-kodumanam-gem-city-and-beryl-bead-craft.md",
        "name_en": "Patittruppathu Verses on Kodumanam Gemstone City, Beryl Slicing & Chera Jewelers",
        "name_ta": "கொடுமணம் பட்ட நன்கலம் எனப் புகழும் பதிற்றுப்பத்து மணிவினைஞர் பாடல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Classical Sangam verses celebrating the Chera industrial haven of Kodumanam ('Kodumanam patta nankalam'), where master lapidaries sliced hexagonal aquamarine beryl crystals, polished radiant quartz, and perforated carnelian beads for trans-oceanic trade.",
        "summary_ta": "சேர நாட்டின் புகழ்பெற்ற கொடுமணத்தில் பச்சை நீல வைடூரியக் கற்கள் மற்றும் பளிங்குக் கற்களை அறுத்து மணிகள் செய்த மணிவினைஞர்களைப் போற்றும் பதிற்றுப்பத்துப் பாடல்கள்.",
        "sources": [
            "Patittruppathu 67:1-5",
            "Patittruppathu 74:5-8",
            "Ahananuru 350",
            "Silappadikaram Adaikkalakkathai"
        ],
        "content": "# Patittruppathu on Kodumanam Gemstone Lapidaries\n\nThe Kongu realm under the Chera dynasty was globally celebrated as the premier gemstone polishing center of antiquity:\n\n**Literary Testimonies:**\n- **Patittruppathu (Verse 67)**: Sings of *Kodumanam patta nankalam*—rare, flawless jewels fashioned in Kodumanal by hereditary lapidaries who cut hexagonal green beryl prisms (*vaidooriyam*) and fire-red carnelian.\n- **Patittruppathu (Verse 74)**: Describes the royal gifts of glittering bead necklaces (*kodumani-maalaigal*) bestowed upon bards by Chera king Selvakkadungo Vazhi Athan.\n- **Silappadikaram (Canto 14)**: Details the gem bazaar of Madurai where appraisers evaluated beryl, sapphire, and quartz exported from the Noyyal and Amaravathi river basins."
    },
    {
        "slug": "concept-pegmatite-beryl-mineralogy-aquamarine-cleavage-and-crystal-optics",
        "category": "concept",
        "file": "concept-pegmatite-beryl-mineralogy-aquamarine-cleavage-and-crystal-optics.md",
        "name_en": "Pegmatite Beryl Mineralogy, Cyclosilicate Hexagonal Prisms & Pleochroism Optics",
        "name_ta": "பெக்மடைட் வைடூரியக் கனிமவியல், அறுகோண படிகக் கட்டமைப்பு மற்றும் இருநிற ஒளிவிலகல் இயற்பியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Geological and crystallographic characteristics of South Indian beryl (Be3Al2Si6O18): pegmatitic intrusion veins in charnockite terrain, basal pinacoid cleavage, Mohs hardness of 7.5-8.0, and distinct blue-green dichroism prized by Greco-Roman elites.",
        "summary_ta": "தென்னிந்திய கொடுமணல்-படியூர் பெக்மடைட் பாறைகளில் தோன்றும் வைடூரியக் கனிமக் கட்டமைப்பு: Mohs அளவுகோலில் 7.5-8.0 கடினத்தன்மை, அறுகோண படிகங்கள் மற்றும் உரோமானியர் விரும்பிய நீல-பச்சை ஒளிவிலகல்.",
        "sources": [
            "Geological Survey of India: Gemstones of Tamil Nadu",
            "American Mineralogist: Pegmatite Beryls",
            "Archaeological Mineralogy Reports"
        ],
        "content": "# Pegmatite Beryl Mineralogy & Crystal Optics\n\nThe gemstone deposits of the Coimbatore-Tiruppur pegmatite belt provided the ancient world's finest beryl:\n\n**Crystallographic Profile:**\n- **Chemical Structure**: Cyclosilicate ring mineral ($\\text{Be}_3\\text{Al}_2\\text{Si}_6\\text{O}_{18}$) crystallizing in the hexagonal dihexagonal bipyramidal class ($P6/mcc$).\n- **Color Centers**: Trace ferrous iron ($\\text{Fe}^{2+}$) substituting in structural channels imparts the deep sea-green and aquamarine azure hues celebrated by Roman encyclopedist Pliny the Elder as *beryllus*.\n- **Fracture Mechanics**: Possesses an imperfect basal pinacoid cleavage $\\{0001\\}$ and conchoidal fracture, demanding precise perpendicular sawing along the c-axis to avoid catastrophic crystal shattering."
    },
    {
        "slug": "technology-double-tipped-bow-drill-micro-perforation-and-corundum-slurry",
        "category": "technology",
        "file": "technology-double-tipped-bow-drill-micro-perforation-and-corundum-slurry.md",
        "name_en": "Double-Tipped Bow-Drill Micro-Perforation, Corundum Slurry & Rotary Lapidary Wheels",
        "name_ta": "இரட்டை முனை வில் துளையிடுதல், குருந்தக்கல் அரைவை மற்றும் சுழல் சக்கர மணி பளபளப்பாக்கல்",
        "era": "Iron Age to Early Historic",
        "year_start": -500,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "High-precision lapidary pyrotechnology of Sangam gem carvers: rotary wire-driven bow drills tipped with chert or sapphire micro-points, corundum (kuruntham) abrasive cutting paste, and wooden faceting wheels lubricated with sesame oil.",
        "summary_ta": "சங்க கால மணி தயாரிப்பு நுட்பம்: குருந்தக்கல் அல்லது வைர முனை கொண்ட வில் துரப்பணம் மூலம் மணிகளில் 1 மி.மீ துளையிடுதல், அரைவை நீர்மக் கலவை மற்றும் மர சக்கர பளபளப்பாக்கல்.",
        "sources": [
            "Kodumanal Archaeological Excavation Monographs",
            "Journal of Archaeological Science: Micro-Drilling Technology",
            "Ancient Indian Bead Making Studies"
        ],
        "content": "# Double-Tipped Bow-Drill Micro-Perforation\n\nExcavations at Kodumanal revealed thousands of half-drilled and polished beads illustrating a standardized micro-mechanical sequence:\n\n**Perforation Sequence:**\n1. **Centering Dimple**: The bead blank (carnelian, quartz, or beryl) was secured in a wooden vice, and a tiny central indent was pecked with a hardened steel punch.\n2. **Opposed Dual-Drilling**: Master artisans employed a bow-powered spindle fitted with a tiny micro-drill bit of chert or corundum, drilling halfway through from both poles to meet perfectly in the center, preventing breakout spalling.\n3. **Corundum Abrasive Slurry**: Native corundum powder (*kuruntham*, Mohs 9) mixed with sesame oil acted as the cutting abrasive, achieving smooth, drill-hole walls with diameters down to 0.8 mm.\n4. **Tumble & Lap Polishing**: Perforated beads were strung on copper wires and polished on rotating wooden lap wheels charged with fine tripoli and silt."
    },
    {
        "slug": "artifact-etched-carnelian-beads-quartz-intaglios-and-beryl-prisms",
        "category": "artifact",
        "file": "artifact-etched-carnelian-beads-quartz-intaglios-and-beryl-prisms.md",
        "name_en": "Etched Alkaline Carnelian Beads, Faceted Quartz Intaglios & Beryl Prisms",
        "name_ta": "காரத்தால் பொறிக்கப்பட்ட செவ்வந்திக்கல் மணிகள், பட்டை தீட்டிய பளிங்கு மற்றும் வைடூரியக் குழல்கள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Diagnostic material assemblages recovered from Kodumanal, Porunthal, and Keezhadi: brilliant carnelian beads etched with white alkaline geometric patterns, faceted hexagonal rock crystal quartz, amethyst pendants, and polished beryl beads.",
        "summary_ta": "தொல்பொருள் சான்றுகள்: வெள்ளை காரத்தால் பொறிக்கப்பட்ட செம்மணிகள், பட்டை தீட்டிய படிகக் கற்கள், செவ்வந்திக்கல் பதக்கங்கள் மற்றும் துளையிடப்பட்ட பச்சை வைடூரிய மணிகள்.",
        "sources": [
            "Kodumanal Excavation Reports (TNSDA)",
            "Porunthal Excavation Catalog",
            "Government Museum Chennai Gem Collections"
        ],
        "content": "# Etched Carnelian Beads & Quartz Intaglios\n\nThe gemstone assemblages of Iron Age and Early Historic Tamil sites exhibit consummate lapidary mastery:\n\n**Material Classifications:**\n- **Alkaline Etched Carnelian**: Natural red cryptocrystalline chalcedony painted with a paste of potash plant ash (*soda*) and crushed wild melon (*Citrullus colocynthis*), then fired to diffuse indelible white lithium-silicate patterns (cross-hatching, chevrons, eye motifs) into the stone.\n- **Faceted Rock Crystal (*Palingu*)**: Clear hexagonal quartz prisms faceted into rhombic and octagonal beads with optical-grade flatness.\n- **Perforated Beryl Cylinders**: Pristine translucent aquamarine and emerald-green beryl blanks drilled longitudinally and polished for royal regalia."
    },
    {
        "slug": "concept-thermal-color-enhancement-and-carnelian-iron-oxide-oxidation",
        "category": "concept",
        "file": "concept-thermal-color-enhancement-and-carnelian-iron-oxide-oxidation.md",
        "name_en": "Thermal Color Enhancement, Limonite-to-Hematite Oxidation & Chalcedony Sintering",
        "name_ta": "வெப்ப நிறமேற்ற வேதியியல், லிமோனைட்-ஹேமடைட் ஆக்சிஜனேற்றம் மற்றும் செம்மணி பதப்படுத்துதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Thermal pyrotechnics of gemstone color transformation: heating yellowish-brown chalcedony containing hydrated iron hydroxide (limonite) in pottery vats at 300°C-350°C, dehydrating it into vibrant red microcrystalline hematite (carnelian).",
        "summary_ta": "மஞ்சள் நிறக் கற்களை 350°C வெப்பத்தில் சுட்டு, நீரேறிய இரும்புத் தாதுவை நீரிழக்கச் செய்து ஆழ்ந்த சிவப்பு நிற செம்மணியாக (கார்னிலியன்) மாற்றும் வேதியியல் நுட்பம்.",
        "sources": [
            "Journal of Archaeological Science: Thermal Treatment of Agates",
            "Archaeometry of Indian Gemstones",
            "CSIR Mineral Chemistry"
        ],
        "content": "# Thermal Color Enhancement & Hematite Oxidation\n\nRaw chalcedony and agate nodules harvested from river terraces were rarely naturally blood-red:\n\n**Solid-State Pyrochemical Kinetics:**\n- **Dehydration Reaction**: Raw yellowish-brown nodules contained dispersed micro-inclusions of goethite and limonite ($\\text{FeO(OH)}\\cdot n\\text{H}_2\\text{O}$).\n- **Controlled Pot Baking**: Nodules were packed in clay pots filled with dry sand and sawdust, slowly heated in charcoal trenches to $300^\\circ\\text{C}-380^\\circ\\text{C}$ over 48 hours.\n- **Hematite Transformation**: Thermal dehydration converted yellow ferric hydroxides into anhydrous, sub-micron red hematite ($\\text{Fe}_2\\text{O}_3$), diffusing brilliant crimson color uniformly throughout the micro-porous silica matrix."
    },
    {
        "slug": "institution-mani-vinaiignar-and-akkasalai-guild-of-master-lapidaries",
        "category": "institution",
        "file": "institution-mani-vinaiignar-and-akkasalai-guild-of-master-lapidaries.md",
        "name_en": "Mani-Vinaiignar & Akkasalai Guild: Master Lapidaries, Gem Appraisers & Royal Mint Masters",
        "name_ta": "மணிவினைஞர் மற்றும் அக்கசாலை சபை: மணி செதுக்குவோர், நவரத்தின ஆய்வாளர் மற்றும் நாணயப் பெருமன்றம்",
        "era": "Sangam to Chola Era",
        "year_start": -400,
        "year_end": 1300,
        "thinai": "mullai",
        "summary_en": "The corporate body of Tamil gem-cutters, drillers, and metallurgists (Mani-Vinaiignar / Akkasalai): controlling mineral mining concessions, regulating lapidary export tariffs, testing gem refraction and hardness, and minting royal coinages.",
        "summary_ta": "பண்டைய மணிக் கலைஞர்கள் மற்றும் அரச நாணய சாலைத் தலைவர்களின் வணிகக் கூட்டமைப்பு: சுரங்க உரிமை மேலாண்மை, ரத்தினத் தரம் பிரித்தல் மற்றும் ஏற்றுமதி ஒழுங்குமுறை.",
        "sources": [
            "South Indian Inscriptions: Goldsmith and Lapidary Charters",
            "Sangam Epigraphy of Kodumanal",
            "Indian Historical Review"
        ],
        "content": "# Mani-Vinaiignar & Akkasalai Guild\n\nGemstone cutting was an elite, capital-intensive industry organized under corporate guild administration:\n\n**Guild Functions:**\n- **Mining Concession Rights**: Leased pegmatite dikes and gravel washes from Chera monarchs in exchange for a fixed tribute (*irai*) in premium gem crystals.\n- **Quality Classification (*Mani-Kool*)**: Evaluated gem rough by water clarity (*neer-karai*), color depth, and structural flaws (*maru*), preventing fractured stones from entering royal workshops.\n- **Export Monopoly**: Handled bulk sales to Mediterranean merchant syndicates operating from Muziris and Tyndis, exchanging beryl for Roman silver denarii hoards."
    },
    {
        "slug": "technology-groove-slicing-wire-sawing-and-agate-grinding-slabs",
        "category": "technology",
        "file": "technology-groove-slicing-wire-sawing-and-agate-grinding-slabs.md",
        "name_en": "Iron Wire Lapidary Slicing, Quartz Slurry Abrasion & Agate Burnishing Slabs",
        "name_ta": "இரும்புக் கம்பி மணி அறுப்பு, குவார்ட்ஸ் குழம்பு உராய்வு மற்றும் அகேட் தேய்ப்புப் பலகைகள்",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1400,
        "thinai": "mullai",
        "summary_en": "The mechanical cutting sequence for hard crystalline quartz and beryl nodules: taut iron or copper wire saws reciprocating across stone blocks with wet abrasive corundum slurry, and fine smoothing on flat granite grinding slabs.",
        "summary_ta": "வைடூரியம் மற்றும் பளிங்கு பாறைகளை அறுக்கும் முறை: இரும்புக் கம்பி கொண்டு உராய்வு மணல் நீர்மம் சேர்த்து பாறைகளை சமச்சீரான துண்டுகளாக அறுத்தல் மற்றும் சாணைக்கல் பளபளப்பு.",
        "sources": [
            "Ethnoarchaeology of Indian Lapidary Crafts",
            "Ancient Stone Working Tools",
            "Bulletin of the Archaeological Survey of India"
        ],
        "content": "# Iron Wire Slicing & Agate Grinding Slabs\n\nDividing dense hexagonal beryl prisms without shattering internal crystal planes required friction wire sawing:\n\n**Lapidary Mechanics:**\n1. **Reciprocating Wire Saws**: A thin copper or wrought-iron wire strung on a wooden bow was drawn back and forth across the stone along a scored groove.\n2. **Continuous Slurry Feed**: An apprentice poured a continuous trickle of wet crushed corundum or garnet sand onto the wire; the hard mineral grit became embedded in the softer metal wire, grinding a narrow kerf through the beryl.\n3. **Planing on Granite Slabs**: Sliced blanks were hand-rubbed with water against fine-grained quartz-mica schist slabs to flatten parallel faces before drilling."
    },
    {
        "slug": "place-padiyur-ancient-kongu-beryl-mining-haven",
        "category": "place",
        "file": "place-padiyur-ancient-kongu-beryl-mining-haven.md",
        "name_en": "Padiyur: Ancient Kongu Beryl Mining Haven, Pegmatite Aquamarine Dikes & Roman Trade Pit",
        "name_ta": "படியூர் - பண்டைய கொங்கு நாட்டு வைடூரிய சுரங்கத் தளம், நீலக் கல் நரம்புகள் மற்றும் உரோமானிய வணிகச் சுரங்கம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "World-famous historical gemstone mining village in Tiruppur district, renowned across Greco-Roman antiquity as the supreme source of Indian beryl (aquamarine), featuring ancient open-cast pegmatite pits that supplied gems to the courts of Roman emperors.",
        "summary_ta": "திருப்பூர் மாவட்டத்தில் அமைந்துள்ள உலகப் புகழ்பெற்ற பழங்கால வைடூரியச் சுரங்கம்: பண்டைய உரோமானிய பேரரசர்களுக்கு ஏற்றுமதி செய்யப்பட்ட நீல-பச்சை அக்வாமரைன் கற்களின் பிறப்பிட வரலாற்று தளம்.",
        "sources": [
            "Coimbatore District Gazetteer",
            "Pliny's Natural History Book XXXVII",
            "Geological Survey of India Padiyur Memoirs"
        ],
        "content": "# Padiyur: Ancient Kongu Beryl Mining Haven\n\nPadiyur, situated near Kangayam in the Kongu heartland, is globally celebrated as the ultimate source of Indian beryl:\n\n**Historical Significance:**\n- **Pliny's Testimonial**: Roman natural historian Pliny the Elder wrote in the 1st century CE that the finest beryls in the world were mined in southern India, specifically identifying the inland Kongu mines.\n- **Archaeological Features**: Giant open-cast pits excavated into quartz-feldspar pegmatite veins have yielded thousands of raw beryl crystal fragments and ancient stone-breaker hammers.\n- **Roman Coin Hoards**: Massive hoards of Roman gold aurei and silver denarii discovered in nearby villages (Vellalur, Pollachi) confirm that Padiyur beryl commanded immense bullion payments from the West."
    },
    {
        "slug": "concept-optical-refraction-pleochroism-and-gemstone-appraisal",
        "category": "concept",
        "file": "concept-optical-refraction-pleochroism-and-gemstone-appraisal.md",
        "name_en": "Optical Refraction Indices, Birefringence Dispersion & Tamil Gemological Appraisal",
        "name_ta": "ஒளிவிலகல் எண், இருநிற ஒளிச் சிதறல் மற்றும் பண்டைய தமிழ் நவரத்தின ஆய்வு மரபு",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Classical Tamil principles of gemological valuation (Mani-Nool): identifying refractive indices, testing specific gravity via heavy liquid flotation (plant saps and brine), detecting flaws (maru, kaagam), and grading optical pleochroism under sunlight.",
        "summary_ta": "பண்டைய தமிழ் நவரத்தின நூல்களின் தரம் பிரிக்கும் விதிமுறைகள்: ஒளியின் ஊடுருவல், அடர்த்தி சோதனைகள், குற்றங்களை அறிதல் மற்றும் இயற்கை சூரிய ஒளியில் நிறமாற்றங்களை ஆய்வு செய்தல்.",
        "sources": [
            "Mani-Nool Classical Manuscripts",
            "Indian Gemology Sourcebook",
            "Bulletin of the Madras Museum"
        ],
        "content": "# Optical Refraction & Tamil Gemstone Appraisal\n\nAncient Tamil gem treatises (*Mani-Nool*) codified sophisticated empirical testing procedures for mineral authenticity:\n\n**Appraisal Criteria:**\n- **Flaw Detection (*Mani-Kuttram*)**: Gem appraisers classified flaws into eight fatal categories: *kaagam* (crow-feather black inclusions), *neer-karai* (water stains), *keetru* (internal cleavage fractures), and *pulikkann* (opaque cloudy spots).\n- **Hardness & Friction Resistance**: Real beryls were tested by scratch resistance against glass and quartz, and by thermal conductivity (remaining cold to the touch on the lips).\n- **Optical Play (*Neer-Ottam*)**: Premium gems displayed brilliant internal water (*oli-neer*), reflecting light with pristine clarity without cloudiness."
    },
    {
        "slug": "artifact-rotary-quern-grinders-micro-drill-bits-and-gem-crucibles",
        "category": "artifact",
        "file": "artifact-rotary-quern-grinders-micro-drill-bits-and-gem-crucibles.md",
        "name_en": "Rotary Stone Quern Lapidaries, Jasper Micro-Drill Bits & Bead Polishing Slabs",
        "name_ta": "சுழல் சாணைக்கற்கள், ஜாஸ்பர் நுண்ணிய துரப்பண முனைகள் மற்றும் மணி தேய்ப்புப் பலகைகள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Excavated tool assemblage of the Kodumanal lapidary workshops: cylindrical stone grinding querns, miniature chipped jasper and chert drill bits, grooved sandstone bead polishers, and quartz crystal storage jars.",
        "summary_ta": "கொடுமணல் அகழ்வாய்வில் கிடைத்த மணிவினைஞர் கருவிகள்: உருளை வடிவ சாணைக்கற்கள், நுண் துளை போடும் ஜாஸ்பர் முனைகள், பள்ளங்கள் கொண்ட மணி தேய்ப்பு பலகைகள்.",
        "sources": [
            "Kodumanal Archaeological Excavation Memoirs",
            "Tamil Nadu State Archaeology Department",
            "Indian Archaeology - A Review"
        ],
        "content": "# Rotary Quern Lapidaries & Micro-Drill Bits\n\nArchaeological trenches at Kodumanal revealed the physical workshops of gem-cutters:\n\n**Tool Inventory:**\n- **Micro-Drill Tips**: Tiny flakes of microcrystalline jasper and chert (2–3 mm length) with carefully retouched drills showing rotational polish wear under scanning electron microscopy.\n- **Grooved Polishing Slabs**: Flat sandstone blocks incised with parallel semi-circular grooves matching the diameters of standard beads, allowing dozen beads to be polished simultaneously by rubbing with abrasive slurries.\n- **Sort Trays & Storage Terracotta**: Small red-ware pots filled with sorted rough crystals of amethyst, smoky quartz, and beryl awaiting cutting."
    }
]

EDGES = [
    [
        "text-patittruppathu-on-kodumanam-gem-city-and-beryl-bead-craft",
        "celebrates",
        "technology-double-tipped-bow-drill-micro-perforation-and-corundum-slurry",
        "material_culture",
        "Sangam Era",
        "Patittruppathu verses celebrate the high lapidary art of drilling and shaping beryl jewels in Kodumanam.",
        "Patittruppathu 67"
    ],
    [
        "concept-pegmatite-beryl-mineralogy-aquamarine-cleavage-and-crystal-optics",
        "supplies",
        "technology-double-tipped-bow-drill-micro-perforation-and-corundum-slurry",
        "material_culture",
        "Iron Age to Modern Era",
        "Pegmatite beryl crystal chemistry dictates the use of corundum abrasive slurries and dual-drilling.",
        "Geological Survey of India"
    ],
    [
        "technology-double-tipped-bow-drill-micro-perforation-and-corundum-slurry",
        "fabricates",
        "artifact-etched-carnelian-beads-quartz-intaglios-and-beryl-prisms",
        "material_culture",
        "Iron Age to Early Historic",
        "Micro-drilling, faceting, and etching produce carnelian beads, beryl prisms, and quartz intaglios.",
        "Kodumanal Excavations"
    ],
    [
        "concept-thermal-color-enhancement-and-carnelian-iron-oxide-oxidation",
        "transforms",
        "artifact-etched-carnelian-beads-quartz-intaglios-and-beryl-prisms",
        "material_culture",
        "Iron Age to Modern Era",
        "Thermal baking oxidizes limonite into red hematite to create bright carnelian beads.",
        "Journal of Archaeological Science"
    ],
    [
        "institution-mani-vinaiignar-and-akkasalai-guild-of-master-lapidaries",
        "manages",
        "place-padiyur-ancient-kongu-beryl-mining-haven",
        "material_culture",
        "Sangam to Chola Era",
        "Lapidary guilds held mining monopolies over beryl extraction and trade at Padiyur.",
        "Coimbatore District Gazetteer"
    ],
    [
        "place-padiyur-ancient-kongu-beryl-mining-haven",
        "hosts",
        "technology-groove-slicing-wire-sawing-and-agate-grinding-slabs",
        "material_culture",
        "Iron Age to Modern Era",
        "Padiyur beryl quarries housed friction wire-sawing and rough-shaping operations.",
        "Pliny Natural History"
    ],
    [
        "technology-groove-slicing-wire-sawing-and-agate-grinding-slabs",
        "shapes",
        "artifact-etched-carnelian-beads-quartz-intaglios-and-beryl-prisms",
        "material_culture",
        "Iron Age to Medieval Era",
        "Wire sawing and flat grinding slabs slice gemstone nodules into uniform preforms.",
        "Stone Working Tools"
    ],
    [
        "concept-optical-refraction-pleochroism-and-gemstone-appraisal",
        "grades",
        "artifact-etched-carnelian-beads-quartz-intaglios-and-beryl-prisms",
        "material_culture",
        "Iron Age to Modern Era",
        "Mani-Nool optical and flaw criteria grade finished beryl and quartz ornaments.",
        "Mani-Nool Manuscripts"
    ],
    [
        "technology-double-tipped-bow-drill-micro-perforation-and-corundum-slurry",
        "utilizes",
        "artifact-rotary-quern-grinders-micro-drill-bits-and-gem-crucibles",
        "material_culture",
        "Iron Age to Early Historic",
        "Bow drilling and polishing operations rely on jasper micro-bits and grooved polishing slabs.",
        "Kodumanal Memoirs"
    ],
    [
        "text-patittruppathu-on-kodumanam-gem-city-and-beryl-bead-craft",
        "documents",
        "place-padiyur-ancient-kongu-beryl-mining-haven",
        "material_culture",
        "Sangam Era",
        "Sangam literature documents the vast gemstone industry centered in the Kongu beryl belt.",
        "Patittruppathu 74"
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
