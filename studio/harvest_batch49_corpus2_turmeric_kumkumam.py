#!/usr/bin/env python3
"""
Harvester: Batch 49 - Ancient Tamil Turmeric Rhizome Agronomy, Alkaline-Lime Kumkumam Chemistry & Auspicious Antiseptic Culture
Generated automatically.
"""

import os
import json
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"
DOSSIER_DIR = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

# The knowledge tree uses real English plurals ("technologies", not "technologys").
CATEGORY_DIRS = {
    "technology": "technologies",
    "archaeology": "archaeology",
    "history": "history",
    "science": "science",
}


def category_dir(category: str) -> str:
    return CATEGORY_DIRS.get(category, category + "s")


DOSSIERS = [
    {
        "slug": "text-sangam-and-bhakti-literature-on-pasu-manjal-turmeric-pastes-and-festive-thresholds",
        "category": "text",
        "file": "text-sangam-and-bhakti-literature-on-pasu-manjal-turmeric-pastes-and-festive-thresholds.md",
        "name_en": "Sangam & Bhakti Literary References to Pasu-Manjal Rhizomes, Manjal-Chanthu & Threshold Festoons",
        "name_ta": "சங்க மற்றும் பக்தி இலக்கியங்களில் பசுமஞ்சள், மஞ்சள் சாந்து மற்றும் மங்கல நிலைப்படி தோரணக் குறிப்புகள்",
        "era": "Sangam to Bhakti Era",
        "year_start": -300,
        "year_end": 900,
        "thinai": "marutham",
        "summary_en": "Classical Tamil poetic accounts in Pattinappalai, Malaipadukadam, Nedunalvadai, Akananuru, and Tiruppavai describing lush turmeric gardens (manjal-patappai) in household backyards, grinding fresh turmeric with sandalwood into cooling pastes (manjal-chanthu), and hanging leafy turmeric stalks across auspicious doorways.",
        "summary_ta": "பட்டினப்பாலை, மலைபடுகடாம், நெடுநல்வாடை, அகநானூறு மற்றும் திருப்பாவை ஆகிய நூல்களில் வீட்டுத் தோட்டத்துப் பசுமஞ்சள், மஞ்சள் சாந்து மற்றும் நிலைப்படிகளில் கட்டப்படும் மஞ்சள் தோரணங்கள் பற்றிய இலக்கியச் சான்றுகள்.",
        "sources": [
            "Pattinappalai",
            "Malaipadukadam",
            "Nedunalvadai",
            "Akananuru",
            "Tiruppavai"
        ],
        "content": "# Sangam & Bhakti Literature on Pasu-Manjal, Fragrant Pastes & Festive Thresholds\n\nClassical Tamil literature portrays *manjal* (*Curcuma longa*) as both a ubiquitous *Marutham/Kurinji* kitchen-garden crop and the supreme emblem of domestic auspiciousness (*mangalam*) and antimicrobial purity:\n\n**Poetic & Textual Attestations (Cited by Title):**\n- **Pattinappalai & Malaipadukadam (Homestead Agronomy)**: Poems describe fertile *Marutham* and foothill *Kurinji* homesteads surrounded by broad-leaved green turmeric beds (*pasu-manjal*) intercropped with fragrant ginger (*inji*), sugarcane, and plantains, where shaded alluvial soil swells the aromatic underground fingers.\n- **Nedunalvadai & Akananuru (Cosmetic & Medicinal Pastes)**: Women grind fresh turmeric rhizomes with white mustard (*ven-kadugu*) and sandalwood on flat grinding stones to prepare *manjal-chanthu*, applied to the skin and doorway lintels to ward off damp monsoon chills and pestilence.\n- **Tiruppavai (Manjal-Neerattu)**: Bhakti hymns celebrate ceremonial turmeric-water lustration (*manjal-neer*) during sacred marriages and temple festivals."
    },
    {
        "slug": "concept-curcuma-longa-virali-and-kilangu-botany-curcuminoid-tautomerism-and-turmerone",
        "category": "concept",
        "file": "concept-curcuma-longa-virali-and-kilangu-botany-curcuminoid-tautomerism-and-turmerone.md",
        "name_en": "Curcuma longa Virali & Kilangu Rhizome Anatomy, Curcuminoid Keto-Enol Tautomerism & Turmerones",
        "name_ta": "விரலி மஞ்சள் மற்றும் கிழங்கு மஞ்சள் தாவரவியல், குர்குமின் (Curcumin) வேதியியலும் ஆவியாகும் எண்ணெய்களும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Botanical and phytochemical differentiation between primary mother bulbs (kilangu-manjal / kundu-manjal), lateral secondary fingers (virali-manjal) of Curcuma longa, and non-staining wild Curcuma aromatica (kasturi-manjal): diarylheptanoid curcuminoid pigments (3–5% curcumin), keto-enol tautomerism, and sesquiterpene ar-turmerone oils.",
        "summary_ta": "தாய் கிழங்கான குண்டு மஞ்சள், பக்கக் கிளைகளான விரலி மஞ்சள் மற்றும் கஸ்தூரி மஞ்சள் ஆகியவற்றின் தாவரவியல் வேறுபாடுகளும், குர்குமின் நிறமியின் கீட்டோ-ஈனால் (Keto-Enol) சமநிலை வேதியியலும்.",
        "sources": [
            "Phytochemistry and Pharmacology of Curcuma longa and Curcuma aromatica",
            "Siddha Materia Medica (Gunapadam: Manjal Vaguppu)",
            "Spices Board of India Agronomy Monograph on Erode Turmeric"
        ],
        "content": "# Curcuma longa Virali & Kilangu Botany, Curcuminoid Tautomerism & Turmerones\n\nTraditional Tamil agronomy and Siddha pharmacy classify underground turmeric rhizomes into distinct morphological and chemical grades:\n\n**1. Rhizome Morphology (*Kilangu vs Virali*):**\n- **Kilangu-Manjal / Kundu-Manjal (Mother Corms)**: The central ovate primary bulb from which aerial shoots emerge. Dense and starchy, it is preferred for seed propagation, rubbing on bath stones (*manjal-kallu*), and carving sacred *Manjal-Pillaiyar* icons.\n- **Virali-Manjal (Lateral Finger Rhizomes)**: Cylindrical, multibranched secondary and tertiary fingers ($6\\text{--}10\\text{ cm}$ long) containing the highest concentration of oleoresin cells and diarylheptanoid pigments—prized for culinary milling and medicinal decoctions.\n- **Kasturi-Manjal (*Curcuma aromatica*)**: Cream-colored wild rhizomes rich in camphoraceous sesquiterpenes (curzerenone and germacrone) with minimal curcumin ($<0.5\\%$), ensuring zero yellow staining on clothing.\n\n**2. Diarylheptanoid Curcuminoid Chemistry:**\n- *Erode Virali-Manjal* contains $3.5\\text{--}5.2\\%$ total **curcuminoids**—primarily **curcumin** (diferuloylmethane, $\\sim 75\\%$), **demethoxycurcumin** ($\\sim 18\\%$), and **bisdemethoxycurcumin** ($\\sim 7\\%$)—alongside $4\\text{--}6\\%$ volatile oil dominated by **ar-turmerone**, $\\alpha$-turmerone, and $\\beta$-turmerone.\n- In neutral and acidic media ($\\text{pH } 3\\text{--}7$), curcumin exists predominantly in its conjugated **bis-keto / enol tautomer**, absorbing blue-violet light at $\\lambda_{\\max} \\approx 420\\text{ nm}$ to reflect brilliant golden yellow."
    },
    {
        "slug": "concept-alkaline-lime-borax-deprotonation-chemistry-of-crimson-kungumam-transformation",
        "category": "concept",
        "file": "concept-alkaline-lime-borax-deprotonation-chemistry-of-crimson-kungumam-transformation.md",
        "name_en": "Alkaline-Lime & Borax Bathochromic Shift Chemistry: Transforming Golden Manjal into Crimson Kungumam",
        "name_ta": "மஞ்சளைச் சுண்ணாம்பு மற்றும் வெங்காரக் கார வினையால் செந்நிறக் குங்குமமாக மாற்றும் நிறமாற்ற வேதியியல்",
        "era": "Early Medieval to Modern Era",
        "year_start": 500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Molecular spectroscopy and acid-base coordination chemistry of traditional Tamil Kungumam (vermilion-free herbal kumkum) and scarlet Aarathi water: alkaline deprotonation of curcumin's phenolic and enolic hydroxyl groups by slaked lime Ca(OH)2 and borax Na2B4O7 shifts optical absorption from 420 nm yellow to 530 nm deep crimson.",
        "summary_ta": "மஞ்சளுடன் சுண்ணாம்பு நீர் (Ca(OH)2), வெங்காரம் (Borax) மற்றும் படிகாரம் சேர்க்கும்போது குர்குமின் மூலக்கூறின் புரோட்டான் நீக்க வினையால் மஞ்சள் நிறம் (420 nm) அடர் சிவப்புக் குங்குமமாக (530 nm) மாறும் நிறமாலை வேதியியல்.",
        "sources": [
            "Spectroscopic Analysis of Curcumin-Borax-Alkali Complexes (Rosocyanine & Rubrocurcumin)",
            "Traditional Kungumam Manufacturing Protocols of Tamil Nadu",
            "Siddha Inorganic-Organic Compounding (Vengaram & Sunnambu)"
        ],
        "content": "# Alkaline-Lime & Borax Bathochromic Chemistry of Crimson Kungumam\n\nUnlike northern cinnabar ($\\text{HgS}$) *sindoor*, authentic Tamil **Kungumam** (*Kumkumam*) is a $100\\%$ plant-mineral pigment synthesized by driving an alkaline bathochromic shift inside *Curcuma longa* starch granules:\n\n**1. Phenolic Deprotonation & $\\pi$-Conjugation Extension ($\\text{pH} > 8.5$):**\n- Curcumin possesses three ionizable protons: one enolic proton ($\\text{p}K_{a1} \\approx 8.3$) and two phenolic $-\\text{OH}$ protons ($\\text{p}K_{a2} \\approx 9.8, \\text{p}K_{a3} \\approx 10.5$).\n- When turmeric is steeped in an alkaline solution of **slaked lime** ($\\text{Ca(OH)}_2$, *sunnambu*) and **borax** ($\\text{Na}_2\\text{B}_4\\text{O}_7 \\cdot 10\\text{H}_2\\text{O}$, *vengaram*), hydroxide ions abstract the enolic and phenolic protons to form the poly-anionic phenolate species ($\\text{Cur}^{2-}$ / $\\text{Cur}^{3-}$).\n- Electron delocalization across the planar diarylheptadiene backbone narrows the $\\text{HOMO}\\rightarrow\\text{LUMO}$ energy gap, producing a dramatic **bathochromic (red) shift** from $\\lambda_{\\max} = 420\\text{ nm}$ (yellow) to $\\lambda_{\\max} = 525\\text{--}540\\text{ nm}$ (deep crimson).\n\n**2. Borate Chelation & Aarathi Prophylaxis:**\n- Tetrahedral borate anions from *vengaram* cross-link with curcumin's $\\beta$-diketone moiety (forming stable red rubrocurcumin-like chelates) while alum (*padikaram*) mordants the pigment onto starch grains. The same instantaneous reaction occurs when a bride or newborn is greeted with a platter of crimson **Aarathi** water (*manjal + sunnambu*)."
    },
    {
        "slug": "concept-auspicious-manjal-antiseptic-hygiene-mangalsutra-cord-dyeing-and-aarathi-prophylaxis",
        "category": "concept",
        "file": "concept-auspicious-manjal-antiseptic-hygiene-mangalsutra-cord-dyeing-and-aarathi-prophylaxis.md",
        "name_en": "Auspicious Manjal Antiseptic Hygiene, Manjal-Kayiru Mangalsutra Dyeing & Threshold Prophylaxis",
        "name_ta": "மங்கல மஞ்சள் கிருமிநாசினிப் பண்பாடு, தாலிக் கயிறு (மஞ்சள் கயிறு) சாயமேற்றல் மற்றும் நிலைப்படி காப்பு அறிவியல்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Biomedical and ethnographic rationale of Tamil turmeric rituals: bactericidal and insect-repellent action of curcumin and turmerones when smeared on wooden door thresholds (nilai-padi), transdermal antimicrobial protection from turmeric-dyed cotton mangalsutra cords (manjal-kayiru), and corner staining of auspicious invitations (manjal-pathirikkai).",
        "summary_ta": "நிலைப்படிகளில் மஞ்சள் பூசி எறும்பு மற்றும் கிருமிகளைத் தடுத்தல், கழுத்தில் அணியும் மஞ்சள் தாலிக்கயிற்றின் சருமப் பாதுகாப்பு, பொங்கல் பானையில் மஞ்சள் கொத்து கட்டுதல் மற்றும் மஞ்சள் நீராட்டின் தொற்றுநோய் எதிர்ப்பு அறிவியல்.",
        "sources": [
            "Antimicrobial and Insecticidal Properties of Curcuma longa Essential Oils",
            "Ethnography of Auspicious Substances (Mangala-Porul) in Tamil Culture",
            "Siddha Preventive Hygiene & Postpartum Care"
        ],
        "content": "# Auspicious Manjal Antiseptic Hygiene, Manjal-Kayiru Dyeing & Threshold Prophylaxis\n\nIn Tamil domestic architecture and life-cycle rites, every ritual deployment of *manjal* doubles as a targeted antimicrobial or entomological barrier:\n\n**1. Architectural Threshold Sanitization (*Nilai-Padi Manjal*):**\n- Wooden doorframes and bottom sills (*nilai-padi*) of Tamil homes are washed every Tuesday and Friday with wet *virali-manjal* paste and dotted with *kungumam*. **Ar-turmerone** and **curlone** volatile oils act as potent contact repellents against foraging ants, termites (*karaiyan*), and silverfish, while curcumin inhibits soil-borne *Staphylococcus* and dermatophytic fungi tracked indoors on bare feet.\n\n**2. Manjal-Kayiru (Turmeric-Dyed Mangalsutra & Wrist Cords):**\n- The traditional Tamil wedding necklace (*thaali*) is strung not on metal chains alone, but on a 9- or 108-strand raw cotton cord (*manjal-kayiru*) saturated in fresh turmeric paste and renewed regularly by married women. Resting continuously against the warm, perspiring skin of the cervical/vagal groove and sternum, trace curcuminoids leach into sweat to prevent contact dermatitis and follicular infections.\n\n**3. Manjal-Kothu & Manjal-Neerattu:**\n- Tying fresh uprooted turmeric plants (*manjal-kothu*) around the neck of boiling *Pongal* clay pots releases steam-distilled turmerones into the kitchen air during the winter-to-spring seasonal transition (*Thai*)."
    },
    {
        "slug": "technology-manjal-kopparai-alkaline-boiling-starch-gelatinization-and-rotary-polishing",
        "category": "technology",
        "file": "technology-manjal-kopparai-alkaline-boiling-starch-gelatinization-and-rotary-polishing.md",
        "name_en": "Manjal-Kopparai Alkaline Rhizome Boiling, Starch Gelatinization & Rotary Drum Polishing",
        "name_ta": "மஞ்சள் கொப்பரை அவித்தல், மாவுச்சத்து கூழாக்கம், வெயிலில் உலர்த்தல் மற்றும் உருளை மெருகேற்றும் தொழில்நுட்பம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Post-harvest thermal and mechanical curing engineering of turmeric rhizomes: boiling washed green fingers and bulbs in perforated troughs (manjal-kopparai) with mildly alkaline water at 95–100°C to gelatinize starch and diffuse curcumin uniformly, 15-day sun-drying on drying yards to 8% moisture, and hexagonal drum polishing.",
        "summary_ta": "பச்சை மஞ்சள் கிழங்குகளைப் பிரித்து, கொப்பரைகளில் கார நீரில் வேகவைத்து மாவுச்சத்தைக் கூழாக்கி, 15 நாட்கள் வெயிலில் உலர்த்தி உலோக ஒலி வரும் வரை காயவைத்து, சுழல் உருளையில் மெருகேற்றும் தொழில்நுட்பம்.",
        "sources": [
            "Post-Harvest Technology of Turmeric (Tamil Nadu Agricultural University)",
            "Erode Turmeric Geographical Indication Technical Dossier",
            "Traditional Agricultural Processing in Kongu Nadu"
        ],
        "content": "# Manjal-Kopparai Alkaline Boiling, Starch Gelatinization & Rotary Polishing\n\nRaw dug turmeric rhizomes ($75\\text{--}80\\%$ moisture) cannot be dried directly in the sun without shriveling into pale, corky, insect-prone roots; their prized vitreous orange core and metallic ring are engineered through a four-stage post-harvest curing sequence:\n\n**1. Alkaline Vat Boiling (*Manjal-Avithal / Kopparai Boiling*):**\n- Separated *virali* fingers and *kilangu* bulbs are loaded into perforated galvanized-iron or terracotta troughs (*manjal-kopparai*) immersed in wide rectangular masonry boilers fired with dried turmeric leaves and agricultural husk.\n- **Alkaline Chemistry**: The boiling water is made mildly alkaline ($\\text{pH } 8.0\\text{--}8.5$, traditionally using a strained slurry of fresh cow dung and lime water, or $0.1\\%$ sodium bicarbonate). Boiling for $45\\text{--}60\\text{ minutes}$ until white froth appears and a pressed broomstick pierces the core easily accomplishes three transformations: (a) kills viable vegetative buds, (b) gelatinizes intracellular starch into a translucent matrix, and (c) ruptures localized oleoresin cells so orange-red curcuminoids diffuse evenly throughout the rhizome cross-section.\n\n**2. Sun-Drying & Rotary Drum Polishing (*Manjal-Theippu*):**\n- Boiled fingers are spread $5\\text{--}7\\text{ cm}$ thick on drying yards (*kalam*) for 12–15 days until moisture drops below $8\\text{--}10\\%$ and snapping a finger yields a crisp metallic click.\n- Dried rough fingers are tumbled inside hand-cranked perforated octagonal iron drums (*polishing urulai*) to abrade scaly rootlets and cork skin, then lightly dusted with a dilute turmeric-water emulsion to impart a smooth, golden-yellow protective skin."
    },
    {
        "slug": "technology-thaazhampoo-kungumam-vat-steeping-sun-evaporation-and-sesame-oil-stabilization",
        "category": "technology",
        "file": "technology-thaazhampoo-kungumam-vat-steeping-sun-evaporation-and-sesame-oil-stabilization.md",
        "name_en": "Thaazhampoo Kungumam Vat Steeping, Solar Crystallization, Stone Milling & Gingelly Oil Conditioning",
        "name_ta": "தாழம்பூ குங்குமம் தயாரிப்பு: எலுமிச்சை-வெங்காரம்-சுண்ணாம்பு ஊறவைத்தல், சூரிய உலர்த்தல் மற்றும் நல்லெண்ணெய்ப் பக்குவம்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Traditional craft protocol for manufacturing temple-grade Thaazhampoo Kungumam: soaking split turmeric fingers in ceramic vats with lemon juice, borax (vengaram), alum (padikaram), and slaked-lime supernatant over 20 days of solar evaporation, stone-grinding the crimson cores, infusing Pandanus (thaazhampoo) distillate, and conditioning with gingelly oil.",
        "summary_ta": "நறுக்கிய மஞ்சள் துண்டுகளை எலுமிச்சைச் சாறு, வெங்காரம், படிகாரம் மற்றும் சுண்ணாம்புத் தெளிவு நீரில் 20 நாட்கள் ஊறவைத்து வெயிலில் உலர்த்தி, இடித்துத் தாழம்பூ தைலம் மற்றும் நல்லெண்ணெய் சேர்த்துக் குங்குமம் செய்யும் தொழில்நுட்பம்.",
        "sources": [
            "Temple Cottage Industries of Madurai, Thiruvanaikaval & Kanchipuram",
            "Traditional Cosmetics & Ritual Powders of Tamil Nadu",
            "Craft Documentation of Herbal Kumkum Making"
        ],
        "content": "# Thaazhampoo Kungumam Vat Steeping, Solar Evaporation & Oil Conditioning\n\nAuthentic temple *Kungumam*—free of synthetic azo dyes or lead/mercury pigments—is manufactured through a slow, 25-day solid-state chemical infusion and milling process:\n\n**1. Multi-Bath Acid-to-Alkali Steeping:**\n- Cured *kilangu-manjal* and *virali-manjal* pieces are chopped into pea-sized grits and placed in wide earthenware vats (*மண் தொட்டி*).\n- **Stage A (Mordanting)**: A solution of freshly squeezed sour lime juice (*elumichai-charu*), powdered alum (*padikaram*), and borax (*vengaram*) is poured over the turmeric grits to swell the starch pores and complex the $\\beta$-diketone sites.\n- **Stage B (Alkaline Color Development)**: Decanted supernatant of slaked shell-lime (*கிளிஞ்சல் சுண்ணாம்புத் தெளிவு*) is added incrementally while the vats are stirred twice daily under hot sunlight for 15 to 20 days. As the liquid slowly evaporates and penetrates to the center of each grit, the yellow turmeric core transforms completely into brittle, dark-maroon nuggets.\n\n**2. Stone Milling, Thaazhampoo Scenting & Oil Stabilization:**\n- The bone-dry maroon nuggets are pounded in stone mortars (*ural*) or burr mills and sifted through silk mesh.\n- Artisans mist the powder with hydro-distilled screw-pine flower water (*thaazhampoo-theeneer*, *Pandanus odorifer*) and *pachai-karpooram*, then knead in $1\\text{--}2\\%$ cold-pressed *nallenai* (gingelly oil) or ghee, which coats the pigment particles so the *kungumam* adheres smoothly to the forehead (*நெற்றித் திலகம்*) without dusting or fading."
    },
    {
        "slug": "artifact-virali-manjal-fingers-kundu-manjal-bulbs-manjal-kayiru-cords-and-pongal-kothu",
        "category": "artifact",
        "file": "artifact-virali-manjal-fingers-kundu-manjal-bulbs-manjal-kayiru-cords-and-pongal-kothu.md",
        "name_en": "Erode Virali-Manjal Fingers, Kundu-Manjal Corms, Manjal-Kayiru Cords & Pongal Manjal-Kothu",
        "name_ta": "ஈரோடு விரலி மஞ்சள், குண்டு மஞ்சள், மஞ்சள் தாலிக்கயிறு மற்றும் பொங்கல் மஞ்சள் கொத்துத் தொகுப்புகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Material typology of cured and fresh turmeric artifacts in Tamil domestic and ritual life: dense golden Erode Virali-Manjal fingers, conical Kundu-Manjal corms, turmeric-dyed nine-strand cotton Manjal-Kayiru mangalsutra and kappu threads, and freshly harvested leafy Manjal-Kothu stalks tied to Pongal pots.",
        "summary_ta": "தமிழர் இல்லற மற்றும் சடங்குப் பயன்பாட்டுப் பொருட்கள்: உலோக ஒலி எழுப்பும் ஈரோடு விரலி மஞ்சள், குண்டு மஞ்சள், ஒன்பது புரி மஞ்சள் தாலிக்கயிறு, காப்பு நூல் மற்றும் தைப்பொங்கல் பானையில் கட்டப்படும் பச்சை மஞ்சள் கொத்து.",
        "sources": [
            "Geographical Indication Registry: Erode Manjal Specification",
            "Folklore and Ritual Material Culture of Tamil Nadu",
            "Ethnobotany of Harvest Festivals in South India"
        ],
        "content": "# Virali-Manjal Fingers, Kundu-Manjal Corms, Manjal-Kayiru & Pongal Manjal-Kothu\n\nAcross the Tamil ritual and culinary calendar, *Curcuma longa* is deployed in four distinct physical artifact forms:\n\n**Artifact Typology:**\n1. **Erode Virali-Manjal (Polished Finger Rhizomes)**: Smooth, golden-yellow cylindrical fingers ($5\\text{--}9\\text{ cm}$ long, $1.2\\text{--}1.8\\text{ cm}$ thick) from the *Chinnavedanpatti* and *Erode Local* landraces. When broken, the interior exhibits a glossy, horn-like reddish-orange fracture (*கண்ணாடிப் பதம்*) with $>4\\%$ curcuminoid content.\n2. **Kundu-Manjal / Kilangu-Manjal (Ovoid Mother Bulbs)**: Plump, conical-ovoid corms carried in auspicious *thamboolam* betel trays, rubbed on sandstone discs for facial application, and tied to yellow threads as protective wrist amulets (*kappu*) before weddings and temple vows.\n3. **Manjal-Kayiru (9-Strand Auspicious Cotton Cords)**: Unbleached hand-spun cotton yarn plied into nine symbolic strands (*navapuri*), dipped repeatedly in boiled *virali-manjal* paste, and shade-dried for threading the gold *thaali* emblems.\n4. **Manjal-Kothu (Leafy Whole-Plant Harvest Bundles)**: Uprooted in *Margazhi–Thai* with the entire $60\\text{ cm}$ pseudostem, broad lance-shaped green leaves, and mud-washed fresh rhizome cluster intact, tied as a fragrant collar around the neck of the *Pongal* boiling pot."
    },
    {
        "slug": "artifact-kunguma-chimizh-caskets-manjal-kopparai-boilers-and-rotary-polishing-drums",
        "category": "artifact",
        "file": "artifact-kunguma-chimizh-caskets-manjal-kopparai-boilers-and-rotary-polishing-drums.md",
        "name_en": "Kunguma-Chimizh Vermilion Caskets, Manjal-Kopparai Perforated Boilers & Rotary Polishing Drums",
        "name_ta": "குங்குமச் சிமிழ்கள், மஞ்சள் அவிக்கும் துளைக் கொப்பரைகள் மற்றும் சுழல் மெருகேற்றும் உருளைகள்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Craft vessels and agricultural machinery of the Tamil turmeric-kungumam complex: lathe-turned silver, brass, horn, and lac-wood Kunguma-Chimizh boxes and mango-shaped threshold caskets, perforated iron Manjal-Kopparai boiling vats, and hand-cranked hexagonal expanded-metal polishing drums.",
        "summary_ta": "குங்குமம் மற்றும் மஞ்சள் சார்ந்த பயன்பாட்டுக் கருவிகள்: வெள்ளி, பித்தளை மற்றும் மரத்தாலான குங்குமச் சிமிழ்கள், மஞ்சள் வேகவைக்கும் துளையிட்ட இரும்பு கொப்பரைகள் மற்றும் தோல் நீக்கும் அறுகோணச் சுழல் உருளைகள்.",
        "sources": [
            "South Indian Decorative Metalwork: Kunguma Chimizh & Thamboolam Trays",
            "Farm Machinery and Processing Equipment of Tamil Nadu",
            "Government Museum Chennai Decorative Arts Catalog"
        ],
        "content": "# Kunguma-Chimizh Caskets, Manjal-Kopparai Boilers & Rotary Polishing Drums\n\nFrom the agro-processing threshing floor to the household altar (*pooja-arai*), specialized containers and mechanical vessels govern the handling of turmeric and *kungumam*:\n\n**1. Domestic & Liturgical Caskets (*Kunguma-Chimizh*):**\n- **Turned & Repoussé Chimizh**: Miniature lidded boxes crafted in silver, high-tin bronze, brass, buffalo horn, sandalwood, or lac-turned wood, shaped like lotus buds (*thamarai-மொட்டு*), mangoes (*maangaai*), or peacocks. Every visitor crossing a Tamil threshold is offered the dual-cup *manjal-kunguma* tray (*இரட்டைச் சிமிழ்*) to apply a cooling dot at the glabella (*ajna* point).\n\n**2. Post-Harvest Curing Apparatus:**\n- **Manjal-Kopparai (Perforated Immersion Troughs)**: Heavy-gauge iron pans fitted with lifting handles and hundreds of $6\\text{ mm}$ perforations along the bottom and walls, allowing boiling alkaline water and steam from the underlying masonry furnace (*அடுப்புத் தொட்டி*) to circulate through $100\\text{ kg}$ batches of green rhizomes and drain rapidly when hoisted.\n- **Rotary Polishing Drums (*Manjal-Theikkum Urulai*)**: Horizontal hexagonal or octagonal barrels mounted on a central iron axle with rough internal grating plates; rotating the drum at $30\\text{ rpm}$ scuffs off dried cork skin by mutual rhizome-to-rhizome friction."
    },
    {
        "slug": "institution-erode-manjal-mundi-commission-guilds-and-underground-manjal-kuzhi-granaries",
        "category": "institution",
        "file": "institution-erode-manjal-mundi-commission-guilds-and-underground-manjal-kuzhi-granaries.md",
        "name_en": "Erode Manjal-Mundi Merchant Guilds, Closed-Bid Auction Systems & Underground Manjal-Kuzhi Granaries",
        "name_ta": "ஈரோடு மஞ்சள் மண்டி வணிகர் சங்கங்கள், இரகசிய ஏல முறை மற்றும் நிலத்தடி மஞ்சள் குழிச் சேமிப்பு மரபு",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Commercial and storage institutions of the Kongu Nadu turmeric economy: hereditary Manjal-Mundi commission guilds and regulated market yards in Erode grading finger and bulb lots by fracture color and bulk density, paired with anaerobic bottle-shaped underground storage pits (manjal-kuzhi) lined with paddy straw and vengai leaves.",
        "summary_ta": "கொங்கு நாட்டு மஞ்சள் வணிக அமைப்புகள்: விரலி மற்றும் கிழங்கு மஞ்சளின் அடர்த்தி, நிறம் கொண்டு தரம் பிரிக்கும் ஈரோடு மஞ்சள் மண்டி வணிகர் சங்கங்களும், வேங்கை இலை மற்றும் வைக்கோல் பரப்பிப் பல ஆண்டுகள் மஞ்சளைப் பாதுகாக்கும் நிலத்தடி மஞ்சள் குழிகளும்.",
        "sources": [
            "Coimbatore & Erode District Gazetteers (Trade & Commerce)",
            "Traditional Underground Storage Structures of Kongu Nadu (Manjal-Kuzhi)",
            "Agricultural Produce Marketing Committee Records: Erode Turmeric"
        ],
        "content": "# Erode Manjal-Mundi Merchant Guilds & Underground Manjal-Kuzhi Granaries\n\nBecause turmeric harvest is concentrated in *Thai–Masi* (January–March) while domestic, pharmaceutical, and export demand spans the entire year, Kongu Nadu farmers and merchants developed specialized storage and market institutions:\n\n**1. Underground Hermetic Storage Pits (*Manjal-Kuzhi*):**\n- **Pit Architecture**: Excavated in elevated, well-drained red gravelly soil (*செம்மண் மேடு*) around Erode, Kodumudi, and Modakurichi, a *manjal-kuzhi* is a flask-shaped subterranean chamber $3\\text{--}4.5\\text{ m}$ deep with a narrow circular mouth ($60\\text{ cm}$ wide) and a bellied floor holding $50\\text{--}150\\text{ bags}$ of cured *virali-manjal*.\n- **Anaerobic Bio-Lining**: The pit walls are cushioned with a $20\\text{ cm}$ mattress of twisted paddy straw (*புரிமனை / வைக்கோல்*), dried sugarcane trash, and insecticidal *vengai* (*Pterocarpus marsupium*) or neem leaves, then sealed airtight at the neck with a stone slab and cow-dung clay plaster. Respiration of the stored rhizomes depletes $\\text{O}_2$ and elevates $\\text{CO}_2$, suffocating cigarette beetles (*Lasioderma serricorne*) while aging the turmeric for 2–3 years into prized, high-value *Pazhaya-Manjal*.\n\n**2. Manjal-Mundi Guilds & Fracture Grading:**\n- At the Erode *Manjal-Mundi* yards (Semmampalayam, Perundurai, and Karungalpalayam), expert graders snap sample fingers to inspect the vitreous orange core, measure litre-weight density, and conduct daily auctions separating culinary *virali*, seed *kilangu*, and industrial *pols*."
    },
    {
        "slug": "place-erode-ancient-kongu-manjal-turmeric-curing-and-trade-haven",
        "category": "place",
        "file": "place-erode-ancient-kongu-manjal-turmeric-curing-and-trade-haven.md",
        "name_en": "Erode: Ancient Kongu Kaveri-Bhavani Canal Belt & GI Manjal Turmeric Curing Haven",
        "name_ta": "ஈரோடு (மஞ்சள் மாநகரம்) - காவிரி-பவானி காலிங்கராயன் பாசனப் பகுதியும் புவிசார் குறியீடு பெற்ற மஞ்சள் வணிகத் தளமும்",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic agrarian and mercantile hub in the Kongu Nadu basin at the confluence belt of the Kaveri and Bhavani rivers (lat 11.3410, lng 77.7170, thinai: marutham), watered by the 13th-century Kalingarayan Canal and celebrated with a Geographical Indication (GI) tag for its high-curcumin Erode Virali-Manjal curing yards and trade mundis.",
        "summary_ta": "காவிரி மற்றும் பவானி ஆறுகள் பாயும் கொங்கு நாட்டின் ஈரோடு (lat 11.3410, lng 77.7170, மருதத் திணை): 13-ஆம் நூற்றாண்டு காலிங்கராயன் கால்வாய்ப் பாசனமும், அதிக குர்குமின் சத்துள்ள புவிசார் குறியீடு பெற்ற ஈரோடு விரலி மஞ்சள் களங்களும் நிறைந்த வரலாற்றுத் தளம்.",
        "sources": [
            "Geographical Indication Journal No. 114: Erode Manjal",
            "Kalingarayan Canal Inscriptions & Kongu Nadu Irrigation History",
            "Coimbatore / Erode District Manual (F.A. Nicholson)"
        ],
        "content": "# Erode: Ancient Kongu Kaveri-Bhavani Canal Belt & GI Manjal Haven\n\nSituated at `lat 11.3410, lng 77.7170` on the fertile *Marutham* plains of the Kaveri and Bhavani river basin in Kongu Nadu (flanked by Kodumudi, Bhavani, Perundurai, and Gobichettipalayam), Erode—popularly known across Tamil Nadu as *Manjal Maanagaram* (Turmeric City)—is one of the world's foremost historical centers for *Curcuma longa* cultivation, curing, and trade:\n\n**Hydro-Edaphic & Varietal Distinction:**\n- **Kalingarayan & Thadapalli-Arakkankottai Canal Alluvium**: Irrigated since $1283\\text{ CE}$ by Kongu chieftain Kalingarayan's $90\\text{ km}$ gravity canal linking the Bhavani to the Noyyal, Erode's friable red calcareous sandy-loam soils (*செம்மண் வண்டல்*) provide ideal root aeration and potassium availability for 10-month long-duration turmeric crops.\n- **GI-Tagged Erode Manjal Ecotypes**: Local ecotypes (*Chinnavedanpatti*, *Perundurai*, and *PTS-8*) produce long, stout, constriction-free *virali* fingers with high dry-recovery ($20\\text{--}23\\%$), $3.8\\text{--}5.0\\%$ curcuminoid content, and exceptional resistance to rotting during storage, anchoring a centuries-old network of curing yards, underground *manjal-kuzhi* granaries, and wholesale *mundis*."
    }
]

EDGES = [
    [
        "text-sangam-and-bhakti-literature-on-pasu-manjal-turmeric-pastes-and-festive-thresholds",
        "describes",
        "artifact-virali-manjal-fingers-kundu-manjal-bulbs-manjal-kayiru-cords-and-pongal-kothu",
        "material_culture",
        "Sangam to Bhakti Era",
        "Pattinappalai, Malaipadukadam, and Nedunalvadai celebrate backyard pasu-manjal gardens, turmeric pastes, and threshold festoons.",
        "Pattinappalai & Nedunalvadai"
    ],
    [
        "text-sangam-and-bhakti-literature-on-pasu-manjal-turmeric-pastes-and-festive-thresholds",
        "codifies",
        "concept-auspicious-manjal-antiseptic-hygiene-mangalsutra-cord-dyeing-and-aarathi-prophylaxis",
        "material_culture",
        "Sangam to Modern Era",
        "Classical poetic traditions establish turmeric paste and manjal-neerattu as emblems of domestic auspiciousness and antimicrobial protection.",
        "Tiruppavai & Akananuru"
    ],
    [
        "concept-curcuma-longa-virali-and-kilangu-botany-curcuminoid-tautomerism-and-turmerone",
        "characterizes",
        "artifact-virali-manjal-fingers-kundu-manjal-bulbs-manjal-kayiru-cords-and-pongal-kothu",
        "material_culture",
        "Sangam to Modern Era",
        "Diarylheptanoid curcuminoids and ar-turmerone essential oils distinguish oleoresin-rich virali-manjal fingers from starchy kundu-manjal mother bulbs.",
        "Siddha Gunapadam"
    ],
    [
        "concept-curcuma-longa-virali-and-kilangu-botany-curcuminoid-tautomerism-and-turmerone",
        "underpins",
        "technology-manjal-kopparai-alkaline-boiling-starch-gelatinization-and-rotary-polishing",
        "material_culture",
        "Early Medieval to Modern Era",
        "Intracellular starch granules and oleoresin cells require alkaline boiling at 95–100°C to diffuse golden curcuminoids uniformly across the rhizome.",
        "TNAU Post-Harvest Monograph"
    ],
    [
        "concept-alkaline-lime-borax-deprotonation-chemistry-of-crimson-kungumam-transformation",
        "drives",
        "technology-thaazhampoo-kungumam-vat-steeping-sun-evaporation-and-sesame-oil-stabilization",
        "material_culture",
        "Medieval to Modern Era",
        "Alkaline deprotonation of curcumin by slaked lime and borax shifts optical absorption from 420 nm yellow to 530 nm crimson during Kungumam vat steeping.",
        "Spectroscopic Curcumin Studies"
    ],
    [
        "concept-auspicious-manjal-antiseptic-hygiene-mangalsutra-cord-dyeing-and-aarathi-prophylaxis",
        "utilizes",
        "artifact-virali-manjal-fingers-kundu-manjal-bulbs-manjal-kayiru-cords-and-pongal-kothu",
        "material_culture",
        "Sangam to Modern Era",
        "Antiseptic threshold washing, wedding manjal-kayiru cord dyeing, and Pongal pot collars employ virali fingers, kundu bulbs, and fresh manjal-kothu.",
        "Tamil Folklore Studies"
    ],
    [
        "technology-manjal-kopparai-alkaline-boiling-starch-gelatinization-and-rotary-polishing",
        "employs",
        "artifact-kunguma-chimizh-caskets-manjal-kopparai-boilers-and-rotary-polishing-drums",
        "material_culture",
        "Early Medieval to Modern Era",
        "Post-harvest curing relies on perforated iron manjal-kopparai immersion troughs and hexagonal rotary polishing drums.",
        "Erode GI Dossier"
    ],
    [
        "technology-thaazhampoo-kungumam-vat-steeping-sun-evaporation-and-sesame-oil-stabilization",
        "fills",
        "artifact-kunguma-chimizh-caskets-manjal-kopparai-boilers-and-rotary-polishing-drums",
        "material_culture",
        "Medieval to Modern Era",
        "Oil-conditioned crimson Thaazhampoo Kungumam is stored and offered in lathe-turned silver, brass, and wood kunguma-chimizh caskets.",
        "Decorative Arts Catalog"
    ],
    [
        "institution-erode-manjal-mundi-commission-guilds-and-underground-manjal-kuzhi-granaries",
        "grades_and_stores",
        "artifact-virali-manjal-fingers-kundu-manjal-bulbs-manjal-kayiru-cords-and-pongal-kothu",
        "material_culture",
        "Medieval to Modern Era",
        "Erode Manjal-Mundi guilds grade cured virali fingers by vitreous fracture and age surplus harvests in straw-lined underground manjal-kuzhi pits.",
        "Erode District Gazetteer"
    ],
    [
        "institution-erode-manjal-mundi-commission-guilds-and-underground-manjal-kuzhi-granaries",
        "flourishes_in",
        "place-erode-ancient-kongu-manjal-turmeric-curing-and-trade-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Hereditary turmeric commission mundis and subterranean storage granaries center on Erode along the Kalingarayan Canal belt.",
        "GI Journal No. 114"
    ]
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=== Phase 1: Markdown Dossiers ===")
    for d in DOSSIERS:
        cat_dir = os.path.join(DOSSIER_DIR, category_dir(d["category"]))
        os.makedirs(cat_dir, exist_ok=True)
        filepath = os.path.join(cat_dir, d["file"])
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"Wrote dossier: {filepath}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=== Phase 2: Lore Nodes Upsert ===")
    for d in DOSSIERS:
        props = json.dumps({"category": d["category"], "canonical_file": d["file"]})
        cur.execute("""
            INSERT INTO lore_nodes (slug, node_type, name_en, name_ta, era, year_start, year_end, thinai, summary_en, summary_ta, sources, layer, properties)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                sources = EXCLUDED.sources,
                layer = EXCLUDED.layer,
                properties = EXCLUDED.properties;
        """, (
            d["slug"], d["category"], d["name_en"], d["name_ta"], d["era"],
            d["year_start"], d["year_end"], d["thinai"], d["summary_en"],
            d["summary_ta"], d["sources"], "material_culture", props
        ))
        print(f"Upserted node: {d['slug']}")
    conn.commit()

    print("=== Phase 3: Lore Edges Insert ===")
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, ev = edge
        cur.execute("""
            SELECT 1 FROM lore_edges
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s
        """, (src, rel, tgt))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO lore_edges (source_slug, relation_type, target_slug, layer, era, description, evidence_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (src, rel, tgt, layer, era, desc, ev))
            print(f"Inserted edge: {src} -> {tgt} ({rel})")
        else:
            print(f"Edge exists: {src} -> {tgt} ({rel})")
    conn.commit()

    print("=== Phase 4: RAG Chunks Embedding ===")
    for d in DOSSIERS:
        title = d["name_en"]
        slug = d["slug"]
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s", (slug,))
        text_en = d["summary_en"] + " " + d["content"][:800]
        emb_en = get_embedding(text_en)
        cur.execute("""
            INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (slug, d["category"], "en", title + " (Overview)", text_en, d["sources"][0] if d["sources"] else "Oral Tradition", emb_en))

        text_ta = d["summary_ta"] + " " + d["name_ta"]
        emb_ta = get_embedding(text_ta)
        cur.execute("""
            INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (slug, d["category"], "ta", d["name_ta"] + " (கண்ணோட்டம்)", text_ta, d["sources"][0] if d["sources"] else "Oral Tradition", emb_ta))
        print(f"Embedded 2 chunks for: {slug}")
    conn.commit()

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
