#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Bronze Icon Lost-Wax Casting & Cire-Perdue Metallurgy
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
        "file": "knowledge/texts/text-karanagama-and-silpa-sastras-on-lost-wax-cire-perdue-bronze-iconography.md",
        "slug": "text-karanagama-and-silpa-sastras-on-lost-wax-cire-perdue-bronze-iconography",
        "category": "text",
        "name_en": "Karanagama: Classical Agamic Verses on Cire-Perdue Lost-Wax Bronze Casting & Devalaya Icons",
        "name_ta": "காரணாகமம் - மதுச்சிட்ட முறை, மெழுகு வார்ப்பு வெண்கலச் சிலைகள் மற்றும் சிற்ப சாஸ்திர பாடல்",
        "era": "Early Medieval Era",
        "year_start": 700,
        "year_end": 1000,
        "thinai": "marutham",
        "summary_en": "Classical liturgical and sculptural verses from the Karanagama and Silpa-Sastras detailing the spiritual consecration, beeswax armature formulation, and bronze alloy casting of temple processional deities (utsava murthis).",
        "summary_ta": "காரணாகமம் மற்றும் சிற்ப சாஸ்திரங்களில், தேன்மெழுகு மாதிரியை உருவாக்கி, சுடுமண் பூசி, மெழுகை உருக்கி அகற்றி, உருகிய வெண்கலத்தை ஊற்றி வடிக்கப்படும் மதுச்சிட்ட முறையை விவரிக்கும் நூல்.",
        "sources": [
            "Karanagama Kriya Pada",
            "Silpa Prakasha",
            "Sarasvati Chitrakarma Sastra"
        ],
        "content": "# Karanagama: Agamic Verses on Lost-Wax Bronze Casting\n\nThe *Karanagama* (one of the 28 primary Saiva Agamas) provides foundational liturgical and metallurgical instructions for casting processional metal icons (*utsava-murthis*):\n\n> *\"The master sthapathi, having cleansed his mind and body, shall sculpt the divine form in pure bee's wax blended with tree resin... Wrapping the wax model in smooth river silt and heating the crucible (*kollai*) to white-hot fire, he shall pour the noble bronze alloy in an unbroken stream into the mold cavity left by the fleeing wax...\"*\n\nThis sacred text codifies the lost-wax method (*madhuchchishtam* / *cire perdue*). In South Indian tradition, metal icons were not merely decorative sculptures; they were conceived as living thermodynamic conductors of divine cosmic vibrations."
    },
    {
        "file": "knowledge/concepts/concept-panchaloha-five-metal-sacred-alloy-metallurgy-and-dendritic-microstructure.md",
        "slug": "concept-panchaloha-five-metal-sacred-alloy-metallurgy-and-dendritic-microstructure",
        "category": "concept",
        "name_en": "Panchaloha: Five-Metal Sacred Alloy Metallurgy, Phase Diagrams & Dendritic Solidification",
        "name_ta": "பஞ்சலோகம் - ஐம்பொன் கலப்புலோக வேதியியல், நுண் படிகக் கட்டமைப்பு மற்றும் வெப்ப உறைவு இயற்பியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Metallurgical synthesis of Panchaloha—a sacred quintuple alloy composed predominantly of copper (82-85%), tin/brass (10-12%), zinc, and trace sanctifying additions of gold and silver.",
        "summary_ta": "செம்பு, பித்தளை/வெள்ளீயம், துத்தநாகம் மற்றும் நுண்ணிய தங்கம், வெள்ளி ஆகிய ஐந்து உலோகங்களை குறிப்பிட்ட விகிதத்தில் உருக்கி உருவாக்கப்படும் ஐம்பொன் கலப்புலோக இயற்பியல்.",
        "sources": [
            "Archaeometallurgical Analysis of Chola Bronzes (Reeves)",
            "Srinivasan: Metallurgical Studies on South Indian Metal Icons",
            "Indian Journal of History of Science"
        ],
        "content": "# Panchaloha: Sacred Quintuple Alloy Metallurgy\n\nThe traditional *Panchaloha* alloy combined esoteric ritual symbolism with advanced practical physical metallurgy:\n\n- **Alloy Stoichiometry**: Master casters formulated the base melt with 82–85% pure copper (*chembu*), 10–12% tin/brass (*vengalam*), 2–3% zinc (*nagap-pudi*), with micro-additions of gold (*pon*) and silver (*velli*).\n- **Fluidity & Mold Detail**: Pure copper has a high melting point (1084°C) and sluggish liquid flow. The addition of tin and zinc lowered the liquidus temperature to ~950°C, dramatically lowering surface tension and enabling the molten metal to flood the finest micro-crevices of the mold without freezing prematurely.\n- **Dendritic Grain Refinement**: Slow cooling within thick clay investments promoted interlocking alpha-bronze dendritic crystal growth, imparting high tensile toughness that prevented breakage of slender protruding fingers and flying locks of hair."
    },
    {
        "file": "knowledge/technologies/technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry.md",
        "slug": "technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry",
        "category": "technology",
        "name_en": "Madhuchchishtam: Beeswax Armature Modeling, Kaveri Alluvial Slurry & Investment Core Baking",
        "name_ta": "மதுச்சிட்ட முறை - தேன்மெழுகு சிற்ப உருவாக்கம், காவிரி வண்டல் மண் களி மற்றும் சுடுமண் வார்ப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Cire-perdue lost-wax technology sculpting intricate solid models from refined beeswax and dammar tree resin, followed by multi-layered applications of fine Kaveri riverbed alluvial clay (vandall-man).",
        "summary_ta": "தேன்மெழுகையும் குங்கிலியத்தையும் கலந்து சிலை வடித்து, அதன் மீது மெல்லிய காவிரி ஆற்று வண்டல் மண்ணைப் பல அடுக்குகளாகப் பூசி, சுட்டு மெழுகை வெளியேற்றும் வார்ப்பு நுட்பம்.",
        "sources": [
            "Reeves: Cire Perdue Casting in India",
            "Swamimalai Traditional Bronze Casting Manuals",
            "Census of India: Handicrafts Monographs on Swamimalai Icons"
        ],
        "content": "# Madhuchchishtam: Lost-Wax Modeling & Clay Investments\n\nThe creation of a Chola bronze was a painstaking multi-stage ceramic and pyrotechnic process:\n\n- **The Wax Compounding (*Mezhugu*)**: Raw forest beeswax (*then-mezhugu*) was melted with dammar tree resin (*kungiliyam*) and groundnut oil in a 4:4:1 ratio. This mixture yielded a plastic, pliable medium that held crisp incised details at room temperature without cracking or slumping.\n- **Multi-Layered Clay Investment (*Karu-Mann*)**:\n  1. *First Coat (Charu-Mann)*: Micro-fine Kaveri silt ground with cow dung slurry was brushed onto the wax, capturing microscopic jewelry incisions.\n  2. *Second Coat*: Silt mixed with clay and charred rice husk (*umi*) to provide thermal insulation and porosity.\n  3. *Third Coat (Kala-Mann)*: Coarse red clay reinforced with jute fiber and bound with iron wire hoops to resist the colossal hydrostatic pressure of liquid metal.\n- **Dewaxing (*Mezhugu-Edutthal*)**: The dry mold was heated over a charcoal fire; the molten wax ran out through pre-cut drain sprues, leaving an intact hollow negative cavity."
    },
    {
        "file": "knowledge/artifacts/artifact-karuvool-crucibles-wax-spatulas-and-lost-wax-sprue-runners.md",
        "slug": "artifact-karuvool-crucibles-wax-spatulas-and-lost-wax-sprue-runners",
        "category": "artifact",
        "name_en": "Karuvool & Uzhari: Refractory Graphite Crucibles, Bronze Wax Spatulas & Funnel Sprues",
        "name_ta": "கருவூள் மற்றும் உழரி - உயர்வெப்ப மூசை, வெண்கல மெழுகு சீவு கரண்டிகள் மற்றும் வார்ப்பு வாய்கள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Foundry tools including refractory clay-graphite crucibles (karuvool), heated bronze carving spatulas (uzhari), and funnel-shaped wax sprue channels (vadi-vaai) engineered for non-turbulent molten metal pour.",
        "summary_ta": "உயர்ந்த வெப்பத்தைத் தாங்கும் களிமண்-கிராபைட் மூசைகள், மெழுகைச் செதுக்கும் வெண்கலக் கரண்டிகள் மற்றும் உருகிய உலோகத்தை வழிநடத்தும் வார்ப்பு வாய்கள்.",
        "sources": [
            "Archaeological Excavations at Kodumanal (Crucible Metallurgy)",
            "Swamimalai Sthapathi Tool Inventories",
            "Government Museum Chennai Metal Artifacts"
        ],
        "content": "# Karuvool & Uzhari: Casting Crucibles & Modeling Tools\n\nExecuting a successful pour required specialized ceramic and metal modeling gear:\n\n- **The Refractory Crucible (*Karuvool* / *Moosai*)**: Hand-built from refractory fireclay blended with crushed quartz, jute fiber, and carbonaceous graphite. These vessels withstood temperatures up to 1300°C in charcoal blast furnaces without fracturing or slag erosion.\n- **Wax Carving Spatulas (*Uzhari*)**: Double-ended bronze and iron tools featuring spatulate, curved, and needle-pointed ends. Heated gently over small oil lamps, they smoothed and micro-detailed facial expressions and drapery folds.\n- **Gating & Vents (*Vaai-Kodu*)**: Wax rods attached to the base of the model formed sprues and air vent chimneys (*kaathu-vaai*). As liquid bronze rushed down the main funnel, trapped air and combustion gases escaped freely, eliminating porosity bubbles."
    },
    {
        "file": "knowledge/concepts/concept-anandatandava-chola-nataraja-cosmic-equilibrium-and-dynamic-bronze-balance.md",
        "slug": "concept-anandatandava-chola-nataraja-cosmic-equilibrium-and-dynamic-bronze-balance",
        "category": "concept",
        "name_en": "Ananda-Tandava: Chola Nataraja Center-of-Gravity Dynamics, Prabha Radiance & Dynamic Equilibrium",
        "name_ta": "ஆனந்த தாண்டவம் - சோழர் நடராஜர் புவியீர்ப்பு மைய இயக்கவியல், திருவாசி வளையம் மற்றும் சமநிலை இயற்பியல்",
        "era": "Early Medieval Era",
        "year_start": 850,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Biomechanical and metallurgical balance of the iconic Chola Nataraja icon, balancing the multi-armed cosmic dancer upon a single planted right foot atop Apasmara within an elliptical ring of fire (prabhavali).",
        "summary_ta": "ஒற்றைக் காலில் முயலகன் மீது நின்று ஆடும் நடராஜரின் புவியீர்ப்பு மையத்தைச் சரியாகக் கணித்து, சுற்றிலும் திருவாசி வளையத்தால் சமநிலைப்படுத்தி வார்க்கப்படும் சிற்ப இயற்பியல் உச்சம்.",
        "sources": [
            "Coomaraswamy: The Dance of Shiva",
            "Rodin: Sculptures of Nataraja",
            "Srinivasan: The Cosmic Dance of Chola Bronzes"
        ],
        "content": "# Ananda-Tandava: Dynamic Balance of Chola Nataraja\n\nThe Chola *Nataraja* is celebrated by art historians and physicists worldwide as the supreme union of art and mechanics:\n\n- **Single-Foot Structural Anchor**: The entire mass of the dancing four-armed deity—holding the drum of creation (*damaru*) and fire of destruction (*agni*)—is supported upon the single bent right leg pressing down on the demon of ignorance (*Apasmara*).\n- **Center-of-Gravity Alignment**: Sthapathis calculated the center of gravity so that the vertical axis passed precisely through the third eye, navel, and right heel, preventing lateral tipping during processional swaying.\n- **The Prabhavali Arch Tension**: The encircling arch of flames (*prabhavali*) was not merely decorative; it functioned as a structural outer tension ring. Welded to the flying locks of hair (*jata*) and the lotus plinth (*padmapitha*), the ring absorbed vibrational stress and prevented the slender lifted left leg (*kunchita-pada*) from shearing off."
    },
    {
        "file": "knowledge/institutions/institution-swamimalai-sthapathi-guild-of-hereditary-imperial-chola-bronze-casters.md",
        "slug": "institution-swamimalai-sthapathi-guild-of-hereditary-imperial-chola-bronze-casters",
        "category": "institution",
        "name_en": "Swamimalai Sthapathis: Hereditary Chola Guild of Master Bronze Casters & Sacred Iconographers",
        "name_ta": "சுவாமிமலை ஸ்தபதிகள் - சோழர் கால பாரம்பரிய வெண்கலச் சிற்பிகள் சங்கம் மற்றும் ஆகம நெறிமுறை அவை",
        "era": "Early Medieval to Modern Era",
        "year_start": 900,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "Imperial guild of hereditary master bronze casters and sculptors (Viswakarma Sthapathis) patronized by Chola monarchs (Raja Raja I, Rajendra I) to populate thousands of monumental stone temples with cast processional icons.",
        "summary_ta": "தஞ்சைப் பெரிய கோயில் மற்றும் சோழ மண்டலக் கோயில்களுக்குத் தெய்வத் திருமேனிகளை வார்க்க ராஜராஜ சோழனால் சுவாமிமலையில் அமர்த்தப்பட்ட தலைசிறந்த சிற்பக் கலைஞர்கள் சங்கம்.",
        "sources": [
            "Thanjavur Brihadisvara Inscriptions on Bronze Gifts",
            "Census of India Monograph: Swamimalai Artisans",
            "UNESCO Intangible Cultural Heritage Surveys"
        ],
        "content": "# Swamimalai Sthapathis: Imperial Guild of Bronze Casters\n\nThe flourishing of imperial Chola bronzes was rooted in the state patronage of the Swamimalai sculpting community:\n\n- **The Royal Foundation**: Historical traditions and epigraphs record that Emperor Raja Raja Chola I settled master metal casters along the banks of the Kaveri at Swamimalai near Kumbakonam, commissioning them to cast hundreds of sacred images for the Great Temple at Thanjavur.\n- **Strict Agamic Lineage**: Guild members preserved the secret oral canons of *Dhyana Slokas*—poetic verses memorized in cadence that describe every facial proportion, mudra, and drapery fold of each divinity.\n- **Ritual Consecration (*Nethronmeelana*)**: The sculptor’s ultimate task was the sacred opening of the deity's eyes (*kan-thirakkal*) using a gold-tipped chisel, transforming a cold metal casting into a consecrated murthi ready for temple worship."
    },
    {
        "file": "knowledge/technologies/technology-chasing-and-burnishing-cold-hammered-detail-engraving-and-patination.md",
        "slug": "technology-chasing-and-burnishing-cold-hammered-detail-engraving-and-patination",
        "category": "technology",
        "name_en": "Chasing & Burnishing: Cold-Hammered Tooling, Agate Burnishing & Organic Oil Patination",
        "name_ta": "செதுக்குதல் மற்றும் பளபளப்பாக்குதல் - உளி வேலைப்பாடு, அகேட் கல் தேய்த்தல் மற்றும் மூலிகை எண்ணெய் மெருகூட்டல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Post-casting metallurgical finishing comprising sprue cut-off, abrasive sand polishing, fine chasing of jewelry and crowns with hardened punches, and hot sesame-oil patination.",
        "summary_ta": "வார்ப்பு முடிந்த சிலையிலிருந்து உலோகம் பாய்ந்த குழாய்களை அறுத்து, நுண்ணிய உளிகளால் ஆடை ஆபரணங்களைச் செதுக்கி, கல் கொண்டு தேய்த்து மெருகூட்டும் நுட்பம்.",
        "sources": [
            "Srinivasan: The Technique of South Indian Bronze Casting",
            "Conservation Manuals for Chola Metal Icons",
            "Government Museum Chennai Metallurgy Bulletins"
        ],
        "content": "# Chasing & Burnishing: Post-Casting Cold Metal Finishing\n\nBreaking open the baked clay mold revealed a raw, rough metal casting that required hundreds of hours of cold mechanical finishing:\n\n- **Sprue & Seam Removal**: The casting sprues and air vents were sawed off with hardened hacksaws and ground flush using iron files and carborundum stones.\n- **Fine Chasing (*Kothu-Velai*)**: Master engravers used small hardened punches and chasing chisels struck with lightweight brass hammers to delineate eye pupils, intricate diadem crowns (*karanda-makuta*), finger rings, and gossamer textile patterns directly into the cold bronze.\n- **Burnishing & Herbal Patination**: The metal was vigorously polished with smooth agate stones and fine emery powder, then rubbed with hot sesame oil and tamarind water, creating the deep, lustrous golden-bronze patination characteristic of classical Chola masterpieces."
    },
    {
        "file": "knowledge/artifacts/artifact-thalamana-measuring-ribbons-brass-dividers-and-iron-chasing-punches.md",
        "slug": "artifact-thalamana-measuring-ribbons-brass-dividers-and-iron-chasing-punches",
        "category": "artifact",
        "name_en": "Oduvolai & Matha-Kole: Palm-Leaf Measuring Strips, Calibrated Dividers & Chasing Punches",
        "name_ta": "ஓடுவோலை மற்றும் மாதாகோல் - பனை ஓலை அளவுப் பட்டை, பித்தளைக் கவை மற்றும் செதுக்குக் கருவிகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Precision metrological instruments including proportional notched palm-leaf ribbons (oduvolai), brass caliper dividers (kavai), and specialized hardened chasing punches (pathivu-uli).",
        "summary_ta": "சிற்பத்தின் ஒவ்வோர் அங்க அளவுகளையும் குறித்து வைக்கும் பனை ஓலை அளவுகோல், பித்தளைக் கவை மற்றும் அணிகலன் செதுக்கும் இரும்பு உளிகள்.",
        "sources": [
            "Traditional Measuring Techniques in Tamil Iconography",
            "Swamimalai Artisan Metrological Tools",
            "National Museum New Delhi Conservation Studies"
        ],
        "content": "# Oduvolai & Matha-Kole: Iconographic Measuring Instruments\n\nCreating divine sculptures that conformed strictly to the Agamic canons required precision layout instruments:\n\n- **The Notched Palm Ribbon (*Oduvolai*)**: Sthapathis cut a long, narrow ribbon of cured palmyra leaf equal to the total designated height of the icon. Folding it repeatedly in halves and thirds, they notched reference marks corresponding to each major canonical proportional junction (forehead, neck, navel, knees).\n- **Proportional Brass Calipers (*Matha-Kole* / *Kavai*)**: Double-jointed brass dividers used to transfer proportional widths between the wax model and the reference canon without relying on arbitrary absolute metric units.\n- **Fine Punches (*Pathivu-Uli*)**: Sets of specialized cold-forged punches featuring textured points (beaded, grooved, diamond) used to stamp decorative surface diaper patterns into royal armlets and thrones."
    },
    {
        "file": "knowledge/concepts/concept-kaveri-riverbed-vandall-clay-plasticity-and-thermal-shock-resistance.md",
        "slug": "concept-kaveri-riverbed-vandall-clay-plasticity-and-thermal-shock-resistance",
        "category": "concept",
        "name_en": "Kaveri Alluvium: Fine Riverbed Silt Plasticity, Refractory Porosity & Thermal Shock Resistance",
        "name_ta": "காவிரி வண்டல் மண் - நுண் ஆற்று வண்டலின் நெகிழ்வுத்தன்மை, உயர்வெப்பத் தாங்குதிறன் மற்றும் வார்ப்பு இயற்பியல்",
        "era": "Prehistoric to Modern Era",
        "year_start": -1000,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Geological and ceramic properties of fine alluvial silt (vandall-man) deposited along the Kaveri riverbed near Swamimalai, possessing optimal plasticity, zero shrinkage cracking, and high refractory thermal shock resistance.",
        "summary_ta": "காவிரி ஆற்றுப் படுகையில் கிடைக்கும் வண்டல் களிமண்ணின் நுணுக்கமான படிக அமைப்பு, சுடும்போது வெடிக்காத தன்மை மற்றும் உருகிய உலோகத்தின் வெப்பத்தைத் தாங்கும் மேன்மை.",
        "sources": [
            "Ceramic and Soil Studies of the Kaveri Delta Basin",
            "Traditional Foundry Practices of Swamimalai",
            "Indian Ceramic Society Transactions"
        ],
        "content": "# Kaveri Alluvium: Riverbed Silt Plasticity & Refractory Molds\n\nThe global preeminence of Swamimalai bronzes is inextricably tied to the unique sedimentology of the Kaveri River:\n\n- **Sub-Micron Silt Grain Size**: The slow-moving waters of the Kaveri delta deposit an extraordinarily fine, colloidal illite and montmorillonite silt (*vandall*). When applied as a liquid slip, it coats the wax model without air bubbles, replicating microscopic engraving marks down to fractions of a millimeter.\n- **Charred Husk Porosity (*Umi-Mann*)**: Blended with charred rice husks, the clay develops a network of microscopic pores during baking. This porosity allows superheated steam and combustion gases to vent harmlessly through the mold walls during pouring, preventing explosive blowouts.\n- **Thermal Shock Tolerance**: The mold withstands the sudden, violent thermal shock of 1000°C liquid bronze poured into its cavity without spalling or structural micro-cracking."
    },
    {
        "file": "knowledge/places/place-swamimalai-ancient-chola-panchaloha-icon-casting-haven.md",
        "slug": "place-swamimalai-ancient-chola-panchaloha-icon-casting-haven",
        "category": "place",
        "name_en": "Swamimalai: Ancient Chola Panchaloha Bronze Casting Haven, Kaveri Delta Sthapathi Citadel & GI Sanctuary",
        "name_ta": "சுவாமிமலை - பண்டைய சோழர் ஐம்பொன் வார்ப்புத் தளம், காவிரி படுகை ஸ்தபதிகள் பெருநகரம் மற்றும் புவிசார் குறியீட்டுத் தளம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 900,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "The legendary temple town on the Kaveri River near Kumbakonam, world-renowned for over a millennium as the unbroken global sanctuary of lost-wax Panchaloha bronze icon casting.",
        "summary_ta": "தஞ்சாவூர் மாவட்டம் கும்பகோணம் அருகே காவிரி ஆற்றங்கரையில் அமைந்துள்ள, சோழர் காலம் தொட்டு உலகப் புகழ்பெற்ற ஐம்பொன் சிலை வார்க்கும் பாரம்பரியச் சிற்பத் தளம்.",
        "sources": [
            "UNESCO Intangible Cultural Heritage Dossier: Swamimalai Bronze Casting",
            "GI Registry of India: Swamimalai Bronze Icons Dossier",
            "Imperial Chola Epigraphical Records"
        ],
        "content": "# Swamimalai: Ancient Chola Bronze Casting Haven\n\nNestled along the banks of the sacred Kaveri River near Kumbakonam in Thanjavur district, Swamimalai is the undisputed global capital of traditional bronze metallurgy:\n\n- **Imperial Chola Capital of Art**: When Raja Raja Chola I built the Brihadisvara Temple at Thanjavur, he concentrated the empire's greatest bronze-casting families (*Sthapathis*) at Swamimalai, endowed by proximity to Kaveri silt and royal foundries.\n- **Unbroken Hereditary Lineage**: For over a thousand years, the artisan families residing on *Sirpa Theru* have passed down the sacred lost-wax technique from father to son across dozens of generations.\n- **Geographical Indication (GI) & World Heritage**: Awarded an official Geographical Indication tag and celebrated by international museums from Paris to New York, Swamimalai stands as the living embodiment of Tamil classical metallurgy and spiritual iconography."
    }
]

EDGES = [
    [
        "text-karanagama-and-silpa-sastras-on-lost-wax-cire-perdue-bronze-iconography",
        "CODIFIES",
        "technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry",
        "core",
        "Early Medieval Era",
        "Karanagama codifies the lost-wax beeswax modeling and alluvial mold casting rituals.",
        "Karanagama Kriya Pada"
    ],
    [
        "technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry",
        "POURS",
        "concept-panchaloha-five-metal-sacred-alloy-metallurgy-and-dendritic-microstructure",
        "core",
        "Iron Age to Modern Era",
        "The baked clay mold cavity was filled with molten five-metal Panchaloha alloy.",
        "Archaeometallurgical Analysis of Chola Bronzes (Reeves)"
    ],
    [
        "technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry",
        "EXECUTED_WITH",
        "artifact-karuvool-crucibles-wax-spatulas-and-lost-wax-sprue-runners",
        "core",
        "Iron Age to Modern Era",
        "Heated wax carving spatulas and refractory graphite crucibles handled the casting.",
        "Swamimalai Sthapathi Tool Inventories"
    ],
    [
        "concept-panchaloha-five-metal-sacred-alloy-metallurgy-and-dendritic-microstructure",
        "EMBODIED_IN",
        "concept-anandatandava-chola-nataraja-cosmic-equilibrium-and-dynamic-bronze-balance",
        "core",
        "Early Medieval Era",
        "Panchaloha bronze alloy achieved dynamic balance in the iconic Chola Nataraja icon.",
        "Srinivasan: The Cosmic Dance of Chola Bronzes"
    ],
    [
        "technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry",
        "MASTERED_BY",
        "institution-swamimalai-sthapathi-guild-of-hereditary-imperial-chola-bronze-casters",
        "core",
        "Early Medieval to Modern Era",
        "Swamimalai sthapathis maintained hereditary mastery of lost-wax casting and Agamic canons.",
        "UNESCO Intangible Cultural Heritage Dossier: Swamimalai Bronze Casting"
    ],
    [
        "institution-swamimalai-sthapathi-guild-of-hereditary-imperial-chola-bronze-casters",
        "PERFORMS",
        "technology-chasing-and-burnishing-cold-hammered-detail-engraving-and-patination",
        "core",
        "Iron Age to Modern Era",
        "Guild masters chased cold details, opened the eyes of deities, and patinated the bronze.",
        "Srinivasan: The Technique of South Indian Bronze Casting"
    ],
    [
        "technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry",
        "MEASURED_BY",
        "artifact-thalamana-measuring-ribbons-brass-dividers-and-iron-chasing-punches",
        "core",
        "Iron Age to Modern Era",
        "Notched palm ribbons and brass dividers calibrated exact canonical icon proportions.",
        "Traditional Measuring Techniques in Tamil Iconography"
    ],
    [
        "technology-madhuchchishtam-beeswax-resin-modeling-kaveri-alluvial-mold-slurry",
        "DEPENDS_ON",
        "concept-kaveri-riverbed-vandall-clay-plasticity-and-thermal-shock-resistance",
        "core",
        "Prehistoric to Modern Era",
        "Kaveri alluvial silt provided crack-free plasticity and thermal shock resistance.",
        "Ceramic and Soil Studies of the Kaveri Delta Basin"
    ],
    [
        "institution-swamimalai-sthapathi-guild-of-hereditary-imperial-chola-bronze-casters",
        "BASED_AT",
        "place-swamimalai-ancient-chola-panchaloha-icon-casting-haven",
        "core",
        "Early Medieval to Modern Era",
        "Swamimalai served as the royal imperial Chola sanctuary for master bronze casters.",
        "Thanjavur Brihadisvara Inscriptions on Bronze Gifts"
    ],
    [
        "concept-kaveri-riverbed-vandall-clay-plasticity-and-thermal-shock-resistance",
        "SOURCED_AT",
        "place-swamimalai-ancient-chola-panchaloha-icon-casting-haven",
        "core",
        "Early Medieval to Modern Era",
        "The Kaveri riverbanks at Swamimalai provided the sacred alluvial clay for the foundries.",
        "GI Registry of India: Swamimalai Bronze Icons Dossier"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 38: Ancient Tamil Bronze Icon Lost-Wax Casting & Cire-Perdue Metallurgy...")
    
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
