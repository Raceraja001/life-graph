#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Leatherworking & War Shields
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
        "file": "knowledge/texts/text-purananuru-warrior-leather-bucklers-and-bellows-poetry.md",
        "slug": "text-purananuru-warrior-leather-bucklers-and-bellows-poetry",
        "category": "text",
        "name_en": "Purananuru: Classical Sangam Odes on Warrior Leather Bucklers, Quivers & Blacksmith Bellows",
        "name_ta": "புறநானூறு - மறவர் தோல் பரிசை, அம்புக்கூடு மற்றும் துருத்திப் பாடல்கள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "marutham",
        "summary_en": "Sangam heroic verses describing multi-layered water-buffalo leather bucklers (parichai), arrow quivers, and animal-hide blacksmith forge bellows (thuruthi).",
        "summary_ta": "புறநானூற்றுப் பாடல்களில் எருமைத் தோல் கேடயங்கள், அம்புக்கூடுகள் மற்றும் இரும்பு கொல்லர்களின் தோல் துருத்தி உலைகள் பற்றிய துல்லியமான போர்க்கலை வர்ணனைகள்.",
        "sources": [
            "Purananuru 95",
            "Purananuru 284",
            "Purananuru 310"
        ],
        "content": "# Purananuru: Classical Sangam Odes on Warrior Leather Bucklers\n\nPurananuru offers profound insights into military leathercraft in classical Tamilakam. The martial poems vividly recount how frontline infantry and elite vanguard shock troops relied upon hardened leather shields (parichai or thol-kaval) to repel flights of bronze and iron-tipped arrows.\n\nPoet Avvaiyar and other Sangam bards depict the battlefield bucklers as thick, reinforced circles of cured hide stretched over wicker or wooden armatures, painted with terrifying protective totems or royal emblems. In addition to personal defense, Purananuru immortalizes the blacksmith's leather bellows (thuruthi), capturing the rhythmic blast of air forced through ox-hide bladders to generate the intense heat necessary for forging lethal spears and swords.\n\nThe verses demonstrate that leather craftsmen (thannar or thol-vinaignar) held a critical place in the logistics of classical Sangam polities."
    },
    {
        "file": "knowledge/concepts/concept-avaram-bark-and-kadukkai-vegetal-tanning-protocols-thol-padaniduthal.md",
        "slug": "concept-avaram-bark-and-kadukkai-vegetal-tanning-protocols-thol-padaniduthal",
        "category": "concept",
        "name_en": "Avaram Bark & Kadukkai Gallnut Vegetal Tanning Protocols (Thol Padaniduthal & Avarai Tannin)",
        "name_ta": "ஆவாரம்பட்டை மற்றும் கடுக்காய் தாவர தோல் பதனிடும் முறைமை",
        "era": "Sangam to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Indigenous vegetable tanning metallurgy utilizing polyphenol-rich golden avaram bark (Senna auriculata) and myrobalan nuts (kadukkai) to yield supple, durable, water-resistant leather.",
        "summary_ta": "ஆவாரம்பட்டை மற்றும் கடுக்காய் ஊறல் கொண்டு விலங்கு தோல்களைப் பதனிட்டு, உழைப்பும் நெகிழ்வுத்தன்மையும் கொண்ட போர்த்தோல் தயாரிக்கும் பாரம்பரிய முறைமை.",
        "sources": [
            "Tamil Lexicon: Thol-Padaniduthal",
            "Indigenous Leathercraft Surveys of Palar Basin"
        ],
        "content": "# Avaram Bark & Kadukkai Vegetal Tanning Protocols\n\nThe historical glory of Tamil leathercraft lies in its indigenous vegetal tanning chemistry. Ancient tanners discovered that the bark of the wild desert shrub avaram (Senna auriculata), known as 'tanner's cassia', contains extraordinary concentrations of condensed catechins and polyphenols that stabilize raw animal collagen fibers.\n\nHides of water buffalo, ox, and deer were first desalted and steeped in lime pits (sunnambu thotti) to strip hair and subcutaneous fats. The dehaired pelts were transferred to successive clay tanning vats infused with crushed avaram bark and dried kadukkai (Terminalia chebula gallnuts).\n\nThis natural bath prevented fungal decay, imparted a rich pale-yellow patina that resists darkening under tropical sunlight, and produced dense, pliable leather immune to hardening when saturated with water."
    },
    {
        "file": "knowledge/concepts/concept-multi-layered-water-buffalo-hide-war-bucklers-parichai.md",
        "slug": "concept-multi-layered-water-buffalo-hide-war-bucklers-parichai",
        "category": "concept",
        "name_en": "Multi-Layered Water Buffalo Hide War Bucklers & Arrow-Deflecting Shields (Parichai)",
        "name_ta": "பல் அடுக்கு எருமைத் தோல் போர்ப் பரிசை மற்றும் அம்பு தடுப்புக் கேடயம்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Military ballistics and layered rawhide construction of Tamil battle shields (parichai), designed to absorb heavy spear thrusts and deflect high-velocity composite bow arrows.",
        "summary_ta": "தடிமனான எருமைத் தோலை அடுக்குகளாக வைத்து, பிசின் மற்றும் இரும்பு விளிம்புகள் சேர்த்து உருவாக்கப்பட்ட போர்ப் பரிசை கேடயத் தயாரிப்பு நுட்பம்.",
        "sources": [
            "Pathitrupathu 54",
            "Perumpanattruppadai lines 115-130"
        ],
        "content": "# Multi-Layered Water Buffalo Hide War Bucklers (Parichai)\n\nThe parichai was the standard defensive armament of ancient Tamil infantry regiments. Constructed primarily from mature swamp buffalo rawhide, these circular bucklers measured approximately twenty to twenty-four inches in diameter.\n\nCraftsmen laminated multiple sheets of semi-tanned hide using boiled animal glue and tree gums (karuvelam resin). The layered composite was pressed into convex wooden molds and dried under tension, creating an extremely rigid yet resilient shell. The outer rim was bound with beaten iron or brass hoops to prevent splitting from slashing broadsword blows.\n\nThe interior featured a padded wrist brace and double leather forearm straps. Tests and classical accounts confirm that this laminated rawhide absorbed kinetic energy far more effectively than thin sheet metal, stopping heavy iron javelins without puncturing."
    },
    {
        "file": "knowledge/concepts/concept-water-resistant-leather-water-skins-and-smithing-bellows-thuruthi.md",
        "slug": "concept-water-resistant-leather-water-skins-and-smithing-bellows-thuruthi",
        "category": "concept",
        "name_en": "Water-Resistant Animal Skins, Travel Flasks & Furnace Bellows Engineering (Thuruthi & Thol-Pai)",
        "name_ta": "துருத்தி - தோல் உலை ஊதுகுழாய், நீர் தோல் பை மற்றும் நீர்ப்புகா தோல் பாண்டங்கள்",
        "era": "Sangam to Medieval Era",
        "year_start": -400,
        "year_end": 1600,
        "thinai": "marutham",
        "summary_en": "Engineering of seamless whole-animal hide water skins (thuruthi/thol-pai) for arid journeys and dual-chambered leather bellows that powered iron smelting and bronze casting furnaces.",
        "summary_ta": "முழு ஆட்டுத்தோல் கொண்டு தைக்கப்படும் நீர் தாங்கும் தோல் பைகள் மற்றும் கொல்லர் உலைகளில் தொடர் காற்று பாய்ச்சும் துருத்தி அமைப்பின் வடிவமைப்பு.",
        "sources": [
            "Purananuru 95",
            "Sirupanattruppadai lines 140-160"
        ],
        "content": "# Water-Resistant Leather Skins & Furnace Bellows (Thuruthi)\n\nLeather's impermeable and elastic properties were harnessed across ancient Tamil industrial and utilitarian spheres through the thuruthi. Two distinct devices shared this name: the whole-hide water container and the metallurgical air bellows.\n\nThe transport thuruthi was crafted from an intact goat or deer hide cased in one piece without longitudinal incisions, with the neck and leg apertures tightly bound and sealed with tree pitch. Impregnated with sesame oil and beeswax, these water skins kept drinking water cool via surface evaporation during long marches across arid Palai wilderness.\n\nIn iron smelting and weapon forges, the mechanical thuruthi consisted of large flexible ox-hide bellows operated by hand levers or foot-treadles, pumping an uninterrupted stream of oxygen into blast furnaces to reach melting temperatures of 1300°C."
    },
    {
        "file": "knowledge/concepts/concept-chariot-harnessry-and-war-elephant-leather-cuirasses-mey-maravadi.md",
        "slug": "concept-chariot-harnessry-and-war-elephant-leather-cuirasses-mey-maravadi",
        "category": "concept",
        "name_en": "War Elephant Trappings, Chariot Traces & Body Armor Cuirasses (Mey-Maravadi & Vandi-Kattal)",
        "name_ta": "மெய்ம்மரவடி - போர் யானைத் தோல் கவசம், தேர்க் கச்சை மற்றும் தோல் உடற்கவசம்",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1250,
        "thinai": "marutham",
        "summary_en": "Heavy leather military gear including boiled-leather body cuirasses (mey-maravadi), war elephant forehead armors, and multi-ply harness traces for high-speed battlefield chariots.",
        "summary_ta": "வேகவைத்த தடித்த தோலால் செய்யப்பட்ட மெய்ம்மரவடி உடற்கவசம், போரியானைகளின் முகபடாம் மற்றும் தேர்க் குதிரைகளின் இழுவைக் கச்சைகள் தயாரிக்கும் முறைமை.",
        "sources": [
            "Silappadikaram Vanchikandam",
            "Manimekalai chapter 20"
        ],
        "content": "# War Elephant Trappings & Leather Cuirasses (Mey-Maravadi)\n\nThe zenith of Tamil tactical leatherworking manifested in heavy cavalry and war elephant protection. Boiled leather armor, known in classical texts as mey-maravadi, was manufactured by soaking cured ox hide in hot wax, oil, and mineral resins until saturated, then molding it around anatomical wooden forms.\n\nUpon cooling, the material hardened into an almost impenetrable, puncture-proof breastplate that protected infantry commanders against arrow volleys and spear stabs while weighing half as much as iron mail.\n\nFor war elephants, royal saddlers crafted massive protective girths, leather face-masks (muka-kavacham), and spiked trunk-sheaths. Chariot builders utilized braided raw-hide traces (vandi-kattal) that resisted sudden mechanical shock and tensile fracture during combat maneuvers over broken terrain."
    },
    {
        "file": "knowledge/inscriptions/insc-ranipet-palar-basin-leather-guild-and-tannery-endowments.md",
        "slug": "insc-ranipet-palar-basin-leather-guild-and-tannery-endowments",
        "category": "inscription",
        "name_en": "Palar Basin Epigraphs on Riverine Leather Guilds, Tannery Vats & Temple Drum Endowments",
        "name_ta": "பாலாற்றுப் படுகை கல்வெட்டுகள் - தோல் பதனிடும் தொழிற்கூடம் மற்றும் முரசுத்தோல் கொடை",
        "era": "Medieval Chola Era",
        "year_start": 980,
        "year_end": 1180,
        "thinai": "marutham",
        "summary_en": "Stone inscriptions from northern Tamil river valleys recording royal charters granted to leather-working guilds who maintained tanning vats and supplied consecrated drum hides to temple complexes.",
        "summary_ta": "பாலாற்றுப் படுகை சோழர் கல்வெட்டுகள் தோல் பதனிடும் கைவினைஞர் கூட்டங்கள், தோல் தொட்டிகள் மற்றும் கோயில்களுக்கு முரசுத் தோல் வழங்கிய உரிமைகளை விவரிக்கின்றன.",
        "sources": [
            "South Indian Inscriptions Vol XIII",
            "Ranipet Historical Inscriptions Archive"
        ],
        "content": "# Palar Basin Riverine Leather Guild Inscriptions\n\nCarved on the plinths of Chola temples along the fertile Palar river valley near modern Ranipet, these epigraphs provide indisputable documentary evidence of organized leatherworking guilds (thannar kottam).\n\nThe river basin, rich in flowing fresh water and indigenous avaram shrubs, was recognized by the imperial administration as a primary tanning hub. The inscriptions record royal land allocations for industrial tanning pits (thol padanidum thotti) situated at safe distances downstream from residential agraharams.\n\nIn exchange for commercial tax remissions, the guild contracted to supply consecrated, defect-free buffalo hides for royal war drums (veera-murasu) and temple ceremonial percussion instruments."
    },
    {
        "file": "knowledge/inscriptions/insc-uraiyur-chola-military-leather-shield-armory-charters.md",
        "slug": "insc-uraiyur-chola-military-leather-shield-armory-charters",
        "category": "inscription",
        "name_en": "Uraiyur Imperial Chola Royal Armory Charters for Leather Shield & Harness Guilds",
        "name_ta": "உறையூர் சோழர் போர்க் களரி கல்வெட்டுகள் - தோல் பரிசைக் கைவினைஞர் மற்றும் கச்சை சாசனங்கள்",
        "era": "Early Chola to Imperial Era",
        "year_start": 880,
        "year_end": 1100,
        "thinai": "marutham",
        "summary_en": "Early medieval Chola armory records from Uraiyur detailing state procurement quotas for hardened buffalo parichai shields, elephant bridles, and chariot leather traces.",
        "summary_ta": "உறையூர் சோழர் கல்வெட்டுகள் அரச போர்க்களரிக்குத் தேவையான எருமைத் தோல் கேடயங்கள், யானைக் கச்சைகள் மற்றும் தேர்த் தோல் கயிறுகளின் கொள்முதல் விபரங்களைப் பதிவு செய்கின்றன.",
        "sources": [
            "Epigraphia Carnatica & Chola Military Epigraphs",
            "Tiruchirappalli District Inscriptions"
        ],
        "content": "# Uraiyur Royal Armory Leather Shield Charters\n\nFound in the ancient Chola capital of Uraiyur on the Kaveri banks, these imperial administrative charters detail the state regulation of military leathercraft.\n\nThe records list stringent metallurgical and leather quality benchmarks for parichai bucklers destined for the elite imperial bodyguard regiments (velaikaarar). The shields were required to withstand five consecutive spear thrusts without tearing or delamination before passing inspection by the master armorer (kadavu thalaivan).\n\nThe charters further exempt master leather armorers from corvée labor, granting them hereditary tenures in recognition of their strategic contribution to the Chola military apparatus."
    },
    {
        "file": "knowledge/characters/char-ranipet-master-vegetal-tanner-and-currier-thol-vinaignan.md",
        "slug": "char-ranipet-master-vegetal-tanner-and-currier-thol-vinaignan",
        "category": "character",
        "name_en": "Ranipet Master Vegetal Tanner & Tannin Currier (Thol Vinaignan)",
        "name_ta": "ராணிப்பேட்டை பாலாற்றுப் படுகை தலைமைத் தோல் பதனிடும் வினைஞன்",
        "era": "Medieval Chola Era",
        "year_start": 1020,
        "year_end": 1100,
        "thinai": "marutham",
        "summary_en": "Master tanner and currier celebrated for formulating optimized avaram-kadukkai enzyme liquor baths that transformed heavy raw water buffalo hides into flexible, impervious military leather.",
        "summary_ta": "ஆவாரம்பட்டை மற்றும் கடுக்காய் ஊறல் சாற்றை சரியான விகிதத்தில் கலந்து, எருமைத் தோலை மென்மையாகவும் அதேசமயம் அம்பு துளைக்காதவாறும் மாற்றும் தலைமைக் கைவினைஞர்.",
        "sources": [
            "Palar Basin Guild Roll Records",
            "Chola Occupational Register"
        ],
        "content": "# Ranipet Master Vegetal Tanner (Thol Vinaignan)\n\nThe Thol Vinaignan represented the master chemist of ancient Tamil industry. Operating along the perennial watercourses of the Palar river, he oversaw the multi-week progression of raw hides through sequential fermentation, liming, unhairing, and tannin-impregnation vats.\n\nHe possessed intimate knowledge of seasonal bark harvesting, timing the stripping of avaram bark to the post-monsoon flowering period when tannin concentrations peaked. By calibrating the temperature and acidity of the tanning broth with myrobalan extracts and wood ash, he prevented surface case-hardening, ensuring deep, uniform penetration into thick buffalo hides.\n\nHis signature leathers were renowned for their silky grain, golden luster, and extraordinary tensile resilience against rot and tropical mildew."
    },
    {
        "file": "knowledge/characters/char-uraiyur-royal-armory-leather-shield-master-parichai-thalaivan.md",
        "slug": "char-uraiyur-royal-armory-leather-shield-master-parichai-thalaivan",
        "category": "character",
        "name_en": "Uraiyur Royal Armory Master Leather Shield Craftsman (Parichai Thalaivan)",
        "name_ta": "உறையூர் சோழர் அரச போர்க்களரி பரிசைத் தலைமை வினைஞன்",
        "era": "Sangam to Early Chola Era",
        "year_start": 850,
        "year_end": 950,
        "thinai": "marutham",
        "summary_en": "Royal armorer overseeing the molding, lamination, and ballistics testing of hardened water-buffalo parichai shields and boiled-leather cuirasses for Chola infantry forces.",
        "summary_ta": "சோழர் அரச போர்க்களரியில் எருமைத் தோல் கேடயங்கள், மெய்ம்மரவடி உடற்கவசங்களை வடிவமைத்து, அவற்றின் வலிமையை சோதித்த தலைமை போர்க்கலைக் கைவினைஞர்.",
        "sources": [
            "Uraiyur Armory Excavation Reports",
            "Chola Martial Guild Chronology"
        ],
        "content": "# Uraiyur Master Leather Shield Craftsman (Parichai Thalaivan)\n\nAppointed by the royal court, the Parichai Thalaivan supervised the manufacture of personal defense armor for the imperial armies. Stationed at the primary garrison workshop of Uraiyur, he commanded hundreds of skilled curriers, stitchers, and brass-smiths.\n\nHe pioneered specialized lamination formulas, blending fish glue, tamarind seed paste, and tree lac to bind multiple plies of rawhide into lightweight, arrow-proof discs. Under his direction, each shield underwent ballistic proofing against iron-tipped broadhead arrows fired at twenty paces.\n\nHe also designed ergonomic shock-absorbing grips that dissipated blunt-force trauma from war maces and heavy broadswords, safeguarding the wielder's arm bones from crushing fractures."
    },
    {
        "file": "knowledge/places/place-ranipet-ancient-palar-basin-leather-tannery-haven.md",
        "slug": "place-ranipet-ancient-palar-basin-leather-tannery-haven",
        "category": "place",
        "name_en": "Ranipet: Ancient Palar Basin Leather Tannery & Guild Craft Haven",
        "name_ta": "ராணிப்பேட்டை - பண்டைய பாலாற்றுப் படுகை தோல் பதனிடும் தொழிலகத் தளம்",
        "era": "Sangam to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Historic riparian industrial cluster on the Palar River, globally celebrated for over two millennia as the preeminent heartland of Tamil avaram-bark vegetable tanning and military leather crafts.",
        "summary_ta": "பாலாற்றின் கரையில் அமைந்துள்ள தொன்மையான தளம்; இரண்டு நூற்றாண்டுகளுக்கும் மேலாக ஆவாரம்பட்டை தாவர தோல் பதனிடுதல் மற்றும் உலகத் தரம் வாய்ந்த தோல் உற்பத்தியின் தலைமை மையம்.",
        "sources": [
            "Imperial Gazetteer of India (North Arcot)",
            "Palar Valley Industrial Heritage Survey"
        ],
        "content": "# Ranipet: Ancient Palar Basin Leather Tannery Haven\n\nLocated on the banks of the Palar River in modern northern Tamil Nadu, the Ranipet region constitutes one of the oldest contiguous leather-processing industrial centers on earth. Its emergence as a tanning capital was conditioned by a unique confluence of geographical advantages: copious sweet river water, extensive herds of pasture-raised livestock, and immense wild groves of avaram shrubs (Senna auriculata).\n\nSangam texts and medieval inscriptions establish that guilds of tanners maintained extensive brick-lined vat complexes along the sandy riverbanks. The porous, well-draining soils allowed rapid drying of hides, while the natural tannin chemistry produced leather of unmatched durability.\n\nFrom classical times when it equipped Chola armories with parichai bucklers to the modern era, Ranipet has continuously preserved this ancient metallurgical and tanning heritage."
    }
]
EDGES = [
    [
        "text-purananuru-warrior-leather-bucklers-and-bellows-poetry",
        "documents_technique",
        "concept-multi-layered-water-buffalo-hide-war-bucklers-parichai",
        "historical_proof",
        "Sangam Era",
        "Purananuru provides explicit heroic verse describing thick buffalo hide parichai bucklers deflecting arrows in combat.",
        "Purananuru 95"
    ],
    [
        "text-purananuru-warrior-leather-bucklers-and-bellows-poetry",
        "documents_equipment",
        "concept-water-resistant-leather-water-skins-and-smithing-bellows-thuruthi",
        "historical_proof",
        "Sangam Era",
        "Purananuru immortalizes the leather thuruthi forge bellows powering blacksmith weaponry furnaces.",
        "Purananuru 310"
    ],
    [
        "concept-avaram-bark-and-kadukkai-vegetal-tanning-protocols-thol-padaniduthal",
        "produces_material",
        "concept-multi-layered-water-buffalo-hide-war-bucklers-parichai",
        "historical_proof",
        "Sangam to Medieval Era",
        "Vegetable tanning with avaram bark and kadukkai yielded the tough, flexible rawhide plies needed for shields.",
        "Tamil Lexicon: Thol-Padaniduthal"
    ],
    [
        "concept-avaram-bark-and-kadukkai-vegetal-tanning-protocols-thol-padaniduthal",
        "supplies_leather",
        "concept-chariot-harnessry-and-war-elephant-leather-cuirasses-mey-maravadi",
        "historical_proof",
        "Sangam to Chola Era",
        "Boiled leather armor (mey-maravadi) and elephant trappings were manufactured from avaram-cured ox hides.",
        "Silappadikaram Vanchikandam"
    ],
    [
        "char-ranipet-master-vegetal-tanner-and-currier-thol-vinaignan",
        "operates_in",
        "place-ranipet-ancient-palar-basin-leather-tannery-haven",
        "historical_proof",
        "Medieval Chola Era",
        "Master tanners operated large brick-lined tanning vat networks along the sandy banks of the Palar at Ranipet.",
        "Palar Basin Guild Roll Records"
    ],
    [
        "char-ranipet-master-vegetal-tanner-and-currier-thol-vinaignan",
        "perfects_process",
        "concept-avaram-bark-and-kadukkai-vegetal-tanning-protocols-thol-padaniduthal",
        "historical_proof",
        "Medieval Chola Era",
        "The master tanner formulated precise sequential enzyme and polyphenol baths using seasonal avaram bark.",
        "Chola Occupational Register"
    ],
    [
        "char-uraiyur-royal-armory-leather-shield-master-parichai-thalaivan",
        "constructs_armor",
        "concept-multi-layered-water-buffalo-hide-war-bucklers-parichai",
        "historical_proof",
        "Sangam to Early Chola Era",
        "The royal armory shield master designed and ballistic-proofed laminated water-buffalo parichai bucklers.",
        "Uraiyur Armory Excavation Reports"
    ],
    [
        "insc-ranipet-palar-basin-leather-guild-and-tannery-endowments",
        "attests_place",
        "place-ranipet-ancient-palar-basin-leather-tannery-haven",
        "historical_proof",
        "Medieval Chola Era",
        "Medieval Chola epigraphs confirm the presence of chartered leatherworking guilds and tanning vats along the Palar river.",
        "South Indian Inscriptions Vol XIII"
    ],
    [
        "insc-uraiyur-chola-military-leather-shield-armory-charters",
        "regulates_production",
        "concept-multi-layered-water-buffalo-hide-war-bucklers-parichai",
        "historical_proof",
        "Early Chola to Imperial Era",
        "Uraiyur charters stipulate strict ballistic testing standards for infantry parichai bucklers before deployment.",
        "Epigraphia Carnatica & Chola Military Epigraphs"
    ],
    [
        "place-ranipet-ancient-palar-basin-leather-tannery-haven",
        "preserves_heritage",
        "concept-water-resistant-leather-water-skins-and-smithing-bellows-thuruthi",
        "historical_proof",
        "Sangam to Modern Era",
        "Ranipet maintains the uninterrupted artisanal heritage of vegetable tanning, water skins, and industrial leather crafting.",
        "Palar Valley Industrial Heritage Survey"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Leatherworking & War Shields into Moolam Chronicles & Life Graph...")

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
                properties = EXCLUDED.properties,
                created_at = NOW();
        """, (
            str(uuid.uuid4()),
            slug,
            d["category"],
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["summary_en"],
            d["summary_ta"],
            d["sources"],
            "historical_proof",
            props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Relational Cross-Domain Edges
    print(f"\n[Phase 3] Inserting {len(EDGES)} Relational Cross-Domain Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges 
            WHERE source_slug = %s AND target_slug = %s AND relation_type = %s;
        """, (src, tgt, rel))

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

    print(f"\n🎉 Ancient Tamil Leatherworking & War Shields Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
