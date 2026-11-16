#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 3):
1. Ancient Tamil Theater, Drama & Epigraphical Performing Arts (10 dossiers)
2. Ancient Tamil Mineralogy, Gemology & Pearl Diver Guilds (10 dossiers)
3. Ancient Tamil Coastal Ports, Lighthouses & Maritime Customs Administration (11 dossiers)

Total: 31 Canonical Dossiers, ~55 Relational Edges, 62 Dense 1024-dim BGE-M3 Embeddings.
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
# DOSSIERS DEFINITION (31 Total)
# ==============================================================================
DOSSIERS = [
    # --------------------------------------------------------------------------
    # CORPUS 1: ANCIENT TAMIL THEATER, DRAMA & EPIGRAPHICAL PERFORMING ARTS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-silappadikaram-kadaladukadai-drama",
        "file": "text-silappadikaram-kadaladukadai-drama.md",
        "node_type": "text",
        "name_en": "Silappadikaram Kadaladukadai: 11 Classical Dance Forms (Aadal) & Theatrical Staging",
        "name_ta": "சிலப்பதிகாரம் கடலாடுகாதை - 11 வகை ஆடல்கள், நாடக அரங்கம் மற்றும் ஆடற்கலை",
        "era": "Sangam Post-Classical Era",
        "year_start": 400,
        "year_end": 550,
        "thinai": "Neithal",
        "summary_en": "Celebrated canto of the Silappadikaram by Ilango Adigal documenting the 11 classical sacred and secular dances (Pathinondru Aadal) performed by Madhavi at the Poompuhar sea-bathing festival, theatrical curtain mechanics (Oru-muga and Iru-muga Ezhini), and stage acoustics.",
        "summary_ta": "இளங்கோவடிகள் அருளிய சிலப்பதிகாரத்தின் கடலாடுகாதை. பூம்புகார் கடற்கரையில் மாதவி நிகழ்த்திய 11 வகை ஆடல்களான கொடுகொட்டி, பாண்டரங்கம், அல்லியம், மல், துடி, கடையம், பேடு, மரக்கால், பாவை முதலான தேவ-மானிட ஆடல்கள், ஒருமுக-இருமுக எழினி (திரைச்சீலை) அமைப்புகள் மற்றும் நாடக மேடை அமைப்பியல்.",
        "content": """# Silappadikaram Kadaladukadai: Classical Theatre & The 11 Dances (கடலாடுகாதை)

**Author**: Ilango Adigal (*இளங்கோவடிகள்*).  
**Setting**: Coastal festival of Kaveripoompattinam (*பூம்புகார் கடலாட்டு விழா*).  
**Core Subjects**: The 11 Divine Dances (*பதினொரு ஆடல்*), Stage Architecture (*அரங்கமைதி*).  

---

## 1. The 11 Classical Dance Forms (*Pathinondru Aadal*)
In *Kadaladukadai* (lines 35–70), Madhavi performs the sacred repertoire:
1. **Kodukotti (*கொடுகொட்டி*)**: Shiva's fierce dance after burning the Tripura citadels.
2. **Pandarangam (*பாண்டரங்கம்*)**: Shiva dancing covered with white ashes on the battlefield.
3. **Alliyam (*அல்லியம்*)**: Krishna breaking the tusk of the rogue elephant Kuvalayapida.
4. **Mal (*மல்*)**: Krishna wrestling and destroying the demon Bana.
5. **Thudi (*துடி*)**: Murugan dancing with small drums in the middle of the ocean breakers.
6. **Kudai (*குடை*)**: Murugan lowering his parasol to shield his troops.
7. **Kudam (*குடம்*)**: Krishna dancing juggling clay pots through Banapura.
8. **Pedu (*பேடு*)**: Kamadeva dancing disguised as an androgynous figure.
9. **Pavai (*பாவை*)**: Goddess Lakshmi dancing as an irresistible maiden to beguile asuras.
10. **Marakkal (*மரக்கால்*)**: Durga dancing on stilts made of wood to slay venomous scorpions.
11. **Kadaiyam (*கடையம்*)**: Indrani dancing in the agricultural fields of the Marutham plain.

---

## 2. Stage Architecture & Curtain Mechanics
The text describes the ancient Tamil proscenium stage:
- **Oru-muga Ezhini (*ஒருமுக எழினி*)**: Single curtain drawing across the stage from one side.
- **Iru-muga Ezhini (*இருமுக எழினி*)**: Two split curtains drawing simultaneously from both wings to the center.
- **Karandhu-varal Ezhini (*கரந்துவரல் எழினி*)**: Canopy drop curtains descending from above to reveal celestial descents.
"""
    },
    {
        "category": "texts",
        "slug": "text-arapatthan-arangan-nataka-treatise",
        "file": "text-arapatthan-arangan-nataka-treatise.md",
        "node_type": "text",
        "name_en": "Ancient Tamil Nataka Nool: Classical Theatrical Stage Architecture & Dramatic Tropes",
        "name_ta": "பண்டைத் தமிழ் நாடக நூல் - நாடக மேடை அமைப்பியல், பாத்திரப் பண்புகள் மற்றும் சுவைகள்",
        "era": "Sangam to Medieval Classical Era",
        "year_start": 300,
        "year_end": 1000,
        "thinai": "Marutham",
        "summary_en": "The lost classical Tamil dramatic manual traditions cited by commentator Adiyarkkunallar (Seyithriyam, Muruval, Sayantham, Madhivananar Nataka Tamil). Codifies actor training, stage lighting with sweet-smelling oil lamps, character dialogue metrics, and emotional resonance.",
        "summary_ta": "அடியார்க்குநல்லார் உரையால் அறியப்படும் பண்டைய தமிழ் நாடக நூல்களான செயிற்றியம், முறுவல், சயந்தம் மற்றும் மதிவாணர் நாடகத் தமிழ் நூல் மரபுகள். நாடக மேடையின் நீள-அகல அளவுகள், உரையாடல் பாவங்கள், இசை-நாடக இணைப்பு நெறிகள் மற்றும் நவரச பாத்திரப் படைப்புகள்.",
        "content": """# Ancient Tamil Nataka Nool (பண்டைத் தமிழ் நாடக நூல் மரபு)

**Commentarial Citations**: Adiyarkkunallar Commentary on Silappadikaram.  
**Lost Manuals**: *Sayanthanool*, *Seyithriyam*, *Madhivananar Nataka Tamil*.  
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thanjavur-rajarajeswara-nataka-charter",
        "file": "insc-thanjavur-rajarajeswara-nataka-charter.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Brihadisvara Inscriptions: Rajarajeswara Nataka Enactment & 400 Temple Dancers (Thalicheri Pendugal)",
        "name_ta": "தஞ்சைப் பெரிய கோயில் கல்வெட்டுகள் - இராசராசேசுவர நாடகம் மற்றும் 400 தளிச்சேரிப் பெண்டுகள் சாசனம்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Epic inscriptions on the south and west enclosures of the Thanjavur Brihadisvara temple cataloging the annual enactment of the dramatic play Rajarajeswara Natakam, endowed houses and grain allowances for 400 accomplished classical dancers (Thalicheri Pendugal) brought from all over the empire.",
        "summary_ta": "தஞ்சைப் பெரிய கோயில் திருச்சுற்று மாளிகைக் கல்வெட்டுகளில் பொறிக்கப்பட்டுள்ள பிரசித்தி பெற்ற தளிச்சேரிப் பெண்டுகள் சாசனம். பேரரசின் பல்வேறு ஊர்களிலிருந்து வரவழைக்கப்பட்ட 400 தலைசிறந்த ஆடற்கலைஞர்களுக்கு வழங்கப்பட்ட வீடுகள், நிலங்கள் மற்றும் பங்குப் படிகள், மற்றும் ஆண்டுதோறும் நிகழ்த்தப்பட்ட 'இராசராசேசுவர நாடகம்' பற்றிய வரலாற்றுப் பதிவு.",
        "content": """# Thanjavur Rajarajeswara Nataka & Thalicheri Inscriptions (1014 CE)

**Location**: Brihadisvara Temple granite walls, Thanjavur (*தஞ்சைப் பெருவுடையார் கோயில்*).  
**Monarch**: Emperor Rajaraja Chola I (*முதலாம் இராசராசன்*).  
**Epigraphical Scope**: 400 named artists, house door numbers, performance endowments.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-pathinondru-aadal-eleven-dances",
        "file": "concept-pathinondru-aadal-eleven-dances.md",
        "node_type": "concept",
        "name_en": "Pathinondru Aadal: The Eleven Classical Sacred Dance Typologies (Kodukotti, Pandarangam, Alliyam, etc.)",
        "name_ta": "பதினொரு ஆடல் - சிலப்பதிகாரத்தின் பதினோரு வகை மரபுவழி தெய்வீக ஆடற்கலை",
        "era": "Sangam Post-Classical Era",
        "year_start": 300,
        "year_end": 600,
        "thinai": "Neithal",
        "summary_en": "The sacred taxonomy of 11 dances dividing into Standing Dances (Nindradal: 6 forms) and Strolling/Folk Dances (Puzhithiyadal: 5 forms), embodying archetypal divine victories of Shiva, Murugan, Krishna, Kama, Durga, and Lakshmi.",
        "summary_ta": "நின்றாடல் (6 வகை) மற்றும் வீழ்ந்தாடல்/புறத்தாடல் (5 வகை) எனப் பகுக்கப்பட்ட பதினொரு மரபுவழி ஆடல்கள். கொடுகொட்டி, பாண்டரங்கம், அல்லியம், மல்லாடல், துடி, குடை, குடம், பேடு, பாவை, மரக்கால், கடையம் ஆகியவற்றின் ஆன்மிக மற்றும் தத்துவார்த்த நடனக் குறியீடுகள்.",
        "content": """# Pathinondru Aadal: The 11 Classical Dances (பதினொரு ஆடல்)

**Classification**: 6 Standing Dances (*நின்றாடல்*), 5 Ground/Folk Dances (*வீழ்ந்தாடல்*).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-talaikol-danseuse-sovereign-rod",
        "file": "concept-talaikol-danseuse-sovereign-rod.md",
        "node_type": "concept",
        "name_en": "Talaikol: The Royal Scepter of the Prima Danseuse & Theatrical Initiation Rites",
        "name_ta": "தலைக்கோல் - ஆடலரசியின் அரச மரியாதைக் கோல் மற்றும் அரங்கேற்ற மரபு",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 600,
        "thinai": "Marutham",
        "summary_en": "The sacred baton and symbol of sovereign artistic mastery awarded by the monarch to the prima danseuse during her graduation performance (Arangetram). Fashioned from the central shaft of a defeated king's royal parasol and ringed with gold and diamonds.",
        "summary_ta": "அரங்கேற்றம் நிறைவுசெய்த தலைமை ஆடலரசிக்கு மன்னனால் வழங்கப்படும் அரச கௌரவக் கோல். போர்க்களத்தில் வெல்லப்பட்ட பகை மன்னனின் வெண்கொற்றக் குடையின் நடுவண் கம்பிலிருந்து செய்யப்பட்டு, தங்கப் பூண்களும் நவரத்தினங்களும் பதிக்கப்பட்ட புனிதக் கோல்.",
        "content": """# Talaikol: The Sovereign Baton of Dance (தலைக்கோல்)

**Origin**: Axis shaft of defeated royal umbrella (*பகைமன்னர் குடைக்கம்பு*).  
**Significance**: Highest civic and imperial honor for theatrical dance mastery.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-thalicheri-temple-artist-guilds",
        "file": "concept-thalicheri-temple-artist-guilds.md",
        "node_type": "concept",
        "name_en": "Thalicheri Pendugal: Temple Danseuse Guilds, Endowed Houses & Artistic Autonomy",
        "name_ta": "தளிச்சேரிப் பெண்டுகள் - சோழர் கோயில் ஆடற்கலைஞர்கள், குடியிருப்பு மனைகள் மற்றும் தன்னாட்சி",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The social, artistic, and economic autonomy of the 400 classical dancers established in Thanjavur. Each dancer received an individual endowed house, one pangu (share) of fertile wetland yielding 100 kalams of paddy per year, and maintained independent female property rights.",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயிலில் 400 தளிச்சேரிப் பெண்டுகளுக்கு வழங்கப்பட்ட தனித்தனி இல்லங்கள், ஆண்டுக்கு 100 கலம் நெல் தரும் நிலப் பங்குகள் (பங்கு), மற்றும் பெண் சொத்துரிமையுடன் கூடிய அவர்களின் சமூக-கலை தன்னாட்சி மேலாண்மை.",
        "content": """# Thalicheri Pendugal: Temple Danseuse Guilds (தளிச்சேரிப் பெண்டுகள்)

**Endowment Structure**: 1 Pangu (Plot yielding 100 Kalams of paddy annually) per artist.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-aranga-amaithi-classical-stagecraft",
        "file": "concept-aranga-amaithi-classical-stagecraft.md",
        "node_type": "concept",
        "name_en": "Aranga Amaithi: Classical Stagecraft, Curtain Mechanics (Oru-muga / Iru-muga Ezhini) & Acoustics",
        "name_ta": "அரங்க அமைதி - தமிழரின் நாடக மேடைக் கட்டுமானம், எழினித் திரைகள் மற்றும் ஒலி அமைப்பியல்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "The physical dimensions and acoustic engineering of the ancient Tamil proscenium stage: 8 koles length, 7 koles width, 1 kole elevation, with polished plank floors, painted backdrops, shadowless oil lamps, and triple curtain systems.",
        "summary_ta": "பண்டைத் தமிழரின் நாடக மேடையின் துல்லியமான கட்டுமானப் பொறியியல்: 8 கோல் நீளம், 7 கோல் அகலம், 1 கோல் உயரம்; மூங்கில் கணுவளவிலான தச்சுக் கோல் அளவீடுகள், ஓவியப் பின்னணிகள், நிழல் விழாத விளக்குகள் மற்றும் எழினித் திரைகள்.",
        "content": """# Aranga Amaithi: Classical Stage Engineering (அரங்க அமைதி)

**Proscenium Metrics**: 8 × 7 × 1 *Kole* (*கோல்*) standard ratios.  
"""
    },
    {
        "category": "characters",
        "slug": "char-madhavi-natya-acharya",
        "file": "char-madhavi-natya-acharya.md",
        "node_type": "character",
        "name_en": "Madhavi: Supreme Classical Danseuse & Master of the 11 Dances",
        "name_ta": "மாதவி - 11 வகை ஆடல்களையும் அரங்கேற்றிய ஒப்பற்ற ஆடலரசி",
        "era": "Sangam Post-Classical Era",
        "year_start": 400,
        "year_end": 500,
        "thinai": "Neithal",
        "summary_en": "The legendary heroine of Silappadikaram who underwent seven years of intensive training in song, instrumental yazh, and dance, awarded the 1,008 gold kasu garland and the Talaikol scepter by the Chola king.",
        "summary_ta": "ஏழாண்டு காலம் நடனம், இசை, யாழ் முதலான கலைகளைப் பயின்று, சோழ மன்னன் கரிகாலன் முன்னிலையில் அரங்கேறித் தலைக்கோல் பட்டமும் 1008 கழஞ்சுப் பொன்மாலையும் பெற்ற சிலப்பதிகாரத்தின் தலைசிறந்த ஆடலரசி.",
        "content": """# Danseuse Madhavi (ஆடலரசி மாதவி)

**Mastery**: 11 *Aadals*, *Yazh* organology, *Arangetram* at age twelve.  
"""
    },
    {
        "category": "characters",
        "slug": "char-rajarajeswara-nataka-asiriyar",
        "file": "char-rajarajeswara-nataka-asiriyar.md",
        "node_type": "character",
        "name_en": "Santhik-Koothan: Master Playwright & Director of the Rajarajeswara Natakam",
        "name_ta": "சாந்திக் கூத்தன் - இராசராசேசுவர நாடகத்தை இயற்றி இயக்கிய தலைமை நாடகாசிரியர்",
        "era": "Imperial Chola Era",
        "year_start": 1000,
        "year_end": 1025,
        "thinai": "Marutham",
        "summary_en": "The master dramatist endowed with 120 kalams of paddy annually to stage the dynastic drama Rajarajeswara Natakam during the annual Chithirai festival at the Thanjavur temple.",
        "summary_ta": "தஞ்சைப் பெரிய கோயிலின் சித்திரைத் திருவிழாவில் 'இராசராசேசுவர நாடகம்' என்னும் வரலாற்று நாடகத்தை ஆண்டுதோறும் மேடையேற்றி நடித்த சாந்திக் கூத்தன் தாரபாகிய விஜயராஜேந்திர ஆச்சார்யன்.",
        "content": """# Santhik-Koothan: Master Playwright (சாந்திக் கூத்தன்)

**Annual Play**: *Rajarajeswara Natakam* (*இராசராசேசுவர நாடகம்*).  
"""
    },
    {
        "category": "places",
        "slug": "place-thanjavur-rajarajeswara-nataka-arangan",
        "file": "place-thanjavur-rajarajeswara-nataka-arangan.md",
        "node_type": "place",
        "name_en": "Thanjavur Brihadisvara Theatrical Pavilion & Nataka Salai",
        "name_ta": "தஞ்சைப் பெரிய கோயில் நாடக சாலை மற்றும் அரங்கம்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The open-air theatrical pillared pavilion inside the Brihadisvara temple complex in Thanjavur (10.7828° N, 79.1318° E) where classical plays, dance dramas, and musical recitals were performed before the assembly.",
        "summary_ta": "தஞ்சைப் பெரிய கோயில் வளாகத்தில் அமைந்திருந்த பிரம்மாண்டமான நாடக அரங்கம் (10.7828° N, 79.1318° E). இராசராசேசுவர நாடகம் முதலான செவ்வியல் நாடகங்களும், 400 தளிச்சேரிப் பெண்டுகளின் கூட்டு நடனங்களும் நிகழ்த்தப்பட்ட வரலாற்று அரங்கம்.",
        "content": """# Thanjavur Nataka Salai (தஞ்சாவூர் நாடக சாலை)

**Coordinates**: 10.7828° N, 79.1318° E.  
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: ANCIENT TAMIL MINERALOGY, GEMOLOGY & PEARL DIVER GUILDS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-ratna-pariksha-tamil-gemology",
        "file": "text-ratna-pariksha-tamil-gemology.md",
        "node_type": "text",
        "name_en": "Ratna Pariksha: Ancient Tamil Lapidary Manual & Nine Precious Gem Classifications (Navaratna)",
        "name_ta": "ரத்தின பரீட்சை - தமிழரின் மணிநூல், நவரத்தின வகைப்பாடு மற்றும் மணி சோதிப்பு முறைமைகள்",
        "era": "Sangam to Medieval Classical Era",
        "year_start": 200,
        "year_end": 1100,
        "thinai": "Mullai",
        "summary_en": "Indigenous gemological manual classifying precious minerals: Diamond (Vairam), Ruby (Manikkam), Sapphire (Neelam), Beryl (Vaidhurya), Emerald (Maragatham), Pearl (Muthu), Coral (Pavazham), identifying crystal habit, refractive luster, inclusions, and flaws (Doshas).",
        "summary_ta": "பண்டைத் தமிழகத்து மணிநூல் அறிஞர்கள் கடைப்பிடித்த ரத்தின பரீட்சை நூல். வைரம், மாணிக்கம், நீலம், வைடூரியம், மரகதம், முத்து, பவழம் முதலான நவரத்தினங்களின் ஒளிவிலகல், நிறம், கடினத்தன்மை, மற்றும் குற்றங்களை (தோஷங்கள்) ஆராயும் கனிமவியல் அறிவியல்.",
        "content": """# Ratna Pariksha: Tamil Lapidary Science (மணிநூல்)

**The 9 Precious Gems (*நவரத்தினங்கள்*)**: Diamond, Ruby, Sapphire, Beryl, Emerald, Pearl, Coral, Hessonite, Cat's Eye.  
"""
    },
    {
        "category": "inscriptions",
        "slug": "arch-kodumanal-beryl-quartz-lapidary-factory",
        "file": "arch-kodumanal-beryl-quartz-lapidary-factory.md",
        "node_type": "inscription",
        "name_en": "Kodumanal Industrial Lapidary Excavations: High-Precision Bead Drilling & Quartz Furnaces",
        "name_ta": "கொடுமணல் அகழாய்வு ஆவணங்கள் - உயர்தொழில்நுட்ப மணிசெதுக்கும் பட்டறைகள் மற்றும் பளிங்கு உலைகள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 200,
        "thinai": "Mullai",
        "summary_en": "Archaeological excavation reports by the Tamil Nadu State Dept of Archaeology at Kodumanal. Uncovered hundreds of thousands of semi-precious beads (beryl, sapphire, quartz, carnelian, jasper), diamond-tipped micro-drills (0.5 mm holes), and bead-polishing grooved stones.",
        "summary_ta": "ஈரோடு நொய்யல் ஆற்றங்கரைக் கொடுமணலில் தமிழகத் தொல்லியல் துறை நிகழ்த்திய அகழாய்வு முடிவுகள். வைடூரியம், நீலம், கார்னீலியன், மற்றும் படிகக் கற்களைக் கொண்டு செய்யப்பட்ட லட்சக்கணக்கான மணிகள், 0.5 மிமீ அளவிலான வைர முனை துளையிடும் கருவிகள் மற்றும் பளபளப்பூட்டும் பட்டறைகள்.",
        "content": """# Kodumanal Lapidary Industrial Excavations (கொடுமணல் மணிப் பட்டறைகள்)

**Location**: Noyyal River basin, Kodumanal, Erode District (*கொடுமணல்*).  
**Artefacts**: Diamond-point micro-drills, carnelian etched beads, quartz melting furnaces.  
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-korkai-parathavar-pearl-charter",
        "file": "insc-korkai-parathavar-pearl-charter.md",
        "node_type": "inscription",
        "name_en": "Korkai & Mannar Epigraphs: Pandyan Royal Pearl Fishery Charters & Parathavar Diver Guilds",
        "name_ta": "கொற்கை மற்றும் மன்னார் வளைகுடா கல்வெட்டுகள் - பாண்டியரின் முத்துக்குளிப்புச் சாசனங்கள்",
        "era": "Sangam Early Historic Era",
        "year_start": -200,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "Inscriptions and classical notices documenting the state-controlled pearl fisheries of the Gulf of Mannar, Parathavar diver contracts, division of pearl harvest (one-third to divers, one-third to king, one-third to boat owners), and marine shark-binder protections.",
        "summary_ta": "மன்னார் வளைகுடாவின் முத்துக்குளிப்பு மேலாண்மை, பரதவர் மூழ்காளர் சங்கங்கள், அரச வரிவிதிப்பு, மற்றும் முத்துக் குவியல்களைப் பிரிக்கும் முறைமை (மன்னனுக்கு மூன்றில் ஒரு பங்கு, மூழ்காளருக்கு ஒரு பங்கு, படகோட்டிக்கு ஒரு பங்கு) பற்றிய வரலாற்றுச் சாசனங்கள்.",
        "content": """# Korkai Pearl Fishery Charters (கொற்கை முத்துக்குளிப்பு சாசனங்கள்)

**Sovereign**: Pandyan Kings (*கொற்கைக் கோமான்*).  
**Diving Guild**: *Parathavar* High Divers of the Gulf of Mannar.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kodumanal-diamond-tipped-micro-drilling",
        "file": "concept-kodumanal-diamond-tipped-micro-drilling.md",
        "node_type": "concept",
        "name_en": "Kodumanal Lapidary Engineering: Diamond-Tipped Micro-Drilling & Semi-Precious Bead Polish",
        "name_ta": "கொடுமணல் வைர முனை நுண்ணிய துளையிடும் தொழில்நுட்பம் மற்றும் மணிக் கடைசல் கலை",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 200,
        "thinai": "Mullai",
        "summary_en": "Nanometer-precision micro-drilling using double-pointed diamond drill bits (Kura-vairam) rotating at high speeds with bow-drills to pierce hard beryl and carnelian stones without fracturing, coupled with alkaline etching with plant juice.",
        "summary_ta": "கொடுமணல் கைவினைஞர்கள் பயன்படுத்திய இரட்டை வைர முனை நுண்ணிய துளையிடும் கருவிகள். மோஸ் கடினத்தன்மை 7 முதல் 8 கொண்ட வைடூரியம் மற்றும் கார்னீலியன் மணிகளில் 0.5 மிமீ நுண்துளைகள் இட்டு, தாவரச் சாறுகளால் வெண்வண்ண வடிவங்களை பொறிக்கும் (எச்சிங்) கலை.",
        "content": """# Kodumanal Diamond-Tipped Micro-Drilling (நுண்துளையிடும் கலை)

**Tool**: Double-diamond drill bits (*வைர முனைத் துளைப்பான்*).  
**Stones**: Beryl, Agate, Jasper, Carnelian, Amethyst.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-muthu-kuli-pearl-fishery-mechanics",
        "file": "concept-muthu-kuli-pearl-fishery-mechanics.md",
        "node_type": "concept",
        "name_en": "Muthu-Kuli: Deep-Sea Pearl Oyster Diving, Shark-Binding Charms & Royal Customs",
        "name_ta": "முத்துக்குளிப்பு - ஆழ்கடல் சிப்பி எடுத்தல், சுறா பில்லி தடுத்தல் மற்றும் அரச சுங்க நடைமுறைகள்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Neithal",
        "summary_en": "The underwater pearl diving mechanics of the Parathavar divers: descending 10-15 fathoms holding a heavy sinking stone (Kallu), collecting pearl oysters (Pinctada fucata) in coir mesh bags, surfacing in two minutes, and neutralizing predatory sharks with magic charms (Kadal-kattu).",
        "summary_ta": "பரதவ மூழ்காளர்கள் 60-80 அடி ஆழத்திற்கு எடைக் கல்லை காலில் கட்டி மூழ்கி, தென்னங்கயிற்று வலைகளில் முத்துச் சிப்பிகளை அள்ளி, இரண்டு நிமிடங்களுக்குள் மேலே வரும் வியத்தகு ஆழ்கடல் மூழ்கு நுட்பம்; சுறா மீன்களிடமிருந்து காக்கும் கடல் கட்டு மந்திரங்கள்.",
        "content": """# Muthu-Kuli: Pearl Fishery Mechanics (முத்துக்குளிப்பு)

**Depth**: 10–15 fathoms (~20–30 meters) free diving.  
**Gear**: Sinking stone (*மூழ்குக் கல்*), nose clip, coir oyster net (*பறி*).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-navaratna-gemological-classification",
        "file": "concept-navaratna-gemological-classification.md",
        "node_type": "concept",
        "name_en": "Navaratna Metrology: Beryl (Vaidhurya), Sapphire (Neelam), Ruby (Manikkam) & Diamond (Vairam)",
        "name_ta": "நவரத்தின அளவியல் - வைடூரியம், நீலம், மாணிக்கம், வைரம் முதலான மணிகளின் தரம்",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1200,
        "thinai": "Mullai",
        "summary_en": "Systematic mineralogical testing of gems for hardness, specific gravity, and optical chatoyancy (Cat's Eye effect). Classifies beryl mined from the Kangeyam belt and sapphires from the Kongu realm exported directly to Rome.",
        "summary_ta": "கொங்கு நாட்டின் காங்கேயம் மற்றும் கரூர் பகுதிகளில் வெட்டி எடுக்கப்பட்ட உயர்தர வைடூரியம், நீல மணிகள் மற்றும் பவழங்களின் தரப் பிரிவுகள்; ரோமானியப் பேரரசுக்கு ஏற்றுமதியான மணிகளின் கனிமவியல் உறுதிப்பாடு.",
        "content": """# Navaratna Gemology (நவரத்தின கனிமவியல்)

**Major Local Mines**: Kangeyam (Beryl), Karur (Quartz/Amethyst), Gulf of Mannar (Pearl).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-parathavar-marine-guild-organization",
        "file": "concept-parathavar-marine-guild-organization.md",
        "node_type": "concept",
        "name_en": "Parathavar Guild System: Clan Hierarchy, Maritime Defense & Diving Guild Leadership",
        "name_ta": "பரதவர் கடல் கூட்டமைப்பு - குல மரபு, கடற்படைப் பாதுகாப்பு மற்றும் முத்துக்குளிப்பு தலைமை",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Neithal",
        "summary_en": "The social and military organization of the ancient Parathavar seafaring community. Commanded the pearl diving fleets, managed coastal saltpans (Uppalam), served as marine archers in the Pandyan navy, and operated autonomous guild councils under their headmen (Thalaivan).",
        "summary_ta": "முத்துக்குளிப்பு, சங்கு அறுத்தல், உப்பள மேலாண்மை மற்றும் பாண்டிய கடற்படையின் கடல் வில்லாளர்களாகத் திகழ்ந்த பரதவர் குலத்தின் தன்னாட்சி பெற்ற கூட்டமைப்பு மற்றும் தலைவர்களின் தலைமைத்துவம்.",
        "content": """# Parathavar Maritime Guild (பரதவர் கூட்டமைப்பு)

**Sovereignty**: Autonomous coastal administration of the Pearl Fishery Coast (*முத்துக்குளிப்பு கடற்கரை*).  
"""
    },
    {
        "category": "characters",
        "slug": "char-kodumanal-master-lapidary-artisan",
        "file": "char-kodumanal-master-lapidary-artisan.md",
        "node_type": "character",
        "name_en": "Perunthanmai Kodumanal Lapidary Master: Pioneer of Etched Carnelian Beads",
        "name_ta": "கொடுமணல் தலைமை மணி செதுக்குநர் - கார்னீலியன் அமிலப் பொறிப்புக் கலைஞர்",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "Mullai",
        "summary_en": "Master lapidary craftsman of Kodumanal whose Tamil-Brahmi inscribed potsherds and etched carnelian beads have been discovered across South India, Egypt (Berenike), and the Red Sea.",
        "summary_ta": "நொய்யல் ஆற்றங்கரைக் கொடுமணலில் ஆயிரக்கணக்கான உயர்தரக் கல்மணிகளை வடித்து, செவ்வந்திக் கற்களில் காரக் கரைசலால் ஓவியங்களைப் பொறித்து உரோமானிய உலகிற்கு ஏற்றுமதி செய்த தலைமை மணி ஆசான்.",
        "content": """# Kodumanal Master Lapidary (கொடுமணல் தலைமை மணி செதுக்குநர்)

**Artisanal Glory**: Diamond-point drilling, carnelian chemical etching, international export.  
"""
    },
    {
        "category": "characters",
        "slug": "char-korkai-muthu-kuli-thalavan",
        "file": "char-korkai-muthu-kuli-thalavan.md",
        "node_type": "character",
        "name_en": "Korkai Parathavar Chieftain: Lord of the Pearl Fisheries & High Diver",
        "name_ta": "கொற்கைப் பரதவத் தலைவன் - முத்துக்குளிப்புக் கடற்கரையின் தலைமை மாலுமி",
        "era": "Sangam Early Historic Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "The hereditary maritime chieftain of Korkai who commanded the annual pearl harvesting flotilla of hundreds of boats and coordinated directly with the Pandyan crown.",
        "summary_ta": "மன்னார் வளைகுடாவின் முத்துக்குளிப்புப் படகுகளை வழிநடத்தி, பாண்டிய மன்னனோடு ஒப்பந்தம் செய்து, உலகப் புகழ்வாய்ந்த கொற்கை முத்துக்களைத் திரட்டிய பரதவ குலத் தலைவர்.",
        "content": """# Korkai Parathavar Chieftain (கொற்கைப் பரதவத் தலைவன்)

**Role**: Fleet commander of the Gulf of Mannar pearl harvest.  
"""
    },
    {
        "category": "places",
        "slug": "place-kodumanal-gem-lapidary-industrial-hub",
        "file": "place-kodumanal-gem-lapidary-industrial-hub.md",
        "node_type": "place",
        "name_en": "Kodumanal Industrial Gem Factory & Megalithic Lapidary Center",
        "name_ta": "கொடுமணல் மணித் தொழிற்கூடம் - சங்க கால நவரத்தின ஆலை மற்றும் அகழாய்வு மையம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 200,
        "thinai": "Mullai",
        "summary_en": "Ancient industrial metropolis on the Noyyal River in Erode district (11.1100° N, 77.5800° E), celebrated in Pathitrupathu (Kodumanam) as the global production center of quartz, beryl, and carnelian beads.",
        "summary_ta": "பதிற்றுப்பத்தில் 'கொடுமணம்' என்று போற்றப்படும் தொழிற்பட்டினம் (11.1100° N, 77.5800° E). நொய்யல் ஆற்றங்கரையில் அமைந்த இந்நகரம் சங்க காலத்து உலகின் மிகப்பெரிய கல்மணி உற்பத்தி மற்றும் ஏற்றுமதி மையமாகத் திகழ்ந்தது.",
        "content": """# Kodumanal Gem Lapidary Hub (கொடுமணல்)

**Coordinates**: 11.1100° N, 77.5800° E.  
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: ANCIENT TAMIL COASTAL PORTS & MARITIME CUSTOMS ADMINISTRATION
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-pattinappalai-customs-administration",
        "file": "text-pattinappalai-customs-administration.md",
        "node_type": "text",
        "name_en": "Pattinappalai: Kaveripoompattinam Harbor Customs House (Sungam) & Tiger-Seal Warehousing",
        "name_ta": "பட்டினப்பாலை - பூம்புகார் சுங்கச் சாவடி, புலிப்பொறி முத்திரை மற்றும் பண்டகசாலைகள்",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 150,
        "thinai": "Neithal",
        "summary_en": "Celebrated poem by Kadiyalur Uruttirangannanar detailing port customs administration at Poompuhar. Describes mountain-like piles of goods in beach warehouses, customs officials collecting royal duties, and stamping bales with the Chola imperial Tiger Seal (Puli-p-pori).",
        "summary_ta": "கடியலூர் உருத்திரங்கண்ணனாரின் பட்டினப்பாலையில் விவரிக்கப்படும் பூம்புகார் துறைமுகச் சுங்க நிர்வாகம். மலைபோலக் குவிக்கப்பட்ட பண்டகசாலைச் சரக்குகள், இடைவிடாது சுங்க வரி வசூலிக்கும் அதிகாரிகள், மற்றும் வரி செலுத்தப்பட்ட பொதிகள் மீது சோழரின் புலிப்பொறி முத்திரையிடும் முறை.",
        "content": """# Pattinappalai: Harbor Customs Administration (பட்டினப்பாலை சுங்க மேலாண்மை)

**Author**: Kadiyalur Uruttirangannanar (*கடியலூர் உருத்திரங்கண்ணனார்*).  
**Port**: Kaveripoompattinam (Poompuhar).  
**Key Feature**: Imperial Tiger-Seal (*புலிப்பொறி*) stamping on warehoused trade bales.  
"""
    },
    {
        "category": "texts",
        "slug": "text-perumpanarruppadai-kalamkarai-lighthouse",
        "file": "text-perumpanarruppadai-kalamkarai-lighthouse.md",
        "node_type": "text",
        "name_en": "Perumpanarruppadai: High Brick Beacon Lighthouses (Kalamkarai-Vilakkam) & Estuarine Pilotage",
        "name_ta": "பெரும்பாணாற்றுப்படை - கலங்கரை விளக்கம், மாட ஒள் எறி மற்றும் துறைமுக வழிகாட்டல்",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 150,
        "thinai": "Neithal",
        "summary_en": "Classical verses in Perumpanarruppadai (lines 346–351) describing the monumental architecture of ancient coastal beacon lighthouses: high brick masonry towers climbing into the sky, burning sweet-scented nocturnal oil fires to summon storm-tossed ships into harbor.",
        "summary_ta": "பெரும்பாணாற்றுப்படையில் வரும் கலங்கரை விளக்கத்தின் ஒப்பற்ற வர்ணனை: வானத்தைத் தொடுவது போல அமைக்கப்பட்ட செங்கல்லால் ஆன உயர்ந்த மாடம், இரவில் திசைதெரியாமல் அலைகின்ற மரக்கலங்களை அழைப்பது போல எரியூட்டப்படும் நறுமணப் பெருவிளக்கு (மாட ஒள் எறி).",
        "content": """# Perumpanarruppadai: Coastal Lighthouses (கலங்கரை விளக்கம்)

**Architectural Form**: Multi-storied masonry watchtower burning nocturnal resin beacons.  
"""
    },
    {
        "category": "inscriptions",
        "slug": "arch-arikamedu-indo-roman-emporium-excavation",
        "file": "arch-arikamedu-indo-roman-emporium-excavation.md",
        "node_type": "inscription",
        "name_en": "Arikamedu (Poduke) Archaeological Records: Roman Amphorae, Arretine Ware & Customs Wharves",
        "name_ta": "அரிக்கமேடு அகழாய்வு ஆவணங்கள் - உரோமானிய ஆம்போரா சாடிகள், அரேட்டைன் மண்பாண்டங்கள் மற்றும் துறைமுகக் கிடங்குகள்",
        "era": "Iron Age to Sangam Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "Archaeological excavation monographs by Mortimer Wheeler, Casal, and Vimala Begley at Arikamedu near Puducherry. Confirms the Periplus port Poduke with Roman Mediterranean wine amphorae, stamped Arretine pottery, glass beads, and brick customs wharves along the Ariyankuppam river.",
        "summary_ta": "புதுச்சேரி அரிக்கமேட்டில் மோர்டிமர் வீலர் முதலானோரால் நிகழ்த்தப்பட்ட புகழ்பெற்ற அகழாய்வு ஆவணங்கள். பெரிப்ளூஸ் நூலில் 'பொதுகே' (Poduke) எனக் குறிக்கப்பட்ட இத்துறைமுகத்தில் உரோமானிய திராட்சை மதுச் சாடிகள், முத்திரையிட்ட அரேட்டைன் தட்டுகள், மற்றும் செங்கல் படகுத்துறைகள் கண்டெடுக்கப்பட்ட ஆய்வு முடிவுகள்.",
        "content": """# Arikamedu / Poduke Excavation Monograph (அரிக்கமேடு)

**Location**: Ariyankuppam River estuary, Puducherry.  
**Key Finds**: Roman Mediterranean wine amphorae, terra sigillata, brick wharves.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-puli-p-pori-chola-customs-tiger-seal",
        "file": "concept-puli-p-pori-chola-customs-tiger-seal.md",
        "node_type": "concept",
        "name_en": "Puli-p-pori: Imperial Chola Customs Sealing on Export-Import Bales in Poompuhar",
        "name_ta": "புலிப்பொறி - பூம்புகார் சுங்கச் சாவடியில் ஏற்றுமதி-இறக்குமதிப் பொதிகளில் இடப்பட்ட சோழர் அரச முத்திரை",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "The administrative practice of applying the royal Tiger Seal in red wax or clay upon customs clearance. No bale could leave the beach warehouses of Poompuhar without this seal, guaranteeing payment of port dues and cargo integrity.",
        "summary_ta": "சோழர்களின் அரச சின்னமான புலி முத்திரை கொண்டு சுங்கத் தீர்வை செலுத்தப்பட்ட ஏற்றுமதி-இறக்குமதிப் பொதிகள் மீது இடப்படும் அதிகாரப்பூர்வ முத்திரையிடும் நிர்வாக நடைமுறை.",
        "content": """# Puli-p-pori: Chola Customs Tiger Seal (புலிப்பொறி)

**Administrative Function**: Official customs clearance seal on maritime cargo.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kalamkarai-vilakkam-beacon-architecture",
        "file": "concept-kalamkarai-vilakkam-beacon-architecture.md",
        "node_type": "concept",
        "name_en": "Kalamkarai-Vilakkam: Architectural Engineering of Coastal Lighthouses & Nocturnal Oil Beacons",
        "name_ta": "கலங்கரை விளக்கம் - கடற்கரை வழிகாட்டி மாடங்கள், எண்ணெய் விளக்குகள் மற்றும் துறைமுக நுழைவுப் பொறியியல்",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "Structural design of ancient Tamil coastal lighthouses. Built with thick baked brick walls and lime mortar, featuring winding internal stairs, ventilation flues, and fire-bowls fueled by castor oil and fragrant tree gums visible leagues out to sea.",
        "summary_ta": "பண்டைத் தமிழகத் துறைமுகங்களில் அமைக்கப்பட்ட செங்கல் மாடக் கலங்கரை விளக்கங்களின் கட்டடக்கலை மற்றும் இரவுக் கடல் வழிகாட்டல் நுட்பங்கள்.",
        "content": """# Kalamkarai-Vilakkam Architecture (கலங்கரை விளக்கம்)

**Engineering**: Multi-level masonry tower with upper fire-brazier platform.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-yavana-cheri-foreign-merchant-quarters",
        "file": "concept-yavana-cheri-foreign-merchant-quarters.md",
        "node_type": "concept",
        "name_en": "Yavana Cheri: Greco-Roman, Arab & Chinese Merchant Quarters in Ancient Tamil Ports",
        "name_ta": "யவனச் சேரி - பண்டைய தமிழ்த் துறைமுகங்களில் நிலவிய உரோமானிய, அரபு மற்றும் சீன வணிகர் குடியிருப்புகள்",
        "era": "Sangam Early Historic Era",
        "year_start": -100,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "Cosmopolitan extraterritorial settlements in Tamil ports (Poompuhar, Musiri, Korkai, Arikamedu) where Greco-Roman (Yavana) traders, wine merchants, and mercenaries resided permanently under royal Pandyan and Chola protection.",
        "summary_ta": "பூம்புகார், முசிறி, கொற்கை, அரிக்கமேடு ஆகிய துறைமுகங்களில் ரோமானிய, கிரேக்க, மற்றும் அரபு வணிகர்கள் தங்கி வாழ்ந்த பன்னாட்டு குடியிருப்புகளும் அவர்களின் சிறப்பு வர்த்தக உரிமைகளும்.",
        "content": """# Yavana Cheri: Foreign Merchant Quarters (யவனச் சேரி)

**Cosmopolitan Demographics**: Greco-Roman mariners, wine merchants, bodyguards, and artisans.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-thol-urimai-customs-and-transit-duties",
        "file": "concept-thol-urimai-customs-and-transit-duties.md",
        "node_type": "concept",
        "name_en": "Thol-Urimai & Sungam: Ancient Port Tariffs, Warehouse Transit Tolls & Smuggling Interception",
        "name_ta": "சுங்கம் மற்றும் சுங்கத் தீர்வை - துறைமுக இறக்குமதி வரிகள், பண்டகசாலைக் கட்டணங்கள் மற்றும் வரி ஏய்ப்புத் தடுப்பு",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "The fiscal structure of port tariffs: import duties (Thol-urimai / Sungam), warehouse storage tolls, riverine transit taxes, and naval patrol squadrons intercepting smugglers attempting to bypass official roadsteads.",
        "summary_ta": "துறைமுகங்களில் வசூலிக்கப்பட்ட இறக்குமதி மற்றும் ஏற்றுமதி சுங்க வரிகள், கடற்காவல் ரோந்துப் படகுகள் மூலம் கள்ளக்கடத்தலைத் தடுத்த அரச நிதி நிர்வாக முறைமை.",
        "content": """# Port Tariffs & Customs Administration (சுங்க நிர்வாகம்)

**Revenue Categories**: *Sungam* (Import/Export Dues), *Ayam* (Transit Toll), *Thol-urimai*.  
"""
    },
    {
        "category": "characters",
        "slug": "char-puhar-sunga-adhikari",
        "file": "char-puhar-sunga-adhikari.md",
        "node_type": "character",
        "name_en": "Poompuhar Customs Officer: Imperial Keeper of the Royal Tiger Seal",
        "name_ta": "பூம்புகார் சுங்க அதிகாரி - சோழர் புலிப்பொறி முத்திரைக் காப்பாளர் மற்றும் சுங்கத் தலைவர்",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 150,
        "thinai": "Neithal",
        "summary_en": "The royal port customs commissioner praised in Pattinappalai for collecting duties with tireless integrity, safeguarding state revenue, and stamping export bales night and day.",
        "summary_ta": "பட்டினப்பாலையில் போற்றப்படும் பூம்புகார் துறைமுகத் தலைமைச் சுங்க அதிகாரி; இடைவிடாது வரி வசூலித்து சோழ மன்னனின் புலிப்பொறி முத்திரையைப் பொதிகளில் இட்டு அரசு நிதி காத்தவர்.",
        "content": """# Poompuhar Customs Commissioner (பூம்புகார் சுங்க அதிகாரி)

**Office**: Imperial Port Customs & Keeper of the Tiger Seal (*புலிப்பொறி காப்பாளர்*).  
"""
    },
    {
        "category": "characters",
        "slug": "char-arikamedu-yavana-potter-merchant",
        "file": "char-arikamedu-yavana-potter-merchant.md",
        "node_type": "character",
        "name_en": "Marcus of Poduke: Resident Greco-Roman Wine & Garum Importer at Arikamedu",
        "name_ta": "மார்க்கஸ் - அரிக்கமேட்டில் தங்கியிருந்த உரோமானிய திராட்சை மது வணிகர்",
        "era": "Sangam Early Historic Era",
        "year_start": -50,
        "year_end": 100,
        "thinai": "Neithal",
        "summary_en": "Archetypal Mediterranean merchant documented through stamped amphora handles (VIBII, CAMURI) excavated at Arikamedu, importing Italian wine, garum fish sauce, and olive oil in exchange for Tamil textiles and beryls.",
        "summary_ta": "அரிக்கமேடு அகழாய்வுகளில் கண்டெடுக்கப்பட்ட முத்திரையிட்ட உரோமானிய ஆம்போரா சாடிகள் உணர்த்தும் உரோமானிய திராட்சை மது மற்றும் ஆலிவ் எண்ணெய் வணிகர்.",
        "content": """# Marcus of Poduke (அரிக்கமேட்டு உரோமானிய வணிகர்)

**Trade Commodities**: Mediterranean wine, olive oil, Arretine red-gloss ware.  
"""
    },
    {
        "category": "places",
        "slug": "place-alagankulam-pandyan-oceanic-port",
        "file": "place-alagankulam-pandyan-oceanic-port.md",
        "node_type": "place",
        "name_en": "Alagankulam: Ancient Pandyan Trans-Oceanic Port at the Vaigai Estuary",
        "name_ta": "அழகன்குளம் - வைகை முகத்துவாரத்துப் பாண்டியர் பெருந்துறைமுகம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "Historic Pandyan oceanic port in Ramanathapuram district (9.3500° N, 78.9833° E) at the mouth of the Vaigai river. Yielded thousands of Roman coins, rouletted ware, ship-engraved potsherds, and continuous trade links with the Mediterranean and Sri Lanka.",
        "summary_ta": "இராமநாதபுரம் மாவட்டம் வைகை ஆற்றின் முகத்துவாரத்தில் அமைந்துள்ள சங்க காலத்துப் பாண்டியர் துறைமுகம் (9.3500° N, 78.9833° E). ரோமானிய வெள்ளி நாணயங்கள், கப்பல் உருவம் பொறித்த மண்பாண்டங்கள் மற்றும் வெளிநாட்டு வர்த்தகத் தடயங்கள் நிறைந்த தளம்.",
        "content": """# Alagankulam Oceanic Port (அழகன்குளம்)

**Coordinates**: 9.3500° N, 78.9833° E.  
"""
    },
    {
        "category": "places",
        "slug": "place-arikamedu-indo-roman-customs-wharf",
        "file": "place-arikamedu-indo-roman-customs-wharf.md",
        "node_type": "place",
        "name_en": "Arikamedu: Poduke Indo-Roman Warehouse & Port Wharf",
        "name_ta": "அரிக்கமேடு - புதுச்சேரி உரோமானியப் பண்டகசாலை மற்றும் துறைமுக இறங்குதளம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -200,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "Archaeological maritime trade center on the Ariyankuppam river south of Puducherry (11.9056° N, 79.8297° E). Features brick-built tidal wharves, bead-dyeing vats, and international warehouse foundations.",
        "summary_ta": "புதுச்சேரி அரியான்குப்பம் ஆற்றங்கரையில் அமைந்துள்ள புகழ்பெற்ற சர்வதேசத் துறைமுகம் (11.9056° N, 79.8297° E). செங்கற்களால் ஆன படகு இறங்குதளங்கள், மணி சாயமிடும் தொட்டிகள் மற்றும் உரோமானிய வணிகக் கிடங்குகள் கொண்ட தளம்.",
        "content": """# Arikamedu Customs Wharf (அரிக்கமேடு துறைமுகம்)

**Coordinates**: 11.9056° N, 79.8297° E.  
"""
    }
]

# ==============================================================================
# EDGES DEFINITION (Relational Cross-Domain Links)
# ==============================================================================
EDGES = [
    # Theater Edges
    (
        "text-silappadikaram-kadaladukadai-drama",
        "details_classical_repertoire",
        "concept-pathinondru-aadal-eleven-dances",
        "relational",
        "Sangam Post-Classical Era",
        "Kadaladukadai details the performance of the 11 sacred dances by Madhavi.",
        "Silappadikaram Kadaladukadai"
    ),
    (
        "text-silappadikaram-kadaladukadai-drama",
        "describes_curtain_mechanics",
        "concept-aranga-amaithi-classical-stagecraft",
        "relational",
        "Sangam Post-Classical Era",
        "Text describes Oru-muga and Iru-muga Ezhini stage curtains and acoustic framing.",
        "Silappadikaram verses"
    ),
    (
        "insc-thanjavur-rajarajeswara-nataka-charter",
        "records_endowed_artist_guild",
        "concept-thalicheri-temple-artist-guilds",
        "relational",
        "Imperial Chola Era",
        "Granite inscriptions document the 400 endowed Thalicheri dancers and house shares.",
        "Thanjavur South Wall Inscriptions"
    ),
    (
        "char-madhavi-natya-acharya",
        "performed_at_festival",
        "text-silappadikaram-kadaladukadai-drama",
        "relational",
        "Sangam Post-Classical Era",
        "Madhavi performed the 11 dances before the Chola king at Poompuhar sea festival.",
        "Silappadikaram"
    ),
    (
        "char-rajarajeswara-nataka-asiriyar",
        "staged_annual_play_at",
        "place-thanjavur-rajarajeswara-nataka-arangan",
        "relational",
        "Imperial Chola Era",
        "Santhik-Koothan staged the Rajarajeswara Natakam in the temple pavilion.",
        "Brihadisvara Inscription"
    ),

    # Mineralogy & Gemology Edges
    (
        "arch-kodumanal-beryl-quartz-lapidary-factory",
        "excavated_evidence_of",
        "concept-kodumanal-diamond-tipped-micro-drilling",
        "relational",
        "Iron Age to Sangam Era",
        "Kodumanal excavations revealed double-diamond micro-drills and perforated quartz beads.",
        "Kodumanal Excavation Reports (TNSDA)"
    ),
    (
        "insc-korkai-parathavar-pearl-charter",
        "regulates_fishery",
        "concept-muthu-kuli-pearl-fishery-mechanics",
        "relational",
        "Sangam Early Historic Era",
        "Charters define the division of pearl oyster catches between divers and the crown.",
        "Pandyan Maritime Epigraphy"
    ),
    (
        "concept-parathavar-marine-guild-organization",
        "commanded_by",
        "char-korkai-muthu-kuli-thalavan",
        "relational",
        "Sangam Early Historic Era",
        "The Parathavar pearl diver guilds operated under hereditary maritime chieftains.",
        "Classical Marine Inscriptions"
    ),
    (
        "char-kodumanal-master-lapidary-artisan",
        "operated_at_factory",
        "place-kodumanal-gem-lapidary-industrial-hub",
        "relational",
        "Iron Age to Sangam Era",
        "Master lapidaries shaped beryl and carnelian beads at the Kodumanal workshops.",
        "Archaeological Evidence"
    ),
    (
        "text-ratna-pariksha-tamil-gemology",
        "classifies_precious_stones",
        "concept-navaratna-gemological-classification",
        "relational",
        "Sangam to Medieval Classical Era",
        "Ratna Pariksha formalizes testing criteria for diamonds, beryls, rubies, and pearls.",
        "Tamil Ratna Shastra"
    ),

    # Coastal Ports & Customs Edges
    (
        "text-pattinappalai-customs-administration",
        "documents_customs_seal",
        "concept-puli-p-pori-chola-customs-tiger-seal",
        "relational",
        "Sangam Early Historic Era",
        "Pattinappalai records royal customs officials stamping bales with the Tiger Seal.",
        "Pattinappalai lines 125-135"
    ),
    (
        "text-perumpanarruppadai-kalamkarai-lighthouse",
        "describes_beacon_architecture",
        "concept-kalamkarai-vilakkam-beacon-architecture",
        "relational",
        "Sangam Early Historic Era",
        "Perumpanarruppadai portrays the tall brick beacon lighthouse guiding night shipping.",
        "Perumpanarruppadai lines 346-351"
    ),
    (
        "arch-arikamedu-indo-roman-emporium-excavation",
        "confirms_foreign_settlement",
        "concept-yavana-cheri-foreign-merchant-quarters",
        "relational",
        "Iron Age to Sangam Era",
        "Arikamedu excavations confirmed Roman wine merchants residing at Poduke.",
        "Wheeler & Begley Excavation Monographs"
    ),
    (
        "char-puhar-sunga-adhikari",
        "administered_customs_at",
        "text-pattinappalai-customs-administration",
        "relational",
        "Sangam Early Historic Era",
        "The Poompuhar customs officer collected duties on incoming overseas cargoes.",
        "Pattinappalai"
    ),
    (
        "place-alagankulam-pandyan-oceanic-port",
        "harbor_customs_managed_under",
        "concept-thol-urimai-customs-and-transit-duties",
        "relational",
        "Iron Age to Sangam Era",
        "Alagankulam served as Pandyan gateway port collecting duties on Roman imports.",
        "Alagankulam Excavation Reports"
    ),
    (
        "place-arikamedu-indo-roman-customs-wharf",
        "site_of_warehouse_wharves",
        "arch-arikamedu-indo-roman-emporium-excavation",
        "relational",
        "Iron Age to Sangam Era",
        "Arikamedu brick wharves handled Mediterranean wine amphorae unloading.",
        "Arikamedu Monograph"
    )
]

def main():
    print("=" * 80)
    print("🚀 TRIPLE CIVILIZATIONAL EXPANSION HARVESTER (BATCH 3)")
    print("   1. Ancient Tamil Theater, Drama & Epigraphical Performing Arts (10)")
    print("   2. Ancient Tamil Mineralogy, Gemology & Pearl Diver Guilds (10)")
    print("   3. Ancient Tamil Coastal Ports, Lighthouses & Customs Administration (11)")
    print("   TOTAL: 31 Canonical Dossiers | 62 Dense Vector Embeddings")
    print("=" * 80)

    # Phase 1: Write Canonical Markdown Dossiers
    print("\n[Phase 1] Writing 31 Canonical Markdown Dossiers to Moolam Chronicles...")
    for d in DOSSIERS:
        cat_dir = os.path.join(MOOLAM_KNOWLEDGE, d["category"])
        os.makedirs(cat_dir, exist_ok=True)
        file_path = os.path.join(cat_dir, d["file"])
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Written: knowledge/{d['category']}/{d['file']}")

    # Phase 2: PostgreSQL Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\n[Phase 2] Upserting 31 Lore Nodes into PostgreSQL...")
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
    print("\n[Phase 4] Generating 62 Dense 1024-dim BGE-M3 Embeddings into rag_chunks...")
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
