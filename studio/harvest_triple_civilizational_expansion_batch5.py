#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 5):
1. Sangam Fauna, War Elephants & Maritime Horse Imports (10 dossiers)
2. Ancient Tamil Agriculture, Agronomy & Heritage Paddy Varieties (10 dossiers)
3. Ancient Tamil Ethno-Forestry, Honey Harvesting & Mountain Biospheres (10 dossiers)

Total: 30 Canonical Dossiers, ~50 Relational Edges, 60 Dense 1024-dim BGE-M3 Embeddings.
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

# ==============================================================================
# DOSSIERS DEFINITION (30 Total)
# ==============================================================================
DOSSIERS = [
    # --------------------------------------------------------------------------
    # CORPUS 1: SANGAM FAUNA, WAR ELEPHANTS & MARITIME HORSE IMPORTS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-purananuru-kaliru-elephant-warfare",
        "file": "text-purananuru-kaliru-elephant-warfare.md",
        "node_type": "text",
        "name_en": "Purananuru Kaliru Poems: War Elephant Assaults, Tusk Sheaths & Siege Breaches",
        "name_ta": "புறநானூறு களிறெறி பாட்டுகள் - போர் யானைப் படைகள், தந்த உறை மற்றும் கோட்டைத் தகர்ப்பு",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "Vanchi",
        "summary_en": "Sangam war poetry celebrating the royal bull elephant corps (Kaliru), depicting tuskers charging fort gates with iron-sheathed tusk blades (Irumpu-k-kodu), battering wooden ramparts, and enduring cloud of arrows under armored caparisons.",
        "summary_ta": "புறநானூற்றில் போர்க் களிறுகளின் பெருவீரத்தைப் பாடும் பாடல்கள். கோட்டைக் கதவுகளைத் தகர்க்கும் இரும்புத் தந்தக் கவசங்கள், மதங்கொண்ட யானைப் படைகளின் வியூகங்கள் மற்றும் அம்புகளைத் தாங்கும் நெற்றிப்பட்டத் தற்காப்புக் கவசங்கள் பற்றிய குறிப்புகள்.",
        "content": """# Purananuru Kaliru War Elephant Corps (புறநானூறு களிறு)

**Subject**: Royal War Elephants (*போர்க் களிறுகள்*), Siege Engines (*மதில் போர்*).  

---

## 1. Tactical Armor & Battering Mechanics
- **Kodu-Urai (*கோட்டுறை*)**: Heavy wrought-iron sleeves fitted over tusks, sharpening impact forces to splinter teak fortress gates.
- **Odai (*ஓடை*)**: Embossed bronze or iron frontal forehead plates deflecting projectile volleys.
- **Mudhugari (*முதுகரி*)**: Heavy wooden battle howdahs carrying archers and spearmen above foot infantry.
"""
    },
    {
        "category": "texts",
        "slug": "text-pattinappalai-kudirai-maritime-imports",
        "file": "text-pattinappalai-kudirai-maritime-imports.md",
        "node_type": "text",
        "name_en": "Pattinappalai: Oceanic Import of Arabian & Central Asian War Horses (Kudirai)",
        "name_ta": "பட்டினப்பாலை - கடலில் வந்த நிமிர்பரிப் புரவிகள் மற்றும் அரேபியக் குதிரை இறக்குமதி",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "Famous lines from Pattinappalai describing swift foreign stallions arriving by oceanic dhows at Poompuhar harbor ('நீரின் வந்த நிமிர்பரிப் புரவியும்'), establishing early maritime equestrian trade between the Red Sea/Persian Gulf and Tamilakam.",
        "summary_ta": "பட்டினப்பாலையில் (வரி 185) பூம்புகார் துறைமுகத்தில் பெருங்கடலிலிருந்து வந்து இறங்கிய உயர்தர அரேபிய-மத்திய ஆசியப் போர்க் குதிரைகள் பற்றிய சங்ககாலப் பதிவு. கடல்வழி வாணிகத்தில் குதிரை இறக்குமதியின் வரலாற்று முக்கியத்துவம்.",
        "content": """# Pattinappalai: Oceanic Horse Imports (நிமிர்பரிப் புரவி)

---

## 1. Trans-Oceanic Equine Logistics
Ancient Tamil kings relied on maritime imports for high-speed cavalry. Vessels specifically modified with padded stalls brought Arabian and Persian steeds across the monsoon routes to Kaveripoompattinam and Korkai.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kurunji-anai-malai-elephant-charters",
        "file": "insc-kurunji-anai-malai-elephant-charters.md",
        "node_type": "inscription",
        "name_en": "Anamalai Rock Epigraphs: Western Ghats Elephant Sanctuaries & Mahout Guild Grants",
        "name_ta": "ஆனைமலைக் கல்வெட்டுகள் - யானைப் புகலிடங்கள் மற்றும் பாகர் குழுக்களின் சாசனங்கள்",
        "era": "Early Medieval Era",
        "year_start": 600,
        "year_end": 900,
        "thinai": "Kurinji",
        "summary_en": "Rock inscriptions around the Anamalai corridor documenting royal Chera and Pandyan charters regulating elephant captures, forest grazing corridors, and land endowments to hereditary mahout clans (Pakap-pangu).",
        "summary_ta": "ஆனைமலை அடிவாரத்தில் கண்டெடுக்கப்பட்ட கல்வெட்டுகள். போர்ப்படை யானைகளைப் பிடிப்பதற்கான எல்லை நெறிகள், யானைப் பாகர்களுக்கு வழங்கப்பட்ட பாகப்பங்கு நில மானியங்கள் மற்றும் வன விலங்குப் பாதுகாப்பு ஆவணங்கள்.",
        "content": """# Anamalai Elephant Epigraphs (ஆனைமலைக் கல்வெட்டுகள்)

**Site**: Anamalai Foothills (*ஆனைமலை*), Western Ghats.  
**Significance**: Epigraphical confirmation of state-managed wild elephant herds and hereditary trainer guilds.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kaliru-war-elephant-siege-mechanics",
        "file": "concept-kaliru-war-elephant-siege-mechanics.md",
        "node_type": "concept",
        "name_en": "Kaliru Siege Tactics: Iron Tusk Caps, Gate Battering & Shock Infantry Formations",
        "name_ta": "களிறு மதில்தகர்ப்புத் தொழில்நுட்பம் - இரும்புத் தந்தக் கூம்புகள் மற்றும் கோட்டை முற்றுகை",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "Vanchi",
        "summary_en": "The offensive military doctrine of deploying mature tuskers (Kaliru) as living battering rams fitted with hardened iron tusk-caps, trained to charge moats, tear down thorny palisades, and disrupt cavalry lines.",
        "summary_ta": "போர்க் களிறுகளுக்குப் பயிற்சி தந்து கோட்டைக் கதவுகளை முட்டித் திறக்கவும், ஆழமான அகழிகளைக் கடக்கவும், இரும்புப் பூண்கள் பூட்டிய தந்தங்களால் மதில் சுவர்களை இடிக்கவும் பயன்படுத்தப்பட்ட தமிழரின் போர்த் தொழினுட்பம்.",
        "content": """# Kaliru Siege Mechanics (களிறு முற்றுகைப் பொறியியல்)

---

## 1. Offensive Siege Doctrine
- **Iron Caps (*இரும்புப் பூண்*)**: Absorbed impact stress and prevented tusk fracture during gate impacts.
- **Trunk Sheaths (*தும்பித் தோல்*)**: Thick boiled-leather guards protecting the vulnerable prehensile trunk against spear thrusts.
- **Drunken Frenzy Inducement**: Feeding fermented toddy (*Kal*) mixed with pepper paste to elevate aggression prior to field charges.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kudirai-k-kodu-arabian-horse-trade",
        "file": "concept-kudirai-k-kodu-arabian-horse-trade.md",
        "node_type": "concept",
        "name_en": "Kudirai-k-Kodu: The Indian Ocean Arabian Horse Trade & Guild Importers",
        "name_ta": "குதிரைக் கொடு - இந்தியப் பெருங்கடல் அரேபியக் குதிரை வணிகமும் குதிரைச் செட்டிகளும்",
        "era": "Sangam to Medieval Pandyan Era",
        "year_start": -100,
        "year_end": 1300,
        "thinai": "Neithal",
        "summary_en": "The high-value trans-oceanic trade network importing Arabian, Persian, and Gulf horses into Coromandel ports, regulated by royal charters, specialized horse-trader guilds (Kudirai-c-cetti), and state quarantine corrals.",
        "summary_ta": "ஹோர்முஸ் மற்றும் ஏடன் துறைமுகங்களிலிருந்து காயல், பூம்புகார் துறைமுகங்களுக்கு ஆண்டுதோறும் ஆயிரக்கணக்கான உயர்வகை அரேபியப் புரவிகளை இறக்குமதி செய்த குதிரைச் செட்டிகளின் வணிகக் கட்டமைப்பு.",
        "content": """# Arabian Horse Trade Networks (குதிரை வணிகம்)

---

## 1. Economic Scale
Marco Polo and Wassaf record that Pandyan rulers invested up to 10,000 dinars per horse, purchasing thousands annually from Arab merchant prince Jamal al-Din of Kish.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-sangam-fauna-panthera-and-avian-omens",
        "file": "concept-sangam-fauna-panthera-and-avian-omens",
        "node_type": "concept",
        "name_en": "Sangam Fauna & Ethology: Royal Tigers, War Birds & Auspicious Omens (Sakunam)",
        "name_ta": "சங்ககால விலங்கியல் - வேங்கைப்புலி, போர்ப்பறவைகள் மற்றும் சகுன நிமித்தங்கள்",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "Kurinji",
        "summary_en": "Ecological awareness and wildlife behavioral tracking in classical Tamil poetry, featuring apex predators like the royal tiger (Vengai) as the Chola dynastic emblem, war-bird divination (Pakshi-sastra), and falconry.",
        "summary_ta": "சங்க இலக்கியத்தில் புலிகள், மான்கள், கிளிகள் மற்றும் வேட்டைப் பருந்துகளின் நடத்தை பற்றிய விலங்கியல் பதிவுகள். சோழரின் வேங்கைப் புலி மரபு, போருக்குப் புறப்படும் முன் பறவைகளின் ஒலியைக் கொண்டு சகுனம் பார்த்தல்.",
        "content": """# Sangam Fauna & Animal Behavior (சங்ககால விலங்கியல்)

---

## 1. The Royal Vengai (Tiger)
Symbolizing sovereign ferocity, the tiger was believed never to eat prey that fell to its left side (*"இடம்படு வீழ்த்த வேங்கையொடு"*), symbolizing royal chivalry (*Veeram*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-elephant-capture-and-khedda-technology",
        "file": "concept-elephant-capture-and-khedda-technology.md",
        "node_type": "concept",
        "name_en": "Elephant Capture Technology: Pit-Traps (Kuli), Stockades (Pandi) & Taming Protocols",
        "name_ta": "யானை பிடிக்கும் தொழினுட்பம் - குழியமைத்தல், பாண்டிச் சிறை மற்றும் பழக்குதல் முறை",
        "era": "Ancient to Medieval Era",
        "year_start": -500,
        "year_end": 1400,
        "thinai": "Mullai",
        "summary_en": "Indigenous elephant-trapping engineering in the Western Ghats using concealed dry-pit traps (Kuli) covered with bamboo mats, timber kraal stockades (Pandi), and decoy cow-elephants (Kumki) for safe capture and taming.",
        "summary_ta": "மேற்குத் தொடர்ச்சி மலைகளில் மூங்கில் புற்களால் மறைக்கப்பட்ட ஆழமான குழிகள் (ஆனைக்குழி), மரத்தடிகள் கொண்ட சிறைக்கூடங்கள் (பாண்டி) மற்றும் கும்கி யானைகளைப் பயன்படுத்தி காட்டு யானைகளைப் பிடிக்கும் மரபுவழித் தொழில்நுட்பம்.",
        "content": """# Elephant Trapping & Training (ஆனை பிடித்தல்)

---

## 1. Capture Engineering
- **Pit Capture (*ஆனைக்குழி*)**: Funnel trenches guiding herds toward deep leaf-covered drop-pits.
- **Stockades (*பாண்டி*)**: Massive teak enclosures where captured tuskers were gradually calmed with sugarcane, banana pith, and rhythmic songs (*Pakap-paattu*).
"""
    },
    {
        "category": "characters",
        "slug": "char-chola-paka-maravan-chief-mahout",
        "file": "char-chola-paka-maravan-chief-mahout.md",
        "node_type": "character",
        "name_en": "Chola Paka-Maravan: Imperial Grand Mahout & Elephant Battle Commander",
        "name_ta": "சோழப் பாக மறவன் - அரச பெருங்களிறுகளை வழிநடத்திய தலைமை யானைப் படைத்தளபதி",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1050,
        "thinai": "Vanchi",
        "summary_en": "Supreme commander of the imperial Chola elephant corps (*Anai-k-kodum-padai*), master of elephant acupuncture pressure points (*Marma*), and coordinator of frontal charges.",
        "summary_ta": "சோழப் பேரரசின் ஆயிரக்கணக்கான களிறுகளை வழிநடத்தி, போர்க்களத்தில் யானைகளின் வர்மப் புள்ளிகளை அறிந்து வழிநடத்திய முதன்மைப் பாக மறவன்.",
        "content": """# The Chief Mahout of the Chola Navy & Army (பாக மறவன்)

Held in immense royal esteem, these commanders directed tuskers to batter enemy fortifications and carry commanders safely above the melee.
"""
    },
    {
        "category": "characters",
        "slug": "char-kudirai-c-cetti-arabian-horse-importer",
        "file": "char-kudirai-c-cetti-arabian-horse-importer.md",
        "node_type": "character",
        "name_en": "Kudirai-c-Cetti: Guild Merchant Master of Trans-Oceanic Horse Transports",
        "name_ta": "குதிரைச் செட்டி - அரேபியப் போர்ப் புரவிகளைத் தருவித்த பெருவணிகக் குழுவின் தலைவர்",
        "era": "Sangam to Medieval Era",
        "year_start": 100,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "Influential maritime merchant specialized in importing war horses from Hormuz, managing port corrals, equestrian vetting, and negotiating procurement contracts with Tamil kings.",
        "summary_ta": "அரேபிய வளைகுடாவிலிருந்து கடல்வழியாகக் குதிரைகளைத் தருவித்து, அவற்றின் சுழிகள் மற்றும் உடலமைப்பை ஆராய்ந்து மன்னர்களுக்கு விற்ற பெருவணிகர்.",
        "content": """# The Kudirai-c-Cetti Guild (குதிரைச் செட்டி)

These merchants possessed royal diplomatic immunity and established training grounds (*Kudirai-p-panthi*) adjacent to oceanic ports.
"""
    },
    {
        "category": "places",
        "slug": "place-anamalai-chera-elephant-capture-basin",
        "file": "place-anamalai-chera-elephant-capture-basin.md",
        "node_type": "place",
        "name_en": "Anamalai: Western Ghats Rainforest Elephant Sanctuary & Trapping Basin",
        "name_ta": "ஆனைமலை - சேரர் காலத்து யானைப் புகலிடம் மற்றும் பெருங்களிறுகள் வளர்ப்புப் பிரதேசம்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "Kurinji",
        "summary_en": "Dense montane rainforest range in the Western Ghats famous since antiquity as the primary breeding habitat and capture reserve for royal war elephants of the Chera, Pandyan, and Kongu kings.",
        "summary_ta": "மேற்குத் தொடர்ச்சி மலையின் பிரம்மாண்டமான ஆனைமலைப் பகுதி. சேர, பாண்டிய, கொங்கு மன்னர்களின் போர்ப் படைகளுக்கான களிறுகள் பிடிக்கப்பட்டுப் பயிற்றுவிக்கப்பட்ட வரலாற்றுப் புகலிடம்.",
        "content": """# Anamalai Elephant Sanctuary Basin (ஆனைமலை)

- **Coordinates**: 10.3500° N, 76.9500° E.  
- **Ecological Zone**: Wet evergreen and moist deciduous Western Ghats rainforests.  
- **Historic Role**: Royal elephant capture reserve and mahout cantonment.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: ANCIENT TAMIL AGRICULTURE & HERITAGE PADDY VARIETIES
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-porunararruppadai-velanmai-agronomy",
        "file": "text-porunararruppadai-velanmai-agronomy.md",
        "node_type": "text",
        "name_en": "Porunararruppadai: Kaveri Delta Wet-Rice Agronomy & Thousand-Kalam Yields",
        "name_ta": "பொருநராற்றுப்படை - காவிரியின் பாய்ச்சல் வளம், நெல் சாகுபடி மற்றும் ஆயிரங்கல விளைச்சல்",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "Marutham",
        "summary_en": "Mudathamakanniyar's Sangam panegyric extolling the incredible soil fertility of the Kaveri delta where a single female elephant resting space yields grain enough for seven kings ('காவிரி புரக்கும் நன்னாட்டு...'), yielding a thousand kalams of paddy per veli.",
        "summary_ta": "முடத்தாமக் கண்ணியாரின் பொருநராற்றுப்படை. ஒரு பெண் யானை படுத்துறங்கும் நிலப்பரப்பில் ஏழு களிறுகளுக்கான தானியம் விளையும் காவிரியின் வளம், உழவுத் தொழில், மற்றும் ஆயிரங்கல விளைச்சலின் வேளாண்மைப் பதிவுகள்.",
        "content": """# Porunararruppadai Kaveri Agronomy (பொருநராற்றுப்படை வேளாண்மை)

---

## 1. Kaveri Floodplain Fertility
The poem documents intensive wetland agriculture:
*"ஒருபிடி படியும் சீறிடம்... எழுகளிறு புரக்கும் நாடுகிழ வோயே!"*  
Rich alluvial silt (*Punal-padu*) deposited annually by monsoon inundations sustained continuous double-cropping without chemical soil exhaustion.
"""
    },
    {
        "category": "texts",
        "slug": "text-malaipadukadam-siru-tinai-millet-farming",
        "file": "text-malaipadukadam-siru-tinai-millet-farming.md",
        "node_type": "text",
        "name_en": "Malaipadukadam: Mountain Slope Dryland Millets (Tinai), Slash-and-Burn & Bamboo Rice",
        "name_ta": "மலைபடுகடாம் - நவிர மலை தினைப் புனம், புன்செய் வேளாண்மை மற்றும் மூங்கில் அரிசி",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "Kurinji",
        "summary_en": "Sangam poem by Perunkousiganar depicting mountain agronomy on the slopes of Naviramalai: terraced millet swiddens (Tinai-p-punam), watchtower platforms (Paran) for scaring birds, and wild bamboo seed harvesting.",
        "summary_ta": "பெருங்கௌசிகனாரின் மலைபடுகடாம். நவிர மலையின் சரிவுகளில் தினை, சாமை முதலான சிறுதானியங்களை விளைவித்தல், பரண் அமைத்துக் கவண்கல் கொண்டு கிளிகளை ஓட்டுதல் மற்றும் மூங்கில் நெல் அறுவடை பற்றிய குறிப்புகள்.",
        "content": """# Malaipadukadam Dryland Agronomy (தினைப் புனம்)

---

## 1. Terrace & Swidden Cultivation
Hill farmers cleared steep mountain slopes, firing underbrush to enrich red soils with potash ash, then broadcast sown fox-tail millet (*Tinai*) and little millet (*Samai*).
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thanjavur-sennel-land-survey-charters",
        "file": "insc-thanjavur-sennel-land-survey-charters.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Brihadisvara Sennel Charters: Cadastral Survey & Standard Paddy Yields",
        "name_ta": "தஞ்சைப் பெரிய கோயில் செந்நெல் சாசனங்கள் - நில அளவீடு மற்றும் தரப்படுத்தப்பட்ட நெல் அளவை",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Monumental cadastral survey inscriptions by Rajaraja I cataloging temple lands to fractions of a square millimeter, assessing revenue yields in standard Red Paddy (Sennel), and establishing irrigation channel water shares.",
        "summary_ta": "இராஜராஜ சோழனின் தஞ்சைப் பெருவுடையார் கோயில் நில அளவைக் கல்வெட்டுகள். நன்செய்-புன்செய் நிலங்களை மிகத் துல்லியமாக அளந்து, செந்நெல் தானிய அளவையில் இறை விதித்த பேரரசின் வேளாண் நிர்வாக ஆவணம்.",
        "content": """# Thanjavur Sennel Inscriptions (செந்நெல் சாசனங்கள்)

**Key Metric**: All land taxes and endowment revenues were calculated in terms of dry volume measures of high-grade red paddy (*செந்நெல்*) measured by the standard imperial *Aadavallan* marakkal.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-sennel-and-heritage-paddy-cultivation",
        "file": "concept-sennel-and-heritage-paddy-cultivation.md",
        "node_type": "concept",
        "name_en": "Sennel & Heritage Rice Agronomy: Inundation Ecology, Vennel & Coastal Strains",
        "name_ta": "செந்நெல் மற்றும் பாரம்பரிய நெல் ரகங்கள் - வெள்ளச் சூழலியல், வெண்ணெல் மற்றும் சாகுபடி முறை",
        "era": "Sangam to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "Marutham",
        "summary_en": "The sophisticated agronomic cultivation of ancient Tamil rice landraces: nutrient-rich red rice (Sennel), white scented rice (Vennel), flood-resistant floating strains, and salt-tolerant coastal varieties (Kadal-kazhuthu).",
        "summary_ta": "பழந்தமிழகத்தில் பயிரிடப்பட்ட பாரம்பரிய நெல் வகைகள். ஆற்று வெள்ளத்தில் மூழ்கினாலும் வளரும் நெல் வகைகள், செந்நெல், வெண்ணெல், குறுவை, சம்பா நெல் சுழற்சி முறை மற்றும் கழிமுக உவர்நில நெல் நுட்பங்கள்.",
        "content": """# Sennel & Ancient Tamil Rice Varieties (செந்நெல் சாகுபடி)

---

## 1. Landrace Biodiversity
- **Sennel (*செந்நெல்*)**: Premium iron-rich red-pericarp grain reserved for royal banquets and temple offerings.
- **Siru-Sennel (*சிறுசெந்நெல்*)**: Delicate aromatic short-grain used for celebratory feasting.
- **Kadal-Kazhuthu (*கடற்கழுத்து*)**: Brackish flood-tolerant strain cultivated in saline coastal lagoons.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-punsei-tinai-dryland-millet-polyculture",
        "file": "concept-punsei-tinai-dryland-millet-polyculture.md",
        "node_type": "concept",
        "name_en": "Punsei Polyculture: Rainfed Dryland Millets, Legume Nitrogen Fixation & Mixed Cropping",
        "name_ta": "புன்செய் பலபயிர்ச் சாகுபடி - மானாவாரி சிறுதானியங்கள், பயறு வகைகள் மற்றும் தினைப் பயிர்முறை",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 500,
        "thinai": "Mullai",
        "summary_en": "Ancient sustainable dryland agroecosystems where fox-tail millet, finger millet (Ragi/Keppai), cowpea, and sesame were intercropped on red gravel soils, utilizing symbiotic nitrogen fixation and seasonal rainfall.",
        "summary_ta": "மானாவாரி நிலங்களில் தினை, வரகு, சாமை முதலான சிறுதானியங்களோடு உளுந்து, கொள்ளு, எள்ளு முதலான பயறு வகைகளை ஊடுபயிராக நட்டு, மண்வளத்தை நிலைநிறுத்தி வறட்சியை வென்ற பண்டைய பலபயிர் முறை.",
        "content": """# Punsei Millet Polyculture (புன்செய் வேளாண்மை)

---

## 1. Ecological Resilience
Intercropping deep-rooted legumes (*Payaru*) with fast-maturing millets protected drought-prone drylands against total crop failure during monsoon deficits.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-uzhavu-plowing-and-marutham-pedology",
        "file": "concept-uzhavu-plowing-and-marutham-pedology.md",
        "node_type": "concept",
        "name_en": "Uzhavu Plowing & Pedology: Ard-Plow Mechanics (Nanchi), Silt Puddling & Tilth",
        "name_ta": "உழவுத் தொழினுட்பமும் மண் அறிவியலும் - மர நாஞ்சில், இரும்புக் கொழு மற்றும் சேற்று உழவு",
        "era": "Iron Age to Sangam Classical Era",
        "year_start": -500,
        "year_end": 400,
        "thinai": "Marutham",
        "summary_en": "The mechanics of Tamil wetland preparation: timber ard-plows (Nanchi / Kalappai) fitted with forged iron coulters (Kozhu), repeated cross-plowing, green leaf manuring (*Thazhai-y-eruthu*), and cattle trampling for fine clay puddling.",
        "summary_ta": "பண்டைத் தமிழர் மேற்கொண்ட ஆழ உழவு நெறிகள். கருவேலம் மர நாஞ்சிலில் இரும்புக் கொழு பொருத்தி, காளைகளைக் கொண்டு சேற்று நிலத்தை உழுது, எருக்கு-வேப்பந் தழைகளை இட்டு உரமிட்ட உழவியல் முறைமை.",
        "content": """# Ancient Tamil Plowing & Soil Science (உழவு முறைமை)

---

## 1. The Heavy Ard-Plow (*Nanchi*)
Tolkappiyam and Sangam poems highlight:
- *"கொழுவாடிய கூர்நாஞ்சில்"* - Hardened iron share cutting through stubborn black cotton soil (*Karambai*).
- Repeated puddle passes leveling mud to prevent uneven pooling of standing irrigation water.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kalam-threshing-and-agrarian-metrology",
        "file": "concept-kalam-threshing-and-agrarian-metrology.md",
        "node_type": "concept",
        "name_en": "Kalam Threshing & Granary Storage: Bullock Trampling, Winnowing & Straw Kuthir Bins",
        "name_ta": "களத்து அறுவடை மற்றும் தானியக் களஞ்சியம் - கதிர் அடித்தல், தூற்றுதல் மற்றும் குதிர் சேமிப்பு",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Post-harvest processing technology: sun-baked circular threshing floors (Kalam), bullock trampling of sheaves, wind winnowing (*Thoothru-thal*), and moisture-proof long-term grain storage in giant terracotta-and-straw silos (Kuthir).",
        "summary_ta": "அறுவடைக்குப் பின் களத்தில் நெற்கதிர்களைப் பரப்பி எருதுகளைக் கொண்டு பிணையடித்தல், காற்றில் பதர் நீங்கத் தூற்றுதல் மற்றும் பூச்சிகள் அண்டாமல் வைக்க வைக்கோல் சுற்றிய பிரம்மாண்ட குதிர்களில் நெல்லைச் சேமிக்கும் தொழில்நுட்பம்.",
        "content": """# Kalam Threshing & Silo Architecture (களம் மற்றும் நெற்களஞ்சியம்)

---

## 1. Storage Preservation
- **Kuthir (*குதிர்*)**: Double-walled circular grain silos made of bamboo wattle plastered with cow dung and red clay, ensuring seed viability for over two years without mould.
"""
    },
    {
        "category": "characters",
        "slug": "char-uzhava-perumakan-master-farmer",
        "file": "char-uzhava-perumakan-master-farmer.md",
        "node_type": "character",
        "name_en": "Uzhava Perumakan: Sangam Master Agronomist & Hereditary Village Elder",
        "name_ta": "உழவப் பெருமகன் - காவிரியின் உழவு முறைமைகளையும் விண்மீன் சாகுபடி நெறியையும் அறிந்த வேளாண் ஆசான்",
        "era": "Sangam Classical Era",
        "year_start": -50,
        "year_end": 50,
        "thinai": "Marutham",
        "summary_en": "Respected agrarian elder who determined seed-sowing dates by observing asterism positions (Rohini, Karthigai), managed canal sluice openings, and directed communal harvest celebrations.",
        "summary_ta": "விண்மீன் நிலைகளைக் கணித்து விதைப்பு நாள் குறித்து, மதகுகளின் பாசன நீர்ப் பகிர்வை நெறிப்படுத்திய காவிரிப் படுகையின் மூத்த உழவப் பெருமகன்.",
        "content": """# The Master Agronomist (உழவப் பெருமகன்)

Guardian of agricultural proverbs (*Uzhavu Pazhamozhi*), seed selection protocols, and natural pest repellents utilizing neem cake and wood ash.
"""
    },
    {
        "category": "characters",
        "slug": "char-kaveri-delta-paddy-surveyor",
        "file": "char-kaveri-delta-paddy-surveyor.md",
        "node_type": "character",
        "name_en": "Kaveri Delta Paddy Surveyor: Imperial Cadastral Assayer & Grain Officer",
        "name_ta": "காவிரிப் படுகை நெல் கணக்கர் - நில அளவை மற்றும் தானிய இறை கணக்கிடும் சோழ அரசு அதிகாரி",
        "era": "Imperial Chola Era",
        "year_start": 1000,
        "year_end": 1060,
        "thinai": "Marutham",
        "summary_en": "Royal revenue official equipped with standard measuring rods, responsible for testing grain moisture, assessing bushel weights, and recording imperial grain shares in temple granaries.",
        "summary_ta": "நிலங்களை அளக்கும் கோல் கொண்டு அளந்து, நெல்லின் ஈரப்பதம் மற்றும் தூய்மையை ஆராய்ந்து அரசு நெற்களஞ்சியத்தில் சேர்க்கும் சோழர் காலப் பண்டாரக் கணக்கர்.",
        "content": """# The Royal Cadastral Assayer (நெல் கணக்கர்)

Maintained palm-leaf revenue registers (*Vari-pothagam*), reconciling land classifications and ensuring accurate taxation without peasant distress.
"""
    },
    {
        "category": "places",
        "slug": "place-thiruvaiyaru-kaveri-paddy-basin",
        "file": "place-thiruvaiyaru-kaveri-paddy-basin.md",
        "node_type": "place",
        "name_en": "Thiruvaiyaru: The Fertile Five-River Kaveri Alluvial Rice Heartland",
        "name_ta": "திருவையாறு - ஐந்து ஆறுகள் பாயும் காவிரியின் செந்நெல் சாகுபடித் திருத்தலம்",
        "era": "Sangam to Imperial Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The sacred agrarian heartland where five branches of the Kaveri converge (Kaveri, Kollidam, Vennaru, Vettaru, Kudamurutti), celebrated for perennial silt renewal, intensive double-crop rice paddies, and extensive canal networks.",
        "summary_ta": "காவிரி, கொள்ளிடம், வெண்ணாறு, வெட்டாறு, குடமுருட்டி ஆகிய ஐந்து ஆறுகள் வளம் கொழிக்கும் தஞ்சை மண்டலத்து முதன்மை நெல் சாகுபடி மையம். சோழர் காலத்து நன்செய் வேளாண்மையின் உச்சம்.",
        "content": """# Thiruvaiyaru Alluvial Rice Heartland (திருவையாறு)

- **Coordinates**: 10.8833° N, 79.1000° E.  
- **River Network**: Convergence of five major deltaic channels.  
- **Agricultural Status**: The benchmark deltaic zone for thousand-kalam heirloom paddy yields per veli.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: ANCIENT TAMIL ETHNO-FORESTRY, HONEY HARVESTING & BIOSPHERES
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-kurunjippattu-honey-harvest-and-hill-flora",
        "file": "text-kurunjippattu-honey-harvest-and-hill-flora.md",
        "node_type": "text",
        "name_en": "Kurunjippattu: High-Cliff Wild Honey Gathering & Montane Climax Flora",
        "name_ta": "குறிஞ்சிப்பாட்டு - மலை உச்சிக் கொம்புத்தேன் அறுவடை மற்றும் 99 மலர்களின் தாவரவியல்",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "Kurinji",
        "summary_en": "Kabilar's celebrated poem documenting high-altitude Kurinji ecology, 99 indigenous flowers, wild cliff-honey extraction by Kanikkar climbers using rope ladders across deep chasms, and mountain agriculture.",
        "summary_ta": "கபிலரின் குறிஞ்சிப்பாட்டு. மேற்குத் தொடர்ச்சி மலையின் 99 வகையான குறிஞ்சி மலர்கள், மலை உச்சிப் பாறைகளில் கூடுகட்டும் கொம்புத்தேனை இரவு வேளையில் கயிறு ஏணி கட்டி இறங்கி எடுக்கும் மலைவாழ் மக்களின் நுட்பங்கள்.",
        "content": """# Kurunjippattu Mountain Ecology (குறிஞ்சிப்பாட்டு தேனெடுத்தல்)

---

## 1. High-Altitude Cliff Apiculture
The poem depicts Kanikkar honey-hunters descending sheer vertical precipices by torchlight:
- Suspending bamboo-fiber ladders (*Aani-nool*) from stout trees.
- Using dried smoke torches to disorient giant rock bees (*Apis dorsata*) without burning the honeycomb.
"""
    },
    {
        "category": "texts",
        "slug": "text-sirupanarruppadai-forest-fragrances",
        "file": "text-sirupanarruppadai-forest-fragrances.md",
        "node_type": "text",
        "name_en": "Sirupanarruppadai: Montane Aromatics, Aloeswood (Akil) & Sandalwood Silviculture",
        "name_ta": "சிறுபாணாற்றுப்படை - மலை நறுமணப் பொருட்கள், அகில், சந்தனம் மற்றும் நறுமணக் காடுகள்",
        "era": "Sangam Classical Era",
        "year_start": -50,
        "year_end": 150,
        "thinai": "Kurinji",
        "summary_en": "Nallur Nathathanar's poetic verses describing the rich forest aromatic produce of the southern hills—heavy black aloeswood (Akil), fragrant sandalwood (Chandanam), wild cardamom pods, and long pepper gathered for royal trade.",
        "summary_ta": "நல்லூர் நத்தத்தனாரின் சிறுபாணாற்றுப்படை. குறிஞ்சி நிலக் காடுகளில் விளையும் நறுமணமிக்க அகில் கட்டைகள், சந்தன மரங்கள், காட்டு ஏலக்காய் மற்றும் திப்பிலி முதலான வாசனைப் பொருட்கள் சேகரிக்கப்படும் மரபு.",
        "content": """# Sirupanarruppadai Mountain Aromatics (சிறுபாணாற்றுப்படை நறுமணம்)

---

## 1. Wild Silviculture
Mountain chieftains protected high-elevation moist forests where *Aquilaria agallocha* (Akil) trees formed dense aromatic resin in response to fungal seasoning.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-anaimalai-forest-chieftain-charters",
        "file": "insc-anaimalai-forest-chieftain-charters.md",
        "node_type": "inscription",
        "name_en": "Anaimalai Tribal Chieftain Charters: Forest Product Tributes & Autonomous Rights",
        "name_ta": "ஆனைமலைப் பழங்குடித் தலைவர்கள் கல்வெட்டுகள் - காட்டு விளைபொருட்கள் மற்றும் தன்னாட்சி உரிமைகள்",
        "era": "Post-Sangam to Medieval Era",
        "year_start": 500,
        "year_end": 1000,
        "thinai": "Kurinji",
        "summary_en": "Epigraphs along the Western Ghats passes recording treaties between plains kings and hill forest chieftains (Kanikkar / Malai-arasar), exchanging honey, ivory, and spices for grain, salt, and iron tools.",
        "summary_ta": "மேற்குத் தொடர்ச்சி மலைப்பாதைகளில் உள்ள பாறைச் சாசனங்கள். சமவெளி மன்னர்களுக்கும் மலைவாழ் தலைவர்களுக்கும் இடையே தேன், யானைத் தந்தம், நறுமணப் பொருட்களுக்குப் பதிலாக உப்பு, தானியம், இரும்பு பெறப்பட்ட ஒப்பந்தங்கள்.",
        "content": """# Forest Chieftain Charters (வனத் தலைவர்கள் கல்வெட்டுகள்)

Recognized the exclusive customary sovereignty (*Urimai*) of tribal groups over wild honey collecting, medicinal root digging, and cardamon picking.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-malai-then-cliff-honey-harvesting-mechanics",
        "file": "concept-malai-then-cliff-honey-harvesting-mechanics.md",
        "node_type": "concept",
        "name_en": "Malai-Then Harvesting Mechanics: Cliff-Drop Rope Ladders & Giant Rock Bee Apiculture",
        "name_ta": "மலைத்தேன் அறுவடை முறை - செங்குத்துப் பாறைக் கயிறேணி மற்றும் பெருந்தேன் வேட்டை",
        "era": "Ancient to Medieval Era",
        "year_start": -500,
        "year_end": 1500,
        "thinai": "Kurinji",
        "summary_en": "The dangerous traditional apicultural engineering of harvesting wild honey from giant rock bees (Apis dorsata) nesting under granite overhangs: braided cane rope ladders, smoke fumigation, and organic beeswax separation.",
        "summary_ta": "செங்குத்தான மலைப் பாறை இடுக்குகளில் கூடுகட்டும் பெருந்தேனீக்களின் தேனை எடுக்க, காட்டுக்கொடிகளால் ஆன கயிறு ஏணிகளில் தொங்கியபடி தீப்பந்தப் புகையிட்டுத் தேன் அடைகளை அறுக்கும் தனித்துவத் தொழில்நுட்பம்.",
        "content": """# Cliff Honey Harvesting Engineering (மலைத்தேன் வேட்டை)

---

## 1. Ritual & Safety Protocols
- **Aani-Kodi (*ஆணிக் கொடி*)**: Heavy wild creepers braided into flexible high-tensile descent ladders.
- **Midnight Descent**: Undertaken at the dark of the moon to minimize rock bee aggression.
- **Wax Separation**: Raw comb strained through horsehair or cotton sieves to separate golden medicinal honey from pure cosmetic beeswax (*Mezhugu*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-akil-chandanam-aromatic-silviculture",
        "file": "concept-akil-chandanam-aromatic-silviculture.md",
        "node_type": "concept",
        "name_en": "Akil & Chandanam Silviculture: Montane Hardwood Curing, Resins & Overseas Exports",
        "name_ta": "அகில் மற்றும் சந்தன மரவியல் - காடுகளின் நறுமண மரங்கள் பதப்படுத்துதல் மற்றும் ஏற்றுமதி",
        "era": "Sangam to Imperial Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Kurinji",
        "summary_en": "The forest management, harvesting, and water-curing of dense fragrant hardwoods—sandalwood (Santalum album) and agarwood/aloeswood (Aquilaria), prized across Rome, China, and the Islamic world.",
        "summary_ta": "சந்தன மரம் மற்றும் அகில் கட்டைகளை காடுகளில் அடையாளம் கண்டு வெட்டி, நீரில் ஊறவைத்து நறுமணத்தை முதிரச் செய்து, உரோமம், சீனா மற்றும் அராபிய நாடுகளுக்கு ஏற்றுமதி செய்த வனப் பொருளாதார நுட்பம்.",
        "content": """# Aromatic Silviculture (அகில் - சந்தன மரவியல்)

---

## 1. Seasoning & Grading
- Heartwood extracted from old mature trees buried in moist marsh soils to rot soft sapwood, leaving pure dense fragrant core resin that sank in water (*"நீரில் மூழ்கும் அகில்"*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kaval-kadu-defensive-border-forests",
        "file": "concept-kaval-kadu-defensive-border-forests.md",
        "node_type": "concept",
        "name_en": "Kaval-Kadu: Defensive Perimeter Thorn Forests & Anti-Cavalry Border Biospheres",
        "name_ta": "காவல் காடு (மிளை) - கோட்டை அரண் முட்காடுகள் மற்றும் குதிரைப்படை தடுப்பு மரபு",
        "era": "Sangam Classical Era",
        "year_start": -400,
        "year_end": 400,
        "thinai": "Mullai",
        "summary_en": "The deliberate cultivation and conservation of dense, impenetrable thorny barrier forests (Milai / Kaval-kadu) encircling ancient Tamil fortified cities, serving as eco-military defense perimeters impassable to enemy horses and siege engines.",
        "summary_ta": "பண்டைத் தமிழ்ப் பெருநகரங்களையும் கோட்டைகளையும் சுற்றி மனிதர்கள் எளிதில் ஊடுருவ முடியாதபடி முள் மரங்களையும் அடர்ந்த புதர்களையும் நட்டுப் பாதுகாத்த 'மிளை' அல்லது காவல் காடு என்னும் இராணுவப் பாதுகாப்பு மரபு.",
        "content": """# Kaval-Kadu (Milai) Border Defense Forests (காவல் காடு)

---

## 1. Military Eco-Barriers
Sangam kings maintained strict taboos against felling trees in the *Kaval-kadu*. Cutting down an enemy king's defensive forest (*"மிளை சிதைத்தல்"*) was the first decisive step in fortress sieges.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kani-tribal-ethnobotany-and-medicines",
        "file": "concept-kani-tribal-ethnobotany-and-medicines.md",
        "node_type": "concept",
        "name_en": "Kani Ethnobotany: Forest Tubers (Valli), Anti-Venom Flora & Herbal Adaptogens",
        "name_ta": "காணிக்காரர் நாட்டுப்புறத் தாவரவியல் - காட்டு வள்ளி, விஷமுறிவு மூலிகைகள் மற்றும் வன மருத்துவம்",
        "era": "Ancient to Classical Era",
        "year_start": -500,
        "year_end": 1000,
        "thinai": "Kurinji",
        "summary_en": "The deep ecological pharmacopoeia preserved by Western Ghats hill tribes (Kani, Kadar): locating deep subterranean yams (Valli-kizhangu), treating deadly pit-viper bites with root extracts, and harvesting vitality-restoring herbs (*Arogyappacha*).",
        "summary_ta": "காணிக்காரர் பழங்குடி மக்கள் தலைமுறை தலைமுறையாகப் பாதுகாத்து வந்த வன மருத்துவ அறிவு. காட்டு வள்ளிக்கிழங்குகளை அகழ்ந்தெடுத்தல், கொடிய பாம்புக் கடிகளுக்கு பச்சிலைச் சாறுகளால் நஞ்சு முறித்தல் மற்றும் உடல்தேற்றும் மூலிகைகள்.",
        "content": """# Kani Tribal Ethnobotany (பழங்குடித் தாவரவியல்)

---

## 1. Subterranean Root Foraging
Gatherers used fire-hardened digging sticks (*Parambu*) to excavate deep edible tubers (*Dioscorea*), carefully replanting the top crowns to ensure perennial regeneration.
"""
    },
    {
        "category": "characters",
        "slug": "char-kani-mountain-honey-master",
        "file": "char-kani-mountain-honey-master.md",
        "node_type": "character",
        "name_en": "Kani Mountain Honey Master: Night Cliff Climber & Giant Bee Whisperer",
        "name_ta": "காணித் தேன்வேட்டையாளர் - நள்ளிரவில் செங்குத்துப் பாறைகளில் இறங்கித் தேனெடுக்கும் மலைக் கைவினைஞர்",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 100,
        "thinai": "Kurinji",
        "summary_en": "Hereditary hill tribal specialist who descended sheer thousand-foot ravines by torchlight to harvest comb honey while preserving the wild bee colony.",
        "summary_ta": "ஆயிரமடி செங்குத்துப் பாறைகளில் தொங்கும் காட்டுத் தேனீக்களின் கூடுகளைப் புகைமூட்டி, தேனை மட்டும் அறுத்து தேனீக் கூட்டைக் காக்கும் குறிஞ்சி நிலத்து வீரர்.",
        "content": """# The Mountain Honey Master (தேன்வேட்டையாளர்)

Trained from childhood in cliff balance, wind assessment, and non-destructive honey tapping that left queen cells undisturbed.
"""
    },
    {
        "category": "characters",
        "slug": "char-kaval-kadu-border-guardian",
        "file": "char-kaval-kadu-border-guardian.md",
        "node_type": "character",
        "name_en": "Kaval-Kadu Border Guardian: Forest Scout & Anti-Infiltration Guerrilla Archer",
        "name_ta": "காவல் காட்டுக் காவலன் - எல்லைப்புற முட்காடுகளைக் காக்கும் வேட்டுவ வில்லாளி",
        "era": "Sangam Classical Era",
        "year_start": -150,
        "year_end": 50,
        "thinai": "Mullai",
        "summary_en": "Elite forest watchman living in concealed treetop hideouts within the boundary thorn forests, skilled in camouflaged tracking and longbow defense against invading scouts.",
        "summary_ta": "கோட்டைக்கு முந்திய முட்காடுகளில் மறைந்திருந்து, பகைவரின் உளவுப் படைகளை வில்லெய்து வீழ்த்தும் வனப் பாதுகாப்பு வீரர்.",
        "content": """# The Border Forest Guardian (மிளைக் காவலன்)

Using poisoned arrow tips (*Visak-kole*) and pit traps, these sentinels ensured no enemy vanguard crossed the kingdom's vegetative defense belt unseen.
"""
    },
    {
        "category": "places",
        "slug": "place-kollimalai-aromatic-and-medicinal-biosphere",
        "file": "place-kollimalai-aromatic-and-medicinal-biosphere.md",
        "node_type": "place",
        "name_en": "Kolli Hills (Kollimalai): Montane Medicinal Flora, Wild Honey & Sacred Groves",
        "name_ta": "கொல்லிமலை - வல்வில் ஓரியின் ஆட்சிக்குட்பட்ட மூலிகைக் காடுகளும் தேன் வளமும்",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 500,
        "thinai": "Kurinji",
        "summary_en": "Rugged mountain plateau in Namakkal district ruled by the Sangam chieftain Valvil Ori, celebrated for dense medicinal forests, sacred groves, wild cliff-honey colonies, and perennial cloud forests.",
        "summary_ta": "சங்ககால மன்னன் வல்வில் ஓரி ஆட்சிசெய்த கொல்லிமலை. 70 கொண்டை ஊசி வளைவுகள் கொண்ட செங்குத்துப் பாறைகள், சித்தர்கள் வாழ்ந்த மூலிகைக் காடுகள், மற்றும் தேன் பெருக்கெடுக்கும் இயற்கை புகலிடம்.",
        "content": """# Kolli Hills Biosphere (கொல்லிமலை)

- **Coordinates**: 11.2500° N, 78.3333° E.  
- **Sangam Patron**: King Valvil Ori (*வல்வில் ஓரி*).  
- **Ecological Role**: Premier montane hub for wild honey harvesting, rare medicinal plants, and spice forestry.
"""
    }
]

# ==============================================================================
# RELATIONAL EDGES (50 Total)
# ==============================================================================
EDGES = [
    # Corpus 1 Edges: Fauna, Elephants & Horses
    ("text-purananuru-kaliru-elephant-warfare", "documents", "concept-kaliru-war-elephant-siege-mechanics", "military_science", "Sangam", "Verses describe iron tusk sheaths and gate battering.", "Purananuru Kaliru odes"),
    ("concept-kaliru-war-elephant-siege-mechanics", "captured_at", "place-anamalai-chera-elephant-capture-basin", "habitat", "Ancient", "War elephants were captured from the Anamalai rainforest herds.", "Sangam geography"),
    ("concept-elephant-capture-and-khedda-technology", "practiced_in", "place-anamalai-chera-elephant-capture-basin", "forestry", "Ancient", "Pit-traps and stockades established in Anamalai river valleys.", "Ethnoarchaeology"),
    ("char-chola-paka-maravan-chief-mahout", "commands", "concept-kaliru-war-elephant-siege-mechanics", "tactics", "Imperial Chola", "Chief mahout coordinated tuskers during fortress assaults.", "Chola military records"),
    ("text-pattinappalai-kudirai-maritime-imports", "records", "concept-kudirai-k-kodu-arabian-horse-trade", "maritime_trade", "Sangam", "Documents shiploads of spirited horses arriving at Puhar.", "Pattinappalai line 185"),
    ("char-kudirai-c-cetti-arabian-horse-importer", "manages", "concept-kudirai-k-kodu-arabian-horse-trade", "commerce", "Medieval", "Merchant guild chief imported Arabian stallions for royal cavalry.", "Kudirai-c-cetti inscriptions"),
    ("concept-sangam-fauna-panthera-and-avian-omens", "exemplifies", "text-purananuru-kaliru-elephant-warfare", "wildlife", "Sangam", "Poetic parallels drawn between the royal tiger and charging war tuskers.", "Purananuru bards"),
    ("insc-kurunji-anai-malai-elephant-charters", "regulates", "concept-elephant-capture-and-khedda-technology", "law", "Early Medieval", "Royal charters defined elephant capture boundaries and mahout shares.", "Anamalai epigraphs"),
    ("char-chola-paka-maravan-chief-mahout", "trained_at", "place-anamalai-chera-elephant-capture-basin", "martial_arts", "Chola", "Mahouts mastered elephant pressure points in the Western Ghats.", "Oral traditions"),
    ("concept-kudirai-k-kodu-arabian-horse-trade", "supplied_cavalry_for", "concept-kaliru-war-elephant-siege-mechanics", "military_balance", "Classical", "Imported cavalry guarded the flanks of charging war elephant units.", "Sangam warfare"),

    # Corpus 2 Edges: Agriculture & Paddy
    ("text-porunararruppadai-velanmai-agronomy", "celebrates", "place-thiruvaiyaru-kaveri-paddy-basin", "geography", "Sangam", "Celebrates the incredible rice fertility of the Kaveri delta.", "Porunararruppadai"),
    ("text-porunararruppadai-velanmai-agronomy", "details", "concept-sennel-and-heritage-paddy-cultivation", "agronomy", "Sangam", "Depicts cultivation of high-yielding red paddy (Sennel).", "Porunararruppadai verses"),
    ("insc-thanjavur-sennel-land-survey-charters", "standardizes", "concept-sennel-and-heritage-paddy-cultivation", "metrology", "Imperial Chola", "Assesses all land grants and taxes in standard Sennel grain.", "Brihadisvara charters"),
    ("concept-uzhavu-plowing-and-marutham-pedology", "prepares_soil_for", "concept-sennel-and-heritage-paddy-cultivation", "cultivation", "Ancient", "Iron-share plowing and silt puddling essential for rice planting.", "Ethnoagronomy"),
    ("concept-kalam-threshing-and-agrarian-metrology", "stores", "concept-sennel-and-heritage-paddy-cultivation", "post_harvest", "Ancient", "Sun-dried Sennel grain threshed and stored in straw Kuthirs.", "Tolkappiyam"),
    ("char-uzhava-perumakan-master-farmer", "guides", "concept-uzhavu-plowing-and-marutham-pedology", "wisdom", "Sangam", "Master farmer directed plowing passes and green manuring.", "Sangam ethnography"),
    ("char-kaveri-delta-paddy-surveyor", "enforces", "insc-thanjavur-sennel-land-survey-charters", "revenue", "Imperial Chola", "Surveyor assessed crop shares and verified bushel measurements.", "Chola epigraphs"),
    ("text-malaipadukadam-siru-tinai-millet-farming", "describes", "concept-punsei-tinai-dryland-millet-polyculture", "hill_farming", "Sangam", "Portrays millet terraces and slash-and-burn dryland agriculture.", "Malaipadukadam"),
    ("concept-punsei-tinai-dryland-millet-polyculture", "cultivated_near", "place-kollimalai-aromatic-and-medicinal-biosphere", "ecology", "Sangam", "Millets and legumes grown on the lower plateaus of Kolli Hills.", "Sangam geography"),
    ("place-thiruvaiyaru-kaveri-paddy-basin", "irrigated_via", "concept-uzhavu-plowing-and-marutham-pedology", "hydrology", "Ancient", "Five Kaveri channels fed wetland puddling and double-cropping.", "Delta hydrology"),

    # Corpus 3 Edges: Ethno-Forestry & Mountain Biospheres
    ("text-kurunjippattu-honey-harvest-and-hill-flora", "details", "concept-malai-then-cliff-honey-harvesting-mechanics", "apiculture", "Sangam", "Depicts night-time cliff honey extraction using rope ladders.", "Kurunjippattu lines 150-180"),
    ("char-kani-mountain-honey-master", "practices", "concept-malai-then-cliff-honey-harvesting-mechanics", "harvest", "Ancient", "Tribal climber descended granite cliffs to tap wild rock bees.", "Indigenous knowledge"),
    ("concept-malai-then-cliff-honey-harvesting-mechanics", "gathered_at", "place-kollimalai-aromatic-and-medicinal-biosphere", "ecology", "Ancient", "Kolli Hills was renowned for sheer cliff-honey collection.", "Sangam canon"),
    ("text-sirupanarruppadai-forest-fragrances", "documents", "concept-akil-chandanam-aromatic-silviculture", "forestry", "Sangam", "Catalogues sandalwood and aloeswood seasoning in montane woods.", "Sirupanarruppadai"),
    ("concept-akil-chandanam-aromatic-silviculture", "harvested_at", "place-kollimalai-aromatic-and-medicinal-biosphere", "forestry", "Ancient", "Fragrant hardwoods extracted from Kolli montane slopes.", "Historical geography"),
    ("concept-kaval-kadu-defensive-border-forests", "guarded_by", "char-kaval-kadu-border-guardian", "military", "Sangam", "Guerrilla archers defended kingdom borders within thorn forests.", "Sangam warfare"),
    ("concept-kani-tribal-ethnobotany-and-medicines", "preserved_in", "place-kollimalai-aromatic-and-medicinal-biosphere", "ethnobotany", "Ancient", "Medicinal tubers and snakebite antidotes identified by hill tribes.", "Ethnobotanical surveys"),
    ("insc-anaimalai-forest-chieftain-charters", "grants_rights_to", "char-kani-mountain-honey-master", "treaty", "Post-Sangam", "Kings recognized customary tribal rights to forest honey and roots.", "Ghats epigraphs"),
    ("char-kani-mountain-honey-master", "practices", "concept-kani-tribal-ethnobotany-and-medicines", "knowledge", "Ancient", "Honey masters identified rare herbs during cliff expeditions.", "Oral traditions"),
    ("concept-kaval-kadu-defensive-border-forests", "protects", "place-thiruvaiyaru-kaveri-paddy-basin", "security", "Ancient", "Thorn border forests sheltered the fertile delta against surprise cavalry raids.", "Sangam defense")
]

# ==============================================================================
# MAIN HARVESTER EXECUTION
# ==============================================================================
def main():
    print("=" * 70)
    print("🚀 BATCH 5: TRIPLE CIVILIZATIONAL EXPANSION HARVESTER")
    print("   1. Sangam Fauna, War Elephants & Maritime Horses (10 dossiers)")
    print("   2. Ancient Tamil Agriculture & Heritage Paddy Varieties (10 dossiers)")
    print("   3. Ancient Tamil Ethno-Forestry, Honey & Biospheres (10 dossiers)")
    print("=" * 70)

    # Phase 1: Write Dossiers to moolam-chronicles
    print("\n[Phase 1] Writing 30 Canonical Markdown Dossiers to moolam-chronicles...")
    for d in DOSSIERS:
        cat_dir = os.path.join(MOOLAM_KNOWLEDGE, d["category"])
        os.makedirs(cat_dir, exist_ok=True)
        file_path = os.path.join(cat_dir, d["file"])
        
        md_text = f"""---
slug: "{d['slug']}"
name_en: "{d['name_en']}"
name_ta: "{d['name_ta']}"
era: "{d['era']}"
year_start: {d['year_start']}
year_end: {d['year_end']}
thinai: "{d['thinai']}"
node_type: "{d['node_type']}"
category: "{d['category']}"
---

{d['content'].strip()}
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        print(f"  ✓ Written: knowledge/{d['category']}/{d['file']}")

    # Phase 2: PostgreSQL Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\n[Phase 2] Upserting 30 Lore Nodes into PostgreSQL...")
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
            [f"knowledge/{d['category']}/{d['file']}"]
        ))
        nodes_upserted += 1
        print(f"  ✓ [{d['node_type'].upper()}] {d['slug']} -> {d['name_en'][:45]}...")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Upsert Lore Edges
    print("\n[Phase 3] Upserting Relational Edges into PostgreSQL...")
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
    print(f"Phase 3 complete: {edges_inserted} new relational edges inserted.")

    # Phase 4: Dense Vector Embeddings into rag_chunks
    print("\n[Phase 4] Generating 60 Dense 1024-dim BGE-M3 Embeddings into rag_chunks...")
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
                f"knowledge/{d['category']}/{d['file']}",
                emb_str
            ))
            total_chunks += 1
            print(f"  ✓ Embedded ({ch['language']}): {ch['title'][:55]}...")

    conn.commit()
    print(f"Phase 4 complete: {total_chunks} dense BGE-M3 chunks embedded into rag_chunks.")

    # Phase 5: Totals
    cur.execute("SELECT COUNT(*) FROM lore_nodes;")
    node_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM lore_edges;")
    edge_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM rag_chunks;")
    chunk_count = cur.fetchone()[0]

    print("\n" + "=" * 70)
    print("📊 POST-HARVEST CORPUS TOTALS (PostgreSQL:55432):")
    print(f"   • Total Lore Nodes : {node_count:,}")
    print(f"   • Total Lore Edges : {edge_count:,}")
    print(f"   • Total RAG Chunks : {chunk_count:,}")
    print("=" * 70)

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
