#!/usr/bin/env python3
"""
Ancient Tamil Maritime Ship Architecture & Naval Warfare Corpus Harvester
Monumental Indigenous Tamil Shipwright Sciences, Hydrodynamics & Trans-Oceanic Armadas:
- Kappal Sattiram: Palm-Leaf Shipbuilding Manual, Hull Proportions & Timber Engineering
- Maduraikkanchi: Towering Ocean Navai, Cloud-Sails & Harbor Beacon Lighthouses (Kalamkarai-Vilakkam)
- Purananuru: Maritime Armada & Sovereign Coastal Expeditions of Chola King Killivalavan
- Thanjavur Brihadisvara Plinth Inscription: Rajendra Chola I's 1025 CE Trans-Oceanic Srivijaya Conquest
- Concepts: Kappal Structural Anatomy & Rigging, Kattumaram Hydrodynamics, Naval Warfare Tactics, Nagapattinam Dockyards
- Figures: Rajendra Chola I (Naval Emperor), Kulamutrathu Killivalavan, Chola Kadal-Padai Thalapathi
- Places: Nagapattinam Naval Dockyard, Korkai Pandyan Naval Harbor
Generates canonical markdown files in moolam-chronicles, upserts lore_nodes, links lore_edges,
and produces 1024-dim BGE-M3 dense vector embeddings into rag_chunks.
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

DOSSIERS = [
    # --------------------------------------------------------------------------
    # 1. PRIMARY TEXTS & CLASSICAL SHIPWRIGHT TREATISES
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-kappal-sattiram-naval-architecture",
        "file": "text-kappal-sattiram-naval-architecture.md",
        "node_type": "text",
        "name_en": "Kappal Sattiram: Ancient Tamil Shipwright Science, Hull Proportions & Timber Selection",
        "name_ta": "கப்பல் சாத்திரம் - பண்டைத் தமிழ் மரக்கலக் கட்டுமானக் கலை, அளவியல் மற்றும் மரத் தேர்வுகள்",
        "era": "Sangam to Medieval Classical Era",
        "year_start": 200,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "Comprehensive indigenous Tamil manual of naval architecture and nautical engineering preserved in classical palm-leaf manuscripts. Codifies sacred timber selection rules (Teak, Vengai, Rosewood, Poovarasu, and Iluppai), hydro-structural dimensions (Ayam length, Veechu beam, Aazham draft), golden proportion ratios for ocean vessels, stitched-hull construction (Koorai) without iron nails, caulking with vegetable resins and fish oil, and precise vessel typologies from coastal catamarans to trans-oceanic multi-masted Perum-Navai ships.",
        "summary_ta": "பண்டைத் தமிழகத்தின் மரக்கலக் கட்டுமானப் பொறியியல் மற்றும் கடலோட்ட அறிவியலை விவரிக்கும் அரிய ஓலைச்சுவடி நூல். நாவாய் கட்டுமானத்திற்குரிய மரத் தேர்வுகள் (தேக்கு, வேங்கை, ஈட்டி, பூவரசு, இலுப்பை), நீளம் (ஆயம்), அகலம் (வீச்சு), ஆழம் (ஆழம்) ஆகியவற்றுக்கு இடையேயான விகிதாச்சார அளவீடுகள், இரும்பாணி இல்லா தையல் மரக்கல முறை (கூரை மரக்கலம்), குங்கிலியம் மற்றும் மூலிகைப் பிசின் பூச்சுகள், மற்றும் கட்டுமரம் முதல் பெருநாவாய் வரையிலான கப்பல் வகைகளைப் பற்றிய முழுமையான அறிவியல் சான்றுகளின் தொகுப்பு.",
        "content": """# Kappal Sattiram: Ancient Tamil Shipwright Science (கப்பல் சாத்திரம்)

**Tradition**: Indigenous Tamil Naval Architecture (*கப்பற்கலை மரபு*).  
**Source Manuscripts**: Oriental Manuscripts Library & Saraswathi Mahal Palm-Leaf Codices.  
**Historical Horizon**: Classical Sangam through Medieval Imperial Chola Eras (~200 BCE – 1250 CE).  
**Geographical Matrix**: Coromandel & Malabar Littorals (*Poompuhar, Nagapattinam, Korkai, Musiri*).  

---

## 1. Overview of Kappal Sattiram
The *Kappal Sattiram* (*கப்பல் சாத்திரம்*) represents an ancient lineage of technical palm-leaf treatises detailing the hydrodynamic principles, carpentry mathematics, celestial navigation, and nautical astronomy practiced by ancient Tamil shipwrights (*Kammalar* and *Marakkala-Aasiriyar*). Long before European naval treatises formalized naval architecture, Tamil master builders possessed an empirical taxonomy of marine timber properties, hull shear-stress mitigation, and monsoon wind aerodynamics.

---

## 2. Timber Selection (*Maram Therivu*) & Metallurgical Avoidance
Tamil naval science strictly classified woods based on density, grain alignment, tensile strength, and resistance to saline decay and marine wood-boring shipworms (*Teredo navalis* / *Kadal-poochi*):

1. **Keel & Spine (*Adimaram* / *Erakku*)**:
   - Primary: Teak (*Tectona grandis* / *தேக்கு*) and Malabar Rosewood (*Dalbergia latifolia* / *ஈட்டி*).
   - Qualities: High flexural modulus, superior straightness, natural oils repelling marine mollusks, and exceptional capacity to absorb axial compressive stress during heavy pitching.
2. **Hull Planking & Strakes (*Pathagai* / *Thattu-p-palagai*)**:
   - Primary: Vengai (*Pterocarpus marsupium* / *வேங்கை*) and Poovarasu (*Thespesia populnea* / *பூவரசு*).
   - Qualities: High impact resilience against hydraulic slamming loads, fine closed grain preventing water seepage under hydrostatic pressure.
3. **Masts & Spars (*Koombu* & *Paraban*)**:
   - Primary: Alexandrian Laurel (*Calophyllum inophyllum* / *புன்னாகம்*) and aged Teak.
   - Qualities: High bending tolerance under gale-force wind shear without splintering or snapping.
4. **Internal Ribs & Frames (*Kura-maram* / *Vangu*)**:
   - Primary: Mahua (*Madhuca longifolia* / *இலுப்பை*) and Black Murdah (*Terminalia tomentosa* / *கருமருது*).
   - Qualities: Naturally curved branch grain matching the desired hull curvature, eliminating cross-grain structural weaknesses.

### Avoidance of Iron Fasteners in Stitched Hulls
A crowning principle of *Kappal Sattiram* is the deliberate avoidance of rigid iron spikes or nails below the waterline. In the high salinity and temperature of tropical waters, iron rapidly corrodes, creating galvanic oxidation and brittle failure. Instead, Tamil shipwrights utilized **Stitched-Hull Construction (*Koorai-kappal*)**:
- Hull planks were bored with evenly spaced edge-holes.
- Planks were joined edge-to-edge using mortise-and-tenon dowels.
- Heavy-gauge triple-ply coconut coir cordage (*Thennam-naar kayiru*) was laced tightly through the holes over internal batten strips.
- The seams were packed with a waterproof matrix of slaked lime (*Chunnam*), black dammar resin (*Kungiliyam*), vegetable pitch, and castor/fish oil.
- This yielded an elastic, hydro-flexible hull that could flex over violent Indian Ocean swells and ocean sandbars without cracking.

---

## 3. Dimensional Metrics & Golden Proportions
The treatise codifies precise ratios connecting overall length (*Ayam*), maximum beam width (*Veechu*), and vertical draft depth (*Aazham*):

$$\text{Beam Ratio} = \frac{\text{Ayam (Length)}}{\text{Veechu (Beam)}} \approx 4.0 \text{ to } 6.0 \quad (\text{Deep-Sea Ocean Navai})$$
$$\text{Draft Ratio} = \frac{\text{Veechu (Beam)}}{\text{Aazham (Draft)}} \approx 1.8 \text{ to } 2.5$$

These proportions guaranteed adequate metacentric height ($GM$), minimizing the danger of catastrophic roll capsize while optimizing low hull hydrodynamic drag coefficient ($C_d$).

---

## 4. Vessel Typology
*Kappal Sattiram* catalogues an evolutionary spectrum of watercraft adapted to distinct aquatic ecosystems:
1. **Kattumaram (*கட்டுமரம்*)**: Log raft utilizing wave-piercing twin/multi-hull hydrodynamics; unsinkable in extreme surf.
2. **Thoni / Valla (*தோணி / வள்ளம்*)**: Canoe and coastal skiff for harbor lighterage and estuarine transit.
3. **Padagu (*படகு*)**: Open-decked transport craft for riverine and sheltered coastal transport.
4. **Kalam (*கலம்*)**: High-capacity coastal cargo vessel equipped with single central mast and steering oars.
5. **Vangam (*வங்கம்*)**: Intermediate ocean sailing craft capable of navigating the Palk Strait and Sri Lankan routes.
6. **Navai & Perum-Navai (*நாவாய் / பெருநாவாய்*)**: Majestic multi-masted trans-oceanic flagship with multiple decks, passenger cabins, cargo holds, and towering sails.

---

## 5. Epigraphical & Archaeological Verification
The principles recorded in *Kappal Sattiram* are confirmed across numerous epigraphical and archaeological discoveries:
- Sangam poems (*Akananuru*, *Purananuru*, *Maduraikkanchi*).
- Thanjavur and Karandai inscriptions of Rajendra Chola I describing the multi-decked warships of the 1025 CE Srivijaya armada.
- Ship depictions on Satavahana and Salankayana lead coins found on the Coromandel coast showing twin masts and steering oars.
- Excavated hull timbers and coir caulking at Poompuhar underwater explorations.
"""
    },
    {
        "category": "texts",
        "slug": "text-maduraikkanchi-oceanic-navai",
        "file": "text-maduraikkanchi-oceanic-navai.md",
        "node_type": "text",
        "name_en": "Maduraikkanchi: Towering Ocean Navai, Cloud-Sails & Harbor Beacon Lighthouses",
        "name_ta": "மதுரைக்காஞ்சி - பெருங்கடல் நாவாய், மேகப் பாய்கள் மற்றும் கலங்கரை விளக்கங்கள்",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "Poetic masterwork by Mangudi Maruthanar in the Pathupattu canon providing monumental eyewitness descriptions of ancient Tamil trans-oceanic maritime commerce. Depicts giant multi-decked Navai ships with tall masts resembling mountain peaks and billowing cloud-like sails anchored in deep coastal roadsteads, lighterage fleets of Thoni boats ferrying imported horses, Roman gold, and precious goods ashore, and towering harbor beacon lighthouses (Maada-oll-eri / Kalamkarai-vilakkam) burning sweet-smelling oil to guide nocturnal navigation.",
        "summary_ta": "பத்துப்பாட்டில் மாங்குடி மருதனாரால் இயற்றப்பட்ட மதுரைக்காஞ்சியில் காணப்படும் சர்வதேசக் கடல் வணிகம் மற்றும் துறைமுகப் பொலிவு பற்றிய விவரிப்பு. மலைபோன்ற உயர்ந்த பாய்மரங்களையும் மேகங்கள் போன்ற பரந்த பாய்களையும் கொண்ட பெரும் நாவாய்கள் ஆழ்கடல் நங்கூரத் தளங்களில் நிற்பதும் (குன்று குயிற்றன்ன கூம்பொடு மீப்பாய்), அவற்றிலிருந்து சிறிய தோணிகள் மூலம் குதிரைகள், ரோமானியப் பொன் முதலான செல்வங்கள் கரையேற்றப்படுவதும், இரவில் திசைதெரியாது அலையும் கலங்களுக்கு வழிகாட்ட உயர்ந்த மாடங்களில் நறுமண நெய்யிட்டு எரியும் கலங்கரை விளக்கங்களும் (மாட ஒள் எறி) விரிவாகப் பதிவு செய்யப்பட்டுள்ளன.",
        "content": """# Maduraikkanchi: Towering Ocean Navai & Harbor Beacons (மதுரைக்காஞ்சி நாவாய்)

**Author**: Mangudi Maruthanar (*மாங்குடி மருதனார்*).  
**Patron**: Pandyan King Nedunchezhiyan of Thalaiyalanganam.  
**Corpus**: *Pathupattu* (Ten Idylls) Canon.  
**Historical Horizon**: ~50 – 200 CE (Sangam Early Historic Era).  
**Geographical Focus**: Pandyan Ports (*Korkai, Alagankulam, Poompuhar*).  

---

## 1. Classical Verses on the Ocean-Going Navai
In *Maduraikkanchi* (lines 375–385 and 536–544), Mangudi Maruthanar offers an extraordinary poetic portrait of international oceanic shipping in ancient Tamilakam:

> *"குன்று குயிற்றன்ன கூம்பொடு மீப்பாய்*  
> *வெண்திரைப் பெருங்கடல் வீங்குவளி கொளீஇ*  
> *நிரம்பா நாவாய் வரம்பில் வங்கம்..."*  
> *(மதுரைக்காஞ்சி 375–377)*  

**Translation**:  
"Ships whose tall masts resembled carved mountain peaks, carrying immense sails billowing under the surging gale-force winds of the white-capped ocean—limitless fleets of massive *Navai* and deep-sea *Vangam* vessels..."

---

## 2. Deep-Draft Logistics & Lighterage Operations
Because of their enormous physical size, multi-deck construction, and deep vertical draft (*Aazham*), these trans-oceanic *Perum-Navai* merchantmen could not pull directly up to the shallow sandy shoreline or shallow river wharves.

*Maduraikkanchi* describes the harbor logistics:
- Giant ocean vessels dropped multi-fluked stone or iron anchors (*Nanguram*) in deep offshore roadsteads (*Kadal-thurai*).
- Specialized shallow-draft skiffs (*Thoni* and *Valla*) moved back and forth between ship and shore.
- These lighterage vessels ferried valuable cargoes:
  - Splendid spirited warhorses (*Kudhirai*) imported from Arabia and Persia.
  - Amphorae of Mediterranean wine and stacks of Roman imperial gold aurei.
  - Heavy bales of export commodities: black pepper (*Kariyuppu*), fine muslins (*Aruvai*), Korkai pearls, and Kodumanal beryls.

---

## 3. Harbor Beacon Lighthouses (*Kalamkarai-Vilakkam* / *Maada-Oll-Eri*)
Navigating the shallow, reef-strewn Coromandel and Gulf of Mannar coasts on stormy, moonless nights required sophisticated coastal navigational aids. *Maduraikkanchi* and parallel Sangam texts (*Perumpanarruppadai* lines 349–351) document the architecture of ancient Tamil harbor lighthouses:

- **Structure**: Multi-tiered brick masonry towers (*Maadam*) erected on prominent headlands or river mouths.
- **Illumination**: Large ceramic or bronze fire-bowls fueled by sweet-smelling wood resins, sesame oil, and camphor, creating blazing white-yellow beacon fires (*Maada-oll-eri*).
- **Function**: Visible over several nautical leagues out at sea, warning approaching navigators of dangerous fringing sandbars while guiding them directly into the safe, deep navigable channels of the harbor basin.

---

## 4. Civilizational & Economic Significance
The nautical descriptions of *Maduraikkanchi* confirm that Sangam Tamil ports operated as highly organized commercial gateways with dedicated customs houses, harbormasters (*Thuraimuga-athikarigal*), maritime warehouse complexes, and night beacon infrastructure matching Alexandria, Rome, and Guangzhou.
"""
    },
    {
        "category": "texts",
        "slug": "text-purananuru-kulamutrathu-killivalavan-navy",
        "file": "text-purananuru-kulamutrathu-killivalavan-navy.md",
        "node_type": "text",
        "name_en": "Purananuru: Maritime Armada & Coastal Expeditions of Chola King Killivalavan",
        "name_ta": "புறநானூறு - குளமுற்றத்துத் துஞ்சிய கிள்ளிவளவனின் கடற்படை மற்றும் கடலாதிக்க வெற்றிகள்",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 200,
        "thinai": "Neithal",
        "summary_en": "Celebrated heroic verses from the Purananuru anthology (poems 35, 37, and 39) composed by court bards Maruthuvan Dhamodharanaar and Kovur Kizhar in honor of the Chola monarch Kulamutrathu Thunjiya Killivalavan. The poems describe an offensive early Chola navy (Kadal-padai) whose forest-like tall masts dominated the horizon, subduing sea pirates, securing merchant convoys across the churned ocean breakers (Thirai-poru perunkadal), and enforcing naval hegemony over coastal principalities from Poompuhar to northern Sri Lanka.",
        "summary_ta": "புறநானூற்றில் மருத்துவன் தாமோதரனார் மற்றும் கோவூர் கிழார் ஆகிய சங்கப் புலவர்களால் பாடப்பட்ட சோழ வேந்தன் குளமுற்றத்துத் துஞ்சிய கிள்ளிவளவனின் கடற்படைப் பெருமை (பாடல்கள் 35, 37, 39). கடலில் திரண்டு நின்ற அவனது போர்க்கப்பல்களின் பாய்மரங்கள் பெருங்காடு போலக் காட்சியளித்ததும், அலைமோதும் பெருங்கடலில் (திரைப் பொரு பெருங்கடல்) கடற்கொள்ளையர்களை ஒடுக்கி, கடற்படை கொண்டு எதிரித் துறைமுகங்களை வென்று, பூம்புகார் முதல் இலங்கை வரையிலான கடல்வழிகளில் சோழரின் இறையாண்மையை நிலைநாட்டிய வரலாற்றுப் பதிவு.",
        "content": """# Purananuru: Killivalavan's Naval Armada (புறநானூறு கிள்ளிவளவன் கடற்படை)

**Poets**: Maruthuvan Dhamodharanaar (*மருத்துவன் தாமோதரனார்*) & Kovur Kizhar (*கோவூர் கிழார்*).  
**Monarch**: Chola King Kulamutrathu Thunjiya Killivalavan (*குளமுற்றத்துத் துஞ்சிய கிள்ளிவளவன்*).  
**Anthology**: *Purananuru* (*புறநானூறு* – Poems 35, 37, 39).  
**Historical Horizon**: ~100 – 200 CE (Sangam Early Historic Era).  
**Theme**: Imperial Thalassocracy & Sovereign Maritime Naval Defense (*கடலாதிக்கம்*).  

---

## 1. Classical Verses on Royal Fleet Power
In *Purananuru* 35, Maruthuvan Dhamodharanaar glorifies the overwhelming visual spectacle and tactical dread inspired by Killivalavan's imperial war fleet assembled along the Coromandel shoreline:

> *"திரைபொரு பெருங்கடல் வரைமணல் காறும்*  
> *மரம்பயில் கூம்பொடு நாவாய் தோன்றி...*  
> *வான்தோய் வெல்கொடி மாமிரை மலிந்து..."*  
> *(புறநானூறு 35)*  

**Translation**:  
"Unto the white sandy limits where the surging breakers churn against the shore, war-ships (*Navai*) with tall masts appearing like a dense, towering forest ride the waves... their victory flags flying high into the heavens..."

---

## 2. Early Chola Blue-Water Naval Warfare
Killivalavan's reign marks a critical transition in ancient South Asian history: the deliberate institutionalization of an offensive state navy (*Kadal-padai*):
- **Anti-Piracy Operations**: Securing international shipping lanes in the Bay of Bengal and Gulf of Mannar against predatory sea rovers and coastal raiders.
- **Amphibious Siege Warfare**: Deploying naval combatants to execute amphibious landings against rebellious deltaic chieftains (*Velir*) and the northern coasts of Eelam (Sri Lanka).
- **Coromandel Fleet Dominance**: Maintaining permanent naval garrisons at Kaveripoompattinam (Poompuhar) and Nagapattinam to protect incoming Yavana (Greco-Roman), Arab, and Southeast Asian merchant flotillas.

---

## 3. Marine Combatants & Tactical Fleet Operations
*Purananuru* celebrates the amphibious martial caste (*Kadal-maravar* / *Thirai-veerar*):
- Fighters trained in swimming, naval boarding, and balancing on wet, rolling decks during storms.
- Fleet coordination using high-visibility standard-bearer pennants (*Kodi*) mounted on the central mast (*Perum-koombu*) and signal conches (*Valampuri-sanghu*).
- Killivalavan's fleet established maritime safe havens that allowed Tamil civilization to control Indian Ocean trade centuries before the Imperial Chola armadas of Rajaraja I and Rajendra I.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thanjavur-rajendra-naval-expedition",
        "file": "insc-thanjavur-rajendra-naval-expedition.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Brihadisvara Plinth Inscription: Rajendra Chola I's 1025 CE Srivijaya Naval Conquest",
        "name_ta": "தஞ்சாவூர் பிரகதீஸ்வரர் கோயில் பீடக் கல்வெட்டு - முதலாம் இராசேந்திர சோழனின் 1025 கடாரக் கடற்படைப் படையெடுப்பு",
        "era": "Imperial Chola Era",
        "year_start": 1025,
        "year_end": 1030,
        "thinai": "Neithal",
        "summary_en": "Monumental royal epigraph engraved on the south wall granite plinth of the Thanjavur Brihadisvara Temple recording Emperor Rajendra Chola I's historic 1025 CE trans-oceanic naval expedition across the Bay of Bengal. Contains the immortal Meikeerthi detailing the deployment of a massive war fleet across the churning ocean, the naval blockade and capture of the Srivijayan capital of Palembang, the capture of King Sangrama Vijayottungavarman with his royal elephant corps, and the conquest of 14 strategic maritime city-states across Sumatra, the Malay Peninsula, and Thailand.",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயிலின் தென்புறக் கருங்கல் பீடத்தில் பொறிக்கப்பட்டுள்ள முதலாம் இராசேந்திர சோழனின் வரலாற்றுப் புகழ்மிக்க 1025-ஆம் ஆண்டுக் கடாரப் படையெடுப்புக் கல்வெட்டு. 'அலைகடல் நடுவுள் பலகலம் செலுத்தி...' என்று தொடங்கும் இதன் மெய்க்கீர்த்தி, வங்கக் கடலைக் கடந்து சென்று ஸ்ரீவிஜயப் பேரரசின் தலைநகரான பாலெம்பாங்கை வீழ்த்தியதும், அரசன் சங்கிராம விஜயோத்துங்கவர்மனைப் போர்க்களத்தில் சிறைபிடித்ததும், மற்றும் மலேசியா, சுமத்ரா, தாய்லாந்துப் பகுதிகளில் அமைந்த 14 முக்கிய கடல்வழி துறைமுக நகரங்களை வெற்றி கொண்டு சோழப் பேரரசின் கடலாதிக்கத்தை நிலைநாட்டிய வியத்தகு வரலாற்றைப் பதிவு செய்கிறது.",
        "content": """# Thanjavur Inscription: Rajendra Chola's 1025 CE Srivijaya Naval Expedition

**Location**: South wall of the Vimana plinth, Brihadisvara Temple, Thanjavur (*தஞ்சைப் பெருவுடையார் கோயில் தெற்குச் சுவர் பீடம்*).  
**Sovereign**: Emperor Rajendra Chola I (*முதலாம் இராசேந்திர சோழன்*), *Kadaram-kondan*.  
**Date**: 1025 – 1030 CE (Regnal Year 14).  
**Epigraphical Classification**: Royal Prasasti / *Meikeerthi* in Classical Tamil Grantha/Tamil script.  
**Related Epigraphs**: Karandai (Tanjore) Plates & Thiruvalangadu Copper Plates.  

---

## 1. The Immortal Meikeerthi Text
The south wall of the Thanjavur Vimana preserves the canonical naval *Meikeerthi* composed by royal court chroniclers to immortalize the trans-oceanic victory:

> *"அலைகடல் நடுவுள் பலகலம் செலுத்திச்*  
> *சங்கிராம விசையோத்துங்க வர்மனாகிய கடாரத் தரசனை*  
> *வாகையும் பொழிற்கடலும் வளைகடல் அடைத்து*  
> *கலையமர் மாக்கடல் நடுவுள் பலகலம் செலுத்தி..."*  

### Literal Translation & Historical Meaning:
"Dispatching many ships across the billowing ocean, trapping King Sangrama Vijayottungavarman of Kadaram together with his war elephants in the midst of his fortified capital surrounded by the ocean; capturing his royal treasures, the jeweled gates (*Vidhyadhara Torana*), and subjugating the strategic kingdoms across the eastern seas..."

---

## 2. The 14 Conquered Maritime Polities
The inscription enumerates fourteen fortified maritime city-states and ports systematically captured by the Chola armada:

| Inscriptional Name | Modern Geographic Identification | Strategic Maritime Function |
|:---|:---|:---|
| **Sri Vijaya** | Palembang, Southern Sumatra, Indonesia | Imperial Capital of Srivijaya Empire |
| **Pannai** | Panai / Pane, East Coast of Sumatra | Naval port guarding the Barumun River basin |
| **Malaiyur** | Jambi, Batang Hari River, Sumatra | Strategic pepper & gold emporium |
| **Mayirudingam** | Beruas / Manjung, Perak, Malaysia | Fortified tin port on Malacca Strait |
| **Ilangasogam** | Langkasuka, Patani / Kedah Border | Trans-peninsular portage emporium |
| **Mappappalam** | Southern Kra Isthmus / Patalung | Deep freshwater naval supply station |
| **Mevilimbangam** | Karmaranga / Ligor Isthmus | Strategic passage port |
| **Valaippanduru** | Panduranga / Phan Rang (Vietnam border) | Outlying naval surveillance point |
| **Talaittakkolam** | Takua Pa, West Coast of Thailand | Prime entry point for trans-peninsular portage |
| **Madamalingam** | Tambralinga / Nakhon Si Thammarat | Gulf of Thailand transit hub |
| **Ilamuri-desam** | Lamuri / Aceh, Northern Sumatra | Western gateway to the Malacca Straits |
| **Manakkavaram** | Great & Car Nicobar Islands | Ocean staging depot and freshwater base |
| **Kadaram** | Bujang Valley / Kedah, Malaysia | Key fortified port below Mount Jerai |

---

## 3. Naval Logistics & Armada Organization
The scale of the 1025 CE expedition was unprecedented in Indian Ocean history:
1. **Fleet Size**: Modern naval historians estimate a fleet of several hundred *Perum-Navai* warships, auxiliary cargo transports, and amphibious landing barges.
2. **Transit**: Crossing the open waters of the Bay of Bengal over 3,000 kilometers utilizing the Southwest Monsoon winds (*Thenmerku Paruva-kaatru*).
3. **Staging**: Fleet rendezvous and fresh water replenishment at the Andaman and Nicobar Islands (*Manakkavaram*).
4. **Coordinated Multi-Pronged Strike**: Rather than a single engagement, the fleet split into squadrons, executing simultaneous amphibious assaults on Palembang in the south and Kedah in the north, paralyzing Srivijaya's ability to concentrate its naval reserves.

---

## 4. Geopolitical & Civilizational Legacy
The expedition was not an imperial territorial annexation, but an offensive punitive and trade-emancipation campaign:
- **Dismantling Toll Monopoly**: Srivijaya had imposed punitive tariffs and forced harbor dues on all vessels passing through the Malacca and Sunda straits.
- **Direct Trade with Song China**: Chola merchant missions (*Ainnurruvar* and *Manigramam*) gained unimpeded access to Guangzhou (Canton), Quanzhou, and the South China Sea.
- **Cultural Diffusion**: Solidified Tamil epigraphical, architectural, and religious influence across Southeast Asia for over three centuries.
"""
    },

    # --------------------------------------------------------------------------
    # 2. CONCEPTS: ANATOMY, HYDRODYNAMICS, DOCKYARDS & TACTICS
    # --------------------------------------------------------------------------
    {
        "category": "concepts",
        "slug": "concept-kappal-anatomy-and-rigging",
        "file": "concept-kappal-anatomy-and-rigging.md",
        "node_type": "concept",
        "name_en": "Kappal Architecture: Structural Anatomy, Rigging & Indigenous Nautical Engineering",
        "name_ta": "கப்பல் கட்டமைப்பு - தமிழரின் மரக்கல உடற்கூறியல், பாய்மரக் கயிறுகள் மற்றும் கப்பற்கலை நுட்பங்கள்",
        "era": "Sangam to Imperial Chola Era",
        "year_start": 100,
        "year_end": 1300,
        "thinai": "Neithal",
        "summary_en": "Comprehensive technical architecture of ancient Tamil ocean-going vessels codifying indigenous terminology and engineering components. Covers the structural spine (Adimaram keel, stem/stern posts), internal framing (Vangu ribs), hull planking (Pathagai strakes), mast configurations (Perum-koombu mainmast, foremast, and mizzen), treated cotton canvas sail systems (Paai / Meepai), dual steering oars and axial rudders (Sukkan), coir standing and running rigging (Vadathu), stone/iron anchors (Nanguram), and bilge management (Thoombu).",
        "summary_ta": "பண்டைத் தமிழகப் பெருங்கப்பல்களின் கட்டமைப்பு உடற்கூறியல், கலைச்சொற்கள் மற்றும் கப்பற்கலை நுட்பங்களின் விரிவான தொகுப்பு. அடித்தள மரமான அடிமரம் (கீல்), முன்னாணி மற்றும் பின்னாணி மரங்கள், பக்கவாட்டு வங்கு மரங்கள் (ரிப்கள்), பலகைக் கூட்டு (பதாகை), பாய்மரங்கள் (பெருங்கூம்பு, அனியக் கூம்பு), பருத்தி மற்றும் மீனெண்ணெய் பதனிட்ட பாய்கள் (மீப்பாய்), சுக்கான் (திசைதிருப்பி), தென்னங்கயிற்று வடங்கள், நங்கூர அமைப்புகள், மற்றும் நீர் வெளியேற்றும் தும்புகள் பற்றிய நுட்பமான கலைச்சொல் களஞ்சியம்.",
        "content": """# Kappal Architecture: Structural Anatomy & Rigging (கப்பல் கட்டமைப்பு)

**Domain**: Indigenous Nautical Architecture & Naval Engineering (*பண்டைத் தமிழரின் கப்பற்கலை*).  
**Operational Eras**: Sangam, Pallava, Pandyan, and Imperial Chola Eras (~300 BCE – 1300 CE).  
**Maritime Ecosystem**: Indian Ocean, Bay of Bengal, Arabian Sea, and South China Sea.  

---

## 1. Classical Hull Architecture & Anatomical Glossary
Ancient Tamil shipwrights possessed a remarkably precise vocabulary for every component of an ocean vessel (*Kalam* / *Navai*):

```
                       [Perum-koombu (Mainmast)]
                                |
                   +------------+------------+
                   |                         |
               [Meepai (Sail)]           [Meepai (Sail)]
                   |                         |
         ============================================= [Thattu (Deck)]
        \    [Pathagai (Hull Planks)]                /
         \   [Vangu / Kura-maram (Internal Ribs)]    /
          \                                         /
           \-------[Adimaram / Erakku (Keel)]------/
```

### Anatomical Components:
1. **Adimaram / Erakku (*அடிமரம் / எரக்கு*) – The Keel**:
   - The primary structural timber running along the centerline of the hull bottom.
   - Sawn from single massive logs of aged Teak or Rosewood, providing the foundational backbone resisting vertical hogging and sagging bending stresses.
2. **Aniyathu-maram / Mun-maram (*அனியத்து மரம் / முன்மரம்*) – Stempost**:
   - Upright forward timber scarphed to the forward end of the keel to form the ship's prow (*Aniyam*).
3. **Pin-maram / Kadasi-maram (*பின்மரம் / கடைசிமரம்*) – Sternpost**:
   - Vertical upright timber scarphed to the after end of the keel supporting the rudder apparatus (*Pinnal*).
4. **Vangu / Kura-maram (*வங்கு / குறமரம்*) – Floor Timbers & Ribs**:
   - Curved timber frames fitted transverse to the keel forming the skeleton of the vessel.
5. **Pathagai (*பதாகை*) – Hull Strakes**:
   - Heavy planks fitted edge-to-edge along the ribs to form the watertight outer skin.
6. **Thattu (*தட்டு*) – Decks**:
   - Multi-level platforms providing living quarters (*Kalam-maadam*), cargo stowage holds (*Kalam-araigal*), and fighting platforms.

---

## 2. Mast Configuration & Sail Aerodynamics
Tamil ocean-going *Perum-Navai* ships carried up to three masts to exploit seasonal monsoon winds:
- **Perum-koombu (*பெருங்கூம்பு*)**: The tall central mainmast.
- **Aniya-koombu (*அனியக் கூம்பு*)**: The foremast tilted slightly forward over the prow to maintain directional stability.
- **Pin-koombu (*பின் கூம்பு*)**: The mizzenmast on the quarterdeck for maneuvering trim.

### Sail Chemistry & Fabric (*Paai* / *Meepai*)
- Woven from heavy multi-ply indigenous *Karunganni* cotton yarn.
- Treated with boiled bark decoctions (*Kadukkai* tannin extract) and castor/fish oil to resist mold, mildew, and salt-crust stiffening while maintaining aerodynamic impermeability.

---

## 3. Steering & Ground Tackle
1. **Sukkan (*சுக்கான்*) & Pani-p-pidi (*பணிப்பிடி*)**:
   - Heavy quarter-mounted steering oars (*Kadaasi-thuzhavu*) and axial stern-post rudders controlled via long tiller arms (*Thandaval*).
2. **Nanguram (*நங்கூரம்*)**:
   - Stone anchors (*Kal-nanguram*) carved from dense granite blocks with cross-holes for wooden flukes.
   - Forged wrought-iron anchors (*Irumby-nanguram*) with twin hooked flukes and lead-weighted stocks for biting into muddy estuarine bottoms.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kattumaram-and-twin-hull-hydrodynamics",
        "file": "concept-kattumaram-and-twin-hull-hydrodynamics.md",
        "node_type": "concept",
        "name_en": "Kattumaram Hydrodynamics: Twin-Hull Stability, Wave-Piercing & Outrigger Mechanics",
        "name_ta": "கட்டுமரம் பாய்மவியல் - இரட்டை மேலோட்டு நிலைத்தன்மை, அலைபிளக்கும் திறன் மற்றும் பக்கக்கட்டை நுட்பங்கள்",
        "era": "Sangam to Modern Era",
        "year_start": 300,
        "year_end": 1300,
        "thinai": "Neithal",
        "summary_en": "Scientific breakdown of the hydrodynamic principles underlying the indigenous Tamil Kattumaram (etymological origin of the global term Catamaran: Kattu 'bound' + Maram 'timber'). Explores how multi-log and twin-hull designs achieve extraordinary metacentric stability, wave-piercing hydrodynamics through breaker zones without broaching, unsinkability through solid timber buoyancy, and outrigger balance (Pakka-k-kattai), forming the conceptual foundation for modern multihull naval architecture.",
        "summary_ta": "உலகளாவிய 'கட்டமரான்' (Catamaran) சொல்லின் மூலமான தமிழரின் கட்டுமரத்தின் பாய்மவியல் (ஹைட்ரோடைனமிக்ஸ்) கோட்பாடுகள். கட்டு (கட்டப்பட்ட) + மரம் (மரக்கட்டைகள்) என்ற அமைப்பில் உருவான இதன் இரட்டை மேலோட்டு நிலைத்தன்மை (மெட்டாசென்ட்ரிக் நிலைப்பு), அலைகளைப் பிளந்து செல்லும் கூர்மை, கொந்தளிப்பான கடலிலும் கவிழாத பக்கக்கட்டை (அவுட்ரிக்கர்) நுட்பம், மற்றும் திடமரங்களின் மிதப்புத்தன்மையால் எக்காலத்தும் மூழ்காத தன்மை ஆகியவை நவீன இரட்டை மேலோட்டுக் கப்பல் கட்டுமானத்தின் முன்னோடி அறிவியலாக விளங்குவதை விளக்கும் ஆய்வு.",
        "content": """# Kattumaram Hydrodynamics & Twin-Hull Architecture (கட்டுமரம் பாய்மவியல்)

**Indigenous Origin**: Tamil Coastal Fisherfolk & Marine Shipwrights (*பரதவர் மற்றும் கடலோடிகள்*).  
**Etymology**: Classical Tamil *Kattu* (கட்டு – tied/bound) + *Maram* (மரம் – timber/logs) $\rightarrow$ English *Catamaran*.  
**Core Scientific Principles**: High Metacentric Height ($GM$), Wave-Piercing Hydrodynamics, Unsinkable Positive Buoyancy.  

---

## 1. Etymological & Historical Genesis
The English word **Catamaran** directly derives from the Tamil term **Kattumaram** (*கட்டுமரம்*). When early Portuguese, Dutch, and British mariners encountered Coromandel seafarers in the 16th and 17th centuries, they observed with astonishment that native mariners could navigate raging monsoon surf in lightweight, log-fastened craft that traversed waters where deep-keeled European longboats consistently broached, capsized, and foundered.

---

## 2. Hydrodynamic Principles of the Kattumaram

```
      Wave Direction --->   [Wave-Piercing Prow]
                           /   /   /   /   /
       +=========================================+
       |   Oram-maram (Outboard buoyant log)     |
       +=========================================+  <--- Multi-log raft
       |   Nadumaram (Centerline load log)       |        tied with coir
       +=========================================+
       |   Oram-maram (Outboard buoyant log)     |
       +=========================================+
```

### A. Metacentric Height ($GM$) & High Initial Stability
In single-hull monohull vessels, resistance to capsizing depends on ballast weight deep in the keel. In contrast, the *Kattumaram* achieves massive initial stability strictly through geometric form:
$$GM = KB + BM - KG$$
By distributing the water-plane area across separated outboard buoyant timbers (*Oram-maram*), the second moment of area of the water-plane ($I_T$) is dramatically increased:
$$BM = \frac{I_T}{\nabla}$$
This yields an immense transverse righting moment at even small heel angles, making accidental capsizing under wind or wave pressure physically nearly impossible.

### B. Wave-Piercing Hydrodynamics & Surf Landing
Unlike blunt-bowed monohull boats that slam into incoming breakers—creating huge slamming forces and swamping risks—the forward logs of a *Kattumaram* are hewn with an upward rake (*Kombu*):
- The sharpened logs cut directly through incoming waves (*Wave-piercing action*), shedding green water instantly across open log interstices.
- When surfing shoreward through violent surf zones (*Alai-mundu*), the craft maintains high dynamic directional stability without broaching (spinning broadside to the breakers).

### C. Inherent Unsinkability
Because the *Kattumaram* is constructed from solid, highly buoyant tropical timbers (*Albizia stipulata* / *Mullu-murukku* and *Erythrina indica*) fastened with elastic coir ropes, it contains no hollow hull envelope that can be punctured or flooded:
- Even if completely submerged by a breaking ocean wave, the vessel immediately pops back to the surface due to permanent positive displacement buoyancy.

---

## 3. Outrigger Mechanics (*Pakka-k-Kattai* / *Oruva*)
For larger ocean-going fishing and scouting vessels, Tamil shipwrights added single or double outrigger floats (*Pakka-k-kattai*) suspended on flexible wooden crossbeams (*Thandu*):
- The outrigger serves as a dynamic counterweight.
- On the windward side, it acts as a stabilizing weight resisting heel; on the leeward side, it provides buoyant displacement preventing overturning.
- This engineering logic enabled ancient Tamil navigators to cross wide oceanic spans across the Bay of Bengal and Gulf of Mannar with maximum speed and negligible displacement resistance.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-naval-warfare-and-tactics",
        "file": "concept-naval-warfare-and-tactics.md",
        "node_type": "concept",
        "name_en": "Ancient Tamil Naval Warfare: Formations, Shock Tactics & Boarding Marines",
        "name_ta": "பண்டைத் தமிழர் கடற்போர் முறைமைகள் - வியூகங்கள், மோதும் உத்திகள் மற்றும் கடற்படைப் போரணி",
        "era": "Sangam to Imperial Chola Era",
        "year_start": 100,
        "year_end": 1100,
        "thinai": "Neithal",
        "summary_en": "Comprehensive military doctrine of ancient and medieval Tamil naval warfare. Analyzes fleet tactical formations (Crescent Pirai-ani, Wedge Sula-ani, Line ahead), offensive naval weapon systems (bronze-sheathed ramming prows Amparam, incendiary fire-pots Thee-panai, catapult ballistae, grapple-hooks Kavvu-mull), the tactical deployment of elite marine shock troops (Kadal-maravar), weather-gage wind maneuvering, and coordinated amphibious landings.",
        "summary_ta": "பண்டைத் தமிழக அரசுகளின் கடற்போர் உத்திகள் மற்றும் படைக்கலப் பயன்பாடுகளின் முழுமையான ஆய்வு. போர்க்கப்பல்களின் அணிவகுப்பு வியூகங்கள் (பிறையணி, சூலவணி, நேரணி), கப்பல் மோதல் கருவிகள் (அம்பாரம் - உலோக மூக்கு), தீப்பம்புகள் மற்றும் எரியும் குண்டுகள் (தீப்பனை, எரியம்பு), பகை மரக்கலங்களை இழுத்துப் பிடிக்கும் கவ்வுமுள்ளுகள், கடற்படை மறவர்களின் (கடல் மறவர்) நேரடிப் போரிடும் உத்திகள், மற்றும் கடற்கரைத் தரையிறக்கத் தாக்குதல் முறைமைகள்.",
        "content": """# Ancient Tamil Naval Warfare & Tactics (பண்டைத் தமிழர் கடற்போர் முறைமைகள்)

**Military Domain**: Maritime Strategy, Tactical Fleet Formations & Amphibious Assault (*கடற்போர் மரபு*).  
**Operational Dynasties**: Early Historic Cholas & Pandyas, Medieval Imperial Cholas (*இராசராசன், இராசேந்திரன்*).  
**Key Weapons**: Ramming Prow (*Amparam*), Incendiary Fire Pots (*Thee-panai*), Grappling Hooks (*Kavvu-mull*).  

---

## 1. Naval Command Structure & Doctrine
The naval military doctrine of the Tamil empires (*Kadal-por Neri*) was governed by an organized hierarchy under the supreme command of the sovereign (*Kadal-vendaan*) and his Grand Admiral (*Kadal-padai Thalapathi* / *Samudra-senathipathi*). The fleet operated as an autonomous branch of the armed forces with dedicated officers overseeing navigation (*Malu-nayagan*), marine infantry (*Kadal-maravar*), and ordnance supply.

---

## 2. Fleet Battle Formations (*Padai-Viyugam*)

```
             [Sula-ani: Trident / Wedge Formation]
                           /\
                          /  \
                         /    \
                       [Flagship]
                        /      \
                       /        \
                      /          \
            [Wing Squadron]    [Wing Squadron]

             [Pirai-ani: Crescent Envelopment Formation]
                    (           )
                     (         )
                      (   x   )  <--- Enemy Fleet trapped in concave crescent
```

1. **Pirai-ani (*பிறையணி*) – Crescent Envelopment**:
   - The battle fleet formed a wide concave arc extending wings forward to wrap around an opposing convoy or fleet.
   - Purpose: To deny the enemy room to maneuver, compressing their ships together where they fouled each other's oars and collided.
2. **Sula-ani (*சூலவணி*) – Trident / Flying Wedge**:
   - Heavily armored flagship and ram-equipped battleships formed a concentrated wedge point designed to pierce the center of the enemy line.
   - Purpose: Breaking enemy fleet cohesion and isolating command vessels.
3. **Ner-ani (*நேரணி*) – Line Ahead / Column**:
   - Utilized when running parallel to hostile shorelines or conducting offshore archer bombardment.

---

## 3. Naval Weapon Systems & Tactics
Tamil naval warfare prioritized close-quarters shock combat and boarding actions:

1. **Amparam / Mookku-maram (*அம்பாரம் / மூக்குமரம்*) – Ramming Prow**:
   - The stempost was reinforced with massive timber beams sheathed in cast bronze or wrought iron, protruding just below or at the waterline.
   - Tactic: Striking the enemy vessel amidships at maximum rowing speed to crush hull strakes, causing catastrophic water ingress.
2. **Thee-panai & Thee-ambu (*தீப்பனை & தீயம்பு*) – Incendiary Projectiles**:
   - Terracotta pots filled with boiling vegetable pitch, sulfur, and naphtha thrown via deck catapults (*Kalthoongi / Yanthiram*) onto enemy decks and canvas sails.
   - Archery corps fired whistling arrows tipped with oil-soaked burning fibers to ignite dry rigging.
3. **Kavvu-mull (*கவ்வுமுள்*) – Iron Grappling Hooks**:
   - Four-pointed iron grapple claws fastened to heavy hemp ropes thrown across gunwales to lock hulls together for boarding.

---

## 4. Elite Marine Shock Troops (*Kadal-Maravar*)
Once ships were locked together, combat was decided by the *Kadal-maravar* (*கடல் மறவர்*):
- Armament: Short stabbing swords (*Kuriya-vaal*), heavy curved daggers, throwing clubs (*Valari*), and water-hardened buffalo-hide shields.
- Training: Exceptional swimming endurance, underwater sabotage (cutting enemy anchor cables and boring holes in enemy hulls with augers), and fierce deck clearing.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-nagapattinam-chola-naval-dockyards",
        "file": "concept-nagapattinam-chola-naval-dockyards.md",
        "node_type": "concept",
        "name_en": "Nagapattinam Imperial Naval Dockyards: Slipways, Seasoning Yards & Fleet Logistics",
        "name_ta": "நாகப்பட்டினம் சோழர் கப்பல் கட்டும் தளம் - உலர் தளங்கள், மரப் பதனிடு கூடம் மற்றும் கடற்படை வழங்கல்",
        "era": "Imperial Chola Era",
        "year_start": 950,
        "year_end": 1250,
        "thinai": "Neithal",
        "summary_en": "Detailed engineering analysis of the Imperial Chola naval dockyards and naval arsenal at Nagapattinam on the Coromandel coast. Details the tidal slipways and dry-dock mud berms along the Kaduvaiyar and Vettar rivers, brackish water timber seasoning basins protecting wood from marine shipworms (Teredo navalis), sail-lofts, coir cordage rope-walks, naval foundries, and maritime logistical supply chains that sustained Rajendra Chola I's trans-oceanic armada.",
        "summary_ta": "நாகப்பட்டினத்தில் அமைந்திருந்த சோழப் பேரரசின் பிரம்மாண்டக் கப்பல் கட்டும் தளம், உலர் தளங்கள் மற்றும் ஆயுதக் கிடங்குகளின் பொறியியல் ஆய்வு. கடுவையாறு மற்றும் வெட்டாற்று முகத்துவாரங்களில் அமைந்த ஓதக் கப்பல் இறங்குதளங்கள், கப்பல் மரங்களை உப்புநீரில் ஊறவைத்து கடல்புழுக்களிடமிருந்து காக்கும் மரப் பதனிடு குளங்கள், பாய் தைக்கும் கூடங்கள், கயிறு திரிக்கும் நீண்ட களங்கள் மற்றும் 1025-ஆம் ஆண்டுக் கடாரப் படையெடுப்புக்குத் தேவையான பிரம்மாண்டக் கடற்படையை உருவாக்கிய உற்பத்தித் தளங்களின் செயல்முறை விளக்கம்.",
        "content": """# Nagapattinam Imperial Chola Naval Dockyards (நாகப்பட்டினம் கப்பல் தளம்)

**Location**: Estuary of Kaduvaiyar & Vettar Rivers, Nagapattinam (*நாகப்பட்டினம் முகத்துவாரம்*).  
**Patron Dynasty**: Imperial Chola Empire (*இராசராசன், முதலாம் இராசேந்திரன்*).  
**Operational Era**: ~950 – 1250 CE.  
**Strategic Function**: Imperial Blue-Water Naval Arsenal, Dry Docks & Ship Construction Center.  

---

## 1. Topographic & Estuarine Advantage
Nagapattinam was selected by the Chola imperial administration as their primary naval base due to extraordinary natural advantages:
- **Sheltered Estuarine Basin**: The convergence of the Kaduvaiyar and Vettar rivers created deep, protected inland waterways sheltered from open Bay of Bengal storm surges.
- **Tidal Fluctuation**: Predictable semi-diurnal tidal cycles allowed large deep-draft ships to be floated into estuarine docks during high spring tides and grounded during low tide for hull maintenance.
- **Proximity to Core Agricultural Base**: Easy riverine transport linking Nagapattinam directly to the agricultural wealth and metallurgical iron centers of the Kaveri delta.

---

## 2. Engineering of Slipways & Dry Docks
1. **Tidal Mud-Berm Docks (*Kappal Thalthum Kalam*)**:
   - Excavated rectangular basins lined with timber piling and baked brick retaining walls.
   - Sluice gates (*Kumizhi / Madagu*) regulated water ingress. A ship in need of repair entered at high tide; the gates were closed, and water was either drained through gravity sluices at low tide or pumped out using waterwheels, leaving the vessel perched securely on timber bilge blocks.
   - Allowed shipwrights to scrape off barnacles, replace rotten strakes (*Pathagai*), and apply fresh hot coats of dammar pitch and lime caulk.
2. **Building Slipways (*Kappal Eka-k-kalam*)**:
   - Inclined earthen ways greased with tallow and vegetable oil down which newly completed hulls slid gently into the river basin.

---

## 3. Timber Seasoning Yards (*Maram Uruthum Poigai*)
Untreated green timber warps and cracks when exposed to ocean waves and is rapidly consumed by marine wood-boring mollusks (*Teredo navalis*).
- Nagapattinam dockyards featured extensive brackish water canals where incoming Teak, Vengai, and Rosewood logs floated submerged for 6 to 12 months.
- This process leached out fermentable starches and saps, replacing them with saline minerals that rendered the seasoned timber virtually impervious to fungal rot and shipworms.

---

## 4. Ancillary Naval Industries
The naval complex housed an entire industrial ecosystem:
- **Cordage Rope-Walks (*Vadathu-kalam*)**: Hundred-meter open sheds where master rope-makers twisted coconut coir fiber into high-tensile three-strand and four-strand anchor cables.
- **Sail-Lofts (*Paai-koodam*)**: Work halls where tailors stitched expansive sails from heavy cotton canvas treated with waterproof resins.
- **Naval Iron Foundries (*Irumby-p-pattarai*)**: Forging iron anchors, grapnels, bolts, and bronze ram fittings.
- **Naval Granaries & Armories (*Padai-kalanja-koodam*)**: Stockpiling dried provisions, freshwater casks, and weapons for overseas campaigns.
"""
    },

    # --------------------------------------------------------------------------
    # 3. HISTORICAL FIGURES & NAVAL COMMANDERS
    # --------------------------------------------------------------------------
    {
        "category": "characters",
        "slug": "char-rajendra-chola-naval-emperor",
        "file": "char-rajendra-chola-naval-emperor.md",
        "node_type": "character",
        "name_en": "Rajendra Chola I: The Ocean Conqueror & Admiral of the Chola Armada",
        "name_ta": "முதலாம் இராசேந்திர சோழன் - கடாரமும் ஈழமும் வென்ற கடற்படைப் பேரரசன்",
        "era": "Imperial Chola Era",
        "year_start": 1014,
        "year_end": 1044,
        "thinai": "Neithal",
        "summary_en": "Architect of the greatest trans-oceanic naval expedition in pre-modern South Asian history. Emperor Rajendra Chola I (r. 1014–1044 CE) assumed the titles Kadaram-kondan and Gangaikonda Cholan, organized the Imperial Chola navy into an invincible blue-water fleet, converted the Bay of Bengal into a 'Chola Lake', launched the 1025 CE maritime conquest of Srivijaya across Sumatra, Malaya, and Thailand, and secured international trade routes between India and Song Dynasty China.",
        "summary_ta": "தெற்காசிய வரலாற்றிலேயே மாபெரும் கடல் கடந்த கடற்படைப் படையெடுப்பை நிகழ்த்திய சோழப் பேரரசன். முதலாம் இராசேந்திர சோழன் (ஆட்சிக் காலம் 1014-1044), 'கடாரம் கொண்டான்', 'கங்கை கொண்ட சோழன்' எனப் புகழ்பெற்றவர்; வங்கக் கடலை 'சோழர் ஏரி'யாக மாற்றிய பெரும் கடற்படை அமைப்பாளர்; 1025-இல் ஸ்ரீவிஜயப் பேரரசின் மீது மின்னல் வேகக் கடற்படைத் தாக்குதல் நடத்தி மலேசியா, சுமத்ரா, தாய்லாந்து துறைமுகங்களை வென்று, தமிழக-சீன வர்த்தகப் பெருவழியைத் திறந்துவைத்த உலக வரலாற்று நாயகன்.",
        "content": """# Rajendra Chola I: The Ocean Conqueror (முதலாம் இராசேந்திர சோழன்)

**Regnal Title**: *Parakesarivarman* Rajendra Chola I (*முதலாம் இராசேந்திர சோழன்*).  
**Popular Epithets**: *Gangaikonda Cholan* (Conqueror of the Ganges), *Kadaram-kondan* (Conqueror of Kedah/Srivijaya), *Mudigonda Cholan*.  
**Reign**: 1014 – 1044 CE.  
**Dynasty**: Imperial Cholas of Thanjavur and Gangaikonda Cholapuram.  

---

## 1. Maritime Vision & Blue-Water Navy
While his illustrious father Rajaraja I laid the foundations of the Chola navy by conquering the Maldives (*Munnir-palantivu*) and northern Sri Lanka, Rajendra Chola I transformed the fleet into an invincible blue-water maritime force capable of autonomous sustained trans-oceanic campaigns over thousands of kilometers.

---

## 2. Strategic Mastery of the 1025 Srivijaya Campaign
The 1025 CE expedition against the Srivijaya Empire remains a masterpiece of combined naval operations:
- **Intelligence & Wind Exploitation**: Rajendra's admirals timed their departure from Nagapattinam to coincide precisely with the onset of the Southwest Monsoon winds, propelling the armada at maximum speed across the open Bay of Bengal.
- **Strategic Surprise**: Rather than engaging Srivijaya's forward pickets along the northern Malacca Straits, the main Chola fleet bypassed traditional routes, sailing directly to southern Sumatra and striking the imperial capital Palembang while Srivijaya's main army was deployed elsewhere.
- **Decapitation Strike**: Capture of Emperor Sangrama Vijayottungavarman, his jewel-encrusted state throne, royal war elephants, and the legendary *Vidhyadhara Torana* (sacred jeweled victory arch).
- **Subjugation of 14 Straits City-States**: Coordinated squadrons captured key chokepoints including Kedah (*Kadaram*), Takua Pa (*Talaittakkolam*), and Jambi (*Malaiyur*).

---

## 3. Civilizational & Commercial Impact
Rajendra Chola I did not seek permanent colonial land annexation of Southeast Asia. His strategic objectives were commercial and civilizational:
1. **Freeing Trade Lanes**: Eradicating Srivijayan trade piracy and predatory toll extortions in the Malacca and Sunda straits.
2. **Direct Trade with China**: Opening direct, uninterrupted diplomatic and mercantile communication with the Song Dynasty emperors at Guangzhou.
3. **Thriving Merchant Guilds**: Empowering Tamil merchant corporations (*Ainnurruvar*, *Manigramam*, and *Anjuvannam*) whose bilingual Tamil inscriptions have been excavated across Sumatra, Malaysia, Thailand, and China.
"""
    },
    {
        "category": "characters",
        "slug": "char-kulamutrathu-killivalavan",
        "file": "char-kulamutrathu-killivalavan.md",
        "node_type": "character",
        "name_en": "Kulamutrathu Thunjiya Killivalavan: Early Sangam Naval Monarch",
        "name_ta": "குளமுற்றத்துத் துஞ்சிய கிள்ளிவளவன் - கடற்படையை நிறுவிய சங்க காலச் சோழ வேந்தன்",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 180,
        "thinai": "Neithal",
        "summary_en": "Formidable Early Sangam Chola monarch celebrated across classical Tamil poetry in Purananuru, Akananuru, and Kurunthogai. Renowned for institutionalizing an early offensive state naval armada, defending the Coromandel littoral against sea piracy, asserting maritime sovereignty over the Palk Strait, and fostering international commerce at the imperial port of Kaveripoompattinam.",
        "summary_ta": "புறநானூறு, அகநானூறு, குறுந்தொகை முதலான சங்க இலக்கியங்களில் போற்றப்படும் வீரஞ்செறிந்த சோழ வேந்தன். வங்கக் கடற்பரப்பில் ஆதிக்கமும் கடற்படைக் கட்டமைப்பும் நிறுவி, கடற்கொள்ளையர்களை ஒடுக்கி, பூம்புகார் துறைமுகத்தில் சர்வதேச யவன-சீன வர்த்தகக் கலங்கள் பாதுகாப்பாக வரவழைக்கச் செய்து, சோழ நாட்டின் கடல் எல்லையை உறுதிப்படுத்திய பெருவேந்தன்.",
        "content": """# Kulamutrathu Thunjiya Killivalavan (குளமுற்றத்துத் துஞ்சிய கிள்ளிவளவன்)

**Identity**: Sangam Chola Sovereign (*சங்க காலச் சோழ வேந்தன்*).  
**Reign**: ~100 – 180 CE.  
**Poets Who Sang His Praise**: Maruthuvan Dhamodharanaar, Kovur Kizhar, Alathur Kizhar, Nakkirar.  
**Burial / Memorial Site**: Kulamutram (*குளமுற்றம்*).  

---

## 1. Naval Achievements in Classical Poetry
Killivalavan is celebrated in the Sangam canon not merely as a terrestrial warrior who besieged the Chera capital of Karur and subdued recalcitrant chieftains, but as a sovereign of the high seas (*Kadal-vendaan*):
- In *Purananuru* 35, he is praised for his naval fleet whose towering masts appeared like a dense floating forest across the ocean horizon.
- In *Purananuru* 37, Kovur Kizhar records his maritime expeditions along the Palk Bay and northern Eelam coast.

---

## 2. Port Development at Kaveripoompattinam
Under Killivalavan's patronage:
- Poompuhar became the premier maritime emporium of the Coromandel coast, bustling with merchants speaking diverse foreign tongues.
- Maritime customs posts (*Puhar Sungam*) systematically stamped all incoming and outgoing goods with the Chola royal Tiger Seal (*Puli-p-pori*).
- Shipwright guilds received royal endowments of timber and iron, expanding the production of ocean-going *Navai* ships.
"""
    },
    {
        "category": "characters",
        "slug": "char-chola-kadal-padai-thalapathi",
        "file": "char-chola-kadal-padai-thalapathi.md",
        "node_type": "character",
        "name_en": "Chola Kadal-Padai Thalapathi: Grand Admiral of the Imperial High Fleet",
        "name_ta": "சோழக் கடற்படைத் தளபதி - பேரரசு பெருங்கடற்படையின் தலைமை மாலுமி",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1100,
        "thinai": "Neithal",
        "summary_en": "The institutional rank and strategic leadership of the Grand Admiral commanding the Imperial Chola navy. Trained in celestial navigation, hydrodynamics, dead reckoning, and monsoon wind aerodynamics, the Thalapathi directed fleet movements from the imperial flagship (Thalaipai-kappal), orchestrated amphibious troop landings, and executed complex naval combat maneuvers across the Indian Ocean and Malacca Straits.",
        "summary_ta": "சோழப் பேரரசின் பெருங்கடற்படையை வழிநடத்திய தலைமைத் தளபதியின் (கப்பற்படை அதிபதி / சமுத்திர சேனாதிபதி) தலைமைத்துவம் மற்றும் கடற்படை மேலாண்மை. வானியல் வழிகாட்டல், பருவக்காற்று சுழற்சிகள், கொடி சமிக்ஞைகள், கப்பல் வியூகங்கள் மற்றும் கடற்கரைத் தரையிறக்கத் தாக்குதல்களில் தேர்ச்சிபெற்ற இந்த தலைமை மாலுமிகள், சோழப் பேரரசின் கடலாதிக்க வெற்றிகளைத் தளத்தில் நின்று நிறைவேற்றிய முதன்மைப் போர்த் தலைவர்கள் ஆவர்.",
        "content": """# Chola Kadal-Padai Thalapathi (சோழக் கடற்படைத் தளபதி)

**Title / Rank**: Grand Admiral (*கடற்படைத் தளபதி / சமுத்திர சேனாபதி / கடற்படை அதிபதி*).  
**Hierarchy**: Directly subordinate to the Chola Emperor (*Chola Peruvendaan*).  
**Command Flagship**: *Thalaipai-kappal* / *Perum-Navai* (*தலைமைக் கப்பல்*).  
**Operational Sphere**: Bay of Bengal, Palk Strait, Andaman Sea, Straits of Malacca.  

---

## 1. Professional Training & Maritime Science
The commander of the Chola imperial fleet underwent rigorous training in multiple disciplines:
1. **Nautical Astronomy (*Vinnival-nerikoodam*)**: Navigating at night by observing the Pole Star (*Dhruva-meen*), Crux constellation (*Velli-meen*), and lunar mansions.
2. **Monsoon Aerodynamics (*Kaathu-paruvam*)**: Exploiting the Southwest Monsoon (*Thenmerku Paruva-kaatru*) for eastward voyages to Sumatra and China, and the Northeast Monsoon (*Vadakizhakku Paruva-kaatru*) for the return passage.
3. **Fleet Signaling**: Coordinating hundreds of vessels across miles of open sea using colored flags (*Kodi*) by day, flaming torches (*Theevatti*) by night, and synchronized conch blasts (*Sanghu*) in fog.

---

## 2. Command in Amphibious Warfare
During the 1025 CE Srivijaya campaign, the Grand Admirals executed a synchronized amphibious operational plan:
- Coordinated multi-squadron simultaneous attacks on Palembang and Kedah separated by over 1,000 km of water.
- Directed specialized shallow-draft landing craft to beach marine shock troops (*Kadal-maravar*) directly onto fortified enemy riverbanks.
- Maintained naval blockades cutting off reinforcement routes between Srivijaya's island dependencies.
"""
    },

    # --------------------------------------------------------------------------
    # 4. PLACES: NAVAL DOCKYARDS & MARITIME BASES
    # --------------------------------------------------------------------------
    {
        "category": "places",
        "slug": "place-nagapattinam-naval-dockyard",
        "file": "place-nagapattinam-naval-dockyard.md",
        "node_type": "place",
        "name_en": "Nagapattinam Imperial Chola Naval Dockyard & Arsenal",
        "name_ta": "நாகப்பட்டினம் சோழர் கப்பல் கட்டும் தளம் மற்றும் கடற்படைத் தலைமையகம்",
        "era": "Imperial Chola Era",
        "year_start": 850,
        "year_end": 1279,
        "thinai": "Neithal",
        "summary_en": "The primary naval shipyard, timber seasoning basin, and high-fleet staging port of the Imperial Chola navy situated at the mouth of the Kaduvaiyar and Vettar rivers on the Coromandel coast (10.7667° N, 79.8417° E). Served as the grand assembly point from which Rajendra Chola I launched the historic 1025 CE trans-oceanic Srivijaya armada, home to naval armories, ship slipways, coir rope-walks, and the famous Chudamani Vihara diplomatic quarter.",
        "summary_ta": "சோழப் பேரரசின் முதன்மைக் கடற்படைத் தளம், கப்பல் கட்டும் உலர் தளங்கள் மற்றும் கடற்படைத் தலைமையகம் அமைந்திருந்த வரலாற்றுத் துறைமுக நகரம் (அமைவிடம்: 10.7667° N, 79.8417° E). கடுவையாறு மற்றும் வெட்டாற்றின் முகத்துவாரத்தில் அமைந்த இந்நகரிலிருந்தே முதலாம் இராசேந்திர சோழன் 1025-ஆம் ஆண்டின் மாபெரும் ஸ்ரீவிஜயப் படையெடுப்பைத் தொடங்கினான்; ஆயுதக் கிடங்குகள், பாய்மரப் பட்டறைகள் மற்றும் சூடாமணி விகாரை அமைந்த சர்வதேசப் பண்பாட்டு மையம்.",
        "content": """# Nagapattinam Naval Dockyard (நாகப்பட்டினம் கடற்படைத் தளம்)

**Geographic Coordinates**: 10.7667° N, 79.8417° E.  
**Ecosystem**: Riverine Estuary & Marine Littoral (*Kaduvaiyar & Vettar Estuary, Bay of Bengal*).  
**Thinai**: *Neithal* (Coastal Maritime Landscape).  
**Dynastic Primacy**: Imperial Cholas (*Rajaraja I, Rajendra I, Kulothunga I*).  

---

## 1. Topography & Harbor Facilities
Nagapattinam served as the maritime lungs of the Thanjavur Chola Empire:
- **Naval Arsenal & Dockyards**: Located along the protected inland loops of the Kaduvaiyar River, allowing battleships to undergo construction and refitting safe from open-ocean monsoonal gales.
- **Ship Slipways & Dry Docks**: Archaeological surveys and historical maps reveal brick-lined mud docks and timber launching ramps where *Perum-Navai* vessels were constructed.
- **Deep Roadstead Anchorage**: An outer deepwater roadstead capable of anchoring hundreds of capital warships simultaneously.

---

## 2. Departure Staging Point for the 1025 CE Armada
In early 1025 CE, the waters of Nagapattinam witnessed the greatest naval assembly in Asian history:
- Hundreds of multi-decked warships, provisions barges, and troop transports gathered under the command of Rajendra Chola I.
- Thousands of *Kadal-maravar* marines, archers, and sailors embarked alongside siege ballistae, supplies, and royal horses.
- The fleet cast off under the favorable winds of the Southwest Monsoon, making landfall in northern Sumatra and the Malacca Straits.

---

## 3. Diplomatic & International Context: Chudamani Vihara
Nagapattinam was also a cosmopolitan diplomatic hub:
- In 1006 CE, King Sri Mara Vijayottungavarman of the Sailendra dynasty of Srivijaya founded the **Chudamani Vihara** (Buddhist monastery) at Nagapattinam with the active royal endowment of Rajaraja Chola I (recorded in the *Larger Leiden Plates*).
- Even during periods of diplomatic tension, Nagapattinam remained a nexus of international maritime commerce connecting Tamilakam with Sri Lanka, Southeast Asia, and China.
"""
    },
    {
        "category": "places",
        "slug": "place-korkai-pandyan-naval-harbor",
        "file": "place-korkai-pandyan-naval-harbor.md",
        "node_type": "place",
        "name_en": "Korkai: Ancient Pandyan Naval Harbor & Pearl Fishery Fleet Base",
        "name_ta": "கொற்கை - பாண்டியரின் தொன்மையான கடற்படைத் துறைமுகம் மற்றும் முத்துக்குளிப்புத் தளம்",
        "era": "Iron Age to Early Historic Sangam Era",
        "year_start": -500,
        "year_end": 300,
        "thinai": "Neithal",
        "summary_en": "Ancient Pandyan naval station, pearl fishery headquarters, and maritime customs gateway at the mouth of the sacred Tamraparni (Porunai) river (8.6333° N, 78.0500° E). Mentioned in Sangam literature, Ptolemy's Geography (Kolkhoi Emporion), and the Periplus Maris Erythraei as the center of the world-famous Korkai pearl fisheries, guarded by Pandyan naval patrol vessels and home to generations of expert Parathavar shipwrights and divers.",
        "summary_ta": "பாண்டிய மன்னர்களின் தொன்மையான தலைசிறந்த துறைமுகம், முத்துக்குளிப்புத் தளம் மற்றும் கடற்படைப் பாசறை (அமைவிடம்: 8.6333° N, 78.0500° E). தாமிரபரணி (பொருநை) ஆற்றின் முகத்துவாரத்தில் அமைந்த இந்நகரம், சங்க இலக்கியங்கள், தாலமியின் பூகோள நூல் மற்றும் பெரிப்ளூஸ் குறிப்புகளில் கொற்கை (Kolkhoi) என்று போற்றப்படுகிறது; உலகப் புகழ்பெற்ற முத்து வணிகத்தின் மையமாகவும், பாண்டியரின் கடற்படைக் காவல் கலங்கள் நின்ற பாதுகாப்புத் தளமாகவும் திகழ்ந்தது.",
        "content": """# Korkai: Pandyan Naval Harbor & Pearl Base (கொற்கை துறைமுகம்)

**Geographic Coordinates**: 8.6333° N, 78.0500° E.  
**Ecosystem**: Deltaic Estuary & Coral Reef Littoral (*Tamraparni / Porunai River Mouth, Gulf of Mannar*).  
**Thinai**: *Neithal* (Maritime Coastal Landscape).  
**Sovereign Patronage**: Sangam Early Historic Pandyas (*கொற்கைக் கோமான்*).  

---

## 1. Classical Identity & Historical Stratigraphy
Korkai was the foundational maritime cradle of the Pandyan kingdom:
- **Classical Literature**: Sangam texts (*Akananuru*, *Purananuru*, *Maduraikkanchi*) style the Pandyan monarch as *Korkai-Koman* (Lord of Korkai).
- **Greco-Roman Records**: Documented in the *Periplus Maris Erythraei* (1st c. CE) as *Kolchoi* and by Ptolemy as *Kolkhoi Emporion*, celebrated throughout the Roman Empire as the sole source of the finest Orient pearls.
- **Archaeological Excavations**: Excavations conducted by the Tamil Nadu State Department of Archaeology revealed punch-marked coins, Roman amphora sherds, black-and-red ware inscribed in Tamil-Brahmi, pearl-oyster shell middens, and ancient brick-built port retaining walls.

---

## 2. Naval Patrol & Pearl Fleet Operations
Korkai functioned as both an economic emporium and a fortified naval base:
1. **The Pearl Diving Fleet (*Muthu-kuli Thoni*)**: Hundreds of specialized double-ended skiffs operated by the seafaring *Parathavar* community gathered annually during calm sea windows to dive into the deep oyster shoals of the Gulf of Mannar.
2. **Pandyan Naval Guard (*Korkai Kadal-Kaval*)**: Fast patrol boats manned by Pandyan marine archers patrolled the shallow waters between Korkai, Rameswaram, and Sri Lanka to protect the lucrative royal pearl banks from foreign sea rovers and smugglers.
3. **Customs & Chank Processing**: Royal officers levied customs duties on all pearl harvests, while adjacent workshops sawed sacred conch shells (*Chank*) into high-value bangles for export throughout South and Southeast Asia.
"""
    }
]

# ------------------------------------------------------------------------------
# 5. RELATIONAL CROSS-DOMAIN EDGES (7-element tuples)
# (source_slug, relation_type, target_slug, layer, era, description, evidence_source)
# ------------------------------------------------------------------------------
EDGES = [
    # Texts to Concepts
    (
        "text-kappal-sattiram-naval-architecture",
        "codifies_ship_architecture",
        "concept-kappal-anatomy-and-rigging",
        "relational",
        "Sangam to Medieval Classical Era",
        "Kappal Sattiram details complete ship anatomy, mast configuration, and timber selection rules.",
        "Oriental Manuscripts Library & Saraswathi Mahal Palm-Leaf Codices"
    ),
    (
        "text-kappal-sattiram-naval-architecture",
        "records_hydrodynamics",
        "concept-kattumaram-and-twin-hull-hydrodynamics",
        "relational",
        "Sangam to Medieval Classical Era",
        "Kappal Sattiram documents multi-log Kattumaram construction and metacentric stability principles.",
        "Kappal Sattiram Palm-Leaf Treatise"
    ),
    (
        "text-maduraikkanchi-oceanic-navai",
        "describes_deep_draft_vessels",
        "concept-kappal-anatomy-and-rigging",
        "relational",
        "Sangam Early Historic Era",
        "Maduraikkanchi depicts massive mountain-masted Navai anchored in deep roadsteads with cloud-like sails.",
        "Maduraikkanchi lines 375-385"
    ),
    (
        "text-maduraikkanchi-oceanic-navai",
        "documents_harbor_operations",
        "place-korkai-pandyan-naval-harbor",
        "relational",
        "Sangam Early Historic Era",
        "Maduraikkanchi documents Pandyan harbor lighterage and pearl fishery commerce at Korkai.",
        "Maduraikkanchi lines 536-544"
    ),
    (
        "text-purananuru-kulamutrathu-killivalavan-navy",
        "celebrates_naval_armada",
        "char-kulamutrathu-killivalavan",
        "relational",
        "Sangam Early Historic Era",
        "Purananuru bards praise Killivalavan for commanding a fleet whose masts appeared like a floating forest.",
        "Purananuru poems 35, 37, 39"
    ),
    (
        "text-purananuru-kulamutrathu-killivalavan-navy",
        "documents_naval_warfare",
        "concept-naval-warfare-and-tactics",
        "relational",
        "Sangam Early Historic Era",
        "Purananuru verses detail offensive maritime campaigns, boarding tactics, and coastal sovereignty.",
        "Purananuru 35"
    ),
    (
        "insc-thanjavur-rajendra-naval-expedition",
        "commemorates_naval_conquest",
        "char-rajendra-chola-naval-emperor",
        "relational",
        "Imperial Chola Era",
        "The Thanjavur plinth inscription records Rajendra Chola I's historic 1025 CE trans-oceanic Srivijaya victory.",
        "Thanjavur Brihadisvara South Wall Inscription (SII Vol II)"
    ),
    (
        "insc-thanjavur-rajendra-naval-expedition",
        "records_transoceanic_armada",
        "concept-chola-naval-armada-1025",
        "relational",
        "Imperial Chola Era",
        "Epigraph contains the official Meikeerthi cataloging the capture of 14 Srivijayan city-states and ports.",
        "Thanjavur Brihadisvara Plinth Meikeerthi"
    ),
    (
        "insc-thanjavur-rajendra-naval-expedition",
        "originates_from_staging_dockyard",
        "place-nagapattinam-naval-dockyard",
        "relational",
        "Imperial Chola Era",
        "The 1025 CE expeditionary fleet assembled and launched from the imperial dockyards at Nagapattinam.",
        "Karandai Plates & Thanjavur Inscription"
    ),

    # Concepts to Concepts & Places
    (
        "concept-nagapattinam-chola-naval-dockyards",
        "site_of_dockyards",
        "place-nagapattinam-naval-dockyard",
        "relational",
        "Imperial Chola Era",
        "Nagapattinam hosted the primary dry docks, slipways, and timber seasoning basins of the Chola navy.",
        "Epigraphical & Archaeological Survey of Nagapattinam"
    ),
    (
        "concept-nagapattinam-chola-naval-dockyards",
        "supplied_armada_vessels",
        "concept-chola-naval-armada-1025",
        "relational",
        "Imperial Chola Era",
        "Nagapattinam shipyards constructed and outfitted the Perum-Navai warships for the 1025 CE expedition.",
        "Chola Maritime Epigraphy & Leiden Plates"
    ),
    (
        "concept-naval-warfare-and-tactics",
        "applied_in_armada",
        "concept-chola-naval-armada-1025",
        "relational",
        "Imperial Chola Era",
        "Chola naval commanders applied Pirai-ani envelopment, ramming, and marine assault during the 1025 campaign.",
        "Thanjavur Prasasti & Maritime Records"
    ),
    (
        "concept-kappal-anatomy-and-rigging",
        "utilized_in_warships",
        "concept-nagapattinam-chola-naval-dockyards",
        "relational",
        "Imperial Chola Era",
        "Shipwright principles of timber selection, hull strakes, and coir stitching were executed at Nagapattinam.",
        "Kappal Sattiram & Naval Epigraphs"
    ),
    (
        "concept-kattumaram-and-twin-hull-hydrodynamics",
        "provided_amphibious_scouts",
        "concept-naval-warfare-and-tactics",
        "relational",
        "Sangam to Imperial Chola Era",
        "Kattumaram multihulls served as unsinkable beach-landing craft and swift reconnaissance scouts.",
        "Classical Marine Accounts & Ethnographic Surveys"
    ),

    # Characters to Concepts, Texts & Places
    (
        "char-rajendra-chola-naval-emperor",
        "elaborates_naval_aspect_of",
        "char-rajendra-chola-i",
        "relational",
        "Imperial Chola Era",
        "Dedicated naval dossier detailing Rajendra Chola I's role as supreme naval architect and admiral-in-chief.",
        "South Indian Inscriptions Vol II"
    ),
    (
        "char-rajendra-chola-naval-emperor",
        "commanded_armada",
        "concept-chola-naval-armada-1025",
        "relational",
        "Imperial Chola Era",
        "Rajendra Chola I personally directed the grand strategy of the 1025 CE trans-oceanic expedition.",
        "Thanjavur Vimana Plinth Epigraph"
    ),
    (
        "char-rajendra-chola-naval-emperor",
        "mobilized_from_dockyard",
        "place-nagapattinam-naval-dockyard",
        "relational",
        "Imperial Chola Era",
        "The emperor established his naval staging headquarters and assembly point at Nagapattinam.",
        "Larger Leiden Plates & Thanjavur Inscription"
    ),
    (
        "char-chola-kadal-padai-thalapathi",
        "directed_fleet_tactics",
        "concept-naval-warfare-and-tactics",
        "relational",
        "Imperial Chola Era",
        "The Grand Admirals executed battle formations, monsoon navigation, and amphibious assault tactics.",
        "Chola Naval Inscriptions & Historical Treatises"
    ),
    (
        "char-chola-kadal-padai-thalapathi",
        "oversaw_ship_construction",
        "concept-nagapattinam-chola-naval-dockyards",
        "relational",
        "Imperial Chola Era",
        "Naval commanders supervised shipbuilding standards, seasoning basins, and arsenal readiness.",
        "Nagapattinam Inscriptional Surveys"
    ),
    (
        "char-kulamutrathu-killivalavan",
        "patronized_early_navy",
        "concept-naval-warfare-and-tactics",
        "relational",
        "Sangam Early Historic Era",
        "Killivalavan institutionalized early offensive naval warfare to protect Coromandel shipping lanes.",
        "Purananuru 35, 37"
    ),
    (
        "char-kulamutrathu-killivalavan",
        "stationed_fleet_at_port",
        "place-poompuhar",
        "relational",
        "Sangam Early Historic Era",
        "Killivalavan's naval fleet guarded the imperial port and customs houses of Kaveripoompattinam.",
        "Purananuru & Pattinappalai"
    ),
    (
        "place-korkai-pandyan-naval-harbor",
        "harbor_base_of",
        "place-korkai",
        "relational",
        "Iron Age to Early Historic Sangam Era",
        "Detailed naval and pearl fleet installation at the ancient Pandyan port of Korkai.",
        "Sangam Literature & Archaeological Excavation Reports"
    ),
    (
        "place-nagapattinam-naval-dockyard",
        "naval_quarter_of",
        "place-nagapattinam",
        "relational",
        "Imperial Chola Era",
        "The dedicated imperial naval shipyard and arsenal quarter of the port of Nagapattinam.",
        "Larger Leiden Plates & Epigraphia Indica"
    )
]

def main():
    print("=" * 75)
    print("⚓ ANCIENT TAMIL MARITIME SHIP ARCHITECTURE & NAVAL WARFARE CORPUS HARVESTER")
    print("=" * 75)

    # 1. Write Markdown Dossiers to Moolam Chronicles
    print("\n[Phase 1] Writing Canonical Markdown Dossiers to Moolam Chronicles...")
    for d in DOSSIERS:
        category_dir = os.path.join(MOOLAM_KNOWLEDGE, d["category"])
        os.makedirs(category_dir, exist_ok=True)
        filepath = os.path.join(category_dir, d["file"])
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Written: knowledge/{d['category']}/{d['file']}")

    # 2. Connect to PostgreSQL
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # 3. Upsert Lore Nodes
    print("\n[Phase 2] Upserting Lore Nodes into PostgreSQL...")
    total_nodes_upserted = 0
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
        total_nodes_upserted += 1
        print(f"  ✓ [{d['node_type'].upper()}] {d['slug']} -> {d['name_en'][:45]}...")

    conn.commit()
    print(f"Phase 2 complete: {total_nodes_upserted} lore nodes upserted.")

    # 4. Upsert Lore Edges
    print("\n[Phase 3] Upserting Lore Edges into PostgreSQL...")
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
    print(f"Phase 3 complete: {edges_inserted} new lore edges inserted.")

    # 5. Generate Dense Vector Embeddings into rag_chunks
    print("\n[Phase 4] Generating 1024-dim BGE-M3 Embeddings into rag_chunks...")
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

    # 6. Corpus Stats Summary
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
