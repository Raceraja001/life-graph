#!/usr/bin/env python3
"""
Ancient Tamil Martial Arts, Weaponry & Fortification Architecture Corpus Harvester
Monumental Military Tactical Treatises, Martial Disciplines & Fortress Engineering:
- Purapporul Venbamalai: The 12 Classical Military Thinais, Siege & Bastion Warfare
- Purananuru Martial Ethos: Heroic Code, Battle Triage, Matriarchal Valor (Okkur Masathiyar)
- Chengam Hero-Stones (Nadukal): 5th–9th c. CE Vatteluttu Epigraphy of Border Skirmishes & Cattle Raids
- Vembakottai Weapon Arsenal: Multi-Period Excavated Projectiles, Swords, and Daggers on Vaippar
- Concepts: Silambam Stick Fencing, Adimurai & Varma Kalai, Valari Aerodynamic Boomerang, Aran 4-fold Forts, Nadukal Cult
- Figures: Aiyanarithanar, Okkur Masathiyar, Talaiyalanganathu Cheru Vendra Nedunchezhiyan
- Sites: Thirumayam Concentric Rock Fortress, Vembakottai Archaeological Citadel
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
    # 1. PRIMARY MILITARY TEXTS & CANONICAL ARSENALS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-purapporul-venbamalai-military-code",
        "file": "text-purapporul-venbamalai-military-code.md",
        "node_type": "text",
        "name_en": "Purapporul Venbamalai: The 12 Classical Military Thinais & Tactical Warfare Manual",
        "name_ta": "புறப்பொருள் வெண்பாமாலை - பன்னிரு புறத்திணைகளும் பண்டைய போரியல் இலக்கணமும்",
        "era": "Early Medieval Classical Era",
        "year_start": 800,
        "year_end": 900,
        "thinai": "Palai",
        "summary_en": "The definitive 9th-century CE military tactical treatise codified by Aiyanarithanar, deriving from the lost Pannirupadalam. Systematically categorizes ancient Tamil warfare into 12 Puram thinais based on military operational phases: cattle-raiding declaration of war (Vetchi), border patrol recovery (Karanthai), invasion (Vanchi), defensive confrontation (Kanchi), fortress siege encirclement (Uzhignai), fortress wall defense (Nochchi), pitched open battlefield collision (Thumpai), victory triumph (Vaagai), martial eulogy (Paadaan), general martial ethics (Poduviyal), unrequited war passion (Kaikkilai), and total war destruction (Perunthinai). Details siege machinery, battering rams, scaling ladders, and moated bastion tactics.",
        "summary_ta": "ஐயனாரிதனாரால் இயற்றப்பட்ட கி.பி. 9-ஆம் நூற்றாண்டு போரியல் இலக்கண நூல்; தொன்மையான பன்னிரு படலத்தை அடிப்படையாகக் கொண்டது. பண்டைய தமிழரின் போரியல் நடவடிக்கைகளை 12 புறத்திணைகளாக வகைப்படுத்துகிறது: ஆநிரை கவர்தல் (வெட்சி), ஆநிரை மீட்டல் (கரந்தை), வஞ்சி (படையெடுத்துச் செல்லல்), காஞ்சி (எதிர்த்து நிற்றல்), உழிஞை (மதில் வளைத்தல் / முற்றுகைப் போர்), நொச்சி (மதில் காத்தல்), தும்பை (நேருக்கு நேர் போர்க்கள மோதல்), வாகை (வெற்றி சூடல்), பாடாண், பொதுவியல், கைக்கிளை, பெருந்திணை. முற்றுகைப் பொறிகள், மதில் ஏறும் ஏணிகள், அகழித் தடைகள், மற்றும் எந்திரப் பொறிகளை விவரிக்கும் ஒப்பற்ற போர்த் தந்திர ஆவணம்.",
        "content": """# Purapporul Venbamalai: Military Warfare Manual (புறப்பொருள் வெண்பாமாலை)

**Author**: Aiyanarithanar (*ஐயனாரிதனார்*).  
**Horizon**: c. 9th century CE (preserving Sangam military doctrines).  
**Classification**: Classical Military Science & Tactical Codification (*போரியல் இலக்கணம்*).

---

## 1. The 12 Tactical Military Thinais (பன்னிரு புறத்திணைகள்)

Ancient Tamil warfare was conducted through structured, ritualized operational phases, each symbolized by a specific botanical flower garland worn by commanders and soldiers:

```
[Declaration of Hostilities]
       |
       +--> 1. Vetchi (Scarlet Ixora): Pre-emptive cattle-rustling at border outposts.
       +--> 2. Karanthai (Basil): Border defense recovery of cattle herds.
       |
[Territorial March & Standoff]
       |
       +--> 3. Vanchi (Creeping Willow): March of imperial invasion into enemy realm.
       +--> 4. Kanchi (River Portia): Static defense and counter-attack by defender.
       |
[Fortress Siege Engineering]
       |
       +--> 5. Uzhignai (Balloon Vine): Assault troops besieging and scaling fortress walls.
       +--> 6. Nochchi (Chaste Tree): Garrison troops defending parapets and battlements.
       |
[Pitched Battlefield Combat]
       |
       +--> 7. Thumpai (White Dead-nettle): Open-field clash of two armored battle lines.
       +--> 8. Vaagai (Siris Tree): Triumphal victory parade and distribution of spoils.
```

---

## 2. Siege Warfare Architecture (*Uzhignai* vs. *Nochchi*)

The treatise provides extraordinary details regarding siege warfare:
1. **Assault Machinery (*Uzhignai-p-pori*)**:
   - **Kuruthezhini**: Armored mobile wicker mantlets pushed toward the moat to shield archers.
   - **Eni**: Jointed scaling ladders fitted with grappling hooks to mount the granite ramparts.
   - **Tholai-maram**: Heavy suspended timber battering rams reinforced with iron heads to shatter bronze-studded gates.
2. **Defensive Bastion Counter-Measures (*Nochchi-k-kaaval*)**:
   - Pouring boiling resin, molten lead, and burning sesame oil from overhead machicolations.
   - Releasing *Kavanam* (giant stone-throwing ballistas) and catapults from corner watchtowers.
   - Archers firing volleyed whistling arrows through narrow arrow-slit apertures (*Tholai*).
"""
    },
    {
        "category": "texts",
        "slug": "text-purananuru-martial-ethos",
        "file": "text-purananuru-martial-ethos.md",
        "node_type": "text",
        "name_en": "Purananuru: The Classical Sangam Martial Ethos, Battlefield Medicine & Valor Code",
        "name_ta": "புறநானூறு - சங்க கால வீரயுக மரபு, போர்க்கள மருத்துவம் மற்றும் மறப்பண்பு",
        "era": "Sangam Early Historic Era",
        "year_start": -100,
        "year_end": 250,
        "thinai": "Palai",
        "summary_en": "The supreme Sangam anthology preserving the heroic ethos of the Tamil heroic age. Documents the unyielding warrior code (Maram), the culture of martial matriarchs who sent three generations to the front lines (Okkur Masathiyar, Puram 277-279), battlefield surgical procedures (Puram 284: suturing gaping spear wounds with white tendril catgut thread), and the supreme martial honor of Vadakkiruthal (ritual fast unto death facing North by monarchs wounded in the back), alongside the hero-stone (Nadukal) veneration of fallen martyrs.",
        "summary_ta": "சங்க கால வீரயுகத்தின் வாழ்வியலையும் போரியல் தர்மங்களையும் வெளிப்படுத்தும் புறநானூற்றுப் பாடல்கள். முதல் நாள் போரில் தந்தையையும், இரண்டாம் நாள் கணவனையும் இழந்து, மூன்றாம் நாள் போர்ப்பறை கேட்டு தன் ஒரே மகனின் கையில் வேலைக் கொடுத்து போர்க்களத்திற்கு அனுப்பும் மூதின் முல்லையின் மறத்தாய் மரபு (ஒக்கூர் மாசாத்தியார், புறம் 277-279), போர்க்களத்தில் கிழிந்த மார்புக் காயங்களை ஊசி மற்றும் நரம்புக் கொண்டு தைக்கும் போர்க்கள அறுவை சிகிச்சை மருத்துவம் (புறம் 284), மற்றும் முதுகில் புண்பட்டதற்காக வடக்கிருந்து உயிர்நீக்கும் மான வீரக் கோட்பாடு ஆகியவற்றை விவரிக்கிறது.",
        "content": """# Purananuru: The Sangam Martial Ethos (புறநானூற்று மறப்பண்பு)

**Anthology**: *Ettuthogai* (The Eight Classical Anthologies).  
**Theme**: *Puram* (Public Life, Statecraft, Heroic Warfare, and Memorialization).  
**Chronology**: c. 3rd century BCE – 3rd century CE.

---

## 1. The Matriarchal Martial Ethos (*Muthingur Vaazhkai*)

In *Purananuru* 279, poetess Okkur Masathiyar captures the legendary stoicism of Sangam mothers:
> *"Her uncle fell in battle on the first day;*  
> *Her husband was speared down on the second day;*  
> *Hearing the morning war drums sound on the third day,*  
> *She combed the hair of her tender young boy, gave him a spear,*  
> *And sent him with joy straight to the front line of battle."*

A warrior's mother was shamed if her son retreated or was struck in the back; but rejoiced if he died facing the enemy spears, proving his lineage.

---

## 2. Ancient Battlefield Surgical Medicine (*Puram* 284)

In *Purananuru* 284, the poet describes battlefield medical triage following a savage cavalry and elephant charge:
- The warrior's chest is slashed open by a heavy broadsword.
- The field surgeons (*Maruthuvar*) clean the gaping wound with botanical disinfectants.
- They utilize a curved bone or copper needle (*Oosi*) threaded with **catgut or plant-tendril thread** (*Kodik-kural*) to suture the wound layers firmly together, while female bards sing protective incantations (*Kanchi-p-paattu*) to ward off nocturnal scavengers and infections.

---

## 3. The Code of *Vadakkiruthal* (Ritual Fasting Facing North)

If a king or commander sustained a wound on his back—even by an arrow passing through his chest—he considered his martial honor irrevocably stained. The sovereign would sit on a bed of dry Dharba grass facing True North (*Vadakku*), lay his sword beside him, and fast unto death in the company of loyal vassal chieftains and bards. Famous examples include Chola King Kopperunchozhan accompanied by poet Pisiranthaiyar, and Cheralathan after being wounded by Karikala Chola at the Battle of Venni.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-nadukal-hero-stones-chengam",
        "file": "insc-nadukal-hero-stones-chengam.md",
        "node_type": "inscription",
        "name_en": "Chengam Hero-Stones: Vatteluttu Epigraphical Archive of Border Warfare (5th–9th c. CE)",
        "name_ta": "செங்கம் நடுகற்கள் - வட்டெழுத்து நடுகல் கல்வெட்டுத் தொடர் (கி.பி. 5-9-ஆம் நூற்றாண்டு)",
        "era": "Pallava-Early Medieval Era",
        "year_start": 450,
        "year_end": 850,
        "thinai": "Mullai",
        "summary_en": "The largest concentration of inscriptional hero-stones (Nadukal) discovered in South Asia, located in the Chengam basin along the Pennaiyar river (Tiruvannamalai / Dharmapuri districts). Over 60 basalt and granite hero-stones inscribed in early Vatteluttu recording historical skirmishes during the reigns of Pallava Kings (Simhavishnu, Mahendravarman I, Narasimhavarman I) and local Ganga chieftains. Each stone depicts a relief carving of the fallen warrior with bow, sword, or spear, recording his name, village, the cattle raid (Tholuk-kollai), and tax-free land endowments (Eri-patti / Raktha-kanya) granted to his heirs.",
        "summary_ta": "தென்னாசியாவிலேயே அதிக எண்ணிக்கையிலான நடுகற்கள் கண்டறியப்பட்ட செங்கம் பெண்ணையாற்றுப் படுகை (திருவண்ணாமலை / தருமபுரி மாவட்டங்கள்). பல்லவ மன்னர்களான சிம்மவிஷ்ணு, முதலாம் மகேந்திரவர்மன், நரசிம்மவர்மன் மற்றும் கங்க மன்னர்களின் ஆட்சிக் காலத்தைச் சேர்ந்த 60-க்கும் மேற்பட்ட வட்டெழுத்து நடுகற்கள். ஆநிரை கவர்தல் (தொழுக் கொள்ளை), ஊர் காவல் சண்டைகள், புலிக்குத்திப் பட்டோன் நடுகற்கள் ஆகியவற்றில் வீரர்களின் உருவங்கள் வில், வாள், வேலுடன் புடைப்புச் சிற்பங்களாகச் செதுக்கப்பட்டு, அவர்களின் குடும்பத்திற்கு வழங்கப்பட்ட 'இரத்தக் காணிக்கை' நிலக்கொடைகளை (ஏரிப்பட்டி) ஆவணப்படுத்துகின்றன.",
        "content": """# Chengam Hero-Stones (செங்கம் நடுகல் கல்வெட்டுகள்)

**Epigraphical Classification**: Memorial Hero-Stones (*நடுகற்கள் / வீரக்கற்கள்*).  
**Geographical Locale**: Chengam Taluk, Tiruvannamalai District, Tamil Nadu (along the Pennaiyar valley).  
**Script**: Archaic Vatteluttu and Tamil-Grantha.  
**Historical Horizon**: c. 5th to 9th century CE.

---

## 1. Typology of Chengam Hero-Stones

The Chengam excavations by the Tamil Nadu State Department of Archaeology revealed over 60 stones representing three major military contexts:
1. **Aanirai Meettal (Cattle Recovery Stones)**:
   - Depicting warriors who pursued raiders into the hill forests, retrieved the village cows, and perished of arrow or spear wounds.
2. **Oor Azhivu Kaaval (Village Defense Stones)**:
   - Commemorating guards who held village gates against nocturnal dacoits or imperial raiding parties.
3. **Puli-k-kutthi Pattoan (Tiger Slayer Stones)**:
   - Memorials to brave men who tackled marauding tigers armed only with short thrusting daggers (*Kattari*), killing the beast before succumbing to mortal claw injuries.

---

## 2. Inscriptional Formula & Social Welfare

The epigraphs follow a strict, dignified formula:
> *"[Regnal Year of Monarch]... [Village Name]... [Warrior Name], son of [Father], stood against the enemy who seized the herd, slew them in combat, and attained the warrior's heaven. In his honor, this stone was raised and [X] kani of wet land granted as Eri-patti."*

This confirms that ancient Tamil states operated an institutionalized social welfare system: the family of a soldier killed in defense of the realm received hereditary, tax-exempt agricultural land linked to village irrigation tanks (*Eri-patti*).
"""
    },
    {
        "category": "archaeology",
        "slug": "arch-vembakottai-weapons-arsenal",
        "file": "arch-vembakottai-weapons-arsenal.md",
        "node_type": "archaeological_site",
        "name_en": "Vembakottai Weapon Arsenal & Pre-Historic Martial Citadel Excavations",
        "name_ta": "வேம்பக்கோட்டை போர்க்கருவிகள் தொழிற்கூடம் மற்றும் அகழாய்வுத் தளம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -800,
        "year_end": 300,
        "thinai": "Mullai",
        "summary_en": "Major ongoing archaeological excavation site situated along the Vaippar river in Virudhunagar district (9.3361° N, 77.7719° E). Spanning continuous habitation layers from the Iron Age through the Sangam era, excavations have unearthed a vast ancient martial arsenal and lapidary industrial center: iron arrowheads, serrated spears, bronze dagger hilts, bone projectile tips, terracotta sling-shots, carnelian beads, and gold ornaments, establishing the southern Pandyan hinterland as a major weapons manufacturing and metallurgical hub.",
        "summary_ta": "விருதுநகர் மாவட்டம் வைப்பாற்றின் வடகரையில் அமைந்துள்ள வேம்பக்கோட்டை அகழாய்வுத் தளம் (9.3361° N, 77.7719° E). இரும்புக் காலம் முதல் சங்க காலம் வரையிலான தொடர்ச்சியான பண்பாட்டு அடுக்குகளைக் கொண்ட தளம். இரும்பு அம்பு முனைகள், ஈட்டி முனைகள், வெண்கலக் குறுவாள் கைப்பிடிகள், கூர்மையான எலும்பு முனை ஏவுகணைகள், சுடுமண் கவண்கற்கள், சூதுபவள மணிகள் மற்றும் தங்க அணிகலன்கள் கண்டறியப்பட்டு, இப்பகுதி பாண்டிய நாட்டின் முக்கிய ஆயுத உற்பத்தி மற்றும் உலோகவியல் தொழில் மையமாக இயங்கியதை உறுதிப்படுத்துகிறது.",
        "content": """# Vembakottai Weapons Arsenal (வேம்பக்கோட்டை அகழாய்வு)

**Site**: Uchchimedu Mound, Vembakottai, Virudhunagar District, Tamil Nadu.  
**Water Basin**: Vaippar River (*வைப்பாற்றுப் படுகை*).  
**Coordinates**: 9.3361° N, 77.7719° E.  
**Excavating Authority**: Tamil Nadu State Department of Archaeology (TNSDA).

---

## 1. Military Artifacts Unearthed

Excavations across multiple trenches have yielded dense assemblages of weapons:
- **Iron Arrowheads**: Barbed, tanged, and triangular aerodynamic arrowheads forged from high-carbon iron.
- **Spearheads (*Vel*)**: Broad-leaf and triangular socketed spearheads designed for both thrusting and throwing.
- **Bone Projectiles**: Polished animal bone micro-tips used for hunting and secondary missile weapons.
- **Sling Bullets (*Kavan-kallu*)**: Spherical hard-fired terracotta balls intended for long-range slingshots during siege defense.
- **Dagger Hilts**: Cast bronze and iron dagger components with grooved grips.

---

## 2. Strategic Context in the Pandyan Realm

Vembakottai served as a fortified frontier garrison and metallurgical production town strategically positioned along the inland route connecting the coastal pearl port of Korkai with the inland capital of Madurai and the Western Ghats passes.
"""
    },

    # --------------------------------------------------------------------------
    # 2. MARTIAL DISCIPLINES & WEAPON TECHNOLOGIES
    # --------------------------------------------------------------------------
    {
        "category": "concepts",
        "slug": "concept-silambam-stick-fencing",
        "file": "concept-silambam-stick-fencing.md",
        "node_type": "concept",
        "name_en": "Silambam: The Ancient Tamil Martial Fencing & Weapon Discipline",
        "name_ta": "சிலம்பம் - தமிழரின் மரபுவழி தற்காப்புக் கலையும் ஆயுதப் போரியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "Kurinji",
        "summary_en": "The oldest surviving weapon-based martial art of Tamilakam, originating in the Kurinji hills. Utilizes the flexible, seasoned male bamboo stave (Kurunji-mungil / Pirampu) measuring up to the practitioner's forehead. Employs 32 fundamental footwork patterns (Kaaladi), continuous high-speed wrist rotations (Veechu), precision thrusting strikes (Kuthu), and parries (Thadukkal). Progresses to metallic weapons: Surul-vaal (flexible whip-sword), Maduvu (deer-horn parrying shield), Vel (spear fencing), and Kathi-silambam (dual dagger combat).",
        "summary_ta": "குறிஞ்சி நில மலையகத்தில் தோன்றிய தமிழரின் ஆதி தற்காப்புக் கலை. புல்லாங்குழல் போல் உள்ளீடற்ற திடமான ஆண் மூங்கில் (பிரம்பு) கொண்டு பயிலப்படும் வாள்வீச்சுக்கு இணையான கலை. 32 வகையான காலடி வரிசைகள், சுழற்சி வீச்சுகள், குத்து முறைகள், மற்றும் தடுத்தல் நுட்பங்கள் இதில் அடங்கும். மூங்கில் சிலம்பத்தில் தேர்ச்சி பெற்ற பின் சுருள்வாள், மான் கொம்பு (மடுவு), வேல்கம்பு, மற்றும் கத்தி சிலம்பம் ஆகிய உலோக ஆயுதப் போரியலுக்கு முன்னேறும் முழுமையான தற்காப்புப் பயிற்சி நெறி.",
        "content": """# Silambam: Ancient Tamil Fencing (சிலம்பக் கலை)

**Origin**: Kurinji mountainous terrain of Tamilakam.  
**Primary Weapon**: Seasoned Male Bamboo Stave (*ஆண் மூங்கில் கம்பு*).  
**Stave Dimensions**: Stature length measured from ground to practitioner's eyebrow or forehead (~5 to 5.5 feet).

---

## 1. Biomechanics & Kinetic Principles

1. **Kaaladi (Footwork Geometry)**:
   - 32 discrete geometric stepping patterns: linear, triangular, circular, and diamond angles.
   - Low center of gravity (*Chavittu*) maintaining balance while shifting evasion lines.
2. **Veechu (Rotational Kinetics)**:
   - High-speed double-ended figure-eight wrist rotations creating an impenetrable defensive kinetic shield.
   - Rotational angular velocity generates massive striking force upon impact at the stave's outer tip.
3. **Striking Points (*Kuthu*)**:
   - Directed at soft neurological joints, solar plexus, throat, temples, and knees.

---

## 2. Advanced Weapons Suite

- **Surul-Vaal**: Flexible multi-bladed spring-steel whip-sword capable of cutting in 360-degree arcs.
- **Maduvu**: Twin spiral horns of the blackbuck (*Maan kombu*) tipped with steel, used for simultaneous parrying and throat gouging.
- **Vel**: The iconic Sangam leaf-bladed spear, the royal weapon of Lord Murugan and warrior heroes.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-adimurai-varma-kalai",
        "file": "concept-adimurai-varma-kalai.md",
        "node_type": "concept",
        "name_en": "Adimurai & Varma Kalai: Ancient Empty-Hand Combat & Vital Nerve Strike Science",
        "name_ta": "அடிமுறை மற்றும் வர்மக்கலை - தமிழரின் மெய்தீண்டாக் கலையும் நரம்புப் போரியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "Kurinji",
        "summary_en": "The ancestral empty-hand martial art of southern Tamilakam (Kanyakumari, Tirunelveli, Travancore). Integrates unarmed striking (Adimurai), grappling and joint manipulation (Pootumuraigal), and the esoteric neurological science of vital pressure points (Varma Kalai). Classifies the human body into 108 vital Varma points: 12 lethal Padu-varmam, 96 disabling Thodu-varmam, alongside resuscitation procedures (Adangal) and Siddha trauma herbalism (Varma Maruthuvam).",
        "summary_ta": "தென் தமிழகத்தின் (கன்னியாகுமரி, திருநெல்வேலி, நாஞ்சில் நாடு) தொன்மையான வெறுங்கை தற்காப்புக் கலை. எதிரியின் தாக்குதல்களை முறியடிக்கும் அடிமுறைகள், மூட்டுப் பூட்டுகள், மற்றும் உடலின் 108 நரம்பு முடிச்சுகளைத் தாக்கி முடக்கும் 'வர்மக்கலை' ஆகியவற்றை உள்ளடக்கியது. 12 படுவர்மங்கள் (உயிர்க்கொல்லி), 96 தொடுவர்மங்கள் (செயலிழக்கச் செய்வன), மற்றும் பாதிக்கப்பட்டவரை மீட்கும் 'அடங்கல்' மற்றும் வர்ம மருத்துவ முறைகளைக் கொண்ட முழுமையான தற்காப்பு அறிவியல்.",
        "content": """# Adimurai & Varma Kalai (அடிமுறையும் வர்மக்கலையும்)

**Tradition**: Southern Martial Lineage (*தெற்கன் களரி / அடிமுறை*).  
**Associated Sage**: Siddha Agastya (*அகத்தியர் வர்ம சாஸ்திரம்*).  
**Core Domain**: Unarmed Combat, Neurological Disabling, and Trauma Revival.

---

## 1. The 108 Varmam Classification

The system maps 108 vital junctions (*Varma-p-pulli*) where nerves, blood vessels, and bones intersect:
1. **Padu-Varmam (12 Major Fatal Points)**:
   - Located on the cranium, spine, heart, and carotid artery. A high-velocity strike induces instant respiratory arrest, cardiac arrhythmia, or paralysis.
2. **Thodu-Varmam (96 Secondary Disabling Points)**:
   - Located across limbs and torso. Strikes induce temporary limb paralysis, numbness, loss of motor control, or unconsciousness.
3. **Noki-Varmam / Meitheenda-Kalai**:
   - The legendary highest tier of mental projection and focal intimidation.

---

## 2. Resuscitation & Healing (*Adangal*)

Every master of Varma Kalai was strictly bound by ethical oaths to master resuscitation (*Adangal*) before learning fatal strikes. If a student was struck during sparring, the teacher applied specific counter-percussion maneuvers (*Thattuvadangal*) to restore circulation and reboot the autonomic nervous system within minutes.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-valari-throwing-boomerang",
        "file": "concept-valari-throwing-boomerang.md",
        "node_type": "concept",
        "name_en": "Valari: The Ancient Aerodynamic Throwing Weapon of Tamilakam",
        "name_ta": "வளரி - தமிழரின் வளைந்த எறிபடையும் காற்றியக்க ஆயுதமும்",
        "era": "Sangam to Poligar War Era",
        "year_start": -300,
        "year_end": 1801,
        "thinai": "Palai",
        "summary_en": "The iconic non-returning aerodynamic curved throwing weapon unique to Tamilakam. Handcrafted from heavy seasoned ironwood (Vengai, Karuvel) or forged from crucible carbon steel with chisel-sharpened inner and outer cutting edges. Exploits gyroscopic rotation and aerodynamic asymmetric lift during horizontal throws, achieving a lethal flat flight path over 100 meters. Capable of decapitation, breaking horse legs, or shattering shields; widely deployed by Sangam Maravar warriors and later in the Poligar Wars against British infantry before being banned and confiscated under the 1801 disarmament proclamations.",
        "summary_ta": "பண்டைத் தமிழகத்திற்கே உரிய வளைந்த காற்றியக்க எறிபடை (நான்-ரிட்டர்னிங் பூமராங்). தேக்கு, வேங்கை அல்லது கருவேல மரத்தின் வைரப்பகுதியிலோ, அல்லது கூர்மையான எஃகினாலோ இருபுறமும் கத்தி போல் தீட்டப்பட்டு உருவாக்கப்படுவது. கிடைமட்டமாக சுழற்றி வீசப்படும் போது கைரோஸ்கோபிக் சுழற்சி மற்றும் காற்றியக்க உயர்த்து விசையைப் பெற்று, 100 மீட்டர் தூரம் வரை நேர்கோட்டில் பறந்து சென்று எதிரியின் கழுத்தை வெட்டும் அல்லது குதிரையின் கால்களை ஒடிக்கும் ஆற்றல் கொண்டது. சங்க கால மறவர்கள் முதல் மருது சகோதரர்களின் பாளையக்காரர் போர் வரை ஆங்கிலேயப் படைகளை நடுங்க வைத்த தமிழரின் மரபு ஆயுதம்.",
        "content": """# Valari: Ancient Aerodynamic Throwing Weapon (வளரி)

**Weapon Type**: Aerodynamic Missile Weapon / Non-Returning Boomerang (*எறிபடை*).  
**Materials**: High-density timber (*Acacia nilotica* / *Pterocarpus*), bronze, or forged iron.  
**Operational Horizon**: Sangam era through the 1801 Poligar Wars.

---

## 1. Aerodynamic Physics & Gyroscopic Lift

Unlike returning sporting boomerangs, the Tamil *Valari* was an uncompromising lethal projectile:
- **Asymmetric Airfoil**: The cross-section is carved with a cambered upper profile and flat bottom, generating vertical aerodynamic lift as it spins.
- **Flight Velocity**: When released with a horizontal whip-flick of the wrist, the Valari rotates at several hundred RPM, stabilizing its trajectory against crosswinds.
- **Lethal Radius**: Effective killing distance ranged from 50 to 120 meters.

---

## 2. Battlefield Deployment & British Suppression

In the 18th-century Poligar Wars against the British East India Company, the Maruthu Pandiyar brothers and their Kallar-Maravar soldiers deployed thousands of iron Valaris to decimate British cavalry lines. British records note that the spinning blades severed the legs of charging cavalry horses and decapitated soldiers behind barricades. Following the defeat of the Sivaganga rebellion in 1801, British authorities declared capital punishment for possessing a Valari, seizing and melting down thousands of historic specimens.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-aran-ancient-fortification",
        "file": "concept-aran-ancient-fortification.md",
        "node_type": "concept",
        "name_en": "Aran: Fourfold Ancient Tamil Fortress Architecture & Moat Engineering",
        "name_ta": "அரண் அமைப்பு - நாற்படை கோட்டைக் கட்டடக் கலையும் அகழிப் பொறியியலும்",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1400,
        "thinai": "Marutham",
        "summary_en": "The monumental military fortress architecture codified in Tirukkural (chapters 741-750) and Sangam literature. Defines the impenetrable fourfold defensive barriers (Aran): Neer-aran (deep concentric moats stocked with man-eating crocodiles Idangar), Nilam-aran (vast barren killing zones exposing advancing infantry), Malai-aran (unassailable granite hill-cliff citadels), and Kaattu-aran (dense thorny defensive jungle perimeters of Euphorbia and bamboo). Details granite rampart construction (Madi), projectile parapets (Nochchi), and subterranean escape sally-ports (Surangam).",
        "summary_ta": "திருக்குறளின் 'அரண்' அதிகாரத்திலும் (741-750) சங்க இலக்கியங்களிலும் போற்றப்படும் பண்டைத் தமிழகத்தின் கோட்டைப் பொறியியல். நான்கு வகை அரண்கள்: நீரரண் (முதலைகள் நிறைந்த ஆழமான அகழிகள்), நிலவரண் (எதிரிகள் மறைவிடமின்றி முன்னேறும் பரந்த வெட்டவெளி), மலையரண் (செங்குத்தான கருங்கல் மலைக் கோட்டைகள்), மற்றும் காட்டரண் (கள்ளி மற்றும் முள்மரங்கள் அடர்ந்த புகமுடியாத பாதுகாப்புக் காடுகள்). கருங்கல் மதில்கள், கொத்தளங்கள், அம்புத் துளைகள், மற்றும் நிலத்தடி தப்பிக்கும் சுரங்கப் பாதைகள் அடங்கிய முழுமையான பாதுகாப்புப் பொறியியல்.",
        "content": """# Aran: Fourfold Ancient Fortification (அரண் கட்டடக் கலை)

**Canonical Definition**: *Tirukkural* Chapter 75 (*அரண்*).  
> *"மணிநீரும் மண்ணும் மலையும் அணிநிழற்*  
> *காடும் உடையது அரண்."* (குறள் 742)  
> ("A fortress is that which possesses deep water moats, vast open terrain, soaring rock cliffs, and dense protective forests").

---

## 1. The Fourfold Barrier Architecture

1. **Neer-Aran (Water Moat Barrier - அகழி)**:
   - Deep, broad trenches encircling the citadel walls, fed by river canals.
   - Stocked with ravenous crocodiles (*Idangar / Muthalai*) to prevent enemy sappers from swimming or building pontoon bridges.
2. **Nilam-Aran (Open Killing Glacis - வெளிப்படை)**:
   - Cleared, level ground extending 500 meters out from the moat, offering zero cover from defensive archers and ballistas.
3. **Malai-Aran (Granite Mountain Citadel - மலையரண்)**:
   - High, sheared granite tors (such as Thirumayam, Tiruchirappalli, Dindigul, and Gingee) where natural cliffs formed vertical ramparts.
4. **Kaattu-Aran (Defensive Thorny Jungle - காட்டரண்)**:
   - Deliberately cultivated impenetrable belts of thorny cactus (*Kalli*), bamboo (*Mungil*), and acacia that prevented cavalry maneuvers and siege tower deployment.

---

## 2. Rampart Engineering & Mechanical Arsenal

- **Kothalam (Bastions)**: Projecting semicircular corner towers providing enfilading fire along the outer wall face.
- **Parambai (Parapet & Merlons)**: Crenellated upper wall protections shielding garrison archers.
- **Surangam (Subterranean Escape Tunnels)**: Secret sally-ports burrowed deep beneath the granite bedrock for messenger relays and counter-mining sorties.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-nadukal-hero-stone-cult",
        "file": "concept-nadukal-hero-stone-cult.md",
        "node_type": "concept",
        "name_en": "Nadukal: The Six-Stage Ritual Cult & Epigraphical Veneration of Fallen Heroes",
        "name_ta": "நடுகல் வணக்கம் - அறுவகை நடுகல் நடும் சடங்கும் வீரயுக வழிபாட்டு மரபும்",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1200,
        "thinai": "Mullai",
        "summary_en": "The sacred memorial institution of ancient Tamilakam codified in Tolkappiyam (Porulathikaram, Puraththinaiyiyal 5) and Silappadikaram. Details the six ritual stages of erecting a hero-stone (Nadukal): Katchi (locating granite boulder in sacred hills), Kaal-kole (quarrying and dedicating), Neer-padai (cleansing in sacred rivers), Nadukal (erecting at village frontier), Perum-padai (inscribing epitaph and carving warrior image), and Vaazhthu (communal feast, toddy libations, and hero deification).",
        "summary_ta": "தொல்காப்பியப் பொருளதிகாரத்தில் (புறத்திணையியல் 5) மற்றும் சிலப்பதிகாரத்தில் விவரிக்கப்படும் நடுகல் நடும் அறுவகைச் சடங்கு மரபு: காட்சி (மலைகளில் தக்க கருங்கல்லைத் தேர்ந்தெடுத்தல்), கால்கோள் (கல்லைப் பெயர்த்து முகூர்த்தம் செய்தல்), நீர்ப்படை (புண்ணிய நதியில் கல்லை நீராட்டித் தூய்மை செய்தல்), நடுகல் (போர்க்களத்திலோ ஊரெல்லையிலோ கல்லை நடுதல்), பெரும்படை (வீரனின் உருவத்தையும் பெயரையும் செதுக்கி படையலிடுதல்), மற்றும் வாழ்த்து (வீரனை தெய்வமாக வணங்கி வாழ்த்துதல்). தமிழரின் பூர்விக நீத்தார் வழிபாட்டு முறை.",
        "content": """# Nadukal: Hero-Stone Cult & Rituals (நடுகல் நடும் முறைமை)

**Earliest Codification**: *Tolkappiyam* (Puraththinaiyiyal, Sutra 5).  
**Epic Narrative**: *Silappadikaram* (Vanchi Kandam: Cheran Senguttuvan erecting the Pattini Nadukal from Himalayan stone).

---

## 1. The Six Classical Ritual Stages (*Aruvagai Sadangu*)

```
1. Katchi (காட்சி)       -> Reconnaissance and identification of unblemished stone.
2. Kaal-kole (கால்கோள்)   -> Auspicious quarrying and ceremonial dedication.
3. Neer-padai (நீர்ப்படை)  -> Immersion and ritual purification in flowing river water.
4. Nadukal (நடுகல்)       -> Physical erection at the village boundary or hero's cairn.
5. Perum-padai (பெரும்படை) -> Inscribing deeds and carving relief iconography with feasts.
6. Vaazhthu (வாழ்த்து)     -> Invoking ancestral protection with toddy, peacock feathers, and incense.
```

---

## 2. Iconography & Epigraphical Heritage

Hero-stones depict the fallen warrior in dynamic action:
- Drawing a composite bow with arrows notched.
- Pierced by multiple arrows or spears yet advancing with raised sword.
- Accompanied by his loyal hunting hound (*Naai*), as preserved in the famous Eduthanur dog hero-stone (*Kovivan*).
- Feathers of the peacock (*Mayil-peeli*) and garlands of fragrant flowers (*Karanthai*) were tied to the stone, while village folk offered daily prayers to the deceased spirit as a protective guardian deity (*Kaval Deivam*).
"""
    },

    # --------------------------------------------------------------------------
    # 3. HISTORICAL FIGURES & MARTIAL HEROES
    # --------------------------------------------------------------------------
    {
        "category": "characters",
        "slug": "char-aiyanarithanar-military-theorist",
        "file": "char-aiyanarithanar-military-theorist.md",
        "node_type": "character",
        "name_en": "Aiyanarithanar (Scholar-General & Author of Purapporul Venbamalai)",
        "name_ta": "ஐயனாரிதனார் - புறப்பொருள் வெண்பாமாலை இயற்றிய போரியல் மேதை",
        "era": "Early Medieval Classical Era",
        "year_start": 820,
        "year_end": 880,
        "thinai": "Palai",
        "summary_en": "The eminent scholar-general and military theorist of ancient Tamilakam, belonging to the illustrious Chera-Pandya royal lineage. Systematized the oral and fragmentary military doctrines of the Sangam era into the masterwork Purapporul Venbamalai, condensing the ancient Pannirupadalam into an exhaustive 12-thinai manual of military strategy, siege warfare, and martial ethics.",
        "summary_ta": "பண்டைத் தமிழகத்தின் தலைசிறந்த போரியல் சிந்தனையாளர் மற்றும் புலவர். சேர-பாண்டிய அரச மரபைச் சார்ந்தவர். சங்க காலத்து பன்னிரு படலத்தின் சிதறிக்கிடந்த போர்த் தந்திரங்களை ஒருங்கிணைத்து, 12 புறத்திணைகளுக்கான இலக்கணத்தை 'புறப்பொருள் வெண்பாமாலை' என்ற ஒப்பற்ற போரியல் நூலாகத் தொகுத்து வழங்கிய வரலாற்று மேதை.",
        "content": """# Aiyanarithanar (ஐயனாரிதனார்)

**Title**: *Perunkavi Purapporul Asiriyan* (Grand Master of Military Grammar).  
**Work**: *Purapporul Venbamalai* (*புறப்பொருள் வெண்பாமாலை*).  
**Patronage**: Pandyan / Chera scholarly assembly.

---

## 1. Systematization of Ancient War Doctrines

Aiyanarithanar recognized that while civilian literature focused on emotional landscape poetry (*Aham*), the survival of sovereign states depended on rigorous tactical grammar (*Puram*). He condensed thousands of heroic Sangam war verses into clear, memorable venba stanzas that served as training manuals for commanders, explaining when to fortify ramparts, when to launch cavalry sorties, and how to honor fallen warriors with memorial stones.
"""
    },
    {
        "category": "characters",
        "slug": "char-okkur-masathiyar-martial-poetess",
        "file": "char-okkur-masathiyar-martial-poetess.md",
        "node_type": "character",
        "name_en": "Okkur Masathiyar (Sangam Poetess & Voice of Matriarchal Valor)",
        "name_ta": "ஒக்கூர் மாசாத்தியார் - சங்க கால மறத்தாய் மரபைப் பாடிய பெண்பாற்புலவர்",
        "era": "Sangam Early Historic Era",
        "year_start": 50,
        "year_end": 150,
        "thinai": "Mullai",
        "summary_en": "Celebrated Sangam poetess from the village of Okkur (near Sivaganga / Pandya kingdom). Renowned for her fiery compositions in Purananuru (especially hymn 279) depicting the indomitable courage of Tamil mothers who considered battlefield martyrdom the highest destiny for their sons, celebrating victory and honorable sacrifice over domestic grief.",
        "summary_ta": "பாண்டிய நாட்டின் ஒக்கூர் (சிவகங்கை அருகே) நகரில் வாழ்ந்த புகழ்பெற்ற சங்க கால பெண்பாற்புலவர். புறநானூற்றில் இவர் பாடிய 279-ஆம் பாடல், வீரத்தாய் ஒருத்தி தன் தமையனையும் கணவனையும் அடுத்தடுத்த நாட்களில் போர்க்களத்தில் பலிகொடுத்த நிலையிலும், மூன்றாம் நாள் போர்ப்பறை கேட்டு தன் இளம் பாலகனை மகிழ்ச்சியோடு வேலைக் கொடுத்துப் போர்க்களத்திற்கு அனுப்பி வைக்கும் மறக்குடி மாண்பினை உலக இலக்கியத்திற்கே பறைசாற்றியது.",
        "content": """# Okkur Masathiyar (ஒக்கூர் மாசாத்தியார்)

**Origin**: Okkur, Pandyan Kingdom.  
**Corpus**: *Purananuru* 279, *Akananuru*, *Kurunthogai*.  
**Legacy**: Foremost literary champion of the Tamil heroic matriarch (*வீரத்தாய்*).

---

## 1. The Philosophy of Martial Motherhood

Okkur Masathiyar articulated a cultural philosophy where women were not passive victims of war, but the ideological guardians of civilizational defense. In her poetry, a woman’s womb is described as a lion's rocky den (*Puli-ch-cherkkai*); it gave birth to warriors whose duty was to protect the village herds and agricultural realm, facing enemy spears without flinching.
"""
    },
    {
        "category": "characters",
        "slug": "char-thalaiyalanganathu-nedunchezhiyan",
        "file": "char-thalaiyalanganathu-nedunchezhiyan.md",
        "node_type": "character",
        "name_en": "Thalaiyalanganathu Cheru Vendra Nedunchezhiyan (The Victor of Talaiyalanganam)",
        "name_ta": "தலையாலங்கானத்துச் செருவென்ற நெடுஞ்செழியன் - பெருவீரப் பாண்டிய வேந்தன்",
        "era": "Sangam Early Historic Era",
        "year_start": 180,
        "year_end": 220,
        "thinai": "Marutham",
        "summary_en": "The heroic Early Pandyan Emperor who ascended the throne of Madurai as a young youth and faced a massive seven-monarch confederacy consisting of the Chera King, the Chola King, and five powerful Velir chieftains (Titiyan, Elini, Erumaiyuran, Irunkovel, and Porunan). In Purananuru 72, he took a sacred royal oath that if he failed to smash the coalition, he would be remembered as an unjust tyrant. At the fateful battle of Talaiyalanganam (Tiruvarur district), his brilliant tactical generalship encircled and destroyed the allied armies, capturing Chera King Mandaran Cheral Irumporai.",
        "summary_ta": "இளம் வயதிலேயே மதுரை அரியணை ஏறி, தன் மீது படையெடுத்து வந்த சேர மன்னன், சோழ மன்னன், மற்றும் ஐந்து வேளிர்கள் (திதியன், எழினி, எருமையூரன், இருங்கோவேள், பொருநன்) அடங்கிய எழுவர் கூட்டணியை தலையாலங்கானத்தில் தனித்து நின்று முறியடித்த மாவீரப் பாண்டிய மன்னன். 'இப்பகையரசர்களை போர்க்களத்தில் தோற்கடித்து சிறைபிடிக்காவிட்டால் என் குடிமக்கள் என்னை கொடுங்கோலன் என தூற்றட்டும்' என புறநானூறு 72-இல் வஞ்சினம் கூறி, தலையாலங்கானப் போர்க்களத்தில் சேர மன்னன் மாந்தரஞ்சேரல் இரும்பொறையை சிறைபிடித்து தென்னகத்தின் பேரரசராக உயர்ந்தவர்.",
        "content": """# Nedunchezhiyan: Victor of Talaiyalanganam (நெடுஞ்செழியன்)

**Dynasty**: Early Pandyas of Madurai.  
**Epochal Battle**: Talaiyalanganam (near Kudavasal / Tiruvarur, Kaveri basin).  
**Adversaries**: Combined Coalition of Chera, Chola, and 5 Velir Chieftains (*எழுவர் கூட்டணி*).

---

## 1. The Royal Oath of Purananuru 72 (*Vanjina-k-kanchi*)

Upon learning that the seven allied kings ridiculed his youth, Nedunchezhiyan swore before his court:
> *"They mock me saying 'He is just a lad!'... If I do not conquer them in pitched battle, capturing their war drums and royal insignia, may my subjects call me a wicked king who levies unjust taxes, and may the greatest poets like Mangudi Maruthanar refuse to sing in my hall!"*

---

## 2. Battlefield Triumph

Nedunchezhiyan met the massive allied host at **Talaiyalanganam**, deployed an aggressive wedge formation, broke their center, captured the Chera Emperor alive, and absorbed vast territories across the Kaveri and Kongu regions, earning him immortality in *Maduraikkanchi* and *Purananuru*.
"""
    },

    # --------------------------------------------------------------------------
    # 4. STRATEGIC SITES & ARCHAEOLOGICAL EXCAVATIONS
    # --------------------------------------------------------------------------
    {
        "category": "places",
        "slug": "place-thirumayam-rock-fortress",
        "file": "place-thirumayam-rock-fortress.md",
        "node_type": "place",
        "name_en": "Thirumayam Concentric Rock Fortress & Moated Citadel",
        "name_ta": "திருமயம் கருங்கல் கோட்டை மற்றும் பாறை அகழி அரண்",
        "era": "Early Historic to Poligar Era",
        "year_start": 700,
        "year_end": 1750,
        "thinai": "Mullai",
        "summary_en": "Monumental multi-tier concentric hill fortress located in Thirumayam, Pudukkottai District (10.2458° N, 78.7533° E). Built around an immense monolithic granite boulder, featuring three concentric outer stone walls, sheer defensive ramparts, rock-cut water moats, elevated gun/ballista platforms, subterranean sally-ports, and famous 8th-century Pandya rock-cut cave temples dedicated to Shiva and Vishnu (Sathyagiriswara and Sathyamurthi Perumal).",
        "summary_ta": "புதுக்கோட்டை மாவட்டம் திருமயத்தில் அமைந்துள்ள பிரம்மாண்டமான மூன்று அடுக்கு கருங்கல் மலைக்கோட்டை (10.2458° N, 78.7533° E). ஒற்றைக் கருங்கல் குன்றின் மீது கட்டப்பட்ட இந்நீண்ட மதில் அரண், ஆழமான பாறை அகழிகள், பீரங்கி மேடைகள், ரகசிய சுரங்கப் பாதைகள், மற்றும் 8-ஆம் நூற்றாண்டு பாண்டியர் குடைவரைக் கோயில்களைக் (சத்தியகிரீஸ்வரர் மற்றும் சத்தியமூர்த்தி பெருமாள்) கொண்டு திகழும் தமிழரின் ஒப்பற்ற கோட்டைப் பொறியியல் சின்னம்.",
        "content": """# Thirumayam Rock Fortress (திருமயம் கோட்டை)

**Location**: Thirumayam, Pudukkottai District, Tamil Nadu.  
**Coordinates**: 10.2458° N, 78.7533° E.  
**Architecture**: Concentric Granite Rock-Citadel (*மலையரண்*).

---

## 1. Fortress Engineering

Thirumayam exemplifies the classical Tamil *Malai-aran* (rock fortress):
- **Three Concentric Rings**: An outer circumvallation wall enclosing the town, a secondary inner defensive ring, and the soaring summit keep (*Kothalam*).
- **Rock-Cut Water Moat**: Carved directly out of granite bedrock, preventing sapping tunnels.
- **Historic Arsenal**: The summit bastion mounts a historic bronze cannon (*Kattu-vangi*) overlooking the surrounding plains.
"""
    },
    {
        "category": "places",
        "slug": "place-vembakottai-archaeological-site",
        "file": "place-vembakottai-archaeological-site.md",
        "node_type": "place",
        "name_en": "Vembakottai Vaippar Basin Weapons Manufacturing Citadel",
        "name_ta": "வேம்பக்கோட்டை வைப்பாற்றுப் போர்க்கருவிகள் தொழிற்கூடம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -800,
        "year_end": 300,
        "thinai": "Mullai",
        "summary_en": "Archaeological citadel and manufacturing town situated on the northern bank of the Vaippar River in Virudhunagar District (9.3361° N, 77.7719° E). Excavations conducted by the Tamil Nadu State Department of Archaeology have uncovered an industrial weaponry sector with hundreds of iron arrowheads, spears, bronze dagger hilts, carnelian beads, and gold artifacts, demonstrating high-volume standardized metallurgical weapon production during the Sangam and pre-Sangam epochs.",
        "summary_ta": "விருதுநகர் மாவட்டம் வேம்பக்கோட்டையில் வைப்பாற்றின் கரையில் அமைந்துள்ள வரலாற்றுத் தளம் (9.3361° N, 77.7719° E). தமிழ்நாடு அரசு தொல்லியல் துறையின் அகழாய்வில் கண்டறியப்பட்ட நூற்றுக்கணக்கான இரும்பு அம்பு முனைகள், ஈட்டிகள், சுடுமண் கவண்கற்கள், மற்றும் ஆயுதப் பட்டறைகள் இப்பகுதி பாண்டியப் பேரரசின் பிரதான படைக்கல உற்பத்தி மையமாகத் திகழ்ந்ததை உலகிற்கு நிறுவியுள்ளன.",
        "content": """# Vembakottai Citadel (வேம்பக்கோட்டை தளம்)

**Location**: Vembakottai, Virudhunagar District, Tamil Nadu.  
**Coordinates**: 9.3361° N, 77.7719° E.  
**River Basin**: Vaippar (*வைப்பாறு*).

---

## 1. Metallurgical Weapon Standardization

The sheer quantity and geometric consistency of the iron arrowheads and socketed spearheads discovered at Vembakottai indicate centralized, guild-regulated weapons production designed to supply Pandyan standing armies (*Kootai-p-padai*) and regional garrison forts along the southern trade corridors.
"""
    }
]

# ------------------------------------------------------------------------------
# 2. RELATIONAL EDGES
# ------------------------------------------------------------------------------
EDGES = [
    ("text-purapporul-venbamalai-military-code", "codifies_siege_tactics", "concept-aran-ancient-fortification", "textual", "Classical", "Details Uzhignai siege assaults and Nochchi rampart defense mechanics", "knowledge/texts/text-purapporul-venbamalai-military-code.md"),
    ("text-purapporul-venbamalai-military-code", "authored_by", "char-aiyanarithanar-military-theorist", "textual", "Classical", "Composed by Aiyanarithanar condensing ancient war doctrines", "knowledge/texts/text-purapporul-venbamalai-military-code.md"),
    ("text-purapporul-venbamalai-military-code", "codifies_memorialization", "concept-nadukal-hero-stone-cult", "textual", "Classical", "Formalizes the six ritual stages of erecting hero-stones for fallen warriors", "knowledge/texts/text-purapporul-venbamalai-military-code.md"),
    ("text-purananuru-martial-ethos", "contains_verse_of", "char-okkur-masathiyar-martial-poetess", "textual", "Sangam", "Preserves hymn 279 on the unyielding courage of the Sangam matriarch", "knowledge/texts/text-purananuru-martial-ethos.md"),
    ("text-purananuru-martial-ethos", "celebrates_triumph_of", "char-thalaiyalanganathu-nedunchezhiyan", "textual", "Sangam", "Records hymn 72 with Nedunchezhiyan's royal oath before Talaiyalanganam", "knowledge/texts/text-purananuru-martial-ethos.md"),
    ("insc-nadukal-hero-stones-chengam", "epigraphical_evidence_of", "concept-nadukal-hero-stone-cult", "epigraphical", "Pallava", "Over 60 Vatteluttu hero-stones physically documenting border skirmish martyrdom", "knowledge/inscriptions/insc-nadukal-hero-stones-chengam.md"),
    ("arch-vembakottai-weapons-arsenal", "produced_weapons_for", "concept-silambam-stick-fencing", "archaeological", "Sangam", "Excavated socketed spearheads, swords, and daggers used in martial combat", "knowledge/archaeology/arch-vembakottai-weapons-arsenal.md"),
    ("arch-vembakottai-weapons-arsenal", "excavated_at", "place-vembakottai-archaeological-site", "archaeological", "Sangam", "Located along the northern bank of the Vaippar river in Virudhunagar", "knowledge/archaeology/arch-vembakottai-weapons-arsenal.md"),
    ("concept-silambam-stick-fencing", "cross_trains_with", "concept-adimurai-varma-kalai", "martial", "Classical", "Adimurai unarmed footwork directly translates into Silambam stave movements", "knowledge/concepts/concept-silambam-stick-fencing.md"),
    ("concept-adimurai-varma-kalai", "shares_lineage_with", "concept-silambam-stick-fencing", "martial", "Classical", "Both martial arts originated in the Kurinji mountain tracts of Agastya", "knowledge/concepts/concept-adimurai-varma-kalai.md"),
    ("concept-valari-throwing-boomerang", "wielded_in", "text-purananuru-martial-ethos", "martial", "Sangam", "Ancient missile weapon deployed by Maravar warriors in arid desert warfare", "knowledge/concepts/concept-valari-throwing-boomerang.md"),
    ("concept-aran-ancient-fortification", "exemplified_by", "place-thirumayam-rock-fortress", "architectural", "Medieval", "Thirumayam's three concentric walls and rock-cut moats embody the Malai-aran doctrine", "knowledge/concepts/concept-aran-ancient-fortification.md"),
    ("char-thalaiyalanganathu-nedunchezhiyan", "exemplifies_thumpai", "text-purapporul-venbamalai-military-code", "historical", "Sangam", "Crushed the 7-king coalition in a classic Thumpai open-field collision", "knowledge/characters/char-thalaiyalanganathu-nedunchezhiyan.md"),
    ("place-thirumayam-rock-fortress", "houses_architecture_of", "concept-aran-ancient-fortification", "architectural", "Medieval", "Possesses concentric ramparts, moats, and rock-cut bastions", "knowledge/places/place-thirumayam-rock-fortress.md")
]

def main():
    print("=" * 75)
    print("⚔️ ANCIENT TAMIL MARTIAL ARTS, WEAPONRY & FORTIFICATION HARVESTER")
    print("=" * 75)

    # 1. Generate Canonical Markdown Files in moolam-chronicles
    print("\n[Phase 1] Writing Canonical Markdown Dossiers...")
    for d in DOSSIERS:
        target_dir = os.path.join(MOOLAM_KNOWLEDGE, d["category"])
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, d["file"])
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Written: knowledge/{d['category']}/{d['file']}")

    # 2. Connect to PostgreSQL
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # 3. Upsert Lore Nodes
    print("\n[Phase 2] Upserting Lore Nodes into PostgreSQL...")
    total_nodes_upserted = 0
    for d in DOSSIERS:
        cur.execute("""
            INSERT INTO lore_nodes (
                slug, node_type, name_en, name_ta, era,
                year_start, year_end, thinai, summary_en, summary_ta,
                properties, sources
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
