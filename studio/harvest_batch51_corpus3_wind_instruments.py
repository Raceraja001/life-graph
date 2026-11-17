#!/usr/bin/env python3
"""
Harvester: Batch 51 - Ancient Tamil Conical Bore Wind Instruments, Acha-Maram Nagaswaram Turning, Seevali Reed Acoustics & Brass Kombu-Tharai Craft
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
        "slug": "text-silappadikaram-kurinjippattu-and-chola-inscriptions-on-vangiyam-kuzhal-kombu-and-nagaswaram",
        "category": "text",
        "file": "text-silappadikaram-kurinjippattu-and-chola-inscriptions-on-vangiyam-kuzhal-kombu-and-nagaswaram.md",
        "name_en": "Silappadikaram, Kurinjippattu & Chola Inscriptions on Vangiyam, Kuzhal, Kombu & Nagaswaram",
        "name_ta": "சிலப்பதிகாரம், குறிஞ்சிப்பாட்டு மற்றும் சோழர் கல்வெட்டுகளில் வங்கியம், குழல், கொம்பு, நாகஸ்வரம்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Classical Tamil literary and epigraphical records in Kurinjippattu, Perumpanarruppadai, Silappadikaram (Arangerrukathai & Aychiyar Kuravai), Tirukkural, and medieval temple inscriptions documenting bamboo flutes (vangiyam / kuzhal), crescent horns (kombu), straight trumpets (tharai / kalam), and conical reed shawms (nagaswaram).",
        "summary_ta": "குறிஞ்சிப்பாட்டு, பெரும்பாணாற்றுப்படை, சிலப்பதிகாரம், திருக்குறள் மற்றும் கோவில் கல்வெட்டுகளில் பதிவு செய்யப்பட்டுள்ள வங்கியம் (புல்லாங்குழல்), கொம்பு, தாரை, காளம் மற்றும் நாகஸ்வர இசைக்கருவிகள்.",
        "sources": [
            "Silappadikaram Arangerrukathai & Aychiyar Kuravai",
            "Perumpanarruppadai",
            "Kurinjippattu",
            "Tirukkural (Couplet 728)",
            "South Indian Inscriptions"
        ],
        "content": "# Silappadikaram, Sangam Literature & Inscriptions on Wind Instruments\n\nClassical Tamil treatises classify wind instruments (*Thulai-Karuvigal*) as the acoustic foundation of vocal and string tuning:\n\n**Literary & Epigraphical Attestations:**\n- **Sangam Vangiyam & Silappadikaram Kuzhal**: *Perumpanarruppadai* details how pastoral *Kovalar* flute-makers bored equidistant holes into fire-seasoned bamboo tubes using a glowing firebrand (*eriyul-thulai*) to craft the *Vangiyam* (*Kuzhal*). In *Silappadikaram* (*Arangerrukathai* and *Aychiyar Kuravai*), the *Kuzhal-Asiriyan* masters *Konrai*, * Mullai*, and *Aambal* flutes and establishes the tonic pitch that the *Yazh* harp follows.\n- **Kombu, Tharai & Medieval Nagaswaram**: *Tevaram* hymns and Chola/Vijayanagara inscriptions record temple bands sounding curved brass horns (*kombu*), straight trumpets (*kalam*, *tharai*, *ekkalam*), and double-reed conical shawms (*timiri* and *nagaswaram*)."
    },
    {
        "slug": "concept-conical-woodwind-bore-standing-wave-acoustics-and-keyless-gamaka-embouchure",
        "category": "concept",
        "file": "concept-conical-woodwind-bore-standing-wave-acoustics-and-keyless-gamaka-embouchure.md",
        "name_en": "Conical Bore Standing-Wave Acoustics, Seevali Reed Coupling & Keyless Gamaka Pitch Bending",
        "name_ta": "கூம்பு வடிவக் குழல் ஒலி அலை இயற்பியல், சீவாளி அதிர்வு மற்றும் விசையின்றி கமகம் இசைக்கும் நுட்பம்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Aero-acoustic physics of the Tamil Nagaswaram: coupling a pressure-controlled double reed (seevali) to a diverging conical hardwood bore so the standing wave supports both even and odd harmonics (overblowing at the octave), while embouchure lip damping and breath pressure bend pitches continuously across two and a half octaves.",
        "summary_ta": "நாகஸ்வரத்தின் கூம்பு வடிவ உள்துளை மற்றும் இரட்டைச் சீவாளி இணையும்போது இரட்டை மற்றும் ஒற்றைப்படை அதிர்வெண்கள் உருவாகும் ஒலி இயற்பியலும், உதட்டு அழுத்தம் மற்றும் மூச்சுக் கட்டுப்பாட்டால் கமகங்களை இசைக்கும் முறையும்.",
        "sources": [
            "Benade Fundamentals of Musical Acoustics (Conical Double-Reed Horns)",
            "C.V. Raman & Indian Musical Instruments Acoustics",
            "Sambamurthy South Indian Music: The Nagaswaram"
        ],
        "content": "# Conical Bore Acoustics & Keyless Gamaka Embouchure\n\nThe intense outdoor carrying power ($>100\\text{ dB}$ across temple streets) and vocal microtonal agility of the *Nagaswaram* arise from the nonlinear coupling of its double reed (*seevali*) with a steeply flaring conical bore:\n\n**Aero-Acoustic Principles:**\n- **Complete Harmonic Series of a Truncated Cone**: Unlike a cylindrical reed pipe (which behaves as a closed-open quarter-wave resonator producing only odd harmonics $f, 3f, 5f$ and overblowing at the twelfth), a diverging conical bore terminated at its narrow apex by the compliant *seevali* reed supports spherical pressure waves with both even and odd harmonics ($f, 2f, 3f, 4f\\dots$), overblowing cleanly at the octave ($2f$).\n- **Keyless Microtonal Gamakas**: Because the wide double reed is held freely between the lips without a rigid key-work mechanism, the player modulates intra-oral blowing pressure and partial finger-hole shading (*arai-thulai*) to execute sweeping *kampita* and *jaru* pitch slides."
    },
    {
        "slug": "concept-hardwickia-binata-acha-maram-century-seasoning-density-and-acoustic-impedance",
        "category": "concept",
        "file": "concept-hardwickia-binata-acha-maram-century-seasoning-density-and-acoustic-impedance.md",
        "name_en": "Hardwickia binata (Acha-Maram) Century-Seasoned Heartwood Density & Acoustic Impedance",
        "name_ta": "நூறாண்டு பழமையான ஆச்சா மரக் கட்டையின் அடர்த்தி மற்றும் ஒலி எதிர்ப்புத் திறன் அறிவியல்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Materials science of the timber pair used in the Nagaswaram: ultra-dense, resin-stabilized Hardwickia binata (acha-maram, specific gravity >1.1) reclaimed from 70-to-100-year-old heritage house pillars for the high-impedance conical body (ulavu), mated to low-density Ficus religiosa (arasu-maram) for the radiating bell (anasu).",
        "summary_ta": "நூறாண்டு பழமையான வீடுகளின் தூண்களிலிருந்து பெறப்படும் அதிக அடர்த்தி கொண்ட ஆச்சா மரக் குழல் (உளவு) மற்றும் குறைந்த அடர்த்தி கொண்ட அரச மர அணசு ஆகியவற்றின் ஒலி இயற்பியல் பொருத்தம்.",
        "sources": [
            "Geographical Indications Journal: Narasingapettai Nagaswaram",
            "Trotter The Common Commercial Timbers of India (Hardwickia binata)",
            "Organology of South Indian Woodwinds"
        ],
        "content": "# Hardwickia binata (Acha-Maram) Seasoning & Acoustic Impedance\n\nMaster luthiers never carve a *Nagaswaram* from freshly felled green timber; the conical body (*ulavu* or *kuzhal*) is turned exclusively from dark, iron-hard *Acha-Maram* (*Hardwickia binata*) that has seasoned under structural compression for $60$ to $100$ years:\n\n**Timber Physics & Bimaterial Pairing:**\n- **Zero-Creep Century Seasoning**: *Acha-maram* pillars and rafters salvaged from demolished ancestral Chettinad and Thanjavur houses have undergone decades of natural thermal cycling, cross-linking their oleoresins and reducing equilibrium moisture fluctuation to near zero so the thin-walled conical bore never cracks under wet breath condensation.\n- **High Bore Impedance vs. Radiating Bell**: With a dry density of $1080-1150\\text{ kg/m}^3$, the glass-smooth *acha-maram* bore wall reflects internal acoustic energy with minimal viscous boundary-layer damping, whereas the detachable flared bell (*anasu*) is carved from light, porous *Arasu* wood (*Ficus religiosa*, $\\approx 450\\text{ kg/m}^3$) to reduce forward wrist torque."
    },
    {
        "slug": "concept-bari-vs-timiri-nagaswaram-scaling-and-brahma-swaram-wax-tuning-physics",
        "category": "concept",
        "file": "concept-bari-vs-timiri-nagaswaram-scaling-and-brahma-swaram-wax-tuning-physics.md",
        "name_en": "Bari vs. Timiri Nagaswaram Bore Scaling & Five-Hole Brahma-Swaram Wax Tuning Physics",
        "name_ta": "பாரி மற்றும் திமிரி நாகஸ்வர நீள அளவீடும் ஐந்து பிரம்மஸ்வர மெழுகுத் துளை சுருதி நுட்பமும்",
        "era": "Late Medieval to Modern Era",
        "year_start": 1600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Acoustic scaling and tuning architecture of Tamil double-reed shawms: contrasting the shorter, high-register Timiri-Nagaswaram (fundamental G#/A) with the elongated, baritone Bari-Nagaswaram (fundamental D/D#) perfected in the Kaveri delta, and the five lower vent holes (brahma-swaram) sealed with beeswax to calibrate tonic pitch.",
        "summary_ta": "குட்டை வடிவத் திமிரி நாகஸ்வரத்திற்கும் நீளமான பாரி நாகஸ்வரத்திற்கும் இடையிலான சுருதி வேறுபாடும், அடிப்பாகத்தில் உள்ள ஐந்து பிரம்மஸ்வரத் துளைகளை மெழுகால் அடைத்து ஆதார சுருதியை மாற்றும் நுட்பமும்.",
        "sources": [
            "P. Sambamurthy Catalogue of Musical Instruments in the Madras Government Museum",
            "Thiruvavaduthurai Rajarathnam Pillai & Bari Nagaswaram History",
            "Acoustics of Vent Holes in Conical Woodwinds"
        ],
        "content": "# Bari vs. Timiri Scaling & Brahma-Swaram Wax Tuning\n\nThe evolution of the Tamil *Nagaswaram* features a decisive acoustic shift in bore length and an ingenious non-mechanical tonic-calibration system:\n\n**Scaling & Acoustic Venting:**\n- **Timiri vs. Bari Bore Geometry**: The older *Timiri-Nagaswaram* ($\\approx 48\\text{ cm}$ long) pitched at *Aindhu-Kattai* ($G\\sharp_4 / A_4$) produced a piercing, high-register tone suited to open battlefields and windy streets. In the early twentieth century, Narasingapettai luthiers and virtuosos such as Thiruvavaduthurai Rajarathnam Pillai lengthened the bore by $15\\text{ cm}$ into the *Bari-Nagaswaram* ($\\approx 63\\text{ cm}$, pitched at *Irandu* or *Moonru-Kattai*, $D_4 / E_4$), imparting a deep, vocal baritone timbre.\n- **Twelve-Hole Architecture & Brahma-Swaram**: Along the *acha-maram* body, seven upper holes (*sapta-swaram*) are fingered by the player, while five additional holes drilled near the lower flare (*Brahma-Swaram* or *Aradhara-Thulai*) are left open or selectively plugged with beeswax (*mezhugu*) to trim the effective acoustic cutoff length."
    },
    {
        "slug": "technology-narasingapettai-bow-lathe-turning-and-graduated-thamar-conical-auger-boring",
        "category": "technology",
        "file": "technology-narasingapettai-bow-lathe-turning-and-graduated-thamar-conical-auger-boring.md",
        "name_en": "Narasingapettai Two-Man Lathe Turning & Graduated Thamar Spoon-Auger Conical Boring",
        "name_ta": "நரசிங்கப்பேட்டை இருவர் இழுப்புக் கடைசல் மற்றும் தமர் துளைக்கருவி கூம்புத் துளையிடல் நுட்பம்",
        "era": "Chola to Modern Era",
        "year_start": 1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Traditional wood-working technology of Narasingapettai Nagaswaram makers: turning the outer conical frustum of seasoned acha-maram on a horizontal rope-pull lathe, boring the internal tapered channel using a set of eight graduated iron spoon-augers (thamar), and precision-burning the twelve acoustic tone and vent holes.",
        "summary_ta": "பழமையான ஆச்சா மரக் கட்டையைக் கடைசல் பட்டறையில் வெளிப்புறம் செதுக்கி, எட்டு விதமான 'தமர்' இரும்புத் துளைப்பான்களால் உட்புறக் கூம்புத் துளையிட்டு, பன்னிரண்டு ஸ்வரத் துளைகள் இடும் நரசிங்கப்பேட்டைத் தொழில்நுட்பம்.",
        "sources": [
            "GI Application No. 433: Narasingapettai Nagaswaram Technical Dossier",
            "Ethnography of Ranganathan Achari & Narasingapettai Luthiers",
            "Craft Documentation of Thanjavur Musical Instrument Makers"
        ],
        "content": "# Narasingapettai Lathe Turning & Thamar Conical Auger Boring\n\nCarving a geometrically true internal cone through rock-hard *acha-maram* without splitting the $6\\text{ mm}$ wall requires a multi-stage boring protocol preserved by the *Achari* artisans of Narasingapettai:\n\n**Luthier Machining Sequence:**\n- **Two-Man Rope-Lathe Turning**: A square billet of aged *acha-maram* is mounted between iron centers on a floor-level wooden lathe (*kadai-maram*). While an assistant pulls a leather or coir strap back and forth to rotate the workpiece, the master luthier shapes the exterior taper with heavy gouges (*uli*).\n- **Graduated Thamar Spoon-Augers**: A pilot hole is drilled longitudinally from both ends to meet at the center. The artisan then reams the interior using a sequence of eight progressively wider, tapered iron spoon-augers (*thamar*) lubricated with castor oil, creating a mirror-smooth conical bore expanding from $6\\text{ mm}$ at the top receiver (*mel-anaichu*) to $28\\text{ mm}$ at the bell socket."
    },
    {
        "slug": "technology-korkai-tattai-reed-paddy-curing-seevali-shaping-and-brass-kombu-brazing",
        "category": "technology",
        "file": "technology-korkai-tattai-reed-paddy-curing-seevali-shaping-and-brass-kombu-brazing.md",
        "name_en": "Korkai-Tattai Reed Granary Curing, Seevali Double-Reed Binding & Sheet-Brass Kombu Brazing",
        "name_ta": "கொற்கைத் தட்டை நாணல் நெற்களஞ்சியப் பதப்படுத்துதல், சீவாளி தயாரிப்பு மற்றும் பித்தளைக் கொம்பு பற்றவைப்பு",
        "era": "Ancient to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Botanical reed-making and brass horn-smithing technologies: curing Phragmites karka (korkai-tattai) river reed inside warm paddy granaries for twelve months, boiling in rice-water, scraping and flattening into vibrating seevali double reeds tied to brass kandai staples, alongside sheet-brass hammering and silver-brazing of curved kombu horns.",
        "summary_ta": "ஆற்றுக் கொற்கைத் தட்டை நாணலை ஓராண்டு நெற்களஞ்சியத்தில் புதைத்துப் பதப்படுத்தி, அரிசி நீரில் வேகவைத்துச் சீவாளி செய்யும் நுட்பமும், பித்தளைத் தகடுகளை வளைத்துப் பற்றவைத்துக் கொம்பு, தாரை செய்யும் முறையும்.",
        "sources": [
            "Botany and Acoustics of Phragmites karka (Seevali Reed) in Tamil Nadu",
            "Kumbakonam & Nachiyarkoil Brass Wind Instrument Makers Survey",
            "Traditional Reed-Making Craft of the Kaveri Delta"
        ],
        "content": "# Korkai-Tattai Reed Curing, Seevali Shaping & Brass Kombu Brazing\n\nThe voice of the *Nagaswaram* resides in its tiny $2.5\\text{ cm}$ double reed (*Seevali*), while the outdoor roar of the *Kombu* and *Tharai* relies on thin-gauge sheet-brass smithing:\n\n**Reed & Horn Fabrication:**\n- **Paddy-Granary Curing of Korkai-Tattai**: Hollow culms of river reed (*Korkai-Tattai* or *Perun-Naanal*, *Phragmites karka*) harvested along the Kaveri and Kollidam banks are buried deep inside household paddy storage bins (*nel-kudhir*) for $10-12$ months, where constant dry warmth cures the vascular bundles without brittle cracking.\n- **Seevali Scraping & Kandai Binding**: A short reed cylinder is boiled in rice-starch water, split, scraped razor-thin on the inside, steamed, and pressed flat with a horn folder into twin vibrating lips tied with waxed cotton thread onto a conical brass tube (*kandai*).\n- **Sheet-Brass Kombu Brazing**: Braziers cut curved gores of $20\\text{-gauge}$ brass sheet, hammer them over lead/pitch mandrels into tapered tubes, braze the longitudinal seam with copper-zinc solder (*podi-vaithal*), and fit three interlocking curved sections into the crescent *Pirai-Kombu*."
    },
    {
        "slug": "artifact-bari-nagaswaram-ottu-drone-pipe-and-ivory-bodkin-seevali-reed-sets",
        "category": "artifact",
        "file": "artifact-bari-nagaswaram-ottu-drone-pipe-and-ivory-bodkin-seevali-reed-sets.md",
        "name_en": "Bari-Nagaswaram, Hole-Less Ottu Drone Pipe & Ivory Bodkin (Seevali-Kuchchi) Reed Harness",
        "name_ta": "பாரி நாகஸ்வரம், துளையில்லா ஒத்து சுருதிக் குழல் மற்றும் தந்தக் குச்சி இணைந்த சீவாளி மாலை",
        "era": "Late Medieval to Modern Era",
        "year_start": 1600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The classical Periya-Melam woodwind artifact pair: the silver-mounted Bari-Nagaswaram fitted with a braided cord carrying spare seevali reeds, brass kandai staples, and a tapered ivory or deer-horn bodkin needle (seevali-kuchchi) for adjusting reed aperture, accompanied by the fingerless conical Ottu drone shawm.",
        "summary_ta": "வெள்ளிப் பூண் கட்டிய பாரி நாகஸ்வரம், அதில் தொங்கும் மாற்றுச் சீவாளிகள், கண்டை மற்றும் சீவாளி வாயைத் திறக்கும் தந்தக் குச்சி (தந்த ஊசி), அத்துடன் இடைவிடாது ஆதார சுருதி எழுப்பும் 'ஒத்து' கருவி.",
        "sources": [
            "Madras Government Museum Musical Instruments Gallery",
            "DakshinaChitra Heritage Performing Arts Collection",
            "Thanjavur Sarasvati Mahal Library Musicology Manuscripts"
        ],
        "content": "# Bari-Nagaswaram, Ottu Drone Pipe & Ivory Bodkin Harness\n\nA concert or temple *Nagaswaram* rig is a complete portable toolkit engineered for uninterrupted multi-hour outdoor performance:\n\n**Instrument & Accessory Architecture:**\n- **Bari-Nagaswaram & Seevali-Kuchchi Harness**: Attached to the upper silver ferrule (*mel-poon*) of the *acha-maram* body is a decorative braided cotton or silver chain stringing together six to ten pre-soaked spare *seevali* reeds mounted on brass *kandai* staples, alongside a $7\\text{ cm}$ tapered bodkin carved from elephant ivory, deer antler, or silver (*seevali-kuchchi*). Whenever saliva swells a reed shut, the player inserts the bodkin tip between the twin blades to restore the elliptical aperture.\n- **The Fingerless Ottu Drone**: Identical in conical *acha-maram* profile to the *Nagaswaram* but lacking finger-holes (having only lower wax-tuned *brahma-swaram* vents), the *Ottu* is played with continuous circular breathing (*வாங்கல் மூச்சு*) to sustain an unwavering tonic drone."
    },
    {
        "slug": "artifact-pirai-kombu-s-kombu-brass-horns-and-nedun-tharai-temple-trumpets",
        "category": "artifact",
        "file": "artifact-pirai-kombu-s-kombu-brass-horns-and-nedun-tharai-temple-trumpets.md",
        "name_en": "Pirai-Kombu Crescent Horns, S-Curved Thuthari Bugles & Nedun-Tharai Straight Brass Trumpets",
        "name_ta": "பிறைக் கொம்பு, எஸ்-வடிவத் துத்தாரி மற்றும் நெடுந்தாரை-எக்காளம் பித்தளை ஊதுகருவிகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Ceremonial lip-reed brass and bronze horns of Tamil Nadu: the three-piece crescent Pirai-Kombu braced with tension rods, the serpentine S-Kombu (Thuthari / Nagapani), and the two-meter straight telescoping Tharai and Ekkalam trumpets sounded at temple Deeparadhana, deity processions, and heroic proclamations.",
        "summary_ta": "மூன்று துண்டுகளாகப் பொருத்தப்படும் பிறை வடிவப் பித்தளைக் கொம்பு, பாம்பு போல் வளைந்த எஸ்-கொம்பு (துத்தாரி) மற்றும் ஆலய தீபாராதனை, வீதி உலாக்களில் முழங்கும் நீண்ட தாரை, எக்காளம்.",
        "sources": [
            "P. Sambamurthy Catalogue of Musical Instruments in the Government Museum Madras",
            "Chola & Nayak Temple Reliefs of Kombu and Tharai Players",
            "Folklore & Ritual Brass Instruments of Tamil Nadu"
        ],
        "content": "# Pirai-Kombu Crescent Horns, S-Kombu & Nedun-Tharai Trumpets\n\nAlongside double-reed woodwinds, Tamil temple and folk rituals deploy natural brass labrosones (lip-vibrating horns) that sound the upper natural overtone partials ($3\\text{rd}$ to $8\\text{th}$ harmonics):\n\n**Horn & Trumpet Typology:**\n- **Pirai-Kombu & S-Kombu**: Assembled from three curved, tapering sleeves of hammered brass joined by friction sockets (*மூட்டு*) and stabilized across the arc by a decorative brass tension strut (*kambi*) hung with jingle bells. Held high toward the sky and blown through an integral cup mouthpiece, pairs of *Pirai-Kombu* (crescent) and *S-Kombu* (*Thuthari*) exchange antiphonal fanfare calls ahead of temple chariots.\n- **Nedun-Tharai & Ekkalam**: Measuring $1.8-2.4\\text{ m}$ in length, the *Tharai* is a slender, straight cylindrical-conical brass trumpet made in two or three telescoping tubes ending in a wide lotus-rimmed bell, always played in pairs (*Tharai-Thappattai*)."
    },
    {
        "slug": "institution-periya-melam-isai-vellalar-temple-guilds-and-narasingapettai-achari-artisans",
        "category": "institution",
        "file": "institution-periya-melam-isai-vellalar-temple-guilds-and-narasingapettai-achari-artisans.md",
        "name_en": "Periya-Melam Temple Music Guilds, Mallari Processional Liturgy & Narasingapettai Achari Lineages",
        "name_ta": "ஆலயப் பெரிய மேளம் இசை மரபு, மல்லாரி ஊர்வல முறைமை மற்றும் நரசிங்கப்பேட்டை ஆசாரி கலைஞர் குலம்",
        "era": "Chola to Modern Era",
        "year_start": 950,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Dual institutional pillars of the Tamil temple wind tradition: the hereditary Periya-Melam ensemble (Nagaswaram, Ottu, Thavil, and Thalam) holding temple land endowments to perform specific raga-tala liturgies (Rakthi, Mallari, and Tiruppalliyezhuchi) for every ritual hour, and the GI-certified Viswakarma Achari luthier families of Narasingapettai.",
        "summary_ta": "ஆகமக் கோவில்களில் ஆறு கால பூஜை மற்றும் வீதி உலாவில் மல்லாரி இசைக்கும் 'பெரிய மேளம்' இசைக் கலைஞர் அமைப்பும், புவிசார் குறியீடு பெற்ற நரசிங்கப்பேட்டை நாகஸ்வர ஆசாரி கலைஞர் குடும்பங்களும்.",
        "sources": [
            "Yoshitaka Terada Temple Music Traditions of South India: Periya Melam",
            "South Indian Inscriptions (Melam-Manyam & Pipers Grants)",
            "Geographical Indications Registry: Narasingapettai Nagaswaram"
        ],
        "content": "# Periya-Melam Temple Guilds & Narasingapettai Achari Lineages\n\nThe survival and acoustic refinement of the *Nagaswaram* rest on an unbroken symbiosis between hereditary temple musicians and hereditary wood-turning artisans:\n\n**Liturgical & Artisanal Institutions:**\n- **The Periya-Melam & Agamic Soundscape**: Endowed with *Melam-Manyam* wet-land grants in Chola, Nayak, and Thanjavur Maratha charters, the *Periya-Melam* ensemble (two *Nagaswarams*, *Ottu* drone, two *Thavil* drums, and *Thalam* cymbals) governs the sonic clock of the temple: playing *Bhupalam* at dawn (*Thirupalliyezhuchi*), vigorous *Mallari* compositions in *Gambhira Nattai* when the deity is lifted onto the shoulders of bearers (*ther-kaal* / *தேர்க்கால்*), and *Neelambari* for the midnight *Palliyarai* chamber.\n- **Narasingapettai Achari Luthier Guild**: Concentrated in a single street of Narasingapettai, descendants of Ranganathan Achari guard the family templates (*alavu-kuchi*) for boring *Bari* and *Timiri* instruments."
    },
    {
        "slug": "place-narasingapettai-ancient-chola-acha-maram-nagaswaram-and-wind-instrument-haven",
        "category": "place",
        "file": "place-narasingapettai-ancient-chola-acha-maram-nagaswaram-and-wind-instrument-haven.md",
        "name_en": "Narasingapettai: Ancient Chola-Delta Acha-Maram Nagaswaram & Seevali Reed Luthier Haven",
        "name_ta": "நரசிங்கப்பேட்டை - காவேரிப் படுகையின் ஆச்சா மர நாகஸ்வரம் மற்றும் சீவாளி உருவாக்கப் பாரம்பரியத் தளம்",
        "era": "Chola to Modern Era",
        "year_start": 1000,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic Kaveri delta village of Narasingapettai (lat 11.0280, lng 79.5120, thinai: marutham) near Kumbakonam and Thiruvavaduthurai in Thanjavur district, world-renowned and Geographical Indication (GI) certified as the cradle of the Bari-Nagaswaram, century-seasoned acha-maram wood-turning, and korkai-tattai seevali reed craft.",
        "summary_ta": "தஞ்சாவூர் மாவட்டம் கும்பகோணம்–திருவாவடுதுறை அருகே அமைந்த நரசிங்கப்பேட்டை (அட்சரேகை 11.0280, தீர்க்கரேகை 79.5120): புவிசார் குறியீடு பெற்ற பாரி நாகஸ்வரம் மற்றும் ஆச்சா மரக் கடைசல் கலையின் தாயகம்.",
        "sources": [
            "Geographical Indications Journal No. 55: Narasingapettai Nagaswaram",
            "Tanjore District Gazetteer: Kumbakonam & Mayavaram Taluks",
            "History of the Thiruvavaduthurai Adheenam & Nagaswaram Patronage"
        ],
        "content": "# Narasingapettai: Acha-Maram Nagaswaram & Wind-Instrument Haven\n\nSituated at latitude $11.0280^\\circ\\text{ N}$, longitude $79.5120^\\circ\\text{ E}$ in the lush *marutham* heartland of the Kaveri delta just $3\\text{ km}$ from the historic *Thiruvavaduthurai Adheenam* monastery near Kumbakonam, the village of Narasingapettai is the supreme center of Tamil woodwind luthiery:\n\n**Geographic & Cultural Ecology:**\n- **Birthplace of the Bari-Nagaswaram**: Working closely with the legendary Nagaswaram maestros patronized by the Thiruvavaduthurai Adheenam and nearby Chola temples, Narasingapettai's master craftsman Ranganathan Achari re-engineered the traditional short *Timiri* pipe into the resonant *Bari-Nagaswaram*, earning a Geographical Indication (GI) tag for the village.\n- **Delta Reed & Heritage Timber Access**: Positioned beside the Kaveri-Kollidam reed beds yielding prime *korkai-tattai* for *seevali* reeds and surrounded by centuries-old delta mansions supplying seasoned *acha-maram* beams, Narasingapettai outfits temple *Periya-Melam* ensembles across the globe."
    }
]

EDGES = [
    [
        "text-silappadikaram-kurinjippattu-and-chola-inscriptions-on-vangiyam-kuzhal-kombu-and-nagaswaram",
        "documents",
        "artifact-pirai-kombu-s-kombu-brass-horns-and-nedun-tharai-temple-trumpets",
        "material_culture",
        "Sangam to Medieval Era",
        "Sangam poems, Tevaram hymns, and Chola inscriptions document bamboo flutes (vangiyam/kuzhal) and ceremonial kombu and tharai brass horns.",
        "Silappadikaram & South Indian Inscriptions"
    ],
    [
        "concept-conical-woodwind-bore-standing-wave-acoustics-and-keyless-gamaka-embouchure",
        "governs",
        "technology-narasingapettai-bow-lathe-turning-and-graduated-thamar-conical-auger-boring",
        "material_culture",
        "Medieval to Modern Era",
        "Spherical standing-wave acoustics in a diverging conical bore govern the graduated thamar spoon-auger reaming of the Nagaswaram interior.",
        "Benade Musical Acoustics & GI Dossier"
    ],
    [
        "concept-hardwickia-binata-acha-maram-century-seasoning-density-and-acoustic-impedance",
        "enables",
        "technology-narasingapettai-bow-lathe-turning-and-graduated-thamar-conical-auger-boring",
        "material_culture",
        "Medieval to Modern Era",
        "Century-seasoned Hardwickia binata (acha-maram) heartwood provides zero-creep dimensional stability and high acoustic impedance for turning thin conical bores.",
        "Trotter Commercial Timbers of India"
    ],
    [
        "concept-bari-vs-timiri-nagaswaram-scaling-and-brahma-swaram-wax-tuning-physics",
        "guides",
        "artifact-bari-nagaswaram-ottu-drone-pipe-and-ivory-bodkin-seevali-reed-sets",
        "material_culture",
        "Late Medieval to Modern Era",
        "Bari bore elongation and five-hole brahma-swaram beeswax venting guide the pitch calibration of the Bari-Nagaswaram and Ottu drone pipe.",
        "Sambamurthy South Indian Music"
    ],
    [
        "technology-narasingapettai-bow-lathe-turning-and-graduated-thamar-conical-auger-boring",
        "fabricates",
        "artifact-bari-nagaswaram-ottu-drone-pipe-and-ivory-bodkin-seevali-reed-sets",
        "material_culture",
        "Chola to Modern Era",
        "Two-man rope-lathe turning and graduated thamar boring fabricate the acha-maram kuzhal body and arasu-wood anasu bell of the Bari-Nagaswaram.",
        "Narasingapettai GI Technical Dossier"
    ],
    [
        "technology-korkai-tattai-reed-paddy-curing-seevali-shaping-and-brass-kombu-brazing",
        "equips",
        "artifact-bari-nagaswaram-ottu-drone-pipe-and-ivory-bodkin-seevali-reed-sets",
        "material_culture",
        "Ancient to Modern Era",
        "Paddy-cured Phragmites karka (korkai-tattai) stalks are scraped and bound onto brass kandai staples to equip the Nagaswaram with vibrating seevali reeds.",
        "Kaveri Delta Reed Craft Survey"
    ],
    [
        "technology-korkai-tattai-reed-paddy-curing-seevali-shaping-and-brass-kombu-brazing",
        "produces",
        "artifact-pirai-kombu-s-kombu-brass-horns-and-nedun-tharai-temple-trumpets",
        "material_culture",
        "Ancient to Modern Era",
        "Sheet-brass hammering over pitch mandrels and copper-zinc brazing produce three-piece crescent Pirai-Kombu horns and straight Nedun-Tharai trumpets.",
        "Nachiyarkoil & Kumbakonam Brazier Survey"
    ],
    [
        "institution-periya-melam-isai-vellalar-temple-guilds-and-narasingapettai-achari-artisans",
        "performs_with",
        "artifact-bari-nagaswaram-ottu-drone-pipe-and-ivory-bodkin-seevali-reed-sets",
        "material_culture",
        "Chola to Modern Era",
        "Hereditary Periya-Melam temple ensembles perform Mallari processional music and daily Agamic pujas with the Bari-Nagaswaram and Ottu drone.",
        "Terada Temple Music Traditions"
    ],
    [
        "place-narasingapettai-ancient-chola-acha-maram-nagaswaram-and-wind-instrument-haven",
        "hosts",
        "institution-periya-melam-isai-vellalar-temple-guilds-and-narasingapettai-achari-artisans",
        "material_culture",
        "Chola to Modern Era",
        "Narasingapettai near Kumbakonam hosts the GI-certified Viswakarma Achari luthier lineage supplying instruments to Kaveri delta Periya-Melam guilds.",
        "Geographical Indications Journal No. 55"
    ],
    [
        "text-silappadikaram-kurinjippattu-and-chola-inscriptions-on-vangiyam-kuzhal-kombu-and-nagaswaram",
        "contextualizes",
        "place-narasingapettai-ancient-chola-acha-maram-nagaswaram-and-wind-instrument-haven",
        "material_culture",
        "Sangam to Medieval Era",
        "Chola and medieval Kaveri delta temple inscriptions recording reed and horn players contextualize the rise of Narasingapettai's wind-instrument workshops.",
        "South Indian Inscriptions"
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
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s", (slug,))
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
