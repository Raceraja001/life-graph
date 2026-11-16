#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 9):
1. Classical Astronomy, Nakshatra Calendrics & Inscriptional Solar Eclipses (10 dossiers)
2. Indo-Pacific Glassmaking, Drawn Micro-Beads & Marine Emporia (10 dossiers)
3. Iron Age Megalithic Burial Architecture & Urn Necropolises (10 dossiers)

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
    # CORPUS 1: CLASSICAL ASTRONOMY, NAKSHATRA CALENDRICS & INSCRIBED ECLIPSES
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-kanakkan-parani-astronomical-nakshatra-canon",
        "file": "text-kanakkan-parani-astronomical-nakshatra-canon.md",
        "node_type": "text",
        "name_en": "Kanakkan Parani & Tamil Astronomical Canon: Nakshatra Calendrics & Solar Transits",
        "name_ta": "கணக்கன் பரணி மற்றும் தமிழ்க் கணித வானியல் - நட்சத்திர நாள்காட்டி மற்றும் சூரிய மாதப் பிறப்பு",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 800,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "Canonical astronomical and horological manuals preserved in Tamil scribal traditions: charting the 27 Nakshatras (asterisms), 12 Raasis (solar zodiacal months), division of day into 60 Nazhikai (24-minute units), and calculating planetary conjunctions.",
        "summary_ta": "பண்டைத் தமிழகத்துக் கணக்கர்கள் மற்றும் வானியலாளர்கள் பயன்படுத்திய கணித வானியல் கையேடு. 27 நட்சத்திரங்கள், 12 இராசிகள் (மேஷம் முதல் மீனம் வரை), ஒரு நாளை 60 நாழிகைகளாகப் பிரித்தல், மற்றும் சூரியன் ஒவ்வொரு ராசியில் நுழையும் மாதப் பிறப்பு (சங்கிராந்தி) கணக்கீடுகள்.",
        "content": """# Kanakkan Parani & Tamil Astronomical Canon (கணித வானியல்)

**Source**: *Kanakkan Parani* (*கணக்கன் பரணி*), Inscriptional Jyotisha Glosses.  
**Subject**: Sidereal Zodiac (*சூரிய-சந்திர நாள்காட்டி*), Eclipse Predictions (*கிரகணக் கணிதம்*).  

---

## 1. Calendrical Mathematics
- **Nazhikai (*நாழிகை*)**: Standard time unit equal to 24 solar minutes (60 Nazhikai = 1 solar day of 1,440 minutes).
- **Vinaadi (*விநாடி*)**: 1/60th of a Nazhikai (24 seconds).
- **Nakshatra Mansions**: The Moon's orbital passage through the 27 stellar asterisms (starting with Asvini / *அஸ்வினி* and ending with Revati / *ரேவதி*).
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-tiruvidaimarudur-solar-eclipse-charters",
        "file": "insc-tiruvidaimarudur-solar-eclipse-charters.md",
        "node_type": "inscription",
        "name_en": "Tiruvidaimarudur Solar Eclipse Charters: Astronomical Dating & Sravana Remissions",
        "name_ta": "திருவிடைமருதூர் சூரிய கிரகணக் கல்வெட்டு - வானியல் நாள் கணிப்பு மற்றும் திருவோண தானங்கள்",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1020,
        "thinai": "Marutham",
        "summary_en": "Monumental Chola epigraphs on the Mahalingaswami temple walls at Tiruvidaimarudur recording exact solar eclipses (Surya-grahana) correlated with royal regnal years, tithis, and nakshatras, confirming astronomical precision to modern retrospective calculations within minutes.",
        "summary_ta": "திருவிடைமருதூர் மகாலிங்கசுவாமி கோயிலில் பொறிக்கப்பட்ட சோழர் வானியல் கல்வெட்டு. சூரிய கிரகணம் நிகழ்ந்த சரியான நாள், திதி, வாரம், நட்சத்திரம் மற்றும் அரசனின் ஆட்சியாண்டு துல்லியமாகப் பதியப்பட்டு, நவீன வானியல் கணக்கீடுகளோடு நிமிட அளவில் ஒத்துப்போகும் அறிவியல் சான்று.",
        "content": """# Tiruvidaimarudur Solar Eclipse Charters (சூரிய கிரகண சாசனம்)

---

## 1. Inscriptional Astronomical Dating
The charter reads: *"இராஜராஜ கேசரிவர்மற்கு யாண்டு... மிதுன ஞாயிற்று அமாவாசையும் பெற்ற ஆதித்ய கிரகணத்து..."*  
Documents a total or annular solar eclipse occurring on a New Moon in Gemini (Mithuna / June-July), enabling modern astrophysicists and epigraphists (such as L.D. Swamikannu Pillai) to date the inscription to an absolute Christian calendar year (e.g., 29 June 1001 CE).
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kudumiyamalai-astronomical-ephemeris-records",
        "file": "insc-kudumiyamalai-astronomical-ephemeris-records.md",
        "node_type": "inscription",
        "name_en": "Kudumiyamalai Astronomical Ephemeris Epigraphs: Planetary Conjunctions & Regnal Dating",
        "name_ta": "குடுமியாமலை வானியல் பஞ்சாங்கக் கல்வெட்டு - கோள் சேர்க்கை மற்றும் ஆட்சியாண்டு ஆவணம்",
        "era": "Early Medieval to Pandya Era",
        "year_start": 900,
        "year_end": 1250,
        "thinai": "Mullai",
        "summary_en": "Rock-cut inscriptions at Kudumiyamalai recording planetary conjunctions of Jupiter (Viyazhan) in Leo (Simha) and Saturn (Sani) in Libra, establishing synchronization between royal Pandyan epigraphs and five-limb astronomical ephemerides (Panchangam).",
        "summary_ta": "குடுமியாமலைக் குடைவரைக் கோயிலில் பொறிக்கப்பட்ட வானியல் ஆவணங்கள். குரு சிம்ம ராசியில் நின்ற காலத்திலும், சனி துலா ராசியில் சஞ்சரித்த காலத்திலும் பொறிக்கப்பட்ட அரச ஆணைகள், தமிழகத்துப் பஞ்சாங்கக் கணிப்பின் துல்லியத்தை வெளிப்படுத்தும் கல்வெட்டுச் சான்றுகள்.",
        "content": """# Kudumiyamalai Astronomical Epigraphs (குடுமியாமலை வானியல்)

---

## 1. Five Astronomical Limbs (*பஞ்சாங்கம்*)
Pandyan epigraphs rigorously cite:
1. **Tithi (*திதி*)**: Lunar phase (Prathama to Amavasya/Purnima).
2. **Vara (*வாரம்*)**: Day of the seven-day planetary week.
3. **Nakshatra (*நட்சத்திரம்*)**: Moon's stellar constellation.
4. **Yoga (*யோகம்*)**: Angular sum of Sun and Moon.
5. **Karana (*கரணம்*)**: Half-tithi subdivision.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-solar-and-lunar-eclipse-epigraphical-reckoning",
        "file": "concept-solar-and-lunar-eclipse-epigraphical-reckoning.md",
        "node_type": "concept",
        "name_en": "Solar & Lunar Eclipse Reckoning: Rahu-Ketu Shadow Mechanics & Epigraphical Verification",
        "name_ta": "சூரிய-சந்திர கிரகணக் கணக்கீடு - இராகு-கேது நிழல் கணிதம் மற்றும் கல்வெட்டு மெய்ப்பித்தல்",
        "era": "Classical to Medieval Era",
        "year_start": 300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The scientific geometric comprehension of eclipses in ancient Tamil country: recognizing eclipses as syzygy alignments where the Earth casts a shadow on the Moon (Chandra-grahana) or the Moon occludes the Sun (Surya-grahana) at orbital nodes (Rahu and Ketu).",
        "summary_ta": "பண்டைத் தமிழரின் அறிவியல் பூர்வ கிரகணக் கோட்பாடு. புராண நிழல் பாம்புகள் என்பதைக் கடந்து, பூமி மற்றும் நிலவின் நிழல்கள் நேர்கோட்டில் சந்திக்கும் விண்வெளி நிகழ்வு என்பதை உணர்ந்து, கிரகணம் நிகழும் தொடக்கம், நடுநிலை மற்றும் விடுபடு காலங்களை நாழிகைக் கணக்கில் முன்கூட்டியே கணித்த முறை.",
        "content": """# Eclipse Mechanics & Epigraphical Verification (கிரகணக் கணிதம்)

---

## 1. Scientific Eclipse Prediction
Astronomers tracked the 18-year Saros eclipse cycle (*நிழல் சுழற்சி*), identifying the intersection nodes of the lunar orbit with the ecliptic. Eclipses were viewed as sacred astrological moments when the merit of land grants (*Brahmadeya*, *Devadana*) was multiplied thousands-fold.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-nakshatra-27-asterism-calendrical-metrology",
        "file": "concept-nakshatra-27-asterism-calendrical-metrology.md",
        "node_type": "concept",
        "name_en": "27 Nakshatra Asterisms: Sidereal Zodiac, Nazhikai Division & Solar Transit (Sankranti)",
        "name_ta": "27 நட்சத்திரங்கள் - விண்மீன் மண்டலம், நாழிகைப் பகுப்பு மற்றும் தமிழ் மாதப் பிறப்பு",
        "era": "Classical to Imperial Chola Era",
        "year_start": 400,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The sidereal solar-lunar calendar system of Tamilakam: twelve solar months named after astronomical constellations (Chittirai, Vaikasi, etc.) commencing precisely when the Sun crosses into a new zodiacal sign, subdivided into 27 lunar asterisms each spanning 13° 20'.",
        "summary_ta": "சூரியனின் சஞ்சாரத்தை அடிப்படையாகக் கொண்ட தமிழ் சூரிய நாள்காட்டி. மேஷத்தில் தொடங்கும் சித்திரை முதல் மீனத்தில் முடியும் பங்குனி வரையிலான 12 மாதங்கள், 27 விண்மீன் கூட்டங்கள் மற்றும் பருவமழை மாற்றங்களோடு இணைக்கப்பட்ட விவசாயக் காலக்கணிப்பு.",
        "content": """# Sidereal Nakshatra Calendrics (தமிழ் வானியல் நாள்காட்டி)

---

## 1. The Solar-Sidereal Year
Unlike purely lunar systems that accumulate seasonal drift, the Tamil astronomical calendar was strictly solar-sidereal:
- One sidereal year equaled approximately 365.256 days.
- Solar transit (*Sankranti / மாதப் பிறப்பு*) occurred when the Sun entered a new zodiacal sign (*Raasi*), monitored at noon via gnomon shadow length.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-meykkirthi-astronomical-regnal-synchronization",
        "file": "concept-meykkirthi-astronomical-regnal-synchronization.md",
        "node_type": "concept",
        "name_en": "Meykkirthi Astronomical Synchronization: Tithi, Vara, Nakshatra & Precise Regnal Year Dating",
        "name_ta": "மெய்க்கீர்த்தி வானியல் பொருத்தம் - திதி, வாரம், நட்சத்திரம் கொண்டு சோழர் ஆட்சியாண்டு அறிதல்",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The rigorous forensic epigraphical method developed by Tamil royal scribes: prefacing every state charter with the sovereign's poetic eulogy (Meykkirthi) followed by an unalterable astronomical date code (Year + Month + Paksha + Tithi + Day of week + Nakshatra).",
        "summary_ta": "சோழர் கல்வெட்டுகளின் தொடக்கத்தில் மன்னனின் போர் வெற்றிகளைப் பாடும் மெய்க்கீர்த்தியைத் தொடர்ந்து, எந்தக் காலத்திலும் மாற்ற முடியாத வானியல் அடையாளங்களோடு (ஆண்டு, மாதம், பக்கம், திதி, வாரம், நட்சத்திரம்) தேதியை நிரந்தரமாகப் பதிவுசெய்த வரலாற்று முறை.",
        "content": """# Meykkirthi Astronomical Synchronization (வானியல் சாசனம்)

---

## 1. Absolute Date Redundancy
Because calendar day counts could be forged, imperial decrees included multi-variable astronomical redundancies:
- Example: *"யாண்டு 14-ஆவது மகர நாயிற்று பூர்வபக்ஷத்து பஞ்சமியும் புதன்கிழமையும் பெற்ற உத்திராடத்து நாள்..."*
- The combination of a 14th regnal year, the solar month of Makara (Thai), waxing 5th lunar day, Wednesday, and Uttarashadha asterism creates a unique mathematical fingerprint occurring only once every several centuries.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-sanku-gnomon-and-neer-nazhikai-water-clocks",
        "file": "concept-sanku-gnomon-and-neer-nazhikai-water-clocks.md",
        "node_type": "concept",
        "name_en": "Sanku Gnomon & Neer-Nazhikai Clepsydras: Hydro-Mechanical Day-Night Time Measurement",
        "name_ta": "சங்குக் குச்சி நிழல் மற்றும் நீர் நாழிகைக் கிண்ணம் - இரவு-பகல் நேரக் கணிப்புப் பொறிகள்",
        "era": "Classical to Medieval Era",
        "year_start": 200,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The physical instrumentation of ancient Tamil timekeeping: the Sanku vertical shadow-casting gnomon rod calibrated for daylight solar hours, paired with the Neer-Nazhikai (inflow or outflow copper bowl clepsydra) for measuring nocturnal and rainy hours.",
        "summary_ta": "பண்டைத் தமிழகத்தில் நேரத்தைக் கணக்கிடப் பயன்படுத்தப்பட்ட கருவிகள். பகலில் சூரிய நிழலின் நீளத்தைக் கொண்டு நாழிகையை அறியும் 'சங்கு' மற்றும் இரவிலும் மேகமூட்டமான நாட்களிலும் துளையிடப்பட்ட செப்புக் கிண்ணம் நீரில் மூழ்கும் வேகத்தைக் கொண்டு நேரம் அறியும் 'நீர் நாழிகை' (Clepsydra).",
        "content": """# Sanku & Neer-Nazhikai Clepsydras (நாழிகைக் கிண்ணம்)

---

## 1. The Outflow/Inflow Copper Bowl (*நாழிகைக் கிண்ணம்*)
- A hemispherical copper bowl of calibrated weight and volume had a micro-hole drilled in its base.
- Floated on a larger vessel of clean water, water trickled in until the bowl sank exactly after 1 Nazhikai (24 minutes).
- The temple attendant or royal timekeeper struck a bronze gong (*Mani*) to announce every Nazhikai to the palace and city.
"""
    },
    {
        "category": "characters",
        "slug": "char-kanakkathikari-astronomical-epigrapher",
        "file": "char-kanakkathikari-astronomical-epigrapher.md",
        "node_type": "character",
        "name_en": "Kanakkathikari: Imperial Court Astronomer, Ephemeris Scribe & Calendar Reformer",
        "name_ta": "கணக்கதிகாரி - சோழப் பேரரசின் தலைமை வானியலாளர் மற்றும் பஞ்சாங்க கணித வல்லுநர்",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1040,
        "thinai": "Marutham",
        "summary_en": "High-ranking royal scientist and math master attached to the Chola secretariat, responsible for calculating royal horoscopes, predicting eclipse dates, verifying temple orientation gnomons, and certifying epigraphical date formulas.",
        "summary_ta": "சோழப் பேரரண்மனையில் பணியாற்றிய தலைமை கணித-வானியல் அறிஞர். அரசனின் மெய்க்கீர்த்திகளுக்கான விண்மீன் தேதிகளை உறுதிசெய்தல், கிரகணங்கள் நிகழும் துல்லிய நேரத்தை முன்கூட்டியே அறிவித்தல் மற்றும் பஞ்சாங்கங்களை முறைப்படுத்திய ஆசான்.",
        "content": """# The Imperial Astronomer (கணக்கதிகாரி)

Master of spherical geometry and fractional calculations, advising the king on auspicious hours (*Muhurtha*) for overseas armada launches and temple consecrations.
"""
    },
    {
        "category": "characters",
        "slug": "char-tiruvidaimarudur-eclipse-assayer",
        "file": "char-tiruvidaimarudur-eclipse-assayer.md",
        "node_type": "character",
        "name_en": "Tiruvidaimarudur Eclipse Assayer: Solar Observation Priest & Gold Auditor",
        "name_ta": "திருவிடைமருதூர் கிரகண நடுவர் - சூரிய கிரகண அவதானிப்பாளர் மற்றும் பொன் தணிக்கையாளர்",
        "era": "Imperial Chola Era",
        "year_start": 995,
        "year_end": 1030,
        "thinai": "Marutham",
        "summary_en": "Temple astronomer and bullion auditor at Tiruvidaimarudur who visually monitored solar eclipse progression through pinhole camera chambers and oversaw massive gold and paddy endowments made during the eclipse syzygy.",
        "summary_ta": "திருவிடைமருதூர் மகாலிங்கசுவாமி கோயிலில் சூரிய கிரகணத்தை உற்றுநோக்கி, கிரகண காலத்தில் மன்னனும் பெருமக்களும் வழங்கிய பொன் தானங்களை எடைபார்த்து ஆவணப்படுத்திய மூத்த அறிஞர்.",
        "content": """# The Eclipse Assayer (கிரகண நடுவர்)

Utilized reflective oil vats to safely observe solar eclipse crescents without retinal damage, recording the exact Nazhikai of peak totality.
"""
    },
    {
        "category": "places",
        "slug": "place-tiruvidaimarudur-astronomical-epigraph-center",
        "file": "place-tiruvidaimarudur-astronomical-epigraph-center.md",
        "node_type": "place",
        "name_en": "Tiruvidaimarudur: Historic Kaveri Sanctuary & Solar Eclipse Observatory Center",
        "name_ta": "திருவிடைமருதூர் - காவிரிக் கரையின் வரலாற்றுச் சிறப்புமிக்க சூரிய கிரகண ஆவண மையம்",
        "era": "Early Medieval to Chola Era",
        "year_start": 850,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "Ancient temple township on the southern bank of the Kaveri near Kumbakonam, renowned in epigraphical science for preserving over 100 royal Chola inscriptions detailing dated solar eclipses, theatre halls (Nataka-salai), and high-precision astronomical grants.",
        "summary_ta": "கும்பகோணம் அருகே காவிரிக் கரையில் அமைந்துள்ள புகழ்பெற்ற பாடல் பெற்ற தளம். சோழர் காலத்து சூரிய கிரகணங்கள், தாள-நாடக அரங்குகள் மற்றும் வானியல் அடிப்படையில் கணக்கிடப்பட்ட தானங்கள் பொறிக்கப்பட்ட வரலாற்றுச் சிறப்புமிக்க மையம்.",
        "content": """# Tiruvidaimarudur Astronomical Center (திருவிடைமருதூர்)

- **Coordinates**: 10.9983° N, 79.4678° E.  
- **River**: Kaveri River alluvial basin (*காவிரித் தென்கரை*).  
- **Epigraphical Benchmark**: The definitive sanctuary for verifying ancient Indian solar eclipses against astronomical software retrodictions.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: INDO-PACIFIC GLASSMAKING, DRAWN MICRO-BEADS & MARINE EMPORIA
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-periplus-maris-erythraei-glass-bead-cargoes",
        "file": "text-periplus-maris-erythraei-glass-bead-cargoes.md",
        "node_type": "text",
        "name_en": "Periplus & Tamil Lexica on Ancient Glass: Lithina Hualos & Kol-Mani Bead Cargoes",
        "name_ta": "பெரிப்ளஸ் மற்றும் சங்க இலக்கியக் கண்ணாடி மணிகள் - லித்தினா ஹுவாலோஸ் மற்றும் கோல்-மணி",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "Classical Greco-Roman maritime text *Periplus Maris Erythraei* (sections 54 and 60) and Sangam poetic lexica (Purananuru, Akananuru) describing the mass export of glass beads, raw cullet, and drawn micro-beads (*Lithina Hualos* / *Kol-Mani*) from Poduke (Arikamedu) to Egypt, Rome, and the Red Sea.",
        "summary_ta": "கி.பி. முதல் நூற்றாண்டின் கிரேக்கக் கடல் வழிகாட்டி நூலான பெரிப்ளஸ் மற்றும் சங்க இலக்கியப் பாடல்களில் இடம்பெறும் கண்ணாடி மணி வர்த்தகம். 'பொதுகே' (அரிக்கமேடு) துறைமுகத்திலிருந்து உரோமப் பேரரசு மற்றும் செங்கடல் துறைமுகங்களுக்கு ஏற்றுமதியான பலவண்ணக் கண்ணாடி மணிகள் மற்றும் குழாய் மணிகளின் வரலாற்றுப் பதிவுகள்.",
        "content": """# Periplus & Ancient Glass Bead Cargoes (கண்ணாடி மணி வணிகம்)

**Sources**: *Periplus Maris Erythraei* (*பெரிப்ளஸ்*), *Akananuru* (*அகநானூறு*).  
**Subject**: Drawn Glass Micro-Bead Technology (*இழுப்புக் கண்ணாடி மணிகள்*).  

---

## 1. Classical References
The *Periplus* notes that ships sailing from Myos Hormos and Berenike to Muziris and Poduke traded wine, copper, and tin in exchange for silk, pepper, and massive consignments of fine translucent glass beads (*Lithina Hualos*).
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-arikamedu-pottery-and-glass-guild-graffiti",
        "file": "insc-arikamedu-pottery-and-glass-guild-graffiti.md",
        "node_type": "inscription",
        "name_en": "Arikamedu Tamil-Brahmi Pottery & Glass Guild Graffiti: Poduke Beadmakers' Marks",
        "name_ta": "அரிக்கமேடு தமிழ்-பிராமி மண்பாண்ட மற்றும் கண்ணாடி மணி வணிகர் கீறல் சாசனங்கள்",
        "era": "Sangam Early Historic Era",
        "year_start": -200,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "Early Historic potsherds and ceramic crucibles discovered during Wheeler and Casal excavations at Arikamedu inscribed with personal and guild names in Tamil-Brahmi (e.g., 'Aadhitan', 'Kuvadhavan', 'Mani-k-kal'), documenting indigenous beadmakers operating at international port Poduke.",
        "summary_ta": "அரிக்கமேடு தொல்லியல் அகழ்வாராய்ச்சியில் கண்டெடுக்கப்பட்ட தமிழ்-பிராமி எழுத்துப் பொறித்த மண்பாண்ட ஓடுகள். 'மணி-க்-கல்', 'குவதவன்', 'ஆதித்தன்' போன்ற கைவினைஞர்களின் பெயர்கள் பொறிக்கப்பட்டு, உலகின் மிகப்பெரிய கண்ணாடி மணி தொழிற்கூடமாக அரிக்கமேடு விளங்கியதை உறுதிசெய்யும் சான்றுகள்.",
        "content": """# Arikamedu Guild Graffiti (அரிக்கமேட்டுக் கீறல்கள்)

---

## 1. Industrial Excavation Context
Excavations revealed millions of monochrome drawn micro-beads, glass furnace wasters, raw glass chunks, and clay tuyeres (blowpipes) littered alongside Mediterranean amphorae and terra sigillata tablewares.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kudikadu-glass-bead-furnace-charters",
        "file": "insc-kudikadu-glass-bead-furnace-charters.md",
        "node_type": "inscription",
        "name_en": "Kudikadu Glass Furnace Inscriptions: Medieval Beadmaking Guild Charters",
        "name_ta": "குடிக்காடு கண்ணாடி உலைக் கல்வெட்டுகள் - இடைக்கால மணி தயாரிப்பாளர் வணிகக் குழு ஆவணம்",
        "era": "Early Medieval to Chola Era",
        "year_start": 900,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "Epigraphical and archaeological records at Kudikadu near Cuddalore documenting specialized artisan corporations (*Kallar-perumakkal*) operating high-temperature coastal glass smelting furnaces, endowed with tax remissions for fuel gathering.",
        "summary_ta": "கடலூர் அருகே குடிக்காட்டில் கண்டறியப்பட்ட கண்ணாடி உலைத் தொழிலாளர் கல்வெட்டுகள். பலவண்ணக் கண்ணாடி உருக்கு உலைகளை இயக்கிய தொழிற்குழுக்கள், உலைக்கான விறகு எடுக்கும் உரிமை மற்றும் ஏற்றுமதி வரிகள் பற்றிய ஆவணங்கள்.",
        "content": """# Kudikadu Glass Furnace Charters (குடிக்காட்டுக் கல்வெட்டுகள்)

---

## 1. Coastal Industrial Continuity
Demonstrates that after the decline of Arikamedu in the 4th century CE, the center of Indian Ocean drawn-glass pyrotechnics shifted southwards to Kudikadu and Nagapattinam, sustaining high-volume trade until the 13th century.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-indo-pacific-drawn-glass-bead-pyrotechnics",
        "file": "concept-indo-pacific-drawn-glass-bead-pyrotechnics.md",
        "node_type": "concept",
        "name_en": "Indo-Pacific Drawn Glass Pyrotechnics: Lada Drawing, Tubes & Silica-Plant Ash Melting",
        "name_ta": "இந்தோ-பசிபிக் இழுப்புக் கண்ணாடி மணி நுட்பம் - குழாய் இழுத்தல் மற்றும் தாவரச் சாம்பல் உருக்கு",
        "era": "Classical to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Neithal",
        "summary_en": "The revolutionary indigenous glass-drawing technique pioneered in ancient Tamilakam: melting silica sand with plant ash flux in circular clay furnaces, gathering molten glass on a hollow iron pipe (Lada), and drawing hollow glass tubes over 20 meters long that were cut into millions of micro-beads.",
        "summary_ta": "பண்டைத் தமிழகத்தில் உருவான உலகின் தனித்துவமான கண்ணாடி மணி தொழில்நுட்பம். மணலையும் தாவரச் சாம்பலையும் உருக்கி, இரும்புக் குழாயில் (Lada) ஊதி, 20 மீட்டர் நீளத்திற்கு மெல்லிய கண்ணாடி நுண்குழாய்களாக இழுத்து, பின்னர் சிறு மணிகளாக நறுக்கி பட்டை தீட்டும் அதிசயத் தொழில்முறை.",
        "content": """# Indo-Pacific Drawn Glass Pyrotechnics (இழுப்புக் கண்ணாடி முறை)

---

## 1. The Lada Drawing Process
1. **Primary Smelting**: White river quartz sand melted with alkaline plant ash (*Karaka-charam*) or mineral soda at 1,100°C.
2. **Tube Drawing**: Two master blowers manipulated an iron mandrel; one stood stationary holding the molten glass gather while the second artisan walked rapidly backwards pulling a continuous hollow micro-tube.
3. **Cutting & Slicing**: Tubes were sliced with fine steel blades into uniform cylinders (1–4 mm diameter).
4. **Ash Tumbling**: Cylinders tumbled in hot clay pans with carbon ash to round the sharp edges without collapsing the central thread aperture.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-arikamedu-red-mutisalah-bead-trade-network",
        "file": "concept-arikamedu-red-mutisalah-bead-trade-network.md",
        "node_type": "concept",
        "name_en": "Red Mutisalah Micro-Beads: Trade Currency from Arikamedu to Japan and Africa",
        "name_ta": "சிவப்பு முத்திசாலா மணிகள் - அரிக்கமேடு முதல் ஆப்பிரிக்கா மற்றும் ஜப்பான் வரையிலான நாணயப் பாதை",
        "era": "Classical to Early Medieval Era",
        "year_start": -100,
        "year_end": 1000,
        "thinai": "Neithal",
        "summary_en": "The ubiquitous opaque brownish-red (Indian Red) drawn glass micro-bead (*Mutisalah*) manufactured at Arikamedu: prized as a universal trade currency, found in massive archaeological contexts from Sub-Saharan Great Zimbabwe and Zanzibar to Han/Yayoi tombs in Japan and Oc Eo in Vietnam.",
        "summary_ta": "அரிக்கமேட்டில் பெருமளவில் உற்பத்தி செய்யப்பட்ட அடர் சிவப்பு நிற நுண் கண்ணாடி மணிகள் (முத்திசாலா). ஆசிய மற்றும் ஆப்பிரிக்கப் பெருங்கடல் வணிகத்தில் தங்கத்திற்கு நிகரான நாணயமாகப் பயன்படுத்தப்பட்டு, தென்னாப்பிரிக்க ஜிம்பாப்வே, வியட்நாமின் ஓக்-ஈயோ மற்றும் ஜப்பானிய அரச கல்லறைகள் வரை கண்டெடுக்கப்பட்ட சான்றுகள்.",
        "content": """# Red Mutisalah Bead Phenomenon (முத்திசாலா மணிகள்)

---

## 1. The Universal Currency
- Derived from the Malay-Tamil trade phrase meaning "false pearls" or "gem-beads".
- Copper-rubbed (*Copper-ruby glass*) recipe using cuprous oxide ($Cu_2O$) nanoparticles that produced the vivid, non-fading terracotta red tone highly valued across indigenous cultures for ritual talismans and bride-wealth.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-mineral-soda-alumina-glass-chemical-recipes",
        "file": "concept-mineral-soda-alumina-glass-chemical-recipes.md",
        "node_type": "concept",
        "name_en": "Mineral Soda-Alumina (m-Na-Al) Glass: Ancient Tamil Chemical Compositions & Colorants",
        "name_ta": "கனிம சோடா-அலுமினா கண்ணாடி - தமிழரின் வேதியியல் சேர்க்கை மற்றும் இயற்கை நிறமிகள்",
        "era": "Iron Age to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "The scientifically distinctive geochemical fingerprint of ancient South Indian glass: characterized by high alumina ($Al_2O_3 > 3\%$) and high mineral soda ($Na_2O > 15\%$) with low potash and magnesia, colored with cobalt blue, copper green, iron amber, and stannous white.",
        "summary_ta": "தென்னிந்தியக் கண்ணாடியின் தனித்துவமான வேதியியல் கலவை (m-Na-Al Glass). அதிக அலுமினா மற்றும் கனிம சோடா கொண்ட இயற்கை மணல் சேர்க்கை. கோபால்ட் நீலம், செம்புப் பச்சை, இரும்பு அம்பர் மற்றும் ஈய வெள்ளைக் காரங்களை உருக்கி உருவாக்கப்பட்ட பலவண்ணக் கண்ணாடி வகைகள்.",
        "content": """# Chemical Recipes of Tamil Glass (கண்ணாடி வேதியியல்)

---

## 1. Geochemical Signature
Scientific electron microprobe (EMPA) and LA-ICP-MS analyses confirm that glass recovered from Arikamedu, Kudikadu, and Kodumanal forms a single coherent geochemical family:
- Silica ($SiO_2$): 60–68%.
- Alumina ($Al_2O_3$): 3.5–8.0% (derived from local feldspar-bearing sands).
- Soda ($Na_2O$): 14–18% (sourced from efflorescent reh/usar soils).
- Colorants: Cobalt oxide for lapis blue, manganese dioxide for amethyst purple.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-grooved-stone-bead-polishing-and-stringing",
        "file": "concept-grooved-stone-bead-polishing-and-stringing.md",
        "node_type": "concept",
        "name_en": "Grooved Stone Bead Polishing: Ash Tumbling, Perforation Drills & Stringing Technology",
        "name_ta": "வரிப்பள்ளக் கல் பட்டை தீட்டுதல் - சாம்பல் உருளை, துளையிடுதல் மற்றும் கோக்கும் நுட்பம்",
        "era": "Sangam Early Historic Era",
        "year_start": -200,
        "year_end": 400,
        "thinai": "Neithal",
        "summary_en": "The mass post-processing techniques of the beadmaking quarter: utilizing multi-grooved granite polishing slabs, wooden rotary bow-drills tipped with diamond or hard quartz splinters, and stringing micro-beads on fine vegetable and silk threads for overseas bale export.",
        "summary_ta": "கண்ணாடி மற்றும் கல் மணிகளைப் பளபளப்பாக்கும் பட்டறை நுட்பங்கள். நீண்ட பள்ளங்கள் கொண்ட கருங்கல் பலகைகளில் வைத்து மணிகளைத் தேய்த்தல், வைரம் மற்றும் குவார்ட்ஸ் முனை கொண்ட வில்-துளைக்கருவிகள் மூலம் துளையிடுதல், மற்றும் பட்டு-பருத்தி நூல்களில் கோத்து பெருங்கட்டுகளாகக் கப்பலில் ஏற்றுமதி செய்யும் முறை.",
        "content": """# Bead Finishing & Grooved Polishing (மணி பட்டை தீட்டுதல்)

---

## 1. The Multi-Grooved Granite Slab
Archaeologists excavated heavy flat granite slabs cut with 10–20 parallel semi-circular grooves:
- Glass bead cylinders were rolled back and forth inside the grooves using fine corundum abrasives and wet slurry, producing smooth, uniform beads with astonishing speed.
"""
    },
    {
        "category": "characters",
        "slug": "char-poduke-master-glass-furnace-blower",
        "file": "char-poduke-master-glass-furnace-blower.md",
        "node_type": "character",
        "name_en": "Poduke Master Glass Furnace Blower: Tube Drawer & Color Formulator",
        "name_ta": "பொதுகே கண்ணாடி உலை ஆசான் - குழாய் இழுப்பாளர் மற்றும் நிறக் கலவை வல்லுநர்",
        "era": "Sangam Early Historic Era",
        "year_start": -50,
        "year_end": 100,
        "thinai": "Neithal",
        "summary_en": "Master pyrotechnologist at Arikamedu who formulated furnace charges of quartz sand, alkali flux, and metallic oxides, directing the critical 20-meter glass tube drawing procedure.",
        "summary_ta": "அரிக்கமேட்டுத் துறைமுகத்தில் செயல்பட்ட தலைமை கண்ணாடி மணி கைவினைஞர். ஆயிரக்கணக்கான டிகிரியில் கண்ணாடியை உருக்கி, சரியான விநாடியில் மெல்லிய குழாய்களை இழுத்து உலகளாவிய மணிகளை உருவாக்கிய உலை ஆசான்.",
        "content": """# The Master Glassmaker (உலை ஆசான்)

Managed thermal gradients inside beehive clay furnaces fueled by coastal mangrove charcoal, testing glass viscosity with iron rods.
"""
    },
    {
        "category": "characters",
        "slug": "char-mutisalah-maritime-bead-merchant",
        "file": "char-mutisalah-maritime-bead-merchant.md",
        "node_type": "character",
        "name_en": "Mutisalah Maritime Bead Merchant: Exporter to Southeast Asia & East Africa",
        "name_ta": "முத்திசாலா பெருங்கடல் மணி வணிகர் - ஆசிய-ஆப்பிரிக்க நாடுகளுக்கு மணிகளை ஏற்றுமதி செய்தவர்",
        "era": "Early Historic to Medieval Era",
        "year_start": 100,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "Wealthy Tamil ocean trader who purchased millions of bundled drawn glass beads directly from port furnaces, loading them onto maritime dhows and junks bound for the Red Sea, the Swahili coast, and the Kra Isthmus.",
        "summary_ta": "அரிக்கமேட்டுக் கிடங்குகளில் இருந்து லட்சக்கணக்கான மணிக் கட்டுகளை வாங்கி, உரோம வணிகர்களிடமும் மலாயா-சீன வர்த்தகர்களிடமும் விற்று தங்கத்தையும் குதிரைகளையும் ஈட்டிய பெருவணிகர்.",
        "content": """# The Bead Merchant (மணிச் செட்டி)

Operated wholesale exchanges at Arikamedu and Kaveripattinam, contracting village workshops across the Coromandel coast.
"""
    },
    {
        "category": "places",
        "slug": "place-kudikadu-coastal-glass-bead-furnaces",
        "file": "place-kudikadu-coastal-glass-bead-furnaces.md",
        "node_type": "place",
        "name_en": "Kudikadu: Historic Cuddalore Glass Furnaces & Indo-Pacific Bead Manufacturing Center",
        "name_ta": "குடிக்காடு - கடலூர்க் கடற்கரையின் வரலாற்றுச் சிறப்புமிக்க கண்ணாடி உலை மற்றும் மணி தயாரிப்பு மையம்",
        "era": "Sangam to Early Medieval",
        "year_start": 300,
        "year_end": 1250,
        "thinai": "Neithal",
        "summary_en": "Major coastal archaeological glassmaking site in Cuddalore district on the Coromandel coast, celebrated for intact multi-chambered glass melting kilns, immense mounds of raw glass slag, and millions of finished drawn Indo-Pacific micro-beads.",
        "summary_ta": "கடலூர் கடற்கரையில் அமைந்துள்ள வரலாற்று முக்கியத்துவம் வாய்ந்த கண்ணாடித் தயாரிப்பு தளம். அரிக்கமேட்டிற்கு அடுத்தபடியாக பல நூற்றாண்டுகள் தொடர்ந்து செயல்பட்ட கண்ணாடி உலைகள், கசடுகள் மற்றும் உலகெங்கும் ஏற்றுமதியான பலவண்ண மணிகளின் மூல மையம்.",
        "content": """# Kudikadu Glass Bead Center (குடிக்காடு)

- **Coordinates**: 11.7167° N, 79.7667° E.  
- **District**: Cuddalore, Tamil Nadu.  
- **Archaeological Legacy**: Represents the vital post-Arikamedu industrial phase of Tamil maritime glass bead pyrotechnics.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: IRON AGE MEGALITHIC BURIAL ARCHITECTURE & URN NECROPOLISES
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-purananuru-mudumakkal-thaazhi-funerary-poetry",
        "file": "text-purananuru-mudumakkal-thaazhi-funerary-poetry.md",
        "node_type": "text",
        "name_en": "Purananuru Mudumakkal Thaazhi: Sangam Funerary Poetry & Megalithic Urn Philosophy",
        "name_ta": "புறநானூறு முதுமக்கள் தாழி - பெருங்கற்கால ஈமப் பாக்களும் புதைப்புத் தத்துவமும்",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "Marutham",
        "summary_en": "Classical verses in Purananuru (poems 228, 256, 364) by poets addressing the potter (*Kalam-chey-kove*) who shapes the giant burial urn (*Thaazhi*), entreating him to mould an urn large enough to enclose the departed king and his loyal retinue along with the vast earth.",
        "summary_ta": "புறநானூற்றில் இடம்பெறும் புகழ்பெற்ற முதுமக்கள் தாழிப் பாடல்கள். 'கலம்செய் கோவே! கலம்செய் கோவே!... அகலிதாக வனைமோ பெருந்தகையோற்கே' எனப் பெருஞ்சோழன் கிள்ளிவளவனின் மரணத்தின் போது குயவனை நோக்கிப் புலவர் பாடிய சங்க காலத்து ஈமப் பண்பாட்டு ஆவணம்.",
        "content": """# Purananuru Mudumakkal Thaazhi (முதுமக்கள் தாழி)

**Source**: *Purananuru* (*புறநானூறு*), Songs 228, 256, 364.  
**Subject**: Megalithic Urn Burial Custom (*ஈமத் தாழி*), Mortuary Philosophy.  

---

## 1. The Poetic Appeal to the Potter (*கலம்செய் கோவே*)
Poet Aiyur Mudavanar mourns:
*"மண்ணுடை உருவின் மண்புகா உருவோன்... கலம்செய் கோவே! அகலிதாக வனைமோ..."*  
(O Potter who moulds clay! The great monarch who protected the earth has fallen; mould an urn wide enough to hold both his boundless glory and the world he ruled!)
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-adichanallur-tamil-brahmi-urn-excavation-records",
        "file": "insc-adichanallur-tamil-brahmi-urn-excavation-records.md",
        "node_type": "inscription",
        "name_en": "Adichanallur Urn Inscriptions: Early Tamil-Brahmi Sherds & Mother Goddess Terracottas",
        "name_ta": "ஆதிச்சநல்லூர் தாழிக் கல்வெட்டுகள் - தொல் தமிழ்-பிராமி கீறல்கள் மற்றும் கொற்றவைத் தாய் தெய்வச் சிற்பங்கள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -1000,
        "year_end": -300,
        "thinai": "Marutham",
        "summary_en": "Epigraphical and archaeological records from Alexander Rea and modern ASI excavations at Adichanallur: unearthing urn rims incised with archaic proto-Tamil-Brahmi characters, floral motifs, and terracotta mother goddess figurines dated from 1000 BCE to 500 BCE.",
        "summary_ta": "ஆதிச்சநல்லூர் அகழ்வாராய்ச்சியில் கண்டெடுக்கப்பட்ட பெருங்கற்காலத் தாழிகளின் விளிம்புகளில் உள்ள தொன்மையான தமிழ்-பிராமி எழுத்துக் கீறல்கள். தாய் தெய்வ உருவங்கள், நெல் மணிகள், மற்றும் கிமு 1000 முதல் கிமு 500 வரையிலான காலக்கணிப்பு பெற்ற அறிவியல் சான்றுகள்.",
        "content": """# Adichanallur Urn Epigraphy (ஆதிச்சநல்லூர் சாசனங்கள்)

---

## 1. Proto-Writing & Decorative Motifs
Excavated urn lids feature raised appliqué clay bands depicting deer, stags, standing women, and incised script characters that represent the earliest developmental phase of the Tamil-Brahmi script in the Porunai river valley.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kodumanal-megalithic-cist-tomb-inscriptions",
        "file": "insc-kodumanal-megalithic-cist-tomb-inscriptions.md",
        "node_type": "inscription",
        "name_en": "Kodumanal Megalithic Cist Tomb Epigraphs: Etched Carnelian & Chieftain Grave Goods",
        "name_ta": "கொடுமணல் பெருங்கற்காலக் கல்லறை சாசனங்கள் - பொறித்த சூதுபவளம் மற்றும் வீரர் கல்லறைப் பொருட்கள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 100,
        "thinai": "Mullai",
        "summary_en": "Epigraphs and grave offerings recovered from the transepted cist tombs of Kodumanal on the Noyyal River: over 500 potsherds bearing personal names in Tamil-Brahmi, accompanied by etched carnelian beads, crucible Wootz steel swords, and jasper ornaments.",
        "summary_ta": "கொடுமணல் கல்வட்டக் கல்லறைகளில் கண்டெடுக்கப்பட்ட 500-க்கும் மேற்பட்ட தமிழ்-பிராமி பொறித்த பானை ஓடுகள். இறந்த தலைவர்களின் பெயர்கள், சுடுமண் கலயங்கள், உட்ஸ் எஃகு வாள்கள் மற்றும் பொறிக்கப்பட்ட சூதுபவள மணிகளின் வரலாற்றுச் சான்றுகள்.",
        "content": """# Kodumanal Cist Inscriptions (கொடுமணல் கல்லறைகள்)

---

## 1. Literacy in Funerary Context
Demonstrates widespread functional literacy among artisans and chieftains during the Iron Age: personal names incised post-firing into funerary Black-and-Red ware vessels placed inside megalithic stone chambers.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-mudumakkal-thaazhi-pyriform-urn-engineering",
        "file": "concept-mudumakkal-thaazhi-pyriform-urn-engineering.md",
        "node_type": "concept",
        "name_en": "Mudumakkal Thaazhi: Giant Pyriform Terracotta Burial Urn Ceramic Engineering",
        "name_ta": "முதுமக்கள் தாழி - பிரம்மாண்ட பேரிக்காய் வடிவ சுடுமண் ஈமத் தாழி தயாரிப்புப் பொறியியல்",
        "era": "Iron Age to Sangam Era",
        "year_start": -1200,
        "year_end": 300,
        "thinai": "Marutham",
        "summary_en": "The ceramic engineering of colossal pyriform burial urns (up to 2 meters tall and 1.5 meters wide): coiled and paddle-beaten with coarse sandy clay, fired in open bonfires or updraft pits to withstand centuries of subterranean hydrostatic earth pressure without collapsing.",
        "summary_ta": "இரண்டு மீட்டர் வரை உயரமுள்ள பிரம்மாண்ட பேரிக்காய் வடிவ ஈமத் தாழிகளை உருவாக்கிய திராவிட மட்பாண்டப் பொறியியல். தடித்த மணல் கலந்த களிமண்ணால் சுருள் முறையில் உருவாக்கப்பட்டு, தட்டுகளால் தட்டி சமன்செய்யப்பட்டு, மண்ணின் அழுத்தத்தைத் தாங்கும் வகையில் சுடப்பட்ட தொழில்நுட்பம்.",
        "content": """# Pyriform Urn Ceramic Engineering (தாழி பொறியியல்)

---

## 1. Structural Form & Hydrostatic Resistance
- The tapering pear-shaped base concentrated gravitational stability deep within the excavated gravel pit.
- Thick cordoned rims and ribbed body bands (*வரம்புகள்*) reinforced the circumference against lateral soil shear.
- Fitted with domical ceramic lids, inverted carinated bowls, and secondary skeletal deposits.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-megalithic-cist-and-dolmen-stone-circle-architecture",
        "file": "concept-megalithic-cist-and-dolmen-stone-circle-architecture.md",
        "node_type": "concept",
        "name_en": "Megalithic Cists & Dolmens: Transepted Chambers, Port-Hole Slabs & Cairns",
        "name_ta": "பெருங்கற்காலக் கல்பதுக்கை மற்றும் டால்மென் - அறைக் கல்லறைகள், இடுதுளை மற்றும் கல்வட்டம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -1000,
        "year_end": 300,
        "thinai": "Kurinji",
        "summary_en": "The monumental funerary stone architecture of ancient Tamilakam: erecting dolmenoid cists composed of orthostatic granite slabs, transepted chambers, circular port-holes (Idu-thulai) oriented eastward, and encircled by massive boulder stone circles (Kal-vattam).",
        "summary_ta": "இறந்தோரின் நினைவாக செங்குத்தான பாறைகளைக் கொண்டு எழுப்பப்பட்ட பிரம்மாண்ட கல் அமைப்புகள். கிழக்கு நோக்கி திறக்கும் வட்ட வடிவ இடுதுளை கொண்ட கல்பதுக்கைகள், பலகைக் கற்கள், மற்றும் அதனைச் சுற்றி அடுக்கப்பட்ட உருண்டைக் கல்வட்டங்கள்.",
        "content": """# Megalithic Dolmen & Cist Architecture (கல்பதுக்கைகளும் டால்மென்களும்)

---

## 1. Key Architectural Elements
- **Orthostats**: Four vertical dressed granite slabs interlocked clockwise like a swastika to prevent inward collapse.
- **Port-Hole (*இடுதுளை*)**: Precision circular perforation (30–45 cm diameter) cut through the eastern slab for symbolic post-mortem soul passage and secondary grave offerings.
- **Capstone**: Multi-ton horizontal granite slab sealing the chamber from above.
- **Lithic Circle (*கல்வட்டம்*)**: Boulders arranged in concentric rings (5–20 meters diameter) packing the interior with rubblestone cairn.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-iron-age-funerary-iron-weapons-and-bronze-diadems",
        "file": "concept-iron-age-funerary-iron-weapons-and-bronze-diadems.md",
        "node_type": "concept",
        "name_en": "Funerary Grave Goods: Gold Filigree Diadems, Iron Broadswords & Bronze Animal Figurines",
        "name_ta": "ஈமப் பொருட்கள் - தங்க நெற்றிப்பட்டங்கள், இரும்பு வாள்கள் மற்றும் வெண்கல விலங்குச் சிற்பங்கள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -1000,
        "year_end": -200,
        "thinai": "Marutham",
        "summary_en": "The extraordinary metallurgical prestige grave goods buried inside Iron Age urns and cists: gossamer-thin gold foil diadems with punctate filigree, socketed iron broadswords, spears, trident javelins, and cast bronze lids surmounted by wild dogs, roosters, and stags.",
        "summary_ta": "ஆதிச்சநல்லூர் மற்றும் கொடுமணல் தாழிகளில் கண்டெடுக்கப்பட்ட அரிய உலோகப் பொருட்கள். மன்னர்களின் நெற்றியில் கட்டப்பட்ட மெல்லிய தங்கப் பட்டங்கள், இரும்புக் குறுவாள்கள், முச்சூலங்கள் மற்றும் நாய்கள், மான்கள், மயில்கள் வடிவில் வார்க்கப்பட்ட வெண்கலக் கலச மூடிகள்.",
        "content": """# Megalithic Funerary Metalwork (ஈம உலோக வேலைப்பாடு)

---

## 1. Gold Diadems (*தங்கப் பட்டம்*)
Oval and leaf-shaped fillets of 90%+ pure gold, punched with intricate geometrical dots along the edges and pierced with tying holes at both ends, worn across the forehead of deceased royalty.

## 2. Advanced Weaponry
Iron swords, lances, and arrows placed points-downward into burial urns, forged with carburized steel edges capable of piercing bronze armor.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-porunai-river-basin-megalithic-metallurgical-ecology",
        "file": "concept-porunai-river-basin-megalithic-metallurgical-ecology.md",
        "node_type": "concept",
        "name_en": "Porunai Megalithic Metallurgical Ecology: High-Tin Bronze Vessels & Red-and-Black Ware",
        "name_ta": "பொருநை பெருங்கற்கால உலோகப் பண்பாடு - வெண்கலப் பாத்திரங்கள் மற்றும் கருப்பு-சிவப்பு மண்பாண்டங்கள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -1150,
        "year_end": 200,
        "thinai": "Marutham",
        "summary_en": "The early industrial ecosystem of the Thamirabarani (Porunai) river valley: combining alluvial iron smelting, 23% high-tin beta-phase bronze casting (for resonant acoustic bowls), inverted reduction Black-and-Red Ware ceramics, and irrigated wet-rice farming dated back to 1155 BCE.",
        "summary_ta": "தாமிரபரணி ஆற்றுப் படுகையில் செழித்து வளர்ந்த உலகின் தொன்மையான உலோகப் பண்பாடு. 23% வெள்ளீயம் கலந்த உயர்-வெண்கலக் கிண்ணங்கள், காந்த இரும்பு தாது உருக்கு, மற்றும் கிமு 1155-இல் உறுதிசெய்யப்பட்ட நெல் உமி சான்றுகளோடு கூடிய பொருநை நாகரிகம்.",
        "content": """# Porunai River Metallurgical Ecology (பொருநை நாகரிகம்)

---

## 1. Deep Antiquity: 1155 BCE
AMS radiocarbon datings from Sivagalai and Adichanallur confirm that iron metallurgy and wet-paddy farming were fully operational along the Porunai river as early as the late 2nd millennium BCE, centuries before urbanization in the Gangetic plain.
"""
    },
    {
        "category": "characters",
        "slug": "char-adichanallur-funerary-potter-and-urn-sculptor",
        "file": "char-adichanallur-funerary-potter-and-urn-sculptor.md",
        "node_type": "character",
        "name_en": "Adichanallur Master Potter: Sculptor of Pyriform Urns & Terracotta Grave Effigies",
        "name_ta": "ஆதிச்சநல்லூர் மட்பாண்டக் கலைஞர் - பிரம்மாண்ட தாழிகள் மற்றும் சுடுமண் சிற்பங்கள் வனைந்த ஆசான்",
        "era": "Iron Age Era",
        "year_start": -800,
        "year_end": -600,
        "thinai": "Marutham",
        "summary_en": "Venerated ceramic artisan (*Kalam-chey-kove*) celebrated in Sangam oral memory, master of monumental coil-pottery who sculpted giant burial urns and ritual terracotta effigies for the Porunai necropolis.",
        "summary_ta": "சங்க இலக்கியத்தில் போற்றப்படும் ஈமக் குயவர். பிரம்மாண்ட தாழிகளை வனைந்து, மண்ணின் ஈரப்பதமும் சுடும் வெப்பநிலையும் துல்லியமாகக் கட்டுப்படுத்தி ஆயிரக்கணக்கான ஆண்டுகள் அழியாத தாழிகளை உருவாக்கிய கைவினைப் பெருமகன்.",
        "content": """# The Master Funerary Potter (தாழி வனைந்த குயவர்)

Possessed sacred social standing as the ritual mediator between the mortal agrarian community and the subterranean ancestral realm.
"""
    },
    {
        "category": "characters",
        "slug": "char-porunai-megalithic-chieftain",
        "file": "char-porunai-megalithic-chieftain.md",
        "node_type": "character",
        "name_en": "Porunai Megalithic Chieftain: Wearer of the Gold Diadem & Commander of the Iron Lance",
        "name_ta": "பொருநைப் பெருங்கற்காலத் தலைவர் - பொன் நெற்றிப்பட்டம் அணிந்த இரும்புப் படைத் தலைவன்",
        "era": "Iron Age Era",
        "year_start": -900,
        "year_end": -700,
        "thinai": "Marutham",
        "summary_en": "Archaic warrior chieftain interred at Adichanallur, adorned with a gold filigree forehead band, surrounded by iron broadswords, bronze banqueting bowls, and hundreds of ceremonial clay pots filled with grain offerings.",
        "summary_ta": "ஆதிச்சநல்லூரில் தங்க நெற்றிப்பட்டமும் இரும்பு வாளும் தாங்கி நல்லடக்கம் செய்யப்பட்ட தொல் தமிழர் பெருந்தலைவர். பொருநைப் படுகையின் வேளாண்மை மற்றும் இரும்பு உற்பத்தியை வழிநடத்திய போர் வீரன்.",
        "content": """# The Porunai Chieftain (பெருங்கற்காலத் தலைவன்)

Embodied early historic martial power, leading iron-armed cavalry and foot-soldiers long before the rise of the classical Pandyan imperial state.
"""
    },
    {
        "category": "places",
        "slug": "place-mallachandram-megalithic-dolmens",
        "file": "place-mallachandram-megalithic-dolmens.md",
        "node_type": "place",
        "name_en": "Mallachandram: The Moraiyar Hill Megalithic Necropolis & 200 Granite Dolmens",
        "name_ta": "மல்லசந்திரம் - மோரையார் மலை 200 பெருங்கற்கால டால்மென் கல்பதுக்கைகளின் பெருந்தளம்",
        "era": "Iron Age to Sangam Early Historic",
        "year_start": -1000,
        "year_end": 200,
        "thinai": "Kurinji",
        "summary_en": "The largest concentration of megalithic dolmens in South India, situated on the slopes of the Moraiyar Hill near Krishnagiri, boasting over 200 intact granite dolmenoid cists, port-hole slabs, concentric stone circles, and white kaolin anthropomorphic rock paintings.",
        "summary_ta": "தென்னிந்தியாவிலேயே மிக அதிக எண்ணிக்கையிலான (200-க்கும் மேற்பட்ட) கல்பதுக்கைகள் மற்றும் டால்மென்கள் கொண்ட மாபெரும் தளம். கிருஷ்ணகிரி மோரையார் மலையில் கம்பீரமாக நிற்கும் கல் அறைகள், இடுதுளைகள் மற்றும் வெண்சாந்துப் பாறை ஓவியங்கள் கொண்ட வரலாற்றுப் பொக்கிஷம்.",
        "content": """# Mallachandram Megalithic Complex (மல்லசந்திரம்)

- **Coordinates**: 12.5833° N, 78.1333° E.  
- **District**: Krishnagiri, Tamil Nadu.  
- **Archaeological Glory**: Over 200 monumental dolmens featuring east-facing circular port-holes, surrounded by concentric cairn circles dating to the 1st millennium BCE.
"""
    }
]

# ==============================================================================
# RELATIONAL EDGES (30 Total)
# ==============================================================================
EDGES = [
    # Corpus 1 Edges: Astronomy & Nakshatra Calendrics
    ("text-kanakkan-parani-astronomical-nakshatra-canon", "codifies", "concept-nakshatra-27-asterism-calendrical-metrology", "astronomy", "Early Medieval", "Manual details the 27 asterisms and 60-Nazhikai daily division.", "Kanakkan Parani verses"),
    ("text-kanakkan-parani-astronomical-nakshatra-canon", "used_by", "char-kanakkathikari-astronomical-epigrapher", "applied_mathematics", "Imperial Chola", "Court astronomers utilized the manual to calculate royal ephemerides.", "Chola epigraphy"),
    ("insc-tiruvidaimarudur-solar-eclipse-charters", "records_phenomenon", "concept-solar-and-lunar-eclipse-epigraphical-reckoning", "astronomy", "1001 CE", "Mahalingaswami inscription records solar eclipse in Mithuna New Moon.", "Tiruvidaimarudur epigraph"),
    ("insc-tiruvidaimarudur-solar-eclipse-charters", "situated_at", "place-tiruvidaimarudur-astronomical-epigraph-center", "geography", "Medieval", "Preserved on the central sanctum walls of Tiruvidaimarudur.", "Archaeological Survey"),
    ("char-tiruvidaimarudur-eclipse-assayer", "observed_at", "place-tiruvidaimarudur-astronomical-epigraph-center", "observation", "Imperial Chola", "Priestly astronomers audited gold endowments during solar eclipses.", "Temple records"),
    ("char-kanakkathikari-astronomical-epigrapher", "authored", "concept-meykkirthi-astronomical-regnal-synchronization", "epigraphy", "Imperial Chola", "Astronomers verified multi-variable date codes prefacing royal charters.", "Meykkirthi formulas"),
    ("concept-meykkirthi-astronomical-regnal-synchronization", "verified_by", "insc-kudumiyamalai-astronomical-ephemeris-records", "chronology", "Medieval", "Planetary conjunctions of Jupiter and Saturn calibrate Pandyan regnal years.", "Kudumiyamalai epigraphs"),
    ("concept-sanku-gnomon-and-neer-nazhikai-water-clocks", "calibrated_by", "char-kanakkathikari-astronomical-epigrapher", "instrumentation", "Ancient-Medieval", "Shadow gnomon and water bowl clepsydras calibrated local solar time.", "Scribal manuals"),
    ("concept-solar-and-lunar-eclipse-epigraphical-reckoning", "monitored_with", "concept-sanku-gnomon-and-neer-nazhikai-water-clocks", "timekeeping", "Classical-Medieval", "Clepsydras timed the exact Nazhikai of eclipse contact and totality.", "Astronomical texts"),
    ("concept-nakshatra-27-asterism-calendrical-metrology", "synchronizes_with", "concept-meykkirthi-astronomical-regnal-synchronization", "calendrics", "Imperial Chola", "Every royal charter records the reigning asterism alongside solar month.", "Tamil epigraphy"),

    # Corpus 2 Edges: Indo-Pacific Glassmaking & Micro-Beads
    ("text-periplus-maris-erythraei-glass-bead-cargoes", "describes_trade_at", "insc-arikamedu-pottery-and-glass-guild-graffiti", "maritime_trade", "1st c. CE", "Greek text chronicles massive glass bead export from Poduke emporium.", "Periplus sec. 60"),
    ("insc-arikamedu-pottery-and-glass-guild-graffiti", "attests_production_of", "concept-indo-pacific-drawn-glass-bead-pyrotechnics", "industrial_epigraphy", "Early Historic", "Inscribed sherds confirm native artisans operating drawn glass furnaces.", "Wheeler excavations"),
    ("concept-indo-pacific-drawn-glass-bead-pyrotechnics", "developed_by", "char-poduke-master-glass-furnace-blower", "pyrotechnology", "Early Historic", "Glassmasters manipulated iron mandrels to draw 20-meter micro-tubes.", "Glass chemical analysis"),
    ("concept-indo-pacific-drawn-glass-bead-pyrotechnics", "produces", "concept-arikamedu-red-mutisalah-bead-trade-network", "manufacturing", "Ancient-Medieval", "Drawn tube technology created millions of red Mutisalah currency beads.", "Archaeological reports"),
    ("concept-mineral-soda-alumina-glass-chemical-recipes", "defines", "concept-indo-pacific-drawn-glass-bead-pyrotechnics", "chemistry", "Ancient", "High alumina-soda recipes yielded the distinctive chemical fingerprint.", "EMPA/LA-ICP-MS data"),
    ("concept-grooved-stone-bead-polishing-and-stringing", "post_processes", "concept-arikamedu-red-mutisalah-bead-trade-network", "beadmaking", "Early Historic", "Multi-grooved granite slabs and hot ash tumbling rounded bead edges.", "Excavation records"),
    ("char-mutisalah-maritime-bead-merchant", "exported_cargo_from", "place-kudikadu-coastal-glass-bead-furnaces", "shipping", "Early Historic", "Merchants loaded glass micro-beads onto dhows bound for the Indian Ocean.", "Maritime archaeology"),
    ("insc-kudikadu-glass-bead-furnace-charters", "situated_at", "place-kudikadu-coastal-glass-bead-furnaces", "geography", "Early Medieval", "Inscriptions at Kudikadu record continuing glassmaking guild charters.", "Cuddalore epigraphy"),
    ("concept-arikamedu-red-mutisalah-bead-trade-network", "traded_by", "char-mutisalah-maritime-bead-merchant", "commerce", "1st-10th c. CE", "Merchants used red Mutisalah beads as international trade currency.", "Global trade history"),
    ("place-kudikadu-coastal-glass-bead-furnaces", "succeeded", "insc-arikamedu-pottery-and-glass-guild-graffiti", "industrial_succession", "4th c. CE", "Kudikadu sustained the Coromandel drawn glass industry after Arikamedu.", "Archaeological stratigraphy"),

    # Corpus 3 Edges: Iron Age Megalithic Urns & Dolmens
    ("text-purananuru-mudumakkal-thaazhi-funerary-poetry", "celebrates_craft_of", "char-adichanallur-funerary-potter-and-urn-sculptor", "oral_tradition", "Sangam Classical", "Poems invoke the potter moulding colossal burial urns for kings.", "Purananuru poem 228"),
    ("text-purananuru-mudumakkal-thaazhi-funerary-poetry", "depicts", "concept-mudumakkal-thaazhi-pyriform-urn-engineering", "mortuary_custom", "Sangam Classical", "Verses describe pyriform terracotta jars burying chieftains with the earth.", "Purananuru poem 256"),
    ("insc-adichanallur-tamil-brahmi-urn-excavation-records", "excavated_from", "concept-porunai-river-basin-megalithic-metallurgical-ecology", "archaeology", "1000 BCE", "Urns in Porunai valley yielded archaic proto-writing and bronze diadems.", "ASI reports"),
    ("char-porunai-megalithic-chieftain", "interred_with", "concept-iron-age-funerary-iron-weapons-and-bronze-diadems", "regalia", "1st millennium BCE", "Chieftain buried wearing gold filigree diadem and socketed iron lances.", "Rea collection"),
    ("concept-mudumakkal-thaazhi-pyriform-urn-engineering", "contains", "concept-iron-age-funerary-iron-weapons-and-bronze-diadems", "burial_assemblage", "Iron Age", "Pyriform jars enclosed secondary skeletal remains and forged grave goods.", "Excavation records"),
    ("insc-kodumanal-megalithic-cist-tomb-inscriptions", "exemplifies", "concept-megalithic-cist-and-dolmen-stone-circle-architecture", "funerary_architecture", "Iron Age", "Kodumanal cist tombs feature orthostats, port-holes, and inscribed pots.", "Tamil University"),
    ("concept-megalithic-cist-and-dolmen-stone-circle-architecture", "manifested_at", "place-mallachandram-megalithic-dolmens", "monumental_site", "Iron Age", "Over 200 intact dolmens and port-holed cists crown the Moraiyar Hill.", "State Archaeology"),
    ("concept-porunai-river-basin-megalithic-metallurgical-ecology", "centered_on", "char-porunai-megalithic-chieftain", "political_economy", "Iron Age", "Porunai iron-smelters and paddy cultivators supported warrior chiefs.", "AMS radiocarbon dates"),
    ("char-adichanallur-funerary-potter-and-urn-sculptor", "fabricated", "concept-mudumakkal-thaazhi-pyriform-urn-engineering", "ceramic_arts", "Iron Age", "Potters engineered two-meter jars capable of resisting earth pressures.", "Ceramic engineering"),
    ("place-mallachandram-megalithic-dolmens", "preserves", "concept-megalithic-cist-and-dolmen-stone-circle-architecture", "heritage", "1st millennium BCE", "Krishnagiri plateau preserves the largest concentration of Tamil dolmens.", "ASI monuments")
]

# ==============================================================================
# MAIN HARVESTER EXECUTION
# ==============================================================================
def main():
    print("=" * 70)
    print("🚀 BATCH 9: TRIPLE CIVILIZATIONAL EXPANSION HARVESTER")
    print("   1. Classical Astronomy, Nakshatra Calendrics & Eclipses (10 dossiers)")
    print("   2. Indo-Pacific Glassmaking & Drawn Micro-Beads (10 dossiers)")
    print("   3. Iron Age Megalithic Burial Architecture & Urns (10 dossiers)")
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
