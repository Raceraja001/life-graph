#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 10):
1. Ancient Perfumery, Sandalwood Distillation & Aromatic Cosmetology (10 dossiers)
2. Maritime Lighthouse Architecture, Night Beacons & Coastal Piloting (10 dossiers)
3. Sangam Ceramic Engineering, Black-and-Red Ware & Updraft Pyrotechnics (10 dossiers)

Total: 30 Canonical Dossiers, ~30 Relational Edges, 60 Dense 1024-dim BGE-M3 Embeddings.
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
    # CORPUS 1: ANCIENT PERFUMERY, SANDALWOOD DISTILLATION & AROMATICS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-silappadikaram-aromatic-cosmetic-canon",
        "file": "text-silappadikaram-aromatic-cosmetic-canon.md",
        "node_type": "text",
        "name_en": "Silappadikaram & Sangam Lexica: The Sixty-Four Fragrant Pastes, Sandalwood & Agarwood",
        "name_ta": "சிலப்பதிகாரம் மற்றும் சங்க இலக்கிய வாசனைத் திரவியங்கள் - அறுபத்து நான்கு நறுமணக் கலை",
        "era": "Sangam Post-Classical Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "Marutham",
        "summary_en": "Canonical poetic documentation in Silappadikaram (Ur-Kaan Kadhai and Adaikkala Kadhai) detailing the elaborate cosmetology of ancient Tamil cities: compounding 64 botanical fragrances, red and white sandalwood pastes (Santhanam), fumigating tresses with resinous agarwood smoke (Akil), and blending cooling camphor (Karpooram).",
        "summary_ta": "சிலப்பதிகாரத்தின் ஊர்காண் காதை மற்றும் அடைக்கலக் காதையில் விவரிக்கப்படும் நறுமண ஒப்பனைக் கலை. அறுபத்து நான்கு வகை வாசனைத் திரவியங்களை அரைத்துக் கூட்டுதல், பொதியமலைச் சந்தனம், அகில் புகை யூட்டுதல், பனிநீர், கஸ்தூரி, புனுகு மற்றும் பச்சைக் கற்பூரப் பயன்பாடுகள்.",
        "content": """# Silappadikaram Aromatic Canon (நறுமணக் கலை)

**Source**: *Silappadikaram* (*சிலப்பதிகாரம்*), *Manimekalai* (*மணிமேகலை*).  
**Subject**: Indigenous Perfumery (*சுவந்தக் கலை*), Sandalwood & Agarwood Maceration.  

---

## 1. The Sixty-Four Fragrant Ingredients (*அறுபத்து நான்கு வகை வாசனை*)
Tamil urban elites, courtesans, and royal temples utilized an exhaustive botanical palette:
- **Sandalwood (*சந்தனம்*)**: Pothigai and Western Ghats white sandalwood (*Santalum album*) ground wet on basalt slabs.
- **Agarwood (*அகில்*)**: Resin-infused heartwood of *Aquilaria agallocha* burned in bronze braziers (*தூபக் கூண்டு*) to scent garments and hair.
- **Civet (*புனுகு*) & Musk (*கஸ்தூரி*)**: Animal musk fixatives blended into floral distillates to prolong evaporative sillage.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kallidaikurichi-sandalwood-guild-charters",
        "file": "insc-kallidaikurichi-sandalwood-guild-charters.md",
        "node_type": "inscription",
        "name_en": "Kallidaikurichi Sandalwood Guild Charters: Aromatic Tribute & Temple Unguent Endowments",
        "name_ta": "கல்லிடைக்குறிச்சி சந்தன வணிகர் கல்வெட்டுகள் - நறுமணத் திறை மற்றும் கோயில் சந்தனக் காப்பு மானியம்",
        "era": "Early Medieval to Pandya Era",
        "year_start": 950,
        "year_end": 1250,
        "thinai": "Mullai",
        "summary_en": "Pandyan epigraphs at Kallidaikurichi recording royal concessions granted to aromatic merchant guilds (*Manigramam* and *Anjuvannam*) trading mountain sandalwood from the Pothigai ranges, mandating daily supplies of pure paste for deity unguent rituals (Santhana-kaappu).",
        "summary_ta": "கல்லிடைக்குறிச்சிக் கோயில்களில் உள்ள பாண்டியர் கல்வெட்டுகள். பொதியமலைச் சாரலில் சந்தனம் சேகரித்து விற்ற மணிக்கிராம வணிகர்களுக்கு வழங்கப்பட்ட வரிச்சலுகைகள், மற்றும் நாள்தோறும் இறைவனுக்குச் சாத்த வேண்டிய சந்தனக் காப்புக்கான நிரந்தர நிதி ஒதுக்கீடுகள்.",
        "content": """# Kallidaikurichi Sandalwood Charters (சந்தனச் சாசனம்)

---

## 1. Commercial Concessions for Aromatics
The charters establish that sandalwood caravans descending from the Agasthyamalai forests enjoyed exemption from local transit tolls (*Ullayam*), provided they supplied measured weights (*Palam*) of aromatic heartwood to the central temple storehouse.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thiruvaiyaru-fragrance-endowment-charters",
        "file": "insc-thiruvaiyaru-fragrance-endowment-charters.md",
        "node_type": "inscription",
        "name_en": "Thiruvaiyaru Temple Charters: Camphor (Karpooram), Rosewater & Saffron Unguent Grants",
        "name_ta": "திருவையாறு நறுமண தானக் கல்வெட்டுகள் - பச்சைக் கற்பூரம், பனிநீர் மற்றும் குங்குமப்பூ காப்பு சாசனம்",
        "era": "Imperial Chola Era",
        "year_start": 1000,
        "year_end": 1150,
        "thinai": "Marutham",
        "summary_en": "Monumental Chola inscriptions on the Panchanadeeswara temple at Thiruvaiyaru recording perpetual endowments deposited in gold to purchase imported Barus camphor (Pachai Karpooram), saffron (Kunkumapoo), and floral distillates for daily sacred ablutions.",
        "summary_ta": "திருவையாறு ஐயாறப்பர் கோயிலில் உள்ள சோழர் காலத்து கல்வெட்டுகள். சுமாத்திரா பாருஸ் தீவிலிருந்து இறக்குமதியான பச்சைக் கற்பூரம், காஷ்மீரக் குங்குமப்பூ மற்றும் நறுமணத் தைலங்களை நாள்தோறும் இறைவனுக்கு அபிஷேகம் செய்ய அரச குடும்பத்தினர் பொன் முதலீடு செய்த ஆவணங்கள்.",
        "content": """# Thiruvaiyaru Fragrance Charters (திருவையாறு வாசனை தானம்)

---

## 1. Ritual Consumption of Exotic Aromatics
The epigraph specifies:
- 1 *Kasunirai* of refined Barus camphor (*கற்பூரம்*) burned at twilight.
- 5 *Palams* of ground sandalwood mixed with saffron for the midday cooling paste (*சாந்துப் பூச்சு*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-sandalwood-grinding-and-clay-hydro-distillation",
        "file": "concept-sandalwood-grinding-and-clay-hydro-distillation.md",
        "node_type": "concept",
        "name_en": "Sandalwood Paste Grinding, Maceration & Retort Distillation Pyrotechnics",
        "name_ta": "சந்தனக் கல் அரைப்பு, ஊறவைத்தல் மற்றும் சுடுமண் காய்ச்சி வடித்தல் நுட்பம்",
        "era": "Classical to Medieval Era",
        "year_start": 100,
        "year_end": 1300,
        "thinai": "Mullai",
        "summary_en": "The chemical and mechanical extraction of volatile plant essences in ancient Tamilakam: circular basalt grinding slabs (Santhana-kallu) lubricated with rosewater, coupled with primitive clay alembics and retorts used for steam hydro-distillation of floral oils.",
        "summary_ta": "தமிழரின் நறுமண வடித்தல் வேதியியல் முறை. வட்ட வடிவ கருங்கல் பலகைகளில் சந்தனக் கட்டைகளை பனிநீர் விட்டு உரைக்கும் முறை, மற்றும் சுடுமண் கலயங்கள், மூங்கில் குழாய்கள் கொண்டு நறுமணப் பூக்களிலிருந்து ஆவி வடித்து தைலம் எடுக்கும் காய்ச்சிவடித்தல் (Hydro-distillation) தொழில்முறை.",
        "content": """# Sandalwood Grinding & Distillation Pyrotechnics (வடித்தல் கலை)

---

## 1. The Basalt Grinding Slab (*சந்தனக் கல்*)
- Fine-grained dolerite or charnockite stones dressed to slight abrasive convexity.
- Grinding was performed in concentric counter-clockwise strokes to generate silky, particle-free emulsions without heating the volatile santalol terpenes.

## 2. Clay Alembic Distillation (*தைலக் குடுவை*)
Double-pot earthenware vessels connected by bamboo condensors: fragrant vetiver roots, screwpine (*Thazhambu*), and jasmine were submerged in water and heated gently over husks to distill essential oils into cool receiving flasks.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-agarwood-smoking-and-civet-musk-blending",
        "file": "concept-agarwood-smoking-and-civet-musk-blending.md",
        "node_type": "concept",
        "name_en": "Agarwood (Akil) Fumigation, Civet (Punugu) & Musk (Kasthuri) Formulation",
        "name_ta": "அகில் புகை யூட்டுதல், புனுகு மற்றும் கஸ்தூரி நறுமணச் சேர்க்கை நெறிமுறை",
        "era": "Classical to Imperial Chola Era",
        "year_start": 200,
        "year_end": 1250,
        "thinai": "Kurinji",
        "summary_en": "The luxury olfactory arts of the Tamil court: harvesting resinous fungal-infected agarwood from deep hill tracts, burning shavings over charcoal embers beneath latticed wicker hair-frames (Akil-koodu), and fixing transient floral notes with civet secretion and deer musk.",
        "summary_ta": "அரண்மனை மற்றும் செல்வந்தர் இல்லங்களில் நிலவிய அகில் நறுமணப் புகை முறை. கூந்தலிலும் பட்டாடைகளிலும் அகில் புகையை ஏற்றுவதற்கான மூங்கில் கூடைகள், மற்றும் புனுகுப்பூனைச் சுரப்பு, கஸ்தூரி மானின் கத்தூரி ஆகியவற்றை நறுமண நிலைநிறுத்தியாகப் (Fixative) பயன்படுத்திய விதம்.",
        "content": """# Agarwood Fumigation & Animal Musk Blending (அகில் புகை)

---

## 1. The Akil-Koodu Frame (*அகில் கூடு*)
Women dried and scented washed hair by draping tresses over dome-shaped wicker or bamboo frames inverted above smoking bronze censers loaded with crushed agarwood and frankincense shavings.

## 2. Fixing Odor Profiles
Raw civet (*Punugu*) was purified through milk washes and blended at 1–2% ratios into sandalwood paste, preventing rapid evaporation under tropical heat and enhancing skin persistence for over 24 hours.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-javvadu-and-attar-herbal-cosmetology",
        "file": "concept-javvadu-and-attar-herbal-cosmetology.md",
        "node_type": "concept",
        "name_en": "Javvadu Powder Formulation, Floral Attars & Royal Bath Unguents (Suvandar)",
        "name_ta": "ஜவ்வாதுப் பொடி தயாரிப்பு, பூந்தயிர் மற்றும் அரச நறுமண நீராட்டுப் பொடிகள்",
        "era": "Early Medieval to Chola Era",
        "year_start": 600,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The complex powder and unguent pharmacology of medieval South India: Javvadu compounded from roasted sandalwood root, saffron, nutmeg, and aromatic resins, serving as dry body deodorants, ceremonial forehead tilakas, and medicinal bath emollients.",
        "summary_ta": "தென்னிந்தியாவின் பாரம்பரிய நறுமணப் பொடி தயாரிப்பு. சந்தன வேர், ஜாதிக்காய், ஏலக்காய், குங்குமப்பூ மற்றும் நறுமணப் பசைகளை அரைத்து உருவாக்கப்பட்ட ஜவ்வாது. உடல் வியர்வை நாற்றத்தை நீக்கும் இயற்கை ஒப்பனையாகவும், வழிபாட்டுத் திலகமாகவும் விளங்கிய மரபு.",
        "content": """# Javvadu Formulation & Herbal Cosmetology (ஜவ்வாதுக் கலை)

---

## 1. Formulation Matrix
- Base: 60% aged sandalwood root flour (*சந்தனத் தூள்*).
- Floral Essential Extracts: Pandanus (*தாழம்பூ*), Champaka, and night-flowering Jasmine.
- Binder: Purified civet gum providing velvety cohesion and water-repellent adhesion to skin.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-aromatic-guild-networks-and-forest-concessions",
        "file": "concept-aromatic-guild-networks-and-forest-concessions.md",
        "node_type": "concept",
        "name_en": "Aromatic Guild Networks: Manigramam Sandalwood Concessions & Western Ghats Biospheres",
        "name_ta": "நறுமண வணிகக் குழுக்கள் - மணிக்கிராம சந்தன உரிமங்கள் மற்றும் மேற்குத் தொடர்ச்சி மலை வர்த்தகம்",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 800,
        "year_end": 1250,
        "thinai": "Mullai",
        "summary_en": "The corporate commercial networks regulating the collection and global export of forest aromatics: merchant corporations (Manigramam, Ainnurruvar) negotiating harvesting pacts with hill chieftains (Kani-alar), managing bulk warehousing and maritime export across the Indian Ocean.",
        "summary_ta": "வாசனைப் பண்டங்களின் சர்வதேச விநியோகத்தை நிர்வகித்த பெருவணிகக் கூட்டமைப்புகள். மலைவாழ் மக்களுடன் ஒப்பந்தம் செய்து சந்தனம், மிளகு, ஏலக்காய், இலவங்கம் ஆகியவற்றை மொத்தமாகச் சேகரித்து துறைமுகங்கள் வழியே அரபுலகிற்கும் சீனத்திற்கும் ஏற்றுமதி செய்த முறை.",
        "content": """# Aromatic Guild Commerce (வாசனை வணிகக் குழுக்கள்)

---

## 1. Forest Royalties & Supply Chains
Guilds maintained fortified relay stations along mountain passes (Palakkad Gap, Shencottah Gap), transporting debarked sandalwood logs on pack bullocks directly to coastal ports (Korkai, Nagapattinam).
"""
    },
    {
        "category": "characters",
        "slug": "char-madurai-master-perfumer-suvanta-karar",
        "file": "char-madurai-master-perfumer-suvanta-karar.md",
        "node_type": "character",
        "name_en": "Suvanta-Karar: Royal Perfumer of Ancient Madurai & Master of Sixty-Four Fragrances",
        "name_ta": "சுவந்தக்காரர் - பண்டைய மதுரையின் அரச வாசனை ஆசான் மற்றும் நறுமண வல்லுநர்",
        "era": "Sangam to Pandya Era",
        "year_start": 200,
        "year_end": 600,
        "thinai": "Marutham",
        "summary_en": "Eminent court cosmetologist and scent compounding master in Madurai celebrated in Sangam literature, possessing sensory expertise to diagnose pure versus adulterated sandalwood and blending custom aromatic pomades for royal ceremonies.",
        "summary_ta": "மதுரை அரசவையில் பணியாற்றிய தலைமை வாசனை திரவியக் கலைஞர். அறுபத்து நான்கு வகை இயற்கை நறுமணங்களை இனம் கண்டு, கலவை விகிதங்களைத் தீர்மானித்து மன்னர்களுக்கும் கோயில்களுக்கும் ஒப்பனைத் தைலங்களை உருவாக்கிய வல்லுநர்.",
        "content": """# The Royal Master Perfumer (சுவந்தக்காரர்)

Mastered olfactory balance, testing volatile evaporation rates on unglazed terracotta sherds and creating seasonal unguents (cooling pastes for summer, warming resin oils for winter monsoons).
"""
    },
    {
        "category": "characters",
        "slug": "char-western-ghats-agarwood-harvester",
        "file": "char-western-ghats-agarwood-harvester.md",
        "node_type": "character",
        "name_en": "Western Ghats Agarwood Harvester: Forest Tracker of Infected Heartwood",
        "name_ta": "அகில் வேட்டைக்காரர் - பொதியமலைக் காடுகளில் வாசனை மரங்களை இனம் காணும் வேடுவர்",
        "era": "Classical to Medieval Era",
        "year_start": 300,
        "year_end": 1000,
        "thinai": "Kurinji",
        "summary_en": "Skilled indigenous tracker of the deep evergreen forests who identified mature agarwood trees bearing the dark, resinous, aromatic heartwood produced by mold infection, extracting prized logs for temple and court guilds.",
        "summary_ta": "மேற்குத் தொடர்ச்சி மலையின் அடர்ந்த காடுகளில் பல தலைமுறைகளாக வாழ்ந்து, இயல்பான மரங்களுக்கும் வாசனைப் பிசின் நிறைந்த அகில் மரங்களுக்கும் உள்ள வேறுபாட்டை வாசனையாலும் பட்டையாலும் அறிந்து வெட்டி எடுத்த கானக வல்லுநர்.",
        "content": """# The Agarwood Tracker (அகில் சேகரிப்பாளர்)

Navigated treacherous cliff terrain and leech-infested streams, using traditional tapping methods that spared young saplings while harvesting resin-dense mature heartwood.
"""
    },
    {
        "category": "places",
        "slug": "place-courtallam-aromatic-hill-groves",
        "file": "place-courtallam-aromatic-hill-groves.md",
        "node_type": "place",
        "name_en": "Courtallam: Western Ghats Medicinal Flora, Sandalwood Grooves & Scented Cascades",
        "name_ta": "குற்றாலம் - பொதியமலைச் சாரலின் மூலிகைக் காடுகளும் நறுமண அருவிகளும்",
        "era": "Sangam to Pandya Era",
        "year_start": 200,
        "year_end": 1250,
        "thinai": "Kurinji",
        "summary_en": "Historic forested foothills and sacred cascade sanctuary in the Chittar river basin (Tenkasi / Tirunelveli), celebrated in Tamil literature for dense natural sandalwood forests, medicinal herb-infused waterfalls, and Pandyan temple unguent endowments.",
        "summary_ta": "தென்காசி அருகே பொதியமலை அடிவாரத்தில் அமைந்துள்ள உலகப் புகழ்பெற்ற இயற்கை எழில் தளம். மூலிகைக் காடுகளின் வழியே பாய்ந்து வரும் நறுமண அருவிகள், சந்தன மரச் சோலைகள் மற்றும் பாண்டிய மன்னர்களின் நறுமண தானக் கல்வெட்டுகள் நிறைந்த வரலாற்று மையம்.",
        "content": """# Courtallam Aromatic Sanctuary (குற்றாலம்)

- **Coordinates**: 8.9300° N, 77.2700° E.  
- **District**: Tenkasi District, Tamil Nadu.  
- **Significance**: Epicenter of Western Ghats botanical aromatic harvesting and temple unguent preparation across two millennia.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: MARITIME LIGHTHOUSE ARCHITECTURE & NIGHT BEACONS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-perumpanarruppadai-ilangu-sudar-lighthouse-poetry",
        "file": "text-perumpanarruppadai-ilangu-sudar-lighthouse-poetry.md",
        "node_type": "text",
        "name_en": "Perumpanarruppadai: The Ilangu-Sudar Masonry Lighthouse & Coastal Night Flares",
        "name_ta": "பெரும்பாணாற்றுப்படை கலங்கரை விளக்கம் - இலங்கு சுடர் மாடமும் இரவுக் கடலோரத் தீபமும்",
        "era": "Sangam Classical Era",
        "year_start": 100,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "Famous Sangam poem in Pattuppattu by poet Kadiyalur Uruttirangannanar (lines 346–351) describing the tall brick-and-mortar lighthouse (*Ilangu-sudar azhuvathu*) erected on the coast of Nirppeyarru / Poompuhar, burning bright vegetable oil flares to guide disoriented sea captains.",
        "summary_ta": "பத்துப்பாட்டின் பெரும்பாணாற்றுப்படையில் இடம்பெறும் விழிப்பூட்டும் வரிகள். 'வானம் ஊன்றிய மதலை போல, ஏணி சாத்திய ஏற்றரும் சென்னி... இரவில் மாட்டிய இலங்கு சுடர் ஞெகிழி' என வானைத் தொடும் தூண் போன்ற மாடத்தின் உச்சியில் இரவுதோறும் ஏற்றப்பட்ட பிரம்மாண்ட கலங்கரை விளக்கத்தின் சங்க கால நேரடி வர்ணனை.",
        "content": """# Perumpanarruppadai Lighthouse Poetry (இலங்கு சுடர்)

**Source**: *Perumpanarruppadai* (*பெரும்பாணாற்றுப்படை*), Lines 346–351.  
**Poet**: Kadiyalur Uruttirangannanar (*கடியலூர் உருத்திரங்கண்ணனார்*).  

---

## 1. The Classical Lighthouse Architectural Verse
*"வானம் ஊன்றிய மதலை போல  
ஏணி சாத்திய ஏற்றரும் சென்னி  
விண்பொர நிவந்த வேயா மாடத்து  
இரவில் மாட்டிய இலங்கு சுடர் ஞெகிழி  
உரவுநீர் அழுவத்து ஓடுகலம் கரையும்..."*  

(Like a colossal pillar propping up the heavens, its laddered summit impossible to scale, the whitewashed open-terraced tower burns a brilliant flaming beacon through the night, beckoning ships tossed on the churning ocean!)
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-poompuhar-maritime-beacon-foundations",
        "file": "insc-poompuhar-maritime-beacon-foundations.md",
        "node_type": "inscription",
        "name_en": "Poompuhar Underwater Marine Excavations & Harbor Beacon Tower Foundations",
        "name_ta": "பூம்புகார் கடலடி தொல்லியல் ஆய்வுகள் - கலங்கரை மாடக் கட்டுமான அடித்தளங்கள்",
        "era": "Sangam Early Historic Era",
        "year_start": -200,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "Marine archaeological excavations by the National Institute of Oceanography (NIO) at Poompuhar (Kaveripattinam) revealing semi-circular brick structures, massive dressed granite jetty foundations, and collapsed watch-tower beacon bases submerged 5 to 7 meters underwater.",
        "summary_ta": "பூம்புகார் கடற்பகுதியில் தேசிய கடல்சார் தொல்லியல் நிறுவனம் (NIO) மேற்கொண்ட கடலடி அகழ்வாராய்ச்சிகள். 5 முதல் 7 மீட்டர் ஆழத்தில் கண்டறியப்பட்ட அரைவட்ட செங்கல் மேடைகள், கருங்கல் தூண்கள் மற்றும் சங்க இலக்கியம் கூறும் கலங்கரை விளக்கக் கோபுரத்தின் கடலடி எச்சங்கள்.",
        "content": """# Poompuhar Submerged Beacon Foundations (பூம்புகார் கடலடி எச்சங்கள்)

---

## 1. Architectural Evidence Underwater
- Semicircular brick platforms made of large Sangam-sized baked bricks ($42 \\times 21 \\times 7$ cm).
- Timber beam sockets aligned with harbor entrance channels, confirming fixed navigation beacons operated during tidal surges.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-marakkanam-eyil-pattinam-beacon-charters",
        "file": "insc-marakkanam-eyil-pattinam-beacon-charters.md",
        "node_type": "inscription",
        "name_en": "Marakkanam (Sopatma) Coastal Beacon Epigraphs: Harbor Tolls & Pilotage Dues",
        "name_ta": "மரக்காணம் எயிற்பட்டினம் கல்வெட்டுகள் - கலங்கரை வரி மற்றும் துறைமுக வழிகாட்டி ஆவணம்",
        "era": "Sangam to Chola Era",
        "year_start": 200,
        "year_end": 1100,
        "thinai": "Neithal",
        "summary_en": "Epigraphs at Marakkanam (the classical port Sopatma of the Periplus and Eyilpattinam of Sangam poetry) recording harbor customs regulations, pilotage cesses (*Kalam-parisu*), and endowments to maintain the coastal beacon fires guiding merchantmen through estuarine sandbars.",
        "summary_ta": "மரக்காணம் கடற்கரைக் கல்வெட்டுகள். உரோம வணிகக் கப்பல்கள் வந்து தங்கிய 'சோபத்மா' துறைமுகத்தில், மணல் மேடுகளைக் கடக்க மாலுமிகளுக்கு வழிகாட்டிய படகோட்டிகளுக்கான ஊதியம் மற்றும் கலங்கரை விளக்குகளுக்கு எண்ணெய் வழங்க விதிக்கப்பட்ட துறைமுக வரிகள்.",
        "content": """# Marakkanam Beacon Charters (மரக்காணச் சாசனங்கள்)

---

## 1. Tolls Dedicated to Light Maintenance
Vessels docking at the mouth of the backwaters contributed a statutory fraction of salt and imported Mediterranean wine to fuel the continuous nighttime warning fires at the harbor mouth.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-deepa-stambham-masonry-lighthouse-engineering",
        "file": "concept-deepa-stambham-masonry-lighthouse-engineering.md",
        "node_type": "concept",
        "name_en": "Deepa-Stambham Masonry Architecture: High Towers, Oil Reservoirs & Reflector Flares",
        "name_ta": "தீப ஸ்தம்பம் மற்றும் மாடக் கலங்கரை விளக்கம் - செங்கல் கட்டுமானம் மற்றும் எண்ணெய் தொட்டிப் பொறியியல்",
        "era": "Classical to Medieval Era",
        "year_start": 100,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "The civil and mechanical engineering of ancient Tamil lighthouses (*Deepa-stambham* / *Maada-vilakku*): erected from salt-resistant vitrified bricks and lime mortar, featuring spiral access stairways, high-capacity coconut-sesame oil vats, and polished bronze or mica reflector shields.",
        "summary_ta": "பண்டைத் தமிழகக் கலங்கரை விளக்கங்களின் பொறியியல் கட்டமைப்பு. கடல் உப்புக்காற்றைத் தாங்கும் சுட்ட செங்கற்கள் மற்றும் சுண்ணச்சாந்து, சுழல் படிக்கட்டுகள், நூற்றுக்கணக்கான லிட்டர் எண்ணெய் கொள்ளளவு கொண்ட செப்புத் தொட்டிகள் மற்றும் ஒளியைப் பெருக்கும் பளபளப்பான வெண்கலப் பிரதிபலிப்பான்கள்.",
        "content": """# Deepa-Stambham Architectural Engineering (கலங்கரை மாடம்)

---

## 1. Structural Design Parameters
- **Height**: Typically 20 to 30 meters, elevated on natural sand bluffs to achieve a visual horizon of 15 to 20 nautical miles.
- **Top Platform (*வேயா மாடம்*)**: Open-air parapet designed to withstand cyclonic gales, housing an iron brazier (*ஞெகிழி*) with continuous draft channels.
- **Fuel Supply**: Castor and illupai (*Madhuca longifolia*) oil yielding smoke-free luminous yellow flames visible across heavy sea mists.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-coastal-bonfire-beacons-and-channel-piloting",
        "file": "concept-coastal-bonfire-beacons-and-channel-piloting.md",
        "node_type": "concept",
        "name_en": "Coastal Night Beacons: High Earthen Mounds, Pitch Flares & Harbor Entrance Piloting",
        "name_ta": "கடலோரத் தீமூட்டல் மற்றும் வழிசெலுத்தல் - மணல் மேட்டுத் தீபங்கள் மற்றும் முகத்துவாரப் பாதுகாப்பு",
        "era": "Sangam Early Historic Era",
        "year_start": -200,
        "year_end": 400,
        "thinai": "Neithal",
        "summary_en": "The auxiliary navigation network of coastal beacons across Tamilakam: constructing conical earth-and-rubble beacons on promontories, kindling resinous driftwood and tar flares during storms, and signaling safe harbor approaches to deep-draft vessels.",
        "summary_ta": "கோபுரங்கள் அற்ற கடற்பகுதிகளில் இயற்கை மணல் குன்றுகளின் மீது மூட்டப்பட்ட வழிகாட்டுத் தீமூட்டல்கள். காய்ந்த மரக்கட்டைகள் மற்றும் மரப்பிசின்களைக் கொண்டு மூட்டப்பட்ட பெரும் தீப்பந்தங்கள், புயல் காலங்களில் கப்பல்கள் பவளப்பாறைகளில் மோதி உடையாமல் காத்த முறை.",
        "content": """# Coastal Bonfire Navigation Systems (கடலோரத் தீமூட்டல்)

---

## 1. Triangulation Guidance
Harbor entrances (such as Poompuhar, Korkai, and Muziris) maintained pairs of fires:
- Aligning the higher rear beacon with the lower forward beacon provided sea captains with a visual transit line, guaranteeing deep water over dangerous sandbars.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-shoal-warning-buoys-and-estuary-sounding-leads",
        "file": "concept-shoal-warning-buoys-and-estuary-sounding-leads.md",
        "node_type": "concept",
        "name_en": "Shoal Warning Systems: Moored Float Buoys, Lead-Line Soundings & Estuary Tides",
        "name_ta": "பவளப்பாறை எச்சரிக்கைப் புறவிகள் - மிதவைக் குண்டுகள், ஈயக் குண்டு ஆழமறிதல் மற்றும் ஓதக் கணிப்பு",
        "era": "Classical to Medieval Era",
        "year_start": 100,
        "year_end": 1250,
        "thinai": "Neithal",
        "summary_en": "Hydrographic safety protocols in ancient Tamil waters: deploying tarred wooden and cork float buoys moored to granite sinkers to mark underwater reefs, accompanied by lead-weighted tallow sounding lines (*Aazha-kollu*) to measure bottom depth and detect mud vs. rock.",
        "summary_ta": "கடல் ஆழத்தையும் பாறைகளையும் கண்டறியும் தொல் தமிழர் நீரியல் கருவிகள். தார் பூசப்பட்ட மர மிதவைகள் மூலம் ஆபத்தான பாறைகளை அடையாளப்படுத்துதல், மற்றும் ஈயக் குண்டுகளின் அடியில் விலங்கு கொழுப்பைத் தடவி ஆழத்தையும் தரையின் தன்மையையும் (மணல் அல்லது பாறை) அறியும் ஆழ அளவீட்டு முறை.",
        "content": """# Shoal Buoys & Sounding Technology (கடல் ஆழமறிதல்)

---

## 1. The Tallow Sounding Lead (*ஆழக் குண்டு*)
A heavy conical lead weight attached to a graduated hemp cord:
- The cavity at the base of the lead was filled with sticky animal fat.
- When dropped to the seabed, it brought up adhered sand, shell fragments, or clay, allowing the navigator to deduce their exact position relative to coastal charts even in zero-visibility fog.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-maritime-pilot-corporations-and-harbor-tolls",
        "file": "concept-maritime-pilot-corporations-and-harbor-tolls",
        "file": "concept-maritime-pilot-corporations-and-harbor-tolls.md",
        "node_type": "concept",
        "name_en": "Coastal Pilot Guilds: Pilotage Protocols, Anchorage Dues & Storm Warning Signals",
        "name_ta": "துறைமுக வழிகாட்டித் தொழிற்குழுக்கள் - பைலட் மரபுகள், நங்கூர வரிகள் மற்றும் புயல் எச்சரிக்கை",
        "era": "Early Historic to Imperial Chola Era",
        "year_start": 100,
        "year_end": 1250,
        "thinai": "Neithal",
        "summary_en": "The institutional governance of ancient Tamil harbor navigation: professional pilot guilds (*Kalam-oottuvor*) whose certified pilots rowed out in light catamarans to board arriving foreign vessels, piloting them safely through river deltas into enclosed docks.",
        "summary_ta": "பண்டைத் துறைமுகங்களின் அதிகாரப்பூர்வ கப்பல் வழிகாட்டி அமைப்புகள். வெளிநாட்டுக் கப்பல்கள் துறைமுகத்தை நெருங்கும் போது, உள்ளூர் வழிகாட்டிகள் சிறிய கட்டுமரங்களில் சென்று ஏறி, நதியின் முகத்துவார வண்டல் மேடுகளைத் தாண்டி நங்கூரமிட வழிநடத்திய தொழில்முறை முறைமை.",
        "content": """# Maritime Pilot Corporations (கப்பல் வழிகாட்டிகள்)

---

## 1. Pilotage Liability
Pilots were legally accountable under royal maritime law: failure due to negligence incurred severe restitution penalties, while successful maneuvering during monsoon swells was rewarded with a fixed share of custom toll revenues.
"""
    },
    {
        "category": "characters",
        "slug": "char-poompuhar-lighthouse-keeper-deepa-kavalar",
        "file": "char-poompuhar-lighthouse-keeper-deepa-kavalar.md",
        "node_type": "character",
        "name_en": "Deepa-Kavalar: Master Keeper of the Poompuhar Tower & Oil Flare Tender",
        "name_ta": "தீபக் காவலர் - பூம்புகார் கலங்கரை மாடத்தின் தலைமைப் பொறுப்பாளர் மற்றும் சுடர்த் தலைவர்",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "Chief lighthouse warden of ancient Kaveripattinam, responsible for maintaining continuous fuel oil supply to the masonry tower brazier, tending reflectors, and sounding warning conch trumpets during dense sea squalls.",
        "summary_ta": "பூம்புகாரின் 30 மீட்டர் உயர கலங்கரை மாடத்தைப் பாதுகாத்து இயக்கிய தலைமை அதிகாரி. இரவு முழுவதும் தீ அணையாமல் எண்ணெயை ஊற்றிப் பராமரித்தல், பனிமூட்டக் காலங்களில் பெருஞ்சங்குகளை முழங்கி கப்பல்களை எச்சரித்த மாலுமி.",
        "content": """# The Master Lighthouse Keeper (தீபக் காவலர்)

Climbed the interior timber ladder nightly bearing oil jars, reading offshore cloud formations to anticipate sudden squalls and illuminating the primary beacon before sunset.
"""
    },
    {
        "category": "characters",
        "slug": "char-marakkanam-estuary-harbor-pilot",
        "file": "char-marakkanam-estuary-harbor-pilot.md",
        "node_type": "character",
        "name_en": "Marakkanam Harbor Pilot: Sounding Lead Specialist & Sandbar Navigator",
        "name_ta": "மரக்காண முகத்துவார வழிகாட்டி - மணல்மேடு நீக்கி நங்கூரம் பாய்ச்சிய கப்பலோட்டி",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 250,
        "thinai": "Neithal",
        "summary_en": "Expert local mariner stationed at Sopatma / Marakkanam who possessed intimate knowledge of shifting estuarine sandbanks and tidal rips, steering Roman and Alexandrian merchantmen into sheltered lagoon docks.",
        "summary_ta": "மரக்காணத்தின் உப்பங்கழி முகத்துவாரத்தை அக்குவேறு ஆணிவேறாக அறிந்த உள்ளூர் மாலுமி. உரோமர்களின் பெரும் பாய்மரக் கப்பல்களை மணல் திட்டுகளில் சிக்காமல் துறைமுகத்திற்குள் பத்திரமாக வழிநடத்தியவர்.",
        "content": """# The Estuary Harbor Pilot (முகத்துவார வழிகாட்டி)

Read water coloration and surface wave chop to assess underwater bar depths, directing deck crews with specialized whistle signals.
"""
    },
    {
        "category": "places",
        "slug": "place-marakkanam-sopatma-historic-beacon-port",
        "file": "place-marakkanam-sopatma-historic-beacon-port.md",
        "node_type": "place",
        "name_en": "Marakkanam (Sopatma): Ancient Coromandel Salt Port & Deep-Sea Beacon Station",
        "name_ta": "மரக்காணம் (எயிற்பட்டினம் / சோபத்மா) - தொல் உப்பளத் துறைமுகம் மற்றும் கலங்கரை மையம்",
        "era": "Sangam Early Historic Era",
        "year_start": -100,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "Historic coastal emporium and salt manufacturing hub in Villupuram district, identified as Sopatma ('Town of the Fortified Wall') in the Greco-Roman Periplus and Eyilpattinam in Tamil Sangam literature, celebrated for its fortified roadstead and towering beacon fires.",
        "summary_ta": "விழுப்புரம் கடற்கரையில் அமைந்துள்ள வரலாற்றுப் புகழ்பெற்ற துறைமுகம். பெரிப்ளஸ் குறிப்பிடும் 'சோபத்மா' மற்றும் சங்க இலக்கியம் கூறும் 'எயிற்பட்டினம்'. கடலோர உப்பளங்கள், உரோமக் கப்பல்கள் வந்து தங்கிய நங்கூரத் தளம் மற்றும் மாடக் கலங்கரை விளக்கம் விளங்கிய மையம்.",
        "content": """# Marakkanam Historic Beacon Port (மரக்காணம்)

- **Coordinates**: 12.2000° N, 79.9500° E.  
- **District**: Villupuram, Tamil Nadu.  
- **Navigational Heritage**: Primary landfall on the Coromandel coast north of the Kaveri delta for ships sailing from Sri Lanka and the Bay of Bengal.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: SANGAM CERAMIC ENGINEERING, BLACK-AND-RED WARE & PYROTECHNICS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-narrinai-kalam-chey-koyil-pottery-hymns",
        "file": "text-narrinai-kalam-chey-koyil-pottery-hymns.md",
        "node_type": "text",
        "name_en": "Narrinai & Ainkurunuru Ceramic Poetry: The Potter's Fast Wheel & Red Slip Burnishing",
        "name_ta": "நற்றிணை மற்றும் ஐங்குறுநூறு மட்பாண்டப் பாடல்கள் - சுழல் திகிரி மற்றும் செம்மண் பூச்சு நுட்பம்",
        "era": "Sangam Classical Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "Marutham",
        "summary_en": "Classical poetic descriptions in Narrinai (poem 200) and Ainkurunuru (poem 44) invoking the master potter (*Kalam-chey-kove*) turning the heavy stone flywheel (*Thigiri*), throwing thin-walled delicate drinking bowls, applying hematite red slip, and firing in straw-insulated kilns.",
        "summary_ta": "நற்றிணை மற்றும் ஐங்குறுநூற்றில் இடம்பெறும் மட்பாண்டக் கலைப் பாடல்கள். வேகமான சுழல் திகிரியை இயக்கி, நுண்ணிய களிமண்ணால் மெல்லிய பாத்திரங்களை வனைந்து, செம்மண் பூச்சுப் பூசி, வைக்கோல் மூடிய சூளையில் சுட்டெடுத்த குயவர்களின் திறனைப் போற்றும் இலக்கியச் சான்றுகள்.",
        "content": """# Sangam Ceramic Poetry (மட்பாண்ட இலக்கியம்)

**Sources**: *Narrinai* (*நற்றிணை*), *Ainkurunuru* (*ஐங்குறுநூறு*), *Kuruntokai* (*குறுந்தொகை*).  
**Subject**: Indigenous Potter's Wheel (*திகிரி*), Slip Burnishing (*மெழுகுதல்*).  

---

## 1. The Fast Wheel (*திகிரி*)
Poets describe the rhythmic rotation of the heavy flywheel balanced on a pivot stone:
*"வேட்கோச் சிறாஅர் தேர்க்கால் போல சுழலும் திகிரி..."*  
(Like the spinning chariot wheel, the potter's youth rotates the flywheel, shaping moist alluvial earth with feathered touch into perfect circular perfection!)
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-keezhadi-black-and-red-ware-graffiti-sherds",
        "file": "insc-keezhadi-black-and-red-ware-graffiti-sherds.md",
        "node_type": "inscription",
        "name_en": "Keezhadi Inscribed Black-and-Red Ware Sherds: Post-Firing Tamil-Brahmi Graffito",
        "name_ta": "கீழடி கருப்பு-சிவப்பு மண்பாண்டக் கல்வெட்டுகள் - சுடுமண் கலயங்களில் தமிழ்-பிராமி எழுத்துக் கீறல்கள்",
        "era": "Sangam Early Historic Era",
        "year_start": -600,
        "year_end": -200,
        "thinai": "Marutham",
        "summary_en": "Monumental archaeological epigraphs discovered across stratified layers at Keezhadi on the Vaigai River: hundreds of Black-and-Red Ware and fine red-slipped bowls incised post-firing with personal names in archaic Tamil-Brahmi (e.g., 'Aadhan', 'Kuviran-Aadhan', 'Disan', 'Udhiran') dating to the 6th century BCE.",
        "summary_ta": "கீழடி அகழ்வாராய்ச்சியில் கண்டெடுக்கப்பட்ட நூற்றுக் கணக்கான கருப்பு-சிவப்பு பானை ஓடுகள். பாண்டங்கள் சுடப்பட்ட பின் கூரிய உளி கொண்டு எழுதப்பட்ட 'ஆதன்', 'குவிரன்-ஆதன்', 'திசன்' போன்ற தமிழ்-பிராமி பெயர்கள், கிமு 6-ஆம் நூற்றாண்டிலேயே சாதாரண மக்களும் எழுத்தறிவு பெற்றிருந்ததை உலகுக்கு பறைசாற்றும் அறிவியல் சான்று.",
        "content": """# Keezhadi Inscribed Ceramic Sherds (கீழடி மண்பாண்டங்கள்)

---

## 1. Mass Literacy Context
The inscriptions occur on everyday utilitarian tableware (bowls, platters, water jugs), confirming that literacy was democratized across common agrarian householders rather than restricted to religious elites.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-alagarankulam-rouletted-ware-graffiti-charters",
        "file": "insc-alagarankulam-rouletted-ware-graffiti-charters.md",
        "node_type": "inscription",
        "name_en": "Alagankulam Rouletted Ware & Roman Amphorae Epigraphs: Mediterranean Ceramic Trade",
        "name_ta": "அழகன்குளம் ரூலட்டட் மண்பாண்டங்கள் மற்றும் உரோம ஆம்போரா சாசனங்கள்",
        "era": "Sangam Early Historic Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "Neithal",
        "summary_en": "Excavation records from the international port of Alagankulam near the Vaigai estuary: revealing thousands of high-luster Rouletted Ware dishes, imported Roman amphora handles bearing Mediterranean kiln stamps, stamped Russian/African red-slip, and Tamil-Brahmi graffiti.",
        "summary_ta": "வைகை முகத்துவாரத்து அழகன்குளத்தில் கண்டெடுக்கப்பட்ட சர்வதேச மட்பாண்டங்கள். பளபளப்பான ரூலட்டட் பாத்திரங்கள், உரோம ஒயின் ஆம்போரா மதுக்குடங்கள், மத்திய தரைக்கடல் முத்திரைகள் மற்றும் தமிழ் வணிகர்களின் பெயர்கள் பொறித்த பானை ஓடுகள்.",
        "content": """# Alagankulam Mediterranean Ceramics (அழகன்குளம் ஆவணங்கள்)

---

## 1. Importation of Wine & Olive Oil
Amphorae sherds yielded crystallized resin residues confirming imports of Spanish and Italian wine and garum fish sauce, swapped directly for local pearls and fine black-and-red table ceramics.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-black-and-red-ware-inverted-firing-pyrotechnics",
        "file": "concept-black-and-red-ware-inverted-firing-pyrotechnics.md",
        "node_type": "concept",
        "name_en": "Black-and-Red Ware Pyrotechnics: Inverted Kiln Firing & Reduction Carbon Smoke Trapping",
        "name_ta": "கருப்பு-சிவப்பு மண்பாண்ட உலை நுட்பம் - தலைகீழ் அடுக்கு மற்றும் கரிப்புகைக் குறைப்பு முறை",
        "era": "Iron Age to Sangam Era",
        "year_start": -1200,
        "year_end": 300,
        "thinai": "Marutham",
        "summary_en": "The sophisticated dual-atmosphere pyrotechnic firing technique of ancient South India: stacking pottery upside down (inverted) in the kiln, trapping combustible organic husks inside the vessel to create a reducing atmosphere that turns the interior jet black, while the oxygenated exterior fires bright terracotta red.",
        "summary_ta": "பண்டைத் தமிழரின் வியத்தகு இரட்டைச் சூழல் சுடுமண் நுட்பம். பானைகளை சூளையில் தலைகீழாக அடுக்கி, உள்ளே வைக்கோல் அல்லது உமியை நிரப்பி, காற்று புகாதவாறு மூடி எரித்தல். இதனால் உட்புறம் கரிப்புகை படிந்து பளபளப்பான கருப்பாகவும், வெளிப்புறம் ஆக்ஸிஜன் பட்டு செழுமையான சிவப்பாகவும் மாறும் இரட்டை வண்ண அறிவியல்.",
        "content": """# Inverted Firing Pyrotechnics (கருப்பு-சிவப்பு நுட்பம்)

---

## 1. The Chemistry of Differential Firing
- **Interior (Reducing / $Fe_3O_4$)**: Limited oxygen plus smoky carbon from burning husks reduces iron oxides to black magnetite and carbonizes the clay surface, producing a smooth, impermeable, waterproof cooking lining.
- **Exterior (Oxidizing / $Fe_2O_3$)**: Ambient airflow oxidizes ferric minerals to bright red hematite.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-high-speed-flywheel-and-paddle-beating-pottery",
        "file": "concept-high-speed-flywheel-and-paddle-beating-pottery.md",
        "node_type": "concept",
        "name_en": "High-Speed Flywheel Dynamics, Clay Silt Levigation & Anvil-Paddle Body Beating",
        "name_ta": "வேகச் சுழல் திகிரி, களிமண் வண்டல் சுத்திகரிப்பு மற்றும் தட்டுக்கல்-ஆப்பு விரிவாக்கம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -800,
        "year_end": 400,
        "thinai": "Marutham",
        "summary_en": "The mechanical forming sequence of Sangam ceramics: multi-stage levigation of fine alluvial tank silts, rapid rotational throwing on pivoting flywheels, followed by secondary thinning using a smooth stone anvil (Kallu) inside and a wooden bat (Thattuppalagai) outside.",
        "summary_ta": "சங்க கால மட்பாண்ட உருவாக்க முறை. குளத்து வண்டல் மண்ணை நீரில் கரைத்து வடிகட்டி சுத்திகரித்தல், திகிரியில் வேகமாகக் கடைந்து வடிவம் கொடுத்தல், மற்றும் சுவர்கள் மெலிதாக அமைய உள்பக்கமாக உருண்டைக் கல்லையும் (தட்டுக்கல்) வெளிப்பக்கமாக மரப் பலகையையும் வைத்துத் தட்டி விரிக்கும் கலை.",
        "content": """# Flywheel & Paddle Forming Dynamics (மட்பாண்ட உருவாக்கம்)

---

## 1. Anvil-Paddle Thinning (*தட்டி விரிவாக்குதல்*)
Throwing on the wheel formed only the upper rim and cylindrical neck:
- The bottom was closed and thinned by rhythmically paddling the moist leather-hard clay against a polished stone anvil held inside, producing feather-light vessels with exceptional tensile elasticity.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-hematite-red-ochre-slip-and-cord-burnishing",
        "file": "concept-hematite-red-ochre-slip-and-cord-burnishing.md",
        "node_type": "concept",
        "name_en": "Hematite Slip Formulation, Pebble Burnishing & Luster Finishes of Sangam Pottery",
        "name_ta": "காவி செம்மண் பூச்சு, கூழாங்கல் பட்டை தீட்டுதல் மற்றும் சங்க கால மண்பாண்டப் பளபளப்பு",
        "era": "Iron Age to Sangam Era",
        "year_start": -600,
        "year_end": 300,
        "thinai": "Marutham",
        "summary_en": "Surface enhancement chemistry of Tamil ceramics: dipping dried vessels into colloidal suspensions of red ochre/hematite slip ($Fe_2O_3$), burnishing the leather-hard surface with smooth agate pebbles or oily seed coatings, yielding mirror-like metallic lusters without vitreous lead glazes.",
        "summary_ta": "மண்பாண்டங்களின் மேற்பரப்பை பளபளப்பாக்கும் நுட்பம். இரும்புச்சத்து நிறைந்த காவிமண் கலவையை பூசி, ஆற்று கூழாங்கற்கள் அல்லது எண்ணெய் வித்துக்களைக் கொண்டு தேய்த்து மெருகூட்டுதல். இதன்மூலம் கண்ணாடி போன்ற பளபளப்பும் நீர்க்கசிவற்ற உறுதியும் மண்பாண்டங்களுக்குக் கிடைத்தது.",
        "content": """# Hematite Slip & Pebble Burnishing (செம்மண் மெருகூட்டல்)

---

## 1. Mirror-Luster Mechanics
Pebble burnishing compacted the surface clay platelets, aligning microscopic phyllosilicate sheets parallel to the surface to create specular optical reflection before firing.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-double-chamber-updraft-ceramic-kiln-engineering",
        "file": "concept-double-chamber-updraft-ceramic-kiln-engineering.md",
        "node_type": "concept",
        "name_en": "Double-Chamber Updraft Ceramic Kiln Mechanics: Perforated Flue Floors & Thermal Gradients",
        "name_ta": "இரு-அறை மேல்நோக்குச் சூளைப் பொறியியல் - துளைத்தள வெப்பக் கட்டுப்பாடு மற்றும் சுடுமண் உலை",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "The industrial pyrotechnic architecture of urban ceramic workshops excavated at Keezhadi, Uraiyur, and Tirukkampuliyur: permanent sunken fireboxes beneath perforated clay grate floors that separated burning fuel from stacked pottery, achieving uniform 900–1,000°C temperatures.",
        "summary_ta": "கீழடி, உறையூர் மற்றும் திருக்காம்புலியூரில் கண்டெடுக்கப்பட்ட பிரம்மாண்ட சுடுமண் சூளைகள். கீழ்ப்பகுதியில் விறகு எரியும் உலை அறையும், மேலே துளைகள் கொண்ட சுடுமண் தளம் வழியே வெப்பம் மட்டும் ஏறும் பாண்ட அடுக்கும் அறையும் கொண்ட மேம்பட்ட மேல்நோக்கு சூளை அமைப்பு.",
        "content": """# Double-Chamber Updraft Kiln Mechanics (மேல்நோக்குச் சூளை)

---

## 1. Thermal Separation
- **Lower Combustion Chamber (*அனல் அறை*)**: Fueled with tamarind charcoal and agricultural stalks.
- **Perforated Clay Grate (*துளைத் தளம்*)**: Circular earthenware floor pierced with 50–100 flue holes directing heat vertically without contaminating vessels with flying ash.
"""
    },
    {
        "category": "characters",
        "slug": "char-keezhadi-master-ceramic-pyrotechnologist",
        "file": "char-keezhadi-master-ceramic-pyrotechnologist.md",
        "node_type": "character",
        "name_en": "Keezhadi Master Potter: Wheel Thrower, Kiln Stoker & Reduction Specialist",
        "name_ta": "கீழடி மண்பாண்ட ஆசான் - திகிரிச் சுழற்சி மற்றும் கரிப்புகைக் குறைப்பு உலை வல்லுநர்",
        "era": "Sangam Early Historic Era",
        "year_start": -500,
        "year_end": -300,
        "thinai": "Marutham",
        "summary_en": "Master urban ceramist at Keezhadi directing large-scale wheel throwing, slip compounding, and the delicate thermal shifts required for Black-and-Red Ware inverted firing.",
        "summary_ta": "கீழடி நகரத்தில் வாழ்ந்த முதன்மை மட்பாண்ட கலைஞர். வண்டல் மண் சுத்திகரிப்பு முதல், பளபளப்பான கருப்பு-சிவப்பு கிண்ணங்களை சூளையில் சுட்டெடுத்து அரசர்களுக்கும் பொதுமக்களுக்கும் வழங்கிய கைவினைப் பெருமகன்.",
        "content": """# The Keezhadi Master Potter (கீழடிக் குயவர்)

Supervised the post-firing graffitists who incised personal ownership seals and clan names in early Tamil-Brahmi script onto finished tableware.
"""
    },
    {
        "category": "characters",
        "slug": "char-alagankulam-imported-ceramic-trader",
        "file": "char-alagankulam-imported-ceramic-trader.md",
        "node_type": "character",
        "name_en": "Alagankulam Ceramic Merchant: Importer of Roman Amphorae & Terra Sigillata",
        "name_ta": "அழகன்குளம் மண்பாண்ட வணிகர் - உரோம ஆம்போரா மதுக்குடங்கள் இறக்குமதி செய்தவர்",
        "era": "Sangam Early Historic Era",
        "year_start": -200,
        "year_end": 100,
        "thinai": "Neithal",
        "summary_en": "Cosmopolitan merchant based at Alagankulam at the Vaigai mouth who handled wholesale redistribution of imported Roman wine amphorae, African red-slip wares, and indigenous luxury Rouletted dishes.",
        "summary_ta": "அழகன்குளத் துறைமுகத்தில் செயல்பட்ட சர்வதேச வணிகர். உரோம மற்றும் எகிப்தியக் கப்பல்களில் இருந்து ஆம்போரா மதுக்குடங்களை இறக்குமதி செய்து, மதுரை பாண்டிய மன்னரின் அரண்மனைக்கு அனுப்பிய பெருவணிகர்.",
        "content": """# The Ceramic Merchant (மண்பாண்டச் செட்டி)

Fluent in Mediterranean commercial terms, brokering maritime barters where fine Indian Black-and-Red tableware was exported westward alongside spices and cotton.
"""
    },
    {
        "category": "places",
        "slug": "place-tirukkampuliyur-kaveri-ceramic-center",
        "file": "place-tirukkampuliyur-kaveri-ceramic-center.md",
        "node_type": "place",
        "name_en": "Tirukkampuliyur: Kaveri Basin Historic Ceramic Kiln Site & Stratified Pottery Center",
        "name_ta": "திருக்காம்புலியூர் - காவிரிக் கரையின் வரலாற்றுச் சிறப்புமிக்க மண்பாண்ட சூளை மையம்",
        "era": "Sangam Early Historic Era",
        "year_start": -300,
        "year_end": 400,
        "thinai": "Marutham",
        "summary_en": "Renowned early historic archaeological site in Karur / Tiruchirappalli district on the southern bank of the Kaveri River, excavated by Madras University to reveal deep stratified sequences of Black-and-Red Ware, Russet-Coated Painted Ware, intact ceramic kilns, and iron-smelting crucibles.",
        "summary_ta": "கரூர்-திருச்சி எல்லையில் காவிரிக் கரையில் அமைந்துள்ள புகழ்பெற்ற தொல்லியல் தளம். சென்னைப் பல்கலைக்கழகத்தால் அகழாய்வு செய்யப்பட்டு, கருப்பு-சிவப்பு மண்பாண்டங்கள், வரிக்கோட்டு ஓவியப் பாண்டங்கள் மற்றும் சங்க கால சுடுமண் உலைகள் முழுமையாக வெளிக்கொணரப்பட்ட முக்கிய மையம்.",
        "content": """# Tirukkampuliyur Ceramic Center (திருக்காம்புலியூர்)

- **Coordinates**: 10.9500° N, 78.3833° E.  
- **District**: Karur / Tiruchirappalli border, Tamil Nadu.  
- **Archaeological Legacy**: Yielded benchmark stratified ceramic sequences confirming the technical evolution of Tamil alluvial pottery from the Iron Age into the Early Historic era.
"""
    }
]

# ==============================================================================
# RELATIONAL EDGES (30 Total)
# ==============================================================================
EDGES = [
    # Corpus 1 Edges: Perfumery & Sandalwood Distillation
    ("text-silappadikaram-aromatic-cosmetic-canon", "documents_art_of", "char-madurai-master-perfumer-suvanta-karar", "biography", "Sangam Post-Classical", "Poems chronicle the perfumer blending sixty-four botanical fragrances.", "Silappadikaram Ur-Kaan Kadhai"),
    ("text-silappadikaram-aromatic-cosmetic-canon", "describes", "concept-agarwood-smoking-and-civet-musk-blending", "cosmetology", "Sangam Post-Classical", "Text portrays women scenting hair over smoking agarwood wicker frames.", "Adaikkala Kadhai verses"),
    ("insc-kallidaikurichi-sandalwood-guild-charters", "endows", "concept-sandalwood-grinding-and-clay-hydro-distillation", "temple_ritual", "Early Medieval", "Charters fund daily sandalwood paste grinding for divine unguent rites.", "Kallidaikurichi inscriptions"),
    ("insc-kallidaikurichi-sandalwood-guild-charters", "regulates", "concept-aromatic-guild-networks-and-forest-concessions", "commerce", "Pandya Era", "Grants transit toll exemptions to mountain sandalwood caravans.", "Pandyan state records"),
    ("insc-thiruvaiyaru-fragrance-endowment-charters", "records_grant_of", "concept-javvadu-and-attar-herbal-cosmetology", "ritual_endowment", "Imperial Chola", "Royal endowments provide gold for camphor, saffron, and Javvadu pastes.", "Thiruvaiyaru epigraphs"),
    ("concept-aromatic-guild-networks-and-forest-concessions", "sources_from", "char-western-ghats-agarwood-harvester", "harvesting", "Ancient-Medieval", "Guilds contracted indigenous forest trackers to extract resinous heartwood.", "Forestry records"),
    ("char-western-ghats-agarwood-harvester", "operates_in", "place-courtallam-aromatic-hill-groves", "geography", "Ancient", "Trackers collected wild sandalwood and agarwood in the Pothigai foothills.", "Sangam geography"),
    ("char-madurai-master-perfumer-suvanta-karar", "compounds", "concept-javvadu-and-attar-herbal-cosmetology", "cosmetic_chemistry", "Classical", "Perfumers compounded sandalwood flour, civet, and floral attars.", "Tamil lexica"),
    ("place-courtallam-aromatic-hill-groves", "famed_for", "concept-sandalwood-grinding-and-clay-hydro-distillation", "natural_resource", "Ancient", "Courtallam cascades and hills provided dense wild sandalwood groves.", "Pandyan charters"),
    ("concept-agarwood-smoking-and-civet-musk-blending", "formulated_by", "char-madurai-master-perfumer-suvanta-karar", "olfactory_arts", "Classical", "Court cosmetologists blended civet and musk fixatives into royal perfumes.", "Sangam literature"),

    # Corpus 2 Edges: Lighthouses & Coastal Beacons
    ("text-perumpanarruppadai-ilangu-sudar-lighthouse-poetry", "celebrates", "concept-deepa-stambham-masonry-lighthouse-engineering", "maritime_poetry", "Sangam Classical", "Famous verse describes tall whitewashed tower burning night oil flares.", "Perumpanarruppadai 346-351"),
    ("text-perumpanarruppadai-ilangu-sudar-lighthouse-poetry", "attests_role_of", "char-poompuhar-lighthouse-keeper-deepa-kavalar", "vocational_heritage", "Sangam Classical", "Poem documents keepers tending flares propping up the sky like pillars.", "Pattuppattu"),
    ("insc-poompuhar-maritime-beacon-foundations", "substantiates", "concept-deepa-stambham-masonry-lighthouse-engineering", "underwater_archaeology", "Early Historic", "Submerged circular brick platforms confirm Sangam masonry lighthouses.", "NIO marine excavations"),
    ("insc-poompuhar-maritime-beacon-foundations", "tendered_by", "char-poompuhar-lighthouse-keeper-deepa-kavalar", "operational_site", "Sangam Era", "Beacon keepers maintained flame elevation to achieve 20-mile horizons.", "Marine survey reports"),
    ("insc-marakkanam-eyil-pattinam-beacon-charters", "situated_at", "place-marakkanam-sopatma-historic-beacon-port", "geography", "Sangam to Chola", "Charters at Marakkanam record pilotage fees and lighthouse oil cesses.", "South Indian Inscriptions"),
    ("char-marakkanam-estuary-harbor-pilot", "operates_at", "place-marakkanam-sopatma-historic-beacon-port", "navigation", "Early Historic", "Pilots steered Roman and native vessels through shifting lagoon shoals.", "Periplus sec. 60"),
    ("concept-coastal-bonfire-beacons-and-channel-piloting", "directed_by", "char-marakkanam-estuary-harbor-pilot", "piloting", "Early Historic", "Pilots triangulated harbor mouths using dual high and low beacon bonfires.", "Maritime piloting lore"),
    ("concept-shoal-warning-buoys-and-estuary-sounding-leads", "utilized_by", "char-marakkanam-estuary-harbor-pilot", "hydrography", "Ancient", "Pilots dropped tallow lead weights to measure estuary depths and sandbars.", "Naval archaeology"),
    ("concept-maritime-pilot-corporations-and-harbor-tolls", "enforced_at", "place-marakkanam-sopatma-historic-beacon-port", "port_governance", "Early Historic", "Guild pilots collected statutory wine and salt cesses to fund beacon oil.", "Commercial charters"),
    ("concept-deepa-stambham-masonry-lighthouse-engineering", "deployed_at", "place-marakkanam-sopatma-historic-beacon-port", "maritime_engineering", "Sangam Era", "Fortified tower guided international merchantmen docking at Sopatma.", "Archaeological reports"),

    # Corpus 3 Edges: Sangam Ceramics & Pyrotechnics
    ("text-narrinai-kalam-chey-koyil-pottery-hymns", "depicts_craft_of", "char-keezhadi-master-ceramic-pyrotechnologist", "oral_poetry", "Sangam Classical", "Verses invoke the potter rotating the flywheel to mould delicate bowls.", "Narrinai poem 200"),
    ("text-narrinai-kalam-chey-koyil-pottery-hymns", "describes", "concept-high-speed-flywheel-and-paddle-beating-pottery", "ceramic_arts", "Sangam Classical", "Poetry portrays stone anvil and paddle thinning of leather-hard vessels.", "Ainkurunuru poem 44"),
    ("insc-keezhadi-black-and-red-ware-graffiti-sherds", "exemplifies", "concept-black-and-red-ware-inverted-firing-pyrotechnics", "stratigraphic_record", "6th c. BCE", "Excavated sherds showcase pristine reduction-black interiors and red rims.", "Keezhadi reports"),
    ("insc-keezhadi-black-and-red-ware-graffiti-sherds", "fabricated_by", "char-keezhadi-master-ceramic-pyrotechnologist", "craft_epigraphy", "Early Historic", "Potters oversaw post-firing incising of personal Tamil-Brahmi names.", "State Archaeology"),
    ("concept-black-and-red-ware-inverted-firing-pyrotechnics", "fired_in", "concept-double-chamber-updraft-ceramic-kiln-engineering", "pyrotechnology", "Iron Age-Sangam", "Inverted vessels fired over perforated flue grates separating fuel ash.", "Ceramic engineering"),
    ("concept-hematite-red-ochre-slip-and-cord-burnishing", "applied_to", "concept-black-and-red-ware-inverted-firing-pyrotechnics", "surface_finishing", "Iron Age", "Pebble-burnished hematite slip created high-luster metallic sheen.", "Material science"),
    ("insc-alagarankulam-rouletted-ware-graffiti-charters", "handled_by", "char-alagankulam-imported-ceramic-trader", "commerce", "Early Historic", "Merchant imported Mediterranean wine amphorae and Rouletted dishes.", "Excavation records"),
    ("insc-alagarankulam-rouletted-ware-graffiti-charters", "situated_at", "place-tirukkampuliyur-kaveri-ceramic-center", "comparative_stratigraphy", "Early Historic", "Tirukkampuliyur stratigraphy matches Alagankulam ceramic chronologies.", "Madras University"),
    ("concept-double-chamber-updraft-ceramic-kiln-engineering", "excavated_at", "place-tirukkampuliyur-kaveri-ceramic-center", "archaeology", "Early Historic", "Multi-chambered updraft kilns with perforated floors unearthed on Kaveri.", "ASI excavation reports"),
    ("char-keezhadi-master-ceramic-pyrotechnologist", "perfected", "concept-hematite-red-ochre-slip-and-cord-burnishing", "pyrotechnic_arts", "6th c. BCE", "Master ceramists burnished fine clay slips to mirror finishes without glaze.", "Keezhadi science")
]

# ==============================================================================
# MAIN HARVESTER EXECUTION
# ==============================================================================
def main():
    print("=" * 70)
    print("🚀 BATCH 10: TRIPLE CIVILIZATIONAL EXPANSION HARVESTER")
    print("   1. Ancient Perfumery, Sandalwood Distillation & Aromatics (10 dossiers)")
    print("   2. Maritime Lighthouse Architecture & Night Beacons (10 dossiers)")
    print("   3. Sangam Ceramic Engineering, Black-and-Red Ware & Kilns (10 dossiers)")
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
