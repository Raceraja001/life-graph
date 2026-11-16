#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Granite Stone Quarrying, Wedging Pyrotechnics & Monolithic Sculpting
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
        "file": "knowledge/texts/text-mandagapattu-inscription-verses-on-mahendravarman-brickless-rock-cut-shrines.md",
        "slug": "text-mandagapattu-inscription-verses-on-mahendravarman-brickless-rock-cut-shrines",
        "category": "text",
        "name_en": "Mandagapattu Inscription: Royal Epigraph on King Vichitrachitta, Brickless Architecture & Living Rock Shrines",
        "name_ta": "மண்டகப்பட்டு கல்வெட்டு - விசித்திரசித்தன் முதலாம் மகேந்திரவர்மன், செங்கல்லற்ற குடைவரைக் கோயில் மற்றும் கல்வெட்டுப் பாடல்",
        "era": "Early Medieval Era",
        "year_start": 600,
        "year_end": 630,
        "thinai": "mullai",
        "summary_en": "Famous 7th-century CE rock-cut Sanskrit and Grantha epigraph of Pallava King Mahendravarman I at Mandagapattu, boasting the creation of temple shrines without brick, timber, metal, or mortar directly from living granite rock.",
        "summary_ta": "செங்கல், மரம், உலோகம் அல்லது சுண்ணச் சாந்து எதுவும் இல்லாமல், உயிர்ப்புள்ள கருங்கல் மலையைக் குடைந்து பிரம்மன், சிவன், விஷ்ணுவுக்குக் கோயில் அமைத்த விசித்திரசித்தன் மகேந்திரவர்மனின் வரலாற்றுப் பிரகடனம்.",
        "sources": [
            "Epigraphia Indica Vol. IV (Mandagapattu)",
            "Srinivasan: Cave-Temples of the Pallavas",
            "Pallava Epigraphical Corpus"
        ],
        "content": "# Mandagapattu Inscription: Brickless Rock-Cut Architecture\n\nIn the early 7th century CE, the innovative Pallava monarch Mahendravarman I (*Vichitrachitta* / \"the curiously-minded\") engraved an epoch-making inscription into the pillar of a newly scooped granite cave shrine at Mandagapattu:\n\n> *\"This temple dedicated to Brahma, Isvara, and Vishnu was caused to be made by the curious-minded King Vichitrachitta without the employment of bricks, without timber, without metal, and without mortar (*anishtakam adrumam aloham asudham*)...\"*\n\nThis famous inscription marks the dramatic civilizational shift in Tamil architecture: transitioning from perishable organic materials (teak rafters, mud mortar, burned bricks) to immutable, hard granite rock (*karungal*). It heralded the golden age of monumental monolithic rock-cut cave temples and freestanding monoliths (*rathas*)."
    },
    {
        "file": "knowledge/concepts/concept-kal-thatchu-granite-cleavage-planes-thermal-expansion-and-hydraulic-wedging.md",
        "slug": "concept-kal-thatchu-granite-cleavage-planes-thermal-expansion-and-hydraulic-wedging",
        "category": "concept",
        "name_en": "Kal-Thatchu: Granite Cleavage Planes, Fire-Setting Thermal Spalling & Hydraulic Dry-Wood Wedging",
        "name_ta": "கல் தச்சு - கருங்கல் பிளவுத் தளங்கள், தீயிட்டுப் பிளக்கும் வெப்ப விரிசல் மற்றும் மர ஆப்பு நீரியல் நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Geological and pyrotechnic quarrying physics utilizing natural natural rift and grain cleavage planes, thermal spalling via fire-setting, and swelling dry hardwood wedges soaked in water to split massive granite boulders.",
        "summary_ta": "கருங்கல்லின் இயற்கை இழைத் திசைகளை அறிந்து, நெருப்பிட்டுப் பாறையை விரிசலாக்கி, காய்ந்த மர ஆப்புகளை துளைகளில் அடித்து நீர் ஊற்றிப் பிளக்கும் பண்டைய கல் உடைக்கும் இயற்பியல்.",
        "sources": [
            "Traditional Granite Quarrying Techniques of South India",
            "Journal of Archaeological Science on Rock Splitting",
            "Archaeometallurgy at Mamallapuram"
        ],
        "content": "# Kal-Thatchu: Granite Cleavage & Hydraulic Wedging\n\nSplitting ultra-hard plutonic charnockite granite without modern dynamite required deep practical mastery over geological fracture mechanics:\n\n- **Cleavage Orientation (*Kal-Izhai*)**: Quarrymen (*kal-kothanar*) identified the natural micro-fissure planes—the primary rift (*ottu*) and grain (*kizhi*)—along which quartz and feldspar crystals align.\n- **Fire-Setting Thermal Spalling**: To remove weathered exterior caps, controlled brushwood fires were stoked directly over the rock face until the surface reached over 400°C. Cold water was then dashed over the stone; differential thermal contraction caused the brittle outer layer to spall off in sheets (*thodu-thal*).\n- **Hydraulic Wooden Wedging (*Marap-Pori*)**: Workers cut a line of mortise slots (5 cm deep, 15 cm apart) using tempered chisels. Seasoned, dry wedges of acacia (*karuvelam*) were driven into the holes and flooded with boiling water. As the dry wood fibers swelled with enormous hydraulic expansion pressure (exceeding 30 MPa), a clean, hairline fracture propagated along the designated quarry line."
    },
    {
        "file": "knowledge/technologies/technology-kudavarai-monolithic-cave-excavation-trenching-and-relief-sculpting.md",
        "slug": "technology-kudavarai-monolithic-cave-excavation-trenching-and-relief-sculpting",
        "category": "technology",
        "name_en": "Kudavarai: Subtractive Monolithic Excavation, Perimeter Trenching & Bas-Relief Carving",
        "name_ta": "குடைவரை - இறங்குமுகக் கல் குடைதல், எல்லைக் கால்வாய் வெட்டுதல் மற்றும் புடைப்புச் சிற்பக் கலை",
        "era": "Early Medieval Era",
        "year_start": 600,
        "year_end": 900,
        "thinai": "mullai",
        "summary_en": "Subtractive monolithic quarrying methodology scooping pillared mandapas and interior sanctums out of living cliff faces by grid trenching, boulder block detachment, and multi-stage relief chasing.",
        "summary_ta": "செங்குத்துப் பாறை முகப்பில் கட்டங்கட்டமாக ஆழமான பள்ளங்களை வெட்டி, பாறைக் கட்டிகளை உடைத்தெடுத்து, தூண்களும் கருவறையும் கொண்ட மண்டபங்களை உருவாக்கும் முறை.",
        "sources": [
            "Srinivasan: The Cave Temples of the Pallavas",
            "Indian Archaeological Review: Mamallapuram Survey",
            "Mahabalipuram Monolith Engineering Reports"
        ],
        "content": "# Kudavarai: Subtractive Cave Temple Excavation\n\nCreating a rock-cut shrine was a purely subtractive sculptural discipline where errors could never be repaired:\n\n- **Perimeter Trench Grid**: Sculptors painted the front facade with red ochre gridlines. Using narrow chisels, stonecutters chiseled deep vertical and horizontal trenches (7–10 cm wide) around 30-centimeter cubes of rock.\n- **Lateral Cleaving**: Iron drifts were driven into the base of the isolated stone cubes, popping them out cleanly to hollow the cave interior layer by layer from the ceiling downwards (*muga-thalam*).\n- **In-Situ Pillar Retention**: Massive stone columns, sanctum cell walls (*garbhagriha*), and life-sized guardian dwarapalas were left intact from the parent rock, emerging directly from the mountain without seams."
    },
    {
        "file": "knowledge/artifacts/artifact-uluki-and-sitra-hardened-steel-chisels-iron-drifts-and-measuring-plumb-lines.md",
        "slug": "artifact-uluki-and-sitra-hardened-steel-chisels-iron-drifts-and-measuring-plumb-lines",
        "category": "artifact",
        "name_en": "Uluki & Sitra: Crucible Wootz Steel Stone Chisels, Hardened Drifts & Plumb Bobs",
        "name_ta": "உளுகி மற்றும் சித்ர உளி - உருக்கு எஃகு கல் உளிகள், பாறை ஆப்புகள் மற்றும் தூக்கு நூல் அளவைகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "High-carbon wootz steel edge-tools tempered for granite impact, including flat chisels (sitra-uli), diamond-point punches (kundu-uli), iron drifts, and beeswax-weighted plumb lines (thookku-nool).",
        "summary_ta": "கடினமான கருங்கல்லை வெட்ட உதவும் உயர்-கார்பன் உருக்கு எஃகு உளிகள், பாறை உடைக்கும் கனரக ஆப்புகள் மற்றும் செங்குத்து மட்டம் அறியும் தூக்கு நூல்.",
        "sources": [
            "Adichanallur and Kodumanal Iron Metallurgy Reports",
            "Traditional Stonemason Tool Kits of Mahabalipuram",
            "Keezhadi Archaeological Iron Implements"
        ],
        "content": "# Uluki & Sitra: Granite Chisels & Masonry Instruments\n\nGranite masonry required edge-tools manufactured from South India's celebrated crucible steel (*wootz*):\n\n- **Point Punches (*Kundu-Uli*)**: Heavy diamond-pointed chisels forged with reinforced conical tips, struck with 2-kg iron sledges (*sathiram*) to shatter the tough crystalline surface into dust.\n- **Flat Dressing Chisels (*Sitra-Uli*)**: Broad, bevel-edged carbon steel chisels used for leveling wavy rock surfaces into silky architectural planes.\n- **Wootz Heat-Treatment**: The cutting edges were quench-hardened in oil and tempered to Rockwell C 58–60, resisting deformation against quartz crystals (Mohs hardness 7).\n- **Plumb Bobs & Squares (*Thookku-Nool & Moolai-Mattam*)**: Cotton cords suspended with lead or bronze weights verified plumb lines, ensuring cave ceilings and columns remained strictly perpendicular to true gravitational vertical."
    },
    {
        "file": "knowledge/concepts/concept-sirpa-sastra-talamana-iconographic-proportions-and-granite-crystallography.md",
        "slug": "concept-sirpa-sastra-talamana-iconographic-proportions-and-granite-crystallography",
        "category": "concept",
        "name_en": "Talamana Metrology: Canonical Anthropometric Proportions, Angula Units & Granite Aesthetics",
        "name_ta": "தாளமான அளவியல் - சிற்ப சாஸ்திர அங்க விகிதங்கள், விரல் அங்ங்குலம் மற்றும் கருங்கல் அழகியல்",
        "era": "Classical Antiquity to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "marutham",
        "summary_en": "Iconometric and proportional canons (Talamana) governing Hindu stone sculpture, dividing deity figures into standardized modular ratios (Dasa-Tala / 120 angulas) to achieve monumental visual harmony.",
        "summary_ta": "மனித மற்றும் தெய்வ வடிவங்களை பத்தளவு (தச தாளம்), ஒன்பதளவு (நவ தாளம்) போன்ற துல்லியமான அங்க கணக்கீடுகளால் செதுக்கும் சிற்ப சாஸ்திர அளவியல் விதிமுறைகள்.",
        "sources": [
            "Kasyapa Silpa Sastra",
            "Mayamata Vastu Treatise",
            "Sivaramamurti: South Indian Bronzes and Sculptures"
        ],
        "content": "# Talamana Metrology: Canonical Sculptural Proportions\n\nAncient stone carvers operated within a mathematical grid of proportions designed to induce spiritual visual equilibrium:\n\n- **The Angula Base Unit**: Measurements were derived from the *angula* (roughly the width of the middle joint of the master's finger) or a proportional fraction of the total designated height.\n- **The Dasa-Tala Canon (120 Angulas)**: Reserved for supreme deities (Siva, Vishnu), dividing the standing figure into 10 harmonious heads: 12 angulas from crown to hairline, 12 from hairline to throat, 24 from throat to navel, 24 from navel to genitals, 24 for thighs, and 24 for shins.\n- **Optical Fore-Shortening Compensation**: For monolithic rock-cut bas-reliefs towering over viewers (such as the Descent of the Ganges), sculptors intentionally elongated upper torsos and inclined facial planes forward, counteracting perspective foreshortening from the ground level."
    },
    {
        "file": "knowledge/institutions/institution-kal-thatchar-corporation-of-pallava-master-sculptors-and-quarrymen.md",
        "slug": "institution-kal-thatchar-corporation-of-pallava-master-sculptors-and-quarrymen",
        "category": "institution",
        "name_en": "Kal-Thatchar: Corporation of Royal Pallava Stonemasons, Quarrymen & Master Sculptors",
        "name_ta": "கல் தச்சர் - பல்லவர் கால அரச கல் தச்சர்கள், சிற்பிகள் அவை மற்றும் பாறை உடைப்போர் சங்கம்",
        "era": "Early Medieval Era",
        "year_start": 600,
        "year_end": 900,
        "thinai": "neithal",
        "summary_en": "State-sponsored royal corporation of quarry masters, stone dressers, and master sculptors (sthapathis) employed by the Pallava kings to carve monolithic monuments and dynastic cave complexes.",
        "summary_ta": "மண்டகப்பட்டு, மாமல்லபுரம், காஞ்சிபுரம் ஆகிய இடங்களில் மாபெரும் பாறைச் சிற்பங்களையும் குடைவரைகளையும் உருவாக்கிய பல்லவப் பேரரசின் அரச சிற்பிகள் அவை.",
        "sources": [
            "Mamallapuram Pillar Inscriptions of Narasimhavarman I",
            "Kanchi Kailasanatha Temple Epigraphs",
            "Minakshi: Administration and Social Life under the Pallavas"
        ],
        "content": "# Kal-Thatchar: Pallava Guild of Master Stonemasons\n\nThe rock-cut revolutions of the 7th and 8th centuries were engineered by highly organized artisan guilds:\n\n- **Division of Quarry Labor**: Guilds separated specialists into *Kallu-Vettuvor* (heavy quarry breakers), *Sirpa-Kothanar* (rough dressers), and *Perun-Thatchar* (master design sthapathis who engraved sacred iconographies).\n- **Royal Titles & Honours**: Pallava monarchs honored chief architects with high civil titles like *Tribhuvana-Acharya* (\"master builder of the three worlds\") and granted hereditary tax-free land endowments (*sirpa-kaani*).\n- **Signature Epigraphs**: Master sculptors inscribed their individual names and creative guild marks beneath temple bas-reliefs, celebrating their technical triumphs over immovable bedrock."
    },
    {
        "file": "knowledge/technologies/technology-ratha-monolith-entablature-cantilever-and-bas-relief-undercutting.md",
        "slug": "technology-ratha-monolith-entablature-cantilever-and-bas-relief-undercutting",
        "category": "technology",
        "name_en": "Pancha-Ratha Monoliths: Freestanding Monolith Carving, Entablature Cantilever & Open-Air Bas-Reliefs",
        "name_ta": "பஞ்ச ரதங்கள் - ஒற்றைக்கல் தேர் செதுக்குதல், கொடுங்கை வளைவு மற்றும் திறந்தவெளிப் புடைப்புச் சிற்ப நுட்பம்",
        "era": "Early Medieval Era",
        "year_start": 630,
        "year_end": 700,
        "thinai": "neithal",
        "summary_en": "Monumental subtractive sculpture carving freestanding full-scale architectural temples (Pancha Rathas) directly downward out of isolated whaleback granite outcrops without joints or mortar.",
        "summary_ta": "தனியாக நின்ற மாபெரும் கருங்கல் பாறைகளை மேலிருந்து கீழாகச் செதுக்கி, முழுமையான கோயில் தேர்களாகவும் திறந்தவெளி சிற்பக் காட்சிகளாகவும் மாற்றிய வியத்தகு கட்டடக் கலை.",
        "sources": [
            "Archaeological Survey of India Monograph: Mahabalipuram",
            "Lockwood: Mamallapuram Monuments",
            "Sivaramamurti: Mahabalipuram"
        ],
        "content": "# Pancha-Ratha Monoliths: Top-Down Monolithic Carving\n\nThe five monolithic rathas of Mamallapuram represent an extraordinary feat in stone sculpting engineering:\n\n- **Top-Down Excavation Strategy**: Rather than building upward from a stone foundation, sculptors climbed to the apex of natural charnockite whaleback boulders (*kal-paarai*). They shaped the finial (*stupika*), curved eaves (*koodu*), and barrel-vaulted roof (*sala*) first, working systematically downward toward the floor plinth (*upapitha*).\n- **Elimination of Scaffolding Collapse**: Carving from the top down meant stonecutters stood on the unfinished parent rock beneath them, eliminating the need for fragile scaffolding to carry heavy hammering loads.\n- **The Great Penance Bas-Relief**: On a natural split-cliff 30 meters long and 15 meters high, sculptors carved the *Descent of the Ganges* (Arjuna's Penance), integrating the central natural geological fissure into a roaring water cascade populated by over 100 life-sized sculpted gods, ascetics, and elephants."
    },
    {
        "file": "knowledge/artifacts/artifact-kal-thookki-heavy-timber-shear-legs-bronze-pulleys-and-stone-slings.md",
        "slug": "artifact-kal-thookki-heavy-timber-shear-legs-bronze-pulleys-and-stone-slings",
        "category": "artifact",
        "name_en": "Kal-Thookki & Thandavalam: Heavy Timber Shear-Legs, Bronze Pulley Blocks & Roller Slings",
        "name_ta": "கல் தூக்கி மற்றும் தண்டவாளம் - கனரக மர முக்காலித் தூக்கி, வெண்கல உருளை மற்றும் கல் நகர்த்தும் உருளைத் தடி",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1400,
        "thinai": "kurinji",
        "summary_en": "Monumental stone handling apparatus comprising heavy teak shear-leg derricks (kal-thookki), compound bronze pulleys, coir rope tackles, and lubricated hardwood rollers (thadi) to haul 50-ton blocks.",
        "summary_ta": "பல்லாயிரக்கணக்கான கிலோ எடையுள்ள கருங்கல் பாறைகளைத் தூக்கி வைக்க உதவும் முக்காலி மரத் தூக்கிகள், வெண்கலக் கப்பியமைப்புகள் மற்றும் எண்ணெய்ப் பூசிய மர உருளைகள்.",
        "sources": [
            "Brihadisvara Temple Stone Handling Inscriptions",
            "Traditional Engineering Machinery of South India",
            "National Institute of Advanced Studies Monographs on Chola Engineering"
        ],
        "content": "# Kal-Thookki & Thandavalam: Heavy Stone Lifting Machinery\n\nTransporting and hoisting monumental granite monoliths demanded sophisticated mechanical lifting tackle:\n\n- **The Timber Shear-Leg Derrick (*Kal-Thookki*)**: Two massive seasoned teak trunks joined at the apex with forged iron pivots, stayed with four guy ropes, supporting a compound tackle block.\n- **Compound Bronze Pulleys (*Kappi*)**: Double- and triple-sheave pulley blocks cast from durable phosphor bronze reduced the mechanical pulling force needed to hoist 10-ton lintels by up to 75%.\n- **Hardwood Rollers & Earthen Ramps**: To transport quarried megaliths over land, stonecutters laid smooth parallel timber tracks (*thandavalam*) lubricated with animal fat and castor oil. Massive boulders lashed in coir slings rolled smoothly across rows of rotating cylindrical ironwood logs."
    },
    {
        "file": "knowledge/concepts/concept-charnockite-granite-weathering-resistance-and-salt-spray-petrology.md",
        "slug": "concept-charnockite-granite-weathering-resistance-and-salt-spray-petrology",
        "category": "concept",
        "name_en": "Charnockite Petrology: Orthopyroxene-Granite Durability, Quartz Interlocking & Marine Salt Weathering",
        "name_ta": "சார்னோகைட் பாறையியல் - ஹைப்பர்ஸ்தீன் கருங்கல் உறுதி, குவார்ட்ஸ் படிகப் பிணைப்பு மற்றும் கடல் உப்பு அரிப்பு எதிர்ப்பு",
        "era": "Prehistoric to Modern Era",
        "year_start": -1000,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Geological petrology and mineralogical structure of South Indian charnockite series granite, possessing high compressive strength (200+ MPa) and exceptional resistance to marine salt spray crystallization.",
        "summary_ta": "மாமல்லபுரக் கடற்கரையில் 1,300 ஆண்டுகளாக ஓயாத கடல் அலைகளையும் உப்புக்காற்றையும் எதிர்கொண்டு நிலைத்து நிற்கும் சார்னோகைட் கருங்கல்லின் தனித்துவமான கனிமக் கட்டமைப்பு.",
        "sources": [
            "Geological Survey of India Memoirs on Charnockites",
            "Studies in Conservation: Shore Temple Granite Weathering",
            "Petrology of South Indian Granulites"
        ],
        "content": "# Charnockite Petrology: Granite Durability & Salt Weathering\n\nThe Pallava monuments have endured 1,300 years of pounding surf and airborne salt mist thanks to the exceptional petrological properties of charnockite:\n\n- **Mineralogical Composition**: South Indian charnockite is a hypersthene-bearing granulite granite formed under extreme metamorphic temperatures (>800°C) and pressures deep in the Earth's crust, composed of tightly interlocking quartz, plagioclase, and pyroxene crystals.\n- **Zero Porosity**: The rock exhibits a water absorption rate under 0.2%, preventing saltwater from penetrating deep into interior pores where sub-florescence crystallization could cleave stone faces.\n- **Salt Spray Haloclasty Resistance**: While softer sandstones and limestones crumble within decades along ocean shores, the hardness of charnockite (compressive strength exceeding 200–250 MPa) enabled the coastal Shore Temple to preserve fine chisel reliefs through 13 centuries of ocean typhoons."
    },
    {
        "file": "knowledge/places/place-mamallapuram-ancient-pallava-granite-sculpting-haven.md",
        "slug": "place-mamallapuram-ancient-pallava-granite-sculpting-haven",
        "category": "place",
        "name_en": "Mamallapuram: Ancient Pallava Ocean Citadel, Living Rock Sculpting Haven & UNESCO Landmark",
        "name_ta": "மாமல்லபுரம் - பண்டைய பல்லவர் துறைமுகம், குடைவரைக் கோயில்கள், ஒற்றைக்கல் ரதங்கள் மற்றும் சிற்பக்கலைத் தளம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 1900,
        "thinai": "neithal",
        "summary_en": "The premier 7th-century coastal seaport and royal sculpting sanctuary of the Pallava Empire in Chengalpattu district, celebrated globally for its monolithic rathas, cave temples, and the Shore Temple.",
        "summary_ta": "மகாபலிபுரம் - பல்லவ மன்னன் மாமல்லன் நரசிம்மவர்மனின் துறைமுக நகரம், உலகப் புகழ்பெற்ற யுனெஸ்கோ பாரம்பரியச் சின்னமான திறந்தவெளி சிற்பக் கலைக்கூடம்.",
        "sources": [
            "UNESCO World Heritage Monument Dossier: Mahabalipuram",
            "ASI Architectural Survey Reports",
            "Epigraphia Indica Vol. X on Pallava Port Charters"
        ],
        "content": "# Mamallapuram: Ancient Pallava Granite Sculpting Haven\n\nLocated along the wave-swept Coromandel coast in Chengalpattu district, Mamallapuram (Mahabalipuram) stands as humanity's premier open-air gallery of monolithic stone sculpture:\n\n- **Imperial Seaport of Mamalla**: Named after the great wrestling monarch Narasimhavarman I (*Mamallan* / \"the great wrestler\"), the port was the departure terminal for Pallava naval expeditions to Sri Lanka and cultural embassies to Southeast Asia.\n- **The Crucible of Dravidian Stone Architecture**: Here, in a single breathtaking landscape, one witnesses every transitional stage of Dravidian sacred architecture: natural caves transformed into scooped mandapas, freestanding whaleback rocks sculpted into monolithic rathas, and finally assembled structural masonry temples (the Shore Temple).\n- **Living Stonemason Heritage**: To this day, Mamallapuram remains India's foremost center for traditional granite stone sculpture, with thousands of hereditary sculptors continuing unbroken sculptural traditions recognized by UNESCO."
    }
]

EDGES = [
    [
        "text-mandagapattu-inscription-verses-on-mahendravarman-brickless-rock-cut-shrines",
        "DOCUMENTS",
        "technology-kudavarai-monolithic-cave-excavation-trenching-and-relief-sculpting",
        "core",
        "Early Medieval Era",
        "Mandagapattu inscription proclaims the creation of rock-cut shrines without brick or timber.",
        "Epigraphia Indica Vol. IV (Mandagapattu)"
    ],
    [
        "technology-kudavarai-monolithic-cave-excavation-trenching-and-relief-sculpting",
        "UTILIZES",
        "concept-kal-thatchu-granite-cleavage-planes-thermal-expansion-and-hydraulic-wedging",
        "core",
        "Iron Age to Modern Era",
        "Rock-cut excavations utilized fire-spalling and swelling wooden wedges along natural cleavage planes.",
        "Traditional Granite Quarrying Techniques of South India"
    ],
    [
        "concept-kal-thatchu-granite-cleavage-planes-thermal-expansion-and-hydraulic-wedging",
        "EXECUTED_WITH",
        "artifact-uluki-and-sitra-hardened-steel-chisels-iron-drifts-and-measuring-plumb-lines",
        "core",
        "Iron Age to Modern Era",
        "Wootz steel diamond-point punches and flat chisels breached hard charnockite granite.",
        "Traditional Stonemason Tool Kits of Mahabalipuram"
    ],
    [
        "technology-kudavarai-monolithic-cave-excavation-trenching-and-relief-sculpting",
        "GOVERNED_BY",
        "concept-sirpa-sastra-talamana-iconographic-proportions-and-granite-crystallography",
        "core",
        "Classical Antiquity to Medieval Era",
        "Deity bas-reliefs adhered strictly to the Dasa-Tala canon of 120 angulas.",
        "Kasyapa Silpa Sastra"
    ],
    [
        "technology-kudavarai-monolithic-cave-excavation-trenching-and-relief-sculpting",
        "ORGANIZED_BY",
        "institution-kal-thatchar-corporation-of-pallava-master-sculptors-and-quarrymen",
        "core",
        "Early Medieval Era",
        "Royal Pallava guilds of sthapathis and stonecutters designed and executed rock shrines.",
        "Mamallapuram Pillar Inscriptions of Narasimhavarman I"
    ],
    [
        "institution-kal-thatchar-corporation-of-pallava-master-sculptors-and-quarrymen",
        "CARVED",
        "technology-ratha-monolith-entablature-cantilever-and-bas-relief-undercutting",
        "core",
        "Early Medieval Era",
        "Guild artisans carved the freestanding Pancha Rathas and Arjuna's Penance bas-relief.",
        "Lockwood: Mamallapuram Monuments"
    ],
    [
        "technology-ratha-monolith-entablature-cantilever-and-bas-relief-undercutting",
        "HOISTED_WITH",
        "artifact-kal-thookki-heavy-timber-shear-legs-bronze-pulleys-and-stone-slings",
        "core",
        "Iron Age to Medieval Era",
        "Heavy timber shear-legs and bronze pulley tackles handled 50-ton granite blocks.",
        "Traditional Engineering Machinery of South India"
    ],
    [
        "technology-ratha-monolith-entablature-cantilever-and-bas-relief-undercutting",
        "RESISTED_BY",
        "concept-charnockite-granite-weathering-resistance-and-salt-spray-petrology",
        "core",
        "Prehistoric to Modern Era",
        "Dense charnockite granulite granite resisted 13 centuries of coastal salt spray haloclasty.",
        "Geological Survey of India Memoirs on Charnockites"
    ],
    [
        "technology-ratha-monolith-entablature-cantilever-and-bas-relief-undercutting",
        "CONCENTRATED_AT",
        "place-mamallapuram-ancient-pallava-granite-sculpting-haven",
        "core",
        "Early Medieval to Modern Era",
        "Mamallapuram served as the premier Pallava imperial rock-cut sculpting sanctuary.",
        "UNESCO World Heritage Monument Dossier: Mahabalipuram"
    ],
    [
        "institution-kal-thatchar-corporation-of-pallava-master-sculptors-and-quarrymen",
        "HEADQUARTERED_AT",
        "place-mamallapuram-ancient-pallava-granite-sculpting-haven",
        "core",
        "Early Medieval to Modern Era",
        "Generations of master stonemasons maintain an unbroken lineage in Mamallapuram.",
        "ASI Architectural Survey Reports"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 38: Ancient Tamil Granite Stone Quarrying, Wedging Pyrotechnics & Monolithic Sculpting...")
    
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

    print(f"Ingestion Complete for Batch 38 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
