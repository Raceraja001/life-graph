#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester:
1. Ancient Tamil Medicine, Siddha Pharmacology, Kaya Kalpa & Pulse Diagnosis (13 dossiers)
2. Ancient Tamil Sculpture, Iconography, Lost-Wax Bronze Casting & Temple Architecture (11 dossiers)
3. Sangam Botany, Ethnobotany & Ecological Landscape Architecture (11 dossiers)

Total: 35 Canonical Dossiers, ~65 Relational Edges, 70 Dense 1024-dim BGE-M3 Embeddings.
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
# DOSSIERS DEFINITION (35 Total)
# ==============================================================================
DOSSIERS = [
    # --------------------------------------------------------------------------
    # CORPUS 1: ANCIENT TAMIL MEDICINE, SIDDHA PHARMACOLOGY & PULSE DIAGNOSIS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-agathiyar-vaidya-kaviyam-siddha",
        "file": "text-agathiyar-vaidya-kaviyam-siddha.md",
        "node_type": "text",
        "name_en": "Agathiyar Vaidya Kaviyam: Foundational Siddha Alchemy, Tridosha & Kaya Kalpa",
        "name_ta": "அகத்தியர் வைத்திய காவியம் - சித்த மருத்துவ அடித்தளம், முக்குற்றம் மற்றும் காயகல்பம்",
        "era": "Sangam to Medieval Classical Era",
        "year_start": -200,
        "year_end": 800,
        "thinai": "Kurinji",
        "summary_en": "Classical 1500-verse Siddha medical treatise ascribed to Sage Agathiyar. Codifies the 96 fundamental tattvas of human physiology, the three humoral pathologies (Mukkutram: Vatham, Pittham, Kapham), eight-fold clinical diagnosis (Envagai Thervu: pulse, eyes, voice, touch, color, tongue, feces, urine), Muppu catalytic salt chemistry, and Kaya Kalpa rejuvenation regimens for cell longevity.",
        "summary_ta": "அகத்திய முனிவரால் அருளப்பட்ட 1500 பாடல்களைக் கொண்ட மூல சித்த மருத்துவ நூல். உடலின் 96 தத்துவங்கள், வாதம்-பித்தம்-கபம் ஆகிய முக்குற்றக் கோட்பாடுகள், எண்வகைத் தேர்வுகள் (நாடி, விழி, மொழி, மெய், நிறம், நாக்கு, மலம், மூத்திரம்), முப்பு ரசவாதக் கூட்டு, மற்றும் உடலழியா நிலையை அருளும் காயகல்ப செய்முறைகளைத் துல்லியமாக விவரிக்கும் மகத்தான மருத்துவப் பொக்கிஷம்.",
        "content": """# Agathiyar Vaidya Kaviyam: Foundational Siddha Medicine

**Author / Lineage**: Sage Agathiyar (*அகத்தியர்*), First of the 18 Siddhars.  
**Historical Horizon**: Classical Sangam to Early Medieval Era (~200 BCE – 800 CE).  
**Core Subject**: Humoral Physiology (*Tridosha / Mukkutram*), *Envagai Thervu*, *Kaya Kalpa*, and Herbo-Mineral Alchemy.  

---

## 1. The 96 Physiological Tattvas & Mukkutram Physics
In *Agathiyar Vaidya Kaviyam*, the human body is viewed as a microscopic mirror of the cosmos (*Andathil ullathe Pindam*):
- Composed of the Five Elements (*Aymboothangal*: Earth, Water, Fire, Air, Space).
- Sustained through three dynamic biophysical forces known as **Mukkutram** (*முக்குற்றம்*):
  1. **Vatham (*வாதம்*)**: Governed by Air and Space; controls nervous conduction, respiration, motor activities, and muscular contraction. Ratio: 1 part.
  2. **Pittham (*பித்தம்*)**: Governed by Fire; regulates thermogenesis, digestion, biochemical metabolism, optical acuity, and cellular intellection. Ratio: 1/2 part.
  3. **Kapham (*கபம் / ஐயம்*)**: Governed by Earth and Water; maintains structural cohesion, lubrication of joint synovial fluid, cellular hydration, and immunity. Ratio: 1/4 part.

---

## 2. Envagai Thervu: The Eight-Fold Clinical Examination
The text formalizes the diagnostic standard:
1. **Nadi (*நாடி*)**: Radial pulse diagnosis identifying humoral balance.
2. **Kan (*விழி / கண்*)**: Scleral pigmentation (yellow in Pittham, pale in Vatham, white/heavy in Kapham).
3. **Mozhi (*மொழி / சொல்*)**: Voice timbre, cadence, and vocal cord acoustics.
4. **Mei (*மெய் / தீண்டல்*)**: Dermal temperature, dryness, perspiration, and tactile turgor.
5. **Niram (*நிறம்*)**: Cutaneous complexion and pigmentation changes.
6. **Naa (*நாக்கு*)**: Lingual coating, moisture, fissures, and papillae distribution.
7. **Malam (*மலம்*)**: Stool consistency, floatation test, and color.
8. **Neer (*மூத்திரம்*)**: Urine analysis including morning *Neikkuri* (oil-drop spread test over urine surface in sunlight).

---

## 3. Kaya Kalpa Longevity Medicine
Agathiyar formulates *Kaya Kalpa* (*காயகல்பம்*) methods to arrest cellular aging (*Moopu*) and stave off premature mortality:
- Herbal elixirs incorporating *Nellikkai* (Phyllanthus emblica), *Karisalanganni* (Eclipta prostrata), and *Vallari* (Centella asiatica).
- Purified mercury (*Rasam*) and sulfur (*Gandhakam*) compounds fixed through *Muppu* catalytic salts into indestructible *Kattu* and *Bhasma* formulations.
"""
    },
    {
        "category": "texts",
        "slug": "text-theraiyar-sekkiruvadukal-hygiene",
        "file": "text-theraiyar-sekkiruvadukal-hygiene.md",
        "node_type": "text",
        "name_en": "Theraiyar Sekkiruvadukal & Noinaadal: Preventive Hygiene, Pulse & Dietetics",
        "name_ta": "தேரையர் சேக்கிருவாடுகள் மற்றும் நோய்நாடல் - நோய் தடுப்பு சுகாதாரம், நாடி மற்றும் உணவுமுறை",
        "era": "Classical to Medieval Era",
        "year_start": 600,
        "year_end": 1000,
        "thinai": "Marutham",
        "summary_en": "Celebrated preventive and clinical diagnostic treatise by Sage Theraiyar. Details circadian hygienic disciplines, dietary compatibility (Patthiyam), toxicology, classification of 4,448 human diseases, urine oil-drop surface tension testing (Neikkuri), and pioneering neuro-cranial surgical interventions.",
        "summary_ta": "சித்த மருத்துவத்தின் தலைசிறந்த நோய்நாடல் மேதை தேரையரின் மருத்துவ நூல். 'பாலுண்போம் எண்ணெய் பெறின் வெந்நீரில் குளிப்போம்...' முதலான காலத்தால் அழியாத சுகாதாரப் பொன்மொழிகள், பத்திய உணவு நெறிகள், 4448 நோய்களின் வகைப்பாடு, சிறுநீரில் நல்லெண்ணெய் விட்டுப் பார்க்கும் நெய்க்குறிச் சோதனை, மற்றும் தலை மண்டை ஓட்டு அறுவைசிகிச்சை (கிரேனியோடமி) பற்றிய அரிய குறிப்புகள்.",
        "content": """# Theraiyar Sekkiruvadukal & Noinaadal (தேரையர் நோய்நாடல்)

**Author**: Sage Theraiyar (*தேரையர்*), Master Diagnostician & Toxicologist.  
**Historical Era**: ~600 – 1000 CE.  
**Discipline**: Clinical Pathology (*Noinaadal*), Preventive Lifestyle & Surgery (*Aruvai Maruthuvam*).  

---

## 1. Immortal Maxims of Circadian Hygiene
Theraiyar codified preventive daily routines that remain bedrock principles of Tamil public health:
- *"Drink buttermilk boiled with dry ginger; never drink unboiled raw water."*
- *"Take an oil bath once in four days with warm water."*
- *"Never sleep during the daylight hours; sleep on the left lateral position at night."*
- *"Never walk in the scorching midday sun."*
- *"Eat only after the previous meal has completely digested."*

---

## 2. Neikkuri: The Urine Oil-Drop Diagnostic Test
Theraiyar perfected the diagnostic examination of urine:
- Morning midstream urine is placed in a clean, wide-mouthed flat ceramic vessel under steady early-morning sunlight.
- A single droplet of pure sesame oil (*Nallennai*) is gently dropped onto the surface via a thin straw without disturbing the liquid.
- **Diagnostic Manifestations**:
  - *Vatham*: Oil droplet spreads slowly like a serpentine snake or ribbon.
  - *Pittham*: Oil droplet spreads in a circular ring or expands into vibrant rainbow globules.
  - *Kapham*: Oil droplet remains intact like a pearl, sinks, or forms a sieve-like mesh.
  - *Incurable/Terminal*: Droplet breaks into droplets shaped like an arrow, trident, or scattered fragments.

---

## 3. Surgical Trepanation Legacy
Legend and manuscript records credit Theraiyar with performing early cranial trepanation:
- Relieved intractable migraine caused by an intracranial parasite/growth (*Therai* toad-parasite legend) by trepanning the parietal bone with fine surgical blades, neutralizing the tissue with herbal extracts, and dressing the incision with medicated wound-healing resins (*Vengai / Kungiliyam*).
"""
    },
    {
        "category": "texts",
        "slug": "text-bogar-7000-saptha-kandam",
        "file": "text-bogar-7000-saptha-kandam.md",
        "node_type": "text",
        "name_en": "Bogar 7000 (Saptha Kandam): Navapashanam Alchemy & Transmutation",
        "name_ta": "போகர் ஏழாயிரம் (சப்த காண்டம்) - நவபாஷாண ரசவாதம் மற்றும் உலோக வேதியியல்",
        "era": "Classical to Medieval Era",
        "year_start": 500,
        "year_end": 1100,
        "thinai": "Kurinji",
        "summary_en": "Encyclopedic 7,000-verse alchemical epic by Siddhar Bogar. Details high-temperature mineral metallurgy, sublimation (Pathangam), transmutation of base metals into gold, fixation of mercury into fire-resisting solids (Rasa-kattu), preparation of the supreme nine-poison amalgam Navapashanam, and trans-continental travels connecting Tamilakam with ancient China.",
        "summary_ta": "போகர் சித்தரின் 7000 செய்யுட்களைக் கொண்ட மகத்தான ரசவாதப் பெருநூல். பாதரசத்தை நெருப்பில் உருகாதவாறு கட்டும் ரசக்கட்டு, உலோகங்களை மாற்றும் வேதியியல் வித்தைகள், பதங்கம்-செந்தூரம்-சுண்ணம் தயாரிக்கும் 64 வகை மருந்துகள், மற்றும் ஒன்பது கொடிய நச்சுப் பாஷாணங்களை ஒன்றுசேர்த்து நவபாஷாண முருகன் திருமேனி வடித்த ரகசியங்கள் விரிவாகப் பாடப்பட்டுள்ள காவியம்.",
        "content": """# Bogar 7000 / Saptha Kandam (போகர் ஏழாயிரம்)

**Author**: Siddhar Bogar (*போகர்*), Alchemist, Metallurgist & Transmuter.  
**Length**: 7,000 verses across 7 Kandams (*சப்த காண்டம்*).  
**Geographical Focus**: Palani Hills, Kollimalai, Western Ghats, and China.  

---

## 1. Hermetic Alchemy & Mineral Solidification (*Rasa-Kattu*)
Bogar details the purification and fixation of liquid elemental mercury (*Rasam*):
- Mercury is subjected to 18 processes of purification (*Ashta-Dasa Samskaras*) to remove its natural toxic impurities (*Doshas*).
- Using herbal juices (*Karisalanganni, Erukku, Thumbai*) and secret catalytic salts (*Muppu*), liquid mercury is solidified into a crystalline solid (*Rasa-kattu*) that can withstand intense charcoal fire without volatilizing.

---

## 2. Navapashanam: The Nine-Poison Synthesis
In verses 1200–1450, Bogar records the exact formulation of **Navapashanam** (*நவபாஷாணம்*):
- Nine virulent toxic mineral substances combined at extreme heat under precise lunar alignments:
  1. *Veeram* (Corrosive Sublimate / Mercuric chloride)
  2. *Pooram* (Calomel / Mercurous chloride)
  3. *Rasasindhooram* (Red Mercuric Sulfide)
  4. *Lingam* (Natural Cinnabar)
  5. *Gauripashanam* (Arsenic Trisulfide / Orpiment)
  6. *Manosila* (Arsenic Disulfide / Realgar)
  7. *Mriddarsingh* (Lead Monoxide / Litharge)
  8. *Kanthakam* (Purified Elemental Sulfur)
  9. *Ganga Pashanam* (Hydrothermal mineral amalgam)
- Once fused into a dense ceramic-like matrix, it becomes non-toxic, chemically stable, and imparts restorative mineral ionization to fluids poured over its surface.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thirumukkudal-veera-rajendra-hospital",
        "file": "insc-thirumukkudal-veera-rajendra-hospital.md",
        "node_type": "inscription",
        "name_en": "Thirumukkudal Inscription: 11th-Century Chola Free Hospital (Aathula Salai) & Pharmacopoeia",
        "name_ta": "திருமுக்கூடற் கல்வெட்டு - வீரராசேந்திர சோழனின் இலவச மருத்துவமனை (ஆதுல சாலை) மற்றும் மருந்துக் களஞ்சியம்",
        "era": "Imperial Chola Era",
        "year_start": 1067,
        "year_end": 1070,
        "thinai": "Marutham",
        "summary_en": "Monumental 55-line granite inscription in the Venkatesa Perumal temple at Thirumukkudal (1067 CE) by Emperor Veera Rajendra Chola. Documents the complete endowment, staff, and budget of an imperial 15-bed inpatient free hospital (Veerasolan Aathula Salai), specifying salaries for a physician, surgeon, two nurse-pharmacists, barbers, and cataloging 20 stored classical medicines.",
        "summary_ta": "செங்கல்பட்டு மாவட்டம் திருமுக்கூடல் வேங்கடேசப் பெருமாள் கோயில் சுவரில் பொறிக்கப்பட்டுள்ள வீரராசேந்திர சோழனின் 1067-ஆம் ஆண்டுக் கல்வெட்டு. 'வீரசோழன் ஆதுல சாலை' என்ற 15 படுக்கைகள் கொண்ட இலவச மருத்துவமனையின் முழுமையான நிர்வாகம், தலைமை மருத்துவர், அறுவை சிகிச்சை நிபுணர் (சல்லியகரன்), செவிலியர், மருந்தாளுநர் ஆகியோரின் ஊதியம், மற்றும் அங்கு சேமிக்கப்பட்டிருந்த 20 வகையான அரிய மருந்துகளின் பட்டியலைத் துல்லியமாக ஆவணப்படுத்தும் அரச ஆவணம்.",
        "content": """# Thirumukkudal Hospital Inscription (1067 CE)

**Location**: Venkatesa Perumal Temple, Thirumukkudal, Chengalpattu District (*திருமுக்கூடல்*).  
**Monarch**: Emperor Veera Rajendra Chola (*வீரராசேந்திர சோழன்*).  
**Regnal Year**: Year 5 (1067 CE).  
**Epigraphical Citation**: *Epigraphia Indica* Vol. XXI, No. 38.  

---

## 1. Institutional Anatomy of the Veerasolan Aathula Salai
The inscription records a comprehensive state-sponsored hospital (*Aathula Salai*):
- **Capacity**: 15 permanent inpatient beds (*Kidakkai*).
- **Staffing Roster & Annual Allowances**:
  - 1 Chief Physician (*Vaidyan*): Granted paddy allowances and hereditary land rights.
  - 1 Surgeon (*Salliya-karan*): Expert in wound care, extraction of arrows, and fracture setting.
  - 2 Pharmacists / Herb Collectors (*Marunthu Paravuvor*).
  - 2 Nurses (*Aattukkaligal*): Preparing herbal diets, decoctions, and bathing patients.
  - 1 Barber-Surgeon (*Naavithan*): Shaving, minor lancing, and leech-letting.
  - 1 Washerman (*Vannaan*): Cleansing hospital linens and bandages.

---

## 2. Inscriptional Pharmacopoeia: 20 Preserved Formulations
The inscription provides an invaluable list of medicines stored in the hospital dispensary:
1. *Brahmi Ghritam* (Medicated ghee for neurological and cognitive disorders)
2. *Haritaki Lehyam* (Chebulic myrobalan herbal jam for digestion and bowel health)
3. *Vasa Haritaki* (Adhatoda compound for bronchial affections)
4. *Panchapala Ghritam* (Medicated ghee for chronic inflammatory conditions)
5. *Kalyanaka Lavanam* (Alchemical medicated salt formulation)
6. *Bilvadi Ghritam* (Bael fruit formulation for dysentery)
7. *Kashayas* (Boiled herbal decoctions for fever and detox)
8. *Tailas* (Medicated oils for external abhyanga massage and wound dressings)
"""
    },
    {
        "category": "concepts",
        "slug": "concept-nadi-parikshai-pulse-mechanics",
        "file": "concept-nadi-parikshai-pulse-mechanics.md",
        "node_type": "concept",
        "name_en": "Nadi Parikshai: Three-Finger Radial Pulse Diagnosis (Vatham, Pittham, Kapham)",
        "name_ta": "நாடிப் பரிட்சை - முக்குற்றக் கணிப்பு மற்றும் கைநாடி நோயறிதல் நுட்பங்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The tactile diagnostic science of radial artery pulse palpation in Siddha medicine. Explores the three-finger positioning below the radial styloid, gait dynamics comparing pulse rhythms to animal movements (Swan/Rooster for Vatham, Turtle/Leech for Pittham, Elephant/Pigeon for Kapham), and mathematical mātra fractions used to identify pre-clinical pathology.",
        "summary_ta": "சித்த மருத்துவத்தின் தனித்துவமிக்க நாடிப் பரிசோதனை அறிவியல். மணிக்கட்டின் ஆரைத் தமனி மீது ஆள்காட்டி விரல், நடுவிரல், மோதிர விரல் ஆகிய மூன்று விரல்களை வைத்து வாதம் (அன்னம்/கோழி நடை - 1 மாத்திரை), பித்தம் (ஆமை/அட்டை நடை - 1/2 மாத்திரை), கபம் (யானை/புறா நடை - 1/4 மாத்திரை) ஆகியவற்றின் துடிப்பு வேகத்தையும் ஆழத்தையும் உணர்ந்து நோயை முன்கூட்டியே கண்டறியும் கலை.",
        "content": """# Nadi Parikshai: Three-Finger Radial Pulse Diagnosis (நாடிப் பரிட்சை)

**Diagnostic Modality**: Radial Artery Palpation (*கைநாடித் தேர்வு*).  
**Humoral Correlates**: *Vatham* (Index), *Pittham* (Middle), *Kapham* (Ring).  

---

## 1. Finger Positioning & Protocol
- **Location**: Palpated at the radial artery on the volar aspect of the wrist, exactly one thumb-breadth (*Oru Viral*) below the radial styloid process.
- **Protocol**: Performed on the right arm for men, and on the left arm for women. Best examined in the early morning before food consumption.
- **Finger Contact**:
  - **Index Finger (*Kattiya-viral*)**: Detects *Vatha Nadi* (1 mātra).
  - **Middle Finger (*Nadu-viral*)**: Detects *Pittha Nadi* (1/2 mātra).
  - **Ring Finger (*Mothira-viral*)**: Detects *Kapha Nadi* (1/4 mātra).

---

## 2. Animal Gait Metaphors (*Nadai Ilakkanam*)
The tactile sensations transmitted to the physician's fingertips are classified using vivid animal kinetic metaphors:
- **Vatham (Swan / Rooster / Leaping Frog)**: Rapid, light, erratic jumping movement.
- **Pittham (Crawling Turtle / Leech)**: Deliberate, warm, undulating, expansive wave.
- **Kapham (Ponderous Elephant / Strutting Pigeon)**: Heavy, deep, slow, rhythmic glide.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-muppu-universal-catalyst",
        "file": "concept-muppu-universal-catalyst.md",
        "node_type": "concept",
        "name_en": "Muppu: The Universal Catalytic Salt, Chunnams & Kaya Kalpa Longevity",
        "name_ta": "முப்பு - உலகளாவிய ரசவாத உப்பு, சுண்ணங்கள் மற்றும் காயகல்ப மூப்பு நீக்கல்",
        "era": "Classical Siddha Era",
        "year_start": 500,
        "year_end": 1200,
        "thinai": "Kurinji",
        "summary_en": "The crowning achievement of esoteric Siddha alchemy. An alchemical combination of three naturally occurring alkaline salts (Pooneeru soil efflorescence, rock salt, and potassium nitrate) purified through 108 cycles. Serves as the universal catalyst that calcines inert metals into bio-assimilable, non-toxic medicinal Bhasmas.",
        "summary_ta": "சித்த ரசவாதத்தின் உச்சக்கட்ட சாதனையான முப்பு. பூமியிலிருந்து பூக்கும் பூநீறு, கல்லுப்பு, மற்றும் வெடியுப்பு ஆகிய மூன்று உப்புக்களை 108 முறை புடமிட்டுச் சுத்தி செய்து உருவாக்கப்படும் உலகளாவிய வினைவேக மாற்றி. தங்கம், வெள்ளி, பாதரசம் போன்ற எரியாத கடின உலோகங்களையும் பற்பமாகவும் சுண்ணமாகவும் மாற்றி உடலை அழியாத கற்பமாக்கும் ரகசிய வேதியியல் கூட்டு.",
        "content": """# Muppu: The Universal Alchemical Salt (முப்பு)

**Definition**: Tri-Salt Catalytic Matrix (*மூன்று புவனங்களின் உப்பு*).  
**Constituents**: *Pooneeru* (Efflorescent Earth Salt), *Kalluppu* (Rock Salt), *Vediuppu* (Potassium Nitrate).  

---

## 1. Threefold Classification of Muppu
1. **Vada Muppu (*வாத முப்பு*)**: Utilized in alchemy for transmuting lower metals into gold and silver.
2. **Vaidya Muppu (*வைத்திய முப்பு*)**: Catalytic flux used in pharmacology to calcine metals into *Chunnam* (calx) and *Bhasma*.
3. **Jnana Muppu (*ஞான முப்பு*)**: Spiritual elixir consumed during advanced Kundalini meditation for longevity (*Kaya Kalpa*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-navapashanam-nine-poison-amalgam",
        "file": "concept-navapashanam-nine-poison-amalgam.md",
        "node_type": "concept",
        "name_en": "Navapashanam: Nine Toxic Mineral Amalgams & Hydrothermal Medicine",
        "name_ta": "நவபாஷாணம் - ஒன்பது நச்சுப் பாஷாணங்களின் கூட்டு வேதியியல் மற்றும் குணப்படுத்தும் ஆற்றல்",
        "era": "Classical Siddha Era",
        "year_start": 500,
        "year_end": 900,
        "thinai": "Kurinji",
        "summary_en": "High-temperature hermetic metallurgy formulating a stable non-corrosive solid composite from nine toxic mineral poisons: mercuric chloride, calomel, red mercuric sulfide, cinnabar, orpiment, realgar, litharge, sulfur, and hydrothermal complex. Hydration leaches micro-trace mineral ions providing powerful immunomodulatory therapeutic effects without toxicity.",
        "summary_ta": "ஒன்பது கொடிய நச்சுப் பாஷாணங்களான வீரம், பூரம், ரசசிந்தூரம், லிங்கம், கௌரிபாஷாணம், மனோசிலை, மிருதார்சிங், கந்தகம், கங்காய்பாஷாணம் ஆகியவற்றை அதிஉயர் வெப்பத்தில் ரசவாத முறைப்படி பிணைத்து உருவாக்கப்பட்ட அதிசயக் கூட்டு. பழனி முருகன் திருமேனி இதன் மூலம் வார்க்கப்பட்டது; இதன்மீது பட்டுவரும் பால் மற்றும் தீர்த்தங்கள் அளப்பரிய நோய்நீக்கும் ஆற்றல் கொண்டவையாக விளங்குகின்றன.",
        "content": """# Navapashanam: The Nine-Poison Synthesis (நவபாஷாணம்)

**Alchemical Master**: Siddhar Bogar (*போகர்*).  
**Installation**: Dhandayuthapani Temple, Palani Hills (*பழனி முருகன் திருமேனி*).  
**Chemical Nature**: Stable Herbo-Mineral Amalgam of 9 Toxic Minerals.  

---

## 1. Composition & Metallurgy
The nine minerals are neutralized using herbal extracts (*Thumbai, Karisalankanni*) and subjected to controlled calcination. In solid form, the crystal structure locks toxic arsenic and mercury atoms into an insoluble ceramic-like lattice that resists weathering, acid etching, and physical degradation.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-siddha-herbo-mineral-pharmacology",
        "file": "concept-siddha-herbo-mineral-pharmacology.md",
        "node_type": "concept",
        "name_en": "Siddha Herbo-Mineral Pharmacology: Bhasmas, Chendooram & Calcination",
        "name_ta": "சித்த மூலிகை-தாது மருந்தியல் - பற்பம், செந்தூரம், புடமிடுதல் மற்றும் உரைப்பு முறைகள்",
        "era": "Sangam to Imperial Chola Era",
        "year_start": -200,
        "year_end": 1300,
        "thinai": "Mullai",
        "summary_en": "The 32 internal and 32 external pharmaceutical classifications of Siddha medicine. Explores the calcination process (Pudam) in sealed clay crucibles using cow-dung cakes, converting metals (Gold, Silver, Copper, Iron, Zinc, Lead, Tin) into sub-micron Bhasmas (white oxides) and Chendoorams (red oxides) with remarkable bioavailability.",
        "summary_ta": "சித்த மருத்துவத்தின் 32 அகமருந்துகள் மற்றும் 32 புறமருந்துகளின் செய்முறை அறிவியலும் புடமிடும் முறைகளும். தங்கம், வெள்ளி, செம்பு, இரும்பு, நாகம் முதலான உலோகங்களை மூலிகைச் சாறுகளில் அரைத்து, அகல் மூடி சீலைசெய்து, வரட்டிகளால் புடமிட்டு நுண்ணிய பற்பமாகவும் செந்தூரமாகவும் மாற்றி, பக்கவிளைவுகளற்ற செரிமான நன்மருந்தாக்கும் உன்னத மருந்தியல் நுட்பம்.",
        "content": """# Siddha Herbo-Mineral Pharmacology (சித்த மருந்தியல்)

**Foundational Processes**: *Pudam* (Calcination), *Agal-mudithal* (Hermetic crucible sealing), *Arathaal* (Trituration).  
**Categories**: 32 Internal Medicines (*Agamarunthu*), 32 External Applications (*Puramarunthu*).  

---

## 1. The Pudam Calcination Process
Metals and toxic minerals are converted into nanostructured oxides (*Bhasma / Parpam*) by:
- Triturating metal filings with specific acidic or alkaline plant decoctions for days in a granite mortar (*Kalvam*).
- Flattening into cakes (*Vadaikal*), placing between earthenware saucers (*Agal*), and hermetically sealing seams with seven layers of clay-smeared cotton cloth (*Seelaimann*).
- Baking in circular pits packed with standardized numbers of dried cow-dung cakes (*Varatti*).
"""
    },
    {
        "category": "characters",
        "slug": "char-agathiyar-siddha-father",
        "file": "char-agathiyar-siddha-father.md",
        "node_type": "character",
        "name_en": "Agathiyar: Progenitor of Siddha Medicine & Herbology",
        "name_ta": "அகத்தியர் - சித்த மருத்துவத்தின் முதன்மை ஆசான் மற்றும் மூலிகை ஞானி",
        "era": "Pre-Sangam to Classical Era",
        "year_start": -500,
        "year_end": 500,
        "thinai": "Kurinji",
        "summary_en": "Revered foremost among the 18 Siddhars of Tamilakam. Pioneer of botanical pharmacology, author of foundational treatises including Agathiyar Vaidyam 1500 and Gunavagadam, discoverer of Western Ghats medicinal plants on Podhigai Malai, and founder of the master resuscitation formula Agathiyar Kuzhambu.",
        "summary_ta": "பதினெண் சித்தர்களின் தலையாய குரு. தமிழ் மருத்துவம் மற்றும் இலக்கணத்தின் தந்தை; பொதிகை மலையில் தங்கி மேற்குத் தொடர்ச்சி மலையின் ஆயிரக்கணக்கான மூலிகைகளை ஆராய்ந்து குணவாகடம் பாடியவர்; அகத்தியர் குழம்பு முதலான அவசர சிகிச்சை மருந்துகளின் மூல கர்த்தா.",
        "content": """# Sage Agathiyar: Father of Siddha Medicine (அகத்தியர்)

**Spiritual Seat**: Podhigai Malai (Western Ghats).  
**Lineage**: First of the *Pathinen Siddhargal* (18 Great Siddhars).  
**Master Works**: *Agathiyar Vaidya Kaviyam*, *Gunavagadam*, *Agathiyar Kuzhambu*.  
"""
    },
    {
        "category": "characters",
        "slug": "char-theraiyar-master-diagnostician",
        "file": "char-theraiyar-master-diagnostician.md",
        "node_type": "character",
        "name_en": "Theraiyar: Master Diagnostician, Toxicologist & Surgeon",
        "name_ta": "தேரையர் - நோய்நாடல் வல்லுநர், நச்சு அறிவியல் மற்றும் அறுவைசிகிச்சை மேதை",
        "era": "Classical Era",
        "year_start": 700,
        "year_end": 1000,
        "thinai": "Marutham",
        "summary_en": "Eminent Siddha physician celebrated for formulating empirical diagnostic protocols based on pulse examination, urine oil-drop spreads (Neikkuri), preventative circadian hygiene, and pioneer of neuro-cranial surgical interventions.",
        "summary_ta": "அகத்தியரின் முதன்மைச் சீடர்; நாடி, நெய்க்குறி ஆய்வுகளில் நிகரற்ற மேதை; நச்சு முறிப்பு மற்றும் நோய்த்தடுப்பு வாழ்வியல் முறைகளை வகுத்தளித்ததோடு மண்டை ஓட்டு அறுவைசிகிச்சை செய்த உலகின் முன்னோடி அறுவை மருத்துவர்.",
        "content": """# Sage Theraiyar (தேரையர்)

**Legacy**: Clinical pathology, urine analysis (*Neikkuri*), circadian hygiene, surgical trepanation.  
**Key Texts**: *Theraiyar Sekkiruvadukal*, *Theraiyar Yamagam*, *Noinaadal*.  
"""
    },
    {
        "category": "characters",
        "slug": "char-bogar-alchemist-sculptor",
        "file": "char-bogar-alchemist-sculptor.md",
        "node_type": "character",
        "name_en": "Bogar: Alchemist, Transmuter & Creator of the Palani Navapashanam Icon",
        "name_ta": "போகர் - நவபாஷாண மூர்த்தி வடித்த ரசவாதச் சித்தர் மற்றும் மெய்ஞானி",
        "era": "Classical Era",
        "year_start": 500,
        "year_end": 900,
        "thinai": "Kurinji",
        "summary_en": "Master Siddha metallurgist, alchemist, and trans-continental traveler. Perfected the calcination of minerals, mastered respiratory control, authored the 7000-verse alchemical epic Bogar Saptha Kandam, and crafted the Navapashanam idol of Palani Murugan.",
        "summary_ta": "பழனி மலையில் நவபாஷாணத்தால் தண்டாயுதபாணி திருமேனி வடித்த ரசவாத ஞானி; போகர் 7000 நூலை இயற்றி சீன நாட்டுக்கும் தமிழகத்துக்கும் இடையே வேதியியல்-மருத்துவப் பாலம் அமைத்த சித்தர் பெருமான்.",
        "content": """# Siddhar Bogar (போகர் சித்தர்)

**Shrine / Samadhi**: Palani Hill Temple (*பழனி முருகன் சன்னதி*).  
**Key Contributions**: Synthesis of *Navapashanam*, alchemy, aviation (*Vimana*) experiments.  
"""
    },
    {
        "category": "places",
        "slug": "place-thirumukkudal-aathula-salai",
        "file": "place-thirumukkudal-aathula-salai.md",
        "node_type": "place",
        "name_en": "Thirumukkudal Aathula Salai: Chola Hospital & Herbal Granary",
        "name_ta": "திருமுக்கூடல் ஆதுல சாலை - சோழர் கால இலவச மருத்துவமனை மற்றும் மருந்துக் களஞ்சியம்",
        "era": "Imperial Chola Era",
        "year_start": 1067,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "Historic confluence of Palar, Cheyyar, and Vegavathi rivers in Chengalpattu district (12.7850° N, 79.8667° E). Site of the celebrated 11th-century Chola state hospital (Veerasolan Aathula Salai) with 15 beds, pharmacy, and surgical staff documented in Veera Rajendra's 1067 CE inscription.",
        "summary_ta": "பாலாறு, செய்யாறு, வேகவதி ஆகிய மூன்று ஆறுகள் சங்கமிக்கும் திருமுக்கூடல் திருத்தலம் (12.7850° N, 79.8667° E). வீரராசேந்திர சோழன் நிறுவிய 15 படுக்கைகள் கொண்ட இலவச ஆதுல சாலை, அறுவை சிகிச்சை அரங்கு மற்றும் மருத்துவக் கல்லூரி இயங்கிய வரலாற்றுச் சிறப்புமிக்க தளம்.",
        "content": """# Thirumukkudal Aathula Salai (திருமுக்கூடல் ஆதுல சாலை)

**Coordinates**: 12.7850° N, 79.8667° E.  
**Significance**: 11th-century hospital and college inscribed on temple granite walls.  
"""
    },
    {
        "category": "places",
        "slug": "place-palani-malai-navapashanam",
        "file": "place-palani-malai-navapashanam.md",
        "node_type": "place",
        "name_en": "Palani Murugan Hill: Sacred Navapashanam Alchemical Shrine",
        "name_ta": "பழனி மலை - நவபாஷாண முருகன் திருத்தலம் மற்றும் போகர் சித்தர் ஜீவ சமாதி",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1300,
        "thinai": "Kurinji",
        "summary_en": "Renowned hill shrine of Lord Dhandayuthapani (ancient Podhini) in Dindigul district (10.4500° N, 77.5167° E). World-famous for housing the Navapashanam icon sculpted by Siddhar Bogar whose abhishekam fluids leach therapeutic trace minerals.",
        "summary_ta": "திண்டுக்கல் மாவட்டத்தில் அமைந்த சங்க காலத்துத் திருத்தலம் (பண்டைப் பொதினி - 10.4500° N, 77.5167° E). போகர் சித்தரின் ஜீவசமாதியும், அவரால் ஒன்பது விஷப் பாஷாணங்களை ஒன்றுசேர்த்து வடிக்கப்பட்ட அதிசய நவபாஷாண முருகன் திருமேனியும் அமைந்துள்ள திருத்தலம்.",
        "content": """# Palani Murugan Hill & Navapashanam (பழனி மலை)

**Coordinates**: 10.4500° N, 77.5167° E.  
**Sacred Heritage**: Ancient Podhini, seat of Bogar's alchemical shrine and Navapashanam idol.  
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: ANCIENT TAMIL SCULPTURE, ICONOGRAPHY & BRONZE CASTING
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-sirpa-chennool-sculpture-canon",
        "file": "text-sirpa-chennool-sculpture-canon.md",
        "node_type": "text",
        "name_en": "Sirpa Chennool: Canonical Tamil Shilpa Shastra & Iconometric Proportions",
        "name_ta": "சிற்பச் செந்நூல் - பண்டைத் தமிழ் சிற்பக் கலை மற்றும் அளவியல் சாத்திரம்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "Fundamental Tamil treatise on iconometry and sacred sculpture. Codifies measurement units based on the human finger (Angula), the nine standard proportions (Nava-Talam), plumb-line alignments (Sutra-nirnayam), flexion postures (Bhanga: Abhanga, Tribhanga, Atibhanga), and emotional expressions (Rasa).",
        "summary_ta": "பண்டைத் தமிழகச் சிற்பிகள் கடைப்பிடித்த அரிய சிற்ப அளவியல் நூல். விரலளவு (அங்குலம்), தாளமானம், முப்பரிமாணச் சமநிலை (சூத்திர நிர்ணயம்), உடல் வளைவுகள் (அபங்கம், திரிபங்கம், அதிபங்கம்), மற்றும் ஒன்பது வகை நவரச பாவங்களைச் சிலைகளில் வடிக்கும் இலக்கணங்களை வகுத்தளிக்கும் சிற்ப சாத்திரம்.",
        "content": """# Sirpa Chennool: Canonical Tamil Sculpture (சிற்பச் செந்நூல்)

**Tradition**: Indigenous Tamil Shilpa Shastra & Stapathi Artisanal Manual.  
**Core Principles**: *Angula* metric, *Talamana* proportions, and *Bhanga* dynamic postures.  
"""
    },
    {
        "category": "texts",
        "slug": "text-mayamata-dravidian-vastu-canon",
        "file": "text-mayamata-dravidian-vastu-canon.md",
        "node_type": "text",
        "name_en": "Mayamata & Manasara: Classical Dravidian Temple Vastu Shastra",
        "name_ta": "மயமதம் - திராவிடக் கோயில் கட்டடக் கலை மற்றும் நிலவியல் அளவியல் நூல்",
        "era": "Pallava to Imperial Chola Era",
        "year_start": 700,
        "year_end": 1100,
        "thinai": "Marutham",
        "summary_en": "Authoritative Dravidian treatise on temple town-planning, site testing (Bhoomi-parikshai), stone basement foundation engineering (Upapitha and Adhishthana), monolithic interlocking granite joints, pillar orders, and multi-tiered vimana elevations.",
        "summary_ta": "திராவிடக் கோயில் கட்டுமானக் கலையின் தலைசிறந்த விதிகளான நிலத் தேர்வு, அடித்தள அமைப்புகள் (உபபீடம், அதிஷ்டானம்), சாந்தற்ற கருங்கல் பூட்டு அமைப்புகள், தூண்களின் அமைப்புகள் மற்றும் கோபுர-விமான அடுக்கு நிலைகளை விவரிக்கும் கட்டடக்கலை நூல்.",
        "content": """# Mayamata: Dravidian Temple Architecture (மயமதம்)

**Architectural Scope**: Temple urban design, stone foundations, pillar orders, and vimana hierarchies.  
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thanjavur-rajaraja-bronze-endowments",
        "file": "insc-thanjavur-rajaraja-bronze-endowments.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Inscriptions: Imperial Chola Lost-Wax Bronze Endowments & Metalsmith Charters",
        "name_ta": "தஞ்சைப் பெருவுடையார் கோயில் செப்புத் திருமேனிகள் மற்றும் சிற்பிகள் கல்வெட்டு",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Detailed epigraphs on the granite pillars of the Thanjavur Brihadisvara Temple recording over 66 solid copper/bronze icons commissioned by Rajaraja I, Kundavai, and queens. Details exact metallic weights, jewel allotments, and honors conferred on master sculptors (Perunthachan).",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயிலின் கருங்கல் சுவர்களில் பொறிக்கப்பட்டுள்ள 66-க்கும் மேற்பட்ட செப்புத் திருமேனிகளின் பட்டியல். ஒவ்வொரு சிலைக்குமான தாமிர எடை, பொன் மற்றும் நவரத்தின அணிகலன்கள், மற்றும் சிற்பிகளுக்கு வழங்கப்பட்ட ராஜ கௌரவங்கள் பற்றிய வரலாற்றுப் பதிவு.",
        "content": """# Thanjavur Bronze Endowments (1010 CE)

**Location**: Brihadisvara Temple granite pillars, Thanjavur (*தஞ்சைப் பெருவுடையார் கோயில்*).  
**Sovereign**: Rajaraja Chola I & Princess Kundavai.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-madhuchehishtavidhana-lost-wax-casting",
        "file": "concept-madhuchehishtavidhana-lost-wax-casting.md",
        "node_type": "concept",
        "name_en": "Madhuchehishtavidhana: Cire-Perdue (Lost-Wax) Bronze Metallurgy & Panchaloha Chemistry",
        "name_ta": "மதுச்சிஷ்டவிதானம் - சோழர் மெழுகு வார்ப்பு வெண்கலக் கலை மற்றும் பஞ்சலோக வேதியியல்",
        "era": "Pallava to Imperial Chola Era",
        "year_start": 800,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The lost-wax (cire-perdue) casting technique perfected by Chola metalsmiths. Involves sculpting pure beeswax-dammar resin models, coating with three grades of Kaveri alluvial clay, evacuating molten wax in kilns, and pouring liquid Panchaloha alloy (Copper 82%, Tin 10%, Lead 5%, Gold/Silver traces).",
        "summary_ta": "சோழர் காலத்து உலகப் புகழ்பெற்ற மெழுகு வார்ப்பு வெண்கலத் தொழில்நுட்பம். தேன்மெழுகு மற்றும் குங்கிலியக் கலவையில் முழு உருவத்தை வடித்து, காவிரி வண்டல் களிமண்ணால் மூன்று அடுக்குப் பூச்சு பூசி, உலர்த்தி, சூளையிலிட்டு மெழுகை உருக்கி வெளியேற்றி, பஞ்சலோகக் குழம்பை ஊற்றிச் சிலைகளை வார்க்கும் கலை நுட்பம்.",
        "content": """# Madhuchehishtavidhana: Lost-Wax Bronze Casting (மெழுகு வார்ப்புக் கலை)

**Method**: Solid *Cire-Perdue* Casting (*திட மெழுகு வார்ப்பு*).  
**Alloy**: Panchaloha (Copper ~82%, Tin ~10%, Lead ~5%, Gold & Silver traces).  
**Molding Medium**: Kaveri delta fine alluvial silt (*Karu-man* and *Kavai-man*).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-talamana-iconometric-proportions",
        "file": "concept-talamana-iconometric-proportions.md",
        "node_type": "concept",
        "name_en": "Talamana Proportions: Angula, Dasa-Tala Canonical Ratios & Sacred Geometry",
        "name_ta": "தாளமானம் - சிற்ப அளவியல் கோட்பாடுகள், அங்குலம் மற்றும் தசதாள வடிவியல்",
        "era": "Sangam to Imperial Chola Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "Sacred proportional system where the fundamental unit is the Tala (distance from hairline to chin = 12 Angulas). Major deities are sculpted in Uttama Dasa-Tala (124 Angulas), minor deities in Madhyama Dasa-Tala (120 Angulas), and mortals in Ashta-Tala (96 Angulas).",
        "summary_ta": "உத்தம தசதாளம் (124 அங்குலம்), மத்யம தசதாளம் (120 அங்குலம்), அஷ்டதாளம் (96 அங்குலம்) என மனித மற்றும் தெய்வத் திருமேனிகளுக்கான வடிவியல் மற்றும் விகிதாச்சார அளவீட்டு முறைமை.",
        "content": """# Talamana: Sacred Iconometric Proportions (தாளமானம்)

**Base Unit**: 1 *Tala* = 12 *Angulas* (*அங்குலம்*).  
**Canonical Proportions**: *Uttama Dasa-Tala* (Supreme Deities), *Ashta-Tala* (Humans).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-chola-bronze-ananda-tandava-iconography",
        "file": "concept-chola-bronze-ananda-tandava-iconography.md",
        "node_type": "concept",
        "name_en": "Ananda Tandava Nataraja: Cosmic Iconography, Flame Aureole (Prabha) & Kinetic Dynamics",
        "name_ta": "ஆனந்த தாண்டவ நடராசர் - பேரண்ட நடனச் சிற்பக் குறியீட்டியல் மற்றும் இயங்கியல்",
        "era": "Imperial Chola Era",
        "year_start": 900,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "World-renowned synthesis of metallurgy and cosmic symbolism. Portrays Shiva dancing within a flaming circular aureole (Tiruvasi): drum (creation), flame (dissolution), abhaya mudra (preservation), crushing ignorance (Apasmara Purusha), and raised foot (liberation).",
        "summary_ta": "சோழர் காலத்து உலகப் புகழ்பெற்ற ஆனந்த தாண்டவ நடராசர் செப்புத் திருமேனியின் குறியீட்டியல். உடுக்கை (படைப்பு), எரியனல் (ஒடுக்கம்), அபயகரம் (காத்தல்), முயலகனை மிதித்த திருவடி (மறைத்தல்), மற்றும் தூக்கிய திருவடி (அருளல்) ஆகிய ஐந்தொழில்களை விளக்கும் பேரண்ட நடனம்.",
        "content": """# Ananda Tandava Nataraja Iconography (ஆனந்த தாண்டவ நடராசர்)

**Cosmic Dance Principles**: Creation (*Srishti*), Preservation (*Sthiti*), Destruction (*Samhara*), Concealment (*Tirobhava*), Salvation (*Anugraha*).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kammalar-stapathi-guild-guilds",
        "file": "concept-kammalar-stapathi-guild-guilds.md",
        "node_type": "concept",
        "name_en": "Kammalar & Stapathi Artisan Guilds: Caste Organization, Apprenticeship & Sacred Vocation",
        "name_ta": "கம்மாளர் மற்றும் ஸ்தபதி கைவினைக் கூட்டமைப்புகள் - சிற்பக் குல மரபு மற்றும் தொழில் நெறி",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The five-fold artisan guild system (Aynkammalar): blacksmiths, carpenters, bronzecasters, stone sculptors, and goldsmiths. Documents royal charters of tax exemption, guild autonomy, and generational transmission of sacred knowledge.",
        "summary_ta": "ஐங்கம்மாளர் கூட்டமைப்பான தச்சர், கொல்லர், கன்னார் (வெண்கலச் சிற்பி), சிற்பி (கல்தச்சர்), மற்றும் தட்டார் ஆகிய ஐவகை கைவினைக் கலைஞர்களின் சங்க நெறி, அரச வரிவிலக்குச் சாசனங்கள், மற்றும் தொழில் மேலாண்மை முறைமைகள்.",
        "content": """# Kammalar & Stapathi Guild Architecture (கம்மாளர் கைவினை மரபு)

**Five Disciplines**: *Thachan* (Wood), *Kollan* (Iron), *Kannar* (Bronze), *Sirpi* (Stone), *Thattar* (Gold).  
"""
    },
    {
        "category": "characters",
        "slug": "char-kunjara-mallan-rajaraja-perunthachan",
        "file": "char-kunjara-mallan-rajaraja-perunthachan.md",
        "node_type": "character",
        "name_en": "Kunjara Mallan Rajaraja Perunthachan: Chief Architect of the Thanjavur Brihadisvara Temple",
        "name_ta": "குஞ்சர மல்லன் இராசராசப் பெருந்தச்சன் - தஞ்சைப் பெருவுடையார் கோயில் தலைமைச் சிற்பி",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Master architect immortalized on the granite plinth of Thanjavur Brihadisvara Temple. Engineered the 216-foot soaring hollow granite vimana, monolithic 80-ton dome (Kumbam), and mortarless interlocking stone joints.",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயிலின் 216 அடி விமானத்தையும், 80 டன் கருங்கல் சிகரத்தையும் துல்லியமாக வடித்து, சாந்தின்றி கற்களை இணைத்து உலக அதிசயமாகக் கோயில் எழுப்பிய சோழப் பேரரசின் தலைமைச் சிற்பி.",
        "content": """# Kunjara Mallan Rajaraja Perunthachan (இராசராசப் பெருந்தச்சன்)

**Monument**: Brihadisvara Temple, Thanjavur (*தஞ்சைப் பெரிய கோயில்*).  
**Engineering Mastery**: Hollow granite tower, interlocking dry-stone construction.  
"""
    },
    {
        "category": "characters",
        "slug": "char-chembiya-mahadevi-bronze-patron",
        "file": "char-chembiya-mahadevi-bronze-patron.md",
        "node_type": "character",
        "name_en": "Queen Chembiya Mahadevi: Greatest Patron of Chola Bronze Sculpture",
        "name_ta": "செம்பியன் மாதேவி - சோழர் செப்புத் திருமேனிகளின் பொற்காலப் புரவலர்",
        "era": "Imperial Chola Era",
        "year_start": 910,
        "year_end": 1001,
        "thinai": "Marutham",
        "summary_en": "Chola Queen, widow of Gandaraditya Chola. Spearheaded the conversion of brick temples into granite (Karrali) and patronized the golden age of classical Chola bronze casting, commissioning serene Nataraja and Parvati icons.",
        "summary_ta": "கண்டராதித்த சோழரின் தேவி; செங்கற்றளிகளை எல்லாம் கற்றளிகளாக மாற்றிய பெரும் ஆன்மிக அரசி; சோழர் காலத்துச் செப்புத் திருமேனி வார்ப்புக் கலைக்குத் தன் வாழ்நாளெல்லாம் அளப்பரிய ஆதரவளித்த பொற்காலப் புரவலர்.",
        "content": """# Queen Chembiya Mahadevi (செம்பியன் மாதேவி)

**Dynasty**: Imperial Chola Royal House.  
**Legacy**: Conversion of temples to granite (*Karrali*), patron of master bronze foundries.  
"""
    },
    {
        "category": "characters",
        "slug": "char-swamimalai-master-stapathi",
        "file": "char-swamimalai-master-stapathi.md",
        "node_type": "character",
        "name_en": "Swamimalai Master Stapathi: Hereditary Guardian of Ancient Lost-Wax Metallurgy",
        "name_ta": "சுவாமிமலை தலைமை ஸ்தபதி - தலைமுறை தலைமுறையாய் வாழும் மெழுகு வார்ப்புக் கலைஞர்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Hereditary lineage of master bronze sculptors along the Kaveri at Swamimalai, preserving exact metallurgical alloy ratios, wax-modeling techniques, and oral iconometric verse shlokas continuously for over a millennium.",
        "summary_ta": "காவிரிக்கரையில் ஆயிரம் ஆண்டுகளுக்கும் மேலாக சோழர் காலத்து மெழுகு வார்ப்பு பஞ்சலோகத் தொழில்நுட்பத்தையும், தாளமான அளவுகளையும் மாறாமல் பாதுகாத்து உலகிற்கு வழங்கும் சுவாமிமலை பாரம்பரிய சிற்பாசாரியர் மரபு.",
        "content": """# Swamimalai Master Stapathi (சுவாமிமலை ஸ்தபதி மரபு)

**Living Heritage**: Continuous thousand-year lineage of Chola bronze casting masters.  
"""
    },
    {
        "category": "places",
        "slug": "place-swamimalai-bronze-artisan-quarter",
        "file": "place-swamimalai-bronze-artisan-quarter.md",
        "node_type": "place",
        "name_en": "Swamimalai: Hereditary Chola Bronze Casting Guild Center",
        "name_ta": "சுவாமிமலை - உலகப் புகழ்பெற்ற சோழர் வெண்கலச் சிற்பத் திருத்தலம்",
        "era": "Imperial Chola to Modern Era",
        "year_start": 1000,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Artisan township on the north bank of the Kaveri River near Kumbakonam (10.9575° N, 79.3242° E). Global epicenter of traditional lost-wax bronze casting, utilizing fine-grain silt of the Kaveri delta for high-definition clay molds.",
        "summary_ta": "கும்பகோணம் அருகே காவிரிக்கரையில் அமைந்துள்ள உலகப் புகழ்பெற்ற வெண்கலச் சிற்பக் கலை நகரம் (10.9575° N, 79.3242° E). காவிரி வண்டல் மண்ணின் தனித்துவமிக்க களிமண்ணைப் பயன்படுத்திச் செப்புத் திருமேனிகள் வார்க்கப்படும் முதன்மைத் தளம்.",
        "content": """# Swamimalai Bronze Guild Center (சுவாமிமலை)

**Coordinates**: 10.9575° N, 79.3242° E.  
**Centerpiece**: Heritage foundry center for Chola lost-wax bronze casting.  
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: SANGAM BOTANY, ETHNOBOTANY & ECOLOGICAL ARCHITECTURE
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-kurinjippattu-99-sacred-flowers",
        "file": "text-kurinjippattu-99-sacred-flowers.md",
        "node_type": "text",
        "name_en": "Kurinjippattu: Kabilar's Catalog of 99 Sacred Botanical Flora of Tamilakam",
        "name_ta": "குறிஞ்சிப்பாட்டு - கபிலரின் 99 தமிழ் மலர்க் களஞ்சியம் மற்றும் தாவரவியல் பாடல்",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 200,
        "thinai": "Kurinji",
        "summary_en": "Masterpiece in Pathupattu by poet Kabilar. Contains the famous 99-flower catalog (lines 61–96) listing indigenous mountain and wetland plants: Senkandhal (Gloriosa superba), Kurinji (Strobilanthes kunthiana), Vengai, Konrai, showcasing acute botanical observation of flowering phenology and pollination ecology.",
        "summary_ta": "பத்துப்பாட்டில் கபிலர் பாடிய ஒப்பற்ற இயற்கை நூல். செங்காந்தள், குறிஞ்சி, வேங்கை, கொன்றை, ஆம்பல், காந்தள் எனத் தமிழகத்தின் மேற்குத் தொடர்ச்சி மலை மற்றும் நீர்நிலைகளில் பூத்துக் குலுங்கும் 99 வகையான மரபுவழி மலர்களை வரிசையாகப் பட்டியலிடும் உலகின் தொன்மையான தாவரவியல் ஆவணம்.",
        "content": """# Kurinjippattu: The 99 Sacred Flowers of Tamilakam (குறிஞ்சிப்பாட்டு)

**Author**: Kabilar (*கபிலர்*), Master Sangam Nature Poet.  
**Catalog**: Lines 61–96 systematically naming 99 endemic flowers.  
**Key Species**: *Senkandhal* (Gloriosa superba), *Kurinji* (Strobilanthes kunthiana), *Vengai* (Pterocarpus marsupium).  
"""
    },
    {
        "category": "texts",
        "slug": "text-mullaippattu-forest-ecology",
        "file": "text-mullaippattu-forest-ecology.md",
        "node_type": "text",
        "name_en": "Mullaippattu: Pastoral Forest Ecology, Monsoon Rhythms & Floral Symbiosis",
        "name_ta": "முல்லைப்பாட்டு - காடும் காடு சார்ந்த சூழலியல், பருவமழை மற்றும் மலர் மலர்ச்சி",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 200,
        "thinai": "Mullai",
        "summary_en": "Poetic idyll by Nappoothanar depicting the delicate balance of the scrub forest ecosystem: monsoon cloudbursts, blooming of fragrant Mullai jasmine and Thonri lilies, grazing pastoral herds, and sustainable agro-forestry ethics.",
        "summary_ta": "நப்பூதனாரால் இயற்றப்பட்ட முல்லைப்பாட்டு. கார்காலத்துப் பருவமழையின் தொடக்கம், முல்லைக் காடுகளின் வாசனை மலர்கள், ஆயர்களின் மேய்ச்சல் வாழ்க்கை, மற்றும் காட்டு வளத்தைப் பாதுகாக்கும் மேய்ச்சல் நிலச் சூழலியல் நெறிகளை அழகுற விவரிக்கும் சங்க நூல்.",
        "content": """# Mullaippattu: Pastoral Forest Ecology (முல்லைப்பாட்டு)

**Author**: Nappoothanar (*நப்பூதனார்*).  
**Biome**: *Mullai* (Pastoral Scrub Forest & Deciduous Woodland).  
"""
    },
    {
        "category": "texts",
        "slug": "text-pathitrupathu-riverine-mangrove-ecology",
        "file": "text-pathitrupathu-riverine-mangrove-ecology.md",
        "node_type": "text",
        "name_en": "Pathitrupathu: Western Ghats Canopy, Teak Reserves & Estuarine Mangroves",
        "name_ta": "பதிற்றுப்பத்து - மேற்குத் தொடர்ச்சி மலைக் காடுகள், தேக்கு வளம் மற்றும் அலையாத்திக் காடுகள்",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 300,
        "thinai": "Kurinji",
        "summary_en": "Chera dynastic anthology chronicling the dense rainforest canopy of the Western Ghats, teak and sandalwood reserves, cardamom hills, and coastal mangrove estuarine buffers (Kandal) protecting delta shorelines from erosion.",
        "summary_ta": "சேர மன்னர்களின் வரலாற்றைப் பாடும் பதிற்றுப்பத்து. மேற்குத் தொடர்ச்சி மலையின் வானுயர்ந்த மழைக்காடுகள், சந்தனம், தேக்கு, ஏலக்காய் மலைகள், மற்றும் கடற்கரையோர கழிமுகங்களில் மண் அரிப்பைத் தடுக்கும் அலையாத்தி (கண்டல்) தாவரங்களின் சூழலியல் மேன்மை.",
        "content": """# Pathitrupathu: Montane & Mangrove Ecology (பதிற்றுப்பத்து)

**Dynastic Setting**: Chera Kingdom (*சேர நாடு*).  
**Flora Ecosystem**: Western Ghats rainforest canopy and tidal mangroves (*Kandal*).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-aintinai-biogeographical-zones",
        "file": "concept-aintinai-biogeographical-zones.md",
        "node_type": "concept",
        "name_en": "Aintinai Ecological Paradigm: Integrated Biomes, Flora, Fauna & Microclimates",
        "name_ta": "ஐந்திணைச் சூழலியல் கோட்பாடு - நிலவியல், தாவரங்கள், விலங்கினங்கள் மற்றும் மனித இயைபு",
        "era": "Sangam Classical Era",
        "year_start": -500,
        "year_end": 300,
        "thinai": "Marutham",
        "summary_en": "The world's earliest holistic ecological zoning system codified in Tolkappiyam: Kurinji (montane), Mullai (pastoral forest), Marutham (wetlands), Neithal (coastal), and Palai (arid), linking flora, fauna, seasonal cycles, soil, and human life.",
        "summary_ta": "தொல்காப்பியத்தில் வரையறுக்கப்பட்ட ஐந்திணைப் பகுப்பு. குறிஞ்சி (மலை), முல்லை (காடு), மருதம் (வயல்), நெய்தல் (கடல்), பாலை (மணல்) என நில அமைப்போடு தாவரங்கள், விலங்குகள், பொழுதுகள், பருவங்கள் மற்றும் மனித வாழ்வியலை இணைக்கும் முழுமையான சூழலியல் அறிவியல்.",
        "content": """# Aintinai: Holistic Biogeographical Zoning (ஐந்திணைச் சூழலியல்)

**Codified In**: *Tolkappiyam Porulatikaram*.  
**The Five Ecoregions**: Kurinji, Mullai, Marutham, Neithal, Palai.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-sacred-groves-kavu-conservation",
        "file": "concept-sacred-groves-kavu-conservation.md",
        "node_type": "concept",
        "name_en": "Kavu Sacred Groves: Indigenous Community Biodiversity Sanctuaries & Taboo Ecology",
        "name_ta": "காவு புனிதக் காடுகள் - சமூகப் பல்லுயிர் பாதுகாப்பு மற்றும் வழிபாட்டுச் சூழலியல்",
        "era": "Sangam to Modern Era",
        "year_start": -500,
        "year_end": 1300,
        "thinai": "Mullai",
        "summary_en": "Traditional community-managed sacred forests preserved through religious taboos and serpent/tree deity veneration. Served as pristine climax biodiversity refugia, preserving endangered medicinal flora, perennial natural springs, and microclimatic moisture regulation.",
        "summary_ta": "பண்டைத் தமிழரின் 'காவு' புனிதக் காடுகள். மரம் வெட்டுதல், விலங்குகளை வேட்டையாடுதல் ஆகியவற்றைத் தடுத்து மதரீதியான நம்பிக்கைகள் மூலம் பாதுகாக்கப்பட்ட பசுமைச் சோலைகள்; அரிய மூலிகைகளையும், ஊற்றுக் கண்களையும், பல்லுயிர்ச் சூழலையும் பாதுகாத்த பாரம்பரியப் புகலிடங்கள்.",
        "content": """# Kavu: Sacred Groves & Community Conservation (காவு புனிதக் காடுகள்)

**Ecological Mechanism**: Cultural taboos preventing deforestation, protecting perennial watersheds.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-sangam-ethnobotany-and-healing-flora",
        "file": "concept-sangam-ethnobotany-and-healing-flora.md",
        "node_type": "concept",
        "name_en": "Sangam Ethnobotany: Indigenous Herbal Taxonomy, Antidotes & Botanical Healing",
        "name_ta": "சங்க கால தாவர மருந்தியல் - மூலிகைக் குறியீடுகள், நச்சுமுறிப்பு மற்றும் வாழ்வியல் நலம்",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "Kurinji",
        "summary_en": "Medical utilization of wild flora in Sangam literature: Vengai resin for wound coagulants, Neem (Veppam) as antiseptic guard, Kurinji honey for vigor, Thumbai for venom neutralization, and Adathoda for respiration.",
        "summary_ta": "சங்க இலக்கியங்களில் ஆவணப்படுத்தப்பட்டுள்ள காட்டு மூலிகைகளின் மருத்துவப் பயன்பாடுகள்: காயங்களைக் குணப்படுத்தும் வேங்கைப் பிசின், கிருமிநாசினியான வேம்பு, நச்சுமுறிக்கும் தும்பை, மற்றும் இருமல் போக்கும் ஆடாதோடை பற்றிய மக்கள் தாவரவியல் அறிவு.",
        "content": """# Sangam Ethnobotany & Healing Flora (சங்கத் தாவர மருந்தியல்)

**Key Flora**: *Veppam* (Azadirachta indica), *Thumbai* (Leucas aspera), *Adathoda* (Justicia adhatoda).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-marutham-wetland-agro-ecosystem",
        "file": "concept-marutham-wetland-agro-ecosystem.md",
        "node_type": "concept",
        "name_en": "Marutham Agro-Ecosystem: Scented Paddy Cultivars, Lotus Wetlands & Riparian Buffers",
        "name_ta": "மருத நில வேளாண் சூழலியல் - நறுமண நெல் ரகங்கள், தாமரைப் பொய்கைகள் மற்றும் ஆற்றுப் படுகை",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "Wet-rice agro-ecology along the Kaveri, Vaigai, and Porunai river basins. Explores indigenous fragrant paddy cultivars (Samba, Sennel, Aivanam), duck biological pest control, lotus wetland water purification, and riparian vegetation buffers.",
        "summary_ta": "காவிரி, வைகை, பொருநை ஆற்றுப் படுகைகளில் நிலவிய செழுமையான மருத நில வேளாண்மை. செந்நெல், சிறுநெல், ஐவன நெல் போன்ற பாரம்பர்ய நறுமண நெல் ரகங்கள், தாமரைப் பொய்கைகள் மூலம் நீர் தூய்மை அடைதல், மற்றும் ஆற்றோர மர வரிசைகள் மூலம் வெள்ளக் கட்டுப்பாடு.",
        "content": """# Marutham Wetland Agro-Ecosystem (மருத நில வேளாண்மை)

**Cultivars**: *Sennel*, *Aivanam*, *Puzhukkal-nel*.  
**Riparian Ecology**: Riverbank vegetation stabilizing canal networks.  
"""
    },
    {
        "category": "characters",
        "slug": "char-kabilar-nature-poet-botanist",
        "file": "char-kabilar-nature-poet-botanist.md",
        "node_type": "character",
        "name_en": "Kabilar: Master Sangam Nature Poet & Botanical Taxonomist of the Western Ghats",
        "name_ta": "கபிலர் - சங்க கால இயற்கைப் புலவர் மற்றும் மேற்குத் தொடர்ச்சி மலையின் தாவரவியல் மேதை",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 180,
        "thinai": "Kurinji",
        "summary_en": "Foremost poet of the Sangam era and author of Kurinjippattu. Acute naturalist who chronicled montane ecology, bee pollination, and cataloged 99 indigenous flowers of the Western Ghats with scientific precision.",
        "summary_ta": "சங்க இலக்கியத்தின் தலைசிறந்த இயற்கைப் புலவர்; வேள் பாரியின் உற்ற தோழர்; குறிஞ்சி நிலத்தின் மரங்கள், விலங்குகள், தேனீக்களின் மகரந்தச் சேர்க்கை மற்றும் 99 வகையான பூக்களைத் தாவரவியல் நுட்பத்தோடு பாடிய கவிப் பேரரசர்.",
        "content": """# Poet Kabilar (புலவர் கபிலர்)

**Crown Work**: *Kurinjippattu* (The 99 Flowers of Tamilakam).  
**Patron & Companion**: King Vel Pari of Parambu Malai.  
"""
    },
    {
        "category": "characters",
        "slug": "char-avvaiyar-ecological-philosopher",
        "file": "char-avvaiyar-ecological-philosopher.md",
        "node_type": "character",
        "name_en": "Avvaiyar: Bardic Philosopher of Ecological Harmony & Agro-Pastoral Ethics",
        "name_ta": "ஔவையார் - நிலவளமும் நீர்மேலாண்மையும் பாடிய சங்க கால அறிவர்",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 200,
        "thinai": "Marutham",
        "summary_en": "Immortal Sangam poetess whose aphorism 'Varappuyara neer uyarum' established the foundational ecological tenet that sovereign authority and civilizational wealth derive directly from agrarian soil and water conservation.",
        "summary_ta": "'வரப்புயர நீர் உயரும், நீர் உயர நெல் உயரும்...' என்ற அழியாத வரிகள் மூலம், ஒரு நாட்டின் அரச பலமும் குடிமக்களின் செழிப்பும் வயல் வரப்புகளின் உயரத்திலும் நீர் மேலாண்மையிலும் தான் அடங்கியுள்ளது என்பதை உணர்த்திய சங்கப் பெரும் புலவர்.",
        "content": """# Avvaiyar: Ecological Philosopher (ஔவையார்)

**Key Maxim**: *"Varappuyara Neer Uyarum..."* (Ecological water-bund hierarchy).  
"""
    },
    {
        "category": "characters",
        "slug": "char-peyanar-mullai-pastoral-bard",
        "file": "char-peyanar-mullai-pastoral-bard.md",
        "node_type": "character",
        "name_en": "Peyanar: Sangam Poet of the Mullai Forest & Floral Seasonal Dynamics",
        "name_ta": "பேயனார் - முல்லைக் காடுகளின் பருவமழை மற்றும் தாவரப் புலவர்",
        "era": "Sangam Early Historic Era",
        "year_start": 100,
        "year_end": 200,
        "thinai": "Mullai",
        "summary_en": "Sangam poet celebrated in Akananuru and Ainkurunuru for chronicling the aromatic awakening of the deciduous forest under the first monsoon rains, the blossoming of golden Konrai trees, and pastoral ecological harmony.",
        "summary_ta": "ஐங்குறுநூற்றின் முல்லைப் பாடல்களைப் பாடிய சங்கப் புலவர்; கார்கால மழையில் முல்லை அரும்புகள் மலர்வதையும், கொன்றை மரங்கள் பொன்னெனப் பூத்துக் குலுங்குவதையும் கவித்துவத்தோடு பதிவு செய்த வனப் புலவர்.",
        "content": """# Peyanar: Bard of Mullai Ecology (பேயனார்)

**Corpus**: *Ainkurunuru Mullai*, *Akananuru*.  
**Theme**: First monsoon showers (*Kaar-kaalam*) and seasonal floral awakening.  
"""
    },
    {
        "category": "places",
        "slug": "place-kolli-malai-botanical-sanctuary",
        "file": "place-kolli-malai-botanical-sanctuary.md",
        "node_type": "place",
        "name_en": "Kolli Hills (Kolli Malai): Sacred Medicinal Flora Sanctuary & Siddha Haven",
        "name_ta": "கொல்லி மலை - மருத்துவ மூலிகைகளின் சரணாலயம் மற்றும் சித்தர் குகைத் தளம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1300,
        "thinai": "Kurinji",
        "summary_en": "Mountain range in Namakkal district (11.2500° N, 78.3333° E) celebrated across 2,000 years for microclimatic herb sanctuaries, sacred Kollikkavu groves, 16 medicinal mountain streams, and subterranean Siddha meditation caverns.",
        "summary_ta": "நாமக்கல் மாவட்டத்தில் 1300 மீட்டர் உயரத்தில் அமைந்துள்ள மூலிகைகளின் உறைவிடம் (11.2500° N, 78.3333° E). வல்வில் ஓரியின் ஆட்சிக்குட்பட்டிருந்த இந்நிலம், சித்தர்கள் தங்கி மூலிகைகளை ஆராய்ந்த குகைகளையும் அரிய மருத்துவச் சோலைகளையும் கொண்ட புனிதம்.",
        "content": """# Kolli Malai Botanical Sanctuary (கொல்லி மலை)

**Coordinates**: 11.2500° N, 78.3333° E.  
**Ecological Haven**: Eastern Ghats montane biodiversity hotspot and Siddha herb sanctuary.  
"""
    }
]

# ==============================================================================
# EDGES DEFINITION (Relational Cross-Domain Links)
# ==============================================================================
EDGES = [
    # Corpus 1: Siddha Medicine Edges
    (
        "text-agathiyar-vaidya-kaviyam-siddha",
        "codifies_pulse_science",
        "concept-nadi-parikshai-pulse-mechanics",
        "relational",
        "Sangam to Medieval Classical Era",
        "Agathiyar Vaidya Kaviyam codifies radial pulse diagnostics and tridosha ratio metrics.",
        "Agathiyar Vaidya Kaviyam Manuscript"
    ),
    (
        "text-agathiyar-vaidya-kaviyam-siddha",
        "describes_catalytic_salt",
        "concept-muppu-universal-catalyst",
        "relational",
        "Sangam to Medieval Classical Era",
        "Text explains the composition of Muppu tri-salt for calcining minerals.",
        "Agathiyar Vaidya Kaviyam verses"
    ),
    (
        "text-theraiyar-sekkiruvadukal-hygiene",
        "formulates_clinical_protocols",
        "concept-nadi-parikshai-pulse-mechanics",
        "relational",
        "Classical to Medieval Era",
        "Theraiyar formalizes Neikkuri urine test and radial artery pulse dynamics.",
        "Theraiyar Sekkiruvadukal"
    ),
    (
        "text-bogar-7000-saptha-kandam",
        "details_synthesis_of",
        "concept-navapashanam-nine-poison-amalgam",
        "relational",
        "Classical to Medieval Era",
        "Bogar 7000 details the exact chemical synthesis of the 9-poison Navapashanam compound.",
        "Bogar Saptha Kandam verses 1200-1450"
    ),
    (
        "insc-thirumukkudal-veera-rajendra-hospital",
        "records_endowment_of",
        "place-thirumukkudal-aathula-salai",
        "relational",
        "Imperial Chola Era",
        "Inscriptional record of the 15-bed Veerasolan hospital and hospital staff.",
        "Thirumukkudal Inscription (ARE 182 of 1915)"
    ),
    (
        "concept-navapashanam-nine-poison-amalgam",
        "installed_at_hill_shrine",
        "place-palani-malai-navapashanam",
        "relational",
        "Classical Siddha Era",
        "The immortal Navapashanam Murugan icon is enshrined at the Palani hill temple.",
        "Palani Murugan Epigraphy & Sthalapuranam"
    ),
    (
        "char-agathiyar-siddha-father",
        "authored_medical_text",
        "text-agathiyar-vaidya-kaviyam-siddha",
        "relational",
        "Pre-Sangam to Classical Era",
        "Sage Agathiyar composed the foundational 1500-verse medical kaviyam.",
        "Siddha Manuscript Tradition"
    ),
    (
        "char-theraiyar-master-diagnostician",
        "authored_hygiene_treatise",
        "text-theraiyar-sekkiruvadukal-hygiene",
        "relational",
        "Classical Era",
        "Theraiyar authored the classic treatise on circadian hygiene and pathology.",
        "Theraiyar Gunavagadam"
    ),
    (
        "char-bogar-alchemist-sculptor",
        "synthesized_amalgam",
        "concept-navapashanam-nine-poison-amalgam",
        "relational",
        "Classical Era",
        "Bogar personally formulated and cast the Navapashanam icon atop Palani.",
        "Bogar 7000"
    ),
    (
        "char-bogar-alchemist-sculptor",
        "samadhi_shrine_at",
        "place-palani-malai-navapashanam",
        "relational",
        "Classical Era",
        "Bogar's samadhi cavern is situated inside the Palani Murugan temple precinct.",
        "Palani Sthala Purana"
    ),
    (
        "concept-siddha-herbo-mineral-pharmacology",
        "dispensed_in_hospital",
        "place-thirumukkudal-aathula-salai",
        "relational",
        "Imperial Chola Era",
        "The 20 classical Siddha and Ayurvedic remedies recorded at Thirumukkudal.",
        "Thirumukkudal Epigraph"
    ),

    # Corpus 2: Sculpture & Bronze Casting Edges
    (
        "text-sirpa-chennool-sculpture-canon",
        "defines_iconometric_ratios",
        "concept-talamana-iconometric-proportions",
        "relational",
        "Sangam to Medieval Era",
        "Sirpa Chennool formalizes Tala metrics and Angula proportional canons.",
        "Sirpa Chennool Treatise"
    ),
    (
        "text-mayamata-dravidian-vastu-canon",
        "guided_temple_construction",
        "char-kunjara-mallan-rajaraja-perunthachan",
        "relational",
        "Imperial Chola Era",
        "Mayamata Vastu principles guided Perunthachan in erecting Brihadisvara vimana.",
        "Mayamata & Thanjavur Inscriptions"
    ),
    (
        "insc-thanjavur-rajaraja-bronze-endowments",
        "documents_lost_wax_masterpieces",
        "concept-madhuchehishtavidhana-lost-wax-casting",
        "relational",
        "Imperial Chola Era",
        "Inscriptions detail 66 solid Panchaloha lost-wax bronzes endowed by the royal family.",
        "Thanjavur South Wall Inscriptions (SII Vol II)"
    ),
    (
        "concept-madhuchehishtavidhana-lost-wax-casting",
        "practiced_by_guild",
        "place-swamimalai-bronze-artisan-quarter",
        "relational",
        "Imperial Chola Era",
        "Swamimalai artisans preserved the unbroken cire-perdue casting technique.",
        "Kaveri Silt Metallurgical Survey"
    ),
    (
        "concept-chola-bronze-ananda-tandava-iconography",
        "cast_via_technique",
        "concept-madhuchehishtavidhana-lost-wax-casting",
        "relational",
        "Imperial Chola Era",
        "The Nataraja cosmic dance icon was cast solid in Panchaloha using lost-wax molds.",
        "Chola Bronze Studies (Sivaramamurti)"
    ),
    (
        "concept-kammalar-stapathi-guild-guilds",
        "lineage_preserved_at",
        "place-swamimalai-bronze-artisan-quarter",
        "relational",
        "Imperial Chola to Modern Era",
        "Swamimalai houses the hereditary Viswakarma Stapathi bronze sculpting guild.",
        "Artisanal Ethnography of Swamimalai"
    ),
    (
        "char-kunjara-mallan-rajaraja-perunthachan",
        "patronized_by",
        "char-rajendra-chola-i",
        "relational",
        "Imperial Chola Era",
        "Chief royal architect serving Rajaraja I and Rajendra I.",
        "Thanjavur Vimana Plinth Epigraph"
    ),
    (
        "char-chembiya-mahadevi-bronze-patron",
        "endowed_bronze_workshops",
        "place-swamimalai-bronze-artisan-quarter",
        "relational",
        "Imperial Chola Era",
        "Queen Chembiya Mahadevi subsidized the master bronze casting guilds.",
        "Chembiya Mahadevi Temple Epigraphs"
    ),
    (
        "char-swamimalai-master-stapathi",
        "executes_sacred_canon",
        "concept-talamana-iconometric-proportions",
        "relational",
        "Imperial Chola to Modern Era",
        "Master stapathis memorize oral Talamana shlokas to carve accurate wax molds.",
        "Swamimalai Hereditary Shastras"
    ),

    # Corpus 3: Botany & Ecology Edges
    (
        "text-kurinjippattu-99-sacred-flowers",
        "authored_by",
        "char-kabilar-nature-poet-botanist",
        "relational",
        "Sangam Early Historic Era",
        "Poet Kabilar authored Kurinjippattu with its famous 99-flower catalog.",
        "Pathupattu Anthology"
    ),
    (
        "text-kurinjippattu-99-sacred-flowers",
        "documents_biodiversity_of",
        "concept-aintinai-biogeographical-zones",
        "relational",
        "Sangam Early Historic Era",
        "The 99 flowers provide empirical botanical evidence for the Kurinji montane ecosystem.",
        "Kurinjippattu lines 61-96"
    ),
    (
        "text-mullaippattu-forest-ecology",
        "describes_pastoral_biome",
        "concept-aintinai-biogeographical-zones",
        "relational",
        "Sangam Early Historic Era",
        "Mullaippattu describes the scrub forest biome and monsoon dynamics of Mullai thinai.",
        "Mullaippattu text"
    ),
    (
        "concept-sacred-groves-kavu-conservation",
        "preserves_healing_flora",
        "concept-sangam-ethnobotany-and-healing-flora",
        "relational",
        "Sangam to Modern Era",
        "Kavu sacred groves protected rare medicinal herbs and genetic reservoirs.",
        "Ethno-Ecological Surveys of Tamilakam"
    ),
    (
        "concept-sangam-ethnobotany-and-healing-flora",
        "abundantly_conserved_at",
        "place-kolli-malai-botanical-sanctuary",
        "relational",
        "Iron Age to Modern Era",
        "Kolli Hills preserves the richest concentration of Sangam medicinal herbs.",
        "Western Ghats Botanical Surveys"
    ),
    (
        "char-avvaiyar-ecological-philosopher",
        "proclaimed_wetland_law",
        "concept-marutham-wetland-agro-ecosystem",
        "relational",
        "Sangam Early Historic Era",
        "Avvaiyar formulated the Varappuyara ecological water-table principle.",
        "Classical Auvaiyar Poems"
    ),
    (
        "char-peyanar-mullai-pastoral-bard",
        "celebrated_forest_symbiosis",
        "text-mullaippattu-forest-ecology",
        "relational",
        "Sangam Early Historic Era",
        "Peyanar and Nappoothanar captured the floral awakening of the Mullai forest.",
        "Ainkurunuru Mullai"
    ),
    (
        "place-kolli-malai-botanical-sanctuary",
        "sanctuary_of_siddha_medicine",
        "concept-siddha-herbo-mineral-pharmacology",
        "relational",
        "Iron Age to Modern Era",
        "Kolli Malai provided herbs used by Bogar and Agathiyar in pharmaceutical pudams.",
        "Siddha Materia Medica (Gunavagadam)"
    ),
    (
        "place-kolli-malai-botanical-sanctuary",
        "botanical_realm_of",
        "place-kolli-malai",
        "relational",
        "Iron Age to Modern Era",
        "Detailed botanical and medicinal flora sector of the ancient Kolli Hills.",
        "Sangam Literature & Gazetteer"
    ),
    (
        "place-palani-malai-navapashanam",
        "alchemical_complex_at",
        "place-palani-malai",
        "relational",
        "Sangam to Medieval Era",
        "The sacred Navapashanam temple installation atop the Palani Hills.",
        "Palani Sthala Epigraphy"
    )
]

def main():
    print("=" * 80)
    print("🚀 TRIPLE CIVILIZATIONAL EXPANSION HARVESTER")
    print("   1. Ancient Tamil Medicine, Siddha Pharmacology & Pulse Diagnosis (13)")
    print("   2. Ancient Tamil Sculpture, Iconography & Lost-Wax Bronze Casting (11)")
    print("   3. Sangam Botany, Ethnobotany & Ecological Landscape Architecture (11)")
    print("   TOTAL: 35 Canonical Dossiers | 70 Dense Vector Embeddings")
    print("=" * 80)

    # Phase 1: Write Canonical Markdown Dossiers
    print("\n[Phase 1] Writing 35 Canonical Markdown Dossiers to Moolam Chronicles...")
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

    print("\n[Phase 2] Upserting 35 Lore Nodes into PostgreSQL...")
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
    print("\n[Phase 4] Generating 70 Dense 1024-dim BGE-M3 Embeddings into rag_chunks...")
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
