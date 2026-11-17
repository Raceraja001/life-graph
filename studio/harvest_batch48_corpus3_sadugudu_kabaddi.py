#!/usr/bin/env python3
"""
Harvester: Batch 48 - Ancient Tamil Sadugudu Breath-Hold Tag-Wrestling, Paadi-Kodu Arena Kinematics & Rural Martial Conditioning
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
        "slug": "text-sangam-malyutham-and-tamil-folk-ballads-on-sadugudu-and-paadi-aattam",
        "category": "text",
        "file": "text-sangam-malyutham-and-tamil-folk-ballads-on-sadugudu-and-paadi-aattam.md",
        "name_en": "Sangam Malyutham References & Tamil Folk Ballads on Sadugudu and Paadi-Aattam",
        "name_ta": "சங்க இலக்கிய மல்யுத்தக் குறிப்புகளும் சடுகுடு மற்றும் பாடி ஆட்ட நாட்டுப்புறப் பாடல்களும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 1950,
        "thinai": "marutham",
        "summary_en": "Classical Tamil literary accounts of bare-handed earthen-arena grappling (mallar / malyutham in Kalithogai, Purananuru, and Periapuranam) alongside oral folkloric verse traditions (Sadugudu-Paattu) chanted on a single breath during rural Sadugudu (Chadukudu / Paadi-Aattam) raids.",
        "summary_ta": "கலித்தொகை, புறநானூறு மற்றும் பெரியபுராணத்தில் இடம்பெறும் மற்போர் குறிப்புகளும், கிராமப்புறச் சடுகுடு (சடுகுடுப் பாட்டு, பாடி ஆட்டம்) வீரர்கள் மூச்சு விடாமல் பாடிச் செல்லும் வாய்மொழிப் பாடல் மரபும்.",
        "sources": [
            "Kalithogai & Purananuru",
            "Periapuranam",
            "Devaneya Pavanar Tamil Nattu Vilaiyattukkal",
            "Folk Songs of Tamil Nadu: Sadugudu Paattu"
        ],
        "content": "# Sangam Malyutham & Tamil Folk Ballads on Sadugudu\n\nThe Tamil martial sport of *Sadugudu* (also known regionally as *Chadukudu*, *Paadi-Aattam*, or *Puli-Kulam*, and recognized as the ancestral root of modern *Kabaddi*) unites Sangam-era bare-handed wrestling (*Malyutham*) with rhythmic single-breath verse chanting:\n\n**Literary & Folkloric Attestations:**\n- **Sangam Mallar & Earthen Arenas**: *Purananuru* and *Kalithogai* celebrate village youths (*mallar*) with broad chests scarred by wrestling locks grappling in prepared earthen enclosures (*kalam*), while *Pillai-Tamil* literature alludes to children's boundary-crossing tag games.\n- **Sadugudu-Paattu Oral Couplets**: As codified by linguist Devaneya Pavanar in *Tamil Nattu Vilaiyattukkal*, traditional raiders did not merely repeat a single word; they chanted metrical, boasting folk couplets (*Sadugudu-Paattu*, e.g., *\"நானந்தப் புலிதானடா, நடுக் கோட்டைப் பிடிப்பேனடா...\"*) terminating each line with *\"சடுகுடு சடுகுடு\"* on a single unbroken exhalation."
    },
    {
        "slug": "concept-paaduthal-single-breath-vocal-canting-and-anaerobic-apnea-physiology",
        "category": "concept",
        "file": "concept-paaduthal-single-breath-vocal-canting-and-anaerobic-apnea-physiology.md",
        "name_en": "Paaduthal Single-Breath Vocal Canting & Expiratory Apnea Anaerobic Physiology",
        "name_ta": "பாடுதல் (மூச்சுப் பாட்டு) ஒரு மூச்சு ஒலிப்பு மற்றும் காற்றில்லா உடற்பயிற்சி உடலியல்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Cardiorespiratory physiology of the core Sadugudu rule (paaduthal / canting): maintaining continuous audible laryngeal phonation on a single vital-capacity exhalation while executing explosive anaerobic sprints and wrestling escapes, serving as an unforgeable acoustic proof of non-inhalation.",
        "summary_ta": "எதிரணி எல்லையில் நுழைந்தவுடன் மூச்சை உள்ளிழுக்காமல் ஒரே மூச்சில் சத்தமாகப் பாடிக்கொண்டே (பாடுதல்) தாக்குதல் நடத்தும் சடுகுடு விதியின் சுவாச உடலியல் மற்றும் ஒலிச் சான்று நுட்பம்.",
        "sources": [
            "Exercise Physiology of Kabaddi & Breath-Hold Athletics",
            "Devaneya Pavanar Tamil Nattu Vilaiyattukkal",
            "Indian Journal of Physiology and Pharmacology: Kabaddi Raid Apnea"
        ],
        "content": "# Paaduthal Single-Breath Canting & Anaerobic Apnea Physiology\n\nThe defining physiological constraint of *Sadugudu* (*Paadi-Aattam*, literally \"the game played while singing/canting\") is that a raider crossing the midline (*paadi-kodu*) must audibly vocalize without pause until returning home:\n\n**Respiratory & Acoustic Mechanics:**\n- **Unforgeable Acoustic Bio-Verification**: Because human vocal folds generate clear phonation primarily during controlled expiratory airflow, continuous loud chanting (*paaduthal*) provides referees and defenders with an immediate, non-invasive acoustic proof that the raider has not taken a covert inhalation in enemy territory.\n- **Hypercapnic Tolerance & Laryngeal Metering**: Elite raiders inhale to total lung capacity ($\\approx 5-6\\text{ L}$) just before crossing the *paadi-kodu*, then meter out subglottal air pressure through nasalized syllables (*\"sadugudu-sadugudu\"*) over $20-35\\text{ seconds}$ while resisting violent thoracic compression from multiple tacklers under acute blood lactate and $\\text{CO}_2$ buildup."
    },
    {
        "slug": "concept-seven-defender-chain-geometry-and-nulle-kodu-midline-kinematics",
        "category": "concept",
        "file": "concept-seven-defender-chain-geometry-and-nulle-kodu-midline-kinematics.md",
        "name_en": "Seven-Defender Arc Geometry (Kai-Korthal) & Nulle-Kodu Midline Raid Kinematics",
        "name_ta": "எழுவர் கைகோர்த்தல் வில் வியூக வடிவியலும் நுழைகோடு (பாடிக்கோடு) தாக்குதல் இயக்கவியலும்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Spatial kinematics of the 7-versus-1 Sadugudu encounter: dynamic curvature of the linked-hand defensive arc (kai-korthal) divided into left/right corner ankle-catchers (moolai), covers, and center blockers, pitted against the lone raider's lateral toe-touches, frog-jumps, and midline (nulle-kodu / paadi-kodu) lunges.",
        "summary_ta": "எதிரணியின் ஏழு வீரர்கள் கைகோர்த்து வில் போல் வளைந்து முனை (மூலை), பிடி, நடுக்கட்டு என நிற்கும் தற்காப்பு வியூகமும், தனியொரு பாடிச் செல்பவரின் கால் தொடுதல் மற்றும் நுழைகோடு பாய்ச்சல் இயக்கவியலும்.",
        "sources": [
            "Biomechanics and Tactical Geometry of Kabaddi",
            "Traditional Sports of Tamil Nadu (World Tamil Research Institute)",
            "Rural Sadugudu Coaching & Strategy Manuals"
        ],
        "content": "# Seven-Defender Arc Geometry & Midline Raid Kinematics\n\nA *Sadugudu* raid is an asymmetric dynamical system pitting one mobile attacker against seven defenders connected in linked-wrist chains (*kai-korthal*):\n\n**Positional & Kinematic Structure:**\n- **Catenary Chain Defense (*Arasu-Kattu*)**: The seven defenders form a concave crescent split into two coupled sub-chains (e.g., $2-3-2$ or $3-1-3$): the two extreme wingers (*Moolai* or corners) specialize in low ankle-picks, the adjacent *Inai-Pidi* (covers) deliver blind-side shoulder blocks, and the central trio (*Nadu-Kattu*) close the encirclement trap (*valai-kattu*).\n- **Raider Reach & Nulle-Kodu Lunges**: The raider uses rapid split-step changes of direction to break chain synchronicity, executing Whip-like lateral toe-touches (*kaal-veechu*), vertical frog-vaults (*thavalai-paaychal*) over diving blockers, or full-body horizontal extensions to brush a fingertip across the central *nulle-kodu* (*paadi-kodu*) before pulmonary air runs out."
    },
    {
        "slug": "concept-sanjeevani-and-goongi-traditional-tamil-sadugudu-revival-and-capture-rules",
        "category": "concept",
        "file": "concept-sanjeevani-and-goongi-traditional-tamil-sadugudu-revival-and-capture-rules.md",
        "name_en": "Sanjeevani Resurrection, Goongi & Gaminee: Traditional Tamil Sadugudu Rule Typologies",
        "name_ta": "சஞ்சீவனி (உயிர்ப்பித்தல்), ஊமை ஆட்டம் மற்றும் காமினி: பாரம்பரிய சடுகுடு விதி வகைமைகள்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Traditional rule systems of Tamil village Sadugudu prior to modern federation timers: the Sanjeevani system of sequential player revival upon every successful touch or tackle, the Gaminee total-elimination match format played until all seven defenders are captured, and the Amar/Goongi attrition variant.",
        "summary_ta": "கிராமப்புறச் சடுகுடு ஆட்டத்தின் பாரம்பரிய விதி முறைகள்: ஆட்டமிழந்த வீரர்களை வரிசையாக மீண்டும் உயிர்ப்பிக்கும் சஞ்சீவனி முறை, எழுவரும் பிடிபடும் வரை ஆடும் காமினி முறை மற்றும் அமர் வகைமைகள்.",
        "sources": [
            "History and Standardization of Indian Kabaddi Rules",
            "Devaneya Pavanar Tamil Nattu Vilaiyattukkal",
            "Madras Presidency Physical Education Reports"
        ],
        "content": "# Sanjeevani, Gaminee & Traditional Sadugudu Rule Typologies\n\nAcross the agrarian districts of Tamil Nadu, village *Sadugudu* tournaments historically operated under three distinct rule architectures reflecting symbolic life-death-rebirth mechanics:\n\n**Traditional Match Formats:**\n- **Sanjeevani (Sequential Resurrection)**: Named after the mythical life-restoring herb, whenever a raider tags a defender and crosses the *paadi-kodu* safely—or whenever defenders pin a raider until his breath-canting stops—one previously eliminated player from the scoring side is \"revived\" (*uyir-peruthal*) in strict first-out, first-in queue order. Capturing all seven opponents inflicts a *Lona* (*All-Out*) bonus.\n- **Gaminee (Total Elimination)**: No player is revived during an inning; captured defenders remain in the sitting box (*out-kattam*) until the entire seven-man squad is eliminated, testing extreme endurance as the last one or two defenders face solo raids across a wide earthen court."
    },
    {
        "slug": "technology-sadugudu-kalam-cushioned-red-earth-paddy-ash-and-neem-court-preparation",
        "category": "technology",
        "file": "technology-sadugudu-kalam-cushioned-red-earth-paddy-ash-and-neem-court-preparation.md",
        "name_en": "Sadugudu-Kalam Earthen Court Engineering: Sieved Red Loam, Paddy Ash & Neem Oil-Cake Cushioning",
        "name_ta": "சடுகுடுக் களம் அமைக்கும் நுட்பம்: சலித்த செம்மண், உமிச் சாம்பல் மற்றும் வேப்பம் புண்ணாக்கு மெத்தைத் தரை",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Indigenous geotechnical preparation of the traditional Tamil Sadugudu wrestling pit (sadugudu-kalam): excavating hardpan clay, triple-sieving red earth and river sand to eliminate gravel, and blending burnt paddy-husk ash, powdered neem oil-cake, and turmeric water to create a shock-absorbing, antiseptic surface.",
        "summary_ta": "விழாக் காலச் சடுகுடுப் போட்டிகளுக்காகக் கற்கள் நீக்கிச் சலித்த செம்மண், ஆற்று மணல், உமிச் சாம்பல், வேப்பம் புண்ணாக்கு மற்றும் மஞ்சள் நீர் கலந்து மெத்தென்ற கிருமிநாசினி ஆடுகளம் அமைக்கும் தொழில்நுட்பம்.",
        "sources": [
            "Traditional Kalari & Sadugudu Arena Construction in Tamil Nadu",
            "Ethnography of Rural Sports in Thanjavur and Madurai",
            "Indigenous Soil Mechanics of Indian Wrestling Akharas"
        ],
        "content": "# Sadugudu-Kalam Cushioned Earthen Court Engineering\n\nLong before synthetic foam mats, village youth clubs engineered high-compliance, abrasion-free organic soil arenas (*Sadugudu-Kalam*) capable of absorbing violent high-altitude suplexes and diving tackles:\n\n**Geotechnical Formulation:**\n- **Excavation & Triple Sieving**: A rectangular pit ($13 \\times 10\\text{ m}$) is dug $25-30\\text{ cm}$ deep. Friable red loam (*semman*) and fine alluvial silt (*vandal-mann*) are passed through inclined bamboo mesh screens (*salladai*) to remove every sharp quartz pebble and thorn.\n- **Paddy-Husk Ash & Antiseptic Conditioning**: The sieved soil is blended $3:1$ with carbonized paddy-husk ash (*umi-saambal*) and coir pith, which prevent clay caking and provide elastic shear cushioning. Crushed neem seed cake (*veppam-punnakku*), castor oil dregs, and turmeric water are hoed into the top $10\\text{ cm}$ to suppress tetanus/staphylococcal bacteria and keep skin scrapes clean, then marked with slaked lime (*sunnambu-kodu*)."
    },
    {
        "slug": "technology-kaal-pidi-ankle-picks-muthalai-pidi-crocodile-rolls-and-chain-tackling",
        "category": "technology",
        "file": "technology-kaal-pidi-ankle-picks-muthalai-pidi-crocodile-rolls-and-chain-tackling.md",
        "name_en": "Kaal-Pidi Ankle-Picks, Muthalai-Pidi Crocodile-Rolls & Sangili-Pidi Chain Tackling",
        "name_ta": "கால்பிடி, முதலைப்பிடி சுழற்றுதல் மற்றும் சங்கிலிப்பிடி கூட்டுத் தற்காப்புப் பிடி நுட்பங்கள்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Biomechanical grappling repertoire (pidi-murai) of Tamil Sadugudu defenders: the corner defender's explosive low ankle-pick and heel-lift (kaal-pidi), the spinning crocodile-roll (muthalai-pidi) that redirects a lunging raider away from the midline, waist-and-thigh lifts (iduppu-pidi), and two-man chain traps (sangili-pidi).",
        "summary_ta": "சடுகுடுத் தற்காப்பு வீரர்களின் பிடி நுட்பங்கள்: மூலை வீரரின் கணுக்கால் பிடி (கால்பிடி), பாடிக்கோட்டைத் தொட விடாமல் சுழற்றி வீழ்த்தும் முதலைப்பிடி, இடுப்புப் பிடி மற்றும் சங்கிலிப்பிடி.",
        "sources": [
            "Tamil Martial Arts & Malyutham Grappling Manuals",
            "Technical Biomechanics of Kabaddi Defensive Holds",
            "Oral Coaching Traditions of Southern Tamil Nadu Sadugudu Clubs"
        ],
        "content": "# Kaal-Pidi Ankle-Picks, Muthalai-Pidi & Chain Tackling\n\nBecause a *Sadugudu* defender must immobilize a sprinting raider within seconds without strikes or chokes, rural coaches refined a specialized arsenal of leverage holds (*Pidi-Murai*):\n\n**Grappling Mechanics:**\n- **Kaal-Pidi (Corner Ankle-Pick & Lift)**: As the raider shifts weight onto his lead foot to execute a toe-touch, the corner defender drops onto one knee, cups the calcaneus (heel) and Achilles tendon with both palms locked, and drives his shoulder into the raider's shin while lifting upward—uprooting the raider's ground reaction force vector.\n- **Muthalai-Pidi (Crocodile Death-Roll)**: When a powerful raider dives headfirst toward the *paadi-kodu*, a static block fails; the defender clamps around the raider's ankles or waist and executes a rapid $360^\\circ$ axial barrel-roll (*muthalai-urulai*), using angular momentum to swing the raider's outstretched arms laterally away from the midline while the remaining chain (*sangili-pidi*) piles on."
    },
    {
        "slug": "artifact-theevatti-oil-torches-lime-marker-horns-and-sandal-paste-victory-shields",
        "category": "artifact",
        "file": "artifact-theevatti-oil-torches-lime-marker-horns-and-sandal-paste-victory-shields.md",
        "name_en": "Theevatti Arena Oil-Torches, Sunnambu Lime-Horns, Komanam Loincloths & Victory Shields",
        "name_ta": "தீவட்டிப் பந்தங்கள், சுண்ணாம்புக் கோட்டுக் குழாய்கள், இறுக்கக் கோமணம் மற்றும் வெற்றிக் கேடயங்கள்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 1980,
        "thinai": "marutham",
        "summary_en": "Material artifacts of the traditional nocturnal Tamil Sadugudu arena: tall iron-casket oil torches (theevatti) fed with castor/iluppai oil at the four court corners, perforated lime-powder horns for renewing the paadi-kodu midline, tightly bound unbleached cotton loincloths (komanam / langot), and repoussé brass championship shields (kedayam).",
        "summary_ta": "இரவு நேரச் சடுகுடுக் களத்தின் நான்கு மூலைகளிலும் எரியும் இலுப்பெண்ணெய்த் தீவட்டிகள், பாடிக்கோடு போடும் சுண்ணாம்புக் குழாய், வீரர்களின் இறுக்கமான பருத்திக் கோமணம் (லங்கோடு) மற்றும் வெற்றிக் கேடயங்கள்.",
        "sources": [
            "Folklore Museum Collections of Tamil Rural Sports",
            "Thanjavur & Pudukkottai District Gazetteers",
            "Material Culture of Traditional South Indian Athletics"
        ],
        "content": "# Theevatti Oil-Torches, Lime-Horns & Victory Shields\n\nBecause daytime agricultural labor and intense tropical sun restricted matches to the cool night hours, historical village *Sadugudu* tournaments relied on distinctive nocturnal arena apparatus:\n\n**Arena & Athlete Artifacts:**\n- **Theevatti Corner Torches**: Four to eight tall wrought-iron braziers or tightly wound cotton-rag torches (*theevatti*) mounted on bamboo standards were planted around the court perimeter and continuously fed with *iluppai* (*Madhuca longifolia*) or castor oil from brass spouted cans (*thoppai*), casting dramatic flickering illumination across the red-earth pit (later supplemented by hanging *Petromax* mantle lamps).\n- **Tightly Bound Komanam (*Langot*)**: To deny opponents any fabric grip and protect against inguinal hernia during heavy lifts, players wore only a triangular strip of thick handwoven unbleached cotton (*komanam* or *langot*) cinched tightly around the waist-cord (*araignan-kayiru*) and smeared their limbs with dry earth (*mann-poochu*) to absorb sweat."
    },
    {
        "slug": "artifact-kida-parisu-champion-fighting-rams-and-kal-eluthu-stone-conditioning-weights",
        "category": "artifact",
        "file": "artifact-kida-parisu-champion-fighting-rams-and-kal-eluthu-stone-conditioning-weights.md",
        "name_en": "Kida-Parisu Tournament Prize Rams, Kal-Eluthu Grip-Stones & Karlakattai Clubs",
        "name_ta": "கிடாப் பரிசு (வெற்றி ஆட்டுக்கிடா), கல் எடுத்தல் தூக்குக் கற்கள் மற்றும் கர்லாக்கட்டை உடற்பயிற்சி",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Trophy and conditioning artifacts of rural Tamil Sadugudu culture: the coveted first-prize horned ram (kida-parisu / vettri-kida) tethered beside the arena stage with garland and turmeric honours, alongside carved granite spherical/ring lifting stones (thookku-kal) and heavy rosewood swinging clubs (karlakattai) used for grip and shoulder conditioning.",
        "summary_ta": "சடுகுடுப் போட்டியின் முதல் பரிசாக வழங்கப்படும் கொம்பு சுற்றிய ஆட்டுக்கிடா (கிடாப் பரிசு) மற்றும் வீரர்களின் விரல் பிடி, தோள் வலிமையைப் பெருக்கும் தூக்குக் கற்கள், கர்லாக்கட்டைப் பயிற்சி.",
        "sources": [
            "Ethnography of Village Festival Prizes in Tamil Nadu",
            "Traditional Physical Culture of South India: Kal-Eluthu and Karlakattai",
            "Madurai & Ramanathapuram Folk Sports Surveys"
        ],
        "content": "# Kida-Parisu Prize Rams & Stone Conditioning Weights\n\nIn traditional Tamil village *Sadugudu* championships, prestige and physical preparation revolved around iconic pastoral trophies and lithic gymnasium implements:\n\n**Trophies & Conditioning Apparatus:**\n- **Kida-Parisu (The Champion's Ram)**: Rather than cash alone, the supreme trophy of a regional *Sadugudu* tournament is a massive, spiral-horned native ram (*Vettri-Kida* of the *Kilakkarisal*, *Vembur*, or *Mecheri* breed), rubbed with sandalwood paste, crowned with a marigold garland and silk shawl (*parivattam*), and tethered prominently on a raised platform beside the court throughout the night to inspire the contenders.\n- **Granite Grip-Stones (*Thookku-Kal*) & Karlakattai**: To forge the vice-like finger and wrist strength needed for *kaal-pidi* ankle catches, village gymnasiums (*kalari*) maintain smooth spherical boulders ($40-100\\text{ kg}$) and undercut stone rings lifted with fingertips, paired with heavy turned *vengai*-wood clubs (*karlakattai*)."
    },
    {
        "slug": "institution-village-sadugudu-kazhagam-clubs-and-panguni-nocturnal-tournament-committees",
        "category": "institution",
        "file": "institution-village-sadugudu-kazhagam-clubs-and-panguni-nocturnal-tournament-committees.md",
        "name_en": "Village Sadugudu-Kazhagam Clubs, Naduvar Referees & Panguni Festival Tournament Committees",
        "name_ta": "கிராமப்புறச் சடுகுடுக் கழகங்கள், நடுவர் பஞ்சாயத்து மற்றும் பங்குனித் திருவிழா இரவுப் போட்டிக் குழுக்கள்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Communal athletic institutions organizing Tamil rural Sadugudu: intergenerational village youth clubs (Sadugudu-Kazhagam) training on moonlit threshing floors, respected retired veterans serving as neutral referees (Naduvar) monitoring continuous breath-canting, and post-harvest Panguni-Chithirai temple festival committees hosting multi-night inter-village knockouts.",
        "summary_ta": "களத்துமேடுகளில் பயிற்சி பெறும் கிராமச் சடுகுடுக் கழகங்கள், மூச்சுப் பாட்டையும் கோட்டுத் தொடுதலையும் துல்லியமாகக் கண்காணிக்கும் மூத்த நடுவர்கள் மற்றும் பங்குனி-சித்திரைத் திருவிழா இரவுப் போட்டிக் குழுக்கள்.",
        "sources": [
            "Sociology of Rural Sports & Youth Associations in Tamil Nadu",
            "Thanjavur & Pudukkottai Village Festival Records",
            "Amateur Kabaddi Federation of Tamil Nadu Historical Souvenirs"
        ],
        "content": "# Village Sadugudu-Kazhagam Clubs & Nocturnal Tournament Committees\n\nAcross rural Tamil Nadu, *Sadugudu* is governed by self-organized village athletic fraternities deeply interwoven with the agrarian calendar:\n\n**Institutional Governance:**\n- **Moonlit Threshing-Floor Training (*Kalathu-Medu*)**: Following the *Thai* and *Maasi* paddy harvest, village *Sadugudu-Kazhagam* clubs convene every evening on the cleared communal threshing floor (*kalathu-medu*) or river sandbed (*aarru-manal*), where veteran captains drill younger cohorts in synchronized chain rotation and single-breath stamina.\n- **Naduvar Refereeing & Festival Knockouts**: During *Panguni* and *Chithirai* guardian-deity (*Ayyanar* and *Mariamman*) festivals, village committees send printed palm-leaf or paper invitations across $30-50$ neighboring settlements. Neutral elder referees (*Naduvar*) stand directly astride the *paadi-kodu* midline, listening intently for the slightest break in the raider's vocal *paaduthal* cant."
    },
    {
        "slug": "place-peravurani-ancient-chola-sadugudu-arena-and-martial-athletics-haven",
        "category": "place",
        "file": "place-peravurani-ancient-chola-sadugudu-arena-and-martial-athletics-haven.md",
        "name_en": "Peravurani: Ancient Chola-Coast Sadugudu Arena, Nocturnal Tournament & Martial Athletics Haven",
        "name_ta": "பேராவூரணி - சோழ நாட்டுச் சடுகுடு ஆடுகளங்கள் மற்றும் இரவு நேரப் பெருந்தொடர்ப் போட்டிகளின் தளம்",
        "era": "Chola to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic agrarian-coastal hub of Peravurani (lat 10.2950, lng 79.1960, thinai: marutham) in the southern Thanjavur–Pattukkottai–Pudukkottai belt, renowned across Tamil Nadu for its dense network of legendary village Sadugudu (Kabaddi) clubs, cushioned red-soil and coconut-coir arenas, and massive multi-night festival tournaments.",
        "summary_ta": "தஞ்சாவூர்–பட்டுக்கோட்டை–புதுக்கோட்டை மருத நிலப் பகுதியில் அமைந்த பேராவூரணி (அட்சரேகை 10.2950, தீர்க்கரேகை 79.1960): பாரம்பரிய சடுகுடுக் கழகங்கள், செம்மண்-தென்னை நார் ஆடுகளங்கள் மற்றும் இரவுப் போட்டிகளின் புகழ்பெற்ற தளம்.",
        "sources": [
            "Tanjore District Gazetteer: Pattukkottai & Peravurani Taluks",
            "Tamil Nadu State Kabaddi Championship Archives",
            "Ethnography of Agni-Aaru and Southern Kaveri Delta Athletics"
        ],
        "content": "# Peravurani: Chola-Coast Sadugudu Arena & Martial Athletics Haven\n\nSituated at latitude $10.2950^\\circ\\text{ N}$, longitude $79.1960^\\circ\\text{ E}$ in the southern *marutham* plains between the Agniyar river basin and the Palk Strait coast of Thanjavur district, Peravurani and its surrounding cluster of villages (along the Pattukkottai–Aranthangi–Pudukkottai corridor) form the historic heartland of Tamil *Sadugudu*:\n\n**Regional Athletic Ecology:**\n- **Red-Earth & Coir-Cushioned Arenas**: Enriched by both friable upland red loam and abundant coconut-husk coir pith (*thennai-naar*) from the region's vast coconut groves, Peravurani's village arenas developed uniquely resilient, non-abrasive *sadugudu-kalam* pits.\n- **Nursery of Champion Seven-Man Squads**: For generations, every hamlet around Peravurani has maintained dedicated floodlit and torchlit *Sadugudu* grounds where post-harvest tournaments attract tens of thousands of spectators through the night, producing national-level raiders and corner defenders."
    }
]

EDGES = [
    [
        "text-sangam-malyutham-and-tamil-folk-ballads-on-sadugudu-and-paadi-aattam",
        "documents",
        "concept-paaduthal-single-breath-vocal-canting-and-anaerobic-apnea-physiology",
        "material_culture",
        "Sangam to Modern Era",
        "Tamil folk ballads (Sadugudu-Paattu) and Devaneya Pavanar's treatises document rhythmic single-breath vocal canting during raids.",
        "Tamil Nattu Vilaiyattukkal"
    ],
    [
        "concept-paaduthal-single-breath-vocal-canting-and-anaerobic-apnea-physiology",
        "constrains",
        "concept-seven-defender-chain-geometry-and-nulle-kodu-midline-kinematics",
        "material_culture",
        "Ancient to Modern Era",
        "Expiratory apnea duration under continuous vocal paaduthal strictly constrains the raider's time-on-court and midline lunge window.",
        "Kabaddi Exercise Physiology"
    ],
    [
        "concept-seven-defender-chain-geometry-and-nulle-kodu-midline-kinematics",
        "governs",
        "technology-kaal-pidi-ankle-picks-muthalai-pidi-crocodile-rolls-and-chain-tackling",
        "material_culture",
        "Ancient to Modern Era",
        "Seven-defender linked-wrist arc geometry governs the deployment of corner kaal-pidi ankle picks and crocodile-roll tackles.",
        "Biomechanics of Kabaddi"
    ],
    [
        "concept-sanjeevani-and-goongi-traditional-tamil-sadugudu-revival-and-capture-rules",
        "regulates",
        "institution-village-sadugudu-kazhagam-clubs-and-panguni-nocturnal-tournament-committees",
        "material_culture",
        "Medieval to Modern Era",
        "Traditional Sanjeevani player-resurrection and Gaminee elimination rules regulate inter-village knockout tournaments.",
        "Madras Physical Education Reports"
    ],
    [
        "technology-sadugudu-kalam-cushioned-red-earth-paddy-ash-and-neem-court-preparation",
        "enables",
        "technology-kaal-pidi-ankle-picks-muthalai-pidi-crocodile-rolls-and-chain-tackling",
        "material_culture",
        "Ancient to Modern Era",
        "Triple-sieved red earth blended with paddy-husk ash and antiseptic neem oil-cake enables safe high-impact diving ankle picks and crocodile rolls.",
        "Traditional Arena Construction"
    ],
    [
        "artifact-theevatti-oil-torches-lime-marker-horns-and-sandal-paste-victory-shields",
        "equips",
        "technology-sadugudu-kalam-cushioned-red-earth-paddy-ash-and-neem-court-preparation",
        "material_culture",
        "Medieval to Modern Era",
        "Corner theevatti oil-torches and perforated lime-powder horns illuminate and demarcate the prepared earthen sadugudu-kalam at night.",
        "Thanjavur District Gazetteer"
    ],
    [
        "artifact-kida-parisu-champion-fighting-rams-and-kal-eluthu-stone-conditioning-weights",
        "conditions",
        "technology-kaal-pidi-ankle-picks-muthalai-pidi-crocodile-rolls-and-chain-tackling",
        "material_culture",
        "Sangam to Modern Era",
        "Lifting heavy spherical thookku-kal stones and swinging karlakattai clubs condition the finger and forearm grip required for kaal-pidi holds.",
        "South Indian Physical Culture"
    ],
    [
        "institution-village-sadugudu-kazhagam-clubs-and-panguni-nocturnal-tournament-committees",
        "awards",
        "artifact-kida-parisu-champion-fighting-rams-and-kal-eluthu-stone-conditioning-weights",
        "material_culture",
        "Medieval to Modern Era",
        "Panguni-Chithirai festival tournament committees award garlanded Kida-Parisu prize rams and victory shields to champion village clubs.",
        "Village Festival Ethnography"
    ],
    [
        "place-peravurani-ancient-chola-sadugudu-arena-and-martial-athletics-haven",
        "hosts",
        "institution-village-sadugudu-kazhagam-clubs-and-panguni-nocturnal-tournament-committees",
        "material_culture",
        "Chola to Modern Era",
        "Peravurani and the surrounding Pattukkottai-Pudukkottai belt host Tamil Nadu's premier rural Sadugudu clubs and all-night tournaments.",
        "State Kabaddi Archives"
    ],
    [
        "text-sangam-malyutham-and-tamil-folk-ballads-on-sadugudu-and-paadi-aattam",
        "celebrates",
        "place-peravurani-ancient-chola-sadugudu-arena-and-martial-athletics-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Sangam malyutham poetry and folk Sadugudu ballads celebrate the agrarian Chola-coast wrestling arenas exemplified by Peravurani.",
        "Purananuru & Folk Ballads"
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
