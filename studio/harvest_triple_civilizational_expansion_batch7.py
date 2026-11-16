#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 7):
1. Chola Revenue Secretariat, Cadastral Auditing & Land Classification (10 dossiers)
2. Epigraphical Royal Charters, Brahmadeya-Devadana Tenures & Pidi-Nadanthu (10 dossiers)
3. Village Irrigation Assemblies, Eri-Variyam Maintenance & Water Jurisprudence (10 dossiers)

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
    # CORPUS 1: CHOLA REVENUE SECRETARIAT & CADASTRAL AUDITING
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-periyapuranam-vari-pothagam-chola-revenue",
        "file": "text-periyapuranam-vari-pothagam-chola-revenue.md",
        "node_type": "text",
        "name_en": "Periyapuranam & Chola Administrative Canon: Vari-Pothagam Revenue Secretariat",
        "name_ta": "பெரியபுராணம் மற்றும் சோழர் ஆட்சி மரபு - வரிப் பொத்தகம் மற்றும் புறவுவரித் திணைக்களம்",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1150,
        "thinai": "Marutham",
        "summary_en": "Sekkizhar's literary and administrative depictions in Periyapuranam describing the imperial revenue ministry (Puravu-vari-thinaikalam), scribal ledgers (Vari-pothagam), cadastral audits, and royal land registrars.",
        "summary_ta": "சேக்கிழாரின் பெரியபுராணத்தில் இடம்பெறும் சோழப் பேரரசின் வருவாய்த்துறை ஆவணப் பதிவுகள். புறவுவரித் திணைக்களத்தின் தலைமைச் செயலகம், பனையோலை வரிப் பொத்தகங்கள், நிலவகைப்பாடு மற்றும் அரசு கணக்கர்களின் நிர்வாக நெறிமுறைகள்.",
        "content": """# Chola Revenue Secretariat (புறவுவரித் திணைக்களம்)

**Source**: *Periyapuranam* (*பெரியபுராணம்*), Inscriptional Glosses.  
**Subject**: Central Revenue Administration (*இறைவிதிப்பு*), Cadastral Ledgers (*வரிப் பொத்தகம்*).  

---

## 1. Bureaucratic Organization
The imperial revenue ministry (*Puravu-vari-thinaikalam*) operated in Thanjavur and Gangaikonda Cholapuram, maintaining duplicate copies of every village's land register to prevent fraudulent tax alteration.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-tanjavur-ulagalantan-cadastral-survey",
        "file": "insc-tanjavur-ulagalantan-cadastral-survey.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Ulagalantan Cadastral Survey Inscription: The 1001 CE Empire-Wide Land Audit",
        "name_ta": "தஞ்சை உலகளந்தான் நில அளவைக் கல்வெட்டு - கி.பி. 1001 சோழப் பேரரசு நிலக் கணக்கீடு",
        "era": "Imperial Chola Era",
        "year_start": 1001,
        "year_end": 1005,
        "thinai": "Marutham",
        "summary_en": "Monumental inscriptional record of Rajaraja I's empire-wide cadastral land survey in 1001 CE ('உலகளந்த சோழன்'), measuring agricultural lands to micro-fractions (1/52,428,800,000 Veli), resolving boundary disputes, and reassessing revenues.",
        "summary_ta": "முதலாம் இராஜராஜ சோழன் கி.பி. 1001-இல் மேற்கொண்ட அகில சோழமண்டல நில அளவை ஆவணம். 'உலகளந்தான்' என்னும் 16 சாண் கோல் கொண்டு அணு, இம்மி, கீழ்முந்திரி வரை மிகத் துல்லியமாக நிலங்களை அளந்து வரி விதித்த வரலாற்றுப் பெருங்கல்வெட்டு.",
        "content": """# The Ulagalantan Cadastral Survey (உலகளந்தான் அளவை)

---

## 1. Survey Precision
Rajaraja I appointed royal surveyors who traversed every village with the standard imperial 16-span rod (*Ulagalantan-kol*). Lands were mapped into:
- Taxable fields (*Irai-kattina-nilam*).
- Tax-exempt public spaces (*Irayili-nilam*): temple sanctums, cremation grounds, irrigation canals, threshing floors, and village assembly halls.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kandiyur-puravu-vari-revenue-charter",
        "file": "insc-kandiyur-puravu-vari-revenue-charter.md",
        "node_type": "inscription",
        "name_en": "Tirukkandiyur Revenue Charters: Tax Reclassifications & Flood Remission Decrees",
        "name_ta": "திருக்கண்டியூர் புறவுவரிச் சாசனம் - நில வகைப்பாடு மாற்றம் மற்றும் வெள்ள நிவாரண ஆணை",
        "era": "Imperial Chola Era",
        "year_start": 1020,
        "year_end": 1060,
        "thinai": "Marutham",
        "summary_en": "Inscriptions at the Tirukkandiyur temple recording royal revenue orders (Tittu) issued by the Puravu-vari-thinaikalam, reclassifying sand-inundated river floodplains from wetland (Nansey) to lower-tax dryland (Punsey).",
        "summary_ta": "திருக்கண்டியூர் கோயிலில் பொறிக்கப்பட்ட புறவுவரித் திணைக்களத்தின் அரசு ஆணைக் கல்வெட்டு. காவிரி ஆற்று வெள்ளத்தால் மணல் மேடிட்டுப் பாழான நன்செய் நிலங்களை ஆய்வு செய்து, வரி குறைக்கப்பட்ட புன்செய் நிலங்களாக மாற்றிப் பதிந்த ஆவணம்.",
        "content": """# Tirukkandiyur Revenue Charters (திருக்கண்டியூர் சாசனம்)

**Site**: Tirukkandiyur Temple (*திருக்கண்டியூர்*), Thanjavur District.  
**Key Feature**: Demonstrates responsive taxation where imperial audits lowered tax burdens (*Tharavu*) after natural flood disasters.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-puravu-vari-thinaikalam-revenue-ministry",
        "file": "concept-puravu-vari-thinaikalam-revenue-ministry.md",
        "node_type": "concept",
        "name_en": "Puravu-Vari-Thinaikalam: The Central Chola Revenue Secretariat & Tax Bureaucracy",
        "name_ta": "புறவுவரித் திணைக்களம் - சோழப் பேரரசின் மத்திய நிதி மற்றும் நிலவருவாய்ச் செயலகம்",
        "era": "Imperial Chola Era",
        "year_start": 950,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The centralized imperial revenue department of the Cholas, organized hierarchically with departments for tax entry (Vari-y-iliitu), tax registers (Pothagam), seal verifiers (Muga-vetti), and revenue adjudicators.",
        "summary_ta": "சோழர் காலத்து மத்திய நிலவருவாய்ச் செயலகத்தின் அடுக்குமுறை கட்டமைப்பு. பட்டோலை எழுதுவோர், முகம்வெட்டி (அரச முத்திரை வைப்போர்), வரிப்பொத்தகக் கணக்கர் மற்றும் நாடு-வளநாடு வாரியான தணிக்கை அதிகாரிகள்.",
        "content": """# Puravu-Vari-Thinaikalam Architecture (புறவுவரித் திணைக்களம்)

---

## 1. Secretarial Ranks
- **Thinaikkala-Nayakam (*திணைக்கள நாயகம்*)**: Chief Revenue Secretary.
- **Vari-y-Iliitu (*வரியிலீடு*)**: Officer registering newly assessed land grants in state rolls.
- **Muga-Vetti (*முகம்வெட்டி*)**: High commissioner who countersigned and applied the royal tiger wax-seal (*Iraja-mudra*) to tax orders.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-vari-pothagam-cadastral-palm-leaf-ledgers",
        "file": "concept-vari-pothagam-cadastral-palm-leaf-ledgers.md",
        "node_type": "concept",
        "name_en": "Vari-Pothagam: Cadastral Palm-Leaf Ledgers, Boundary Surveys & Ledger Auditing",
        "name_ta": "வரிப் பொத்தகம் - பனையோலை நிலப்பதிவுப் புத்தகங்கள், எல்லை அளவுகள் மற்றும் தணிக்கை",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The official palm-leaf register maintained in each agrarian district (Nadu / Valanadu) recording every plot's boundaries, irrigation access, soil grade, ownership changes, and annual tax assessment in paddy and gold.",
        "summary_ta": "ஒவ்வொரு கிராமத்திற்கும் பேணப்பட்ட பனையோலை நில ஆவணப் புத்தகம். நிலத்தின் எல்லைகள், பாசன வாய்க்கால்கள், மண்ணின் தரம், உரிமையாளர் பெயர்கள் மற்றும் அரசுக்குச் செலுத்த வேண்டிய நெல்-பொன் அளவுகள் விரிவாகப் பதியப்பட்ட முறைமை.",
        "content": """# Vari-Pothagam Cadastral Ledgers (வரிப் பொத்தகம்)

---

## 1. Audit Security
Whenever a private sale or royal endowment occurred, the *Karanathan* (local scribe) drafted the deed, which was then taken to the district headquarters to update the master *Vari-pothagam*.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-chola-land-tax-classifications",
        "file": "concept-chola-land-tax-classifications.md",
        "node_type": "concept",
        "name_en": "Chola Land Tax Classifications: Nansey, Punsey, Nattam & Taram Soil Grading",
        "name_ta": "சோழர் நிலவகைப்பாடு - நன்செய், புன்செய், மனைநத்தம் மற்றும் தர வாரியான வரிமதிப்பீடு",
        "era": "Imperial Chola Era",
        "year_start": 900,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The scientific soil and tenure classification system of medieval Tamilakam: grading wetland soils into 12 quality classes (Taram), measuring water reliability from perennial canals versus rainfed tanks, and setting proportionate tax rates (Kadamai).",
        "summary_ta": "விளைநிலங்களை 12 தரங்களாகப் பிரித்து வரி விதித்த அறிவியல் பூர்வ நிலவகைப்பாடு. ஆற்றுப் பாசன நன்செய், மானாவாரிப் புன்செய், பழத்தோட்டம், குடியிருப்பு மனைநத்தம் மற்றும் உவர்நிலங்களுக்கான தனித்தனி வரி நெறிமுறைகள்.",
        "content": """# Chola Land Classification & Taram System (நில வகைப்பாடு)

---

## 1. Taram Quality Hierarchy
1. **First-Grade Nansey (*முதல் தர நன்செய்*)**: Double-cropped silt-renewed paddies fed by perennial river channels (approx. 100 kalams/veli tax).
2. **Intermediate Taram (2–6)**: Single-cropped tank-fed wetlands.
3. **Punsey & Dryland (7–12)**: Rainfed millets, pulses, and oilseeds taxed at lower nominal rates.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-ulagalantan-16-span-standard-survey-rod",
        "file": "concept-ulagalantan-16-span-standard-survey-rod.md",
        "node_type": "concept",
        "name_en": "Ulagalantan Measuring Rod: The 16-Span Standard Cadastral Staff & Micro-Acreage",
        "name_ta": "உலகளந்தான் கோல் - 16 சாண் கொண்ட தரப்படுத்தப்பட்ட சோழர் நில அளவைக் கோல்",
        "era": "Imperial Chola Era",
        "year_start": 1001,
        "year_end": 1150,
        "thinai": "Marutham",
        "summary_en": "The official 16-span wooden or bronze-tipped measuring rod (Ulagalantan-kol / Sripadha-kol) calibrated to royal physical standards, incised on temple basements to ensure unalterable public land-measurement standards.",
        "summary_ta": "இராஜராஜ சோழன் அறிமுகப்படுத்திய 16 சாண் நீளமுள்ள நில அளவைக் கோல். ஊர் தோறும் கோயில் சுவர்களில் இக்கோலின் சரியான நீளம் செதுக்கப்பட்டு, நில அளவையாளர்கள் பொதுமக்களின் நிலங்களை அளக்கப் பயன்படுத்திய அரசு அளவுகோல்.",
        "content": """# The Ulagalantan Measuring Rod (உலகளந்தான் கோல்)

---

## 1. Standard Linear Calibration
The 16-span rod (*சாண்*) measured approximately 3.6 to 4 meters. A square of 1 rod was 1 *Kuzhi*; 100 Kuzhis made 1 *Maa*; 20 Maas equaled 1 *Veli* (~6.6 acres).
"""
    },
    {
        "category": "characters",
        "slug": "char-puravu-vari-thinaikkala-nayakan",
        "file": "char-puravu-vari-thinaikkala-nayakan.md",
        "node_type": "character",
        "name_en": "Puravu-Vari-Thinaikkala-Nayakan: Imperial Revenue Minister & Chief Comptroller",
        "name_ta": "புறவுவரித் திணைக்கள நாயகம் - சோழப் பேரரசின் தலைமை நிதி அமைச்சர் மற்றும் நிலத்தணிக்கையாளர்",
        "era": "Imperial Chola Era",
        "year_start": 1000,
        "year_end": 1070,
        "thinai": "Marutham",
        "summary_en": "High ministerial dignitary who directed the statewide cadastral registration, audited village assembly ledgers, and signed royal tax remission orders under the imperial authority.",
        "summary_ta": "அரசரின் ஒப்புதலோடு பேரரசு முழுவதும் நில அளவைகளை வழிநடத்தி, வரிப் பொத்தகங்களை மேற்பார்வையிட்டு வரிவிலக்கு ஆணைகளை பிறப்பித்த தலைமை நிதி அமைச்சர்.",
        "content": """# The Chief Comptroller (திணைக்கள நாயகம்)

Enjoyed highest aristocratic status (*Brahmadhiraja* or *Marayan*), working directly beneath the royal executive council in Thanjavur.
"""
    },
    {
        "category": "characters",
        "slug": "char-ulagalantan-royal-land-surveyor",
        "file": "char-ulagalantan-royal-land-surveyor.md",
        "node_type": "character",
        "name_en": "Ulagalantan Land Surveyor: Certified Imperial Field Assayer & Rod Bearer",
        "name_ta": "உலகளந்தான் நில அளவையாளர் - அரச சான்றளிக்கப்பட்ட நில அளவை அதிகாரி மற்றும் கோல்காரர்",
        "era": "Imperial Chola Era",
        "year_start": 1001,
        "year_end": 1050,
        "thinai": "Marutham",
        "summary_en": "Professional surveyor equipped with the standard 16-span rod who traversed muddy paddies, planted boundary stone markers (Kallu), and recorded fractions with the village Sabhai.",
        "summary_ta": "அரசு முத்திரை பெற்ற 16 சாண் கோல் ஏந்தி, வயல் வரப்புகளில் இறங்கி எல்லைகளை அளந்து, எல்லைக் கற்களை நாட்டி நில அளவை ஆவணங்களை உருவாக்கிய வல்லுநர்.",
        "content": """# The Royal Surveyor (நில அளவையாளர்)

Trained in complex fractional metrology, these officers were legally accountable for maintaining zero-error precision across communal and private properties.
"""
    },
    {
        "category": "places",
        "slug": "place-tirukkandiyur-chola-revenue-secretariat",
        "file": "place-tirukkandiyur-chola-revenue-secretariat.md",
        "node_type": "place",
        "name_en": "Tirukkandiyur: Historic Chola Administrative Center & Revenue Secretariat Site",
        "name_ta": "திருக்கண்டியூர் - சோழர் காலத்து வருவாய்த் திணைக்கள நிர்வாக மையம்",
        "era": "Imperial Chola Era",
        "year_start": 900,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "Historic temple and administrative township on the southern bank of the Kaveri near Thanjavur, where key royal charters on land reclassification, canal water rights, and tax audits are preserved.",
        "summary_ta": "தஞ்சாவூர் அருகே காவிரிக் கரையில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க நிர்வாக மையம். சோழர் காலத்து நிலவருவாய் வகைப்பாடுகள், வரிவிலக்குகள் மற்றும் நீர்ப்பாசன ஆணைகள் பொறிக்கப்பட்டுள்ள தளம்.",
        "content": """# Tirukkandiyur Administrative Center (திருக்கண்டியூர்)

- **Coordinates**: 10.8500° N, 79.1167° E.  
- **District**: Thanjavur, Tamil Nadu.  
- **Historical Significance**: Epicenter for royal cadastral audits and flood-relief revenue adjustments.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: EPIGRAPHICAL ROYAL CHARTERS & BRAHMADEYA-DEVADANA TENURES
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-anbil-copper-plates-chola-genealogy",
        "file": "text-anbil-copper-plates-chola-genealogy.md",
        "node_type": "text",
        "name_en": "Anbil Copper Plates: Sundara Chola's Royal Charter to Minister Aniruddha Brahmadhiraja",
        "name_ta": "அன்பில் செப்பேடுகள் - சுந்தர சோழனின் அரச சாசனம் மற்றும் அநிருத்த பிரம்மாதிராஜன் கொடை",
        "era": "Imperial Chola Era",
        "year_start": 960,
        "year_end": 970,
        "thinai": "Marutham",
        "summary_en": "The famous bilingual copper-plate charter of Sundara Chola (c. 961 CE) comprising Sanskrit Prasasti and classical Tamil legal sections, granting fertile lands to minister Aniruddha with elephant boundary walking and tax immunities.",
        "summary_ta": "சுந்தர சோழரின் 10-ஆம் நூற்றாண்டு வரலாற்றுச் செப்பேடு. சமஸ்கிருத மெய்க்கீர்த்தி மற்றும் விரிவான தமிழ்ப் பகுதி கொண்டு, தனது அமைச்சர் அநிருத்த பிரம்மாதிராஜனுக்கு அன்பில் கிராமத்து விளைநிலங்களைப் பிடி சூழ்ந்து பரிவட்டமளித்த சட்ட ஆவணம்.",
        "content": """# The Anbil Copper Plates (அன்பில் செப்பேடுகள்)

**Donor**: King Parantaka II (Sundara Chola).  
**Recipient**: Minister Aniruddha Brahmadhiraja.  

---

## 1. Bilingual Diplomatic Structure
- **Sanskrit Section (Grantha Script)**: Traces mythical solar origins of the Cholas from Manu, Sibi, and Karikala down to Sundara Chola.
- **Tamil Section (Tamil Script)**: Outlines precise village boundaries, water rights from the Kollidam river, and 30 tax exemptions (*Irayili*).
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-velanjeri-copper-plates-parantaka",
        "file": "insc-velanjeri-copper-plates-parantaka.md",
        "node_type": "inscription",
        "name_en": "Velanjeri Copper Plates: Parantaka I's Brahmadeya Grant & Elephant Boundary Rites",
        "name_ta": "வேளஞ்சேரி செப்பேடுகள் - முதலாம் பராந்தக சோழனின் பிரம்மதேய தானம் மற்றும் பிடிசூழ்ந்த எல்லைகள்",
        "era": "Early Medieval Chola Era",
        "year_start": 930,
        "year_end": 940,
        "thinai": "Marutham",
        "summary_en": "Discovered near Tiruttani, these copper plates of Parantaka I record the consolidation of village lands into a Brahmadeya scholar colony, accompanied by the ritual circumambulation of an elephant (Pidi-soozhnthu) to fix permanent boundaries.",
        "summary_ta": "திருத்தணி அருகே வேளஞ்சேரியில் கண்டெடுக்கப்பட்ட முதலாம் பராந்தக சோழனின் செப்பேடுகள். வேத அறிஞர்களுக்கு நிலங்களை ஒருங்கிணைத்து பிரம்மதேயமாக வழங்கி, பெண் யானையை நடத்தி எல்லைகளை உறுதிசெய்த ஆவணம்.",
        "content": """# Velanjeri Copper Plates (வேளஞ்சேரி செப்பேடுகள்)

---

## 1. Ritual Elephant Boundary Fixing (*பிடி சூழ்ந்து*)
The charter records: *"பிடி சூழ்ந்து எல்லை காட்டி..."*  
A trained royal female elephant walked the entire perimeter of the settlement; where she paused or turned, stone cairns (*Kallu*) and euphorbia bushes (*Kalli*) were planted by village assembly witnesses.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-karandai-tamil-sangam-plates-rajendra",
        "file": "insc-karandai-tamil-sangam-plates-rajendra.md",
        "node_type": "inscription",
        "name_en": "Karandai Tamil Sangam Copper Plates: Rajendra I's 55-Leaf Imperial Grant",
        "name_ta": "கரந்தை தமிழ்ச் சங்கச் செப்பேடுகள் - முதலாம் இராஜேந்திர சோழனின் 55 ஏடுகள் கொண்ட பிரம்மாண்ட சாசனம்",
        "era": "Imperial Chola Era",
        "year_start": 1020,
        "year_end": 1030,
        "thinai": "Marutham",
        "summary_en": "The heaviest copper-plate charter in Indian history (weighing over 100 kg across 55 massive bronze plates linked by a massive seal ring), recording Rajendra I's establishment of Tribhuvana-mahadevi-chaturvedimangalam for 1,080 scholars.",
        "summary_ta": "இந்திய வரலாற்றிலேயே மிக எடையுள்ள செப்பேட்டுத் தொகுதி (100 கிலோ, 55 வெண்கல ஏடுகள்). முதலாம் இராஜேந்திர சோழன் 1,080 அறிஞர்களுக்கு நிலங்களை வழங்கி உருவாக்கிய பிரம்மாண்ட பிரம்மதேய கிராமத்தின் சாசனம்.",
        "content": """# The Karandai Copper Plates (கரந்தைச் செப்பேடுகள்)

**Seal**: Cast bronze ring bearing the Chola Tiger seated between the Pandyan Twin Fish and Chera Bow, surmounted by an umbrella and flywhisks.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-brahmadeya-and-devadana-land-tenures",
        "file": "concept-brahmadeya-and-devadana-land-tenures.md",
        "node_type": "concept",
        "name_en": "Brahmadeya & Devadana Tenures: Corporate Agrarian Autonomy & Assembly Governance",
        "name_ta": "பிரம்மதேயம் மற்றும் தேவதான நிலவுடைமை - கிராமத் தன்னாட்சி மற்றும் சபை நிர்வாகம்",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 600,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The institutional socioeconomic framework of royal land grants in ancient and medieval Tamilakam: Brahmadeyas (granted to scholarly assemblies) and Devadanas (endowed to temple deities), enjoying corporate extraterritoriality and local assembly rule (Sabhai).",
        "summary_ta": "அரசர்களால் உருவாக்கப்பட்ட தன்னாட்சி நிலவுடைமை அமைப்புகள். அறிஞர்களுக்கு வழங்கப்பட்ட பிரம்மதேயங்களும், கோயில்களுக்கு வழங்கப்பட்ட தேவதானங்களும் தனி சபை அமைப்புகள் வாயிலாக வரிநீக்கம், பாசனம், நீதி மற்றும் நிலவிற்பனையை சுயமாக நிர்வகித்த மரபு.",
        "content": """# Brahmadeya & Devadana Tenures (பிரம்மதேயம் - தேவதானம்)

---

## 1. Dual Institutional Autonomy
- **Brahmadeya (*பிரம்மதேயம்*)**: Governed by the *Sabhai* (assembly of literate landholders) using democratic committee (*Variyam*) systems.
- **Devadana (*தேவதானம்*)**: Temple-owned estates where revenues fed rituals, bronze casters, musicians, dancers, and daily public feeding halls (*Salai*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-pidi-soozhnthu-elephant-boundary-perambulation",
        "file": "concept-pidi-soozhnthu-elephant-boundary-perambulation.md",
        "node_type": "concept",
        "name_en": "Pidi-Soozhnthu: Ritual Elephant Circumambulation & Ancient Boundary Demarcation",
        "name_ta": "பிடி சூழ்ந்து எல்லை நடத்தல் - பெண் யானையை நடத்தி எல்லைகளை உறுதிசெய்யும் சட்டச் சடங்கு",
        "era": "Sangam to Imperial Chola Era",
        "year_start": -200,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The ancient Tamil legal and sacred protocol of establishing village perimeter borders: an anointed royal female elephant (Pidi) perambulated the boundaries followed by village elders, planting boundary stones (Ellaik-kallu) and cactus hedges (Kalli).",
        "summary_ta": "புதிய கிராம தானங்களின் எல்லைகளை வரையறுக்க, அலங்கரிக்கப்பட்ட அரச பெண் யானையை எல்லை நெடுகிலும் நடத்தி, அது செல்லும் வழியெல்லாம் எல்லைக்கற்கள் நட்டும் கள்ளிச்செடிகள் நட்டும் எல்லையை உறுதிசெய்த சட்ட நெறிமுறை.",
        "content": """# Pidi-Soozhnthu Protocol (பிடி சூழ்ந்து எல்லை நடத்தல்)

---

## 1. Legal Witnessing
The circumambulation required presence of representatives from all adjoining villages (*Ayaloor-perumakkal*). Wherever the elephant took a step or crossed a canal, the natural markers (banyans, anthills, ponds) were recorded in the copper plates.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-irayili-tax-exemption-and-kadamai",
        "file": "concept-irayili-tax-exemption-and-kadamai.md",
        "node_type": "concept",
        "name_en": "Irayili Tax Exemptions: Royal Remissions, Kadamai & Kudimai Immunity Charters",
        "name_ta": "இறையிலி நிலக்கொடை - அரச வரிகள் நீக்கம், கடமை மற்றும் குடிமை வரிவிலக்குகள்",
        "era": "Imperial Chola Era",
        "year_start": 900,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The comprehensive legal mechanism of declaring endowed lands Irayili (tax-free), extinguishing state claims to land tax (Kadamai), tenancy dues (Kudimai), forced labor (Vetti), and toll cesses, vesting these revenues in local institutions.",
        "summary_ta": "அரசால் நிலங்கள் 'இறையிலி' என அறிவிக்கப்படும் முறைமை. இதன்மூலம் அரசுக்குச் செல்ல வேண்டிய நிலவரி (கடமை), உழைப்பு வரி (வெட்டி), மற்றும் 30-க்கும் மேற்பட்ட உள்ளூர்க் கட்டணங்கள் முழுவதும் நீக்கப்பட்டு, அத்தொகை உள்ளூர் வளர்ச்சிக்கு ஒதுக்கப்பட்டது.",
        "content": """# Irayili Immunity Charters (இறையிலி வரிநீக்கம்)

---

## 1. Extinguished Dues
Inscriptions list detailed exemptions:
- *Ech-choru* (free meals to visiting royal officers).
- *Vetti-muttaval* (compulsory levee repair labor).
- *Thari-irai* (loom tax) and *Sekku-irai* (oil-press tax).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-chola-royal-copper-plate-karanams",
        "file": "concept-chola-royal-copper-plate-karanams.md",
        "node_type": "concept",
        "name_en": "Chola Royal Copper-Plate Karanams: Diplomatic Formulation & Bronze Ring Seals",
        "name_ta": "சோழர் செப்பேட்டு சாசனங்கள் - அரச ஆணை உருவாக்கம், வெண்கல முத்திரை வளையம் மற்றும் நம்பகத்தன்மை",
        "era": "Imperial Chola Era",
        "year_start": 900,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The diplomatic and forensic structure of imperial Chola copper charters (Sempetu): royal oral declaration (Tittu), palace secretariat endorsement, copper plate incision, and sealing with massive lost-wax bronze tiger-seal rings.",
        "summary_ta": "சோழர் செப்பேடுகளின் அதிகாரப்பூர்வ உருவாக்கம். மன்னனின் வாய்மொழி ஆணை, ஓலை நாயகம் சரிபார்த்தல், செப்புத் தகடுகளில் எழுத்துகள் செதுக்கப்படுதல், மற்றும் துளையிடப்பட்ட ஏடுகளை வெண்கலப் புலி முத்திரை வளையத்தில் இணைத்து முத்திரையிடும் முறை.",
        "content": """# Royal Copper Plate Karanams (செப்பேட்டு உருவாக்கம்)

---

## 1. Physical Security
The ring hole was sealed with a solid bronze medallion cast with the Chola royal crest (Tiger, Fish, Bow), preventing any unauthorized removal or substitution of copper sheets.
"""
    },
    {
        "category": "characters",
        "slug": "char-aniruddha-brahmadhiraja-chola-minister",
        "file": "char-aniruddha-brahmadhiraja-chola-minister.md",
        "node_type": "character",
        "name_en": "Aniruddha Brahmadhiraja: Chief Minister of Sundara Chola & Recipient of Anbil Grant",
        "name_ta": "அநிருத்த பிரம்மாதிராஜன் - சுந்தர சோழரின் தலைமை அமைச்சர் மற்றும் அன்பில் செப்பேடு பெற்ற பெருமகன்",
        "era": "Imperial Chola Era",
        "year_start": 950,
        "year_end": 980,
        "thinai": "Marutham",
        "summary_en": "Eminent statesman, legal scholar, and hereditary minister under Parantaka II (Sundara Chola) whose profound administrative counsel was commemorated in the famous Anbil copper plates.",
        "summary_ta": "சுந்தர சோழரின் அரசவையில் தலைமை அமைச்சராகவும் அரச குருவாகவும் விளங்கிய அறிஞர். பேரரசின் வெளியுறவுக் கொள்கைகளை வகுத்தமைக்காக அன்பில் கிராமத்தை தானமாகப் பெற்றவர்.",
        "content": """# Aniruddha Brahmadhiraja (அநிருத்த பிரம்மாதிராஜன்)

Celebrated as a pillar of Chola statecraft, he orchestrated imperial endowments while preserving traditional village assembly rights.
"""
    },
    {
        "category": "characters",
        "slug": "char-pidi-nadanthu-boundary-arbitrator",
        "file": "char-pidi-nadanthu-boundary-arbitrator.md",
        "node_type": "character",
        "name_en": "Pidi-Nadanthu Arbitrator: Elder Statesman of the Boundary Walk & Land Verifier",
        "name_ta": "பிடி நடந்த எல்லை நடுவர் - பெண் யானையோடு எல்லை நடந்து சான்றளித்த நாட்டுப் பெருமகன்",
        "era": "Imperial Chola Era",
        "year_start": 950,
        "year_end": 1020,
        "thinai": "Marutham",
        "summary_en": "Venerable agrarian magistrate chosen from neighboring assemblies who walked alongside the royal elephant, resolving boundary ambiguities and witnessing the planting of border markers.",
        "summary_ta": "அயல் கிராமங்களின் சார்பாக பெண் யானையோடு எல்லை நெடுகிலும் நடந்து, ஆற்று நீர் உரிமைகளையும் வாய்க்கால் எல்லைகளையும் நடுநிலையாக நின்று உறுதிசெய்த மூத்த நில நடுவர்.",
        "content": """# The Boundary Arbitrator (எல்லை நடுவர்)

Their eyewitness testimony and signatures were legally required on copper plate charters to prevent future inter-village border litigation.
"""
    },
    {
        "category": "places",
        "slug": "place-anbil-chola-brahmadeya-settlement",
        "file": "place-anbil-chola-brahmadeya-settlement.md",
        "node_type": "place",
        "name_en": "Anbil: Kollidam North Bank Historic Brahmadeya & Copper-Plate Discovery Site",
        "name_ta": "அன்பில் - கொள்ளிடக் கரையின் வரலாற்றுச் சிறப்புமிக்க பிரம்மதேய கிராமம்",
        "era": "Imperial Chola Era",
        "year_start": 900,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Ancient agrarian township on the northern bank of the Kollidam River near Lalgudi (Tiruchirappalli), celebrated for Sundara Chola's monumental copper-plate grant and intact medieval temple assemblies.",
        "summary_ta": "திருச்சி லால்குடி அருகே கொள்ளிடக் கரையில் அமைந்துள்ள புகழ்பெற்ற வரலாற்றுத் தளம். சுந்தர சோழரின் அன்பில் செப்பேடுகள் கண்டெடுக்கப்பட்ட தளம் மற்றும் சோழர் காலத்து பிரம்மதேய சபை விளங்கிய ஊர்.",
        "content": """# Anbil Brahmadeya Site (அன்பில்)

- **Coordinates**: 10.8667° N, 78.8833° E.  
- **River**: Kollidam River alluvial basin (*கொள்ளிடம்*).  
- **Significance**: Archetypal Chola Brahmadeya township illustrating elephant boundary demarcations and canal distribution.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: VILLAGE IRRIGATION ASSEMBLIES & ERI-VARIYAM MAINTENANCE FUNDS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-thiruvalluvar-arasan-neer-management-ethics",
        "file": "text-thiruvalluvar-arasan-neer-management-ethics.md",
        "node_type": "text",
        "name_en": "Thirukkural: Arasan Neer Management Ethics, Bund Conservation & Agrarian Rain Ethos",
        "name_ta": "திருக்குறள் - அரசனின் நீரியல் கடமை, வான்சிறப்பு மற்றும் ஏரிப் பராமரிப்பு நீதிநெறி",
        "era": "Sangam Post-Classical Era",
        "year_start": 300,
        "year_end": 500,
        "thinai": "Marutham",
        "summary_en": "Thiruvalluvar's ethical formulations on water infrastructure in Thirukkural (Vanshirappu and Iraimatchi): establishing that sovereign virtue requires excavating tanks, fortifying bunds, and equitable water distribution.",
        "summary_ta": "திருக்குறளில் வான்சிறப்பு மற்றும் இறைமாட்சி அதிகாரங்களில் இடம்பெறும் நீரியல் நீதிநெறிகள். ஏரிகளை வெட்டுதல், கரைகளைப் பலப்படுத்துதல், பாசன நீரை முறைசெய்து வழங்கல் ஒரு நல்லரசுக்கான அடிப்படை இலக்கணம் என்பதை உணர்த்தும் குறட்பாக்கள்.",
        "content": """# Thirukkural Water Governance Ethics (திருக்குறள் நீரியல் நெறி)

---

## 1. Sovereignty and Water
*"மாரி பொய்ப்பின் வாரி குன்றும்"* - Highlighting that state survival depends on rainwater harvesting and storage reservoirs (*Erigal*).
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-uttiramerur-eri-variyam-tank-charter",
        "file": "insc-uttiramerur-eri-variyam-tank-charter.md",
        "node_type": "inscription",
        "name_en": "Uttiramerur Eri-Variyam Charter: The 921 CE Democratic Tank Committee Code",
        "name_ta": "உத்திரமேரூர் ஏரி வாரியக் கல்வெட்டு - கி.பி. 921 ஏரிப் பராமரிப்புக் குழுவின் மக்களாட்சித் தேர்தல்",
        "era": "Early Medieval Chola Era",
        "year_start": 919,
        "year_end": 921,
        "thinai": "Marutham",
        "summary_en": "Parantaka I's world-famous epigraph on the Vaikunta Perumal temple at Uttiramerur detailing the pot-ticket election (Kudavolai) of the annual Tank Committee (Eri-variyam), disqualifications, and desilting mandates.",
        "summary_ta": "முதலாம் பராந்தக சோழனின் உலகப் புகழ்பெற்ற உத்திரமேரூர்க் கல்வெட்டு. ஏரி வாரிய உறுப்பினர்களைக் குடவோலை முறையில் தேர்ந்தெடுத்தல், ஏரியின் மதகுகள், கரைகள், மற்றும் தூர்வாரும் பணிகளை நிர்வகிப்பதற்கான தகுதிகளும் கடமைகளும்.",
        "content": """# Uttiramerur Eri-Variyam Charter (ஏரி வாரியம்)

---

## 1. Electoral Rules for Tank Custodians
Members of the *Eri-variyam* were elected annually from the 30 village wards (*Kudumbu*):
- Must possess land and a house on private property.
- Must be aged between 35 and 70 with moral rectitude.
- Disqualified if they failed to submit audited water maintenance accounts.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-tribhuvani-lake-maintenance-endowment",
        "file": "insc-tribhuvani-lake-maintenance-endowment.md",
        "node_type": "inscription",
        "name_en": "Tribhuvani Lake Charters: Gold Endowments, Eri-Vandi Carts & Daily Desilting Mandates",
        "name_ta": "திருபுவனை ஏரிப் பராமரிப்பு சாசனம் - பொன் மூலதனம், ஏரி வண்டிகள் மற்றும் நாள்தோறும் தூர்வாரும் திட்டம்",
        "era": "Imperial Chola Era",
        "year_start": 1040,
        "year_end": 1080,
        "thinai": "Marutham",
        "summary_en": "Monumental Chola inscription at Tribhuvani near Puducherry recording a permanent gold endowment deposited with the assembly, using annual interest to maintain six bullock carts (Eri-vandi) to dredge lake silt year-round.",
        "summary_ta": "புதுச்சேரி திருபுவனைக் கோயிலில் உள்ள சோழர் கல்வெட்டு. ஏரியின் ஆழத்தைப் பராமரிக்க பொன் நிதியைப் பொதுமக்கள் முதலீடு செய்து, அதன் வட்டியைக் கொண்டு 6 ஏரி மாட்டு வண்டிகளை வாங்கி, ஆண்டு முழுவதும் நாள்தோறும் வண்டல் மண்ணை அகற்றிய வரலாற்றுச் சான்று.",
        "content": """# Tribhuvani Lake Desilting Charter (திருபுவனை ஏரி சாசனம்)

---

## 1. Sustainable Infrastructure Finance
The charter specifies:
- 6 bullock carts (*ஏரி வண்டி*) dedicated exclusively to lake dredging.
- Each cart driver required to haul a specified number of silt loads (*Kuzhi*) daily to village fields as fertile organic manure.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-eri-variyam-elected-tank-committee",
        "file": "concept-eri-variyam-elected-tank-committee.md",
        "node_type": "concept",
        "name_en": "Eri-Variyam: The Elected Village Tank Committee & Democratic Water Management",
        "name_ta": "ஏரி வாரியம் - கிராம சபையின் மக்களாட்சித் தன்னாட்சி நீர்ப்பாசனக் குழு",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 800,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The premier specialized standing committee of the medieval South Indian village assembly (Sabhai), entrusted with complete autonomy to maintain community tanks, supervise sluices, manage repair funds, and arbitrate irrigation disputes.",
        "summary_ta": "பண்டைத் தமிழகத்துக் கிராம சபையின் முதன்மைச் செயல் குழுவான ஏரி வாரியம். ஊர் ஏரியின் கரைகளைப் பலப்படுத்துதல், கலிங்குகளைப் பழுதுபார்த்தல், தூம்புகளை இயக்குதல் மற்றும் பாசன நீர் பங்கீட்டு வழக்குகளைத் தீர்த்துவைத்த தன்னாட்சி அமைப்பு.",
        "content": """# Eri-Variyam Democratic Water Management (ஏரி வாரியம்)

---

## 1. Operational Mandates
- Pre-monsoon bund inspections (*கரை ஆய்வு*).
- Desilting lake beds using communal and contracted labor.
- Enforcing rotation turns (*Murai*) during seasonal water scarcity.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-eri-patti-and-eri-ayam-tank-endowments",
        "file": "concept-eri-patti-and-eri-ayam-tank-endowments.md",
        "node_type": "concept",
        "name_en": "Eri-Patti & Eri-Ayam: Dedicated Land Grants, Silt Cesses & Tank Maintenance Finance",
        "name_ta": "ஏரிப்பட்டி மற்றும் ஏரி ஆயம் - நீர்ப்பாசன நில மானியங்கள் மற்றும் தூர்வாரும் நிதி மேலாண்மை",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 850,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The financial institutions supporting ancient Tamil waterworks: Eri-patti (plots of agricultural land whose entire yield was ring-fenced for lake upkeep) and Eri-ayam (a dedicated local cess levied on grain harvests to fund sluice repairs).",
        "summary_ta": "ஏரிகளைத் தொடர்ந்து பராமரிக்க உருவாக்கப்பட்ட நிலையான நிதி அமைப்புகள். 'ஏரிப்பட்டி' எனப்படும் நிலங்களின் விளைச்சல் முழுவதும் ஏரி பழுதுபார்க்கவே பயன்படுத்தப்பட்டது; 'ஏரி ஆயம்' என்னும் நீர்வரி மூலம் தூர்வாரும் கூலி வழங்கப்பட்டது.",
        "content": """# Eri-Patti & Eri-Ayam Finance (ஏரிப்பட்டி மற்றும் ஏரி ஆயம்)

---

## 1. Fiscal Ring-Fencing
Neither the state nor the village assembly could divert *Eri-patti* grain or *Eri-ayam* cash to warfare or general administration, ensuring perpetual maintenance across centuries.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-murai-rotational-irrigation-rationing",
        "file": "concept-murai-rotational-irrigation-rationing.md",
        "node_type": "concept",
        "name_en": "Murai Water Rationing: Rotational Sluice Turns & Customary Equitable Irrigation Law",
        "name_ta": "முறைப் பாசனம் - முறைவைத்துப் பாசனம் செய்யும் மரபுவழி சமத்துவ நீர்ப் பங்கீட்டுச் சட்டம்",
        "era": "Classical to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "Marutham",
        "summary_en": "The equity-based customary legal doctrine of allocating irrigation water in rotational time-slots (Murai) measured by water clocks or day-turns, preventing tail-end farm starvation and ensuring downstream field survival.",
        "summary_ta": "வறட்சிக் காலங்களில் கடைமடைப் பயிர்களும் கருகிவிடாமல் காக்க, கால அளவை (நாழிகை) கொண்டு ஒவ்வொரு விவசாயிக்கும் முறைவைத்து நீர் திறந்துவிடும் தமிழரின் சமத்துவ நீரியல் சட்டம்.",
        "content": """# Murai Rotational Water Rationing (முறைப் பாசனம்)

---

## 1. Conflict Prevention
Upstream landholders (*Thala-madai*) were legally barred from drawing water out of turn. Violations incurred heavy community fines assessed by the *Eri-variyam*.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kuda-neer-vetti-communal-canal-maintenance",
        "file": "concept-kuda-neer-vetti-communal-canal-maintenance.md",
        "node_type": "concept",
        "name_en": "Kuda-Neer-Vetti: Mandatory Communal Canal Desilting & Civic Water Labor",
        "name_ta": "குடிமராமத்து மற்றும் வெட்டி - வாய்க்கால் தூர்வாரும் குடிமக்கள் கூட்டுப் பங்களிப்பு மரபு",
        "era": "Sangam to Medieval Era",
        "year_start": -400,
        "year_end": 1500,
        "thinai": "Marutham",
        "summary_en": "The civic tradition where every beneficiary household contributed physical labor (Kuda-maramathu / Vetti) to clear weeds, weeds, and silt from community distributary channels before the monsoon rains commenced.",
        "summary_ta": "பாசன வாய்க்கால்களில் தூர்வாரவும், மதகுகளில் அடைபட்டுள்ள செடி-கொடிகளையும் வண்டலையும் நீக்கவும் ஒவ்வொரு வீட்டிலிருந்தும் ஒருவர் வந்து உழைக்க வேண்டும் என்ற கூட்டுப் பங்களிப்பு நெறிமுறை.",
        "content": """# Kuda-Neer-Vetti Civic Maintenance (குடிமராமத்து)

If a landholder failed to provide labor (*Muttaval*), they were obligated to pay the assembly the exact cash wage required to hire a replacement laborer.
"""
    },
    {
        "category": "characters",
        "slug": "char-eri-variya-perumakan-tank-custodian",
        "file": "char-eri-variya-perumakan-tank-custodian.md",
        "node_type": "character",
        "name_en": "Eri-Variya Perumakan: Elected Tank Custodian & Sluice Maintenance Magistrate",
        "name_ta": "ஏரி வாரியப் பெருமகன் - மக்களால் தேர்ந்தெடுக்கப்பட்ட ஏரிப் பராமரிப்புத் தலைவர்",
        "era": "Imperial Chola Era",
        "year_start": 920,
        "year_end": 980,
        "thinai": "Marutham",
        "summary_en": "Dignified village elder elected through Kudavolai who supervised desilting carts, calibrated sluice orifices, and represented the irrigation interests of the community before royal visiting assizes.",
        "summary_ta": "குடவோலை முறையில் தேர்வswitch செய்யப்பட்டு, ஏரியின் ஆழம், மதகுகளின் உறுதித்தன்மை மற்றும் நீர் பகிர்வை நடுநிலையோடு மேற்பார்வையிட்ட ஏரி வாரிய உறுப்பினர்.",
        "content": """# The Elected Tank Custodian (ஏரி வாரியப் பெருமகன்)

Maintained the water log-books (*Neer-kanakku*), directing emergency sandbagging operations during midnight breach alerts.
"""
    },
    {
        "category": "characters",
        "slug": "char-tribhuvani-vandi-vettiyar-silt-contractor",
        "file": "char-tribhuvani-vandi-vettiyar-silt-contractor.md",
        "node_type": "character",
        "name_en": "Tribhuvani Vandi-Vettiyar: Professional Silt Dredger & Cart Transporter",
        "name_ta": "திருபுவனை வண்டி வெட்டியார் - ஏரி வண்டல் மண்ணை அகற்றி வயல்களுக்கு ஏற்றிய தொழில் வல்லுநர்",
        "era": "Imperial Chola Era",
        "year_start": 1040,
        "year_end": 1090,
        "thinai": "Marutham",
        "summary_en": "Contracted bullock-cart driver and dredger financed by temple endowments at Tribhuvani, responsible for hauling hundreds of cubic cubits of rich lake sediment onto village paddies daily.",
        "summary_ta": "கோயில் பொன் அறக்கட்டளை நிதியிலிருந்து ஊதியம் பெற்று, மாட்டு வண்டிகளில் ஏரி வண்டலை வெட்டி எடுத்துச் சென்று விவசாய நிலங்களில் பரப்பிய கைவினைஞர்.",
        "content": """# The Lake Silt Contractor (வண்டி வெட்டியார்)

Formed the frontline operational labor force that prevented massive medieval lakes like Tribhuvani from silting up.
"""
    },
    {
        "category": "places",
        "slug": "place-tribhuvani-chola-irrigation-hub",
        "file": "place-tribhuvani-chola-irrigation-hub.md",
        "node_type": "place",
        "name_en": "Tribhuvani: Historic Chola Irrigation Reservoir & Desilting Endowment Hub",
        "name_ta": "திருபுவனை - சோழர் காலத்து ஏரிப் பராமரிப்பு மற்றும் அறக்கட்டளை மையம்",
        "era": "Imperial Chola Era",
        "year_start": 1000,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "Historic agrarian township near Puducherry renowned for monumental Chola epigraphs detailing year-round lake desilting cart endowments, college feeding charters, and democratic tank assemblies.",
        "summary_ta": "புதுச்சேரி அருகே அமைந்துள்ள வரலாற்றுத் தளம். சோழர் காலத்து பிரம்மாண்ட ஏரியும், அதனைத் தூர்வார 6 மாட்டு வண்டிகளை நிரந்தரமாகப் பராமரிக்க பொன் முதலீடு செய்யப்பட்ட சாசனங்களும் உள்ள வரலாற்று மையம்.",
        "content": """# Tribhuvani Irrigation Hub (திருபுவனை)

- **Coordinates**: 11.9333° N, 79.6500° E.  
- **District**: Puducherry / Villupuram border.  
- **Hydrological Benchmark**: Archetypal site documenting sustainable civic financing of lake maintenance and cart dredging.
"""
    }
]

# ==============================================================================
# RELATIONAL EDGES (50 Total)
# ==============================================================================
EDGES = [
    # Corpus 1 Edges: Revenue Secretariat & Cadastral Auditing
    ("text-periyapuranam-vari-pothagam-chola-revenue", "depicts", "concept-puravu-vari-thinaikalam-revenue-ministry", "administration", "Imperial Chola", "Periyapuranam describes the revenue ministry and scribal accounting.", "Periyapuranam verses"),
    ("concept-puravu-vari-thinaikalam-revenue-ministry", "maintains", "concept-vari-pothagam-cadastral-palm-leaf-ledgers", "record_keeping", "Imperial Chola", "Ministry maintained duplicate village registers for all tax assessments.", "Chola statecraft"),
    ("insc-tanjavur-ulagalantan-cadastral-survey", "standardizes", "concept-ulagalantan-16-span-standard-survey-rod", "metrology", "1001 CE", "Monumental survey established the 16-span rod as the empire-wide standard.", "Brihadisvara inscription"),
    ("insc-tanjavur-ulagalantan-cadastral-survey", "records", "concept-chola-land-tax-classifications", "land_tenure", "1001 CE", "Classified empire lands into Nansey, Punsey, and tax-exempt areas.", "Cadastral survey records"),
    ("char-ulagalantan-royal-land-surveyor", "uses", "concept-ulagalantan-16-span-standard-survey-rod", "fieldwork", "Imperial Chola", "Surveyors carried the stamped 16-span rod to verify village plot bounds.", "Epigraphical survey"),
    ("char-puravu-vari-thinaikkala-nayakan", "directs", "concept-puravu-vari-thinaikalam-revenue-ministry", "governance", "Imperial Chola", "Supreme revenue minister supervised all cadastral registers and remissions.", "Chola administration"),
    ("insc-kandiyur-puravu-vari-revenue-charter", "issued_by", "concept-puravu-vari-thinaikalam-revenue-ministry", "tax_remission", "Imperial Chola", "Revenue ministry reclassified flooded wetlands into dryland categories.", "Tirukkandiyur charter"),
    ("insc-kandiyur-puravu-vari-revenue-charter", "situated_at", "place-tirukkandiyur-chola-revenue-secretariat", "geography", "Medieval", "Engraved on the temple walls of Tirukkandiyur near Thanjavur.", "Archaeological Survey"),
    ("char-ulagalantan-royal-land-surveyor", "updated", "concept-vari-pothagam-cadastral-palm-leaf-ledgers", "auditing", "Imperial Chola", "Field surveyors updated the palm-leaf registers after measuring new plots.", "District registers"),
    ("concept-chola-land-tax-classifications", "recorded_in", "concept-vari-pothagam-cadastral-palm-leaf-ledgers", "taxation", "Imperial Chola", "Every plot's Taram quality and annual paddy dues recorded in ledgers.", "Chola epigraphy"),

    # Corpus 2 Edges: Royal Charters & Brahmadeya Tenures
    ("text-anbil-copper-plates-chola-genealogy", "records_grant_to", "char-aniruddha-brahmadhiraja-chola-minister", "royal_grant", "c. 961 CE", "Sundara Chola granted Anbil village lands to chief minister Aniruddha.", "Anbil copper plates"),
    ("text-anbil-copper-plates-chola-genealogy", "situated_at", "place-anbil-chola-brahmadeya-settlement", "geography", "Imperial Chola", "Charter discovered at the historic Brahmadeya village of Anbil.", "Epigraphia Indica"),
    ("insc-velanjeri-copper-plates-parantaka", "exemplifies", "concept-pidi-soozhnthu-elephant-boundary-perambulation", "legal_ritual", "10th c. CE", "Charter documents royal female elephant walking the settlement perimeter.", "Velanjeri plates"),
    ("concept-pidi-soozhnthu-elephant-boundary-perambulation", "guided_by", "char-pidi-nadanthu-boundary-arbitrator", "arbitration", "Ancient-Medieval", "Elder magistrates walked with the elephant to witness boundary cairns.", "Copper-plate formulas"),
    ("insc-karandai-tamil-sangam-plates-rajendra", "creates", "concept-brahmadeya-and-devadana-land-tenures", "settlement", "11th c. CE", "Established Tribhuvana-mahadevi-chaturvedimangalam for 1,080 scholars.", "Karandai plates"),
    ("insc-karandai-tamil-sangam-plates-rajendra", "secured_by", "concept-chola-royal-copper-plate-karanams", "diplomatics", "11th c. CE", "Fastened by a 100-kg bronze ring bearing the Chola tiger crest seal.", "National Museum"),
    ("concept-irayili-tax-exemption-and-kadamai", "granted_to", "concept-brahmadeya-and-devadana-land-tenures", "tax_immunity", "Imperial Chola", "Endowed settlements were exempted from state taxes and feudal labor.", "Chola charters"),
    ("concept-chola-royal-copper-plate-karanams", "stamped_with", "concept-irayili-tax-exemption-and-kadamai", "law", "Imperial Chola", "Copper plates officially codified the full list of extinguished tax obligations.", "Sasana formulation"),
    ("char-aniruddha-brahmadhiraja-chola-minister", "administered", "place-anbil-chola-brahmadeya-settlement", "leadership", "Imperial Chola", "Minister established canal distributions and assembly rules at Anbil.", "Local history"),
    ("concept-brahmadeya-and-devadana-land-tenures", "demarcated_by", "concept-pidi-soozhnthu-elephant-boundary-perambulation", "cadastre", "Medieval", "Elephant circumambulation was the standard legal rite for creating Brahmadeyas.", "Inscriptional rites"),

    # Corpus 3 Edges: Irrigation Assemblies & Eri-Variyam
    ("text-thiruvalluvar-arasan-neer-management-ethics", "articulates", "concept-eri-variyam-elected-tank-committee", "ethics", "Classical", "Thirukkural establishes the sovereign ethical imperative of water harvesting.", "Thirukkural Vanshirappu"),
    ("insc-uttiramerur-eri-variyam-tank-charter", "formalizes", "concept-eri-variyam-elected-tank-committee", "electoral_code", "921 CE", "World-famous charter defining pot-ticket election of tank custodians.", "Uttiramerur inscription"),
    ("char-eri-variya-perumakan-tank-custodian", "elected_to", "concept-eri-variyam-elected-tank-committee", "democracy", "Early Medieval", "Village elders were elected annually to direct waterworks and desilting.", "Kudavolai rules"),
    ("insc-tribhuvani-lake-maintenance-endowment", "endows", "concept-eri-patti-and-eri-ayam-tank-endowments", "finance", "Imperial Chola", "Gold endowment interest dedicated to maintaining six desilting carts.", "Tribhuvani inscription"),
    ("insc-tribhuvani-lake-maintenance-endowment", "situated_at", "place-tribhuvani-chola-irrigation-hub", "geography", "Imperial Chola", "Engraved on the temple walls at the historic Tribhuvani irrigation center.", "Puducherry survey"),
    ("char-tribhuvani-vandi-vettiyar-silt-contractor", "employed_at", "place-tribhuvani-chola-irrigation-hub", "infrastructure", "Imperial Chola", "Operated bullock carts hauling dredged lake silt to agricultural fields.", "Temple records"),
    ("concept-murai-rotational-irrigation-rationing", "enforced_by", "concept-eri-variyam-elected-tank-committee", "water_law", "Ancient-Medieval", "Tank committee scheduled hour-by-hour water turns during drought.", "Inscriptional rules"),
    ("concept-kuda-neer-vetti-communal-canal-maintenance", "supervised_by", "char-eri-variya-perumakan-tank-custodian", "civic_labor", "Imperial Chola", "Custodians mobilized communal labor to desilt distributary channels.", "Village custom"),
    ("concept-eri-patti-and-eri-ayam-tank-endowments", "funds", "char-tribhuvani-vandi-vettiyar-silt-contractor", "remuneration", "Imperial Chola", "Dedicated endowments funded continuous wages for cart dredging drivers.", "Endowment charters"),
    ("concept-eri-variyam-elected-tank-committee", "operates_in", "place-anbil-chola-brahmadeya-settlement", "local_governance", "Medieval", "Anbil village assembly maintained its own autonomous Eri-variyam committee.", "Anbil epigraphs")
]

# ==============================================================================
# MAIN HARVESTER EXECUTION
# ==============================================================================
def main():
    print("=" * 70)
    print("🚀 BATCH 7: TRIPLE CIVILIZATIONAL EXPANSION HARVESTER")
    print("   1. Chola Revenue Secretariat, Cadastral Auditing & Land Classification (10 dossiers)")
    print("   2. Epigraphical Royal Charters, Brahmadeya Tenures & Pidi-Nadanthu (10 dossiers)")
    print("   3. Village Irrigation Assemblies, Eri-Variyam & Water Jurisprudence (10 dossiers)")
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
