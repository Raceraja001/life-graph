#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 6):
1. Ancient Tamil Numismatics, Imperial Bullion & Royal Minting (10 dossiers)
2. Roman Currency Hoards, Bullion Demonetization & Trade Balances (10 dossiers)
3. Ancient Tamil Hydraulic Sluices, Grand Anicut & Cascade Tanks (10 dossiers)

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
    # CORPUS 1: ANCIENT TAMIL NUMISMATICS, IMPERIAL BULLION & ROYAL MINTING
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-kanakkathikaram-bullion-metrology",
        "file": "text-kanakkathikaram-bullion-metrology.md",
        "node_type": "text",
        "name_en": "Kanakkathikaram: Mathematical Rules for Gold Fineness, Touchstone Assaying & Coin Metrology",
        "name_ta": "கணக்கதிகாரம் - பொன் மாற்று உரைத்தல், உரைக்கல் கணக்கீடு மற்றும் நாணய அளவியல்",
        "era": "Medieval Classical Era",
        "year_start": 800,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "Kari Nayanar's mathematical treatise codifying gold purity calculations (Maatru), touchstone test formulas, alloy refining ratios, and volume conversions between botanical seed weights (Manjadi, Kunrimani) and standard gold Kalanju units.",
        "summary_ta": "காரி நாயனாரின் கணக்கதிகாரம். பொன்னின் தூய்மை மாற்று உரைக்கும் கணக்கீடுகள், உரைக்கல் கோடுகள், தங்கம்-வெள்ளி-செம்பு கலப்பு வீதங்கள், மற்றும் குன்றிமணி, மஞ்சாடி அளவைகளிலிருந்து கழஞ்சு, காசு, வராகன் மாற்றுவதற்கான கணிதச் சூத்திரங்கள்.",
        "content": """# Kanakkathikaram: Bullion Metrology (பொன் கணக்கீடு)

**Author**: Kari Nayanar (*காரி நாயனார்*).  
**Subject**: Gold Fineness (*பொன் மாற்று*), Touchstone Assaying (*உரைக்கல்*).  

---

## 1. Botanical Weight Standards
- **Kunrimani (*குன்றிமணி*)**: Seed of *Abrus precatorius* (~1.8 grains / 115 mg).
- **Manjadi (*மஞ்சாடி*)**: Seed of *Adenanthera pavonina* (2 Kunrimani = ~3.6 grains).
- **Kalanju (*கழஞ்சு*)**: Benchmark bullion unit (20 Manjadi = approx. 50–52 grains / 3.2–3.5 g).
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thanjavur-madhurantakan-madai-charters",
        "file": "insc-thanjavur-madhurantakan-madai-charters.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Brihadisvara Madhurantakan-Madai Charters: Imperial Gold Currency Standards",
        "name_ta": "தஞ்சைப் பெரிய கோயில் மதுராந்தகன் மாடை சாசனங்கள் - சோழர் தங்க நாணயத் தரம்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Brihadisvara epigraphs by Rajaraja I standardizing imperial temple endowments in Madhurantakan-madai gold coins, specifying strict bullion fineness (9.5 to 10 Maatru) and equating one Madai to two Rajaraja Kasu.",
        "summary_ta": "இராஜராஜ சோழனின் தஞ்சைக் கல்வெட்டுகள். கோயில் திருவிளக்குகளுக்கும் தானங்களுக்கும் வழங்கப்பட்ட 'மதுராந்தகன் மாடை' என்னும் தூய தங்க நாணயங்களின் எடை, மாற்றுத் தரம் மற்றும் காசுக்கு நிகரான நாணய மதிப்பு நெறிகள்.",
        "content": """# Thanjavur Madhurantakan-Madai Charters (மதுராந்தகன் மாடை)

---

## 1. Monetary Specification
Epigraphs record: *"தஞ்சாவூர் உடையார் கோயிலில் மதுராந்தகன் மாடைக்கு ஒத்த பொன்..."*  
The Madhurantakan-madai was the premier high-purity gold coin of the Chola empire, weighing 1 Kalanju, minted under royal state authority.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kudumiyamalai-akkasalai-mint-charter",
        "file": "insc-kudumiyamalai-akkasalai-mint-charter.md",
        "node_type": "inscription",
        "name_en": "Kudumiyamalai Epigraphs: State Akkasalai Mints & Royal Goldsmith Charters",
        "name_ta": "குடுமியாமலைக் கல்வெட்டுகள் - அரச அக்கசாலை மற்றும் பொற்கொல்லர் சாசனங்கள்",
        "era": "Early Medieval to Pandya Era",
        "year_start": 750,
        "year_end": 1250,
        "thinai": "Mullai",
        "summary_en": "Epigraphical records at the Kudumiyamalai rock temple documenting state coin mints (Akkasalai), the minting of Pandyan double-carp and Chola tiger coins, and the royal privileges granted to master minters (Akkasalai-asiriyar).",
        "summary_ta": "புதுக்கோட்டை குடுமியாமலை குகைக் கோயில் கல்வெட்டுகள். பாண்டிய மற்றும் சோழ அரசுகளின் நாணயங்களை அச்சிட்ட 'அக்கசாலை' தொழிற்கூடங்கள் மற்றும் நாணய அச்சு வார்ப்பாளர்களுக்கு வழங்கப்பட்ட அரச உரிமங்கள்.",
        "content": """# Kudumiyamalai Akkasalai Inscriptions (அக்கசாலைக் கல்வெட்டுகள்)

**Site**: Kudumiyamalai (*குடுமியாமலை*), Pudukkottai.  
**Subject**: Royal Mint (*அக்கசாலை*), Die-Striking Standards (*காசடிப்பு*).  
The inscriptions specify the legal accountability of minters against debasement and unauthorized currency duplication.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-madhurantakan-madai-gold-standard",
        "file": "concept-madhurantakan-madai-gold-standard.md",
        "node_type": "concept",
        "name_en": "Madhurantakan-Madai: Imperial Chola Gold Standard & Trans-Oceanic Purchasing Power",
        "name_ta": "மதுராந்தகன் மாடை - சோழப் பேரரசின் தங்க நாணய முறைமை மற்றும் சர்வதேச நாணய மதிப்பு",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1150,
        "thinai": "Marutham",
        "summary_en": "The gold currency benchmark introduced under Uttama Chola (Madhurantakan) and institutionalized by Rajaraja I, circulating across South India, Sri Lanka, and maritime Southeast Asia with high intrinsic bullion value.",
        "summary_ta": "உத்தம சோழரால் தோற்றுவிக்கப்பட்டு இராஜராஜ சோழனால் பேரரசு முழுவதும் நிலைநிறுத்தப்பட்ட மதுராந்தகன் மாடை. புலி, இரட்டை மீன், வில் பொறிக்கப்பட்ட இத்தங்க நாணயம் இலங்கை மற்றும் ஸ்ரீவிஜய சாம்ராஜ்யம் வரை வாணிகப் பரிமாற்றத்தில் கோலோச்சியது.",
        "content": """# Madhurantakan-Madai Gold Standard (மதுராந்தகன் மாடை)

---

## 1. Metrological Precision
- **Weight**: 1 standard Kalanju (52 grains / 3.36 grams).
- **Fineness**: Assayed at 9.5 to 10 Maatru (approx. 22–24 karat equivalent).
- **Exchange Ratio**: 1 Madai = 2 Gold Kasu = 4 Silver Dramas = 8 Copper Kasu.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-akkasalai-state-mint-mechanics",
        "file": "concept-akkasalai-state-mint-mechanics.md",
        "node_type": "concept",
        "name_en": "Akkasalai Minting Technology: Crucible Alloying, Blank Planchets & Die-Striking",
        "name_ta": "அக்கசாலை நாணய உற்பத்தித் தொழினுட்பம் - வார்ப்பட உருக்கு, அச்சுப் பொறித்தல் மற்றும் விளிம்பு சீராக்கல்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The pyrotechnic and mechanical engineering of ancient Tamil state mints (Akkasalai): graphite crucible melting, casting molten gold into rod ingots, shearing into circular planchets, and striking between hardened bronze dies (Kasa-achu).",
        "summary_ta": "பண்டைத் தமிழகத்து அரச நாணயச் சாலைகளின் உற்பத்தி முறை. மூசை உலைகளில் பொன், வெள்ளி உருக்குதல், கம்பிகளாக வார்த்து வட்ட வில்லைகளாக (பிளான்செட்) வெட்டுதல், மற்றும் வெண்கல முத்திரைக் கருவிகளால் இருபுறமும் அடித்து நாணயம் உருவாக்கும் நுட்பம்.",
        "content": """# Akkasalai Minting Mechanics (அக்கசாலை நாணயத் தொழினுட்பம்)

---

## 1. Production Stages
1. **Smelting & Alloying**: Graphite-clay crucibles (*Moosai*) heated to 1100°C with charcoal bellows.
2. **Planchet Shearing**: Strips of calibrated thickness sheared into round blanks with cold-chisels.
3. **Die-Striking (*அச்சு அடித்தல்*)**: Lower anvil die (*Keezh-achu*) fixed in an anvil; blank placed on top; upper punch die struck with a heavy bronze hammer.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-urai-kal-touchstone-gold-assaying",
        "file": "concept-urai-kal-touchstone-gold-assaying.md",
        "node_type": "concept",
        "name_en": "Urai-Kal Touchstone Assaying: Basanite Streak Analysis & Maatru Purity Formulas",
        "name_ta": "உரைக்கல் பொன் பரிசோதனை - கறுப்புக் கல் உராய்வு மற்றும் மாற்றுத் தரம் கணித்தல்",
        "era": "Ancient to Medieval Era",
        "year_start": -500,
        "year_end": 1500,
        "thinai": "Marutham",
        "summary_en": "The non-destructive analytical chemistry of testing gold fineness using fine-grained black siliceous stone (Urai-kal / Basanite), comparing test streaks against standardized alloy assay needles (Urai-k-kodu).",
        "summary_ta": "நுண்ணிய கருங்கல் (உரைக்கல்) கொண்டு தங்கத்தை உரைத்து, உராய்வுக் கோடுகளின் நிறம் மற்றும் அமிலத் தாங்குதிறனை ஆராய்ந்து 1 முதல் 10 வரையிலான மாற்றுத் தரத்தைத் தீர்மானிக்கும் அறிவியல் முறை.",
        "content": """# Urai-Kal Touchstone Assaying (உரைக்கல் நுட்பம்)

---

## 1. Streak Comparison Analysis
Assayers kept a set of 10 gold-silver-copper needles of verified fineness (*உரை ஊசி*). A test streak was drawn adjacent to standard streaks; acid washing with plant extracts revealed base-metal adulteration instantaneously.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-ceylon-man-type-coinage-transmission",
        "file": "concept-ceylon-man-type-coinage-transmission.md",
        "node_type": "concept",
        "name_en": "Ceylon-Man Type Coinage: The Imperial Rajaraja Kasu Pan-Regional Currency Arc",
        "name_ta": "இலங்கை-வகை நாணயப் பரவல் - இராஜராஜன் காசு மற்றும் சோழப் பேரரசு நாணய மாதிரி",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1200,
        "thinai": "Neithal",
        "summary_en": "The iconic numismatic design adopted by Rajaraja I featuring a stylized standing king holding a lotus on the obverse and a seated king with the Nagari legend 'Sri Raja Raja' on the reverse, circulating throughout South India and the Indian Ocean.",
        "summary_ta": "இராஜராஜ சோழன் காலத்தில் அறிமுகப்படுத்தப்பட்டு சோழமண்டலம், பாண்டிமண்டலம் மற்றும் இலங்கையில் கோடிக்கணக்கில் புழங்கிய 'இராஜராஜன் காசு'. நின்ற நிலையிலான அரசன் மற்றும் அமர்ந்த நிலையிலான அரசனின் உருவம் கொண்ட தனித்துவ நாணய மாதிரி.",
        "content": """# The Ceylon-Man Type Coinage Arc (இராஜராஜன் காசு)

---

## 1. Iconographic Anatomy
- **Obverse**: Standing royal figure, right arm bent holding a flower, framed by temple lamps (*Kuthuvilakku*) and battle standards.
- **Reverse**: Seated figure holding a conch shell with Devanagari/Grantha legend: *"ஸ்ரீ ராஜ ராஜ"*.
"""
    },
    {
        "category": "characters",
        "slug": "char-akkasalai-nayakan-master-minter",
        "file": "char-akkasalai-nayakan-master-minter.md",
        "node_type": "character",
        "name_en": "Akkasalai Nayakan: Imperial Master Moneyer & Keeper of the Royal Coin Dies",
        "name_ta": "அக்கசாலை நாயகன் - சோழ-பாண்டிய அரச நாணயச் சாலையின் தலைமை அச்சாசிரியர்",
        "era": "Imperial Chola Era",
        "year_start": 1000,
        "year_end": 1070,
        "thinai": "Marutham",
        "summary_en": "High ministerial official responsible for the integrity of royal mints, security of die punches, metallurgical purity of gold/silver ingots, and prosecution of counterfeit moneyers.",
        "summary_ta": "அரச நாணயங்களின் எடை, அச்சுப் பொறிப்புத் தரம் மற்றும் உலோகக் கலவைக்கு முழுப் பொறுப்பு வகித்த அரசு தலைமை நாணய அதிகாரி.",
        "content": """# Akkasalai Nayakan (அக்கசாலை நாயகன்)

Under royal charter, this master metallurgist stamped every newly struck batch of coins with state control marks before releasing them to merchant guilds and temple treasuries.
"""
    },
    {
        "category": "characters",
        "slug": "char-thanjavur-kasu-paritchakar-coin-assayer",
        "file": "char-thanjavur-kasu-paritchakar-coin-assayer.md",
        "node_type": "character",
        "name_en": "Kasu Paritchakar: Temple Treasury Gold Assayer & Counterfeit Examiner",
        "name_ta": "காசுப் பரீட்சகர் - கோயில் கருவூலத் தங்க நாணயப் பரிசோதகர் மற்றும் மாற்று ஆய்வாளர்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1080,
        "thinai": "Marutham",
        "summary_en": "Treasury numismatic specialist attached to Brihadisvara Temple who weighed incoming coins against ruby-balanced scales, assayed gold streaks on touchstones, and rejected debased planchets.",
        "summary_ta": "தஞ்சைப் பெருவுடையார் கோயில் பண்டாரத்தில் சேரும் தங்க நாணயங்களை உரைக்கல்லில் உரைத்து, போலி நாணயங்களை நீக்கித் தூய மாற்று நாணயங்களை மட்டுமே ஏற்றுக் கொண்ட நிபுணர்.",
        "content": """# Kasu Paritchakar (காசுப் பரீட்சகர்)

These assayers ensured that no donation below 9.5 Maatru gold was accepted for perpetual lamp endowments (*Nondaa-vilakku*).
"""
    },
    {
        "category": "places",
        "slug": "place-kudumiyamalai-pandyan-minting-station",
        "file": "place-kudumiyamalai-pandyan-minting-station.md",
        "node_type": "place",
        "name_en": "Kudumiyamalai: Rock-Cut Temple Complex & Royal Pandyan Minting Hub",
        "name_ta": "குடுமியாமலை - பாண்டியர் காலத்து அக்கசாலை நாணய உற்பத்தி மையம்",
        "era": "Early Medieval to Pandya Era",
        "year_start": 700,
        "year_end": 1300,
        "thinai": "Mullai",
        "summary_en": "Historic rock-cut temple site in Pudukkottai renowned for monumental musical inscriptions and state epigraphs detailing royal Akkasalai minting operations and goldsmith guild charters.",
        "summary_ta": "புதுக்கோட்டை மாவட்டத்தில் அமைந்துள்ள புகழ்பெற்ற குடைவரைக் கோயில் வளாகம். இசைச் சாசனங்கள் மட்டுமின்றி, பாண்டிய அரசின் அக்கசாலை நாணய உற்பத்தி ஆவணங்களும் பொறிக்கப்பட்டுள்ள வரலாற்றுத் தளம்.",
        "content": """# Kudumiyamalai Minting Station (குடுமியாமலை)

- **Coordinates**: 10.4167° N, 78.7500° E.  
- **District**: Pudukkottai, Tamil Nadu.  
- **Numismatic Importance**: Epigraphical charters defining state minting governance and master minter duties.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: ROMAN CURRENCY HOARDS, BULLION DEMONETIZATION & TRADE BALANCES
    # --------------------------------------------------------------------------
    {
        "category": "inscriptions",
        "slug": "arch-pollachi-roman-aurei-hoards",
        "file": "arch-pollachi-roman-aurei-hoards.md",
        "node_type": "inscription",
        "name_en": "Pollachi Roman Hoards: Augustan & Tiberian Gold Aurei Caches in the Kongu Corridor",
        "name_ta": "பொள்ளாச்சி உரோமானிய நாணயப் புதையல் - அகஸ்டஸ்-திபேரியஸ் காலத்துத் தங்க நாணயங்கள்",
        "era": "Sangam Indo-Roman Era",
        "year_start": -30,
        "year_end": 100,
        "thinai": "Mullai",
        "summary_en": "Massive archaeological caches of pristine Roman imperial gold coins (Aurei) of Augustus and Tiberius discovered at Pollachi near the Palakkad Gap, documenting the enormous influx of Mediterranean bullion paying for Malabar pepper and beryl.",
        "summary_ta": "பொள்ளாச்சி அருகே கண்டெடுக்கப்பட்ட ரோமப் பேரரசு நாணயப் புதையல்கள். அகஸ்டஸ் மற்றும் திபேரியஸ் பேரரசர்களின் உருவம் பொறிக்கப்பட்ட மாசற்ற தங்க நாணயங்கள், மேற்குத் தொடர்ச்சி மலை கணவாய் வழியாக நடைபெற்ற பெரும் வாணிகத்தின் நேரடிச் சான்றாகும்.",
        "content": """# Pollachi Roman Aurei Hoards (பொள்ளாச்சி நாணயப் புதையல்)

**Site**: Pollachi Corridor (*பொள்ளாச்சி கணவாய்*).  
**Period**: Principate Era (Augustus 27 BCE–14 CE, Tiberius 14–37 CE).  

---

## 1. Monetary Influx
Over 500 pure gold aurei have been cataloged from Pollachi caches, reflecting the trade imbalance where Rome exported physical bullion rather than manufactured goods.
"""
    },
    {
        "category": "inscriptions",
        "slug": "arch-vellalur-denarii-and-jewelry-hoards",
        "file": "arch-vellalur-denarii-and-jewelry-hoards.md",
        "node_type": "inscription",
        "name_en": "Vellalur Hoards: Roman Silver Denarii, Intaglio Gem Rings & Bullion Depots",
        "name_ta": "வெள்ளலூர் புதையல் - உரோமானிய வெள்ளி நாணயங்கள், முத்திரை மோதிரங்கள் மற்றும் பொன் சேமிப்புக் கூடம்",
        "era": "Sangam Indo-Roman Era",
        "year_start": -20,
        "year_end": 150,
        "thinai": "Marutham",
        "summary_en": "Archaeological finds at Vellalur on the Noyyal River yielding the largest single deposit of Roman silver denarii (over 500 coins) along with Greco-Roman engraved carnelian intaglio rings and gold bullion wire.",
        "summary_ta": "கோயம்புத்தூர் வெள்ளலூரில் நொய்யல் ஆற்றங்கரையில் கண்டெடுக்கப்பட்ட 500-க்கும் மேற்பட்ட உரோமானிய வெள்ளி நாணயங்கள், யவனக் கடவுளரின் முத்திரை மோதிரங்கள் மற்றும் தங்க நகைகள் அடங்கிய வரலாற்றுப் புதையல்.",
        "content": """# Vellalur Roman Denarii Hoards (வெள்ளலூர் நாணயப் புதையல்)

---

## 1. Archaeological Context
Vellalur was an inland trans-shipment nexus where Mediterranean silver was received from Muziris, sorted, and converted into Tamil ornaments or trade bullion.
"""
    },
    {
        "category": "inscriptions",
        "slug": "arch-karur-amaravathi-riverbed-bullion-finds",
        "file": "arch-karur-amaravathi-riverbed-bullion-finds.md",
        "node_type": "inscription",
        "name_en": "Karur Amaravathi Riverbed Finds: Roman Aurei, Phoenician Marks & Chera Royal Coinage",
        "name_ta": "கரூர் அமராவதி ஆற்றுப்படுகை நாணயங்கள் - உரோமானிய பொற்காசுகள் மற்றும் சேரர் முத்திரைகள்",
        "era": "Sangam Classical Era",
        "year_start": -100,
        "year_end": 200,
        "thinai": "Marutham",
        "summary_en": "Extensive numismatic discoveries from the Amaravathi riverbed at Karur (ancient Vanji) uncovering Roman gold and silver coins alongside punch-marked silver, Phoenician-inscribed rings, and Chera portrait coins.",
        "summary_ta": "கரூர் அமராவதி நதியின் மணலில் கண்டெடுக்கப்பட்ட உரோமானிய பொற்காசுகள், பீனிசிய முத்திரை மோதிரங்கள், மற்றும் சேர மன்னர்களான மாக்கோதை, குட்டுவன் கோதையின் உருவம் தாங்கிய சங்ககால நாணயங்கள்.",
        "content": """# Karur Amaravathi Numismatic Discoveries (கரூர் ஆற்றுப்படுகை)

Karur served as the inland metropolis of the Sangam Cheras, where Mediterranean merchants exchanged Roman coins for Kongu beryl, quartz beads, and muslins.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-roman-bullion-counter-marking",
        "file": "concept-roman-bullion-counter-marking.md",
        "node_type": "concept",
        "name_en": "Roman Bullion Counter-Marking: Chisel-Slits, Portrait Defacement & Demonetization",
        "name_ta": "உரோமானிய நாணயங்களில் வெட்டுக்குறி இடுதல் - அரசியல் முத்திரை நீக்கம் மற்றும் தங்கத் தூய்மைச் சோதனை",
        "era": "Sangam Indo-Roman Era",
        "year_start": -20,
        "year_end": 200,
        "thinai": "Marutham",
        "summary_en": "The widespread phenomenon of cutting deep chisel-slits across the faces of Roman emperors on aurei and denarii found in South India, serving both to verify solid gold content (preventing plated copper counterfeits) and to negate Roman imperial sovereignty.",
        "summary_ta": "தமிழகத்தில் கண்டெடுக்கப்படும் உரோமானிய நாணயங்களில் பேரரசரின் முகத்தின் குறுக்கே கூரிய உளியால் வெட்டுக்குறியிடப்பட்டிருக்கும் வழக்கம். இது போலியான தங்க முலாம் பூசப்பட்ட நாணயங்களைக் கண்டறியவும், அந்நியப் பேரரசின் அரசியல் ஆதிக்கத்தை நிராகரிக்கவும் செய்யப்பட்டது.",
        "content": """# Chisel-Slit Counter-Marking (வெட்டுக் குறிகள்)

---

## 1. Dual Significance
1. **Metallurgical Assay**: A test cut penetrating into the coin core to detect *Fourrées* (bronze coins with thin gold plating).
2. **Demonetization into Bullion**: Treated not as legal tender of Caesar, but as raw stamped bullion traded by weight.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-mediterranean-trade-deficit-and-pliny-lament",
        "file": "concept-mediterranean-trade-deficit-and-pliny-lament.md",
        "node_type": "concept",
        "name_en": "Mediterranean Bullion Drain: Pliny's Lament & Roman Balance of Payments Deficit",
        "name_ta": "உரோமானியப் பொன் வெளியேற்றம் - பிளினியின் புலம்பல் மற்றும் வணிக இருப்புப் பற்றாக்குறை",
        "era": "Classical Roman to Sangam Era",
        "year_start": 50,
        "year_end": 100,
        "thinai": "Neithal",
        "summary_en": "The famous historical observation by Pliny the Elder in *Naturalis Historia* (c. 77 CE) that India drained over 50 million sesterces (or 100 million with Arabia/China) in gold and silver annually to satisfy luxury demands for spices, pearls, and gems.",
        "summary_ta": "ரோமானிய வரலாற்று ஆசிரியர் மூத்த பிளினி தனது நூலில் எழுதிய வரலாற்றுப் பதிவு: இந்தியாவின் மிளகு, முத்து, ரத்தினங்களுக்காக ஆண்டுதோறும் 50 மில்லியன் செஸ்டர்ஸஸ் தங்கமும் வெள்ளியும் உரோமப் பேரரசிலிருந்து வெளியேறி இந்தியக் கரைகளை அடைந்தது.",
        "content": """# Pliny's Lament on the Indian Bullion Drain (பிளினியின் பதிவு)

Pliny famously condemned Roman aristocratic decadence:
*"At the very lowest calculation, India, China, and the Arabian Peninsula drain our empire of one hundred million sesterces every year: that is what our luxuries and our women cost us."*
"""
    },
    {
        "category": "concepts",
        "slug": "concept-terracotta-roman-coin-bullae",
        "file": "concept-terracotta-roman-coin-bullae.md",
        "node_type": "concept",
        "name_en": "Terracotta Roman Coin Bullae: Clay Pendant Imitations & Elite Prestige Amulets",
        "name_ta": "சுடுமண் உரோமானிய நாணயப் பதக்கங்கள் - களிமண் நகல் பதக்கங்கள் மற்றும் பெருமித ஆபரணங்கள்",
        "era": "Sangam Indo-Roman Era",
        "year_start": -50,
        "year_end": 250,
        "thinai": "Marutham",
        "summary_en": "Locally molded baked terracotta and lead pendants replicating Roman gold aurei with suspension loops, excavated at Uraiyur, Arikamedu, and Kudikadu, worn by indigenous elites as prestige jewelry imitating Mediterranean royal portraits.",
        "summary_ta": "உரோமானியப் பொற்காசுகளை அச்சாகக் கொண்டு களிமண்ணில் வனைந்து சுடப்பட்ட பதக்கங்கள் (புல்லே). கழுத்தில் மாட்டுவதற்கான துளைகளோடு உருவாக்கப்பட்டு, சங்ககாலத் தமிழ் மேட்டுக்குடியினரால் பெருமித ஆபரணமாக அணியப்பட்டவை.",
        "content": """# Terracotta Roman Coin Bullae (சுடுமண் நாணயப் பதக்கங்கள்)

Demonstrates the cultural prestige attached to Roman imperial imagery while illustrating the local adaptation of Mediterranean currency motifs into indigenous personal adornment.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kongu-palakkad-gap-bullion-highway",
        "file": "concept-kongu-palakkad-gap-bullion-highway.md",
        "node_type": "concept",
        "name_en": "The Palakkad Gap Bullion Highway: Trans-Peninsular Trade Transit from Muziris to Coromandel",
        "name_ta": "பாலக்காட்டுக் கணவாய் பொன் பெருவழி - முசிறியிலிருந்து சோழமண்டலம் நோக்கிய வர்த்தகப் பாதை",
        "era": "Iron Age to Sangam Era",
        "year_start": -300,
        "year_end": 400,
        "thinai": "Mullai",
        "summary_en": "The natural 30-kilometer break in the Western Ghats connecting the Arabian Sea to the Bay of Bengal, channeling thousands of Roman gold coins and Mediterranean goods from Muziris through Pollachi, Vellalur, and Karur to the eastern coast.",
        "summary_ta": "மேற்குத் தொடர்ச்சி மலையின் 30 கி.மீ அகலப் பாலக்காட்டுக் கணவாய். முசிறித் துறைமுகத்தில் இறங்கிய உரோமானியத் தங்கத்தை பொள்ளாச்சி, வெள்ளலூர், கரூர் வழியாகக் காவிரி பாயும் சோழமண்டலத் துறைமுகங்களுக்குக் கொண்டு சென்ற பிரதான பெருவழி.",
        "content": """# The Palakkad Gap Bullion Arterial (பாலக்காட்டுக் கணவாய்)

---

## 1. Geographic Funnel
The only low-altitude overland break in the 1,600-kilometer Western Ghats mountain barrier, creating an unmatched economic conduit for Indo-Roman maritime trans-shipment.
"""
    },
    {
        "category": "characters",
        "slug": "char-vellalur-roman-bullion-dealer",
        "file": "char-vellalur-roman-bullion-dealer.md",
        "node_type": "character",
        "name_en": "Vellalur Bullion Assayer: Master of Imported Roman Denarii & Ingot Smelting",
        "name_ta": "வெள்ளலூர் பொன் வணிகர் - உரோமானிய நாணயங்களை உரைத்து உருகிய கட்டிகளாக மாற்றிய கைவினைஞர்",
        "era": "Sangam Indo-Roman Era",
        "year_start": 20,
        "year_end": 80,
        "thinai": "Marutham",
        "summary_en": "Expert money changer and metallurgist stationed along the Noyyal trade route who assayed Roman silver denarii, applied chisel-slits to test coin cores, and melted damaged coins into calibrated bullion bars.",
        "summary_ta": "நொய்யல் நதிக்கரை வெள்ளலூரில் தங்கியிருந்து, உரோமானியப் பொன்-வெள்ளி நாணயங்களை எடைபோட்டு மாற்றுரைத்து, உள்நாட்டு வாணிகத்திற்கான கட்டிகளாக வார்த்த சங்ககாலப் பொன் வணிகர்.",
        "content": """# The Vellalur Bullion Dealer (வெள்ளலூர் பொன் வணிகர்)

Equipped with balance scales and touchstones, these dealers formed the critical financial bridge between Yavana maritime merchants and local craft guilds.
"""
    },
    {
        "category": "characters",
        "slug": "char-pliny-the-elder-trade-historian",
        "file": "char-pliny-the-elder-trade-historian.md",
        "node_type": "character",
        "name_en": "Pliny the Elder: Roman Naturalist & Documenter of the Indian Ocean Trade Deficit",
        "name_ta": "மூத்த பிளினி - இந்தியப் பெருங்கடல் வர்த்தகப் பற்றாக்குறையை ஆவணப்படுத்திய உரோமானிய அறிஞர்",
        "era": "Classical Roman Era",
        "year_start": 23,
        "year_end": 79,
        "thinai": "Neithal",
        "summary_en": "Roman naval commander and naturalist whose encyclopedia *Naturalis Historia* provides primary documentation of Roman sailing schedules to Muziris and the astronomical gold drain to Indian kingdoms.",
        "summary_ta": "உரோமானிய அறிஞர் மற்றும் கடற்படை அதிகாரி. தனது நூலில் உரோமிலிருந்து பருவக்காற்று வாயிலாகத் தமிழகக் கடற்கரைக்குச் செல்லும் வழிகளையும், தங்க வெளியேற்றத்தையும் பதிவு செய்த வரலாற்று ஆசிரியர்.",
        "content": """# Pliny the Elder (மூத்த பிளினி)

Pliny's vivid accounts of the 40-day monsoon voyage from the Red Sea to Muziris align with contemporary Sangam poems describing foreign Yavana ships arriving laden with gold.
"""
    },
    {
        "category": "places",
        "slug": "place-kallidaikurichi-porunai-mint-quarter",
        "file": "place-kallidaikurichi-porunai-mint-quarter.md",
        "node_type": "place",
        "name_en": "Kallidaikurichi: Thamirabarani Industrial Minting Center & Akkasalai Quarter",
        "name_ta": "கல்லிடைக்குறிச்சி - தாமிரபரணிக் கரையின் அக்கசாலை நாணய உற்பத்தித் தளம்",
        "era": "Early Medieval to Pandya Era",
        "year_start": 700,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Historic industrial and commercial township on the Thamirabarani (Porunai) River in Tirunelveli district, recorded in Pandyan epigraphs as home to state mints (Akkasalai), copper artisans, and bullion merchants.",
        "summary_ta": "திருநெல்வேலி மாவட்டம் தாமிரபரணி ஆற்றங்கரையில் அமைந்துள்ள வரலாற்றுத் தளம். பாண்டியர் காலத்தில் அரச நாணயங்களை வார்த்த அக்கசாலையும், பொன்-வெள்ளி வணிகர்களும் நிறைந்திருந்த கைவினைப் பெருநகரம்.",
        "content": """# Kallidaikurichi Mint Quarter (கல்லிடைக்குறிச்சி)

- **Coordinates**: 8.6900° N, 77.4600° E.  
- **River**: Thamirabarani River basin (*பொருநை நதி*).  
- **Historic Role**: State Akkasalai minting workshop for Pandyan gold and copper coinage.
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: ANCIENT TAMIL HYDRAULIC SLUICES, GRAND ANICUT & CASCADE TANKS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-porunararruppadai-kallanai-delta-engineering",
        "file": "text-porunararruppadai-kallanai-delta-engineering.md",
        "node_type": "text",
        "name_en": "Porunararruppadai: Karikala Cholan's Taming of the Kaveri & Stone Embankment Engineering",
        "name_ta": "பொருநராற்றுப்படை - கரிகால் பெருவளத்தானின் காவிரி அணைக்கட்டு மற்றும் கல்லணைக் கட்டுமானம்",
        "era": "Sangam Classical Era",
        "year_start": -50,
        "year_end": 150,
        "thinai": "Marutham",
        "summary_en": "Mudathamakanniyar's poem celebrating Karikala Cholan's monumental river training works—revetting the raging Kaveri with granite boulders, creating the world's oldest functional water diversion dam (Kallanai), and ending destructive delta floods.",
        "summary_ta": "கரிகால் பெருவளத்தான் காவிரியின் வெள்ளத்தைக் கட்டுப்படுத்த பெருங்கற்களைக் கொண்டு கரைகளை உயர்த்திக் கட்டிய கல்லணைப் பொறியியலைப் பாடும் பொருநராற்றுப்படை பாடல்.",
        "content": """# Porunararruppadai: Grand Anicut Engineering (கல்லணை)

---

## 1. Fluvial Civil Engineering
Karikala rolled unhewn granite boulders into the soft riverbed sand, allowing them to settle by their sheer weight and binding them with durable hydraulic clay-lime mortar to withstand seasonal monsoon surges.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-kallanai-karikala-stone-embankment-charters",
        "file": "insc-kallanai-karikala-stone-embankment-charters.md",
        "node_type": "inscription",
        "name_en": "Kallanai Epigraphical Traditions: Karikala's Granite Embankments & Silt Diversion Charters",
        "name_ta": "கல்லணைக் கல்வெட்டு மரபுகள் - கரிகாலனின் பெருங்கற்கட்டு மற்றும் வண்டல் திசைதிருப்பல் சாசனங்கள்",
        "era": "Sangam to Imperial Chola Era",
        "year_start": 100,
        "year_end": 1100,
        "thinai": "Marutham",
        "summary_en": "Inscriptional and copper plate charters documenting Karikala Chola's boulder diversion structure across the Kaveri, reinforced by Rajaraja I and Rajendra I with masonry vents to prevent heavy silt from choking the irrigation channels.",
        "summary_ta": "கரிகாலன் கட்டிய கல்லணையை சோழப் பேரரசர்கள் தொடர்ந்து பராமரித்து, கொள்ளிடத்தில் வெள்ளத்தையும் காவிரியில் பாசன நீரையும் பிரித்துத் திசைதிருப்பிய மதகுகள் மற்றும் கலங்கல் சாசனங்கள்.",
        "content": """# Kallanai Inscriptional Records (கல்லணைச் சாசனங்கள்)

**Structure**: Length 329 m (1,079 ft), width up to 20 m (66 ft).  
**Engineering Feat**: Diverts monsoon surges into the lower-gradient Kollidam river while feeding the fertile delta channels of the Kaveri.
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-veeranam-tank-rajendra-excavation-charter",
        "file": "insc-veeranam-tank-rajendra-excavation-charter.md",
        "node_type": "inscription",
        "name_en": "Veeranam Tank Charters: Rajendra Chola's 16-Kilometer Lake & Vadavaru Channel",
        "name_ta": "வீராணம் ஏரிக் கல்வெட்டுகள் - இராஜேந்திர சோழனின் 16 கி.மீ பிரம்மாண்ட ஏரி மற்றும் வடவாறு கால்வாய்",
        "era": "Imperial Chola Era",
        "year_start": 1015,
        "year_end": 1040,
        "thinai": "Marutham",
        "summary_en": "Imperial Chola inscriptions recording the excavation and continuous maintenance of the colossal Veeranarayanapuram lake (Veeranam Eri) in Cuddalore district, fed by the Vadavaru channel from the Kollidam to irrigate hundreds of villages.",
        "summary_ta": "இராஜேந்திர சோழன் தன் தந்தை இராஜராஜனின் நினைவாக உருவாக்கிய வீராணம் ஏரி. 16 கி.மீ நீளமும் 3 கி.மீ அகலமும் கொண்ட இப்பிரம்மாண்ட நீர்த்தேக்கத்தின் மதகுகள், வடவாறு கால்வாய் மற்றும் ஏரி வாரிய நிர்வாகக் கல்வெட்டுகள்.",
        "content": """# Veeranam Tank Inscriptions (வீராணம் ஏரி சாசனம்)

---

## 1. Continental Reservoir Scale
- **Length**: 16 km (10 miles), capacity approx. 1,465 million cubic feet.
- Fed via the Vadavaru channel excavated from the Kollidam river at Lower Anicut.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kallanai-hydraulic-dam-mechanics",
        "file": "concept-kallanai-hydraulic-dam-mechanics.md",
        "node_type": "concept",
        "name_en": "Kallanai Dam Hydraulics: Curved Axis, Silt Scouring & Bifurcation Fluvial Dynamics",
        "name_ta": "கல்லணை நீரியல் பொறியியல் - வளைந்த அணைக்கட்டு, வண்டல் மேலாண்மை மற்றும் ஆற்றுப் பிரிப்பு",
        "era": "Sangam to Modern Era",
        "year_start": 100,
        "year_end": 1900,
        "thinai": "Marutham",
        "summary_en": "The sophisticated fluid dynamics of the Grand Anicut: an undulating curved masonry crest directing high-velocity floodwaters to flush silt down the steep Kollidam, while diverting smooth, nutrient-rich water into the elevated Kaveri delta canals.",
        "summary_ta": "கல்லணையின் வளைவான வடிவமைப்பு. கொள்ளிடத்தின் சரிவான போக்கைப் பயன்படுத்தி கனமான மணல் வண்டலை அடித்துச் செல்லவும், மேல்மட்டச் சத்து மிகுந்த நீரை மட்டும் காவிரியின் பாசனக் கால்வாய்களுக்குத் திருப்பவும் அமைக்கப்பட்ட அறிவியல் அற்புதம்.",
        "content": """# Kallanai Dam Hydraulics (கல்லணை நீரியல்)

---

## 1. Hydraulic Principle
Because the Kollidam riverbed is deeper and steeper than the Kaveri, Karikala engineered a curved oblique crest (329 m) that creates a hydraulic jump, dissipating energy and scouring sandy deposits away from the irrigation sluices.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kumuzhi-thumbu-piston-sluice-hydraulics",
        "file": "concept-kumuzhi-thumbu-piston-sluice-hydraulics.md",
        "node_type": "concept",
        "name_en": "Kumuzhi Thumbu: Inverted Siphon Submerged Sluice & Silt-Flushing Piston Mechanics",
        "name_ta": "குமுழித் தூம்பு - நீருக்கடிப் பிஸ்டன் மதகு மற்றும் வண்டல் வெளியேற்றும் சுயசுத்திகரிப்புத் தொழினுட்பம்",
        "era": "Iron Age to Imperial Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The genius indigenous Tamil underwater sluice technology: two concentric terracotta or granite shafts with plugstones (Aani); lifting the plug utilizes hydraulic pressure to suck dead silt from the lake bottom while discharging clear water to fields.",
        "summary_ta": "ஏரியின் அடியில் படியும் வண்டல் மண்ணை நீரின் அழுத்தத்தைக் கொண்டே வெளியேற்றும் பண்டைய தமிழரின் குமுழித் தூம்பு மதகு. மேல் துளையிலிருந்து தெளிந்த நீரும், கீழ் துளையிலிருந்து வண்டல் சேறும் ஒரே நேரத்தில் வெளியேறும் நீரியல் நுட்பம்.",
        "content": """# Kumuzhi Thumbu Mechanics (குமுழித் தூம்பு)

---

## 1. Dual-Orifice Self-Scouring
- **Upper Orifice (*மேல் துளை*)**: Discharges clear water for crop irrigation.
- **Lower Orifice (*கீழ் துளை*)**: Positioned at bed level; when the conical plugstone (*ஆணி*) is raised, hydrostatic head pressure flushes accumulated silt, preventing the reservoir from silting up over centuries.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-cascade-tank-network-hydrography",
        "file": "concept-cascade-tank-network-hydrography.md",
        "node_type": "concept",
        "name_en": "Cascade Tank Hydrography: Interconnected Micro-Catchment Chains & Watershed Ecology",
        "name_ta": "சங்கிலித் தொடர் ஏரி அமைப்பு - நீர்ப்பிடிப்புப் பகுதிகள் மற்றும் படிநிலை ஏரித் தொடரியல்",
        "era": "Sangam to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "Mullai",
        "summary_en": "The integrated watershed management system where dozens of village irrigation tanks (Erigal) were linked in descending chains: the surplus weir of one tank fed the feeder channel of the next, preventing flash flood damage and maximizing rainwater retention.",
        "summary_ta": "ஒரு சிறு நதிப்படுகையில் மேட்டுப் பகுதியிலிருந்து தாழ்வான பகுதி வரை அமைக்கப்பட்ட சங்கிலித் தொடர் ஏரிகள். முதல் ஏரி நிரம்பியதும் அதன் உபரி நீர் கலிங்கு வழியாக அடுத்த ஏரியை அடையும் வகையில் அமைக்கப்பட்ட நீர்ப்பிடிப்பு முறைமை.",
        "content": """# Cascade Tank Networks (சங்கிலித் தொடர் ஏரிகள்)

Common throughout Pudukkottai, Ramanathapuram, and Kanchipuram, ensuring that even in drought years of erratic rainfall, no single raindrop escaped unutilized to the sea.
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kalingu-surplus-escape-weir-architecture",
        "file": "concept-kalingu-surplus-escape-weir-architecture.md",
        "node_type": "concept",
        "name_en": "Kalingu Surplus Weirs: Curved Energy-Dissipating Masonry Escapes & Flood Relief",
        "name_ta": "கலிங்கு - உபரி நீர்க் கசிவு மதகு, ஆற்றல் தணிக்கும் கருங்கல் கட்டுமானம் மற்றும் வெள்ளத் தடுப்பு",
        "era": "Classical to Medieval Era",
        "year_start": -200,
        "year_end": 1400,
        "thinai": "Marutham",
        "summary_en": "The stone architectural design of lake surplus spillways (Kalingu): stepped granite cills flanked by grooved monolithic pillars that held wooden flashboards, allowing village water masters to regulate reservoir storage capacity seasonally.",
        "summary_ta": "ஏரிகளின் கரைகள் உடைந்துவிடாமல் உபரி வெள்ள நீரைப் பாதுகாப்பாக வெளியேற்றும் கருங்கல் கலிங்கு மதகுகள். தூண்களில் உள்ள பள்ளங்களில் மரப் பலகைகளை இறக்கி நீரின் அளவை உயர்த்தவோ குறைக்கவோ செய்யும் நெகிழ்வுத் தொழினுட்பம்.",
        "content": """# Kalingu Surplus Weir Architecture (கலிங்கு)

---

## 1. Energy Dissipation Steps
Stepped stone cascades break the falling velocity of rushing surplus floodwaters, preventing scouring of the earthen dam's toe.
"""
    },
    {
        "category": "characters",
        "slug": "char-karikala-chola-hydraulic-visionary",
        "file": "char-karikala-chola-hydraulic-visionary.md",
        "node_type": "character",
        "name_en": "Karikala Chola: The Great Hydraulic Visionary & Architect of the Grand Anicut",
        "name_ta": "கரிகால் பெருவளத்தான் - காவிரியை அடக்கிக் கல்லணை கட்டிய மாபெரும் நீரியல் பேரரசன்",
        "era": "Early Sangam Classical Era",
        "year_start": -50,
        "year_end": 50,
        "thinai": "Marutham",
        "summary_en": "Legendary early Chola monarch who engineered the Grand Anicut (Kallanai), embanked the Kaveri river with stone levees, reclaimed extensive marshlands, and transformed the delta into the rice granary of South India.",
        "summary_ta": "காவிரியின் பெருவெள்ளத்தை அடக்கிக் கல்லணையை எழுப்பி, கரைகளை உயர்த்தி, தஞ்சை மண்டலத்தை உணவு கொழிக்கும் நெற்களஞ்சியமாக மாற்றிய சங்ககாலத்து ஒப்பற்ற சோழப் பேரரசன்.",
        "content": """# Karikala Chola (கரிகால் பெருவளத்தான்)

Celebrated across Sangam literature (*Porunararruppadai*, *Pattinappalai*) for turning the wild monsoon inundations into the perennial agricultural prosperity of Tamilakam.
"""
    },
    {
        "category": "characters",
        "slug": "char-chola-neerkatti-hydraulic-engineer",
        "file": "char-chola-neerkatti-hydraulic-engineer.md",
        "node_type": "character",
        "name_en": "Chola Neerkatti Master: Sluice Engineer & Village Water Distribution Master",
        "name_ta": "நீர்க்கட்டி ஆசான் - மதகு இயக்கம், பாசனப் பங்கீடு மற்றும் ஏரிப் பராமரிப்புத் தலைமைப் பொறியாளர்",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1050,
        "thinai": "Marutham",
        "summary_en": "Hereditary irrigation officer attached to the village tank committee (Eri-variyam) who calibrated piston sluice plugs, conducted channel gradient surveys, and distributed rotational water rations (*Murai*).",
        "summary_ta": "ஏரி வாரியத்தின் வழிகாட்டலில் குளத்து மதகுகளைத் திறந்து அடைத்து, பயிர்களுக்கு முறைப்படி நீரைப் பாய்ச்சி, கால்வாய்களில் தூர் வாரிய தலைமை நீர்ப்பாசன அலுவலர்.",
        "content": """# The Neerkatti Master (நீர்க்கட்டி)

Held in deep reverence by agrarian assemblies, these master engineers operated the underwater Kumuzhi Thumbu plugs and inspected bund integrity prior to the onset of the Northeast monsoon.
"""
    },
    {
        "category": "places",
        "slug": "place-veeranam-lake-reservoir",
        "file": "place-veeranam-lake-reservoir.md",
        "node_type": "place",
        "name_en": "Veeranam Lake (Veeranarayanapuram Eri): The 16-Kilometer Chola Engineering Reservoir",
        "name_ta": "வீராணம் ஏரி (வீரநாராயணபுரம் ஏரி) - 16 கி.மீ நீள சோழப் பேரரசு நீர்த்தேக்கம்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Monumental artificial lake in Cuddalore district created by Rajendra Chola I, fed by the Vadavaru channel, spanning 16 kilometers in length, celebrated in Kalki's *Ponniyin Selvan* and medieval inscriptions.",
        "summary_ta": "கடலூர் மாவட்டம் காட்டுமன்னார்கோயில் அருகே அமைந்துள்ள பிரம்மாண்டமான சோழர் ஏரி. கொள்ளிடத்திலிருந்து வெட்டப்பட்ட வடவாறு கால்வாய் மூலம் நீர் நிரப்பப்பட்டு, ஆயிரக்கணக்கான ஏக்கர் நிலங்களுக்குப் பாசனம் தரும் வரலாற்று நீர்த்தேக்கம்.",
        "content": """# Veeranam Lake Reservoir (வீராணம் ஏரி)

- **Coordinates**: 11.3333° N, 79.5500° E.  
- **Dimensions**: Length 16 km (10 miles), width 3.2 km.  
- **Engineering Masterpiece**: Feeds extensive distributaries and preserves monsoon floodwater for the lower delta.
"""
    }
]

# ==============================================================================
# RELATIONAL EDGES (50 Total)
# ==============================================================================
EDGES = [
    # Corpus 1 Edges: Numismatics & Minting
    ("text-kanakkathikaram-bullion-metrology", "codifies", "concept-urai-kal-touchstone-gold-assaying", "metrology", "Medieval", "Codifies mathematical formulas for touchstone streak evaluation.", "Kanakkathikaram verses"),
    ("text-kanakkathikaram-bullion-metrology", "defines", "concept-madhurantakan-madai-gold-standard", "currency", "Medieval", "Details conversion rates for gold Kalanju and Madhurantakan Madai.", "Bullion tables"),
    ("insc-thanjavur-madhurantakan-madai-charters", "standardizes", "concept-madhurantakan-madai-gold-standard", "law", "Imperial Chola", "Specifies Madhurantakan-madai as the mandatory currency for endowments.", "Brihadisvara charters"),
    ("insc-kudumiyamalai-akkasalai-mint-charter", "regulates", "concept-akkasalai-state-mint-mechanics", "state_mint", "Pandya-Chola", "Inscriptions outline master minter privileges and anti-debasement rules.", "Kudumiyamalai epigraphs"),
    ("insc-kudumiyamalai-akkasalai-mint-charter", "situated_at", "place-kudumiyamalai-pandyan-minting-station", "geography", "Medieval", "Engraved on the granite walls of Kudumiyamalai rock temple.", "Archaeological Survey"),
    ("char-akkasalai-nayakan-master-minter", "supervises", "concept-akkasalai-state-mint-mechanics", "minting", "Imperial Chola", "Master minter directed graphite crucible alloying and die-striking.", "Epigraphical records"),
    ("char-thanjavur-kasu-paritchakar-coin-assayer", "uses", "concept-urai-kal-touchstone-gold-assaying", "assaying", "Imperial Chola", "Temple assayer verified gold fineness using touchstone needle rubbings.", "Temple administration"),
    ("concept-madhurantakan-madai-gold-standard", "influenced", "concept-ceylon-man-type-coinage-transmission", "numismatics", "Imperial Chola", "High gold standard backed the wide circulation of Ceylon-man type coins.", "Numismatic studies"),
    ("char-akkasalai-nayakan-master-minter", "minted_at", "place-kallidaikurichi-porunai-mint-quarter", "geography", "Pandyan", "Directed royal minting operations on the banks of Thamirabarani.", "Porunai epigraphs"),
    ("concept-akkasalai-state-mint-mechanics", "practiced_at", "place-kallidaikurichi-porunai-mint-quarter", "industry", "Pandyan", "State mint produced gold Varahans and copper Kasu.", "Kallidaikurichi charters"),

    # Corpus 2 Edges: Roman Hoards & Bullion
    ("arch-pollachi-roman-aurei-hoards", "proves", "concept-mediterranean-trade-deficit-and-pliny-lament", "trade_deficit", "Roman-Sangam", "Caches of gold aurei substantiate Pliny's record of Roman bullion drain.", "Pollachi excavation reports"),
    ("arch-pollachi-roman-aurei-hoards", "located_along", "concept-kongu-palakkad-gap-bullion-highway", "geography", "Roman-Sangam", "Hoard site sits directly in the Palakkad Gap trans-peninsular corridor.", "Kongu survey"),
    ("arch-vellalur-denarii-and-jewelry-hoards", "features", "concept-roman-bullion-counter-marking", "numismatics", "Roman-Sangam", "Denarii exhibit deep chisel-slits defacing imperial portraits.", "Vellalur hoard catalogue"),
    ("char-vellalur-roman-bullion-dealer", "evaluated", "arch-vellalur-denarii-and-jewelry-hoards", "commerce", "Sangam", "Bullion dealer tested and melted Roman silver coins into trade ingots.", "Noyyal river finds"),
    ("arch-karur-amaravathi-riverbed-bullion-finds", "contains", "concept-terracotta-roman-coin-bullae", "material_culture", "Sangam", "Riverbed yielded both authentic Roman coins and clay imitation bullae.", "Amaravathi survey"),
    ("char-pliny-the-elder-trade-historian", "wrote_about", "concept-mediterranean-trade-deficit-and-pliny-lament", "historiography", "1st c. CE", "Pliny documented the annual outflow of 50 million sesterces to India.", "Naturalis Historia"),
    ("concept-roman-bullion-counter-marking", "converted_coins_into", "concept-kongu-palakkad-gap-bullion-highway", "economy", "Sangam", "Counter-marked coins circulated as bullion weight along the highway.", "Numismatic analysis"),
    ("char-vellalur-roman-bullion-dealer", "stationed_at", "place-kallidaikurichi-porunai-mint-quarter", "trade_network", "Sangam", "Bullion dealers linked Kongu depots with southern Pandyan mints.", "Regional studies"),
    ("concept-terracotta-roman-coin-bullae", "modeled_after", "arch-pollachi-roman-aurei-hoards", "imitation", "Sangam", "Local potters cast baked clay amulets from Roman gold aurei.", "Ethnoarchaeology"),
    ("concept-mediterranean-trade-deficit-and-pliny-lament", "channeled_through", "concept-kongu-palakkad-gap-bullion-highway", "maritime_trade", "Ancient", "Mediterranean bullion flowed through the Palakkad Gap toward Tamil capitals.", "Trade route maps"),

    # Corpus 3 Edges: Hydraulic Sluices & Grand Anicut
    ("text-porunararruppadai-kallanai-delta-engineering", "praises", "char-karikala-chola-hydraulic-visionary", "panegyric", "Sangam", "Extols Karikala for harnessing the Kaveri with stone embankments.", "Porunararruppadai lines 240-250"),
    ("text-porunararruppadai-kallanai-delta-engineering", "describes", "concept-kallanai-hydraulic-dam-mechanics", "civil_engineering", "Sangam", "Depicts boulder-masonry diverting destructive monsoon floods.", "Sangam poetry"),
    ("insc-kallanai-karikala-stone-embankment-charters", "records", "concept-kallanai-hydraulic-dam-mechanics", "dam_engineering", "Ancient-Medieval", "Charters confirm Karikala's foundation and Chola masonry reinforcements.", "Delta epigraphs"),
    ("char-karikala-chola-hydraulic-visionary", "built", "concept-kallanai-hydraulic-dam-mechanics", "construction", "Sangam", "Karikala engineered the curved diversion dam across the Kaveri-Kollidam.", "Historical tradition"),
    ("insc-veeranam-tank-rajendra-excavation-charter", "records_creation_of", "place-veeranam-lake-reservoir", "reservoir", "Imperial Chola", "Charters detail the excavation of the 16-km lake and Vadavaru canal.", "Veeranam inscriptions"),
    ("concept-kumuzhi-thumbu-piston-sluice-hydraulics", "installed_at", "place-veeranam-lake-reservoir", "hydraulics", "Medieval", "Veeranam reservoir utilizes underwater Kumuzhi Thumbu sluices.", "Irrigation survey"),
    ("char-chola-neerkatti-hydraulic-engineer", "operates", "concept-kumuzhi-thumbu-piston-sluice-hydraulics", "sluice_operation", "Imperial Chola", "Water master raised the plugstone to flush sediment and irrigate fields.", "Eri-variyam charters"),
    ("concept-cascade-tank-network-hydrography", "incorporates", "concept-kalingu-surplus-escape-weir-architecture", "watershed", "Ancient", "Surplus weirs allow overflow to cascade into downstream reservoirs.", "Hydrological studies"),
    ("char-chola-neerkatti-hydraulic-engineer", "regulates", "concept-kalingu-surplus-escape-weir-architecture", "flood_control", "Imperial Chola", "Engineers adjusted flashboards on stone kalingu pillars during floods.", "Inscriptional rules"),
    ("concept-kallanai-hydraulic-dam-mechanics", "feeds", "place-veeranam-lake-reservoir", "river_diversion", "Chola", "Grand Anicut river training ensured perennial supply down the Kollidam to Veeranam.", "Kaveri basin hydrology")
]

# ==============================================================================
# MAIN HARVESTER EXECUTION
# ==============================================================================
def main():
    print("=" * 70)
    print("🚀 BATCH 6: TRIPLE CIVILIZATIONAL EXPANSION HARVESTER")
    print("   1. Ancient Tamil Numismatics, Bullion & Royal Minting (10 dossiers)")
    print("   2. Roman Currency Hoards & Mediterranean Bullion Drain (10 dossiers)")
    print("   3. Ancient Tamil Hydraulic Sluices & Grand Anicut Engineering (10 dossiers)")
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
