#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 2):
1. Ancient Tamil Philosophy, Epistemology & Dialectics (13 dossiers)
2. Ancient Tamil Mathematics, Metrology, Fractions & Land Surveying (10 dossiers)
3. Ancient Tamil Legal Systems, Village Assemblies & Judiciary (11 dossiers)

Total: 34 Canonical Dossiers, ~60 Relational Edges, 68 Dense 1024-dim BGE-M3 Embeddings.
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
# DOSSIERS DEFINITION (34 Total)
# ==============================================================================
DOSSIERS = [
    # --------------------------------------------------------------------------
    # CORPUS 1: ANCIENT TAMIL PHILOSOPHY, EPISTEMOLOGY & DIALECTICS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-manimekalai-samaya-kanakkar-epistemology",
        "file": "text-manimekalai-samaya-kanakkar-epistemology.md",
        "node_type": "text",
        "name_en": "Manimekalai: Samaya Kanakkar Thanthiram (Classical Buddhist & Inter-School Dialectics)",
        "name_ta": "மணிமேகலை - சமயக் கணக்கர் தந்திறம் கேட்ட காதை, பௌத்த அளவை நூல் மற்றும் தருக்க வாதங்கள்",
        "era": "Sangam Post-Classical Era",
        "year_start": 400,
        "year_end": 600,
        "thinai": "Marutham",
        "summary_en": "Landmark epistemological canto of the Manimekalai epic composed by Seethalai Sathanar (Canto 27 & 29). Details formal debate between major philosophical schools: Lokayata materialism, Nyaya-Vaisheshika, Samkhya, Mimamsa, and Buddhist Pramana-Vada, establishing direct perception (Katchi) and valid inference (Karuthu) as the premier epistemological criteria.",
        "summary_ta": "சீத்தலைச் சாத்தனாரின் மணிமேகலை காப்பியத்தில் சமயக் கணக்கர் தந்திறம் கேட்ட காதை மற்றும் தவத்திறம் பூண்டு தருமம் கேட்ட காதை. உலகாயதம், நியாயம், வைசேஷிகம், சாங்கியம், மீமாம்சை மற்றும் பௌத்த அளவை வாதங்களின் ஒப்பீட்டுத் தருக்க வாதங்களை விளக்கி, காட்சி மற்றும் கருத்து அளவைகள் மூலம் உண்மை அறிவை எய்தும் வழியைக் காட்டும் ஒப்பற்ற தத்துவ ஆவணம்.",
        "content": """# Manimekalai: Epistemology & Inter-School Dialectics

**Author**: Seethalai Sathanar (*சீத்தலைச் சாத்தனார்*).  
**Cantos**: Canto 27 (*சமயக் கணக்கர் தந்திறம் கேட்ட காதை*) & Canto 29 (*தவத்திறம் பூண்டு தருமம் கேட்ட காதை*).  
**Key Schools Analyzed**: Lokayata (Materialism), Bauddha (Buddhism), Samkhya, Vaisheshika, Nyaya, Mimamsa.  

---

## 1. Classical Pramana-Vada (Theory of Knowledge)
In Canto 27, Sathanar reviews the ten classical means of knowledge (*Pramana* / *அளவை*) accepted across Indian philosophy:
1. *Katchi* (Direct Sensory Perception / Pratyaksha)
2. *Karuthu* (Logical Inference / Anumana)
3. *Uvamam* (Analogy / Upamana)
4. *Agamam* / *Urai* (Authoritative Testimony / Sabda)
5. *Arutpaththi* (Presumption / Arthapatti)
6. *Iyalbu* (Inherent Nature / Sambhava)
7. *Aithiham* (Tradition / Aitihya)
8. *Abhava* (Non-perception / Anupalabdhi)

Buddhist epistemology refined this down to **Two Irreducible Pramanas**:
- **Direct Perception (*Katchi*)**: Indisputable apprehension devoid of conceptual error or illusion.
- **Valid Inference (*Karuthu*)**: Knowledge derived through invariant concomitance (*Vyapti* / *Pukai-Thee thodarbu* - where there is smoke, there is fire).

---

## 2. Refutation of Fatalism and Materialism
The epic refutes the fatalistic determinism of Makkhali Gosala's Ajivika school and the nihilistic materialism of Lokayata, establishing that moral actions (*Karma*) have causal consequences that shape rebirth and spiritual evolution.
"""
    },
    {
        "category": "texts",
        "slug": "text-nilakesi-jain-epistemological-polemics",
        "file": "text-nilakesi-jain-epistemological-polemics.md",
        "node_type": "text",
        "name_en": "Nilakesi: Jain Logical Refutations of Materialism, Buddhism & Nyaya-Vaisheshika",
        "name_ta": "நீலகேசி - சமண தருக்க வாத நூல், உலகாயத-பௌத்த-சாங்கிய தத்துவ மறுப்புகள்",
        "era": "Post-Sangam to Medieval Era",
        "year_start": 600,
        "year_end": 900,
        "thinai": "Marutham",
        "summary_en": "Celebrated Jain dialectical epic poem where the philosopher-heroine Nilakesi engages Buddhist masters (Mokkalan), Ajivika teachers, and Lokayata materialists in debate, utilizing Jain Anekantavada (multi-faceted ontology) and Syadvada conditional logic to defend non-violence (Ahimsa) and soul permanence (Jiva).",
        "summary_ta": "ஐஞ்சிறுங்காப்பியங்களுள் ஒன்றான நீலகேசி. சமயத் தலைவர்களான மொக்கலன் (பௌத்தம்), பூராணன் (ஆசீவகம்), உலகாயதன் ஆகியோருடன் நீலகேசி நிகழ்த்தும் தத்துவ வாதப் போர்; அநேகாந்தவாதம் மற்றும் சியாத்வாதம் என்னும் பன்மைத்துவ தருக்க முறையின் மூலம் சமணத்தின் அகிம்சை மற்றும் ஆன்மக் கொள்கைகளை நிலைநாட்டும் அரிய தத்துவ நூல்.",
        "content": """# Nilakesi: Jain Dialectical Polemics (நீலகேசி)

**Tradition**: Jain Epistemology (*சமண அளவை இயல்*).  
**Core Dialectic Method**: *Anekantavada* (Multi-faceted Truth) and *Syadvada* (Conditional Predication).  
"""
    },
    {
        "category": "texts",
        "slug": "text-sivajnana-bodham-saiva-metaphysics",
        "file": "text-sivajnana-bodham-saiva-metaphysics.md",
        "node_type": "text",
        "name_en": "Sivajnana Bodham: Meikandar's Canonical 12 Epistemological Aphorisms of Saiva Siddhanta",
        "name_ta": "சிவஞான போதம் - மெய்கண்டாரின் 12 சைவ சித்தாந்த மெய்ப்பொருள் நூற்பாக்கள்",
        "era": "Imperial Chola Era",
        "year_start": 1200,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The foundational root text of systematic Saiva Siddhanta philosophy by Meikandar of Thiruvennainallur (c. 1220 CE). Formulates 12 concise sutras demonstrating the tripartite reality of Pathi (Supreme Godhead), Pasu (Individual Soul), and Paasa (Cosmic Bondage: Anava, Karma, Maya), analyzed through strict epistemological syllogisms.",
        "summary_ta": "மெய்கண்ட தேவரால் அருளப்பட்ட 12 நூற்பாக்களைக் கொண்ட சைவ சித்தாந்தத்தின் முதன்மை மெய்ப்பொருள் நூல். 'அவன் அவள் அது எனும் அவை மூவினைமையின்...' என்று தொடங்கும் இதன் முதல் நூற்பா, உலகம் தோன்றி அழியும் இயல்பினதாகையால் அதனை இயக்கும் ஒரு முதல்வன் (பதி) உண்டு என்பதை தர்க்கரீதியாக நிறுவி, பதி-பசு-பாசம் என்ற முப்பொருள்களின் மெய்ம்மையை விளக்குகிறது.",
        "content": """# Sivajnana Bodham: Saiva Siddhanta Epistemology (சிவஞான போதம்)

**Author**: Meikandar (*மெய்கண்டார்*) of Thiruvennainallur.  
**Historical Era**: ~1220 CE (Late Imperial Chola Era).  
**Aphorisms**: 12 Sutras (*நூற்பாக்கள்*) divided into General (*Podhu*) and Special (*Sirappu*) Realization.  
"""
    },
    {
        "category": "texts",
        "slug": "text-tolkappiyam-meyppattiyal-aesthetics",
        "file": "text-tolkappiyam-meyppattiyal-aesthetics.md",
        "node_type": "text",
        "name_en": "Tolkappiyam Meyppattiyal: Eight-Fold Aesthetic Psychology, Cognitive States & Rasa Theory",
        "name_ta": "தொல்காப்பியம் மெய்ப்பாட்டியல் - எண்வகை உளவியல் மெய்ப்பாடுகள் மற்றும் அழகியல் கோட்பாடு",
        "era": "Sangam Classical Era",
        "year_start": -500,
        "year_end": 200,
        "thinai": "All Thinais",
        "summary_en": "Ancient Tamil aesthetic and cognitive psychology treatise codified in Tolkappiyam Porulatikaram. Analyzes internal psychological feelings manifested as physical somatic signs (Meyppadu) across eight primary emotional categories: Nagai (mirth), Azhugai (grief), Ilivaral (disgust), Marutkai (wonder), Acham (fear), Perumitham (valour), Vekuli (wrath), and Uvakai (joy).",
        "summary_ta": "தொல்காப்பியப் பொருளதிகாரத்தில் அமைந்துள்ள அழகியல் மற்றும் உளவியல் கோட்பாடு. மனித மனத்தின் அக உணர்வுகள் உடலில் மெய்ப்பட்டுத் தோன்றும் எட்டு வகை உணர்ச்சிகளான நகை, அழுகை, இளிவரல், மருட்கை, அச்சம், பெருமிதம், வெகுளி, உவகை ஆகியவற்றின் தோற்றுவாய்களையும் அவற்றின் உளவியல் விளைவுகளையும் ஆராயும் ஒப்புயர்வற்ற இலக்கணப் பகுதி.",
        "content": """# Tolkappiyam Meyppattiyal (தொல்காப்பியம் மெய்ப்பாட்டியல்)

**Author**: Tolkappiyar (*தொல்காப்பியர்*).  
**The 8 Somatic-Aesthetic States (*எண்வகை மெய்ப்பாடுகள்*)**:
1. *Nagai* (Mirth / Comedy)
2. *Azhugai* (Pathos / Grief)
3. *Ilivaral* (Disgust / Contempt)
4. *Marutkai* (Astonishment / Wonder)
5. *Acham* (Terror / Fear)
6. *Perumitham* (Heroic Pride / Valour)
7. *Vekuli* (Wrath / Indignation)
8. *Uvakai* (Ecstatic Joy / Bliss)
"""
    },
    {
        "category": "concepts",
        "slug": "concept-pramana-vada-tamil-epistemology",
        "file": "concept-pramana-vada-tamil-epistemology.md",
        "node_type": "concept",
        "name_en": "Pramana-Vada: Sensory Perception (Katchi), Inference (Karuthu) & Testimony (Urai)",
        "name_ta": "அளவை வாதம் - காட்சி, கருத்து மற்றும் உரை வழியிலான தமிழரின் அறிவாராய்ச்சி மெய்யியல்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Indigenous Tamil epistemological framework classifying valid means of true knowledge. Explores direct sensory perception (Katchi), deductive inference (Karuthu using invariant concomitance), and reliable testimony (Urai), alongside rigorous refutations of logical fallacies (Hetvabhasa / Poraipoli).",
        "summary_ta": "தமிழரின் மெய்யியல் அறிவாராய்ச்சி முறையான அளவை வாதம். கண்ணாலும் பொறிகளாலும் நேரடியாக உணரும் காட்சி அளவை (பிரத்தியட்சம்), புகையைக் கண்டு நெருப்பை அறிவது போன்ற தருக்கரீதியான கருத்து அளவை (அனுமானம்), மற்றும் பொய்யற்ற அறிஞர் மொழியான உரை அளவை (சப்தம்) ஆகியவற்றின் தத்துவ அடித்தளம்.",
        "content": """# Pramana-Vada: Tamil Epistemology (அளவை வாதம்)

**Three Valid Instruments of Knowledge**:
- *Katchi* (Perception)
- *Karuthu* (Inference)
- *Urai* (Testimony)
"""
    },
    {
        "category": "concepts",
        "slug": "concept-anatta-and-pratityasamutpada-manimekalai",
        "file": "concept-anatta-and-pratityasamutpada-manimekalai.md",
        "node_type": "concept",
        "name_en": "Dependent Origination (Pratityasamutpada) & Non-Self (Anatta) in Tamil Buddhism",
        "name_ta": "சார்புத் தோற்றம் மற்றும் அனாத்மக் கோட்பாடு - மணிமேகலையின் பௌத்த மெய்யியல்",
        "era": "Sangam Post-Classical Era",
        "year_start": 400,
        "year_end": 700,
        "thinai": "Neithal",
        "summary_en": "Analysis of the 12-link causal chain of Dependent Origination (Pratityasamutpada / Bhavachakra) expounded in Canto 30 of Manimekalai, demonstrating how ignorance produces karmic formations, suffering, and rebirth, and how its dissolution yields liberation (Nirvana).",
        "summary_ta": "மணிமேகலை காப்பியத்தின் 30-ஆம் காதையில் அறவண அடிகள் விளக்கும் 12 நிலைச் சார்புத் தோற்றக் கோட்பாடு (பவச்சக்கரம்). அறியாமை (பேதைமை) முதல் மூப்பு-மரணங்கள் வரையிலான சங்கிலித் தொடர் விளைவுகளும், ஆன்மா என்ற தனித்த அழியாப் பொருள் இல்லை என்ற அனாத்மத் தத்துவமும் விளக்கப்படும் முறை.",
        "content": """# Dependent Origination in Manimekalai (சார்புத் தோற்றம்)

**Core Principle**: Nothing exists independently; all phenomena arise dependent upon causes (*Pratityasamutpada*).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-pathi-pasu-paasa-triad",
        "file": "concept-pathi-pasu-paasa-triad.md",
        "node_type": "concept",
        "name_en": "The Pathi-Pasu-Paasa Triad: Metaphysics of God, Soul & Cosmic Bondage",
        "name_ta": "பதி-பசு-பாச முப்பொருள் உண்மை - சைவ சித்தாந்த உள்ளியல் மெய்ப்பொருள் ஆய்வு",
        "era": "Medieval Classical Era",
        "year_start": 800,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The tripartite ontology of Saiva Siddhanta: Pathi (transcendent Godhead Shiva), Pasu (finite embodied individual soul), and Paasa (the threefold fetter of Anava primordial ego, Karma action-reaction, and Maya material embodiment), resolved through divine grace (Arul).",
        "summary_ta": "சைவ சித்தாந்தத்தின் முப்பொருள் உண்மை: என்றும் மாறாத முழுமுதற் கடவுளான 'பதி', உடலெடுத்து உழலும் சிற்றுயிரான 'பசு', மற்றும் உயிரை அறியாமையில் பிணிக்கும் மும்மலங்களான ஆணவம், கன்மம், மாயை ஆகிய 'பாசம்'; இறைவனின் திருவருளால் பாசம் நீங்கி ஆன்மா முக்தி அடையும் தத்துவப் படிநிலை.",
        "content": """# The Pathi-Pasu-Paasa Triad (பதி பசு பாச உண்மை)

**Three Eternal Realities**:
1. *Pathi*: The Uncaused Supreme Reality.
2. *Pasu*: The Bound Soul endowed with cognitive potential.
3. *Paasa*: The Threefold Fetter (*Anava*, *Karma*, *Maya*).
"""
    },
    {
        "category": "concepts",
        "slug": "concept-meyppadu-eightfold-aesthetic-emotions",
        "file": "concept-meyppadu-eightfold-aesthetic-emotions.md",
        "node_type": "concept",
        "name_en": "Meyppadu: The Eightfold Somatic-Cognitive Emotional Spectrum (Nagai, Azhugai, Ilivaral, etc.)",
        "name_ta": "எண்வகை மெய்ப்பாடுகள் - தொல்காப்பியரின் உளவியல்-அழகியல் வெளிப்பாடுகள்",
        "era": "Sangam Classical Era",
        "year_start": -500,
        "year_end": 200,
        "thinai": "All Thinais",
        "summary_en": "Breakdown of the somatic correlates of human emotion codified in Tolkappiyam. Details how external physical signs (Meyppadu) reveal cognitive processing across heroic (Puram) and romantic (Akam) contexts.",
        "summary_ta": "தொல்காப்பிய மெய்ப்பாட்டியலின் எட்டு வகை நவரச வெளிப்பாடுகளின் உளவியல் பகுப்பாய்வு. ஒவ்வொரு மெய்ப்பாடும் தோன்றுவதற்கான நான்கு களங்கள் (எ.கா. நகை தோன்றும் நான்கு நிலைகள்: எள்ளல், இளமை, பேதைமை, மடன்) பற்றிய நுட்பமான உளவியல் வகைப்பாடு.",
        "content": """# Meyppadu: Somatic Emotional States (எண்வகை மெய்ப்பாடுகள்)

**The 8 Modes**: *Nagai*, *Azhugai*, *Ilivaral*, *Marutkai*, *Acham*, *Perumitham*, *Vekuli*, *Uvakai*.  
"""
    },
    {
        "category": "characters",
        "slug": "char-seethalai-sathanar-philosopher-poet",
        "file": "char-seethalai-sathanar-philosopher-poet.md",
        "node_type": "character",
        "name_en": "Seethalai Sathanar: Author of Manimekalai & Pioneer of Buddhist Logic",
        "name_ta": "சீத்தலைச் சாத்தனார் - மணிமேகலை காப்பிய ஆசிரியர் மற்றும் பௌத்த தருக்க மேதை",
        "era": "Sangam Post-Classical Era",
        "year_start": 400,
        "year_end": 550,
        "thinai": "Marutham",
        "summary_en": "Great grain merchant, scholar, and poet from Madurai who authored the epic Manimekalai, blending soaring narrative poetry with rigorous dialectical epistemology and social compassion.",
        "summary_ta": "மதுரை கூலவாணிகன் சீத்தலைச் சாத்தனார். மணிமேகலை காப்பியத்தை இயற்றி, சிலப்பதிகாரத்தின் தொடர்ச்சியாகப் பௌத்த அறநெறிகளையும் பசிப்பிணி போக்கும் அமுதசுரபி தத்துவத்தையும் தமிழ் உலகுக்குத் தந்த மாபெரும் கவிஞர்.",
        "content": """# Seethalai Sathanar (சீத்தலைச் சாத்தனார்)

**Masterpiece**: *Manimekalai* (*மணிமேகலை*).  
**Legacy**: Epistemological logic, anti-poverty ethics (*Aakkar Karunai*), Buddhist philosophy.  
"""
    },
    {
        "category": "characters",
        "slug": "char-meikandar-epistemological-reformer",
        "file": "char-meikandar-epistemological-reformer.md",
        "node_type": "character",
        "name_en": "Meikandar: 13th-Century Formulator of Systematic Saiva Siddhanta Metaphysics",
        "name_ta": "மெய்கண்ட தேவர் - சிவஞான போதம் அருளிய சைவ சித்தாந்த சீர்திருத்த மெய்ஞ்ஞானி",
        "era": "Imperial Chola Era",
        "year_start": 1200,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "Child prodigy philosopher of Thiruvennainallur whose realization yielded the foundational text Sivajnana Bodham, establishing a rigorous dialectical tradition carried on by the Santhana Acharyas.",
        "summary_ta": "திருவெண்ணெய்நல்லூரில் அருளுரை வழங்கிய இளம் மெய்ஞ்ஞானி. 'சிவஞான போதம்' என்னும் தலைசிறந்த தத்துவ நூலை அருளி, தர்க்கரீதியான சைவ சித்தாந்த மரபை நிறுவிய சந்தான குரவர்களில் முதன்மையானவர்.",
        "content": """# Meikandar Devar (மெய்கண்ட தேவர்)

**Seat**: Thiruvennainallur on the South Pennai river.  
**Foundational Work**: *Sivajnana Bodham* (12 Sutras).  
"""
    },
    {
        "category": "characters",
        "slug": "char-aravanavadigal-buddhist-preceptor",
        "file": "char-aravanavadigal-buddhist-preceptor.md",
        "node_type": "character",
        "name_en": "Aravana Adigal: Master of Buddhist Dialectics & Compassionate Ascetic Teacher",
        "name_ta": "அறவண அடிகள் - பௌத்த தருக்கவியல் குரு மற்றும் மணிமேகலையின் ஞானாசிரியர்",
        "era": "Sangam Post-Classical Era",
        "year_start": 450,
        "year_end": 550,
        "thinai": "Marutham",
        "summary_en": "Venerable Buddhist monk of Kanchipuram and Kaveripoompattinam who initiates heroine Manimekalai into higher Buddhist logic, Dependent Origination, and the eradication of desire.",
        "summary_ta": "காஞ்சிபுரத்திலும் பூம்புகாரிலும் பௌத்த தர்மத்தை அருளிய தவத்திரு முதிய துறவி; மணிமேகலைக்கு அளவை வாதங்களையும் பவச்சக்கரத்தின் 12 நிலைகளையும் உபதேசித்து வழிகாட்டிய ஞான குரு.",
        "content": """# Venerable Aravana Adigal (அறவண அடிகள்)

**Role**: Buddhist Preceptor and Grand Teacher of Logic in *Manimekalai*.  
"""
    },
    {
        "category": "places",
        "slug": "place-kanchipuram-buddhist-dialectical-vihara",
        "file": "place-kanchipuram-buddhist-dialectical-vihara.md",
        "node_type": "place",
        "name_en": "Kanchipuram Raja Vihara: Ancient University of Logic & Dialectics",
        "name_ta": "காஞ்சிபுரம் பௌத்த ராஜ விகாரை - தருக்கவியல் மற்றும் அளவை ஆராய்ச்சிக் கல்விப் பீடம்",
        "era": "Classical to Medieval Era",
        "year_start": 300,
        "year_end": 800,
        "thinai": "Marutham",
        "summary_en": "Renowned monastic educational center in Kanchipuram (12.8342° N, 79.7036° E) where master logicians like Dignaga, Dharmapala, and Aravana Adigal taught Buddhist epistemology and grammar.",
        "summary_ta": "பண்டைக் காஞ்சிபுரத்தின் வரலாற்றுப் புகழ்பெற்ற பௌத்த பல்கலைக்கழக மையம் (12.8342° N, 79.7036° E). திக்நாகர், தர்மபாலர், போதிதர்மர் மற்றும் அறவண அடிகள் ஆகியோர் தங்கித் தருக்கவியலையும் தத்துவங்களையும் போதித்த சர்வதேச கல்விப் பீடம்.",
        "content": """# Kanchipuram Raja Vihara (காஞ்சிபுரம் பௌத்த விகாரை)

**Coordinates**: 12.8342° N, 79.7036° E.  
**Historical Glory**: Ancient Asian center for Buddhist logic, Sanskrit/Pali studies, and epistemological research.  
"""
    },
    {
        "category": "places",
        "slug": "place-thiruvennainallur-meikandar-ashram",
        "file": "place-thiruvennainallur-meikandar-ashram.md",
        "node_type": "place",
        "name_en": "Thiruvennainallur: Birthplace of Systematic Saiva Siddhanta Epistemology",
        "name_ta": "திருவெண்ணெய்நல்லூர் - மெய்கண்டாரின் சைவ சித்தாந்த குருபீடம் மற்றும் மெய்ஞ்ஞானத் தளம்",
        "era": "Imperial Chola Era",
        "year_start": 1200,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Historic town on the South Pennai river in Villupuram district (11.8500° N, 79.3500° E) where Meikandar composed Sivajnana Bodham and trained his teacher Arulnandi Sivachariyar.",
        "summary_ta": "விழுப்புரம் மாவட்டத்தில் தென்பெண்ணை ஆற்றங்கரையில் அமைந்துள்ள திருவெண்ணெய்நல்லூர் (11.8500° N, 79.3500° E). சுந்தரமூர்த்தி நாயனாரைத் தடுத்தாட்கொண்டதும், மெய்கண்ட தேவர் 'சிவஞான போதம்' அருளித் தன் குருநாதரான அருள்நந்திக்கு உபதேசம் செய்த வரலாற்றுத் தளம்.",
        "content": """# Thiruvennainallur Ashram (திருவெண்ணெய்நல்லூர்)

**Coordinates**: 11.8500° N, 79.3500° E.  
**Spiritual Matrix**: Cradle of systematic 13th-century Saiva Siddhanta philosophy.  
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 2: ANCIENT TAMIL MATHEMATICS, METROLOGY & FRACTIONS
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-kanakkathikaram-kari-nayanar",
        "file": "text-kanakkathikaram-kari-nayanar.md",
        "node_type": "text",
        "name_en": "Kanakkathikaram: Kari Nayanar's Manual of Tamil Arithmetic, Geometry & Fractions",
        "name_ta": "கணக்கதிகாரம் - காரி நாயனாரின் தமிழ்க் கணிதவியல், வடிவவியல் மற்றும் பின்னக் கணக்கு நூல்",
        "era": "Early Medieval Classical Era",
        "year_start": 700,
        "year_end": 1000,
        "thinai": "Marutham",
        "summary_en": "Classical Tamil mathematical treatise in metrical verse. Covers basic arithmetic, fractional division, area calculations for irregular agrarian plots, grain volumetric estimation, shadow gnomonics for calculating sun declination, and gold fineness verification.",
        "summary_ta": "காரி நாயனாரால் செய்யுள் வடிவில் இயற்றப்பட்ட தமிழ்க் கணிதப் பேரிலக்கணம். நிலப் பரப்பளவுகள், வரப்பு வளைவுகள், நெல் குவியல் அளவுகள், சூரிய நிழல் கணிப்புகள், மற்றும் பொன் மாற்று தரம் அறியும் கணக்கீடுகளை எளிய பாக்களில் விளக்கும் கணிதப் பொக்கிஷம்.",
        "content": """# Kanakkathikaram: Tamil Mathematical Treatise (கணக்கதிகாரம்)

**Author**: Kari Nayanar (*காரி நாயனார்*).  
**Subjects**: Fractional calculus, agrarian land geometry, volumetric grain metrics, shadow trigonometrics.  
"""
    },
    {
        "category": "texts",
        "slug": "text-aathisudi-kondrai-vendan-metrology",
        "file": "text-aathisudi-kondrai-vendan-metrology.md",
        "node_type": "text",
        "name_en": "Tamil Didactic Arithmetic: Fractional Tables, Grain Volumes & Weighing Metrics",
        "name_ta": "தமிழ் மரபுவழிக் கணித அட்டவணைகள் - எண் சுவடி, நெல் அளவைகள் மற்றும் பொன் நிறுத்தல்கள்",
        "era": "Classical to Medieval Era",
        "year_start": 500,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "Indigenous pedagogical mathematical traditions preserved in En-Suvadi arithmetic palm-leaves: multiplication tables, fractional series down to infinitesimal units, cubic dry measures, and merchant guild weighing rules.",
        "summary_ta": "திண்ணைப் பள்ளிக்கூடங்களில் கற்பிக்கப்பட்ட தமிழரின் எண் சுவடி அட்டவணைகள். 1 முதல் 100 வரையிலான வாய்பாடுகள், கீழ்வாய்ச் சிற்றிலக்கப் பின்னங்கள், முகத்தல்-நிறுத்தல் அளவைகள் மற்றும் வணிகக் குழுக்கள் கடைப்பிடித்த நாணய மாற்று விகிதங்கள்.",
        "content": """# En-Suvadi: Pedagogical Tamil Mathematics (எண் சுவடி)

**Traditional Curriculum**: Tinnai School practical arithmetic and trade metrology.  
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-thanjavur-land-survey-metrology",
        "file": "insc-thanjavur-land-survey-metrology.md",
        "node_type": "inscription",
        "name_en": "Thanjavur Brihadisvara Land Survey Epigraphs: Veli, Ma, Kani & Micro-Fractions",
        "name_ta": "தஞ்சைப் பெரிய கோயில் நில அளவை மற்றும் நில அளவைக்கோல் கல்வெட்டுகள்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Granite plinth inscriptions at Thanjavur Brihadisvara recording cadastral measurements of thousands of agricultural plots accurate down to 1/52,428,800,000 of a Veli using standardized 16-span measuring rods (Ulagalandan-kol).",
        "summary_ta": "தஞ்சைப் பெரிய கோயில் பீடத்தில் பொறிக்கப்பட்டுள்ள சோழர் கால நில அளவை ஆவணங்கள். 'உலகளந்தான் கோல்' கொண்டு அளக்கப்பட்ட ஆயிரக்கணக்கான நிலங்களின் பரப்பளவுகள் ஒரு வேலியின் 52,42,88,00,000-ல் ஒரு பங்கு வரை மிகத் துல்லியமாகக் கணக்கிடப்பட்டுப் பொறிக்கப்பட்டுள்ள வியத்தகு சாதனை.",
        "content": """# Thanjavur Cadastral Land Survey Epigraphs (1010 CE)

**Standard Measuring Rod**: *Ulagalandan-kol* of 16 spans (*பதினாறு சாண் கோல்*).  
**Mathematical Accuracy**: Down to micro-fractions of a *Veli*.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-tamil-micro-fractional-mathematics",
        "file": "concept-tamil-micro-fractional-mathematics.md",
        "node_type": "concept",
        "name_en": "Tamil Micro-Fractional Metrology: Immi, Mummi, Anu & Kizh-Mundri (1/320 to 1/10^12)",
        "name_ta": "தமிழ்ப் பின்னக் கணிதம் - முந்திரி, இம்மி, மும்மி, அணு மற்றும் கீழ்-முந்திரி நுண்ணளவியல்",
        "era": "Sangam to Imperial Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Vigesimal and binary micro-fractional taxonomy: Mundri (1/320), Kaani (1/80), Maa (1/20), Immi (1/2,150,400), down to Kizh-mundri (1/102,400) and Anu (1/3,211,264,000,000), enabling precise land revenue taxation without rounding errors.",
        "summary_ta": "பண்டைத் தமிழரின் வியத்தகு பின்னக் கணித முறைமை: முந்திரி (1/320), காணி (1/80), மா (1/20), இம்மி (1/21,50,400), கீழ்-முந்திரி (1/1,02,400) முதல் அணு (1/32,11,26,40,00,000) வரை செல்லும் நுண்ணிய பின்னங்கள்.",
        "content": """# Tamil Micro-Fractional Arithmetic (தமிழ்ப் பின்னக் கணிதம்)

**Fractional Scale**:
- *Maa* = 1/20
- *Kaani* = 1/80
- *Mundri* = 1/320
- *Immi* = 1/2,150,400
- *Anu* = 1/3,211,264,000,000
"""
    },
    {
        "category": "concepts",
        "slug": "concept-chola-land-survey-standardization",
        "file": "concept-chola-land-survey-standardization.md",
        "node_type": "concept",
        "name_en": "Imperial Chola Land Cadastral Survey: Padigam, Nilam-Alantha-Kol & Veli Taxation",
        "name_ta": "சோழர் நில அளவைத் திட்டம் - உலகளந்தான் கோல், பதிவுக் கணக்கு மற்றும் வேலி வரி விதிப்பு",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Empire-wide cadastral survey initiated by Rajaraja I in 1001 CE: standardizing the measuring rod (Ulagalandan-kol of 16 spans), grading soils into 12 productivity classes (Tharam), and establishing non-taxable public reserves (Irayili).",
        "summary_ta": "முதலாம் இராசராச சோழன் 1001-இல் தொடங்கிய பேரரசு தழுவிய நில அளவைத் திட்டம். 16 சாண் நீள உலகளந்தான் கோல், 12 தரங்களாக நிலங்களை வகைப்படுத்துதல், மற்றும் வரிக்கணக்குப் புத்தகங்களில் (வரிப்பொத்தகம்) பதிவேற்றிய நிர்வாக முறைமை.",
        "content": """# Chola Cadastral Survey (சோழர் நில அளவை)

**Reforms**: Standard measuring rods, land quality grading (*Tharam*), permanent boundary stones (*Kallu*).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-ancient-tamil-grain-and-cubic-measures",
        "file": "concept-ancient-tamil-grain-and-cubic-measures.md",
        "node_type": "concept",
        "name_en": "Traditional Grain & Liquid Volumetric Metrology: Sevidu, Aazhakku, Padi, Marakkal & Kalam",
        "name_ta": "தமிழரின் முகத்தல் அளவைகள் - செவிடு, ஆழாக்கு, உழக்கு, படி, மரக்கால் மற்றும் கலம்",
        "era": "Sangam to Medieval Era",
        "year_start": -500,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Hierarchical liquid and grain volumetric standards: 5 Sevidu = 1 Aazhakku; 2 Aazhakku = 1 Uzhakku; 2 Uzhakku = 1 Uri; 2 Uri = 1 Padi / Nazhi; 8 Padi = 1 Marakkal / Kuruni; 12 Marakkal = 1 Kalam (~96 liters), certified with the royal seal.",
        "summary_ta": "பண்டைத் தமிழரின் தானிய மற்றும் திரவ முகத்தல் அளவைகள்: செவிடு, ஆழாக்கு, உழக்கு, உரி, நாழி (படி), குறுணி (மரக்கால்) மற்றும் கலம். சோழர் கால 'இராசராசகேசரி' மரக்கால் போன்ற தரப்படுத்தப்பட்ட அரச முத்திரை மரக்கால்கள்.",
        "content": """# Traditional Grain & Volumetric Measures (முகத்தல் அளவைகள்)

**Volumetric Ladder**: 5 Sevidu $\rightarrow$ Aazhakku $\rightarrow$ Uzhakku $\rightarrow$ Uri $\rightarrow$ Nazhi (Padi) $\rightarrow$ Kuruni (Marakkal) $\rightarrow$ Kalam.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-pon-weight-and-touchstone-metrology",
        "file": "concept-pon-weight-and-touchstone-metrology.md",
        "node_type": "concept",
        "name_en": "Gold Metallurgy & Weight Metrology: Kunrimani, Manjadi, Kalanju & Kasu Fineness",
        "name_ta": "தமிழரின் நிறுத்தல் அளவைகள் - குன்றிமணி, மஞ்சாடி, கழஞ்சு மற்றும் மாற்றுப் பொன் தரம்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "Botanical seed standards for gold and gem metrology: Kunrimani (Abrus precatorius, 105 mg), Manjadi (Adenanthera pavonina, 210 mg), 20 Manjadi = 1 Kalanju (4.2 grams). Touchstone testing (Uraikal) determining gold purity (Maatru).",
        "summary_ta": "பொன்னும் மணிகளும் எடைபோடப் பயன்பட்ட இயற்கை விதை அளவைகள்: குன்றிமணி, மஞ்சாடி, மற்றும் கழஞ்சு. உரைகல்லில் உரசிப் பொன்னின் தரத்தை (மாற்று) அறியும் நாணயவியல் மற்றும் உலோகவியல் கலை.",
        "content": """# Gold Metrology & Weighing (நிறுத்தல் அளவைகள்)

**Seed Standards**: *Kunrimani* (~105 mg), *Manjadi* (~210 mg), *Kalanju* (~4.2 g).  
"""
    },
    {
        "category": "characters",
        "slug": "char-kari-nayanar-mathematician",
        "file": "char-kari-nayanar-mathematician.md",
        "node_type": "character",
        "name_en": "Kari Nayanar: Classical Tamil Mathematician & Author of Kanakkathikaram",
        "name_ta": "காரி நாயனார் - கணக்கதிகாரம் இயற்றிய தமிழ்க் கணித அறிஞர்",
        "era": "Early Medieval Era",
        "year_start": 700,
        "year_end": 900,
        "thinai": "Marutham",
        "summary_en": "Mathematician and scholar who codified practical field geometry, architectural timber calculations, and compound fractions into memorable metrical Tamil verses.",
        "summary_ta": "கணக்கதிகாரம் என்னும் அரிய கணித நூலை இயற்றிய மேதை; நில அளவைகள், பின்னங்கள் மற்றும் வணிகக் கணக்குகளைச் செய்யுள் வடிவில் தந்து தமிழ் கணித வளர்ச்சிக்கு வித்திட்ட முன்னோடி.",
        "content": """# Kari Nayanar (காரி நாயனார்)

**Key Work**: *Kanakkathikaram* (*கணக்கதிகாரம்*).  
"""
    },
    {
        "category": "characters",
        "slug": "char-rajaraja-nilam-alandha-senapathi",
        "file": "char-rajaraja-nilam-alandha-senapathi.md",
        "node_type": "character",
        "name_en": "Kuravan Ulagalandan: Chief Royal Surveyor of the Imperial Cadastral Land Survey",
        "name_ta": "குறவன் உலகளந்தான் - சோழப் பேரரசின் தலைமை நில அளவைத் துறை இயக்குநர்",
        "era": "Imperial Chola Era",
        "year_start": 990,
        "year_end": 1014,
        "thinai": "Marutham",
        "summary_en": "Chief royal surveyor who directed the nationwide cadastral land survey under Rajaraja Chola I, systematically measuring agrarian plots across South India.",
        "summary_ta": "முதலாம் இராசராச சோழனின் ஆணைப்படி தமிழகமெங்கும் நிலங்களை அளந்து வரிக்கணக்குகளை முறைப்படுத்திய சோழப் பேரரசின் தலைமை நில அளவை அதிகாரி.",
        "content": """# Kuravan Ulagalandan (குறவன் உலகளந்தான்)

**Title**: Chief Royal Cadastral Officer (*நிலமளந்த பெருமான்*).  
"""
    },
    {
        "category": "places",
        "slug": "place-thanjavur-royal-survey-archives",
        "file": "place-thanjavur-royal-survey-archives.md",
        "node_type": "place",
        "name_en": "Thanjavur Nilam-Alappu Office: Imperial Cadastral Land Registry Archives",
        "name_ta": "தஞ்சாவூர் நில அளவைப் பதிவகம் - சோழர் அரசு ஆவணக் காப்பகம் மற்றும் வரைபடப் பிரிவு",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The administrative land revenue registry (Vari-p-poththagam) in Thanjavur palace complex (10.7870° N, 79.1378° E) where cadastral survey maps, palm-leaf title deeds, and tax assessments were maintained.",
        "summary_ta": "தஞ்சைப் பேரரசு அரண்மனை வளாகத்தில் இயங்கிய நில அளவைப் பதிவகம் (10.7870° N, 79.1378° E). நிலங்களின் எல்லை வரைபடங்கள் மற்றும் வரிப்பொத்தகம் ஓலைக்கட்டுகள் பாதுகாக்கப்பட்ட தலைமை ஆவணக் காப்பகம்.",
        "content": """# Thanjavur Royal Survey Archives (தஞ்சாவூர் நில ஆவணக் காப்பகம்)

**Coordinates**: 10.7870° N, 79.1378° E.  
"""
    },

    # --------------------------------------------------------------------------
    # CORPUS 3: ANCIENT TAMIL LEGAL SYSTEMS, VILLAGE ASSEMBLIES & JUDICIARY
    # --------------------------------------------------------------------------
    {
        "category": "texts",
        "slug": "text-thirukkural-porutpal-jurisprudence",
        "file": "text-thirukkural-porutpal-jurisprudence.md",
        "node_type": "text",
        "name_en": "Thirukkural Porutpal: Canonical Jurisprudence, Sengol Impartial Justice & Penal Law",
        "name_ta": "திருக்குறள் பொருட்பால் - அறநெறிச் சட்டம், செங்கோன்மை மற்றும் நீதி பரிபாலனம்",
        "era": "Sangam Classical Era",
        "year_start": -300,
        "year_end": 100,
        "thinai": "Marutham",
        "summary_en": "The jurisprudence chapters of Thirukkural: Sengonmai (Righteous Scepter / Rule of Law), Kodunkonmai (Tyranny), and Iraimatsthi, establishing that sovereign authority and state stability derive entirely from impartial judicial equity.",
        "summary_ta": "திருவள்ளுவரின் பொருட்பாலில் அமைந்துள்ள செங்கோன்மை, கொடுங்கோன்மை, இறைமாட்சி முதலான அதிகாரங்கள். 'ஓர்ந்துகண் ணோடாது இறைபுரிந்து யார்மாட்டும் தேர்ந்துசெய் வஃதே முறை' எனச் சட்டத்தின் முன் அனைவரும் சமம் என்ற சமநீதிக் கோட்பாட்டை வகுத்தளிக்கும் அறநெறிச் சட்டம்.",
        "content": """# Thirukkural: Classical Jurisprudence & Rule of Law (செங்கோன்மை)

**Author**: Thiruvalluvar (*திருவள்ளுவர்*).  
**Key Chapters**: *Sengonmai* (Righteous Rule), *Kodunkonmai* (Tyranny), *Neethi* (Justice).  
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-chola-penal-justice-dharmasana",
        "file": "insc-chola-penal-justice-dharmasana.md",
        "node_type": "inscription",
        "name_en": "Chola Inscriptional Judiciary: Dharmasana Court Tribunals, Fines & Restitution",
        "name_ta": "சோழர் குற்றவியல் நீதிமன்றக் கல்வெட்டுகள் - தர்மசனம், தண்டம் மற்றும் இழப்பீட்டு நீதி",
        "era": "Imperial Chola Era",
        "year_start": 950,
        "year_end": 1150,
        "thinai": "Marutham",
        "summary_en": "Inscriptions documenting trials for accidental manslaughter, boundary disputes, and corruption. Demonstrates restorative justice where accidental killers were sentenced to endow perpetual temple lamps (Nanda-vilakku) rather than capital vengeance.",
        "summary_ta": "சோழர் கால குற்றவியல் நீதிமன்ற ஆவணங்கள். தற்செயலான மரணங்களுக்கும் திட்டமிட்ட கொலைகளுக்கும் உள்ள சட்ட வேறுபாடுகள், மற்றும் குற்றவாளிகள் பழிவாங்கும் தண்டனைக்கு மாறாக பாதிக்கப்பட்ட குடும்பங்களின் ஆன்ம நலனுக்காக நந்தா விளக்குகள் எரிக்கப் பொன் செலுத்தும் இழப்பீட்டு நீதிமுறை.",
        "content": """# Chola Penal Justice & Restitution (தர்மசனம்)

**Judicial Body**: *Dharmasana* Court presided over by *Dharmasana-Bhattas*.  
**Legal Philosophy**: Restorative justice, fines (*Dhandam*), and ritual restitution.  
"""
    },
    {
        "category": "inscriptions",
        "slug": "insc-brahmadesam-chola-panchavara-variyam",
        "file": "insc-brahmadesam-chola-panchavara-variyam.md",
        "node_type": "inscription",
        "name_en": "Brahmadesam Inscription: 5-Fold Executive Governance & Judicial Oversight",
        "name_ta": "பிரம்மதேசம் கல்வெட்டு - பஞ்சவார வாரியம் மற்றும் நீதிபரிபாலனக் குழு அமைப்பு",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1010,
        "thinai": "Marutham",
        "summary_en": "Epigraph from Brahmadesam detailing the constitution of the Panchavara-Variyam (special executive audit and judicial arbitration committee) empowered to audit village accounts, resolve boundary disputes, and ensure electoral compliance.",
        "summary_ta": "பிரம்மதேசம் கோயில் கல்வெட்டு. கிராம சபையின் நிர்வாகக் குழுவான 'பஞ்சவார வாரியம்' வரிவிதிப்பு, கணக்குத் தணிக்கை, மற்றும் எல்லைத் தகராறுகளை விசாரித்துத் தீர்ப்பு வழங்கும் அதிகாரம் பெற்றிருந்ததை விவரிக்கும் வரலாற்று ஆவணம்.",
        "content": """# Brahmadesam Panchavara-Variyam Inscription

**Location**: Brahmadesam Temple.  
**Administrative Board**: *Panchavara-Variyam* (Executive Audit & Arbitration Board).  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-kudavolai-pot-ticket-electoral-system",
        "file": "concept-kudavolai-pot-ticket-electoral-system.md",
        "node_type": "concept",
        "name_en": "Kudavolai: Blindfolded Boy Drawing of Palm-Leaf Ballots & Electoral Democracy",
        "name_ta": "குடவோலை முறை - பானையில் ஓலைச்சீட்டு இட்டு சிறுவன் மூலம் தேர்ந்தெடுக்கும் மக்களாட்சி",
        "era": "Early Medieval to Imperial Chola Era",
        "year_start": 800,
        "year_end": 1200,
        "thinai": "Marutham",
        "summary_en": "Documented secret-ballot ward election system. 30 village wards nominated eligible candidates written on palm leaves, tied in bundles, deposited in an earthen pot, and drawn by a young boy in public view before the assembly.",
        "summary_ta": "பண்டைத் தமிழகத்தின் ஜனநாயகத் தேர்தல் முறைமை. 30 குடும்புகளிலிருந்து தகுதியுள்ள வேட்பாளர்களின் பெயர்கள் ஓலைகளில் எழுதப்பட்டு, குடத்தில் இடப்பட்டு, சிறுவன் ஒருவனால் குலுக்கல் முறையில் வெளிப்படையாக எடுக்கப்பட்டுத் தலைவர்கள் தேர்ந்தெடுக்கப்பட்ட முறை.",
        "content": """# Kudavolai Electoral System (குடவோலை முறை)

**Democratic Mechanism**: Secret palm-leaf ballot (*Olai-cheettu*), sealed pot (*Kudam*), innocent child draw.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-variyam-standing-committee-governance",
        "file": "concept-variyam-standing-committee-governance.md",
        "node_type": "concept",
        "name_en": "Variyam Governance: Eri-Variyam (Tanks), Thotta-Variyam (Gardens) & Panchavara-Variyam",
        "name_ta": "வாரிய ஆட்சி முறைமை - ஏரி வாரியம், தோட்ட வாரியம் மற்றும் பஞ்சவார வாரியத் தொழிற்பாடுகள்",
        "era": "Pallava to Imperial Chola Era",
        "year_start": 750,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The committee system administering autonomous village republics: Samvatsara-Variyam (Annual Council), Eri-Variyam (Tank & Water), Thotta-Variyam (Gardens), Pon-Variyam (Treasury), and Panchavara-Variyam (Audit).",
        "summary_ta": "கிராம தன்னாட்சி நிர்வாகத்தை வழிநடத்திய சிறப்பு வாரியங்கள்: ஆண்டு வாரியம் (சம்வத்ஸர வாரியம்), ஏரி வாரியம், தோட்ட வாரியம், பொன் வாரியம் மற்றும் பஞ்சவார வாரியம்.",
        "content": """# Variyam Committee Governance (வாரிய ஆட்சி முறை)

**Committees**: *Samvatsara-Variyam*, *Eri-Variyam*, *Thotta-Variyam*, *Pon-Variyam*, *Panchavara-Variyam*.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-sengol-sovereign-rule-of-law",
        "file": "concept-sengol-sovereign-rule-of-law.md",
        "node_type": "concept",
        "name_en": "Sengol Jurisprudence: The Royal Scepter of Dharma & Judicial Equity",
        "name_ta": "செங்கோன்மை - தமிழரின் அறநெறிச் செங்கோல் மற்றும் சட்டத்தின் மாட்சிமை",
        "era": "Sangam to Imperial Chola Era",
        "year_start": -500,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The sacred civilizational symbol of sovereignty in Tamil political philosophy. Represents the Sengol (Straight Scepter) symbolizing unbending, impartial justice without fear or favor, contrasted with the Kodunkol of tyranny.",
        "summary_ta": "தமிழர் அரசமைப்பின் அறவழிக் கோட்பாடான செங்கோன்மை. மன்னனின் ஆணைக்கு மேலாக நீதி மற்றும் அறத்தின் மேன்மையை உணர்த்தும் செங்கோல்; நேரிய நடுநிலைமை தவறாத ஆட்சியின் அடையாளம்.",
        "content": """# Sengol Jurisprudence (செங்கோன்மை)

**Core Philosophy**: Justice unbent by favor or fear; the moral supremacy of the rule of law.  
"""
    },
    {
        "category": "concepts",
        "slug": "concept-ur-and-sabhai-village-republics",
        "file": "concept-ur-and-sabhai-village-republics.md",
        "node_type": "concept",
        "name_en": "Ur, Sabhai & Nagaram: Autonomy, Communal Landholding & Dispute Settlement",
        "name_ta": "ஊர், சபை மற்றும் நகரம் - தன்னாட்சி பெற்ற கிராமக் குடியரசுகள் மற்றும் நீதி நிர்வாகம்",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1300,
        "thinai": "Marutham",
        "summary_en": "The three-tier local assembly framework of Tamilakam: Ur (general agrarian assembly), Sabhai / Mahasabha (scholarly assembly), and Nagaram (mercantile guild assembly), functioning as autonomous local republics.",
        "summary_ta": "பண்டைத் தமிழகத்தின் முப்பெரும் தன்னாட்சி அமைப்புகள்: அனைத்து நில உரிமையாளர்களும் கூடிய 'ஊர்', கற்றறிந்த அறிஞர்களின் 'சபை' (மகாசபை), மற்றும் வணிகர்களின் நகரக் கூட்டமைப்பான 'நகரம்'.",
        "content": """# Ur, Sabhai & Nagaram: Village Republics (ஊரும் சபையும்)

**Three Assemblies**:
1. *Ur*: Agrarian village council.
2. *Sabhai*: Brahmadeya assembly.
3. *Nagaram*: Merchant trading guild council.
"""
    },
    {
        "category": "characters",
        "slug": "char-parantaka-chola-i-constitutionalist",
        "file": "char-parantaka-chola-i-constitutionalist.md",
        "node_type": "character",
        "name_en": "Parantaka Chola I: Monarch of the Immortal Uttiramerur Electoral Charters",
        "name_ta": "முதலாம் பராந்தக சோழன் - உத்திரமேரூர் மக்களாட்சி சாசனங்களை நிலைநாட்டிய வேந்தன்",
        "era": "Imperial Chola Era",
        "year_start": 907,
        "year_end": 955,
        "thinai": "Marutham",
        "summary_en": "Chola monarch (Maduraikondan) whose royal edicts in 919 and 921 CE at Uttiramerur codified the definitive village constitutional laws, anti-corruption clauses, term limits, and the Kudavolai voting process.",
        "summary_ta": "மதுரை கொண்ட முதலாம் பராந்தக சோழன். உத்திரமேரூர் வைகுண்டப் பெருமாள் கோயில் கல்வெட்டுகளில் மக்களாட்சி முறைமைகளையும் ஊழல் எதிர்ப்புக் கட்டுப்பாடுகளையும் கல்வெட்டாகப் பொறித்த சட்ட மாமன்னன்.",
        "content": """# Parantaka Chola I (முதலாம் பராந்தக சோழன்)

**Historic Edicts**: Uttiramerur Inscriptions of 919 & 921 CE.  
"""
    },
    {
        "category": "characters",
        "slug": "char-manur-sabhai-nyayathipathi",
        "file": "char-manur-sabhai-nyayathipathi.md",
        "node_type": "character",
        "name_en": "Manur Sabhai Dharmadhyaksha: Early Pandyan Village Magistrate & Jurist",
        "name_ta": "மானூர் சபை தர்மவாதி - பாண்டியர் கால கிராம நீதித்துறை நடுவர்",
        "era": "Early Medieval Pandyan Era",
        "year_start": 800,
        "year_end": 850,
        "thinai": "Marutham",
        "summary_en": "Judicial presiding officer of the ancient Pandyan Mahasabha at Manur, responsible for interpreting property title deeds, civil dispute resolution, and enforcing the 800 CE assembly participation edict.",
        "summary_ta": "மானூர் அம்பலவாணசுவாமி கோயில் கல்வெட்டில் குறிப்பிடப்படும் பாண்டியர் கால கிராம நீதிபதி; நில உரிமைச் சாசனங்களையும் மக்களாட்சி சபை நெறிமுறைகளையும் பரிபாலித்த தலைமை நீதி அதிகாரி.",
        "content": """# Manur Sabhai Dharmadhyaksha (மானூர் சபை தர்மவாதி)

**Role**: Judicial arbitrator and assembly administrator in 800 CE Pandyan territory.  
"""
    },
    {
        "category": "places",
        "slug": "place-thanjavur-dharmasana-court",
        "file": "place-thanjavur-dharmasana-court.md",
        "node_type": "place",
        "name_en": "Thanjavur Dharmasana High Court & Court of Arbitration",
        "name_ta": "தஞ்சாவூர் தர்மசனம் - சோழப் பேரரசின் உயர்நீதிமன்றம் மற்றும் நடுவர் மன்றம்",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1250,
        "thinai": "Marutham",
        "summary_en": "The supreme judicial court of the Imperial Chola capital (10.7870° N, 79.1378° E), presided over by Dharmasana-Bhattas who adjudicated inter-village disputes, treason cases, and appeals.",
        "summary_ta": "சோழப் பேரரசின் தலைநகரில் இயங்கிய தலைமை உயர்நீதிமன்ற வளாகம் (10.7870° N, 79.1378° E). தர்மசனப் பட்டர்களால் வழிநடத்தப்பட்டு கிராம சபைகளின் மேல்முறையீடுகளை விசாரித்த உயர்நீதிப் பீடம்.",
        "content": """# Thanjavur Dharmasana Court (தஞ்சாவூர் தர்மசனம்)

**Coordinates**: 10.7870° N, 79.1378° E.  
"""
    },
    {
        "category": "places",
        "slug": "place-manur-pandyan-assembly-site",
        "file": "place-manur-pandyan-assembly-site.md",
        "node_type": "place",
        "name_en": "Manur: Ancient Pandyan Democratic Assembly Township",
        "name_ta": "மானூர் - பாண்டியர் கால மக்களாட்சி சபை விளங்கிய வரலாற்றுத் தளம்",
        "era": "Early Medieval Pandyan Era",
        "year_start": 750,
        "year_end": 1000,
        "thinai": "Marutham",
        "summary_en": "Historic township in Tirunelveli district (8.8333° N, 77.6500° E) where the Ambalavanaswami temple plinth preserves the monumental 800 CE inscription outlining qualifications for democratic village assembly membership.",
        "summary_ta": "திருநெல்வேலி மாவட்டத்தில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க மானூர் திருத்தலம் (8.8333° N, 77.6500° E). உத்திரமேரூர் கல்வெட்டுக்கு ஒரு நூற்றாண்டுக்கு முன்பே கி.பி. 800-இல் கிராம சபைக்கான தகுதிகளை வகுத்த அம்பலவாணசுவாமி கல்வெட்டு அமைந்துள்ள தளம்.",
        "content": """# Manur Assembly Site (மானூர்)

**Coordinates**: 8.8333° N, 77.6500° E.  
**Historical Glory**: Discovery site of the 800 CE Pandyan democratic sabha charter.  
"""
    }
]

# ==============================================================================
# EDGES DEFINITION (Relational Cross-Domain Links)
# ==============================================================================
EDGES = [
    # Philosophy Edges
    (
        "text-manimekalai-samaya-kanakkar-epistemology",
        "codifies_pramana_vada",
        "concept-pramana-vada-tamil-epistemology",
        "relational",
        "Sangam Post-Classical Era",
        "Manimekalai Canto 27 details Buddhist Pramana-Vada and the refutation of rival schools.",
        "Manimekalai Canto 27"
    ),
    (
        "text-manimekalai-samaya-kanakkar-epistemology",
        "expounds_dependent_origination",
        "concept-anatta-and-pratityasamutpada-manimekalai",
        "relational",
        "Sangam Post-Classical Era",
        "Aravana Adigal expounds the 12-link chain of Bhavachakra in Canto 30.",
        "Manimekalai Canto 30"
    ),
    (
        "text-sivajnana-bodham-saiva-metaphysics",
        "systematizes_tripartite_ontology",
        "concept-pathi-pasu-paasa-triad",
        "relational",
        "Imperial Chola Era",
        "Meikandar formulates the 12 sutras defining Pathi, Pasu, and Paasa.",
        "Sivajnana Bodham Sutras"
    ),
    (
        "text-tolkappiyam-meyppattiyal-aesthetics",
        "formalizes_aesthetic_psychology",
        "concept-meyppadu-eightfold-aesthetic-emotions",
        "relational",
        "Sangam Classical Era",
        "Tolkappiyar classifies the 8 primary somatic emotional states.",
        "Tolkappiyam Porulatikaram Meyppattiyal"
    ),
    (
        "char-seethalai-sathanar-philosopher-poet",
        "authored_dialectical_epic",
        "text-manimekalai-samaya-kanakkar-epistemology",
        "relational",
        "Sangam Post-Classical Era",
        "Seethalai Sathanar composed the epic Manimekalai with its philosophical cantos.",
        "Manimekalai Epic"
    ),
    (
        "char-meikandar-epistemological-reformer",
        "authored_treatise_at",
        "place-thiruvennainallur-meikandar-ashram",
        "relational",
        "Imperial Chola Era",
        "Meikandar formulated Sivajnana Bodham at his ashram in Thiruvennainallur.",
        "Saiva Siddhanta Hagiography"
    ),
    (
        "char-aravanavadigal-buddhist-preceptor",
        "taught_at_vihara",
        "place-kanchipuram-buddhist-dialectical-vihara",
        "relational",
        "Sangam Post-Classical Era",
        "Aravana Adigal presided as abbot over the Buddhist dialectical school in Kanchi.",
        "Manimekalai & Chinese Pilgrimage Records"
    ),

    # Mathematics Edges
    (
        "text-kanakkathikaram-kari-nayanar",
        "documents_fractional_arithmetic",
        "concept-tamil-micro-fractional-mathematics",
        "relational",
        "Early Medieval Classical Era",
        "Kanakkathikaram explains calculations using Immi, Mundri, and Kaani fractions.",
        "Kanakkathikaram verses"
    ),
    (
        "insc-thanjavur-land-survey-metrology",
        "applies_cadastral_system",
        "concept-chola-land-survey-standardization",
        "relational",
        "Imperial Chola Era",
        "Thanjavur plinth inscriptions record measurements using the Ulagalandan-kol.",
        "Thanjavur Temple Inscriptions (SII Vol II)"
    ),
    (
        "concept-chola-land-survey-standardization",
        "archived_at_registry",
        "place-thanjavur-royal-survey-archives",
        "relational",
        "Imperial Chola Era",
        "Cadastral land surveys were registered in the Vari-p-poththagam office at Thanjavur.",
        "Chola Revenue Inscriptions"
    ),
    (
        "char-rajaraja-nilam-alandha-senapathi",
        "directed_survey_from",
        "place-thanjavur-royal-survey-archives",
        "relational",
        "Imperial Chola Era",
        "Kuravan Ulagalandan directed the empire-wide cadastral survey operations.",
        "Thanjavur Temple Edicts"
    ),
    (
        "char-kari-nayanar-mathematician",
        "authored_mathematical_canon",
        "text-kanakkathikaram-kari-nayanar",
        "relational",
        "Early Medieval Era",
        "Kari Nayanar composed the definitive practical arithmetic manual.",
        "Kanakkathikaram"
    ),

    # Legal & Democratic Systems Edges
    (
        "text-thirukkural-porutpal-jurisprudence",
        "defines_rule_of_law",
        "concept-sengol-sovereign-rule-of-law",
        "relational",
        "Sangam Classical Era",
        "Thirukkural establishes the concept of Sengonmai as supreme impartial governance.",
        "Thirukkural Porutpal"
    ),
    (
        "insc-chola-penal-justice-dharmasana",
        "adjudicated_by_tribunal",
        "place-thanjavur-dharmasana-court",
        "relational",
        "Imperial Chola Era",
        "Judicial trials for accidental manslaughter and boundary disputes at Dharmasana.",
        "Chola Inscriptional Corpus"
    ),
    (
        "concept-kudavolai-pot-ticket-electoral-system",
        "practiced_in_elections",
        "insc-uttiramerur-kudavolai",
        "relational",
        "Early Medieval to Imperial Chola Era",
        "Kudavolai secret-ballot ward system detailed in Parantaka I's edicts.",
        "Uttiramerur Temple Inscriptions"
    ),
    (
        "concept-variyam-standing-committee-governance",
        "governed_village_republics",
        "concept-ur-and-sabhai-village-republics",
        "relational",
        "Pallava to Imperial Chola Era",
        "Standing committee (Variyam) structure enabled autonomy of Ur and Sabhai.",
        "South Indian Inscriptions"
    ),
    (
        "char-parantaka-chola-i-constitutionalist",
        "sanctioned_constitutional_charters",
        "insc-uttiramerur-kudavolai",
        "relational",
        "Imperial Chola Era",
        "Parantaka I issued the 919 and 921 CE constitutional electoral edicts at Uttiramerur.",
        "Uttiramerur Edicts of Parantaka I"
    ),
    (
        "char-manur-sabhai-nyayathipathi",
        "enforced_charter_at",
        "place-manur-pandyan-assembly-site",
        "relational",
        "Early Medieval Pandyan Era",
        "Village magistrate administered the 800 CE assembly qualification rules at Manur.",
        "Manur Inscription (ARE 423 of 1906)"
    ),
    (
        "place-manur-pandyan-assembly-site",
        "discovery_site_of_edict",
        "insc-manur-sabha-rules",
        "relational",
        "Early Medieval Pandyan Era",
        "The Ambalavanaswami temple at Manur preserves the democratic sabha charter.",
        "Epigraphia Indica Vol XXII"
    )
]

def main():
    print("=" * 80)
    print("🚀 TRIPLE CIVILIZATIONAL EXPANSION HARVESTER (BATCH 2)")
    print("   1. Ancient Tamil Philosophy, Epistemology & Dialectics (13)")
    print("   2. Ancient Tamil Mathematics, Metrology & Fractions (10)")
    print("   3. Ancient Tamil Legal Systems, Village Assemblies & Judiciary (11)")
    print("   TOTAL: 34 Canonical Dossiers | 68 Dense Vector Embeddings")
    print("=" * 80)

    # Phase 1: Write Canonical Markdown Dossiers
    print("\n[Phase 1] Writing 34 Canonical Markdown Dossiers to Moolam Chronicles...")
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

    print("\n[Phase 2] Upserting 34 Lore Nodes into PostgreSQL...")
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
    print("\n[Phase 4] Generating 68 Dense 1024-dim BGE-M3 Embeddings into rag_chunks...")
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
