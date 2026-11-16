#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 8):
1. Temple Architecture, Stone Quarrying & Agamic Vastu Engineering (10 dossiers)
2. Classical Dance, Koothu Traditions & Natya Metrology (10 dossiers)
3. Overseas Maritime Expeditions, Kadaram (Kedah) & Song Dynasty Diplomacy (10 dossiers)

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
    # CORPUS 1: TEMPLE ARCHITECTURE, STONE QUARRYING & AGAMIC VASTU
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-mayamata-silparatna-tamil-agamic-vastu",
        "file": "text-mayamata-silparatna-tamil-agamic-vastu.md",
        "node_type": "text",
        "name_en": "Mayamata & Silpa Texts: Agamic Vastu, Mandala Grids & Dravidian Metrology",
        "name_ta": "மயமதம் மற்றும் சிற்பசாஸ்திரம் - ஆகம வாஸ்து, மண்டல அமைப்புகள் மற்றும் திராவிட கட்டிடக்கலை",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 800,
        "year_end": 1150,
        "thinai": "Marutham",
        "summary_en": "Canonical architectural treatises codified in Tamil country defining sacred geometry, the 64- and 81-square Padavinyasa Vastu Mandalas, linear Hasta metrology, vertical Tala proportions, and sanctum-to-vimana structural mechanics.",
        "summary_ta": "தமிழகத்தில் பின்பற்றப்பட்ட சிற்ப, கட்டிடக்கலை மூல நூல்கள். 64 மற்றும் 81 கட்டங்கள் கொண்ட பதவின்யாச வாஸ்து மண்டலங்கள், முழம்-அங்குலம் சார்ந்த அளவீடுகள், விமான உயர விகிதங்கள் மற்றும் கருவறை நிர்மாணக் கோட்பாடுகள்.",
        "content": """# Mayamata & Silpa Sastras (மயமதம் - சிற்பசாஸ்திரம்)

**Source**: *Mayamata* (*மயமதம்*), *Silparatna* (*சிற்பரத்னம்*), Inscriptional Silpa Glosses.  
**Key Disciplines**: Vastu Vidya (*வாஸ்து வித்யா*), Sacred Metrology (*தாளமானம்*), Dravidian Vimana Structural Dynamics.

---

## 1. Sacred Spatial Metrology
- **Hasta / Muzham (*முழம்*)**: The fundamental linear unit calibrated to 24 *Angulas* (~33 inches / 84 cm).
- **Vastu Purusha Mandala (*வாஸ்து புருஷ மண்டலம்*)**:
  - *Manduka Mandala* (8x8 = 64 squares) used for royal civic complexes and open shrines.
  - *Paramasayika Mandala* (9x9 = 81 squares) dedicated to cosmic Siva sanctuaries, where the central 9 squares (*Brahmasthana*) harbor the sanctum garbhagriha.

## 2. Proportion and Tala Harmony
Vertical elevation was governed by fixed ratios derived from sanctum width (*Adhishthana* to *Stupi*):
1. **Upapitha (*உபபீடம்*)**: Plinth pedestal height (0.25 to 0.5 ratio).
2. **Bhiti (*சுவர்/பாதம்*)**: Vertical pilastered wall bearing devakoshtha niche sculptures.
3. **Prastara (*பிரஸ்தரம்*)**: Entablature with kapota cornices and yali friezes.
4. **Griva & Sikhara (*கழுத்து மற்றும் சிகரம்*)**: Octagonal or square drum crowned by monolithic spherical cupola.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thanjavur-peruvudaiyar-architect-charter",
        "file": "insc-thanjavur-peruvudaiyar-architect-charter.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Brihadisvara Foundation Epigraphs: Inscribing the Master Architects & Sculptors",
        "name_ta": "தஞ்சைப் பெரியகோயில் அடிக்கல்வெட்டு - தலைமைத் தச்சர்கள் மற்றும் சிற்பிகள் பெயர் பொறித்த சாசனம்",
        "era": "Imperial Chola Era",
        "year_start": 1004,
        "year_end": 1010,
        "thinai": "Marutham",
        "summary_en": "Monumental royal epigraphs on the southern and northern basements of the Brihadisvara temple in Thanjavur recording Rajaraja I's decree honoring chief architects Kunjaramallan Rajaraja Perunthatchan, Ilaiyan, and their teams.",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயில் வடக்கு மற்றும் தெற்குத் தளவரிசைகளில் பொறிக்கப்பட்ட இராஜராஜ சோழனின் அடிக்கல்வெட்டு. தலைமைப் பெருந்தச்சன் வீரசோழன் குஞ்சரமல்லன் மற்றும் அவரது துணைச் சிற்பிகளின் பெயர்களை அழியாமல் கல்லில் பதித்த அரிய வரலாற்று ஆவணம்.",
        "content": """# Brihadisvara Foundation Charters (தஞ்சை அடிக்கல்வெட்டு)

**Location**: Brihadisvara Temple (*இராஜராஜேச்சரம்*), Thanjavur.  
**Commission**: King Rajaraja Chola I (completed 1010 CE).  

---

## 1. Royal Recognition of Sthapatis
Unlike contemporaneous civilizations where monumental architects remained anonymous, Rajaraja I ordered the exact names and titles of his master builders incised on the sanctum base:
- **Kunjaramallan Rajaraja Perunthatchan (*குஞ்சரமல்லன் இராஜராஜப் பெருந்தச்சன்*)**: Supreme Architect.
- **Nittavinoda Perunthatchan (*நித்தவிநோதப் பெருந்தச்சன்*)**: Master Stone Carver and Scaffolding Engineer.
- **Ilaiyan (*இளையான்*)**: Associate Architect.

## 2. The Golden Kalasam Endowment
In his 25th regnal year (1010 CE), the king personally mounted the scaffolding to present the 25-kalaju gold-plated copper finial (*Stupi-k-kudam*) atop the 216-foot vimana, recorded in line-by-line inventory.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-gangaikonda-cholapuram-foundation-charters",
        "file": "insc-gangaikonda-cholapuram-foundation-charters.md",
        "node_type": "inscription",
        "name_en": "Gangaikonda Cholapuram Foundation Charters: Rajendra I's Octagonal Vimana Engineering",
        "name_ta": "கங்கைகொண்ட சோழபுரம் அடிக்கல்வெட்டுகள் - இராஜேந்திர சோழனின் வளைந்த எண்கோண விமான அமைப்பு",
        "era": "Imperial Chola Era",
        "year_start": 1025,
        "year_end": 1035,
        "thinai": "Marutham",
        "summary_en": "Foundation epigraphs and structural inscriptions of Rajendra I's grand capital temple, documenting its revolutionary concave curvilinear vimana (182 feet tall), female architectural grace, and vast subterranean water vaults.",
        "summary_ta": "முதலாம் இராஜேந்திர சோழன் தனது கங்கை வெற்றியைத் தொடர்ந்து நிர்மாணித்த கங்கைகொண்ட சோழீச்சரக் கோயில் கல்வெட்டுகள். தஞ்சையின் நேர்கோட்டு அமைப்பிற்கு மாறாக, மென்மையான வளைவுகளுடன் கூடிய எண்கோண விமானம் மற்றும் சுரங்க நீர் தொட்டிகளின் நுட்பங்கள்.",
        "content": """# Gangaikonda Cholapuram Foundation Charters (கங்கைகொண்ட சோழீச்சரம்)

---

## 1. Architectural Counterpoint to Thanjavur
- While Thanjavur exhibits masculine, rigid rectilinear geometry, Gangaikonda Cholapuram features a soaring, inward-curving parabolic contour (*சுழல்வளைவு*).
- Rising 55 meters (182 feet), the vimana sits on an expansive recessed basement engineered to cushion dynamic wind shear and heavy alluvial settling.

## 2. Engineering Innovations
- **Ganga-Jalam Cisterns**: Underground granite vaults connected to the Chola-gangam lake to maintain cool sanctum temperatures during tropical droughts.
- **Massive Monolithic Dvarapalas**: Sculpted from imported blue-black chlorite schist and granite blocks transported over 60 km from riverside quarries.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-granite-quarrying-and-kaveri-barge-transport",
        "file": "concept-granite-quarrying-and-kaveri-barge-transport.md",
        "node_type": "concept",
        "name_en": "Granite Quarrying, Wedge-Splitting & Kaveri Fluvial Barge Transport",
        "name_ta": "கற்கோவாரி நுட்பம், மர ஆப்பு பிளத்தல் மற்றும் காவிரி ஆற்றுப் படகுப் போக்குவரத்து",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1150,
        "thinai": "Marutham",
        "summary_en": "The monumental logistics of Chola temple masonry: quarrying millions of tons of dense charnockite granite without explosives using dry-wood swelling wedges, and ferrying multi-ton dressed blocks across the Kaveri and Kollidam rivers on flat-bottom wooden barges.",
        "summary_ta": "வெடிபொருட்கள் இல்லாத காலத்தில் கடினமான கருங்கற்களைப் பிளந்த திராவிடப் பொறியியல். பாறை இடுக்குகளில் உலர்ந்த மர ஆப்புகளை அடித்து நீர் ஊற்றிப் பிளத்தல், மற்றும் அம்மங்குடி, குன்னாண்டார்கோயில் பாறைகளிலிருந்து தட்டை மரப் படகுகள் (பரிசல்/தோணி) மூலம் காவிரியில் மிதக்கவிட்டு தஞ்சைக்குக் கொண்டுசென்ற முறைமை.",
        "content": """# Granite Quarrying & Fluvial Barge Logistics (கற்பாறை போக்குவரத்து)

---

## 1. Wooden Wedge Rock-Splitting (*ஆப்பு முறை*)
1. Stonecutters chiseled rectangular grooves (6–10 cm apart) along natural rock grain.
2. Dried tamarind or babul wood pegs were hammered tight into the slots.
3. Boiling water poured continuously caused wood fibers to swell with enormous hydrostatic pressure, cleanly fracturing multi-ton megaliths along true planes.

## 2. Riverine Flotillas (*ஆற்றுப் படகுகள்*)
Since Thanjavur lies entirely within deep Kaveri alluvial silt devoid of stone, over 130,000 tons of granite were ferried from Mammallapuram, Pachaimalai, and Ammangudi:
- Large catamaran-style rafts (*Kattu-maram*) and flat-bottomed timber barges hauled megaliths during the high-water monsoon floods.
- Megaliths were transferred onto greased log rollers pulled by royal war elephants directly to the temple site.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-interlocking-dry-masonry-and-corbelled-vaulting",
        "file": "concept-interlocking-dry-masonry-and-corbelled-vaulting.md",
        "node_type": "concept",
        "name_en": "Interlocking Dry-Stone Masonry, Mortise-and-Tenon Joints & Corbelled Vaults",
        "name_ta": "சாந்தற்ற உலர் கருங்கல் அடுக்கு, குடைவு மூட்டு மற்றும் அடுக்குக் குவிமாடம்",
        "era": "Imperial Chola Era",
        "year_start": 950,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "The dry-masonry construction technique of medieval Tamil vimanas erected entirely without binding mortar, utilizing perfectly polished load-bearing surfaces, stone dowels, mortise-tenon joints, and hollow-box corbelled vaulting that distributed loads downwards by pure gravity.",
        "summary_ta": "சுண்ணாம்பு அல்லது சாந்துப் பூச்சு ஏதுமின்றி, முழுவதுமாக உலர் கருங்கற்களைக் கொண்டு கட்டப்பட்ட திராவிட விமான நுட்பம். கற்களுக்கிடையே செதுக்கப்பட்ட ஆண்-பெண் மூட்டுகள் (குடைவு மற்றும் குமிழ்), மற்றும் உட்புறம் உள்ளீடற்ற வெற்றிடமாக எடையைக் குறைக்கும் அடுக்குக் குவிமாட (Corbelling) பொறியியல்.",
        "content": """# Dry-Masonry & Corbelled Vaulting (உலர் கருங்கல் அடுக்கு முறை)

---

## 1. Zero-Mortar Gravity Lock
Chola master builders relied on absolute geometric leveling:
- Each stone was dressed to mirror-smooth tolerances; stone surfaces gripped via direct friction.
- Hidden stone mortise-and-tenon dowels (*ஆண்-பெண் முளைகள்*) prevented horizontal sliding during earth tremors.

## 2. Hollow-Core Corbelled Vimana
The 66-meter Brihadisvara tower is not a solid mass:
- Above the sanctum ceiling, the hollow interior tapers upwards via successive overlapping stone rings (*Corbelling / அடுக்குக் குவிப்பு*).
- This eliminated deadweight, directing massive gravitational compression vertically into the 5-meter-thick double perimeter walls (*Anthar-mandala*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-agamic-vastu-mandala-temple-metrology",
        "file": "concept-agamic-vastu-mandala-temple-metrology.md",
        "node_type": "concept",
        "name_en": "Agamic Vastu Mandala: Padavinyasa Grids, Hastas & Proportional Tala Ratios",
        "name_ta": "ஆகம வாஸ்து மண்டலம் - பதவின்யாசக் கட்டமைப்பு, முழம் மற்றும் தாளமான விகிதங்கள்",
        "era": "Classical to Imperial Chola Era",
        "year_start": 700,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The sacred spatial mathematics governing temple floorplans according to Saiva Agamas (Kamika, Karana): allocating concentric perimeter rings (Paisacha, Manusha, Daivika, Brahma), orientation by gnomon sun-shadows (Sanku), and modular harmony.",
        "summary_ta": "சைவாகமங்கள் வகுத்த புனித கணித நிலவரைபடம். சங்குக் குச்சி நிழல் கொண்டு திசைகளைத் துல்லியமாக அறிதல், பிரம்ம பதம் முதல் பைசாச பதம் வரையிலான சமச்சீர் வளையங்கள், மற்றும் கருவறையை மையமாகக் கொண்ட கட்டிடக் கணித சமநிலை.",
        "content": """# Agamic Vastu Mandala Metrology (வாஸ்து கணிதம்)

---

## 1. Astronomical Orientation via Sanku
Before groundbreaking, a vertical gnomon staff (*சங்கு*) was planted on leveled ground:
- The circular shadow cast at vernal and autumnal equinoxes marked true astronomical East-West and North-South axes with zero compass deviation.

## 2. Concentric Padavinyasa Zones
1. **Brahma-Pada (*பிரம்ம பதம்*)**: Sanctum core containing the Mula-murti.
2. **Daivika-Pada (*தெய்வீக பதம்*)**: Internal ambulatory passage (*Pradakshina-patha*).
3. **Manusha-Pada (*மானுஷ பதம்*)**: Pillared gathering pavilions (*Ardha-mandapa*, *Maha-mandapa*).
4. **Paisacha-Pada (*பைசாச பதம்*)**: Outermost circumambulatory precinct and boundary cloister walls (*Malika*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kudamuzha-and-sikhara-monolith-hoisting-ramps",
        "file": "concept-kudamuzha-and-sikhara-monolith-hoisting-ramps.md",
        "node_type": "concept",
        "name_en": "Sikhara Monolith Hoisting: Inclined Earth Ramps & Capstone Placement Engineering",
        "name_ta": "சிகரப் பெருங்கல் ஏற்றுதல் - சாய்தள மண்மேடு மற்றும் உச்சித்தளப் பொறியியல்",
        "era": "Imperial Chola Era",
        "year_start": 1005,
        "year_end": 1010,
        "thinai": "Marutham",
        "summary_en": "The colossal civil engineering achievement of hoisting the 81.3-ton octagonal granite cupola capstone atop the 216-foot Brihadisvara tower: constructing an inclined earthen and timber ramp extending 6 kilometers from Sarabhojirajapuram / Vayalur, propelled by elephant teams and capstans.",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயிலின் 216 அடி உயர விமான உச்சிக்கு 80 டன் எடையுள்ள பிரம்மாண்ட கருங்கல் சிகரத்தை ஏற்றிய வரலாற்றுப் பொறியியல். சாரப்பள்ளம் (சாரோஜிபுரம்) கிராமத்திலிருந்து 6 கி.மீ நீளத்திற்கு அமைக்கப்பட்ட சாய்தள மண்மேடு, மர உருளைகள் மற்றும் யானைப்படைகளைக் கொண்டு உச்சிக்கு நகர்த்திய விதம்.",
        "content": """# Sikhara Monolith Hoisting Engineering (சிகரக் கல் ஏற்றல்)

---

## 1. The 6-Kilometer Inclined Ramp (*சாரப்பள்ளம்*)
To lift the massive 80-ton granite sikhara to a height of 66 meters without modern cranes:
- Royal engineers constructed a gradual earthen incline starting from the village of *Sarappallam* (modern Sarabhojirajapuram), sloping at ~1:90 grade.
- Reinforced with timber bulkheads and palm-trunk rollers (*உருளை மரம்*), teams of armored war elephants and thousands of draft oxen pushed and hauled the block upward using hemp cordage and geared capstans (*கப்பி*).

## 2. Capstone Placement & Ramp Dismantling
Once hoisted into position above the griva neck, the capstone was set onto copper dowels. The earthen ramp was excavated away and distributed across village agriculture lands as fertile embankment fill.
"""
    },
    {
        "category": "characters",
        "slug": "char-kunjaramallan-rajaraja-perunthatchan-architect",
        "file": "char-kunjaramallan-rajaraja-perunthatchan-architect.md",
        "node_type": "character",
        "name_en": "Kunjaramallan Rajaraja Perunthatchan: Chief Imperial Architect of Brihadisvara",
        "name_ta": "குஞ்சரமல்லன் இராஜராஜப் பெருந்தச்சன் - தஞ்சைப் பெருவுடையார் கோயிலின் தலைமைத் தச்சன்",
        "era": "Imperial Chola Era",
        "year_start": 970,
        "year_end": 1030,
        "thinai": "Marutham",
        "summary_en": "The supreme master architect, geometrician, and state civil engineer commissioned by Rajaraja I to design, engineer, and oversee the entire construction of Brihadisvara Temple, honored with royal titles incised in stone.",
        "summary_ta": "தஞ்சைப் பெரிய கோயிலின் தலைமை வடிவமைப்பாளர் மற்றும் தலைமைப் பொறியாளர். ஆகம வாஸ்து, கணித அளவீடுகள், கருங்கல் பிளத்தல் மற்றும் 216 அடி விமான நிர்மாணத்தை முழுமையாக வழிநடத்தி, இராஜராஜ சோழனால் கல்வெட்டில் புகழப்பட்ட வரலாற்றுப் பெருந்தச்சன்.",
        "content": """# Kunjaramallan Rajaraja Perunthatchan (தலைமைப் பெருந்தச்சன்)

---

## 1. Identity & Titles
Inscriptions proclaim him as *Perunthatchan* (Grand Architect) bearing the royal honorific *Veeracholan Kunjaramallan*. His intimate mastery of Dravidian structural dynamics enabled the erection of the tallest stone monument of the medieval world.
"""
    },
    {
        "category": "characters",
        "slug": "char-ammangudi-granite-quarry-master",
        "file": "char-ammangudi-granite-quarry-master.md",
        "node_type": "character",
        "name_en": "Ammangudi Granite Quarry Master: Fluvial Stone Mason & Flotilla Pilot",
        "name_ta": "அம்மங்குடிக் கல் தச்சன் - பாறை பிளக்கும் வல்லுநர் மற்றும் படகோட்டி",
        "era": "Imperial Chola Era",
        "year_start": 990,
        "year_end": 1040,
        "thinai": "Marutham",
        "summary_en": "Master stonecutter and quarry superintendent based at the granite outcrops north of the Kaveri, directing wedge cleavage, surface dressing, and barge loading during the imperial building boom.",
        "summary_ta": "காவிரியின் வடகரைக் குன்றுகளில் கருங்கற்களை ஆய்வு செய்து பிளந்து, செப்பனிட்டு, ஆற்றுப் படகுகளில் ஏற்றி தஞ்சைக்கு அனுப்பிவைத்த கல் தச்சர்களின் தலைமை அதிகாரி.",
        "content": """# Ammangudi Quarry Master (கற்பாறை ஆசான்)

Responsible for selecting flawless plutonic charnockite blocks free of hair-cracks (*சுண்ணாம்புக் கீறல்*), testing density with rhythmic copper hammer strikes.
"""
    },
    {
        "category": "places",
        "slug": "place-ammangudi-chola-granite-quarries",
        "file": "place-ammangudi-chola-granite-quarries.md",
        "node_type": "place",
        "name_en": "Ammangudi: Chola Imperial Granite Quarries & Kaveri Barge Loading Basin",
        "name_ta": "அம்மங்குடி - சோழர் காலத்துக் கருங்கல் சுரங்கம் மற்றும் ஆற்றுப் படகுத் துறை",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "Historic granite outcrop and river harbor basin located north of Kumbakonam in the Kaveri alluvial delta, identified as the primary source quarry for massive granite blocks ferried to Thanjavur and Gangaikonda Cholapuram.",
        "summary_ta": "கும்பகோணம் அருகே காவிரிக் கரையில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க கருங்கல் குவாரி மற்றும் படகுத் துறை. தஞ்சைப் பெரியகோயில் மற்றும் கங்கைகொண்ட சோழபுரக் கட்டுமானத்திற்கு டன் கணக்கில் பாறைகள் வெட்டி அனுப்பப்பட்ட முக்கிய தளம்.",
        "content": """# Ammangudi Granite Quarries (அம்மங்குடி)

- **Coordinates**: 10.9667° N, 79.3500° E.  
- **District**: Thanjavur / Kumbakonam region, Tamil Nadu.  
- **Geological Heritage**: Exposed outcrops of Precambrian charnockite granite situated directly adjacent to navigable waterways.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: CLASSICAL DANCE, KOOTHU TRADITIONS & NATYA METROLOGY
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-silappadikaram-arangetru-kadhai-dance-canon",
        "file": "text-silappadikaram-arangetru-kadhai-dance-canon.md",
        "node_type": "text",
        "name_en": "Silappadikaram Arangetru Kadhai: The Classical Tamil Natya Canon & Stage Debut Protocol",
        "name_ta": "சிலப்பதிகாரம் அரங்கேற்று காதை - செவ்வியல் நாட்டிய சாஸ்திரம், மாதவி அரங்கேற்றம் மற்றும் மேடை அமைப்பு",
        "era": "Sangam Post-Classical Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "Marutham",
        "summary_en": "The third canto of Ilango Adigal's Silappadikaram serving as the definitive indigenous treatise on Tamil dance (Koothu), theatrical proscenium metrics, bamboo measuring rods, the 11 forms of sacred dances (Aadal), tala varieties, and the formal arangetram of dancer Madhavi.",
        "summary_ta": "இளங்கோவடிகள் இயற்றிய சிலப்பதிகாரத்தின் அரங்கேற்று காதை. நாட்டிய மேடை அளவுகள் (எண்கோல் மேடை), திரைச்சீலை நுட்பங்கள், 11 வகை ஆடல்கள் (அல்லியம், கொடுகொட்டி, குடைக்கூத்து போன்றவை), தலைக்கோல் ஆசான் மற்றும் மாதவியின் வரலாற்றுச் சிறப்புமிக்க நாட்டிய அரங்கேற்ற நெறிமுறைகள்.",
        "content": """# Silappadikaram Arangetru Kadhai (அரங்கேற்று காதை)

**Source**: *Silappadikaram* (*சிலப்பதிகாரம்*), Canto 3.  
**Author**: Ilango Adigal (*இளங்கோவடிகள்*).  

---

## 1. The Eleven Classical Dances (*பதினொரு ஆடல்கள்*)
The text categorizes indigenous divine dances into two broad schools:
- **Standing Dances (*நின்றாடல்*)**:
  1. *Alliyam* (Krishna destroying the rogue elephant).
  2. *Kodukotti* (Siva's cosmic cremation dance with Uma).
  3. *Katai* (Siva as Ardhanarisvara).
  4. *Kudaikoothu* (Subrahmanya dancing with a lowered parasol).
  5. *Thudi* (Subrahmanya celebrating victory over Surapadman on the sea).
- **Falling/Pantomimic Dances (*வீழ்ந்தாடல்*)**:
  6. *Mallu* (Krishna's wrestling dance against Banasura).
  7. *Kudaikoothu / Kudam* (Vishnu dancing with water pots).
  8. *Pedhi* (Kama dancing in the guise of a hermaphrodite).
  9. *Marakkal* (Durga dancing on wooden stilts over venomous serpents).
  10. *Pavai* (Lakshmi dancing in golden effigy).
  11. *Kadayal* (Indrani dancing in the agricultural fields).
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thanjavur-talicceri-pendir-dance-charter",
        "file": "insc-thanjavur-talicceri-pendir-dance-charter.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Talicceri Pendir Inscriptions: Rajaraja I's 400 Temple Dancers & Street Endowments",
        "name_ta": "தஞ்சை தளிச்சேரிப் பெண்டிர் கல்வெட்டு - 400 நடன மாதர்கள் பெயர், ஊர் மற்றும் நில மானியப் பட்டியல்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Monumental epigraph incised across the northern exterior basement of the Brihadisvara sanctum, listing all 400 master dancers (Talicceri Pendir) brought from temple centers across Tamilakam, their individual house numbers, native towns, and permanent land endowments (Pangu).",
        "summary_ta": "தஞ்சைப் பெரிய கோயில் வடக்குச் சுவரில் பொறிக்கப்பட்ட வியத்தகு வரலாற்று ஆவணம். தமிழகத்தின் பல்வேறு ஊர்களிலிருந்து வரவழைக்கப்பட்ட 400 தலைசிறந்த நடனக் கலைஞர்களின் இயற்பெயர்கள், வீட்டின் கதவு எண்கள், ஊர்ப் பெயர்கள் மற்றும் அவர்களுக்கு வழங்கப்பட்ட நிலப் பங்கு (பங்கு ஒன்றுக்கு 100 கலம் நெல்) பற்றிய முழுமையான பதிவு.",
        "content": """# Talicceri Pendir Inscriptions (தளிச்சேரிப் பெண்டிர் சாசனம்)

---

## 1. Social & Professional Demographics
Rajaraja I settled 400 accomplished dancers in four newly built avenues (*Talicceri*):
- **Northern Wing (*வடக்குத் தளிச்சேரி*)**: 200 dancers.
- **Southern Wing (*தெற்குத் தளிச்சேரி*)**: 200 dancers.

## 2. Economic Endowments (*பங்கு நிலம்*)
Every single artist was assigned one full share (*Pangu*) yielding 100 kalams of paddy per year from royal lands, ensuring lifelong artistic freedom without economic dependence. Accompanists (flutists, drummers, singers, conch blowers) were similarly endowed.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-chidambaram-natya-karana-sculptural-epigraphs",
        "file": "insc-chidambaram-natya-karana-sculptural-epigraphs.md",
        "node_type": "inscription",
        "name_en": "Chidambaram Natya Karana Epigraphs: 108 Classical Dance Postures & Inscribed Labels",
        "name_ta": "சிதம்பரம் நாட்டிய கரணக் கல்வெட்டுகள் - 108 பரதநாட்டிய கரணச் சிற்பங்களும் விளக்கக் குறிப்புகளும்",
        "era": "Later Chola Era",
        "year_start": 1180,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "Sculptural bas-reliefs on the eastern and western gopurams of the Chidambaram Nataraja Temple, accompanied by precise bilingual Sanskrit and Grantha/Tamil label inscriptions detailing all 108 Karanas (dance transition units) codified in the Natya Shastra.",
        "summary_ta": "சிதம்பரம் நடராஜர் கோயில் கிழக்கு மற்றும் மேற்கு கோபுர நுழைவாயில்களில் செதுக்கப்பட்டுள்ள 108 நாட்டிய கரணச் சிற்பங்கள். ஒவ்வொரு சிற்பத்திற்கு அருகிலும் அதன் வடமொழி மற்றும் தமிழ்ப் பெயர் பொறிக்கப்பட்டு, உலகிலேயே நடன இயக்கங்களை காட்சிப்படுத்திய முதல் சிற்பக் கலைக்களஞ்சியம்.",
        "content": """# Chidambaram 108 Karana Epigraphs (சிதம்பரம் கரணங்கள்)

---

## 1. Visual Dance Codification
Each niche depicts a female dancer frozen in dynamic motion executing a *Karana*:
- Sculpted alongside two musicians (a drummer playing the *Maddalam* and a singer striking *Cymbals*).
- Below each relief, an inscription records the exact verse definition from the *Natya Shastra*, preserving exact 12th-century choreographic conventions.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-adavu-and-karana-biomechanics-metrology",
        "file": "concept-adavu-and-karana-biomechanics-metrology.md",
        "node_type": "concept",
        "name_en": "Adavu & Karana Biomechanics: 108 Movement Units & Gravitational Stances",
        "name_ta": "அடவு மற்றும் கரண உடலியங்கியல் - 108 நடன அலகுகள் மற்றும் ஈர்ப்பு சமநிலை",
        "era": "Classical to Medieval Era",
        "year_start": 400,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The physiological biomechanics and kinetic vocabulary of Tamil dance: the coordination of foot strikes (Tattu), leg extensions (Kuthu), body bends (Bhanga), hand mudras (Hastha), and spinal alignments composing the 108 Karanas and basic Adavu steps.",
        "summary_ta": "தமிழர் நாட்டியத்தின் அடிப்படை உடலியக்கவியல். தட்டு, குத்து, தை தை தாம் போன்ற அடவு வரிசைகள், பாத நிலைகள் (மண்டல ஸ்தானம்), உடல் வளைவுகள் (திரிபங்கம்) மற்றும் 108 கரணங்களை இணைக்கும் ஈர்ப்பு மையக் கட்டுப்பாடுகள்.",
        "content": """# Adavu & Karana Biomechanics (அடவு - கரணக் கோட்பாடு)

---

## 1. The Core Triad
A *Karana* is formed by the simultaneous coordination of three distinct kinetic components:
1. **Sthana (*ஸ்தானம்*)**: Static posture of the torso and center of mass (*Aramandi / Ardhamandala*).
2. **Nrtta Hastha (*நிருத்த ஹஸ்தம்*)**: Geometric hand and arm gestures (*Pataka*, *Tripataka*).
3. **Chari (*சாரி*)**: Coordinated leg movement, leaps, glides, and floor sweeps.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-chola-tala-metrology-and-solkattu-rhythms",
        "file": "concept-chola-tala-metrology-and-solkattu-rhythms.md",
        "node_type": "concept",
        "name_en": "Chola Tala Metrology: Solkattu Syllables, Akshara Fractions & Laya Rhythms",
        "name_ta": "சோழர் காலத் தாள இயல் - சொற்கட்டு, அட்சரக் கணக்குகள் மற்றும் லய நுட்பங்கள்",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 800,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The sophisticated mathematical system of rhythm governing Tamil temple music and dance: Solkattu rhythmic mnemonic syllables (Ta-Dhi-Tom-Nam), fractional sub-divisions (Jatis: Tisra, Chatusra, Khanda, Misra, Sankirna), and Kudamuzha five-faced drum polyrhythms.",
        "summary_ta": "நாட்டியத்தின் தாளக் கட்டமைப்பு. சொற்கட்டுகளின் கணிதக் கணக்கீடுகள், 5 வகை ஜாதிகள் (திஸ்ரம், சதுஸ்ரம், கண்டம், மிஸ்ரம், சங்கீர்ணம்), மற்றும் ஐந்து முகக் குடமுழா வாத்தியத்தில் எழுப்பப்பட்ட பல்தாள (Polyrhythm) லய முறைமைகள்.",
        "content": """# Chola Tala Metrology (தாளவியல் கணிதம்)

---

## 1. Fractional Time Division (*அட்சரக் கால அளவு*)
- **Matra (*மாத்திரை*)**: Base duration unit.
- **Gati / Jati Subdivisions**:
  - *Chatusra* (4 pulses/beat): Standard walking pulse (*Tha-Ka-Dhi-Mi*).
  - *Tisra* (3 pulses/beat): Swirling triplet pulse (*Tha-Ki-Ta*).
  - *Misra* (7 pulses/beat): Mixed syncopation (*Tha-Ki-Ta Tha-Ka-Dhi-Mi*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-arangam-theatrical-stage-architecture",
        "file": "concept-arangam-theatrical-stage-architecture.md",
        "node_type": "concept",
        "name_en": "Arangam Stage Architecture: Silappadikaram Proscenium Dimensions & Screen Engineering",
        "name_ta": "அரங்கம் மேடைக் கட்டிடக்கலை - சிலப்பதிகார எண்-கோல் மேடை மற்றும் திரைச்சீலை நுட்பங்கள்",
        "era": "Sangam to Classical Era",
        "year_start": 200,
        "year_end": 700,
        "thinai": "Marutham",
        "summary_en": "The physical architectural specifications of the ancient Tamil proscenium theater recorded in Silappadikaram: constructed using a bamboo rod of 24 spans (En-kol), featuring 4-cubit stage elevation, acoustic plank flooring, and three specialized painted silk screens (Thirai).",
        "summary_ta": "சிலப்பதிகாரத்தில் விவரிக்கப்படும் தொல் தமிழர் நாட்டிய மேடை அமைப்பு. 24 சாண் நீள மூங்கில் கொண்டு அளக்கப்பட்ட 8 கோல் அகலம், 7 கோல் நீளம் கொண்ட 'எண்கோல் மேடை'. ஒருமுக எழினி, பொருமுக எழினி, கரந்துவரல் எழினி ஆகிய முத்திறை நுட்பங்கள்.",
        "content": """# Arangam Stage Architecture (நாட்டிய அரங்கம்)

---

## 1. Metric Proportions (*எண்கோல் மேடை*)
- **Length**: 8 standard staff units (*கோல்*).
- **Width**: 7 staff units.
- **Height**: 4 cubits (*முழம்*) above floor level to ensure unhindered sightlines for the monarch and citizenry.

## 2. Mechanical Silk Curtain Systems (*எழினி*)
1. **Oru-muga Ezhini (*ஒருமுக எழினி*)**: Single large curtain drawing horizontally from one side to the other.
2. **Poru-muga Ezhini (*பொருமுக எழினி*)**: Double curtains parting simultaneously from the center to both wings.
3. **Karanthu-varal Ezhini (*கரந்துவரல் எழினி*)**: Drop curtain descending silently from ceiling beams to conceal scenic transitions.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-talicceri-dance-quarters-and-paddy-endowments",
        "file": "concept-talicceri-dance-quarters-and-paddy-endowments.md",
        "node_type": "concept",
        "name_en": "Talicceri Quarters: Residential Agrarian Endowments (Kani) for Imperial Dancers",
        "name_ta": "தளிச்சேரி - நாட்டியக் கலைஞர்களுக்கான குடியிருப்புகள் மற்றும் நெல் மானிய முறை",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "The urban and agrarian institutional system supporting performing arts under the Cholas: dedicated residential quarters (Talicceri) constructed adjacent to royal temples, supported by hereditary agrarian rights (Kani-udaimai) ensuring state patronage of music and dance.",
        "summary_ta": "சோழப் பேரரசு நாட்டியக் கலைஞர்களை கௌரவித்து உருவாக்கிய நகரக் குடியிருப்பு அமைப்பு. பெரிய கோயில்களைச் சுற்றி அமைக்கப்பட்ட நான்கு தளிச்சேரித் தெருக்கள் மற்றும் கலைஞர்களின் குடும்பங்களுக்குப் பரம்பரையாக வழங்கப்பட்ட காணி நில மானியங்கள்.",
        "content": """# Talicceri Urban Patronage System (தளிச்சேரி அமைப்பு)

---

## 1. Professional Guild Status
Dancers held prestigious status (*Nakkan* / *Devi*), enjoying autonomous guild councils, ownership of private properties, and authority to endow bronze lamps and golden ornaments to temple sanctums.
"""
    },
    {
        "category": "characters",
        "slug": "char-madhavi-classical-natya-virtuoso",
        "file": "char-madhavi-classical-natya-virtuoso.md",
        "node_type": "character",
        "name_en": "Madhavi: Silappadikaram Classical Natya Virtuoso & Master of Seven Tala Systems",
        "name_ta": "மாதவி - சிலப்பதிகார நாட்டியப் பேரரசி மற்றும் ஏழு வகை தாள வித்தகர்",
        "era": "Sangam Post-Classical Era",
        "year_start": 150,
        "year_end": 250,
        "thinai": "Marutham",
        "summary_en": "The celebrated heroine of Silappadikaram whose seven years of rigorous training culminated in her peerless arangetram before Chola King Karikala, mastering the 11 divine dances, 22 srutis of the yazh, and subtle abhinaya.",
        "summary_ta": "சிலப்பதிகாரத்தின் முதன்மைக் கதாநாயகிகளுள் ஒருவரான மாதவி. தனது ஐந்தாம் வயது முதல் பன்னிரண்டாம் வயது வரை ஏழாண்டுகள் நடனம், பாடல், யாழ் மற்றும் தாளங்களை முழுமையாகக் கற்றுத் தேர்ந்து, சோழ மன்னன் முன்னிலையில் அரங்கேற்றம் செய்து 'தலைக்கோலரிசி' பட்டம் பெற்ற நாட்டிய மேதை.",
        "content": """# Madhavi: The Supreme Natya Virtuoso (நாட்டிய மாதவி)

---

## 1. Comprehensive Artistic Training
Trained under four specialized masters:
- **Aadal Asiriyan (*ஆடல் ஆசான்*)**: Dance master knowing both indigenous Tamil (*Vethiyal*) and pan-Indian (*Podhuviyal*) dance forms.
- **Isai Asiriyan (*இசை ஆசான்*)**: Master vocalist.
- **Kavi Asiriyan (*கவிஞன்*)**: Lyricist and metrical poet.
- **Thanneerum Yazh Asiriyan (*யாழ் ஆசான்*)**: Master harpist.
"""
    },
    {
        "category": "characters",
        "slug": "char-thanjavur-tala-asiriyar-rhythm-director",
        "file": "char-thanjavur-tala-asiriyar-rhythm-director.md",
        "node_type": "character",
        "name_en": "Thanjavur Tala Asiriyar: Imperial Dance Conductor, Nattuvanar & Solkattu Master",
        "name_ta": "தஞ்சைத் தாள ஆசான் - நட்டுவனார் மற்றும் அரச நாட்டிய நெறியாளர்",
        "era": "Imperial Chola Era",
        "year_start": 1000,
        "year_end": 1060,
        "thinai": "Marutham",
        "summary_en": "Imperial dance director and master conductor (*Nattuvanar*) recorded in Thanjavur inscriptions, wielding the bronze cymbals (*Nattuvangam*) to synchronize 400 temple dancers, percussionists, and sacred choir vocalists.",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயிலில் 400 நடனக் கலைஞர்களை ஒரே லயத்தில் இயக்கிய தலைமை நட்டுவனார். வெண்கல தாளக் கிண்ணங்கள் ஏந்தி சொற்கட்டுகளை முழங்கி, வழிபாட்டு நடனங்களை நெறிப்படுத்திய அரச ஆசான்.",
        "content": """# The Imperial Nattuvanar (தாள ஆசான்)

Responsible for composing intricate rhythmic crescendos (*Theermanam*) and auditioning all candidate artists seeking admission into the royal Talicceri guild.
"""
    },
    {
        "category": "places",
        "slug": "place-thanjavur-talicceri-peruntheru-quarters",
        "file": "place-thanjavur-talicceri-peruntheru-quarters.md",
        "node_type": "place",
        "name_en": "Thanjavur Talicceri Peruntheru: The Four Quarters of the Imperial Royal Dancers",
        "name_ta": "தஞ்சைத் தளிச்சேரிப் பெருந்தெரு - 400 நடன மாதர்கள் வாழ்ந்த அரச குடியிருப்பு வீதிகள்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The historic residential boulevard constructed by Rajaraja I flanking the northern and southern moats of Brihadisvara Temple, housing 400 endowed artists, musicians, percussionists, and stage architects.",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயிலைச் சுற்றி அமைக்கப்பட்ட வரலாற்றுப் பெருந்தெரு. அரண்மனை ஆதரவு பெற்ற 400 நடனக் கலைஞர்கள், பாடகர்கள் மற்றும் பக்கவாத்தியக் கலைஞர்கள் வரிசையாக இல்லங்கள் அமைத்து வாழ்ந்த பண்பாட்டு மையம்.",
        "content": """# Thanjavur Talicceri Peruntheru (தளிச்சேரிப் பெருந்தெரு)

- **Coordinates**: 10.7870° N, 79.1378° E.  
- **District**: Thanjavur City, Tamil Nadu.  
- **Significance**: The most densely documented cultural and theatrical artist district in ancient Asian epigraphy.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: OVERSEAS MARITIME EXPEDITIONS, KADARAM & SONG DIPLOMACY
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-song-shi-chola-diplomatic-annals",
        "file": "text-song-shi-chola-diplomatic-annals.md",
        "node_type": "text",
        "name_en": "Song Shi (Song Dynasty Official History): Imperial Chola Embassies of 1015 & 1077 CE",
        "name_ta": "சோங் ஷி (சீன அரச வரலாற்று ஆவணம்) - சோழப் பேரரசின் கி.பி. 1015 மற்றும் 1077 தூதுக்குழு பதிவுகள்",
        "era": "Imperial Chola to Song Dynasty Era",
        "year_start": 1015,
        "year_end": 1080,
        "thinai": "Neithal",
        "summary_en": "The official imperial annals of China's Song Dynasty (*Song Shi*, Fascicle 489, Liezhuan) recording high-level diplomatic and tributary trade embassies sent by Chola emperors Rajaraja I (Lo-ts'a-lo-ts'a) in 1015 CE and Kulottunga I (Ti-hua-kia-lo) in 1077 CE, bringing 227,000 strings of copper coins, pearls, and frankincense.",
        "summary_ta": "சீனாவின் சோங் வம்சத்தின் அதிகாரப்பூர்வ வரலாற்றுப் பதிவான சோங் ஷி. முதலாம் இராஜராஜ சோழன் (கி.பி. 1015) மற்றும் முதலாம் குலோத்துங்க சோழன் (கி.பி. 1077) கைஃபெங் நகரத்து சீன பேரரசரின் அவைக்கு அனுப்பிய தூதுக்குழுக்கள், முத்துக்கள், நறுமணப் பொருட்கள் மற்றும் 227,000 செப்பு நாணய மாலைகள் வர்த்தகப் பரிமாற்ற ஆவணங்கள்.",
        "content": """# The Song Shi Chola Annals (சோங் ஷி சீன ஆவணங்கள்)

**Source**: *Song Shi* (*宋史* - History of the Song), Chapter 489.  
**Subject**: Embassies from *Zhu-lian* (*注輦* - The Chola Empire) to the Song Court in Kaifeng (*開封*).  

---

## 1. The 1015 CE Embassy of Rajaraja I
Led by chief ambassador Soli Samudra (*Shou-li San-wen*):
- Traversed the Bay of Bengal, anchored in Srivijaya, waited for the northeast monsoon, and landed at Guangzhou after 1,150 days.
- Presented gifts of 21,000 ounces of frankincense, 87 large pearls, elephant tusks, and medicinal aromatics.

## 2. The 1077 CE Embassy of Kulottunga I
The 72-member envoy arrived carrying immense treasure:
- The Chinese Emperor Shenzong bestowed 81,800 strings of copper cash and 52,000 taels of silver in return, confirming the Cholas as the preeminent superpower of the maritime silk route.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-tiruvalangadu-kadaram-conquest-charters",
        "file": "insc-tiruvalangadu-kadaram-conquest-charters.md",
        "node_type": "inscription",
        "name_en": "Tiruvalangadu Copper Plates & Thanjavur Epigraphs: Rajendra I's 1025 CE Kadaram Armada Campaign",
        "name_ta": "திருவாலங்காட்டுச் செப்பேடுகள் மற்றும் தஞ்சைக் கல்வெட்டு - கி.பி. 1025 கடாரப் போர்ப் பிரசஸ்தி",
        "era": "Imperial Chola Era",
        "year_start": 1025,
        "year_end": 1030,
        "thinai": "Neithal",
        "summary_en": "The triumphant inscriptional Meykkirthi of Rajendra Chola I recording his unprecedented trans-oceanic armada assault across Southeast Asia in 1025 CE: capturing King Sangrama Vijayottungavarman, seizing the jewel-encrusted Vidyadhara Torana gateway, and subduing 14 maritime city-states across Sumatra and Malaya.",
        "summary_ta": "முதலாம் இராஜேந்திர சோழனின் கடாரப் படையெடுப்பை விளக்கும் உலகப் புகழ்பெற்ற மெய்க்கீர்த்தி. 'அலைகடல் நடுவுள் பலகலம் செலுத்தி...' எனத் தொடங்கும் பாடல். ஸ்ரீவிஜய மன்னன் சங்கிராம விஜயோத்துங்கவர்மனை சிறைபிடித்து, ரத்தினங்கள் பதித்த வித்யாதரத் தோரணத்தைக் கைப்பற்றி, மலாயா மற்றும் சுமாத்திராவின் 14 துறைமுக நகரங்களை வென்ற வரலாற்றுச் சாசனம்.",
        "content": """# Rajendra Chola's 1025 CE Armada Campaign (கடாரப் படையெடுப்பு)

---

## 1. The Monumental Maritime Meykkirthi
The epigraph lists the conquered maritime kingdoms in strategic navigation order:
1. **Sri Vijaya (*ஸ்ரீவிஜயம்*)**: Palembang, southern Sumatra.
2. **Pannai (*பண்ணை*)**: North Sumatra eastern coastline.
3. **Malaiyur (*மலையூர்*)**: Jambi on the Batang Hari River, fortified mountain kingdom.
4. **Mayirudingam (*மாயிருடிங்கம்*)**: Central Malay Peninsula protected by deep moats.
5. **Ilangasogam (*இலங்காசோகம்*)**: Langkasuka / Patani on the eastern peninsula.
6. **Mappappalam (*மாப்பப்பாளம்*)**: Pegu / Lower Burma riverine delta.
7. **Mevilimbangam (*மேவிலிம்பங்கம்*)**: Southern Malay fortress.
8. **Valaippanduru (*வளைப்பந்தூரு*)**: Champa coast or southern Vietnam.
9. **Talaittakkolam (*தலைத்தக்கோலம்*)**: Takua Pa on the Kra Isthmus.
10. **Madamalingam (*மாதமாலிங்கம்*)**: Tambralinga / Ligor.
11. **Ilamuridesam (*இலாமுரிதேசம்*)**: Lamuri, northern tip of Sumatra (Aceh).
12. **Manakkavaram (*மாநக்கவாரம்*)**: Nicobar Islands deep-water anchorage.
13. **Kadaram (*கடாரம்*)**: Bujang Valley / Kedah, capital citadel.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-nagapattinam-chudamani-vihara-charters",
        "file": "insc-nagapattinam-chudamani-vihara-charters.md",
        "node_type": "inscription",
        "name_en": "Nagapattinam Chudamani Vihara Charters: Srivijayan King Sri Mara Vijayottungavarman's Grant",
        "name_ta": "நாகப்பட்டினம் சூடாமணி விகாரச் சாசனம் - ஸ்ரீவிஜய மன்னனின் பௌத்த அறக்கட்டளை",
        "era": "Imperial Chola Era",
        "year_start": 1006,
        "year_end": 1015,
        "thinai": "Neithal",
        "summary_en": "The famous larger Leiden copper plates recording Rajaraja I's endowment of Anaimangalam village revenues to maintain the magnificent Buddhist Chudamani Vihara constructed at the international port of Nagapattinam by Sailendra Emperor Sri Mara Vijayottungavarman of Srivijaya.",
        "summary_ta": "பெரிய லைடன் செப்பேடுகள் என்று அழைக்கப்படும் வரலாற்றுச் சாசனம். ஸ்ரீவிஜயப் பேரரசன் ஸ்ரீ மாற விஜயோத்துங்கவர்மன் நாகப்பட்டினத் துறைமுகத்தில் கட்டிய பௌத்த சூடாமணி விகாரத்திற்கு, முதலாம் இராஜராஜ சோழன் ஆனைமங்கலம் கிராமத்தின் முழு நிலவரியையும் கொடையாக வழங்கிய சர்வதேச நல்லுறவு ஆவணம்.",
        "content": """# Chudamani Vihara Diplomatic Charters (சூடாமணி விகாரம்)

---

## 1. International Maritime Diplomacy
- King Rajaraja I and his successor Rajendra I actively supported the Sailendra dynasty's Mahayana Buddhist sanctuary at Nagapattinam, ensuring safe harbor, tax exemption, and spiritual solace for overseas merchants arriving from Java, Sumatra, and China.
- Demonstrates the extraordinary cosmopolitan tolerance of the Chola empire prior to the geopolitical rupture of 1025 CE.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-chola-armada-trans-oceanic-naval-tactics",
        "file": "concept-chola-armada-trans-oceanic-naval-tactics.md",
        "node_type": "concept",
        "name_en": "Chola Armada Naval Tactics: Monsoon Navigation, Flotilla Formations & Malacca Amphibious Assaults",
        "name_ta": "சோழர் கடற்படைப் போர்த் தந்திரங்கள் - பருவக்காற்றுப் பயணம், அணிவகுப்பு மற்றும் மலாக்கா நீர்சந்தி தாக்குதல்",
        "era": "Imperial Chola Era",
        "year_start": 1020,
        "year_end": 1080,
        "thinai": "Neithal",
        "summary_en": "The military naval doctrine of Rajendra I's blue-water battlefleet: synchronizing departures with the late Southwest Monsoon, dual-prong fleet envelopment through the Malacca and Sunda straits, boarding actions with grapnels, and combined naval-infantry amphibious beachheads.",
        "summary_ta": "சோழர் பெருங்கடற்படையின் போர் உத்திகள். தென்மேற்குப் பருவக்காற்றைப் பயன்படுத்தி ஒரே நேரத்தில் நூற்றுக்கணக்கான பெருங்கப்பல்களைச் செலுத்துதல், மலாக்கா மற்றும் சுண்டா நீர்சந்திகளை இருமுனைத் தாக்குதலால் அடைத்தல், மற்றும் ஆற்று முகத்துவாரங்களில் இறங்கி நகரங்களை முற்றுகையிட்ட நில-நீர் கூட்டுப் போர்முறை.",
        "content": """# Chola Armada Naval Doctrine (சோழர் கடற்படை உத்திகள்)

---

## 1. Dual-Pincer Strategic Envelopment
To conquer Srivijaya's maritime monopoly without getting trapped:
- **Flotilla A**: Traversed the Strait of Malacca, striking Kedah (*Kadaram*) and Takua Pa to decapitate northern defenses.
- **Flotilla B**: Circumnavigated western Sumatra to enter through the Sunda Strait, launching surprise assaults on Palembang (*Sri Vijaya*) and Jambi (*Malaiyur*).

## 2. Shipboard Weaponry
- Multi-deck battleships (*Kappal*) equipped with raised wooden ramparts for archers firing incendiary pitch arrows.
- Iron boarding grapnels (*இரும்புக் கொக்கிகள்*) and catapult-launched Greek-fire-type combustible resins.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-srivijaya-maritime-chokepoint-toll-geopolitics",
        "file": "concept-srivijaya-maritime-chokepoint-toll-geopolitics.md",
        "node_type": "concept",
        "name_en": "Srivijayan Malacca Chokepoints: Kedah (Kadaram), Sunda Strait & Toll Geopolitics",
        "name_ta": "ஸ்ரீவிஜய மலாக்கா நீர்சந்தி ஆதிக்கம் - கடாரம், சுண்டா மற்றும் கப்பல் சுங்க வரி பூகோள அரசியல்",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 700,
        "year_end": 1100,
        "thinai": "Neithal",
        "summary_en": "The geopolitical crisis triggering the 1025 CE naval war: the Thalassocracy of Srivijaya exploiting its control of the Malacca and Sunda straits to impose extortionate transit tolls and pirate boarding raids on Tamil merchant convoys (Ayyavole, Manigramam) bound for Song China.",
        "summary_ta": "கி.பி. 1025 போருக்கு வித்திட்ட புவிசார் அரசியல் சூழல். மலாக்கா மற்றும் சுண்டா நீர்சந்திகளைத் தனது முழுக் கட்டுப்பாட்டில் வைத்திருந்த ஸ்ரீவிஜய அரசு, சீனாவுக்குச் சென்ற தமிழ் வணிகக் கப்பல்களின் மீது தாங்கொணா சுங்க வரிகளை விதித்து, வழிமறித்து கொள்ளையடித்ததால் ஏற்பட்ட பெரும் மோதல்.",
        "content": """# The Malacca Chokepoint Conflict (நீர்சந்தி சுங்க வரி மோதல்)

---

## 1. The Strategic Bottleneck
Every merchant vessel traveling between India and China was forced through the narrow funnel of the Malacca Strait:
- Srivijaya established fortified naval stations at Kedah (*Kadaram*) and Palembang.
- Passing ships were coerced by naval squadrons (*Orang Laut*) to dock and pay heavy ad valorem transit dues.
- Rajendra Chola's armada shattered this toll barrier, restoring free navigation for global Indian Ocean commerce for over two centuries.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-chola-song-tribute-diplomacy-and-bullion-flow",
        "file": "concept-chola-song-tribute-diplomacy-and-bullion-flow.md",
        "node_type": "concept",
        "name_en": "Chola-Song Tribute Trade Diplomacy: Pearls, Aromatics, Cloves & Chinese Silver Ingot Flow",
        "name_ta": "சோழ-சீனப் பேரரசு வர்த்தகத் தூது - முத்து, நறுமணப் பொருட்கள் மற்றும் வெள்ளிப் பரிமாற்றம்",
        "era": "Imperial Chola to Song Era",
        "year_start": 1000,
        "year_end": 1150,
        "thinai": "Neithal",
        "summary_en": "The lucrative macro-economic axis between the Chola Empire and the Song Dynasty: exchanging Gulf of Mannar pearls, frankincense, Arabian horses, and Moluccan cloves for hundreds of thousands of strings of Chinese copper cash, silver ingots, raw silks, and green celadon ceramics.",
        "summary_ta": "சோழப் பேரரசுக்கும் சீன சோங் வம்சத்திற்கும் இடையே நடைபெற்ற வரலாற்றுச் சிறப்புமிக்க பெருவணிகப் பரிமாற்றம். கொற்கை முத்துக்கள், மூலிகைகள் மற்றும் நறுமணப் பண்டங்களுக்கு ஈடாக, லட்சக்கணக்கான சீன செப்பு நாணய மாலைகள், வெள்ளிப் பாளங்கள், பட்டு மற்றும் பீங்கான் பாண்டங்கள் தமிழகத்திற்குப் பெருமளவில் வந்தடைந்த விதம்.",
        "content": """# Chola-Song Macro-Economic Diplomacy (சோழ-சீன வர்த்தகம்)

---

## 1. The Tributary Trade Mechanism
Under the guise of ceremonial tribute (*Chao-gong*), Chola merchants conducted massive duty-free bulk trade with the Chinese imperial court:
- Chinese courts issued state bullion to purchase entire ship cargoes immediately upon arrival at Guangzhou (*Canton*) and Quanzhou.
- Hundreds of Chinese Song coins and celadon ceramic shards unearthed across Thanjavur, Gangaikonda Cholapuram, and Nagapattinam confirm the sheer scale of this trans-oceanic flow.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-chudamani-vihara-buddhist-diplomatic-complex",
        "file": "concept-chudamani-vihara-buddhist-diplomatic-complex.md",
        "node_type": "concept",
        "name_en": "Chudamani Vihara: The Nagapattinam Diplomatic Enclave & Maritime Mahayana Sanctuary",
        "name_ta": "சூடாமணி விகாரம் - நாகப்பட்டினத்து சர்வதேச பௌத்த தூதரக வளாகம்",
        "era": "Imperial Chola Era",
        "year_start": 1006,
        "year_end": 1300,
        "thinai": "Neithal",
        "summary_en": "The towering brick and stone multi-story Buddhist monastic complex at Nagapattinam (known as Pudhuveli Gopuram / China Pagoda), serving as an extraterritorial sanctuary, international maritime hospital, and diplomatic trading consulate for Southeast Asian and Chinese merchants.",
        "summary_ta": "நாகப்பட்டினத்தில் கடலோரமாக எழுந்து நின்ற பிரம்மாண்ட பௌத்த விகாரம் ('சீனக் கோயில்' / புதுவெளி கோபுரம்). ஸ்ரீவிஜய மன்னர்களால் கட்டப்பட்டு, சோழ மன்னர்களால் ஆதரிக்கப்பட்ட இவ்வளாகம் வெளிநாட்டு வணிகர்களுக்கான தூதரகமாகவும், மருத்துவமனையாகவும், ஆன்மீக சரணாலயமாகவும் விளங்கியது.",
        "content": """# Chudamani Vihara Diplomatic Enclave (சூடாமணி விகாரம்)

---

## 1. Physical Architecture: The China Pagoda
- Stood as a monumental 3-tier brick pagoda visible miles out at sea, serving as a lighthouse beacon for vessels crossing the Palk Strait.
- Survived intact until 1867 when colonial engineers dismantled it, yielding over 350 exquisite inscribed Chola-style Buddhist bronzes now housed in the Chennai Government Museum.
"""
    },
    {
        "category": "characters",
        "slug": "char-chola-maritime-admiral-samudradhipati",
        "file": "char-chola-maritime-admiral-samudradhipati.md",
        "node_type": "character",
        "name_en": "Chola Maritime Admiral (Samudradhipati): Commander of the Eastern Armada",
        "name_ta": "சோழ கடற்படைத் தளபதி (சமுத்திராதிபதி) - கிழக்கு பெருங்கடல் கடற்படைப் பெருந்தலைவர்",
        "era": "Imperial Chola Era",
        "year_start": 1020,
        "year_end": 1050,
        "thinai": "Neithal",
        "summary_en": "High naval flag officer who directed the logistics, formation maneuvering, and coastal bombardment of Rajendra Chola's fleet during the multi-theater assault on Srivijaya and the Malay Peninsula in 1025 CE.",
        "summary_ta": "முதலாம் இராஜேந்திர சோழனின் கடற்படையை கடாரத்தை நோக்கி வழிநடத்தி, ஸ்ரீவிஜய தலைநகரை வளைத்து சங்கிராம விஜயோத்துங்கவர்மனை சிறைபிடித்த வரலாற்றுப் பெருந்தளபதி.",
        "content": """# The Chola Fleet Admiral (சமுத்திராதிபதி)

Master of monsoon timing, astro-navigation using the Kamaal quadrant, and coordinate signaling using colored silk battle-pennants across open ocean formations.
"""
    },
    {
        "category": "characters",
        "slug": "char-chola-ambassador-to-song-court",
        "file": "char-chola-ambassador-to-song-court.md",
        "node_type": "character",
        "name_en": "Chola Ambassador to Kaifeng: Chief Diplomat of the 1077 CE Song Embassy",
        "name_ta": "சீன அரசவைக்குச் சென்ற சோழத் தூதர் - கி.பி. 1077 கைஃபெங் நகரத்து தலைமை ராஜதந்திரி",
        "era": "Imperial Chola to Song Era",
        "year_start": 1070,
        "year_end": 1090,
        "thinai": "Neithal",
        "summary_en": "Eminent diplomat and merchant grandee who led Kulottunga Chola I's 72-member envoy to the Northern Song capital of Kaifeng, negotiating preferential tariff treaties and presenting astronomical instruments.",
        "summary_ta": "முதலாம் குலோத்துங்க சோழனின் சார்பாக 72 உறுப்பினர்கள் கொண்ட குழுவோடு சீன தலைநகர் கைஃபெங் சென்று, பேரரசர் ஷென்சாங்கை நேரில் சந்தித்து வர்த்தக ஒப்பந்தங்களை மேற்கொண்ட தலைமைத் தூதர்.",
        "content": """# The Imperial Ambassador to Song China (சீனத் தூதர்)

Honored in Chinese court records with the prestigious title of *Grand General of the Imperial Guards* and awarded golden court robes.
"""
    },
    {
        "category": "places",
        "slug": "place-malaiyur-jambi-sumatra-anchorage",
        "file": "place-malaiyur-jambi-sumatra-anchorage.md",
        "node_type": "place",
        "name_en": "Malaiyur (Jambi, Sumatra): Batang Hari River Naval Citadel Conquered by Rajendra I",
        "name_ta": "மலையூர் (ஜாம்பி, சுமாத்திரா) - இராஜேந்திர சோழனால் வெல்லப்பட்ட படாங் ஹரி ஆற்றுத் துறைமுகம்",
        "era": "Imperial Chola Era",
        "year_start": 1025,
        "year_end": 1250,
        "thinai": "Neithal",
        "summary_en": "Ancient fortified riverine kingdom and gold-trading center on the Batang Hari River in central Sumatra (Melayu / Jambi), celebrated in the Thanjavur inscriptions as 'மலையூர் தீயுரண் கடந்த...' for its formidable water and mountain ramparts conquered by the Chola armada in 1025 CE.",
        "summary_ta": "மத்திய சுமாத்திராவின் படாங் ஹரி ஆற்றுப் படுகையில் அமைந்திருந்த பழம்பெரும் மலையூர் அரசு (தற்கால ஜாம்பி). தங்கம், கற்பூரம் விளையும் வளமிக்க மையமாகவும், இராஜேந்திர சோழனின் கடற்படையால் கி.பி. 1025-இல் வீழ்த்தப்பட்ட வரலாற்றுப் புகழ்மிக்க கோட்டையாகவும் விளங்கிய தளம்.",
        "content": """# Malaiyur Naval Citadel (மலையூர்)

- **Coordinates**: -1.5900° S, 103.6100° E.  
- **River**: Batang Hari River, Sumatra, Indonesia.  
- **Epigraphical Glory**: Inscribed in the Brihadisvara Meykkirthi: *"மலையூர் தீயுரண் கடந்த வண்புகழ் மலையூர்"* (Conquering Malaiyur protected by fierce mountain ramparts).
"""
    }
]

# ==============================================================================
# RELATIONAL EDGES (30 Total)
# ==============================================================================
EDGES = [
    # Corpus 1 Edges: Temple Architecture & Agamic Vastu
    ("text-mayamata-silparatna-tamil-agamic-vastu", "codifies", "concept-agamic-vastu-mandala-temple-metrology", "sacred_geometry", "Early Medieval", "Treatise formulates the 64- and 81-square Padavinyasa Vastu Mandalas.", "Mayamata chapter 7"),
    ("text-mayamata-silparatna-tamil-agamic-vastu", "guides", "char-kunjaramallan-rajaraja-perunthatchan-architect", "architecture", "Imperial Chola", "Chief architect applied canonical Agamic ratios to the Brihadisvara vimana.", "Brihadisvara inscriptions"),
    ("insc-thanjavur-peruvudaiyar-architect-charter", "commemorates", "char-kunjaramallan-rajaraja-perunthatchan-architect", "royal_patronage", "1010 CE", "Rajaraja I incised the architect's name and title on the southern basement.", "Thanjavur south wall"),
    ("insc-thanjavur-peruvudaiyar-architect-charter", "exemplifies", "concept-interlocking-dry-masonry-and-corbelled-vaulting", "construction", "1010 CE", "Documents the mortar-free granite construction of the 216-foot vimana.", "Archaeological Survey"),
    ("concept-kudamuzha-and-sikhara-monolith-hoisting-ramps", "utilized_by", "char-kunjaramallan-rajaraja-perunthatchan-architect", "engineering", "1010 CE", "Chief architect engineered the 6-km inclined earthen ramp from Sarappallam.", "Oral and epigraphic record"),
    ("concept-granite-quarrying-and-kaveri-barge-transport", "managed_by", "char-ammangudi-granite-quarry-master", "resource_extraction", "Imperial Chola", "Quarry masters cleaved charnockite blocks using wood swelling wedges.", "Geological surveys"),
    ("concept-granite-quarrying-and-kaveri-barge-transport", "originates_at", "place-ammangudi-chola-granite-quarries", "geography", "Imperial Chola", "Granite megaliths were quarried and loaded onto barges along the Kaveri.", "Epigraphia Indica"),
    ("insc-gangaikonda-cholapuram-foundation-charters", "evolves_from", "insc-thanjavur-peruvudaiyar-architect-charter", "architectural_evolution", "1025 CE", "Rajendra I evolved his father's rectilinear tower into a concave vimana.", "State archaeology"),
    ("concept-interlocking-dry-masonry-and-corbelled-vaulting", "implemented_at", "place-ammangudi-chola-granite-quarries", "masonry", "Imperial Chola", "Dressed granite blocks from Ammangudi were mortised without binding lime.", "Field analysis"),
    ("concept-agamic-vastu-mandala-temple-metrology", "applied_to", "insc-thanjavur-peruvudaiyar-architect-charter", "temple_planning", "1004 CE", "Sanku sun-shadows oriented Brihadisvara with zero compass error.", "Agama manuscripts"),

    # Corpus 2 Edges: Classical Dance & Koothu Traditions
    ("text-silappadikaram-arangetru-kadhai-dance-canon", "chronicles", "char-madhavi-classical-natya-virtuoso", "biography", "Sangam Post-Classical", "Documents Madhavi's seven years of artistic training and royal arangetram.", "Silappadikaram Canto 3"),
    ("text-silappadikaram-arangetru-kadhai-dance-canon", "defines", "concept-arangam-theatrical-stage-architecture", "theater_design", "Sangam Post-Classical", "Defines the 8-kol by 7-kol proscenium stage and triple silk curtains.", "Arangetru Kadhai verses"),
    ("insc-thanjavur-talicceri-pendir-dance-charter", "settles_artists_at", "place-thanjavur-talicceri-peruntheru-quarters", "urban_patronage", "1014 CE", "Rajaraja I settled 400 master dancers in four dedicated grand avenues.", "Thanjavur north wall"),
    ("insc-thanjavur-talicceri-pendir-dance-charter", "endows", "concept-talicceri-dance-quarters-and-paddy-endowments", "agrarian_endowment", "1014 CE", "Each dancer received one Pangu yielding 100 kalams of paddy per year.", "Chola epigraphy"),
    ("char-thanjavur-tala-asiriyar-rhythm-director", "directs_dance_at", "place-thanjavur-talicceri-peruntheru-quarters", "direction", "Imperial Chola", "Conductor led rhythmic coordination across the 400 temple dancers.", "Temple records"),
    ("char-thanjavur-tala-asiriyar-rhythm-director", "masters", "concept-chola-tala-metrology-and-solkattu-rhythms", "musicology", "Imperial Chola", "Nattuvanars wielded bronze cymbals to conduct complex Matra and Jati cycles.", "Natya texts"),
    ("insc-chidambaram-natya-karana-sculptural-epigraphs", "visualizes", "concept-adavu-and-karana-biomechanics-metrology", "choreography", "Later Chola", "108 bas-reliefs depict exact kinetic movements labeled with verses.", "Chidambaram gopurams"),
    ("concept-adavu-and-karana-biomechanics-metrology", "performed_by", "char-madhavi-classical-natya-virtuoso", "performance", "Classical Era", "Madhavi mastered the 11 divine dances and complex Sthana-Chari units.", "Silappadikaram"),
    ("concept-chola-tala-metrology-and-solkattu-rhythms", "regulates", "concept-adavu-and-karana-biomechanics-metrology", "rhythm_and_motion", "Ancient-Medieval", "Tala subdivisions prescribe exact foot strikes and laya tempos for Karanas.", "Natya Shastra glosses"),
    ("concept-talicceri-dance-quarters-and-paddy-endowments", "documented_in", "insc-thanjavur-talicceri-pendir-dance-charter", "institutional_record", "1014 CE", " северная стена храма Брихадисвара фиксирует все земельные наделы.", "Epigraphia Indica"),

    # Corpus 3 Edges: Overseas Expeditions & Song Diplomacy
    ("text-song-shi-chola-diplomatic-annals", "records_embassy_from", "char-chola-ambassador-to-song-court", "diplomacy", "1077 CE", "Song annals chronicle Kulottunga I's 72-member embassy to Kaifeng.", "Song Shi fascicle 489"),
    ("text-song-shi-chola-diplomatic-annals", "documents_trade_in", "concept-chola-song-tribute-diplomacy-and-bullion-flow", "international_trade", "11th c. CE", "Chinese court exchanged silver ingots and copper coins for Chola pearls.", "Song Dynasty records"),
    ("insc-tiruvalangadu-kadaram-conquest-charters", "commemorates", "concept-chola-armada-trans-oceanic-naval-tactics", "naval_warfare", "1025 CE", "Meykkirthi celebrates the trans-oceanic armada defeating Srivijaya.", "Tiruvalangadu plates"),
    ("insc-tiruvalangadu-kadaram-conquest-charters", "records_fall_of", "place-malaiyur-jambi-sumatra-anchorage", "conquest", "1025 CE", "Epigraph lists Malaiyur on the Batang Hari river as subdued by the armada.", "Thanjavur Meykkirthi"),
    ("char-chola-maritime-admiral-samudradhipati", "commanded", "concept-chola-armada-trans-oceanic-naval-tactics", "naval_command", "1025 CE", "Naval admirals executed dual-prong envelopment through Malacca and Sunda.", "Naval histories"),
    ("concept-srivijaya-maritime-chokepoint-toll-geopolitics", "triggered", "insc-tiruvalangadu-kadaram-conquest-charters", "causation", "1025 CE", "Srivijayan extortionate transit tolls prompted Rajendra's punitive expedition.", "Maritime geopolitics"),
    ("insc-nagapattinam-chudamani-vihara-charters", "establishes", "concept-chudamani-vihara-buddhist-diplomatic-complex", "sanctuary", "1006 CE", "Leiden plates grant Anaimangalam village revenues to the Buddhist vihara.", "Leiden plates"),
    ("concept-chudamani-vihara-buddhist-diplomatic-complex", "sheltered_merchants_of", "place-malaiyur-jambi-sumatra-anchorage", "cosmopolitanism", "11th c. CE", "Vihara served as diplomatic haven for Srivijayan and Melayu mariners.", "Buddhist epigraphy"),
    ("char-chola-ambassador-to-song-court", "negotiated_for", "concept-srivijaya-maritime-chokepoint-toll-geopolitics", "treaties", "1077 CE", "Envoys guaranteed unhindered transit through the newly opened straits.", "Sino-Tamil treaties"),
    ("concept-chola-song-tribute-diplomacy-and-bullion-flow", "anchored_at", "place-malaiyur-jambi-sumatra-anchorage", "trade_route", "Medieval", "Sumatran riverine ports served as key victualing stations on route to China.", "Archaeological ceramics")
]

# ==============================================================================
# MAIN HARVESTER EXECUTION
# ==============================================================================
def main():
    print("=" * 70)
    print("🚀 BATCH 8: TRIPLE CIVILIZATIONAL EXPANSION HARVESTER")
    print("   1. Temple Architecture, Stone Quarrying & Agamic Vastu (10 dossiers)")
    print("   2. Classical Dance, Koothu Traditions & Natya Metrology (10 dossiers)")
    print("   3. Overseas Maritime Expeditions, Kadaram & Song Diplomacy (10 dossiers)")
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
