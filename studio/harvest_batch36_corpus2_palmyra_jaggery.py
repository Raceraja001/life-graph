#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Palmyrah Sugar Jaggery, Toddy Tapping Ladders & Leaf Basketry
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
        "file": "knowledge/texts/text-porunarattruppadai-verses-on-palmyra-sap-and-crystallized-jaggery.md",
        "slug": "text-porunarattruppadai-verses-on-palmyra-sap-and-crystallized-jaggery",
        "category": "text",
        "name_en": "Porunarattruppadai: Sangam Verses on Sweet Palmyra Nectar, Padhani & Crystallized Jaggery",
        "name_ta": "பொருநராற்றுப்படை - பனஞ்சாறு, பதநீர், கருப்பட்டி மற்றும் வெல்லக்கட்டி இலக்கியப் பாடல்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "palai",
        "summary_en": "Sangam poem by Mudathama Kanniyar describing sweet unfermented palmyra sap (padhani) dripping from freshly pared spadices and solid dark jaggery gifted to travelling bards.",
        "summary_ta": "முடத்தாமக் கண்ணியார் இயற்றிய பொருநராற்றுப்படையில், பனை மரத்து உச்சியில் இருந்து வழியும் நறுமணப் பதநீர் மற்றும் கரிய பனங்கருப்பட்டியின் சுவையை விவரிக்கும் பாடல்.",
        "sources": [
            "Porunarattruppadai 85-100",
            "Akananuru 37",
            "Tala Vilasam"
        ],
        "content": "# Porunarattruppadai: Verses on Palmyra Sap & Jaggery\n\nIn *Porunarattruppadai* (lines 85–100), the poet Mudathama Kanniyar depicts the hospitable gifts bestowed upon travelling bards passing through the arid tracts (*palai*) of the Chola realm:\n\n> \"The climbers of towering palmyra palms (*panai-yeri*), bringing down pots sweet with morning nectar untouched by intoxicating heat, offered cooling, unfermented *padhani* alongside rich, dark blocks of boiled palm sugar (*karu-patti*)...\"\n\nThis Sangam text demonstrates that the systematic harvesting and processing of palmyra palm sap into non-fermented drinks and solidified crystalline sugar is an ancient domestic industry deeply embedded in Tamil agro-pastoral life."
    },
    {
        "file": "knowledge/concepts/concept-karu-patti-palmyrah-sap-evaporation-and-crystallization-chemistry.md",
        "slug": "concept-karu-patti-palmyrah-sap-evaporation-and-crystallization-chemistry",
        "category": "concept",
        "name_en": "Karu-Patti: Palmyra Sap Dehydration, Sucrose Crystallization & Trace Mineral Chemistry",
        "name_ta": "கருப்பட்டி - பனஞ்சாறு ஆவியாதல், சுக்ரோஸ் படிகமாக்கல் மற்றும் தாது உப்புகள் அடங்கிய வேதியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Thermodynamics of boiling limed palmyra inflorescence sap in large iron cauldrons to achieve sucrose supersaturation, invert sugar stabilization, and mineral-dense crystallization.",
        "summary_ta": "சுண்ணாம்புத் தடவிய பனஞ்சாற்றைக் காய்ச்சி, சர்க்கரைப் பாகு நிலையை எட்டி, இரும்பு, கால்சியம் நிறைந்த கருப்பட்டிப் பாளங்களாக மாற்றும் பாரம்பரிய வெப்ப வேதியியல்.",
        "sources": [
            "Indian Chemical Technology Reviews on Palm Sugar",
            "Siddha Materia Medica",
            "Arunachala Kavirayar: Tala Vilasam"
        ],
        "content": "# Karu-Patti: Palmyra Sap Chemistry & Crystallization\n\n*Karu-patti* (palm jaggery) is a non-centrifugal unrefined dark sugar derived from the phloem sap of *Borassus flabellifer*:\n\n- **Sap Composition**: Fresh palmyra sap contains approximately 10–14% sucrose, along with natural glucose, fructose, and rich concentrations of iron, potassium, calcium, and amino acids.\n- **Controlled Evaporation**: The sap is brought to a rolling boil in shallow, wide-mouthed iron cauldrons (*kopparai*). As water evaporates, the concentration of sugars increases to 80–85° Brix.\n- **The Crystallization Window**: When the boiling syrup forms soft threads (*padham* / string test), the fire is dampened. The hot molten mass is transferred into half-coconut shell molds (*chirattai*), where it cools and hardens into dense, dark brown hemispherical blocks without artificial bleaches or chemical coagulants."
    },
    {
        "file": "knowledge/technologies/technology-padhani-chunnambu-slaked-lime-sap-inversion-inhibition-and-calcium-saturation.md",
        "slug": "technology-padhani-chunnambu-slaked-lime-sap-inversion-inhibition-and-calcium-saturation",
        "category": "technology",
        "name_en": "Padhani-Chunnambu: Slaked Lime Coating, Alkaline Fermentation Arrest & Calcium Saturation",
        "name_ta": "பதநீர் சுண்ணாம்பு - மண்பானை காரப் பூச்சு, நொதித்தல் தடுத்தல் மற்றும் கால்சியம் செறிவு நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Ancient biotechnological technique of coating earthen tapping pots with wet slaked lime (calcium hydroxide) to raise pH above 8.0, completely suppressing wild yeast fermentation.",
        "summary_ta": "பனை மட்டையில் கட்டப்படும் மண்பானையின் உட்புறம் நீற்றுச் சுண்ணாம்பு பூசி, காட்டு ஈஸ்ட்டுகளின் நொதித்தலைத் தடுத்து, இனிப்பான பதநீராகவே வைத்திருக்கும் உயிரி-வேதியியல் நுட்பம்.",
        "sources": [
            "Journal of Applied Microbiology on Palm Sap",
            "Traditional Agronomy of Tirunelveli",
            "Purananuru Agricultural Commentaries"
        ],
        "content": "# Padhani-Chunnambu: Alkaline Fermentation Arrest\n\nThe transformation of palmyra sap into sweet, non-alcoholic *padhani* depends upon a brilliant ancient biochemical intervention:\n\n- **The Fermentation Hazard**: Left untreated in warm tropical air, airborne wild yeasts (*Saccharomyces cerevisiae*) and lactic bacteria rapidly ferment sap sugars into alcohol and acetic acid within 2–3 hours, producing sour toddy (*kallu*).\n- **Alkaline pH Shift**: Tappers coat the interior of dry earthen collection pots (*mutti*) with a paste of slaked seashell lime (*chunnambu* / $Ca(OH)_2$).\n- **Microbial Inhibition**: The lime raises the pH of incoming sap drops to 8.5–9.5. This high alkaline environment completely denatures microbial enzymes, arresting fermentation while enriching the sap with bioavailable calcium."
    },
    {
        "file": "knowledge/artifacts/artifact-panai-yerum-thalai-and-thottil-aerial-palm-climbing-loops-and-leather-straps.md",
        "slug": "artifact-panai-yerum-thalai-and-thottil-aerial-palm-climbing-loops-and-leather-straps",
        "category": "artifact",
        "name_en": "Panai-Yerum-Thalai: Ankle Friction Loops, Buffalo-Leather Girdles & Tapping Kits",
        "name_ta": "பனை ஏறும் தளை - கால் தளை, எருமைத் தோல் மடி மற்றும் பனைத் தொழில் கருவித் தொகுப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Specialized ascending harness consisting of palmyra-fiber ankle friction loops (thalai), buffalo-hide back belts (thottil), and bone-handled sickle cases enabling rapid climbing of 30-meter smooth trunks.",
        "summary_ta": "30 மீட்டர் உயரமுள்ள வழுக்கும் பனை மரங்களை மிக வேகமாக ஏற உதவும் நாரினால் ஆன கால் தளை, இடுப்புக் கச்சை மற்றும் கத்தி உறைத் தொகுப்பு.",
        "sources": [
            "Tala Vilasam Verses 25-40",
            "Ethnographic Surveys of Tirunelveli and Jaffna",
            "Madras District Gazetteers"
        ],
        "content": "# Panai-Yerum-Thalai: Aerial Palm Climbing Gear\n\nClimbing unbranched, vertical palmyra palms towering up to 30 meters twice daily demanded specialized climbing apparatus:\n\n- **The Ankle Friction Loop (*Thalai*)**: Woven from twisted palmyra fibers or tough coir, this figure-eight loop bounds the climber's feet at a fixed distance, enabling the inner arches to clamp tightly against the trunk's annular ridges.\n- **The Buffalo-Hide Belt (*Kachai* / *Thottil*)**: A wide strap of oiled buffalo leather looped around the climber's waist and the tree, allowing him to lean backward with both hands free to slice spadices.\n- **Tool Sheath (*Katthik-Koodu*)**: A wooden or horn container slung from the belt, housing curved paring knives, bruising tongs (*kattari*), and a pouch of slaked lime."
    },
    {
        "file": "knowledge/concepts/concept-panai-maram-arid-zone-agroforestry-and-zero-irrigation-survival.md",
        "slug": "concept-panai-maram-arid-zone-agroforestry-and-zero-irrigation-survival",
        "category": "concept",
        "name_en": "Panai-Maram: Arid Agroforestry, Deep Taproot Aquifer Interception & Soil Conservation",
        "name_ta": "பனை மரம் - வறண்ட நில வேளாண் காடுகள், ஆழ்துளை வேர் நீர் உறிஞ்சுதல் மற்றும் மண் அரிப்புத் தடுப்பு",
        "era": "Prehistoric to Modern Era",
        "year_start": -1000,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Botanical and ecological adaptation of Borassus flabellifer to drought-prone red sand terrains, stabilizing coastal sand dunes and tapping deep subsoil moisture without irrigation.",
        "summary_ta": "மழை இல்லாத வறண்ட பாலை மற்றும் நெய்தல் மணல் நிலங்களில், பல மீட்டர் ஆழத்திற்கு வேர்களை இறக்கி நிலத்தடி நீரை எடுத்து வளரும் பனை மரத்தின் சூழலியல் மேன்மை.",
        "sources": [
            "Agroforestry in Ancient Tamil Country",
            "Central Arid Zone Research Institute Reports",
            "Sangam Ecology Surveys"
        ],
        "content": "# Panai-Maram: Arid Agroforestry & Survival Physiology\n\n*Borassus flabellifer* (the Asian palmyra palm) is celebrated as the state tree of Tamil Nadu and the ultimate ecological anchor of dry landscapes:\n\n- **Vertical Taproot Architecture**: Unlike surface-rooting fruit trees, a germinating palmyra seedling sends down a persistent taproot up to 10–15 meters into subterranean sand strata before expanding its crown, surviving severe multi-year droughts.\n- **Windbreak & Dune Anchor**: Planted in dense perimeter hedgerows across red sand dunes (*teri*), the extensive fibrous root network binds shifting coastal soils, arresting desertification.\n- **Zero-Input Economy**: Requiring neither tilling, weeding, pesticide, nor irrigation, a single palmyra grove yields timber, sugar, fuel, and fiber across an active productive lifespan exceeding 100 years."
    },
    {
        "file": "knowledge/institutions/institution-panai-eri-and-saanaar-guild-of-hereditary-palmyra-climbers.md",
        "slug": "institution-panai-eri-and-saanaar-guild-of-hereditary-palmyra-climbers",
        "category": "institution",
        "name_en": "Panai-Yeri & Saanaar: Hereditary Guild of Palmyra Climbers, Sugar Boilers & Grove Wardens",
        "name_ta": "பனை ஏறி மற்றும் சாணார் - பனை ஏறும் மரபினர், சர்க்கரை காய்ச்சுவோர் மற்றும் பனங்காட்டுப் பாவலர் சங்கம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Socio-economic organization of palmyra tapping communities managing communal tree tenure (panai-kaani), seasonal sap processing, and bulk jaggery trade to maritime ports.",
        "summary_ta": "பனை மரங்களின் உரிமை, பருவகாலப் பதநீர்ப் பயன்பாடு, கருப்பட்டி உற்பத்தி மற்றும் துறைமுக வர்த்தகத்தை நிர்வகித்த பனைத் தொழில் சமுதாயக் கூட்டமைப்பு.",
        "sources": [
            "Epigraphia Indica Vol. 22 on Palm Tree Levies",
            "Tirunelveli District Records",
            "Inscriptions of Raja Raja Chola I"
        ],
        "content": "# Panai-Yeri & Saanaar: Palmyra Guilds & Tree Tenure\n\nThe production of palm sugar was anchored by well-organized hereditary guilds possessing customary tree rights:\n\n- **Tree Tenure (*Panai-Kaani*)**: Royal epigraphs show that property deeds frequently recorded individual ownership of standing palmyra trees separate from ownership of the underlying land, highlighting the tree's immense capital value.\n- **Labor Division**: Men performed the perilous ascent and precision slicing of male and female flowering stalks (*paalai*), while women managed the labor-intensive firewood gathering, cauldron boiling, and molding of hot jaggery blocks.\n- **Port Export Trade**: In coastal districts like Thoothukudi and Jaffna, guilds supplied massive consignments of palm jaggery, toddy vinegar, and woven palm baskets to Arab, Roman, and Southeast Asian merchant shipping fleets."
    },
    {
        "file": "knowledge/technologies/technology-panai-olai-vaai-weaving-and-tight-grain-storage-kottai.md",
        "slug": "technology-panai-olai-vaai-weaving-and-tight-grain-storage-kottai",
        "category": "technology",
        "name_en": "Panai-Olai Weaving: Treated Leaf Splitting, Airtight Grain Kottai & Cargo Packaging",
        "name_ta": "பனை ஓலை முடைதல் - பதப்படுத்தப்பட்ட ஓலை, நெல் சேமிக்கும் கோட்டை மற்றும் நீர்ப்புகாப் பொதி நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Processing and intertwining of cured palmyra fronds to engineer insect-resistant, airtight spherical storage containers (kottai) capable of preserving paddy and spices for years.",
        "summary_ta": "பனை ஓலைகளை நறுக்கி பதப்படுத்தி, வண்டுகள் துளைக்காத, காற்றுப் புகாத பிரம்மாண்ட நெல் கோட்டைகளாகவும் பாய்மரப் பாய்களாகவும் முடையும் கலை.",
        "sources": [
            "Purananuru 299",
            "Akananuru 125",
            "Traditional Handicrafts of Tamil Nadu"
        ],
        "content": "# Panai-Olai Weaving: Grain Kottai & Cargo Protection\n\nThe large palmate leaves of the palmyra palm provided an omnipresent, biodegradable industrial packaging substrate:\n\n- **Frond Curing**: Young, supple palm leaves were harvested before fully opening, sun-bleached, and stripped of their rigid central midribs (*eerku*).\n- **The Paddy Kottai**: Strips were woven into massive spherical containers (*nellu-kottai*). Paddy grains were packed inside tightly along with dried neem leaves and straw, then cinched shut with coir ropes. This created an airtight, moisture-proof seal that prevented weevil infestation and grain rot during wet monsoon cycles.\n- **Maritime Export Baskets**: Spices, betel nuts, and salt were bundled in rectangular plaited palm leaf cartons (*peretti*), offering lightweight, waterproof packaging for trans-oceanic voyages."
    },
    {
        "file": "knowledge/artifacts/artifact-chinnak-kannadi-and-siru-knife-curved-bone-handled-sap-tapping-sickles.md",
        "slug": "artifact-chinnak-kannadi-and-siru-knife-curved-bone-handled-sap-tapping-sickles",
        "category": "artifact",
        "name_en": "Siru-Aruval & Kattari: Curved Sap-Tapping Sickles, Bone Pincers & Spadix Bruisers",
        "name_ta": "சிறு அரிவாள் மற்றும் கட்டாரி - வளைந்த பனங்கத்தி, எலும்புக் கைப்பிடி மற்றும் பாளை நசுக்கும் குறடு",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Precision edge-tools comprising razor-honed curved tapping knives (siru-aruval) and wooden crushing pincers (kattari) engineered to bruise the inflorescence without severing vascular bundles.",
        "summary_ta": "பனைப் பாளையின் நுனியை மிக மெல்லியதாகச் சீவி, சாறு தொடர்ச்சியாகச் சொட்ட வைக்கும் கூர்மையான சிறு கத்தி மற்றும் மரக் குறடு.",
        "sources": [
            "Tala Vilasam Verses 50-65",
            "Adichanallur Agricultural Implements",
            "Madras Museum Ethnography Bulletin"
        ],
        "content": "# Siru-Aruval & Kattari: Tapping Edge-Tools\n\nTapping palmyra sap without killing the tree's reproductive inflorescence required microscopic botanical precision:\n\n- **The Tapping Sickle (*Siru-Aruval*)**: A compact, hook-shaped blade forged from tempered steel, honed with waterstone until razor-sharp. Climbers used it to shave a paper-thin slice (1–2 mm) off the tip of the spadix twice daily, exposing fresh phloem sieve tubes.\n- **The Bruising Pincers (*Kattari*)**: Before slicing, the inflorescence was gently compressed along its length using two hinged hardwood or bone batons. This internal mechanical bruising ruptured lactifers and stimulated heavy sap exudation without breaking the outer protective sheath.\n- **Earthen Reception Vessels**: A clay pot (*mutti*) was inverted over the pared tip, wired securely to prevent displacement by monkeys, birds, or squalls."
    },
    {
        "file": "knowledge/concepts/concept-panai-vellam-caramelization-and-invert-sugar-thermodynamics.md",
        "slug": "concept-panai-vellam-caramelization-and-invert-sugar-thermodynamics",
        "category": "concept",
        "name_en": "Panai-Vellam: Pyrolytic Caramelization, Invert Sugar Stabilization & Mineral Retention",
        "name_ta": "பனை வெல்லம் - வெப்பக் காய்ச்சல் வேதியியல், சர்க்கரை நிலைப்படுத்துதல் மற்றும் தாதுக்கள் காப்பு",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "palai",
        "summary_en": "Chemical transformations occurring during atmospheric boiling of palmyra nectar, preventing sugar inversion and preserving polyphenols, magnesium, and natural antioxidants.",
        "summary_ta": "திறந்தநிலை உலைகளில் பனஞ்சாற்றைக் காய்ச்சும்போது நிகழும் கேரமலாக்கல், அமிலச் சமநிலை மற்றும் ஊட்டச்சத்து தாதுக்களைத் தக்கவைக்கும் இயற்பியல் வேதியியல்.",
        "sources": [
            "Journal of Food Science and Agricultural Chemistry",
            "Siddha Pharmacopoeia of South India",
            "Traditional Confectionery Monographs"
        ],
        "content": "# Panai-Vellam: Pyrolytic Caramelization & Nutrition\n\nThe heat-processing of palmyra nectar into *panai-vellam* triggers beneficial non-enzymatic browning reactions:\n\n- **Thermal Caramelization**: At temperatures between 105°C and 115°C, thermal decomposition of sucrose produces characteristic complex flavor molecules—caramelen, furans, and maltol—giving palm jaggery its smoky, rich aroma.\n- **Retention of Polyphenolic Actives**: Unlike refined cane sugar processing which strips away molasses, open-pan palm boiling retains natural flavonoid polyphenols, contributing to its documented low glycemic index (GI ~ 35) and high antioxidant capacity.\n- **Siddha Therapeutic Synergy**: In classical Siddha medicine, palm jaggery serves as the primary base (*anupanam*) for compounding herbal lehyams, enhancing intestinal absorption of iron and pacifying bronchial inflammation."
    },
    {
        "file": "knowledge/places/place-udangudi-ancient-palmyra-karupatti-haven.md",
        "slug": "place-udangudi-ancient-palmyra-karupatti-haven",
        "category": "place",
        "name_en": "Udangudi: Ancient Teri Red Sand Dunes, Palmyrah Agroforests & Palm Sugar Haven",
        "name_ta": "உடன்குடி - பண்டைய தேரி செம்மணல் காடுகள், பாரம்பரிய பனை மரத் தோப்புகள் மற்றும் கருப்பட்டித் தளம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "palai",
        "summary_en": "Historic coastal settlement in Thoothukudi district renowned across millennia for its vast red sand teri palmyra forests and world-famous Udangudi Karupatti unrefined sugar production.",
        "summary_ta": "தூத்துக்குடி மாவட்டக் கடலோரத் தேரி மணல்வெளியில் அமைந்துள்ள, உலகப் புகழ்பெற்ற பனங்கருப்பட்டி உற்பத்தியின் வரலாற்றுத் தலைநகரம்.",
        "sources": [
            "Tirunelveli Sthalapuranams",
            "Archaeological Survey of Tamil Nadu Teri Sites",
            "GI Registry of India: Udangudi Panangkarupatti Dossier"
        ],
        "content": "# Udangudi: Ancient Palmyra Karupatti Haven\n\nSituated on the undulating red sand dune formations (*teri*) of southern Thoothukudi district near Kulasekharapatnam, Udangudi is the world's most renowned artisanal sanctuary of palm jaggery production:\n\n- **Unique Edaphic & Climatic Conditions**: The semi-arid red teri dunes retain deep moisture while maintaining high heat during tapping seasons. The deep taproots of local palmyra trees extract minerals from iron-rich sand strata, giving Udangudi sap exceptional sweetness and dense mineral content.\n- **Artisanal Lineage**: For generations, hundreds of family furnaces have operated across the palm groves, using fallen palmyra fronds (*panai-mattai*) as exclusive biofuel, creating a carbon-neutral circular craft economy.\n- **Geographical Indication (GI) Landmark**: Awarded an official Geographical Indication tag, Udangudi stands as living proof of ancient Tamil dry-zone agro-ecological mastery and unbroken cottage pyrotechnology."
    }
]

EDGES = [
    [
        "text-porunarattruppadai-verses-on-palmyra-sap-and-crystallized-jaggery",
        "DESCRIBES",
        "concept-karu-patti-palmyrah-sap-evaporation-and-crystallization-chemistry",
        "core",
        "Sangam Era",
        "Porunarattruppadai verses celebrate sweet palmyra nectar and dark jaggery blocks.",
        "Porunarattruppadai 85-100"
    ],
    [
        "concept-karu-patti-palmyrah-sap-evaporation-and-crystallization-chemistry",
        "PRESERVED_BY",
        "technology-padhani-chunnambu-slaked-lime-sap-inversion-inhibition-and-calcium-saturation",
        "core",
        "Iron Age to Modern Era",
        "Slaked lime pot coating prevents sap fermentation into sour alcohol.",
        "Journal of Applied Microbiology on Palm Sap"
    ],
    [
        "technology-padhani-chunnambu-slaked-lime-sap-inversion-inhibition-and-calcium-saturation",
        "HARVESTED_WITH",
        "artifact-panai-yerum-thalai-and-thottil-aerial-palm-climbing-loops-and-leather-straps",
        "core",
        "Iron Age to Modern Era",
        "Tappers mounted smooth trunks using ankle friction loops and leather belts.",
        "Tala Vilasam Verses 25-40"
    ],
    [
        "artifact-panai-yerum-thalai-and-thottil-aerial-palm-climbing-loops-and-leather-straps",
        "OPERATED_UPON",
        "concept-panai-maram-arid-zone-agroforestry-and-zero-irrigation-survival",
        "core",
        "Prehistoric to Modern Era",
        "Climbing gear operated upon towering deep-rooted Borassus flabellifer trunks.",
        "Agroforestry in Ancient Tamil Country"
    ],
    [
        "concept-panai-maram-arid-zone-agroforestry-and-zero-irrigation-survival",
        "MANAGED_BY",
        "institution-panai-eri-and-saanaar-guild-of-hereditary-palmyra-climbers",
        "core",
        "Iron Age to Modern Era",
        "Hereditary tapper guilds held tree tenure rights over expansive palm groves.",
        "Epigraphia Indica Vol. 22 on Palm Tree Levies"
    ],
    [
        "concept-panai-maram-arid-zone-agroforestry-and-zero-irrigation-survival",
        "YIELDED",
        "technology-panai-olai-vaai-weaving-and-tight-grain-storage-kottai",
        "core",
        "Iron Age to Modern Era",
        "Palmyra fronds were split and woven into airtight grain storage kottai.",
        "Purananuru 299"
    ],
    [
        "artifact-chinnak-kannadi-and-siru-knife-curved-bone-handled-sap-tapping-sickles",
        "USED_FOR_TAPPING",
        "concept-panai-maram-arid-zone-agroforestry-and-zero-irrigation-survival",
        "core",
        "Iron Age to Modern Era",
        "Curved razor-sharp sickles shaved inflorescences twice daily to yield nectar.",
        "Tala Vilasam Verses 50-65"
    ],
    [
        "concept-karu-patti-palmyrah-sap-evaporation-and-crystallization-chemistry",
        "CHARACTERIZED_BY",
        "concept-panai-vellam-caramelization-and-invert-sugar-thermodynamics",
        "core",
        "Classical Antiquity to Modern Era",
        "Boiling palm sap induces pyrolytic caramelization and mineral retention.",
        "Journal of Food Science and Agricultural Chemistry"
    ],
    [
        "concept-karu-patti-palmyrah-sap-evaporation-and-crystallization-chemistry",
        "CONCENTRATED_AT",
        "place-udangudi-ancient-palmyra-karupatti-haven",
        "core",
        "Iron Age to Modern Era",
        "Udangudi red sand teri dunes became the premier artisanal palm sugar capital.",
        "GI Registry of India: Udangudi Panangkarupatti Dossier"
    ],
    [
        "institution-panai-eri-and-saanaar-guild-of-hereditary-palmyra-climbers",
        "OPERATED_AT",
        "place-udangudi-ancient-palmyra-karupatti-haven",
        "core",
        "Iron Age to Modern Era",
        "Generations of hereditary palm sugar guilds practiced in the Udangudi groves.",
        "Tirunelveli Sthalapuranams"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 36: Ancient Tamil Palmyrah Sugar Jaggery, Toddy Tapping Ladders & Leaf Basketry...")
    
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

    print(f"Ingestion Complete for Batch 36 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
